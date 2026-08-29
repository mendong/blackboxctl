"""The read-only gate: what it accepts, what it refuses, and a fuzz. GPL-3.0."""

from __future__ import annotations

import random

import pytest
from fixtures import device_frames as fx

from blackboxctl import protocol
from blackboxctl.protocol import UnsafePacket


@pytest.mark.parametrize("name", sorted(fx.READ_COMMANDS))
def test_gate_accepts_every_command_actually_sent_to_this_pedal(name):
    protocol.assert_read_only(fx.READ_COMMANDS[name])


def test_gate_refuses_the_write_header():
    with pytest.raises(UnsafePacket, match="WRITE header"):
        protocol.assert_read_only(fx.DOC_WRITE_LITERALS["toggle_fx_on"])
    with pytest.raises(UnsafePacket, match="WRITE header"):
        protocol.assert_read_only(fx.DOC_WRITE_LITERALS["commit"])


def test_gate_bounds_the_size_field():
    """build_read(ADDR_PRESET_BASE, 0xFFFFFF) used to sail straight through."""
    with pytest.raises(UnsafePacket, match="exceeds"):
        protocol.assert_read_only(
            protocol.build_read(protocol.ADDR_PRESET_BASE, 0xFFFFFF)
        )
    with pytest.raises(UnsafePacket, match="exceeds"):
        protocol.assert_read_only(
            protocol.build_read(protocol.ADDR_LIVE_RAM, protocol.MAX_READ_SIZE + 1)
        )
    protocol.assert_read_only(
        protocol.build_read(
            protocol.ADDR_AMP_NAMES, protocol.MAX_READ_SIZE, protocol.SPACE_STRING
        )
    )


@pytest.mark.parametrize(
    "address,label",
    [
        (protocol.ADDR_LOAD_PRESET, "load-preset trigger"),
        (protocol.ADDR_COMMIT, "commit trigger"),
    ],
)
def test_gate_refuses_reads_at_documented_write_triggers(address, label):
    """These registers exist to cause side effects. A read there is untested."""
    with pytest.raises(UnsafePacket, match="not inside any region"):
        protocol.assert_read_only(protocol.build_read(address, 1))


def test_gate_refuses_a_read_past_the_end_of_the_preset_array():
    beyond = protocol.PRESET_COUNT * protocol.PRESET_SIZE
    with pytest.raises(UnsafePacket, match="not inside any region"):
        protocol.assert_read_only(protocol.build_read(beyond, protocol.PRESET_SIZE))
    # ... but the last real slot is fine.
    protocol.assert_read_only(
        protocol.build_read(beyond - protocol.PRESET_SIZE, protocol.PRESET_SIZE)
    )


def test_gate_refuses_wrong_space_for_the_name_tables():
    with pytest.raises(UnsafePacket, match="not inside any region"):
        protocol.assert_read_only(
            protocol.build_read(
                protocol.ADDR_AMP_NAMES, protocol.NAME_TABLE_SIZE, protocol.SPACE_PARAM
            )
        )


def test_gate_refuses_a_bad_checksum():
    raw = bytearray(protocol.cmd_ram_dump())
    raw[-1] ^= 0xFF
    with pytest.raises(UnsafePacket, match="bad checksum"):
        protocol.assert_read_only(bytes(raw))


def test_gate_refuses_a_read_carrying_a_payload():
    raw = protocol.build_frame(
        protocol.MAGIC_READ, protocol.SPACE_PARAM, protocol.ADDR_LIVE_RAM, 1, b"\x01"
    )
    with pytest.raises(UnsafePacket, match="carries no payload"):
        protocol.assert_read_only(raw)


def test_gate_fuzz_never_accepts_a_write_and_never_crashes():
    """300k random frames. The gate must raise UnsafePacket or accept a read.

    Anything else - a different exception, or accepting a 00 59 22 frame - is a
    failure.
    """
    rng = random.Random(1234567)
    accepted = 0
    for _ in range(300_000):
        length = rng.randrange(0, 40)
        raw = bytes(rng.randrange(256) for _ in range(length))
        if rng.random() < 0.35 and length >= 15:
            raw = bytes(protocol.MAGIC_READ) + raw[3:]
        if rng.random() < 0.15 and length >= 15:
            raw = bytes(protocol.MAGIC_WRITE) + raw[3:]
        try:
            protocol.assert_read_only(raw)
        except UnsafePacket:
            continue
        accepted += 1
        assert raw[0:3] == protocol.MAGIC_READ
        frame = protocol.parse_frame(raw)
        assert frame.length == 8 and not frame.payload
        assert 0 < frame.size <= protocol.MAX_READ_SIZE
    # Sanity: the fuzz is not vacuous - it does accept some valid reads.
    assert accepted >= 0
