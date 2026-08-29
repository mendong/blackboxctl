"""Capture and IR parsing. GPL-3.0.

The regressions here are all "we used to refuse a file the device is actually
running", which is as damaging as accepting a broken one.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from blackboxctl import captures

LIVE_LIBRARY = Path.home() / (
    "Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS"
)
SLOT10_IR = LIVE_LIBRARY / "cabFile" / "10SoldSC412.wav"


def make_wav(tag: int, channels: int, rate: int, bits: int, frames: int) -> bytes:
    block_align = channels * bits // 8
    data = bytes(frames * block_align)
    fmt = struct.pack(
        "<HHIIHH", tag, channels, rate, rate * block_align, block_align, bits
    )
    body = (
        b"WAVE"
        + b"fmt "
        + len(fmt).to_bytes(4, "little")
        + fmt
        + b"data"
        + len(data).to_bytes(4, "little")
        + data
    )
    return b"RIFF" + len(body).to_bytes(4, "little") + body


def make_capture(magic: bytes = b"AM2\x00", name: bytes = b"TEST\x00") -> bytes:
    header = bytearray(captures.HEADER_LEN)
    header[0:4] = magic
    header[4 : 4 + len(name)] = name
    header[captures.OFF_MIX] = 50
    header[captures.OFF_LEVEL] = 50
    header[captures.OFF_GAIN_MAX] = 100
    header[captures.OFF_GAIN_MIN] = 0
    for band, freq in enumerate((100.0, 1000.0, 5000.0)):
        struct.pack_into("<fff", header, captures.OFF_EQ + band * 12, freq, -12.0, 12.0)
    return bytes(header) + bytes(captures.PAYLOAD_LEN)


# --- IR parsing -----------------------------------------------------------


def test_float_wav_is_valid_not_an_error():
    """32-bit IEEE float, mono, 44.1k, 1020 frames - the shape of slot 10's IR."""
    ir = captures.parse_ir(
        Path("synthetic.wav"),
        make_wav(captures.WAVE_FORMAT_IEEE_FLOAT, 1, 44100, 32, 1020),
    )
    assert ir.ok, ir.errors
    assert ir.format_tag == captures.WAVE_FORMAT_IEEE_FLOAT
    assert (ir.channels, ir.sample_rate, ir.sample_width_bits, ir.frames) == (
        1,
        44100,
        32,
        1020,
    )
    assert any("IEEE float" in w for w in ir.warnings)


def test_pcm_24bit_mono_is_clean():
    ir = captures.parse_ir(
        Path("s.wav"), make_wav(captures.WAVE_FORMAT_PCM, 1, 44100, 24, 1024)
    )
    assert ir.ok and not ir.warnings


def test_extensible_wav_resolves_its_subformat():
    fmt = (
        struct.pack(
            "<HHIIHH", captures.WAVE_FORMAT_EXTENSIBLE, 1, 44100, 44100 * 4, 4, 32
        )  # 16 bytes
        + struct.pack("<HHI", 22, 32, 0)  # cbSize, validBits, mask
        + struct.pack("<H", captures.WAVE_FORMAT_IEEE_FLOAT)
        + bytes(14)
    )  # rest of the SubFormat GUID
    assert len(fmt) == 40
    data = bytes(1024 * 4)
    body = (
        b"WAVE"
        + b"fmt "
        + len(fmt).to_bytes(4, "little")
        + fmt
        + b"data"
        + len(data).to_bytes(4, "little")
        + data
    )
    ir = captures.parse_ir(
        Path("x.wav"), b"RIFF" + len(body).to_bytes(4, "little") + body
    )
    assert ir.ok, ir.errors
    assert ir.format_tag == captures.WAVE_FORMAT_IEEE_FLOAT


@pytest.mark.skipif(not SLOT10_IR.is_file(), reason="live M-EFCS library absent")
def test_the_pedals_own_slot_10_ir_validates():
    """The pedal reports CAB slot 10 as 'SoldSC412'. It is 32-bit float.

    Refusing it as 'unreadable WAVE data: unknown format: 3' condemned a file
    the device is demonstrably running.
    """
    ir = captures.parse_ir(SLOT10_IR)
    assert ir.ok, ir.errors
    assert ir.format_tag == captures.WAVE_FORMAT_IEEE_FLOAT
    assert ir.channels == 1 and ir.sample_rate == 44100


def test_a_non_riff_file_is_still_an_error():
    ir = captures.parse_ir(Path("x.wav"), b"not a wav at all")
    assert not ir.ok


