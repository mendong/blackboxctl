"""No write frame can reach the wire. GPL-3.0.

This is the file that must never be deleted. It asserts the whole point of the
safety model: that nothing reachable without an explicit, correctly-scoped
WriteConsent can emit magic 00 59 22, and that even WITH consent the transport
refuses every currently-unverified write path.
"""

from __future__ import annotations

import inspect

import pytest

from blackboxctl import cli, protocol
from blackboxctl.protocol import UnsafePacket, WriteConsent


WRITE_BUILDERS = {
    "cmd_load_preset": (protocol.cmd_load_preset, (0,), "load-preset"),
    "cmd_write_byte": (protocol.cmd_write_byte, (0x08, 1), "set-toggle"),
    "cmd_write_u16": (protocol.cmd_write_u16, (0x20, 45), "set-knob"),
    "cmd_write_routing": (protocol.cmd_write_routing, ([0, 1, 2, 3, 4, 5],),
                          "set-routing"),
    "cmd_commit": (protocol.cmd_commit, (), "commit"),
    "cmd_write_flash_preset": (protocol.cmd_write_flash_preset,
                               (40, bytes(protocol.PRESET_SIZE)), "restore"),
}


@pytest.mark.parametrize("name", sorted(WRITE_BUILDERS))
def test_every_write_builder_requires_consent(name):
    builder, args, _key = WRITE_BUILDERS[name]
    with pytest.raises(TypeError):
        builder(*args)


@pytest.mark.parametrize("name", sorted(WRITE_BUILDERS))
def test_default_consent_is_refused(name):
    builder, args, key = WRITE_BUILDERS[name]
    with pytest.raises(UnsafePacket, match="confirmed_by_user"):
        builder(*args, consent=WriteConsent(path_key=key))


@pytest.mark.parametrize("name", sorted(WRITE_BUILDERS))
def test_consent_for_a_different_path_is_refused(name):
    builder, args, key = WRITE_BUILDERS[name]
    wrong = "commit" if key != "commit" else "set-knob"
    with pytest.raises(UnsafePacket):
        builder(*args, consent=WriteConsent(path_key=wrong,
                                            confirmed_by_user=True,
                                            accept_unverified=True,
                                            allow_flash=True))


@pytest.mark.parametrize("name", sorted(WRITE_BUILDERS))
def test_unverified_paths_need_accept_unverified(name):
    builder, args, key = WRITE_BUILDERS[name]
    assert not protocol.WRITE_PATHS[key].hardware_confirmed
    with pytest.raises(UnsafePacket, match="NOT confirmed"):
        builder(*args, consent=WriteConsent(path_key=key,
                                            confirmed_by_user=True))


def test_flash_write_needs_allow_flash_on_top_of_everything_else():
    with pytest.raises(UnsafePacket, match="allow_flash"):
        protocol.cmd_write_flash_preset(
            40, bytes(protocol.PRESET_SIZE),
            consent=WriteConsent(path_key="restore", confirmed_by_user=True,
                                 accept_unverified=True))


def test_the_flash_frame_is_what_the_brief_says_must_never_be_sent():
    """With every gate cleared, the builder emits 00 59 22 with byte[3]==0x64."""
    raw = protocol.cmd_write_flash_preset(
        40, bytes(protocol.PRESET_SIZE),
        consent=WriteConsent(path_key="restore", confirmed_by_user=True,
                             accept_unverified=True, allow_flash=True))
    assert raw[0:3] == protocol.MAGIC_WRITE
    assert raw[3] == 0x64
    # ... and the read gate still refuses it, unconditionally.
    with pytest.raises(UnsafePacket, match="WRITE header"):
        protocol.assert_read_only(raw)


def test_no_write_path_is_hardware_confirmed():
    enabled = [k for k, p in protocol.WRITE_PATHS.items() if p.hardware_confirmed]
    assert enabled == [], (
        f"{enabled} claims hardware confirmation. No write has ever been "
        f"transmitted to this pedal; see STATUS.md before flipping this.")


def test_no_cli_command_mentions_a_write_builder():
    """A CLI subcommand must not be able to reach a write builder at all."""
    source = inspect.getsource(cli)
    for name in WRITE_BUILDERS:
        assert name not in source, (
            f"cli.py references {name}; the CLI must have no write surface")
    assert "WriteConsent" not in source
    assert "allow_flash" not in source
