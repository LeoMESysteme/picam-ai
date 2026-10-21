import dataclasses
import time

import numpy as np
import pytest
from dotmatrix_helpers import GRID, render, synthetic_reader

from dispread.layout import CharLayout
from dispread.ocr import ValueReader
from dispread.ocr.dotmatrix import DotMatrixReader, parse_gsv2as

LAYOUT = CharLayout(grid=GRID, unit="mV/V")


@pytest.fixture(scope="module")
def reader():
    return synthetic_reader()


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


def test_from_file_requires_checksum(reader, tmp_path):
    from dispread.ocr.dotmatrix_templates import save_templates

    p = tmp_path / "templates.json"
    save_templates(reader._t, p)
    with pytest.raises(TypeError):
        DotMatrixReader.from_file(p)  # type: ignore[call-arg]


def test_unknown_glyph_rejected(reader):
    r = reader.read(render("+ 1.2°45 "), LAYOUT)
    assert r.value is None
    assert r.diagnostics["reject_reason"] in ("zelle_unbekannt", "zelle_mehrdeutig")


# --- "Rest leer" pruefen (Final-Fix 3) --------------------------------------
#
# GRID hat 16 Zellen; render() zeichnet nur so viele Zellen wie der Text lang
# ist. Ein 16-Zeichen-Text ohne Einheit (Zellen 9-12 als Leerzeichen, da 'm',
# 'V', '/' nicht im ROM-Test-Zeichensatz vorkommen) deckt Zellen 0-15 ab.


def test_blank_cells_13_to_15_do_not_change_value(reader):
    text = "+ 1.2345 " + " " * 7  # Zellen 9-12 (Einheit) + 13-15 (Rest), alle leer
    assert len(text) == 16
    r = reader.read(render(text), LAYOUT)
    assert r.value == 1.2345 and r.diagnostics["reject_reason"] is None
    assert r.diagnostics["blank_cells_ok"] is True


def test_character_in_cell_14_is_rejected_as_format(reader):
    chars = list("+ 1.2345 " + " " * 7)
    assert len(chars) == 16
    chars[14] = "0"  # Zeichen statt Leerzelle in Zelle 14 (Rest)
    text = "".join(chars)
    r = reader.read(render(text), LAYOUT)
    assert r.value is None and r.diagnostics["reject_reason"] == "format"
    assert r.diagnostics["blank_cells_ok"] is False


def test_unknown_format_id_raises(reader):
    other = CharLayout(grid=GRID, unit="mV/V", format_id="andere_version")
    with pytest.raises(ValueError, match="format_id"):
        reader.read(render("+ 1.2345 "), other)


# --- Sicherheitstest "richtig oder abgelehnt, nie falsch" (Final-Fix 4) -----


def test_trailing_dot_is_rejected():
    assert parse_gsv2as("+ 12345. ") is None


def _random_gsv2as_case(rng: np.random.Generator) -> tuple[str, str, float]:
    """Baut eine zufaellige gueltige gsv2as_v1-Zeichenkette (9 Zellen):
    Zelle 0 '+', 0-2 unterdrueckte fuehrende Nullen (Leerzellen), danach
    genau 6 Ziffern mit genau einem Punkt (nie am Anfang/Ende des Zahlkoerpers),
    Zelle 8 leer. Gibt (render-Text, erwarteter raw_text, erwarteter Wert) zurueck."""
    leading = int(rng.integers(0, 3))
    body_len = 7 - leading
    dot_pos = int(rng.integers(1, body_len - 1))  # nie an Position 0 oder am Ende
    digits = [str(int(d)) for d in rng.integers(0, 10, body_len - 1)]
    body = "".join(digits[:dot_pos] + ["."] + digits[dot_pos:])
    text = "+" + (" " * leading) + body + " "
    assert len(text) == 9
    return text, "+" + body, float(body)


def _sweep_never_wrong(reader, cases: int, seed: int) -> int:
    """Zufaellige gueltige gsv2as-Zeichenketten mit Stoerungen lesen; der Leser
    darf nur den wahren Wert oder gar keinen freigeben. Gibt die Zahl der
    freigegebenen Werte zurueck."""
    rng = np.random.default_rng(seed)
    n_released = 0
    for _ in range(cases):
        text, raw_expected, value_expected = _random_gsv2as_case(rng)
        dx = float(rng.uniform(-1.5, 1.5))
        dy = float(rng.uniform(-1.5, 1.5))
        blur = float(rng.uniform(0.0, 2.0))
        noise_sigma = float(rng.uniform(0.0, 12.0))
        gain_end = float(rng.uniform(0.6, 1.0))

        offset_grid = dataclasses.replace(GRID, left=GRID.left + dx, top=GRID.top + dy)
        img = render(text, grid=offset_grid, blur=blur).astype(np.float32)
        gain = np.linspace(1.0, gain_end, img.shape[1], dtype=np.float32)
        img = img * gain[None, :]
        img = img + rng.normal(0.0, noise_sigma, img.shape)
        img = np.clip(img, 0, 255).astype(np.uint8)

        r = reader.read(img, LAYOUT)
        assert r.value is None or r.value == value_expected, (
            f"falscher Wert freigegeben: erwartet {value_expected}, gelesen {r.value} "
            f"(text={text!r}, dx={dx}, dy={dy}, blur={blur}, noise={noise_sigma}, gain_end={gain_end})"
        )
        if r.value is not None:
            n_released += 1
            assert r.raw_text == raw_expected
    return n_released


