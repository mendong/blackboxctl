"""Base-128 codec and checksum regressions against real device bytes.

GPL-3.0. See ../LICENSE and ../NOTICE.
"""

from __future__ import annotations

import random

import pytest

from blackboxctl import protocol
from fixtures import device_frames as fx


def test_roundtrip_fuzz():
    rng = random.Random(20260828)
    for length in range(1, 300):
        blob = bytes(rng.randrange(256) for _ in range(length))
        assert protocol.base128_decode(
            protocol.base128_encode(blob))[:length] == blob


def test_logged_340_byte_sysex_decodes_to_the_logged_295_byte_frame():
    """The regression fixture the upstream doc's worked example cannot be."""
    decoded = protocol.sysex_unwrap(fx.RX_SYSEX_CAB_NAMES)
    assert decoded == fx.REPLY_CAB_NAMES
    assert len(fx.RX_SYSEX_CAB_NAMES) == 340
    assert len(decoded) == 295


@pytest.mark.parametrize("name", sorted(fx.READ_COMMANDS))
def test_outbound_sysex_matches_the_wire(name):
    assert protocol.sysex_wrap(fx.READ_COMMANDS[name]) == fx.TX_SYSEX[name]


def test_documented_worked_example_is_internally_inconsistent():
    """Lock in the DOC defect so nobody "fixes" the codec to match it.

    The doc prints a raw packet beside an encoded packet that is not its
    encoding. The encoded one decodes to a different, checksum-valid frame and
    re-encodes bit-exactly - so the codec is right and the doc pair is wrong.
    """
    doc_raw = fx.h("00 59 22 09 00 00 04 08 00 00 10 01 00 00 01 E1")
    doc_encoded = fx.h("00 32 09 49 00 00 40 02 09 00 00 00 18 00 00 00 01 5E 01")

    assert protocol.base128_encode(doc_raw) != doc_encoded

    other = protocol.base128_decode(doc_encoded)
    assert other == fx.h("00 59 22 09 00 00 05 09 00 00 80 01 00 00 01 6F")
    assert protocol.checksum_tx(other) == other[-1] == 0x6F
    assert protocol.base128_encode(other) == doc_encoded

    # And the checksum formula does reproduce the doc's own 0xE1.
    assert protocol.checksum_tx(doc_raw) == 0xE1


@pytest.mark.parametrize("name", sorted(fx.UNIQUE_REPLIES))
def test_checksum_rx_validates_every_real_reply(name):
    frame = fx.UNIQUE_REPLIES[name]
    assert protocol.checksum_rx(frame) == frame[-1]


@pytest.mark.parametrize("name", sorted(fx.UNIQUE_REPLIES))
def test_checksum_tx_fails_on_exactly_the_two_name_blocks(name):
    """The empirical claim, stated so it stays reproducible.

    Offset 5 validates 7/7 unique replies; offset 4 validates 5/7, failing on
    the two 295-byte name blocks, which are the only replies with byte[4] != 0.
    """
    frame = fx.UNIQUE_REPLIES[name]
    agrees = protocol.checksum_tx(frame) == frame[-1]
    if name in fx.BYTE4_NONZERO:
        assert frame[4] == 0x01
        assert not agrees
    else:
        assert frame[4] == 0x00
        assert agrees


def test_offset_counts_are_seven_of_seven_and_five_of_seven():
    ok5 = sum(1 for f in fx.UNIQUE_REPLIES.values()
              if protocol.checksum_rx(f) == f[-1])
    ok4 = sum(1 for f in fx.UNIQUE_REPLIES.values()
              if protocol.checksum_tx(f) == f[-1])
    assert (ok5, ok4, len(fx.UNIQUE_REPLIES)) == (7, 5, 7)
