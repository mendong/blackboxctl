"""Validated, resumable AMP/CAB library manifests for a BlackBox pedal.

GPL-3.0-or-later. See ../LICENSE and ../NOTICE.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import backups, captures, protocol

SCHEMA = "blackboxctl.device-library.v1"


class ManifestError(RuntimeError):
    """A device-library manifest is incomplete or unsafe to apply."""


@dataclass(frozen=True)
class PreparedEntry:
    kind: str
    slot: int
    name: str
    source: Path
    record: bytes
    level: int | None = None
    source_sha256: str | None = None

    @property
    def sha256(self) -> str:
        return backups.sha256(self.record)


def load(
    path: Path, *, library_root: Path, dsp_helper: Path | None = None
) -> list[PreparedEntry]:
    """Parse and fully build every record before any hardware is opened."""
    path = Path(path).expanduser().resolve()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ManifestError(f"manifest schema must be {SCHEMA!r}")
    unknown_top_level = set(doc) - {"schema", "entries", "source_set_sha256"}
    if unknown_top_level:
        raise ManifestError(f"unknown manifest field(s): {sorted(unknown_top_level)}")
    rows = doc.get("entries")
    if not isinstance(rows, list) or not rows:
        raise ManifestError("manifest entries must be a non-empty list")
    expected_source_set = doc.get("source_set_sha256")
    if expected_source_set is not None and (
        not isinstance(expected_source_set, str)
        or len(expected_source_set) != 64
        or any(ch not in "0123456789abcdef" for ch in expected_source_set)
    ):
        raise ManifestError("source_set_sha256 must be 64 lowercase hex characters")

    root = Path(library_root).expanduser().resolve()
    prepared: list[PreparedEntry] = []
    source_evidence: list[str] = []
    seen: set[tuple[str, int]] = set()
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ManifestError(f"entry {number} must be an object")
        kind = row.get("kind")
        if kind == "ir":
            kind = "cab"
        if kind not in ("amp", "cab"):
            raise ManifestError(f"entry {number}: kind must be amp or cab")
        allowed_fields = {"kind", "slot", "name", "file"}
        if kind == "cab":
            allowed_fields.add("level")
        unknown_fields = set(row) - allowed_fields
        if unknown_fields:
            raise ManifestError(
                f"entry {number}: unknown field(s): {sorted(unknown_fields)}"
            )
        slot = row.get("slot")
        if isinstance(slot, bool) or not isinstance(slot, int):
            raise ManifestError(f"entry {number}: slot must be an integer")
        try:
            protocol.check_capture_index(slot - 1)
        except ValueError as exc:
            raise ManifestError(f"entry {number}: {exc}") from exc
        key = (kind, slot)
        if key in seen:
            raise ManifestError(f"entry {number}: duplicate {kind} slot {slot}")
        seen.add(key)
        name = row.get("name")
        if not isinstance(name, str) or not name:
            raise ManifestError(f"entry {number}: name is required")
        raw_source = row.get("file")
        if not isinstance(raw_source, str) or not raw_source:
            raise ManifestError(f"entry {number}: file is required")
        source = Path(raw_source).expanduser()
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if not source.is_file():
            raise ManifestError(f"entry {number}: no such file: {source}")
        try:
            source_before = source.read_bytes()
        except OSError as exc:
            raise ManifestError(f"entry {number}: cannot read {source}: {exc}") from exc
        try:
            if kind == "amp":
                record = captures.build_amp_device_record(source, name, dsp_helper)
                level = None
            else:
                level = row.get("level", 50)
                if isinstance(level, bool) or not isinstance(level, int):
                    raise ManifestError(f"entry {number}: CAB level must be an integer")
                record = captures.build_cab_record(source, name, level)
        except (OSError, captures.CaptureEditError) as exc:
            raise ManifestError(f"entry {number}: {exc}") from exc
        try:
            source_after = source.read_bytes()
        except OSError as exc:
            raise ManifestError(
                f"entry {number}: cannot reread {source}: {exc}"
            ) from exc
        if source_after != source_before:
            raise ManifestError(
                f"entry {number}: source changed while it was being prepared: {source}"
            )
        source_sha256 = backups.sha256(source_before)
        source_evidence.append(f"{kind}\t{slot}\t{raw_source}\t{source_sha256}")
        prepared.append(
            PreparedEntry(
                kind=kind,
                slot=slot,
                name=name,
                source=source,
                record=record,
                level=level,
                source_sha256=source_sha256,
            )
        )
    actual_source_set = backups.sha256(("\n".join(source_evidence) + "\n").encode())
    if expected_source_set is not None and actual_source_set != expected_source_set:
        raise ManifestError(
            "source_set_sha256 mismatch: the selected AMP/CAB files changed; "
            "review them and intentionally update the manifest hash"
        )
    return prepared
