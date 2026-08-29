"""Lossless device-backup bundle tests. GPL-3.0."""

from __future__ import annotations

import json

import pytest

from blackboxctl import backups, protocol, storage


def bundle():
    return backups.make_bundle(
        active_index0=2,
        amp_names=[f"amp{i}" for i in range(protocol.NAME_COUNT)],
        cab_names=[f"cab{i}" for i in range(protocol.NAME_COUNT)],
        images=[
            bytes([i]) * protocol.PRESET_SIZE for i in range(protocol.PRESET_COUNT)
        ],
        device={"manufacturer": "Jieli Technology"},
    )


def test_round_trip_and_slot_extraction(tmp_path):
    path = tmp_path / "backup.json"
    backups.write_atomic(path, bundle())
    loaded = backups.load(path)
    assert backups.image_for_slot(loaded, 80) == bytes([79]) * 92
    assert loaded["active_preset"]["slot"] == 3
    images = backups.slot_images(loaded)
    assert len(images) == protocol.PRESET_COUNT
    assert images[0] == (1, bytes([0]) * 92)
    assert images[-1] == (80, bytes([79]) * 92)


def test_refuses_overwrite_without_force(tmp_path):
    path = tmp_path / "backup.json"
    backups.write_atomic(path, bundle())
    with pytest.raises(backups.BackupError, match="--force"):
        backups.write_atomic(path, bundle())


def test_atomic_write_does_not_clobber_a_concurrent_destination(tmp_path, monkeypatch):
    path = tmp_path / "backup.json"
    real_link = storage.os.link

    def racing_link(source, destination):
        destination.write_text("other invocation")
        return real_link(source, destination)

    monkeypatch.setattr(storage.os, "link", racing_link)
    with pytest.raises(backups.BackupError, match="concurrently"):
        backups.write_atomic(path, bundle())
    assert path.read_text() == "other invocation"


def test_atomic_replace_replaces_a_symlink_not_its_target(tmp_path):
    victim = tmp_path / "outside.txt"
    victim.write_text("IMPORTANT")
    destination = tmp_path / "backup.json"
    destination.symlink_to(victim)

    backups.write_atomic(destination, bundle(), force=True)

    assert not destination.is_symlink()
    assert backups.load(destination)["schema"] == backups.SCHEMA
    assert victim.read_text() == "IMPORTANT"


def test_detects_one_changed_byte(tmp_path):
    doc = bundle()
    doc["presets"][5]["image_hex"] = "ff" + doc["presets"][5]["image_hex"][2:]
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(backups.BackupError, match="P06: SHA-256 mismatch"):
        backups.load(path)


def test_detects_missing_slot():
    doc = bundle()
    doc["presets"].pop()
    with pytest.raises(backups.BackupError, match="exactly 80"):
        backups.validate_bundle(doc)


def test_detects_missing_created_at_before_cli_consumes_it():
    doc = bundle()
    del doc["created_at"]
    with pytest.raises(backups.BackupError, match="created_at"):
        backups.validate_bundle(doc)


def test_detects_active_slot_index_mismatch():
    doc = bundle()
    doc["active_preset"]["slot"] = 4
    with pytest.raises(backups.BackupError, match=r"index0 \+ 1"):
        backups.validate_bundle(doc)


@pytest.mark.parametrize(
    ("location", "field", "message"),
    [
        ("active", "index0", "active_preset.index0"),
        ("active", "slot", r"index0 \+ 1"),
        ("preset", "index0", "integer index0"),
        ("preset", "slot", "slot/index mismatch"),
        ("preset", "address", "address/index mismatch"),
    ],
)
def test_backup_integer_fields_reject_json_booleans(location, field, message):
    doc = bundle()
    target = doc["active_preset"] if location == "active" else doc["presets"][0]
    target[field] = False

    with pytest.raises(backups.BackupError, match=message):
        backups.validate_bundle(doc)
