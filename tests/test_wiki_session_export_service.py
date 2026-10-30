"""Artificial permission boundaries for the private export service."""

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("wiki_session_export_service", SCRIPTS / "wiki_session_export_service.py")
service = importlib.util.module_from_spec(SPEC)
if Path(SPEC.origin).exists():
    SPEC.loader.exec_module(service)


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def fixture(archive):
    snapshot = archive / "snapshots" / "generation-test"
    snapshot.mkdir(parents=True)
    (snapshot / "runs").mkdir()
    for file in [snapshot / "published", snapshot / "catalog.json", snapshot / "runs" / "manifest.json"]:
        file.write_text("{}")
        file.chmod(0o600)
    (archive / "current").write_text(snapshot.name + "\n")
    (archive / "current").chmod(0o600)
    (archive / "blocks").mkdir()
    (archive / "blocks" / "private.gz.bin").write_bytes(b"private")
    (archive / "blocks" / "private.gz.bin").chmod(0o600)
    (archive / "checkpoint.sqlite3").write_bytes(b"private")
    (archive / "checkpoint.sqlite3").chmod(0o600)
    return snapshot


def test_exposure_changes_only_published_snapshot_and_pointer(tmp_path):
    archive = tmp_path / "archive"
    snapshot = fixture(archive)
    source = tmp_path / "source"
    source.mkdir(mode=0o700)
    (source / "records").write_text("untouched")
    source_before = mode(source)
    assert service.expose_snapshot(archive, snapshot, idle=lambda: True)
    assert mode(archive / "snapshots") == 0o750
    assert mode(snapshot) == mode(snapshot / "runs") == 0o750
    assert mode(snapshot / "catalog.json") == 0o640
    assert mode(archive / "current") == 0o640
    assert mode(archive / "checkpoint.sqlite3") == 0o600
    assert mode(archive / "blocks" / "private.gz.bin") == 0o600
    assert mode(source) == source_before
    assert (source / "records").read_text() == "untouched"


def test_interrupted_exposure_never_exposes_pointer(tmp_path):
    archive = tmp_path / "archive"
    snapshot = fixture(archive)

    def idle():
        return mode(snapshot) != 0o750

    assert not service.expose_snapshot(archive, snapshot, idle=idle)
    assert mode(snapshot) == 0o750
    assert mode(archive / "current") == 0o600
    assert service.expose_snapshot(archive, snapshot, idle=lambda: True)
    assert mode(archive / "current") == 0o640


def test_exposure_opens_files_then_directories_bottom_up(tmp_path):
    archive = tmp_path / "archive"
    snapshot = fixture(archive)

    def idle():
        # Interrupt as soon as the first directory changes.
        return mode(snapshot / "runs") == 0o700 and mode(snapshot) == 0o700

    (snapshot / "runs").chmod(0o700)
    snapshot.chmod(0o700)
    assert not service.expose_snapshot(archive, snapshot, idle=idle)
    assert mode(snapshot / "catalog.json") == mode(snapshot / "runs" / "manifest.json") == 0o640
    assert mode(snapshot / "runs") == 0o750  # deepest directory first
    assert mode(snapshot) == 0o700  # generation root stays closed until last
    assert mode(archive / "current") == 0o600


@pytest.mark.parametrize("kind", ["outside", "traversal", "symlink", "unpublished", "pointer-symlink"])
def test_unsafe_exposure_refused(tmp_path, kind):
    archive = tmp_path / "archive"
    snapshot = fixture(archive)
    target = snapshot
    if kind == "outside":
        target = tmp_path / "outside"
        target.mkdir()
        (target / "published").write_text("{}")
    elif kind == "traversal":
        target = snapshot / ".." / snapshot.name
    elif kind == "symlink":
        (snapshot / "leak").symlink_to(tmp_path)
    elif kind == "unpublished":
        (snapshot / "published").unlink()
    else:
        (archive / "current").unlink()
        (archive / "current").symlink_to(snapshot / "published")
    with pytest.raises((ValueError, OSError)):
        service.expose_snapshot(archive, target, idle=lambda: True)