def test_sweep_richtig_oder_abgelehnt_nie_falsch(reader):
    """300 zufaellige gueltige gsv2as-Zeichenketten, gerendert mit
    Rasterversatz +-1.5 px, Unschaerfe 0-2, Rauschen sigma<=12 und
    multiplikativem Helligkeitsverlauf bis 0.6: der Leser darf nie einen
    falschen Wert freigeben - nur den wahren Wert oder gar keinen (Final-Fix
    4, Konzept.md §7)."""
    start = time.monotonic()
    n_released = _sweep_never_wrong(reader, 300, 20260924)
    assert time.monotonic() - start < 30.0
    assert n_released > 0  # Test waere sonst leer bewiesen


def test_sweep_mit_hoechster_toleranz_nie_falsch(reader):
    """Angepasste Lesetoleranz (L3): auch bei d_max x 2,0, der hoechsten
    erlaubten Lockerung, gibt der Leser unter denselben Stoerungen nie einen
    falschen Wert frei; margin_min bleibt die Sperre gegen Verwechslungen."""
    from dispread.ocr.dotmatrix import DotMatrixReader

    loose = DotMatrixReader(reader._t, d_max_factor=2.0)
    strict_released = _sweep_never_wrong(reader, 150, 20261021)
    loose_released = _sweep_never_wrong(loose, 150, 20261021)
    assert loose_released >= strict_released > 0


def test_cell_diagnostics_expose_decision_and_blank_check_on_rejection(reader):
    r = reader.read(render("+ 1.2°45 "), LAYOUT)
    cells = r.diagnostics["cells"]
    assert cells[0]["text"] == "+" and cells[0]["reason"] is None
    assert cells[5]["text"] is None
    assert cells[5]["reason"] in ("zelle_unbekannt", "zelle_mehrdeutig")
    assert r.diagnostics["blank_cells_ok"] is True


@pytest.mark.parametrize('factor', [0.99, 2.01, float('nan'), float('inf')])
def test_tolerance_factor_rejects_invalid_values(reader, factor):
    with pytest.raises(ValueError, match='d_max_factor'):
        DotMatrixReader(reader._t, d_max_factor=factor)


def test_tolerance_default_preserves_decisions_and_margin_rule(reader, tmp_path):
    from dispread.ocr.dotmatrix_templates import classify, save_templates

    crop = render('+ 1.2345 ')
    strict = reader.read(crop, LAYOUT)
    explicit = DotMatrixReader(reader._t, d_max_factor=1.0).read(crop, LAYOUT)
    assert strict == explicit
    path = tmp_path / 'templates.json'
    sha = save_templates(reader._t, path)
    adaptive = DotMatrixReader.from_file(path, sha, d_max_factor=1.5)
    diag = adaptive.read(crop, LAYOUT).diagnostics
    assert diag['d_max'] == reader._t.d_max * 1.5
    assert diag['d_max_factor'] == 1.5
    # Gleiche Kandidaten bleiben mehrdeutig, auch mit erweitertem Abstand.
    t = dataclasses.replace(reader._t, mean={'0': reader._t.mean['0'], '1': reader._t.mean['0']},
                            std={'0': reader._t.std['0'], '1': reader._t.std['0']})
    vectors = np.tile(t.mean['0'], (9, 1))
    assert classify(vectors, t, d_max_factor=2).reason == 'zelle_mehrdeutig'


def test_tolerance_recovers_distance_reject_without_changing_candidate(reader):
    crop = render('+ 1.2345 ')
    observed = reader.read(crop, LAYOUT)
    max_distance = max(cell['d_best'] for cell in observed.diagnostics['cells'])
    templates = dataclasses.replace(reader._t, d_max=max_distance / 1.4)
    strict = DotMatrixReader(templates).read(crop, LAYOUT)
    adaptive = DotMatrixReader(templates, d_max_factor=1.5).read(crop, LAYOUT)
    assert strict.diagnostics['reject_reason'] == 'zelle_unbekannt'
    assert adaptive.value == 1.2345
    assert [cell['best'] for cell in strict.diagnostics['cells']] == [
        cell['text'] for cell in adaptive.diagnostics['cells']]
