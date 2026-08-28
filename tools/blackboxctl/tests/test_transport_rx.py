"""Transport receive path, driven by synthetic MIDIPacketLists. GPL-3.0.

No hardware is involved: a MIDIPacketList is built in a ctypes buffer exactly as
CoreMIDI lays it out on arm64 and handed to BlackBox._on_packets. That exercises
the packet walk, the cross-callback stream reassembly, the real-time filter and
the SysEx extractor without opening a device.

The send path, MIDISendSysex completion wait and endpoint resolution are NOT
covered here and remain unverified on hardware; see STATUS.md.
"""

from __future__ import annotations

import ctypes

import pytest

from blackboxctl import protocol
from fixtures import device_frames as fx

transport = pytest.importorskip("blackboxctl.transport")


def packet_list(*chunks: bytes) -> ctypes.Array:
    """Build a MIDIPacketList: UInt32 numPackets, then packed MIDIPackets.

    MIDIPacket is timeStamp(8) | length(UInt16) | data[length], and the next
    packet starts at (&data[length] + 3) & ~3 on arm64.
    """
    size = 4 + sum(((10 + len(c) + 3) & ~3) for c in chunks) + 16
    buf = ctypes.create_string_buffer(size)
    ctypes.memmove(buf, len(chunks).to_bytes(4, "little"), 4)
    offset = 4
    for chunk in chunks:
        ctypes.memmove(ctypes.byref(buf, offset), bytes(8), 8)
        ctypes.memmove(ctypes.byref(buf, offset + 8),
                       len(chunk).to_bytes(2, "little"), 2)
        ctypes.memmove(ctypes.byref(buf, offset + 10), chunk, len(chunk))
        offset = (offset + 10 + len(chunk) + 3) & ~3
    return buf


class Receiver(transport.BlackBox):
    """BlackBox with the CoreMIDI binding skipped - receive logic only."""

    def __init__(self):                             # noqa: D107
        self._log_sink = None
        self.log_lines = []
        import threading
        self._lock = threading.Lock()
        self._stream = bytearray()
        self._sysex = []
        self._decoded = []

    def feed(self, *chunks: bytes) -> None:
        # The buffer must outlive the call: ctypes.addressof() on a temporary
        # hands _on_packets a pointer into freed memory and segfaults.
        buf = packet_list(*chunks)
        self._on_packets(ctypes.addressof(buf), 0, 0)
        del buf


def test_one_sysex_split_across_packets_in_one_callback():
    rx = Receiver()
    whole = fx.RX_SYSEX_CAB_NAMES
    rx.feed(whole[:200], whole[200:])
    sysex, decoded = rx.received()
    assert len(sysex) == 1 and sysex[0] == whole
    assert decoded[0] == fx.REPLY_CAB_NAMES


def test_one_sysex_split_across_two_callbacks():
    rx = Receiver()
    whole = fx.RX_SYSEX_CAB_NAMES
    rx.feed(whole[:137])
    assert rx.received()[0] == []
    rx.feed(whole[137:])
    assert rx.received()[1][0] == fx.REPLY_CAB_NAMES


def test_two_sysex_in_one_packet():
    rx = Receiver()
    both = fx.TX_SYSEX["ram_dump"] + fx.RX_SYSEX_CAB_NAMES
    rx.feed(both)
    sysex, decoded = rx.received()
    assert len(sysex) == 2
    assert decoded[1] == fx.REPLY_CAB_NAMES


def test_realtime_bytes_inside_a_sysex_are_filtered_out():
    """MIDI permits F8..FE inside a SysEx; one used to corrupt the whole decode.

    HYPOTHESIS-level hardening: this pedal has never been observed to send one.
    Before the fix an injected F8 produced a 341-byte message decoding to 296
    bytes that did not equal the original, with no error raised.
    """
    rx = Receiver()
    whole = fx.RX_SYSEX_CAB_NAMES
    with_clock = whole[:170] + b"\xF8" + whole[170:]
    rx.feed(with_clock)
    sysex, decoded = rx.received()
    assert len(sysex) == 1
    assert len(sysex[0]) == 341
    assert decoded[0] == fx.REPLY_CAB_NAMES, "the F8 must not reach the decoder"


@pytest.mark.parametrize("intruder", [0xF9, 0xFA, 0xFE])
def test_all_realtime_bytes_are_filtered(intruder):
    rx = Receiver()
    whole = fx.RX_SYSEX_CAB_NAMES
    rx.feed(whole[:20] + bytes((intruder,)) + whole[20:])
    assert rx.received()[1][0] == fx.REPLY_CAB_NAMES


def test_a_status_byte_inside_a_sysex_is_dropped_not_decoded_to_garbage():
    rx = Receiver()
    whole = fx.RX_SYSEX_CAB_NAMES
    rx.feed(whole[:20] + b"\x90" + whole[20:])
    sysex, decoded = rx.received()
    assert sysex == [] and decoded == []
    assert any("status byte inside SysEx" in line for line in rx.log_lines)


def test_leading_garbage_before_f0_is_discarded():
    rx = Receiver()
    rx.feed(b"\x00\x01\x02" + fx.RX_SYSEX_CAB_NAMES)
    assert rx.received()[1][0] == fx.REPLY_CAB_NAMES


def test_reset_rx_clears_everything():
    rx = Receiver()
    rx.feed(fx.RX_SYSEX_CAB_NAMES)
    rx.reset_rx()
    assert rx.received() == ([], [])


def test_matches_routes_replies_by_address_not_arrival_order():
    """The device emits unsolicited 0x20000000 frames between request and reply."""
    assert transport._matches(fx.REPLY_RAM_DUMP, protocol.ADDR_LIVE_RAM)
    assert not transport._matches(fx.REPLY_PRESET_SYNC, protocol.ADDR_LIVE_RAM)
    assert transport._matches(fx.REPLY_PRESET_SYNC, protocol.ADDR_CURRENT_PRESET)
    assert transport._matches(fx.REPLY_FLASH_40, 40 * protocol.PRESET_SIZE)
