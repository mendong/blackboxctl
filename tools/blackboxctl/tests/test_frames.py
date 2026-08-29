"""Frame build/parse round trip and reply validation. GPL-3.0."""

from __future__ import annotations

import pytest
from fixtures import device_frames as fx

from blackboxctl import protocol


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


def test_build_frame_accepts_captured_chunk_size_and_refuses_larger():
    raw = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_STRING,
        0,
        protocol.LIBRARY_CHUNK_SIZE,
        bytes(protocol.LIBRARY_CHUNK_SIZE),
    )
    assert protocol.parse_frame(raw).well_formed
    with pytest.raises(ValueError, match=r"1,015|1015"):
        protocol.build_frame(
            protocol.MAGIC_WRITE,
            protocol.SPACE_STRING,
            0,
            protocol.LIBRARY_CHUNK_SIZE + 1,
            bytes(protocol.LIBRARY_CHUNK_SIZE + 1),
        )


def test_a_truncated_reply_is_detectable():
    """A 61-byte truncation of the 107-byte RAM dump parses but is not ok."""
    truncated = fx.REPLY_RAM_DUMP[:60] + fx.REPLY_RAM_DUMP[-1:]
    frame = protocol.parse_frame(truncated)
    assert frame.size == 92
    assert len(frame.payload) == 46
    assert not frame.size_ok
    assert not frame.well_formed


def test_ack_uses_its_own_confirmed_compact_shape():
    """Physical write ACKs are deliberately not parsed as memory reply frames."""
    assert len(protocol.ACK_FRAME) == 8
    with pytest.raises(ValueError, match="too short"):
        protocol.parse_frame(protocol.ACK_FRAME)


@pytest.mark.parametrize("value", [True, False, 1.0, "1"])
def test_slot_and_index_validators_refuse_non_integer_values(value):
    for validator in (
        protocol.check_preset_index,
        protocol.check_capture_index,
        protocol.check_slot_number,
    ):
        with pytest.raises(TypeError, match="integer"):
            validator(value)


def test_every_slot_addressing_builder_refuses_boolean_indexes():
    flash = protocol.WriteConsent(
        path_key="restore", confirmed_by_user=True, allow_flash=True
    )
    load = protocol.WriteConsent(path_key="load-preset", confirmed_by_user=True)
    amp = protocol.WriteConsent(
        path_key="save-amp", confirmed_by_user=True, allow_flash=True
    )
    cab = protocol.WriteConsent(
        path_key="save-cab", confirmed_by_user=True, allow_flash=True
    )
    builders = (
        lambda: protocol.cmd_read_flash_preset(True),
        lambda: protocol.cmd_write_flash_preset(
            True, bytes(protocol.PRESET_SIZE), consent=flash
        ),
        lambda: protocol.cmd_load_preset(True, consent=load),
        lambda: protocol.cmd_save_amp(
            True, bytes(protocol.AMP_RECORD_SIZE), consent=amp
        ),
        lambda: protocol.cmd_save_cab_header(
            True, bytes(protocol.CAB_HEADER_SIZE), consent=cab
        ),
    )

    for build in builders:
        with pytest.raises(TypeError, match="integer"):
            build()
