"""Offline-Auswertung: echte Dateien im temporaeren Verzeichnis, kein var/."""

import importlib.util
import json
from pathlib import Path

import cv2
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "r13-tracker-eval.py"
FIXTURES = Path(__file__).parent / "fixtures" / "r13"


def module():
    spec = importlib.util.spec_from_file_location("r13_eval", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def recording(tmp_path):
    metadata = json.loads((FIXTURES / "r13-fixtures.json").read_text())
    reference = FIXTURES / "reference.jpg"
    (tmp_path / "frames").mkdir()
    rows = []
    for index, stamp in enumerate((10, 11.5, 12)):
        name = f"frame_{index}.png"
        image = cv2.imread(str(FIXTURES / "faktor-2_0.jpg"))
        assert cv2.imwrite(str(tmp_path / "frames" / name), image)
        rows.append({"file": name, "capture_timestamp": {"value_ns": int(stamp*1e9), "base": "v4l2_monotonic"}})
    session = {"clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 0}}
    (tmp_path / "session.json").write_text(json.dumps(session))
    files = {"frames": rows, "commands": [{"event": "resume_transmission", "label": "schedule[0] factor=2.0", "t_boot": 10}],
             "serial": [{"t_boot": 9, "text": "+01.2114 mV/V"}, {"t_boot": 11.6, "text": "spaeter"}]}
    for name, data in files.items():
        (tmp_path / f"{name}.jsonl").write_text("".join(json.dumps(row)+"\n" for row in data))
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps({"quad": metadata["quad"], "reference_frame": {"path": str(reference.resolve())}}))
    return profile


def test_auswertung_beider_tracker_und_overlay(tmp_path):
    profile = recording(tmp_path)
    out, overlay = tmp_path / "out.json", tmp_path / "overlay.png"
    assert module().main([str(tmp_path), "--profile", str(profile), "--tracker", "both",
                          "--out", str(out), "--overlay", str(overlay)]) == 0
    data = json.loads(out.read_text())
    assert len(data["frames"]) == 3
    assert [row["settled"] for row in data["frames"]] == [False, False, True]
    assert [row["serial"] for row in data["frames"]] == ["+01.2114 mV/V", "+01.2114 mV/V", "spaeter"]
    summary = data["summary"]["settled"]["2.0"]
    assert summary["ecc"]["kept_share"] == 0
    assert summary["ecc"]["reasons"] == {"low_score": 1}
    assert summary["frame"]["kept_share"] == 1
    assert summary["frame"]["corner_deviation_px"]["max"] <= 1
    assert data["summary"]["timing_ms"]["frame"]["median"] > 0
    assert data["frames"][0]["capture_timestamp"]["base"] == "v4l2_monotonic"
    painted = cv2.imread(str(overlay))
    assert painted is not None and painted.shape == cv2.imread(str(FIXTURES / "reference.jpg")).shape


@pytest.mark.parametrize("missing", ["session.json", "frames.jsonl", "serial.jsonl", "commands.jsonl", "frames/frame_1.png", "profile.json"])
def test_unvollstaendige_aufnahme_exit_1(tmp_path, missing, capsys):
    profile = recording(tmp_path)
    (tmp_path / missing).unlink()
    assert module().main([str(tmp_path), "--profile", str(profile)]) == 1
    assert "unvollstaendig" in capsys.readouterr().err


def test_falsche_zeitbasis_wird_nicht_ausgewertet(tmp_path, capsys):
    profile = recording(tmp_path)
    path = tmp_path / "frames.jsonl"
    path.write_text(path.read_text().replace("v4l2_monotonic", "synthetic"))
    assert module().main([str(tmp_path), "--profile", str(profile)]) == 1
    assert "Zeitbasis" in capsys.readouterr().err


def test_fehlender_zeitversatz_exit_1(tmp_path, capsys):
    profile = recording(tmp_path)
    (tmp_path / "session.json").write_text("{}")
    assert module().main([str(tmp_path), "--profile", str(profile)]) == 1
    assert "clock_offset" in capsys.readouterr().err


def test_zeitversatz_wird_beruecksichtigt(tmp_path):
    profile = recording(tmp_path)
    session = {"clock_offset_boottime_minus_monotonic_ns": {"start": 2_000_000_000, "end": 2_000_000_000}}
    (tmp_path / "session.json").write_text(json.dumps(session))
    result = module().evaluate(tmp_path, profile, "frame")
    assert all(row["settled"] for row in result["frames"])
    assert result["frames"][0]["t_boottime_ns"] == 12_000_000_000


def test_restore_ist_kein_stabiles_faktorfenster(tmp_path):
    profile = recording(tmp_path)
    with (tmp_path / "commands.jsonl").open("a") as stream:
        stream.write(json.dumps({"event": "resume_transmission", "label": "restore", "t_boot": 11.6}) + "\n")
    result = module().evaluate(tmp_path, profile, "frame")
    assert result["frames"][-1]["factor"] == "restore"
    assert not result["frames"][-1]["settled"]


def test_referenzpfad_relativ_zum_repo_statt_cwd(tmp_path, monkeypatch):
    profile = recording(tmp_path)
    data = json.loads(profile.read_text())
    data["reference_frame"]["path"] = "tests/fixtures/r13/reference.jpg"
    profile.write_text(json.dumps(data))
    monkeypatch.chdir(tmp_path)
    result = module().evaluate(tmp_path, profile, "frame")
    assert all(row["trackers"]["frame"]["kept"] for row in result["frames"])


@pytest.mark.parametrize("error_type", [TypeError, IndexError])
def test_programmierfehler_nicht_als_unvollstaendig_verstecken(tmp_path, monkeypatch, error_type):
    profile = recording(tmp_path)
    evaluator = module()

    def broken_update(self, image):
        raise error_type("Programmierfehler")

    monkeypatch.setattr(evaluator.FrameTracker, "update", broken_update)
    with pytest.raises(error_type, match="Programmierfehler"):
        evaluator.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame"])


def test_scorestatistik_nur_gehaltene_bilder():
    evaluator = module()
    rows = [{"factor": "1", "trackers": {"frame": {"kept": kept, "score": score,
             "reason": None if kept else "lcd_rand_fehlt", "corner_deviation_px": 0 if kept else None}}}
            for kept, score in [(False, 0), (False, 0.1), (True, 0.9)]]
    summary = evaluator._summary(rows, ["frame"])["1"]["frame"]
    assert summary["score_kept_frames"] == {"median": 0.9, "max": 0.9}
    assert evaluator._summary(rows[:2], ["frame"])["1"]["frame"]["score_kept_frames"] == {"median": None, "max": None}


def test_overlay_verwendet_einzigen_vorschlag(tmp_path, monkeypatch):
    profile = recording(tmp_path)
    evaluator = module()
    real_propose = evaluator.propose_regions
    calls = []

    def propose_once(*args):
        assert not calls, "Vorschlag fuer Overlay erneut erzeugt"
        calls.append(True)
        return real_propose(*args)

    monkeypatch.setattr(evaluator, "propose_regions", propose_once)
    overlay = tmp_path / "overlay.png"
    assert evaluator.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame",
                           "--overlay", str(overlay)]) == 0
    assert cv2.imread(str(overlay)) is not None


