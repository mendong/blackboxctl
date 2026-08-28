"""BlackBox.send's own gate, checked without opening a device. GPL-3.0."""

from __future__ import annotations

import pytest

from blackboxctl import protocol
from blackboxctl.protocol import UnsafePacket, WriteConsent
from fixtures import device_frames as fx

transport = pytest.importorskip("blackboxctl.transport")


class Gate(transport.BlackBox):
    """Only the authorisation half of BlackBox; no CoreMIDI binding."""

    def __init__(self):                             # noqa: D107
        pass


def test_send_no_longer_takes_a_bare_allow_write_bool():
    """One default-False kwarg used to be the only barrier to a flash write."""
    import inspect
    signature = inspect.signature(transport.BlackBox.send)
    assert "allow_write" not in signature.parameters
    assert signature.parameters["consent"].default is None


@pytest.mark.parametrize("name", sorted(fx.READ_COMMANDS))
def test_read_commands_pass_without_consent(name):
    Gate()._authorise_write  # attribute exists
    protocol.assert_read_only(fx.READ_COMMANDS[name])


def test_a_hand_built_flash_frame_is_refused_even_with_matching_consent():
    """The gate must hold for a frame nobody built with our builders."""
    raw = protocol.build_frame(protocol.MAGIC_WRITE, protocol.SPACE_PARAM,
                               40 * protocol.PRESET_SIZE,
                               protocol.PRESET_SIZE,
                               bytes(protocol.PRESET_SIZE))
    assert raw[3] == 0x64
    with pytest.raises(UnsafePacket, match="allow_flash"):
        Gate()._authorise_write(
            raw, WriteConsent(path_key="restore", confirmed_by_user=True,
                              accept_unverified=True))


def test_even_full_consent_is_refused_while_the_path_is_unconfirmed():
    raw = protocol.build_frame(protocol.MAGIC_WRITE, protocol.SPACE_PARAM,
                               40 * protocol.PRESET_SIZE,
                               protocol.PRESET_SIZE,
                               bytes(protocol.PRESET_SIZE))
    with pytest.raises(UnsafePacket, match="never been confirmed"):
        Gate()._authorise_write(
            raw, WriteConsent(path_key="restore", confirmed_by_user=True,
                              accept_unverified=True, allow_flash=True))


def test_a_ram_poke_is_refused_because_set_knob_is_unconfirmed():
    raw = protocol.build_frame(protocol.MAGIC_WRITE, protocol.SPACE_PARAM,
                               protocol.ADDR_LIVE_RAM + 0x20, 2,
                               (45).to_bytes(2, "little"))
    with pytest.raises(UnsafePacket, match="never been confirmed"):
        Gate()._authorise_write(
            raw, WriteConsent(path_key="set-knob", confirmed_by_user=True,
                              accept_unverified=True))


def test_unknown_magic_is_refused():
    with pytest.raises(UnsafePacket, match="unknown frame magic"):
        Gate()._authorise_write(bytes(20),
                                WriteConsent(path_key="commit",
                                             confirmed_by_user=True,
                                             accept_unverified=True))


def test_open_reports_a_missing_device_clearly_rather_than_crashing():
    """The pedal may be unplugged. That must be a readable error, not a stack."""
    try:
        device = transport.open_device()
    except transport.TransportUnavailable as exc:
        assert "BlackBox" in str(exc) or "CoreMIDI" in str(exc)
        return
    device.close()
