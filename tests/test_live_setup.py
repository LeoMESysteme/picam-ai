from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from frame_tracking_helpers import reference_scene

from dispread.camera_settings import CameraSettings
from dispread.live import setup as live_setup


class FakeSetupCamera:
    device = "/dev/fake"

    def __init__(self, image):
        self.image = image
        self.controls = []

    def set_controls(self, controls):
        self.controls.append(list(controls))

    def get_controls(self, names):
        values = {"exposure_time_absolute": 156, "white_balance_temperature": 4600, "gain": 10}
        return {n: values[n] for n in names}

    def fresh_still(self, discard=10):
        return self.image


class SequenceSetupCamera(FakeSetupCamera):
    def __init__(self, values):
        super().__init__(None)
        self.images = iter(np.full((2, 3, 3), value, np.uint8) for value in values)
        self.discards = []

    def fresh_still(self, discard=10):
        self.discards.append(discard)
        return next(self.images)


@pytest.mark.parametrize("values,expected", [([250, 251, 253], 251), ([250, 253, 253], 252)])
def test_mean_still_averages_without_uint8_overflow_and_rounds(values, expected):
    cam = SequenceSetupCamera(values)
    image = live_setup.mean_still(cam, frames=3, discard=7)
    np.testing.assert_array_equal(image, np.full((2, 3, 3), expected, np.uint8))
    assert image.dtype == np.uint8
    assert cam.discards == [7, 0, 0]


def test_mean_still_one_frame_preserves_original():
    image = np.full((2, 3, 3), 253, np.uint8)
    cam = FakeSetupCamera(image)
    assert live_setup.mean_still(cam, frames=1) is image


