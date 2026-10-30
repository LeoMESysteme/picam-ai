"""Offline-Einrichtung: echte R13-Bilder, gemeinsame Pruefungen, Live-Sperre."""

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from dispread.live.recording import load_recording
from dispread.live.session import LiveSession, StartRefused
from dispread.session_profile import SessionProfile

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests/fixtures/r13"
SCRIPT = ROOT / "scripts/r13-offline-setup.py"


def module():
    assert SCRIPT.is_file(), "Offline-Einrichtung fehlt"
    spec = importlib.util.spec_from_file_location("r13_offline_setup", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def recording(tmp_path):
    source = tmp_path / "recording"
    (source / "frames").mkdir(parents=True)
    frames = []
    # Alle Fixture-Frames sind identisch: getestet wird nur die Verdrahtung,
    # keine unabhaengige Stabilitaet oder Erkennungszuverlaessigkeit.
    for index, seconds in enumerate((10, 12, 12.1, 27.2, 28), start=1):
        name = f"frame_{index:06}.jpg"
        shutil.copyfile(FIXTURES / "faktor-1_0.jpg", source / "frames" / name)
        frames.append({"file": name, "frame_sequence": index, "capture_timestamp": {
            "value_ns": round(seconds * 1e9), "base": "v4l2_monotonic",
            "semantics": "unknown", "uncertainty_ns": None,
        }})
    write_rows(source / "frames.jsonl", frames)
    write_rows(source / "serial.jsonl", [
        {"t_boot": seconds, "text": "+0.60572 mV/V"} for seconds in (10, 12, 12.1, 27.2, 28)
    ])
    write_rows(source / "commands.jsonl", [
        {"event": "resume_transmission", "label": "schedule[0] factor=1.0", "t_boot": 10},
        {"event": "resume_transmission", "label": "schedule[1] factor=2.0", "t_boot": 40},
    ])
    image = cv2.imread(str(FIXTURES / "faktor-1_0.jpg"))
    (source / "session.json").write_text(json.dumps({
        "clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 0},
        "camera": {"camera_model": "logitech_streamcam", "usb_id": "046d:0893",
            "size": [image.shape[1], image.shape[0]], "fourcc": "YUYV", "fps": 30,
            "controls_readback": {"focus_absolute": 48, "exposure_time_absolute": 156,
                                  "white_balance_temperature": 4600, "gain": 10}},
    }))
    return source


@pytest.mark.parametrize("suffixes", [(".jpg", ".jpg"), (".png", ".JPEG"), (".png", ".png")])
def test_jpeg_source_warning_before_fit_even_when_fit_fails(tmp_path, monkeypatch, capsys, suffixes):
    from dispread.live import setup as live_setup

    source = recording(tmp_path)
    rows = [json.loads(line) for line in (source / "frames.jsonl").read_text().splitlines()]
    for index, suffix in zip((2, 3), suffixes, strict=True):
        old = source / "frames" / rows[index]["file"]
        new = old.with_suffix(suffix)
        assert cv2.imwrite(str(new), cv2.imread(str(old)))
        rows[index]["file"] = new.name
    write_rows(source / "frames.jsonl", rows)

    def refuse_fit(*args, **kwargs):
        raise ValueError("keine_startlage")

    monkeypatch.setattr(live_setup, "assist_measure", refuse_fit)
    assert module().main([str(source), "--out", str(tmp_path / "setup")]) == 1
    warning = capsys.readouterr().err
    if any(suffix.lower() in (".jpg", ".jpeg") for suffix in suffixes):
        assert "WARNUNG" in warning and "JPEG" in warning
        assert "Rasterfit" in warning and "nicht repraesentativ" in warning
    else:
        assert "JPEG" not in warning


def test_recording_setup_uses_real_checks_and_copied_reference(tmp_path, capsys):
    source = recording(tmp_path)
    before = {path.relative_to(source): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in source.rglob("*") if path.is_file()}
    out = tmp_path / "setup"
    assert module().main([str(source), "--out", str(out)]) == 0
    result = json.loads((out / "setup-result.json").read_text())
    assert result["first"]["file"] == "frame_000003.jpg"
    assert result["second"]["file"] == "frame_000004.jpg"
    assert result["first"]["cell_text"] == "+0.60572 "
    assert result["stability_elapsed_s"] == pytest.approx(15.1)
    profile = SessionProfile.load(out / "profile.json")
    assert profile.offline is True
    assert profile.confirmed_by == "offline-auswertung"
    assert profile.reference_frame["path"] == str(out / "still.png")
    assert profile.reference_frame["sha256"] == hashlib.sha256((out / "still.png").read_bytes()).hexdigest()
    assert profile.live_tracking is not None
    for name in ("rasterversatz", "gegenlesen", "nachfuehrung", "displayfehler"):
        assert name in profile.setup_checks["checks"]
    assert profile.setup_checks["checks"]["gegenlesen"]["status"] == "OK"
    for name in ("still.png", "stability.png", "overlay_source.png", "overlay_rectified.png", "overlay_sampling.png"):
        assert cv2.imread(str(out / name)) is not None
    np.testing.assert_array_equal(cv2.imread(str(out / "still.png")),
                                  cv2.imread(str(source / "frames/frame_000003.jpg")))
    assert before == {path.relative_to(source): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in source.rglob("*") if path.is_file()}
    output = capsys.readouterr().out
    assert "nachfuehrung" in output and "displayfehler" in output
    replay_spec = importlib.util.spec_from_file_location("r13_replay", ROOT / "scripts/r13-replay.py")
    replay = importlib.util.module_from_spec(replay_spec)
    replay_spec.loader.exec_module(replay)
    replay_result = replay.evaluate(source, out / "profile.json", "frame")
    assert replay_result["offline"] is True and replay_result["regions_source"] == "profil"
    assert replay_result["summary"]["frames"] == 5
    tracker_spec = importlib.util.spec_from_file_location("r13_tracker_eval", ROOT / "scripts/r13-tracker-eval.py")
    tracker = importlib.util.module_from_spec(tracker_spec)
    tracker_spec.loader.exec_module(tracker)
    tracked = tracker.evaluate(source, out / "profile.json", "both")
    assert tracked["summary"]["settled"]["1.0"]["frame"]["kept_share"] == 1.0


def test_offline_profile_refused_before_live_resources_or_output(tmp_path):
    # Bestehender Profilvertrag: nur die neue Offline-Markierung unterscheidet ihn.
    from test_live_session import _files

    path, config = _files(tmp_path)
    data = json.loads(path.read_text())
    data["offline"] = True
    data["confirmed_by"] = "offline-auswertung"
    path.write_text(json.dumps(data))
    run = tmp_path / "run"

    def forbidden_reader(*args, **kwargs):
        pytest.fail("Offline-Profil muss vor dem Leseraufbau abgewiesen werden")

    session = LiveSession(SimpleNamespace(), path, config, run, reader_factory=forbidden_reader)
    with pytest.raises(StartRefused, match="Offline-Profil"):
        session.start()
    assert not run.exists()
    loaded = SessionProfile.load(path)
    loaded.save(path)
    assert json.loads(path.read_text())["offline"] is True


@pytest.mark.parametrize("marker", [None, 1, "false", [], {}])
def test_malformed_offline_marker_is_rejected(tmp_path, marker):
    from test_live_session import _files

    path, _ = _files(tmp_path)
    data = json.loads(path.read_text())
    data["offline"] = marker
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="offline"):
        SessionProfile.load(path)


