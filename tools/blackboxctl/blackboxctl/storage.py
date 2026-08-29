"""Durable, private atomic writes for recovery evidence.

Device-changing commands depend on rollback images and progress journals being
present after a crash or power loss. Keep the filesystem mechanics here so
every caller gets the same no-clobber, mode-0600, and directory-fsync rules.

GPL-3.0-or-later. See ../LICENSE and ../NOTICE.
"""

from __future__ import annotations

import errno
import fcntl
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path


class DestinationExistsError(FileExistsError):
    """A no-clobber atomic write found an existing destination."""

    def __init__(self, path: Path, *, concurrent: bool) -> None:
        self.path = path
        self.concurrent = concurrent
        detail = "was created concurrently" if concurrent else "already exists"
        super().__init__(f"{path} {detail}")


class LockUnavailableError(RuntimeError):
    """Another process owns an exclusive artifact lock."""


def final_component_path(path: Path) -> Path:
    """Canonicalize the parent while preserving the named final component."""
    expanded = path.expanduser()
    absolute = Path(os.path.abspath(os.fspath(expanded)))
    return absolute.parent.resolve() / absolute.name


def fsync_directory(path: Path) -> None:
    """Persist directory-entry changes where directory fsync is supported."""
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def mkdir_durable(path: Path) -> None:
    """Create *path* and persist each newly created link in its parent."""
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent

    path.mkdir(parents=True, exist_ok=True)
    # ``missing`` is deepest-first: persist C in B before persisting B in A.
    for created in missing:
        fsync_directory(created.parent)


@contextmanager
def exclusive_lock(path: Path) -> Iterator[Path]:
    """Hold a private, fail-fast advisory lock for one multi-step operation."""
    lock_path = final_component_path(path)
    mkdir_durable(lock_path.parent)
    descriptor: int | None = None
    try:
        flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(lock_path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                raise LockUnavailableError(
                    f"another process is using {lock_path}"
                ) from exc
            raise
        yield lock_path
    finally:
        if descriptor is not None:
            with suppress(OSError):
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def write_bytes_atomic(
    path: Path,
    payload: bytes,
    *,
    replace: bool,
    mode: int = 0o600,
) -> Path:
    """Atomically write *payload* with durable directory metadata.

    With ``replace=False``, a hard-link publish step makes no-clobber atomic
    even if another process creates the destination after the initial check.
    """
    # Keep the final path component lexical. ``Path.resolve()`` follows an
    # existing (or dangling) destination symlink, which would make a requested
    # atomic replacement overwrite the symlink target outside the named
    # directory. Parent-directory symlinks still follow normal OS semantics.
    destination = final_component_path(path)
    mkdir_durable(destination.parent)
    if not replace and destination.exists():
        raise DestinationExistsError(destination, concurrent=False)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        if replace:
            os.replace(temporary, destination)
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError as exc:
                raise DestinationExistsError(destination, concurrent=True) from exc
            temporary.unlink()

        fsync_directory(destination.parent)
    except BaseException:  # cleanup must also run on Ctrl-C
        with suppress(FileNotFoundError):
            temporary.unlink()
        raise
    return destination
