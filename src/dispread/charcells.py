"""Zeichenzellenraster fuer Punktmatrix-Anzeigen (Konzept.md §4, Ernte Phase 1).

`CharGrid` beschreibt die Zeichenzellen eines Punktmatrix-Displays (HD44780,
16 x 1, 5 x 8 Punkte) auf dem **entzerrten** Bild. Der Bediener bestaetigt das
Raster einmal je Sitzung, so wie die manuelle ROI - siehe
docs/superpowers/plans/2026-09-23-ernte-phase1.md, Entscheidung 2. Zusaetzlich
misst `source_dot_column_px` die Punktspaltenbreite im **Quellbild**, denn das
Aufloesungs-Gate (Entscheidung 3) prueft dort, nicht im hochgerechneten
entzerrten Bild.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from dispread.detect import Quad
from dispread.rectify import _order_quad


@dataclass(frozen=True, slots=True)
class CharGrid:
    """Regelmaessiges Zeichenzellenraster im entzerrten Bild.

    Zelle i ueberdeckt horizontal `[left + i*pitch, left + (i+1)*pitch)` und
    vertikal `[top, bottom)`. Alle Laengen sind Pixel des entzerrten Bildes.
    """

    n_cells: int
    left: float
    pitch: float
    top: float
    bottom: float
    dot_columns: int = 5
    gap_columns: int = 1

    def cell_boxes(self) -> list[tuple[int, int, int, int]]:
        """Zellenboxen als `(x, y, w, h)`, gerundet auf ganze Pixel."""
        y = round(self.top)
        h = round(self.bottom) - y
        boxes = []
        for i in range(self.n_cells):
            x0 = round(self.left + i * self.pitch)
            x1 = round(self.left + (i + 1) * self.pitch)
            boxes.append((x0, y, x1 - x0, h))
        return boxes

    def to_dict(self) -> dict:
        return {
            "n_cells": self.n_cells,
            "left": self.left,
            "pitch": self.pitch,
            "top": self.top,
            "bottom": self.bottom,
            "dot_columns": self.dot_columns,
            "gap_columns": self.gap_columns,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CharGrid:
        return cls(
            n_cells=d["n_cells"],
            left=d["left"],
            pitch=d["pitch"],
            top=d["top"],
            bottom=d["bottom"],
            dot_columns=d.get("dot_columns", 5),
            gap_columns=d.get("gap_columns", 1),
        )

    def validate(self, width: int, height: int) -> None:
        """Wirft `ValueError`, wenn das Raster nicht ins Bild passt."""
        if self.n_cells < 1:
            raise ValueError(f"n_cells muss >= 1 sein, ist {self.n_cells}")
        if self.pitch <= 0:
            raise ValueError(f"pitch muss > 0 sein, ist {self.pitch}")
        if self.top >= self.bottom:
            raise ValueError(f"top ({self.top}) muss < bottom ({self.bottom}) sein")
        right = self.left + self.n_cells * self.pitch
        if self.left < 0 or right > width:
            raise ValueError(
                f"Raster ragt horizontal ueber das Bild hinaus: [{self.left}, {right}] vs. Breite {width}"
            )
        if self.top < 0 or self.bottom > height:
            raise ValueError(
                f"Raster ragt vertikal ueber das Bild hinaus: [{self.top}, {self.bottom}] vs. Hoehe {height}"
            )


def source_dot_column_px(grid: CharGrid, quad: Quad, target_size: tuple[int, int]) -> float:
    """Punktspaltenbreite im Quellbild, Minimum ueber alle Zellen.

    Die Zellecken werden ueber die inverse Homographie (dieselbe Eckordnung
    wie `dispread.rectify._order_quad`) ins Quellbild abgebildet. Die
    Zellbreite im Quellbild ist die euklidische Distanz der abgebildeten
    Punkte `(x_links, y_mitte)` und `(x_rechts, y_mitte)`. Zurueckgegeben wird
    das Minimum ueber alle Zellen von
    `(Zellbreite im Quellbild) / (dot_columns + gap_columns)`.
    """
    width, height = target_size
    src = _order_quad(quad)
    dst = np.array(
        [[0, 0], [width, 0], [width, height], [0, height]],
        dtype=np.float32,
    )
    inverse = cv2.getPerspectiveTransform(dst, src)

    y_mid = (grid.top + grid.bottom) / 2.0
    min_px = math.inf
    for i in range(grid.n_cells):
        x_left = grid.left + i * grid.pitch
        x_right = grid.left + (i + 1) * grid.pitch
        pts = np.array([[[x_left, y_mid]], [[x_right, y_mid]]], dtype=np.float32)
        mapped = cv2.perspectiveTransform(pts, inverse)
        p_left = mapped[0, 0]
        p_right = mapped[1, 0]
        cell_width_src = float(np.hypot(p_right[0] - p_left[0], p_right[1] - p_left[1]))
        per_dot = cell_width_src / (grid.dot_columns + grid.gap_columns)
        min_px = min(min_px, per_dot)
    return min_px
