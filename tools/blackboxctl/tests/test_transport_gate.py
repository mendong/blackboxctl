"""BlackBox.send's own gate, checked without opening a device. GPL-3.0."""

from __future__ import annotations

import pytest
from fixtures import device_frames as fx

from blackboxctl import protocol
from blackboxctl.protocol import UnsafePacket, WriteConsent

transport = pytest.importorskip("blackboxctl.transport")


class Gate(transport.BlackBox):
    """Only the authorisation half of BlackBox; no CoreMIDI binding."""

    def __init__(self):
        pass


def test_send_no_longer_takes_a_bare_allow_write_bool():
    """One default-False kwarg used to be the only barrier to a flash write."""
    import inspect

    signature = inspect.signature(transport.BlackBox.send)
    assert "allow_write" not in signature.parameters
    assert signature.parameters["consent"].default is None


def test_send_timeout_blocks_every_later_frame(monkeypatch):
    from types import SimpleNamespace

    class NeverCompletes:
        calls = 0

        def MIDISendSysex(self, _request):
            self.calls += 1
            return 0

    midi = NeverCompletes()
    device = Gate()
    device.destination = transport.Endpoint(0, 7, "USB", None, "Jieli Technology")
    device._fw = SimpleNamespace(midi=midi)
    device._keepalive = []
    device._send_blocked = False
    device.log = lambda _message: None
    moments = iter((0.0, 3.0))
    monkeypatch.setattr(transport.time, "monotonic", lambda: next(moments))

    with pytest.raises(transport.SendInFlight, match="device state is uncertain"):
        device.send(fx.READ_COMMANDS["ram_dump"])
    assert device._send_blocked
    assert midi.calls == 1

    with pytest.raises(transport.SendInFlight, match="previous CoreMIDI SysEx"):
        device.send(fx.READ_COMMANDS["ram_dump"])
    assert midi.calls == 1, "a recovery/read frame must not race the pending SysEx"


@pytest.mark.parametrize("name", sorted(fx.READ_COMMANDS))
def test_read_commands_pass_without_consent(name):
    assert callable(Gate()._authorise_write)
    protocol.assert_read_only(fx.READ_COMMANDS[name])


def test_a_hand_built_flash_frame_is_refused_even_with_matching_consent():
    """The gate must hold for a frame nobody built with our builders."""
    raw = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_PARAM,
        40 * protocol.PRESET_SIZE,
        protocol.PRESET_SIZE,
        bytes(protocol.PRESET_SIZE),
    )
    assert raw[3] == 0x64
    with pytest.raises(UnsafePacket, match="allow_flash"):
        Gate()._authorise_write(
            raw,
            WriteConsent(
                path_key="restore", confirmed_by_user=True, accept_unverified=True
            ),
        )


def test_unconfirmed_commit_path_is_still_refused():
    raw = protocol.build_frame(
        protocol.MAGIC_WRITE, protocol.SPACE_PARAM, protocol.ADDR_COMMIT, 0
    )
    with pytest.raises(UnsafePacket, match="never been confirmed"):
        Gate()._authorise_write(
            raw,
            WriteConsent(
                path_key="commit", confirmed_by_user=True, accept_unverified=True
            ),
        )


def test_confirmed_flash_write_with_full_consent_is_allowed():
    raw = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_PARAM,
        40 * protocol.PRESET_SIZE,
        protocol.PRESET_SIZE,
        bytes(protocol.PRESET_SIZE),
    )
    Gate()._authorise_write(
        raw, WriteConsent(path_key="restore", confirmed_by_user=True, allow_flash=True)
    )


def test_confirmed_live_ram_knob_write_is_allowed():
    raw = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_PARAM,
        protocol.ADDR_LIVE_RAM + 0x20,
        2,
        (45).to_bytes(2, "little"),
    )
    Gate()._authorise_write(
        raw, WriteConsent(path_key="set-knob", confirmed_by_user=True)
    )


def test_consent_cannot_authorise_an_unrelated_hand_built_write():
    raw = protocol.build_frame(
        protocol.MAGIC_WRITE, protocol.SPACE_STRING, 0xDEADBEEF, 3, b"BAD"
    )
    with pytest.raises(UnsafePacket, match="does not match write path"):
        Gate()._authorise_write(
            raw, WriteConsent(path_key="set-knob", confirmed_by_user=True)
        )