@pytest.mark.parametrize("stability_s", [30.0, 15.0])
@pytest.mark.parametrize("explicit_hint", [None, (0.1, 0.2, 0.3, 0.4)])
def test_assist_retry_uses_successful_mean_text_hint_and_timestamp(monkeypatch, tmp_path, explicit_hint, stability_s):
    cam = SequenceSetupCamera([10, 12, 30, 34, 32, 32])
    texts = iter(["old", "new", "new"])
    brackets = []

    def cell_text(capture):
        start = len(cam.discards)
        image = capture()
        brackets.append((start, len(cam.discards)))
        return image, next(texts)

    hints = []

    def find_hint(image):
        value = int(image[0, 0, 0])
        hints.append(value)
        return (value / 100, 0.0, 0.5, 0.5)

    fit = SimpleNamespace(quad=[[0, 0], [3, 0], [3, 2], [0, 2]])
    searches = []

    def search(image, hint, **kwargs):
        searches.append((int(image[0, 0, 0]), hint, kwargs))
        return "keine_startlage" if len(searches) == 1 else fit

    checks = SimpleNamespace(overall="OK", checks={}, to_dict=lambda: {})
    checked = []

    def check(image, found_fit, **kwargs):
        checked.append((image, found_fit, kwargs))
        return checks

    refinement = []

    def refine(frame_texts, quad, *_args):
        refinement.extend(frame_texts)
        return quad, []

    offsets = []
    offset = SimpleNamespace(status="OK", metrics={}, to_dict=lambda: {})

    def raster(frame_texts, _quad):
        offsets.append(frame_texts)
        return offset

    monkeypatch.setattr(live_setup, "find_green_hint_box", find_hint)
    monkeypatch.setattr(live_setup, "fit_lattice", search)
    monkeypatch.setattr(live_setup, "check_setup", check)
    monkeypatch.setattr(live_setup, "refine_quad", refine)
    monkeypatch.setattr(live_setup, "raster_offset_check", raster)
    timestamps = iter([100.0, 110.0, 110.0 + stability_s])
    attempts = []
    messages, sleeps = [], []
    result = live_setup.assist_measure(
        cam, cell_text=cell_text, expected_size=(3, 2), out_dir=tmp_path, hint_box=explicit_hint,
        stack_frames=2, fit_attempts=3, info=messages.append, sleep=sleeps.append,
        monotonic=lambda: next(timestamps), stability_s=stability_s, min_stability_s=stability_s,
        on_attempt=attempts.append,
    )
    assert brackets == [(0, 2), (2, 4), (4, 6)]
    assert cam.discards == [10, 0, 10, 0, 10, 0]
    assert [value for value, _, _ in searches] == [11, 32]
    assert hints == ([11, 32] if explicit_hint is None else [])
    assert result.hint_box == (explicit_hint or (0.32, 0.0, 0.5, 0.5))
    assert searches[-1][1] == result.hint_box
    assert all(kwargs == {"empty_cells": live_setup.GSV2AS_EMPTY_CELLS} for _, _, kwargs in searches)
    np.testing.assert_array_equal(result.first, np.full((2, 3, 3), 32, np.uint8))
    np.testing.assert_array_equal(result.second, result.first)
    np.testing.assert_array_equal(cv2.imread(str(tmp_path / "still.png")), result.first)
    np.testing.assert_array_equal(cv2.imread(str(tmp_path / "stability.png")), result.second)
    assert result.first_text == result.second_text == "new"
    assert result.setup_attempt == 2
    assert checked[0][0] is result.first and checked[0][1] is fit
    assert checked[-1][2]["stability_image_bgr"] is result.second
    assert checked[-1][2]["stability_elapsed_s"] == result.stability_elapsed_s == stability_s
    assert refinement[0][0] is result.first and refinement[0][1] == "new"
    assert offsets[-1][0][0] is result.first and offsets[-1][0][1] == "new"
    assert offsets[-1][1][0] is result.second and offsets[-1][1][1] == "new"
    assert sleeps == [stability_s]
    assert checked[-1][2]["stability_min_elapsed_s"] == stability_s
    assert attempts == [
        {"attempt": 1, "still": "still", "masked": "old"},
        {"attempt": 1, "still": "still", "masked": "old", "fit": "keine_startlage"},
        {"attempt": 2, "still": "still", "masked": "new"},
        {"attempt": 2, "still": "still", "masked": "new", "fit": "ok"},
        {"attempt": 2, "still": "stability", "masked": "new"},
        {"attempt": 2, "still": "still", "masked": "new"},
        {"attempt": 2, "still": "stability", "masked": "new"},
    ]
    assert len(messages) == 2
    assert "1/3" in messages[0] and "2/3" in messages[1]


def test_assist_all_search_attempts_fail_with_last_reason(monkeypatch, tmp_path):
    cam = SequenceSetupCamera([10, 12, 20, 22, 30, 32])
    brackets = []
    reasons = iter(["keine_startlage", "startlage_mehrdeutig", "letzter_grund"])

    def cell_text(capture):
        image = capture()
        brackets.append(int(image[0, 0, 0]))
        return image, "text"

    monkeypatch.setattr(live_setup, "fit_lattice", lambda *_args, **_kwargs: next(reasons))
    messages = []
    with pytest.raises(live_setup.SetupError, match="Punktraster abgelehnt: letzter_grund;"):
        live_setup.assist_measure(
            cam, cell_text=cell_text, expected_size=(3, 2), out_dir=tmp_path,
            hint_box=(0.0, 0.0, 1.0, 1.0), stack_frames=2, fit_attempts=3, info=messages.append,
        )
    assert brackets == [11, 21, 31]
    assert cam.discards == [10, 0, 10, 0, 10, 0]
    assert len(messages) == 3 and "3/3" in messages[-1]


def test_focus_camera_turns_autofocus_off_first_and_reads_back(monkeypatch):
    cam = FakeSetupCamera(np.full((1080, 1920, 3), 128, np.uint8))
    monkeypatch.setattr(live_setup, "sharpness", lambda roi: 1000 - (cam.controls[-1][0][1] - 48) ** 2)
    settings, sweep = live_setup.focus_camera(cam, None, settle_s=0, sleep=lambda _s: None)
    assert cam.controls[0] == [("focus_automatic_continuous", 0)]
    assert cam.controls[1] == [("focus_absolute", 48)]
    assert cam.controls[-1] == [("auto_exposure", 3), ("white_balance_automatic", 1)]
    assert settings.controls == {
        "focus_absolute": 48, "exposure_time_absolute": 156, "white_balance_temperature": 4600, "gain": 10,
    }
    assert settings.device == "/dev/fake" and sweep[0][0] == 48


