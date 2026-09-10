"""Regression des Live-Messpfads gegen real annotierte Aufnahmen.

Anders als `test_workbench.py`s `fit_ocr_box*`-Tests (die nur die
Box-*Vorschlaege* aus `vision.py` pruefen) laeuft dieser Test den
tatsaechlichen Werte-Lesepfad: `rectify()` -> `crop_box()` ->
`SevenSegmentReader.read()`, bitgenau wie `Controller._read`.

Sammelt seine Eingaben automatisch aus `var/workbench/annotations/` ein -
jede im `annotate`-Modus mit getipptem `ground_truth_text` gespeicherte
Aufnahme nimmt automatisch an dieser Pruefung teil, ohne dass diese Datei
angefasst werden muss (PLANNED_FEATURES.md: "neue annotationen sollen
automatisch in den live messpfad aufgenommen werden").
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import cv2
import pytest

from dispread.layout import DisplayLayout
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.rectify import rectify
from dispread.workbench.controller import CROP_SIZE, crop_box

_ANNOTATIONS_ROOT = Path("var/workbench/annotations")

_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _parse_ground_truth_value(text: str) -> float | None:
    """Getippten Zielwert in eine Vergleichszahl uebersetzen.

    `ground_truth_text` ist frei formatiert (Komma- oder Punkt-Dezimaltrenner,
    optionale Einheit/Leerzeichen drumherum - siehe
    `test_ground_truth_text_is_stored_with_the_annotation` in
    `test_workbench.py`, Beispiel `" -012.34 mV "`). `None`, wenn sich keine
    Zahl herausloesen laesst - dann wird nur diese eine Annotation
    uebersprungen, nicht der ganze Lauf abgebrochen.
    """
    match = _NUMBER.search(text)
    if match is None:
        return None
    return float(match.group(0).replace(",", "."))


def _annotation_has_ground_truth(data: dict) -> bool:
    """Genug fuer eine Live-Messpfad-Pruefung: Geometrie, Layout UND ein
    tatsaechlich als Zahl lesbarer getippter Zielwert."""
    if not ("roi_quad" in data and "ocr_box" in data and data.get("profile", {}).get("layout") is not None):
        return False
    text = data.get("ground_truth_text")
    return bool(text) and _parse_ground_truth_value(text) is not None


def _discover_ground_truth_annotations(base: Path = _ANNOTATIONS_ROOT) -> list[Path]:
    """Alle Annotationsordner unter `base` mit auswertbarer Ground Truth -
    automatisch statt einer festen Pfadliste, die bei jeder neuen Aufnahme von
    Hand nachgezogen werden muesste. `var/` ist nicht versioniert, deshalb
    leere Liste statt Fehler, wenn `base` fehlt."""
    if not base.exists():
        return []
    return sorted(
        p.parent
        for p in base.glob("*/annotation.json")
        if _annotation_has_ground_truth(json.loads(p.read_text()))
    )


#: Bekannt falsch lesende Aufnahmen (OQ-23: gepoolter Schwellwert scheitert an
#: einer insgesamt dunkleren Ziffernstelle), mit Grund fuer `xfail`. Wird eine
#: dieser IDs hier je entfernt, MUSS das eine echte, validierte Behebung sein
#: - kein stilles Weichspuelen einer neu auftretenden Regression.
_KNOWN_MISREADS = {
    "8a18ee05e31241b9b6702c5bb904ec97": (
        "OQ-23: gepoolter globaler Schwellwert liest '11.00' als '110?' - "
        "die zweite Stelle liegt unter der von den helleren Stellen "
        "dominierten Schwelle. Ground-Truth-Text nachtraeglich 2026-09-10 "
        "ergaenzt (visuell aus image.png bestaetigt), siehe annotation.json "
        "'ground_truth_text_note' und docs/VALIDATION.md."
    ),
}

_GROUND_TRUTH_ANNOTATIONS = _discover_ground_truth_annotations()
_GROUND_TRUTH_PARAMS = (
    [
        pytest.param(
            p,
            id=p.name,
            marks=(
                [pytest.mark.xfail(strict=True, reason=_KNOWN_MISREADS[p.name])]
                if p.name in _KNOWN_MISREADS
                else []
            ),
        )
        for p in _GROUND_TRUTH_ANNOTATIONS
    ]
    if _GROUND_TRUTH_ANNOTATIONS
    else [
        pytest.param(
            None,
            id="keine-annotationen",
            marks=pytest.mark.skip(
                reason="reale Annotationen mit ground_truth_text nicht im Checkout "
                "vorhanden (var/ ist nicht versioniert)"
            ),
        )
    ]
)


@pytest.mark.parametrize("folder", _GROUND_TRUTH_PARAMS)
def test_sevenseg_reads_the_annotated_ground_truth(folder):
    """Live-Messpfad gegen jede reale Annotation mit getipptem Zielwert.

    Waechst automatisch mit jeder neuen `annotate`-Aufnahme mit - keine
    Codeaenderung noetig, wenn im Labor eine weitere Aufnahme mit
    Ground-Truth-Text gespeichert wird.

    Stand 2026-09-10, spaeter Nachtrag: Die aus OQ-23 bekannten Aufnahmen
    (`6ffc561b...`, `8a18ee05...`) hatten urspruenglich kein
    `ground_truth_text` - dieser Test haette sie deshalb gar nicht erfasst,
    obwohl sie der dokumentierte Bugbeleg sind. Nachtraeglich ergaenzt
    (visuell aus `image.png` bestaetigt: beide zeigen "11.00", siehe
    `annotation.json`s `ground_truth_text_note`). Gegen die aktuell
    gespeicherte Geometrie liest `6ffc561b...` inzwischen korrekt (die
    ROI-/Rasterkalibrierung wurde nach der urspruenglichen OQ-23-Messung
    mehrfach nachgezogen, siehe deren Update-Historie); `8a18ee05...`
    reproduziert den gepoolten-Schwellwert-Fehler weiterhin exakt ("110?")
    und ist deshalb per `_KNOWN_MISREADS` als `xfail(strict=True)` markiert,
    nicht stillschweigend uebersprungen. Ein kuenftiger `sevenseg.py`-Fix muss
    diesen xfail-Eintrag bewusst entfernen, sobald er hier tatsaechlich
    validiert grün wird - `strict=True` laesst die Suite sonst rot werden,
    falls er unbeabsichtigt gruen faellt.
    """
    annotation = json.loads((folder / "annotation.json").read_text())
    expected = _parse_ground_truth_value(annotation["ground_truth_text"])
    image = cv2.imread(str(folder / "image.png"))
    height, width = image.shape[:2]
    quad_px = [(x * width, y * height) for x, y in annotation["roi_quad"]]
    layout = DisplayLayout.from_dict(annotation["profile"]["layout"])
    crop = rectify(image, quad_px, target_size=CROP_SIZE)
    reader_crop = crop_box(crop.image, annotation["ocr_box"])

    result = SevenSegmentReader().read(reader_crop, layout)

    assert result.value is not None, (
        f"kein Zahlenwert gelesen (raw_text={result.raw_text!r}, diagnostics={result.diagnostics})"
    )
    tolerance = 0.5 * 10 ** -(layout.decimals if layout.decimals is not None else 0)
    assert result.value == pytest.approx(expected, abs=tolerance), (
        f"erwartet {expected}, gelesen {result.value} "
        f"(raw_text={result.raw_text!r}, diagnostics={result.diagnostics})"
    )
