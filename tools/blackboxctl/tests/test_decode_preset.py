"""decode_preset against the four real preset images. GPL-3.0.

The regression that matters most here is the AMP/CAB knob bug: Block.knob_names
used to index a 1-tuple by the model byte, and the model byte for AMP and CAB is
a 0..19 capture/IR SLOT number, not an algorithm id. Any slot but #1 fell
through to an all-ghost fallback and every AMP and CAB knob silently vanished.
Three of the four real presets below have a non-zero AMP or CAB model byte, so
these tests fail loudly if that regresses.
"""

from __future__ import annotations

import pytest
from fixtures import device_frames as fx

from blackboxctl import protocol


def decode(reply: bytes):
    frame = protocol.parse_frame(reply)
    return protocol.decode_preset(frame.payload, fx.AMP_NAMES, fx.CAB_NAMES)


def knobs(preset, key):
    block = next(b for b in preset.blocks if b.key == key)
    return [(name, value) for _slot, name, _addr, value in block.knobs]


def block(preset, key):
    return next(b for b in preset.blocks if b.key == key)


# --- The AMP/CAB knob bug -------------------------------------------------


@pytest.mark.parametrize("model_index", range(protocol.NAME_COUNT))
def test_amp_knobs_are_the_same_five_for_every_capture_slot(model_index):
    image = bytearray(protocol.parse_frame(fx.REPLY_FLASH_40).payload)
    amp = protocol.BLOCKS_BY_KEY["amp"]
    image[amp.model_addr] = model_index
    preset = protocol.decode_preset(bytes(image), fx.AMP_NAMES, fx.CAB_NAMES)
    assert [n for n, _ in knobs(preset, "amp")] == [
        "Gain",
        "Level",
        "Bass",
        "Mid",
        "Treble",
    ]
    # The values must be the raw bytes, not a fallback.
    assert knobs(preset, "amp") == fx.EXPECTED_P41["amp_knobs"]


@pytest.mark.parametrize("model_index", range(protocol.NAME_COUNT))
def test_cab_knobs_are_the_same_three_for_every_ir_slot(model_index):
    image = bytearray(protocol.parse_frame(fx.REPLY_FLASH_40).payload)
    cab = protocol.BLOCKS_BY_KEY["cab"]
    image[cab.model_addr] = model_index
    preset = protocol.decode_preset(bytes(image), fx.AMP_NAMES, fx.CAB_NAMES)
    assert knobs(preset, "cab") == fx.EXPECTED_P41["cab_knobs"]


def test_amp_and_cab_are_marked_non_dynamic():
    for key in protocol.MODELLESS_BLOCKS:
        assert not protocol.BLOCKS_BY_KEY[key].is_dynamic
    for key in ("fx", "mod", "dly", "rev"):
        assert protocol.BLOCKS_BY_KEY[key].is_dynamic


def test_an_unknown_model_index_raises_instead_of_decoding_to_nothing():
    """A dynamic block with an out-of-range model byte must not look empty."""
    image = bytearray(protocol.parse_frame(fx.REPLY_FLASH_40).payload)
    image[protocol.BLOCKS_BY_KEY["mod"].model_addr] = 99
    with pytest.raises(ValueError, match="model index 99"):
        protocol.decode_preset(bytes(image), fx.AMP_NAMES, fx.CAB_NAMES)


# --- The four real presets ------------------------------------------------


def test_p41_matches_device_validation_exactly():
    """P41 'Wonderwall Live' - the memory-map ground truth."""
    preset = decode(fx.REPLY_FLASH_40)
    want = fx.EXPECTED_P41
    assert preset.volume == want["volume"]
    assert preset.routing_names == want["routing_names"]
    for key, enabled in want["enabled"].items():
        assert block(preset, key).enabled is enabled, key
    for key, model in want["models"].items():
        assert block(preset, key).model_index == model, key
    assert block(preset, "amp").model_name == want["model_names"]["amp"]
    assert block(preset, "cab").model_name == want["model_names"]["cab"]
    assert knobs(preset, "amp") == want["amp_knobs"]
    assert knobs(preset, "cab") == want["cab_knobs"]
    assert knobs(preset, "mod") == want["mod_knobs"]
    assert knobs(preset, "rev") == want["rev_knobs"]


