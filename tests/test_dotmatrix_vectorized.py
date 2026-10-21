"""Vergleich mit dem bisherigen Leser; Referenzcode bleibt nur im Test."""

from dataclasses import fields, replace
from pathlib import Path

import cv2
import numpy as np
import pytest
from dotmatrix_helpers import GRID, LAYOUT, render, synthetic_reader

from dispread.charcells import CharGrid
from dispread.layout import CharLayout
from dispread.live import DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256
from dispread.ocr import dotmatrix
from dispread.ocr import dotmatrix_sampling as sampling
from dispread.ocr import dotmatrix_templates as templates
from dispread.rectify import rectify


def _reference_best_per_class(vectors, mean, std):
    out = {}
    for ch in mean:
        ds = [float(np.sqrt(np.mean(((v - mean[ch]) / np.maximum(std[ch], templates.SIGMA_FLOOR)) ** 2)))
              for v in vectors]
        j = int(np.argmin(ds))
        out[ch] = (ds[j], j)
    return out


def _reference_classify(vectors, t, d_max_factor=1.0):
    per = _reference_best_per_class(vectors, t.mean, t.std)
    order = sorted(per, key=lambda c: per[c][0])
    best, second = order[:2]
    d_best, j = per[best]
    d_second = per[second][0]
    gap = d_second - d_best
    d_max = t.d_max * d_max_factor
    margin = min(d_max - d_best, gap - t.margin_min)
    reason = None
    if d_best > d_max:
        reason = "zelle_unbekannt"
    elif gap < t.margin_min:
        reason = "zelle_mehrdeutig"
    return templates.CellDecision(None if reason else best, best, second, d_best, d_second, j, reason, margin)


def _assert_decision(actual, expected):
    for f in fields(expected):
        a, e = getattr(actual, f.name), getattr(expected, f.name)
        if f.name in {"d_best", "d_second", "margin"}:
            assert a == pytest.approx(e, rel=1e-5, abs=0)
        else:
            assert a == e, f.name


@pytest.fixture(scope="module")
def reader():
    return synthetic_reader()


def test_vectorized_classification_matches_reference_on_synthetic_cells(reader):
    t = reader._t
    stacked = templates.stack_templates(t)
    assert stacked.classes == tuple(t.mean)
    assert stacked.mean.shape == stacked.inv_std.shape == (len(t.mean), 40)
    assert stacked.mean.dtype == stacked.inv_std.dtype == np.float32
    rng = np.random.default_rng(1)
    vectors = [rng.uniform(0, 1, (len(sampling.SHIFTS), 40)).astype(np.float32) for _ in range(200)]
    vectors.extend(sampling.normalized(sampling.sample_image(render('+0.60972 '), GRID, range(9))))
    for v in vectors:
        for factor in (1.0, 1.41, 2.0):
            expected = _reference_classify(v, t, factor)
            _assert_decision(templates.classify(v, t, factor), expected)
            _assert_decision(templates.classify(v, stacked, factor), expected)


def test_ties_use_dict_order_and_first_shift(reader):
    mean = {c: np.full(40, 0.5, np.float32) for c in reversed(reader._t.mean)}
    t = replace(reader._t, mean=mean)
    v = np.full((9, 40), 0.5, np.float32)
    actual = templates.classify(v, templates.stack_templates(t))
    assert (actual.best, actual.second) == tuple(mean)[:2]
    assert actual.shift_index == 0
    _assert_decision(actual, _reference_classify(v, t))


def test_threshold_boundaries_preserve_acceptance(reader):
    v = sampling.normalized(sampling.sample_image(render('+0.60972 '), GRID, range(9)))[0]
    ref = _reference_classify(v, reader._t)
    for threshold in (ref.d_best, np.nextafter(ref.d_best, -np.inf), np.nextafter(ref.d_best, np.inf)):
        t = replace(reader._t, d_max=threshold)
        _assert_decision(templates.classify(v, templates.stack_templates(t)), _reference_classify(v, t))
    for gap in (ref.d_second - ref.d_best, np.nextafter(ref.d_second - ref.d_best, np.inf)):
        t = replace(reader._t, margin_min=gap)
        _assert_decision(templates.classify(v, templates.stack_templates(t)), _reference_classify(v, t))


