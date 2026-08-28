"""
M-Vave BlackBox USB MIDI SysEx transport for macOS (CoreMIDI via ctypes).

Protocol derived from documentation by Joel Victor (CC BY-SA 4.0),
https://github.com/jvsobrinho/mvave-blackbox-ble , and from reference logic in
https://github.com/jvsobrinho/mvave-blackbox-edit (MIT).

SAFETY: this module refuses to transmit anything that is not one of the four
read-only commands on the allowlist below. Any packet whose header is not
00 59 23 (Flash/Polling READ header) or whose command type is not 0x08 is
rejected with a RuntimeError before it reaches CoreMIDI.

pyobjc's CoreMIDI bindings do not export MIDISend/MIDISendSysex/MIDIPacketList
helpers (verified on pyobjc 12.2.2 on this machine), so we bind CoreMIDI with
ctypes directly.
"""

import ctypes
import ctypes.util
import threading
import time

# ---------------------------------------------------------------- codec

def encode_base128(data: bytes) -> bytes:
    """Continuous 8-to-7 bit packing, LSB-first. 7 raw bytes -> 8 payload bytes."""
    out, accum, bits = [], 0, 0
    for b in data:
        accum |= b << bits
        bits += 8
        while bits >= 7:
            out.append(accum & 0x7F)
            accum >>= 7
            bits -= 7
    out.append(accum & 0x7F)
    return bytes(out)


def decode_base128(enc: bytes) -> bytes:
    out, accum, bits = [], 0, 0
    for b in enc:
        accum |= b << bits
        bits += 7
        if bits >= 8:
            out.append(accum & 0xFF)
            accum >>= 8
            bits -= 8
    return bytes(out)


def checksum(payload) -> int:
    """0xFF - (sum of bytes offset 4 .. N-2), masked. As documented (CC BY-SA doc)."""
    return (0xFF - (sum(payload[4:len(payload) - 1]) & 0xFF)) & 0xFF


def checksum_rx(payload) -> int:
    """0xFF - (sum of bytes offset 5 .. N-2), masked.

    EMPIRICAL CORRECTION measured on this device: the string-block replies
    (00 59 23 20 01 00 05 ...) carry byte[4] = 0x01 and their stored checksum
    only validates when the sum starts at offset 5, not offset 4. Every packet
    in the published documentation has byte[4] == 0x00, which makes the two
    formulas indistinguishable there. Offset 5 validates 100% of observed
    traffic (107-byte dumps, 19-byte preset sync, 295-byte name blocks).
    """
    return (0xFF - (sum(payload[5:len(payload) - 1]) & 0xFF)) & 0xFF


def build_packet(hex_or_bytes) -> bytes:
    """Parse a hex string / bytes and overwrite the final byte with the checksum."""
    if isinstance(hex_or_bytes, str):
        b = bytearray.fromhex(hex_or_bytes.replace(" ", ""))
    else:
        b = bytearray(hex_or_bytes)
    b[-1] = checksum(b)
    return bytes(b)


def hexs(b) -> str:
    return bytes(b).hex(" ").upper()


# ---------------------------------------------------------------- safety

READ_HEADER = bytes([0x00, 0x59, 0x23])
WRITE_HEADER_FORBIDDEN = bytes([0x00, 0x59, 0x22])


def assert_read_only(raw: bytes):
    """Hard gate. Only the four documented read-only commands may leave this process."""
    if len(raw) < 15:
        raise RuntimeError(f"REFUSED: packet too short: {hexs(raw)}")
    if raw[0:3] == WRITE_HEADER_FORBIDDEN:
        raise RuntimeError(
            f"REFUSED: 00 59 22 is the RAM WRITE header. Never send. {hexs(raw)}")
    if raw[0:3] != READ_HEADER:
        raise RuntimeError(f"REFUSED: header is not 00 59 23: {hexs(raw)}")
    if raw[3] != 0x08:
        raise RuntimeError(
            f"REFUSED: command type 0x{raw[3]:02X} is not the read command 0x08: {hexs(raw)}")
    if raw[4:6] != b"\x00\x00" or raw[6] not in (0x04, 0x05):
        raise RuntimeError(f"REFUSED: routing must be 00 00 04 or 00 00 05: {hexs(raw)}")
    if raw[-1] != checksum(raw):
        raise RuntimeError(f"REFUSED: bad checksum: {hexs(raw)}")
    return True


