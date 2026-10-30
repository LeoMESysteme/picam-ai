"""Small artificial fixtures for the standalone archive exporter."""

import gzip
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("wiki_sessions", Path(__file__).parents[1] / "scripts/wiki_sessions.py")
w = importlib.util.module_from_spec(SPEC)
if SPEC.loader and SPEC.origin and Path(SPEC.origin).exists():
    SPEC.loader.exec_module(w)


def make_run(source, name="run-1", values=(1, 2, 3), base="sensor_boottime", test=False):
    run = source / "session-a" / name
    run.mkdir(parents=True)
    meta = {
        "schema": "live-session/1",
        "ended_at_utc": "2026-10-28T12:00:00Z",
        "started_at_utc": "2026-10-28T11:00:00Z",
        "device_id": "device",
        "gate": {"backend": "dotmatrix", "expected_unit": "kg", "confirm_frames": 2},
        "reader_tolerance": None,
        "camera": {"size": [640, 480], "fps": 30, "fourcc": "YUYV"},
        "summary": {"tracking_lost": 1},
        "test_run": {"reason": "fixture"} if test else None,
    }
    (run / "session.json").write_text(json.dumps(meta))
    records = [
        {
            "schema_version": 1,
            "status": "valid",
            "value": v,
            "confidence": 0.8,
            "capture_timestamp": {"base": base, "value_ns": i * 1000000000},
            "trace": {"t_dequeue_ns": 0, "t_record_built_ns": v * 1000000},
            "raw_text": "Größe ☃",
            "component_versions": {"reader": "dotmatrix/1"},
        }
        for i, v in enumerate(values)
    ]
    (run / "records.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in records))
    return run


def catalog(path):
    return json.loads((path / "catalog.json").read_text())


def test_export_exact_statistics_and_lossless_chunks(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source, values=(1, 2, 3, 4, 100))
    make_run(source, name="run-2", values=(20,))
    result = w.Exporter(source, archive, idle=lambda: True, block_size=37).run()
    data = catalog(result)
    assert data["schema"] == "sessions/1"
    group = data["groups"][0]
    assert group["run_equal"]["processing_median_ms"] == 11.5
    assert group["frame_weighted"]["processing_median_ms"] == 3.5
    assert group["frame_weighted"]["processing_p95_ms"] == 80
    # Five frames at 0..4 s span four intervals; run-2 has no duration.
    assert group["frame_weighted"]["rate_hz"] == 1.0
    assert group["run_equal"]["rate_hz"] == 1.0
    first = next(x for x in data["runs"] if x["id"].endswith("run-1"))
    assert first["stats"]["frames"] == 5
    manifest = json.loads((result / first["manifest"]).read_text())
    f = next(x for x in manifest["files"] if x["name"] == "records.jsonl")
    raw = b""
    for part in f["parts"]:
        compressed = (result / part["path"]).read_bytes()
        assert hashlib.sha256(compressed).hexdigest() == part["sha256"]
        block = gzip.decompress(compressed)
        assert hashlib.sha256(block).hexdigest() == part["raw_sha256"]
        raw += block
    assert raw == (run / "records.jsonl").read_bytes()


def test_resume_atomicity_and_deletion(tmp_path, monkeypatch):
    # Counts individual guard calls, so the process-scan throttle is disabled.
    monkeypatch.setattr(w, "GUARD_INTERVAL_S", 0)
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source, values=tuple(range(30)))
    checks = [0]

    def idle():
        checks[0] += 1
        return checks[0] < 12

    assert w.Exporter(source, archive, idle=idle, block_size=97).run() is None
    path = w.Exporter(source, archive, idle=lambda: True, block_size=97).run()
    assert catalog(path)["runs"][0]["stats"]["frames"] == 30
    assert w.Exporter(source, archive, idle=lambda: True).run() == path
    shutil.rmtree(source)
    assert w.Exporter(source, archive, idle=lambda: True).run() == path


