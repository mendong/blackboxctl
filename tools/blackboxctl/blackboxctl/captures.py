"""Parsing, validation and safe renaming of BlackBox capture and IR files.

Two file families are handled:

* Neural amp captures - ``.am2`` / ``.am2Data`` / ``.am2data`` / ``.am3Data``.
  A 60-byte header followed by 1536 little-endian float32 (6144 bytes) = 6204
  bytes; a bare ``.am2`` is the same 6144-byte payload with the header stripped.
  CONFIRMED by static analysis of ``libamx_parser.dylib`` plus a 1686-file corpus.
* Cabinet impulse responses - ``.wav``, inspected with a hand-written RIFF
  chunk walk and a direct ``fmt `` parse. The stdlib ``wave`` module is
  deliberately NOT used: it raises on any format tag but 1 (PCM), which would
  reject the pedal's own 32-bit-float factory IR.

CONFIRMED: there is no checksum, CRC or hash anywhere in the capture container
(10 algorithms x 8 byte ranges against every header window, 400 files, zero
hits). Editing the header - including renaming - therefore cannot invalidate a
file, which is what makes ``blackboxctl rename --in-place`` safe.

Error vs warning
----------------
An ``error`` means "this file is structurally broken" and blocks installation.
A ``warning`` means "this is unusual and you should know" and does not.

Several checks that used to be errors are warnings, because nothing has ever
tested what the device actually does with them, and refusing a file the pedal
may well accept is its own kind of wrong answer:

* magic ``00 00 32 00`` - written by am2manager's ``am2converter``
  (``am2.go:14``'s ``InitData`` literally begins ``{0, 0, 50, 0, ...}``), not
  damage to a good file. 318 of 1295 headered files in the community pack and 4
  of the files ``presets/library.md`` calls for carry it, all already sitting in
  the user's live M-EFCS library. UNTESTED on the device.
* non-printable bytes in the name field - cosmetic; the audio payload is intact.
* a 7868-byte AM4 record - needs firmware V20; this pedal reports V19 and would
  presumably ignore it. Also UNTESTED.
* an IEEE-float or non-24-bit WAV - the pedal's own factory IR in CAB slot 10
  (``10SoldSC412.wav``) is 32-bit float, so 24-bit is a documented figure, not
  a requirement.

Prior art for the header field names: https://github.com/walterwanderley/am2manager
(Apache-2.0). See ../NOTICE. GPL-3.0.
"""

from __future__ import annotations

import ctypes
import math
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path

from . import storage

HEADER_LEN = 60
PAYLOAD_LEN = 6144
RECORD_LEN = HEADER_LEN + PAYLOAD_LEN  # 6204
LMT_MAGIC = b"LMT\x00"
LMT_LEN = 4 + 16 * 4  # runtime block the DSP appends
AM4_RECORD_LEN = 7868  # firmware V20 only, not V19

NAME_OFFSET = 4
NAME_FIELD = 14  # 13 usable chars + NUL
NAME_MAX = NAME_FIELD - 1

OFF_MIX, OFF_LEVEL, OFF_GAIN_MAX, OFF_GAIN_MIN = 0x12, 0x13, 0x14, 0x15
OFF_RESERVED = 0x16
OFF_EQ = 0x18

KNOWN_MAGIC = (b"AM2\x00", b"AM3\x00")
"""Magics this generation of firmware (V19) actually loads. AM4 exists but needs
firmware V20 and a 7868-byte record."""

SAMPLE_RATE = 44100
Q_SCALE = 2097151.0  # 2**21 - 1, the DSP's Q21 scale
MAX_ABS_WEIGHT = 1024.0  # |w| beyond this overflows Q21

CAPTURE_SUFFIXES = (".am2", ".am2data", ".am3data", ".am4", ".am4data")
IR_SUFFIXES = (".wav",)

IR_DOCUMENTED_RATE = 44100
IR_DOCUMENTED_BITS = 24
IR_DOCUMENTED_CHANNELS = 1
IR_TAPS = 2048
"""Samples M-EFCS actually stages: 44.1 kHz / signed 24-bit mono / 2,048 frames.

CONFIRMED byte-for-byte on 2026-08-29 by matching a captured 6,164-byte
device-bound staging transfer to the source WAV. This does not establish the
firmware's factory flash layout or effective convolution length.
"""

WAVE_FORMAT_PCM = 1
WAVE_FORMAT_IEEE_FLOAT = 3
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

