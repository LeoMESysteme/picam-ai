#!/usr/bin/env python3
"""Private export service: expose only complete, published generations to readers."""

from __future__ import annotations

import json
import os
import stat
import uuid
from pathlib import Path

from wiki_sessions import Exporter, workbench_idle

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


def _chmod(path, permissions, *, directory=False):
    descriptor = _descriptor(path, directory=directory)
    try:
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(os.fstat(descriptor).st_mode):
            raise ValueError("unexpected exposure path type")
        os.fchmod(descriptor, permissions)
    finally:
        os.close(descriptor)


def _detach_private_link(path, idle):
    """Keep chmod on a published chunk from changing its private cache inode."""
    _check(idle)
    source = _descriptor(path)
    parent = None
    temporary = ".expose-" + uuid.uuid4().hex
    try:
        before = os.fstat(source)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("regular payload required")
        if before.st_nlink <= 1:
            return
        _check(idle)
        parent = _descriptor(path.parent, directory=True)
        destination = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(destination, "wb") as stream:
            os.fchown(stream.fileno(), -1, before.st_gid)
            while True:
                _check(idle)
                block = os.read(source, 1024 * 1024)
                if not block:
                    break
                stream.write(block)
            stream.flush()
            _check(idle)
            os.fsync(stream.fileno())
        after = os.fstat(source)

        def identity(value):
            return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

        if identity(before) != identity(after):
            raise ValueError("published payload changed during exposure")
        _check(idle)
        os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
    finally:
        os.close(source)
        if parent is not None:
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
            os.close(parent)


def expose_snapshot(archive, snapshot, *, idle=workbench_idle):
    """Grant group access to one published generation; expose current last.

    Return False when Workbench activity interrupts the walk. Private cache,
    checkpoints, archive root and source paths are never permission targets.
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
        descriptor = _descriptor(snapshot, directory=True)
        os.close(descriptor)
        _check(idle)
        _regular(snapshot / "published")
        _check(idle)
        _regular(archive / "current")
        # Validate the whole tree before the first chmod. Symlinks to files,
        # directories, special files and symlink ancestors are all refused.
        for root, directories, files in os.walk(snapshot, followlinks=False):
            _check(idle)
            for name in directories:
                _check(idle)
                if not stat.S_ISDIR((Path(root) / name).lstat().st_mode):
                    raise ValueError("symlink directory refused")
            for name in files:
                _check(idle)
                _regular(Path(root) / name)
        _check(idle)
        _chmod(parent, 0o2750, directory=True)
        for root, _directories, files in os.walk(snapshot, followlinks=False):
            _check(idle)
            _chmod(Path(root), 0o750, directory=True)
            for name in files:
                _check(idle)
                _detach_private_link(Path(root) / name, idle)
                _check(idle)
                _chmod(Path(root) / name, 0o640)
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
            if not expose_snapshot(archive, snapshot, idle=idle):
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
