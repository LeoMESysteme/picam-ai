"""Fensterauswertung mit und ohne Werteplan, echte Dateien in tmp_path."""

import importlib.util
import json
from pathlib import Path

import pytest
from test_r13_tracker_eval import recording

SCRIPT = Path(__file__).parents[1] / "scripts" / "r13-window-eval.py"


def module():
    spec = importlib.util.spec_from_file_location("r13_window_eval", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize("tracker", ["window", "frame", "ecc", "all"])
@pytest.mark.parametrize("without_plan", [False, True])
def test_tracker_und_ohne_plan(tmp_path, tracker, without_plan, capsys):
    profile = recording(tmp_path)
    if without_plan:
        (tmp_path / "commands.jsonl").unlink()
    out = tmp_path / "out.json"
    assert module().main([str(tmp_path), "--profile", str(profile), "--tracker", tracker, "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    names = {"window", "frame", "ecc"} if tracker == "all" else {tracker}
    assert set(data["frames"][0]["trackers"]) == names
    assert [row["settled"] for row in data["frames"]] == [False, False, True]
    factor = "ohne_plan" if without_plan else "2.0"
    assert all(row["factor"] == factor for row in data["frames"])
    assert data["frames"][-1]["serial"] == "spaeter"
    assert data["frames"][0]["capture_timestamp"]["base"] == "v4l2_monotonic"
    for name in names:
        summary = data["summary"]["settled"][factor][name]
        assert summary["frames"] == 1
        assert summary["timing_ms"]["median"] > 0
        if name != "ecc":
            assert summary["kept_share"] == 1
            assert summary["corner_deviation_px"]["max"] <= 1
    assert json.loads(capsys.readouterr().out) == data["summary"]


@pytest.mark.parametrize("alias", [False, True])
def test_var_ausgabe_gesperrt(tmp_path, alias, monkeypatch, capsys):
    evaluator = module()
    protected = SCRIPT.parents[1] / "var"
    if alias:
        shortcut = tmp_path / "alias"
        shortcut.symlink_to(protected, target_is_directory=True)
        protected = shortcut

    def must_not_evaluate(*args):
        pytest.fail("var-Sperre muss vor Auswertung greifen")

    monkeypatch.setattr(evaluator, "evaluate", must_not_evaluate)
    assert evaluator.main([str(tmp_path), "--profile", "missing.json", "--out", str(protected / "forbidden")]) == 1
    assert "var/" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["drop", "time", "count", "commands"])
def test_ohne_plan_behaelt_integritaetspruefung(tmp_path, bad):
    profile = recording(tmp_path)
    (tmp_path / "commands.jsonl").unlink()
    if bad in ("drop", "count"):
        session = json.loads((tmp_path / "session.json").read_text())
        session["frames_dropped_write_failed" if bad == "drop" else "frames_recorded"] = 5
        (tmp_path / "session.json").write_text(json.dumps(session))
    elif bad == "time":
        path = tmp_path / "frames.jsonl"
        path.write_text(path.read_text().replace("v4l2_monotonic", "synthetic"))
    else:
        (tmp_path / "commands.jsonl").write_text('{}\n')
    assert module().main([str(tmp_path), "--profile", str(profile)]) == 1
