"""USB MIDI SysEx transport for the M-Vave BlackBox on macOS.

CoreMIDI is bound directly with ``ctypes``. pyobjc's CoreMIDI bindings expose
213 ``MIDI*`` symbols on this machine but none of the send helpers
(``MIDISend``, ``MIDISendSysex``, ``MIDIPacketListInit``, ``MIDIPacketListAdd``),
so they cannot transmit at all. ``python-rtmidi`` does not build here. Both are
therefore avoided.

This module is an OPTIONAL import: every command in ``blackboxctl`` that does not
touch the pedal works without it. :func:`open_device` raises
:class:`TransportUnavailable` with a readable explanation when CoreMIDI cannot be
reached.

Safety
------
:meth:`BlackBox.send` refuses to transmit anything that is not one of the
confirmed read-only commands unless the caller passes an explicit
:class:`protocol.WriteConsent`. Even with consent, ``send`` independently
re-checks the frame on the wire: it refuses any ``00 59 22`` frame whose target
address falls in the flash preset array or whose length low byte is ``0x64``
(a 92-byte payload, i.e. a full preset image) unless ``allow_flash`` is set, and
it refuses any write path whose ``hardware_confirmed`` is False.

Every entry in ``protocol.WRITE_PATHS`` currently has
``hardware_confirmed=False``, so **no write frame can reach the wire at all**,
from the CLI or from a REPL. That is enforced here, not in the CLI, so a future
script cannot bypass it by not being the CLI.

Verification status
-------------------
This module is a rewrite of ``scratchpad/proto/midi_transport.py``, which is the
file that actually produced the hardware logs in
``docs/reverse-engineering/device-validation.md``. The protocol facts it encodes
are CONFIRMED; **this file's own send path, MIDIReadProc parser and
request/response matching are INHERITED, not independently re-verified on
hardware.** See STATUS.md for what that blocks.

Attribution: see ../NOTICE. GPL-3.0.
"""

from __future__ import annotations

import ctypes
import threading
import time
from dataclasses import dataclass
from typing import Callable

from . import protocol
from .protocol import Frame, UnsafePacket, assert_read_only, hexs

MANUFACTURER = "Jieli Technology"
"""CoreMIDI kMIDIPropertyManufacturer of the BlackBox.

CONFIRMED on this Mac by the predecessor module
(``scratchpad/proto/midi_transport.py``), which enumerated source and
destination index 0 as ``name='USB Composite Device'``,
``manufacturer='Jieli Technology'``. Not re-verified through THIS module,
because the pedal has been offline (``kMIDIPropertyOffline == 1``, zero
CoreMIDI sources and destinations) every time this module was run.

Endpoint integer refs are NOT stable across replug, so endpoints are always
resolved by this string, never by a hardcoded id.
"""


class TransportUnavailable(RuntimeError):
    """CoreMIDI could not be loaded, or no BlackBox endpoint was found."""


class CorruptReply(RuntimeError):
    """A reply arrived but failed checksum / length / size validation."""


# ---------------------------------------------------------------------------
# CoreMIDI binding
# ---------------------------------------------------------------------------

_CF_ENCODING_UTF8 = 0x08000100
_MIDIObjectRef = ctypes.c_uint32


@dataclass(frozen=True)
class _Frameworks:
    midi: ctypes.CDLL
    cf: ctypes.CDLL


_FRAMEWORKS: _Frameworks | None = None