@pytest.mark.parametrize("change,reason", [
    ("synthetic_time", "Zeitbasis"), ("unknown_serial", "telegram"),
    ("no_stability", "Stabilitaet"), ("no_camera", "camera"),
])
def test_unverifiable_recording_is_rejected(tmp_path, change, reason, capsys):
    source = recording(tmp_path)
    if change == "synthetic_time":
        path = source / "frames.jsonl"
        path.write_text(path.read_text().replace("v4l2_monotonic", "synthetic"))
    elif change == "unknown_serial":
        path = source / "serial.jsonl"
        path.write_text(path.read_text().replace("+0.60572 mV/V", "???"))
    elif change == "no_stability":
        path = source / "frames.jsonl"
        path.write_text("\n".join(path.read_text().splitlines()[:3]) + "\n")
    else:
        path = source / "session.json"
        path.write_text(json.dumps({"clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 0}}))
    out = tmp_path / "setup"
    assert module().main([str(source), "--out", str(out)]) == 1
    assert not (out / "profile.json").exists()
    result = json.loads((out / "setup-result.json").read_text())
    assert result["stage"] == "auswahl"
    assert reason.lower() in result["reason"].lower()
    assert "Traceback" not in capsys.readouterr().err


def test_output_under_var_is_refused_without_writes(tmp_path):
    out = ROOT / "var/r14-test-must-not-exist"
    assert not out.exists()
    assert module().main([str(tmp_path), "--out", str(out)]) == 1
    assert not out.exists()


def test_explicit_frame_and_text_and_missing_frame(tmp_path):
    source = recording(tmp_path)
    setup = module()
    first, second = setup.select_stills(load_recording(source), Path("frame_000003.jpg"), "+0.60571 ")
    assert first["cell_text"] == second["cell_text"] == "+0.60571 "
    assert first["file"] == "frame_000003.jpg" and second["file"] == "frame_000004.jpg"
    with pytest.raises(ValueError, match="Standbild"):
        setup.select_stills(load_recording(source), Path("absent.jpg"))
    with pytest.raises(ValueError, match=">2 s"):
        setup.select_stills(load_recording(source), Path("frame_000002.jpg"))


def test_fit_failure_keeps_reason_and_never_confirms(tmp_path, monkeypatch, capsys):
    from dispread.live import setup as live_setup

    source = recording(tmp_path)
    monkeypatch.setattr(live_setup, "fit_lattice", lambda *_args, **_kwargs: "keine_startlage")
    out = tmp_path / "setup"
    assert module().main([str(source), "--out", str(out)]) == 1
    result = json.loads((out / "setup-result.json").read_text())
    assert result["stage"] == "assist_measure"
    assert "keine_startlage" in result["reason"]
    assert result["attempts"][-1]["fit"] == "keine_startlage"
    assert "keine_startlage" in capsys.readouterr().out
    assert not (out / "profile.json").exists()
    assert (out / "source-first.jpg").read_bytes() == (source / "frames/frame_000003.jpg").read_bytes()
    assert (out / "source-second.jpg").read_bytes() == (source / "frames/frame_000004.jpg").read_bytes()


def test_nonempty_output_is_preserved(tmp_path):
    source = recording(tmp_path)
    out = tmp_path / "setup"
    out.mkdir()
    (out / "profile.json").write_text("vorhanden")
    assert module().main([str(source), "--out", str(out)]) == 1
    assert (out / "profile.json").read_text() == "vorhanden"
    assert list(out.iterdir()) == [out / "profile.json"]