def test_busy_service_does_not_construct_exporter_or_walk(tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("busy exporter constructed")

    result = service.run_once(tmp_path / "absent", tmp_path / "archive", idle=lambda: False, exporter_factory=forbidden)
    assert result == {"path": None, "deferred": True, "error": None}
    assert not (tmp_path / "archive").exists()


def test_main_logs_json_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PICAM_EXPORT_SOURCE", str(tmp_path / "source"))
    monkeypatch.setattr(service, "run_once", lambda source: {"path": None, "deferred": False, "error": "fixture"})
    assert service.main() == 0
    assert json.loads(capsys.readouterr().out)["error"] == "fixture"


def test_private_umask_export_exposes_only_completed_generation(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = source / "session-one" / "run-one"
    run.mkdir(parents=True)
    metadata = {"schema": "live-session/1", "ended_at_utc": "2026-10-28T12:00:00Z"}
    (run / "session.json").write_text(json.dumps(metadata))
    (run / "records.jsonl").write_text('{"schema_version":1,"status":"valid","value":1}\n')
    before = (run / "records.jsonl").stat()
    previous_mask = os.umask(0o077)
    try:
        result = service.run_once(source, archive, idle=lambda: True)
    finally:
        os.umask(previous_mask)
    assert result["error"] is None and result["deferred"] is False
    snapshot = Path(result["path"])
    assert mode(archive / "current") == 0o640
    assert mode(snapshot / "catalog.json") == 0o640
    assert mode(archive / "checkpoint.sqlite3") == 0o600
    assert mode(archive / "integrity.sqlite3") == 0o600
    # Shared block store: 0640 inodes behind a private 0700 directory. The
    # runner reaches them only through links in a published generation.
    assert mode(archive / "blocks") == 0o700
    assert all(mode(p) == 0o640 for p in (archive / "blocks").iterdir())
    after = (run / "records.jsonl").stat()
    assert (after.st_mode, after.st_size, after.st_mtime_ns) == (before.st_mode, before.st_size, before.st_mtime_ns)


@pytest.mark.parametrize("has_previous", [False, True])
def test_service_recovers_receiptless_pointer_and_exposes_twice(tmp_path, has_previous):
    import shutil

    source, archive = tmp_path / "source", tmp_path / "archive"

    def add(name):
        run = source / "session-one" / name
        run.mkdir(parents=True)
        (run / "session.json").write_text(json.dumps({"schema": "live-session/1", "ended_at_utc": "done"}))
        (run / "records.jsonl").write_text('{"status":"valid"}\n')
        return run

    add("run-one")
    if has_previous:
        previous = service.run_once(source, archive, idle=lambda: True)
        added = add("run-two")
    interrupted = service.run_once(source, archive, idle=lambda: True)
    (Path(interrupted["path"]) / "published").unlink()
    (archive / "current").chmod(0o600)
    if has_previous:
        shutil.rmtree(added)
    for _ in range(2):
        result = service.run_once(source, archive, idle=lambda: True)
        assert result["error"] is None and result["deferred"] is False
        assert (archive / "current").read_text().strip() == Path(result["path"]).name
        assert mode(archive / "current") == 0o640
        assert (Path(result["path"]) / "published").is_file()
        if has_previous:
            assert result["path"] == previous["path"]


def test_production_rights_setgid_group_without_chown(tmp_path, monkeypatch):
    """Mirror /srv: archive 2750 in a group the service user is NOT in.

    Without root we use a supplementary group and emulate the two kernel rules
    that matter for a non-member owner: chmod clears S_ISGID, and fchown/chown
    to the archive group fails with EPERM. Every published entry must still
    carry the archive group, which only setgid inheritance can provide.
    """
    groups = [g for g in os.getgroups() if g != os.getegid()]
    if not groups:
        pytest.skip("keine Zusatzgruppe zum Nachbilden der Runner-Gruppe")
    group = groups[0]
    source, archive = tmp_path / "source", tmp_path / "archive"
    archive.mkdir()
    os.chown(archive, -1, group)
    archive.chmod(0o2750)
    assert mode(archive) == 0o2750

    real_fchmod, real_chmod = os.fchmod, os.chmod

    def strip(gid, permissions):
        return permissions & ~stat.S_ISGID if gid == group else permissions

    def fchmod(fd, permissions):
        real_fchmod(fd, strip(os.fstat(fd).st_gid, permissions))

    def chmod(path, permissions, *args, **kwargs):
        gid = os.stat(path, *args, **kwargs).st_gid
        real_chmod(path, strip(gid, permissions), *args, **kwargs)

    def eperm(*args, **kwargs):
        raise PermissionError(1, "Operation not permitted (non-member)")

    monkeypatch.setattr(os, "fchmod", fchmod)
    monkeypatch.setattr(os, "chmod", chmod)
    monkeypatch.setattr(os, "fchown", eperm)
    monkeypatch.setattr(os, "chown", eperm)

    def add(name, values):
        run = source / "session-one" / name
        run.mkdir(parents=True)
        (run / "session.json").write_text(json.dumps({"schema": "live-session/1", "ended_at_utc": "done"}))
        stamp = '"capture_timestamp":{"base":"sensor_boottime","value_ns":%d}'
        (run / "records.jsonl").write_text("".join('{"status":"valid",%s}\n' % (stamp % v) for v in values))

    previous_mask = os.umask(0o077)
    try:
        add("run-one", range(3))
        first = service.run_once(source, archive, idle=lambda: True)
        # The second generation is built after the first exposure already
        # cleared setgid on snapshots/ (as on the Pi) and links shared blocks.
        add("run-two", range(5))
        second = service.run_once(source, archive, idle=lambda: True)
    finally:
        os.umask(previous_mask)
    for result in (first, second):
        assert result["error"] is None and result["deferred"] is False, result
    generation = Path(second["path"])
    assert (archive / "current").read_text().strip() == generation.name
    assert mode(archive) == 0o2750
    assert mode(archive / "blocks") == 0o2700
    assert (archive / "current").stat().st_gid == group and mode(archive / "current") == 0o640
    assert mode(archive / "checkpoint.sqlite3") == 0o600
    for path in [generation, *generation.rglob("*")]:
        assert path.stat().st_gid == group, path
        assert mode(path) & 0o777 == (0o750 if path.is_dir() else 0o640), path
    for chunk in (generation / "chunks").iterdir():
        assert chunk.stat().st_ino == (archive / "blocks" / chunk.name).stat().st_ino