def test_truncated_audio_is_rejected_instead_of_zero_padded(tmp_path):
    complete = make_wav(captures.WAVE_FORMAT_PCM, 1, 44100, 24, 2048)
    truncated = complete[:-6000]
    path = tmp_path / "truncated.wav"
    path.write_bytes(truncated)
    ir = captures.parse_ir(path)
    assert not ir.ok
    assert any("truncated RIFF" in error for error in ir.errors)
    with pytest.raises(captures.CaptureEditError, match="truncated RIFF"):
        captures.build_cab_record(path, "TRUNC")


@pytest.mark.parametrize(
    ("offset", "width", "message"),
    [
        (22, 2, "channel count"),
        (24, 4, "sample rate"),
        (32, 2, "block align"),
        (34, 2, "sample width"),
    ],
)
def test_structurally_invalid_wav_header_is_rejected(offset, width, message):
    data = bytearray(make_wav(captures.WAVE_FORMAT_PCM, 1, 44100, 24, 1))
    data[offset : offset + width] = bytes(width)

    parsed = captures.parse_ir(Path("invalid.wav"), bytes(data))

    assert not parsed.ok
    assert any(message in error for error in parsed.errors)


def test_partial_pcm_frame_is_rejected_instead_of_staged(tmp_path):
    malformed = bytearray(make_wav(captures.WAVE_FORMAT_PCM, 1, 44100, 24, 1))
    malformed.extend(b"\xff")
    malformed[4:8] = (len(malformed) - 8).to_bytes(4, "little")
    malformed[40:44] = (4).to_bytes(4, "little")
    path = tmp_path / "partial-frame.wav"
    path.write_bytes(malformed)

    parsed = captures.parse_ir(path)

    assert not parsed.ok
    assert any("not divisible by block align 3" in error for error in parsed.errors)
    with pytest.raises(captures.CaptureEditError, match="not divisible"):
        captures.wav_to_cab_samples(path)


def test_build_cab_record_matches_captured_layout(tmp_path):
    path = tmp_path / "cab.wav"
    path.write_bytes(make_wav(captures.WAVE_FORMAT_PCM, 1, 44100, 24, 2048))
    record = captures.build_cab_record(path, "20AC_TAYLOR", level=50)
    assert len(record) == 6164
    assert record[:4] == b"CAB\x00"
    assert record[4:18] == b"20AC_TAYLOR".ljust(14, b"\x00")
    assert record[18:20] == b"\x01\x32"
    assert record[20:] == bytes(6144)


def test_build_cab_record_converts_float_stereo_and_pads(tmp_path):
    path = tmp_path / "float.wav"
    path.write_bytes(make_wav(captures.WAVE_FORMAT_IEEE_FLOAT, 2, 48000, 32, 100))
    record = captures.build_cab_record(path, "FLOAT")
    assert len(record) == 6164
    assert record[20:] == bytes(6144)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_build_cab_record_refuses_non_finite_float_samples(tmp_path, value):
    fmt = struct.pack(
        "<HHIIHH", captures.WAVE_FORMAT_IEEE_FLOAT, 1, 44100, 44100 * 4, 4, 32
    )
    audio = struct.pack("<f", value)
    body = (
        b"WAVE"
        + b"fmt "
        + len(fmt).to_bytes(4, "little")
        + fmt
        + b"data"
        + len(audio).to_bytes(4, "little")
        + audio
    )
    path = tmp_path / "non-finite.wav"
    path.write_bytes(b"RIFF" + len(body).to_bytes(4, "little") + body)
    with pytest.raises(captures.CaptureEditError, match="non-finite"):
        captures.build_cab_record(path, "BADFLOAT")


def test_build_cab_record_refuses_overlong_name(tmp_path):
    path = tmp_path / "cab.wav"
    path.write_bytes(make_wav(captures.WAVE_FORMAT_PCM, 1, 44100, 24, 1))
    with pytest.raises(captures.CaptureEditError, match="maximum is 13"):
        captures.build_cab_record(path, "x" * 14)


# --- Capture parsing ------------------------------------------------------


def test_good_capture_parses_clean():
    parsed = captures.parse_capture(Path("g.am2Data"), make_capture())
    assert parsed.ok, parsed.errors
    assert parsed.name == "TEST"
    assert parsed.magic_ok


def test_am2converter_magic_is_a_warning_not_an_error():
    """00 00 32 00 is what am2converter WRITES (am2.go:14 InitData), not damage.

    318/1295 headered files in the community pack and 4 files presets/library.md
    requires carry it, all already in the live M-EFCS library. Whether the
    device accepts it is UNTESTED, so refusing overstates the evidence.
    """
    parsed = captures.parse_capture(
        Path("x.am2data"), make_capture(magic=b"\x00\x00\x32\x00")
    )
    assert parsed.ok, parsed.errors
    assert not parsed.magic_ok
    assert any("am2converter" in w for w in parsed.warnings)
    assert not any("InitData damage" in w for w in parsed.warnings)


