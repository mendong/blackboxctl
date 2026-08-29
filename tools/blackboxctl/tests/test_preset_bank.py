"""Reproducibility checks for the committed P01-P12 preset bank."""

from __future__ import annotations

from pathlib import Path

import pytest

from blackboxctl import presetfiles, protocol

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PRESETS = REPOSITORY_ROOT / "presets"


def _spec_for(slot: int) -> Path:
    matches = sorted((PRESETS / "specs").glob(f"P{slot:02d}-*.json"))
    assert len(matches) == 1, f"P{slot:02d} must have exactly one specification"
    return matches[0]


@pytest.mark.parametrize("slot", range(1, 13))
def test_core_bank_render_is_reproducible_and_lossless(slot: int) -> None:
    """Each checked-in image must be the exact base-plus-spec transformation."""
    base = presetfiles.load_image(PRESETS / "base-before-20260829" / f"P{slot:02d}.bin")
    rendered = presetfiles.load_image(PRESETS / "rendered" / f"P{slot:02d}.bin")
    regenerated, _changes = presetfiles.apply(
        base, presetfiles.load_spec(_spec_for(slot))
    )

    assert len(base) == protocol.PRESET_SIZE
    assert regenerated == rendered
