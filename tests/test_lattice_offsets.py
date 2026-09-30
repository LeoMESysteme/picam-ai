"""Tests fuer die Messung des Rasterversatzes und die Quad-Korrektur
(`dispread.lattice_offsets`, Befund Rasterversatz 2026-09-30)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from dispread.charcells import CharGrid
from dispread.lattice_offsets import (
    max_abs_offset,
    measure_offsets,
    median_offsets,
    refine_quad,
    refit_quad,
)
from dispread.ocr.dotmatrix_font import COLS, ROWS, rom_vector

GRID = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=17.78, bottom=160.0)
SIZE = (400, 160)
TRUE_QUAD = np.array([[120.0, 150.0], [760.0, 120.0], [770.0, 215.0], [110.0, 240.0]], np.float32)
TEXTS = ("+0.46781 ", "+ 23.905 ", "+1.20364 ")


def _source_image(text: str, quad=TRUE_QUAD, scale: int = 4) -> np.ndarray:
    """Zeichen scharf in Rasterkoordinaten (`scale`-fach aufgeloest) zeichnen
    und mit `quad` ins Quellbild (900 x 420) abbilden."""
    w, h = SIZE[0] * scale, SIZE[1] * scale
    hi = np.full((h, w), 200, np.uint8)
    kx, ky = (w - 1) / (SIZE[0] - 1), (h - 1) / (SIZE[1] - 1)  # Raster -> hochaufgeloest
    col_w = GRID.pitch / 6 * kx
    row_h = (GRID.bottom - GRID.top) / ROWS * ky
    for cell, ch in enumerate(text):
        v = rom_vector(ch).reshape(ROWS, COLS)
        for r in range(ROWS):
            for c in range(COLS):
                if v[r, c]:
                    x = (cell * GRID.pitch + GRID.left) * kx + (c + 0.5) * col_w
                    y = GRID.top * ky + (r + 0.5) * row_h
                    cv2.rectangle(
                        hi,
                        (int(x - 0.4 * col_w), int(y - 0.4 * row_h)),
                        (int(x + 0.4 * col_w), int(y + 0.4 * row_h)),
                        60,
                        -1,
                    )
    src = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32) * np.array(
        [(SIZE[0] - 1) / (w - 1), (SIZE[1] - 1) / (h - 1)], np.float32
    )
    hom = cv2.getPerspectiveTransform(src, quad) @ np.diag([(SIZE[0] - 1) / (w - 1), (SIZE[1] - 1) / (h - 1), 1.0])
    return cv2.warpPerspective(hi, hom, (900, 420), flags=cv2.INTER_AREA, borderValue=200)


FRAMES = [(_source_image(t), t) for t in TEXTS]


def test_true_quad_has_no_offset():
    """Messgenauigkeit je Halbzelle bei nur 1-3 Bildern: <= 0,1 Punkt (dy
    streut staerker, die Punkte sind hoch und das Plateau in y breiter)."""
    meds = median_offsets([measure_offsets(img, TRUE_QUAD, GRID, SIZE, t) for img, t in FRAMES])
    dx, dy = max_abs_offset(meds)
    assert dx < 0.06 and dy < 0.1, meds


def test_blank_cells_and_sparse_halves_are_skipped():
    offsets = measure_offsets(FRAMES[0][0], TRUE_QUAD, GRID, SIZE, FRAMES[0][1])
    cells = {(m.cell, m.half) for m in offsets}
    assert not any(c == 8 for c, _ in cells)  # Leerzelle
    assert (2, 0) not in cells  # obere Haelfte von '.'


def test_sheared_quad_shows_offset_in_lower_half():
    """Wie `ab4`: untere linke Ecke 8 px zu weit links -> geschertes Raster,
    die untere Halbzelle liegt links der Punkte (positiver Versatz)."""
    wrong = TRUE_QUAD.copy()
    wrong[3, 0] -= 8.0
    meds = median_offsets([measure_offsets(img, wrong, GRID, SIZE, t) for img, t in FRAMES])
    assert meds[(0, 1)][0] > meds[(0, 0)][0] + 0.2


def test_refine_recovers_true_quad_from_sheared_and_scaled_quad():
    wrong = TRUE_QUAD.copy()
    wrong[3, 0] -= 8.0  # Scherung (ab4)
    wrong[1, 0] -= 12.0  # Punktabstand zu klein (ab3)
    wrong[2, 0] -= 12.0
    refined, history = refine_quad(FRAMES, wrong, GRID, SIZE)
    assert np.abs(refined - TRUE_QUAD).max() < 1.5, refined
    after = median_offsets([measure_offsets(img, refined, GRID, SIZE, t) for img, t in FRAMES])
    dx, dy = max_abs_offset(after)
    assert dx < 0.06 and dy < 0.1
    assert max_abs_offset(history[0]["offsets"])[0] > 0.3


def test_refit_needs_enough_halves():
    with pytest.raises(ValueError):
        refit_quad(TRUE_QUAD, GRID, SIZE, {(0, 0): (0.0, 0.0, 3), (1, 0): (0.0, 0.0, 3)})


def test_low_correlation_measurements_are_ignored():
    blank = np.full((420, 900), 200, np.uint8)
    offsets = measure_offsets(blank, TRUE_QUAD, GRID, SIZE, TEXTS[0])
    assert median_offsets([offsets]) == {}
