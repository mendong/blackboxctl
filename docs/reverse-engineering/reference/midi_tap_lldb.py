"""LLDB breakpoint callback that records M-EFCS CoreMIDI output packets.

Unsupported research helper. Not part of blackboxctl. Attach it only to an
M-EFCS build you already have a licence to run, and only to record sends.

Usage (attach only while reverse-engineering the installed app):

    command script import /absolute/path/to/midi_tap_lldb.py
    breakpoint set -n MIDISend
    breakpoint command add -F midi_tap_lldb.on_send 1
    continue

The callback returns False so the app continues immediately. It does not alter
the app or packet data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import lldb


LOG = Path("/tmp/m-efcs-midi-out.log")


def on_send(
    frame: lldb.SBFrame, _bp_loc: lldb.SBBreakpointLocation, _internal_dict: dict
) -> bool:
    process = frame.GetThread().GetProcess()
    is_arm = frame.GetThread().GetProcess().GetTarget().GetTriple().startswith("arm64")
    register = "x2" if is_arm else "rdx"
    address = frame.FindRegister(register).GetValueAsUnsigned()
    error = lldb.SBError()
    count_data = process.ReadMemory(address, 4, error)
    if not error.Success() or len(count_data) != 4:
        with LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"READ_ERROR address={address:#x} {error}\n")
        return False
    count = int.from_bytes(count_data, "little")
    offset = 4
    lines = []
    for index in range(min(count, 256)):
        error = lldb.SBError()
        header = process.ReadMemory(address + offset, 10, error)
        if not error.Success() or len(header) != 10:
            lines.append(f"READ_ERROR packet={index + 1} header {error}")
            break
        length = int.from_bytes(header[8:10], "little")
        error = lldb.SBError()
        payload = process.ReadMemory(address + offset + 10, length, error)
        if not error.Success() or len(payload) != length:
            lines.append(f"READ_ERROR packet={index + 1} payload {error}")
            break
        lines.append(
            f"{datetime.now(timezone.utc).isoformat()} packet={index + 1}/{count} "
            f"len={length} hex={payload.hex(' ').upper()}"
        )
        offset += 10 + length
        if is_arm:
            offset = (offset + 3) & ~3
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return False