def test_busy_zero_source_access_and_guard(tmp_path):
    source = tmp_path / "missing"
    archive = tmp_path / "archive"
    assert w.Exporter(source, archive, idle=lambda: False).run() is None
    assert not archive.exists()
    proc = tmp_path / "proc"
    proc.mkdir()
    assert w.workbench_idle(proc)
    p = proc / "123"
    p.mkdir()
    (p / "cmdline").write_bytes(b"/usr/bin/python\0-m\0dispread\0serve\0")
    assert not w.workbench_idle(proc)
    (p / "cmdline").write_bytes(b"/usr/local/bin/dispread\0serve\0")
    assert not w.workbench_idle(proc)
    (p / "cmdline").unlink()
    assert not w.workbench_idle(proc)


def test_invalid_json_unknown_status_and_timebases(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source, base="synthetic")
    stamp = {"base": "synthetic", "value_ns": 5}
    with (run / "records.jsonl").open("a") as f:
        f.write("bad\n" + json.dumps({"status": "future", "confidence": 1, "value": 999, "capture_timestamp": stamp}) + "\n")
        # Explorer acceptance rule: no string status or no finite capture
        # timestamp is an invalid line, not an "unknown" frame.
        f.write(json.dumps({"confidence": 1, "capture_timestamp": stamp}) + "\n")
        f.write(json.dumps({"status": 3, "capture_timestamp": stamp}) + "\n")
        f.write(json.dumps({"status": "valid", "value": 7}) + "\n")
        f.write(json.dumps({"status": "valid", "capture_timestamp": {"base": "synthetic", "value_ns": "5"}}) + "\n")
    result = w.Exporter(source, archive, idle=lambda: True).run()
    stat = catalog(result)["runs"][0]["stats"]
    assert stat["frames"] == 4
    assert stat["invalid_lines"] == 5
    assert stat["counts"] == {"valid": 3, "future": 1}
    assert stat["duration_s"] is None
    assert stat["rate_hz"] is None
    assert stat["processing_ms"]["median"] == 2
    assert stat["value"]["n"] == 3
    shares = catalog(result)["groups"][0]["frame_weighted"]["shares"]
    assert shares == {"valid": 0.75, "future": 0.25}
    assert sum(shares.values()) == 1


