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
            "checks": {
                "kanten": {"status": "WARNUNG", "metrics": {}, "cells": [8]},
                "rasterversatz": {"status": "OK", "metrics": {}},
            },
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


@pytest.mark.parametrize("route", ["quad", "glass"])
def test_propose_fixed_quad_runs_offset_and_setup_checks(tmp_path, monkeypatch, route):
    frame = tmp_path / "frame.png"
    cv2.imwrite(str(frame), np.full((360, 640, 3), 120, np.uint8))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"camera": _settings().to_dict()}))
    seen = []

    def evaluate(_image, _hint, quad, **_kwargs):
        seen.append(("evaluate", quad))
        return _fit()

    def offset(frames, quad):
        seen.append(("offset", frames[0][1], quad))
        return CheckResult("WARNUNG", {"max_abs_dx_cols": 0.16, "max_abs_dy_rows": 0.06})

    def check(*_args, **kwargs):
        seen.append(("checks", kwargs["offset_check"].status))
        return SimpleNamespace(
            overall="WARNUNG", checks={"kanten": SimpleNamespace(cells=())},
            to_dict=lambda: {"overall": "WARNUNG", "checks": {
                "kanten": {"status": "OK", "metrics": {}, "cells": []},
                "rasterversatz": kwargs["offset_check"].to_dict(),
            }},
        )

    monkeypatch.setattr(harvest_setup, "evaluate_quad", evaluate)
    monkeypatch.setattr(harvest_setup, "raster_offset_check", offset)
    monkeypatch.setattr(harvest_setup, "check_setup", check)
    monkeypatch.setattr(harvest_setup, "glass_quad_in_region", lambda *_args: QUAD)
    out = tmp_path / "proposal"
    argv = [
        "propose", "--frame", str(frame), "--hint-box", "0.1,0.1,0.8,0.5",
        "--camera-settings", str(settings), "--device-id", "d", "--session-id", "s",
        "--cell-text", "+12.3456 ", "--out", str(out),
    ]
    if route == "quad":
        argv += ["--quad", ",".join(str(value) for pair in QUAD for value in pair)]
    assert harvest_setup.main(argv) == 0
    proposal = json.loads((out / "proposal.json").read_text())
    assert proposal["setup_checks"]["checks"]["rasterversatz"]["status"] == "WARNUNG"
    assert [entry[0] for entry in seen] == ["evaluate", "offset", "checks"]


@pytest.mark.parametrize(("scene", "profile_name", "frame_number", "cell_text"), [
    ("ab4", "ab4-profile-regrid1.json", 16, "+0.46780 "),
    ("ab5", "ab5-profile", 7, "+0.46788 "),
    ("ab6", "ab6-profile", 20, "+0.46789 "),
    ("sc6", "sc6-profile", 15, "+0.46786 "),
])
def test_propose_accepts_validated_profile_quad_with_cell_text(
    tmp_path, scene, profile_name, frame_number, cell_text,
):
    diagnostics = Path(__file__).parents[1] / "var" / "diagnostics"
    profile_path = diagnostics / profile_name
    frame_path = diagnostics / f"{scene}-still" / "frames" / f"frame_{frame_number:06d}.png"
    if not profile_path.is_file() or not frame_path.is_file():
        pytest.skip(f"local diagnostic inputs missing for {scene}")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"camera": profile["camera"]}), encoding="utf-8")
    quad_arg = ",".join(str(value) for point in profile["quad"] for value in point)
    out = tmp_path / "proposal"

    rc = harvest_setup.main([
        "propose", "--frame", str(frame_path), "--hint-box", "0,0,1,1",
        "--camera-settings", str(settings), "--device-id", profile["device_id"],
        "--session-id", profile["session_id"], "--quad", quad_arg,
        "--cell-text", cell_text, "--out", str(out),
    ])
    assert rc == 0
    proposal = json.loads((out / "proposal.json").read_text(encoding="utf-8"))
    assert proposal["quad"] == profile["quad"]
    assert proposal["setup_checks"]["overall"] in {"OK", "WARNUNG"}
    assert proposal["setup_checks"]["checks"]["rasterversatz"]["status"] in {"OK", "WARNUNG"}