# read-only command builders -------------------------------------------------

def cmd_ram_dump() -> bytes:
    return build_packet("00 59 23 08 00 00 04 00 00 00 10 5C 00 00 00")


def cmd_preset_sync() -> bytes:
    return build_packet("00 59 23 08 00 00 04 00 00 00 20 04 00 00 00")


def cmd_read_flash_preset(index: int) -> bytes:
    addr = index * 92
    a = addr.to_bytes(4, "little")
    return build_packet(bytes([0x00, 0x59, 0x23, 0x08, 0x00, 0x00, 0x04]) + a +
                        bytes([0x5C, 0x00, 0x00, 0x00]))


AMP_NAMES_ADDR = bytes([0x90, 0x18, 0x01, 0x00])
CAB_NAMES_ADDR = bytes([0x80, 0x18, 0x01, 0x00])


def cmd_read_string_block(addr4: bytes) -> bytes:
    return build_packet(bytes([0x00, 0x59, 0x23, 0x08, 0x00, 0x00, 0x05,
                               0x00, 0x00, 0x00]) + addr4 + bytes([0x00]))


# --- generalized read primitive -------------------------------------------
# CONFIRMED on 14/14 packets observed on this device. All four documented read
# commands are one memory-mapped read:
#     magic(3) | len LE16 = payload+8 | space LE16 | address LE32 | size LE24
# Address map: 0x00000000 + i*92 preset slot, 0x10000000 live RAM,
#              0x20000000 current preset id, 0x80000000 CAB names,
#              0x90000000 AMP names.  Spaces: 0x0400 params, 0x0500 strings.

SPACE_PARAM = 0x0400
SPACE_STRING = 0x0500

ADDR_PRESET_BASE = 0x00000000
ADDR_LIVE_RAM = 0x10000000
ADDR_CURRENT_PRESET = 0x20000000
ADDR_CAB_NAMES = 0x80000000
ADDR_AMP_NAMES = 0x90000000

NAME_STRIDE = 14      # CONFIRMED: 20 records x 14 bytes = 280-byte name table
NAME_COUNT = 20
PRESET_SIZE = 92


def cmd_read(address: int, size: int, space: int = SPACE_PARAM) -> bytes:
    """Build a generic read request. Read-only by construction (magic 00 59 23)."""
    p = bytearray(b"\x00\x59\x23")
    p += (0 + 8).to_bytes(2, "little")          # no payload on a request
    p += space.to_bytes(2, "little")
    p += address.to_bytes(4, "little")
    p += size.to_bytes(3, "little")
    p += b"\x00"                                 # checksum placeholder
    return build_packet(bytes(p))


def parse_reply(pkt: bytes):
    """Split a decoded reply into its fields. Returns a dict."""
    return dict(magic=pkt[0:3],
                length=int.from_bytes(pkt[3:5], "little"),
                space=int.from_bytes(pkt[5:7], "little"),
                address=int.from_bytes(pkt[7:11], "little"),
                size=int.from_bytes(pkt[11:14], "little"),
                payload=pkt[14:-1],
                checksum=pkt[-1],
                checksum_ok=(pkt[-1] == checksum_rx(pkt)))


# ---------------------------------------------------------------- CoreMIDI

_cm = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
_cf = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")

kCFStringEncodingUTF8 = 0x08000100

_cf.CFStringCreateWithCString.restype = ctypes.c_void_p
_cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
_cf.CFStringGetCString.restype = ctypes.c_bool
_cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                   ctypes.c_long, ctypes.c_uint32]
_cf.CFRelease.argtypes = [ctypes.c_void_p]

