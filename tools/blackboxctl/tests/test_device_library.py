"""Device-library manifest validation and CLI dry-run behavior."""

from __future__ import annotations

import json
import subprocess
import sys
import wave
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from blackboxctl import backups, cli, device_library, protocol, storage, transport

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _write_ir(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(3)
        wav.setframerate(44100)
        wav.writeframes(bytes(2048 * 3))


def _manifest(path: Path, entries: list[dict]) -> None:
    path.write_text(
        json.dumps(
            {
                "schema": device_library.SCHEMA,
                "entries": entries,
            }
        ),
        encoding="utf-8",
    )


def test_manifest_prepares_relative_cab_without_hardware(tmp_path):
    root = tmp_path / "M-EFCS"
    (root / "cabFile").mkdir(parents=True)
    source = root / "cabFile" / "test.wav"
    _write_ir(source)
    manifest = tmp_path / "library.json"
    _manifest(
        manifest,
        [
            {
                "kind": "cab",
                "slot": 7,
                "name": "7HIWATT412",
                "file": "cabFile/test.wav",
                "level": 50,
            }
        ],
    )
    entries = device_library.load(manifest, library_root=root)
    assert len(entries) == 1
    assert entries[0].slot == 7 and entries[0].name == "7HIWATT412"
    assert len(entries[0].record) == protocol.CAB_RECORD_SIZE


def test_manifest_refuses_duplicate_target(tmp_path):
    source = tmp_path / "test.wav"
    _write_ir(source)
    manifest = tmp_path / "library.json"
    row = {"kind": "cab", "slot": 1, "name": "ONE", "file": "test.wav"}
    _manifest(manifest, [row, dict(row)])
    with pytest.raises(device_library.ManifestError, match="duplicate"):
        device_library.load(manifest, library_root=tmp_path)


@pytest.mark.parametrize(
    ("location", "field"),
    [
        ("top", "source_set_sha265"),
        ("entry", "leve"),
        ("amp_entry", "level"),
    ],
)
def test_manifest_refuses_unknown_or_kind_inappropriate_fields(
    tmp_path, location, field
):
    source = tmp_path / "test.wav"
    _write_ir(source)
    row = {
        "kind": "cab",
        "slot": 1,
        "name": "ONE",
        "file": "test.wav",
    }
    document = {"schema": device_library.SCHEMA, "entries": [row]}
    if location == "top":
        document[field] = "0" * 64
    else:
        row[field] = 99
        if location == "amp_entry":
            row["kind"] = "amp"
    manifest = tmp_path / "library.json"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(device_library.ManifestError, match="unknown"):
        device_library.load(manifest, library_root=tmp_path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("slot", True, "slot must be an integer"),
        ("level", False, "CAB level must be an integer"),
    ],
)
def test_manifest_refuses_booleans_for_integer_fields(tmp_path, field, value, message):
    source = tmp_path / "test.wav"
    _write_ir(source)
    row = {
        "kind": "cab",
        "slot": 1,
        "name": "ONE",
        "file": "test.wav",
        "level": 50,
    }
    row[field] = value
    manifest = tmp_path / "library.json"
    _manifest(manifest, [row])

    with pytest.raises(device_library.ManifestError, match=message):
        device_library.load(manifest, library_root=tmp_path)


def test_manifest_can_pin_the_complete_source_set(tmp_path):
    root = tmp_path / "M-EFCS"
    source = root / "cabFile" / "test.wav"
    source.parent.mkdir(parents=True)
    _write_ir(source)
    row = {
        "kind": "cab",
        "slot": 7,
        "name": "7HIWATT412",
        "file": "cabFile/test.wav",
    }
    evidence = (
        f"cab\t7\tcabFile/test.wav\t{backups.sha256(source.read_bytes())}\n"
    ).encode()
    manifest = tmp_path / "library.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": device_library.SCHEMA,
                "source_set_sha256": backups.sha256(evidence),
                "entries": [row],
            }
        ),
        encoding="utf-8",
    )

    [entry] = device_library.load(manifest, library_root=root)
    assert entry.source_sha256 == backups.sha256(source.read_bytes())

    source.write_bytes(source.read_bytes()[:-1] + b"\x01")
    with pytest.raises(device_library.ManifestError, match="source_set_sha256"):
        device_library.load(manifest, library_root=root)


def test_library_apply_is_offline_dry_run_by_default(tmp_path):
    root = tmp_path / "M-EFCS"
    (root / "cabFile").mkdir(parents=True)
    _write_ir(root / "cabFile" / "test.wav")
    manifest = tmp_path / "library.json"
    _manifest(
        manifest,
        [
            {
                "kind": "cab",
                "slot": 7,
                "name": "7HIWATT412",
                "file": "cabFile/test.wav",
            }
        ],
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "blackboxctl",
            "--library-root",
            str(root),
            "device",
            "library-apply",
            str(manifest),
        ],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DRY RUN" in result.stdout
    assert "no device was opened" in result.stdout