DEFAULT_AMX_DYLIB = Path(
    "/Applications/M-EFCS.app/Contents/Frameworks/libamx_parser.dylib"
)


# ---------------------------------------------------------------------------
# Captures
# ---------------------------------------------------------------------------


@dataclass
class Capture:
    """A parsed capture file."""

    path: Path
    size: int
    has_header: bool
    magic: bytes | None = None
    magic_ok: bool = False
    name: str | None = None
    name_raw: bytes | None = None
    mix: int | None = None
    level: int | None = None
    gain_max: int | None = None
    gain_min: int | None = None
    reserved: bytes | None = None
    eq: list[tuple[float, float, float]] = field(default_factory=list)
    weight_min: float | None = None
    weight_max: float | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "kind": "capture",
            "size": self.size,
            "has_header": self.has_header,
            "magic": self.magic.decode("latin1") if self.magic else None,
            "magic_ok": self.magic_ok,
            "name": self.name,
            "name_raw": self.name_raw.hex() if self.name_raw else None,
            "mix": self.mix,
            "level": self.level,
            "gain_max": self.gain_max,
            "gain_min": self.gain_min,
            "reserved": self.reserved.hex() if self.reserved else None,
            "eq": [
                {"freq_hz": f, "gain_min_db": lo, "gain_max_db": hi}
                for f, lo, hi in self.eq
            ],
            "weight_min": self.weight_min,
            "weight_max": self.weight_max,
            "errors": self.errors,
            "warnings": self.warnings,
            "ok": self.ok,
        }


def _floats(buf: bytes, offset: int, count: int) -> list[float]:
    return list(struct.unpack_from(f"<{count}f", buf, offset))


def parse_capture(path: Path, data: bytes | None = None) -> Capture:
    """Parse and validate a capture file. Never raises on malformed content."""
    path = Path(path)
    if data is None:
        data = path.read_bytes()
    size = len(data)

    if size == RECORD_LEN:
        capture = Capture(path=path, size=size, has_header=True)
        payload = data[HEADER_LEN:]
    elif size == PAYLOAD_LEN:
        capture = Capture(path=path, size=size, has_header=False)
        capture.warnings.append(
            "bare payload with no 60-byte header: no name, level or EQ metadata"
        )
        payload = data
    elif (
        size == RECORD_LEN + LMT_LEN and data[RECORD_LEN : RECORD_LEN + 4] == LMT_MAGIC
    ):
        capture = Capture(path=path, size=size, has_header=True)
        capture.warnings.append(
            "record carries a runtime LMT block (on-device / flash form)"
        )
        payload = data[HEADER_LEN:RECORD_LEN]
    elif size == AM4_RECORD_LEN:
        capture = Capture(path=path, size=size, has_header=True)
        capture.warnings.append(
            f"{size}-byte AM4 record: AM4 captures are documented to need "
            f"firmware V20 (2026-01-31) and this pedal reports V19. Whether "
            f"V19 ignores it or misbehaves is UNTESTED, so this is a warning, "
            f"not a refusal"
        )
        _parse_header(capture, data[:HEADER_LEN])
        return capture
    else:
        capture = Capture(path=path, size=size, has_header=False)
        capture.errors.append(
            f"bad size {size}: expected {PAYLOAD_LEN} (bare payload) or "
            f"{RECORD_LEN} (header + payload)"
        )
        return capture

    if capture.has_header:
        _parse_header(capture, data[:HEADER_LEN])
    _check_weights(capture, payload)
    return capture


