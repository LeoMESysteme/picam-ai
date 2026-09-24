"""Punktabtastung fuer den Dot-Matrix-Leser (Spec Abschnitt 2, Schritte 1-4).

Jede Zelle des bestaetigten `CharGrid` hat 5 x 8 Punktmitten. Abgetastet wird
ein gewichteter Mittelwert um jede Mitte (Gaussfilter, dann bilinear), nicht
ein einzelnes Pixel. Normiert wird je Bild: Hintergrund je Zelle (hellste
Punkte der Zelle), Punktpegel global - so gleicht sich ein Helligkeitsverlauf
ueber das Glas aus (in allen drei Ernte-Aufstellungen war das rechte Drittel
dunkler, VALIDATION.md 2026-09-24).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import COLS, N_DOTS, ROWS

SHIFTS: tuple[tuple[int, int], ...] = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1))
#: Vorabwert, nicht validiert - Stufe 1 prueft ihn (Spec Abschnitt 3).
MIN_CONTRAST = 0.08
#: Gaussbreite als Anteil der Punktspaltenbreite.
_SIGMA_FRACTION = 0.3
#: Anteil der hellsten Punkte einer Zelle, der als Hintergrund gilt.
_BACKGROUND_PERCENTILE = 80.0
_INK_PERCENTILE = 3.0


def dot_centers(grid: CharGrid, cell: int, shift: tuple[int, int] = (0, 0)) -> np.ndarray:
    """Punktmitten einer Zelle im entzerrten Bild, Form (40, 2) als (x, y)."""
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    row_h = (grid.bottom - grid.top) / ROWS
    x0 = grid.left + cell * grid.pitch + shift[0]
    y0 = grid.top + shift[1]
    pts = [(x0 + (c + 0.5) * col_w, y0 + (r + 0.5) * row_h) for r in range(ROWS) for c in range(COLS)]
    return np.asarray(pts, dtype=np.float32)


@dataclass(frozen=True)
class SampledImage:
    raw: np.ndarray
    background: np.ndarray
    ink: float
    contrast: float
    saturated_fraction: float


def _bilinear(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    h, w = img.shape
    x = np.clip(pts[:, 0], 0, w - 1.001)
    y = np.clip(pts[:, 1], 0, h - 1.001)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = x - x0
    fy = y - y0
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def sample_image(gray: np.ndarray, grid: CharGrid, cells: range) -> SampledImage:
    """Tastet jede Zelle bei allen `SHIFTS` ab (Rohhelligkeiten, ungeglaettet)."""
    img = gray.astype(np.float32)
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    smooth = cv2.GaussianBlur(img, (0, 0), max(0.5, _SIGMA_FRACTION * col_w))
    raw = np.empty((len(cells), len(SHIFTS), N_DOTS), dtype=np.float32)
    for i, cell in enumerate(cells):
        for j, shift in enumerate(SHIFTS):
            raw[i, j] = _bilinear(smooth, dot_centers(grid, cell, shift))
    zero = SHIFTS.index((0, 0))
    background = np.percentile(raw[:, zero, :], _BACKGROUND_PERCENTILE, axis=1)
    ink = float(np.percentile(raw[:, zero, :], _INK_PERCENTILE))
    ref = float(np.median(background))
    contrast = (ref - ink) / ref if ref > 0 else 0.0
    y0, y1 = int(max(0, grid.top)), int(min(img.shape[0], grid.bottom))
    x0 = int(max(0, grid.left))
    x1 = int(min(img.shape[1], grid.left + grid.n_cells * grid.pitch))
    region = gray[y0:y1, x0:x1]
    saturated = float((region >= 250).mean()) if region.size else 0.0
    return SampledImage(raw, background.astype(np.float32), ink, float(max(contrast, 0.0)), saturated)


def normalized(s: SampledImage) -> np.ndarray:
    """Rohhelligkeiten auf [0, 1] normiert, 1 = voll dunkel (Punkt an)."""
    depth = s.background[:, None, None] - s.ink
    depth = np.where(depth > 1e-3, depth, 1e-3)
    out = (s.background[:, None, None] - s.raw) / depth
    return np.clip(out, 0.0, 1.0).astype(np.float32)
