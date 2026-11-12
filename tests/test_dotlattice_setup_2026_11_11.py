"""Rasterstart auf den Einrichtungsbildern vom 2026-11-11 (OQ-69).

Die Originalbilder liegen unter `$DISPREAD_DEV_DATA/regression/2026-11-11/`
(PNG-Originale aus den Belegpaketen, Pruefsummen in `SHA256SUMS.oq69`).
Ohne Entwicklungsmedium werden die Tests uebersprungen.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.dotlattice import LatticeFit, fit_lattice
from dispread.setup_checks import diagnose_reader, raster_offset_check
from dispread.setup_hint import find_green_hint_box

EMPTY_CELLS = (8, 13, 14, 15)
TEMPLATES = Path(__file__).resolve().parents[1] / "var/dotmatrix/templates-stufe2c-2026-09-30.json"

# Bezugsquads: fuer bisher erfolgreiche Aufstellungen das Ergebnis vor dem
# Fix (Stand 070d69f), fuer die vier Fehlerfaelle das neue Ergebnis, das
# zusaetzlich per 2j und Gegenlesen gegen den seriellen Zellentext geprueft
# ist (siehe test_failure_stills_now_find_text_confirmed_lattice).
REFERENCE_QUADS = {
    "154403Z": [[280.4, 521.7], [939.6, 533.2], [936.4, 616.6], [273.8, 601.0]],
    "154459Z": [[599.1, 538.4], [1289.9, 596.9], [1284.3, 682.8], [588.9, 619.1]],
    "155404Z": [[599.3, 538.5], [1289.9, 596.9], [1284.6, 682.9], [588.9, 619.1]],
    "162902Z": [[642.1, 173.7], [1247.9, 185.0], [1250.0, 252.3], [639.0, 241.9]],
    "155557Z": [[682.7, 527.1], [1231.0, 519.4], [1239.2, 580.7], [680.5, 589.9]],
    "161702Z": [[557.9, 361.6], [1359.1, 360.6], [1358.5, 454.8], [560.0, 460.0]],
    "161955Z": [[557.9, 361.5], [1359.1, 360.6], [1358.6, 454.9], [559.9, 460.0]],
    "170836Z": [[319.6, 402.1], [1028.2, 406.0], [1025.9, 497.0], [317.6, 487.5]],
    "164508Z": [[603.7, 665.0], [1256.2, 663.5], [1261.4, 741.7], [599.6, 744.4]],
    "165234Z": [[859.2, 501.3], [1506.8, 503.3], [1512.0, 580.1], [861.2, 583.5]],
    "165754Z": [[846.5, 517.0], [1509.5, 525.0], [1510.7, 605.6], [846.4, 607.3]],
    "095426Z": [[486.9, 528.6], [1182.0, 531.6], [1185.1, 613.7], [483.0, 612.3]],
    "103604Z": [[487.0, 529.5], [1183.3, 532.4], [1186.3, 614.8], [482.9, 613.1]],
    "111008Z": [[487.0, 529.9], [1182.8, 532.9], [1185.9, 615.2], [482.8, 613.6]],
    "122753Z": [[487.2, 530.0], [1183.2, 532.9], [1186.3, 615.3], [482.8, 613.7]],
    "124851Z": [[280.3, 521.7], [939.6, 533.2], [936.3, 616.8], [273.7, 601.2]],
}
FAILURES = ("154403Z", "154459Z", "155404Z", "162902Z")
PREVIOUSLY_FITTED = tuple(name for name in REFERENCE_QUADS if name not in FAILURES)


def _case(name: str) -> Path:
    root = os.environ.get("DISPREAD_DEV_DATA")
    folder = Path(root or "/nonexistent") / "regression/2026-11-11" / f"live-20261111T{name}"
    if not (folder / "still.png").exists():
        pytest.skip(f"Regressionsbild fehlt: {folder} (DISPREAD_DEV_DATA setzen)")
    return folder


def _fit(folder: Path):
    image = cv2.imread(str(folder / "still.png"))
    assert image is not None
    hint = find_green_hint_box(image)
    assert hint is not None
    return image, fit_lattice(image, hint, empty_cells=EMPTY_CELLS)


def _corner_error(quad, reference) -> float:
    return float(np.max(np.linalg.norm(np.asarray(quad) - np.asarray(reference), axis=1)))


def _serial_text(folder: Path) -> str:
    """Zellentext des gespeicherten Standbilds (letzter Versuch, seriell)."""
    entries = [e for e in json.loads((folder / "cell-text.json").read_text()) if e.get("still") == "still"]
    return entries[-1]["masked"]


@pytest.mark.parametrize("name", FAILURES)
def test_failure_stills_now_find_text_confirmed_lattice(name):
    folder = _case(name)
    image, result = _fit(folder)
    assert isinstance(result, LatticeFit), result
    assert _corner_error(result.quad, REFERENCE_QUADS[name]) <= 1.5
    # Unabhaengig vom Rasterfit: ROM-Punktversatz gegen den seriellen Text.
    text = _serial_text(folder)
    assert "?" not in text
    offset = raster_offset_check([(image, text)], result.quad)
    assert offset.status == "OK", offset.metrics
    if TEMPLATES.exists():
        reader = diagnose_reader([(image, text)], result.quad, TEMPLATES,
                                 hashlib.sha256(TEMPLATES.read_bytes()).hexdigest())
        assert reader.metrics["contradictions"] == []


def test_ambiguous_pair_finds_lattice_of_same_setup():
    # 124851Z (bestaetigt) und 154403Z (bisher mehrdeutig) haben dieselbe
    # Aufstellung und pixelgleiche Hinweisbox. Beide Fits muessen deckungsgleich sein.
    _, confirmed = _fit(_case("124851Z"))
    _, previously_ambiguous = _fit(_case("154403Z"))
    assert isinstance(confirmed, LatticeFit), confirmed
    assert isinstance(previously_ambiguous, LatticeFit), previously_ambiguous
    assert _corner_error(previously_ambiguous.quad, confirmed.quad) <= 1.0


@pytest.mark.parametrize("name", PREVIOUSLY_FITTED)
def test_previously_fitted_stills_keep_lattice(name):
    folder = _case(name)
    image, result = _fit(folder)
    assert isinstance(result, LatticeFit), result
    assert _corner_error(result.quad, REFERENCE_QUADS[name]) <= 1.5
    assert raster_offset_check([(image, _serial_text(folder))], result.quad).status != "FEHLER"