def _parse_header(capture: Capture, header: bytes) -> None:
    capture.magic = header[0:4]
    capture.magic_ok = capture.magic in KNOWN_MAGIC
    if not capture.magic_ok:
        if (
            capture.magic[:2] == b"\x00\x00"
            and capture.magic[3] == 0
            and capture.magic[2] in (0x32, 0x33)
        ):
            capture.warnings.append(
                f"magic {capture.magic.hex()} has the AM prefix unset. This "
                f"header was WRITTEN this way by am2manager's am2converter - "
                f"am2.go:14 defines InitData as {{0, 0, 50, 0, ...}} and it "
                f"matches these 60 header bytes byte for byte, so nothing was "
                f"corrupted and no good file was damaged. Whether M-EFCS or "
                f"BlackBox firmware V19 accepts it is UNTESTED. "
                f"'blackboxctl rename --repair-magic' can set it to "
                f"AM{chr(capture.magic[2])}\\0 if you want to find out"
            )
        elif (
            capture.magic[:2] == b"\x00\x00"
            and capture.magic[3] == 0
            and capture.magic[2] in (0x35, 0x38)
        ):
            capture.warnings.append(
                f"magic {capture.magic.hex()} is an observed but unexplained "
                "corrupt-magic form. It is accepted for inspection only; "
                "firmware V19 device preparation and --repair-magic refuse it "
                "rather than inventing an AMP version"
            )
        else:
            capture.errors.append(
                f"bad magic {capture.magic.hex()} (expected AM2\\0 or AM3\\0, "
                f"or an observed 00 00 3x 00 corrupt-magic form)"
            )

    capture.name_raw = header[NAME_OFFSET : NAME_OFFSET + NAME_FIELD]
    nul = capture.name_raw.find(b"\x00")
    if nul < 0:
        capture.warnings.append(
            f"name field is not NUL-terminated within {NAME_FIELD} bytes; the "
            f"device reads a fixed-width field, so this is cosmetic"
        )
        text = capture.name_raw
    else:
        text = capture.name_raw[:nul]
        if any(capture.name_raw[nul + 1 :]):
            capture.warnings.append("non-zero bytes after the name NUL terminator")
    if any(b < 0x20 or b > 0x7E for b in text):
        capture.warnings.append(
            f"name contains non-printable bytes: {text.hex()}. The audio payload "
            f"is unaffected; 'blackboxctl rename' can set a clean name"
        )
        capture.name = "".join(chr(b) for b in text if 0x20 <= b <= 0x7E)
    else:
        capture.name = text.decode("ascii")
    if capture.name == "":
        capture.warnings.append("empty name")

    capture.mix = header[OFF_MIX]
    capture.level = header[OFF_LEVEL]
    capture.gain_max = header[OFF_GAIN_MAX]
    capture.gain_min = header[OFF_GAIN_MIN]
    capture.reserved = header[OFF_RESERVED : OFF_RESERVED + 2]
    if capture.reserved != b"\x00\x00":
        capture.errors.append(
            f"reserved bytes 0x16..0x17 are not zero: {capture.reserved.hex()}"
        )
    if capture.mix > 100:
        capture.errors.append(f"mix {capture.mix} out of range 0..100")
    if capture.gain_min > capture.gain_max:
        capture.warnings.append(
            f"gain_min {capture.gain_min} > gain_max {capture.gain_max}"
        )

    values = _floats(header, OFF_EQ, 9)
    for band in range(3):
        freq, low, high = values[3 * band : 3 * band + 3]
        capture.eq.append((freq, low, high))
        if not all(math.isfinite(value) for value in (freq, low, high)):
            capture.errors.append(
                f"eq band {band + 1} contains a non-finite value: "
                f"frequency={freq!r}, gain_min={low!r}, gain_max={high!r}"
            )
            continue
        if not 0.0 < freq < SAMPLE_RATE / 2:
            capture.errors.append(
                f"eq band {band + 1} frequency {freq!r} outside (0, {SAMPLE_RATE // 2})"
            )
        if low > high:
            capture.errors.append(
                f"eq band {band + 1} gain range inverted: {low:.1f} > {high:.1f}"
            )
        elif not low <= 0.0 <= high:
            capture.warnings.append(
                f"eq band {band + 1} gain range [{low:.1f}, {high:.1f}] does not "
                f"bracket 0 dB"
            )
        if not (-48.0 <= low <= 48.0 and -48.0 <= high <= 48.0):
            capture.warnings.append(f"eq band {band + 1} gain range outside +/-48 dB")
    freqs = [band[0] for band in capture.eq]
    if freqs != sorted(freqs):
        capture.warnings.append("eq band frequencies are not ascending")