def test_offline_text_source_returns_capture_and_text():
    image = np.zeros((2, 2, 3), np.uint8)
    assert live_setup.offline_text_source("ABC")(lambda: image) == (image, "ABC")


def test_mask_changed_cells_rejects_length_mismatch():
    with pytest.raises(live_setup.SetupError, match="Laenge"):
        live_setup.mask_changed_cells("ab", "abc")


def test_assist_rejects_short_stability(tmp_path):
    cam = FakeSetupCamera(np.zeros((1080, 1920, 3), np.uint8))
    with pytest.raises(live_setup.SetupError, match="30"):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("x"), expected_size=(1920, 1080),
            out_dir=tmp_path, stability_s=5.0,
        )


def test_assist_rejects_wrong_still_size(tmp_path):
    cam = FakeSetupCamera(np.zeros((720, 1280, 3), np.uint8))
    with pytest.raises(live_setup.SetupError, match="Kameraaufloesung"):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("x"), expected_size=(1920, 1080), out_dir=tmp_path,
        )


_CAMERA = CameraSettings(model="logitech_streamcam", usb_id="046d:0893", size=(1920, 1080), fourcc="YUYV",
                         fps=30, controls={"focus_absolute": 48, "exposure_time_absolute": 156,
                                           "white_balance_temperature": 4600, "gain": 10})


def _proposal(tmp_path, overall="OK", raster="OK"):
    frame = tmp_path / "still.png"
    frame.write_bytes(b"png")
    return {
        "frame": str(frame), "device_id": "gsv-sensor-161a", "session_id": "live-test",
        "quad": [[0, 0], [400, 0], [400, 160], [0, 160]], "target_size": [400, 160],
        "grid": live_setup.LATTICE_GRID.to_dict(), "grid_source": "dot_lattice", "scaler_crop": None,
        "min_source_dot_column_px": 5.0, "native_scale": 1.0, "min_native_dot_column_px": 5.0,
        "camera": _CAMERA.to_dict(),
        "setup_checks": {"overall": overall, "checks": {"rasterversatz": {"status": raster}}},
    }


def test_confirm_builds_confirmed_profile(tmp_path):
    timestamp = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    profile = live_setup.confirm_proposal(_proposal(tmp_path), confirmed_by="Leonhard Hentschke",
                                          resolution_threshold_px=2.6, now=lambda: timestamp)
    assert profile.confirmed_by == "Leonhard Hentschke" and profile.resolution_ok
    assert profile.camera == _CAMERA and profile.reference_frame["path"].endswith("still.png")
    assert profile.confirmed_at_utc == timestamp.isoformat()


def test_confirm_refuses_fehler_without_override(tmp_path):
    with pytest.raises(live_setup.SetupError, match="FEHLER"):
        live_setup.confirm_proposal(_proposal(tmp_path, overall="FEHLER"), confirmed_by="x",
                                    resolution_threshold_px=2.6)


def test_confirm_refuses_empty_name(tmp_path):
    with pytest.raises(live_setup.SetupError, match="Name"):
        live_setup.confirm_proposal(_proposal(tmp_path), confirmed_by="  ", resolution_threshold_px=2.6)


def test_propose_with_fit_refuses_image_size_different_from_camera_settings(tmp_path):
    from types import SimpleNamespace

    fit = SimpleNamespace(quad=[[0, 0], [400, 0], [400, 160], [0, 160]])
    with pytest.raises(live_setup.SetupError, match="Bild ist"):
        live_setup.propose_with_fit(
            np.zeros((720, 1280, 3), np.uint8), fit=fit, frame_path=tmp_path / "still.png",
            camera_settings=_CAMERA, device_id="test", session_id="test", out_dir=tmp_path,
        )


