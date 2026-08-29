"""Failure reconciliation for state-changing CLI commands. GPL-3.0."""

from __future__ import annotations

import json
import os
import signal
import stat
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from blackboxctl import cli, device_library, protocol, storage, transport


class FakePresetDevice:
    def __init__(self, original: bytes) -> None:
        self.stored = original
        self.raise_after_first_write = True

    def read_memory(self, address, _size, *args, **kwargs):
        if address == protocol.ADDR_CURRENT_PRESET:
            return SimpleNamespace(payload=bytes((79, 0, 0, 0)))
        return SimpleNamespace(payload=self.stored)

    def write_and_wait_ack(self, raw, *args, **kwargs):
        self.stored = protocol.parse_frame(raw).payload
        if self.raise_after_first_write:
            self.raise_after_first_write = False
            raise TimeoutError("simulated lost ACK")


def _install_fake_device(monkeypatch, device):
    @contextmanager
    def open_device():
        yield device

    monkeypatch.setattr(transport, "open_device", open_device)


class FakeLoadDevice:
    def __init__(self, expected: bytes, failure: BaseException) -> None:
        self.expected = expected
        self.failure = failure
        self.active = 0
        self.live = bytes(protocol.PRESET_SIZE)

    def read_memory(self, address, _size, *args, **kwargs):
        if address == protocol.ADDR_CURRENT_PRESET:
            return SimpleNamespace(payload=bytes((self.active, 0, 0, 0)))
        if address == protocol.ADDR_LIVE_RAM:
            return SimpleNamespace(payload=self.live)
        return SimpleNamespace(payload=self.expected)

    def write_and_wait_ack(self, raw, *args, **kwargs):
        frame = protocol.parse_frame(raw)
        self.active = frame.payload[0]
        self.live = self.expected
        raise self.failure


def test_load_reconciles_a_lost_ack_from_active_and_ram(monkeypatch):
    expected = bytes((7,)) * protocol.PRESET_SIZE
    device = FakeLoadDevice(expected, transport.AckTimeout("lost load ACK"))
    _install_fake_device(monkeypatch, device)

    result = cli.cmd_device_load(SimpleNamespace(slot=2, yes=True), cli.Out(False))

    assert result == cli.EXIT_OK
    assert device.active == 1
    assert device.live == expected


def test_load_reports_verified_state_before_delivering_ctrl_c(monkeypatch, capsys):
    expected = bytes((7,)) * protocol.PRESET_SIZE
    device = FakeLoadDevice(expected, KeyboardInterrupt())
    _install_fake_device(monkeypatch, device)

    with pytest.raises(KeyboardInterrupt):
        cli.cmd_device_load(SimpleNamespace(slot=2, yes=True), cli.Out(False))

    assert "loaded and exactly verified" in capsys.readouterr().err


def test_save_reconciles_lost_ack_as_success_when_flash_matches(tmp_path, monkeypatch):
    original = bytes(protocol.PRESET_SIZE)
    target = bytes((1,)) * protocol.PRESET_SIZE
    image = tmp_path / "target.bin"
    image.write_bytes(target)
    device = FakePresetDevice(original)
    _install_fake_device(monkeypatch, device)
    args = SimpleNamespace(
        slot=1,
        image=str(image),
        yes=True,
        rollback_output=str(tmp_path / "rollback.bin"),
        force=False,
    )
    assert cli.cmd_device_save(args, cli.Out(False)) == cli.EXIT_OK
    assert device.stored == target
    assert (tmp_path / "rollback.bin").read_bytes() == original


