"""OQ-70: dunkler Rahmen mit Lichtkerbe statt Rueckfall auf das feste Band.

Bei `live-20261111T155557Z` beleuchtet das Raumlicht die untere rechte Fase.
Sie faellt aus der dunklen Rahmenkomponente heraus, die Soliditaet sinkt auf
0,9605 < 0,97, und der Vorschlag fiel auf das feste Band zurueck. Das ist bei
diesem kleinen Quad links zu schmal, um die Fase zu erreichen: nur 2 Bereiche
auf der -x-Seite, keine Reserve.

Die Soliditaetsgrenze bleibt. Unterschreitet eine Komponente sie, wird die
Rahmenkontur je Seite robust aus Strahlen gemessen. Die Komponente zaehlt nur
dann als Rahmen, wenn ausserhalb dieser Kontur nichts liegt, das ein
Suchfenster tragen kann (Balken, Kabel, Schatten). Die Kerbe selbst bleibt
ausserhalb des Bandes.

Echte Bilder: `$DISPREAD_DEV_DATA/regression/2026-11-11/<sitzung>/` mit
`still.png`, `stability.png` (gespeichertes Zweitmittelbild) und
`proposal.json` (gespeichertes Quad). Ohne SSD werden sie uebersprungen.
"""

import json
import os
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.live import frame_tracking as ft
from dispread.live.frame_tracking import FrameTrackingConfig, propose_regions

# Mindestzahl je Achsenseite samt Reserve (min_inliers_per_side + reserve_regions).
REQUIRED = FrameTrackingConfig().min_inliers_per_side + FrameTrackingConfig().reserve_regions


def _scene(*, notch=False, bar=False):
    """Rahmen mit Struktur, helles LCD; optional Lichtkerbe oder anliegender Balken."""
    image = np.full((800, 1100), 210, np.uint8)
    cv2.rectangle(image, (230, 205), (870, 555), 35, -1)
    cv2.rectangle(image, (330, 320), (770, 440), 180, -1)
    rng = np.random.default_rng(70)
    for x in range(250, 860, 45):
        for y in range(225, 545, 45):
            if 300 < x < 800 and 300 < y < 460:
                continue
            cv2.rectangle(image, (x, y), (x+8, y+8), int(rng.integers(55, 80)), -1)
    if notch:
        # Beleuchtete untere rechte Fase: heller als die Bandschwelle.
        cv2.fillConvexPoly(image, np.array([[520, 495], [870, 495], [870, 555], [520, 555]]), 140)
    if bar:
        # Strukturierter dunkler Balken, liegt aussen am ungekerbten Rahmenteil an
        # (wie der R13-11-Review-Balken, hier schraeg nach links unten).
        cv2.line(image, (400, 580), (100, 680), 35, 60)
        for t in np.linspace(0.3, 1.0, 6):
            cx, cy = int(400 - t*300), int(580 + t*100)
            cv2.rectangle(image, (cx-3, cy-3), (cx+3, cy+3), 90, -1)
    quad = np.array([[360, 345], [740, 345], [740, 415], [360, 415]], float)
    return image, quad


def test_kerbe_senkt_soliditaet_und_faellt_bisher_zurueck():
    image, quad = _scene(notch=True)
    strict = replace(FrameTrackingConfig(), bezel_notch_quantile=0.5)
    _, _, _, metrics, _ = ft._geometry(image, quad, FrameTrackingConfig())
    assert metrics["band_soliditaet"] < FrameTrackingConfig().bezel_min_solidity
    # Median-Kontur: die Kerbe belegt mehr als die Haelfte der unteren Seite,
    # der Rest des Rahmens ragt ueber die Kontur hinaus -> Rueckfall bleibt.
    _, _, _, median_metrics, _ = ft._geometry(image, quad, strict)
    assert median_metrics["band_quelle"] == "festes_band"
    assert median_metrics["band_rueckfallgrund"] == "rahmenform_unplausibel"


