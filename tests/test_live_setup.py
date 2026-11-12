from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from devdata_helpers import local_recording
from frame_tracking_helpers import reference_scene

from dispread.camera_settings import CameraSettings
from dispread.live import setup as live_setup
from dispread.setup_checks import CheckResult, SetupChecks


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


class ExposureCamera:
    """StreamCam-Ersatz: Neustart setzt feste Regler, Helligkeit folgt exp/gain."""

    device = '/dev/fake'

    def __init__(self, base=65, slope=1, exposure=200, gain=10, hint=True):
        self.base, self.slope, self.hint = base, slope, hint
        self.settings = CameraSettings('logitech_streamcam', '046d:0893', (600, 240), 'YUYV', 30,
                                       {'focus_absolute': 48, 'exposure_time_absolute': exposure,
                                        'gain': gain, 'white_balance_temperature': 4600})
        self.applied = []
        self.discards = []

    def apply(self, settings):
        self.settings = settings
        controls = dict(settings.ordered_controls())
        assert controls['auto_exposure'] == 1
        assert controls['focus_absolute'] == 48
        assert controls['exposure_time_absolute'] in (100, 200, 300)
        assert 0 <= controls['gain'] <= 128
        self.applied.append(settings)

    def fresh_still(self, discard=10):
        self.discards.append(discard)
        controls = self.settings.controls
        level = np.clip(self.base * controls['exposure_time_absolute'] / 200
                        + self.slope * controls['gain'], 0, 205)
        image = np.full((240, 600, 3), 245, np.uint8)  # helle Umgebung darf nicht eingehen
        if self.hint:
            green = tuple(min(255, round(level * c)) for c in (.45, 1.35, .8))
            image[60:180, 50:550] = green
            for y in range(85, 161, 15):
                for x in range(80, 521, 20):
                    cv2.circle(image, (x, y), 3, tuple(round(c * .3) for c in green), -1)
        return image


def test_adjust_exposure_reports_each_round(monkeypatch):
    cam = ExposureCamera(exposure=300, gain=0)
    levels = iter([100.0, 124.0])
    monkeypatch.setattr(live_setup, "hint_glass_level", lambda *args: next(levels))
    rounds = []
    initial_controls = dict(cam.settings.controls)
    settings, audit = live_setup.adjust_exposure(
        cam, cam.settings, apply=cam.apply, sleep=lambda s: None, on_round=rounds.append,
    )
    assert rounds == [
        {"level": 100.0, "controls": initial_controls},
        {"level": 124.0, "controls": {**initial_controls, "gain": 30}},
    ]
    assert settings.controls == rounds[-1]["controls"]
    # Das bestehende Audit zaehlt weiterhin nur die Nachregelungen.
    assert len(audit["rounds"]) == 1
    rounds[-1]["controls"]["gain"] = 999
    assert settings.controls["gain"] == audit["rounds"][0]["controls"]["gain"] == 30


def test_adjust_exposure_rounds_omit_unmeasurable_levels(monkeypatch):
    cam = ExposureCamera(exposure=300, gain=0)
    levels = iter([100.0, None])
    monkeypatch.setattr(live_setup, "hint_glass_level", lambda *args: next(levels))
    rounds = []
    _, audit = live_setup.adjust_exposure(
        cam, cam.settings, apply=cam.apply, sleep=lambda s: None, on_round=rounds.append,
    )
    assert [entry["level"] for entry in rounds] == [100.0]
    assert audit["reason"] == "gruene_hinweisbox_verloren"


@pytest.mark.parametrize('base,slope,exposure,gain', [
    (65, 1, 200, 10), (25, 1, 300, 0), (65, 1, 300, 90),
    (170, 1, 300, 0), (65, .25, 200, 0), (65, 2, 200, 0), (70, 2, 300, 0), (104, 1, 200, 0),
])
def test_display_exposure_converges_with_fixed_flicker_free_controls(base, slope, exposure, gain):
    cam = ExposureCamera(base, slope, exposure, gain)
    initial = cam.settings
    settings, audit = live_setup.adjust_exposure(cam, initial, apply=cam.apply, sleep=lambda s: None)
    assert audit['achieved'] is True
    assert 115 <= audit['final_level'] <= 150
    assert 1 <= len(audit['rounds']) <= 4
    assert audit['initial_level'] < 115 or audit['initial_level'] > 150
    assert settings == cam.settings
    assert audit['selected_controls'] == settings.controls
    assert initial.controls['gain'] == gain  # bestehendes Fokusresultat bleibt unveraendert
    assert len(cam.discards) == 8 * (1 + len(audit['rounds']))
    assert cam.discards[:8] == [10, 0, 0, 0, 0, 0, 0, 0]


def test_display_exposure_too_bright_never_lengthens_exposure_first():
    # Review R13-20: zu hell bei 20 ms darf die erste Runde nicht auf 30 ms gehen.
    cam = ExposureCamera(base=120, slope=1, exposure=200, gain=60)
    settings, audit = live_setup.adjust_exposure(cam, cam.settings, apply=cam.apply, sleep=lambda s: None)
    assert audit['initial_level'] > 150
    assert audit['rounds'][0]['controls']['exposure_time_absolute'] <= 200
    assert audit['rounds'][0]['level'] < audit['initial_level']
    assert audit['achieved'] is True and settings == cam.settings


def test_display_exposure_keeps_already_suitable_settings():
    cam = ExposureCamera(base=80, exposure=300, gain=10)
    settings, audit = live_setup.adjust_exposure(cam, cam.settings, apply=cam.apply, sleep=lambda s: None)
    assert audit['achieved'] is True
    assert audit['rounds'] == []
    assert settings == cam.settings
    assert cam.applied == []


