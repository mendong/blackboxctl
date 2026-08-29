"""Every write requires explicit, correctly scoped consent. GPL-3.0.

This is the file that must never be deleted. It asserts the whole point of the
safety model: nothing reachable without an explicit, correctly-scoped
WriteConsent can emit magic 00 59 22. Flash additionally needs allow_flash.
"""

from __future__ import annotations

import pytest

from blackboxctl import cli, protocol
from blackboxctl.protocol import UnsafePacket, WriteConsent

WRITE_BUILDERS = {
    "cmd_load_preset": (protocol.cmd_load_preset, (0,), "load-preset"),
    "cmd_write_byte": (protocol.cmd_write_byte, (0x08, 1), "set-toggle"),
    "cmd_write_byte_model": (protocol.cmd_write_byte, (0x10, 1), "set-model"),
    "cmd_write_u16": (protocol.cmd_write_u16, (0x20, 45), "set-knob"),
    "cmd_write_routing": (
        protocol.cmd_write_routing,
        ([0, 1, 2, 3, 4, 5],),
        "set-routing",
    ),
    "cmd_commit": (protocol.cmd_commit, (), "commit"),
    "cmd_write_flash_preset": (
        protocol.cmd_write_flash_preset,
        (40, bytes(protocol.PRESET_SIZE)),
        "restore",
    ),
    "cmd_stage_cab": (
        protocol.cmd_stage_cab,
        (bytes(protocol.CAB_RECORD_SIZE),),
        "stage-cab",
    ),
    "cmd_save_cab_header": (
        protocol.cmd_save_cab_header,
        (0, bytes(protocol.CAB_HEADER_SIZE)),
        "save-cab",
    ),
    "cmd_stage_amp": (
        protocol.cmd_stage_amp,
        (bytes(protocol.AMP_RECORD_SIZE),),
        "stage-amp",
    ),
    "cmd_save_amp": (
        protocol.cmd_save_amp,
        (0, bytes(protocol.AMP_RECORD_SIZE)),
        "save-amp",
    ),
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
        builder(
            *args,
            consent=WriteConsent(
                path_key=wrong,
                confirmed_by_user=True,
                accept_unverified=True,
                allow_flash=True,
            ),
        )


@pytest.mark.parametrize(
    "name",
    [
        name
        for name, (_builder, _args, key) in sorted(WRITE_BUILDERS.items())
        if not protocol.WRITE_PATHS[key].hardware_confirmed
    ],
)
def test_unverified_paths_need_accept_unverified(name):
    builder, args, key = WRITE_BUILDERS[name]
    with pytest.raises(UnsafePacket, match="NOT confirmed"):
        builder(*args, consent=WriteConsent(path_key=key, confirmed_by_user=True))


@pytest.mark.parametrize(
    "name",
    [
        name
        for name, (_builder, _args, key) in sorted(WRITE_BUILDERS.items())
        if protocol.WRITE_PATHS[key].touches_flash
    ],
)
def test_flash_write_needs_allow_flash_on_top_of_everything_else(name):
    builder, args, key = WRITE_BUILDERS[name]
    with pytest.raises(UnsafePacket, match="allow_flash"):
        builder(
            *args,
            consent=WriteConsent(
                path_key=key, confirmed_by_user=True, accept_unverified=True
            ),
        )


@pytest.mark.parametrize("truthy_non_bool", [1, "yes", [True]])
def test_truthy_non_boolean_confirmation_is_refused(truthy_non_bool):
    with pytest.raises(UnsafePacket, match="confirmed_by_user"):
        protocol.cmd_write_u16(
            0x20,
            45,
            consent=WriteConsent(
                path_key="set-knob", confirmed_by_user=truthy_non_bool
            ),
        )


@pytest.mark.parametrize("truthy_non_bool", [1, "yes", [True]])
def test_truthy_non_boolean_unverified_acceptance_is_refused(truthy_non_bool):
    with pytest.raises(UnsafePacket, match="NOT confirmed"):
        protocol.cmd_commit(
            consent=WriteConsent(
                path_key="commit",
                confirmed_by_user=True,
                accept_unverified=truthy_non_bool,
            )
        )


@pytest.mark.parametrize("truthy_non_bool", [1, "yes", [True]])
def test_truthy_non_boolean_flash_consent_is_refused(truthy_non_bool):
    with pytest.raises(UnsafePacket, match="allow_flash"):
        protocol.cmd_write_flash_preset(
            40,
            bytes(protocol.PRESET_SIZE),
            consent=WriteConsent(
                path_key="restore",
                confirmed_by_user=True,
                allow_flash=truthy_non_bool,
            ),
        )


def test_the_flash_frame_is_what_the_brief_says_must_never_be_sent():
    """With every gate cleared, the builder emits 00 59 22 with byte[3]==0x64."""
    raw = protocol.cmd_write_flash_preset(
        40,
        bytes(protocol.PRESET_SIZE),
        consent=WriteConsent(
            path_key="restore",
            confirmed_by_user=True,
            accept_unverified=True,
            allow_flash=True,
        ),
    )
    assert raw[0:3] == protocol.MAGIC_WRITE
    assert raw[3] == 0x64
    # ... and the read gate still refuses it, unconditionally.
    with pytest.raises(UnsafePacket, match="WRITE header"):
        protocol.assert_read_only(raw)


def test_only_physically_exercised_write_paths_are_confirmed():
    enabled = [k for k, p in protocol.WRITE_PATHS.items() if p.hardware_confirmed]
    assert enabled == [
        "load-preset",
        "set-knob",
        "set-toggle",
        "set-model",
        "set-routing",
        "restore",
        "stage-cab",
        "save-cab",
        "stage-amp",
        "save-amp",
    ]
    assert not protocol.WRITE_PATHS["commit"].hardware_confirmed


def test_cli_mutations_are_dry_run_without_yes():
    parser = cli.build_parser()
    for argv in (
        ["device", "load", "80"],
        ["device", "audition", "preset.bin"],
        ["device", "save", "80", "preset.bin"],
        ["device", "cab", "audition", "cab.wav"],
        ["device", "cab", "save", "1", "cab.wav", "--name", "CAB"],
        ["device", "amp", "audition", "amp.am2"],
        ["device", "amp", "save", "1", "amp.am2", "--name", "AMP"],
        ["device", "library-apply", "library.json"],
        ["device", "probe-amp-gain"],
        ["device", "probe-live"],
        ["device", "probe-flash"],
    ):
        args = parser.parse_args(argv)
        assert args.yes is False
