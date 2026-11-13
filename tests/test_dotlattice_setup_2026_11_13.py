"""Regression of the boundary minima and independent bottom-edge failure."""
from pathlib import Path

import cv2
import numpy as np
import pytest
from devdata_helpers import local_recording

from dispread.dotlattice import LatticeFit, fit_lattice, refine
from dispread.setup_hint import find_green_hint_box


@pytest.mark.parametrize(("session", "still"), [
    ("121656", "still-versuch-1.png"),
    ("130253", "still-versuch-1.png"),
    ("130253", "still-versuch-2.png"),
])
def test_neighbor_edge_minima_do_not_occupy_empty_cell(session, still):
    path = local_recording(Path(f"live/live-20261113T{session}Z/setup") / still)
    image = cv2.imread(str(path))
    assert image is not None
    hint = find_green_hint_box(image)
    assert hint is not None
    fit = fit_lattice(image, hint, empty_cells=(8, 13, 14, 15))
    assert isinstance(fit, LatticeFit), fit
    # Same stationary setup, independently identified in the research notes.
    reference = np.array([[731.7, 364.4], [1400.5, 374.9],
                          [1405.4, 454.1], [733.2, 453.1]])
    assert np.max(np.linalg.norm(np.asarray(fit.quad) - reference, axis=1)) < 3


@pytest.mark.parametrize(("session", "still", "reference"), [
    ("130253", "still.png", [[731.7, 364.4], [1400.5, 374.9],
                              [1405.4, 454.1], [733.2, 453.1]]),
    ("115232", "still-versuch-1.png", [[732.4755, 364.6657], [1400.0222, 375.2388],
                                        [1403.7087, 454.1134], [734.1314, 452.8929]]),
])
def test_wrong_bottom_edge_does_not_block_start(session, still, reference):
    path = local_recording(Path(f"live/live-20261113T{session}Z/setup") / still)
    image = cv2.imread(str(path))
    assert image is not None
    hint = find_green_hint_box(image)
    assert hint is not None
    fit = fit_lattice(image, hint, empty_cells=(8, 13, 14, 15))
    assert isinstance(fit, LatticeFit), fit
    # Comparison from another image of the same setup; movement is possible.
    assert np.max(np.linalg.norm(np.asarray(fit.quad) - reference, axis=1)) < 3


def test_115232_subsequent_image_can_seed_a_checked_fit():
    path = local_recording("live/live-20261113T115232Z/setup/still-versuch-1.png")
    image = cv2.imread(str(path))
    assert image is not None
    # Vergleichsquad aus dem spaeteren still.png; Bewegung zwischen Aufnahmen moeglich.
    comparison_quad = np.float32([[732.4755, 364.6657], [1400.0222, 375.2388],
                             [1403.7087, 454.1134], [734.1314, 452.8929]])
    target = np.float32([[0, 0], [399, 0], [399, 159], [0, 159]])
    fit = refine(image, cv2.getPerspectiveTransform(comparison_quad, target),
                 empty_cells=(8, 13, 14, 15))
    assert isinstance(fit, LatticeFit), fit
    assert np.max(np.linalg.norm(np.asarray(fit.quad) - comparison_quad, axis=1)) < 1

@pytest.mark.parametrize(("session", "reference"), [
    ("082712", [[731.3371, 453.0855], [1204.4663, 477.5379],
                [1205.5040, 540.3736], [734.0253, 531.9523]]),
    ("083418", [[731.5566, 452.9592], [1204.5266, 477.5099],
                [1205.8433, 540.5169], [734.0559, 531.9354]]),
])
def test_existing_october_bottom_edge_fit_is_preserved(session, reference):
    path = local_recording(f"live/live-20261026T{session}Z/setup/still.png")
    image = cv2.imread(str(path))
    assert image is not None
    hint = find_green_hint_box(image)
    assert hint is not None
    fit = fit_lattice(image, hint, empty_cells=(8, 13, 14, 15))
    assert isinstance(fit, LatticeFit), fit
    # Regression against the baseline fit, not an independently established truth.
    assert np.max(np.linalg.norm(np.asarray(fit.quad) - reference, axis=1)) < 1
