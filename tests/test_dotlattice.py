"""Punktraster-Anpassung an synthetischen und vorhandenen Standbildern."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from dotmatrix_helpers import render

from dispread import dotlattice
from dispread.charcells import CharGrid
from dispread.dotlattice import LatticeFit, fit_lattice
from dispread.setup_checks import check_setup
from dispread.setup_hint import find_green_hint_box

GRID = CharGrid(n_cells=16, left=0, pitch=25, top=160 / 9, bottom=160)
DIAGNOSTICS = Path("/home/me-systeme/picam-ai/var/diagnostics")
EMPTY_CELLS = (8, 13, 14, 15)


def _box(quad: np.ndarray, shape: tuple[int, int], margin: float = 0.1):
    h, w = shape
    lo, hi = quad.min(axis=0), quad.max(axis=0)
    pad = (hi - lo) * margin
    x0, y0 = (lo - pad).tolist()
    x1, y1 = (hi + pad).tolist()
    return x0 / w, y0 / h, (x1 - x0) / w, (y1 - y0) / h


def _profile_pixel_centers(quad: np.ndarray) -> np.ndarray:
    """Historische 400/160-Randkoordinaten in 399/159-Pixelmitten umrechnen."""
    old = np.float32([[0, 0], [400, 0], [400, 160], [0, 160]])
    centers = np.float32([[0, 0], [399, 0], [399, 159], [0, 159]])
    h = cv2.getPerspectiveTransform(old, quad)
    return cv2.perspectiveTransform(centers[None], h)[0]


def _synthetic(quad: np.ndarray, text: str = "+123456789012345"):
    display = render(text, GRID, bg=210, ink=30)
    h = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [399, 0], [399, 159], [0, 159]]), quad.astype(np.float32)
    )
    image = cv2.warpPerspective(display, h, (1920, 1080), borderValue=120)
    rng = np.random.default_rng(73)
    image = np.clip(image.astype(float) + rng.normal(0, 3, image.shape), 0, 255).astype(np.uint8)
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), h


def _seeds(h: np.ndarray):
    cr = np.float32([[2, 1], [2, 5], [74, 1], [74, 5]])
    lat = np.column_stack(((cr[:, 0] + 0.5) * 25 / 6, 160 / 9 + (cr[:, 1] + 0.5) * 160 / 9))
    pts = cv2.perspectiveTransform(lat.astype(np.float32)[None], h)[0]
    return [(tuple(map(float, xy)), tuple(map(int, coord))) for xy, coord in zip(pts, cr, strict=True)]


@pytest.mark.parametrize("quad", [
    np.float32([[710, 540], [1190, 610], [1182, 677], [707, 600]]),
    np.float32([[740, 608], [1210, 536], [1215, 598], [745, 678]]),
    np.float32([[770, 520], [1160, 625], [1153, 678], [768, 573]]),
    np.float32([[760, 620], [1150, 515], [1155, 568], [765, 673]]),
])
def test_refine_recovers_synthetic_quad_from_seeds(quad):
    image, h = _synthetic(quad)
    result = fit_lattice(image, _box(quad, image.shape[:2]), seeds=_seeds(h))
    assert isinstance(result, LatticeFit), result
    assert np.max(np.linalg.norm(np.asarray(result.quad) - quad, axis=1)) <= 1.0
    assert result.rms_cols < 0.2


@pytest.mark.parametrize("quad", [
    np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]]),
    np.float32([[770, 520], [1160, 625], [1153, 678], [768, 573]]),
    np.float32([[760, 620], [1150, 515], [1155, 568], [765, 673]]),
])
def test_automatic_start_recovers_synthetic_quad(quad):
    image, _ = _synthetic(quad)
    result = fit_lattice(image, _box(quad, image.shape[:2]))
    assert isinstance(result, LatticeFit), result
    assert np.max(np.linalg.norm(np.asarray(result.quad) - quad, axis=1)) <= 1.0


def test_sparse_display_is_rejected():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, _ = _synthetic(quad, "+1              ")
    assert isinstance(fit_lattice(image, _box(quad, image.shape[:2])), str)


def test_shifted_column_seed_cannot_relabel_plus_as_valid():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, h = _synthetic(quad)
    shifted = [(xy, (cr[0] + 1, cr[1])) for xy, cr in _seeds(h)]
    assert isinstance(fit_lattice(image, _box(quad, image.shape[:2]), seeds=shifted), str)


def test_two_column_seed_shift_is_rejected():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, h = _synthetic(quad, "+1234567 9012   ")
    assert isinstance(
        fit_lattice(image, _box(quad, image.shape[:2]), seeds=_seeds(h),
                    empty_cells=EMPTY_CELLS), LatticeFit,
    )
    shifted = [(xy, (cr[0] + 2, cr[1])) for xy, cr in _seeds(h)]
    assert isinstance(fit_lattice(image, _box(quad, image.shape[:2]), seeds=shifted,
                                  empty_cells=EMPTY_CELLS), str)


def test_minus_sign_has_specific_rejection_reason():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, _ = _synthetic(quad, "-1234567 9012   ")
    assert fit_lattice(image, _box(quad, image.shape[:2]),
                       empty_cells=EMPTY_CELLS) == "vorzeichen_kein_plus"


@pytest.mark.skipif(
    not (DIAGNOSTICS / "ab3-still/frames/frame_000015.png").exists()
    or not (DIAGNOSTICS / "ab3-profile").exists(),
    reason="Standbild oder bestaetigtes Profil fehlt",
)
def test_ab3_plus_is_not_reported_as_proven_minus():
    image = cv2.imread(str(DIAGNOSTICS / "ab3-still/frames/frame_000015.png"))
    quad = np.asarray(json.loads((DIAGNOSTICS / "ab3-profile").read_text())["quad"], np.float32)
    result = fit_lattice(image, _box(quad, image.shape[:2]), empty_cells=EMPTY_CELLS)
    assert result != "vorzeichen_kein_plus"


@pytest.mark.parametrize("column", (2, 5))
def test_candidate_in_format_empty_cell_is_rejected(column):
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, h = _synthetic(quad, "+1234567 9012   ")
    target = np.float32([[[8 * 25 + (column + 0.5) * 25 / 6,
                           160 / 9 + 3.5 * 160 / 9]]])
    x, y = cv2.perspectiveTransform(target, h)[0, 0]
    cv2.circle(image, (round(float(x)), round(float(y))), 2, (10, 10, 10), -1)
    assert fit_lattice(image, _box(quad, image.shape[:2]), seeds=_seeds(h),
                       empty_cells=EMPTY_CELLS) == "leerzelle_belegt"


def test_cell_bias_over_limit_rejects_locally_displaced_dots():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    display = render("+1234567 9012   ", GRID, bg=210, ink=30)
    left, right = 4 * 25, 5 * 25
    display[:, left:right] = cv2.warpAffine(
        display[:, left:right], np.float32([[1, 0, 1.5], [0, 1, 0]]),
        (right - left, display.shape[0]), borderValue=210,
    )
    h = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [399, 0], [399, 159], [0, 159]]), quad,
    )
    gray = cv2.warpPerspective(display, h, (1920, 1080), borderValue=120)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    assert fit_lattice(image, _box(quad, image.shape[:2]), seeds=_seeds(h),
                       empty_cells=EMPTY_CELLS) == "bias_zu_gross"


def test_automatic_start_recovers_seven_pixel_pitch():
    quad = np.float32([[600, 480], [1272, 480], [1272, 650], [600, 650]])
    image, _ = _synthetic(quad, "+1234567 9012   ")
    result = fit_lattice(image, _box(quad, image.shape[:2]), empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result
    assert np.max(np.linalg.norm(np.asarray(result.quad) - quad, axis=1)) <= 1.5


def test_cursor_row_point_is_rejected():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, h = _synthetic(quad)
    target = np.float32([[[2.5 * 25 / 6, 160 / 9 + 7.5 * 160 / 9]]])
    x, y = cv2.perspectiveTransform(target, h)[0, 0]
    cv2.circle(image, (round(float(x)), round(float(y))), 3, (10, 10, 10), -1)
    assert isinstance(fit_lattice(image, _box(quad, image.shape[:2]), seeds=_seeds(h)), str)


def test_two_equally_clear_displays_have_ambiguous_start():
    upper = np.float32([[450, 450], [930, 525], [923, 595], [448, 510]])
    lower = upper + np.float32([0, 200])
    image, _ = _synthetic(upper)
    second, _ = _synthetic(lower)
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, lower.astype(np.int32), 1)
    image[mask != 0] = second[mask != 0]
    hint = _box(np.concatenate((upper, lower)), image.shape[:2])
    assert fit_lattice(image, hint) == "startlage_mehrdeutig"


def test_two_displays_with_unequal_plus_strength_have_ambiguous_start():
    upper = np.float32([[450, 450], [930, 525], [923, 595], [448, 510]])
    lower = upper + np.float32([0, 200])
    image, _ = _synthetic(upper)
    second, h = _synthetic(lower)
    dot = cv2.perspectiveTransform(
        np.float32([[[2.5 * 25 / 6, 160 / 9 + 1.5 * 160 / 9]]]), h,
    )[0, 0]
    cv2.circle(second, tuple(np.rint(dot).astype(int)), 3, (210, 210, 210), -1)
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, lower.astype(np.int32), 1)
    image[mask != 0] = second[mask != 0]
    hint = _box(np.concatenate((upper, lower)), image.shape[:2])
    assert fit_lattice(image, hint) == "startlage_mehrdeutig"


def _fit_at(x: float, n_assigned: int) -> LatticeFit:
    return LatticeFit(
        quad=[[x, 0], [x + 400, 0], [x + 400, 160], [x, 160]],
        n_dots=n_assigned,
        n_assigned=n_assigned,
        rms_cols=0.1,
        rms_rows=0.1,
        cells=(0,),
        row_bias=(0.0,),
        cell_bias=(0.0,),
    )


def test_near_duplicate_does_not_hide_competing_end_lattice():
    best = _fit_at(0, 100)
    duplicate = _fit_at(2.5, 99)
    competitor = _fit_at(5, 98)
    assert dotlattice._select_unambiguous_fit([best, duplicate, competitor]) == "startlage_mehrdeutig"


def test_clear_best_end_lattice_is_selected():
    best = _fit_at(0, 100)
    duplicate = _fit_at(1, 99)
    distant_weaker = _fit_at(5, 90)
    assert dotlattice._select_unambiguous_fit([best, duplicate, distant_weaker]) is best


def test_evaluate_quad_preserves_supplied_pixel_center_quad():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, _ = _synthetic(quad, "+1234567 9012   ")
    result = dotlattice.evaluate_quad(image, _box(quad, image.shape[:2]), quad,
                                      empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result
    np.testing.assert_allclose(result.quad, quad, atol=1e-5)
    assert result.n_assigned >= 70


def test_evaluate_quad_still_rejects_wrong_plus_location():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    image, _ = _synthetic(quad, "+1234567 9012   ")
    wrong_quad = quad + np.float32([10, 0])
    assert dotlattice.evaluate_quad(
        image, _box(quad, image.shape[:2]), wrong_quad, empty_cells=EMPTY_CELLS,
    ) == "plus_nicht_gefunden"


@pytest.mark.parametrize("name,profile,frame,proxy", [
    ("ab4", "ab4-profile-regrid1.json", 16, "rms"),
    ("ab5", "ab5-profile", 7, None),
    ("ab6", "ab6-profile", 22, "rms"),
    ("sc6", "sc6-profile", 15, "bias"),
])
def test_evaluate_quad_reports_validated_profile_despite_proxy_limit(name, profile, frame, proxy):
    still = DIAGNOSTICS / f"{name}-still/frames/frame_{frame:06d}.png"
    profile_path = DIAGNOSTICS / profile
    if not still.exists() or not profile_path.exists():
        pytest.skip("Standbild oder bestaetigtes Profil fehlt")
    image = cv2.imread(str(still))
    assert image is not None
    hint = find_green_hint_box(image)
    assert hint is not None
    quad = json.loads(profile_path.read_text())["quad"]
    # Hier wird absichtlich das gespeicherte Quad unveraendert uebergeben,
    # genau wie bei `propose --quad`. Der 2j-Textabgleich folgt im Aufrufer.
    result = dotlattice.evaluate_quad(image, hint, quad, empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result
    np.testing.assert_allclose(result.quad, quad, atol=1e-4)
    if proxy == "rms":
        assert result.rms_cols > dotlattice._MAX_RMS_COLS or result.rms_rows > dotlattice._MAX_RMS_ROWS
    elif proxy == "bias":
        assert max(map(abs, (*result.row_bias, *result.cell_bias))) > 0.15


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            name,
            marks=pytest.mark.skipif(
                not (DIAGNOSTICS / f"{name}-still/frames/"
                     f"frame_{'000015' if name == 'sc6' else '000017'}.png").exists()
                or not (DIAGNOSTICS / f"{name if name != 'sc3' else 'sc3b'}-profile").exists(),
                reason="Standbild oder bestaetigtes Profil fehlt",
            ),
        )
        for name in ("sc3", "sc4", "sc5", "ab1", "ab2", "sc6")
    ],
)
def test_real_still_matches_confirmed_quad(name):
    frame = "frame_000015.png" if name == "sc6" else "frame_000017.png"
    still = DIAGNOSTICS / f"{name}-still/frames/{frame}"
    profile = DIAGNOSTICS / f"{name if name != 'sc3' else 'sc3b'}-profile"
    image = cv2.imread(str(still))
    quad = np.asarray(json.loads(profile.read_text())["quad"], np.float32)
    result = fit_lattice(image, _box(quad, image.shape[:2]), empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result
    assert np.max(np.linalg.norm(np.asarray(result.quad) - _profile_pixel_centers(quad), axis=1)) <= 1.5


@pytest.mark.skipif(
    not (DIAGNOSTICS / "ab2-still/frames/frame_000017.png").exists()
    or not (DIAGNOSTICS / "ab2-profile").exists(),
    reason="Standbild oder bestaetigtes Profil fehlt",
)
def test_green_hint_still_finds_ab2_lattice():
    image = cv2.imread(str(DIAGNOSTICS / "ab2-still/frames/frame_000017.png"))
    quad = np.asarray(json.loads((DIAGNOSTICS / "ab2-profile").read_text())["quad"], np.float32)
    hint = find_green_hint_box(image)
    assert hint is not None
    result = fit_lattice(image, hint, empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result
    assert np.max(np.linalg.norm(np.asarray(result.quad) - _profile_pixel_centers(quad), axis=1)) <= 1.5


@pytest.mark.parametrize("name,frame", [
    pytest.param(
        name, frame,
        marks=pytest.mark.skipif(
            not (DIAGNOSTICS / f"{name}-still/frames/{frame}").exists()
            or not (DIAGNOSTICS / f"{name if name != 'sc3' else 'sc3b'}-profile").exists(),
            reason="Standbild oder bestaetigtes Profil fehlt",
        ),
    )
    for name, frame in [
        ("sc3", "frame_000017.png"),
        ("sc4", "frame_000017.png"),
        ("sc5", "frame_000017.png"),
        ("ab1", "frame_000017.png"),
        ("sc6", "frame_000015.png"),
    ]
])
def test_green_hint_still_matches_confirmed_quad(name, frame):
    still = DIAGNOSTICS / f"{name}-still/frames/{frame}"
    profile = DIAGNOSTICS / f"{name if name != 'sc3' else 'sc3b'}-profile"
    image = cv2.imread(str(still))
    quad = np.asarray(json.loads(profile.read_text())["quad"], np.float32)
    hint = find_green_hint_box(image)
    assert hint is not None
    result = fit_lattice(image, hint, empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result
    assert np.max(np.linalg.norm(np.asarray(result.quad) - _profile_pixel_centers(quad), axis=1)) <= 1.5


@pytest.mark.skipif(
    not (DIAGNOSTICS / "sc6-still/frames/frame_000015.png").exists(),
    reason="Standbild fehlt",
)
def test_evaluate_quad_agrees_with_fit_on_sc6_still():
    image = cv2.imread(str(DIAGNOSTICS / "sc6-still/frames/frame_000015.png"))
    hint = find_green_hint_box(image)
    assert hint is not None
    fit = fit_lattice(image, hint, empty_cells=EMPTY_CELLS)
    assert isinstance(fit, LatticeFit), fit
    evaluated = dotlattice.evaluate_quad(image, hint, fit.quad, empty_cells=EMPTY_CELLS)
    assert isinstance(evaluated, LatticeFit), evaluated
    assert abs(evaluated.n_dots - fit.n_dots) <= 15
    assert abs(evaluated.n_assigned - fit.n_assigned) <= 5
    assert check_setup(image, evaluated).to_dict()["overall"] in {"OK", "WARNUNG"}


@pytest.mark.parametrize("name,frame,reason", [
    ("ab4", 16, "startlage_mehrdeutig"),
    ("ab6", 22, "keine_startlage"),
])
def test_uncertain_real_still_start_is_rejected(name, frame, reason):
    still = DIAGNOSTICS / f"{name}-still/frames/frame_{frame:06d}.png"
    if not still.exists():
        pytest.skip("Standbild fehlt")
    image = cv2.imread(str(still))
    hint = find_green_hint_box(image)
    assert hint is not None
    assert fit_lattice(image, hint, empty_cells=EMPTY_CELLS) == reason
