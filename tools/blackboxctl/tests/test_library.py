"""install() backup, idempotence, batch survival; slot map validation. GPL-3.0.

Everything here runs against a temporary library root. Nothing in this file
touches the real M-EFCS container.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from blackboxctl import library, protocol
from test_captures import make_capture, make_wav
from blackboxctl import captures


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def lib(tmp_path):
    root = tmp_path / "M-EFCS"
    (root / library.AMP_DIR).mkdir(parents=True)
    (root / library.CAB_DIR).mkdir(parents=True)
    return library.Library(root=root)


@pytest.fixture
def source_a(tmp_path):
    path = tmp_path / "src" / "Amp.am2Data"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(make_capture(name=b"AAA\x00"))
    return path


@pytest.fixture
def source_b(tmp_path):
    path = tmp_path / "src2" / "Amp.am2Data"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(make_capture(name=b"BBB\x00"))
    return path


def test_install_creates_the_file(lib, source_a):
    results = library.install(lib, [source_a])
    assert [r.action for r in results] == ["installed"]
    assert results[0].destination.is_file()
    assert results[0].backup is None
    assert sha(results[0].destination) == sha(source_a)


def test_install_skips_without_force(lib, source_a, source_b):
    library.install(lib, [source_a])
    results = library.install(lib, [source_b])
    assert [r.action for r in results] == ["skipped"]
    assert sha(results[0].destination) == sha(source_a)


def test_two_replacements_in_one_second_keep_both_backups(lib, source_a,
                                                          source_b, tmp_path):
    """A same-second collision must not overwrite the first backup."""
    library.install(lib, [source_a])
    library.install(lib, [source_b], force=True)
    third = tmp_path / "src3" / "Amp.am2Data"
    third.parent.mkdir(exist_ok=True)
    third.write_bytes(make_capture(name=b"CCC\x00"))
    library.install(lib, [third], force=True)
    backups = sorted((lib.amp_dir).glob("*.bak"))
    assert len(backups) == 2, [p.name for p in backups]
    assert sha(backups[0]) != sha(backups[1])


def test_force_replaces_but_keeps_the_original(lib, source_a, source_b):
    """force=True must mean 'replace and keep', never 'replace irrecoverably'.

    The sibling module's captures.write_with_backup already copies aside; this
    path used to shutil.copy2 straight over the incumbent with no backup.
    """
    first = library.install(lib, [source_a])[0]
    before = sha(first.destination)
    result = library.install(lib, [source_b], force=True)[0]
    assert result.action == "replaced"
    assert sha(result.destination) == sha(source_b)
    assert result.backup is not None and result.backup.is_file()
    assert sha(result.backup) == before


def test_installing_a_file_over_itself_is_skipped_not_an_exception(lib, source_a):
    """shutil.SameFileError used to escape and abandon the whole batch."""
    installed = library.install(lib, [source_a])[0].destination
    results = library.install(lib, [installed], force=True)
    assert [r.action for r in results] == ["skipped"]
    assert "same file" in results[0].reason


def test_one_bad_file_does_not_abandon_the_batch(lib, source_a, tmp_path):
    installed = library.install(lib, [source_a])[0].destination
    later = tmp_path / "src" / "Later.am2Data"
    later.write_bytes(make_capture(name=b"CCC\x00"))
    missing = tmp_path / "does-not-exist.am2Data"
    results = library.install(lib, [installed, missing, later], force=True)
    assert len(results) == 3, "every source must get exactly one result row"
    assert [r.action for r in results] == ["skipped", "refused", "installed"]


def test_reason_and_warnings_are_separate_fields(lib, tmp_path):
    """'installed | empty name' used to read like a failure."""
    path = tmp_path / "Empty.am2Data"
    path.write_bytes(make_capture(name=b"\x00"))
    result = library.install(lib, [path])[0]
    assert result.action == "installed"
    assert result.reason == ""
    assert "empty name" in result.warnings
    described = result.describe()
    assert described.startswith("installed "), described
    # The warning must be labelled as a warning, not sit where a refusal
    # reason goes. "installed | empty name" used to read like a failure.
    assert "warnings: empty name" in described
    assert described.index("warnings:") > described.index("installed")
    # Warnings live on their own line, never inline after the action.
    assert described.splitlines()[0].strip().endswith("Empty.am2Data")


def test_am2converter_magic_installs(lib, tmp_path):
    """install() and diff_slots must not disagree about one path."""
    path = tmp_path / "Conv.am2data"
    path.write_bytes(make_capture(magic=b"\x00\x00\x32\x00"))
    result = library.install(lib, [path])[0]
    assert result.action == "installed"
    assert any("am2converter" in w for w in result.warnings)


def test_float_ir_installs(lib, tmp_path):
    path = tmp_path / "Float.wav"
    path.write_bytes(make_wav(captures.WAVE_FORMAT_IEEE_FLOAT, 1, 44100, 32, 1020))
    result = library.install(lib, [path])[0]
    assert result.action == "installed"
    assert result.destination.parent.name == library.CAB_DIR


def test_a_broken_file_is_still_refused(lib, tmp_path):
    path = tmp_path / "Broken.am2Data"
    path.write_bytes(b"\x00" * 100)
    result = library.install(lib, [path])[0]
    assert result.action == "refused"
    assert result.reason


# --- Slot maps ------------------------------------------------------------


def write_map(tmp_path, rows: str) -> Path:
    doc = tmp_path / "library.md"
    doc.write_text("## AMP slot map\n\n"
                   "| Slot | File | Role |\n| --- | --- | --- |\n" + rows)
    return doc


def test_slot_numbers_are_range_checked(tmp_path):
    for bad in (0, 21, 25):
        doc = write_map(tmp_path, f"| {bad} | Thing | role |\n")
        with pytest.raises(library.LibraryError, match="out of range"):
            library.parse_slot_maps(doc)


def test_duplicate_slots_are_rejected(tmp_path):
    doc = write_map(tmp_path, "| 3 | A | r |\n| 3 | B | r |\n")
    with pytest.raises(library.LibraryError, match="more than once"):
        library.parse_slot_maps(doc)


def test_a_valid_slot_map_parses(tmp_path):
    doc = write_map(tmp_path, "| 1 | A | r |\n| 20 | B | r |\n")
    planned = library.parse_slot_maps(doc)
    assert [p.slot for p in planned] == [1, 20]
    assert all(p.kind == "amp" for p in planned)


def test_the_real_library_doc_still_parses():
    doc = library.default_library_doc()
    if not doc.is_file():
        pytest.skip("presets/library.md not present")
    planned = library.parse_slot_maps(doc)
    assert planned
    for slot in planned:
        protocol.check_slot_number(slot.slot, slot.kind)


# --- restart_editor -------------------------------------------------------


def test_restart_editor_without_consent_only_reports():
    commands = library.restart_editor()
    assert len(commands) == 2
    assert "quit" in commands[0] and "open -b" in commands[1]


def test_restart_editor_refuses_half_consent():
    with pytest.raises(library.LibraryError, match="confirmed_by_user"):
        library.restart_editor(library.RestartConsent())
    with pytest.raises(library.LibraryError, match="unsaved"):
        library.restart_editor(
            library.RestartConsent(confirmed_by_user=True))
