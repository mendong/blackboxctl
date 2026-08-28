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
    "Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS")
SLOT10_IR = LIVE_LIBRARY / "cabFile" / "10SoldSC412.wav"


def make_wav(tag: int, channels: int, rate: int, bits: int, frames: int) -> bytes:
    block_align = channels * bits // 8
    data = bytes(frames * block_align)
    fmt = struct.pack("<HHIIHH", tag, channels, rate,
                      rate * block_align, block_align, bits)
    body = b"WAVE" + b"fmt " + len(fmt).to_bytes(4, "little") + fmt \
        + b"data" + len(data).to_bytes(4, "little") + data
    return b"RIFF" + len(body).to_bytes(4, "little") + body


def make_capture(magic: bytes = b"AM2\x00", name: bytes = b"TEST\x00") -> bytes:
    header = bytearray(captures.HEADER_LEN)
    header[0:4] = magic
    header[4:4 + len(name)] = name
    header[captures.OFF_MIX] = 50
    header[captures.OFF_LEVEL] = 50
    header[captures.OFF_GAIN_MAX] = 100
    header[captures.OFF_GAIN_MIN] = 0
    for band, freq in enumerate((100.0, 1000.0, 5000.0)):
        struct.pack_into("<fff", header, captures.OFF_EQ + band * 12,
                         freq, -12.0, 12.0)
    return bytes(header) + bytes(captures.PAYLOAD_LEN)


# --- IR parsing -----------------------------------------------------------


def test_float_wav_is_valid_not_an_error():
    """32-bit IEEE float, mono, 44.1k, 1020 frames - the shape of slot 10's IR."""
    ir = captures.parse_ir(Path("synthetic.wav"),
                           make_wav(captures.WAVE_FORMAT_IEEE_FLOAT, 1, 44100,
                                    32, 1020))
    assert ir.ok, ir.errors
    assert ir.format_tag == captures.WAVE_FORMAT_IEEE_FLOAT
    assert (ir.channels, ir.sample_rate, ir.sample_width_bits, ir.frames) \
        == (1, 44100, 32, 1020)
    assert any("IEEE float" in w for w in ir.warnings)


def test_pcm_24bit_mono_is_clean():
    ir = captures.parse_ir(Path("s.wav"),
                           make_wav(captures.WAVE_FORMAT_PCM, 1, 44100, 24, 1024))
    assert ir.ok and not ir.warnings


def test_extensible_wav_resolves_its_subformat():
    fmt = (struct.pack("<HHIIHH", captures.WAVE_FORMAT_EXTENSIBLE, 1, 44100,
                       44100 * 4, 4, 32)          # 16 bytes
           + struct.pack("<HHI", 22, 32, 0)       # cbSize, validBits, mask
           + struct.pack("<H", captures.WAVE_FORMAT_IEEE_FLOAT)
           + bytes(14))                           # rest of the SubFormat GUID
    assert len(fmt) == 40
    data = bytes(1024 * 4)
    body = b"WAVE" + b"fmt " + len(fmt).to_bytes(4, "little") + fmt \
        + b"data" + len(data).to_bytes(4, "little") + data
    ir = captures.parse_ir(Path("x.wav"),
                           b"RIFF" + len(body).to_bytes(4, "little") + body)
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
    parsed = captures.parse_capture(Path("x.am2data"),
                                    make_capture(magic=b"\x00\x00\x32\x00"))
    assert parsed.ok, parsed.errors
    assert not parsed.magic_ok
    assert any("am2converter" in w for w in parsed.warnings)
    assert not any("InitData damage" in w for w in parsed.warnings)


def test_a_genuinely_unknown_magic_is_still_an_error():
    parsed = captures.parse_capture(Path("x.am2data"),
                                    make_capture(magic=b"XYZ!"))
    assert not parsed.ok


def test_non_printable_name_is_a_warning_not_an_error():
    parsed = captures.parse_capture(Path("x.am2data"),
                                    make_capture(name=b"A\x01B\x00"))
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
            captures.repair_capture_magic(
                make_capture(magic=bytes((0, 0, digit, 0))))


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