def test_save_restores_original_when_target_readback_is_uncertain(
    tmp_path, monkeypatch
):
    original = bytes(protocol.PRESET_SIZE)
    target = bytes((1,)) * protocol.PRESET_SIZE
    image = tmp_path / "target.bin"
    image.write_bytes(target)

    class UncertainReadDevice(FakePresetDevice):
        def __init__(self):
            super().__init__(original)
            self.raise_after_first_write = False
            self.flash_reads = 0

        def read_memory(self, address, size, *args, **kwargs):
            if address == protocol.ADDR_CURRENT_PRESET:
                return super().read_memory(address, size, *args, **kwargs)
            self.flash_reads += 1
            if self.flash_reads == 2:
                raise TimeoutError("simulated uncertain target read-back")
            return SimpleNamespace(payload=self.stored)

    device = UncertainReadDevice()
    _install_fake_device(monkeypatch, device)
    args = SimpleNamespace(
        slot=1,
        image=str(image),
        yes=True,
        rollback_output=str(tmp_path / "rollback.bin"),
        force=False,
    )
    assert cli.cmd_device_save(args, cli.Out(False)) == cli.EXIT_FAIL
    assert device.stored == original


def test_save_reconciles_and_restores_before_honoring_ctrl_c(tmp_path, monkeypatch):
    original = bytes(protocol.PRESET_SIZE)
    target = bytes((1,)) * protocol.PRESET_SIZE
    image = tmp_path / "target.bin"
    image.write_bytes(target)

    class InterruptedDevice(FakePresetDevice):
        def write_and_wait_ack(self, raw, *args, **kwargs):
            self.stored = protocol.parse_frame(raw).payload
            if self.raise_after_first_write:
                self.raise_after_first_write = False
                raise KeyboardInterrupt

    device = InterruptedDevice(original)
    _install_fake_device(monkeypatch, device)
    args = SimpleNamespace(
        slot=1,
        image=str(image),
        yes=True,
        rollback_output=str(tmp_path / "rollback.bin"),
        force=False,
    )
    with pytest.raises(KeyboardInterrupt):
        cli.cmd_device_save(args, cli.Out(False))
    assert device.stored == original


def test_audition_restores_baseline_after_a_mid_sequence_failure(tmp_path, monkeypatch):
    before = bytes(protocol.PRESET_SIZE)
    target = bytes((1,)) * protocol.PRESET_SIZE
    image = tmp_path / "target.bin"
    image.write_bytes(target)
    device = FakePresetDevice(before)
    _install_fake_device(monkeypatch, device)
    calls = 0

    def partial_then_restore(
        _device,
        _before,
        wanted,
        _label,
        *,
        force=False,
        continue_on_error=False,
        errors=None,
    ):
        nonlocal calls
        calls += 1
        if calls == 1:
            device.stored = target[:20] + before[20:]
            raise TimeoutError("simulated mid-sequence timeout")
        device.stored = wanted
        return ["rollback"]

    monkeypatch.setattr(cli, "_write_live_image", partial_then_restore)
    args = SimpleNamespace(image=str(image), yes=True)
    assert cli.cmd_device_audition(args, cli.Out(False)) == cli.EXIT_FAIL
    assert calls == 2
    assert device.stored == before