MIDIObjectRef = ctypes.c_uint32

_cm.MIDIClientCreate.restype = ctypes.c_int32
_cm.MIDIClientCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.POINTER(MIDIObjectRef)]
_cm.MIDIOutputPortCreate.restype = ctypes.c_int32
_cm.MIDIOutputPortCreate.argtypes = [MIDIObjectRef, ctypes.c_void_p,
                                     ctypes.POINTER(MIDIObjectRef)]
MIDIReadProc = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_cm.MIDIInputPortCreate.restype = ctypes.c_int32
_cm.MIDIInputPortCreate.argtypes = [MIDIObjectRef, ctypes.c_void_p, MIDIReadProc,
                                    ctypes.c_void_p, ctypes.POINTER(MIDIObjectRef)]
_cm.MIDIPortConnectSource.restype = ctypes.c_int32
_cm.MIDIPortConnectSource.argtypes = [MIDIObjectRef, MIDIObjectRef, ctypes.c_void_p]
_cm.MIDIGetNumberOfSources.restype = ctypes.c_ulong
_cm.MIDIGetNumberOfDestinations.restype = ctypes.c_ulong
_cm.MIDIGetSource.restype = MIDIObjectRef
_cm.MIDIGetSource.argtypes = [ctypes.c_ulong]
_cm.MIDIGetDestination.restype = MIDIObjectRef
_cm.MIDIGetDestination.argtypes = [ctypes.c_ulong]
_cm.MIDIObjectGetStringProperty.restype = ctypes.c_int32
_cm.MIDIObjectGetStringProperty.argtypes = [MIDIObjectRef, ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_void_p)]
_cm.MIDIClientDispose.argtypes = [MIDIObjectRef]
_cm.MIDIPortDispose.argtypes = [MIDIObjectRef]


class MIDISysexSendRequest(ctypes.Structure):
    _fields_ = [
        ("destination", MIDIObjectRef),
        ("data", ctypes.c_void_p),
        ("bytesToSend", ctypes.c_uint32),
        ("complete", ctypes.c_ubyte),
        ("reserved", ctypes.c_ubyte * 3),
        ("completionProc", ctypes.c_void_p),
        ("completionRefCon", ctypes.c_void_p),
    ]


_cm.MIDISendSysex.restype = ctypes.c_int32
_cm.MIDISendSysex.argtypes = [ctypes.POINTER(MIDISysexSendRequest)]


def _cfstr(s: str):
    return ctypes.c_void_p(_cf.CFStringCreateWithCString(None, s.encode(), kCFStringEncodingUTF8))


def _prop(obj, name: str):
    key = _cfstr(name)
    out = ctypes.c_void_p()
    st = _cm.MIDIObjectGetStringProperty(obj, key, ctypes.byref(out))
    _cf.CFRelease(key)
    if st != 0 or not out.value:
        return None
    buf = ctypes.create_string_buffer(512)
    ok = _cf.CFStringGetCString(out, buf, 512, kCFStringEncodingUTF8)
    _cf.CFRelease(out)
    return buf.value.decode("utf-8", "replace") if ok else None


def list_endpoints():
    """Return (sources, destinations); each entry is a dict."""
    src, dst = [], []
    for i in range(_cm.MIDIGetNumberOfSources()):
        e = _cm.MIDIGetSource(i)
        src.append(dict(index=i, ref=e, name=_prop(e, "name"),
                        display=_prop(e, "displayName"),
                        manufacturer=_prop(e, "manufacturer")))
    for i in range(_cm.MIDIGetNumberOfDestinations()):
        e = _cm.MIDIGetDestination(i)
        dst.append(dict(index=i, ref=e, name=_prop(e, "name"),
                        display=_prop(e, "displayName"),
                        manufacturer=_prop(e, "manufacturer")))
    return src, dst


# ---------------------------------------------------------------- device