def _check_weights(capture: Capture, payload: bytes) -> None:
    weights = _floats(payload, 0, PAYLOAD_LEN // 4)
    finite = [weight for weight in weights if math.isfinite(weight)]
    if len(finite) != len(weights):
        first = next(
            index for index, weight in enumerate(weights) if not math.isfinite(weight)
        )
        capture.errors.append(
            f"{len(weights) - len(finite)} non-finite float32 in payload, "
            f"first at index {first}"
        )
    if finite:
        capture.weight_min = min(finite)
        capture.weight_max = max(finite)
    oversized = [i for i, w in enumerate(finite) if abs(w) >= MAX_ABS_WEIGHT]
    if oversized:
        capture.errors.append(
            f"{len(oversized)} weights with |w| >= {MAX_ABS_WEIGHT:.0f} would "
            f"overflow the DSP's Q21 fixed point, first at index {oversized[0]}"
        )


# ---------------------------------------------------------------------------
# Header edits
# ---------------------------------------------------------------------------


class CaptureEditError(ValueError):
    """A requested header edit cannot be performed."""


def set_capture_name(data: bytes, name: str) -> bytes:
    """Return a copy of a 6204-byte record with a new name. Weights untouched."""
    if len(data) != RECORD_LEN:
        raise CaptureEditError(
            f"renaming needs a {RECORD_LEN}-byte record with a header; this file "
            f"is {len(data)} bytes. A bare {PAYLOAD_LEN}-byte .am2 has no name "
            f"field to rename"
        )
    encoded = name.encode("ascii", "strict") if name.isascii() else None
    if encoded is None:
        raise CaptureEditError("name must be ASCII")
    if len(encoded) > NAME_MAX:
        raise CaptureEditError(
            f"name is {len(encoded)} characters; the field holds at most {NAME_MAX}"
        )
    if any(b < 0x20 or b > 0x7E for b in encoded):
        raise CaptureEditError("name must be printable ASCII (0x20..0x7E)")
    return (
        data[:NAME_OFFSET]
        + encoded.ljust(NAME_FIELD, b"\x00")
        + data[NAME_OFFSET + NAME_FIELD :]
    )


def repair_capture_magic(data: bytes) -> bytes:
    """Set the ``AM`` prefix on a ``00 00 3x 00`` magic, preserving the version.

    Only bytes 0 and 1 are touched. The version digit at byte 2 and the NUL at
    byte 3 are left exactly as they are, because the observed corpus contains
    ``00 00 35 00`` and ``00 00 38 00`` as well as ``00 00 32 00`` - rewriting
    byte 2 to a caller-chosen version would silently change what the file
    claims to be.

    Refuses anything whose byte 2 is not a loadable AM2/AM3 version digit or
    whose byte 3 is not NUL, rather than stamping a header onto an unrecognised
    file.
    """
    if len(data) != RECORD_LEN:
        raise CaptureEditError(f"repair needs a {RECORD_LEN}-byte record")
    magic = data[0:4]
    if magic in KNOWN_MAGIC:
        raise CaptureEditError(
            f"magic is already {magic.decode('latin1')!r}; nothing to repair"
        )
    if magic[0:2] != b"\x00\x00" or magic[3] != 0:
        raise CaptureEditError(
            f"magic {magic.hex()} is not the am2converter form 00 00 3x 00; "
            f"refusing to guess what this file is"
        )
    if magic[2] not in (0x32, 0x33):
        raise CaptureEditError(
            f"byte 2 is {magic[2]:#04x} ({chr(magic[2])!r}), not '2' or '3'. "
            f"Only AM2 and AM3 are loadable by firmware V19, and this function "
            f"will not invent a version digit"
        )
    return b"AM" + data[2:3] + data[3:4] + data[4:]


def default_amp_header() -> bytes:
    """Return the standard 60-byte AM2 header used for bare 6,144-byte files."""
    header = bytearray(HEADER_LEN)
    header[:4] = b"AM2\x00"
    header[OFF_MIX : OFF_GAIN_MIN + 1] = bytes((100, 100, 60, 30))
    for band, frequency in enumerate((100.0, 2000.0, 4000.0)):
        struct.pack_into("<fff", header, OFF_EQ + band * 12, frequency, -6.0, 6.0)
    return bytes(header)


def build_amp_file_record(path: Path, name: str) -> bytes:
    """Normalize a capture to a named 6,204-byte AM2/AM3 interchange record."""
    path = Path(path)
    data = path.read_bytes()
    if len(data) == PAYLOAD_LEN:
        data = default_amp_header() + data
    elif (
        len(data) == RECORD_LEN + LMT_LEN
        and data[RECORD_LEN : RECORD_LEN + 4] == LMT_MAGIC
    ):
        data = data[:RECORD_LEN]
    elif len(data) != RECORD_LEN:
        raise CaptureEditError(
            f"capture is {len(data)} bytes; expected {PAYLOAD_LEN} bare bytes "
            f"or {RECORD_LEN} headered bytes"
        )
    # Normalise the known am2converter header defect on the wire while leaving
    # the source file untouched. Firmware V19 expects AM2/AM3 magic.
    if data[:2] == b"\x00\x00" and data[2] in (0x32, 0x33) and data[3] == 0:
        data = b"AM" + data[2:]
    parsed = parse_capture(path, data)
    if not parsed.ok:
        raise CaptureEditError("; ".join(parsed.errors))
    if data[:4] not in KNOWN_MAGIC:
        raise CaptureEditError(
            f"capture magic {data[:4].hex()} is not loadable by firmware V19; "
            "device writes require AM2\\0 or AM3\\0"
        )
    return set_capture_name(data, name)


def append_amp_runtime(record: bytes, dylib_path: Path | None = None) -> bytes:
    """Append the exact 68-byte LMT block M-EFCS computes before USB upload.

    This calls the installed editor's small native DSP helper, not its GUI. The
    function is deterministic: its output was matched byte-for-byte against a
    captured M-EFCS transfer. A pure-Python replacement remains a later
    portability task; failing to find the helper is explicit, never silent.
    """
    if len(record) != RECORD_LEN:
        raise CaptureEditError(
            f"AMP runtime generation needs {RECORD_LEN} bytes, got {len(record)}"
        )
    library_path = Path(dylib_path or DEFAULT_AMX_DYLIB)
    if not library_path.is_file():
        raise CaptureEditError(
            f"AMP DSP helper not found at {library_path}; install M-EFCS or "
            "provide its libamx_parser.dylib"
        )
    buffer = ctypes.create_string_buffer(record + bytes(LMT_LEN), RECORD_LEN + LMT_LEN)
    try:
        library = ctypes.CDLL(str(library_path))
        function = library.calc_bias_gru
        function.argtypes = [ctypes.c_void_p]
        function.restype = ctypes.c_int
        # The vendor helper prints three unconditional "GRU Unit init" lines
        # to C stdout.  Keep blackboxctl's human and --json output deterministic
        # by silencing only that native call (Python's own stdout is restored
        # immediately afterwards).
        libc = ctypes.CDLL(None)
        libc.fflush.argtypes = [ctypes.c_void_p]
        libc.fflush.restype = ctypes.c_int
        libc.fflush(None)
        saved_stdout = os.dup(1)
        null_stdout = os.open(os.devnull, os.O_WRONLY)
        try:
            os.dup2(null_stdout, 1)
            result = function(ctypes.addressof(buffer))
            libc.fflush(None)
        finally:
            os.dup2(saved_stdout, 1)
            os.close(saved_stdout)
            os.close(null_stdout)
    except (OSError, AttributeError) as exc:
        raise CaptureEditError(f"could not run AMP DSP helper: {exc}") from exc
    device_record = buffer.raw
    if result != 0 or device_record[RECORD_LEN : RECORD_LEN + 4] != LMT_MAGIC:
        raise CaptureEditError(
            f"AMP DSP helper failed (return {result}, missing LMT block)"
        )
    return device_record


def build_amp_device_record(
    path: Path, name: str, dylib_path: Path | None = None
) -> bytes:
    """Build the exact 6,272-byte AMP record transmitted by M-EFCS."""
    return append_amp_runtime(build_amp_file_record(path, name), dylib_path)


def backup_path(path: Path) -> Path:
    """Where :func:`write_with_backup` puts the untouched original."""
    return path.with_name(path.name + ".bak")


def write_with_backup(path: Path, data: bytes, force: bool = False) -> Path:
    """Atomically back up and replace *path*. Return the backup path."""
    path = Path(path)
    backup = backup_path(path)
    try:
        storage.write_bytes_atomic(backup, path.read_bytes(), replace=force)
    except storage.DestinationExistsError as exc:
        raise CaptureEditError(
            f"backup {exc.path} already exists; refusing to overwrite it. Move it "
            "aside or pass --force"
        ) from exc
    except OSError as exc:
        raise CaptureEditError(f"could not preserve backup {backup}: {exc}") from exc
    try:
        storage.write_bytes_atomic(path, data, replace=True)
    except OSError as exc:
        raise CaptureEditError(
            f"backup preserved at {backup}, but could not replace {path}: {exc}"
        ) from exc
    return backup


# ---------------------------------------------------------------------------
# Impulse responses
# ---------------------------------------------------------------------------


@dataclass
class ImpulseResponse:
    """A parsed IR .wav file."""

    path: Path
    size: int
    channels: int | None = None
    sample_rate: int | None = None
    sample_width_bits: int | None = None
    format_tag: int | None = None
    frames: int | None = None
    duration_s: float | None = None
    chunks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "kind": "ir",
            "size": self.size,
            "channels": self.channels,
            "sample_rate": self.sample_rate,
            "sample_width_bits": self.sample_width_bits,
            "format_tag": self.format_tag,
            "frames": self.frames,
            "duration_s": self.duration_s,
            "chunks": self.chunks,
            "errors": self.errors,
            "warnings": self.warnings,
            "ok": self.ok,
        }


