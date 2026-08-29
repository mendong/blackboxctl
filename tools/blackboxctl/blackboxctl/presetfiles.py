"""Declarative, lossless preset image editing.

Specifications describe only values to change. Unknown/reserved bytes are
preserved from the 92-byte base image, making this safer than rebuilding a
preset from a partially understood schema.

GPL-3.0-or-later. See ../LICENSE and ../NOTICE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import protocol


class PresetSpecError(RuntimeError):
    """A preset source or declarative field is invalid."""


@dataclass(frozen=True)
class Change:
    field: str
    before: Any
    after: Any


def normalize_image_bytes(image: bytes) -> bytes:
    """Return one validated 92-byte preset image from raw bytes or a reply frame."""
    if len(image) == protocol.RAM_DUMP_FRAME_LEN:
        frame = protocol.parse_frame(image)
        flash_end = (
            protocol.ADDR_PRESET_BASE + protocol.PRESET_COUNT * protocol.PRESET_SIZE
        )
        is_live = frame.address == protocol.ADDR_LIVE_RAM
        is_flash = (
            protocol.ADDR_PRESET_BASE <= frame.address < flash_end
            and frame.address % protocol.PRESET_SIZE == 0
        )
        if (
            not frame.well_formed
            or frame.magic != protocol.MAGIC_READ
            or frame.space != protocol.SPACE_PARAM
            or frame.size != protocol.PRESET_SIZE
            or not (is_live or is_flash)
        ):
            raise PresetSpecError(
                "preset reply frame is malformed or does not address one complete "
                "live/stored preset"
            )
        image = frame.payload
    if len(image) != protocol.PRESET_SIZE:
        raise PresetSpecError(
            f"preset image must be {protocol.PRESET_SIZE} bytes, got {len(image)}"
        )
    return image


def load_image(path: Path) -> bytes:
    try:
        image = path.expanduser().read_bytes()
    except OSError as exc:
        raise PresetSpecError(f"cannot read {path}: {exc}") from exc
    return normalize_image_bytes(image)


def load_spec(path: Path) -> dict[str, Any]:
    try:
        spec = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except OSError as exc:
        raise PresetSpecError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise PresetSpecError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise PresetSpecError("preset specification root must be an object")
    return spec


def _int(value: Any, field: str, lo: int = 0, hi: int = 100) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PresetSpecError(f"{field} must be an integer {lo}..{hi}")
    if not lo <= value <= hi:
        raise PresetSpecError(f"{field} {value} is outside {lo}..{hi}")
    return value


def _norm(text: str) -> str:
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def _dynamic_model(block: protocol.Block, value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        if 0 <= value < len(block.models):
            return value
        raise PresetSpecError(
            f"{block.key}.model index {value} is outside 0..{len(block.models) - 1}"
        )
    if isinstance(value, str):
        wanted = _norm(value)
        for index, name in enumerate(block.models):
            if _norm(name) == wanted:
                return index
        raise PresetSpecError(
            f"{block.key}.model {value!r} is not one of {list(block.models)}"
        )
    raise PresetSpecError(f"{block.key}.model must be a model name or 0-based integer")


def apply(image: bytes, spec: dict[str, Any]) -> tuple[bytes, list[Change]]:
    """Apply a validated partial JSON spec while preserving every other byte."""
    if len(image) != protocol.PRESET_SIZE:
        raise PresetSpecError(
            f"preset image must be {protocol.PRESET_SIZE} bytes, got {len(image)}"
        )
    allowed_top = {"name", "volume", "routing", "blocks"}
    unknown = set(spec) - allowed_top
    if unknown:
        raise PresetSpecError(f"unknown top-level field(s): {sorted(unknown)}")
    data = bytearray(image)
    changes: list[Change] = []

    if "volume" in spec:
        value = _int(spec["volume"], "volume")
        before = int.from_bytes(data[0:2], "little")
        data[0:2] = value.to_bytes(2, "little")
        if before != value:
            changes.append(Change("volume", before, value))

    if "routing" in spec:
        routing = spec["routing"]
        if not isinstance(routing, list) or len(routing) != 6:
            raise PresetSpecError("routing must be a six-item block-key array")
        if not all(
            isinstance(key, str) and key in protocol.BLOCKS_BY_KEY for key in routing
        ):
            raise PresetSpecError(
                f"routing keys must come from {sorted(protocol.BLOCKS_BY_KEY)}"
            )
        if len(set(routing)) != 6:
            raise PresetSpecError("routing must contain every block exactly once")
        value = [protocol.BLOCKS_BY_KEY[key].block_id for key in routing]
        before = list(data[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6])
        data[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6] = bytes(value)
        if before != value:
            changes.append(Change("routing", before, value))

    blocks = spec.get("blocks", {})
    if not isinstance(blocks, dict):
        raise PresetSpecError(
            "blocks must be an object keyed by fx/amp/mod/dly/rev/cab"
        )
    unknown_blocks = set(blocks) - set(protocol.BLOCKS_BY_KEY)
    if unknown_blocks:
        raise PresetSpecError(f"unknown block(s): {sorted(unknown_blocks)}")

    for key, block_spec in blocks.items():
        if not isinstance(block_spec, dict):
            raise PresetSpecError(f"blocks.{key} must be an object")
        block = protocol.BLOCKS_BY_KEY[key]
        allowed = {"enabled", "model", "slot", "knobs"}
        bad = set(block_spec) - allowed
        if bad:
            raise PresetSpecError(f"blocks.{key}: unknown field(s) {sorted(bad)}")

        if "enabled" in block_spec:
            enabled = block_spec["enabled"]
            if not isinstance(enabled, bool):
                raise PresetSpecError(f"blocks.{key}.enabled must be true or false")
            before = bool(data[block.toggle_addr])
            data[block.toggle_addr] = int(enabled)
            if before != enabled:
                changes.append(Change(f"{key}.enabled", before, enabled))

        if key in protocol.MODELLESS_BLOCKS:
            if "model" in block_spec:
                raise PresetSpecError(f"blocks.{key} uses 1-based 'slot', not 'model'")
            if "slot" in block_spec:
                slot1 = _int(
                    block_spec["slot"], f"blocks.{key}.slot", 1, protocol.NAME_COUNT
                )
                model = slot1 - 1
                before = data[block.model_addr]
                data[block.model_addr] = model
                if before != model:
                    changes.append(Change(f"{key}.slot", before + 1, slot1))
        else:
            if "slot" in block_spec:
                raise PresetSpecError(f"blocks.{key} uses 'model', not 'slot'")
            if "model" in block_spec:
                model = _dynamic_model(block, block_spec["model"])
                before = data[block.model_addr]
                data[block.model_addr] = model
                if before != model:
                    changes.append(Change(f"{key}.model", before, model))

        knobs = block_spec.get("knobs", {})
        if not isinstance(knobs, dict):
            raise PresetSpecError(f"blocks.{key}.knobs must be an object")
        model_index = data[block.model_addr]
        known = block.knob_names(model_index)
        by_name = {
            _norm(name): (slot1, name)
            for slot1, name in enumerate(known, start=1)
            if name != protocol.GHOST
        }
        for requested, raw_value in knobs.items():
            if not isinstance(requested, str) or _norm(requested) not in by_name:
                names = [name for name in known if name != protocol.GHOST]
                raise PresetSpecError(
                    f"blocks.{key}.knobs.{requested}: unknown for selected model; "
                    f"available: {names}"
                )
            slot1, canonical = by_name[_norm(requested)]
            value = _int(raw_value, f"blocks.{key}.knobs.{canonical}")
            addr = block.knob_addr(slot1)
            before = int.from_bytes(data[addr : addr + 2], "little")
            data[addr : addr + 2] = value.to_bytes(2, "little")
            if before != value:
                changes.append(Change(f"{key}.{canonical}", before, value))

    return bytes(data), changes


def export_spec(image: bytes) -> dict[str, Any]:
    preset = protocol.decode_preset(image)
    routing_ids = set(protocol.BLOCKS_BY_ID)
    if len(preset.routing) != len(routing_ids) or set(preset.routing) != routing_ids:
        raise PresetSpecError(
            "cannot export this image: routing bytes must contain each block id "
            f"exactly once; got {preset.routing}"
        )
    blocks: dict[str, Any] = {}
    for state in preset.blocks:
        row: dict[str, Any] = {"enabled": state.enabled}
        if state.key in protocol.MODELLESS_BLOCKS:
            row["slot"] = state.model_index + 1
        else:
            row["model"] = state.model_name
        row["knobs"] = {name: value for _slot, name, _addr, value in state.knobs}
        blocks[state.key] = row
    return {
        "volume": preset.volume,
        "routing": [protocol.BLOCKS_BY_ID[item].key for item in preset.routing],
        "blocks": blocks,
    }