def _load_frameworks() -> _Frameworks:
    """Load and prototype CoreMIDI + CoreFoundation once."""
    global _FRAMEWORKS
    if _FRAMEWORKS is not None:
        return _FRAMEWORKS
    try:
        midi = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI")
        cf = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    except OSError as exc:                        # pragma: no cover - macOS only
        raise TransportUnavailable(
            "CoreMIDI is unavailable on this system. blackboxctl's device "
            "commands require macOS with CoreMIDI; every other command works "
            f"without it. Underlying error: {exc}") from exc

    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                             ctypes.c_uint32]
    cf.CFStringGetCString.restype = ctypes.c_bool
    cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                      ctypes.c_long, ctypes.c_uint32]
    cf.CFRelease.argtypes = [ctypes.c_void_p]

    midi.MIDIClientCreate.restype = ctypes.c_int32
    midi.MIDIClientCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p,
                                      ctypes.POINTER(_MIDIObjectRef)]
    midi.MIDIOutputPortCreate.restype = ctypes.c_int32
    midi.MIDIOutputPortCreate.argtypes = [_MIDIObjectRef, ctypes.c_void_p,
                                          ctypes.POINTER(_MIDIObjectRef)]
    midi.MIDIInputPortCreate.restype = ctypes.c_int32
    midi.MIDIInputPortCreate.argtypes = [_MIDIObjectRef, ctypes.c_void_p,
                                         _MIDIReadProc, ctypes.c_void_p,
                                         ctypes.POINTER(_MIDIObjectRef)]
    midi.MIDIPortConnectSource.restype = ctypes.c_int32
    midi.MIDIPortConnectSource.argtypes = [_MIDIObjectRef, _MIDIObjectRef,
                                           ctypes.c_void_p]
    midi.MIDIGetNumberOfSources.restype = ctypes.c_ulong
    midi.MIDIGetNumberOfDestinations.restype = ctypes.c_ulong
    midi.MIDIGetSource.restype = _MIDIObjectRef
    midi.MIDIGetSource.argtypes = [ctypes.c_ulong]
    midi.MIDIGetDestination.restype = _MIDIObjectRef
    midi.MIDIGetDestination.argtypes = [ctypes.c_ulong]
    midi.MIDIObjectGetStringProperty.restype = ctypes.c_int32
    midi.MIDIObjectGetStringProperty.argtypes = [_MIDIObjectRef, ctypes.c_void_p,
                                                 ctypes.POINTER(ctypes.c_void_p)]
    midi.MIDISendSysex.restype = ctypes.c_int32
    midi.MIDISendSysex.argtypes = [ctypes.POINTER(_MIDISysexSendRequest)]
    midi.MIDIClientDispose.argtypes = [_MIDIObjectRef]
    midi.MIDIPortDispose.argtypes = [_MIDIObjectRef]

    _FRAMEWORKS = _Frameworks(midi=midi, cf=cf)
    return _FRAMEWORKS


_MIDIReadProc = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.c_void_p)


class _MIDISysexSendRequest(ctypes.Structure):
    _fields_ = [
        ("destination", _MIDIObjectRef),
        ("data", ctypes.c_void_p),
        ("bytesToSend", ctypes.c_uint32),
        ("complete", ctypes.c_ubyte),
        ("reserved", ctypes.c_ubyte * 3),
        ("completionProc", ctypes.c_void_p),
        ("completionRefCon", ctypes.c_void_p),
    ]


def _cfstr(fw: _Frameworks, text: str) -> ctypes.c_void_p:
    return ctypes.c_void_p(
        fw.cf.CFStringCreateWithCString(None, text.encode(), _CF_ENCODING_UTF8))


def _string_property(fw: _Frameworks, obj: int, key: str) -> str | None:
    cfkey = _cfstr(fw, key)
    out = ctypes.c_void_p()
    status = fw.midi.MIDIObjectGetStringProperty(obj, cfkey, ctypes.byref(out))
    fw.cf.CFRelease(cfkey)
    if status != 0 or not out.value:
        return None
    buf = ctypes.create_string_buffer(512)
    ok = fw.cf.CFStringGetCString(out, buf, 512, _CF_ENCODING_UTF8)
    fw.cf.CFRelease(out)
    return buf.value.decode("utf-8", "replace") if ok else None