@pytest.mark.parametrize("route", ["quad", "glass"])
def test_propose_fixed_quad_rejects_bad_offset(tmp_path, monkeypatch, route):
    frame = tmp_path / "frame.png"
    cv2.imwrite(str(frame), np.full((360, 640, 3), 120, np.uint8))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"camera": _settings().to_dict()}))
    monkeypatch.setattr(harvest_setup, "evaluate_quad", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "raster_offset_check", lambda *_args: CheckResult("FEHLER", {}))
    monkeypatch.setattr(harvest_setup, "glass_quad_in_region", lambda *_args: QUAD)
    out = tmp_path / "proposal"
    argv = [
        "propose", "--frame", str(frame), "--hint-box", "0.1,0.1,0.8,0.5",
        "--camera-settings", str(settings), "--device-id", "d", "--session-id", "s",
        "--cell-text", "+12.3456 ", "--out", str(out),
    ]
    if route == "quad":
        argv += ["--quad", ",".join(str(value) for pair in QUAD for value in pair)]
    assert harvest_setup.main(argv) == 2
    assert not (out / "proposal.json").exists()


def test_propose_with_cell_text_rejects_missing_raster_check(tmp_path, monkeypatch):
    frame = tmp_path / "frame.png"
    cv2.imwrite(str(frame), np.full((360, 640, 3), 120, np.uint8))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"camera": _settings().to_dict()}))
    monkeypatch.setattr(harvest_setup, "evaluate_quad", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "raster_offset_check", lambda *_args: CheckResult("OK", {}))
    missing_raster = SimpleNamespace(
        overall="OK", checks={"kanten": SimpleNamespace(cells=())},
        to_dict=lambda: {"overall": "OK", "checks": {"kanten": {"status": "OK", "metrics": {}}}},
    )
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: missing_raster)
    out = tmp_path / "proposal"
    assert harvest_setup.main([
        "propose", "--frame", str(frame), "--hint-box", "0.1,0.1,0.8,0.5",
        "--camera-settings", str(settings), "--device-id", "d", "--session-id", "s",
        "--cell-text", "+12.3456 ", "--out", str(out),
        "--quad", ",".join(str(value) for pair in QUAD for value in pair),
    ]) == 2
    assert not (out / "proposal.json").exists()


@pytest.mark.parametrize("geometry_args", [
    ["--target-size", "320x160"],
    ["--grid", "0,20,10,150"],
])
def test_propose_with_cell_text_rejects_incompatible_geometry(tmp_path, monkeypatch, geometry_args):
    frame = tmp_path / "frame.png"
    cv2.imwrite(str(frame), np.full((360, 640, 3), 120, np.uint8))
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"camera": _settings().to_dict()}))
    monkeypatch.setattr(harvest_setup, "evaluate_quad", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "raster_offset_check", lambda *_args: CheckResult("OK", {}))
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: _checks())
    out = tmp_path / "proposal"
    assert harvest_setup.main([
        "propose", "--frame", str(frame), "--hint-box", "0.1,0.1,0.8,0.5",
        "--camera-settings", str(settings), "--device-id", "d", "--session-id", "s",
        "--cell-text", "+12.3456 ", "--out", str(out),
        "--quad", ",".join(str(value) for pair in QUAD for value in pair), *geometry_args,
    ]) == 2
    assert not (out / "proposal.json").exists()


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


