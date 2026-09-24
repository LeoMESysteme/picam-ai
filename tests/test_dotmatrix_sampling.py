"""Tests fuer Abtastung, Normierung und Verschiebungssuche (Dot-Matrix-Leser)."""

from __future__ import annotations

import numpy as np
from dotmatrix_helpers import GRID, render

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import rom_vector
from dispread.ocr.dotmatrix_sampling import (
    MIN_CONTRAST,
    SHIFTS,
    dot_centers,
    normalized,
    sample_image,
)


def test_nine_shifts():
    assert len(SHIFTS) == 9 and (0, 0) in SHIFTS


def test_dot_centers_first_cell():
    c = dot_centers(GRID, 0)
    assert c.shape == (40, 2)
    assert np.allclose(c[0], (10 + 24 / 6 * 0.5, 40 + 80 / 8 * 0.5))


def test_normalized_matches_rom_at_zero_shift():
    img = render("+0.60972 ")
    s = sample_image(img, GRID, range(9))
    n = normalized(s)
    zero = SHIFTS.index((0, 0))
    assert n.shape == (9, 9, 40)
    for i, ch in enumerate("+0.60972 "):
        assert np.abs(n[i, zero] - rom_vector(ch)).max() < 0.35
    assert s.contrast > MIN_CONTRAST


def test_blank_display_has_low_contrast_and_no_nan():
    img = np.full((160, 400), 180, np.uint8)
    s = sample_image(img, GRID, range(9))
    assert s.contrast < MIN_CONTRAST
    assert np.isfinite(normalized(s)).all()


def test_shift_at_image_border_does_not_raise():
    grid = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    img = render("+0.60972 ", grid=grid)
    s = sample_image(img, grid, range(9))
    assert s.raw.shape == (9, 9, 40)


def test_normalized_survives_multiplicative_illumination_gradient():
    text = "+0.60972 "
    img = render(text)
    w = img.shape[1]
    gain = np.linspace(1.0, 0.4, w, dtype=np.float32)
    gradient_img = np.clip(img.astype(np.float32) * gain[None, :], 0, 255).astype(np.uint8)
    s = sample_image(gradient_img, GRID, range(9))
    n = normalized(s)
    zero = SHIFTS.index((0, 0))
    for i, ch in enumerate(text):
        assert np.abs(n[i, zero] - rom_vector(ch)).max() < 0.35
