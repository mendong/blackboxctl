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
:meth:`BlackBox.send` refuses to transmit anything that is not an allowlisted
read unless the caller passes an explicit :class:`protocol.WriteConsent`. Even
with consent, ``send`` independently re-checks the final frame's exact space,
address, payload shape, checksum, and bounds against the named write path.
Flash paths additionally require ``allow_flash`` and unconfirmed paths remain
blocked except for one frame-bound physical probe capability.

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
import errno
import fcntl
import os
import platform
import threading
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

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

DEVICE_LOCK_PATH = (
    Path.home() / ".local" / "share" / "blackboxctl" / "locks" / "device.lock"
)
"""Per-user advisory lock held for the full lifetime of an open pedal link."""

MIDI_PACKET_ALIGN_4 = platform.machine().lower() in ("arm64", "aarch64")


def _next_packet_offset(offset: int, length: int, *, align4: bool) -> int:
    """Mirror CoreMIDI's architecture-dependent ``MIDIPacketNext`` macro."""
    result = offset + 10 + length
    return (result + 3) & ~3 if align4 else result


class TransportUnavailable(RuntimeError):
    """CoreMIDI could not be loaded, or no BlackBox endpoint was found."""


class CorruptReply(RuntimeError):
    """A reply arrived but failed checksum / length / size validation."""


class AckTimeout(RuntimeError):
    """A write may have landed, but its exact acknowledgement was not observed."""


class ReplyTimeout(RuntimeError):
    """An open device did not return the requested read reply in time."""


class SendInFlight(RuntimeError):
    """CoreMIDI did not confirm that an asynchronous SysEx stopped sending."""


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
            "/System/Library/Frameworks/CoreMIDI.framework/CoreMIDI"
        )
        cf = ctypes.cdll.LoadLibrary(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
    except OSError as exc:  # pragma: no cover - macOS only
        raise TransportUnavailable(
            "CoreMIDI is unavailable on this system. blackboxctl's device "
            "commands require macOS with CoreMIDI; every other command works "
            f"without it. Underlying error: {exc}"
        ) from exc

    cf.CFStringCreateWithCString.restype = ctypes.c_void_p
    cf.CFStringCreateWithCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_uint32,
    ]
    cf.CFStringGetCString.restype = ctypes.c_bool
    cf.CFStringGetCString.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_uint32,
    ]
    cf.CFRelease.argtypes = [ctypes.c_void_p]

    midi.MIDIClientCreate.restype = ctypes.c_int32
    midi.MIDIClientCreate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(_MIDIObjectRef),
    ]
    midi.MIDIOutputPortCreate.restype = ctypes.c_int32
    midi.MIDIOutputPortCreate.argtypes = [
        _MIDIObjectRef,
        ctypes.c_void_p,
        ctypes.POINTER(_MIDIObjectRef),
    ]
    midi.MIDIInputPortCreate.restype = ctypes.c_int32
    midi.MIDIInputPortCreate.argtypes = [
        _MIDIObjectRef,
        ctypes.c_void_p,
        _MIDIReadProc,
        ctypes.c_void_p,
        ctypes.POINTER(_MIDIObjectRef),
    ]
    midi.MIDIPortConnectSource.restype = ctypes.c_int32
    midi.MIDIPortConnectSource.argtypes = [
        _MIDIObjectRef,
        _MIDIObjectRef,
        ctypes.c_void_p,
    ]
    midi.MIDIGetNumberOfSources.restype = ctypes.c_ulong
    midi.MIDIGetNumberOfDestinations.restype = ctypes.c_ulong
    midi.MIDIGetSource.restype = _MIDIObjectRef
    midi.MIDIGetSource.argtypes = [ctypes.c_ulong]
    midi.MIDIGetDestination.restype = _MIDIObjectRef
    midi.MIDIGetDestination.argtypes = [ctypes.c_ulong]
    midi.MIDIObjectGetStringProperty.restype = ctypes.c_int32
    midi.MIDIObjectGetStringProperty.argtypes = [
        _MIDIObjectRef,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    midi.MIDISendSysex.restype = ctypes.c_int32
    midi.MIDISendSysex.argtypes = [ctypes.POINTER(_MIDISysexSendRequest)]
    midi.MIDIClientDispose.argtypes = [_MIDIObjectRef]
    midi.MIDIPortDispose.argtypes = [_MIDIObjectRef]

    _FRAMEWORKS = _Frameworks(midi=midi, cf=cf)
    return _FRAMEWORKS


_MIDIReadProc = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
)


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
        fw.cf.CFStringCreateWithCString(None, text.encode(), _CF_ENCODING_UTF8)
    )


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
        return (
            f"index={self.index} ref={self.ref} name={self.name!r} "
            f"display={self.display!r} manufacturer={self.manufacturer!r}"
        )


