"""Versatz des Punktrasters gegen die Punkte messen und das Quad korrigieren.

Befund 2026-09-30 (VALIDATION.md, Rasterversatz): Die Profile `ab3`/`ab4`
(auch `ernte1`, `auf2`, `auf3`) tasten bis 0,5-0,8 Punktspalten neben den
Punktmitten ab. Das Restmass der Rasteranpassung war trotzdem klein, und die
Einrichtungspruefungen fanden den Fehler nicht.

Messung ohne Leser und ohne Vorlagen: Bei bekanntem Text (Label aus dem
seriellen Strom) wird je Zelle und Halbzelle (Zeilen 0-3 bzw. 3-6) der
Versatz im Rasterkoordinatensystem gesucht, bei dem die abgetasteten
Helligkeiten am besten mit dem ROM-Muster des Zeichens korrelieren. Abgetastet
wird im Quellbild (ueber die Homographie), damit die Aufloesung der
Entzerrung die Messung nicht begrenzt.

Korrektur: Die Mediane der Versaetze je (Zelle, Halbzelle) ueber mehrere
Bilder verschieben die zugehoerigen Rasterpunkte; aus diesen Punkten wird die
Homographie neu angepasst. Das wird wiederholt, bis sich das Quad kaum noch
aendert.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import COLS, ROWS, rom_vector

#: Halbzellen als Zeilenbereiche (Zeile 3 gehoert zu beiden - mittlere Zeile
#: der meisten Ziffern, sonst haette die untere Haelfte bei `7` zu wenig
#: An-Punkte).
HALVES: tuple[tuple[int, int], ...] = ((0, 4), (3, 7))
#: Ganze Zelle (Zeilen 0-6). Fuer den senkrechten Versatz verlaesslicher: Bei
#: senkrecht symmetrischen Zeichen wie `+` sehen die beiden Halbzellen den
#: durchlaufenden Strich und messen entgegengesetzt (+-0,1-0,2 Punktzeilen).
FULL: tuple[tuple[int, int], ...] = ((0, 7),)
#: Mindestzahl An- und Aus-Punkte je Halbzelle, sonst keine Messung.
_MIN_DOTS = 3
#: Suchbereich und Schritte in Punktspalten bzw. Punktzeilen.
_COARSE = np.arange(-1.0, 1.0001, 0.125)
_FINE = np.arange(-0.25, 0.25001, 0.03125)
#: Glaettung des Quellbilds als Anteil der Punktspaltenbreite im Quellbild.
_SIGMA_FRACTION = 0.3
#: Blende der Abtastung in Punktabstaenden: Mittel ueber 3 x 3 Stellen im
#: Abstand +-`_APERTURE`. Ein LCD-Punkt fuellt etwa 80 % seiner Zelle; mit
#: einer punktfoermigen Abtastung waere die Korrelation innerhalb des Punkts
#: flach und das Maximum laege zufaellig am Rand dieses Plateaus.
_APERTURE = 0.3
#: Stellen der Feinsuche mit Korrelation hoechstens so weit unter dem
#: Maximum zaehlen zum Plateau (Schwerpunkt statt erstes Maximum).
_PLATEAU = 0.01
#: Mindestkorrelation, sonst gilt die Messung als nicht belastbar.
MIN_CORRELATION = 0.5


@dataclass(frozen=True)
class HalfOffset:
    cell: int
    half: int
    dx_cols: float
    dy_rows: float
    correlation: float


def _lattice(grid: CharGrid, cell: int, rows: tuple[int, int], dx: float, dy: float) -> np.ndarray:
    """Punktmitten (Rasterkoordinaten) einer Halbzelle, verschoben um dx
    Punktspalten und dy Punktzeilen. Form (n, 2)."""
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    row_h = (grid.bottom - grid.top) / ROWS
    x0 = grid.left + cell * grid.pitch
    pts = [
        (x0 + (c + 0.5 + dx) * col_w, grid.top + (r + 0.5 + dy) * row_h)
        for r in range(*rows)
        for c in range(COLS)
    ]
    return np.asarray(pts, dtype=np.float32)


def _homography(quad, target_size: tuple[int, int]) -> np.ndarray:
    """Rasterkoordinaten -> Quellbild, wie `rectify` (Ecken auf 0..w-1)."""
    w, h = target_size
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    return cv2.getPerspectiveTransform(dst, np.asarray(quad, dtype=np.float32))


def _source_col_width(quad, grid: CharGrid, target_size: tuple[int, int]) -> float:
    q = np.asarray(quad, dtype=np.float64)
    top = np.linalg.norm(q[1] - q[0])
    bottom = np.linalg.norm(q[2] - q[3])
    return float(min(top, bottom) / target_size[0] * grid.pitch / (grid.dot_columns + grid.gap_columns))


def _bilinear(img: np.ndarray, pts: np.ndarray) -> np.ndarray:
    h, w = img.shape
    x = np.clip(pts[..., 0], 0, w - 1.001)
    y = np.clip(pts[..., 1], 0, h - 1.001)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = x - x0
    fy = y - y0
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def _best_offset(smooth, hom, grid, cell, rows, pattern, center):
    """Bester Versatz (dx, dy, Korrelation) auf einem Suchgitter um `center`."""
    steps = _COARSE if center is None else _FINE
    cx, cy = (0.0, 0.0) if center is None else center
    dxs = cx + steps
    dys = cy + steps
    base = _lattice(grid, cell, rows, 0.0, 0.0)
    col_w = grid.pitch / (grid.dot_columns + grid.gap_columns)
    row_h = (grid.bottom - grid.top) / ROWS
    gx, gy = np.meshgrid(dxs, dys, indexing="ij")
    shifts = np.stack([gx.ravel() * col_w, gy.ravel() * row_h], axis=1)
    ap = np.array([(ax * col_w, ay * row_h) for ax in (-_APERTURE, 0, _APERTURE) for ay in (-_APERTURE, 0, _APERTURE)])
    pts = base[None, None, :, :] + shifts[:, None, None, :] + ap[None, :, None, :]
    src = cv2.perspectiveTransform(pts.reshape(1, -1, 2).astype(np.float32), hom)[0].reshape(pts.shape)
    vals = -_bilinear(smooth, src).mean(axis=1)
    vals = vals - vals.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(vals, axis=1) * np.linalg.norm(pattern)
    corr = (vals @ pattern) / np.where(norms > 0, norms, np.inf)
    k = int(np.argmax(corr))
    if center is None:
        return float(gx.ravel()[k]), float(gy.ravel()[k]), float(corr[k])
    # Feinsuche: Mitte des Plateaus statt erstes Maximum. Innerhalb eines
    # Punkts bleibt die Korrelation trotz Blende nahezu gleich; der
    # Schwerpunkt aller Stellen nahe am Maximum ist dann die Punktmitte.
    near = corr >= corr[k] - _PLATEAU
    return float(gx.ravel()[near].mean()), float(gy.ravel()[near].mean()), float(corr[k])


def measure_offsets(
    image: np.ndarray,
    quad,
    grid: CharGrid,
    target_size: tuple[int, int],
    cell_text: str,
    row_sets: tuple[tuple[int, int], ...] = HALVES,
) -> list[HalfOffset]:
    """Versatz je Zelle und Halbzelle fuer ein Bild mit bekanntem Text.

    Halbzellen mit weniger als `_MIN_DOTS` An- oder Aus-Punkten (Leerzelle,
    obere Haelfte von `.`) werden uebersprungen.
    """
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sigma = max(0.5, _SIGMA_FRACTION * _source_col_width(quad, grid, target_size))
    smooth = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), sigma)
    hom = _homography(quad, target_size)
    out: list[HalfOffset] = []
    for cell, ch in enumerate(cell_text):
        rom = rom_vector(ch).reshape(ROWS, COLS)
        for half, rows in enumerate(row_sets):
            pat = rom[rows[0] : rows[1]].ravel().astype(np.float64)
            n_on = int(pat.sum())
            if n_on < _MIN_DOTS or pat.size - n_on < _MIN_DOTS:
                continue
            pattern = pat - pat.mean()
            dx, dy, _ = _best_offset(smooth, hom, grid, cell, rows, pattern, None)
            dx, dy, corr = _best_offset(smooth, hom, grid, cell, rows, pattern, (dx, dy))
            out.append(HalfOffset(cell, half, dx, dy, corr))
    return out


def median_offsets(measurements: list[list[HalfOffset]]) -> dict[tuple[int, int], tuple[float, float, int]]:
    """Median-Versatz je (Zelle, Halbzelle) ueber alle Bilder, nur Messungen
    mit Korrelation >= `MIN_CORRELATION`. Wert: (dx, dy, Anzahl)."""
    buckets: dict[tuple[int, int], list[HalfOffset]] = {}
    for per_image in measurements:
        for m in per_image:
            if m.correlation >= MIN_CORRELATION:
                buckets.setdefault((m.cell, m.half), []).append(m)
    return {
        k: (float(np.median([m.dx_cols for m in v])), float(np.median([m.dy_rows for m in v])), len(v))
        for k, v in sorted(buckets.items())
    }


def refit_quad(
    quad, grid: CharGrid, target_size: tuple[int, int], offsets: dict[tuple[int, int], tuple[float, float, int]]
) -> np.ndarray:
    """Neues Quad aus den Median-Versaetzen: Jede gemessene Halbzelle liefert
    ihren Mittelpunkt im Raster und die Stelle im Quellbild, an der er
    tatsaechlich liegt; daraus wird die Homographie neu angepasst."""
    if len({c for c, _ in offsets}) < 3 or len({h for _, h in offsets}) < 2:
        raise ValueError("zu wenige Halbzellen fuer eine Neuanpassung (mindestens 3 Zellen, beide Haelften)")
    hom = _homography(quad, target_size)
    lattice_pts, source_pts = [], []
    for (cell, half), (dx, dy, _count) in offsets.items():
        rows = HALVES[half]
        nominal = _lattice(grid, cell, rows, 0.0, 0.0).mean(axis=0)
        actual = _lattice(grid, cell, rows, dx, dy).mean(axis=0)
        lattice_pts.append(nominal)
        source_pts.append(cv2.perspectiveTransform(actual.reshape(1, 1, 2).astype(np.float32), hom)[0, 0])
    new_hom, _ = cv2.findHomography(np.asarray(lattice_pts, np.float32), np.asarray(source_pts, np.float32), 0)
    w, h = target_size
    corners = np.array([[[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]], dtype=np.float32)
    return cv2.perspectiveTransform(corners, new_hom)[0]


def refine_quad(
    frames: list[tuple[np.ndarray, str]],
    quad,
    grid: CharGrid,
    target_size: tuple[int, int],
    iterations: int = 4,
    tol_px: float = 0.05,
) -> tuple[np.ndarray, list[dict]]:
    """Quad iterativ korrigieren. `frames`: (Bild, Zellentext). Rueckgabe:
    neues Quad und je Durchgang die Median-Versaetze vor der Anpassung."""
    current = np.asarray(quad, dtype=np.float32)
    history: list[dict] = []
    for _ in range(iterations):
        meds = median_offsets([measure_offsets(img, current, grid, target_size, txt) for img, txt in frames])
        history.append({"quad": current.tolist(), "offsets": meds})
        new = refit_quad(current, grid, target_size, meds)
        moved = float(np.abs(new - current).max())
        current = new.astype(np.float32)
        if moved < tol_px:
            break
    return current, history


def max_abs_offset(offsets: dict[tuple[int, int], tuple[float, float, int]]) -> tuple[float, float]:
    """Groesster Betrag des Median-Versatzes (dx in Punktspalten, dy in
    Punktzeilen) ueber alle Halbzellen."""
    if not offsets:
        return float("inf"), float("inf")
    return (
        max(abs(v[0]) for v in offsets.values()),
        max(abs(v[1]) for v in offsets.values()),
    )