def test_assist_reports_rejected_improved_quad_instead_of_using_start_quad(tmp_path, monkeypatch, capsys):
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
        return CheckResult("OK" if improved else "WARNUNG", {
            "max_abs_dx_cols": 0.05 if improved else 0.22,
            "max_abs_dy_rows": 0.05,
        })

    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="fake", capture=FakeCapture(), set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup, "fit_lattice", lambda *_args, **_kw: _fit())
    monkeypatch.setattr(harvest_setup, "raster_offset_check", fake_offset)
    monkeypatch.setattr(harvest_setup, "refine_quad", lambda *_args, **_kw: (better_quad, []))
    monkeypatch.setattr(harvest_setup, "evaluate_quad", lambda *_args, **_kw: "restfehler_zu_gross")
    monkeypatch.setattr(harvest_setup, "check_setup", lambda *_args, **_kw: _checks())
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    monotonic = iter((100.0, 131.0))
    monkeypatch.setattr(harvest_setup.time, "monotonic", lambda: next(monotonic))

    rc = harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "d", "--session-id", "s",
        "--hint-box", "0.1,0.1,0.8,0.5", "--cell-text", "+12.3456 ",
    ])
    assert rc == 2
    assert "restfehler_zu_gross" in capsys.readouterr().err
    assert not (out / "proposal.json").exists()


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


def test_serial_capture_masks_cells_changing_during_and_between_stills():
    class Port:
        def __init__(self):
            self.lines = iter((
                b"+01.2193 mV/V\r\n", b"+01.2194 mV/V\r\n",
                b"+01.2294 mV/V\r\n", b"+01.2295 mV/V\r\n",
            ))
            self.clears = 0

        def reset_input_buffer(self):
            self.clears += 1

        def readline(self):
            return next(self.lines)

    port = Port()
    captures = []

    def capture():
        captures.append(True)
        return np.zeros((1, 1, 3), np.uint8)

    first, first_text = harvest_setup._capture_with_serial_text(capture, port)
    second, second_text = harvest_setup._capture_with_serial_text(capture, port)
    first_text, second_text = harvest_setup._mask_changed_cells(first_text, second_text)
    assert first.shape == second.shape
    assert captures == [True, True]
    assert port.clears == 4
    assert first_text == second_text == "+ 1.2?9? "


def test_masked_serial_text_reaches_real_offset_check_without_unknown_glyph():
    class Port:
        def __init__(self):
            self.lines = iter((b"+01.2193 mV/V\r\n", b"+01.2194 mV/V\r\n"))

        def reset_input_buffer(self):
            pass

        def readline(self):
            return next(self.lines)

    image, text = harvest_setup._capture_with_serial_text(
        lambda: np.full((360, 640, 3), 120, np.uint8), Port(),
    )
    assert "?" in text
    check = harvest_setup.raster_offset_check([(image, text)], QUAD)
    assert isinstance(check, CheckResult)
    assert check.reason != "messung_unmoeglich:KeyError"


def test_heldout_requires_meaningful_improvement():
    def offset(value):
        return CheckResult("OK", {"max_abs_dx_cols": value, "max_abs_dy_rows": 0.04})

    assert not harvest_setup._heldout_improves(offset(0.10), offset(0.09))
    assert harvest_setup._heldout_improves(offset(0.10), offset(0.07))


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


@pytest.mark.parametrize("serial_change", [None, "one", "many"])
def test_assist_runs_real_lattice_and_checks_with_synthetic_camera(tmp_path, monkeypatch, serial_change):
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

    serial_port = None
    if serial_change is not None:
        class FakeSerial:
            reads = 0
            closed = False

            def reset_input_buffer(self):
                pass

            def readline(self):
                self.reads += 1
                if self.reads % 2:
                    return b"+12.3456 mV/V\r\n"
                return b"+12.3457 mV/V\r\n" if serial_change == "one" else b"+98.7654 mV/V\r\n"

            def close(self):
                self.closed = True

        serial_port = FakeSerial()
        monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=lambda *_args, **_kw: serial_port))

    argv = ["assist", "--out", str(out), "--device-id", "d", "--session-id", "s", "--hint-box", hint_box]
    if serial_change is None:
        argv += ["--cell-text", "+12.3456 "]
    rc = harvest_setup.main(argv)
    assert rc == (2 if serial_change == "many" else 0)
    if serial_port is not None:
        assert serial_port.reads == 4
        assert serial_port.closed
    assert capture.released
    assert capture.reads >= 22
    if serial_change == "many":
        assert not (out / "proposal.json").exists()
        return
    proposal = json.loads((out / "proposal.json").read_text())
    assert proposal["grid_source"] == "dot_lattice"
    assert np.max(np.linalg.norm(np.asarray(proposal["quad"]) - quad, axis=1)) <= 1.5
    assert proposal["setup_checks"]["checks"]["stabilitaet"]["metrics"]["elapsed_s"] == 31.0
    assert (out / "overlay_source.png").is_file()
    assert (out / "overlay_sampling.png").is_file()