def list_endpoints() -> tuple[list[Endpoint], list[Endpoint]]:
    """Enumerate (sources, destinations) visible to CoreMIDI."""
    fw = _load_frameworks()
    sources: list[Endpoint] = []
    destinations: list[Endpoint] = []
    for index in range(fw.midi.MIDIGetNumberOfSources()):
        ref = fw.midi.MIDIGetSource(index)
        sources.append(
            Endpoint(
                index,
                ref,
                _string_property(fw, ref, "name"),
                _string_property(fw, ref, "displayName"),
                _string_property(fw, ref, "manufacturer"),
            )
        )
    for index in range(fw.midi.MIDIGetNumberOfDestinations()):
        ref = fw.midi.MIDIGetDestination(index)
        destinations.append(
            Endpoint(
                index,
                ref,
                _string_property(fw, ref, "name"),
                _string_property(fw, ref, "displayName"),
                _string_property(fw, ref, "manufacturer"),
            )
        )
    return sources, destinations


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------


class BlackBox:
    """Open USB MIDI SysEx link to the pedal. Read-only unless explicitly told."""

    def __init__(
        self,
        manufacturer: str = MANUFACTURER,
        on_log: Callable[[str], None] | None = None,
    ) -> None:
        self.manufacturer = manufacturer
        self._log_sink = on_log
        self.log_lines: list[str] = []
        self._device_lock_path = Path(DEVICE_LOCK_PATH).expanduser()
        self._device_lock_fd: int | None = None
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
        self._send_blocked = False

    # -- logging ----------------------------------------------------------

    def log(self, line: str) -> None:
        self.log_lines.append(line)
        if self._log_sink is not None:
            self._log_sink(line)

    # -- lifecycle --------------------------------------------------------

    def _acquire_device_lock(self) -> None:
        """Fail fast unless this process exclusively owns the pedal session."""
        if self._device_lock_fd is not None:
            return

        path = self._device_lock_path
        descriptor: int | None = None
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(path.parent, 0o700)
            flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
            flags |= getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, 0o600)
            os.fchmod(descriptor, 0o600)
        except BaseException as exc:
            if descriptor is not None:
                with suppress(OSError):
                    os.close(descriptor)
            if isinstance(exc, OSError):
                raise TransportUnavailable(
                    f"Cannot create the private BlackBox device lock at {path}: {exc}"
                ) from exc
            raise

        assert descriptor is not None

        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException as exc:
            if not (
                isinstance(exc, OSError) and exc.errno in (errno.EACCES, errno.EAGAIN)
            ):
                os.close(descriptor)
                if isinstance(exc, OSError):
                    raise TransportUnavailable(
                        f"Cannot lock BlackBox device session {path}: {exc}"
                    ) from exc
                raise
            try:
                owner = os.pread(descriptor, 256, 0).decode("utf-8", "replace").strip()
            except OSError:
                owner = ""
            os.close(descriptor)
            detail = f" Current owner: {owner}." if owner else ""
            raise TransportUnavailable(
                "Another blackboxctl process already has the BlackBox open. "
                "Wait for that command to finish before running any read or "
                f"write operation.{detail} Lock: {path}"
            ) from exc

        try:
            owner = f"pid={os.getpid()}\n".encode()
            os.ftruncate(descriptor, 0)
            os.pwrite(descriptor, owner, 0)
            os.fsync(descriptor)
        except BaseException as exc:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
            if isinstance(exc, OSError):
                raise TransportUnavailable(
                    f"Cannot record ownership in BlackBox device lock {path}: {exc}"
                ) from exc
            raise
        self._device_lock_fd = descriptor

    def _release_device_lock(self) -> None:
        descriptor = self._device_lock_fd
        self._device_lock_fd = None
        if descriptor is None:
            return
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            # Closing also releases flock if the explicit unlock failed.
            os.close(descriptor)

    def open(self) -> BlackBox:
        """Acquire the CoreMIDI client and ports. Idempotent.

        Re-opening an already-open instance MUST be a no-op. ``open_device()``
        returns an instance on which ``open()`` has already run, and callers
        then use it as a context manager, so ``__enter__`` calls ``open()`` a
        second time. Before this guard existed, that second call replaced
        ``self._read_proc`` with a fresh ``CFUNCTYPE`` trampoline and let the
        first one be garbage collected while the first input port -- leaked,
        never disposed, still connected to the source -- could still invoke it.
        CoreMIDI then called freed code on its own thread and the process died
        with SIGBUS on the next reply from the pedal. Found on real hardware
        2026-08-28; regression test in tests/test_transport_reopen.py.
        """
        if self._client:
            return self

        self._acquire_device_lock()
        try:
            sources, destinations = list_endpoints()
            src = [e for e in sources if (e.manufacturer or "") == self.manufacturer]
            dst = [
                e for e in destinations if (e.manufacturer or "") == self.manufacturer
            ]
            if not src or not dst:
                raise TransportUnavailable(
                    f"No complete MIDI endpoint pair with manufacturer "
                    f"{self.manufacturer!r} was found. Is the BlackBox connected "
                    f"over USB?\n  sources:      "
                    f"{[e.describe() for e in sources] or 'none'}\n"
                    f"  destinations: "
                    f"{[e.describe() for e in destinations] or 'none'}"
                )
            if len(src) != 1 or len(dst) != 1:
                raise TransportUnavailable(
                    f"Ambiguous BlackBox endpoint set: found {len(src)} source(s) "
                    f"and {len(dst)} destination(s) from {self.manufacturer!r}. "
                    "Refusing to guess a cross-device pairing. Disconnect extra "
                    "devices, then run 'blackboxctl device endpoints' to inspect "
                    f"them.\n  matching sources:      "
                    f"{[e.describe() for e in src]}\n"
                    f"  matching destinations: {[e.describe() for e in dst]}"
                )
            self.source, self.destination = src[0], dst[0]
            self.log(f"[midi] destination {self.destination.describe()}")
            self.log(f"[midi] source      {self.source.describe()}")

            fw = self._fw
            client_name = _cfstr(fw, "blackboxctl")
            try:
                status = fw.midi.MIDIClientCreate(
                    client_name, None, None, ctypes.byref(self._client)
                )
            finally:
                fw.cf.CFRelease(client_name)
            if status != 0:
                raise TransportUnavailable("MIDIClientCreate failed")

            output_name = _cfstr(fw, "out")
            try:
                status = fw.midi.MIDIOutputPortCreate(
                    self._client, output_name, ctypes.byref(self._out_port)
                )
            finally:
                fw.cf.CFRelease(output_name)
            if status != 0:
                raise TransportUnavailable("MIDIOutputPortCreate failed")

            self._read_proc = _MIDIReadProc(self._on_packets)  # must stay referenced
            input_name = _cfstr(fw, "in")
            try:
                status = fw.midi.MIDIInputPortCreate(
                    self._client,
                    input_name,
                    self._read_proc,
                    None,
                    ctypes.byref(self._in_port),
                )
            finally:
                fw.cf.CFRelease(input_name)
            if status != 0:
                raise TransportUnavailable("MIDIInputPortCreate failed")

            if (
                fw.midi.MIDIPortConnectSource(
                    self._in_port, _MIDIObjectRef(self.source.ref), None
                )
                != 0
            ):
                raise TransportUnavailable("MIDIPortConnectSource failed")
        except BaseException:
            # A failed CoreMIDI create call may still leave its output handle
            # non-zero. Dispose every acquired object and clear the guard so a
            # later open() performs a real retry instead of treating this
            # partially initialised instance as connected.
            try:
                self.close()
            except BaseException as cleanup_error:  # noqa: BLE001
                # Preserve the acquisition failure while retaining evidence of
                # an unexpected cleanup failure. close() resets handles before
                # it calls CoreMIDI, so retry remains possible either way.
                self.log(f"[midi cleanup error] {cleanup_error!r}")
            raise
        return self

    def close(self) -> None:
        fw = self._fw
        in_port, out_port, client = (self._in_port, self._out_port, self._client)
        # Reset first. Even if a native disposer unexpectedly raises, open()
        # must not mistake a partial or closed connection for a live one.
        self._client = _MIDIObjectRef()
        self._in_port = _MIDIObjectRef()
        self._out_port = _MIDIObjectRef()
        self.source = None
        self.destination = None
        errors: list[BaseException] = []
        for port in (in_port, out_port):
            if port:
                try:
                    fw.midi.MIDIPortDispose(port)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)
        if client:
            try:
                fw.midi.MIDIClientDispose(client)
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
        try:
            self._release_device_lock()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
        if errors:
            raise errors[0]

    def __enter__(self) -> BlackBox:  # noqa: PYI034 - supports Python 3.10
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
                    ctypes.POINTER(ctypes.c_uint16),
                )[0]
                chunks.append(
                    bytes(bytearray(base[offset + 10 : offset + 10 + length]))
                )
                # MIDIPacketNext aligns only on ARM; Intel packets are packed.
                offset = _next_packet_offset(offset, length, align4=MIDI_PACKET_ALIGN_4)
            with self._lock:
                for chunk in chunks:
                    self._stream.extend(chunk)
                self._extract_sysex_locked()
        except Exception as exc:  # noqa: BLE001  # pragma: no cover - defensive
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
            message = bytes(self._stream[start : end + 1])
            del self._stream[: end + 1]
            body = bytes(b for b in message[1:-1] if not 0xF8 <= b <= 0xFE)
            if any(b > 0x7F for b in body):
                self.log_lines.append(
                    f"[rx dropped] status byte inside SysEx: {hexs(message[:16])}"
                )
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

    def send(
        self,
        raw: bytes,
        label: str = "",
        consent: protocol.WriteConsent | None = None,
        probe: protocol.WriteProbe | None = None,
    ) -> bytes:
        """Transmit one raw frame as SysEx.

        Without ``consent`` the frame must pass :func:`assert_read_only`, which
        allows only the confirmed read commands aimed at mapped regions.

        With ``consent``, the frame is re-validated here against the wire bytes
        themselves, independently of whoever built it:

        * the write path named by the consent must exist and be authorised;
        * the final bytes must match that path's exact address and payload shape;
        * the write path must have ``hardware_confirmed=True`` unless this is an
          exact frame-bound physical probe;
        * a frame that writes a preset image, a flash preset slot, or an
          AMP/CAB slot-commit register requires ``consent.allow_flash``.

        Returns the SysEx bytes actually put on the wire.
        """
        if consent is None:
            assert_read_only(raw)
        else:
            self._authorise_write(raw, consent, probe=probe)
        if self.destination is None:
            raise TransportUnavailable("MIDI destination is not open")
        if self._send_blocked:
            raise SendInFlight(
                "a previous CoreMIDI SysEx is still in an uncertain in-flight "
                "state; this connection is blocked from sending recovery or "
                "retry frames. Close it and inspect device state before retrying"
            )
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
        self.log(
            f"[out done ] complete={bool(request.complete)} "
            f"remaining={request.bytesToSend}"
        )
        if not request.complete or request.bytesToSend:
            # CoreMIDI documents setting ``complete`` as the asynchronous abort
            # request. Without a completion callback there is no proof the
            # worker has observed it yet, so retain the request buffer and block
            # every later send on this connection. In particular, recovery must
            # not race a late original write.
            request.complete = 1
            self._send_blocked = True
            raise SendInFlight(
                "CoreMIDI did not complete the SysEx within 2.0s "
                f"({request.bytesToSend} byte(s) remained). Abort was requested, "
                "but completion is unconfirmed; device state is uncertain"
            )
        return sysex

    def _writes_permanent_storage(self, raw: bytes, frame: protocol.Frame) -> bool:
        """True when the wire bytes themselves are a permanent-slot write.

        Independent of ``WritePath.touches_flash`` so a hand-built commit
        frame cannot hide behind a RAM-only consent.
        """
        if raw[3] == self._FLASH_IMAGE_LENGTH_LOW_BYTE:
            return True
        preset_last = (
            protocol.ADDR_PRESET_BASE + protocol.PRESET_COUNT * protocol.PRESET_SIZE
        )
        if frame.space == protocol.SPACE_PARAM and frame.address < preset_last:
            return True
        if frame.space != protocol.SPACE_STRING:
            return False
        amp_commit = (
            protocol.ADDR_AMP_COMMIT_BASE
            <= frame.address
            < protocol.ADDR_AMP_COMMIT_BASE + protocol.NAME_COUNT
        )
        cab_commit = (
            protocol.ADDR_CAB_COMMIT_BASE
            <= frame.address
            < protocol.ADDR_CAB_COMMIT_BASE + protocol.NAME_COUNT
        )
        return amp_commit or cab_commit

    def _authorise_write(
        self,
        raw: bytes,
        consent: protocol.WriteConsent,
        probe: protocol.WriteProbe | None = None,
    ) -> None:
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
        protocol.assert_write_for_path(raw, path.key)
        writes_flash = self._writes_permanent_storage(raw, frame)
        if writes_flash and consent.allow_flash is not True:
            raise UnsafePacket(
                f"REFUSED: this frame writes permanent device storage "
                f"(length low byte {raw[3]:#04x}, address "
                f"{frame.address:#010x}) and WriteConsent.allow_flash is False. "
                f"Flash writes are irreversible and can destroy stored "
                f"presets or AMP/CAB slots: {hexs(raw)}"
            )
        if not path.hardware_confirmed and not (
            probe is not None and probe.matches(path.key, raw)
        ):
            raise UnsafePacket(
                f"REFUSED: write path {path.key!r} has never been confirmed on "
                f"this pedal, so this transport will not put it on the wire "
                f"regardless of consent. {path.evidence} To enable it, someone "
                f"must perform the verification described in STATUS.md and set "
                f"WRITE_PATHS[{path.key!r}].hardware_confirmed = True."
            )

    def write_and_wait_ack(
        self,
        raw: bytes,
        *,
        label: str,
        consent: protocol.WriteConsent,
        probe: protocol.WriteProbe | None = None,
        timeout: float = 3.0,
    ) -> bytes:
        """Send one write and require the exact compact ACK frame.

        This method intentionally does not call :func:`protocol.parse_frame` on
        the 8-byte ACK. The caller must still read the target memory back;
        upstream implementations disagree about the ACK payload semantics.
        """
        self.reset_rx()
        self.send(raw, label=label, consent=consent, probe=probe)
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            time.sleep(0.01)
            _, decoded = self.received()
            for message in decoded:
                if protocol.is_ack(message):
                    self.log(f"[in  ack  ] {hexs(message)}")
                    return message
        _, decoded = self.received()
        compact = [hexs(message) for message in decoded if len(message) < 15]
        raise AckTimeout(
            f"No exact write ACK within {timeout:.1f}s. "
            f"The requested state may already have changed; reconcile it before "
            f"retrying. Observed compact frame(s): {compact or 'none'}"
        )

    # -- request/response -------------------------------------------------

    def request(
        self,
        raw: bytes,
        label: str = "",
        timeout: float = 3.0,
        quiet_for: float = 0.5,
        want: Callable[[list[bytes]], bool] | None = None,
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

    def read_memory(
        self,
        address: int,
        size: int,
        space: int = protocol.SPACE_PARAM,
        expect_len: int | None = None,
        label: str = "",
        timeout: float = 3.0,
    ) -> Frame:
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

        # This unit occasionally drops the first read immediately after a
        # CoreMIDI client reconnect while remaining fully enumerated. A second
        # identical read succeeds. Unrelated preset-sync notifications do not
        # suppress that retry; a matching malformed reply does, and is rejected
        # below without asking the device again.
        decoded: list[bytes] = []
        for attempt in range(2):
            _, decoded = self.request(
                command, label=label, timeout=timeout, want=matched
            )
            if any(_matches(message, address) for message in decoded):
                break
            if attempt == 1:
                break
            time.sleep(0.1)
        for message in decoded:
            if _matches(message, address):
                frame = protocol.parse_frame(message)
                self.log(
                    f"[in  frame] addr={frame.address:#010x} "
                    f"size={frame.size} payload={len(frame.payload)}B "
                    f"checksum_ok={frame.checksum_ok} "
                    f"length_ok={frame.length_ok} size_ok={frame.size_ok}"
                )
                problems = []
                if not frame.checksum_ok:
                    problems.append(
                        f"checksum {frame.checksum:#04x} != "
                        f"{protocol.checksum_rx(frame.raw):#04x} (offset-5 rule)"
                    )
                if not frame.length_ok:
                    problems.append(
                        f"length field {frame.length} != len(payload) + 8 = "
                        f"{len(frame.payload) + 8}"
                    )
                if not frame.size_ok:
                    problems.append(
                        f"size field {frame.size} != len(payload) {len(frame.payload)}"
                    )
                if frame.size != size:
                    problems.append(f"reply size {frame.size} != requested {size}")
                if problems:
                    raise CorruptReply(
                        f"malformed reply for {address:#010x}: "
                        + "; ".join(problems)
                        + f". Raw: {hexs(frame.raw[:32])}"
                        + (" ..." if len(frame.raw) > 32 else "")
                    )
                return frame
        raise ReplyTimeout(
            f"No reply for address {address:#010x} within {timeout:.1f}s. "
            f"Received {len(decoded)} frame(s): "
            f"{[hexs(d[:14]) for d in decoded] or 'none'}"
        )


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
