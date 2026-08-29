"""``BlackBox.open()`` must be idempotent. GPL-3.0.

This is a regression test for a crash found on real hardware on 2026-08-28.

``transport.open_device()`` returns a BlackBox on which ``open()`` has already
run. Every CLI device command then uses it as a context manager, so
``__enter__`` called ``open()`` a second time. The second call replaced
``self._read_proc`` with a fresh ``ctypes.CFUNCTYPE`` trampoline and let the
first one be garbage collected, while the first input port — leaked, never
disposed, still connected to the source — could still invoke it. CoreMIDI then
called freed code on its own thread and the process died with SIGBUS as soon as
the pedal replied. Every ``blackboxctl device …`` command exited 138.

No hardware is involved here: the CoreMIDI entry points are replaced with
counting stubs, so the test asserts the contract rather than the symptom.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from blackboxctl import transport


@dataclass
class Calls:
    """How many times each CoreMIDI object-creating entry point was invoked."""

    client: int = 0
    in_port: int = 0
    out_port: int = 0
    connect: int = 0
    port_dispose: int = 0
    client_dispose: int = 0
    cf_create: int = 0
    cf_release: int = 0


class _StubMIDI:
    """The subset of the CoreMIDI C API that ``open()`` touches."""

    def __init__(self, calls: Calls, fail_once_at: str | None = None) -> None:
        self._calls = calls
        self._next_ref = 100
        self._fail_once_at = fail_once_at

    def _ref(self) -> int:
        self._next_ref += 1
        return self._next_ref

    def _result(self, stage: str) -> int:
        if self._fail_once_at == stage:
            self._fail_once_at = None
            return -1
        return 0

    def MIDIClientCreate(self, name, notify, refcon, out):
        self._calls.client += 1
        out._obj.value = self._ref()
        return self._result("client")

    def MIDIInputPortCreate(self, client, name, proc, refcon, out):
        self._calls.in_port += 1
        out._obj.value = self._ref()
        return self._result("in_port")

    def MIDIOutputPortCreate(self, client, name, out):
        self._calls.out_port += 1
        out._obj.value = self._ref()
        return self._result("out_port")

    def MIDIPortConnectSource(self, port, source, refcon):
        self._calls.connect += 1
        return self._result("connect")

    def MIDIPortDispose(self, port):
        self._calls.port_dispose += 1
        return 0

    def MIDIClientDispose(self, client):
        self._calls.client_dispose += 1
        return 0


class _StubCF:
    """CoreFoundation calls made during open(); string handling only."""

    def __init__(self, calls: Calls) -> None:
        self._calls = calls

    def CFStringCreateWithCString(self, alloc, text, encoding):
        self._calls.cf_create += 1
        return self._calls.cf_create

    def CFRelease(self, obj):
        self._calls.cf_release += 1


def _stubbed_device(
    monkeypatch: pytest.MonkeyPatch,
    lock_path: Path,
    *,
    fail_once_at: str | None = None,
) -> tuple[transport.BlackBox, Calls]:
    calls = Calls()
    fw = transport._Frameworks(
        midi=_StubMIDI(calls, fail_once_at=fail_once_at),
        cf=_StubCF(calls),
    )
    monkeypatch.setattr(transport, "_load_frameworks", lambda: fw)

    endpoint = transport.Endpoint(
        ref=7,
        index=0,
        name="USB Composite Device",
        display="USB Composite Device",
        manufacturer="Jieli Technology",
    )
    monkeypatch.setattr(transport, "list_endpoints", lambda: ([endpoint], [endpoint]))
    monkeypatch.setattr(transport, "DEVICE_LOCK_PATH", lock_path)

    return transport.BlackBox(), calls


@pytest.fixture()
def stubbed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[tuple[transport.BlackBox, Calls]]:
    """A BlackBox whose CoreMIDI bindings are counting stubs."""
    device, calls = _stubbed_device(monkeypatch, tmp_path / "device.lock")
    try:
        yield device, calls
    finally:
        device.close()


def test_open_is_idempotent(stubbed) -> None:
    """A second open() must not create a second client or port."""
    device, calls = stubbed
    device.open()
    assert (calls.client, calls.in_port, calls.out_port, calls.connect) == (1, 1, 1, 1)
    assert (calls.cf_create, calls.cf_release) == (3, 3)

    device.open()
    device.open()
    assert (calls.client, calls.in_port, calls.out_port, calls.connect) == (
        1,
        1,
        1,
        1,
    ), (
        "open() created CoreMIDI objects on a second call; the first input port "
        "leaks while still connected to the source"
    )
    assert (calls.cf_create, calls.cf_release) == (3, 3)


def test_open_keeps_the_same_read_proc(stubbed) -> None:
    """The CFUNCTYPE trampoline must survive re-opening.

    Replacing it is what let CoreMIDI call freed code.
    """
    device, _ = stubbed
    device.open()
    first = device._read_proc
    assert isinstance(first, transport._MIDIReadProc)

    device.open()
    assert device._read_proc is first, (
        "open() replaced the read proc; the previous trampoline can be collected "
        "while CoreMIDI still holds its address"
    )


def test_open_device_result_survives_context_manager_entry(stubbed) -> None:
    """The exact shape the CLI uses: an opened instance used as a context manager."""
    device, calls = stubbed
    opened = device.open()
    proc = opened._read_proc

    with opened as inner:
        assert inner is opened
        assert inner._read_proc is proc
        assert (calls.client, calls.in_port) == (1, 1)


def test_reopen_after_close_creates_a_fresh_client(stubbed) -> None:
    """close() must clear the guard so the instance can be reused."""
    device, calls = stubbed
    device.open()
    device.close()
    assert not device._client

    device.open()
    assert calls.client == 2, "open() after close() must acquire a new client"


@pytest.mark.parametrize(
    ("stage", "message", "expected_port_disposals", "expected_cf_strings"),
    [
        ("client", "MIDIClientCreate", 0, 1),
        ("out_port", "MIDIOutputPortCreate", 1, 2),
        ("in_port", "MIDIInputPortCreate", 2, 3),
        ("connect", "MIDIPortConnectSource", 2, 3),
    ],
)
def test_partial_open_failure_cleans_up_and_can_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    stage: str,
    message: str,
    expected_port_disposals: int,
    expected_cf_strings: int,
) -> None:
    """Every partial acquisition is disposed before a real retry."""
    device, calls = _stubbed_device(
        monkeypatch, tmp_path / "device.lock", fail_once_at=stage
    )

    with pytest.raises(transport.TransportUnavailable, match=message):
        device.open()

    assert not device._client
    assert not device._in_port
    assert not device._out_port
    assert device.source is None
    assert device.destination is None
    assert calls.client_dispose == 1
    assert calls.port_dispose == expected_port_disposals
    assert calls.cf_create == expected_cf_strings
    assert calls.cf_release == expected_cf_strings

    reopened = device.open()
    assert reopened is device
    assert device._client and device._in_port and device._out_port
    assert calls.client == 2
    assert calls.out_port == (1 if stage == "client" else 2)
    assert calls.in_port == (1 if stage in ("client", "out_port") else 2)
    assert calls.connect == (2 if stage == "connect" else 1)
    assert calls.cf_create == expected_cf_strings + 3
    assert calls.cf_release == expected_cf_strings + 3
    device.close()


@pytest.mark.parametrize(
    ("source_count", "destination_count"), [(2, 1), (1, 2), (2, 2)]
)
def test_ambiguous_manufacturer_endpoints_are_refused_and_lock_is_released(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source_count: int,
    destination_count: int,
) -> None:
    lock_path = tmp_path / "device.lock"
    device, calls = _stubbed_device(monkeypatch, lock_path)
    endpoints = [
        transport.Endpoint(
            ref=7 + index,
            index=index,
            name=f"USB Composite Device {index}",
            display=f"USB Composite Device {index}",
            manufacturer=transport.MANUFACTURER,
        )
        for index in range(2)
    ]
    monkeypatch.setattr(
        transport,
        "list_endpoints",
        lambda: (endpoints[:source_count], endpoints[:destination_count]),
    )

    with pytest.raises(transport.TransportUnavailable, match="Ambiguous"):
        device.open()

    assert calls.client == 0
    assert device._device_lock_fd is None

    monkeypatch.setattr(
        transport, "list_endpoints", lambda: (endpoints[:1], endpoints[:1])
    )
    device.open()
    assert calls.client == 1
    device.close()


_LOCK_PROBE = """
import fcntl
import os
import sys

fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit(17)
raise SystemExit(0)
"""


def _probe_lock(path: Path) -> int:
    return subprocess.run(
        [sys.executable, "-c", _LOCK_PROBE, str(path)],
        check=False,
    ).returncode


def test_device_lock_is_private_held_for_context_and_reusable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lock_path = tmp_path / "private" / "device.lock"
    device, _ = _stubbed_device(monkeypatch, lock_path)

    device.open()
    assert stat.S_IMODE(lock_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600
    assert _probe_lock(lock_path) == 17

    device.close()
    assert _probe_lock(lock_path) == 0

    device.open()
    assert _probe_lock(lock_path) == 17
    device.close()


_LOCK_HOLDER = """
import fcntl
import os
import sys

fd = os.open(sys.argv[1], os.O_RDWR | os.O_CREAT, 0o600)
fcntl.flock(fd, fcntl.LOCK_EX)
os.ftruncate(fd, 0)
os.write(fd, f"pid={os.getpid()}\\n".encode())
print("ready", flush=True)
sys.stdin.buffer.read(1)
"""


def test_device_open_fails_fast_during_cross_process_contention(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lock_path = tmp_path / "device.lock"
    holder = subprocess.Popen(
        [sys.executable, "-c", _LOCK_HOLDER, str(lock_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline() == "ready\n"
        device, calls = _stubbed_device(monkeypatch, lock_path)

        with pytest.raises(
            transport.TransportUnavailable,
            match=r"Another blackboxctl process.*pid=",
        ):
            device.open()

        assert calls.client == 0
        assert device._device_lock_fd is None
    finally:
        if holder.poll() is None:
            assert holder.stdin is not None
            holder.stdin.write("\n")
            holder.stdin.flush()
            holder.wait(timeout=5)

    device.open()
    assert calls.client == 1
    device.close()


def test_device_lock_is_released_when_acquisition_is_interrupted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    lock_path = tmp_path / "device.lock"
    device, calls = _stubbed_device(monkeypatch, lock_path)
    real_fsync = transport.os.fsync

    def interrupt(_descriptor: int) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(transport.os, "fsync", interrupt)
    with pytest.raises(KeyboardInterrupt):
        device.open()

    assert device._device_lock_fd is None
    assert calls.client == 0
    assert _probe_lock(lock_path) == 0

    monkeypatch.setattr(transport.os, "fsync", real_fsync)
    device.open()
    assert calls.client == 1
    device.close()
