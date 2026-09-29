"""Kontrollbilder fuer das Punktraster und die Abtaststellen der Einrichtung."""

from __future__ import annotations

import cv2
import numpy as np

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_sampling import dot_centers

TARGET_SIZE = (400, 160)
OVERLAY_SCALE = 4
GRID = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0)


def _bgr(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image.copy()


def draw_source_overlay(image_bgr: np.ndarray, fit: object, verdict: str) -> np.ndarray:
    """Quad und gefundene Punkte im unveraenderten Quellbild markieren."""
    overlay = _bgr(image_bgr)
    quad = np.asarray(fit.quad, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(overlay, [quad], True, (0, 255, 255), 2)
    for x, y in fit.assigned_points:
        cv2.circle(overlay, (round(x), round(y)), 2, (0, 255, 0), -1)
    for x, y in fit.rejected_points:
        cv2.circle(overlay, (round(x), round(y)), 2, (0, 0, 255), -1)
    color = {"OK": (0, 255, 0), "WARNUNG": (0, 255, 255), "FEHLER": (0, 0, 255)}.get(verdict, (255, 255, 255))
    cv2.putText(overlay, verdict, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
    return overlay


def draw_sampling_overlay(rectified_bgr: np.ndarray, *, edge_cells: tuple[int, ...] = ()) -> np.ndarray:
    """Das feste 16-Zellen-Raster vierfach mit allen 8 Punktzeilen zeigen."""
    if rectified_bgr.shape[:2] != (TARGET_SIZE[1], TARGET_SIZE[0]):
        raise ValueError("Entzerrtes Bild muss 400x160 Pixel gross sein")
    overlay = cv2.resize(_bgr(rectified_bgr), None, fx=OVERLAY_SCALE, fy=OVERLAY_SCALE, interpolation=cv2.INTER_NEAREST)
    for cell in range(GRID.n_cells):
        points = dot_centers(GRID, cell)
        for index, (x, y) in enumerate(points):
            color = (255, 0, 0) if index // 5 == 7 else (0, 0, 255)
            cv2.circle(overlay, (round(float(x) * OVERLAY_SCALE), round(float(y) * OVERLAY_SCALE)), 2, color, -1)
    for cell in edge_cells:
        if not 0 <= cell < GRID.n_cells:
            continue
        x0 = round((GRID.left + cell * GRID.pitch) * OVERLAY_SCALE)
        x1 = round((GRID.left + (cell + 1) * GRID.pitch) * OVERLAY_SCALE) - 1
        y0 = round(GRID.top * OVERLAY_SCALE)
        y1 = round(GRID.bottom * OVERLAY_SCALE) - 1
        cv2.rectangle(overlay, (x0, y0), (x1, y1), (0, 255, 255), 2)
    return overlay
