"""Schwache Punktschatten unter Zeile 6 gegen echte Cursorpunkte abgrenzen."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
from dotmatrix_helpers import render

from dispread.charcells import CharGrid
from dispread.dotlattice import LatticeFit, evaluate_quad
from dispread.setup_hint import find_green_hint_box

DIAGNOSTICS = Path("var/diagnostics")
EMPTY_CELLS = (8, 13, 14, 15)


@pytest.mark.parametrize("still", (
    "sc7a-assist/still.png",
    "sc7a-still/frames/frame_000007.png",
    "sc7a-still/frames/frame_000014.png",
    "sc7a-still/frames/frame_000016.png",
    "sc7a-still/frames/frame_000023.png",
))
def test_sc7a_point_shadows_do_not_populate_cursor_row(still: str):
    image_path = DIAGNOSTICS / still
    quad_path = DIAGNOSTICS / "sc7a-quad.json"
    if not image_path.exists() or not quad_path.exists():
        pytest.skip("Gespeichertes sc7a-Bild oder Quad fehlt")
    image = cv2.imread(str(image_path))
    assert image is not None
    hint = find_green_hint_box(image)
    assert hint is not None
    quad = json.loads(quad_path.read_text())
    result = evaluate_quad(image, hint, quad, empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result


def test_genuinely_populated_cursor_row_is_rejected():
    quad = np.float32([[720, 550], [1200, 625], [1193, 695], [718, 610]])
    grid = CharGrid(n_cells=16, left=0, pitch=25, top=160 / 9, bottom=160)
    display = render("+123456789012345", grid, bg=210, ink=30)
    transform = cv2.getPerspectiveTransform(
        np.float32([[0, 0], [399, 0], [399, 159], [0, 159]]), quad,
    )
    gray = cv2.warpPerspective(display, transform, (1920, 1080), borderValue=120)
    image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    cursor_points = np.float32([
        [(col + 0.5) * 25 / 6, 160 / 9 + 7.5 * 160 / 9]
        for col in range(5)
    ])
    positions = cv2.perspectiveTransform(cursor_points[None], transform)[0]
    for x, y in positions:
        cv2.circle(image, (round(float(x)), round(float(y))), 3, (30, 30, 30), -1)
    lo, hi = quad.min(axis=0), quad.max(axis=0)
    pad = (hi - lo) * 0.1
    x0, y0 = lo - pad
    x1, y1 = hi + pad
    hint = (x0 / 1920, y0 / 1080, (x1 - x0) / 1920, (y1 - y0) / 1080)
    assert evaluate_quad(image, hint, quad) == "cursorzeile_belegt"