def test_library_commit_lost_ack_can_be_reconciled_by_persistent_state():
    consent = protocol.WriteConsent(
        path_key="save-cab", confirmed_by_user=True, allow_flash=True
    )
    frames = protocol.cmd_save_cab_header(
        0, bytes(protocol.CAB_HEADER_SIZE), consent=consent
    )

    class LostFinalAck:
        calls = 0

        def write_and_wait_ack(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == len(frames):
                raise TimeoutError("lost final ACK")

    device = LostFinalAck()
    exact_acks = cli._send_probed_sequence(
        device,
        frames,
        "save-cab",
        "test",
        allow_flash=True,
        reconcile_final=lambda: True,
    )
    assert exact_acks == len(frames) - 1


def test_library_commit_same_name_lost_ack_is_reported_uncertain():
    consent = protocol.WriteConsent(
        path_key="save-cab", confirmed_by_user=True, allow_flash=True
    )
    frames = protocol.cmd_save_cab_header(
        0, bytes(protocol.CAB_HEADER_SIZE), consent=consent
    )

    class LostFinalAck:
        calls = 0

        def write_and_wait_ack(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == len(frames):
                raise TimeoutError("lost final ACK")

    with pytest.raises(cli.CommitUncertain, match="uncertain"):
        cli._send_probed_sequence(
            LostFinalAck(), frames, "save-cab", "test", allow_flash=True
        )


def test_library_commit_ctrl_c_reconciles_before_it_is_reraised():
    consent = protocol.WriteConsent(
        path_key="save-cab", confirmed_by_user=True, allow_flash=True
    )
    frames = protocol.cmd_save_cab_header(
        0, bytes(protocol.CAB_HEADER_SIZE), consent=consent
    )

    class InterruptedFinalAck:
        calls = 0

        def write_and_wait_ack(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == len(frames):
                raise KeyboardInterrupt

    with pytest.raises(cli.CommitInterrupted) as captured:
        cli._send_probed_sequence(
            InterruptedFinalAck(),
            frames,
            "save-cab",
            "test",
            allow_flash=True,
            reconcile_final=lambda: True,
        )
    assert captured.value.committed is True
    assert captured.value.exact_acks == len(frames) - 1


def test_rollback_image_is_atomic_private_and_exact(tmp_path):
    path = tmp_path / "P80.bin"
    image = bytes(range(protocol.PRESET_SIZE))
    cli._write_rollback_image(path, image, force=False)
    assert path.read_bytes() == image
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_rollback_image_fsyncs_the_containing_directory(tmp_path, monkeypatch):
    opened_directories: list[object] = []
    real_open = storage.os.open

    def recording_open(path, flags, *args, **kwargs):
        opened_directories.append(path)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(storage.os, "open", recording_open)
    cli._write_rollback_image(
        tmp_path / "P80.bin", bytes(protocol.PRESET_SIZE), force=False
    )
    assert tmp_path in opened_directories


def test_rollback_image_fsyncs_parents_of_new_directories(tmp_path, monkeypatch):
    opened_directories: list[object] = []
    real_open = storage.os.open

    def recording_open(path, flags, *args, **kwargs):
        opened_directories.append(path)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(storage.os, "open", recording_open)
    nested = tmp_path / "new" / "nested"
    cli._write_rollback_image(
        nested / "P80.bin", bytes(protocol.PRESET_SIZE), force=False
    )
    assert tmp_path in opened_directories
    assert tmp_path / "new" in opened_directories
    assert nested in opened_directories


def test_rollback_image_does_not_clobber_a_concurrent_destination(
    tmp_path, monkeypatch
):
    path = tmp_path / "P80.bin"
    real_link = storage.os.link

    def racing_link(source, destination):
        destination.write_bytes(b"other invocation")
        return real_link(source, destination)

    monkeypatch.setattr(storage.os, "link", racing_link)
    with pytest.raises(RuntimeError, match="concurrently"):
        cli._write_rollback_image(path, bytes(protocol.PRESET_SIZE), force=False)
    assert path.read_bytes() == b"other invocation"


def test_keyboard_interrupt_is_deferred_until_evidence_update_finishes():
    completed: list[bool] = []
    with pytest.raises(KeyboardInterrupt), cli._defer_keyboard_interrupt():
        os.kill(os.getpid(), signal.SIGINT)
        completed.append(True)
    assert completed == [True]


def test_resilient_live_restore_continues_after_a_lost_ack():
    before = bytes((7,)) * protocol.PRESET_SIZE
    target_data = bytearray(protocol.PRESET_SIZE)
    target_data[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6] = bytes(range(6))
    target = bytes(target_data)

    class LiveDevice:
        def __init__(self):
            self.current = before
            self.calls = 0

        def write_and_wait_ack(self, raw, *_args, **_kwargs):
            frame = protocol.parse_frame(raw)
            offset = frame.address - protocol.ADDR_LIVE_RAM
            changed = bytearray(self.current)
            changed[offset : offset + len(frame.payload)] = frame.payload
            self.current = bytes(changed)
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("lost rollback ACK")

    device = LiveDevice()
    errors: list[BaseException] = []
    cli._write_live_image(
        device,
        before,
        target,
        "test rollback",
        force=True,
        continue_on_error=True,
        errors=errors,
    )
    assert errors and isinstance(errors[0], TimeoutError)
    assert device.current == target


def test_library_apply_journals_post_ack_verification_failure(tmp_path, monkeypatch):
    entry = device_library.PreparedEntry(
        kind="cab",
        slot=1,
        name="TARGET",
        source=tmp_path / "source.wav",
        record=bytes(protocol.CAB_RECORD_SIZE),
        level=50,
    )
    monkeypatch.setattr(device_library, "load", lambda *_args, **_kwargs: [entry])
    monkeypatch.setattr(
        cli,
        "_wait_for_library_name",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            TimeoutError("name read timed out")
        ),
    )

    class LibraryDevice:
        def read_memory(self, address, *_args, **_kwargs):
            name = b"OLD".ljust(protocol.NAME_STRIDE, b"\0")
            return SimpleNamespace(payload=name * protocol.NAME_COUNT)

        def write_and_wait_ack(self, *_args, **_kwargs):
            return None

    _install_fake_device(monkeypatch, LibraryDevice())
    journal = tmp_path / "journal.json"
    args = SimpleNamespace(
        manifest=str(tmp_path / "manifest.json"),
        library_root=str(tmp_path),
        dsp_helper=None,
        yes=True,
        journal=str(journal),
        rewrite=False,
    )
    assert cli.cmd_device_library_apply(args, cli.Out(False)) == cli.EXIT_FAIL
    saved = __import__("json").loads(journal.read_text())
    assert saved["results"][-1]["status"] == "commit-uncertain"
    assert saved["results"][-1]["kind"] == "cab"


def test_library_apply_defers_ctrl_c_until_verified_result_is_durable(
    tmp_path, monkeypatch
):
    entry = device_library.PreparedEntry(
        kind="cab",
        slot=1,
        name="TARGET",
        source=tmp_path / "source.wav",
        record=bytes(protocol.CAB_RECORD_SIZE),
        level=50,
    )
    monkeypatch.setattr(device_library, "load", lambda *_args, **_kwargs: [entry])

    class InterruptingNames(list):
        def __getitem__(self, index):
            os.kill(os.getpid(), signal.SIGINT)
            return super().__getitem__(index)

    monkeypatch.setattr(
        cli,
        "_wait_for_library_name",
        lambda *_args, **_kwargs: InterruptingNames(["TARGET"] * protocol.NAME_COUNT),
    )

    class LibraryDevice:
        def read_memory(self, _address, *_args, **_kwargs):
            name = b"OLD".ljust(protocol.NAME_STRIDE, b"\0")
            return SimpleNamespace(payload=name * protocol.NAME_COUNT)

        def write_and_wait_ack(self, *_args, **_kwargs):
            return None

    _install_fake_device(monkeypatch, LibraryDevice())
    journal = tmp_path / "journal.json"
    args = SimpleNamespace(
        manifest=str(tmp_path / "manifest.json"),
        library_root=str(tmp_path),
        dsp_helper=None,
        yes=True,
        journal=str(journal),
        rewrite=False,
    )

    with pytest.raises(KeyboardInterrupt):
        cli.cmd_device_library_apply(args, cli.Out(False))

    saved = json.loads(journal.read_text())
    assert saved["results"][-1]["status"] == "saved-name-verified"
    assert saved["results"][-1]["record_sha256"] == entry.sha256


@pytest.mark.parametrize("kind", ["cab", "amp"])
def test_standalone_library_save_reports_plain_post_commit_ctrl_c(
    kind, monkeypatch, capsys
):
    record_size = (
        protocol.CAB_RECORD_SIZE if kind == "cab" else protocol.AMP_RECORD_SIZE
    )
    monkeypatch.setattr(
        cli, f"_{kind}_record_from_args", lambda _args: bytes(record_size)
    )
    monkeypatch.setattr(
        cli,
        "_wait_for_library_name",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    class LibraryDevice:
        def read_memory(self, _address, *_args, **_kwargs):
            name = b"OLD".ljust(protocol.NAME_STRIDE, b"\0")
            return SimpleNamespace(payload=name * protocol.NAME_COUNT)

        def write_and_wait_ack(self, *_args, **_kwargs):
            return None

    _install_fake_device(monkeypatch, LibraryDevice())
    args = SimpleNamespace(
        slot=1, file="source", name="TARGET", yes=True, level=50, dsp_helper=None
    )
    command = cli.cmd_device_cab_save if kind == "cab" else cli.cmd_device_amp_save

    with pytest.raises(KeyboardInterrupt):
        command(args, cli.Out(False))

    error = capsys.readouterr().err
    assert f"{kind.upper()} slot 1 received the final commit ACK" in error
    assert "persistent name is unverified" in error
    assert "before retrying" in error


@pytest.mark.parametrize("kind", ["cab", "amp"])
def test_library_audition_does_not_write_when_identity_handshake_fails(
    kind, monkeypatch
):
    record_size = (
        protocol.CAB_RECORD_SIZE if kind == "cab" else protocol.AMP_RECORD_SIZE
    )
    monkeypatch.setattr(
        cli, f"_{kind}_record_from_args", lambda _args: bytes(record_size)
    )

    class HandshakeFailureDevice:
        writes = 0

        def read_memory(self, *_args, **_kwargs):
            raise TimeoutError("identity handshake failed")

        def write_and_wait_ack(self, *_args, **_kwargs):
            self.writes += 1

    device = HandshakeFailureDevice()
    _install_fake_device(monkeypatch, device)
    args = SimpleNamespace(
        file="source", name="TARGET", yes=True, level=50, dsp_helper=None
    )
    command = (
        cli.cmd_device_cab_audition if kind == "cab" else cli.cmd_device_amp_audition
    )

    assert command(args, cli.Out(False)) == cli.EXIT_FAIL
    assert device.writes == 0


def test_standalone_gain_probe_restores_after_lost_candidate_ack(monkeypatch):
    baseline = bytearray(protocol.PRESET_SIZE)
    baseline[0x20:0x22] = (23).to_bytes(2, "little")

    class LiveDevice:
        def __init__(self):
            self.current = bytes(baseline)
            self.writes = 0

        def read_memory(self, *_args, **_kwargs):
            return SimpleNamespace(payload=self.current)

        def write_and_wait_ack(self, raw, *_args, **_kwargs):
            frame = protocol.parse_frame(raw)
            offset = frame.address - protocol.ADDR_LIVE_RAM
            data = bytearray(self.current)
            data[offset : offset + len(frame.payload)] = frame.payload
            self.current = bytes(data)
            self.writes += 1
            if self.writes == 1:
                raise TimeoutError("lost candidate ACK")

    device = LiveDevice()
    _install_fake_device(monkeypatch, device)
    assert (
        cli.cmd_device_probe_amp_gain(SimpleNamespace(yes=True), cli.Out(False))
        == cli.EXIT_FAIL
    )
    assert device.current == bytes(baseline)


def test_standalone_gain_probe_refuses_unrestorable_baseline_before_write(monkeypatch):
    baseline = bytearray(protocol.PRESET_SIZE)
    baseline[0x20:0x22] = (101).to_bytes(2, "little")

    class LiveDevice:
        writes = 0

        def read_memory(self, *_args, **_kwargs):
            return SimpleNamespace(payload=bytes(baseline))

        def write_and_wait_ack(self, *_args, **_kwargs):
            self.writes += 1

    device = LiveDevice()
    _install_fake_device(monkeypatch, device)

    result = cli.cmd_device_probe_amp_gain(SimpleNamespace(yes=True), cli.Out(False))

    assert result == cli.EXIT_FAIL
    assert device.writes == 0


@pytest.mark.parametrize(
    ("offset", "value"),
    [
        (protocol.BLOCKS_BY_KEY["amp"].knob_addr(1), (101).to_bytes(2, "little")),
        (protocol.BLOCKS_BY_KEY["mod"].toggle_addr, b"\x02"),
        (
            protocol.BLOCKS_BY_KEY["mod"].model_addr,
            bytes((len(protocol.BLOCKS_BY_KEY["mod"].models),)),
        ),
        (protocol.BLOCKS_BY_KEY["amp"].model_addr, bytes((protocol.NAME_COUNT,))),
        (protocol.ADDR_ROUTING, b"\x00\x00\x02\x03\x04\x05"),
    ],
)
def test_full_live_probe_preflights_rollback_before_first_write(
    offset, value, monkeypatch
):
    baseline = bytearray(protocol.PRESET_SIZE)
    baseline[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6] = bytes(range(6))
    baseline[offset : offset + len(value)] = value

    class LiveDevice:
        writes = 0

        def read_memory(self, *_args, **_kwargs):
            return SimpleNamespace(payload=bytes(baseline))

        def write_and_wait_ack(self, *_args, **_kwargs):
            self.writes += 1

    device = LiveDevice()
    _install_fake_device(monkeypatch, device)

    result = cli.cmd_device_probe_live(SimpleNamespace(yes=True), cli.Out(False))

    assert result == cli.EXIT_FAIL
    assert device.writes == 0


def test_full_live_probe_restores_ram_if_load_preset_is_not_idempotent(monkeypatch):
    """A surprising load must not leave the live image dirty."""
    baseline = bytearray(protocol.PRESET_SIZE)
    baseline[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6] = bytes(range(6))
    baseline = bytes(baseline)

    class LiveDevice:
        def __init__(self) -> None:
            self.current = baseline
            self.load_writes = 0

        def read_memory(self, address, _size, *args, **kwargs):
            if address == protocol.ADDR_CURRENT_PRESET:
                return SimpleNamespace(payload=bytes(4))
            return SimpleNamespace(payload=self.current)

        def write_and_wait_ack(self, raw, *_args, **_kwargs):
            frame = protocol.parse_frame(raw)
            if (
                protocol.ADDR_LOAD_PRESET
                <= frame.address
                < protocol.ADDR_LOAD_PRESET + protocol.PRESET_COUNT
            ):
                self.load_writes += 1
                dirty = bytearray(self.current)
                dirty[0:2] = (50).to_bytes(2, "little")
                self.current = bytes(dirty)
                return
            offset = frame.address - protocol.ADDR_LIVE_RAM
            data = bytearray(self.current)
            data[offset : offset + len(frame.payload)] = frame.payload
            self.current = bytes(data)

    device = LiveDevice()
    _install_fake_device(monkeypatch, device)

    result = cli.cmd_device_probe_live(SimpleNamespace(yes=True), cli.Out(False))

    assert result == cli.EXIT_FAIL
    assert device.load_writes == 1
    assert device.current == baseline


def test_production_sequence_does_not_attach_a_write_probe():
    """Confirmed AMP/CAB paths must not fall back to a frame-bound probe."""
    captured: dict = {}

    class Device:
        def write_and_wait_ack(self, _raw, **kwargs):
            captured.update(kwargs)

    consent = protocol.WriteConsent(path_key="stage-cab", confirmed_by_user=True)
    frames = protocol.cmd_stage_cab(bytes(protocol.CAB_RECORD_SIZE), consent=consent)
    assert cli._send_probed_sequence(Device(), frames[:1], "stage-cab", "test") == 1
    assert captured.get("probe") is None
    assert captured["consent"].accept_unverified is not True
    assert captured["consent"].path_key == "stage-cab"