def _reference_centers(grid, cell, shift=(0, 0)):
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    row_h = (grid.bottom - grid.top) / 8
    x0, y0 = grid.left + cell * grid.pitch + shift[0], grid.top + shift[1]
    return np.asarray([(x0 + (c + 0.5) * col_w, y0 + (r + 0.5) * row_h)
                       for r in range(8) for c in range(5)], dtype=np.float32)


def _assert_sampling(gray, grid, monkeypatch):
    for cells in (range(9), (13, 14, 15)):
        actual = sampling.sample_image(gray, grid, cells)
        # Alte Schleife gegen den neuen zusammengefassten _bilinear-Aufruf.
        original = sampling._bilinear
        def reference_bilinear(image, pts, original=original, cells=cells):
            return np.stack([original(image, _reference_centers(grid, c, s))
                             for c in cells for s in sampling.SHIFTS]).reshape(-1)
        with monkeypatch.context() as m:
            m.setattr(sampling, '_bilinear', reference_bilinear)
            expected = sampling.sample_image(gray, grid, cells)
        for name in ('raw', 'background_dots', 'background'):
            np.testing.assert_allclose(getattr(actual, name), getattr(expected, name), rtol=0, atol=1e-4)
        assert actual.ink == pytest.approx(expected.ink, abs=1e-4)
        assert actual.contrast == pytest.approx(expected.contrast, abs=1e-4)
        assert actual.saturated_fraction == expected.saturated_fraction


def test_sampling_matches_original_loop(monkeypatch):
    _assert_sampling(render('+0.60972 '), GRID, monkeypatch)
    grid = replace(GRID, left=0.123, top=0.456, bottom=159.3, pitch=24.765)
    _assert_sampling(np.random.default_rng(8).integers(0, 255, (160, 400), dtype=np.uint8), grid, monkeypatch)


def test_sampling_uses_two_bilinear_calls(monkeypatch):
    calls = []
    original = sampling._bilinear
    def spy(img, pts):
        calls.append(pts.shape)
        return original(img, pts)
    monkeypatch.setattr(sampling, '_bilinear', spy)
    sampling.sample_image(render('+0.60972 '), GRID, range(9))
    assert calls == [(9 * 9 * 40, 2)] * 2


_REAL = sorted(p for p in Path('var/live').glob('*/setup/*.png')
               if p.name in {'still.png', 'stability.png'} and (p.parent / 'proposal.json').is_file())


@pytest.mark.parametrize('path', _REAL or [None], ids=lambda p: str(p))
def test_real_crops_match_reference(path, monkeypatch):
    if path is None or not DEFAULT_TEMPLATES.is_file():
        pytest.skip('Keine gespeicherten Setup-Crops/Vorlagen')
    import json
    data = json.loads((path.parent / 'proposal.json').read_text())
    image = cv2.imread(str(path))
    assert image is not None
    crop = rectify(image, data['quad'], target_size=(400, 160)).image
    layout = CharLayout(grid=CharGrid.from_dict(data['grid']), unit=LAYOUT.unit)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _assert_sampling(gray, layout.grid, monkeypatch)
    for factor in (1.0, 1.41, 2.0):
        reader = dotmatrix.DotMatrixReader.from_file(DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256, factor)
        decisions = []
        original = dotmatrix.classify
        def checked(v, t, d_max_factor=1.0, original=original, reader=reader, decisions=decisions):
            actual = original(v, t, d_max_factor)
            expected = _reference_classify(v, reader._t, d_max_factor)
            _assert_decision(actual, expected)
            decisions.append(actual)
            return actual
        with monkeypatch.context() as m:
            m.setattr(dotmatrix, 'classify', checked)
            actual = reader.read(crop, layout)
        with monkeypatch.context() as m:
            m.setattr(dotmatrix, 'classify', lambda v, t, d_max_factor=1.0, reader=reader:
                         _reference_classify(v, reader._t, d_max_factor))
            expected = reader.read(crop, layout)
        assert actual == expected
        # Kontrast-/Saettigungsablehnungen brauchen keine Zellentscheidung.
        assert decisions or actual.diagnostics['reject_reason'] in {'kontrast', 'ueberbelichtet'}