@dataclass(frozen=True)
class Endpoint:
    """One CoreMIDI source or destination."""

    index: int
    ref: int
    name: str | None
    display: str | None
    manufacturer: str | None

    def describe(self) -> str:
        return (f"index={self.index} ref={self.ref} name={self.name!r} "
                f"display={self.display!r} manufacturer={self.manufacturer!r}")


def list_endpoints() -> tuple[list[Endpoint], list[Endpoint]]:
    """Enumerate (sources, destinations) visible to CoreMIDI."""
    fw = _load_frameworks()
    sources: list[Endpoint] = []
    destinations: list[Endpoint] = []
    for index in range(fw.midi.MIDIGetNumberOfSources()):
        ref = fw.midi.MIDIGetSource(index)
        sources.append(Endpoint(index, ref,
                                _string_property(fw, ref, "name"),
                                _string_property(fw, ref, "displayName"),
                                _string_property(fw, ref, "manufacturer")))
    for index in range(fw.midi.MIDIGetNumberOfDestinations()):
        ref = fw.midi.MIDIGetDestination(index)
        destinations.append(Endpoint(index, ref,
                                     _string_property(fw, ref, "name"),
                                     _string_property(fw, ref, "displayName"),
                                     _string_property(fw, ref, "manufacturer")))
    return sources, destinations


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------