def test_propose_with_fit_refuses_missing_offset_check_and_cell_text(tmp_path):
    from types import SimpleNamespace

    fit = SimpleNamespace(quad=[[0, 0], [400, 0], [400, 160], [0, 160]])
    with pytest.raises(live_setup.SetupError, match="Zellentext"):
        live_setup.propose_with_fit(
            np.zeros((1080, 1920, 3), np.uint8), fit=fit, frame_path=tmp_path / "still.png",
            camera_settings=_CAMERA, device_id="test", session_id="test", out_dir=tmp_path,
            offset_check=None, cell_text=None,
        )


@pytest.mark.parametrize("start,flat,method", [(48, False, "climb"), (68, False, "climb"),
                                              (200, True, "sweep")])
def test_focus_camera_sucht_ab_start_und_protokolliert_rueckfall(monkeypatch, start, flat, method):
    cam = FakeSetupCamera(np.zeros((12, 12), np.uint8))

    def score(_roi):
        focus = cam.controls[-1][0][1]
        if flat:
            return max(10.0, 1000.0 - (focus - 50) ** 2)
        return float(np.interp(focus, [0, 32, 40, 48, 56, 64, 80, 255],
                               [11, 79.6, 264.3, 431.6, 135.6, 55.3, 16, 11]))

    monkeypatch.setattr(live_setup, "sharpness", score)
    messages = []
    settings, measured = live_setup.focus_camera(cam, None, start_focus=start, sleep=lambda _s: None, info=messages.append)
    assert messages == ["Fokus: Bergsteigen"] + (["Fokus: Vollsweep (Rueckfall)"] if flat else [])
    assert measured[0][0] == start
    assert measured.focus_method == method
    assert abs(settings.controls["focus_absolute"] - (50 if flat else 48)) <= 2
    if not flat:
        assert len(measured) <= 12


@pytest.mark.parametrize("missing", [1, 3])
def test_assist_retries_missing_hint_with_fresh_mean(monkeypatch, tmp_path, missing):
    cam = SequenceSetupCamera([10, 12, 20, 22, 30, 32])
    seen = []

    def hint(image):
        seen.append(int(image[0, 0, 0]))
        return None if len(seen) <= missing else (0, 0, 1, 1)

    monkeypatch.setattr(live_setup, "find_green_hint_box", hint)
    monkeypatch.setattr(live_setup, "fit_lattice", lambda *_a, **_kw: "last_fit")
    reason = "Kein gruener Bereich" if missing == 3 else "last_fit"
    with pytest.raises(live_setup.SetupError, match=reason):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("text"), expected_size=(3, 2),
            out_dir=tmp_path, stack_frames=2, fit_attempts=3,
        )
    assert seen == [11, 21, 31]


def test_serial_cell_text_discards_partial_line_after_reset(monkeypatch):
    events = []
    lines = iter([b"partial\r\n", b"telegram\r\n"])

    class Port:
        def reset_input_buffer(self):
            events.append("reset")

        def readline(self):
            events.append("read")
            return next(lines)

    parsed = []
    monkeypatch.setattr(live_setup, "cell_text_from_telegram", lambda line: parsed.append(line) or "cells")
    assert live_setup.serial_cell_text(Port()) == "cells"
    assert parsed == [b"telegram"]
    assert events == ["reset", "read", "read"]


