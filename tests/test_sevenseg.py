"""7-Segment-Auswertung: erkennen, was lesbar ist - und ablehnen, was nicht."""

from __future__ import annotations

import pytest

from dispread.frames import open_source
from dispread.frames.synthetic_source import render_display
from dispread.layout import DIGIT_SEGMENTS, DisplayLayout
from dispread.ocr.sevenseg import SevenSegmentReader, segment_threshold


@pytest.fixture
def layout() -> DisplayLayout:
    return DisplayLayout(digits=5, decimals=2, unit="N")


@pytest.fixture
def reader() -> SevenSegmentReader:
    return SevenSegmentReader()


def _read(value, layout, reader, **kw):
    img, _, area = render_display(value, layout, **kw)
    x, y, w, h = area
    return reader.read(img[y : y + h, x : x + w], layout)


@pytest.mark.parametrize("value", [0.0, 1.11, 12.34, -5.67, 88.88, -99.99, 10.08, 60.06])
def test_ziffern_werden_korrekt_gelesen(value, layout, reader):
    """Alle Ziffern, inklusive der 8 mit sieben aktiven Segmenten."""
    result = _read(value, layout, reader)
    assert result.value == value, f"gelesen {result.raw_text!r}"


def test_acht_wird_gelesen_obwohl_alle_segmente_aktiv_sind(layout, reader):
    """Regression: eine zellinterne Schwelle wuerde die 8 verwerfen.

    Bei "8" sind alle sieben Segmente aktiv, der zellinterne Kontrast ist also
    null. Die Schwelle muss aus den gepoolten Segmentmessungen aller Stellen
    kommen, sonst wird die Zelle faelschlich als unlesbar abgelehnt.
    """
    result = _read(88.88, layout, reader)
    assert result.value == 88.88
    assert result.diagnostics["unreadable_cells"] == 0


def test_vorzeichen_wird_getrennt_gefuehrt(layout, reader):
    minus = _read(-1.23, layout, reader)
    plus = _read(1.23, layout, reader)
    assert minus.sign_detected and minus.sign_region_readable
    assert not plus.sign_detected and plus.sign_region_readable


def test_ueberlauf_ist_ein_zustand_kein_wert(layout, reader):
    """Konzept.md §7 verlangt, Ueberlauf als Betriebszustand zu erkennen."""
    result = _read(0.0, layout, reader, overflow=True)
    assert "overflow" in result.status_flags
    assert result.value is None


def test_segmentausfall_wird_abgelehnt_nicht_geraten(layout, reader):
    """Ein unbekanntes Segmentmuster darf keine Ziffer werden.

    Konzept.md §7: unlesbare Eingaben muessen explizit abgelehnt werden. Die
    naheliegenden Kandidaten werden als Evidenz festgehalten.
    """
    result = _read(-12.50, layout, reader, dropout_segments={(2, "b")})
    assert result.value is None
    broken = [g for g in result.glyphs if g.text == "?"]
    assert broken, "der Ausfall haette auffallen muessen"
    assert broken[0].ambiguous_with, "Kandidaten sollten festgehalten werden"


def test_starke_unschaerfe_erzeugt_keine_stillen_fehlablesungen(layout, reader):
    """Der gefaehrliche Fall ist nicht Ablehnung, sondern falsche Freigabe."""
    src = open_source("synthetic://seven-seg?count=30&blur=10")
    src.open()
    wrong = 0
    for frame in src.frames():
        truth = frame.raw_metadata["ground_truth"]["value"]
        x, y, w, h = frame.raw_metadata["digit_area"]
        result = reader.read(frame.image[y : y + h, x : x + w], src.layout)
        if result.value is not None and result.value != truth:
            wrong += 1
    assert wrong == 0, f"{wrong} stille Fehlablesungen bei starker Unschaerfe"


def test_konfidenz_ist_nicht_als_kalibriert_deklariert(reader):
    """Konzept.md §7: Konfidenz ist keine Fehlerwahrscheinlichkeit.

    Solange keine Kalibriermessung in docs/VALIDATION.md steht, muss dieses
    Flag False bleiben.
    """
    assert reader.declares_confidence_calibrated is False


def test_segmentschwelle_bei_zu_wenig_daten():
    threshold, contrast = segment_threshold([0.5])
    assert contrast == 0.0
    assert 0.0 <= threshold <= 1.0


def test_segmenttabelle_ist_eindeutig():
    """Keine zwei Ziffern duerfen dasselbe Segmentmuster haben."""
    patterns = list(DIGIT_SEGMENTS.values())
    assert len(patterns) == len(set(patterns))