@pytest.mark.parametrize(("scene", "frame_number", "cell_text", "hint_box"), [
    ("sc6", 15, "+0.46786 ", "0.034443,0.689981,0.443562,0.088000"),
    ("ab5", 7, "+0.46788 ", "0.122188,0.330565,0.385625,0.254333"),
])
def test_assist_real_still_completes_fit_refine_and_checks(
    tmp_path, monkeypatch, scene, frame_number, cell_text, hint_box,
):
    frame_dir = Path(__file__).parents[1] / "var" / "diagnostics" / f"{scene}-still" / "frames"
    first_path = frame_dir / f"frame_{frame_number:06d}.png"
    second_path = frame_dir / "frame_000030.png"
    if not first_path.is_file() or not second_path.is_file():
        pytest.skip(f"diagnostic still missing in {frame_dir}")
    first_image = cv2.imread(str(first_path))
    second_image = cv2.imread(str(second_path))
    assert first_image is not None and second_image is not None
    assert first_image.shape == second_image.shape
    height, width = first_image.shape[:2]
    settings = CameraSettings(
        model=STREAMCAM_MODEL, usb_id=STREAMCAM_USB_ID, size=(width, height),
        fourcc="YUYV", fps=30, controls=_settings().controls,
    )
    out = tmp_path / scene

    def fake_focus(args):
        args.out.mkdir(parents=True)
        (args.out / "camera-settings.json").write_text(json.dumps({"camera": settings.to_dict()}))
        return 0

    class StillCapture:
        released = False
        reads = 0

        def read(self):
            self.reads += 1
            return True, first_image if self.reads <= 11 else second_image

        def release(self):
            self.released = True

    capture = StillCapture()
    monkeypatch.setattr(harvest_setup, "run_focus", fake_focus)
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda _device: SimpleNamespace(
        device="injected", capture=capture, set_controls=lambda *_args: None,
    ))
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda _seconds: None)
    monotonic = iter((100.0, 131.0))
    monkeypatch.setattr(harvest_setup.time, "monotonic", lambda: next(monotonic))

    assert harvest_setup.main([
        "assist", "--out", str(out), "--device-id", "offline", "--session-id", scene,
        "--hint-box", hint_box, "--cell-text", cell_text,
    ]) == 0
    assert capture.released
    assert capture.reads == 22
    assert np.any(first_image != second_image)
    proposal = json.loads((out / "proposal.json").read_text())
    assert proposal["setup_checks"]["overall"] in {"OK", "WARNUNG"}
    assert proposal["setup_checks"]["checks"]["rasterversatz"]["status"] in {"OK", "WARNUNG"}
    initial_fit = harvest_setup.fit_lattice(
        first_image, harvest_setup._parse_hint_box(hint_box),
        empty_cells=harvest_setup.GSV2AS_EMPTY_CELLS,
    )
    assert not isinstance(initial_fit, str)
    initial_holdout = harvest_setup.raster_offset_check([(second_image, cell_text)], initial_fit.quad)
    final_holdout = harvest_setup.raster_offset_check([(second_image, cell_text)], proposal["quad"])
    assert not np.allclose(proposal["quad"], initial_fit.quad, atol=0.1)
    assert harvest_setup._heldout_improves(initial_holdout, final_holdout)
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
            "rasterversatz": {"status": "OK", "metrics": {}},
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