@pytest.mark.parametrize("minimum", [15.0, 30.0])
def test_propose_forwards_stability_minimum_without_final_checks(monkeypatch, tmp_path, minimum):
    called = []
    checks = SimpleNamespace(overall="OK", checks={"kanten": SimpleNamespace(cells=[])},
                             to_dict=lambda: {"overall": "OK", "checks": {"rasterversatz": {"status": "OK"}}})
    monkeypatch.setattr(live_setup, "check_setup", lambda *a, **kw: called.append(kw) or checks)
    monkeypatch.setattr(live_setup, "write_overlays", lambda *a, **kw: [])
    image, quad = reference_scene()
    fit = SimpleNamespace(quad=quad)
    cv2.imwrite(str(tmp_path / "still.png"), image)
    kwargs = {"stability_min_elapsed_s": minimum} if minimum == 15.0 else {}
    proposal = live_setup.propose_with_fit(
        image, fit=fit, frame_path=tmp_path / "still.png",
        camera_settings=replace(_CAMERA, size=image.shape[1::-1]), device_id="test", session_id="test", out_dir=tmp_path,
        offset_check=SimpleNamespace(status="OK"), stability_elapsed_s=minimum, setup_attempt=2, **kwargs,
    )
    assert called[0]["stability_min_elapsed_s"] == minimum
    assert proposal["setup_attempt"] == 2
    import json

    assert json.loads((tmp_path / "proposal.json").read_text())["setup_attempt"] == 2


@pytest.mark.parametrize("reader_status", ["OK", "WARNUNG", "FEHLER"])
def test_proposal_merges_reader_status(monkeypatch, tmp_path, reader_status):
    from dispread.setup_checks import CheckResult

    checks = SimpleNamespace(overall="OK", checks={"kanten": SimpleNamespace(cells=[])},
                             to_dict=lambda: {"overall": "OK", "checks": {"rasterversatz": {"status": "OK"}}})
    monkeypatch.setattr(live_setup, "write_overlays", lambda *a, **kw: [])
    image, quad = reference_scene()
    cv2.imwrite(str(tmp_path / "still.png"), image)
    proposal = live_setup.propose_with_fit(
        image, fit=SimpleNamespace(quad=quad),
        frame_path=tmp_path / "still.png", camera_settings=replace(_CAMERA, size=image.shape[1::-1]),
        device_id="test", session_id="test",
        out_dir=tmp_path, final_checks=checks, offset_check=CheckResult("OK", {}),
        reader_check=CheckResult(reader_status, {}),
    )
    assert proposal["setup_checks"]["overall"] == reader_status
    if reader_status == "FEHLER":
        with pytest.raises(live_setup.SetupError, match="FEHLER"):
            live_setup.confirm_proposal(proposal, confirmed_by="x", resolution_threshold_px=2.6)


@pytest.mark.parametrize("reference_kind", ["eingabe", "seriell"])
def test_assist_reader_gets_per_still_masks(monkeypatch, tmp_path, reference_kind):
    from dispread.setup_checks import CheckResult

    cam = SequenceSetupCamera([10, 20])
    texts = iter(["+0.60972 ", "+0.6097? "])
    fit = SimpleNamespace(quad=[[0, 0], [3, 0], [3, 2], [0, 2]])
    monkeypatch.setattr(live_setup, "fit_lattice", lambda *a, **kw: fit)
    monkeypatch.setattr(live_setup, "check_setup", lambda *a, **kw: SimpleNamespace(
        overall="OK", checks={}, to_dict=lambda: {}))
    monkeypatch.setattr(live_setup, "refine_quad", lambda *a: (fit.quad, []))
    monkeypatch.setattr(live_setup, "raster_offset_check", lambda *a: CheckResult("OK", {}))
    observed = []

    def diagnose(frames, *args, **kwargs):
        assert kwargs["reference_kind"] == reference_kind
        observed.extend(frames)

    monkeypatch.setattr(live_setup, "diagnose_reader", diagnose)
    result = live_setup.assist_measure(
        cam, cell_text=lambda capture: (capture(), next(texts)), expected_size=(3, 2),
        out_dir=tmp_path, hint_box=(0, 0, 1, 1), sleep=lambda _: None, templates=tmp_path / 't.json', reference_kind=reference_kind,
    )
    assert [text for _, text in observed] == ["+0.60972 ", "+0.6097? "]
    assert result.first_text == result.second_text == "+0.6097? "


