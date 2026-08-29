"""Command line interface for blackboxctl.

Safety model, in one place
--------------------------
1. Device writes are dry-run by default and require ``--yes``. Each operation
   is bound to a narrow, independently checked write capability. Preset writes
   preserve exact rollback bytes; AMP/CAB writes require exact ACKs or reconcile
   a lost final ACK through changed persistent state, then verify the slot name.
   This firmware exposes no AMP-weight or CAB-waveform read-back path.
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
import signal
import sys
import time
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import (
    __version__,
    backups,
    captures,
    device_library,
    library,
    presetfiles,
    protocol,
    storage,
)

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

    def error(self, message: str, *, hint: str | None = None) -> None:
        """Record a machine-readable error or print one human error block."""
        if self.as_json:
            self.data(error=message)
            if hint:
                self.data(hint=hint)
            return
        print(f"error: {message}", file=sys.stderr)
        if hint:
            print(f"\n{hint}", file=sys.stderr)

    def flush(self, exit_code: int = EXIT_OK) -> None:
        if self.as_json:
            self._doc.setdefault("ok", exit_code == EXIT_OK)
            self._doc.setdefault("exit_code", exit_code)
            print(json.dumps(self._doc, indent=2, default=_jsonable))


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex(" ").upper()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return str(value)


def _fail(out: Out, message: str) -> int:
    out.error(message)
    return EXIT_FAIL


def _write_output(path: Path, payload: bytes, *, force: bool) -> Path:
    """Atomically publish a CLI output, refusing clobber unless requested."""
    try:
        return storage.write_bytes_atomic(path, payload, replace=force)
    except storage.DestinationExistsError as exc:
        raise RuntimeError(f"{exc.path} exists; pass --force to replace it") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot write {path}: {exc}") from exc


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
        "ram dump": (
            protocol.cmd_ram_dump(),
            "00 59 23 08 00 00 04 00 00 00 10 5C 00 00 8F",
        ),
        "preset sync": (
            protocol.cmd_preset_sync(),
            "00 59 23 08 00 00 04 00 00 00 20 04 00 00 D7",
        ),
        "cab names": (
            protocol.cmd_read_cab_names(),
            "00 59 23 08 00 00 05 00 00 00 80 18 01 00 61",
        ),
        "amp names": (
            protocol.cmd_read_amp_names(),
            "00 59 23 08 00 00 05 00 00 00 90 18 01 00 51",
        ),
        "flash P01": (
            protocol.cmd_read_flash_preset(0),
            "00 59 23 08 00 00 04 00 00 00 00 5C 00 00 9F",
        ),
        "flash P03": (
            protocol.cmd_read_flash_preset(2),
            "00 59 23 08 00 00 04 B8 00 00 00 5C 00 00 E7",
        ),
        "flash P41": (
            protocol.cmd_read_flash_preset(40),
            "00 59 23 08 00 00 04 60 0E 00 00 5C 00 00 31",
        ),
    }
    for name, (built, expected) in literals.items():
        check(
            f"read literal: {name}",
            protocol.hexs(built) == expected,
            protocol.hexs(built),
        )

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

    # Every exercised path is enabled; the undocumented commit path is not.
    enabled = [k for k, p in protocol.WRITE_PATHS.items() if p.hardware_confirmed]
    expected_enabled = [
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
    check(
        "hardware-confirmed write paths match the physical probes",
        enabled == expected_enabled,
        str(enabled),
    )

    passed = sum(1 for _, ok, _ in checks if ok)
    for name, ok, detail in checks:
        out.line(
            f"  {'PASS' if ok else 'FAIL'}  {name}"
            + (f"    {detail}" if detail and not ok else "")
        )
    out.line(f"\n{passed}/{len(checks)} checks passed")
    out.data(
        checks=[{"name": n, "ok": o, "detail": d} for n, o, d in checks],
        passed=passed,
        total=len(checks),
    )
    return EXIT_OK if passed == len(checks) else EXIT_FAIL


def cmd_doctor(args: argparse.Namespace, out: Out) -> int:
    """Report host, protocol, MIDI, and M-EFCS readiness. Touches no device RAM."""
    code = cmd_selftest(args, out)
    python = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    helper = captures.DEFAULT_AMX_DYLIB
    library_root = (
        Path(args.library_root).expanduser()
        if args.library_root
        else library.DEFAULT_LIBRARY_ROOT
    )
    transport_status = "unavailable"
    device_ready = False
    device_detail = "CoreMIDI was not loaded"
    try:
        from . import transport as midi

        transport_status = "available"
        try:
            sources, destinations = midi.list_endpoints()
        except Exception as exc:  # noqa: BLE001 - doctor must not traceback
            device_detail = str(exc)
        else:
            matching_sources = [
                endpoint
                for endpoint in sources
                if (endpoint.manufacturer or "") == midi.MANUFACTURER
            ]
            matching_destinations = [
                endpoint
                for endpoint in destinations
                if (endpoint.manufacturer or "") == midi.MANUFACTURER
            ]
            device_ready = (
                len(matching_sources) == 1 and len(matching_destinations) == 1
            )
            device_detail = (
                f"{len(matching_sources)} source, {len(matching_destinations)} "
                "destination; need exactly one of each"
            )
    except Exception as exc:  # noqa: BLE001 - Linux/CI have no CoreMIDI
        device_detail = str(exc)

    out.line("")
    out.line("host")
    out.line(f"  python     {python}")
    out.line(f"  platform   {sys.platform}")
    out.line("MIDI")
    out.line(f"  transport  {transport_status}")
    out.line(
        f"  device     {'ready' if device_ready else 'not ready'} ({device_detail})"
    )
    out.line("AMP helper")
    out.line(f"  {helper}  {'present' if helper.is_file() else 'missing'}")
    out.line("M-EFCS library")
    out.line(f"  {library_root}  {'present' if library_root.is_dir() else 'missing'}")
    out.data(
        python=python,
        platform=sys.platform,
        transport=transport_status,
        device_ready=device_ready,
        device_detail=device_detail,
        amp_helper=str(helper),
        amp_helper_present=helper.is_file(),
        library_root=str(library_root),
        library_root_present=library_root.is_dir(),
    )
    if code != EXIT_OK:
        return code
    if getattr(args, "require_device", False) and not device_ready:
        out.error(
            "no BlackBox MIDI pair is ready",
            hint="Plug the pedal in over USB and re-run without --require-device "
            "to inspect the host only.",
        )
        return EXIT_NO_DEVICE
    return EXIT_OK


# ---------------------------------------------------------------------------
# write-paths
# ---------------------------------------------------------------------------


def cmd_write_paths(args: argparse.Namespace, out: Out) -> int:
    """Show every state-changing command and its hardware evidence."""
    rows = []
    for path in protocol.WRITE_PATHS.values():
        rows.append(
            {
                "key": path.key,
                "description": path.description,
                "hardware_confirmed": path.hardware_confirmed,
                "touches_flash": path.touches_flash,
                "evidence": path.evidence,
            }
        )
        out.line(f"{path.key}")
        out.line(f"  what           {path.description}")
        out.line(f"  confirmed      {path.hardware_confirmed}")
        out.line(f"  touches flash  {path.touches_flash}")
        out.line(f"  evidence       {path.evidence}")
        out.line()
    out.line(
        "Preset load/edit/save and AMP/CAB stage/save paths are physically "
        "confirmed. No generic address writer or firmware writer exists."
    )
    out.data(
        write_paths=rows,
        any_enabled=bool(
            [p for p in protocol.WRITE_PATHS.values() if p.hardware_confirmed]
        ),
    )
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
            results.append({"path": str(path), "errors": ["no such file"], "ok": False})
            worst = EXIT_FAIL
            continue
        parsed = captures.inspect(path)
        results.append(parsed.to_dict())
        if not parsed.ok:
            worst = EXIT_FAIL
        out.line(f"{path.name}")
        if isinstance(parsed, captures.Capture):
            out.line(
                f"  kind      capture, {parsed.size} bytes"
                f"{', header' if parsed.has_header else ', bare payload'}"
            )
            if parsed.magic is not None:
                out.line(
                    f"  magic     {parsed.magic.hex(' ').upper()} "
                    f"({'known' if parsed.magic_ok else 'unrecognised'})"
                )
            if parsed.name is not None:
                out.line(f"  name      {parsed.name!r}")
            if parsed.level is not None:
                out.line(
                    f"  mix/level {parsed.mix}/{parsed.level}  "
                    f"gain {parsed.gain_min}..{parsed.gain_max}"
                )
            if parsed.weight_min is not None:
                out.line(
                    f"  weights   {parsed.weight_min:.4g} .. {parsed.weight_max:.4g}"
                )
        else:
            out.line(f"  kind      IR, {parsed.size} bytes")
            out.line(
                f"  format    tag {parsed.format_tag}, {parsed.channels} ch, "
                f"{parsed.sample_rate} Hz, {parsed.sample_width_bits}-bit"
            )
            out.line(
                f"  length    {parsed.frames} frames"
                + (f", {parsed.duration_s * 1000:.1f} ms" if parsed.duration_s else "")
            )
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
        return _fail(out, f"no such file: {path}")
    data = path.read_bytes()

    try:
        if args.repair_magic:
            data = captures.repair_capture_magic(data)
            out.line(f"magic -> {data[0:4].hex(' ').upper()}")
        if args.name is not None:
            data = captures.set_capture_name(data, args.name)
            out.line(f"name  -> {args.name!r}")
    except captures.CaptureEditError as exc:
        return _fail(out, str(exc))

    if args.name is None and not args.repair_magic:
        return _fail(out, "nothing to do: pass a NAME, --repair-magic, or both")

    if args.output:
        destination = Path(args.output)
    elif args.in_place:
        destination = path
    else:
        out.line(f"\nDRY RUN. Nothing was written. {len(data)} bytes prepared.")
        out.line(
            "Pass --in-place --yes to rewrite the file (the original is "
            "copied to a .bak sidecar first), or --output PATH to write a "
            "copy."
        )
        out.data(dry_run=True, would_write=len(data), source=str(path))
        return EXIT_OK

    if destination == path:
        if not args.yes:
            out.line(f"\nDRY RUN. Would rewrite {path} in place.")
            out.line(
                "Pass --yes to do it. The original is copied to a .bak sidecar first."
            )
            out.data(dry_run=True, destination=str(destination))
            return EXIT_OK
        try:
            backup = captures.write_with_backup(path, data, force=args.force)
        except captures.CaptureEditError as exc:
            return _fail(out, str(exc))
        out.line(f"\nwrote {path}  (original kept at {backup.name})")
        out.data(destination=str(path), backup=str(backup))
    else:
        try:
            destination = _write_output(destination, data, force=args.force)
        except RuntimeError as exc:
            return _fail(out, str(exc))
        out.line(f"\nwrote {destination}")
        out.data(destination=str(destination))
    return EXIT_OK


def cmd_decode(args: argparse.Namespace, out: Out) -> int:
    """Decode a 92-byte preset image supplied as hex or as a file."""
    if args.file is None and args.hex is None:
        return _fail(out, "pass a preset image FILE or --hex DATA")
    if args.file is not None and args.hex is not None:
        return _fail(out, "pass either a preset image FILE or --hex DATA, not both")
    try:
        if args.hex is not None:
            image = bytes.fromhex(args.hex.replace(",", " "))
        else:
            assert args.file is not None
            image = Path(args.file).read_bytes()
    except ValueError as exc:
        return _fail(out, f"not hex: {exc}")
    except OSError as exc:
        return _fail(out, f"cannot read {args.file}: {exc}")
    framed = len(image) == protocol.RAM_DUMP_FRAME_LEN
    try:
        image = presetfiles.normalize_image_bytes(image)
        preset = protocol.decode_preset(image, args.amp_names, args.cab_names)
    except (presetfiles.PresetSpecError, ValueError) as exc:
        return _fail(out, str(exc))
    if framed:
        out.line(
            f"(input was a {protocol.RAM_DUMP_FRAME_LEN}-byte frame; "
            "decoding its payload)"
        )
    _print_preset(preset, out)
    return EXIT_OK


# ---------------------------------------------------------------------------
# backup bundles
# ---------------------------------------------------------------------------


def cmd_backup_verify(args: argparse.Namespace, out: Out) -> int:
    path = Path(args.file).expanduser()
    try:
        bundle = backups.load(path)
    except backups.BackupError as exc:
        return _fail(out, str(exc))
    out.line(f"verified {path}")
    out.line(f"  schema      {bundle['schema']}")
    out.line(f"  created     {bundle['created_at']}")
    out.line(f"  presets     {len(bundle['presets'])} / {protocol.PRESET_COUNT}")
    out.line(f"  AMP names   {len(bundle['amp_names'])} / {protocol.NAME_COUNT}")
    out.line(f"  CAB names   {len(bundle['cab_names'])} / {protocol.NAME_COUNT}")
    out.line(f"  active      P{bundle['active_preset']['slot']:02d}")
    out.data(
        valid=True,
        path=str(path.resolve()),
        schema=bundle["schema"],
        created_at=bundle["created_at"],
        preset_count=len(bundle["presets"]),
        active_preset=bundle["active_preset"],
    )
    return EXIT_OK


def cmd_backup_extract(args: argparse.Namespace, out: Out) -> int:
    source = Path(args.file).expanduser()
    destination = Path(args.output).expanduser()
    try:
        bundle = backups.load(source)
        image = backups.image_for_slot(bundle, args.slot)
    except (backups.BackupError, ValueError) as exc:
        return _fail(out, str(exc))
    try:
        destination = _write_output(destination, image, force=args.force)
    except RuntimeError as exc:
        return _fail(out, str(exc))
    out.line(f"extracted P{args.slot:02d}: {len(image)} bytes -> {destination}")
    out.data(
        source=str(source.resolve()),
        slot=args.slot,
        destination=str(destination.resolve()),
        sha256=backups.sha256(image),
    )
    return EXIT_OK


def cmd_backup_extract_all(args: argparse.Namespace, out: Out) -> int:
    source = Path(args.file).expanduser()
    directory = Path(args.output).expanduser()
    try:
        bundle = backups.load(source)
        images = backups.slot_images(bundle)
    except backups.BackupError as exc:
        return _fail(out, str(exc))
    planned = [(slot, directory / f"P{slot:02d}.bin", image) for slot, image in images]
    if not args.force:
        existing = [path for _slot, path, _image in planned if path.exists()]
        if existing:
            return _fail(
                out,
                f"{existing[0]} exists; pass --force to replace extracted images",
            )
    try:
        storage.mkdir_durable(directory)
    except OSError as exc:
        return _fail(out, f"cannot create {directory}: {exc}")
    written: list[str] = []
    try:
        for slot, destination, image in planned:
            path = _write_output(destination, image, force=args.force)
            written.append(str(path))
            out.line(f"P{slot:02d}  {path}")
    except RuntimeError as exc:
        return _fail(out, str(exc))
    out.data(
        source=str(source.resolve()),
        directory=str(directory.resolve()),
        count=len(written),
        files=written,
    )
    return EXIT_OK


def cmd_preset_export(args: argparse.Namespace, out: Out) -> int:
    source = Path(args.image)
    destination = Path(args.output)
    try:
        image = presetfiles.load_image(source)
        spec = presetfiles.export_spec(image)
    except (presetfiles.PresetSpecError, ValueError) as exc:
        return _fail(out, str(exc))
    payload = (json.dumps(spec, indent=2, ensure_ascii=False) + "\n").encode()
    try:
        destination = _write_output(destination, payload, force=args.force)
    except RuntimeError as exc:
        return _fail(out, str(exc))
    out.line(f"exported declarative preset -> {destination}")
    out.data(
        source=str(source.resolve()),
        destination=str(destination.resolve()),
        image_sha256=backups.sha256(image),
    )
    return EXIT_OK


def cmd_preset_render(args: argparse.Namespace, out: Out) -> int:
    source = Path(args.base)
    spec_path = Path(args.spec)
    destination = Path(args.output)
    try:
        image = presetfiles.load_image(source)
        spec = presetfiles.load_spec(spec_path)
        result, changes = presetfiles.apply(image, spec)
    except (presetfiles.PresetSpecError, ValueError) as exc:
        return _fail(out, str(exc))
    for change in changes:
        out.line(f"{change.field:<20s} {change.before!r} -> {change.after!r}")
    if not args.yes:
        out.line(f"\nDRY RUN. {len(changes)} field(s) would change; no file written.")
        out.line("Pass --yes to write the 92-byte image.")
        out.data(
            dry_run=True,
            change_count=len(changes),
            changes=changes,
            result_sha256=backups.sha256(result),
        )
        return EXIT_OK
    try:
        destination = _write_output(destination, result, force=args.force)
    except RuntimeError as exc:
        return _fail(out, str(exc))
    out.line(f"\nwrote {len(result)} bytes -> {destination}")
    out.data(
        dry_run=False,
        destination=str(destination.resolve()),
        change_count=len(changes),
        changes=changes,
        result_sha256=backups.sha256(result),
    )
    return EXIT_OK


def _print_preset(preset: protocol.PresetImage, out: Out) -> None:
    out.line(f"patch volume  {preset.volume}")
    out.line(f"routing       {' -> '.join(preset.routing_names)}")
    out.line()
    dly = next((b.model_index for b in preset.blocks if b.key == "dly"), 0)
    blocks = []
    for block in preset.blocks:
        out.line(
            f"{block.name:4s} {'ON ' if block.enabled else 'off'}  "
            f"model {block.model_index:2d}  {block.model_name}"
        )
        for slot1, knob, addr, value in block.knobs:
            shown = protocol.format_knob_value(block.key, knob, value, dly)
            out.line(f"       knob {slot1} {knob:<10s} @{addr:#04x}  {shown}")
        blocks.append(
            {
                "key": block.key,
                "name": block.name,
                "enabled": block.enabled,
                "model_index": block.model_index,
                "model_name": block.model_name,
                "knobs": [
                    {"slot": s, "name": k, "address": a, "value": v}
                    for s, k, a, v in block.knobs
                ],
            }
        )
    out.data(
        preset={
            "volume": preset.volume,
            "routing": preset.routing,
            "routing_names": preset.routing_names,
            "blocks": blocks,
            "raw": preset.raw.hex(" ").upper(),
        }
    )


# ---------------------------------------------------------------------------
# library
# ---------------------------------------------------------------------------


def _library(args: argparse.Namespace) -> library.Library:
    root = (
        Path(args.library_root) if args.library_root else library.DEFAULT_LIBRARY_ROOT
    )
    return library.Library(root=root)


def cmd_library_list(args: argparse.Namespace, out: Out) -> int:
    lib = _library(args)
    try:
        entries = lib.entries(kind=args.kind, text=args.filter)
    except library.LibraryError as exc:
        return _fail(out, str(exc))
    for entry in entries:
        out.line(f"{entry.kind:8s} {entry.size:>8d}  {entry.path.name}")
    out.line(f"\n{len(entries)} file(s) in {lib.root}")
    out.data(
        root=str(lib.root),
        entries=[
            {"kind": e.kind, "size": e.size, "path": str(e.path)} for e in entries
        ],
    )
    return EXIT_OK


def cmd_library_diff(args: argparse.Namespace, out: Out) -> int:
    lib = _library(args)
    doc = Path(args.doc) if args.doc else library.default_library_doc()
    try:
        diffs = library.diff_slots(lib, doc)
    except library.LibraryError as exc:
        return _fail(out, str(exc))
    counts: dict[str, int] = {}
    for diff in diffs:
        counts[diff.status] = counts.get(diff.status, 0) + 1
        target = diff.matches[0].name if diff.matches else (diff.slot.file_stem or "-")
        out.line(
            f"{diff.slot.kind:3s} {diff.slot.slot:2d}  {diff.status:9s}  "
            f"{target}" + (f"   {diff.note}" if diff.note else "")
        )
    out.line("\n" + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    out.data(
        doc=str(doc),
        counts=counts,
        diffs=[
            {
                "kind": d.slot.kind,
                "slot": d.slot.slot,
                "status": d.status,
                "stem": d.slot.file_stem,
                "matches": [str(p) for p in d.matches],
                "note": d.note,
            }
            for d in diffs
        ],
    )
    return (
        EXIT_OK
        if counts.get("missing", 0) == 0 and counts.get("ambiguous", 0) == 0
        else EXIT_FAIL
    )


def cmd_library_install(args: argparse.Namespace, out: Out) -> int:
    lib = _library(args)
    sources = [Path(p) for p in args.files]
    if not args.yes:
        out.line("DRY RUN. Nothing will be copied. Pass --yes to install.")
        out.line(f"target library: {lib.root}")
        out.line(
            "NOTE: this writes into the M-EFCS sandbox container, i.e. "
            "another application's data directory."
        )
        out.line()
        rows = []
        for source in sources:
            if not source.is_file():
                out.line(f"refused   {source}  (no such file)")
                rows.append(
                    {
                        "source": str(source),
                        "action": "refused",
                        "reason": "no such file",
                    }
                )
                continue
            parsed = captures.inspect(source)
            try:
                destination = lib.destination_for(source)
            except library.LibraryError as exc:
                out.line(f"refused   {source.name}  ({exc})")
                rows.append(
                    {"source": str(source), "action": "refused", "reason": str(exc)}
                )
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
            rows.append(
                {
                    "source": str(source),
                    "destination": str(destination),
                    "action": action,
                    "warnings": parsed.warnings,
                    "errors": parsed.errors,
                }
            )
        out.data(dry_run=True, root=str(lib.root), plan=rows)
        return EXIT_OK

    try:
        results = library.install(lib, sources, force=args.force)
    except library.LibraryError as exc:
        return _fail(out, str(exc))
    for result in results:
        out.line(result.describe())
    refused = [r for r in results if r.action == "refused"]
    out.line(f"\n{len(results) - len(refused)} applied, {len(refused)} refused")
    if any(r.action in ("installed", "replaced") for r in results):
        out.line(
            "M-EFCS scans the library only at launch. Run "
            "'blackboxctl library restart-editor' to make these appear."
        )
    out.data(
        root=str(lib.root),
        results=[
            {
                "source": str(r.source),
                "destination": str(r.destination),
                "action": r.action,
                "reason": r.reason,
                "warnings": r.warnings,
                "backup": str(r.backup) if r.backup else None,
            }
            for r in results
        ],
    )
    return EXIT_FAIL if refused else EXIT_OK


def cmd_library_restart(args: argparse.Namespace, out: Out) -> int:
    consent = None
    if args.yes:
        consent = library.RestartConsent(
            confirmed_by_user=True, accept_unsaved_work_loss=True
        )
    try:
        commands = library.restart_editor(consent)
    except library.LibraryError as exc:
        return _fail(out, str(exc))
    for command in commands:
        out.line(f"{'ran' if args.yes else 'would run'}: {command}")
    if not args.yes:
        out.line("\nDRY RUN. Nothing was executed.")
        out.line(
            "WARNING: --yes quits M-EFCS with an AppleScript 'quit'. "
            "Any unsaved work in that GUI is lost, and the GUI may be in "
            "use by someone else right now."
        )
    out.data(dry_run=not args.yes, commands=commands)
    return EXIT_OK


# ---------------------------------------------------------------------------
# device access
# ---------------------------------------------------------------------------


def _device_error(out: Out, exc: Exception) -> int:
    from . import transport

    if isinstance(exc, transport.TransportUnavailable):
        out.error(
            str(exc),
            hint=(
                "The pedal must be connected over USB and visible to CoreMIDI. "
                "Check that it is powered on and plugged in; endpoints are "
                "resolved by manufacturer 'Jieli Technology'."
            ),
        )
        return EXIT_NO_DEVICE
    out.error(str(exc))
    return EXIT_FAIL


def cmd_device_endpoints(args: argparse.Namespace, out: Out) -> int:
    try:
        from . import transport

        sources, destinations = transport.list_endpoints()
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(f"sources ({len(sources)}):")
    for endpoint in sources:
        out.line(f"  {endpoint.describe()}")
    out.line(f"destinations ({len(destinations)}):")
    for endpoint in destinations:
        out.line(f"  {endpoint.describe()}")
    matching_sources = [
        e for e in sources if (e.manufacturer or "") == transport.MANUFACTURER
    ]
    matching_destinations = [
        e for e in destinations if (e.manufacturer or "") == transport.MANUFACTURER
    ]
    ready = len(matching_sources) == 1 and len(matching_destinations) == 1
    total_matches = len(matching_sources) + len(matching_destinations)
    out.line(
        f"\nBlackBox endpoints found: {total_matches} "
        f"({len(matching_sources)} source, {len(matching_destinations)} destination; "
        "need exactly one of each)"
    )
    out.data(
        sources=[e.__dict__ for e in sources],
        destinations=[e.__dict__ for e in destinations],
        blackbox_endpoints=total_matches,
        blackbox_sources=len(matching_sources),
        blackbox_destinations=len(matching_destinations),
        ready=ready,
    )
    return EXIT_OK if ready else EXIT_NO_DEVICE


def _read_name_table(device: Any, table_index: int) -> list[str]:
    """Read one AMP (0) or CAB (1) table with bounded transient retries."""
    if table_index not in (0, 1):
        raise ValueError(f"name-table index must be 0 or 1, got {table_index}")
    address, label = (
        (protocol.ADDR_AMP_NAMES, "amp names")
        if table_index == 0
        else (protocol.ADDR_CAB_NAMES, "cab names")
    )
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            return protocol.parse_name_table(
                device.read_memory(
                    address,
                    protocol.NAME_TABLE_SIZE,
                    protocol.SPACE_STRING,
                    label=f"{label} attempt {attempt}",
                ).payload
            )
        except Exception as exc:  # noqa: BLE001 - retries transport/parser errors
            last_error = exc
            time.sleep(0.2 * attempt)
    assert last_error is not None
    raise last_error


def _read_names(device: Any) -> tuple[list[str], list[str]]:
    return _read_name_table(device, 0), _read_name_table(device, 1)


def _require_blackbox_handshake(device: Any, label: str) -> int:
    """Prove a BlackBox-specific safe read succeeds before a write-only action."""
    frame = device.read_memory(
        protocol.ADDR_CURRENT_PRESET, 4, label=f"{label} identity handshake"
    )
    if len(frame.payload) != 4:
        raise RuntimeError(
            f"{label}: identity handshake returned {len(frame.payload)} bytes, "
            "expected the 4-byte BlackBox active-preset register"
        )
    active = frame.payload[0]
    try:
        protocol.check_preset_index(active)
    except ValueError as exc:
        raise RuntimeError(
            f"{label}: identity handshake returned invalid preset index {active}"
        ) from exc
    return active


def cmd_device_names(args: argparse.Namespace, out: Out) -> int:
    try:
        from . import transport

        with transport.open_device() as device:
            amp, cab = _read_names(device)
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
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
            frame = device.read_memory(
                protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE, label="ram dump"
            )
            amp, cab = _read_names(device)
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(f"live RAM, {len(frame.payload)} bytes, checksum_ok={frame.checksum_ok}")
    out.line()
    _print_preset(protocol.decode_preset(frame.payload, amp, cab), out)
    return EXIT_OK


def cmd_device_sync(args: argparse.Namespace, out: Out) -> int:
    try:
        from . import transport

        with transport.open_device() as device:
            frame = device.read_memory(
                protocol.ADDR_CURRENT_PRESET, 4, label="preset sync"
            )
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    index0 = frame.payload[0]
    out.line(f"active preset  P{index0 + 1:02d}  (protocol index {index0})")
    out.line(f"raw payload    {frame.payload.hex(' ').upper()}")
    out.data(
        active_index0=index0,
        active_label=f"P{index0 + 1:02d}",
        payload=frame.payload.hex(" ").upper(),
    )
    return EXIT_OK


def cmd_device_preset(args: argparse.Namespace, out: Out) -> int:
    slot1 = args.slot
    index0 = slot1 - 1
    try:
        protocol.check_preset_index(index0)
    except ValueError as exc:
        return _fail(out, str(exc))
    try:
        from . import transport

        with transport.open_device() as device:
            frame = device.read_memory(
                protocol.ADDR_PRESET_BASE + index0 * protocol.PRESET_SIZE,
                protocol.PRESET_SIZE,
                label=f"flash P{slot1:02d}",
            )
            amp, cab = _read_names(device)
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(
        f"P{slot1:02d} (flash index {index0}, address {index0 * protocol.PRESET_SIZE})"
    )
    out.line()
    _print_preset(protocol.decode_preset(frame.payload, amp, cab), out)
    return EXIT_OK


def _default_backup_path() -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return (
        Path.home()
        / ".local"
        / "share"
        / "blackboxctl"
        / "backups"
        / f"blackbox-{stamp}.json"
    )


def cmd_device_backup(args: argparse.Namespace, out: Out) -> int:
    """Read every restore-critical preset byte without changing device state."""
    destination = (
        Path(args.output).expanduser() if args.output else _default_backup_path()
    )
    if destination.exists() and not args.force:
        return _fail(out, f"{destination} exists; pass --force to replace it")
    try:
        from . import transport

        with transport.open_device() as device:
            active = device.read_memory(
                protocol.ADDR_CURRENT_PRESET, 4, label="backup active preset"
            )
            amp, cab = _read_names(device)
            images = []
            for index0 in range(protocol.PRESET_COUNT):
                slot1 = index0 + 1
                out.line(f"reading P{slot1:02d}/{protocol.PRESET_COUNT:02d} ...")
                frame = device.read_memory(
                    protocol.ADDR_PRESET_BASE + index0 * protocol.PRESET_SIZE,
                    protocol.PRESET_SIZE,
                    label=f"backup P{slot1:02d}",
                )
                images.append(frame.payload)
            device_info = {
                "manufacturer": transport.MANUFACTURER,
                "source": device.source.describe() if device.source else None,
                "destination": (
                    device.destination.describe() if device.destination else None
                ),
            }
        bundle = backups.make_bundle(
            active_index0=active.payload[0],
            amp_names=amp,
            cab_names=cab,
            images=images,
            device=device_info,
        )
        backups.write_atomic(destination, bundle, force=args.force)
        # Validate bytes from disk, not merely the object we intended to write.
        backups.load(destination)
    except backups.BackupError as exc:
        return _fail(out, str(exc))
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    digest = backups.sha256(destination.read_bytes())
    out.line(f"\nbackup complete: {destination}")
    out.line(f"  {len(images)} presets, {len(amp)} AMP names, {len(cab)} CAB names")
    out.line(f"  active preset P{active.payload[0] + 1:02d}")
    out.line(f"  file SHA-256 {digest}")
    out.data(
        path=str(destination.resolve()),
        file_sha256=digest,
        preset_count=len(images),
        amp_name_count=len(amp),
        cab_name_count=len(cab),
        active_index0=active.payload[0],
    )
    return EXIT_OK


def _plan_live_image_writes(
    before: bytes,
    target: bytes,
    *,
    force: bool = False,
) -> list[tuple[bytes, str, str]]:
    """Build every required frame before a live image can be mutated.

    Building the whole plan first is a rollback guarantee: an out-of-range
    model, toggle, knob, volume, or malformed routing permutation is rejected
    before the first frame reaches the device.
    """
    if len(before) != protocol.PRESET_SIZE or len(target) != protocol.PRESET_SIZE:
        raise ValueError("live image must be exactly 92 bytes")
    planned: list[tuple[bytes, str, str]] = []

    # Model selection resets the selected block's knobs. It must happen before
    # any knob words are applied.
    model_changed: set[str] = set()
    for block in protocol.BLOCKS:
        if force or before[block.model_addr] != target[block.model_addr]:
            consent = protocol.WriteConsent(
                path_key="set-model", confirmed_by_user=True
            )
            planned.append(
                (
                    protocol.cmd_write_byte(
                        block.model_addr, target[block.model_addr], consent=consent
                    ),
                    "set-model",
                    f"{block.name} model {target[block.model_addr]}",
                )
            )
            model_changed.add(block.key)

    for block in protocol.BLOCKS:
        for slot1 in range(1, 7):
            addr = block.knob_addr(slot1)
            old = int.from_bytes(before[addr : addr + 2], "little")
            new = int.from_bytes(target[addr : addr + 2], "little")
            if force or old != new or block.key in model_changed:
                consent = protocol.WriteConsent(
                    path_key="set-knob", confirmed_by_user=True
                )
                planned.append(
                    (
                        protocol.cmd_write_u16(addr, new, consent=consent),
                        "set-knob",
                        f"{block.name} knob {slot1}={new}",
                    )
                )

    for block in protocol.BLOCKS:
        if force or before[block.toggle_addr] != target[block.toggle_addr]:
            consent = protocol.WriteConsent(
                path_key="set-toggle", confirmed_by_user=True
            )
            planned.append(
                (
                    protocol.cmd_write_byte(
                        block.toggle_addr, target[block.toggle_addr], consent=consent
                    ),
                    "set-toggle",
                    f"{block.name} {'on' if target[block.toggle_addr] else 'off'}",
                )
            )

    before_route = list(before[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6])
    target_route = list(target[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6])
    if force or before_route != target_route:
        consent = protocol.WriteConsent(path_key="set-routing", confirmed_by_user=True)
        planned.append(
            (
                protocol.cmd_write_routing(target_route, consent=consent),
                "set-routing",
                f"routing {target_route}",
            )
        )

    old_volume = int.from_bytes(before[0:2], "little")
    new_volume = int.from_bytes(target[0:2], "little")
    if force or old_volume != new_volume:
        consent = protocol.WriteConsent(path_key="set-knob", confirmed_by_user=True)
        planned.append(
            (
                protocol.cmd_write_u16(0, new_volume, consent=consent),
                "set-knob",
                f"patch volume {new_volume}",
            )
        )
    return planned


def _write_live_image(
    device: Any,
    before: bytes,
    target: bytes,
    label: str,
    *,
    force: bool = False,
    continue_on_error: bool = False,
    errors: list[BaseException] | None = None,
) -> list[str]:
    """Apply a preflighted RAM image in firmware-safe order."""
    planned = _plan_live_image_writes(before, target, force=force)
    operations: list[str] = []
    for raw, path_key, detail in planned:
        consent = protocol.WriteConsent(
            path_key=path_key, confirmed_by_user=True, accept_unverified=False
        )
        try:
            device.write_and_wait_ack(raw, label=f"{label}: {detail}", consent=consent)
        except BaseException as exc:  # includes Ctrl-C after send
            if not continue_on_error:
                raise
            if errors is not None:
                errors.append(exc)
            continue
        operations.append(detail)
    return operations


def cmd_device_load(args: argparse.Namespace, out: Out) -> int:
    index0 = args.slot - 1
    try:
        protocol.check_preset_index(index0)
    except ValueError as exc:
        return _fail(out, str(exc))
    if not args.yes:
        out.line(
            f"DRY RUN. Would load P{args.slot:02d} into live RAM; flash is "
            "not changed. Unsaved live edits would be discarded."
        )
        out.data(dry_run=True, slot=args.slot)
        return EXIT_OK
    try:
        from . import transport

        consent = protocol.WriteConsent(path_key="load-preset", confirmed_by_user=True)
        with transport.open_device() as device:
            expected = device.read_memory(
                index0 * protocol.PRESET_SIZE,
                protocol.PRESET_SIZE,
                label=f"load P{args.slot:02d} expected",
            ).payload
            raw = protocol.cmd_load_preset(index0, consent=consent)
            transfer_error: BaseException | None = None
            try:
                device.write_and_wait_ack(
                    raw, label=f"load P{args.slot:02d}", consent=consent
                )
            except BaseException as exc:  # noqa: BLE001 - reconcile after send/Ctrl-C
                transfer_error = exc
            try:
                active = device.read_memory(
                    protocol.ADDR_CURRENT_PRESET, 4, label="load active read-back"
                ).payload[0]
                observed = device.read_memory(
                    protocol.ADDR_LIVE_RAM,
                    protocol.PRESET_SIZE,
                    label="load RAM read-back",
                ).payload
            except BaseException as reconcile_error:
                if isinstance(transfer_error, KeyboardInterrupt):
                    print(
                        f"interrupted: P{args.slot:02d} load state is uncertain; "
                        f"reconciliation failed ({reconcile_error})",
                        file=sys.stderr,
                    )
                    raise transfer_error from reconcile_error
                if transfer_error is not None:
                    raise RuntimeError(
                        f"load transfer failed ({transfer_error}); reconciliation "
                        f"failed ({reconcile_error})"
                    ) from transfer_error
                raise
            if active != index0 or observed != expected:
                if isinstance(transfer_error, KeyboardInterrupt):
                    print(
                        f"interrupted: P{args.slot:02d} was not verified as loaded "
                        f"(active={active}, RAM_match={observed == expected})",
                        file=sys.stderr,
                    )
                    raise transfer_error
                raise RuntimeError(
                    f"load verification failed"
                    f"{f' after transfer error ({transfer_error})' if transfer_error else ''}: "
                    f"active={active}, "
                    f"RAM_match={observed == expected}"
                )
            if isinstance(transfer_error, KeyboardInterrupt):
                print(
                    f"interrupted: P{args.slot:02d} was loaded and exactly verified "
                    "before cancellation was delivered",
                    file=sys.stderr,
                )
                raise transfer_error
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    reconciled = transfer_error is not None
    suffix = " (missing ACK reconciled by active/RAM read-back)" if reconciled else ""
    out.line(f"loaded and verified P{args.slot:02d}; flash unchanged{suffix}")
    out.data(
        slot=args.slot,
        active_index0=active,
        image_sha256=backups.sha256(observed),
        transfer_reconciled=reconciled,
    )
    return EXIT_OK


def cmd_device_audition(args: argparse.Namespace, out: Out) -> int:
    try:
        target = presetfiles.load_image(Path(args.image))
    except presetfiles.PresetSpecError as exc:
        return _fail(out, str(exc))
    if not args.yes:
        out.line(
            "DRY RUN. Would apply the 92-byte image to live RAM and verify "
            "it. No preset would be saved."
        )
        out.data(dry_run=True, image_sha256=backups.sha256(target))
        return EXIT_OK
    try:
        from . import transport

        with transport.open_device() as device:
            before = device.read_memory(
                protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE, label="audition baseline"
            ).payload
            try:
                operations = _write_live_image(device, before, target, "audition")
                observed = device.read_memory(
                    protocol.ADDR_LIVE_RAM,
                    protocol.PRESET_SIZE,
                    label="audition read-back",
                ).payload
                if observed != target:
                    raise RuntimeError("audition image did not read back exactly")
            except BaseException as failure:
                # A timeout can happen after the pedal accepted an earlier
                # frame. Reconstruct every known field from the saved baseline,
                # even when reading the partially changed RAM also fails.
                try:
                    try:
                        current = device.read_memory(
                            protocol.ADDR_LIVE_RAM,
                            protocol.PRESET_SIZE,
                            label="audition failure reconciliation",
                        ).payload
                        force = False
                    except BaseException:  # noqa: BLE001 - continue after Ctrl-C
                        current = target
                        force = True
                    rollback_errors: list[BaseException] = []
                    _write_live_image(
                        device,
                        current,
                        before,
                        "audition rollback",
                        force=force,
                        continue_on_error=True,
                        errors=rollback_errors,
                    )
                    restored = device.read_memory(
                        protocol.ADDR_LIVE_RAM,
                        protocol.PRESET_SIZE,
                        label="audition rollback read-back",
                    ).payload
                except BaseException as rollback_error:  # noqa: BLE001
                    raise RuntimeError(
                        f"audition failed ({failure}); rollback FAILED "
                        f"({rollback_error})"
                    ) from failure
                if restored != before:
                    raise RuntimeError(
                        f"audition failed ({failure}); rollback FAILED exact "
                        "92-byte verification"
                    ) from failure
                cancellation = next(
                    (
                        error
                        for error in [failure, *rollback_errors]
                        if isinstance(error, KeyboardInterrupt)
                    ),
                    None,
                )
                if cancellation is not None:
                    if cancellation is failure:
                        raise
                    raise cancellation from failure
                raise RuntimeError(
                    f"audition failed ({failure}); rollback succeeded"
                ) from failure
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(
        f"audition image applied and verified in RAM ({len(operations)} writes); "
        "not saved"
    )
    out.data(image_sha256=backups.sha256(target), writes=len(operations), saved=False)
    return EXIT_OK


def _default_rollback_path(slot1: int) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return (
        Path.home()
        / ".local"
        / "share"
        / "blackboxctl"
        / "rollback"
        / f"P{slot1:02d}-before-{stamp}.bin"
    )


@contextmanager
def _defer_keyboard_interrupt():
    """Finish one tiny recovery-evidence update before delivering Ctrl-C."""
    interrupted = False
    previous = signal.getsignal(signal.SIGINT)

    def remember_interrupt(_signum: int, _frame: Any) -> None:
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, remember_interrupt)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
    if interrupted:
        raise KeyboardInterrupt


def _write_rollback_image(path: Path, image: bytes, *, force: bool) -> None:
    """Atomically persist and fsync a mode-0600 raw preset rollback image."""
    try:
        destination = storage.write_bytes_atomic(path, image, replace=force)
    except storage.DestinationExistsError as exc:
        detail = "was created concurrently" if exc.concurrent else "exists"
        raise RuntimeError(f"rollback file {exc.path} {detail}; pass --force") from exc
    if destination.read_bytes() != image:
        raise RuntimeError("rollback file did not read back byte-identically")


def cmd_device_save(args: argparse.Namespace, out: Out) -> int:
    index0 = args.slot - 1
    try:
        protocol.check_preset_index(index0)
        target = presetfiles.load_image(Path(args.image))
    except (ValueError, presetfiles.PresetSpecError) as exc:
        return _fail(out, str(exc))
    if not args.yes:
        out.line(
            f"DRY RUN. Would save {Path(args.image)} to P{args.slot:02d}, "
            "read all 92 bytes back, and keep the incumbent image as a "
            "rollback file."
        )
        out.line("The command refuses to write the currently active slot.")
        out.data(dry_run=True, slot=args.slot, image_sha256=backups.sha256(target))
        return EXIT_OK
    rollback_path = (
        Path(args.rollback_output).expanduser()
        if args.rollback_output
        else _default_rollback_path(args.slot)
    )
    try:
        from . import transport

        with transport.open_device() as device:
            active = device.read_memory(
                protocol.ADDR_CURRENT_PRESET, 4, label="save active preset"
            ).payload[0]
            if active == index0:
                raise RuntimeError(
                    f"P{args.slot:02d} is active; load another slot first so a "
                    "failed save cannot affect the sounding preset"
                )
            address = index0 * protocol.PRESET_SIZE
            original = device.read_memory(
                address, protocol.PRESET_SIZE, label=f"save P{args.slot:02d} original"
            ).payload
            _write_rollback_image(rollback_path, original, force=args.force)
            consent = protocol.WriteConsent(
                path_key="restore", confirmed_by_user=True, allow_flash=True
            )

            def flash(image: bytes, label: str) -> None:
                raw = protocol.cmd_write_flash_preset(index0, image, consent=consent)
                device.write_and_wait_ack(
                    raw, label=label, consent=consent, timeout=5.0
                )

            write_error: BaseException | None = None
            try:
                flash(target, f"save P{args.slot:02d}")
            except BaseException as exc:  # noqa: BLE001 - reconcile after Ctrl-C
                # An ACK can be lost after flash has already changed. Do not
                # decide success/failure until the actual slot is reconciled.
                write_error = exc
            try:
                observed = device.read_memory(
                    address,
                    protocol.PRESET_SIZE,
                    label=f"save P{args.slot:02d} reconciliation",
                    timeout=5.0,
                ).payload
            except BaseException as exc:  # noqa: BLE001 - reconcile after Ctrl-C
                observed = None
                if write_error is None:
                    write_error = exc

            interrupted = isinstance(write_error, KeyboardInterrupt)
            if observed != target or interrupted:
                rollback_error: BaseException | None = None
                if observed != original:
                    try:
                        flash(original, f"rollback P{args.slot:02d}")
                    except BaseException as exc:  # noqa: BLE001 - finish recovery
                        # As above, a missing ACK is not proof that rollback
                        # failed. The read below is authoritative.
                        rollback_error = exc
                try:
                    restored = device.read_memory(
                        address,
                        protocol.PRESET_SIZE,
                        label=f"rollback P{args.slot:02d} reconciliation",
                        timeout=5.0,
                    ).payload
                except BaseException as exc:  # noqa: BLE001 - retain evidence
                    restored = None
                    rollback_error = rollback_error or exc
                if restored != original:
                    raise RuntimeError(
                        f"save target was not verified; rollback FAILED "
                        f"({rollback_error or 'stored bytes differ'})"
                    ) from write_error
                if interrupted:
                    raise write_error
                raise RuntimeError(
                    "save target was not verified; rollback succeeded"
                ) from write_error
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(f"saved and verified P{args.slot:02d}")
    out.line(f"rollback image: {rollback_path}")
    out.data(
        slot=args.slot,
        image_sha256=backups.sha256(target),
        rollback_path=str(rollback_path.resolve()),
        rollback_sha256=backups.sha256(original),
    )
    return EXIT_OK


class CommitUncertain(RuntimeError):
    """A permanent commit may have landed, but read-back could not prove it."""


class CommitInterrupted(KeyboardInterrupt):
    """Ctrl-C arrived at final commit; persistent state was reconciled first."""

    def __init__(self, message: str, *, committed: bool, exact_acks: int) -> None:
        super().__init__(message)
        self.committed = committed
        self.exact_acks = exact_acks


def _send_probed_sequence(
    device: Any,
    frames: Sequence[bytes],
    path_key: str,
    label: str,
    *,
    allow_flash: bool = False,
    reconcile_final: Any = None,
) -> int:
    """Send a sequence, reconciling a lost final ACK when persistent state can."""
    consent = protocol.WriteConsent(
        path_key=path_key,
        confirmed_by_user=True,
        allow_flash=allow_flash,
    )
    exact_acks = 0
    for number, raw in enumerate(frames, start=1):
        # M-EFCS waits about 320 ms after the last 1,015-byte CAB data chunk
        # before sending the activation trigger. The ACK means the transfer was
        # received, not that the DSP has finished ingesting the record.
        if path_key in ("stage-cab", "stage-amp") and number == len(frames):
            time.sleep(0.35)
        if (path_key == "save-cab" and number == 2) or (
            path_key == "save-amp" and number == len(frames)
        ):
            # Captured M-EFCS packets are 17 ms apart. Leave a wider margin so
            # the 20-byte header reaches staging RAM before the commit trigger.
            time.sleep(0.05)
        try:
            device.write_and_wait_ack(
                raw,
                label=f"{label} {number}/{len(frames)}",
                consent=consent,
                timeout=8.0,
            )
            exact_acks += 1
        except BaseException as failure:
            if number != len(frames) or not allow_flash:
                raise
            if reconcile_final is not None:
                try:
                    if reconcile_final():
                        if isinstance(failure, KeyboardInterrupt):
                            raise CommitInterrupted(
                                f"{label}: interrupted after a persistent commit "
                                "that was name-verified",
                                committed=True,
                                exact_acks=exact_acks,
                            ) from failure
                        return exact_acks
                except CommitInterrupted:
                    raise
                except BaseException as reconcile_error:  # noqa: BLE001
                    if isinstance(failure, KeyboardInterrupt):
                        raise CommitInterrupted(
                            f"{label}: interrupted and persistent-state "
                            f"reconciliation failed ({reconcile_error})",
                            committed=False,
                            exact_acks=exact_acks,
                        ) from failure
                    raise CommitUncertain(
                        f"{label}: final ACK was lost and persistent-state "
                        f"reconciliation failed ({reconcile_error})"
                    ) from failure
            if isinstance(failure, KeyboardInterrupt):
                raise CommitInterrupted(
                    f"{label}: interrupted after the final commit frame; "
                    "persistent state is uncertain",
                    committed=False,
                    exact_acks=exact_acks,
                ) from failure
            raise CommitUncertain(
                f"{label}: final ACK was lost; the permanent commit is uncertain"
            ) from failure
    return exact_acks


def _wait_for_library_name(
    device: Any, table_index: int, index0: int, expected: str, timeout: float
) -> list[str]:
    """Poll one persistent AMP/CAB name, retaining the last readable table."""
    deadline = time.monotonic() + timeout
    last_names: list[str] | None = None
    last_error: Exception | None = None
    while True:
        try:
            last_names = _read_name_table(device, table_index)
            if last_names[index0] == expected:
                return last_names
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        if time.monotonic() >= deadline:
            if last_names is not None:
                return last_names
            raise RuntimeError(f"could not read persistent name table: {last_error}")
        time.sleep(0.1)


def _persistent_name_matches(
    device: Any,
    table_index: int,
    index0: int,
    expected: str,
    timeout: float,
) -> bool:
    names = _wait_for_library_name(device, table_index, index0, expected, timeout)
    return names[index0] == expected


@dataclass(frozen=True)
class LibraryCommitTransfer:
    """Wire-level outcome before persistent-name verification."""

    exact_acks: int
    frame_count: int
    table_index: int
    timeout: float

    @property
    def reconciled(self) -> bool:
        return self.exact_acks < self.frame_count


def _transmit_library_commit(
    device: Any,
    *,
    kind: str,
    slot: int,
    name: str,
    record: bytes,
    previous_name: str,
) -> LibraryCommitTransfer:
    """Stage and commit one AMP/CAB record using the shared safe sequence."""
    index0 = slot - 1
    protocol.check_capture_index(index0)
    if kind not in ("amp", "cab"):
        raise ValueError(f"library kind must be 'amp' or 'cab', got {kind!r}")

    table_index = 0 if kind == "amp" else 1
    timeout = 3.0 if kind == "amp" else 2.0
    reconcile = (
        None
        if previous_name == name
        else partial(
            _persistent_name_matches,
            device,
            table_index,
            index0,
            name,
            timeout,
        )
    )

    if kind == "amp":
        consent = protocol.WriteConsent(
            path_key="save-amp",
            confirmed_by_user=True,
            allow_flash=True,
        )
        frames = protocol.cmd_save_amp(index0, record, consent=consent)
        exact_acks = _send_probed_sequence(
            device,
            frames,
            "save-amp",
            f"AMP {slot} save",
            allow_flash=True,
            reconcile_final=reconcile,
        )
    else:
        stage_consent = protocol.WriteConsent(
            path_key="stage-cab",
            confirmed_by_user=True,
        )
        save_consent = protocol.WriteConsent(
            path_key="save-cab",
            confirmed_by_user=True,
            allow_flash=True,
        )
        stage_frames = protocol.cmd_stage_cab(record, consent=stage_consent)
        save_frames = protocol.cmd_save_cab_header(
            index0, record[: protocol.CAB_HEADER_SIZE], consent=save_consent
        )
        stage_acks = _send_probed_sequence(
            device, stage_frames, "stage-cab", f"CAB {slot} stage"
        )
        time.sleep(0.5)
        save_acks = _send_probed_sequence(
            device,
            save_frames,
            "save-cab",
            f"CAB {slot} save",
            allow_flash=True,
            reconcile_final=reconcile,
        )
        frames = stage_frames + save_frames
        exact_acks = stage_acks + save_acks

    return LibraryCommitTransfer(
        exact_acks=exact_acks,
        frame_count=len(frames),
        table_index=table_index,
        timeout=timeout,
    )


def _cab_record_from_args(args: argparse.Namespace) -> bytes:
    return captures.build_cab_record(
        Path(args.file).expanduser(), name=args.name or "", level=args.level
    )


def cmd_device_cab_audition(args: argparse.Namespace, out: Out) -> int:
    try:
        record = _cab_record_from_args(args)
    except (OSError, captures.CaptureEditError) as exc:
        return _fail(out, str(exc))
    chunks = protocol.chunk_library_record(record)
    if not args.yes:
        out.line(
            f"DRY RUN. Would convert {Path(args.file).name} to 2,048 samples, "
            f"upload {len(record)} bytes in {len(chunks)} chunks, and activate "
            "it as the live CAB. No CAB slot would be saved."
        )
        out.data(
            dry_run=True,
            record_bytes=len(record),
            chunks=len(chunks),
            record_sha256=backups.sha256(record),
        )
        return EXIT_OK
    try:
        from . import transport

        consent = protocol.WriteConsent(path_key="stage-cab", confirmed_by_user=True)
        frames = protocol.cmd_stage_cab(record, consent=consent)
        with transport.open_device() as device:
            _require_blackbox_handshake(device, "CAB audition")
            _send_probed_sequence(device, frames, "stage-cab", "CAB audition")
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(
        f"CAB staged and activated: {len(record)} bytes, {len(frames) - 1} "
        "data chunks; not saved to a slot"
    )
    out.data(
        saved=False,
        record_bytes=len(record),
        data_chunks=len(frames) - 1,
        record_sha256=backups.sha256(record),
    )
    return EXIT_OK


def cmd_device_cab_save(args: argparse.Namespace, out: Out) -> int:
    index0 = args.slot - 1
    final_commit_ack_received = False
    persistent_name_verified = False
    try:
        protocol.check_capture_index(index0)
        if not args.name:
            raise captures.CaptureEditError("--name is required when saving a CAB slot")
        record = _cab_record_from_args(args)
    except (ValueError, OSError, captures.CaptureEditError) as exc:
        return _fail(out, str(exc))
    chunks = protocol.chunk_library_record(record)
    if not args.yes:
        out.line(
            f"DRY RUN. Would replace CAB slot {args.slot} with "
            f"{Path(args.file).name} as {args.name!r}: {len(record)} bytes in "
            f"{len(chunks)} chunks, activation, header write, then flash commit."
        )
        out.line(
            "The current slot name is read first, but the device has no known "
            "command for reading the incumbent CAB waveform back for rollback."
        )
        out.data(
            dry_run=True,
            slot=args.slot,
            name=args.name,
            record_bytes=len(record),
            chunks=len(chunks),
            record_sha256=backups.sha256(record),
        )
        return EXIT_OK
    try:
        from . import transport

        with transport.open_device() as device:
            before_names = _read_name_table(device, 1)
            transfer = _transmit_library_commit(
                device,
                kind="cab",
                slot=args.slot,
                name=args.name,
                record=record,
                previous_name=before_names[index0],
            )
            final_commit_ack_received = transfer.exact_acks == transfer.frame_count
            persistent_name_verified = transfer.reconciled
            after_names = _wait_for_library_name(
                device,
                transfer.table_index,
                index0,
                args.name,
                transfer.timeout,
            )
            if after_names[index0] != args.name:
                raise RuntimeError(
                    f"CAB slot name read-back mismatch: expected {args.name!r}, "
                    f"got {after_names[index0]!r}"
                )
            persistent_name_verified = True
    except CommitInterrupted as exc:
        state = (
            "WAS saved and persistent-name verified"
            if exc.committed
            else "may have been saved; state is uncertain"
        )
        print(f"interrupted: CAB slot {args.slot} {state}", file=sys.stderr)
        raise
    except KeyboardInterrupt:
        if persistent_name_verified:
            state = "WAS saved and persistent-name verified"
        elif final_commit_ack_received:
            state = (
                "received the final commit ACK, but its persistent name is unverified"
            )
        else:
            state = "may have been saved; persistent state is uncertain"
        print(
            f"interrupted: CAB slot {args.slot} {state}. Read the persistent "
            "CAB names before retrying.",
            file=sys.stderr,
        )
        raise
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(
        f"CAB slot {args.slot} saved and name-verified: "
        f"{before_names[index0]!r} -> {after_names[index0]!r}"
    )
    out.line(
        f"{transfer.exact_acks}/{transfer.frame_count} transfers received "
        "an exact ACK; a missing final ACK, if any, was reconciled by the "
        "persistent name. The device does not expose CAB-waveform read-back, "
        "so audible verification remains separate."
    )
    out.data(
        slot=args.slot,
        previous_name=before_names[index0],
        name=after_names[index0],
        exact_acks=transfer.exact_acks,
        commit_reconciled=transfer.reconciled,
        record_sha256=backups.sha256(record),
        waveform_readback=False,
    )
    return EXIT_OK


def _amp_record_from_args(args: argparse.Namespace) -> bytes:
    helper = Path(args.dsp_helper).expanduser() if args.dsp_helper else None
    return captures.build_amp_device_record(
        Path(args.file).expanduser(), args.name or "", helper
    )


def cmd_device_amp_audition(args: argparse.Namespace, out: Out) -> int:
    try:
        record = _amp_record_from_args(args)
    except (OSError, captures.CaptureEditError) as exc:
        return _fail(out, str(exc))
    chunks = protocol.chunk_library_record(record)
    if not args.yes:
        out.line(
            f"DRY RUN. Would normalize {Path(args.file).name}, compute the AMP "
            f"runtime block, upload {len(record)} bytes in {len(chunks)} chunks, "
            "and activate it. No AMP slot would be saved."
        )
        out.data(
            dry_run=True,
            record_bytes=len(record),
            chunks=len(chunks),
            record_sha256=backups.sha256(record),
        )
        return EXIT_OK
    try:
        from . import transport

        consent = protocol.WriteConsent(path_key="stage-amp", confirmed_by_user=True)
        frames = protocol.cmd_stage_amp(record, consent=consent)
        with transport.open_device() as device:
            _require_blackbox_handshake(device, "AMP audition")
            _send_probed_sequence(device, frames, "stage-amp", "AMP audition")
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(
        f"AMP staged and activated: {len(record)} bytes, {len(frames) - 1} "
        "data chunks; not saved to a slot"
    )
    out.data(
        saved=False,
        record_bytes=len(record),
        data_chunks=len(frames) - 1,
        record_sha256=backups.sha256(record),
    )
    return EXIT_OK


def cmd_device_amp_save(args: argparse.Namespace, out: Out) -> int:
    index0 = args.slot - 1
    final_commit_ack_received = False
    persistent_name_verified = False
    try:
        protocol.check_capture_index(index0)
        if not args.name:
            raise captures.CaptureEditError(
                "--name is required when saving an AMP slot"
            )
        record = _amp_record_from_args(args)
    except (ValueError, OSError, captures.CaptureEditError) as exc:
        return _fail(out, str(exc))
    chunks = protocol.chunk_library_record(record)
    if not args.yes:
        out.line(
            f"DRY RUN. Would replace AMP slot {args.slot} with "
            f"{Path(args.file).name} as {args.name!r}: {len(record)} bytes in "
            f"{len(chunks)} chunks followed by a flash commit."
        )
        out.line(
            "The current slot name is read first, but the device has no known "
            "command for reading the incumbent neural weights back for rollback."
        )
        out.data(
            dry_run=True,
            slot=args.slot,
            name=args.name,
            record_bytes=len(record),
            chunks=len(chunks),
            record_sha256=backups.sha256(record),
        )
        return EXIT_OK
    try:
        from . import transport

        with transport.open_device() as device:
            before_names = _read_name_table(device, 0)
            transfer = _transmit_library_commit(
                device,
                kind="amp",
                slot=args.slot,
                name=args.name,
                record=record,
                previous_name=before_names[index0],
            )
            final_commit_ack_received = transfer.exact_acks == transfer.frame_count
            persistent_name_verified = transfer.reconciled
            after_names = _wait_for_library_name(
                device,
                transfer.table_index,
                index0,
                args.name,
                transfer.timeout,
            )
            if after_names[index0] != args.name:
                raise RuntimeError(
                    f"AMP slot name read-back mismatch: expected {args.name!r}, "
                    f"got {after_names[index0]!r}"
                )
            persistent_name_verified = True
    except CommitInterrupted as exc:
        state = (
            "WAS saved and persistent-name verified"
            if exc.committed
            else "may have been saved; state is uncertain"
        )
        print(f"interrupted: AMP slot {args.slot} {state}", file=sys.stderr)
        raise
    except KeyboardInterrupt:
        if persistent_name_verified:
            state = "WAS saved and persistent-name verified"
        elif final_commit_ack_received:
            state = (
                "received the final commit ACK, but its persistent name is unverified"
            )
        else:
            state = "may have been saved; persistent state is uncertain"
        print(
            f"interrupted: AMP slot {args.slot} {state}. Read the persistent "
            "AMP names before retrying.",
            file=sys.stderr,
        )
        raise
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(
        f"AMP slot {args.slot} saved and name-verified: "
        f"{before_names[index0]!r} -> {after_names[index0]!r}"
    )
    out.line(
        f"{transfer.exact_acks}/{transfer.frame_count} transfers received an "
        "exact ACK; a missing "
        "final ACK, if any, was reconciled by the persistent name. The device "
        "does not expose neural-weight read-back, so audible verification remains "
        "separate."
    )
    out.data(
        slot=args.slot,
        previous_name=before_names[index0],
        name=after_names[index0],
        exact_acks=transfer.exact_acks,
        commit_reconciled=transfer.reconciled,
        record_sha256=backups.sha256(record),
        weights_readback=False,
    )
    return EXIT_OK


def _default_library_journal_path() -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    unique = uuid4().hex[:12]
    return (
        Path.home()
        / ".local"
        / "share"
        / "blackboxctl"
        / "journal"
        / f"library-apply-{stamp}-{unique}.json"
    )


def _write_library_journal(path: Path, document: dict[str, Any]) -> None:
    """Atomically persist progress after every permanent slot commit."""
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
    storage.write_bytes_atomic(path, payload, replace=True)


def _record_library_uncertain(
    journal: dict[str, Any],
    run_results: list[dict[str, Any]],
    journal_path: Path,
    entry: device_library.PreparedEntry,
    previous_name: str,
    error: BaseException,
) -> None:
    """Durably append one uncertain permanent-library transaction."""
    result = {
        "kind": entry.kind,
        "slot": entry.slot,
        "name": entry.name,
        "previous_name": previous_name,
        "status": "commit-uncertain",
        "record_sha256": entry.sha256,
        "error": str(error),
    }
    journal["results"].append(result)
    run_results.append(result)
    _write_library_journal(journal_path, journal)


class JournalError(RuntimeError):
    """A library-apply journal is unreadable or incompatible with this run."""


def _load_library_journal(path: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Load a compatible resume journal without discarding prior evidence."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise JournalError(f"cannot read resume journal {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise JournalError(f"resume journal {path} is invalid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise JournalError("resume journal root must be an object")
    if document.get("schema") != "blackboxctl.library-apply-journal.v1":
        raise JournalError("resume journal has an unsupported schema")
    if document.get("entries") != entries:
        raise JournalError(
            "resume journal entries do not exactly match this prepared manifest"
        )
    results = document.get("results")
    if not isinstance(results, list) or not all(
        isinstance(result, dict) for result in results
    ):
        raise JournalError("resume journal results are missing or invalid")
    return document


def _journal_verified_records(
    results: Sequence[dict[str, Any]],
) -> set[tuple[Any, Any, Any]]:
    """Return only the latest still-authoritative verification per slot.

    A rewrite attempt supersedes older content evidence. In particular, a
    later ``commit-uncertain`` invalidates an earlier successful save even when
    the persistent name is unchanged. A skip performs no write and therefore
    retains, but never creates, prior evidence.
    """
    latest: dict[tuple[Any, Any], Any | None] = {}
    for result in results:
        key = (result.get("kind"), result.get("slot"))
        status = result.get("status")
        digest = result.get("record_sha256")
        if status == "saved-name-verified":
            latest[key] = digest
        elif status == "skipped-journal-verified":
            if latest.get(key) != digest:
                latest[key] = None
        else:
            # Any attempted or unknown outcome is not positive evidence for the
            # current slot contents. This includes commit-uncertain.
            latest[key] = None
    return {
        (kind, slot, digest)
        for (kind, slot), digest in latest.items()
        if digest is not None
    }


def _cmd_device_library_apply_locked(args: argparse.Namespace, out: Out) -> int:
    """Apply a manifest while the wrapper owns its journal sidecar lock."""
    manifest_path = Path(args.manifest).expanduser().resolve()
    root = (
        Path(args.library_root).expanduser()
        if args.library_root
        else library.DEFAULT_LIBRARY_ROOT
    )
    helper = Path(args.dsp_helper).expanduser() if args.dsp_helper else None
    try:
        entries = device_library.load(
            manifest_path, library_root=root, dsp_helper=helper
        )
    except device_library.ManifestError as exc:
        return _fail(out, str(exc))

    summary = [
        {
            "kind": entry.kind,
            "slot": entry.slot,
            "name": entry.name,
            "source": str(entry.source),
            "source_sha256": entry.source_sha256,
            "record_sha256": entry.sha256,
        }
        for entry in entries
    ]
    if not args.yes:
        out.line(
            f"DRY RUN. Fully prepared {len(entries)} records from "
            f"{manifest_path.name}; no device was opened."
        )
        for entry in entries:
            out.line(
                f"  {entry.kind.upper():3s} {entry.slot:02d}  "
                f"{entry.name:<13s}  {entry.source.name}"
            )
        out.line(
            "Pass --yes to write one slot at a time, verify its name, and "
            "record a resumable journal after every commit."
        )
        out.data(dry_run=True, manifest=str(manifest_path), entries=summary)
        return EXIT_OK

    journal_path = (
        Path(args.journal).expanduser()
        if args.journal
        else _default_library_journal_path()
    )
    journal_path = storage.final_component_path(journal_path)
    if journal_path.is_symlink():
        return _fail(out, f"resume journal path is a symlink: {journal_path}")
    try:
        if journal_path.exists():
            journal = _load_library_journal(journal_path, summary)
            journal.setdefault("resume_events", []).append(
                {
                    "resumed_at": datetime.now().astimezone().isoformat(),
                    "manifest": str(manifest_path),
                }
            )
        else:
            journal = {
                "schema": "blackboxctl.library-apply-journal.v1",
                "started_at": datetime.now().astimezone().isoformat(),
                "manifest": str(manifest_path),
                "entries": summary,
                "results": [],
            }
        _write_library_journal(journal_path, journal)
    except Exception as exc:  # noqa: BLE001
        return _fail(out, str(exc))

    verified = _journal_verified_records(journal["results"])
    run_results: list[dict[str, Any]] = []
    try:
        from . import transport

        with transport.open_device() as device:
            amp_names, cab_names = _read_names(device)
            live_names = {"amp": amp_names, "cab": cab_names}
            for entry in entries:
                index0 = entry.slot - 1
                previous = live_names[entry.kind][index0]
                resume_key = (entry.kind, entry.slot, entry.sha256)
                if (
                    getattr(args, "trust_journal", False)
                    and resume_key in verified
                    and previous == entry.name
                    and not args.rewrite
                ):
                    result = {
                        "kind": entry.kind,
                        "slot": entry.slot,
                        "name": entry.name,
                        "previous_name": previous,
                        "status": "skipped-journal-verified",
                        "record_sha256": entry.sha256,
                    }
                    journal["results"].append(result)
                    run_results.append(result)
                    _write_library_journal(journal_path, journal)
                    out.line(
                        f"skip {entry.kind.upper()} {entry.slot:02d}: "
                        f"same record hash was previously saved and name is "
                        f"still {entry.name!r}"
                    )
                    continue

                try:
                    transfer = _transmit_library_commit(
                        device,
                        kind=entry.kind,
                        slot=entry.slot,
                        name=entry.name,
                        record=entry.record,
                        previous_name=previous,
                    )
                except CommitInterrupted as exc:
                    if exc.committed:
                        result = {
                            "kind": entry.kind,
                            "slot": entry.slot,
                            "name": entry.name,
                            "previous_name": previous,
                            "status": "saved-name-verified",
                            "exact_acks": exc.exact_acks,
                            "commit_reconciled": True,
                            "interrupted": True,
                            "record_sha256": entry.sha256,
                        }
                        journal["results"].append(result)
                        run_results.append(result)
                        _write_library_journal(journal_path, journal)
                    else:
                        _record_library_uncertain(
                            journal, run_results, journal_path, entry, previous, exc
                        )
                    journal["interrupted_at"] = datetime.now().astimezone().isoformat()
                    _write_library_journal(journal_path, journal)
                    raise
                except CommitUncertain as exc:
                    _record_library_uncertain(
                        journal, run_results, journal_path, entry, previous, exc
                    )
                    raise
                except KeyboardInterrupt as exc:
                    # Ctrl-C can arrive after the commit frame was sent. Record
                    # the slot as uncertain before allowing the process to exit.
                    _record_library_uncertain(
                        journal, run_results, journal_path, entry, previous, exc
                    )
                    journal["interrupted_at"] = datetime.now().astimezone().isoformat()
                    _write_library_journal(journal_path, journal)
                    raise

                try:
                    names = _wait_for_library_name(
                        device,
                        transfer.table_index,
                        index0,
                        entry.name,
                        transfer.timeout,
                    )
                except BaseException as exc:
                    uncertain = CommitUncertain(
                        f"{entry.kind.upper()} {entry.slot}: commit ACKed but "
                        f"persistent-name verification failed ({exc})"
                    )
                    _record_library_uncertain(
                        journal,
                        run_results,
                        journal_path,
                        entry,
                        previous,
                        uncertain,
                    )
                    if isinstance(exc, KeyboardInterrupt):
                        raise
                    raise uncertain from exc
                with _defer_keyboard_interrupt():
                    # The commit is already persistent here. Defer Ctrl-C from
                    # the final value check through the atomic journal fsync so
                    # resume cannot lose a slot that was successfully verified.
                    observed = names[index0]
                    if observed != entry.name:
                        uncertain = CommitUncertain(
                            f"{entry.kind.upper()} {entry.slot}: name read-back "
                            f"mismatch; expected {entry.name!r}, got {observed!r}"
                        )
                        _record_library_uncertain(
                            journal,
                            run_results,
                            journal_path,
                            entry,
                            previous,
                            uncertain,
                        )
                        raise uncertain
                    live_names[entry.kind] = names
                    result = {
                        "kind": entry.kind,
                        "slot": entry.slot,
                        "name": entry.name,
                        "previous_name": previous,
                        "status": "saved-name-verified",
                        "exact_acks": transfer.exact_acks,
                        "commit_reconciled": transfer.reconciled,
                        "record_sha256": entry.sha256,
                    }
                    journal["results"].append(result)
                    run_results.append(result)
                    _write_library_journal(journal_path, journal)
                    out.line(
                        f"saved {entry.kind.upper()} {entry.slot:02d}: "
                        f"{previous!r} -> {entry.name!r}"
                    )
    except Exception as exc:  # noqa: BLE001
        journal["failed_at"] = datetime.now().astimezone().isoformat()
        journal["error"] = str(exc)
        _write_library_journal(journal_path, journal)
        out.line(f"journal: {journal_path}")
        return _device_error(out, exc)

    journal["completed_at"] = datetime.now().astimezone().isoformat()
    _write_library_journal(journal_path, journal)
    saved = sum(r["status"] == "saved-name-verified" for r in run_results)
    skipped = len(run_results) - saved
    out.line(f"library apply complete: {saved} saved, {skipped} skipped")
    out.line(f"journal: {journal_path}")
    out.data(
        saved=saved,
        skipped=skipped,
        journal=str(journal_path.resolve()),
        results=run_results,
    )
    return EXIT_OK


def _library_journal_lock_path(journal_path: Path) -> Path:
    return journal_path.with_name(f"{journal_path.name}.lock")


def cmd_device_library_apply(args: argparse.Namespace, out: Out) -> int:
    """Preflight and apply a complete AMP/CAB manifest with a resume journal."""
    if not args.yes:
        return _cmd_device_library_apply_locked(args, out)

    journal_path = (
        Path(args.journal).expanduser()
        if args.journal
        else _default_library_journal_path()
    )
    journal_path = storage.final_component_path(journal_path)
    if journal_path.is_symlink():
        return _fail(out, f"resume journal path is a symlink: {journal_path}")
    # Feed the exact path chosen here to the implementation. The sidecar lock
    # is acquired before the journal is read and held through the final fsync,
    # so a losing process can never rewrite a stale snapshot after failing the
    # device lock.
    args.journal = str(journal_path)
    try:
        with storage.exclusive_lock(_library_journal_lock_path(journal_path)):
            return _cmd_device_library_apply_locked(args, out)
    except storage.LockUnavailableError as exc:
        return _fail(
            out,
            f"resume journal is already in use; refusing a stale concurrent "
            f"writer ({exc})",
        )


def cmd_device_probe_amp_gain(args: argparse.Namespace, out: Out) -> int:
    """Prove the live-RAM write address with a one-count reversible gain change."""
    if not args.yes:
        out.line(
            "DRY RUN. This would change live AMP Gain by one count, read it "
            "back, then restore its original value. It never saves a preset."
        )
        out.line(
            "Pass --yes only when the pedal is connected and you accept this "
            "unverified, reversible RAM-write probe."
        )
        out.data(dry_run=True, target="live RAM AMP Gain @0x20")
        return EXIT_OK
    try:
        from . import transport

        with transport.open_device() as device:
            before = device.read_memory(
                protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE, label="probe before"
            )
            original = int.from_bytes(before.payload[0x20:0x22], "little")
            consent = protocol.WriteConsent(
                path_key="set-knob", confirmed_by_user=True, accept_unverified=True
            )
            try:
                protocol.cmd_write_u16(0x20, original, consent=consent)
            except (TypeError, ValueError, protocol.UnsafePacket) as exc:
                raise RuntimeError(
                    "live AMP Gain baseline is not safely restorable; refusing "
                    f"the probe before any write ({exc})"
                ) from exc
            candidate = original + 1 if original < 100 else original - 1
            failure: BaseException | None = None
            try:
                raw = protocol.cmd_write_u16(0x20, candidate, consent=consent)
                device.write_and_wait_ack(
                    raw, label="probe AMP Gain +1", consent=consent
                )
                changed = device.read_memory(
                    protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE, label="probe changed"
                ).payload
                observed = int.from_bytes(changed[0x20:0x22], "little")
                if observed != candidate:
                    raise RuntimeError("probe candidate did not read back")
            except BaseException as exc:  # noqa: BLE001 - restore after Ctrl-C
                failure = exc
            finally:
                try:
                    try:
                        current = device.read_memory(
                            protocol.ADDR_LIVE_RAM,
                            protocol.PRESET_SIZE,
                            label="probe pre-restore",
                        ).payload
                    except BaseException:  # noqa: BLE001 - continue restoration
                        current = None
                    restore_error: BaseException | None = None
                    if current != before.payload:
                        try:
                            restore_raw = protocol.cmd_write_u16(
                                0x20, original, consent=consent
                            )
                            device.write_and_wait_ack(
                                restore_raw,
                                label="probe restore AMP Gain",
                                consent=consent,
                            )
                        except BaseException as exc:  # noqa: BLE001
                            restore_error = exc
                    restored = device.read_memory(
                        protocol.ADDR_LIVE_RAM,
                        protocol.PRESET_SIZE,
                        label="probe restored",
                    ).payload
                    final = int.from_bytes(restored[0x20:0x22], "little")
                    if restored != before.payload:
                        raise RuntimeError(
                            f"probe rollback FAILED ({restore_error or 'RAM differs'})"
                        )
                except BaseException as rollback_error:  # noqa: BLE001
                    raise RuntimeError(
                        f"probe failed ({failure}); rollback FAILED ({rollback_error})"
                    ) from failure
            cancellation = next(
                (
                    error
                    for error in (failure, restore_error)
                    if isinstance(error, KeyboardInterrupt)
                ),
                None,
            )
            if cancellation is not None:
                raise cancellation
            if failure is not None:
                raise RuntimeError(
                    f"probe failed ({failure}); rollback succeeded"
                ) from failure
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)
    out.line(
        f"probe passed: AMP Gain {original} -> {candidate} -> {final}; "
        "no preset was saved"
    )
    out.data(
        probe="set-knob",
        address="0x20",
        original=original,
        candidate=candidate,
        restored=final,
    )
    return EXIT_OK


def cmd_device_probe_live(args: argparse.Namespace, out: Out) -> int:
    """Validate every reversible live-write path and restore every byte."""
    if not args.yes:
        out.line(
            "DRY RUN. This validates ACK, knob, toggle, model, routing and an "
            "idempotent reload of the active preset. Every test reads back "
            "the result and restores the original 92-byte RAM image."
        )
        out.line("Pass --yes only with the pedal connected. No preset is saved.")
        out.data(
            dry_run=True,
            paths=["set-knob", "set-toggle", "set-model", "set-routing", "load-preset"],
        )
        return EXIT_OK

    results: list[dict[str, Any]] = []
    try:
        from . import transport

        with transport.open_device() as device:

            def read_ram(label: str) -> bytes:
                return device.read_memory(
                    protocol.ADDR_LIVE_RAM, protocol.PRESET_SIZE, label=label
                ).payload

            baseline = read_ram("live-probe baseline")
            try:
                _plan_live_image_writes(baseline, baseline, force=True)
            except (TypeError, ValueError, protocol.UnsafePacket) as exc:
                raise RuntimeError(
                    "live-probe baseline is not fully restorable; refusing all "
                    f"probe writes ({exc})"
                ) from exc

            def transaction(
                path_key: str, candidate: bytes, verify: Any, label: str
            ) -> None:
                nonlocal baseline
                consent = protocol.WriteConsent(
                    path_key=path_key, confirmed_by_user=True, accept_unverified=True
                )

                def send_one(raw: bytes, suffix: str) -> None:
                    path = protocol.WRITE_PATHS[path_key]
                    probe = (
                        None
                        if path.hardware_confirmed
                        else protocol.WriteProbe.for_frame(path_key, raw)
                    )
                    device.write_and_wait_ack(
                        raw, label=f"{label} {suffix}", consent=consent, probe=probe
                    )

                failure: BaseException | None = None
                try:
                    send_one(candidate, "candidate")
                    observed = read_ram(f"{label} changed")
                    if not verify(observed):
                        raise RuntimeError(f"{label}: candidate did not read back")
                except BaseException as exc:  # noqa: BLE001 - restore after Ctrl-C
                    failure = exc
                finally:
                    rollback_errors: list[BaseException] = []
                    try:
                        try:
                            current = read_ram(f"{label} pre-restore")
                            force = False
                        except BaseException:  # noqa: BLE001 - continue restoration
                            current = baseline
                            force = True
                        if current != baseline or force:
                            _write_live_image(
                                device,
                                current,
                                baseline,
                                f"{label} baseline rollback",
                                force=force,
                                continue_on_error=True,
                                errors=rollback_errors,
                            )
                        restored = read_ram(f"{label} restored")
                        if restored != baseline:
                            raise RuntimeError(
                                f"{label}: restoration did not return all 92 RAM "
                                "bytes to the baseline; stop writing"
                            )
                    except BaseException as rollback_error:  # noqa: BLE001
                        raise RuntimeError(
                            f"{label}: operation failed ({failure}); rollback "
                            f"FAILED ({rollback_error})"
                        ) from failure
                cancellation = next(
                    (
                        error
                        for error in [failure, *rollback_errors]
                        if isinstance(error, KeyboardInterrupt)
                    ),
                    None,
                )
                if cancellation is not None:
                    raise cancellation
                if failure is not None:
                    raise RuntimeError(
                        f"{label}: operation failed ({failure}); rollback succeeded"
                    ) from failure
                results.append({"path": path_key, "label": label, "restored": True})
                baseline = read_ram(f"{label} final baseline")

            # Confirm the compact ACK on the already-proven knob address.
            amp = protocol.BLOCKS_BY_KEY["amp"]
            knob_addr = amp.knob_addr(1)
            original_knob = int.from_bytes(
                baseline[knob_addr : knob_addr + 2], "little"
            )
            candidate_knob = original_knob + 1 if original_knob < 100 else 99
            knob_consent = protocol.WriteConsent(
                path_key="set-knob", confirmed_by_user=True, accept_unverified=True
            )
            transaction(
                "set-knob",
                protocol.cmd_write_u16(knob_addr, candidate_knob, consent=knob_consent),
                lambda image: (
                    int.from_bytes(image[knob_addr : knob_addr + 2], "little")
                    == candidate_knob
                ),
                "AMP Gain ACK probe",
            )

            mod = protocol.BLOCKS_BY_KEY["mod"]
            original_toggle = baseline[mod.toggle_addr]
            candidate_toggle = 0 if original_toggle else 1
            toggle_consent = protocol.WriteConsent(
                path_key="set-toggle", confirmed_by_user=True, accept_unverified=True
            )
            transaction(
                "set-toggle",
                protocol.cmd_write_byte(
                    mod.toggle_addr, candidate_toggle, consent=toggle_consent
                ),
                lambda image: image[mod.toggle_addr] == candidate_toggle,
                "MOD toggle probe",
            )

            original_model = baseline[mod.model_addr]
            candidate_model = (original_model + 1) % len(mod.models)
            model_consent = protocol.WriteConsent(
                path_key="set-model", confirmed_by_user=True, accept_unverified=True
            )

            transaction(
                "set-model",
                protocol.cmd_write_byte(
                    mod.model_addr, candidate_model, consent=model_consent
                ),
                lambda image: image[mod.model_addr] == candidate_model,
                "MOD model probe",
            )

            original_route = list(
                baseline[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6]
            )
            candidate_route = list(original_route)
            candidate_route[0], candidate_route[1] = (
                candidate_route[1],
                candidate_route[0],
            )
            routing_consent = protocol.WriteConsent(
                path_key="set-routing", confirmed_by_user=True, accept_unverified=True
            )
            transaction(
                "set-routing",
                protocol.cmd_write_routing(candidate_route, consent=routing_consent),
                lambda image: (
                    list(image[protocol.ADDR_ROUTING : protocol.ADDR_ROUTING + 6])
                    == candidate_route
                ),
                "routing probe",
            )

            active = device.read_memory(
                protocol.ADDR_CURRENT_PRESET, 4, label="load-probe active preset"
            ).payload[0]
            stored = device.read_memory(
                protocol.ADDR_PRESET_BASE + active * protocol.PRESET_SIZE,
                protocol.PRESET_SIZE,
                label="load-probe stored preset",
            ).payload
            baseline = read_ram("load-probe RAM comparison")
            if stored != baseline:
                raise RuntimeError(
                    "active live RAM differs from its saved slot; refusing the "
                    "load-preset probe because it would discard unsaved edits"
                )
            load_consent = protocol.WriteConsent(
                path_key="load-preset", confirmed_by_user=True
            )
            expected = bytes(baseline)
            transaction(
                "load-preset",
                protocol.cmd_load_preset(active, consent=load_consent),
                lambda image: image == expected,
                f"idempotent P{active + 1:02d} reload",
            )
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)

    out.line("live-write probe passed; RAM is byte-identical to its baseline")
    for result in results:
        out.line(f"  {result['path']:<12s} ACK + read-back + restore")
    out.data(paths=results, ram_restored=True)
    return EXIT_OK


def cmd_device_probe_flash(args: argparse.Namespace, out: Out) -> int:
    """Prove preset flash write/read/restore on inactive P80 only."""
    target_index0 = protocol.PRESET_COUNT - 1
    target_slot1 = target_index0 + 1
    if not args.yes:
        out.line(
            f"DRY RUN. This writes one changed patch-volume value to "
            f"P{target_slot1:02d}, reads all 92 bytes back, then writes and "
            "verifies the original 92 bytes from the device."
        )
        out.line(
            "It refuses to run if P80 is active. A full device backup should "
            "exist before --yes."
        )
        out.data(
            dry_run=True, target_slot=target_slot1, writes=2, requires_inactive=True
        )
        return EXIT_OK

    candidate_verified = False
    restored_verified = False
    original = b""
    rollback_path = (
        Path(args.rollback_output).expanduser()
        if args.rollback_output
        else _default_rollback_path(80)
    )
    try:
        from . import transport

        with transport.open_device() as device:
            active_before = device.read_memory(
                protocol.ADDR_CURRENT_PRESET, 4, label="flash-probe active before"
            ).payload[0]
            if active_before == target_index0:
                raise RuntimeError(
                    "P80 is active; switch to another preset before this probe"
                )
            live_before = device.read_memory(
                protocol.ADDR_LIVE_RAM,
                protocol.PRESET_SIZE,
                label="flash-probe live before",
            ).payload
            target_address = target_index0 * protocol.PRESET_SIZE
            original = device.read_memory(
                target_address, protocol.PRESET_SIZE, label="flash-probe P80 original"
            ).payload
            _write_rollback_image(rollback_path, original, force=args.force)
            candidate = bytearray(original)
            volume = int.from_bytes(candidate[0:2], "little")
            candidate_volume = volume + 1 if volume < 100 else 99
            candidate[0:2] = candidate_volume.to_bytes(2, "little")
            candidate = bytes(candidate)
            consent = protocol.WriteConsent(
                path_key="restore",
                confirmed_by_user=True,
                accept_unverified=True,
                allow_flash=True,
            )

            def write_image(image: bytes, label: str) -> None:
                raw = protocol.cmd_write_flash_preset(
                    target_index0, image, consent=consent
                )
                device.write_and_wait_ack(
                    raw,
                    label=label,
                    consent=consent,
                    probe=protocol.WriteProbe.for_frame("restore", raw),
                    timeout=5.0,
                )

            failure: BaseException | None = None
            try:
                write_image(candidate, "P80 flash candidate")
                observed = device.read_memory(
                    target_address,
                    protocol.PRESET_SIZE,
                    label="flash-probe P80 candidate read-back",
                    timeout=5.0,
                ).payload
                if observed != candidate:
                    raise RuntimeError(
                        "P80 candidate write ACKed but 92-byte read-back differs"
                    )
                candidate_verified = True
            except BaseException as exc:  # noqa: BLE001 - restore after Ctrl-C
                failure = exc
            finally:
                # Even an ACK timeout may have completed the flash write.
                try:
                    current = device.read_memory(
                        target_address,
                        protocol.PRESET_SIZE,
                        label="flash-probe P80 pre-restore",
                        timeout=5.0,
                    ).payload
                except BaseException as exc:  # noqa: BLE001 - continue restoration
                    current = None
                    failure = failure or exc
                rollback_error: BaseException | None = None
                if current != original:
                    try:
                        write_image(original, "P80 flash original restore")
                    except BaseException as exc:  # noqa: BLE001
                        rollback_error = exc
                try:
                    restored = device.read_memory(
                        target_address,
                        protocol.PRESET_SIZE,
                        label="flash-probe P80 restored read-back",
                        timeout=5.0,
                    ).payload
                except BaseException as exc:  # noqa: BLE001 - retain evidence
                    restored = None
                    rollback_error = rollback_error or exc
                restored_verified = restored == original
                if not restored_verified:
                    raise RuntimeError(
                        "CRITICAL: P80 did not return to its original 92-byte "
                        f"image ({rollback_error or 'stored bytes differ'}); stop "
                        f"all device writes and restore {rollback_path}"
                    )
            cancellation = next(
                (
                    error
                    for error in (failure, rollback_error)
                    if isinstance(error, KeyboardInterrupt)
                ),
                None,
            )
            if cancellation is not None:
                raise cancellation
            if failure is not None:
                raise failure
            active_after = device.read_memory(
                protocol.ADDR_CURRENT_PRESET, 4, label="flash-probe active after"
            ).payload[0]
            live_after = device.read_memory(
                protocol.ADDR_LIVE_RAM,
                protocol.PRESET_SIZE,
                label="flash-probe live after",
            ).payload
            if active_after != active_before or live_after != live_before:
                raise RuntimeError(
                    "P80 flash probe unexpectedly changed the active preset or "
                    "live RAM, although P80 itself was restored"
                )
    except Exception as exc:  # noqa: BLE001
        return _device_error(out, exc)

    out.line(
        "flash probe passed: P80 candidate saved/read back, then original "
        "saved/read back; active preset and live RAM unchanged"
    )
    out.data(
        path="restore",
        slot=target_slot1,
        candidate_verified=candidate_verified,
        restored_verified=restored_verified,
        original_sha256=backups.sha256(original),
        rollback_path=str(rollback_path.resolve()),
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="blackboxctl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Read and manage an M-Vave BlackBox and its M-EFCS library. "
        "Permanent writes are dry-run by default, explicitly confirmed, "
        "and verified after each operation.",
        epilog=(
            "Examples:\n"
            "  blackboxctl doctor\n"
            "  blackboxctl backup extract-all backup.json ./presets\n"
            "  blackboxctl device names\n"
            "  blackboxctl write-paths\n"
            "\n"
            "GPL-3.0. Protocol reverse engineered by Joel Victor "
            "(github.com/jvsobrinho/mvave-blackbox-ble, CC BY-SA 4.0). "
            "See NOTICE."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"blackboxctl {__version__}"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit one JSON document instead of text"
    )
    parser.add_argument(
        "--library-root",
        default=None,
        help=f"M-EFCS library root (default: {library.DEFAULT_LIBRARY_ROOT})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("selftest", help="offline protocol self-test; touches nothing")
    p.set_defaults(func=cmd_selftest)

    p = sub.add_parser(
        "doctor",
        help="report host, protocol, MIDI, and M-EFCS readiness; writes nothing",
    )
    p.add_argument(
        "--require-device",
        action="store_true",
        help="exit 3 unless a BlackBox MIDI pair is ready",
    )
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser(
        "write-paths", help="list state-changing commands and their safeguards"
    )
    p.set_defaults(func=cmd_write_paths)

    p = sub.add_parser("inspect", help="parse and validate capture / IR files")
    p.add_argument("files", nargs="+")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("rename", help="edit a capture file's header name / magic")
    p.add_argument("file")
    p.add_argument(
        "name",
        nargs="?",
        default=None,
        help="new name, at most 13 printable ASCII characters",
    )
    p.add_argument(
        "--in-place", action="store_true", help="rewrite the file itself (needs --yes)"
    )
    p.add_argument("--output", default=None, help="write a copy here instead")
    p.add_argument(
        "--repair-magic",
        action="store_true",
        help="set the AM prefix on a 00 00 32/33 00 magic, keeping the version digit",
    )
    p.add_argument("--yes", action="store_true", help="actually write")
    p.add_argument(
        "--force", action="store_true", help="overwrite an existing output or .bak"
    )
    p.set_defaults(func=cmd_rename)

    p = sub.add_parser("decode", help="decode a 92-byte preset image offline")
    p.add_argument("file", nargs="?", default=None)
    p.add_argument("--hex", default=None, help="the image as hex instead")
    p.add_argument("--amp-names", nargs="*", default=None)
    p.add_argument("--cab-names", nargs="*", default=None)
    p.set_defaults(func=cmd_decode)

    bak = sub.add_parser("backup", help="verify or extract a device backup")
    baksub = bak.add_subparsers(dest="subcommand", required=True)

    p = baksub.add_parser("verify", help="verify all checksums and required slots")
    p.add_argument("file")
    p.set_defaults(func=cmd_backup_verify)

    p = baksub.add_parser("extract", help="extract one raw 92-byte preset image")
    p.add_argument("file")
    p.add_argument("slot", type=int, help="1-based P01..P80")
    p.add_argument("output")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_backup_extract)

    p = baksub.add_parser(
        "extract-all", help="extract all 80 raw 92-byte preset images"
    )
    p.add_argument("file")
    p.add_argument("output", help="directory for P01.bin .. P80.bin")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_backup_extract_all)

    pre = sub.add_parser("preset", help="build declarative 92-byte preset images")
    presub = pre.add_subparsers(dest="subcommand", required=True)

    p = presub.add_parser("export", help="export a base image as editable JSON")
    p.add_argument("image")
    p.add_argument("output")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_preset_export)

    p = presub.add_parser("render", help="apply a JSON spec to a base image")
    p.add_argument("base")
    p.add_argument("spec")
    p.add_argument("output")
    p.add_argument(
        "--yes", action="store_true", help="write the rendered 92-byte image"
    )
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_preset_render)

    lib = sub.add_parser("library", help="the M-EFCS on-disk capture/IR library")
    libsub = lib.add_subparsers(dest="subcommand", required=True)

    p = libsub.add_parser("list", help="list installed captures and IRs")
    p.add_argument("--kind", choices=("capture", "ir"), default=None)
    p.add_argument("--filter", default=None)
    p.set_defaults(func=cmd_library_list)

    p = libsub.add_parser("diff", help="compare presets/library.md's slot maps to disk")
    p.add_argument("--doc", default=None)
    p.set_defaults(func=cmd_library_diff)

    p = libsub.add_parser(
        "install",
        help="copy captures/IRs into the M-EFCS library (DRY RUN unless --yes)",
    )
    p.add_argument("files", nargs="+")
    p.add_argument(
        "--force",
        action="store_true",
        help="replace an existing file, keeping a timestamped .bak",
    )
    p.add_argument("--yes", action="store_true", help="actually copy")
    p.set_defaults(func=cmd_library_install)

    p = libsub.add_parser(
        "restart-editor",
        help="quit and relaunch M-EFCS so it rescans (DRY RUN unless --yes)",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="actually quit and relaunch; unsaved GUI work is lost",
    )
    p.set_defaults(func=cmd_library_restart)

    dev = sub.add_parser("device", help="inspect the pedal over USB MIDI")
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

    p = devsub.add_parser(
        "backup", help="read and checksum all 80 presets (device remains unchanged)"
    )
    p.add_argument(
        "--output",
        default=None,
        help="JSON path (default: ~/.local/share/blackboxctl/backups/)",
    )
    p.add_argument(
        "--force", action="store_true", help="replace an existing output path"
    )
    p.set_defaults(func=cmd_device_backup)

    p = devsub.add_parser("load", help="load and verify a stored slot in live RAM")
    p.add_argument("slot", type=int, help="1-based P01..P80")
    p.add_argument(
        "--yes",
        action="store_true",
        help="discard unsaved live edits and load the slot",
    )
    p.set_defaults(func=cmd_device_load)

    p = devsub.add_parser(
        "audition", help="apply a 92-byte image to RAM without saving"
    )
    p.add_argument("image")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_device_audition)

    p = devsub.add_parser(
        "save", help="save a 92-byte image to an inactive slot with rollback"
    )
    p.add_argument("slot", type=int, help="1-based P01..P80")
    p.add_argument("image")
    p.add_argument("--rollback-output", default=None)
    p.add_argument(
        "--force", action="store_true", help="replace an existing rollback file"
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="write flash, read back, and preserve the old image",
    )
    p.set_defaults(func=cmd_device_save)

    cab = devsub.add_parser(
        "cab", help="convert, audition, and save cabinet IRs without M-EFCS"
    )
    cabsub = cab.add_subparsers(dest="cab_command", required=True)

    p = cabsub.add_parser(
        "audition", help="convert and activate a WAV in CAB RAM; do not save"
    )
    p.add_argument("file")
    p.add_argument(
        "--name", default="", help="optional record name, at most 13 ASCII characters"
    )
    p.add_argument("--level", type=int, default=50, help="CAB level 0..100")
    p.add_argument(
        "--yes", action="store_true", help="upload and activate the converted CAB"
    )
    p.set_defaults(func=cmd_device_cab_audition)

    p = cabsub.add_parser(
        "save", help="convert a WAV and replace one permanent CAB slot"
    )
    p.add_argument("slot", type=int, help="1-based CAB slot 1..20")
    p.add_argument("file")
    p.add_argument(
        "--name",
        required=True,
        help="stored name, at most 13 printable ASCII characters",
    )
    p.add_argument("--level", type=int, default=50, help="CAB level 0..100")
    p.add_argument(
        "--yes",
        action="store_true",
        help="upload, flash, and verify the target slot name",
    )
    p.set_defaults(func=cmd_device_cab_save)

    amp = devsub.add_parser(
        "amp", help="audition and save neural captures without M-EFCS's GUI"
    )
    ampsub = amp.add_subparsers(dest="amp_command", required=True)

    p = ampsub.add_parser(
        "audition", help="compute, upload, and activate a capture; do not save"
    )
    p.add_argument("file")
    p.add_argument(
        "--name", default="", help="optional record name, at most 13 ASCII characters"
    )
    p.add_argument(
        "--dsp-helper",
        default=None,
        help="path to libamx_parser.dylib (default: installed M-EFCS)",
    )
    p.add_argument(
        "--yes", action="store_true", help="upload and activate the computed AMP"
    )
    p.set_defaults(func=cmd_device_amp_audition)

    p = ampsub.add_parser(
        "save", help="compute a capture and replace one permanent AMP slot"
    )
    p.add_argument("slot", type=int, help="1-based AMP slot 1..20")
    p.add_argument("file")
    p.add_argument(
        "--name",
        required=True,
        help="stored name, at most 13 printable ASCII characters",
    )
    p.add_argument(
        "--dsp-helper",
        default=None,
        help="path to libamx_parser.dylib (default: installed M-EFCS)",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="compute, flash, and verify the target slot name",
    )
    p.set_defaults(func=cmd_device_amp_save)

    p = devsub.add_parser(
        "library-apply",
        help="apply a validated AMP/CAB manifest with per-slot journaling",
    )
    p.add_argument("manifest", help="blackboxctl.device-library.v1 JSON file")
    p.add_argument(
        "--dsp-helper",
        default=None,
        help="path to libamx_parser.dylib (default: installed M-EFCS)",
    )
    p.add_argument(
        "--journal",
        default=None,
        help="progress journal path (default: ~/.local/share/blackboxctl)",
    )
    p.add_argument(
        "--rewrite",
        action="store_true",
        help="explicitly rewrite every slot (the safe default)",
    )
    p.add_argument(
        "--trust-journal",
        action="store_true",
        help=(
            "skip journal-verified hashes whose names still match; unsafe if "
            "M-EFCS or another journal may have overwritten same-name content"
        ),
    )
    p.add_argument(
        "--yes", action="store_true", help="write and verify each permanent slot"
    )
    p.set_defaults(func=cmd_device_library_apply)

    p = devsub.add_parser(
        "probe-amp-gain",
        help="hardware check: reversible live AMP Gain write (DRY RUN unless --yes)",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="change AMP Gain by one, verify, and restore it",
    )
    p.set_defaults(func=cmd_device_probe_amp_gain)

    p = devsub.add_parser(
        "probe-live",
        help="hardware check: reversible live writes (DRY RUN unless --yes)",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="run ACK/read-back/restore probes; never save a preset",
    )
    p.set_defaults(func=cmd_device_probe_live)

    p = devsub.add_parser(
        "probe-flash",
        help="hardware check: save/read/restore inactive P80 (DRY RUN unless --yes)",
    )
    p.add_argument(
        "--rollback-output", default=None, help="durable original P80 image path"
    )
    p.add_argument(
        "--force", action="store_true", help="replace an existing rollback image"
    )
    p.add_argument(
        "--yes", action="store_true", help="perform two verified P80 flash writes"
    )
    p.set_defaults(func=cmd_device_probe_flash)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = Out(as_json=args.json)
    try:
        code = args.func(args, out)
    except KeyboardInterrupt:
        code = 130
        out.error("interrupted")
    except Exception as exc:  # noqa: BLE001 - keep --json as one document
        code = _device_error(out, exc)
    out.flush(code)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
