"""OQ-74: Fokus-ROI auf echten Einrichtungsbildern vom 2026-11-11.

PNG-Originale aus den Belegpaketen liegen unter
`$DISPREAD_DEV_DATA/regression/2026-11-11/<sitzung>/still.png` (SSD, nicht im
Repo). Ohne `DISPREAD_DEV_DATA` werden die Tests uebersprungen.

Die alte Fokus-ROI war fest das mittlere Bilddrittel. Bei `162902Z` lag die
LCD-Hinweisbox zu 0 % darin, bei den uebrigen Faellen zu 45-53 %. Die neue ROI
kommt aus der Hinweisbox und muss sie zu >= 90 % ueberdecken, auch auf einem
unscharfen Vorabbild (Gauss sigma 3 als Ersatz fuer einen Fehlfokus vor der
Suche). Das optische Verhalten des Fokusmotors ist hiermit nicht belegt.
"""

import os
from pathlib import Path

import cv2
import pytest

from dispread.live import setup as live_setup
from dispread.setup_hint import find_green_hint_box

# Sitzung -> Anteil der Hinweisbox im alten mittleren Drittel (Triage 2026-11-11).
CASES = {
    "live-20261111T162902Z": 0.00,
    "live-20261111T154403Z": 0.45,
    "live-20261111T124851Z": 0.45,
    "live-20261111T164508Z": 0.47,
    "live-20261111T161702Z": 0.47,
    "live-20261111T161955Z": 0.47,
    "live-20261111T170836Z": 0.53,
}


def _still(session: str):
    root = os.environ.get("DISPREAD_DEV_DATA")
    path = Path(root or "/nonexistent") / "regression" / "2026-11-11" / session / "still.png"
    if not root or not path.exists():
        pytest.skip(f"Regressionsbild fehlt: {path} (DISPREAD_DEV_DATA setzen)")
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    assert image is not None and image.shape == (1080, 1920, 3)
    return image


def _covered(outer, inner):
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    dx = max(0.0, min(ox + ow, ix + iw) - max(ox, ix))
    dy = max(0.0, min(oy + oh, iy + ih) - max(oy, iy))
    return dx * dy / (iw * ih)


def _pixels(box):
    return [box[0] * 1920, box[1] * 1080, box[2] * 1920, box[3] * 1080]


@pytest.mark.parametrize("session,old_share", sorted(CASES.items()))
@pytest.mark.parametrize("sigma", [0, 3])
def test_focus_roi_covers_lcd_hint_box(session, old_share, sigma):
    image = _still(session)
    hint = find_green_hint_box(image)
    assert hint is not None
    preview = image if sigma == 0 else cv2.GaussianBlur(image, (0, 0), sigma)
    focus_box = live_setup.focus_hint_box(preview)
    assert focus_box is not None, "Vorabsuche findet die LCD-Hinweisbox nicht"
    roi = live_setup.measurement_roi_pixels(live_setup.FOCUS_SOURCE_SIZE, focus_box)
    assert _covered(roi, _pixels(hint)) >= 0.90
    # Die Ausgangslage aus der Triage: das feste Drittel verfehlte die Anzeige.
    third = live_setup.measurement_roi_pixels(live_setup.FOCUS_SOURCE_SIZE, None)
    assert _covered(third, _pixels(hint)) == pytest.approx(old_share, abs=0.01)
    # Kleiner Rand: die ROI bleibt bei der Anzeige statt das halbe Bild zu messen.
    # 5 % je Seite ergeben 1,21 der Boxflaeche; Unschaerfe verbreitert die
    # Gruenkontur etwas (gemessen hoechstens 1,26 bei sigma 3).
    assert roi[2] * roi[3] <= 1.4 * _pixels(hint)[2] * _pixels(hint)[3]