@pytest.mark.parametrize("option", ["--out", "--overlay"])
@pytest.mark.parametrize("alias", [False, True])
def test_var_ausgaben_vor_auswertung_verweigern(tmp_path, monkeypatch, option, alias, capsys):
    evaluator = module()
    protected = SCRIPT.parents[1] / "var"
    if alias:
        shortcut = tmp_path / "alias"
        shortcut.symlink_to(protected, target_is_directory=True)
        protected = shortcut

    def must_not_evaluate(*args, **kwargs):
        pytest.fail("Pfadsperre muss vor Auswertung und jedem Schreibzugriff greifen")

    monkeypatch.setattr(evaluator, "evaluate", must_not_evaluate)
    assert evaluator.main([str(tmp_path), "--profile", str(tmp_path / "missing.json"),
                           option, str(protected / "r13-forbidden-test-output")]) == 1
    assert "var/" in capsys.readouterr().err


@pytest.mark.parametrize("label", ["schedule[0]", "schedule[0] factor=", "schedule[0] factor=nan"])
def test_ungueltige_faktormarke_exit_1(tmp_path, label):
    profile = recording(tmp_path)
    (tmp_path / "commands.jsonl").write_text(json.dumps({"event": "resume_transmission", "label": label, "t_boot": 10}) + "\n")
    assert module().main([str(tmp_path), "--profile", str(profile)]) == 1
