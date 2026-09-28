"""`dispread.frame_alignment` - Ausrichtungspruefung Ernte <-> Profilbild
(Task 10, StreamCam-Umstieg).

Synthetisches, texturiertes Bild (zufaellige Rechtecke) statt eines reinen
Rauschbilds - Rauschen liefert zwar ORB-Deskriptoren, aber `warpAffine` mit
`BORDER_REFLECT` an den Raendern erzeugt dort neue, im Original nicht
vorhandene Muster; die Rechtecke bleiben dagegen als klare Kanten/Ecken auch
nach einer Translation im ueberlappenden Bereich wiedererkennbar.

Die realen Schwellenwerte des Moduls sind gegen `var/diagnostics/sc1-run`
(gegen `sc1-focus/control.png`) und `var/diagnostics/sc2-run` (gegen
`sc2-still/frame_000014.png`) kalibriert (siehe Moduldocstring) - hier nur
noch synthetisch die drei Grundfaelle: unverschoben, verschoben, unpruefbar.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from dispread.frame_alignment import estimate_quad_shift

CANVAS_SIZE = (500, 400)  # (Breite, Hoehe)
QUAD = [[150.0, 120.0], [250.0, 120.0], [250.0, 180.0], [150.0, 180.0]]


def _textured_scene() -> np.ndarray:
    width, height = CANVAS_SIZE
    rng = np.random.default_rng(7)
    gray = np.full((height, width), 200, dtype=np.uint8)
    for _ in range(60):
        x0, y0 = rng.integers(0, width - 30), rng.integers(0, height - 30)
        w, h = rng.integers(10, 40), rng.integers(10, 40)
        color = int(rng.integers(0, 180))
        cv2.rectangle(gray, (x0, y0), (x0 + w, y0 + h), color, -1)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _translated(image: np.ndarray, dx: float, dy: float) -> np.ndarray:
    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(image, matrix, (image.shape[1], image.shape[0]), borderMode=cv2.BORDER_REFLECT)


def test_identical_images_have_zero_shift():
    scene = _textured_scene()
    estimate = estimate_quad_shift(scene, scene, QUAD)
    assert estimate.reliable is True
    assert estimate.max_corner_shift_px == 0.0
    assert estimate.moved_quad is not None


def test_translated_image_reports_matching_corner_shift():
    scene = _textured_scene()
    shifted = _translated(scene, dx=40, dy=25)
    estimate = estimate_quad_shift(scene, shifted, QUAD)
    assert estimate.reliable is True
    # Translation ohne Rotation/Massstab: alle vier Ecken verschieben sich
    # um denselben Betrag wie das Bild selbst.
    expected = float(np.hypot(40, 25))
    assert estimate.max_corner_shift_px == pytest.approx(expected, abs=2.0)
    moved = estimate.moved_quad
    for (mx, my), (ox, oy) in zip(moved, QUAD, strict=True):
        assert abs((mx - ox) - 40) < 3
        assert abs((my - oy) - 25) < 3


def test_small_translation_stays_small():
    scene = _textured_scene()
    shifted = _translated(scene, dx=3, dy=-2)
    estimate = estimate_quad_shift(scene, shifted, QUAD)
    assert estimate.reliable is True
    assert estimate.max_corner_shift_px < 5.0


def test_structureless_current_image_is_unreliable():
    scene = _textured_scene()
    blank = np.full_like(scene, 128)
    estimate = estimate_quad_shift(scene, blank, QUAD)
    assert estimate.reliable is False
    assert estimate.max_corner_shift_px is None
    assert estimate.moved_quad is None
    assert estimate.reason


def test_structureless_both_images_is_unreliable():
    blank = np.full(CANVAS_SIZE[::-1] + (3,), 128, dtype=np.uint8)
    estimate = estimate_quad_shift(blank, blank, QUAD)
    assert estimate.reliable is False
    assert estimate.reason
