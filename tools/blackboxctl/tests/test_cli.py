"""The CLI actually exists, and its dry-run defaults hold. GPL-3.0."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from blackboxctl import cli
from test_captures import make_capture

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "blackboxctl", *args],
                          cwd=PACKAGE_ROOT, capture_output=True, text=True)


def test_python_m_blackboxctl_works():
    """It used to fail with 'No module named blackboxctl.__main__'."""
    result = run("--version")
    assert result.returncode == 0
    assert result.stdout.startswith("blackboxctl ")


def test_package_has_an_entrypoint_and_packaging():
    for name in ("__init__.py", "__main__.py", "cli.py"):
        assert (PACKAGE_ROOT / "blackboxctl" / name).is_file(), name
    assert (PACKAGE_ROOT / "pyproject.toml").is_file()
    assert (PACKAGE_ROOT / "LICENSE").is_file()
    assert (PACKAGE_ROOT / "NOTICE").is_file()
    assert (PACKAGE_ROOT / "README.md").is_file()


def test_license_is_gpl3_and_notice_names_every_upstream():
    assert "GNU GENERAL PUBLIC LICENSE" in (PACKAGE_ROOT / "LICENSE").read_text()
    assert "Version 3" in (PACKAGE_ROOT / "LICENSE").read_text()
    notice = (PACKAGE_ROOT / "NOTICE").read_text()
    for url in ("jvsobrinho/mvave-blackbox-ble", "jvsobrinho/mvave-blackbox-edit",
                "pferreir/cuvave-midi", "walterwanderley/am2manager"):
        assert url in notice, url
    for licence in ("CC BY-SA 4.0", "MIT", "GPL-3.0", "Apache-2.0"):
        assert licence in notice, licence


def test_selftest_passes():
    result = run("selftest")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAIL" not in result.stdout


def test_write_paths_reports_nothing_enabled():
    result = run("--json", "write-paths")
    assert result.returncode == 0
    doc = json.loads(result.stdout)
    assert doc["any_enabled"] is False
    assert all(not p["hardware_confirmed"] for p in doc["write_paths"])


def test_no_cli_flag_enables_a_write():
    """Grep the whole parser's help text for anything that sounds like a write."""
    parser = cli.build_parser()
    text = parser.format_help()
    assert "write" not in text.lower().replace("write-paths", "")


def test_decode_from_hex_matches_the_recorded_p41():
    from fixtures import device_frames as fx
    result = run("decode", "--hex", fx.REPLY_FLASH_40.hex())
    assert result.returncode == 0, result.stderr
    assert "Gain" in result.stdout and "45" in result.stdout
    assert "Low Cut" in result.stdout


def test_install_is_dry_run_by_default(tmp_path):
    root = tmp_path / "M-EFCS"
    (root / "ampFile").mkdir(parents=True)
    source = tmp_path / "A.am2Data"
    source.write_bytes(make_capture())
    result = run("--library-root", str(root), "library", "install", str(source))
    assert result.returncode == 0
    assert "DRY RUN" in result.stdout
    assert not (root / "ampFile" / "A.am2Data").exists(), "dry run wrote a file"


def test_install_with_yes_actually_installs(tmp_path):
    root = tmp_path / "M-EFCS"
    (root / "ampFile").mkdir(parents=True)
    source = tmp_path / "A.am2Data"
    source.write_bytes(make_capture())
    result = run("--library-root", str(root), "library", "install",
                 str(source), "--yes")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "ampFile" / "A.am2Data").is_file()


def test_restart_editor_is_dry_run_by_default():
    result = run("library", "restart-editor")
    assert result.returncode == 0
    assert "DRY RUN" in result.stdout
    assert "would run" in result.stdout
    assert "unsaved" in result.stdout.lower()


def test_rename_is_dry_run_by_default(tmp_path):
    path = tmp_path / "A.am2Data"
    original = make_capture()
    path.write_bytes(original)
    result = run("rename", str(path), "NewName")
    assert result.returncode == 0
    assert "DRY RUN" in result.stdout
    assert path.read_bytes() == original


def test_rename_in_place_with_yes_keeps_a_backup(tmp_path):
    path = tmp_path / "A.am2Data"
    original = make_capture()
    path.write_bytes(original)
    result = run("rename", str(path), "NewName", "--in-place", "--yes")
    assert result.returncode == 0, result.stdout + result.stderr
    assert path.read_bytes()[4:18] == b"NewName".ljust(14, b"\x00")
    assert (tmp_path / "A.am2Data.bak").read_bytes() == original


def test_inspect_reports_a_broken_file_with_a_nonzero_exit(tmp_path):
    path = tmp_path / "bad.am2Data"
    path.write_bytes(b"\x00" * 99)
    result = run("inspect", str(path))
    assert result.returncode != 0
    assert "REFUSED" in result.stdout


def test_device_commands_fail_cleanly_when_the_pedal_is_absent():
    result = run("device", "sync")
    if result.returncode == 0:
        pytest.skip("pedal is actually connected")
    assert result.returncode == cli.EXIT_NO_DEVICE
    assert "connected over USB" in result.stderr


@pytest.mark.parametrize("docstring_claim", [
    "blackboxctl rename --in-place",
    "--repair-magic",
    "--library-root",
    "--force",
    "--yes",
])
def test_every_flag_the_docstrings_advertise_actually_exists(docstring_claim):
    """The modules' docstrings used to promise CLI surface that did not exist."""
    flag = docstring_claim.split()[-1]
    help_text = cli.build_parser().format_help()
    subcommands = ["rename", "inspect", "decode", "library", "device",
                   "selftest", "write-paths"]
    combined = help_text + "".join(
        subprocess.run([sys.executable, "-m", "blackboxctl", c, "--help"],
                       cwd=PACKAGE_ROOT, capture_output=True,
                       text=True).stdout for c in subcommands)
    combined += "".join(
        subprocess.run([sys.executable, "-m", "blackboxctl", "library", c,
                        "--help"], cwd=PACKAGE_ROOT, capture_output=True,
                       text=True).stdout
        for c in ("install", "restart-editor", "list", "diff"))
    assert flag in combined, f"{flag} is advertised but not implemented"
