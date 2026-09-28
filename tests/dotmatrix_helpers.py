"""Test-Helfer fuer den Dot-Matrix-Leser: Test-Raster und Synthese-Renderer.

`GRID` und `render` werden von mehreren Testdateien der Dot-Matrix-Aufgaben
benutzt (Task 2 ff.), deshalb hier ausgelagert statt in jeder Testdatei
dupliziert.
"""

from __future__ import annotations

import numpy as np

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import rom_vector
from dispread.ocr.dotmatrix_sampling import dot_centers

GRID = CharGrid(n_cells=16, left=10.0, pitch=24.0, top=40.0, bottom=120.0)


def render(text: str, grid: CharGrid = GRID, size=(400, 160), bg=200, ink=60, blur=0.0):
    img = np.full((size[1], size[0]), bg, np.float32)
    for i, ch in enumerate(text):
        v = rom_vector(ch)
        for k, (x, y) in enumerate(dot_centers(grid, i)):
            if v[k]:
                r = 1.4
                ys, xs = np.ogrid[: size[1], : size[0]]
                img[(xs - x) ** 2 + (ys - y) ** 2 <= r * r] = ink
    if blur:
        import cv2

        img = cv2.GaussianBlur(img, (0, 0), blur)
    return img.astype(np.uint8)
