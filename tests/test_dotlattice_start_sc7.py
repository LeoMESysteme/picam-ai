"""Startsuche auf den gespeicherten Standbildern der Aufstellungen sc7/sc7a."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.dotlattice import LatticeFit, fit_lattice
from dispread.setup_hint import find_green_hint_box

DIAGNOSTICS = Path(__file__).resolve().parents[1] / "var/diagnostics"
EMPTY_CELLS = (8, 13, 14, 15)


@pytest.mark.parametrize("name", ("sc7", "sc7a"))
def test_saved_close_still_finds_start_lattice(name: str):
    still = DIAGNOSTICS / f"{name}-assist/still.png"
    if not still.exists():
        pytest.skip("Gespeichertes Standbild fehlt")

    image = cv2.imread(str(still))
    hint = find_green_hint_box(image)
    assert hint is not None
    result = fit_lattice(image, hint, empty_cells=EMPTY_CELLS)
    assert isinstance(result, LatticeFit), result

    if name == "sc7a":
        reference_path = DIAGNOSTICS / "sc7a-quad.json"
        if not reference_path.exists():
            pytest.skip("Unabhaengig geprueftes Quad fehlt")
        reference = np.asarray(json.loads(reference_path.read_text()), dtype=np.float32)
        assert np.max(np.linalg.norm(np.asarray(result.quad) - reference, axis=1)) < 10