def test_p01_matches_device_validation_exactly():
    """P01 - AMP slot 2 and CAB slot 11, both non-zero model bytes."""
    preset = decode(fx.REPLY_FLASH_00)
    want = fx.EXPECTED_P01
    assert preset.volume == want["volume"]
    assert preset.routing_names == want["routing_names"]
    for key, model in want["models"].items():
        assert block(preset, key).model_index == model, key
    assert block(preset, "amp").model_name == want["model_names"]["amp"]
    assert block(preset, "cab").model_name == want["model_names"]["cab"]
    assert knobs(preset, "amp") == want["amp_knobs"]
    assert knobs(preset, "cab") == want["cab_knobs"]


def test_live_ram_matches_device_validation_exactly():
    preset = decode(fx.REPLY_RAM_DUMP)
    want = fx.EXPECTED_RAM
    assert preset.volume == want["volume"]
    assert preset.routing_names == want["routing_names"]
    for key, model in want["models"].items():
        assert block(preset, key).model_index == model, key
    assert block(preset, "amp").model_name == want["model_names"]["amp"]
    assert block(preset, "cab").model_name == want["model_names"]["cab"]
    assert knobs(preset, "amp") == want["amp_knobs"]
    assert knobs(preset, "cab") == want["cab_knobs"]


def test_flash_index_2_is_byte_identical_to_the_live_ram_dump():
    """The cross-check that resolved address == preset_index * 92."""
    ram = protocol.parse_frame(fx.REPLY_RAM_DUMP).payload
    flash = protocol.parse_frame(fx.REPLY_FLASH_02).payload
    assert ram == flash
    assert protocol.parse_frame(fx.REPLY_PRESET_SYNC).payload[0] == 2


# --- Display mappings, now actually reachable -----------------------------


def test_cab_display_mappings_are_reachable_from_a_real_preset():
    """These were dead code while the CAB knob lookup was broken."""
    preset = decode(fx.REPLY_FLASH_40)
    values = dict(knobs(preset, "cab"))
    assert (
        protocol.format_knob_value("cab", "Low Cut", values["Low Cut"]) == "26 (93 Hz)"
    )
    assert "18.0 kHz" in protocol.format_knob_value(
        "cab", "High Cut", values["High Cut"]
    )


# --- Name tables ----------------------------------------------------------


def test_name_tables_decode_to_the_forty_recorded_names():
    cab = protocol.parse_name_table(protocol.parse_frame(fx.REPLY_CAB_NAMES).payload)
    amp = protocol.parse_name_table(protocol.parse_frame(fx.REPLY_AMP_NAMES).payload)
    assert cab == fx.CAB_NAMES
    assert amp == fx.AMP_NAMES
    assert len(cab) == len(amp) == 20


def test_the_trailing_checksum_never_becomes_a_phantom_21st_name():
    """AMP's checksum byte is 0x36 = '6'; a naive null-split yields 21 names."""
    assert fx.REPLY_AMP_NAMES[-1] == 0x36
    assert (
        len(protocol.parse_name_table(protocol.parse_frame(fx.REPLY_AMP_NAMES).payload))
        == 20
    )


def test_a_truncated_name_table_raises_instead_of_under_reporting():
    payload = protocol.parse_frame(fx.REPLY_CAB_NAMES).payload
    with pytest.raises(ValueError, match="truncated"):
        protocol.parse_name_table(payload[:42])


def test_strip_slot_prefix():
    assert protocol.strip_slot_prefix("10SoldSC412", 10) == "SoldSC412"
    assert protocol.strip_slot_prefix("1ML_BEST_IR", 1) == "ML_BEST_IR"
