"""Startsuche auf den gespeicherten Standbildern der Aufstellungen sc7/sc7a."""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest
from devdata_helpers import local_recording

from dispread.dotlattice import LatticeFit, fit_lattice
from dispread.setup_hint import find_green_hint_box

EMPTY_CELLS = (8, 13, 14, 15)


@pytest.mark.parametrize("name", ("sc7", "sc7a"))
def test_saved_close_still_finds_start_lattice(name: str):
    still = local_recording(f"diagnostics/{name}-assist/still.png")

    image = cv2.imread(str(still))
    hint = find_green_hint_box(image)
    assert hint is not None
    result = fit_lattice(image, hint, empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result

    if name == "sc7a":
        reference_path = local_recording("diagnostics/sc7a-quad.json")

        reference = np.asarray(json.loads(reference_path.read_text()), dtype=np.float32)
        assert np.max(np.linalg.norm(np.asarray(result.quad) - reference, axis=1)) < 10