def test_display_exposure_skips_missing_hint_without_guessing():
    cam = ExposureCamera(hint=False)
    settings, audit = live_setup.adjust_exposure(cam, cam.settings, apply=cam.apply, sleep=lambda s: None)
    assert settings == cam.settings
    assert not audit['achieved']
    assert audit['initial_level'] is audit['final_level'] is None
    assert audit['reason'] == 'keine_gruene_hinweisbox'
    assert cam.applied == []


def test_display_exposure_restores_best_if_hint_disappears():
    cam = ExposureCamera()
    initial = cam.settings

    def apply(settings):
        cam.apply(settings)
        cam.hint = False

    settings, audit = live_setup.adjust_exposure(cam, initial, apply=apply, sleep=lambda s: None)
    assert settings == initial == cam.settings
    assert not audit['achieved']
    assert audit['reason'] == 'gruene_hinweisbox_verloren'
    assert audit['final_level'] == audit['initial_level']
    assert len(audit['rounds']) == 1
    assert audit['rounds'][0]['level'] is None


def test_display_exposure_stops_after_four_rounds_if_gain_has_no_effect():
    cam = ExposureCamera(base=65, slope=0, exposure=200, gain=0)
    settings, audit = live_setup.adjust_exposure(cam, cam.settings, apply=cam.apply, sleep=lambda s: None)
    assert not audit['achieved']
    assert len(audit['rounds']) == 4
    assert audit['reason'] == 'zielband_nach_vier_runden_nicht_erreicht'
    assert settings == cam.settings
    assert settings.controls['exposure_time_absolute'] == 300
    assert settings.controls['gain'] == 0
    assert len(cam.applied) == 5  # vier Messrunden plus Rueckstellung ohne weitere Messung


@pytest.mark.parametrize('exposure', [156, 400])
def test_display_exposure_never_restores_non_flicker_free_initial_controls_on_box_loss(exposure):
    cam = ExposureCamera(exposure=exposure)

    def apply(settings):
        cam.apply(settings)
        cam.hint = False

    settings, audit = live_setup.adjust_exposure(cam, cam.settings, apply=apply, sleep=lambda s: None)
    assert not audit['achieved']
    assert audit['reason'] == 'gruene_hinweisbox_verloren'
    assert settings.controls['exposure_time_absolute'] in (100, 200, 300)
    assert audit['final_level'] is None  # fuer das gueltige Reglerpaar fehlt eine Messung
    assert settings == cam.settings


@pytest.mark.parametrize('base,slope,exposure,gain', [(35, .1, 200, 0), (350, 0, 100, 0)])
def test_display_exposure_keeps_best_measured_controls_when_unreachable(base, slope, exposure, gain):
    cam = ExposureCamera(base, slope, exposure, gain)
    settings, audit = live_setup.adjust_exposure(cam, cam.settings, apply=cam.apply, sleep=lambda s: None)
    assert not audit['achieved']
    assert audit['reason']
    assert len(audit['rounds']) <= 4
    levels = [audit['initial_level']] + [r['level'] for r in audit['rounds']]
    assert abs(audit['final_level'] - 130) == min(abs(level - 130) for level in levels)
    assert settings == cam.settings
    assert audit['selected_controls'] == settings.controls


@pytest.mark.parametrize('stamp,expected', [
    ('20261023T075343Z', 112), ('20261023T084344Z', 114), ('20261023T100613Z', 116),
    ('20261023T121436Z', 113), ('20261023T131121Z', 118), ('20261023T124226Z', 148),
    ('20261028T110248Z', 142), ('20261028T121101Z', 137), ('20261028T123044Z', 128),
    ('20261028T133959Z', 144), ('20261028T134306Z', 97), ('20261026T082712Z', 77),
])
def test_hint_exposure_calibration_on_saved_stills(stamp, expected):
    image = cv2.imread(str(local_recording(f'live/live-{stamp}/setup/still.png')))
    hint = live_setup.find_green_hint_box(image)
    assert hint is not None
    assert live_setup.hint_glass_level(image, hint) == pytest.approx(expected, abs=1)


def test_hint_glass_ignores_bright_surroundings_in_box_margin():
    cam = ExposureCamera()
    image = cam.fresh_still()
    hint = live_setup.find_green_hint_box(image)
    assert hint is not None
    # Handrechnung BGR(34,101,60): Grauwert 81, Umgebung 245.
    assert live_setup.hint_glass_level(image, hint) == 81


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


def test_mean_still_optionally_keeps_unaveraged_copies_when_camera_reuses_memory():
    class ReusedBufferCamera:
        def __init__(self):
            self.image = np.zeros((2, 3, 3), np.uint8)
            self.values = iter((10, 20, 60))

        def fresh_still(self, discard=10):
            self.image[:] = next(self.values)
            return self.image

    cam = ReusedBufferCamera()
    frames = []
    averaged = live_setup.mean_still(cam, frames=3, captured_frames=frames)
    np.testing.assert_array_equal(averaged, np.full((2, 3, 3), 30, np.uint8))
    assert [int(frame[0, 0, 0]) for frame in frames] == [10, 20, 60]
    cam.image[:] = 99
    assert [int(frame[0, 0, 0]) for frame in frames] == [10, 20, 60]


@pytest.mark.parametrize("stability_s", [30.0, 15.0])
@pytest.mark.parametrize("explicit_hint", [None, (0.1, 0.2, 0.3, 0.4)])
def test_assist_retry_uses_successful_mean_text_hint_and_timestamp(monkeypatch, tmp_path, explicit_hint, stability_s):
    cam = SequenceSetupCamera([10, 12, 30, 34, 28, 36])
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
    assert isinstance(result.stability_frames, tuple)
    assert [int(frame[0, 0, 0]) for frame in result.stability_frames] == [28, 36]
    # OQ-74: Das Mittelbild des abgelehnten ersten Versuchs bleibt erhalten.
    assert {path.name for path in tmp_path.glob('*.png')} == {'still.png', 'stability.png', 'still-versuch-1.png'}
    assert int(cv2.imread(str(tmp_path / 'still-versuch-1.png'))[0, 0, 0]) == 11
    assert result.first_text == result.second_text == "new"
    assert result.setup_attempt == 2
    assert checked[0][0] is result.first and checked[0][1] is fit
    assert checked[-1][2]["stability_image_bgr"] is result.second
    assert checked[-1][2]["stability_elapsed_s"] == result.stability_elapsed_s == stability_s
    assert refinement[0][0] is result.first and refinement[0][1] == "new"
    assert offsets[-1][0][0] is result.first and offsets[-1][0][1] == "new"
    assert offsets[-1][1][0] is result.second and offsets[-1][1][1] == "new"
    assert sum(sleeps) == pytest.approx(stability_s)
    assert all(0 < seconds <= 0.5 for seconds in sleeps)
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


