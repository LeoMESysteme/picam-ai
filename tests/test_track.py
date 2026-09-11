"""Verankerte Nachfuehrung: derselben Anzeige folgen, nie eine andere waehlen."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from dispread.frames.synthetic_source import render_display
from dispread.layout import DisplayLayout
from dispread.track import QuadTracker, TrackConfig


def _scene(shift_x=0, shift_y=0, angle=0.0):
    """Anzeige auf grosser Flaeche, optional verschoben und gedreht."""
    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")
    display, _, _ = render_display(12.34, layout, size=(240, 100))
    scene = np.full((400, 640, 3), 30, np.uint8)
    scene[150:250, 200:440] = display
    if shift_x or shift_y or angle:
        matrix = cv2.getRotationMatrix2D((320.0, 200.0), angle, 1.0)
        matrix[0, 2] += shift_x
        matrix[1, 2] += shift_y
        scene = cv2.warpAffine(scene, matrix, (640, 400), borderValue=(30, 30, 30))
    return scene


_QUAD = ((200.0, 150.0), (440.0, 150.0), (440.0, 250.0), (200.0, 250.0))


def test_unbewegte_szene_wird_nicht_verschoben():
    tracker = QuadTracker(_scene(), _QUAD)
    result = tracker.update(_scene())
    assert result.quad is not None
    assert result.shift < 0.01
    assert result.score > 0.9


def test_kleine_verschiebung_wird_nachgefuehrt():
    """Der korrigierte Ausschnitt muss der Anzeige folgen, nicht stehenbleiben."""
    tracker = QuadTracker(_scene(), _QUAD)
    result = tracker.update(_scene(shift_x=8, shift_y=-4))
    assert result.quad is not None, result.reason
    moved_x = result.quad[0][0] - _QUAD[0][0]
    moved_y = result.quad[0][1] - _QUAD[0][1]
    assert moved_x == pytest.approx(8, abs=2.0)
    assert moved_y == pytest.approx(-4, abs=2.0)


def test_zu_grosse_verschiebung_wird_abgelehnt_nicht_korrigiert():
    """Ausserhalb der Grenze: nicht korrigieren. Die Ablehnung ist die sichere Richtung."""
    tracker = QuadTracker(_scene(), _QUAD, config=TrackConfig(max_shift=0.05))
    result = tracker.update(_scene(shift_x=90))
    assert result.quad is None
    assert result.reason == "shift_out_of_bounds"


def test_zu_grosse_drehung_wird_abgelehnt():
    tracker = QuadTracker(_scene(), _QUAD, config=TrackConfig(max_rotation_deg=2.0))
    result = tracker.update(_scene(angle=8.0))
    assert result.quad is None
    assert result.reason in ("rotation_out_of_bounds", "low_score", "ecc_diverged")


def test_voellig_anderes_bild_wird_abgelehnt():
    """Wird die Anzeige verdeckt, darf keine Geometrie 'gefunden' werden."""
    tracker = QuadTracker(_scene(), _QUAD)
    result = tracker.update(np.full((400, 640, 3), 200, np.uint8))
    assert result.quad is None


def test_nachfuehrung_haeuft_keine_drift_an():
    """Immer gegen die Referenz der Bestaetigung, nie gegen das vorige Bild."""
    tracker = QuadTracker(_scene(), _QUAD)
    for _ in range(20):
        tracker.update(_scene(shift_x=5))
    result = tracker.update(_scene())          # zurueck an den Ausgangsort
    assert result.quad is not None
    assert abs(result.quad[0][0] - _QUAD[0][0]) < 2.0
