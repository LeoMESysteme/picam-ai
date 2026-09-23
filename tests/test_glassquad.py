"""`dispread.glassquad` - Nachbesserung zu Task 3 aus
docs/superpowers/plans/2026-09-23-ernte-phase1.md.

`lcd_quad_in_region` (dispread.workbench.vision) filtert nur auf Saettigung -
das reicht nicht, wenn das Geraetegehaeuse um das Glas herum ebenfalls
gesaettigt ist (gemessen an frame_000412.jpg des GSV-2AS: das blaeuliche
Gehaeuse hat dort selbst hohe Saettigung). `glass_quad_in_region` schraenkt
deshalb zusaetzlich auf den am Zentrum der Hinweisbox gemessenen Farbton ein
und passt eine echte Vierpunkt-Trapezform an (nicht nur ein `minAreaRect`,
das rechte Winkel voraussetzt und bei Kameraperspektive - Task 6, 30/45 Grad -
systematisch daneben liegt).
"""

from __future__ import annotations

import cv2
import numpy as np

from dispread.glassquad import glass_quad_in_region
from dispread.rectify import _order_quad


def _hsv_to_bgr(hue: int, sat: int, val: int) -> tuple[int, int, int]:
    patch = np.uint8([[[hue, sat, val]]])
    bgr = cv2.cvtColor(patch, cv2.COLOR_HSV2BGR)[0, 0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


def _warp_fill(canvas: np.ndarray, quad_dst: list[list[float]], color: tuple[int, int, int]) -> None:
    """Ein flaches, einfarbiges Rechteck per echter Homographie in `quad_dst`
    projizieren und in `canvas` einblenden (nur die getroffenen Pixel)."""
    flat_w, flat_h = 300, 150
    flat = np.full((flat_h, flat_w, 3), color, dtype=np.uint8)
    src_pts = np.array([[0, 0], [flat_w, 0], [flat_w, flat_h], [0, flat_h]], dtype=np.float32)
    dst_pts = np.array(quad_dst, dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    size = (canvas.shape[1], canvas.shape[0])
    warped = cv2.warpPerspective(flat, matrix, size, flags=cv2.INTER_NEAREST)
    mask = cv2.warpPerspective(
        np.full((flat_h, flat_w), 255, dtype=np.uint8), matrix, size, flags=cv2.INTER_NEAREST
    )
    canvas[mask > 0] = warped[mask > 0]


# Echtes Trapez (Kameraperspektive, keine reine Drehung): die rechte Seite ist
# rund 32 % kuerzer als die linke - genau der Fall, den `minAreaRect`
# (rechtwinklige Hypothese) nicht abbilden kann, den Task 6 (30/45 Grad) aber
# braucht. Reihenfolge oben-links, oben-rechts, unten-rechts, unten-links.
GLASS_QUAD = [[150.0, 100.0], [550.0, 140.0], [530.0, 330.0], [160.0, 380.0]]
CANVAS_SIZE = (700, 500)  # (Breite, Hoehe)
GLASS_HUE = 43  # gelbgruen, gemessen am GSV-2AS-Display (frame_000412.jpg)
HOUSING_HUE = 112  # blaeulich, deutlich ausserhalb der Hue-Toleranz zum Glas


def _glass_hint_box() -> str:
    xs = [p[0] for p in GLASS_QUAD]
    ys = [p[1] for p in GLASS_QUAD]
    left, right = min(xs) - 30, max(xs) + 30
    top, bottom = min(ys) - 30, max(ys) + 30
    w, h = CANVAS_SIZE
    return f"{left / w},{top / h},{(right - left) / w},{(bottom - top) / h}"


def _assert_matches_glass_quad(found) -> None:
    assert found is not None
    expected = _order_quad(GLASS_QUAD)
    for (fx, fy), (ex, ey) in zip(found, expected, strict=True):
        assert abs(fx - ex) <= 2, (found, expected)
        assert abs(fy - ey) <= 2, (found, expected)


def test_perspective_trapezoid_within_2px():
    canvas_w, canvas_h = CANVAS_SIZE
    canvas = np.full((canvas_h, canvas_w, 3), 128, dtype=np.uint8)  # neutral grauer Grund
    _warp_fill(canvas, GLASS_QUAD, _hsv_to_bgr(GLASS_HUE, 200, 200))

    hint_x, hint_y, hint_w, hint_h = (float(v) for v in _glass_hint_box().split(","))
    found = glass_quad_in_region(canvas, (hint_x, hint_y, hint_w, hint_h))
    _assert_matches_glass_quad(found)


def test_saturated_housing_is_excluded():
    canvas_w, canvas_h = CANVAS_SIZE
    canvas = np.full((canvas_h, canvas_w, 3), 128, dtype=np.uint8)

    # Gesaettigtes blaeuliches Gehaeuse rund um das Glas - genau der Fall, an
    # dem eine reine Saettigungsschwelle (lcd_quad_in_region) scheitert.
    cv2.rectangle(canvas, (50, 50), (650, 450), _hsv_to_bgr(HOUSING_HUE, 180, 150), thickness=-1)
    # Dunkler, ungesaettigter Rahmen (Bezel) zwischen Gehaeuse und Glas.
    cv2.rectangle(canvas, (110, 80), (590, 400), (20, 20, 20), thickness=-1)
    _warp_fill(canvas, GLASS_QUAD, _hsv_to_bgr(GLASS_HUE, 200, 200))

    hint_x, hint_y, hint_w, hint_h = 50 / canvas_w, 50 / canvas_h, 600 / canvas_w, 400 / canvas_h
    found = glass_quad_in_region(canvas, (hint_x, hint_y, hint_w, hint_h))
    _assert_matches_glass_quad(found)


def test_no_glass_returns_none_no_guessing():
    canvas_w, canvas_h = CANVAS_SIZE
    canvas = np.full((canvas_h, canvas_w, 3), 128, dtype=np.uint8)
    hint_x, hint_y, hint_w, hint_h = (float(v) for v in _glass_hint_box().split(","))
    found = glass_quad_in_region(canvas, (hint_x, hint_y, hint_w, hint_h))
    assert found is None


def test_tiny_hint_box_returns_none():
    canvas = np.full((200, 200, 3), 128, dtype=np.uint8)
    found = glass_quad_in_region(canvas, (0.1, 0.1, 0.01, 0.01))
    assert found is None