@pytest.fixture
def assist_progress_camera(monkeypatch):
    fit = SimpleNamespace(quad=[[0, 0], [3, 0], [3, 2], [0, 2]])
    monkeypatch.setattr(live_setup, "fit_lattice", lambda *a, **kw: fit)
    monkeypatch.setattr(live_setup, "check_setup", lambda *a, **kw: SetupChecks("OK", {}))
    monkeypatch.setattr(live_setup, "refine_quad", lambda *a: (fit.quad, []))
    monkeypatch.setattr(live_setup, "raster_offset_check", lambda *a: CheckResult("OK", {}))
    return SequenceSetupCamera([10, 10, 20])


@pytest.mark.parametrize("total", [15.0, 15.25])
def test_assist_measure_waits_in_slices_and_reports_wait(tmp_path, assist_progress_camera, total):
    sleeps, waits = [], []
    now = [100.0]

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    result = live_setup.assist_measure(
        assist_progress_camera, cell_text=live_setup.offline_text_source("text"),
        expected_size=(3, 2), out_dir=tmp_path, hint_box=(0, 0, 1, 1),
        sleep=sleep, monotonic=lambda: now[0], stability_s=total, min_stability_s=15.0,
        on_wait=lambda elapsed, duration: waits.append((elapsed, duration)),
    )
    assert sum(sleeps) == total
    assert all(0 < seconds <= 0.5 for seconds in sleeps)
    assert waits[0] == (0.5, total)
    assert waits[-1] == (total, total)
    assert len(waits) == len(sleeps)
    assert result.stability_elapsed_s == total


@pytest.mark.parametrize("attempt", [1, 2])
def test_assist_measure_reports_phases_in_order(tmp_path, monkeypatch, assist_progress_camera, attempt):
    if attempt == 2:
        fit = SimpleNamespace(quad=[[0, 0], [3, 0], [3, 2], [0, 2]])
        fits = iter(["keine_startlage", fit])
        monkeypatch.setattr(live_setup, "fit_lattice", lambda *a, **kw: next(fits))
    phases = []
    live_setup.assist_measure(
        assist_progress_camera, cell_text=live_setup.offline_text_source("text"),
        expected_size=(3, 2), out_dir=tmp_path, hint_box=(0, 0, 1, 1),
        sleep=lambda _: None, fit_attempts=3,
        on_phase=lambda phase, number: phases.append((phase, number)),
    )
    expected = [("mitteln", 1), ("zelltext", 1), ("raster", 1)]
    if attempt == 2:
        expected += [("mitteln", 2), ("zelltext", 2), ("raster", 2)]
    expected += [("stabilitaet", attempt), ("zweites_standbild", attempt), ("gegenlesen", attempt)]
    assert phases == expected


@pytest.mark.parametrize('failures,details', [
    ({'kanten': CheckResult('FEHLER', {}, (8,))}, 'kanten (Zelle 8)'),
    ({'kanten': CheckResult('FEHLER', {}, (8,)), 'kontrast': CheckResult('FEHLER', {})},
     'kanten (Zelle 8), kontrast'),
    ({'kanten': CheckResult('FEHLER', {}, (8, 13))}, 'kanten (Zellen 8, 13)'),
    # OQ-72: Bedienertext der Pruefung steht mit in der Abbruchmeldung.
    ({'kanten': CheckResult('FEHLER', {}, (7,), 'Reflex über Zelle 7, Licht abschatten')},
     'kanten (Zelle 7) - Reflex über Zelle 7, Licht abschatten'),
])
def test_assist_precheck_error_names_checks_and_cells(monkeypatch, tmp_path, failures, details):
    cam = SequenceSetupCamera([10])
    lattice = SimpleNamespace(quad=[[0, 0], [3, 0], [3, 2], [0, 2]])
    checks = SetupChecks('FEHLER', {
        'raster': CheckResult('FEHLER', {}, (4,)),
        'glanz': CheckResult('WARNUNG', {}),
        'stabilitaet': CheckResult(None, {}),
        **failures,
    })
    monkeypatch.setattr(live_setup, 'fit_lattice', lambda *_a, **_kw: lattice)
    monkeypatch.setattr(live_setup, 'check_setup', lambda *_a, **_kw: checks)
    reports, sleeps = [], []

    with pytest.raises(live_setup.SetupError) as exc:
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source('text'), expected_size=(3, 2),
            out_dir=tmp_path, hint_box=(0.0, 0.0, 1.0, 1.0),
            report=reports.append, sleep=sleeps.append,
        )
    assert str(exc.value) == f'Vorpruefung meldet FEHLER: {details}; Stabilitaetsmessung nicht gestartet'
    assert reports == [checks.to_dict()]
    assert sleeps == []
    assert cam.discards == [10]
    assert not (tmp_path / 'stability.png').exists()


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
    assert cam.controls[1:3] == [[("focus_absolute", 36)], [("focus_absolute", 48)]]
    assert cam.controls[-1] == [("auto_exposure", 3), ("white_balance_automatic", 1)]
    assert settings.controls == {
        "focus_absolute": 48, "exposure_time_absolute": 156, "white_balance_temperature": 4600, "gain": 10,
    }
    assert settings.device == "/dev/fake" and sweep[0][0] == 48


