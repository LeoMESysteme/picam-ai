"""Publication failures must not turn optional sessions into a build prerequisite."""
import gzip
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("wiki_session_site", Path(__file__).parents[1] / "scripts/wiki_session_site.py")
site_tools = importlib.util.module_from_spec(SPEC)
if SPEC.loader and SPEC.origin and Path(SPEC.origin).exists():
    SPEC.loader.exec_module(site_tools)


def fixture_snapshot(root, label="safe"):
    root.mkdir(parents=True)
    raw = b'{"status":"valid"}\n'
    zipped = gzip.compress(raw, mtime=0)
    part = {"path": "runs/run/records.000.gz.bin", "size": len(zipped),
            "sha256": hashlib.sha256(zipped).hexdigest(), "raw_size": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest()}
    files = [{"name": "records.jsonl", "size": len(raw), "parts": [part]}]
    (root / "runs/run").mkdir(parents=True)
    (root / part["path"]).write_bytes(zipped)
    (root / "runs/run/manifest.json").write_text(json.dumps({"schema": "session-files/1", "id": label, "files": files}))
    run = {"id": label, "group": "g", "device_id": "<script>alert(1)</script>", "unit": "mV/V",
           "test_run": False, "warnings": ["Hinweis <sicher>"], "manifest": "runs/run/manifest.json",
           "files": files, "started_at_utc": "2026-10-23T10:00:00+00:00", "ended_at_utc": "2026-10-23T10:01:00+00:00",
           "stats": {"frames": 1, "counts": {"valid": 1}, "processing_ms": {"median": 10, "p95": 10}}}
    catalog = {"schema": "sessions/1", "stats_version": "sessions-stats/1", "generated_at": "2026-10-23T10:02:00+00:00",
               "runs": [run], "groups": [], "errors": []}
    (root / "catalog.json").write_text(json.dumps(catalog))
    return root


@pytest.fixture
def site(tmp_path):
    root = tmp_path / "site"
    (root / "docs").mkdir(parents=True)
    (root / "docs/session-explorer.html").write_text('<html><!-- SESSION-SNAPSHOT:START -->Leer<!-- SESSION-SNAPSHOT:END --></html>')
    return root


def test_missing_archive_keeps_regular_site_usable(site):
    result = site_tools.attach(site, [])
    assert result["attached"] is False
    assert "Keine Sessions" in (site / "docs/session-explorer.html").read_text()
    assert json.loads((site / "assets/sessions/catalog.json").read_text())["runs"] == []


def test_production_attachment_is_complete_escaped_and_visible_without_js(site, tmp_path):
    snapshot = fixture_snapshot(tmp_path / "snapshot")
    result = site_tools.attach(site, [snapshot])
    assert result["attached"] is True
    html = (site / "docs/session-explorer.html").read_text()
    assert "&lt;script&gt;" in html and "<script>alert(1)</script>" not in html
    assert "records.jsonl" in html and "10:00" in html
    assert "runs/run/records.000.gz.bin" in html
    assert (site / "assets/sessions/runs/run/manifest.json").exists()


def test_corrupt_new_snapshot_falls_back_to_previous_without_failing_site(site, tmp_path):
    bad = fixture_snapshot(tmp_path / "bad", "bad")
    good = fixture_snapshot(tmp_path / "good", "old")
    (bad / "runs/run/records.000.gz.bin").write_bytes(b"corrupt")
    result = site_tools.attach(site, [bad, good])
    assert result["attached"] is True and result["snapshot"] == str(good)
    html = (site / "docs/session-explorer.html").read_text()
    assert "old" in html and "Aktualisierung" in html


def test_combined_site_limits_reject_session_attachment_only(site, tmp_path):
    snapshot = fixture_snapshot(tmp_path / "snapshot")
    (site / "already.dat").write_bytes(b"existing")
    result = site_tools.attach(site, [snapshot], max_files=2)
    assert result["attached"] is False
    assert (site / "already.dat").read_bytes() == b"existing"


