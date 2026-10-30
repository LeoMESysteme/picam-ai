"""`dispread.focus_sweep` - Task 4 (Profil v3 und harvest-setup.py)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from dispread.focus_sweep import climb_focus, sharpness, sweep_focus


def test_sweep_findet_maximum_grob_dann_fein():
    calls = []

    def measure(f):
        calls.append(f)
        return -abs(f - 50)

    best, measured = sweep_focus(measure)
    assert best == 50
    assert calls[:32] == list(range(0, 256, 8))
    assert all(42 <= f <= 58 for f in calls[32:])
    assert measured[-1][0] == calls[-1]


def test_sweep_bleibt_im_bereich():
    best, measured = sweep_focus(lambda f: f)
    assert best == max(f for f, _ in measured)
    assert all(0 <= f <= 255 for f, _ in measured)


def test_sweep_misst_keinen_fokuswert_zweimal():
    calls = []

    def measure(f):
        calls.append(f)
        return -abs(f - 48)  # 48 liegt bereits in `coarse`

    sweep_focus(measure)
    assert len(calls) == len(set(calls))


def _checkerboard(size: int = 64, cell: int = 4) -> np.ndarray:
    row = (np.arange(size) // cell) % 2
    return (np.logical_xor(row[:, None], row[None, :]).astype(np.uint8)) * 255


def test_sharpness_scharf_groesser_als_weichgezeichnet():
    sharp = _checkerboard()
    blurred = cv2.GaussianBlur(sharp, (9, 9), 0)
    assert sharpness(sharp) > sharpness(blurred)


@pytest.mark.parametrize("peak,limit", [(46, 10), (68, 12), (12, 15), (250, 35)])
def test_climb_findet_gipfel_ohne_vollsweep(peak, limit):
    calls = []

    def measure(focus):
        calls.append(focus)
        return float(1000 * np.exp(-((focus - peak) / 10) ** 2))

    best, measured = climb_focus(measure)
    assert abs(best - peak) <= 2
    assert len(calls) <= limit
    assert len(calls) == len(set(calls))
    assert [f for f, _ in measured] == calls
    assert measured.focus_method == "climb"


def test_climb_flacher_rand_faellt_auf_sweep_zurueck_ohne_doppelmessung():
    calls = []

    def measure(focus):
        calls.append(focus)
        return max(10.0, 1000.0 - (focus - 50) ** 2)

    best, measured = climb_focus(measure, start=200)
    assert abs(best - 50) <= 2
    assert calls[:3] == [200, 208, 192]
    assert len(calls) == len(set(calls))
    assert [f for f, _ in measured] == calls
    assert measured.focus_method == "sweep"


@pytest.mark.parametrize("start", [48, 68])
def test_climb_reale_interpolierte_kurve(start):
    calls = []

    def measure(focus):
        calls.append(focus)
        return float(np.interp(focus, [0, 32, 40, 48, 56, 64, 80, 255],
                               [11, 79.6, 264.3, 431.6, 135.6, 55.3, 16, 11]))

    best, measured = climb_focus(measure, start=start)
    assert abs(best - 48) <= 2
    assert len(calls) <= 12
    assert len(calls) == len(set(calls)) == len(measured)


@pytest.mark.parametrize("start", [100, 150, 200, 240])
@pytest.mark.parametrize("noise_level", [0.05, 0.10])
@pytest.mark.parametrize("seed", range(20))
def test_climb_rauschender_flacher_rand_findet_realen_gipfel(start, noise_level, seed):
    noise = np.random.default_rng(seed).uniform(-noise_level, noise_level, 256)
    calls = []

    def measure(focus):
        calls.append(focus)
        score = np.interp(focus, [0, 32, 40, 48, 56, 64, 80, 255],
                          [11, 79.6, 264.3, 431.6, 135.6, 55.3, 16, 11])
        return float(score * (1 + noise[focus]))

    best, measured = climb_focus(measure, start=start)
    assert abs(best - 48) <= 2
    if measured.focus_method == "climb":
        assert max(s for _, s in measured) >= 2 * min(s for _, s in measured)
    assert len(calls) == len(set(calls)) == len(measured)
    assert [f for f, _ in measured] == calls


def test_climb_leichtes_rauschen_bleibt_innerhalb_eines_feinschritts():
    def curve(focus):
        return 10 + 1000 * np.exp(-((focus - 46) / 10) ** 2)

    clean, _ = climb_focus(curve)
    for seed in range(10):
        noise = np.random.default_rng(seed).uniform(-0.02, 0.02, 256)
        best, _ = climb_focus(lambda f, noise=noise: curve(f) * (1 + noise[f]))
        assert abs(best - clean) <= 2


@pytest.mark.parametrize("start,peak", [(0, 0), (255, 255), (0, 12), (255, 250)])
def test_climb_begrenzt_nachbarn_und_misst_grenzen_nur_einmal(start, peak):
    calls = []

    def measure(focus):
        assert 0 <= focus <= 255
        calls.append(focus)
        return 1000 - abs(focus - peak)

    best, _ = climb_focus(measure, start=start, flat_tolerance=0)
    assert abs(best - peak) <= 2
    assert len(calls) == len(set(calls))


def test_climb_geht_ueber_plateau_bis_zum_abfall():
    scores = {48: 100, 56: 110, 64: 108, 72: 150, 80: 50}
    calls = []

    def measure(focus):
        calls.append(focus)
        return scores.get(focus, 90)

    best, _ = climb_focus(measure)
    assert best == 72
    assert calls[:5] == [48, 56, 64, 72, 80]
    assert 88 not in calls


def test_climb_feinsuche_scannt_aufsteigend_das_ganze_fenster():
    best, measured = climb_focus(lambda f: 100 - (f - 48) ** 2)
    assert best == 48
    assert [f for f, _ in measured] == [48, 56, 40, 42, 44, 46, 50, 52, 54]


def test_climb_feinsuche_nimmt_das_grobmaximum_auch_unter_der_richtungsschwelle():
    scores = {48: 100, 56: 104, 40: 50, 60: 150}
    best, measured = climb_focus(lambda focus: scores.get(focus, 90))
    assert best == 60
    assert max(score for _, score in measured) == 150


@pytest.mark.parametrize("peak_ratio,method", [(2.0, "climb"), (2.01, "sweep")])
def test_climb_feinabstand_und_plausibilitaetsgrenze(peak_ratio, method):
    best, measured = climb_focus(lambda f: 50 if f in (38, 58) else 100,
                                 step=10, fine_step=4, peak_ratio=peak_ratio)
    assert best == 48
    assert measured.focus_method == method
    assert [f for f, _ in measured][:7] == [48, 58, 38, 42, 46, 50, 54]
    if method == "climb":
        assert len(measured) == 7
