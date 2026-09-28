"""`dispread.focus_sweep` - Task 4 (Profil v3 und harvest-setup.py)."""

from __future__ import annotations

import cv2
import numpy as np

from dispread.focus_sweep import sharpness, sweep_focus


def test_sweep_findet_maximum_grob_dann_fein():
    calls = []

    def measure(f):
        calls.append(f)
        return -abs(f - 50)

    best, measured = sweep_focus(measure)
    assert best == 50
    assert calls[:32] == list(range(0, 256, 8))
    assert all(42 <= f <= 58 for f in calls[32:])
    assert measured[-1][0] == calls[-1]


def test_sweep_bleibt_im_bereich():
    best, measured = sweep_focus(lambda f: f)
    assert best == max(f for f, _ in measured)
    assert all(0 <= f <= 255 for f, _ in measured)


def test_sweep_misst_keinen_fokuswert_zweimal():
    calls = []

    def measure(f):
        calls.append(f)
        return -abs(f - 48)  # 48 liegt bereits in `coarse`

    sweep_focus(measure)
    assert len(calls) == len(set(calls))


def _checkerboard(size: int = 64, cell: int = 4) -> np.ndarray:
    row = (np.arange(size) // cell) % 2
    return (np.logical_xor(row[:, None], row[None, :]).astype(np.uint8)) * 255


def test_sharpness_scharf_groesser_als_weichgezeichnet():
    sharp = _checkerboard()
    blurred = cv2.GaussianBlur(sharp, (9, 9), 0)
    assert sharpness(sharp) > sharpness(blurred)