def test_symlinks_and_traversal_in_manifests_are_rejected(site, tmp_path):
    snapshot = fixture_snapshot(tmp_path / "snapshot")
    manifest = snapshot / "runs/run/manifest.json"
    obj = json.loads(manifest.read_text())
    obj["files"][0]["parts"][0]["path"] = "../../private"
    manifest.write_text(json.dumps(obj))
    assert site_tools.attach(site, [snapshot])["attached"] is False
    manifest.unlink()
    manifest.symlink_to(tmp_path / "outside")
    assert site_tools.attach(site, [snapshot])["attached"] is False


@pytest.mark.parametrize("broken", [[], {"runs": [None]}, {"groups": [None]}, {"warnings": "bad"}, {"stats": []}])
def test_malformed_optional_metadata_falls_back_before_changing_site(site, tmp_path, broken):
    snapshot = fixture_snapshot(tmp_path / "bad")
    old = fixture_snapshot(tmp_path / "old", "old")
    path = snapshot / "catalog.json"
    catalog = json.loads(path.read_text())
    if isinstance(broken, list):
        catalog = broken
    elif "runs" in broken or "groups" in broken:
        catalog.update(broken)
    else:
        catalog["runs"][0].update(broken)
    path.write_text(json.dumps(catalog))
    result = site_tools.attach(site, [snapshot, old])
    assert result["snapshot"] == str(old)
    assert json.loads((site / "assets/sessions/catalog.json").read_text())["runs"][0]["id"] == "old"


