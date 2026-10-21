"""Replay benutzt echte Tracker/Bilder, die Live-Freigabe und Aufnahmezeiten."""

import hashlib
import importlib.util
import json
import shutil
from dataclasses import replace
from pathlib import Path

import cv2
import pytest

from dispread.live.frame_tracking import FrameTrackingConfig, propose_regions
from dispread.live.session import LiveConfig
from dispread.ocr import ReadResult

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/r13-replay.py"
FIXTURES = ROOT / "tests/fixtures/r13"


def module():
    assert SCRIPT.is_file(), "Offline-Replay fehlt"
    spec = importlib.util.spec_from_file_location("r13_replay", SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def recording(tmp_path, factors=(1.0, 2.0, 0.5, 5.0, 10.0)):
    metadata = json.loads((FIXTURES / "r13-fixtures.json").read_text())
    reference = FIXTURES / "reference.jpg"
    profile = {
        "schema_version": 2, "device_id": "test", "session_id": "replay", "quad": metadata["quad"],
        "target_size": [400, 160], "grid": {"n_cells": 16, "left": 0, "pitch": 25,
            "top": 17.77777777777778, "bottom": 160, "dot_columns": 5, "gap_columns": 1},
        "scaler_crop": None, "min_source_dot_column_px": 5, "native_scale": 1.0,
        "min_native_dot_column_px": 5, "resolution_threshold_px": 2.6, "resolution_ok": True,
        "confirmed_by": "Testperson", "confirmed_at_utc": "2026-10-21T12:00:00+00:00",
        "reference_frame": {"path": str(reference), "sha256": hashlib.sha256(reference.read_bytes()).hexdigest()},
    }
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile))
    (tmp_path / "frames").mkdir()
    frames, serial, commands = [], [], []
    for window, factor in enumerate(factors):
        fixture = next(row for row in metadata["frames"] if row["factor"] == factor)
        start = 10 + window * 4
        commands.append({"event": "resume_transmission", "label": f"schedule[{window}] factor={factor}",
                         "t_boot": start})
        for index in range(7):
            t = start + index * .4
            serial.append({"t_boot": t, "text": fixture["serial"]})
            if index == 6:
                continue
            name = f"frame_{len(frames) + 1:06}.jpg"
            shutil.copyfile(FIXTURES / fixture["file"], tmp_path / "frames" / name)
            frames.append({"file": name, "frame_sequence": len(frames) + 1,
                           "capture_timestamp": {"value_ns": round(t * 1e9), "base": "v4l2_monotonic",
                                                 "semantics": "unknown", "uncertainty_ns": None}})
    write_rows(tmp_path / "frames.jsonl", frames)
    write_rows(tmp_path / "serial.jsonl", serial)
    write_rows(tmp_path / "commands.jsonl", commands)
    (tmp_path / "session.json").write_text(json.dumps({
        "clock_offset_boottime_minus_monotonic_ns": {"start": 0, "end": 0},
        "frames_recorded": len(frames), "serial_lines_recorded": len(serial),
        "commands_jsonl_event_count": len(commands), "frame_writer_finished": True,
    }))
    return profile_path


class ConstantReader:
    backend_id = "dotmatrix"
    declares_confidence_calibrated = False

    def read(self, crop, layout):
        assert crop.shape == (160, 400, 3)
        return ReadResult(raw_text="+ 1.2114 ", value=1.2114, sign_detected=True, sign_region_readable=True,
                          decimal_point_detected=True, decimal_point_index=1, unit_text="mV/V",
                          status_flags=frozenset(), glyphs=(), backend_id="dotmatrix", backend_version="test")


def fake_live_dependencies(tmp_path, monkeypatch, replay):
    calibration = tmp_path / "timing.json"
    calibration.write_text(json.dumps({"schema_version": 1, "camera_usb_id": "046d:0893",
        "guard_margin_ms": 325.9, "display_offset_ms": 89.6, "measured_at_utc": "2026-09-29T00:00:00+00:00",
        "sources": []}))
    config = replace(LiveConfig(), calibration=calibration)
    monkeypatch.setattr(replay, "LiveConfig", lambda: config)

    def reader(path, sha256, *, d_max_factor):
        assert path == config.templates and sha256 == config.templates_sha256 and d_max_factor == 1.0
        return ConstantReader()

    monkeypatch.setattr(replay.DotMatrixReader, "from_file", reader)


