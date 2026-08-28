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

import ctypes
from dataclasses import dataclass

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


class _StubMIDI:
    """The subset of the CoreMIDI C API that ``open()`` touches."""

    def __init__(self, calls: Calls) -> None:
        self._calls = calls
        self._next_ref = 100

    def _ref(self) -> int:
        self._next_ref += 1
        return self._next_ref

    def MIDIClientCreate(self, name, notify, refcon, out):  # noqa: N802
        self._calls.client += 1
        out._obj.value = self._ref()
        return 0

    def MIDIInputPortCreate(self, client, name, proc, refcon, out):  # noqa: N802
        self._calls.in_port += 1
        out._obj.value = self._ref()
        return 0

    def MIDIOutputPortCreate(self, client, name, out):  # noqa: N802
        self._calls.out_port += 1
        out._obj.value = self._ref()
        return 0

    def MIDIPortConnectSource(self, port, source, refcon):  # noqa: N802
        self._calls.connect += 1
        return 0

    def MIDIPortDispose(self, port):  # noqa: N802
        self._calls.port_dispose += 1
        return 0

    def MIDIClientDispose(self, client):  # noqa: N802
        self._calls.client_dispose += 1
        return 0


class _StubCF:
    """CoreFoundation calls made during open(); string handling only."""

    def CFStringCreateWithCString(self, alloc, text, encoding):  # noqa: N802
        return 1

    def CFRelease(self, obj):  # noqa: N802
        return None


@pytest.fixture()
def stubbed(monkeypatch: pytest.MonkeyPatch) -> tuple[transport.BlackBox, Calls]:
    """A BlackBox whose CoreMIDI bindings are counting stubs."""
    calls = Calls()
    fw = transport._Frameworks(midi=_StubMIDI(calls), cf=_StubCF())
    monkeypatch.setattr(transport, "_load_frameworks", lambda: fw)

    endpoint = transport.Endpoint(
        ref=7, index=0, name="USB Composite Device",
        display="USB Composite Device", manufacturer="Jieli Technology")
    monkeypatch.setattr(transport, "list_endpoints",
                        lambda: ([endpoint], [endpoint]))

    device = transport.BlackBox()
    return device, calls


def test_open_is_idempotent(stubbed) -> None:
    """A second open() must not create a second client or port."""
    device, calls = stubbed
    device.open()
    assert (calls.client, calls.in_port, calls.out_port, calls.connect) == (1, 1, 1, 1)

    device.open()
    device.open()
    assert (calls.client, calls.in_port, calls.out_port, calls.connect) == (1, 1, 1, 1), (
        "open() created CoreMIDI objects on a second call; the first input port "
        "leaks while still connected to the source")


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
        "while CoreMIDI still holds its address")


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
