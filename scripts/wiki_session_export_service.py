#!/usr/bin/env python3
"""Private export service: expose only complete, published generations to readers."""

from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

from wiki_sessions import GUARD_INTERVAL_S, Exporter, workbench_idle

ARCHIVE = Path("/srv/picam-wiki-export/archive")


class ExposureDeferred(Exception):
    """Workbench activity stopped a permission update."""


def _check(idle):
    if not idle():
        raise ExposureDeferred()


def _descriptor(path, *, directory=False):
    """Open every component without following symlinks, including ancestors."""
    parts = path.absolute().parts
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[1:-1]:
            next_descriptor = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        if directory:
            flags |= os.O_DIRECTORY
        return os.open(parts[-1], flags, dir_fd=descriptor)
    finally:
        os.close(descriptor)


def _regular(path):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("regular published file required: " + path.name)
    return metadata


def _chmod(path, permissions, *, directory=False, keep_setgid=False):
    """Set a mode through a no-follow descriptor; skip when already correct.

    Owner chmod by a non-member of the directory group silently clears setgid
    (kernel rule). Skipping unchanged modes keeps it where it already exists.
    """
    descriptor = _descriptor(path, directory=directory)
    try:
        metadata = os.fstat(descriptor)
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(metadata.st_mode):
            raise ValueError("unexpected exposure path type")
        current = stat.S_IMODE(metadata.st_mode)
        if keep_setgid:
            permissions |= current & stat.S_ISGID
        if current != permissions:
            os.fchmod(descriptor, permissions)
    finally:
        os.close(descriptor)


def throttled(idle, interval=GUARD_INTERVAL_S):
    """Scan /proc at most every interval; a busy answer is never cached."""
    last = [None]

    def guard():
        now = time.monotonic()
        if last[0] is not None and now - last[0] < interval:
            return True
        if not idle():
            return False
        last[0] = now
        return True

    return guard


def expose_snapshot(archive, snapshot, *, idle=workbench_idle):
    """Grant group access to one published generation; expose current last.

    Return False when Workbench activity interrupts the walk. Nothing is
    created, copied or chowned here: chunks are hard links to the shared 0640
    block store, and every published entry must already carry the archive's
    group (inherited through setgid). Files are opened first, directories
    bottom-up, so a reader never reaches a partly readable generation. Private
    cache, checkpoints, archive root and source paths are never targets.
    Directory-descriptor opens prevent symlink swaps from redirecting chmod.
    """
    try:
        _check(idle)
        archive, snapshot = Path(archive).absolute(), Path(snapshot).absolute()
        if ".." in archive.parts or ".." in snapshot.parts:
            raise ValueError("path traversal refused")
        parent = archive / "snapshots"
        if snapshot.parent != parent or not snapshot.name.startswith("generation-"):
            raise ValueError("snapshot must be a generation inside archive/snapshots")
        _check(idle)
        descriptor = _descriptor(archive, directory=True)
        try:
            group = os.fstat(descriptor).st_gid
        finally:
            os.close(descriptor)
        descriptor = _descriptor(snapshot, directory=True)
        os.close(descriptor)
        _check(idle)
        _regular(snapshot / "published")
        _check(idle)
        if _regular(archive / "current").st_gid != group:
            raise ValueError("current has a foreign group; archive setgid missing?")
        # Validate the whole tree before the first chmod. Symlinks to files,
        # directories, special files, symlink ancestors and entries without the
        # archive group (lost setgid) are all refused.
        files, directories = [], [snapshot]
        if snapshot.lstat().st_gid != group:
            raise ValueError("generation has a foreign group; archive setgid missing?")
        for root, names, file_names in os.walk(snapshot, followlinks=False):
            _check(idle)
            for name in names:
                _check(idle)
                metadata = (Path(root) / name).lstat()
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError("symlink directory refused")
                if metadata.st_gid != group:
                    raise ValueError("published directory has a foreign group: " + name)
                directories.append(Path(root) / name)
            for name in file_names:
                _check(idle)
                if _regular(Path(root) / name).st_gid != group:
                    raise ValueError("published file has a foreign group: " + name)
                files.append(Path(root) / name)
        for path in files:
            _check(idle)
            _chmod(path, 0o640)
        # Deepest directories first; the generation root becomes traversable last.
        for path in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            _check(idle)
            _chmod(path, 0o750, directory=True, keep_setgid=True)
        _check(idle)
        _chmod(parent, 0o750, directory=True, keep_setgid=True)
        # Hold the pointer descriptor while checking and chmodding it. A newer
        # atomic pointer replacement keeps its own private mode until exposed.
        _check(idle)
        descriptor = _descriptor(archive / "current")
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("current must be a regular file")
            _check(idle)
            if os.read(descriptor, 256).decode("ascii").strip() != snapshot.name:
                raise ValueError("current points to a different generation")
            _check(idle)
            os.fchmod(descriptor, 0o640)
        finally:
            os.close(descriptor)
        return True
    except ExposureDeferred:
        return False


def run_once(source, archive=ARCHIVE, *, idle=workbench_idle, exporter_factory=Exporter, budget_s=45):
    """One fixed-archive service pass; injectable paths/factory support tiny tests."""
    result = {"path": None, "deferred": False, "error": None}
    try:
        if not idle():
            result["deferred"] = True
            return result
        exporter = exporter_factory(Path(source), Path(archive), idle=idle)
        snapshot = exporter.run(budget_s)
        result.update(
            path=str(snapshot) if snapshot is not None else None, deferred=exporter.deferred, error=exporter.error
        )
        if snapshot is not None and not exporter.deferred:
            if not expose_snapshot(archive, snapshot, idle=throttled(idle)):
                result["deferred"] = True
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def main():
    try:
        source = os.environ.get("PICAM_EXPORT_SOURCE")
        if not source:
            raise ValueError("PICAM_EXPORT_SOURCE is required")
        result = run_once(Path(source))
    except Exception as exc:
        result = {"path": None, "deferred": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
