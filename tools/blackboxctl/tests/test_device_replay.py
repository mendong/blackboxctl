"""Drive the device CLI commands against the RECORDED device replies. GPL-3.0.

This is not a hardware test and does not pretend to be. It replaces only the
CoreMIDI I/O with a replay of the exact SysEx messages the pedal sent on
2026-08-28, and then runs the real request/reassembly/parse/decode/render path
on top. That covers everything in transport.py except the actual send and the
MIDIReadProc callback registration.

What it does NOT cover, and what STATUS.md records as still unverified:
MIDISendSysex, its completion wait, MIDIInputPortCreate/MIDIPortConnectSource,
and endpoint resolution against a live device.
"""

from __future__ import annotations

import pytest

from blackboxctl import cli, protocol
from fixtures import device_frames as fx

transport = pytest.importorskip("blackboxctl.transport")


class ReplayDevice(transport.BlackBox):
    """A BlackBox whose wire is the recorded log instead of CoreMIDI."""

    #: address -> the reply frame the real pedal returned for it
    REPLIES = {
        protocol.ADDR_LIVE_RAM: fx.REPLY_RAM_DUMP,
        protocol.ADDR_CURRENT_PRESET: fx.REPLY_PRESET_SYNC,
        protocol.ADDR_AMP_NAMES: fx.REPLY_AMP_NAMES,
        protocol.ADDR_CAB_NAMES: fx.REPLY_CAB_NAMES,
        0: fx.REPLY_FLASH_00,
        2 * protocol.PRESET_SIZE: fx.REPLY_FLASH_02,
        40 * protocol.PRESET_SIZE: fx.REPLY_FLASH_40,
    }

    def __init__(self):                             # noqa: D107
        import threading
        self._log_sink = None
        self.log_lines = []
        self._lock = threading.Lock()
        self._stream = bytearray()
        self._sysex = []
        self._decoded = []
        self.sent: list[bytes] = []

    def open(self):
        return self

    def close(self):
        pass

    def send(self, raw, label="", consent=None):
        # The real gate, unmodified. A write here would raise.
        assert consent is None, "the replay device must never be asked to write"
        protocol.assert_read_only(raw)
        self.sent.append(raw)
        address = int.from_bytes(raw[7:11], "little")
        reply = self.REPLIES[address]
        with self._lock:
            # The device also emits unsolicited preset-sync frames; include one
            # so the address-matching demultiplexer is genuinely exercised.
            self._stream.extend(protocol.sysex_wrap(fx.REPLY_PRESET_SYNC))
            self._stream.extend(protocol.sysex_wrap(reply))
            self._extract_sysex_locked()
        return b""


@pytest.fixture
def replay(monkeypatch):
    device = ReplayDevice()
    monkeypatch.setattr(transport, "open_device", lambda *a, **k: device)
    return device


def test_read_memory_returns_the_recorded_ram_dump(replay):
    frame = replay.read_memory(protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE,
                               timeout=1.0)
    assert frame.raw == fx.REPLY_RAM_DUMP
    assert frame.well_formed
    assert replay.sent == [fx.READ_COMMANDS["ram_dump"]]


def test_read_memory_demultiplexes_past_an_unsolicited_frame(replay):
    """An unrequested 0x20000000 frame arrives first; it must not be returned."""
    frame = replay.read_memory(40 * protocol.PRESET_SIZE, protocol.PRESET_SIZE,
                               timeout=1.0)
    assert frame.address == 40 * protocol.PRESET_SIZE
    assert frame.raw == fx.REPLY_FLASH_40
    assert len(replay.received()[1]) >= 2


def test_read_memory_raises_on_a_corrupt_reply(replay, monkeypatch):
    """A truncated reply used to be handed to the caller as if it were data."""
    broken = dict(ReplayDevice.REPLIES)
    broken[protocol.ADDR_LIVE_RAM] = fx.REPLY_RAM_DUMP[:60] + fx.REPLY_RAM_DUMP[-1:]
    monkeypatch.setattr(replay, "REPLIES", broken)
    with pytest.raises(transport.CorruptReply, match="size field"):
        replay.read_memory(protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE,
                           timeout=1.0)


def run_cli(*args) -> tuple[int, dict]:
    import io
    import json
    import contextlib
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = cli.main(["--json", *args])
    return code, json.loads(buffer.getvalue())


def test_cli_device_names_renders_the_forty_recorded_names(replay):
    code, doc = run_cli("device", "names")
    assert code == cli.EXIT_OK
    assert doc["amp_names"] == fx.AMP_NAMES
    assert doc["cab_names"] == fx.CAB_NAMES


def test_cli_device_sync_reports_p03(replay):
    code, doc = run_cli("device", "sync")
    assert code == cli.EXIT_OK
    assert doc["active_index0"] == 2
    assert doc["active_label"] == "P03"


def test_cli_device_dump_decodes_the_live_preset_with_knobs(replay):
    code, doc = run_cli("device", "dump")
    assert code == cli.EXIT_OK
    blocks = {b["key"]: b for b in doc["preset"]["blocks"]}
    assert blocks["amp"]["model_name"] == "3JC120_CL"
    assert blocks["cab"]["model_name"] == "5HIFI_OK"
    assert [(k["name"], k["value"]) for k in blocks["amp"]["knobs"]] \
        == fx.EXPECTED_RAM["amp_knobs"]
    assert [(k["name"], k["value"]) for k in blocks["cab"]["knobs"]] \
        == fx.EXPECTED_RAM["cab_knobs"]


def test_cli_device_preset_41_matches_the_gui_values(replay):
    """The seven P41 values known independently from the M-EFCS GUI."""
    code, doc = run_cli("device", "preset", "41")
    assert code == cli.EXIT_OK
    preset = doc["preset"]
    blocks = {b["key"]: b for b in preset["blocks"]}
    assert preset["volume"] == 85
    assert blocks["amp"]["model_name"] == "1J900_CL"
    assert blocks["cab"]["model_name"] == "7VOX_AC30"
    assert blocks["dly"]["enabled"] is False
    knobs = {b["key"]: {k["name"]: k["value"] for k in b["knobs"]}
             for b in preset["blocks"]}
    assert knobs["amp"]["Gain"] == 45
    assert knobs["mod"]["Mix"] == 12
    assert knobs["rev"]["Mix"] == 12


def test_the_replay_only_ever_saw_read_commands(replay):
    run_cli("device", "dump")
    for raw in replay.sent:
        assert raw[0:3] == protocol.MAGIC_READ
        protocol.assert_read_only(raw)