def test_resume_journal_preserves_verified_hash_evidence(tmp_path):
    path = tmp_path / "journal.json"
    entries = [
        {
            "kind": "cab",
            "slot": 1,
            "name": "ONE",
            "source": "/one.wav",
            "record_sha256": "abc",
        }
    ]
    original = {
        "schema": "blackboxctl.library-apply-journal.v1",
        "entries": entries,
        "results": [
            {
                "kind": "cab",
                "slot": 1,
                "name": "ONE",
                "status": "saved-name-verified",
                "record_sha256": "abc",
            }
        ],
    }
    path.write_text(json.dumps(original))
    loaded = cli._load_library_journal(path, entries)
    assert loaded["results"] == original["results"]


def test_uncertain_rewrite_invalidates_older_verified_resume_evidence(
    tmp_path, monkeypatch
):
    entry = device_library.PreparedEntry(
        kind="cab",
        slot=1,
        name="TARGET",
        source=tmp_path / "source.wav",
        record=bytes(protocol.CAB_RECORD_SIZE),
    )
    monkeypatch.setattr(device_library, "load", lambda *_args, **_kwargs: [entry])
    calls = 0

    def transmit(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return cli.LibraryCommitTransfer(
            exact_acks=1, frame_count=1, table_index=1, timeout=0.0
        )

    monkeypatch.setattr(cli, "_transmit_library_commit", transmit)
    monkeypatch.setattr(
        cli,
        "_wait_for_library_name",
        lambda *_args, **_kwargs: ["TARGET"] * protocol.NAME_COUNT,
    )

    class LibraryDevice:
        def read_memory(self, *_args, **_kwargs):
            name = b"TARGET".ljust(protocol.NAME_STRIDE, b"\0")
            return SimpleNamespace(payload=name * protocol.NAME_COUNT)

    @contextmanager
    def open_device():
        yield LibraryDevice()

    monkeypatch.setattr(transport, "open_device", open_device)
    summary = [
        {
            "kind": entry.kind,
            "slot": entry.slot,
            "name": entry.name,
            "source": str(entry.source),
            "source_sha256": entry.source_sha256,
            "record_sha256": entry.sha256,
        }
    ]
    journal = tmp_path / "journal.json"
    journal.write_text(
        json.dumps(
            {
                "schema": "blackboxctl.library-apply-journal.v1",
                "entries": summary,
                "results": [
                    {
                        "kind": "cab",
                        "slot": 1,
                        "status": "saved-name-verified",
                        "record_sha256": entry.sha256,
                    },
                    {
                        "kind": "cab",
                        "slot": 1,
                        "status": "commit-uncertain",
                        "record_sha256": entry.sha256,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    args = SimpleNamespace(
        manifest=str(tmp_path / "manifest.json"),
        library_root=str(tmp_path),
        dsp_helper=None,
        yes=True,
        journal=str(journal),
        rewrite=False,
    )

    assert cli.cmd_device_library_apply(args, cli.Out(False)) == cli.EXIT_OK
    assert calls == 1, "an uncertain rewrite must be rewritten, never skipped"
    saved = json.loads(journal.read_text(encoding="utf-8"))
    assert saved["results"][-1]["status"] == "saved-name-verified"


def test_resume_journal_refuses_a_different_prepared_manifest(tmp_path):
    path = tmp_path / "journal.json"
    path.write_text(
        json.dumps(
            {
                "schema": "blackboxctl.library-apply-journal.v1",
                "entries": [],
                "results": [],
            }
        )
    )
    with pytest.raises(RuntimeError, match="do not exactly match"):
        cli._load_library_journal(path, [{"record_sha256": "different"}])


def test_default_journal_paths_do_not_collide_within_one_second():
    first = cli._default_library_journal_path()
    second = cli._default_library_journal_path()

    assert first != second
    assert first.parent == second.parent
    assert first.name.startswith("library-apply-")


@pytest.mark.parametrize("preexisting", [False, True])
def test_library_apply_cannot_touch_a_journal_owned_by_another_process(
    tmp_path, preexisting
):
    journal = tmp_path / "shared-journal.json"
    sentinel = b"first process evidence\n"
    if preexisting:
        journal.write_bytes(sentinel)
    args = SimpleNamespace(
        manifest=str(tmp_path / "manifest.json"),
        library_root=str(tmp_path),
        dsp_helper=None,
        yes=True,
        journal=str(journal),
        rewrite=False,
    )

    with storage.exclusive_lock(cli._library_journal_lock_path(journal.resolve())):
        result = cli.cmd_device_library_apply(args, cli.Out(False))

    assert result == cli.EXIT_FAIL
    if preexisting:
        assert journal.read_bytes() == sentinel
    else:
        assert not journal.exists()
