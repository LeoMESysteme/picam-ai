import numpy as np
import pytest
from dotmatrix_helpers import GRID, render

from dispread.layout import CharLayout
from dispread.ocr import ValueReader
from dispread.ocr.dotmatrix import DotMatrixReader, parse_gsv2as
from dispread.ocr.dotmatrix_font import CLASSES
from dispread.ocr.dotmatrix_sampling import normalized, sample_image
from dispread.ocr.dotmatrix_templates import build_templates

LAYOUT = CharLayout(grid=GRID, unit="mV/V")
TRAIN_TEXTS = ["+0.60972 ", "+ 1.2345 ", "+ 67.890 ", "+  988.5 ", "+ 3456.7 ", "+0.11111 "]


@pytest.fixture(scope="module")
def reader():
    rng = np.random.default_rng(7)
    samples = {c: [] for c in CLASSES}
    for text in TRAIN_TEXTS * 6:
        img = render(text, blur=rng.uniform(0.3, 1.0))
        img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
        n = normalized(sample_image(img, GRID, range(9)))
        for i, ch in enumerate(text):
            samples[ch].append(n[i])
    return DotMatrixReader(build_templates(samples, ("synthetisch",)))


@pytest.mark.parametrize("cells,expected", [
    ("+0.60972 ", ("+0.60972", 0.60972)),
    ("+ 909.09 ", ("+909.09", 909.09)),
    ("+  988.5 ", ("+988.5", 988.5)),
])
def test_parse_ok(cells, expected):
    assert parse_gsv2as(cells) == expected


@pytest.mark.parametrize("cells", [
    "+   88.5 ",   # drei Leerzellen
    "+0.6.972 ",   # zwei Punkte
    "+0 60972 ",   # Leerzelle mitten in der Zahl
    "+06097211",   # kein Punkt, Zelle 8 nicht leer
    "+ 12.34  ",   # nur 5 Ziffern
    " 0.60972 ",   # kein Vorzeichen
    "+ .12345 ",   # Leerzelle direkt vor dem Punkt
])
def test_parse_rejects(cells):
    assert parse_gsv2as(cells) is None


def test_is_value_reader(reader):
    assert isinstance(reader, ValueReader)
    assert reader.backend_id == "dotmatrix"
    assert reader.declares_confidence_calibrated is False


@pytest.mark.parametrize("text,value", [("+ 1.2345 ", 1.2345), ("+  988.5 ", 988.5)])
def test_reads_value(reader, text, value):
    r = reader.read(render(text), LAYOUT)
    assert r.value == value and r.unit_text == "mV/V"
    assert r.sign_region_readable and not r.sign_detected
    assert r.decimal_point_detected and r.diagnostics["reject_reason"] is None


def test_grayscale_and_color_same(reader):
    g = render("+ 67.890 ")
    c = np.dstack([g, g, g])
    assert reader.read(g, LAYOUT).value == reader.read(c, LAYOUT).value == 67.89


def test_minus_is_rejected(reader):
    r = reader.read(render("- 1.2345 "), LAYOUT)
    assert r.value is None and not r.sign_region_readable
    assert r.diagnostics["reject_reason"] in ("vorzeichen", "zelle_unbekannt")


def test_blank_display_rejected_as_contrast(reader):
    r = reader.read(np.full((160, 400), 190, np.uint8), LAYOUT)
    assert r.value is None and r.diagnostics["reject_reason"] == "kontrast"


def test_saturated_rejected(reader):
    img = render("+ 1.2345 ")
    img[40:120, 10:200] = 255
    r = reader.read(img, LAYOUT)
    assert r.value is None and r.diagnostics["reject_reason"] == "ueberbelichtet"


def test_unknown_glyph_rejected(reader):
    r = reader.read(render("+ 1.2°45 "), LAYOUT)
    assert r.value is None
    assert r.diagnostics["reject_reason"] in ("zelle_unbekannt", "zelle_mehrdeutig")