def test_kerbe_nutzt_dunklen_rahmen_ohne_kerbe():
    image, quad = _scene(notch=True)
    _, _, mask, metrics, fixed = ft._geometry(image, quad, FrameTrackingConfig())
    assert metrics["band_quelle"] == "dunkler_rahmen"
    assert metrics["band_rueckfallgrund"] is None
    assert metrics["band_soliditaet"] < FrameTrackingConfig().bezel_min_solidity
    assert set(metrics["band_kerbe_kontur_px"]) == {"oben", "rechts", "unten", "links"}
    # Kein Suchfenster auf der beleuchteten Fase.
    assert not mask[500:555, 560:870].any()
    assert (mask & ~fixed).any()
    proposal = propose_regions(image, quad)
    assert proposal.ok, (proposal.reasons, proposal.metrics["regions_per_axis_side"])
    assert all(not (495 <= y <= 555 and x >= 520) for x, y in (r.centre for r in proposal.regions))


def test_ohne_kerbe_unveraendert():
    image, quad = _scene()
    _, _, _, metrics, _ = ft._geometry(image, quad, FrameTrackingConfig())
    assert metrics["band_quelle"] == "dunkler_rahmen"
    assert metrics["band_soliditaet"] >= FrameTrackingConfig().bezel_min_solidity
    assert "band_kerbe_kontur_px" not in metrics


@pytest.mark.parametrize("notch", [False, True])
def test_anliegender_balken_bleibt_rahmenform_unplausibel(notch):
    image, quad = _scene(notch=notch, bar=True)
    _, _, mask, metrics, fixed = ft._geometry(image, quad, FrameTrackingConfig())
    assert metrics["band_quelle"] == "festes_band"
    assert metrics["band_rueckfallgrund"] == "rahmenform_unplausibel"
    assert metrics["band_soliditaet"] < FrameTrackingConfig().bezel_min_solidity
    np.testing.assert_array_equal(mask, fixed)


def test_kerbenquantil_ist_reine_einrichtungsgrenze():
    from dispread.live.session import _run_start_tracking_config

    config = FrameTrackingConfig()
    assert config.bezel_notch_quantile == 0.75
    for value in (0.49, 1.0, float("nan")):
        with pytest.raises(ValueError):
            FrameTrackingConfig(bezel_notch_quantile=value)
    old = {key: value for key, value in config.to_dict().items() if key != "bezel_notch_quantile"}
    assert FrameTrackingConfig.from_dict(old) == config
    changed = replace(config, bezel_notch_quantile=0.9).to_dict()
    assert _run_start_tracking_config(changed) == _run_start_tracking_config(config.to_dict())


# Echte Aufstellungen 2026-11-11: OQ-70-Fall und die neun positiven Aufstellungen.
POSITIVE = ("095426Z", "103604Z", "111008Z", "122753Z", "124851Z",
            "164508Z", "165234Z", "165754Z")


def _case(session):
    root = os.environ.get("DISPREAD_DEV_DATA")
    folder = Path(root or "/nonexistent") / "regression" / "2026-11-11" / f"live-20261111T{session}"
    if not root or not all((folder / name).is_file() for name in ("still.png", "stability.png", "proposal.json")):
        pytest.skip(f"Regressionsdaten fehlen: {folder} (DISPREAD_DEV_DATA setzen)")
    still = cv2.imread(str(folder / "still.png"))
    stability = cv2.imread(str(folder / "stability.png"))
    quad = json.loads((folder / "proposal.json").read_text())["quad"]
    return still, stability, quad


def _judge(session):
    still, stability, quad = _case(session)
    proposal = propose_regions(still, quad, stability_image=stability)
    # Nur ein gespeichertes Zweitmittelbild statt acht Einzelbildern: Artefakt der Nachrechnung.
    reasons = [reason for reason in proposal.reasons if reason != "rahmenbereiche_einzelbilder_fehlen"]
    return proposal, reasons


def test_155557z_vorschlag_verteilt_mit_reserve():
    proposal, reasons = _judge("155557Z")
    sides = proposal.metrics["regions_per_axis_side"]
    assert reasons == [], (reasons, sides)
    assert proposal.metrics["band_quelle"] == "dunkler_rahmen"
    assert proposal.metrics["reserve_ok"]
    assert min(min(side) for side in sides) >= REQUIRED, sides


@pytest.mark.parametrize("session", POSITIVE)
def test_positive_aufstellungen_bleiben_verteilt(session):
    proposal, reasons = _judge(session)
    sides = proposal.metrics["regions_per_axis_side"]
    assert reasons == [], (reasons, sides)
    assert proposal.metrics["reserve_ok"]
    assert min(min(side) for side in sides) >= REQUIRED, sides