def _riff_walk(data: bytes) -> list[tuple[str, int, int]]:
    """Walk the top-level RIFF chunks as (id, data offset, size)."""
    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return []
    found: list[tuple[str, int, int]] = []
    offset = 12
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4].decode("latin1").strip()
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        found.append((chunk_id, offset + 8, size))
        offset += 8 + size + (size & 1)
    return found


def _riff_chunks(data: bytes) -> list[str]:
    """Walk the top-level RIFF chunk ids. Tolerant of odd-sized chunks."""
    return [chunk_id for chunk_id, _, _ in _riff_walk(data)]


def parse_ir(path: Path, data: bytes | None = None) -> ImpulseResponse:
    """Inspect a ``.wav`` IR and check it against the device's documented limits."""
    path = Path(path)
    if data is None:
        data = path.read_bytes()
    ir = ImpulseResponse(path=path, size=len(data))

    if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        ir.errors.append("not a RIFF/WAVE file (bad magic)")
        return ir
    declared_riff_end = 8 + int.from_bytes(data[4:8], "little")
    if declared_riff_end > len(data):
        ir.errors.append(
            f"truncated RIFF: header declares {declared_riff_end} bytes, "
            f"file has {len(data)}"
        )
        return ir
    walk = _riff_walk(data)
    ir.chunks = [chunk_id for chunk_id, _, _ in walk]
    truncated = next(
        ((cid, off, size) for cid, off, size in walk if off + size > len(data)), None
    )
    if truncated is not None:
        cid, off, size = truncated
        ir.errors.append(
            f"truncated {cid!r} chunk: declares {size} bytes at {off}, "
            f"only {max(0, len(data) - off)} remain"
        )
        return ir

    # Parse `fmt ` directly rather than through the stdlib `wave` module, which
    # refuses every format tag except 1 (PCM) and turns that refusal into an
    # exception. The pedal's own factory IR in CAB slot 10, 10SoldSC412.wav, is
    # tag 3 (IEEE float) - rejecting it would condemn a file the device is
    # demonstrably running.
    fmt = next(((off, size) for cid, off, size in walk if cid == "fmt"), None)
    if fmt is None:
        ir.errors.append("no 'fmt ' chunk")
        return ir
    off, size = fmt
    if size < 16 or off + 16 > len(data):
        ir.errors.append(f"'fmt ' chunk is {size} bytes, need at least 16")
        return ir
    (tag, channels, rate, _byte_rate, block_align, bits) = struct.unpack_from(
        "<HHIIHH", data, off
    )
    ir.format_tag = tag
    ir.channels = channels
    ir.sample_rate = rate
    ir.sample_width_bits = bits

    structural_errors = []
    if channels < 1:
        structural_errors.append(f"invalid channel count {channels}")
    if rate < 1:
        structural_errors.append(f"invalid sample rate {rate}")
    if block_align < 1:
        structural_errors.append(f"invalid block align {block_align}")
    if bits < 1:
        structural_errors.append(f"invalid sample width {bits}")
    if structural_errors:
        ir.errors.extend(structural_errors)
        return ir

    if tag == WAVE_FORMAT_EXTENSIBLE and size >= 40 and off + 40 <= len(data):
        sub = int.from_bytes(data[off + 24 : off + 26], "little")
        ir.format_tag = sub
        tag = sub
    if tag not in (WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT):
        ir.errors.append(
            f"unsupported WAVE format tag {tag} (known: {WAVE_FORMAT_PCM}=PCM, "
            f"{WAVE_FORMAT_IEEE_FLOAT}=IEEE float, "
            f"{WAVE_FORMAT_EXTENSIBLE}=extensible)"
        )
        return ir
    if tag == WAVE_FORMAT_IEEE_FLOAT:
        ir.warnings.append(
            f"{bits}-bit IEEE float samples rather than integer PCM. This is "
            f"NOT a defect: the device's own CAB slot 10 IR (10SoldSC412.wav) "
            f"is 32-bit float"
        )

    data_chunk = next(((o, s) for cid, o, s in walk if cid == "data"), None)
    if data_chunk is None:
        ir.errors.append("no 'data' chunk")
        return ir
    _, data_size = data_chunk
    if data_size % block_align:
        ir.errors.append(
            f"WAV 'data' chunk has {data_size} bytes, not divisible by "
            f"block align {block_align}; trailing partial frames are unsafe"
        )
        return ir
    ir.frames = data_size // block_align

    if ir.sample_rate and ir.frames is not None:
        ir.duration_s = ir.frames / ir.sample_rate

    if ir.sample_rate != IR_DOCUMENTED_RATE:
        ir.warnings.append(
            f"sample rate {ir.sample_rate} Hz; the manual documents "
            f"{IR_DOCUMENTED_RATE} Hz. M-EFCS appears to convert on import, but "
            f"that is HYPOTHESIS, not confirmed"
        )
    if ir.channels != IR_DOCUMENTED_CHANNELS:
        ir.warnings.append(f"{ir.channels} channels; the manual documents mono")
    if ir.sample_width_bits != IR_DOCUMENTED_BITS:
        ir.warnings.append(
            f"{ir.sample_width_bits}-bit samples; the manual documents "
            f"{IR_DOCUMENTED_BITS}-bit. That is the manual's figure, not a "
            f"requirement - slot 10's factory IR is 32-bit"
        )
    if ir.frames and ir.frames > IR_TAPS:
        ir.warnings.append(
            f"{ir.frames} frames exceeds M-EFCS's {IR_TAPS}-sample "
            f"({IR_TAPS / IR_DOCUMENTED_RATE * 1000:.1f} ms) staging transfer; "
            "the tail is truncated on conversion"
        )
    if ir.frames == 0:
        ir.errors.append("no audio frames")
    return ir