class BlackBox:
    """USB MIDI SysEx transport. Read-only commands only."""

    MANUFACTURER = "Jieli Technology"

    def __init__(self, verbose=True, log=None):
        self.verbose = verbose
        self.log_lines = log if log is not None else []
        self._client = MIDIObjectRef()
        self._outport = MIDIObjectRef()
        self._inport = MIDIObjectRef()
        self._dest = None
        self._src = None
        self._lock = threading.Lock()
        self._stream = bytearray()      # raw bytes as they arrive from CoreMIDI
        self.sysex_msgs = []            # completed F0..F7 messages (with markers)
        self.decoded_msgs = []          # base128-decoded raw 00 59 .. packets
        self._keepalive = []            # keep ctypes buffers alive

    # -- logging
    def _log(self, s):
        self.log_lines.append(s)
        if self.verbose:
            print(s, flush=True)

    # -- lifecycle
    def open(self):
        srcs, dsts = list_endpoints()
        cand_d = [d for d in dsts if (d["manufacturer"] or "") == self.MANUFACTURER]
        cand_s = [s for s in srcs if (s["manufacturer"] or "") == self.MANUFACTURER]
        if not cand_d or not cand_s:
            raise RuntimeError(
                f"BlackBox endpoints not found by manufacturer {self.MANUFACTURER!r}.\n"
                f"sources={srcs}\ndestinations={dsts}")
        self._dest = cand_d[0]
        self._src = cand_s[0]
        self._log(f"[MIDI] destination ref={self._dest['ref']} "
                  f"display={self._dest['display']!r} mfr={self._dest['manufacturer']!r}")
        self._log(f"[MIDI] source      ref={self._src['ref']} "
                  f"display={self._src['display']!r} mfr={self._src['manufacturer']!r}")

        name = _cfstr("blackbox-probe")
        st = _cm.MIDIClientCreate(name, None, None, ctypes.byref(self._client))
        if st != 0:
            raise RuntimeError(f"MIDIClientCreate failed: {st}")
        st = _cm.MIDIOutputPortCreate(self._client, _cfstr("out"),
                                      ctypes.byref(self._outport))
        if st != 0:
            raise RuntimeError(f"MIDIOutputPortCreate failed: {st}")

        self._readproc = MIDIReadProc(self._on_packets)   # keep ref alive
        st = _cm.MIDIInputPortCreate(self._client, _cfstr("in"), self._readproc,
                                     None, ctypes.byref(self._inport))
        if st != 0:
            raise RuntimeError(f"MIDIInputPortCreate failed: {st}")
        st = _cm.MIDIPortConnectSource(self._inport, MIDIObjectRef(self._src["ref"]), None)
        if st != 0:
            raise RuntimeError(f"MIDIPortConnectSource failed: {st}")
        _cf.CFRelease(name)
        return self

    def close(self):
        try:
            if self._inport:
                _cm.MIDIPortDispose(self._inport)
            if self._outport:
                _cm.MIDIPortDispose(self._outport)
            if self._client:
                _cm.MIDIClientDispose(self._client)
        except Exception:
            pass

    def __enter__(self):
        return self.open()

    def __exit__(self, *a):
        self.close()

    # -- receive
    def _on_packets(self, pktlist, refcon, srcrefcon):
        """MIDIReadProc. Runs on a CoreMIDI thread. Parses a packed MIDIPacketList."""
        try:
            base = ctypes.cast(pktlist, ctypes.POINTER(ctypes.c_ubyte))
            num = ctypes.cast(pktlist, ctypes.POINTER(ctypes.c_uint32))[0]
            off = 4  # MIDIPacketList: UInt32 numPackets, then packet[] (pack(4))
            chunks = []
            for _ in range(num):
                length = ctypes.cast(ctypes.addressof(base.contents) + off + 8,
                                     ctypes.POINTER(ctypes.c_uint16))[0]
                data = bytes(bytearray(base[off + 10: off + 10 + length]))
                chunks.append(data)
                # MIDIPacketNext on arm64: round (&data[length]) up to 4 bytes
                off = (off + 10 + length + 3) & ~3
            with self._lock:
                for c in chunks:
                    self._stream.extend(c)
                self._extract_sysex_locked()
        except Exception as e:  # never raise into CoreMIDI
            self.log_lines.append(f"[READPROC ERROR] {e!r}")

    def _extract_sysex_locked(self):
        while True:
            try:
                i = self._stream.index(0xF0)
            except ValueError:
                self._stream.clear()
                return
            try:
                j = self._stream.index(0xF7, i)
            except ValueError:
                del self._stream[:i]
                return
            msg = bytes(self._stream[i:j + 1])
            del self._stream[:j + 1]
            self.sysex_msgs.append(msg)
            self.decoded_msgs.append(decode_base128(msg[1:-1]))

    def reset_rx(self):
        with self._lock:
            self._stream.clear()
            self.sysex_msgs = []
            self.decoded_msgs = []

    def rx(self):
        with self._lock:
            return list(self.sysex_msgs), list(self.decoded_msgs)

    # -- send
    def send_raw(self, raw: bytes, label=""):
        assert_read_only(raw)                       # hard gate
        enc = encode_base128(raw)
        sysex = bytes([0xF0]) + enc + bytes([0xF7])
        self._log(f"[OUT RAW  ]{(' ' + label) if label else ''} {hexs(raw)}")
        self._log(f"[OUT SYSEX] {hexs(sysex)}")

        buf = ctypes.create_string_buffer(sysex, len(sysex))
        req = MIDISysexSendRequest()
        req.destination = MIDIObjectRef(self._dest["ref"])
        req.data = ctypes.cast(buf, ctypes.c_void_p)
        req.bytesToSend = len(sysex)
        req.complete = 0
        req.completionProc = None
        req.completionRefCon = None
        self._keepalive.append((buf, req))
        st = _cm.MIDISendSysex(ctypes.byref(req))
        if st != 0:
            raise RuntimeError(f"MIDISendSysex failed: {st}")
        t0 = time.time()
        while not req.complete and time.time() - t0 < 2.0:
            time.sleep(0.005)
        self._log(f"[OUT DONE ] complete={bool(req.complete)} "
                  f"remaining={req.bytesToSend} in {time.time()-t0:.3f}s")
        return sysex

    def request(self, raw: bytes, label="", timeout=3.0, quiet_for=0.6, want=None):
        """Send a read command and collect notifications.

        Stops early when `want(decoded_msgs)` is truthy, otherwise when the link
        has been quiet for `quiet_for` seconds, otherwise at `timeout`.
        """
        self.reset_rx()
        self.send_raw(raw, label)
        t0 = time.time()
        last_n, last_change = 0, time.time()
        while time.time() - t0 < timeout:
            time.sleep(0.02)
            _, dec = self.rx()
            if len(dec) != last_n:
                last_n, last_change = len(dec), time.time()
            if want and want(dec):
                break
            if last_n and time.time() - last_change > quiet_for:
                break
        sx, dec = self.rx()
        for k, (s, d) in enumerate(zip(sx, dec)):
            self._log(f"[IN  SYSEX {k}] ({len(s)}B) {hexs(s)}")
            self._log(f"[IN  RAW   {k}] ({len(d)}B) {hexs(d)}")
        if not sx:
            self._log("[IN] (nothing received)")
        return sx, dec


# ---------------------------------------------------------------- name parsing

def parse_names(payload: bytes):
    """Split a null-terminated ASCII name dictionary. Returns [(raw, clean), ...]."""
    names, cur = [], ""
    for b in payload:
        if b == 0x00:
            if cur.strip():
                names.append(cur)
            cur = ""
        elif 32 <= b <= 126:
            cur += chr(b)
    if cur.strip():
        names.append(cur)
    return [(n, n.lstrip("0123456789")) for n in names]