def test_oversized_json_numbers_do_not_turn_optional_attachment_into_ci_failure(site, tmp_path):
    snapshot = fixture_snapshot(tmp_path / "bad")
    path = snapshot / "catalog.json"
    catalog = json.loads(path.read_text())
    catalog["groups"] = [{"id": "bad", "run_equal": {"shares": {"valid": 10**400}}, "frame_weighted": {"shares": {}}}]
    path.write_text(json.dumps(catalog))
    result = subprocess.run([sys.executable, str(Path(__file__).parents[1] / "scripts/wiki_session_site.py"),
                             "--site", str(site), "--snapshot", str(snapshot)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["attached"] is False
    assert "Keine Sessions" in (site / "docs/session-explorer.html").read_text()


def test_real_export_contract_reaches_publication_and_no_js_tables(site, tmp_path):
    spec = importlib.util.spec_from_file_location("wiki_sessions", Path(__file__).parents[1] / "scripts/wiki_sessions.py")
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    source = tmp_path / "source"
    run = source / "live-integration" / "run-01"
    run.mkdir(parents=True)
    meta = {"schema": "live-session/1", "session_id": "live-integration", "device_id": "GSV-2AS",
            "started_at_utc": "2026-10-28T10:00:00+00:00", "ended_at_utc": "2026-10-28T10:01:00+00:00",
            "reader_tolerance": None, "gate": {"backend": "dotmatrix", "expected_unit": "mV/V", "confirm_frames": 2},
            "camera": {"size": [1920, 1080], "fps": 30, "fourcc": "YUYV"}}
    (run / "session.json").write_text(json.dumps(meta))
    rows = [{"schema_version": 1, "status": "valid", "value": 1, "confidence": .9,
             "capture_timestamp": {"value_ns": i * 10**9, "base": "v4l2_monotonic"},
             "trace": {"t_dequeue_ns": i * 10**9, "t_record_built_ns": i * 10**9 + duration}}
            for i, duration in enumerate([10_000_000, 30_000_000])]
    raw = "".join(json.dumps(row) + "\n" for row in rows)
    (run / "records.jsonl").write_text(raw)
    snapshot = exporter.Exporter(source, tmp_path / "archive", idle=lambda: True).run()
    result = site_tools.attach(site, [snapshot])
    assert result["attached"] is True
    document = (site / "docs/session-explorer.html").read_text()
    assert "live-integration/run-01" in document and "20,00 / 29,00" in document
    assert (run / "records.jsonl").read_text() == raw
    catalog = json.loads((site / "assets/sessions/catalog.json").read_text())
    entry = next(f for f in catalog["runs"][0]["files"] if f["name"] == "records.jsonl")
    reconstructed = b"".join(gzip.decompress((site / "assets/sessions" / p["path"]).read_bytes()) for p in entry["parts"])
    assert reconstructed == raw.encode()


def test_no_js_summary_preserves_both_weightings_and_optional_metrics(site, tmp_path):
    snapshot = fixture_snapshot(tmp_path / "snapshot")
    path = snapshot / "catalog.json"
    catalog = json.loads(path.read_text())
    base = {"shares": {"valid": .5, "unreadable": .5}, "processing_median_ms": 10,
            "processing_p95_ms": 30, "confidence_median": .8, "rate_hz": 20, "tracking_per_1000": 3}
    catalog["groups"] = [{"id": "g", "label": "Vergleich", "frames": 10, "session_count": 2,
                          "run_equal": base, "frame_weighted": {**base, "processing_median_ms": 25}}]
    path.write_text(json.dumps(catalog))
    assert site_tools.attach(site, [snapshot])["attached"]
    html = (site / "docs/session-explorer.html").read_text()
    assert "Jeder Lauf zählt gleich" in html and "Alle Frames gemeinsam" in html
    assert "10,00 / 30,00" in html and "25,00 / 30,00" in html
    assert "Konfidenz" in html and "80,00" in html and "20,00" in html


def test_request_goes_to_runner_writable_path_by_default():
    # forgejo-runner.service: ProtectSystem=strict, ReadWritePaths=/var/lib/forgejo-runner.
    assert site_tools.REQUEST.parent == Path("/var/lib/forgejo-runner")
    unit = (Path(__file__).parents[1] / "systemd/picam-wiki-export.path").read_text()
    assert f"PathChanged={site_tools.REQUEST}" in unit
    runner = (Path(__file__).parents[1] / "systemd/forgejo-runner.service").read_text()
    assert "ReadWritePaths=/var/lib/forgejo-runner" in runner


def test_request_is_written_and_new_generation_is_selected(tmp_path):
    root, request = tmp_path / "export", tmp_path / "runner" / "wiki-export-request"
    request.parent.mkdir()
    (root / "archive/snapshots").mkdir(parents=True)
    report = {}
    assert site_tools.select_snapshots(root, tmp_path / "state.json", 0, report, request) == []
    assert request.read_bytes() == b"export\n"
    assert report["request_error"] is None


def test_failed_request_is_reported_not_swallowed_and_skips_waiting(tmp_path, monkeypatch, capsys):
    root = tmp_path / "export"
    (root / "archive/snapshots").mkdir(parents=True)
    unwritable = tmp_path / "missing-dir" / "wiki-export-request"
    monkeypatch.setattr(site_tools.time, "sleep", lambda s: pytest.fail("must not wait after a failed request"))
    report = {}
    assert site_tools.select_snapshots(root, tmp_path / "state.json", 15, report, unwritable) == []
    assert "Exportanfrage" in report["request_error"] and str(unwritable) in report["request_error"]
    site = tmp_path / "site"
    (site / "docs").mkdir(parents=True)
    (site / "docs/session-explorer.html").write_text("<!-- SESSION-SNAPSHOT:START --><!-- SESSION-SNAPSHOT:END -->")
    monkeypatch.setattr(sys, "argv", ["wiki_session_site.py", "--site", str(site), "--export-root", str(root),
                                      "--state", str(tmp_path / "state.json"), "--request", str(unwritable)])
    site_tools.main()
    output = json.loads(capsys.readouterr().out)
    assert output["attached"] is False and "Exportanfrage" in output["request_error"]