def _wave_format(data: bytes) -> tuple[int, int, int, int, int, bytes]:
    """Return tag, channels, rate, block-align, bits and raw audio bytes."""
    walk = _riff_walk(data)
    fmt = next(((off, size) for cid, off, size in walk if cid == "fmt"), None)
    audio = next(((off, size) for cid, off, size in walk if cid == "data"), None)
    if fmt is None or audio is None:
        raise CaptureEditError("WAV needs both 'fmt ' and 'data' chunks")
    off, size = fmt
    if size < 16 or off + 16 > len(data):
        raise CaptureEditError("WAV 'fmt ' chunk is truncated")
    tag, channels, rate, _byte_rate, align, bits = struct.unpack_from(
        "<HHIIHH", data, off
    )
    if tag == WAVE_FORMAT_EXTENSIBLE and size >= 40 and off + 40 <= len(data):
        tag = int.from_bytes(data[off + 24 : off + 26], "little")
    if tag not in (WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT):
        raise CaptureEditError(f"unsupported WAV format tag {tag}")
    if channels < 1 or rate < 1 or align < 1:
        raise CaptureEditError("invalid WAV channels, sample rate, or block align")
    data_off, data_size = audio
    if data_off + data_size > len(data):
        raise CaptureEditError(
            f"WAV 'data' chunk declares {data_size} bytes, but only "
            f"{max(0, len(data) - data_off)} remain"
        )
    if data_size % align:
        raise CaptureEditError(
            f"WAV 'data' chunk has {data_size} bytes, not divisible by "
            f"block align {align}"
        )
    return tag, channels, rate, align, bits, data[data_off : data_off + data_size]


