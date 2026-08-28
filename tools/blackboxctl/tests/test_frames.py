"""Frame build/parse round trip and reply validation. GPL-3.0."""

from __future__ import annotations

import pytest

from blackboxctl import protocol
from fixtures import device_frames as fx


@pytest.mark.parametrize("name", sorted(fx.READ_COMMANDS))
def test_read_command_literals(name):
    builders = {
        "ram_dump": protocol.cmd_ram_dump,
        "preset_sync": protocol.cmd_preset_sync,
        "cab_names": protocol.cmd_read_cab_names,
        "amp_names": protocol.cmd_read_amp_names,
        "flash_00": lambda: protocol.cmd_read_flash_preset(0),
        "flash_02": lambda: protocol.cmd_read_flash_preset(2),
        "flash_40": lambda: protocol.cmd_read_flash_preset(40),
    }
    assert builders[name]() == fx.READ_COMMANDS[name]


@pytest.mark.parametrize("name", sorted(fx.UNIQUE_REPLIES))
def test_every_real_reply_is_well_formed(name):
    frame = protocol.parse_frame(fx.UNIQUE_REPLIES[name])
    assert frame.checksum_ok
    assert frame.length_ok, f"length {frame.length} vs payload {len(frame.payload)}"
    assert frame.size_ok
    assert frame.well_formed


def test_build_frame_output_always_parses_as_well_formed():
    """length_ok holds for requests too; size_ok is a REPLY-only invariant.

    A request states the size it WANTS and carries no payload, so size != 0 is
    correct there. Replies echo size == len(payload).
    """
    for size in (4, 92, 280):
        raw = protocol.build_read(protocol.ADDR_LIVE_RAM, size)
        frame = protocol.parse_frame(raw)
        assert frame.length_ok
        assert frame.payload == b"" and frame.size == size


def test_build_frame_refuses_the_undetermined_checksum_region():
    """Above 247 payload bytes the two checksum formulas diverge.

    Previously build_frame happily emitted a frame its own parse_frame
    rejected. It must refuse instead of guessing.
    """
    protocol.build_frame(protocol.MAGIC_WRITE, protocol.SPACE_STRING,
                         0x90000000, 247, bytes(247))
    with pytest.raises(ValueError, match="247"):
        protocol.build_frame(protocol.MAGIC_WRITE, protocol.SPACE_STRING,
                             0x90000000, 280, bytes(280))


def test_a_truncated_reply_is_detectable():
    """A 61-byte truncation of the 107-byte RAM dump parses but is not ok."""
    truncated = fx.REPLY_RAM_DUMP[:60] + fx.REPLY_RAM_DUMP[-1:]
    frame = protocol.parse_frame(truncated)
    assert frame.size == 92
    assert len(frame.payload) == 46
    assert not frame.size_ok
    assert not frame.well_formed


def test_ack_frame_is_too_short_for_the_confirmed_field_model():
    """Documented, never observed, and inconsistent with the field model."""
    assert len(protocol.ACK_FRAME) == 8
    with pytest.raises(ValueError, match="too short"):
        protocol.parse_frame(protocol.ACK_FRAME)