class FocusMotorCamera(FakeSetupCamera):
    def __init__(self, readings):
        super().__init__(None)
        self.readings = iter(readings)
        self.captured_at = []
        self.now = 0.0

    def sleep(self, seconds):
        self.now += seconds

    def fresh_still(self, discard=10):
        self.captured_at.append(self.now)
        return np.full((12, 12), next(self.readings), dtype=float)


class HysteresisCamera(FakeSetupCamera):
    """Abwaerts liegt die effektive Endlage drei Schritte ueber dem Sollwert."""

    def __init__(self, peak):
        super().__init__(None)
        self.peak = peak
        self.focus = 120
        self.effective = 123
        self.samples = []

    def set_controls(self, controls):
        super().set_controls(controls)
        for name, value in controls:
            if name == "focus_absolute":
                assert 0 <= value <= 255
                if value != self.focus:
                    self.effective = value + (3 if value < self.focus else 0)
                self.focus = value

    def fresh_still(self, discard=10):
        self.samples.append((self.focus, self.effective))
        # Drei Schritte vom Gipfel kosten rund 40 % Schaerfe.
        score = 1 + 614 * np.exp(-((self.effective - self.peak) ** 2) / 18)
        return np.full((12, 12), score, dtype=float)


@pytest.mark.parametrize("start,peak", [(42, 52), (100, 63), (200, 52), (48, 1), (48, 255)])
def test_focus_hysteresis_reproduces_peak_on_first_verification(monkeypatch, start, peak):
    cam = HysteresisCamera(peak)
    monkeypatch.setattr(live_setup, "sharpness", lambda roi: float(roi[0, 0]))
    settings, measured = live_setup.focus_camera(
        cam, None, start_focus=start, settle_s=0, sleep=lambda _s: None,
    )
    assert abs(settings.controls["focus_absolute"] - peak) <= 1
    assert measured.focus_verify["attempts"] == 1
    assert measured.focus_verify["verified"] == pytest.approx(max(score for _, score in measured))
    assert all(focus == effective for focus, effective in cam.samples)
    assert measured.focus_verify["approach"] == "from_below"
    assert measured.focus_verify["backlash_margin"] == 12


def _focus_motor(monkeypatch, readings, *, target=48, best=100.0, sample=False):
    from dispread.focus_sweep import FocusMeasurements

    cam = FocusMotorCamera(readings)
    monkeypatch.setattr(live_setup.time, "monotonic", lambda: cam.now)
    monkeypatch.setattr(live_setup, "sharpness", lambda roi: float(roi[0, 0]))

    def climb(measure, **kwargs):
        measured = FocusMeasurements()
        measured.append((target, measure(target) if sample else best))
        return target, measured

    monkeypatch.setattr(live_setup, "climb_focus", climb)
    return cam


def test_focus_motor_waits_for_stable_sharpness_and_verifies(monkeypatch):
    cam = _focus_motor(monkeypatch, [10, 30, 60, 100, 105, 90, 94], sample=True)
    messages = []
    settings, measured = live_setup.focus_camera(cam, None, sleep=cam.sleep, info=messages.append)
    # Je eine Sekunde am Anfahrpunkt vor Suchmessung und Endpruefung.
    assert cam.captured_at == pytest.approx([2, 2.3, 2.6, 2.9, 3.2, 5.2, 5.5])
    assert measured == [(48, 105)]
    assert settings.controls["focus_absolute"] == 48
    assert measured.focus_verify == {
        "target": 48, "best_measured": 105, "verified": 94, "attempts": 1,
        "approach": "from_below", "backlash_margin": 12,
    }
    assert "Fokus geprueft: Schaerfe 94.0 von 105.0" in messages


def test_focus_motor_stops_waiting_after_five_seconds(monkeypatch):
    cam = _focus_motor(monkeypatch, [10, 100] * 8 + [100], sample=True)
    _, measured = live_setup.focus_camera(cam, None, sleep=cam.sleep)
    # Fuenf Sekunden ab Setzen des Ziels, nach einer Sekunde am Anfahrpunkt.
    assert cam.captured_at[14] == pytest.approx(6.0)
    assert measured == [(48, 10)]
    assert measured.focus_verify["attempts"] == 1


@pytest.mark.parametrize("target,below", [(1, 0), (48, 36), (255, 243)])
def test_focus_verification_retries_once_and_records_result(monkeypatch, target, below):
    cam = _focus_motor(monkeypatch, [80, 80, 85, 85], target=target)
    _, measured = live_setup.focus_camera(cam, None, sleep=cam.sleep)
    moves = [value for controls in cam.controls for name, value in controls if name == "focus_absolute"]
    assert moves == [below, target, below, target]
    assert measured.focus_verify == {
        "target": target, "best_measured": 100, "verified": 85, "attempts": 2,
        "approach": "from_below", "backlash_margin": 12,
    }


def test_focus_zero_is_rejected_without_a_below_approach(monkeypatch):
    cam = _focus_motor(monkeypatch, [], target=0)
    with pytest.raises(live_setup.SetupError, match="nicht von unten erreichbar"):
        live_setup.focus_camera(cam, None, sleep=cam.sleep)
    assert cam.controls == [[("focus_automatic_continuous", 0)]]


def test_focus_verification_fails_twice_with_restart_message(monkeypatch):
    cam = _focus_motor(monkeypatch, [80, 80, 84, 84])
    messages = []
    with pytest.raises(live_setup.SetupError, match=(
        "Fokus nicht stabil: Schaerfe 84.0 von 100.0 erreicht - Einrichtung neu starten"
    )):
        live_setup.focus_camera(cam, None, sleep=cam.sleep, info=messages.append)
    assert cam.controls[-4:] == [
        [("focus_absolute", 36)], [("focus_absolute", 48)],
        [("focus_absolute", 36)], [("focus_absolute", 48)],
    ]
    assert not any(message.startswith("Fokus geprueft:") for message in messages)


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