def _decode_sample(raw: bytes, tag: int, bits: int) -> float:
    """Decode one WAV channel sample to approximately -1.0..1.0."""
    if tag == WAVE_FORMAT_IEEE_FLOAT:
        if bits == 32 and len(raw) == 4:
            value = float(struct.unpack("<f", raw)[0])
        elif bits == 64 and len(raw) == 8:
            value = float(struct.unpack("<d", raw)[0])
        else:
            raise CaptureEditError(f"unsupported IEEE-float sample width {bits}")
        if not math.isfinite(value):
            raise CaptureEditError("WAV contains a non-finite IEEE-float sample")
        return value
    width = (bits + 7) // 8
    if width != len(raw) or bits not in (8, 16, 24, 32):
        raise CaptureEditError(f"unsupported PCM sample width {bits}")
    if bits == 8:
        return (raw[0] - 128) / 128.0
    value = int.from_bytes(raw, "little", signed=True)
    return value / float(1 << (bits - 1))


def _encode_s24(value: float) -> bytes:
    """Clamp a normalized float and encode one signed 24-bit LE sample."""
    if value >= 1.0:
        integer = (1 << 23) - 1
    elif value <= -1.0:
        integer = -(1 << 23)
    else:
        integer = round(value * (1 << 23))
        integer = max(-(1 << 23), min((1 << 23) - 1, integer))
    return int(integer).to_bytes(3, "little", signed=True)


