"""Portable, checksummed full-device backups for :mod:`blackboxctl`.

The bundle deliberately stores the device's 92-byte preset images verbatim.
Named/decoded fields are useful for display, but only the raw images are a
lossless restore source when a future firmware adds fields this client does not
yet understand.

GPL-3.0-or-later. See ../LICENSE and ../NOTICE.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import protocol, storage

SCHEMA = "blackboxctl.device-backup.v1"


class BackupError(RuntimeError):
    """The backup is incomplete, corrupt, or unsafe to use."""


def _is_integer(value: Any) -> bool:
    """JSON integer, excluding booleans (which subclass ``int`` in Python)."""
    return isinstance(value, int) and not isinstance(value, bool)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_bundle(
    *,
    active_index0: int,
    amp_names: Sequence[str],
    cab_names: Sequence[str],
    images: Sequence[bytes],
    device: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate a lossless backup document."""
    if len(images) != protocol.PRESET_COUNT:
        raise BackupError(
            f"need {protocol.PRESET_COUNT} preset images, got {len(images)}"
        )
    if len(amp_names) != protocol.NAME_COUNT or len(cab_names) != protocol.NAME_COUNT:
        raise BackupError(
            f"need {protocol.NAME_COUNT} AMP and CAB names, got "
            f"{len(amp_names)} and {len(cab_names)}"
        )
    presets = []
    for index0, image in enumerate(images):
        if len(image) != protocol.PRESET_SIZE:
            raise BackupError(
                f"P{index0 + 1:02d}: expected {protocol.PRESET_SIZE} bytes, "
                f"got {len(image)}"
            )
        presets.append(
            {
                "slot": index0 + 1,
                "index0": index0,
                "address": index0 * protocol.PRESET_SIZE,
                "sha256": sha256(image),
                "image_hex": image.hex(),
            }
        )
    bundle = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "device": device or {},
        "active_preset": {"slot": active_index0 + 1, "index0": active_index0},
        "amp_names": list(amp_names),
        "cab_names": list(cab_names),
        "presets": presets,
    }
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle: dict[str, Any]) -> None:
    """Raise :class:`BackupError` unless every restore-critical byte validates."""
    if bundle.get("schema") != SCHEMA:
        raise BackupError(
            f"unsupported backup schema {bundle.get('schema')!r}; expected {SCHEMA!r}"
        )
    created_at = bundle.get("created_at")
    if not isinstance(created_at, str) or not created_at.strip():
        raise BackupError("created_at is missing or invalid")
    try:
        datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise BackupError("created_at is not an ISO-8601 timestamp") from exc
    for key in ("amp_names", "cab_names"):
        names = bundle.get(key)
        if not isinstance(names, list) or len(names) != protocol.NAME_COUNT:
            raise BackupError(f"{key} must contain exactly {protocol.NAME_COUNT} names")
        if not all(isinstance(name, str) for name in names):
            raise BackupError(f"{key} contains a non-string value")
    active = bundle.get("active_preset")
    if not isinstance(active, dict) or not _is_integer(active.get("index0")):
        raise BackupError("active_preset.index0 is missing or invalid")
    try:
        protocol.check_preset_index(active["index0"])
    except ValueError as exc:
        raise BackupError(str(exc)) from exc
    expected_active_slot = active["index0"] + 1
    if not _is_integer(active.get("slot")) or active["slot"] != expected_active_slot:
        raise BackupError("active_preset.slot must equal active_preset.index0 + 1")

    presets = bundle.get("presets")
    if not isinstance(presets, list) or len(presets) != protocol.PRESET_COUNT:
        raise BackupError(f"presets must contain exactly {protocol.PRESET_COUNT} slots")
    seen: set[int] = set()
    for entry in presets:
        if not isinstance(entry, dict) or not _is_integer(entry.get("index0")):
            raise BackupError("a preset entry has no integer index0")
        index0 = entry["index0"]
        try:
            protocol.check_preset_index(index0)
        except ValueError as exc:
            raise BackupError(str(exc)) from exc
        if index0 in seen:
            raise BackupError(f"duplicate preset index {index0}")
        seen.add(index0)
        expected_slot = index0 + 1
        expected_address = index0 * protocol.PRESET_SIZE
        if not _is_integer(entry.get("slot")) or entry["slot"] != expected_slot:
            raise BackupError(f"P{expected_slot:02d}: slot/index mismatch")
        if (
            not _is_integer(entry.get("address"))
            or entry["address"] != expected_address
        ):
            raise BackupError(f"P{expected_slot:02d}: address/index mismatch")
        try:
            image = bytes.fromhex(entry.get("image_hex", ""))
        except (TypeError, ValueError) as exc:
            raise BackupError(f"P{expected_slot:02d}: image_hex is invalid") from exc
        if len(image) != protocol.PRESET_SIZE:
            raise BackupError(
                f"P{expected_slot:02d}: image is {len(image)} bytes, expected "
                f"{protocol.PRESET_SIZE}"
            )
        if entry.get("sha256") != sha256(image):
            raise BackupError(f"P{expected_slot:02d}: SHA-256 mismatch")
    if seen != set(range(protocol.PRESET_COUNT)):
        raise BackupError("backup does not contain every preset index exactly once")


def load(path: Path) -> dict[str, Any]:
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BackupError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BackupError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(bundle, dict):
        raise BackupError("backup root must be a JSON object")
    validate_bundle(bundle)
    return bundle


def image_for_slot(bundle: dict[str, Any], slot1: int) -> bytes:
    validate_bundle(bundle)
    protocol.check_preset_index(slot1 - 1)
    entry = next(p for p in bundle["presets"] if p["index0"] == slot1 - 1)
    return bytes.fromhex(entry["image_hex"])


def slot_images(bundle: dict[str, Any]) -> list[tuple[int, bytes]]:
    """Return ``(slot, image)`` pairs in P01..P80 order."""
    validate_bundle(bundle)
    ordered = sorted(bundle["presets"], key=lambda entry: entry["index0"])
    return [(entry["slot"], bytes.fromhex(entry["image_hex"])) for entry in ordered]


def write_atomic(path: Path, bundle: dict[str, Any], *, force: bool = False) -> None:
    """Write a validated bundle atomically, refusing overwrite by default."""
    validate_bundle(bundle)
    payload = (json.dumps(bundle, indent=2, ensure_ascii=False) + "\n").encode()
    try:
        storage.write_bytes_atomic(path, payload, replace=force)
    except storage.DestinationExistsError as exc:
        detail = "was created concurrently" if exc.concurrent else "exists"
        raise BackupError(f"{exc.path} {detail}; pass --force to replace it") from exc