def test_a_genuinely_unknown_magic_is_still_an_error():
    parsed = captures.parse_capture(Path("x.am2data"), make_capture(magic=b"XYZ!"))
    assert not parsed.ok


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_amp_device_record_refuses_non_finite_eq_bounds(tmp_path, value):
    data = bytearray(make_capture())
    struct.pack_into("<f", data, captures.OFF_EQ + 4, value)
    path = tmp_path / "unsafe.am2data"
    path.write_bytes(data)

    parsed = captures.parse_capture(path)
    assert not parsed.ok
    assert any("non-finite" in error for error in parsed.errors)
    with pytest.raises(captures.CaptureEditError, match="non-finite"):
        captures.build_amp_file_record(path, "UNSAFE")


@pytest.mark.parametrize("digit", (0x35, 0x38))
def test_amp_device_record_refuses_unexplained_corrupt_magic(tmp_path, digit):
    path = tmp_path / "unsafe.am2data"
    path.write_bytes(make_capture(magic=bytes((0, 0, digit, 0))))

    inspected = captures.parse_capture(path)
    assert inspected.ok
    assert any("inspection only" in warning for warning in inspected.warnings)
    assert not any("am2converter" in warning for warning in inspected.warnings)

    with pytest.raises(captures.CaptureEditError, match="not loadable"):
        captures.build_amp_file_record(path, "UNSAFE")


def test_non_printable_name_is_a_warning_not_an_error():
    parsed = captures.parse_capture(Path("x.am2data"), make_capture(name=b"A\x01B\x00"))
    assert parsed.ok, parsed.errors
    assert any("non-printable" in w for w in parsed.warnings)


def test_am4_record_is_a_warning_not_an_error():
    data = make_capture() + bytes(captures.AM4_RECORD_LEN - captures.RECORD_LEN)
    parsed = captures.parse_capture(Path("x.am4"), data)
    assert parsed.ok, parsed.errors
    assert any("AM4" in w for w in parsed.warnings)


def test_bad_size_is_still_an_error():
    parsed = captures.parse_capture(Path("x.am2"), b"\x00" * 1234)
    assert not parsed.ok


# --- Header edits ---------------------------------------------------------


def test_repair_magic_preserves_the_version_digit():
    """It used to rewrite byte 2, silently turning 00 00 35 00 into AM2\\0."""
    for digit in (0x32, 0x33):
        data = make_capture(magic=bytes((0, 0, digit, 0)))
        repaired = captures.repair_capture_magic(data)
        assert repaired[0:4] == b"AM" + bytes((digit, 0)), digit
        assert repaired[4:] == data[4:]


def test_repair_magic_refuses_an_unrecognised_version_digit():
    for digit in (0x35, 0x38):
        with pytest.raises(captures.CaptureEditError, match="not '2' or '3'"):
            captures.repair_capture_magic(make_capture(magic=bytes((0, 0, digit, 0))))


def test_repair_magic_refuses_an_already_good_file():
    with pytest.raises(captures.CaptureEditError, match="already"):
        captures.repair_capture_magic(make_capture())


def test_set_capture_name_touches_only_the_name_field():
    data = make_capture()
    renamed = captures.set_capture_name(data, "Hello")
    assert renamed[0:4] == data[0:4]
    assert renamed[4:18] == b"Hello".ljust(14, b"\x00")
    assert renamed[18:] == data[18:]
    assert len(renamed) == len(data)


def test_set_capture_name_rejects_an_overlong_name():
    with pytest.raises(captures.CaptureEditError, match="at most"):
        captures.set_capture_name(make_capture(), "x" * 14)


def test_bare_amp_capture_gets_standard_header_and_name(tmp_path):
    path = tmp_path / "bare.am2"
    path.write_bytes(bytes(captures.PAYLOAD_LEN))
    record = captures.build_amp_file_record(path, "20AC_PREAMP")
    assert len(record) == captures.RECORD_LEN
    assert record[:4] == b"AM2\x00"
    assert record[4:18] == b"20AC_PREAMP".ljust(14, b"\x00")
    assert record[18:22] == bytes((100, 100, 60, 30))
    assert struct.unpack_from("<fff", record, 24) == (100.0, -6.0, 6.0)


@pytest.mark.skipif(
    not captures.DEFAULT_AMX_DYLIB.is_file(),
    reason="installed M-EFCS DSP helper absent",
)
def test_amp_runtime_helper_appends_lmt_deterministically(tmp_path):
    path = tmp_path / "capture.am2Data"
    path.write_bytes(make_capture())
    record = captures.build_amp_device_record(path, "AMP_TEST")
    assert len(record) == captures.RECORD_LEN + captures.LMT_LEN
    assert record[captures.RECORD_LEN : captures.RECORD_LEN + 4] == b"LMT\x00"