@pytest.mark.parametrize('achieved,status', [(True, 'OK'), (False, 'WARNUNG')])
def test_proposal_warns_about_unfinished_exposure_adjustment_without_blocking_run(tmp_path, monkeypatch,
                                                                             achieved, status):
    from dispread.live.service import run_block_reason

    checks = SetupChecks('OK', {'belichtung': CheckResult('OK', {'glaspegel': 110}),
                               'kanten': CheckResult('OK', {}),
                               'rasterversatz': CheckResult('OK', {})})
    image, quad = reference_scene()
    cv2.imwrite(str(tmp_path / 'still.png'), image)
    monkeypatch.setattr(live_setup, 'write_overlays', lambda *a, **kw: [])
    proposal = live_setup.propose_with_fit(
        image, fit=SimpleNamespace(quad=quad), frame_path=tmp_path / 'still.png',
        camera_settings=replace(_CAMERA, size=image.shape[1::-1]), device_id='test', session_id='test',
        out_dir=tmp_path, final_checks=checks, offset_check=CheckResult('OK', {}),
        reader_check=CheckResult('OK', {}),
        exposure_adjust={'achieved': achieved, 'reason': None if achieved else 'reglergrenze_oder_wiederholung'},
    )
    result = proposal['setup_checks']['checks']['belichtung']
    assert result['status'] == proposal['setup_checks']['overall'] == status
    assert result['metrics']['glaspegel'] == 110
    if not achieved:
        assert 'neu einrichten' in result['reason']
    assert run_block_reason(proposal) is None


@pytest.mark.parametrize('final_level,expected', [(170.0, 'zu hell'), (95.0, 'näher stellen'), (None, 'näher stellen')])
def test_unfinished_exposure_reason_matches_direction(tmp_path, monkeypatch, final_level, expected):
    checks = SetupChecks('OK', {'kanten': CheckResult('OK', {}), 'rasterversatz': CheckResult('OK', {})})
    image, quad = reference_scene()
    cv2.imwrite(str(tmp_path / 'still.png'), image)
    monkeypatch.setattr(live_setup, 'write_overlays', lambda *a, **kw: [])
    proposal = live_setup.propose_with_fit(
        image, fit=SimpleNamespace(quad=quad), frame_path=tmp_path / 'still.png',
        camera_settings=replace(_CAMERA, size=image.shape[1::-1]), device_id='test', session_id='test',
        out_dir=tmp_path, final_checks=checks, offset_check=CheckResult('OK', {}),
        reader_check=CheckResult('OK', {}),
        exposure_adjust={'achieved': False, 'reason': 'zielband_nach_vier_runden_nicht_erreicht',
                         'final_level': final_level},
    )
    assert expected in proposal['setup_checks']['checks']['belichtung']['reason']


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
    assert messages[:-1] == ["Fokus: Bergsteigen"] + (["Fokus: Vollsweep (Rueckfall)"] if flat else [])
    assert messages[-1].startswith("Fokus geprueft: Schaerfe ")
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


@pytest.mark.parametrize('fallback', [False, True])
def test_focus_cancel_between_samples_keeps_applied_controls(monkeypatch, fallback):
    cam = FakeSetupCamera(np.full((12, 12), 100, np.uint8))
    stopped = [False]
    samples = []
    monkeypatch.setattr(live_setup, 'sharpness', lambda roi: float(roi.mean()))

    def sample(focus, score):
        samples.append([focus, score])
        if not fallback or len(samples) == 4:
            stopped[0] = True

    with pytest.raises(live_setup.SetupCancelled, match='^Einrichtung abgebrochen$'):
        live_setup.focus_camera(cam, None, settle_s=0, sleep=lambda _: None,
                                on_sample=sample, should_stop=lambda: stopped[0])
    assert len(samples) == (4 if fallback else 1)
    assert cam.controls[-1] == [('focus_absolute', samples[-1][0])]


def test_focus_cancel_during_settle_stops_within_one_slice():
    cam = FakeSetupCamera(np.full((12, 12), 100, np.uint8))
    sleeps = []
    with pytest.raises(live_setup.SetupCancelled, match='^Einrichtung abgebrochen$'):
        live_setup.focus_camera(cam, None, sleep=sleeps.append, should_stop=lambda: bool(sleeps))
    assert sleeps == [0.5]


@pytest.mark.parametrize('cancel_phase', ['mitteln', 'zelltext', 'raster', 'stabilitaet',
                                         'zweites_standbild', 'gegenlesen', 'wait'])
def test_assist_cancel_between_phases_and_wait_slices(tmp_path, assist_progress_camera, cancel_phase):
    stopped = [False]
    sleeps, phases = [], []

    def phase(name, attempt):
        phases.append(name)
        if name == cancel_phase:
            stopped[0] = True

    def sleep(seconds):
        sleeps.append(seconds)
        if cancel_phase == 'wait':
            stopped[0] = True

    with pytest.raises(live_setup.SetupCancelled, match='^Einrichtung abgebrochen$'):
        live_setup.assist_measure(
            assist_progress_camera, cell_text=live_setup.offline_text_source('text'),
            expected_size=(3, 2), out_dir=tmp_path, hint_box=(0, 0, 1, 1),
            sleep=sleep, on_phase=phase, should_stop=lambda: stopped[0],
        )
    if cancel_phase == 'wait':
        assert sleeps == [0.5]
        assert phases[-1] == 'stabilitaet'
    else:
        assert phases[-1] == cancel_phase
    assert not (tmp_path / 'proposal.json').exists()