class BlackBox:
    """Open USB MIDI SysEx link to the pedal. Read-only unless explicitly told."""

    def __init__(self, manufacturer: str = MANUFACTURER,
                 on_log: Callable[[str], None] | None = None) -> None:
        self.manufacturer = manufacturer
        self._log_sink = on_log
        self.log_lines: list[str] = []
        self._fw = _load_frameworks()
        self._client = _MIDIObjectRef()
        self._out_port = _MIDIObjectRef()
        self._in_port = _MIDIObjectRef()
        self.source: Endpoint | None = None
        self.destination: Endpoint | None = None
        self._lock = threading.Lock()
        self._stream = bytearray()
        self._sysex: list[bytes] = []
        self._decoded: list[bytes] = []
        self._read_proc: object = None
        self._keepalive: list[object] = []

    # -- logging ----------------------------------------------------------

    def log(self, line: str) -> None:
        self.log_lines.append(line)
        if self._log_sink is not None:
            self._log_sink(line)

    # -- lifecycle --------------------------------------------------------

    def open(self) -> "BlackBox":
        sources, destinations = list_endpoints()
        src = [e for e in sources if (e.manufacturer or "") == self.manufacturer]
        dst = [e for e in destinations
               if (e.manufacturer or "") == self.manufacturer]
        if not src or not dst:
            raise TransportUnavailable(
                f"No MIDI endpoint with manufacturer {self.manufacturer!r} was "
                f"found. Is the BlackBox connected over USB?\n"
                f"  sources:      {[e.describe() for e in sources] or 'none'}\n"
                f"  destinations: {[e.describe() for e in destinations] or 'none'}")
        self.source, self.destination = src[0], dst[0]
        self.log(f"[midi] destination {self.destination.describe()}")
        self.log(f"[midi] source      {self.source.describe()}")

        fw = self._fw
        name = _cfstr(fw, "blackboxctl")
        if fw.midi.MIDIClientCreate(name, None, None,
                                    ctypes.byref(self._client)) != 0:
            raise TransportUnavailable("MIDIClientCreate failed")
        if fw.midi.MIDIOutputPortCreate(self._client, _cfstr(fw, "out"),
                                        ctypes.byref(self._out_port)) != 0:
            raise TransportUnavailable("MIDIOutputPortCreate failed")
        self._read_proc = _MIDIReadProc(self._on_packets)   # must stay referenced
        if fw.midi.MIDIInputPortCreate(self._client, _cfstr(fw, "in"),
                                       self._read_proc, None,
                                       ctypes.byref(self._in_port)) != 0:
            raise TransportUnavailable("MIDIInputPortCreate failed")
        if fw.midi.MIDIPortConnectSource(self._in_port,
                                         _MIDIObjectRef(self.source.ref),
                                         None) != 0:
            raise TransportUnavailable("MIDIPortConnectSource failed")
        fw.cf.CFRelease(name)
        return self

    def close(self) -> None:
        fw = self._fw
        for port in (self._in_port, self._out_port):
            if port:
                fw.midi.MIDIPortDispose(port)
        if self._client:
            fw.midi.MIDIClientDispose(self._client)
        self._client = _MIDIObjectRef()
        self._in_port = _MIDIObjectRef()
        self._out_port = _MIDIObjectRef()

    def __enter__(self) -> "BlackBox":
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- receive ----------------------------------------------------------

    def _on_packets(self, packet_list: int, refcon: int, src_refcon: int) -> None:
        """MIDIReadProc. Runs on a CoreMIDI thread; must never raise."""
        try:
            base = ctypes.cast(packet_list, ctypes.POINTER(ctypes.c_ubyte))
            count = ctypes.cast(packet_list, ctypes.POINTER(ctypes.c_uint32))[0]
            # MIDIPacketList is pack(4): UInt32 numPackets, then MIDIPacket[].
            # MIDIPacket: UInt64 timeStamp, UInt16 length, Byte data[length].
            offset = 4
            chunks: list[bytes] = []
            for _ in range(count):
                length = ctypes.cast(
                    ctypes.addressof(base.contents) + offset + 8,
                    ctypes.POINTER(ctypes.c_uint16))[0]
                chunks.append(bytes(bytearray(
                    base[offset + 10:offset + 10 + length])))
                # MIDIPacketNext on arm64 rounds up to a 4-byte boundary.
                offset = (offset + 10 + length + 3) & ~3
            with self._lock:
                for chunk in chunks:
                    self._stream.extend(chunk)
                self._extract_sysex_locked()
        except Exception as exc:                  # pragma: no cover - defensive
            self.log_lines.append(f"[readproc error] {exc!r}")

    def _extract_sysex_locked(self) -> None:
        """Reassemble complete F0..F7 messages from the byte stream.

        MIDI real-time messages (0xF8..0xFE) are permitted by the spec to appear
        *inside* a SysEx and must be removed before decoding, or they corrupt
        every subsequent 7-bit group. This pedal has never been observed to send
        one - filtering them is HYPOTHESIS-driven hardening, verified against a
        synthetic packet list in tests/test_transport_rx.py, not against
        hardware.

        A data byte above 0x7F that is not F7 or a real-time byte cannot occur
        in a well-formed SysEx; such a message is dropped rather than decoded
        into garbage.
        """
        while True:
            try:
                start = self._stream.index(SYSEX_START_BYTE)
            except ValueError:
                self._stream.clear()
                return
            try:
                end = self._stream.index(SYSEX_END_BYTE, start)
            except ValueError:
                del self._stream[:start]
                return
            message = bytes(self._stream[start:end + 1])
            del self._stream[:end + 1]
            body = bytes(b for b in message[1:-1] if not 0xF8 <= b <= 0xFE)
            if any(b > 0x7F for b in body):
                self.log_lines.append(
                    f"[rx dropped] status byte inside SysEx: {hexs(message[:16])}")
                continue
            self._sysex.append(message)
            self._decoded.append(protocol.base128_decode(body))

    def reset_rx(self) -> None:
        with self._lock:
            self._stream.clear()
            self._sysex = []
            self._decoded = []

    def received(self) -> tuple[list[bytes], list[bytes]]:
        with self._lock:
            return list(self._sysex), list(self._decoded)

    # -- send -------------------------------------------------------------

    # Length low byte 0x64 == payload length 100 - 8 == 92 == a full preset
    # image. Under the confirmed field model there is no "command type" byte;
    # raw[3] is the low byte of the LE16 length. A write frame carrying a
    # 92-byte payload is Write Flash Save, the one irreversible command.
    _FLASH_IMAGE_LENGTH_LOW_BYTE = 0x64

    def send(self, raw: bytes, label: str = "",
             consent: protocol.WriteConsent | None = None) -> bytes:
        """Transmit one raw frame as SysEx.

        Without ``consent`` the frame must pass :func:`assert_read_only`, which
        allows only the confirmed read commands aimed at mapped regions.

        With ``consent``, the frame is re-validated here against the wire bytes
        themselves, independently of whoever built it:

        * the write path named by the consent must exist and be authorised;
        * the write path must have ``hardware_confirmed=True`` - none currently
          does, so this branch always refuses today;
        * a ``00 59 22`` frame whose length low byte is ``0x64`` (92-byte
          payload = a whole preset image) or whose address lies in the flash
          preset array requires ``consent.allow_flash``.

        Returns the SysEx bytes actually put on the wire.
        """
        if consent is None:
            assert_read_only(raw)
        else:
            self._authorise_write(raw, consent)
        sysex = protocol.sysex_wrap(raw)
        self.log(f"[out raw  ]{(' ' + label) if label else ''} {hexs(raw)}")
        self.log(f"[out sysex] {hexs(sysex)}")

        buf = ctypes.create_string_buffer(sysex, len(sysex))
        request = _MIDISysexSendRequest()
        request.destination = _MIDIObjectRef(self.destination.ref)
        request.data = ctypes.cast(buf, ctypes.c_void_p)
        request.bytesToSend = len(sysex)
        request.complete = 0
        request.completionProc = None
        request.completionRefCon = None
        self._keepalive.append((buf, request))
        if self._fw.midi.MIDISendSysex(ctypes.byref(request)) != 0:
            raise TransportUnavailable("MIDISendSysex failed")
        deadline = time.monotonic() + 2.0
        while not request.complete and time.monotonic() < deadline:
            time.sleep(0.005)
        self.log(f"[out done ] complete={bool(request.complete)} "
                 f"remaining={request.bytesToSend}")
        return sysex

    def _authorise_write(self, raw: bytes,
                         consent: protocol.WriteConsent) -> None:
        """Re-check a write frame against the bytes actually going on the wire.

        Deliberately independent of the builders: this must hold even when
        called from a REPL with a hand-assembled frame.
        """
        if len(raw) < protocol.HEADER_LEN + 1:
            raise UnsafePacket(f"REFUSED: packet too short: {hexs(raw)}")
        if raw[0:3] not in (protocol.MAGIC_READ, protocol.MAGIC_WRITE):
            raise UnsafePacket(f"REFUSED: unknown frame magic: {hexs(raw)}")

        path = consent.authorise(consent.path_key)

        if raw[0:3] == protocol.MAGIC_READ:
            # Consent is not needed for a read, but it must still be a legal one.
            assert_read_only(raw)
            return

        frame = protocol.parse_frame(raw)
        touches_flash = (
            raw[3] == self._FLASH_IMAGE_LENGTH_LOW_BYTE
            or (frame.space == protocol.SPACE_PARAM
                and frame.address
                < protocol.ADDR_PRESET_BASE
                + protocol.PRESET_COUNT * protocol.PRESET_SIZE))
        if touches_flash and not consent.allow_flash:
            raise UnsafePacket(
                f"REFUSED: this frame writes the permanent flash preset array "
                f"(length low byte {raw[3]:#04x}, address "
                f"{frame.address:#010x}) and WriteConsent.allow_flash is False. "
                f"Flash writes are irreversible and can destroy the owner's "
                f"presets: {hexs(raw)}")
        if not path.hardware_confirmed:
            raise UnsafePacket(
                f"REFUSED: write path {path.key!r} has never been confirmed on "
                f"this pedal, so this transport will not put it on the wire "
                f"regardless of consent. {path.evidence} To enable it, someone "
                f"must perform the verification described in STATUS.md and set "
                f"WRITE_PATHS[{path.key!r}].hardware_confirmed = True.")

    # -- request/response -------------------------------------------------

    def request(self, raw: bytes, label: str = "", timeout: float = 3.0,
                quiet_for: float = 0.5,
                want: Callable[[list[bytes]], bool] | None = None
                ) -> tuple[list[bytes], list[bytes]]:
        """Send a read command and collect the notifications that follow.

        Stops when `want` is satisfied, else after `quiet_for` seconds of silence
        following at least one reply, else at `timeout`.
        """
        self.reset_rx()
        self.send(raw, label)
        started = time.monotonic()
        seen = 0
        last_change = time.monotonic()
        while time.monotonic() - started < timeout:
            time.sleep(0.02)
            _, decoded = self.received()
            if len(decoded) != seen:
                seen = len(decoded)
                last_change = time.monotonic()
            if want is not None and want(decoded):
                break
            if seen and time.monotonic() - last_change > quiet_for:
                break
        return self.received()

    def read_memory(self, address: int, size: int,
                    space: int = protocol.SPACE_PARAM,
                    expect_len: int | None = None,
                    label: str = "", timeout: float = 3.0) -> Frame:
        """Issue a memory read and return the matching, validated reply frame.

        The pedal emits unsolicited preset-sync frames, so replies are matched by
        address rather than by arrival order. Five unrequested `0x20000000`
        frames were observed during a flash-read sequence (CONFIRMED by the
        predecessor module; see the module docstring).

        A reply that does not validate raises instead of being returned. A
        truncated 61-byte reply parses cleanly as size=92 / payload=46 and would
        otherwise be handed to the caller as if it were real data.
        """
        command = protocol.build_read(address, size, space)

        def matched(decoded: list[bytes]) -> bool:
            return any(_matches(d, address) for d in decoded)

        _, decoded = self.request(command, label=label, timeout=timeout,
                                  want=matched)
        for message in decoded:
            if _matches(message, address):
                frame = protocol.parse_frame(message)
                self.log(f"[in  frame] addr={frame.address:#010x} "
                         f"size={frame.size} payload={len(frame.payload)}B "
                         f"checksum_ok={frame.checksum_ok} "
                         f"length_ok={frame.length_ok} size_ok={frame.size_ok}")
                problems = []
                if not frame.checksum_ok:
                    problems.append(
                        f"checksum {frame.checksum:#04x} != "
                        f"{protocol.checksum_rx(frame.raw):#04x} (offset-5 rule)")
                if not frame.length_ok:
                    problems.append(
                        f"length field {frame.length} != len(payload) + 8 = "
                        f"{len(frame.payload) + 8}")
                if not frame.size_ok:
                    problems.append(
                        f"size field {frame.size} != len(payload) "
                        f"{len(frame.payload)}")
                if frame.size != size:
                    problems.append(
                        f"reply size {frame.size} != requested {size}")
                if problems:
                    raise CorruptReply(
                        f"malformed reply for {address:#010x}: "
                        + "; ".join(problems)
                        + f". Raw: {hexs(frame.raw[:32])}"
                        + (" ..." if len(frame.raw) > 32 else ""))
                return frame
        raise TransportUnavailable(
            f"No reply for address {address:#010x} within {timeout:.1f}s. "
            f"Received {len(decoded)} frame(s): "
            f"{[hexs(d[:14]) for d in decoded] or 'none'}")


SYSEX_START_BYTE = protocol.SYSEX_START
SYSEX_END_BYTE = protocol.SYSEX_END


def _matches(decoded: bytes, address: int) -> bool:
    """True when a decoded frame is a well-formed reply for `address`."""
    if len(decoded) < protocol.HEADER_LEN + 1:
        return False
    if decoded[0:3] != protocol.MAGIC_READ:
        return False
    return int.from_bytes(decoded[7:11], "little") == address


def open_device(on_log: Callable[[str], None] | None = None) -> BlackBox:
    """Open the pedal, or raise TransportUnavailable with a readable reason."""
    return BlackBox(on_log=on_log).open()