def test_write_path_checks_the_final_checksum_and_size():
    raw = bytearray(
        protocol.cmd_write_u16(
            0x20, 45, consent=WriteConsent(path_key="set-knob", confirmed_by_user=True)
        )
    )
    raw[-1] ^= 1
    with pytest.raises(UnsafePacket, match="malformed write frame"):
        Gate()._authorise_write(
            bytes(raw), WriteConsent(path_key="set-knob", confirmed_by_user=True)
        )


@pytest.mark.parametrize(
    "path_key,frames",
    [
        (
            "stage-cab",
            protocol.cmd_stage_cab(
                bytes(protocol.CAB_RECORD_SIZE),
                consent=WriteConsent(path_key="stage-cab", confirmed_by_user=True),
            ),
        ),
        (
            "save-cab",
            protocol.cmd_save_cab_header(
                19,
                bytes(protocol.CAB_HEADER_SIZE),
                consent=WriteConsent(
                    path_key="save-cab", confirmed_by_user=True, allow_flash=True
                ),
            ),
        ),
        (
            "stage-amp",
            protocol.cmd_stage_amp(
                bytes(protocol.AMP_RECORD_SIZE),
                consent=WriteConsent(path_key="stage-amp", confirmed_by_user=True),
            ),
        ),
        (
            "save-amp",
            protocol.cmd_save_amp(
                19,
                bytes(protocol.AMP_RECORD_SIZE),
                consent=WriteConsent(
                    path_key="save-amp", confirmed_by_user=True, allow_flash=True
                ),
            ),
        ),
    ],
)
def test_library_frames_match_only_their_declared_path(path_key, frames):
    consent = WriteConsent(
        path_key=path_key,
        confirmed_by_user=True,
        allow_flash=protocol.WRITE_PATHS[path_key].touches_flash,
    )
    for raw in frames:
        Gate()._authorise_write(raw, consent)


def test_unknown_magic_is_refused():
    with pytest.raises(UnsafePacket, match="unknown frame magic"):
        Gate()._authorise_write(
            bytes(20),
            WriteConsent(
                path_key="commit", confirmed_by_user=True, accept_unverified=True
            ),
        )


def test_amp_and_cab_commit_addresses_count_as_permanent_storage():
    device = Gate()
    amp = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_STRING,
        protocol.ADDR_AMP_COMMIT_BASE + 19,
        1,
        b"\x00",
    )
    cab = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_STRING,
        protocol.ADDR_CAB_COMMIT_BASE + 19,
        1,
        b"\x00",
    )
    header = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_STRING,
        0,
        protocol.CAB_HEADER_SIZE,
        bytes(protocol.CAB_HEADER_SIZE),
    )
    knob = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_PARAM,
        protocol.ADDR_LIVE_RAM + 0x20,
        2,
        (45).to_bytes(2, "little"),
    )
    assert device._writes_permanent_storage(amp, protocol.parse_frame(amp))
    assert device._writes_permanent_storage(cab, protocol.parse_frame(cab))
    assert not device._writes_permanent_storage(header, protocol.parse_frame(header))
    assert not device._writes_permanent_storage(knob, protocol.parse_frame(knob))


def test_amp_commit_without_allow_flash_is_refused():
    raw = protocol.build_frame(
        protocol.MAGIC_WRITE,
        protocol.SPACE_STRING,
        protocol.ADDR_AMP_COMMIT_BASE,
        1,
        b"\x00",
    )
    with pytest.raises(UnsafePacket, match="allow_flash"):
        Gate()._authorise_write(
            raw, WriteConsent(path_key="save-amp", confirmed_by_user=True)
        )


def test_open_reports_a_missing_device_clearly_rather_than_crashing():
    """The pedal may be unplugged. That must be a readable error, not a stack."""
    try:
        device = transport.open_device()
    except transport.TransportUnavailable as exc:
        assert "BlackBox" in str(exc) or "CoreMIDI" in str(exc)
        return
    device.close()