@pytest.mark.parametrize("without_templates", [False, True])
def test_ecc_verliert_2_5_rahmen_haelt_alle(tmp_path, monkeypatch, without_templates):
    profile = recording(tmp_path)
    replay = module()
    config = LiveConfig()
    real_reader = not without_templates and config.templates.is_file() and config.calibration.is_file()
    if not real_reader:
        fake_live_dependencies(tmp_path, monkeypatch, replay)
        # Ohne Vorlagen nur Geometrie pruefen; keine korrekten Werte erfinden.
        good_read = ConstantReader.read

        def unavailable(self, crop, layout):
            return replace(good_read(self, crop, layout), value=None)

        monkeypatch.setattr(ConstantReader, "read", unavailable)
    ecc = replay.evaluate(tmp_path, profile, "ecc")
    frame = replay.evaluate(tmp_path, profile, "frame")
    assert ecc["summary"]["by_factor"]["2.0"]["tracking_loss_reasons"] == {"low_score": 6}
    assert ecc["summary"]["by_factor"]["2.0"]["stable"]["tracking_loss_reasons"] == {"low_score": 4}
    assert ecc["summary"]["by_factor"]["5.0"]["unreadable_share"] == 1
    assert frame["summary"]["tracking_loss_reasons"] == {}
    if real_reader:
        for factor in ("2.0", "5.0"):
            assert frame["summary"]["by_factor"][factor]["valid_share"] > 0
    assert frame["regions_source"] == "offline_vorschlag"
    assert frame["summary"]["misreads"] == 0
    assert len(frame["frames"]) == 30 and len(frame["summary"]["windows"]) == 5
    assert frame["summary"]["processing_fps"] > 0
    assert frame["summary"]["frame_time_ms"]["p90"] >= frame["summary"]["frame_time_ms"]["median"] > 0
    assert frame["frames"][0]["record"]["capture_timestamp"] == {
        "value_ns": 10_000_000_000, "base": "v4l2_monotonic", "semantics": "unknown", "uncertainty_ns": None}


def test_bestaetigung_aufnahmezeit_und_stabiles_fenster(tmp_path, monkeypatch):
    profile = recording(tmp_path, (2.0,))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    out = tmp_path / "out.json"
    assert replay.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert [row["record"]["status"] for row in data["frames"]] == ["transition"] + ["valid"] * 5
    assert data["frames"][1]["record"]["confirmation_span_ns"] == 400_000_000
    assert data["summary"]["compared_valid"] == 4
    assert data["summary"]["undecided_valid"] == 1
    assert data["summary"]["by_factor"]["2.0"]["valid_share"] == 5 / 6
    window = data["summary"]["windows"][0]
    assert window["stable"]["valid_share"] == 1
    assert window["settled"]["frames"] == 2


def test_fehllesung_exit_1(tmp_path, monkeypatch):
    profile = recording(tmp_path, (2.0,))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    path = tmp_path / "serial.jsonl"
    path.write_text(path.read_text().replace("+01.2114 mV/V", "+09.9999 mV/V"))
    out = tmp_path / "out.json"
    assert replay.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame", "--out", str(out)]) == 1
    assert json.loads(out.read_text())["summary"]["misreads"] == 4


def test_abgelehntes_telegramm_wird_gezaehlt_und_maskiert_referenzfenster(tmp_path, monkeypatch):
    profile = recording(tmp_path, (2.0,))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    path = tmp_path / "serial.jsonl"
    serial = [json.loads(line) for line in path.read_text().splitlines()]
    serial[2]["text"] = "ungueltiges Telegramm"
    write_rows(path, serial)
    out = tmp_path / "out.json"
    assert replay.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame", "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["reference"] == {"lines": 7, "parse_errors": 1}
    assert data["summary"]["frames"] == 6
    assert data["summary"]["uncovered_valid"] == 4
    assert data["summary"]["compared_valid"] == 1
    assert data["summary"]["misreads"] == 0


@pytest.mark.parametrize("corruption", ["serial_text", "profile_type", "grid_type"])
def test_falsche_eingabetypen_ohne_traceback(tmp_path, monkeypatch, capsys, corruption):
    profile = recording(tmp_path, (2.0,))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    if corruption == "serial_text":
        path = tmp_path / "serial.jsonl"
        serial = [json.loads(line) for line in path.read_text().splitlines()]
        serial[2]["text"] = 42
        write_rows(path, serial)
    else:
        data = json.loads(profile.read_text())
        if corruption == "profile_type":
            data = []
        else:
            data["grid"] = None
        profile.write_text(json.dumps(data))
    out = tmp_path / "out.json"
    assert replay.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame", "--out", str(out)]) == 1
    error = capsys.readouterr().err
    assert "unvollstaendig oder ungueltig" in error
    assert "Traceback" not in error
    assert not out.exists()


