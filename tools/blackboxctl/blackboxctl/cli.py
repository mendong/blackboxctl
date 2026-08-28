"""Command line interface for blackboxctl.

Safety model, in one place
--------------------------
1. Device commands are READ ONLY. Every frame handed to CoreMIDI passes
   :func:`protocol.assert_read_only`, which allows only the ``00 59 23`` read
   header, an empty payload, a size <= 280, and an address inside one of the
   five regions that have actually been read from this pedal. There is no
   command here that transmits a write, and there is no flag that enables one.
2. Commands that change files on disk (``library install``,
   ``library restart-editor``, ``rename --in-place``) are DRY RUN by default and
   need ``--yes`` to act.
3. ``library install --force`` copies the incumbent file to a timestamped
   ``.bak`` sidecar before replacing it.

GPL-3.0. See ../LICENSE and ../NOTICE.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Sequence

from . import __version__, captures, library, protocol

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NO_DEVICE = 3


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


class Out:
    """Print either human text or one JSON document, never a mixture."""

    def __init__(self, as_json: bool) -> None:
        self.as_json = as_json
        self._doc: dict[str, Any] = {}

    def line(self, text: str = "") -> None:
        if not self.as_json:
            print(text)

    def data(self, **fields: Any) -> None:
        self._doc.update(fields)

    def flush(self) -> None:
        if self.as_json:
            print(json.dumps(self._doc, indent=2, default=_jsonable))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex(" ").upper()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return EXIT_FAIL


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------


def cmd_selftest(args: argparse.Namespace, out: Out) -> int:
    """Offline protocol self-test. Touches no hardware and no files."""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    # Codec round trip.
    import random
    rng = random.Random(20260828)
    ok = True
    for length in range(1, 300):
        blob = bytes(rng.randrange(256) for _ in range(length))
        if protocol.base128_decode(protocol.base128_encode(blob))[:length] != blob:
            ok = False
            break
    check("base128 round trip, 1..299 bytes", ok)

    # The four documented read literals.
    literals = {
        "ram dump": (protocol.cmd_ram_dump(),
                     "00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F"),
        "preset sync": (protocol.cmd_preset_sync(),
                        "00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7"),
        "cab names": (protocol.cmd_read_cab_names(),
                      "00 59 23 08 00 00 05 00 00 00 80 18 01 00 61"),
        "amp names": (protocol.cmd_read_amp_names(),
                      "00 59 23 08 00 00 05 00 00 00 90 18 01 00 51"),
        "flash P01": (protocol.cmd_read_flash_preset(0),
                      "00 59 23 08 00 00 04 00 00 00 00 5C 00 00 9F"),
        "flash P03": (protocol.cmd_read_flash_preset(2),
                      "00 59 23 08 00 00 04 B8 00 00 00 5C 00 00 E7"),
        "flash P41": (protocol.cmd_read_flash_preset(40),
                      "00 59 23 08 00 00 04 60 0E 00 00 5C 00 00 31"),
    }
    for name, (built, expected) in literals.items():
        check(f"read literal: {name}", protocol.hexs(built) == expected,
              protocol.hexs(built))

    # The gate accepts every read command and refuses the write header.
    for name, (built, _expected) in literals.items():
        try:
            protocol.assert_read_only(built)
            check(f"gate accepts: {name}", True)
        except protocol.UnsafePacket as exc:
            check(f"gate accepts: {name}", False, str(exc))

    refusals = {
        "write magic": bytes.fromhex("005922") + bytes(12),
        "oversized read": protocol.build_read(protocol.ADDR_PRESET_BASE, 0xFFFFFF),
        "load-preset trigger": protocol.build_read(protocol.ADDR_LOAD_PRESET, 1),
        "commit trigger": protocol.build_read(protocol.ADDR_COMMIT, 1),
        "unmapped address": protocol.build_read(0x12345678, 4),
    }
    for name, frame in refusals.items():
        try:
            protocol.assert_read_only(frame)
            check(f"gate refuses: {name}", False, "ACCEPTED - this is a bug")
        except protocol.UnsafePacket:
            check(f"gate refuses: {name}", True)

    # No write path is enabled.
    enabled = [k for k, p in protocol.WRITE_PATHS.items() if p.hardware_confirmed]
    check("no write path is hardware-confirmed", not enabled, str(enabled))

    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        out.line(f"  {'PASS' if ok else 'FAIL'}  {name}"
                 + (f"    {detail}" if detail and not ok else ""))
    out.line(f"\n{passed}/{len(checks)} checks passed")
    out.data(checks=[{"name": n, "ok": o, "detail": d} for n, o, d in checks],
             passed=passed, total=len(checks))
    return EXIT_OK if passed == len(checks) else EXIT_FAIL


# ---------------------------------------------------------------------------
# write-paths
# ---------------------------------------------------------------------------


def cmd_write_paths(args: argparse.Namespace, out: Out) -> int:
    """Show every state-changing command and why it is not enabled."""
    rows = []
    for path in protocol.WRITE_PATHS.values():
        rows.append({
            "key": path.key,
            "description": path.description,
            "hardware_confirmed": path.hardware_confirmed,
            "touches_flash": path.touches_flash,
            "evidence": path.evidence,
        })
        out.line(f"{path.key}")
        out.line(f"  what           {path.description}")
        out.line(f"  confirmed      {path.hardware_confirmed}")
        out.line(f"  touches flash  {path.touches_flash}")
        out.line(f"  evidence       {path.evidence}")
        out.line()
    out.line("No write path has hardware_confirmed=True, so transport refuses "
             "all of them.")
    out.line("There is no CLI command that transmits a write, and no flag that "
             "enables one.")
    out.data(write_paths=rows, any_enabled=False)
    return EXIT_OK


# ---------------------------------------------------------------------------
# inspect / rename / decode
# ---------------------------------------------------------------------------


def cmd_inspect(args: argparse.Namespace, out: Out) -> int:
    results = []
    worst = EXIT_OK
    for raw in args.files:
        path = Path(raw)
        if not path.is_file():
            out.line(f"{path}: no such file")
            results.append({"path": str(path), "errors": ["no such file"],
                            "ok": False})
            worst = EXIT_FAIL
            continue
        parsed = captures.inspect(path)
        results.append(parsed.to_dict())
        if not parsed.ok:
            worst = EXIT_FAIL
        out.line(f"{path.name}")
        if isinstance(parsed, captures.Capture):
            out.line(f"  kind      capture, {parsed.size} bytes"
                     f"{', header' if parsed.has_header else ', bare payload'}")
            if parsed.magic is not None:
                out.line(f"  magic     {parsed.magic.hex(' ').upper()} "
                         f"({'known' if parsed.magic_ok else 'unrecognised'})")
            if parsed.name is not None:
                out.line(f"  name      {parsed.name!r}")
            if parsed.level is not None:
                out.line(f"  mix/level {parsed.mix}/{parsed.level}  "
                         f"gain {parsed.gain_min}..{parsed.gain_max}")
            if parsed.weight_min is not None:
                out.line(f"  weights   {parsed.weight_min:.4g} .. "
                         f"{parsed.weight_max:.4g}")
        else:
            out.line(f"  kind      IR, {parsed.size} bytes")
            out.line(f"  format    tag {parsed.format_tag}, {parsed.channels} ch, "
                     f"{parsed.sample_rate} Hz, {parsed.sample_width_bits}-bit")
            out.line(f"  length    {parsed.frames} frames"
                     + (f", {parsed.duration_s * 1000:.1f} ms"
                        if parsed.duration_s else ""))
        for warning in parsed.warnings:
            out.line(f"  warn      {warning}")
        for error in parsed.errors:
            out.line(f"  ERROR     {error}")
        out.line(f"  verdict   {'ok' if parsed.ok else 'REFUSED'}")
        out.line()
    out.data(files=results)
    return worst


def cmd_rename(args: argparse.Namespace, out: Out) -> int:
    path = Path(args.file)
    if not path.is_file():
        return _fail(f"no such file: {path}")
    data = path.read_bytes()

    try:
        if args.repair_magic:
            data = captures.repair_capture_magic(data)
            out.line(f"magic -> {data[0:4].hex(' ').upper()}")
        if args.name is not None:
            data = captures.set_capture_name(data, args.name)
            out.line(f"name  -> {args.name!r}")
    except captures.CaptureEditError as exc:
        return _fail(str(exc))

    if args.name is None and not args.repair_magic:
        return _fail("nothing to do: pass a NAME, --repair-magic, or both")

    if args.output:
        destination = Path(args.output)
    elif args.in_place:
        destination = path
    else:
        out.line(f"\nDRY RUN. Nothing was written. {len(data)} bytes prepared.")
        out.line("Pass --in-place --yes to rewrite the file (the original is "
                 "copied to a .bak sidecar first), or --output PATH to write a "
                 "copy.")
        out.data(dry_run=True, would_write=len(data), source=str(path))
        return EXIT_OK

    if destination == path:
        if not args.yes:
            out.line(f"\nDRY RUN. Would rewrite {path} in place.")
            out.line("Pass --yes to do it. The original is copied to a .bak "
                     "sidecar first.")
            out.data(dry_run=True, destination=str(destination))
            return EXIT_OK
        try:
            backup = captures.write_with_backup(path, data, force=args.force)
        except captures.CaptureEditError as exc:
            return _fail(str(exc))
        out.line(f"\nwrote {path}  (original kept at {backup.name})")
        out.data(destination=str(path), backup=str(backup))
    else:
        if destination.exists() and not args.force:
            return _fail(f"{destination} exists; pass --force to overwrite")
        destination.write_bytes(data)
        out.line(f"\nwrote {destination}")
        out.data(destination=str(destination))
    return EXIT_OK


def cmd_decode(args: argparse.Namespace, out: Out) -> int:
    """Decode a 92-byte preset image supplied as hex or as a file."""
    if args.hex:
        try:
            image = bytes.fromhex(args.hex.replace(",", " "))
        except ValueError as exc:
            return _fail(f"not hex: {exc}")
    else:
        image = Path(args.file).read_bytes()
    if len(image) == protocol.RAM_DUMP_FRAME_LEN:
        frame = protocol.parse_frame(image)
        out.line(f"(input was a {len(image)}-byte frame; decoding its payload)")
        image = frame.payload
    try:
        preset = protocol.decode_preset(image, args.amp_names, args.cab_names)
    except ValueError as exc:
        return _fail(str(exc))
    _print_preset(preset, out)
    return EXIT_OK


def _print_preset(preset: protocol.PresetImage, out: Out) -> None:
    out.line(f"patch volume  {preset.volume}")
    out.line(f"routing       {' -> '.join(preset.routing_names)}")
    out.line()
    dly = next((b.model_index for b in preset.blocks if b.key == "dly"), 0)
    blocks = []
    for block in preset.blocks:
        out.line(f"{block.name:4s} {'ON ' if block.enabled else 'off'}  "
                 f"model {block.model_index:2d}  {block.model_name}")
        for slot1, knob, addr, value in block.knobs:
            shown = protocol.format_knob_value(block.key, knob, value, dly)
            out.line(f"       knob {slot1} {knob:<10s} @{addr:#04x}  {shown}")
        blocks.append({
            "key": block.key, "name": block.name, "enabled": block.enabled,
            "model_index": block.model_index, "model_name": block.model_name,
            "knobs": [{"slot": s, "name": k, "address": a, "value": v}
                      for s, k, a, v in block.knobs],
        })
    out.data(preset={"volume": preset.volume, "routing": preset.routing,
                     "routing_names": preset.routing_names, "blocks": blocks,
                     "raw": preset.raw.hex(" ").upper()})


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------


def _library(args: argparse.Namespace) -> library.Library:
    root = Path(args.library_root) if args.library_root \
        else library.DEFAULT_LIBRARY_ROOT
    return library.Library(root=root)


def cmd_library_list(args: argparse.Namespace, out: Out) -> int:
    lib = _library(args)
    try:
        entries = lib.entries(kind=args.kind, text=args.filter)
    except library.LibraryError as exc:
        return _fail(str(exc))
    for entry in entries:
        out.line(f"{entry.kind:8s} {entry.size:>8d}  {entry.path.name}")
    out.line(f"\n{len(entries)} file(s) in {lib.root}")
    out.data(root=str(lib.root),
             entries=[{"kind": e.kind, "size": e.size, "path": str(e.path)}
                      for e in entries])
    return EXIT_OK


def cmd_library_diff(args: argparse.Namespace, out: Out) -> int:
    lib = _library(args)
    doc = Path(args.doc) if args.doc else library.default_library_doc()
    try:
        diffs = library.diff_slots(lib, doc)
    except library.LibraryError as exc:
        return _fail(str(exc))
    counts: dict[str, int] = {}
    for diff in diffs:
        counts[diff.status] = counts.get(diff.status, 0) + 1
        target = diff.matches[0].name if diff.matches else (diff.slot.file_stem or "-")
        out.line(f"{diff.slot.kind:3s} {diff.slot.slot:2d}  {diff.status:9s}  "
                 f"{target}"
                 + (f"   {diff.note}" if diff.note else ""))
    out.line("\n" + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    out.data(doc=str(doc), counts=counts,
             diffs=[{"kind": d.slot.kind, "slot": d.slot.slot,
                     "status": d.status, "stem": d.slot.file_stem,
                     "matches": [str(p) for p in d.matches], "note": d.note}
                    for d in diffs])
    return EXIT_OK if counts.get("missing", 0) == 0 \
        and counts.get("ambiguous", 0) == 0 else EXIT_FAIL


def cmd_library_install(args: argparse.Namespace, out: Out) -> int:
    lib = _library(args)
    sources = [Path(p) for p in args.files]
    if not args.yes:
        out.line("DRY RUN. Nothing will be copied. Pass --yes to install.")
        out.line(f"target library: {lib.root}")
        out.line("NOTE: this writes into the M-EFCS sandbox container, i.e. "
                 "another application's data directory.")
        out.line()
        rows = []
        for source in sources:
            if not source.is_file():
                out.line(f"refused   {source}  (no such file)")
                rows.append({"source": str(source), "action": "refused",
                             "reason": "no such file"})
                continue
            parsed = captures.inspect(source)
            try:
                destination = lib.target_dir(source) / source.name
            except library.LibraryError as exc:
                out.line(f"refused   {source.name}  ({exc})")
                rows.append({"source": str(source), "action": "refused",
                             "reason": str(exc)})
                continue
            if not parsed.ok:
                action = "refused"
            elif destination.exists() and not args.force:
                action = "skipped"
            elif destination.exists():
                action = "replaced"
            else:
                action = "installed"
            out.line(f"would {action:9s} {source.name} -> {destination}")
            for warning in parsed.warnings:
                out.line(f"          warn: {warning}")
            for error in parsed.errors:
                out.line(f"          ERROR: {error}")
            rows.append({"source": str(source), "destination": str(destination),
                         "action": action, "warnings": parsed.warnings,
                         "errors": parsed.errors})
        out.data(dry_run=True, root=str(lib.root), plan=rows)
        return EXIT_OK

    try:
        results = library.install(lib, sources, force=args.force)
    except library.LibraryError as exc:
        return _fail(str(exc))
    for result in results:
        out.line(result.describe())
    refused = [r for r in results if r.action == "refused"]
    out.line(f"\n{len(results) - len(refused)} applied, {len(refused)} refused")
    if any(r.action in ("installed", "replaced") for r in results):
        out.line("M-EFCS scans the library only at launch. Run "
                 "'blackboxctl library restart-editor' to make these appear.")
    out.data(root=str(lib.root),
             results=[{"source": str(r.source), "destination": str(r.destination),
                       "action": r.action, "reason": r.reason,
                       "warnings": r.warnings,
                       "backup": str(r.backup) if r.backup else None}
                      for r in results])
    return EXIT_FAIL if refused else EXIT_OK


def cmd_library_restart(args: argparse.Namespace, out: Out) -> int:
    consent = None
    if args.yes:
        consent = library.RestartConsent(confirmed_by_user=True,
                                         accept_unsaved_work_loss=True)
    try:
        commands = library.restart_editor(consent)
    except library.LibraryError as exc:
        return _fail(str(exc))
    for command in commands:
        out.line(f"{'ran' if args.yes else 'would run'}: {command}")
    if not args.yes:
        out.line("\nDRY RUN. Nothing was executed.")
        out.line("WARNING: --yes quits M-EFCS with an AppleScript 'quit'. "
                 "Any unsaved work in that GUI is lost, and the GUI may be in "
                 "use by someone else right now.")
    out.data(dry_run=not args.yes, commands=commands)
    return EXIT_OK


# ---------------------------------------------------------------------------
# device (read only)
# ---------------------------------------------------------------------------


def _device_error(exc: Exception) -> int:
    print(f"error: {exc}", file=sys.stderr)
    print("\nThe pedal must be connected over USB and visible to CoreMIDI. "
          "Check that it is powered on and plugged in; endpoints are resolved "
          "by manufacturer 'Jieli Technology'.", file=sys.stderr)
    return EXIT_NO_DEVICE


def cmd_device_endpoints(args: argparse.Namespace, out: Out) -> int:
    try:
        from . import transport
        sources, destinations = transport.list_endpoints()
    except Exception as exc:                       # noqa: BLE001
        return _device_error(exc)
    out.line(f"sources ({len(sources)}):")
    for endpoint in sources:
        out.line(f"  {endpoint.describe()}")
    out.line(f"destinations ({len(destinations)}):")
    for endpoint in destinations:
        out.line(f"  {endpoint.describe()}")
    match = [e for e in sources + destinations
             if (e.manufacturer or "") == transport.MANUFACTURER]
    out.line(f"\nBlackBox endpoints found: {len(match)} "
             f"(need at least one source and one destination)")
    out.data(sources=[e.__dict__ for e in sources],
             destinations=[e.__dict__ for e in destinations],
             blackbox_endpoints=len(match))
    return EXIT_OK if match else EXIT_NO_DEVICE


def _read_names(device) -> tuple[list[str], list[str]]:
    amp = protocol.parse_name_table(
        device.read_memory(protocol.ADDR_AMP_NAMES, protocol.NAME_TABLE_SIZE,
                           protocol.SPACE_STRING, label="amp names").payload)
    cab = protocol.parse_name_table(
        device.read_memory(protocol.ADDR_CAB_NAMES, protocol.NAME_TABLE_SIZE,
                           protocol.SPACE_STRING, label="cab names").payload)
    return amp, cab


def cmd_device_names(args: argparse.Namespace, out: Out) -> int:
    try:
        from . import transport
        with transport.open_device() as device:
            amp, cab = _read_names(device)
    except Exception as exc:                       # noqa: BLE001
        return _device_error(exc)
    for kind, names in (("AMP", amp), ("CAB/IR", cab)):
        if args.kind != "both" and args.kind.upper() not in kind:
            continue
        out.line(f"{kind} slots:")
        for index, name in enumerate(names, start=1):
            out.line(f"  {index:2d}  {protocol.strip_slot_prefix(name, index)}")
        out.line()
    out.data(amp_names=amp, cab_names=cab)
    return EXIT_OK


def cmd_device_dump(args: argparse.Namespace, out: Out) -> int:
    try:
        from . import transport
        with transport.open_device() as device:
            frame = device.read_memory(protocol.ADDR_LIVE_RAM,
                                       protocol.PRESET_SIZE, label="ram dump")
            amp, cab = _read_names(device)
    except Exception as exc:                       # noqa: BLE001
        return _device_error(exc)
    out.line(f"live RAM, {len(frame.payload)} bytes, "
             f"checksum_ok={frame.checksum_ok}")
    out.line()
    _print_preset(protocol.decode_preset(frame.payload, amp, cab), out)
    return EXIT_OK


def cmd_device_sync(args: argparse.Namespace, out: Out) -> int:
    try:
        from . import transport
        with transport.open_device() as device:
            frame = device.read_memory(protocol.ADDR_CURRENT_PRESET, 4,
                                       label="preset sync")
    except Exception as exc:                       # noqa: BLE001
        return _device_error(exc)
    index0 = frame.payload[0]
    out.line(f"active preset  P{index0 + 1:02d}  (protocol index {index0})")
    out.line(f"raw payload    {frame.payload.hex(' ').upper()}")
    out.data(active_index0=index0, active_label=f"P{index0 + 1:02d}",
             payload=frame.payload.hex(" ").upper())
    return EXIT_OK


def cmd_device_preset(args: argparse.Namespace, out: Out) -> int:
    slot1 = args.slot
    index0 = slot1 - 1
    try:
        protocol.check_preset_index(index0)
    except ValueError as exc:
        return _fail(str(exc))
    try:
        from . import transport
        with transport.open_device() as device:
            frame = device.read_memory(
                protocol.ADDR_PRESET_BASE + index0 * protocol.PRESET_SIZE,
                protocol.PRESET_SIZE, label=f"flash P{slot1:02d}")
            amp, cab = _read_names(device)
    except Exception as exc:                       # noqa: BLE001
        return _device_error(exc)
    out.line(f"P{slot1:02d} (flash index {index0}, address "
             f"{index0 * protocol.PRESET_SIZE})")
    out.line()
    _print_preset(protocol.decode_preset(frame.payload, amp, cab), out)
    return EXIT_OK


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blackboxctl",
        description="Read and manage an M-Vave BlackBox and its M-EFCS library. "
                    "Device access is READ ONLY: no command here can transmit a "
                    "state-changing frame.",
        epilog="GPL-3.0. Protocol reverse engineered by Joel Victor "
               "(github.com/jvsobrinho/mvave-blackbox-ble, CC BY-SA 4.0). "
               "See NOTICE.")
    parser.add_argument("--version", action="version",
                        version=f"blackboxctl {__version__}")
    parser.add_argument("--json", action="store_true",
                        help="emit one JSON document instead of text")
    parser.add_argument("--library-root", default=None,
                        help=f"M-EFCS library root "
                             f"(default: {library.DEFAULT_LIBRARY_ROOT})")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("selftest",
                       help="offline protocol self-test; touches nothing")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser("write-paths",
                       help="list state-changing commands and why each is disabled")
    p.set_defaults(func=cmd_write_paths)

    p = sub.add_parser("inspect", help="parse and validate capture / IR files")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("rename", help="edit a capture file's header name / magic")
    p.add_argument("file")
    p.add_argument("name", nargs="?", default=None,
                   help="new name, at most 13 printable ASCII characters")
    p.add_argument("--in-place", action="store_true",
                   help="rewrite the file itself (needs --yes)")
    p.add_argument("--output", default=None, help="write a copy here instead")
    p.add_argument("--repair-magic", action="store_true",
                   help="set the AM prefix on a 00 00 3x 00 magic, keeping the "
                        "version digit")
    p.add_argument("--yes", action="store_true", help="actually write")
    p.add_argument("--force", action="store_true",
                   help="overwrite an existing output or .bak")
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("decode", help="decode a 92-byte preset image offline")
    p.add_argument("file", nargs="?", default=None)
    p.add_argument("--hex", default=None, help="the image as hex instead")
    p.add_argument("--amp-names", nargs="*", default=None)
    p.add_argument("--cab-names", nargs="*", default=None)
    p.set_defaults(func=cmd_decode)

    lib = sub.add_parser("library", help="the M-EFCS on-disk capture/IR library")
    libsub = lib.add_subparsers(dest="subcommand", required=True)

    p = libsub.add_parser("list", help="list installed captures and IRs")
    p.add_argument("--kind", choices=("capture", "ir"), default=None)
    p.add_argument("--filter", default=None)
    p.set_defaults(func=cmd_library_list)

    p = libsub.add_parser("diff",
                          help="compare presets/library.md's slot maps to disk")
    p.add_argument("--doc", default=None)
    p.set_defaults(func=cmd_library_diff)

    p = libsub.add_parser(
        "install",
        help="copy captures/IRs into the M-EFCS library (DRY RUN unless --yes)")
    p.add_argument("files", nargs="+")
    p.add_argument("--force", action="store_true",
                   help="replace an existing file, keeping a timestamped .bak")
    p.add_argument("--yes", action="store_true", help="actually copy")
    p.set_defaults(func=cmd_library_install)

    p = libsub.add_parser(
        "restart-editor",
        help="quit and relaunch M-EFCS so it rescans (DRY RUN unless --yes)")
    p.add_argument("--yes", action="store_true",
                   help="actually quit and relaunch; unsaved GUI work is lost")
    p.set_defaults(func=cmd_library_restart)

    dev = sub.add_parser("device", help="read from the pedal over USB MIDI")
    devsub = dev.add_subparsers(dest="subcommand", required=True)

    p = devsub.add_parser("endpoints", help="list CoreMIDI endpoints")
    p.set_defaults(func=cmd_device_endpoints)

    p = devsub.add_parser("dump", help="read and decode the live RAM preset")
    p.set_defaults(func=cmd_device_dump)

    p = devsub.add_parser("sync", help="read the active preset id")
    p.set_defaults(func=cmd_device_sync)

    p = devsub.add_parser("names", help="read the 20 amp and 20 IR slot names")
    p.add_argument("--kind", choices=("amp", "cab", "both"), default="both")
    p.set_defaults(func=cmd_device_names)

    p = devsub.add_parser("preset", help="read and decode a stored preset")
    p.add_argument("slot", type=int, help="1-based, as the pedal shows it (P01..)")
    p.set_defaults(func=cmd_device_preset)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = Out(as_json=args.json)
    try:
        code = args.func(args, out)
    except KeyboardInterrupt:
        return 130
    out.flush()
    return code


if __name__ == "__main__":                          # pragma: no cover
    raise SystemExit(main())
