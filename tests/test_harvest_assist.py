"""Automatischer Einrichtungsweg ohne Hardwarezugriff."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from dispread.camera_settings import STREAMCAM_MODEL, STREAMCAM_USB_ID, CameraSettings
from dispread.charcells import CharGrid
from dispread.frames.uvc_source import UvcError
from dispread.ocr.dotmatrix_font import CLASSES, rom_vector
from dispread.ocr.dotmatrix_sampling import dot_centers
from dispread.ocr.dotmatrix_templates import Templates, save_templates
from dispread.setup_checks import CheckResult

SCRIPT = Path(__file__).parents[1] / "scripts" / "harvest-setup.py"
_spec = importlib.util.spec_from_file_location("harvest_assist_test", SCRIPT)
harvest_setup = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = harvest_setup
_spec.loader.exec_module(harvest_setup)

QUAD = [[80.0, 80.0], [480.0, 80.0], [480.0, 160.0], [80.0, 160.0]]


def _settings() -> CameraSettings:
    return CameraSettings(
        model=STREAMCAM_MODEL,
        usb_id=STREAMCAM_USB_ID,
        size=(640, 360),
        fourcc="YUYV",
        fps=30,
        controls={
            "focus_absolute": 48,
            "exposure_time_absolute": 157,
            "white_balance_temperature": 4600,
            "gain": 32,
        },
    )


def _fit():
    return SimpleNamespace(
        quad=QUAD,
        assigned_points=((100.0, 100.0),),
        rejected_points=((200.0, 100.0),),
    )


def _checks():
    return SimpleNamespace(
        overall="WARNUNG",
        checks={"kanten": SimpleNamespace(cells=(8,))},
        to_dict=lambda: {
            "overall": "WARNUNG",
            "checks": {"kanten": {"status": "WARNUNG", "metrics": {}, "cells": [8]}},
        },
    )


def _error_checks():
    return SimpleNamespace(
        overall="FEHLER",
        checks={"kanten": SimpleNamespace(status="FEHLER", metrics={"cell_step": [9.0]}, cells=(8,))},
        to_dict=lambda: {"overall": "FEHLER", "checks": {
            "kanten": {"status": "FEHLER", "metrics": {"cell_step": [9.0]}, "cells": [8]},
        }},
    )


def _raster_error_checks():
    return SimpleNamespace(
        overall="FEHLER",
        checks={"raster": CheckResult("FEHLER", {"assigned_fraction": 0.7})},
        to_dict=lambda: {"overall": "FEHLER", "checks": {
            "raster": {"status": "FEHLER", "metrics": {"assigned_fraction": 0.7}},
        }},
    )


@pytest.fixture
def mocked_offsets(monkeypatch):
    monkeypatch.setattr(harvest_setup, "raster_offset_check", lambda *_args, **_kw: CheckResult(
        "OK", {"max_abs_dx_cols": 0.05, "max_abs_dy_rows": 0.05},
    ))
    monkeypatch.setattr(harvest_setup, "refine_quad", lambda _frames, quad, *_args, **_kw: (np.asarray(quad), []))


def test_propose_auto_quad_writes_checks_and_sampling_overlay(tmp_path, monkeypatch, capsys, mocked_offsets):
    image = np.full((360, 640, 3), 120, dtype=np.uint8)
    frame = tmp_path / "frame.png"
    cv2.imwrite(str(frame), image)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"camera": _settings().to_dict()}))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: _fit(), raising=False)
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: _checks(), raising=False)

    out = tmp_path / "proposal"
    rc = harvest_setup.main([
        "propose", "--frame", str(frame), "--hint-box", "0.1,0.1,0.8,0.5",
        "--camera-settings", str(settings), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--out", str(out), "--auto-quad",
    ])
    assert rc == 0
    proposal = json.loads((out / "proposal.json").read_text())
    assert proposal["quad"] == QUAD
    assert proposal["grid_source"] == "dot_lattice"
    assert proposal["setup_checks"]["overall"] == "WARNUNG"
    assert (out / "overlay_source.png").is_file()
    assert (out / "overlay_sampling.png").is_file()
    assert "overlay_sampling.png" in capsys.readouterr().out


def test_assist_rejects_invalid_offline_text_before_camera(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(harvest_setup, "run_focus", lambda _args: pytest.fail("camera started"))
    rc = harvest_setup.main([
        "assist", "--out", str(tmp_path / "assist"), "--device-id", "d", "--session-id", "s",
        "--cell-text", "+12.34x6 ",
    ])
    assert rc == 2
    assert "Zellentext" in capsys.readouterr().err


@pytest.mark.parametrize("failure", ["offset", "raster"])
def test_assist_final_error_writes_no_proposal(tmp_path, monkeypatch, capsys, failure):
    out = tmp_path / "assist"

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": _settings().to_dict()}))
        return 0

    class FakeCapture:
        def read(self):
            return True, np.full((360, 640, 3), 120, dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=FakeCapture(), set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: (
        _raster_error_checks() if failure == "raster" else _checks()
    ))
    monkeypatch.setattr(harvest_setup, "raster_offset_check", lambda *_args, **_kw: CheckResult(
        "FEHLER" if failure == "offset" else "OK",
        {"max_abs_dx_cols": 0.4 if failure == "offset" else 0.05, "max_abs_dy_rows": 0.1},
    ), raising=False)
    monkeypatch.setattr(harvest_setup, "refine_quad", lambda *_args, **_kw: (np.asarray(QUAD), []), raising=False)
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    monotonic = iter((100.0, 131.0))
    monkeypatch.setattr(harvest_setup.time, "monotonic", lambda: next(monotonic))
    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s",
        "--hint-box", "0.1,0.1,0.8,0.5", "--cell-text", "+12.3456 ",
    ])
    assert rc == 2
    output = capsys.readouterr()
    assert ("rasterversatz" if failure == "offset" else "raster: FEHLER") in output.out + output.err
    assert not (out / "proposal.json").exists()


def test_assist_adopts_refined_quad_only_with_better_heldout_offset(tmp_path, monkeypatch):
    out = tmp_path / "assist"
    better_quad = np.asarray(QUAD, dtype=float) + (2.0, 0.0)

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": _settings().to_dict()}))
        return 0

    class FakeCapture:
        def read(self):
            return True, np.full((360, 640, 3), 120, dtype=np.uint8)

        def release(self):
            pass

    def fake_offset(_frames, quad):
        improved = np.allclose(quad, better_quad)
        return CheckResult("OK" if improved else "FEHLER", {
            "max_abs_dx_cols": 0.05 if improved else 0.4,
            "max_abs_dy_rows": 0.05,
        })

    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=FakeCapture(), set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "raster_offset_check", fake_offset)
    monkeypatch.setattr(harvest_setup, "refine_quad", lambda *_args, **_kw: (better_quad, []))
    monkeypatch.setattr(harvest_setup, "evaluate_quad", lambda *_args, **_kw: SimpleNamespace(
        **{**vars(_fit()), "quad": better_quad.tolist()},
    ))
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: _checks())
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    monotonic = iter((100.0, 131.0))
    monkeypatch.setattr(harvest_setup.time, "monotonic", lambda: next(monotonic))
    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s",
        "--hint-box", "0.1,0.1,0.8,0.5", "--cell-text", "+12.3456 ",
    ])
    assert rc == 0
    assert np.allclose(json.loads((out / "proposal.json").read_text())["quad"], better_quad)


def test_offline_cell_text_file_and_serial_telegram(tmp_path):
    path = tmp_path / "cells.txt"
    path.write_text("+12.3456 \n", encoding="utf-8")
    assert harvest_setup._offline_cell_text(SimpleNamespace(cell_text=None, cell_text_file=path)) == "+12.3456 "

    class FakePort:
        cleared = False

        def reset_input_buffer(self):
            self.cleared = True

        def readline(self):
            return b"+01.2193 mV/V\r\n"

    port = FakePort()
    assert harvest_setup._serial_cell_text(port) == "+ 1.2193 "
    assert port.cleared


def test_propose_auto_quad_rejects_uncertain_start(tmp_path, monkeypatch, capsys):
    frame = tmp_path / "frame.png"
    cv2.imwrite(str(frame), np.full((360, 640, 3), 120, dtype=np.uint8))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"camera": _settings().to_dict()}))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: "startlage_mehrdeutig")
    out = tmp_path / "proposal"
    rc = harvest_setup.main([
        "propose", "--frame", str(frame), "--hint-box", "0.1,0.1,0.8,0.5",
        "--camera-settings", str(settings), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--out", str(out), "--auto-quad",
    ])
    assert rc == 2
    assert "startlage_mehrdeutig" in capsys.readouterr().err
    assert not (out / "proposal.json").exists()


def test_assist_uses_injected_camera_and_writes_two_stills(tmp_path, monkeypatch, mocked_offsets):
    out = tmp_path / "assist"

    def fake_focus(args):
        assert args.settle_s == 1.0
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": _settings().to_dict()}))
        return 0

    class FakeCapture:
        reads = 0
        released = False

        def read(self):
            self.reads += 1
            image = np.full((360, 640, 3), 120, dtype=np.uint8)
            image[80:160, 80:480] = (30, 160, 45)
            for row in range(3):
                for col in range(12):
                    cv2.circle(image, (100 + col * 28, 95 + row * 24), 3, (0, 35, 0), -1)
            return True, image

        def release(self):
            self.released = True

    capture = FakeCapture()
    camera_opens = []

    def fake_open(device):
        camera_opens.append(device)
        return SimpleNamespace(
            device="fake-device", capture=capture,
            set_controls=lambda *_args: None,
        )

    events = []
    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", fake_open)
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda value: events.append(("sleep", value)))

    def fake_fit(_image, hint_box, **_kwargs):
        assert hint_box[0] < 80 / 640
        assert hint_box[0] + hint_box[2] > 480 / 640
        events.append(("fit", None))
        return _fit()

    monkeypatch.setattr(harvest_setup, "fit_lattice", fake_fit, raising=False)
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: _checks(), raising=False)

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--stability-s", "30",
    ])
    assert rc == 0
    assert camera_opens == [None]
    assert capture.released
    assert capture.reads >= 22  # vor jedem Standbild mindestens 10 alte Frames
    assert ("sleep", 30.0) in events
    assert events.index(("fit", None)) < events.index(("sleep", 30.0))
    assert events.count(("fit", None)) == 1
    proposal = json.loads((out / "proposal.json").read_text())
    assert proposal["setup_checks"]["overall"] == "WARNUNG"
    assert (out / "still.png").is_file()
    assert (out / "stability.png").is_file()
    assert (out / "overlay_source.png").is_file()
    assert (out / "overlay_sampling.png").is_file()


def test_assist_reports_precheck_error_without_stability_wait(tmp_path, monkeypatch, capsys, mocked_offsets):
    out = tmp_path / "assist"

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": _settings().to_dict()}))
        return 0

    class FakeCapture:
        reads = 0
        released = False

        def read(self):
            self.reads += 1
            return True, np.full((360, 640, 3), 120, dtype=np.uint8)

        def release(self):
            self.released = True

    capture = FakeCapture()
    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=capture, set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: _error_checks())
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: pytest.fail("Stabilitaetswartezeit begonnen"))

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--hint-box", "0.1,0.1,0.8,0.5",
    ])
    assert rc == 2
    assert capture.released
    assert capture.reads == 11
    assert "kanten: FEHLER" in capsys.readouterr().out
    assert not (out / "stability.png").exists()
    assert not (out / "proposal.json").exists()


def test_assist_records_measured_stability_elapsed(tmp_path, monkeypatch, mocked_offsets):
    out = tmp_path / "assist"

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": _settings().to_dict()}))
        return 0

    class FakeCapture:
        def read(self):
            return True, np.full((360, 640, 3), 120, dtype=np.uint8)

        def release(self):
            pass

    timestamps = iter((100.0, 131.25))
    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=FakeCapture(), set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: _checks())
    monkeypatch.setattr(harvest_setup.time, "monotonic", lambda: next(timestamps))
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    proposed_elapsed = []
    original_propose = harvest_setup.run_propose

    def record_propose(args):
        proposed_elapsed.append(args.stability_elapsed_s)
        return original_propose(args)

    monkeypatch.setattr(harvest_setup, "run_propose", record_propose)

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--hint-box", "0.1,0.1,0.8,0.5",
    ])
    assert rc == 0
    assert proposed_elapsed == [31.25]


def test_assist_runs_real_lattice_and_checks_with_synthetic_camera(tmp_path, monkeypatch):
    """Die CLI-Datenkette nutzt echte Rasteranpassung und echte Pruefungen."""
    out = tmp_path / "assist"
    settings = CameraSettings(
        model=STREAMCAM_MODEL, usb_id=STREAMCAM_USB_ID, size=(1920, 1080),
        fourcc="YUYV", fps=30, controls=_settings().controls,
    )
    quad = np.float32([[600, 480], [1272, 480], [1272, 650], [600, 650]])
    grid = CharGrid(16, 0.0, 25.0, 160.0 / 9.0, 160.0)
    display = np.full((160, 400), 210, dtype=np.uint8)
    for cell, char in enumerate("+12.3456 9012   "):
        for active, (x, y) in zip(rom_vector(char), dot_centers(grid, cell), strict=True):
            if active:
                cv2.circle(display, (round(float(x)), round(float(y))), 2, 30, -1)
    display = cv2.GaussianBlur(display, (0, 0), 0.7)
    transform = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [399, 0], [399, 159], [0, 159]]), quad,
    )
    image = cv2.warpPerspective(display, transform, settings.size, borderValue=120)
    rng = np.random.default_rng(73)
    image = np.clip(image.astype(float) + rng.normal(0, 1, image.shape), 0, 255).astype(np.uint8)
    image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    margin = (quad.max(axis=0) - quad.min(axis=0)) * 0.1
    x0, y0 = quad.min(axis=0) - margin
    x1, y1 = quad.max(axis=0) + margin
    hint_box = f"{x0 / 1920},{y0 / 1080},{(x1 - x0) / 1920},{(y1 - y0) / 1080}"

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": settings.to_dict()}))
        return 0

    class FakeCapture:
        reads = 0
        released = False

        def read(self):
            self.reads += 1
            return True, image.copy()

        def release(self):
            self.released = True

    capture = FakeCapture()
    monotonic = iter((100.0, 131.0))
    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=capture, set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(harvest_setup.time, "monotonic", lambda: next(monotonic))

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--hint-box", hint_box,
    ])
    assert rc == 0
    assert capture.released
    assert capture.reads >= 22
    proposal = json.loads((out / "proposal.json").read_text())
    assert proposal["grid_source"] == "dot_lattice"
    assert np.max(np.linalg.norm(np.asarray(proposal["quad"]) - quad, axis=1)) <= 1.5
    assert proposal["setup_checks"]["checks"]["stabilitaet"]["metrics"]["elapsed_s"] == 31.0
    assert (out / "overlay_source.png").is_file()
    assert (out / "overlay_sampling.png").is_file()


def test_assist_reader_diagnostic_is_persisted_and_reported(tmp_path, monkeypatch, capsys, mocked_offsets):
    out = tmp_path / "assist"

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": _settings().to_dict()}))
        return 0

    class FakeCapture:
        def read(self):
            return True, np.full((360, 640, 3), 120, dtype=np.uint8)

        def release(self):
            pass

    diagnostic_calls = []
    overlay_statuses = []

    def fake_diagnose(frames, quad, path, sha256):
        diagnostic_calls.append((len(frames), quad, path, sha256))
        return CheckResult("WARNUNG", {
            "frames": 2, "read_count": 0, "read_rate": 0.0,
            "rejection_reasons": {"format": 2},
        })

    def fake_source_overlay(frame, _fit, status):
        overlay_statuses.append(status)
        return frame.copy()

    ok_checks = SimpleNamespace(
        overall="OK",
        checks={"kanten": SimpleNamespace(cells=())},
        to_dict=lambda: {"overall": "OK", "checks": {
            "kanten": {"status": "OK", "metrics": {}, "cells": []},
        }},
    )
    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=FakeCapture(), set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: ok_checks)
    monkeypatch.setattr(harvest_setup, "diagnose_reader", fake_diagnose)
    monkeypatch.setattr(harvest_setup, "draw_source_overlay", fake_source_overlay)
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    monotonic = iter((100.0, 131.0))
    monkeypatch.setattr(harvest_setup.time, "monotonic", lambda: next(monotonic))
    templates = tmp_path / "templates.json"
    sha256 = save_templates(Templates(
        mean={ch: rom_vector(ch) for ch in CLASSES},
        std={ch: np.full(40, 0.1, np.float32) for ch in CLASSES},
        d_max=1.0, margin_min=0.2, groups=("synthetisch",),
        counts={ch: 1 for ch in CLASSES},
    ), templates)

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--hint-box", "0.1,0.1,0.8,0.5", "--templates", str(templates),
        "--templates-sha256", sha256,
    ])
    assert rc == 0
    assert diagnostic_calls == [(2, QUAD, templates, sha256)]
    checks = json.loads((out / "proposal.json").read_text())["setup_checks"]
    assert checks["overall"] == "WARNUNG"
    assert checks["checks"]["gegenlesen"]["metrics"]["rejection_reasons"] == {"format": 2}
    assert overlay_statuses == ["WARNUNG"]
    assert "gegenlesen: WARNUNG" in capsys.readouterr().out


@pytest.mark.parametrize(("bad_checksum", "expected_error"), [
    (False, "normalization"),
    (True, "Pruefsumme"),
])
def test_assist_rejects_incompatible_or_wrong_checksum_templates_before_camera(
    tmp_path, monkeypatch, capsys, bad_checksum, expected_error,
):
    incompatible_templates = tmp_path / "templates.json"
    blob = json.dumps({"format_version": 3, "normalization": "bg_closing_shadow_v1"}).encode()
    incompatible_templates.write_bytes(blob)
    checksum = "0" * 64 if bad_checksum else hashlib.sha256(blob).hexdigest()
    monkeypatch.setattr(harvest_setup, "run_focus", lambda _args: pytest.fail("Fokus wurde gestartet"))
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: pytest.fail("Kamera wurde geoeffnet"))
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: pytest.fail("Wartezeit begonnen"))
    out = tmp_path / "assist"

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--templates", str(incompatible_templates), "--templates-sha256", checksum,
    ])
    assert rc == 2
    assert expected_error in capsys.readouterr().err
    assert not out.exists()


@pytest.mark.parametrize("flag", ["--templates", "--templates-sha256"])
def test_assist_requires_template_file_and_hash_together(tmp_path, monkeypatch, flag):
    monkeypatch.setattr(harvest_setup, "run_focus", lambda _args: pytest.fail("Fokus wurde gestartet"))
    assert harvest_setup.main([
        "assist", "--out", str(tmp_path), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        flag, "dummy",
    ]) == 2


@pytest.mark.parametrize("interval", ["29", "nan", "inf"])
def test_assist_rejects_bad_stability_interval_before_camera_access(tmp_path, monkeypatch, interval):
    def unexpected(_args):
        raise AssertionError("Kamera/Fokus darf bei ungueltigem Intervall nicht starten")

    monkeypatch.setattr(harvest_setup, "run_focus", unexpected)
    rc = harvest_setup.main([
        "assist", "--out", str(tmp_path), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--stability-s", interval,
    ])
    assert rc == 2


def test_focus_releases_camera_when_sweep_capture_fails(tmp_path, monkeypatch):
    class FailingCapture:
        released = False

        def read(self):
            return False, None

        def release(self):
            self.released = True

    capture = FailingCapture()
    monkeypatch.setattr(
        harvest_setup, "_open_camera_io",
        lambda _device: SimpleNamespace(
            device="fake-device", capture=capture,
            set_controls=lambda *_args: None,
        ),
    )
    monkeypatch.setattr(harvest_setup, "sweep_focus", lambda measure: measure(48))
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    args = SimpleNamespace(hint_box=None, device=None, settle_s=1.0, out=tmp_path)
    with pytest.raises(UvcError, match="kein Bild"):
        harvest_setup.run_focus(args)
    assert capture.released


def test_assist_rejects_bad_lattice_before_stability_wait(tmp_path, monkeypatch):
    out = tmp_path / "assist"

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": _settings().to_dict()}))
        return 0

    class FakeCapture:
        released = False

        def read(self):
            return True, np.full((360, 640, 3), 120, dtype=np.uint8)

        def release(self):
            self.released = True

    capture = FakeCapture()
    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=capture, set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: "startlage_mehrdeutig")
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: pytest.fail("Stabilitaetswartezeit begonnen"))

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--hint-box", "0.1,0.1,0.8,0.5",
    ])
    assert rc == 2
    assert capture.released
    assert not (out / "proposal.json").exists()


@pytest.mark.parametrize("box", ["0,0,0,0", "nan,0,0.5,0.5", "0.8,0.1,0.4,0.4"])
def test_assist_rejects_bad_hint_before_camera_access(tmp_path, monkeypatch, box):
    monkeypatch.setattr(harvest_setup, "run_focus", lambda _args: pytest.fail("Fokus wurde gestartet"))
    rc = harvest_setup.main([
        "assist", "--out", str(tmp_path), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
        "--hint-box", box,
    ])
    assert rc == 2


def test_assist_reports_focus_error_without_traceback(tmp_path, monkeypatch, capsys):
    def fail(_args):
        raise UvcError("kein Bild im Fokus-Sweep")

    monkeypatch.setattr(harvest_setup, "run_focus", fail)
    rc = harvest_setup.main([
        "assist", "--out", str(tmp_path), "--device-id", "d", "--session-id", "s", "--cell-text", "+12.3456 ",
    ])
    assert rc == 2
    assert "kein Bild im Fokus-Sweep" in capsys.readouterr().err
