"""tesseract_cli: OCR-Backend fuer dot-matrix-/Zeichen-LCDs (kein 7-Segment).

Die Parser-/Ablehnungslogik wird deterministisch gegen einen gefakten
`_run_tesseract` getestet (siehe `test_parsing_*`), nicht gegen echte
Tesseract-Erkennungsguete - die haengt vom Bild ab und ist kein Verhalten
dieses Moduls. Die echten GSV-Sensor-Fotos pruefen stattdessen nur die
Sicherheitseigenschaft: nie ein falscher Wert, hoechstens eine Ablehnung
(siehe `test_reale_gsv_proben_liefern_nie_einen_falschen_wert` und Plan/Spec
- die Erkennungsguete auf dieser Schrift ist noch nicht zuverlaessig, das ist
ein dokumentierter Folgeaufwand, keine Regression dieses Tests).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.layout import DisplayLayout
from dispread.ocr import GlyphEvidence
from dispread.ocr.tesseract_cli import BACKEND_ID, TesseractReader

TESSERACT_MISSING = shutil.which("tesseract") is None

SAMPLES_ROOT = Path(__file__).resolve().parents[1] / "var" / "workbench" / "datasets" / "samples"
GSV_DEVICE_ID = "87564e345aa047338f954c045bc9df02"


def _gsv_samples() -> list[tuple[Path, dict]]:
    samples = []
    if not SAMPLES_ROOT.is_dir():
        return samples
    for sample_dir in sorted(SAMPLES_ROOT.glob("*")):
        manifest_path = sample_dir / "sample.json"
        if not manifest_path.is_file():
            continue
        data = json.loads(manifest_path.read_text())
        if data.get("device_id") == GSV_DEVICE_ID and data.get("label_state") == "readable":
            samples.append((sample_dir, data))
    return samples


def _crop_for(sample_dir: Path, data: dict) -> np.ndarray:
    image = cv2.imread(str(sample_dir / "image.png"))
    x, y, w, h = (int(v) for v in data["bbox"])
    return image[y : y + h, x : x + w]


# --- Parser-/Ablehnungslogik, deterministisch mit gefaktem Tesseract-Output -


def _layout(*, digits=6, decimals=5, has_sign=True, unit=None) -> DisplayLayout:
    return DisplayLayout(digits=digits, decimals=decimals, has_sign=has_sign, unit=unit, polarity="dark_on_bright")


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_korrekt_erkannter_text_ergibt_richtigen_wert(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "+"), (90.0, "1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value == pytest.approx(1.05)
    assert result.raw_text == "1.05000"
    assert result.sign_detected is False
    assert result.backend_id == BACKEND_ID
    assert len(result.glyphs) == 6
    assert all(isinstance(g, GlyphEvidence) for g in result.glyphs)


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_negatives_vorzeichen_wird_erkannt(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "-1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value == pytest.approx(-1.05)
    assert result.sign_detected is True


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_fehlendes_pflicht_vorzeichen_wird_abgelehnt_nicht_als_positiv_angenommen(monkeypatch):
    """Konzept.md §7: ein nicht auswertbarer Vorzeichenbereich darf nie zu
    'positiv' werden."""
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout(has_sign=True))

    assert result.value is None
    assert result.sign_region_readable is False


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_falsche_ziffernzahl_wird_abgelehnt_nicht_falsch_angenommen(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    # Layout erwartet 6 Ziffern, der (gefakte) erkannte Text hat nur 4.
    # Negative sign ensures we test that sign_detected is correctly preserved in rejection path.
    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "-1.05")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout(digits=6, decimals=5))

    assert result.value is None
    assert result.diagnostics.get("reject_reason") == "ziffernzahl_stimmt_nicht"
    # Bug fix: sign_detected and sign_region_readable must be preserved even in rejection paths
    assert result.sign_detected is True  # "-" was recognized
    assert result.sign_region_readable is True  # sign parsing succeeded


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_niedrige_konfidenz_wird_abgelehnt_trotz_passendem_muster(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    # Negative sign ensures we test that sign_detected is correctly preserved in rejection path.
    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(5.0, "-1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value is None
    assert result.diagnostics.get("reject_reason") == "konfidenz_zu_niedrig"
    # Bug fix: sign_detected and sign_region_readable must be preserved even in rejection paths
    assert result.sign_detected is True  # "-" was recognized
    assert result.sign_region_readable is True  # sign parsing succeeded


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_kein_erkannter_text_wird_abgelehnt(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value is None
    assert result.diagnostics.get("reject_reason") == "kein_text_erkannt"
    assert len(result.glyphs) == 6


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_ohne_vorzeichenpflicht_wird_reiner_zifferntext_gelesen(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "12.340")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout(digits=5, decimals=3, has_sign=False))

    assert result.value == pytest.approx(12.34)
    assert result.sign_region_readable is True


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_declares_confidence_calibrated_ist_false():
    reader = TesseractReader()
    assert reader.declares_confidence_calibrated is False
    assert reader.backend_id == BACKEND_ID


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_konstruktion_ohne_tesseract_binary_wirft(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="tesseract"):
        TesseractReader()


# --- _run_tesseract gegen den echten Subprozess (Rauchtest, kein Guete-Test) -


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_run_tesseract_liefert_liste_von_konfidenz_text_paaren():
    from dispread.ocr.tesseract_cli import _run_tesseract

    blank = np.full((160, 400), 255, np.uint8)
    words = _run_tesseract(blank, whitelist="0123456789.+- ")

    assert isinstance(words, list)
    assert all(isinstance(item, tuple) and len(item) == 2 for item in words)


# --- Sicherheitseigenschaft gegen echte GSV-Sensor-Fotos -------------------


#: Alle bekannten Ablehnungsgruende von TesseractReader.read() (siehe
#: tesseract_cli.py). Aktuell (2026-09-21) lehnen alle 11 echten GSV-Proben
#: ab, keine liefert einen Wert - deshalb prueft dieser Test zusaetzlich, dass
#: jede Ablehnung einen dieser bekannten Gruende hat. Ohne diese Pruefung
#: waere der Test vakuos: die value-is-not-None-Assertion unten wuerde nie
#: ausgefuehrt und ein kuenftiger stiller Bug, der aus einem ganz anderen,
#: unbekannten Grund `value=None` liefert, wuerde nicht auffallen.
_KNOWN_REJECT_REASONS = {
    "kein_text_erkannt",
    "vorzeichen_nicht_erkannt",
    "ziffernzahl_stimmt_nicht",
    "konfidenz_zu_niedrig",
}


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
@pytest.mark.skipif(not _gsv_samples(), reason="keine GSV-Sensor-Proben im Arbeitsbaum")
def test_reale_gsv_proben_liefern_nie_einen_falschen_wert():
    reader = TesseractReader()
    for sample_dir, data in _gsv_samples():
        layout = DisplayLayout(digits=6, decimals=5, has_sign=True, unit="mV/V", polarity="dark_on_bright")
        crop = _crop_for(sample_dir, data)

        result = reader.read(crop, layout)

        if result.value is not None:
            assert result.value == pytest.approx(float(data["expected_text"])), (
                f"{sample_dir.name}: gelesen {result.raw_text!r} -> {result.value}, "
                f"soll {data['expected_text']!r} - falsche Annahme, keine Ablehnung"
            )
        else:
            assert result.diagnostics.get("reject_reason") in _KNOWN_REJECT_REASONS, (
                f"{sample_dir.name}: unbekannter Ablehnungsgrund "
                f"{result.diagnostics.get('reject_reason')!r} - moeglicherweise ein neuer, "
                "unbeabsichtigter Fehlerpfad statt einer der bekannten Ablehnungen"
            )