@pytest.mark.parametrize('size,hint,expected', [
    ((1920, 1080), None, [640, 360, 640, 360]),
    ((1920, 1080), (.421, .471, .296, .077), [808, 509, 569, 83]),
    ((11, 8), None, [3, 2, 4, 3]),
])
def test_focus_roi_pixels_equal_actual_measurement_crop(size, hint, expected):
    width, height = size
    # Jedes Pixel traegt seine Position, sodass auch der Ursprung geprueft wird.
    gray = np.arange(width * height).reshape(height, width)
    roi = live_setup.measurement_roi_pixels(size, hint)
    assert roi == expected
    x, y, w, h = roi
    np.testing.assert_array_equal(live_setup.measurement_roi(gray, hint), gray[y:y + h, x:x + w])


# --- OQ-74: Fokus-ROI aus der LCD-Hinweisbox, Endpruefung nach Kameraneustart ---

def _green_hint_frame(size=(600, 240), box=(50, 60, 500, 120)):
    """Gruen leuchtende Punktmatrix wie bei ExposureCamera, Lage frei waehlbar."""
    width, height = size
    x, y, w, h = box
    image = np.full((height, width, 3), 90, np.uint8)
    green = (58, 175, 104)
    image[y:y + h, x:x + w] = green
    for cy in range(y + 25, y + h - 15, 15):
        for cx in range(x + 30, x + w - 25, 20):
            cv2.circle(image, (cx, cy), 3, tuple(round(c * .3) for c in green), -1)
    return image


def _covered(outer, inner):
    """Anteil der Flaeche von `inner`, der in `outer` liegt (beide x,y,w,h)."""
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    dx = max(0.0, min(ox + ow, ix + iw) - max(ox, ix))
    dy = max(0.0, min(oy + oh, iy + ih) - max(oy, iy))
    return dx * dy / (iw * ih)


def test_focus_hint_box_is_lcd_hint_with_small_margin_clipped_to_image():
    image = _green_hint_frame()
    hint = live_setup.find_green_hint_box(image)
    box = live_setup.focus_hint_box(image)
    assert hint is not None and box is not None
    assert _covered(box, hint) == pytest.approx(1.0)
    # Kleiner Rand: je Seite hoechstens FOCUS_ROI_MARGIN_FRACTION der Boxgroesse.
    margin = live_setup.FOCUS_ROI_MARGIN_FRACTION
    assert box[2] <= hint[2] * (1 + 2 * margin) + 1e-9
    assert box[3] <= hint[3] * (1 + 2 * margin) + 1e-9
    # Randnahe Box: der Rand wird auf das Bild begrenzt.
    edge = live_setup.focus_hint_box(_green_hint_frame(box=(0, 0, 500, 120)))
    assert edge is not None
    assert edge[0] >= 0 and edge[1] >= 0
    assert edge[0] + edge[2] <= 1 + 1e-9 and edge[1] + edge[3] <= 1 + 1e-9


@pytest.mark.parametrize('image', [
    np.full((240, 600, 3), 90, np.uint8),          # keine Gruenflaeche
    np.full((12, 12), 128.0),                     # Graubild ohne Farbe (Fokus-Fakes)
    None,                                         # noch kein Vorschaubild
])
def test_focus_hint_box_none_without_green_lcd(image):
    assert live_setup.focus_hint_box(image) is None


def test_focus_camera_records_roi_means_and_verify_frame(monkeypatch):
    cam = HysteresisCamera(52)
    monkeypatch.setattr(live_setup, "sharpness", lambda roi: float(roi[0, 0]))
    _, measured = live_setup.focus_camera(cam, None, start_focus=42, settle_s=0, sleep=lambda _s: None)
    assert set(measured.roi_means) == {focus for focus, _ in measured}
    assert all(mean > 0 for mean in measured.roi_means.values())
    assert measured.verify_frame is not None and measured.verify_frame.shape == (12, 12)
    assert measured.verify_roi_mean == pytest.approx(float(measured.verify_frame.mean()))


class RestartFocusCamera(FakeSetupCamera):
    """Schaerfe haengt an der Lage; ein Neustart kann die Linse verlieren.

    `lost` steht fuer eine Linse, die nach dem Kameraneustart nicht am Sollwert
    steht, obwohl der Reglerwert stimmt. Erst ein echtes Anfahren von unten
    stellt sie wieder her (`recover`), sonst bleibt sie verloren.
    """

    def __init__(self, *, best=600.0, mean=100.0, lost=False, recover=True, brightness=1.0):
        super().__init__(None)
        self.best, self.mean, self.lost, self.recover = best, mean, lost, recover
        self.brightness = brightness
        self.focus = 48
        self.frames = 0

    def set_controls(self, controls):
        super().set_controls(controls)
        for name, value in controls:
            if name == "focus_absolute":
                if value < self.focus and self.recover:
                    self.lost = False
                self.focus = value

    def fresh_still(self, discard=10):
        self.frames += 1
        score = self.best * (0.05 if self.lost else 1.0) * self.brightness ** 2
        image = np.full((90, 160), self.mean * self.brightness, dtype=float)
        image[0, 0] = score  # Messwert fuer die gepatchte Schaerfe
        return image


def _end_check_sweep(best=600.0, mean=100.0, target=48):
    from dispread.focus_sweep import FocusMeasurements

    sweep = FocusMeasurements()
    sweep.extend([(40, best * 0.4), (target, best), (56, best * 0.6)])
    sweep.roi_means = {40: mean, target: mean, 56: mean}
    sweep.focus_verify = {"target": target, "best_measured": best, "verified": best * 0.97, "attempts": 1,
                          "approach": "from_below", "backlash_margin": 12}
    return sweep


@pytest.fixture
def end_check_sharpness(monkeypatch):
    monkeypatch.setattr(live_setup, "sharpness", lambda roi: float(roi[0, 0]))
    monkeypatch.setattr(live_setup, "measurement_roi", lambda gray, hint: gray)