def wav_to_cab_samples(path: Path, data: bytes | None = None) -> bytes:
    """Convert a WAV to M-EFCS's exact 2,048 x signed-24-bit mono payload.

    Already-compliant files take a byte-exact fast path. Other PCM/float files
    are mixed to mono and linearly resampled to 44.1 kHz, then truncated or
    zero-padded to the captured M-EFCS staging-record length.
    """
    path = Path(path)
    if data is None:
        data = path.read_bytes()
    parsed = parse_ir(path, data)
    if not parsed.ok:
        raise CaptureEditError("; ".join(parsed.errors))
    tag, channels, rate, align, bits, audio = _wave_format(data)
    wanted = IR_TAPS * 3
    if (
        tag == WAVE_FORMAT_PCM
        and channels == 1
        and rate == SAMPLE_RATE
        and bits == 24
        and align == 3
    ):
        return (audio[:wanted] + bytes(wanted))[:wanted]

    sample_width = (bits + 7) // 8
    minimum_align = sample_width * channels
    if align < minimum_align:
        raise CaptureEditError(
            f"WAV block align {align} is smaller than {minimum_align}"
        )
    frame_count = len(audio) // align
    if frame_count == 0:
        raise CaptureEditError("WAV has no complete audio frames")
    mono: list[float] = []
    for frame_index in range(frame_count):
        base = frame_index * align
        values = []
        for channel in range(channels):
            start = base + channel * sample_width
            values.append(
                _decode_sample(audio[start : start + sample_width], tag, bits)
            )
        mono.append(sum(values) / channels)

    result = bytearray()
    for output_index in range(IR_TAPS):
        source_position = output_index * rate / SAMPLE_RATE
        left = int(source_position)
        if left >= len(mono):
            value = 0.0
        else:
            right = min(left + 1, len(mono) - 1)
            fraction = source_position - left
            value = mono[left] + (mono[right] - mono[left]) * fraction
        result += _encode_s24(value)
    return bytes(result)


def build_cab_record(path: Path, name: str = "", level: int = 50) -> bytes:
    """Build the exact 6,164-byte CAB staging record captured from M-EFCS."""
    try:
        encoded_name = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise CaptureEditError("CAB name must contain printable ASCII only") from exc
    if len(encoded_name) > NAME_MAX:
        raise CaptureEditError(
            f"CAB name is {len(encoded_name)} bytes; maximum is {NAME_MAX}"
        )
    if any(byte < 0x20 or byte > 0x7E for byte in encoded_name):
        raise CaptureEditError("CAB name must contain printable ASCII only")
    if not 0 <= level <= 100:
        raise CaptureEditError("CAB level must be 0..100")
    header = (
        b"CAB\x00" + encoded_name.ljust(NAME_FIELD, b"\x00") + b"\x01" + bytes((level,))
    )
    record = header + wav_to_cab_samples(path)
    if len(record) != 20 + IR_TAPS * 3:
        raise AssertionError("internal CAB record size mismatch")
    return record


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def classify(path: Path) -> str:
    """Return "capture", "ir" or "unknown" from the file suffix."""
    suffix = Path(path).suffix.lower()
    if suffix in CAPTURE_SUFFIXES:
        return "capture"
    if suffix in IR_SUFFIXES:
        return "ir"
    return "unknown"


def inspect(path: Path) -> Capture | ImpulseResponse:
    """Parse a file as whichever family its suffix (or size) indicates."""
    path = Path(path)
    kind = classify(path)
    if kind == "capture":
        return parse_capture(path)
    if kind == "ir":
        return parse_ir(path)
    # Fall back on content: capture records have two fixed sizes.
    size = path.stat().st_size
    if size in (PAYLOAD_LEN, RECORD_LEN, RECORD_LEN + LMT_LEN, AM4_RECORD_LEN):
        return parse_capture(path)
    data = path.read_bytes()[:12]
    if data[0:4] == b"RIFF":
        return parse_ir(path)
    result = Capture(path=path, size=size, has_header=False)
    result.errors.append(
        f"unrecognised file: suffix {path.suffix!r} is neither a capture "
        f"{CAPTURE_SUFFIXES} nor an IR {IR_SUFFIXES}, and the content matches "
        f"neither a {RECORD_LEN}-byte capture record nor a RIFF/WAVE header"
    )
    return result
