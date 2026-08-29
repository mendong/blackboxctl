"""Transport receive path, driven by synthetic MIDIPacketLists. GPL-3.0.

No hardware is involved: a MIDIPacketList is built in a ctypes buffer exactly as
CoreMIDI lays it out on arm64 and handed to BlackBox._on_packets. That exercises
the packet walk, the cross-callback stream reassembly, the real-time filter and
the SysEx extractor without opening a device.

Synthetic lists use the same ARM/Intel stride as :data:`MIDI_PACKET_ALIGN_4`,
so the walker is tested against this host's CoreMIDI layout.

This file covers receive mechanics only. The send path, completion wait, and
endpoint resolution have separate unit tests and were exercised on hardware;
see STATUS.md for the dated evidence boundary.
"""

from __future__ import annotations

import ctypes

import pytest
from fixtures import device_frames as fx

from blackboxctl import protocol

transport = pytest.importorskip("blackboxctl.transport")


def packet_list(*chunks: bytes) -> ctypes.Array:
    """Build a MIDIPacketList using this host's CoreMIDI packet stride.

    MIDIPacket is timeStamp(8) | length(UInt16) | data[length]. The next packet
    is 4-byte aligned on ARM and packed on Intel, matching MIDIPacketNext.
    """
    align4 = transport.MIDI_PACKET_ALIGN_4
    offset = 4
    for chunk in chunks:
        offset = transport._next_packet_offset(offset, len(chunk), align4=align4)
    buf = ctypes.create_string_buffer(offset + 16)
    ctypes.memmove(buf, len(chunks).to_bytes(4, "little"), 4)
    offset = 4
    for chunk in chunks:
        ctypes.memmove(ctypes.byref(buf, offset), bytes(8), 8)
        ctypes.memmove(
            ctypes.byref(buf, offset + 8), len(chunk).to_bytes(2, "little"), 2
        )
        ctypes.memmove(ctypes.byref(buf, offset + 10), chunk, len(chunk))
        offset = transport._next_packet_offset(offset, len(chunk), align4=align4)
    return buf


class Receiver(transport.BlackBox):
    """BlackBox with the CoreMIDI binding skipped - receive logic only."""

    def __init__(self):
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
    with_clock = whole[:170] + b"\xf8" + whole[170:]
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


def test_read_retries_after_only_an_unrelated_notification(monkeypatch):
    class Reader:
        def __init__(self):
            self.calls = 0

        def request(self, *_args, **_kwargs):
            self.calls += 1
            decoded = [fx.REPLY_PRESET_SYNC] if self.calls == 1 else [fx.REPLY_RAM_DUMP]
            return [], decoded

        def log(self, _message):
            return None

    reader = Reader()
    monkeypatch.setattr(transport.time, "sleep", lambda _seconds: None)

    frame = transport.BlackBox.read_memory(
        reader, protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE
    )

    assert reader.calls == 2
    assert frame.payload == protocol.parse_frame(fx.REPLY_RAM_DUMP).payload


def test_read_does_not_retry_a_malformed_matching_reply(monkeypatch):
    corrupted = bytearray(fx.REPLY_RAM_DUMP)
    corrupted[-1] ^= 1

    class Reader:
        calls = 0

        def request(self, *_args, **_kwargs):
            self.calls += 1
            return [], [bytes(corrupted)]

        def log(self, _message):
            return None

    reader = Reader()
    monkeypatch.setattr(transport.time, "sleep", lambda _seconds: None)

    with pytest.raises(transport.CorruptReply, match="malformed reply"):
        transport.BlackBox.read_memory(
            reader, protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE
        )
    assert reader.calls == 1


def test_midipacket_stride_matches_arm_and_intel_macros():
    assert transport._next_packet_offset(4, 3, align4=True) == 20
    assert transport._next_packet_offset(4, 3, align4=False) == 17