def test_focus_end_check_ok_without_moving_lens(end_check_sharpness):
    cam = RestartFocusCamera()
    result, frames = live_setup.check_focus_after_restart(cam, None, _end_check_sweep(), settle_s=0,
                                                          sleep=lambda _s: None)
    assert result["status"] == "OK" and result["reapproach"] is None
    assert result["after_restart"]["ratio"] == pytest.approx(1.0, rel=0.01)
    assert result["threshold_ratio"] == live_setup.FOCUS_END_RATIO
    assert cam.controls == []  # Linse nicht angefasst
    assert set(frames) == {"nach_neustart"}


def test_focus_end_check_resets_lens_from_below_after_restart_loss(end_check_sharpness):
    cam = RestartFocusCamera(lost=True)
    messages = []
    result, frames = live_setup.check_focus_after_restart(cam, None, _end_check_sweep(), settle_s=0,
                                                          sleep=lambda _s: None, info=messages.append)
    # CLAUDE.md StreamCam: erst Automatik aus, dann Absolutwert (von unten).
    assert cam.controls == [[("focus_automatic_continuous", 0)], [("focus_absolute", 36)],
                            [("focus_absolute", 48)]]
    assert result["status"] == "OK"
    assert result["after_restart"]["ratio"] < live_setup.FOCUS_END_RATIO
    assert result["reapproach"]["ratio"] == pytest.approx(1.0, rel=0.01)
    # Gleiche Belichtung vor und nach dem Neusetzen: der Neustarteffekt ist direkt vergleichbar.
    assert result["reapproach"]["restart_effect"] == pytest.approx(0.05, rel=0.01)
    assert "neu gesetzt" in result["reason"]
    assert set(frames) == {"nach_neustart", "nach_neusetzen"}
    assert any("neu setzen" in message for message in messages)


def test_focus_end_check_warns_when_reset_does_not_restore_sharpness(end_check_sharpness):
    cam = RestartFocusCamera(lost=True, recover=False)
    result, _ = live_setup.check_focus_after_restart(cam, None, _end_check_sweep(), settle_s=0,
                                                     sleep=lambda _s: None)
    assert result["status"] == "WARNUNG"
    assert "Fokus nach Kameraneustart unscharf" in result["reason"]
    assert "5 %" in result["reason"]
    # Genau einmal neu gesetzt, kein stilles Weiter und keine Endlosschleife.
    assert sum(1 for controls in cam.controls for name, _ in controls if name == "focus_absolute") == 2


@pytest.mark.parametrize("brightness", [0.8, 1.25])
def test_focus_end_check_normalizes_display_brightness(end_check_sharpness, brightness):
    # Belichtung nach der Suche geaendert: Laplace-Varianz skaliert mit dem
    # Quadrat der Helligkeit, die normierte Schaerfe bleibt gleich.
    cam = RestartFocusCamera(brightness=brightness)
    result, _ = live_setup.check_focus_after_restart(cam, None, _end_check_sweep(), settle_s=0,
                                                     sleep=lambda _s: None)
    assert result["status"] == "OK" and result["reapproach"] is None
    assert result["after_restart"]["ratio"] == pytest.approx(1.0, rel=0.01)
    assert result["after_restart"]["raw_ratio"] == pytest.approx(brightness ** 2, rel=0.01)


def test_focus_end_check_skipped_without_search_verification():
    from dispread.focus_sweep import FocusMeasurements

    assert live_setup.check_focus_after_restart(FakeSetupCamera(None), None, FocusMeasurements()) is None


@pytest.mark.parametrize("roi_source,end_status,status,needle", [
    ("lcd_hinweis", "OK", "OK", None),
    ("mittleres_drittel", "OK", "WARNUNG", "Fokus ohne LCD-Hinweis gemessen"),
    ("lcd_hinweis", "WARNUNG", "WARNUNG", "Fokus nach Kameraneustart unscharf"),
    ("lcd_hinweis", None, "OK", None),
])
def test_focus_check_reports_fallback_roi_and_end_check(roi_source, end_status, status, needle):
    roi = {"pixels": [1, 2, 3, 4], "quelle": roi_source, "hint_box": None}
    end = None if end_status is None else {
        "status": end_status,
        "reason": "Fokus nach Kameraneustart unscharf: 5 % ..." if end_status == "WARNUNG" else None,
    }
    check = live_setup.focus_check(roi, end)
    assert check["status"] == status
    assert check["metrics"]["roi"] == roi
    assert check["metrics"]["endpruefung"] == end
    if needle is None:
        assert "reason" not in check or check["reason"] is None or "LCD" not in check["reason"]
    else:
        assert needle in check["reason"]


def test_proposal_carries_focus_check_and_warning(tmp_path, monkeypatch):
    checks = SetupChecks('OK', {'kanten': CheckResult('OK', {}), 'rasterversatz': CheckResult('OK', {})})
    image, quad = reference_scene()
    cv2.imwrite(str(tmp_path / 'still.png'), image)
    monkeypatch.setattr(live_setup, 'write_overlays', lambda *a, **kw: [])
    focus = live_setup.focus_check({"pixels": [640, 360, 640, 360], "quelle": "mittleres_drittel",
                                    "hint_box": None}, None)
    proposal = live_setup.propose_with_fit(
        image, fit=SimpleNamespace(quad=quad), frame_path=tmp_path / 'still.png',
        camera_settings=replace(_CAMERA, size=image.shape[1::-1]), device_id='test', session_id='test',
        out_dir=tmp_path, final_checks=checks, offset_check=CheckResult('OK', {}),
        reader_check=CheckResult('OK', {}), focus_check=focus,
    )
    assert list(proposal['setup_checks']['checks'])[0] == 'fokus'
    assert proposal['setup_checks']['checks']['fokus']['status'] == 'WARNUNG'
    assert proposal['setup_checks']['overall'] == 'WARNUNG'


