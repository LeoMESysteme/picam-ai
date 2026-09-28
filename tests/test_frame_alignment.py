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

from dispread.frame_alignment import estimate_quad_shift, prepare_reference

CANVAS_SIZE = (500, 400)  # (Breite, Hoehe)
QUAD = [[150.0, 120.0], [250.0, 120.0], [250.0, 180.0], [150.0, 180.0]]

# --- Periodisches Glas (Review Fix-Runde 2) --------------------------------
#
# Eigene, groessere Szene: ein Schachbrettraster (stark periodisch, klassische
# Aliasing-Falle fuer Merkmalsabgleich) fuellt das GESAMTE Profil-Quad, nur
# eine Handvoll Rechtecke ausserhalb liefern nicht-periodische Gegenmerkmale.
# Das ist bewusst ein Extremfall (viel periodische, wenig echte Struktur) -
# er reproduziert die vom Review beschriebene Aliasing-Falle zuverlaessig
# (siehe Bericht dieser Aufgabe: ohne Maskierung liefert dieselbe Szene bei
# mehreren Seeds `max_corner_shift_px == 0.0` fuer eine tatsaechliche
# Verschiebung von zwei Rasterperioden).
PERIODIC_CANVAS_SIZE = (400, 300)  # (Breite, Hoehe)
PERIODIC_QUAD = [[100.0, 90.0], [300.0, 90.0], [300.0, 210.0], [100.0, 210.0]]
DOT_PERIOD_PX = 10


def _scene_with_periodic_glass(seed: int, *, n_rects: int = 10) -> np.ndarray:
    width, height = PERIODIC_CANVAS_SIZE
    rng = np.random.default_rng(seed)
    gray = np.full((height, width), 200, dtype=np.uint8)
    for _ in range(n_rects):
        x0, y0 = rng.integers(0, width - 30), rng.integers(0, height - 30)
        w, h = rng.integers(10, 40), rng.integers(10, 40)
        color = int(rng.integers(0, 180))
        cv2.rectangle(gray, (x0, y0), (x0 + w, y0 + h), color, -1)
    qx0, qy0, qx1, qy1 = (int(v) for v in (100, 90, 300, 210))
    for gy in range(qy0, qy1, DOT_PERIOD_PX):
        for gx in range(qx0, qx1, DOT_PERIOD_PX):
            parity = ((gx - qx0) // DOT_PERIOD_PX + (gy - qy0) // DOT_PERIOD_PX) % 2
            gray[gy : gy + DOT_PERIOD_PX, gx : gx + DOT_PERIOD_PX] = 40 if parity == 0 else 220
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


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


def test_periodic_pattern_inside_quad_is_not_aliased_to_zero_shift():
    """Review Fix-Runde 2: das Punktmatrix-Glas ist periodisch. Ohne die
    Maskierung des Quad-Inneren wuerde `cv2.estimateAffinePartial2D` bei
    dieser Szene (Schachbrettraster, wenig Gegenstruktur) eine Verschiebung
    um zwei Rasterperioden bei mehreren Seeds faelschlich als ~0 messen -
    exakt der Fall, den die Pruefung erkennen soll. Mit Maskierung muss die
    tatsaechliche Verschiebung (2 * DOT_PERIOD_PX) herauskommen, nicht 0."""
    for seed in (1, 2, 3, 4, 5):
        reference = _scene_with_periodic_glass(seed)
        shifted = _translated(reference, dx=2 * DOT_PERIOD_PX, dy=0)
        estimate = estimate_quad_shift(reference, shifted, PERIODIC_QUAD)
        assert estimate.reliable is True, (seed, estimate.reason)
        assert estimate.max_corner_shift_px == pytest.approx(2 * DOT_PERIOD_PX, abs=3.0), (
            seed,
            estimate.max_corner_shift_px,
        )


def test_reference_features_reused_gives_same_result_as_raw_image():
    """`prepare_reference()` + Wiederverwendung (Review Fix-Runde 2, Minor:
    Referenz-Merkmale einmal statt je Bild berechnen) muss dasselbe Ergebnis
    liefern wie der bisherige Aufruf mit dem rohen Referenzbild."""
    scene = _textured_scene()
    shifted = _translated(scene, dx=12, dy=-6)

    direct = estimate_quad_shift(scene, shifted, QUAD)
    reference_features = prepare_reference(scene, QUAD)
    via_cache = estimate_quad_shift(reference_features, shifted, QUAD)

    assert via_cache.reliable is direct.reliable is True
    assert via_cache.max_corner_shift_px == pytest.approx(direct.max_corner_shift_px, abs=1e-6)
    assert via_cache.moved_quad == direct.moved_quad

    # Dieselbe vorbereitete Referenz laesst sich gegen ein ZWEITES Bild
    # wiederverwenden (der eigentliche Zweck des Caches).
    second_current = _translated(scene, dx=5, dy=8)
    second = estimate_quad_shift(reference_features, second_current, QUAD)
    assert second.reliable is True
