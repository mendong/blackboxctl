"""Declarative preset editing tests. GPL-3.0."""

from __future__ import annotations

from pathlib import Path

import pytest
from fixtures import device_frames as fx

from blackboxctl import presetfiles, protocol


def p41():
    return protocol.parse_frame(fx.REPLY_FLASH_40).payload


def test_partial_spec_changes_only_named_bytes():
    source = p41()
    result, changes = presetfiles.apply(
        source,
        {
            "volume": 77,
            "blocks": {
                "amp": {"slot": 3, "knobs": {"Gain": 42}},
                "rev": {"enabled": False, "model": "Hall", "knobs": {"Mix": 9}},
            },
        },
    )
    expected_changed = {0, 0x0F, 0x20, 0x0C, 0x12, 0x46}
    actual_changed = {
        i for i, (a, b) in enumerate(zip(source, result, strict=True)) if a != b
    }
    assert actual_changed == expected_changed
    assert {c.field for c in changes} == {
        "volume",
        "amp.slot",
        "amp.Gain",
        "rev.enabled",
        "rev.model",
        "rev.Mix",
    }


def test_export_then_apply_is_byte_identical_for_known_fields():
    source = p41()
    spec = presetfiles.export_spec(source)
    result, changes = presetfiles.apply(source, spec)
    assert result == source
    assert changes == []


@pytest.mark.parametrize(
    "routing",
    [
        (99, 1, 2, 3, 4, 5),
        (0, 0, 2, 3, 4, 5),
    ],
)
def test_export_refuses_unknown_or_duplicate_routing(routing):
    image = bytearray(p41())
    image[2:8] = bytes(routing)

    with pytest.raises(presetfiles.PresetSpecError, match="routing bytes"):
        presetfiles.export_spec(bytes(image))


@pytest.mark.parametrize(
    "spec, message",
    [
        ({"volume": 101}, "outside"),
        ({"routing": ["fx"] * 6}, "exactly once"),
        ({"blocks": {"amp": {"model": 1}}}, "uses 1-based 'slot'"),
        ({"blocks": {"mod": {"slot": 1}}}, "uses 'model'"),
        ({"blocks": {"rev": {"model": "nope"}}}, "not one of"),
    ],
)
def test_invalid_specs_are_refused(spec, message):
    with pytest.raises(presetfiles.PresetSpecError, match=message):
        presetfiles.apply(p41(), spec)


def test_load_image_refuses_a_corrupted_reply_frame(tmp_path: Path):
    raw = bytearray(fx.REPLY_FLASH_40)
    raw[20] ^= 1
    path = tmp_path / "corrupt-frame.bin"
    path.write_bytes(raw)
    with pytest.raises(presetfiles.PresetSpecError, match="malformed"):
        presetfiles.load_image(path)


def test_load_image_accepts_a_well_formed_live_or_flash_reply(tmp_path: Path):
    for name, raw in (("live", fx.REPLY_RAM_DUMP), ("flash", fx.REPLY_FLASH_40)):
        path = tmp_path / f"{name}.bin"
        path.write_bytes(raw)
        assert presetfiles.load_image(path) == protocol.parse_frame(raw).payload