def test_focus_diagnostic_crop_is_small_and_contains_roi():
    frame = np.arange(1080 * 1920 * 3, dtype=np.uint32).astype(np.uint8).reshape(1080, 1920, 3)
    hint = (0.28, 0.13, 0.42, 0.10)
    crop, rect = live_setup.focus_diagnostic_crop(frame, hint)
    x, y, w, h = rect
    roi = live_setup.measurement_roi_pixels((1920, 1080), hint)
    assert _covered(rect, roi) == pytest.approx(1.0)
    np.testing.assert_array_equal(crop, frame[y:y + h, x:x + w])
    assert w * h < 0.25 * 1920 * 1080


def test_assist_measure_keeps_rejected_attempt_stills(tmp_path, monkeypatch):
    cam = SequenceSetupCamera([10, 20, 30, 40])
    reasons = iter(["keine_startlage", SimpleNamespace(quad=None)])
    monkeypatch.setattr(live_setup, "fit_lattice", lambda *_a, **_kw: next(reasons))
    monkeypatch.setattr(live_setup, "check_setup", lambda *_a, **_kw: SetupChecks(
        "FEHLER", {"kanten": CheckResult("FEHLER", {})}))
    with pytest.raises(live_setup.SetupError, match="Vorpruefung"):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("x"), expected_size=(3, 2), out_dir=tmp_path,
            hint_box=(0.0, 0.0, 1.0, 1.0), fit_attempts=3,
        )
    # Versuch 1 abgelehnt: sein Mittelbild bleibt neben dem des verwendeten Versuchs.
    assert {p.name for p in tmp_path.glob("*.png")} == {"still.png", "still-versuch-1.png"}
    assert int(cv2.imread(str(tmp_path / "still-versuch-1.png"))[0, 0, 0]) == 10
    assert int(cv2.imread(str(tmp_path / "still.png"))[0, 0, 0]) == 20


# --- OQ-74: Fokuspruefung nach dem Kameraneustart beim Laufstart ---

def test_quad_focus_reference_uses_single_stability_frames_on_quad_bbox():
    rng = np.random.default_rng(1)
    frames = [rng.integers(0, 255, (120, 200, 3), dtype=np.uint8) for _ in range(5)]
    quad = [[40.4, 30.0], [160.0, 32.0], [158.0, 90.6], [42.0, 88.0]]
    ref = live_setup.quad_focus_reference(frames, quad, (200, 120), source="einzelbilder")
    assert ref["roi_pixels"] == [40, 30, 120, 61]
    x, y, w, h = ref["roi_pixels"]
    assert ref["roi_box"] == pytest.approx([x / 200, y / 120, w / 200, h / 120])
    scores = [live_setup.sharpness(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)[y:y + h, x:x + w]) for f in frames]
    assert ref["score"] == pytest.approx(float(np.median(scores)))
    assert ref["frames"] == 5 and ref["quelle"] == "einzelbilder"
    assert ref["roi_mean"] > 0


def test_proposal_stores_focus_reference_from_stability_frames(tmp_path):
    from test_live_setup_tracking import _propose

    _, quad, proposal = _propose(tmp_path)
    ref = proposal["focus_reference"]
    assert ref["quelle"] == "stabilitaet_einzelbilder" and ref["frames"] > 1
    xs, ys = [p[0] for p in quad], [p[1] for p in quad]
    x, y, w, h = ref["roi_pixels"]
    assert x <= min(xs) + 1 and y <= min(ys) + 1 and x + w >= max(xs) - 1 and y + h >= max(ys) - 1


def _run_reference(score=600.0, mean=100.0):
    return {"roi_pixels": [0, 0, 160, 90], "roi_box": [0.0, 0.0, 1.0, 1.0], "score": score,
            "roi_mean": mean, "frames": 8, "quelle": "stabilitaet_einzelbilder"}


def test_run_start_focus_check_ok_without_moving_lens(end_check_sharpness):
    cam = RestartFocusCamera()
    result, frames = live_setup.check_focus_at_run_start(cam, _run_reference(), target=48, settle_s=0,
                                                         sleep=lambda _s: None)
    assert result["status"] == "OK" and result["reapproach"] is None and result["text"] is None
    assert cam.controls == []
    assert set(frames) == {"nach_neustart"}


def test_run_start_focus_check_resets_from_below_once(end_check_sharpness):
    cam = RestartFocusCamera(lost=True)
    result, _ = live_setup.check_focus_at_run_start(cam, _run_reference(), target=48, settle_s=0,
                                                    sleep=lambda _s: None)
    assert cam.controls == [[("focus_automatic_continuous", 0)], [("focus_absolute", 36)],
                            [("focus_absolute", 48)]]
    assert result["status"] == "OK"
    assert result["reapproach"]["restart_effect"] == pytest.approx(0.05, rel=0.01)
    assert "neu gesetzt" in result["text"]


def test_run_start_focus_check_warns_visibly_with_value(end_check_sharpness):
    cam = RestartFocusCamera(lost=True, recover=False)
    result, _ = live_setup.check_focus_at_run_start(cam, _run_reference(), target=48, settle_s=0,
                                                    sleep=lambda _s: None)
    assert result["status"] == "WARNUNG"
    assert result["text"] == "Bild nach Kamerastart unschärfer als bei der Einrichtung (5 %) – Fokus prüfen"
    assert sum(1 for controls in cam.controls for name, _ in controls if name == "focus_absolute") == 2


def test_run_start_focus_check_normalizes_brightness(end_check_sharpness):
    cam = RestartFocusCamera(brightness=1.25)
    result, _ = live_setup.check_focus_at_run_start(cam, _run_reference(), target=48, settle_s=0,
                                                    sleep=lambda _s: None)
    assert result["status"] == "OK"
    assert result["after_restart"]["ratio"] == pytest.approx(1.0, rel=0.01)


def test_run_start_focus_check_skipped_without_reference():
    assert live_setup.check_focus_at_run_start(FakeSetupCamera(None), None, target=48) is None
