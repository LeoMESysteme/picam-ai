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
    assert mode(archive / "snapshots") == 0o2750
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
        return mode(archive / "snapshots") != 0o2750

    assert not service.expose_snapshot(archive, snapshot, idle=idle)
    assert mode(archive / "snapshots") == 0o2750
    assert mode(archive / "current") == 0o600
    assert service.expose_snapshot(archive, snapshot, idle=lambda: True)
    assert mode(archive / "current") == 0o640


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
    assert mode(archive / "blocks") == 0o700
    assert all(mode(p) == 0o600 for p in (archive / "blocks").iterdir())
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
