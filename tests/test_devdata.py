"""Pfadprioritaet und Produktgrenze ohne Zugriff auf echte Projektdaten."""

import importlib.util
import json
from pathlib import Path

import _devdata
import pytest
from _devdata import diagnostic_output, input_path, logical_path, recording_glob
from devdata_helpers import local_recording


def _write(path, content="aufnahme"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@pytest.mark.parametrize("spelling", ["relative", "var", "absolute", "linked"])
def test_inputs_prefer_local_file_then_external_file(tmp_path, monkeypatch, spelling):
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    local = _write(repo / "var/diagnostics/run/still.png")
    external = _write(dev / "diagnostics/run/still.png")
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    relative = Path("diagnostics/run/still.png")
    path = {"relative": relative, "var": Path("var") / relative,
            "absolute": local, "linked": local}[spelling]
    if spelling == "linked":
        shared = tmp_path / "shared-var"
        (repo / "var").rename(shared)
        (repo / "var").symlink_to(shared, target_is_directory=True)
        path = shared / relative
    # Ein vorhandener Pfad bleibt so, wie er uebergeben wurde (Kennungen).
    assert input_path(path, repo_root=repo) == (path if spelling in {"absolute", "linked"} else local)
    local.unlink()
    # Das lokale Elternverzeichnis bleibt vorhanden: pro Datei aufloesen.
    assert input_path(path, repo_root=repo) == external
    external.unlink()
    assert input_path(path, repo_root=repo) == local


def test_unset_variable_does_not_search_external_data(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPREAD_DEV_DATA", raising=False)
    assert input_path("diagnostics/run", repo_root=tmp_path) == tmp_path / "var/diagnostics/run"
    assert diagnostic_output("run") == Path("var/diagnostics/run")


@pytest.mark.parametrize("session", ["live-20261022T235959Z", "live-20261023T000000Z", "live-20261104T120000Z"])
@pytest.mark.parametrize("suffix", ["", "images.jsonl", "0012.png"])
def test_live_diagnose_inputs_resolve_independently_of_local_session(tmp_path, monkeypatch, session, suffix):
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    relative = Path("live") / session / "run-01/diagnose"
    external = _write(dev / relative / "0012.png").parent
    _write(external / "images.jsonl")
    _write(repo / "var" / relative.parent.parent / "profile.json")
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    assert input_path(relative / suffix, repo_root=repo) == external / suffix


@pytest.mark.parametrize("spelling", ["relative", "var", "absolute", "linked"])
def test_diagnose_dir_prefers_local_then_external_then_missing_local(tmp_path, monkeypatch, spelling):
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    relative = Path("live/live-20261104T120000Z/run-01")
    local_image = _write(repo / "var" / relative / "diagnose/0012.png")
    external_image = _write(dev / relative / "diagnose/0012.png")
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    run = {"relative": relative, "var": Path("var") / relative,
           "absolute": local_image.parent.parent, "linked": local_image.parent.parent}[spelling]
    if spelling == "linked":
        shared = tmp_path / "shared-var"
        (repo / "var").rename(shared)
        (repo / "var").symlink_to(shared, target_is_directory=True)
        run = shared / relative
    local = repo / "var" / relative / "diagnose"
    assert _devdata.diagnose_dir(run, repo_root=repo) == (run / "diagnose" if run.is_absolute() else local)
    local_image.unlink()
    local.rmdir()
    assert _devdata.diagnose_dir(run, repo_root=repo) == external_image.parent
    external_image.unlink()
    external_image.parent.rmdir()
    assert _devdata.diagnose_dir(run, repo_root=repo) == local
    assert not local.exists()
    assert not external_image.parent.exists()


def test_diagnose_dir_without_dev_data_keeps_missing_local_path(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPREAD_DEV_DATA", raising=False)
    local = tmp_path / "var/live/live-20261104T120000Z/run-01/diagnose"
    assert _devdata.diagnose_dir(local.parent, repo_root=tmp_path) == local
    assert not local.exists()


@pytest.mark.parametrize("relative", [
    "live/live-20261104T120000Z/profile.json",
    "live/live-20261104T120000Z/run-01/session.json",
    "live/live-20261104T120000Z/run-01/other/diagnose/0012.png",
    "live/live-20261104T120000Z/run-01/diagnose/../../profile.json",
])
def test_live_diagnose_exception_does_not_redirect_other_product_inputs(tmp_path, monkeypatch, relative):
    dev = tmp_path / "dev"
    _write(dev / relative)
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    assert input_path(relative, repo_root=tmp_path) == tmp_path / "var" / relative


@pytest.mark.parametrize("relative", ["diagnostics/run", "workbench/run", "live/../outside/run"])
def test_diagnose_dir_does_not_redirect_other_recordings(tmp_path, monkeypatch, relative):
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    _write(dev / relative / "diagnose/0012.png")
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    run = repo / "var" / relative
    assert _devdata.diagnose_dir(run, repo_root=repo) == run / "diagnose"


def test_diagnose_dir_preserves_explicit_paths_outside_var(tmp_path, monkeypatch):
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    external = _write(dev / "live/live-20261104T120000Z/run-01/diagnose/0012.png").parent
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    assert _devdata.diagnose_dir(external.parent, repo_root=repo) == external
    run = tmp_path / "other/live/live-20261104T120000Z/run-01"
    assert _devdata.diagnose_dir(run, repo_root=repo) == run / "diagnose"


def test_output_uses_external_root_even_when_local_directory_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(tmp_path / "dev"))
    assert diagnostic_output("run/setup") == tmp_path / "dev/diagnostics/run/setup"
    assert not (tmp_path / "dev").exists()


@pytest.mark.parametrize("relative", ["/absolute", "../outside"])
def test_output_requires_relative_path(relative):
    with pytest.raises(ValueError):
        diagnostic_output(relative)


@pytest.mark.parametrize("name", ["rescue-20260925", "removed-20260928-sc", "removed-20260929-sc3a"])
def test_legacy_inputs_use_altlasten(tmp_path, monkeypatch, name):
    dev = tmp_path / "dev"
    external = _write(dev / "altlasten" / name / "still.png")
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    assert input_path(f"{name}/still.png", repo_root=tmp_path) == external


@pytest.mark.parametrize("relative,external_allowed", [
    ("live/live-20261022T235959Z/setup/still.png", True),
    ("live/live-20261023T000000Z/setup/still.png", False),
    ("diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json", False),
    ("workbench/datasets/samples", False),
])
def test_product_paths_do_not_use_external_data(tmp_path, monkeypatch, relative, external_allowed):
    dev = tmp_path / "dev"
    external = _write(dev / relative)
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    result = input_path(Path("var") / relative, repo_root=tmp_path)
    assert (result == external) is external_allowed


def test_glob_merges_recordings_with_local_priority(tmp_path, monkeypatch):
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    local = _write(repo / "var/diagnostics/a/still.png")
    _write(dev / "diagnostics/a/still.png")
    external = _write(dev / "diagnostics/b/still.png")
    _write(dev / "live/live-20261023T000000Z/setup/still.png")
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    assert recording_glob("diagnostics/*/still.png", repo_root=repo) == [local, external]
    assert recording_glob("live/*/setup/still.png", repo_root=repo) == []


def test_missing_recording_skips_only_the_calling_test(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPREAD_DEV_DATA", raising=False)
    monkeypatch.setattr("devdata_helpers.input_path", lambda _: tmp_path / "missing")
    with pytest.raises(pytest.skip.Exception, match="lokale Aufnahme fehlt: diagnostics/missing .*DISPREAD_DEV_DATA"):
        local_recording("diagnostics/missing")
    assert local_recording("diagnostics/missing", required=False) == tmp_path / "missing"


def test_replay_resolves_embedded_reference_without_changing_profile(tmp_path, monkeypatch):
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    reference = _write(dev / "diagnostics/run/still.png")
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    script = Path(__file__).resolve().parents[1] / "scripts/r13-replay.py"
    spec = importlib.util.spec_from_file_location("r13_devdata_replay", script)
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    monkeypatch.setattr(replay, "input_path", lambda path: input_path(path, repo_root=repo))
    original = json.dumps({"reference_frame": {"path": "var/diagnostics/run/still.png", "sha256": "behalten"},
                           "live_tracking": {"proposal": "behalten"}})
    profile = _write(tmp_path / "profile.json", original)
    with replay._pipeline_profile(profile) as resolved:
        data = json.loads(resolved.read_text())
        assert data["reference_frame"] == {"path": str(reference), "sha256": "behalten"}
        assert data["live_tracking"] == {"proposal": "behalten"}
    assert profile.read_text() == original
    assert not resolved.exists()


def test_logical_path_maps_external_recordings_back_to_var_schema(tmp_path, monkeypatch):
    dev = tmp_path / "dev"
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    assert logical_path(dev / "diagnostics/run/f.png") == Path("var/diagnostics/run/f.png")
    assert logical_path(dev / "live/live-20261014T1/setup/still.png") == Path(
        "var/live/live-20261014T1/setup/still.png")
    assert logical_path(dev / "altlasten/rescue-20260925/x.json") == Path("var/rescue-20260925/x.json")
    assert logical_path("var/live/live-20261026T1/setup/still.png") == Path(
        "var/live/live-20261026T1/setup/still.png")
    monkeypatch.delenv("DISPREAD_DEV_DATA")
    assert logical_path(dev / "diagnostics/run/f.png") == dev / "diagnostics/run/f.png"


def test_resolution_round_trips_to_the_spelling_used_before_the_move(tmp_path, monkeypatch):
    """Kennungen aus logical_path(input_path(p)) bleiben gleich, egal wo die Datei liegt."""
    repo, dev = tmp_path / "repo", tmp_path / "dev"
    monkeypatch.setenv("DISPREAD_DEV_DATA", str(dev))
    monkeypatch.chdir(repo.parent)
    _write(dev / "diagnostics/run/f.png")
    resolved = input_path("var/diagnostics/run/f.png", repo_root=repo)
    assert resolved == dev / "diagnostics/run/f.png"
    assert logical_path(resolved) == Path("var/diagnostics/run/f.png")
