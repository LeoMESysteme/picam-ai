"""Startsuche und sichere Ablehnung auf den Werkbank-Standbildern."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread import dotlattice
from dispread.dotlattice import LatticeFit, _lattice_candidates, evaluate_quad, fit_lattice
from dispread.setup_checks import raster_offset_check
from dispread.setup_hint import find_green_hint_box

VAR = Path(__file__).resolve().parents[1] / "var"
EMPTY_CELLS = (8, 13, 14, 15)
STILLS = [
    ("live/live-20261014T123033Z/setup/still.png", "+0.46801 "),
    ("live/live-20261014T123033Z/setup/stability.png", "+0.46801 "),
    ("live/live-20261014T123533Z/setup/still.png", "+0.46801 "),
    ("live/live-20261014T154211Z/setup/still.png", "+0.46797 "),
]


def _load(path):
    still = VAR / path
    if not still.exists():
        pytest.skip("Gespeichertes Standbild fehlt")
    image = cv2.imread(str(still))
    assert image is not None
    hint = find_green_hint_box(image)
    assert hint is not None
    return image, hint


@pytest.mark.parametrize("path,text", STILLS)
def test_bench_still_finds_lattice_with_ok_offset(path, text):
    image, hint = _load(path)
    result = fit_lattice(image, hint, empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result
    assert raster_offset_check([(image, text)], result.quad).status == "OK"


def test_one_row_skewed_bench_quad_exceeds_row_limit_and_fails_offset():
    image, hint = _load(STILLS[0][0])
    quad = [[643.6, 516.9], [1290.7, 530.8], [1287.0, 601.7], [645.2, 588.3]]
    result = evaluate_quad(image, hint, quad, empty_cells=EMPTY_CELLS)
    assert result == "zu_wenige_punkte"
    # Das falsche Quad scheitert schon vor dem RMS-Bericht (67 < 70 Punkte).
    # Den Restfehler deshalb direkt an den zugeordneten Kandidaten messen.
    q = np.asarray(quad, dtype=np.float32)
    h = cv2.getPerspectiveTransform(q, dotlattice._CORNERS[0])
    points = _lattice_candidates(image, q)
    ok, columns, rows = dotlattice._assignment(points, h)
    assert np.any(ok)
    residuals = dotlattice._warp_points(points[ok], h) - dotlattice._lat(columns[ok], rows[ok])
    rms_rows = float(np.sqrt(np.mean(residuals[:, 1] ** 2)) / dotlattice._PV)
    assert rms_rows > dotlattice._MAX_RMS_ROWS
    assert raster_offset_check([(image, STILLS[0][1])], quad).status == "FEHLER"


def test_sc7_stability_still_remains_rejected():
    image, hint = _load("diagnostics/sc7-assist/stability.png")
    assert isinstance(fit_lattice(image, hint, empty_cells=EMPTY_CELLS), str)


@pytest.mark.parametrize("path,text", STILLS)
@pytest.mark.parametrize("perturbation", ["noise", "brightness"])
def test_perturbed_bench_still_never_accepts_wrong_lattice(path, text, perturbation):
    image, hint = _load(path)
    if perturbation == "noise":
        noise = np.random.default_rng(7).normal(0, 4, image.shape)
        image = np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    else:
        image = (image.astype(np.float32) * 0.85).astype(np.uint8)
    result = fit_lattice(image, hint, empty_cells=EMPTY_CELLS)
    if isinstance(result, LatticeFit):
        assert raster_offset_check([(image, text)], result.quad).status == "OK"
    else:
        assert isinstance(result, str)


def test_lattice_candidates_on_blank_image_returns_empty_array():
    image = np.full((160, 400, 3), 200, np.uint8)
    quad = np.float32([[0, 0], [399, 0], [399, 159], [0, 159]])
    result = _lattice_candidates(image, quad)
    assert result.shape == (0, 2)
    assert result.dtype == np.float32


@pytest.mark.parametrize("terminal", ["startlage_mehrdeutig", "vorzeichen_kein_plus",
                                    "zu_wenige_punkte"])
def test_start_search_does_not_retry_terminal_rejection(monkeypatch, terminal):
    def search(*args, **kwargs):
        return next(results)

    results = iter([terminal])
    monkeypatch.setattr(dotlattice, "_auto_fit", search)
    image = np.full((160, 400, 3), 200, np.uint8)
    assert fit_lattice(image, (0, 0, 1, 1)) == terminal


@pytest.mark.parametrize("outcomes,expected", [
    (["keine_startlage", "keine_startlage", "startlage_mehrdeutig"], "startlage_mehrdeutig"),
    (["keine_startlage"] * 3, "keine_startlage"),
])
def test_start_search_retries_only_missing_start_with_measured_smoothing(monkeypatch, outcomes, expected):
    def search(*args, sigma_fraction=None, **kwargs):
        assert sigma_fraction == next(fractions)
        return next(results)

    fractions = iter([None, 0.15, 0.18])
    results = iter(outcomes)
    monkeypatch.setattr(dotlattice, "_auto_fit", search)
    image = np.full((160, 400, 3), 200, np.uint8)
    assert fit_lattice(image, (0, 0, 1, 1)) == expected
    assert list(results) == []


@pytest.mark.parametrize("pass_index", [1, 2])
@pytest.mark.parametrize("rejection", ["zu_wenige_punkte", "vorzeichen_kein_plus",
                                      "restfehler_zu_gross", "startlage_mehrdeutig"])
def test_fallback_rejection_preserves_missing_start_hint(monkeypatch, pass_index, rejection):
    outcomes = ["keine_startlage"] * pass_index + [rejection]
    calls = []

    def search(*args, sigma_fraction=None, **kwargs):
        calls.append(sigma_fraction)
        return outcomes[len(calls) - 1]

    monkeypatch.setattr(dotlattice, "_auto_fit", search)
    image = np.full((160, 400, 3), 200, np.uint8)
    expected = rejection if rejection in {"startlage_mehrdeutig", "vorzeichen_kein_plus"} else "keine_startlage"
    assert fit_lattice(image, (0, 0, 1, 1)) == expected
    assert calls == list(dotlattice._START_SIGMA_FRACTIONS[:pass_index + 1])


@pytest.mark.parametrize("pass_index", [0, 1, 2])
def test_start_search_returns_accepted_fit_unchanged(monkeypatch, pass_index):
    accepted = object()
    outcomes = iter(["keine_startlage"] * pass_index + [accepted])
    monkeypatch.setattr(dotlattice, "_auto_fit", lambda *args, **kwargs: next(outcomes))
    image = np.full((160, 400, 3), 200, np.uint8)
    assert fit_lattice(image, (0, 0, 1, 1)) is accepted
    assert list(outcomes) == []
