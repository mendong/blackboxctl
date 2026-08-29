"""The M-EFCS on-disk library: listing, installing, and diffing against the plan.

M-EFCS is sandboxed and keeps no index file. It scans ``ampFile`` and ``cabFile``
once at launch, so a file copied in while the app is running does not appear until
the app is restarted. That behaviour is what ``install`` and ``restart-editor``
are built around.

Read-only by default. The only directory this module ever writes to is
``ampFile`` / ``cabFile``, and only for files the user explicitly named. It never
touches ``model/`` (a 114 MB app-internal blob) or the app bundle.

Two functions here have real-world side effects outside this repository, and
both are the actual point of the tool rather than accidents. Read their
docstrings before calling them:

* :func:`install` copies files into another application's sandbox container.
* :func:`restart_editor` quits and relaunches that application, which discards
  its unsaved work. It does nothing without a :class:`RestartConsent`.

GPL-3.0. See ../NOTICE.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import captures, protocol, storage

DEFAULT_LIBRARY_ROOT = Path.home() / (
    "Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS"
)
"""Sandbox container for M-EFCS (bundle id com.digAmp.dgAmp). CONFIRMED."""

AMP_DIR = "ampFile"
CAB_DIR = "cabFile"
DS_DIR = "dsFile"
PROTECTED_DIRS = ("model",)
"""Never written to, never listed, never cleaned. The app owns these."""

MEFCS_BUNDLE_ID = "com.digAmp.dgAmp"


class LibraryError(RuntimeError):
    """A library operation could not be completed."""


@dataclass(frozen=True)
class LibraryEntry:
    """One file present in the M-EFCS library."""

    path: Path
    kind: str  # "capture" or "ir"
    size: int

    @property
    def stem(self) -> str:
        return self.path.stem


@dataclass
class Library:
    """The M-EFCS library on disk."""

    root: Path

    @property
    def amp_dir(self) -> Path:
        return self.root / AMP_DIR

    @property
    def cab_dir(self) -> Path:
        return self.root / CAB_DIR

    @property
    def ds_dir(self) -> Path:
        return self.root / DS_DIR

    def check(self) -> None:
        if not self.root.is_dir():
            raise LibraryError(
                f"M-EFCS library not found at {self.root}. Pass --library-root if "
                f"it lives elsewhere."
            )

    def entries(
        self, kind: str | None = None, text: str | None = None
    ) -> list[LibraryEntry]:
        """List library files, optionally filtered by kind and substring."""
        self.check()
        found: list[LibraryEntry] = []
        for directory, entry_kind in ((self.amp_dir, "capture"), (self.cab_dir, "ir")):
            if kind is not None and kind != entry_kind:
                continue
            if not directory.is_dir():
                continue
            for path in sorted(directory.iterdir()):
                if not path.is_file() or path.name.startswith("."):
                    continue
                if text and text.lower() not in path.name.lower():
                    continue
                found.append(
                    LibraryEntry(path=path, kind=entry_kind, size=path.stat().st_size)
                )
        return found

    def target_dir(self, path: Path) -> Path:
        """Which library directory a given file belongs in."""
        kind = captures.classify(path)
        if kind == "capture":
            directory = self.amp_dir
        elif kind == "ir":
            directory = self.cab_dir
        else:
            raise LibraryError(
                f"{path.name}: not a capture ({', '.join(captures.CAPTURE_SUFFIXES)}) "
                f"or an IR ({', '.join(captures.IR_SUFFIXES)}); refusing to guess "
                f"where it belongs"
            )
        self.check()
        if directory.is_symlink():
            raise LibraryError(
                f"refusing library target symlink {directory}; AMP/CAB files must "
                "stay in the real M-EFCS library directory"
            )
        if not directory.is_dir():
            raise LibraryError(f"M-EFCS library directory not found: {directory}")
        try:
            root = self.root.expanduser().resolve(strict=True)
            resolved = directory.expanduser().resolve(strict=True)
        except OSError as exc:
            raise LibraryError(f"cannot resolve M-EFCS library target: {exc}") from exc
        if resolved.parent != root:
            raise LibraryError(f"refusing library target outside {root}: {resolved}")
        return directory

    def destination_for(self, path: Path) -> Path:
        """Return a confined, non-symlink destination for one source file."""
        destination = self.target_dir(path) / path.name
        if destination.is_symlink():
            raise LibraryError(
                f"refusing destination symlink {destination}; move it aside first"
            )
        return destination


@dataclass
class InstallResult:
    """Outcome of installing one file.

    ``reason`` is only ever a refusal or skip explanation. Parse warnings go in
    ``warnings``, so that "installed" can never be rendered next to text that
    reads like a failure.
    """

    source: Path
    destination: Path
    action: str  # "installed", "replaced", "skipped", "refused"
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    backup: Path | None = None
    """Where the incumbent file was copied before being replaced."""

    def describe(self) -> str:
        """One line, plus one indented line per warning.

        Warnings are on their own labelled lines and never inline after the
        action, so "installed" can never be read as "installed, but ...".
        """
        parts = [f"{self.action:9s} {self.source.name}"]
        if self.reason:
            parts.append(f"({self.reason})")
        if self.backup is not None:
            parts.append(f"[backup {self.backup.name}]")
        line = " ".join(parts)
        if self.warnings:
            line += "\n" + "\n".join(f"          warnings: {w}" for w in self.warnings)
        return line


def backup_path(destination: Path) -> Path:
    """Timestamped sidecar for the file about to be replaced.

    A counter is appended when a backup for the same second already exists, so
    two replacements inside one second cannot silently destroy the first
    backup - which would defeat the whole point of taking one.
    """
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    candidate = destination.with_name(f"{destination.name}.{stamp}.bak")
    counter = 2
    while candidate.exists():
        candidate = destination.with_name(f"{destination.name}.{stamp}-{counter}.bak")
        counter += 1
    return candidate


def install(
    library: Library, sources: list[Path], force: bool = False
) -> list[InstallResult]:
    """Copy captures and IRs into the M-EFCS library.

    WARNING: this writes into the M-EFCS sandbox container at
    ``~/Library/Containers/com.digAmp.dgAmp/Data/Documents/M-EFCS``. That is
    another application's data directory. It only ever writes files the caller
    named, only into ``ampFile`` / ``cabFile``, and never into ``model/``.

    A file that fails validation is refused rather than installed, and an
    existing destination is only overwritten with `force`. ``force`` means
    "replace and keep the original": the incumbent is copied to a timestamped
    ``.bak`` sidecar first, matching ``captures.write_with_backup``. It never
    means "replace irrecoverably".

    One file's failure never abandons the batch: every copy error becomes a
    ``refused`` row and the loop continues, so the caller always gets one result
    per source.
    """
    library.check()
    results: list[InstallResult] = []
    for raw_source in sources:
        source = Path(raw_source)
        if not source.is_file():
            results.append(InstallResult(source, source, "refused", "no such file"))
            continue
        try:
            destination = library.destination_for(source)
        except LibraryError as exc:
            results.append(InstallResult(source, source, "refused", str(exc)))
            continue

        parsed = captures.inspect(source)
        if not parsed.ok:
            results.append(
                InstallResult(source, destination, "refused", "; ".join(parsed.errors))
            )
            continue

        # Short-circuit the same-file case before touching anything: copying a
        # file over itself raises SameFileError and would truncate nothing but
        # would abort the batch.
        if destination.exists() and _same_file(source, destination):
            results.append(
                InstallResult(
                    source,
                    destination,
                    "skipped",
                    "source and destination are the same file",
                    warnings=list(parsed.warnings),
                )
            )
            continue
        if destination.exists() and not force:
            results.append(
                InstallResult(
                    source,
                    destination,
                    "skipped",
                    "already present; pass --force to replace",
                    warnings=list(parsed.warnings),
                )
            )
            continue

        backup: Path | None = None
        try:
            replaced = destination.exists()
            if replaced:
                backup = backup_path(destination)
                storage.write_bytes_atomic(
                    backup, destination.read_bytes(), replace=False
                )
            storage.write_bytes_atomic(
                destination, source.read_bytes(), replace=replaced and force
            )
        except (storage.DestinationExistsError, OSError) as exc:
            results.append(
                InstallResult(
                    source,
                    destination,
                    "refused",
                    f"{type(exc).__name__}: {exc}",
                    warnings=list(parsed.warnings),
                    backup=backup,
                )
            )
            continue
        results.append(
            InstallResult(
                source,
                destination,
                "replaced" if replaced else "installed",
                warnings=list(parsed.warnings),
                backup=backup,
            )
        )
    return results


def _same_file(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve() or a.samefile(b)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# The planned slot maps in presets/library.md
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlannedSlot:
    """One row of a slot map table in presets/library.md."""

    slot: int
    kind: str  # "amp" or "ir"
    device_name: str | None
    file_stem: str | None
    role: str
    reserved: bool


@dataclass
class SlotDiff:
    """One planned slot compared against what is on disk."""

    slot: PlannedSlot
    status: str  # "ok", "reserved", "missing", "ambiguous"
    matches: list[Path] = field(default_factory=list)
    note: str = ""


_TABLE_ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*$")


def _split_row(line: str) -> list[str] | None:
    match = _TABLE_ROW.match(line.rstrip())
    if match is None:
        return None
    return [cell.strip() for cell in match.group(1).split("|")]


def _clean_cell(cell: str) -> str:
    """Strip markdown emphasis, backticks and bold markers from a table cell."""
    cell = cell.replace("**", "")
    cell = re.sub(r"\*\(([^)]*)\)\*", r"(\1)", cell)
    cell = cell.replace("`", "")
    return cell.strip()


def locate_library_doc(source_file: Path, cwd: Path) -> Path:
    """Find ``presets/library.md`` for ``library diff``.

    Prefer the repository checkout that contains this package (in-tree runs and
    editable installs). If that layout is absent — a wheel install — search
    *cwd* and its parents so a clone can still be diffed. The returned path
    may not exist; callers report that as a normal document error.
    """
    try:
        packaged = source_file.resolve().parents[3] / "presets" / "library.md"
    except IndexError:
        packaged = None
    if packaged is not None and packaged.is_file():
        return packaged
    cursor = cwd.resolve()
    for candidate in (cursor, *cursor.parents):
        path = candidate / "presets" / "library.md"
        if path.is_file():
            return path
    return packaged if packaged is not None else cursor / "presets" / "library.md"


def default_library_doc() -> Path:
    """``presets/library.md`` from this checkout, or from the working directory."""
    return locate_library_doc(Path(__file__), Path.cwd())


def parse_slot_maps(doc: Path) -> list[PlannedSlot]:
    """Extract the amp and IR slot map tables from presets/library.md.

    The two tables differ in shape: the amp map is ``Slot | File | Role`` and the
    IR map is ``Slot | Device name | File | Role``. They are told apart by their
    header row rather than by position.

    Slot numbers are range-checked against the pedal's 20 amp and 20 IR slots
    and checked for duplicates. An edited document naming slot 0 or slot 25 is a
    document bug, and letting it through silently produces a plan that can never
    be applied.
    """
    doc = Path(doc)
    if not doc.is_file():
        raise LibraryError(f"slot map document not found: {doc}")

    planned: list[PlannedSlot] = []
    seen: set[tuple[str, int]] = set()
    kind: str | None = None
    columns: list[str] = []
    for line in doc.read_text(encoding="utf-8").splitlines():
        heading = line.strip().lower()
        if heading.startswith("## "):
            if "amp slot map" in heading:
                kind, columns = "amp", []
            elif "ir slot map" in heading:
                kind, columns = "ir", []
            else:
                kind, columns = None, []
            continue
        if kind is None:
            continue
        cells = _split_row(line)
        if cells is None:
            continue
        if all(set(cell) <= set("-: ") for cell in cells):
            continue  # separator row
        lowered = [c.strip().lower() for c in cells]
        if lowered and lowered[0] == "slot":
            columns = lowered
            continue
        if not columns:
            continue
        row = dict(zip(columns, cells, strict=False))
        try:
            slot = int(_clean_cell(row.get("slot", "")))
        except ValueError:
            continue
        try:
            protocol.check_slot_number(slot, f"{kind} slot")
        except ValueError as exc:
            raise LibraryError(
                f"{doc}: {exc}. The pedal has exactly "
                f"{protocol.NAME_COUNT} amp slots and {protocol.NAME_COUNT} IR "
                f"slots, numbered from 1."
            ) from exc
        if (kind, slot) in seen:
            raise LibraryError(
                f"{doc}: {kind} slot {slot} appears more than once in the slot "
                f"map. Two files cannot occupy one slot."
            )
        seen.add((kind, slot))
        file_cell = _clean_cell(row.get("file", ""))
        name_cell = _clean_cell(row.get("device name", "")) or None
        role = _clean_cell(row.get("role", ""))
        reserved = (
            "(reserved)" in file_cell.lower()
            or "(reserved)" in (name_cell or "").lower()
            or "factory" in file_cell.lower()
        )
        stem = None if reserved or not file_cell else file_cell
        planned.append(
            PlannedSlot(
                slot=slot,
                kind=kind,
                device_name=name_cell,
                file_stem=stem,
                role=role,
                reserved=reserved,
            )
        )
    return planned


def _match_stem(stem: str, entries: list[LibraryEntry]) -> list[Path]:
    """Find library files for a planned stem.

    ``presets/library.md`` records shortened stems (the pack's filenames carry
    extra ``_AuditionX_A+`` style suffixes), so an exact match is tried first and
    a prefix match second.
    """
    exact = [e.path for e in entries if e.stem == stem]
    if exact:
        return exact
    return [e.path for e in entries if e.stem.startswith(stem)]


def diff_slots(library: Library, doc: Path) -> list[SlotDiff]:
    """Compare every planned slot against the files actually in the library."""
    planned = parse_slot_maps(doc)
    amp_entries = library.entries(kind="capture")
    ir_entries = library.entries(kind="ir")
    diffs: list[SlotDiff] = []
    for slot in planned:
        if slot.reserved or not slot.file_stem:
            diffs.append(
                SlotDiff(slot, "reserved", note="factory contents kept on purpose")
            )
            continue
        entries = amp_entries if slot.kind == "amp" else ir_entries
        matches = _match_stem(slot.file_stem, entries)
        if not matches:
            diffs.append(
                SlotDiff(
                    slot,
                    "missing",
                    note=f"no file in the library starts with {slot.file_stem!r}",
                )
            )
        elif len(matches) > 1:
            diffs.append(
                SlotDiff(
                    slot,
                    "ambiguous",
                    matches=matches,
                    note=f"{len(matches)} files match the prefix",
                )
            )
        else:
            diffs.append(SlotDiff(slot, "ok", matches=matches))
    return diffs


# ---------------------------------------------------------------------------
# Restarting the editor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RestartConsent:
    """Capability object required to actually quit and relaunch M-EFCS.

    Same reasoning as :class:`protocol.WriteConsent`: a bare boolean is too easy
    to pass by accident, and this action can destroy work that belongs to
    someone else. Both fields must be set deliberately.
    """

    confirmed_by_user: bool = False
    accept_unsaved_work_loss: bool = False

    def authorise(self) -> None:
        if self.confirmed_by_user is not True:
            raise LibraryError(
                "REFUSED: restart_editor needs RestartConsent("
                "confirmed_by_user=True). Quitting M-EFCS is not automatic."
            )
        if self.accept_unsaved_work_loss is not True:
            raise LibraryError(
                "REFUSED: restart_editor needs "
                "RestartConsent(accept_unsaved_work_loss=True). "
                "'tell application ... to quit' discards whatever the GUI has "
                "not saved, and that GUI may belong to another person or "
                "process."
            )


def restart_editor(consent: RestartConsent | None = None) -> list[str]:
    """Quit and reopen M-EFCS so it rescans the library directories.

    Returns the commands that were (or would be) run. Without ``consent`` this
    is a dry run: it returns the commands and executes nothing.

    DANGEROUS. M-EFCS scans ``ampFile`` and ``cabFile`` once at launch and keeps
    no index, so a restart is the only way to make a newly installed file
    appear. But the quit is an AppleScript ``quit`` of another application:
    anything unsaved in that GUI is lost, and the GUI may be driven by someone
    else at the time. Requires an explicit :class:`RestartConsent`; the CLI maps
    that to ``--yes``.
    """
    quit_cmd = ["osascript", "-e", f'tell application id "{MEFCS_BUNDLE_ID}" to quit']
    open_cmd = ["open", "-b", MEFCS_BUNDLE_ID]
    commands = [" ".join(quit_cmd), " ".join(open_cmd)]
    if consent is None:
        return commands
    consent.authorise()
    for action, command in (("quit", quit_cmd), ("relaunch", open_cmd)):
        try:
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True
            )
        except OSError as exc:
            raise LibraryError(f"could not {action} M-EFCS: {exc}") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            suffix = f": {detail}" if detail else ""
            raise LibraryError(
                f"could not {action} M-EFCS (exit {completed.returncode}){suffix}"
            )
    return commands