def test_stale_nach_aufnahmezeit_statt_verarbeitungsuhr(tmp_path, monkeypatch):
    profile = recording(tmp_path, (2.0,))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    good_read = ConstantReader.read
    reads = []

    def fading(self, crop, layout):
        read = good_read(self, crop, layout)
        reads.append(True)
        return read if len(reads) <= 2 else replace(read, value=None, sign_region_readable=False)

    monkeypatch.setattr(ConstantReader, "read", fading)
    result = replay.evaluate(tmp_path, profile, "frame")
    assert [row["record"]["status"] for row in result["frames"]] == [
        "transition", "valid", "unreadable", "stale", "stale", "stale"]
    assert result["summary"]["stable"]["stale_share"] == .75
    assert all(row["record"]["value"] is None for row in result["frames"][2:])


@pytest.mark.parametrize("missing", ["session.json", "frames.jsonl", "serial.jsonl", "commands.jsonl",
                                    "frames/frame_000002.jpg"])
def test_unvollstaendig_exit_1(tmp_path, monkeypatch, missing, capsys):
    profile = recording(tmp_path, (2.0,))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    (tmp_path / missing).unlink()
    assert replay.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame"]) == 1
    assert "unvollstaendig" in capsys.readouterr().err


@pytest.mark.parametrize("alias", [False, True])
def test_var_sperre_vor_auswertung(tmp_path, monkeypatch, alias, capsys):
    replay = module()
    protected = ROOT / "var"
    if alias:
        shortcut = tmp_path / "alias"
        shortcut.symlink_to(protected, target_is_directory=True)
        protected = shortcut
    monkeypatch.setattr(replay, "evaluate", lambda *a, **kw: pytest.fail("Vor Pfadsperre ausgewertet"))
    assert replay.main([str(tmp_path), "--profile", "missing.json", "--tracker", "ecc",
                        "--out", str(protected / "forbidden-r5.json")]) == 1
    assert "var/" in capsys.readouterr().err


@pytest.mark.parametrize("corruption", ["hash", "unconfirmed", "calibration", "synthetic", "order", "count",
                                        "timestamp_bool", "uncertainty_text"])
def test_live_pruefungen_und_zeitbasis(tmp_path, monkeypatch, corruption):
    profile = recording(tmp_path, (2.0,))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    if corruption in ("hash", "unconfirmed"):
        data = json.loads(profile.read_text())
        if corruption == "hash":
            data["reference_frame"]["sha256"] = "0" * 64
        else:
            data["confirmed_by"] = ""
        profile.write_text(json.dumps(data))
    elif corruption == "calibration":
        (tmp_path / "timing.json").unlink()
    else:
        path = tmp_path / "frames.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if corruption == "synthetic":
            rows[0]["capture_timestamp"]["base"] = "synthetic"
        elif corruption == "order":
            rows.reverse()
        elif corruption == "timestamp_bool":
            rows[0]["capture_timestamp"]["value_ns"] = True
        elif corruption == "uncertainty_text":
            rows[0]["capture_timestamp"]["uncertainty_ns"] = "unbekannt"
        else:
            rows.pop()
        write_rows(path, rows)
    assert replay.main([str(tmp_path), "--profile", str(profile), "--tracker", "frame"]) == 1


def test_bestaetigte_bereiche_ohne_neuen_vorschlag(tmp_path, monkeypatch):
    profile = recording(tmp_path, (2.0,))
    data = json.loads(profile.read_text())
    config = FrameTrackingConfig()
    proposal = propose_regions(cv2.imread(data["reference_frame"]["path"]), data["quad"], config)
    data["live_tracking"] = {"version": 1, "method": "rahmenbereiche",
        "frame_sha256": data["reference_frame"]["sha256"], "config": config.to_dict(), "proposal": proposal.to_dict()}
    profile.write_text(json.dumps(data))
    replay = module()
    fake_live_dependencies(tmp_path, monkeypatch, replay)
    monkeypatch.setattr(replay, "propose_regions", lambda *a: pytest.fail("Bestaetigte Bereiche ersetzt"))
    result = replay.evaluate(tmp_path, profile, "frame")
    assert result["regions_source"] == "profil" and result["summary"]["valid_share"] == 5 / 6