@pytest.mark.parametrize("changing_tries", [0, 2, 5])
def test_capture_waits_for_stable_bracket_and_reports_used_try(changing_tries):
    class Port:
        def __init__(self):
            self.lines = iter(
                telegram for attempt in range(5)
                for telegram in (b"+0.60972 mV/V\r\n",
                                 b"+0.60973 mV/V\r\n" if attempt < changing_tries else b"+0.60972 mV/V\r\n"))

        def readline(self):
            return next(self.lines)

    captures, texts, messages = [], [], []

    def capture():
        captures.append(len(captures) + 1)
        return np.full((2, 3), captures[-1], np.uint8)

    image, text = live_setup.capture_with_text(
        capture, Port(), on_text=lambda before, after, tries: texts.append((before, after, tries)), info=messages.append,
    )
    tries = min(changing_tries + 1, 5)
    assert captures == list(range(1, tries + 1))
    assert np.all(image == tries)
    assert text == ("+0.6097? " if changing_tries == 5 else "+0.60972 ")
    assert texts == [("+0.60972 ", "+0.60973 " if changing_tries == 5 else "+0.60972 ", tries)]
    assert messages == [f"Standbild: Anzeige hat sich waehrend der Aufnahme geaendert, neuer Versuch {n}/5"
                        for n in range(2, tries + 1)]


def test_capture_retry_surfaces_serial_error_with_partial_texts():
    class Port:
        lines = iter([b"+0.60972 mV/V\r\n", b"+0.60973 mV/V\r\n", b"+0.60972 mV/V\r\n", b"Unsinn\r\n"])

        def readline(self):
            return next(self.lines)

    texts = []
    with pytest.raises(live_setup.SetupError, match="unlesbar"):
        live_setup.capture_with_text(
            lambda: np.zeros((2, 3), np.uint8), Port(),
            on_text=lambda before, after, tries: texts.append((before, after, tries)),
        )
    assert texts == [("+0.60972 ", None, 2)]


@pytest.mark.parametrize("first_status,second_status,specific", [
    ("OK", "FEHLER", True), ("WARNUNG", "FEHLER", True),
    ("FEHLER", "FEHLER", False), ("OK", "OK", False),
])
def test_assist_explains_manual_text_change(monkeypatch, tmp_path, first_status, second_status, specific):
    from dispread.setup_checks import CheckResult

    cam = SequenceSetupCamera([10, 20])
    fit = SimpleNamespace(quad=[[0, 0], [3, 0], [3, 2], [0, 2]])
    monkeypatch.setattr(live_setup, "fit_lattice", lambda *a, **kw: fit)
    monkeypatch.setattr(live_setup, "check_setup", lambda *a, **kw: SimpleNamespace(
        overall="OK", checks={}, to_dict=lambda: {}))
    # Keine Nachfuehrung: die drei Aufrufe pruefen nur das endgueltige Quad.
    monkeypatch.setattr(live_setup, "refine_quad", lambda *a: (_ for _ in ()).throw(ValueError("kein Fit")))
    observed = []

    def offset(frames, quad):
        observed.append((len(frames), int(frames[0][0][0, 0, 0])))
        if len(frames) == 2:
            return CheckResult("FEHLER", {})
        return CheckResult(first_status if frames[0][0][0, 0, 0] == 10 else second_status, {})

    monkeypatch.setattr(live_setup, "raster_offset_check", offset)
    with pytest.raises(live_setup.SetupError) as exc:
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("+0.60972 "), expected_size=(3, 2),
            out_dir=tmp_path, hint_box=(0, 0, 1, 1), sleep=lambda _: None,
        )
    if specific:
        assert str(exc.value) == (
            "Anzeige hat sich zwischen den Standbildern geaendert (2j: erstes Standbild passt zum Zellentext, "
            "zweites nicht). Zellentext-Feld leer lassen - der Wert wird dann vom GSV-2AS gelesen - "
            "oder schwankende Ziffern mit ? markieren, z. B. +0.4678?")
    else:
        assert str(exc.value) == "Rasterversatz 2j meldet FEHLER; kein Vorschlag"
    assert observed == [(2, 10), (1, 10), (1, 20)]
