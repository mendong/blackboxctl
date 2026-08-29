"""The CLI actually exists, and its dry-run defaults hold. GPL-3.0."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_captures import make_capture

from blackboxctl import backups, cli, transport

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "blackboxctl", *args],
        cwd=PACKAGE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_package_version_matches_pyproject():
    pyproject = (PACKAGE_ROOT / "pyproject.toml").read_text()
    assert f'version = "{cli.__version__}"' in pyproject
    assert '"pytest>=7"' in pyproject
    assert "github.com/mendong/blackboxctl" in pyproject


def test_json_mode_emits_one_document_for_uncaught_errors(monkeypatch, capsys):
    class Parser:
        def parse_args(self, _argv=None):
            namespace = argparse.Namespace(json=True)

            def boom(_args, _out):
                raise RuntimeError("unexpected failure")

            namespace.func = boom
            return namespace

    monkeypatch.setattr(cli, "build_parser", Parser)
    code = cli.main([])
    document = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_FAIL
    assert document["ok"] is False
    assert document["error"] == "unexpected failure"


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


def test_repository_mixed_license_files_exist():
    root = PACKAGE_ROOT.resolve().parents[1]
    mapping = root / "LICENSE"
    if not mapping.is_file():
        pytest.skip("repository license map not present")
    text = mapping.read_text()
    assert "GNU General Public License v3.0" in text
    assert "CC BY-SA 4.0" in text
    cc = root / "LICENSES" / "CC-BY-SA-4.0.txt"
    assert cc.is_file()
    assert "Attribution-ShareAlike 4.0" in cc.read_text()


def test_license_is_gpl3_and_notice_names_every_upstream():
    assert "GNU GENERAL PUBLIC LICENSE" in (PACKAGE_ROOT / "LICENSE").read_text()
    assert "Version 3" in (PACKAGE_ROOT / "LICENSE").read_text()
    notice = (PACKAGE_ROOT / "NOTICE").read_text()
    for url in (
        "jvsobrinho/mvave-blackbox-ble",
        "jvsobrinho/mvave-blackbox-edit",
        "pferreir/cuvave-midi",
        "walterwanderley/am2manager",
    ):
        assert url in notice, url
    for licence in ("CC BY-SA 4.0", "MIT", "GPL-3.0", "Apache-2.0"):
        assert licence in notice, licence


def test_doctor_runs_offline_without_a_pedal():
    result = run("--json", "doctor")
    document = json.loads(result.stdout)
    assert document["passed"] == document["total"]
    assert document["transport"] in {"available", "unavailable"}
    assert "device_ready" in document
    assert result.returncode == 0
    assert document["ok"] is True


def test_doctor_require_device_uses_exit_3_when_absent():
    result = run("--json", "doctor", "--require-device")
    if result.returncode == 0:
        pytest.skip("pedal is actually connected")
    document = json.loads(result.stdout)
    assert result.returncode == cli.EXIT_NO_DEVICE
    assert document["device_ready"] is False
    assert document["ok"] is False


def test_backup_extract_all_writes_every_slot(tmp_path):
    from test_backups import bundle

    source = tmp_path / "backup.json"
    destination = tmp_path / "bank"
    backups.write_atomic(source, bundle())
    result = run("backup", "extract-all", str(source), str(destination))
    assert result.returncode == 0, result.stdout + result.stderr
    files = sorted(destination.glob("P*.bin"))
    assert len(files) == 80
    assert (destination / "P01.bin").read_bytes() == bytes([0]) * 92
    assert (destination / "P80.bin").read_bytes() == bytes([79]) * 92
    again = run("backup", "extract-all", str(source), str(destination))
    assert again.returncode == cli.EXIT_FAIL
    assert b"exists" in again.stderr.encode() or "exists" in again.stderr


def test_selftest_passes():
    result = run("selftest")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "FAIL" not in result.stdout


def test_write_paths_reports_physically_confirmed_paths():
    result = run("--json", "write-paths")
    assert result.returncode == 0
    doc = json.loads(result.stdout)
    assert doc["any_enabled"] is True
    assert [p["key"] for p in doc["write_paths"] if p["hardware_confirmed"]] == [
        "load-preset",
        "set-knob",
        "set-toggle",
        "set-model",
        "set-routing",
        "restore",
        "stage-cab",
        "save-cab",
        "stage-amp",
        "save-amp",
    ]


def test_cli_exposes_verified_preset_workflow():
    parser = cli.build_parser()
    text = parser.format_help()
    for command in ("preset", "backup", "device"):
        assert command in text


def test_decode_from_hex_matches_the_recorded_p41():
    from fixtures import device_frames as fx

    result = run("decode", "--hex", fx.REPLY_FLASH_40.hex())
    assert result.returncode == 0, result.stderr
    assert "Gain" in result.stdout and "45" in result.stdout
    assert "Low Cut" in result.stdout


def test_decode_rejects_a_corrupt_reply_frame(tmp_path):
    from fixtures import device_frames as fx

    raw = bytearray(fx.REPLY_FLASH_40)
    raw[20] ^= 1
    path = tmp_path / "corrupt-frame.bin"
    path.write_bytes(raw)

    result = run("decode", str(path))

    assert result.returncode == cli.EXIT_FAIL
    assert "malformed" in result.stderr


def test_decode_requires_exactly_one_input_source(tmp_path):
    missing = run("decode")
    assert missing.returncode == cli.EXIT_FAIL
    assert "FILE or --hex" in missing.stderr

    image = tmp_path / "preset.bin"
    image.write_bytes(bytes(92))
    duplicate = run("decode", str(image), "--hex", bytes(92).hex())
    assert duplicate.returncode == cli.EXIT_FAIL
    assert "not both" in duplicate.stderr


def test_preset_export_reports_invalid_routing_without_a_traceback(tmp_path):
    from fixtures import device_frames as fx

    image = bytearray(fx.REPLY_FLASH_40[14:-1])
    image[2:8] = bytes((99, 1, 2, 3, 4, 5))
    source = tmp_path / "invalid.bin"
    destination = tmp_path / "invalid.json"
    source.write_bytes(image)

    result = run("--json", "preset", "export", str(source), str(destination))

    assert result.returncode == cli.EXIT_FAIL
    assert result.stderr == ""
    assert "Traceback" not in result.stdout
    assert "routing bytes" in json.loads(result.stdout)["error"]
    assert not destination.exists()


def test_json_errors_remain_one_machine_readable_document():
    result = run("--json", "decode")

    assert result.returncode == cli.EXIT_FAIL
    assert result.stderr == ""
    document = json.loads(result.stdout)
    assert document == {
        "error": "pass a preset image FILE or --hex DATA",
        "ok": False,
        "exit_code": cli.EXIT_FAIL,
    }


def test_device_error_distinguishes_connection_from_verification(capsys):
    verification = cli.Out(as_json=True)
    verification_code = cli._device_error(
        verification, RuntimeError("read-back mismatch")
    )
    verification.flush(verification_code)
    verification_doc = json.loads(capsys.readouterr().out)
    assert verification_code == cli.EXIT_FAIL
    assert verification_doc["error"] == "read-back mismatch"
    assert "hint" not in verification_doc

    connection = cli.Out(as_json=True)
    connection_code = cli._device_error(
        connection, transport.TransportUnavailable("no endpoint")
    )
    connection.flush(connection_code)
    connection_doc = json.loads(capsys.readouterr().out)
    assert connection_code == cli.EXIT_NO_DEVICE
    assert "connected over USB" in connection_doc["hint"]

    for error in (
        transport.AckTimeout("write state may have changed"),
        transport.ReplyTimeout("read timed out"),
    ):
        timeout = cli.Out(as_json=True)
        timeout_code = cli._device_error(timeout, error)
        timeout.flush(timeout_code)
        timeout_doc = json.loads(capsys.readouterr().out)
        assert timeout_code == cli.EXIT_FAIL
        assert "hint" not in timeout_doc


@pytest.mark.parametrize(
    ("source_count", "destination_count", "expected"),
    [
        (1, 1, cli.EXIT_OK),
        (0, 0, cli.EXIT_NO_DEVICE),
        (1, 0, cli.EXIT_NO_DEVICE),
        (0, 1, cli.EXIT_NO_DEVICE),
        (2, 1, cli.EXIT_NO_DEVICE),
        (1, 2, cli.EXIT_NO_DEVICE),
    ],
)
def test_endpoints_requires_exactly_one_matching_pair(
    monkeypatch, capsys, source_count, destination_count, expected
):
    def endpoints(count, start):
        return [
            transport.Endpoint(
                index=index,
                ref=start + index,
                name="USB Composite Device",
                display=None,
                manufacturer=transport.MANUFACTURER,
            )
            for index in range(count)
        ]

    monkeypatch.setattr(
        transport,
        "list_endpoints",
        lambda: (endpoints(source_count, 100), endpoints(destination_count, 200)),
    )
    out = cli.Out(as_json=True)

    result = cli.cmd_device_endpoints(argparse.Namespace(), out)
    out.flush(result)
    document = json.loads(capsys.readouterr().out)

    assert result == expected
    assert document["ready"] is (expected == cli.EXIT_OK)


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
    result = run(
        "--library-root", str(root), "library", "install", str(source), "--yes"
    )
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


@pytest.mark.parametrize(
    "docstring_claim",
    [
        "blackboxctl rename --in-place",
        "--repair-magic",
        "--library-root",
        "--force",
        "--yes",
    ],
)
def test_every_flag_the_docstrings_advertise_actually_exists(docstring_claim):
    """The modules' docstrings used to promise CLI surface that did not exist."""
    flag = docstring_claim.split()[-1]
    help_text = cli.build_parser().format_help()
    subcommands = [
        "rename",
        "inspect",
        "decode",
        "library",
        "device",
        "selftest",
        "doctor",
        "write-paths",
        "backup",
    ]
    combined = help_text + "".join(
        subprocess.run(
            [sys.executable, "-m", "blackboxctl", c, "--help"],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        for c in subcommands
    )
    combined += "".join(
        subprocess.run(
            [sys.executable, "-m", "blackboxctl", "library", c, "--help"],
            cwd=PACKAGE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        for c in ("install", "restart-editor", "list", "diff")
    )
    assert flag in combined, f"{flag} is advertised but not implemented"
