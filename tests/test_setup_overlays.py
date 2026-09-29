"""Bediener-Overlays des Einrichtungsassistenten."""

from types import SimpleNamespace

import numpy as np

from dispread.setup_overlays import draw_sampling_overlay, draw_source_overlay


def test_source_overlay_marks_quad_candidates_and_verdict():
    image = np.full((100, 200, 3), 80, dtype=np.uint8)
    fit = SimpleNamespace(
        quad=[[20, 20], [180, 20], [180, 80], [20, 80]],
        assigned_points=((60.0, 50.0),),
        rejected_points=((140.0, 50.0),),
    )
    overlay = draw_source_overlay(image, fit, "WARNUNG")
    assert overlay.shape == image.shape
    assert tuple(overlay[50, 60]) == (0, 255, 0)
    assert tuple(overlay[50, 140]) == (0, 0, 255)
    assert tuple(overlay[20, 100]) != (80, 80, 80)
    assert not np.array_equal(overlay, image)


def test_sampling_overlay_marks_text_cursor_and_edge_cell():
    image = np.full((160, 400, 3), 100, dtype=np.uint8)
    overlay = draw_sampling_overlay(image, edge_cells=(8,))
    assert overlay.shape == (640, 1600, 3)
    # Punktmitte Spalte 0, Zeile 0: (2.08, 26.67) bei Faktor 4.
    assert tuple(overlay[107, 8]) == (0, 0, 255)
    # Cursorzeile 7 unter den sieben Zeichenzeilen.
    assert tuple(overlay[604, 8]) == (255, 0, 0)
    # Zelle 8 hat einen sichtbaren Kantenbefund.
    assert tuple(overlay[80, 800]) != (100, 100, 100)