def test_deeply_nested_line_is_invalid_and_does_not_block_export(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    with (run / "records.jsonl").open("a") as f:
        f.write("[" * 200000 + "\n")
    broken = make_run(source, name="run-2")
    (broken / "session.json").write_text("[" * 200000)
    exporter = w.Exporter(source, archive, idle=lambda: True)
    result = exporter.run()
    assert exporter.error is None
    data = catalog(result)
    assert [r["id"] for r in data["runs"]] == ["session-a/run-1"]
    stat = data["runs"][0]["stats"]
    assert stat["frames"] == 3 and stat["invalid_lines"] == 1
    assert any(e.startswith("session-a/run-2: ") for e in data["errors"])


def test_conflict_retains_archived_bytes_and_symlink_refusal(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    (run / "records.jsonl").write_text("{}\n")
    new = w.Exporter(source, archive, idle=lambda: True).run()
    assert catalog(new)["errors"]
    assert catalog(new)["runs"][0]["stats"]["frames"] == 3
    assert (old / "catalog.json").exists()
    other = make_run(source, name="run-2")
    (other / "records.jsonl").unlink()
    (other / "records.jsonl").symlink_to(run / "records.jsonl")
    result = w.Exporter(source, archive, idle=lambda: True).run()
    assert len(catalog(result)["runs"]) == 1


def test_test_runs_and_missing_configuration_separate_groups(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    run = make_run(source, name="run-2", test=True)
    meta = json.loads((run / "session.json").read_text())
    meta.pop("camera")
    (run / "session.json").write_text(json.dumps(meta))
    result = w.Exporter(source, archive, idle=lambda: True).run()
    data = catalog(result)
    assert len(data["groups"]) == 2
    assert {x["test_run"] for x in data["groups"]} == {True, False}
    assert all("missing-profile" in x["warnings"] for x in data["runs"])


def test_conflict_cannot_change_pooled_samples(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    w.Exporter(source, archive, idle=lambda: True).run()
    records = (
        (run / "records.jsonl").read_text().replace('"value": 1', '"value": 1001').replace("1000000}", "1001000000}")
    )
    (run / "records.jsonl").write_text(records)
    new = w.Exporter(source, archive, idle=lambda: True).run()
    assert catalog(new)["groups"][0]["frame_weighted"]["processing_median_ms"] == 2
    assert catalog(new)["errors"]


def test_lock_keeps_old_snapshot_and_empty_stats_are_null(tmp_path):
    import fcntl

    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source, values=())
    old = w.Exporter(source, archive, idle=lambda: True).run()
    stat = catalog(old)["runs"][0]["stats"]
    assert stat["frames"] == 0
    assert stat["processing_ms"] == {"n": 0, "mean": None, "median": None, "p95": None}
    assert stat["rate_hz"] is None
    make_run(source, name="run-2")
    with (archive / "export.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        exporter = w.Exporter(source, archive, idle=lambda: True)
        assert exporter.run() == old
        assert exporter.deferred
    new = w.Exporter(source, archive, idle=lambda: True).run()
    assert len(catalog(new)["runs"]) == 2


def test_negative_trace_and_mixed_capture_bases(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    records = [json.loads(x) for x in (run / "records.jsonl").read_text().splitlines()]
    records[1]["trace"]["t_record_built_ns"] = -1
    records[2]["capture_timestamp"]["base"] = "v4l2_monotonic"
    records[2]["confidence"] = None
    (run / "records.jsonl").write_text("\n".join(json.dumps(x) for x in records))
    stat = catalog(w.Exporter(source, archive, idle=lambda: True).run())["runs"][0]["stats"]
    assert stat["processing_ms"]["n"] == 2
    assert stat["confidence"]["n"] == 2
    assert stat["duration_s"] is None


def test_nan_and_blank_lines_follow_the_explorer(tmp_path):
    # JSON.parse lehnt NaN ab und der Explorer überspringt Leerzeilen; das Archiv zählt gleich.
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    lines = (run / "records.jsonl").read_text().splitlines()
    nan = json.loads(lines[1])
    nan["confidence"] = float("nan")
    (run / "records.jsonl").write_text("\n".join([lines[0], json.dumps(nan), "", "   ", *lines[2:]]) + "\n")
    stat = catalog(w.Exporter(source, archive, idle=lambda: True).run())["runs"][0]["stats"]
    assert stat["invalid_lines"] == 1
    assert stat["frames"] == len(lines) - 1


def test_busy_after_checkpoint_preserves_published_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "GUARD_INTERVAL_S", 0)
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    make_run(source, name="run-2", values=tuple(range(30)))
    checks = [0]

    def idle():
        checks[0] += 1
        return checks[0] < 16

    exporter = w.Exporter(source, archive, idle=idle, block_size=43)
    assert exporter.run() == old
    assert exporter.deferred
    assert len(catalog(w.current_snapshot(archive))["runs"]) == 1
    new = w.Exporter(source, archive, idle=lambda: True, block_size=43).run()
    assert len(catalog(new)["runs"]) == 2
    assert next(r for r in catalog(new)["runs"] if r["id"].endswith("run-2"))["stats"]["frames"] == 30


def test_source_mutation_after_completed_run_cannot_publish(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    make_run(source, name="run-2")
    exporter = w.Exporter(source, archive, idle=lambda: True, block_size=200)
    original = exporter._import

    def import_then_mutate(directory):
        original(directory)
        if directory == run:
            (run / "records.jsonl").write_text("changed after checkpoint\n")

    exporter._import = import_then_mutate
    assert exporter.run() is None
    assert w.current_snapshot(archive) is None


def test_parent_symlink_source_refused(tmp_path):
    real = tmp_path / "real"
    make_run(real / "source")
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    exporter = w.Exporter(tmp_path / "link" / "source", tmp_path / "archive", idle=lambda: True)
    assert exporter.run() is None
    assert "symlink" in exporter.error


def test_unreadable_records_visible_without_fake_observations(tmp_path, monkeypatch):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    original = w.os.open

    def guarded(path, *args, **kwargs):
        if Path(path).name == "records.jsonl" and not args[0] & w.os.O_PATH:
            raise PermissionError("fixture unreadable records")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(w.os, "open", guarded)
    result = w.Exporter(source, archive, idle=lambda: True).run()
    data = catalog(result)["runs"][0]
    assert "unreadable-records" in data["warnings"]
    assert data["stats"]["frames"] == 0
    assert data["stats"]["processing_ms"]["median"] is None


def test_cli_deferred_success_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(w, "workbench_idle", lambda: False)
    assert w.main(["export", "--source", str(tmp_path / "missing"), "--archive", str(tmp_path / "archive")]) == 0
    assert json.loads(capsys.readouterr().out) == {"path": None, "deferred": True, "error": None}


def test_weightings_tracking_and_declared_frame_count_warning(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source, values=(1, 2, 3, 4, 100))
    run = make_run(source, name="run-2", values=(20,))
    meta = json.loads((run / "session.json").read_text())
    meta["summary"]["frames_read"] = 2
    (run / "session.json").write_text(json.dumps(meta))
    data = catalog(w.Exporter(source, archive, idle=lambda: True).run())
    group = data["groups"][0]
    assert group["run_equal"]["processing_p95_ms"] == pytest.approx(50.4)
    assert group["run_equal"]["tracking_per_1000"] == 600
    assert group["frame_weighted"]["tracking_per_1000"] == pytest.approx(1000 / 3)
    assert "frame-count-mismatch" in next(x for x in data["runs"] if x["id"].endswith("run-2"))["warnings"]


def test_rejected_pending_run_is_never_retained_on_retry_or_deletion(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    first = make_run(source)
    make_run(source, name="run-2")
    exporter = w.Exporter(source, archive, idle=lambda: True)
    validate = exporter._validate_sources
    changed = [False]

    def mutate():
        if not changed[0]:
            (first / "records.jsonl").write_text(
                '{"status":"fresh","capture_timestamp":{"base":"sensor_boottime","value_ns":0}}\n'
            )
            changed[0] = True
        validate()

    exporter._validate_sources = mutate
    assert exporter.run() is None
    result = w.Exporter(source, archive, idle=lambda: True).run()
    assert next(x for x in catalog(result)["runs"] if x["id"].endswith("run-1"))["stats"]["counts"] == {"fresh": 1}
    # Another rejected pending run must disappear if its source disappears.
    archive2 = tmp_path / "archive2"
    exporter = w.Exporter(source, archive2, idle=lambda: True)
    exporter._validate_sources = lambda: (_ for _ in ()).throw(ValueError("reject fixture"))
    assert exporter.run() is None
    shutil.rmtree(first)
    result = w.Exporter(source, archive2, idle=lambda: True).run()
    assert [x["id"] for x in catalog(result)["runs"]] == ["session-a/run-2"]


@pytest.mark.parametrize("field", ["gate", "camera", "summary"])
def test_malformed_nested_metadata_falls_back(tmp_path, field):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    run = make_run(source, name="run-2")
    metadata = json.loads((run / "session.json").read_text())
    metadata[field] = ["bad"]
    (run / "session.json").write_text(json.dumps(metadata))
    result = w.Exporter(source, archive, idle=lambda: True).run()
    assert catalog(result)["errors"]
    assert len(catalog(result)["runs"]) == 1
    assert old.exists()


@pytest.mark.parametrize("target", ["catalog", "manifest"])
def test_malformed_existing_archive_is_rejected(tmp_path, target):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    path = old / ("catalog.json" if target == "catalog" else catalog(old)["runs"][0]["manifest"])
    path.write_text("[]")
    assert w.current_snapshot(archive) is None


def test_same_size_corruption_and_manifest_disagreement_rejected(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    manifest_path = old / catalog(old)["runs"][0]["manifest"]
    manifest = json.loads(manifest_path.read_text())
    part = old / manifest["files"][0]["parts"][0]["path"]
    raw = bytearray(part.read_bytes())
    raw[len(raw) // 2] ^= 1
    part.write_bytes(raw)
    assert w.current_snapshot(archive) is None
    assert w.Exporter(source, archive, idle=lambda: True).run() is None


def test_unchanged_export_skips_group_recomputation(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    exporter = w.Exporter(source, archive, idle=lambda: True)

    def forbidden(_):
        raise AssertionError("unchanged groups recomputed")

    exporter._groups = forbidden
    assert exporter.run() == old


def test_aggregate_sql_interruption_defers_without_publication(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    exporter = w.Exporter(source, archive, idle=lambda: True)
    original = exporter._summary

    def interrupted(ids, metric):
        exporter.idle = lambda: False
        # Force SQLite to invoke the same registered progress callback on a
        # tiny query, without constructing a large performance fixture.
        exporter._guard_at = None
        exporter.db.set_progress_handler(exporter._sql_progress, 1)
        return original(ids, metric)

    exporter._summary = interrupted
    assert exporter.run() is None
    assert exporter.deferred
    assert exporter.sql_deferred
    assert exporter.error is None
    result = w.Exporter(source, archive, idle=lambda: True).run()
    assert catalog(result)["runs"][0]["stats"]["frames"] == 3


def test_manifest_contract_must_match_catalog(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    path = old / catalog(old)["runs"][0]["manifest"]
    manifest = json.loads(path.read_text())
    manifest["files"][0]["name"] = "wrong.json"
    path.write_text(json.dumps(manifest))
    assert w.current_snapshot(archive) is None


def test_verified_hashes_reused_and_busy_does_no_bulk_validation(tmp_path, monkeypatch):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    original = Path.open

    def no_payload(path, *args, **kwargs):
        if str(path).endswith(".gz.bin"):
            raise AssertionError("unchanged compressed payload rehashed")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", no_payload)
    assert w.current_snapshot(archive) == old
    assert w.Exporter(source, archive, idle=lambda: False).run() == old


def test_unpublished_generation_never_used_as_fallback(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    unpublished = archive / "snapshots" / "generation-unpublished"
    shutil.copytree(old, unpublished)
    (unpublished / "published").unlink(missing_ok=True)
    (old / "catalog.json").write_text("[]")
    assert w.current_snapshot(archive) is None


def test_fallback_selects_previous_published_generation(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    make_run(source, name="run-2")
    latest = w.Exporter(source, archive, idle=lambda: True).run()
    (latest / "catalog.json").write_text("[]")
    assert w.current_snapshot(archive) == old
    assert catalog(w.Exporter(source, archive, idle=lambda: True).run())["runs"][0]["stats"]["frames"] == 3


def test_sql_interruption_during_pooled_query_reuses_completed_summaries(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    make_run(source, name="run-2")
    exporter = w.Exporter(source, archive, idle=lambda: True)
    original = exporter._summary

    def interrupted(ids, metric):
        if len(ids) > 1:
            exporter.idle = lambda: False
            exporter._guard_at = None
            exporter.db.set_progress_handler(exporter._sql_progress, 1)
        return original(ids, metric)

    exporter._summary = interrupted
    assert exporter.run() is None
    assert exporter.deferred and exporter.error is None
    assert exporter.sql_deferred
    import sqlite3

    with sqlite3.connect(archive / "checkpoint.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM aggregates").fetchone()[0] == 6
        assert db.execute("SELECT count(*) FROM archived").fetchone()[0] == 0
    data = catalog(w.Exporter(source, archive, idle=lambda: True).run())
    assert data["groups"][0]["frame_weighted"]["processing_median_ms"] == 2


def test_group_tolerance_uses_only_semantic_factor(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    for name, tolerance in [
        ("run-2", {"factor": 1.0, "confirmed_by": "A", "at": "one"}),
        ("run-3", {"factor": 1.0, "confirmed_by": "B", "at": "two"}),
        ("run-4", {"factor": 1.2, "confirmed_by": "B"}),
    ]:
        run = make_run(source, name=name)
        meta = json.loads((run / "session.json").read_text())
        meta["reader_tolerance"] = tolerance
        (run / "session.json").write_text(json.dumps(meta))
    data = catalog(w.Exporter(source, archive, idle=lambda: True).run())
    assert len(data["groups"]) == 2
    regular = next(g for g in data["groups"] if g["config"]["tolerance"] == 1.0)
    assert regular["session_count"] == 3
    tolerant = next(r for r in data["runs"] if r["id"].endswith("run-4"))
    assert tolerant["config"]["tolerance"] == 1.2
    assert "unvalidated-reader-tolerance" in tolerant["warnings"]


@pytest.mark.parametrize("tolerance", [{}, {"factor": 0}, {"factor": -1}, {"factor": "1"}, {"factor": float("inf")}])
def test_malformed_tolerance_rejected_without_default(tmp_path, tolerance):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    meta = json.loads((run / "session.json").read_text())
    meta["reader_tolerance"] = tolerance
    (run / "session.json").write_text(json.dumps(meta))
    data = catalog(w.Exporter(source, archive, idle=lambda: True).run())
    assert data["runs"] == []
    assert data["errors"]


def test_missing_tolerance_unknown_and_invalid_lines_warned(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source)
    meta = json.loads((run / "session.json").read_text())
    del meta["reader_tolerance"]
    (run / "session.json").write_text(json.dumps(meta))
    with (run / "records.jsonl").open("a") as stream:
        stream.write("not JSON\n")
    data = catalog(w.Exporter(source, archive, idle=lambda: True).run())
    assert data["runs"][0]["config"]["tolerance"] == "unknown"
    assert "invalid-record-lines" in data["runs"][0]["warnings"]


def test_fallback_uses_publication_order_not_generation_uuid(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    one = w.Exporter(source, archive, idle=lambda: True).run()
    make_run(source, name="run-2")
    two = w.Exporter(source, archive, idle=lambda: True).run()
    # Pruning keeps only current plus one previous; add a third by copy.
    three = archive / "snapshots" / "generation-third"
    shutil.copytree(two, three)
    renamed = []
    for index, (path, name) in enumerate(
        [(one, "generation-zzzz"), (two, "generation-aaaa"), (three, "generation-current")]
    ):
        target = path.with_name(name)
        path.rename(target)
        w.os.utime(target / "published", ns=(1000000000 + index, 1000000000 + index))
        renamed.append(target)
    (archive / "current").write_text("generation-current\n")
    (renamed[2] / "catalog.json").write_text("[]")
    shutil.rmtree(source)
    assert w.current_snapshot(archive) == renamed[1]
    assert len(catalog(w.Exporter(source, archive, idle=lambda: True).run())["runs"]) == 2


def test_unrepresentable_integer_observations_are_excluded_without_crash(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source, values=(1,))
    record = json.loads((run / "records.jsonl").read_text())
    record["value"] = record["confidence"] = 10**400
    record["trace"]["t_record_built_ns"] = 10**400
    unstamped = json.loads(json.dumps(record))
    unstamped["capture_timestamp"]["value_ns"] = 10**400
    (run / "records.jsonl").write_text(json.dumps(record) + "\n" + json.dumps(unstamped) + "\n")
    exporter = w.Exporter(source, archive, idle=lambda: True)
    data = catalog(exporter.run())
    assert exporter.error is None
    assert data["runs"][0]["stats"]["frames"] == 1
    assert data["runs"][0]["stats"]["invalid_lines"] == 1  # unrepresentable capture time
    for metric in ["processing_ms", "confidence", "value"]:
        assert data["runs"][0]["stats"][metric]["n"] == 0
    assert data["runs"][0]["stats"]["duration_s"] is None


@pytest.mark.parametrize("has_previous", [False, True])
def test_receiptless_current_is_rejected_and_export_recovers(tmp_path, has_previous):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    previous = None
    if has_previous:
        previous = w.Exporter(source, archive, idle=lambda: True).run()
        make_run(source, name="run-2")
    interrupted = w.Exporter(source, archive, idle=lambda: True).run()
    (interrupted / "published").unlink()
    assert w.current_snapshot(archive) == previous
    recovered = w.Exporter(source, archive, idle=lambda: True).run()
    assert recovered is not None and recovered != interrupted
    assert (recovered / "published").is_file()
    assert len(catalog(recovered)["runs"]) == (2 if has_previous else 1)
    assert w.current_snapshot(archive) == recovered


def test_sql_progress_checks_budget_each_callback_and_limits_process_scans(tmp_path, monkeypatch):
    now = [10.0]
    scans = []
    active = [False]

    def idle():
        scans.append(now[0])
        return not active[0]

    exporter = w.Exporter(tmp_path / "source", tmp_path / "archive", idle=idle)
    exporter.deadline = 20.0
    exporter.sql_deferred = False
    monkeypatch.setattr(w.time, "monotonic", lambda: now[0])
    for _ in range(1000):
        assert exporter._sql_progress() == 0
    assert scans == [10.0]
    now[0] = 10.099
    assert exporter._sql_progress() == 0
    assert len(scans) == 1
    now[0] = 10.101
    assert exporter._sql_progress() == 0
    assert len(scans) == 2
    active[0] = True
    now[0] = 10.202
    assert exporter._sql_progress() == 1
    assert exporter.sql_deferred
    # Even inside the process-scan interval, the budget remains unconditional.
    exporter.sql_deferred = False
    exporter.deadline = 10.203
    now[0] = 10.204
    assert exporter._sql_progress() == 1
    assert exporter.sql_deferred
    assert len(scans) == 3


def chunk_files(generation):
    return {p.name: p for p in (generation / "chunks").iterdir()}


def test_new_generation_reuses_integrity_proofs_of_linked_blocks(tmp_path, monkeypatch):
    # os.link changes ctime; the cache key must not, or every generation rehashes all.
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    old_chunks = set(chunk_files(old))
    make_run(source, name="run-2", values=(7, 8, 9, 10))
    hashed = []
    original = Path.open

    def recording(path, *args, **kwargs):
        if str(path).endswith(".gz.bin") and "/snapshots/" in str(path):
            hashed.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording)
    new = w.Exporter(source, archive, idle=lambda: True).run()
    assert new != old and len(catalog(new)["runs"]) == 2
    assert hashed, "new blocks must be verified once"
    assert not old_chunks & set(hashed)


def test_generations_share_block_inodes_and_old_ones_are_pruned(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    generations = [w.Exporter(source, archive, idle=lambda: True).run()]
    for name in ("run-2", "run-3", "run-4", "run-5", "run-6"):
        make_run(source, name=name, values=(int(name[-1]),))
        generations.append(w.Exporter(source, archive, idle=lambda: True).run())
    remaining = sorted(p.name for p in (archive / "snapshots").iterdir())
    assert remaining == sorted(g.name for g in generations[-(w.KEEP_PREVIOUS + 1):])
    assert not [p for p in archive.iterdir() if p.name.startswith(("stage-", "trash-"))]
    latest, previous = generations[-1], generations[-2]
    for name, path in chunk_files(previous).items():
        block = archive / "blocks" / name
        assert path.stat().st_ino == chunk_files(latest)[name].stat().st_ino == block.stat().st_ino
        assert (block.stat().st_mode & 0o777) == 0o640
    assert w.current_snapshot(archive) == latest


def test_pruning_keeps_exposed_previous_generation(tmp_path):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    exposed = w.Exporter(source, archive, idle=lambda: True).run()
    exposed.chmod(0o750)  # the exposure service made it readable for the runner
    make_run(source, name="run-2")
    unexposed = w.Exporter(source, archive, idle=lambda: True).run()
    unexposed.chmod(0o700)
    make_run(source, name="run-3")
    latest = w.Exporter(source, archive, idle=lambda: True).run()
    assert sorted(p.name for p in (archive / "snapshots").iterdir()) == sorted([exposed.name, latest.name])


@pytest.mark.parametrize("stage", ["validate", "pointer"])
def test_deferred_publication_leaves_no_orphaned_generation(tmp_path, monkeypatch, stage):
    source, archive = tmp_path / "source", tmp_path / "archive"
    make_run(source)
    old = w.Exporter(source, archive, idle=lambda: True).run()
    make_run(source, name="run-2")
    exporter = w.Exporter(source, archive, idle=lambda: True)
    staged = []
    if stage == "validate":
        validate = w._validate_snapshot

        def deferred(directory, cache, check):
            if directory != old:
                staged.append(directory)
                raise w.Deferred()
            return validate(directory, cache, check)

        monkeypatch.setattr(w, "_validate_snapshot", deferred)
    else:
        original = w._atomic

        def failing(path, data):
            if path.name == "current":
                staged.append(path)
                raise OSError("pointer write failed")
            return original(path, data)

        monkeypatch.setattr(w, "_atomic", failing)
    assert exporter.run() == old
    assert staged, "publication path was not reached"
    assert exporter.deferred == (stage == "validate")
    assert [p.name for p in (archive / "snapshots").iterdir()] == [old.name]
    assert not [p for p in archive.iterdir() if p.name.startswith(("stage-", "trash-"))]


def test_guard_scans_processes_at_most_every_interval(tmp_path, monkeypatch):
    now = [100.0]
    scans = []
    exporter = w.Exporter(tmp_path / "source", tmp_path / "archive", idle=lambda: scans.append(now[0]) or True)
    exporter.deadline = 200.0
    monkeypatch.setattr(w.time, "monotonic", lambda: now[0])
    for _ in range(500):
        exporter._check()
    assert scans == [100.0]
    now[0] = 100.101
    exporter._check()
    assert len(scans) == 2
    exporter.idle = lambda: False
    now[0] = 100.15
    exporter._check()  # inside the interval: no scan
    now[0] = 100.25
    with pytest.raises(w.Deferred):
        exporter._check()
    exporter.idle = lambda: True
    now[0] = 200.0
    with pytest.raises(w.Deferred):
        exporter._check()  # deadline stays unconditional


def test_archived_runs_are_reevaluated_once_from_blocks_under_new_rules(tmp_path, monkeypatch):
    import sqlite3

    source, archive = tmp_path / "source", tmp_path / "archive"
    run = make_run(source, values=(1, 2, 3, 4), name="run-1")
    with (run / "records.jsonl").open("a") as f:
        f.write(json.dumps({"status": "valid", "value": 9}) + "\n")  # no capture time
    monkeypatch.setattr(w, "STATS_RULES", 1)
    old = w.Exporter(source, archive, idle=lambda: True, block_size=61).run()
    assert catalog(old)["runs"][0]["stats"]["rules"] == 1
    monkeypatch.setattr(w, "STATS_RULES", 2)
    original = w._open_source

    def no_records(path, flags=w.os.O_RDONLY):
        if path.name == "records.jsonl" and not flags & w.os.O_PATH:
            raise AssertionError("re-evaluation must read stored blocks, not the source")
        return original(path, flags)

    monkeypatch.setattr(w, "_open_source", no_records)
    # Interrupt the block-wise re-evaluation once, then resume.
    monkeypatch.setattr(w, "GUARD_INTERVAL_S", 0)
    checks = [0]

    def idle():
        checks[0] += 1
        return checks[0] < 25

    assert w.Exporter(source, archive, idle=idle, block_size=61).run() == old
    new = w.Exporter(source, archive, idle=lambda: True, block_size=61).run()
    assert new != old
    stats = catalog(new)["runs"][0]["stats"]
    assert stats["rules"] == 2
    assert stats["frames"] == 4 and stats["invalid_lines"] == 1
    assert stats["rate_hz"] == 1.0  # four frames over three seconds
    assert catalog(new)["runs"][0]["files"] == catalog(old)["runs"][0]["files"]
    with sqlite3.connect(archive / "checkpoint.sqlite3") as db:
        keys = {row[0] for row in db.execute("SELECT DISTINCT run FROM samples")}
    assert keys and all(k.endswith(":r2") for k in keys)
    # Unchanged afterwards: no further generation.
    assert w.Exporter(source, archive, idle=lambda: True, block_size=61).run() == new
