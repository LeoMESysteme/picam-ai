"""Test-Helfer fuer den Dot-Matrix-Leser: Test-Raster und Synthese-Renderer.

`GRID` und `render` werden von mehreren Testdateien der Dot-Matrix-Aufgaben
benutzt (Task 2 ff.), deshalb hier ausgelagert statt in jeder Testdatei
dupliziert.
"""

from __future__ import annotations

import cv2
import numpy as np

from dispread.charcells import CharGrid
from dispread.layout import CharLayout
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
        img = cv2.GaussianBlur(img, (0, 0), blur)
    return img.astype(np.uint8)


TRAIN_TEXTS = ["+0.60972 ", "+ 1.2345 ", "+ 67.890 ", "+  988.5 ", "+ 3456.7 ", "+0.11111 "]
LAYOUT = CharLayout(grid=GRID, unit="mV/V")
FRAME_SIZE = (800, 400)
ORIGIN = (200, 120)
#: Bildet den in `embed` eingesetzten 400x160-Ausschnitt 1:1 zurueck.
#: rectify bildet die Pixelzentren auf (0, 0) bis (399, 159) ab.
QUAD = [[200.0, 120.0], [599.0, 120.0], [599.0, 279.0], [200.0, 279.0]]


def synthetic_reader(seed: int = 7):
    """DotMatrixReader mit synthetischen Vorlagen (wie test_dotmatrix_reader)."""
    from dispread.ocr.dotmatrix import DotMatrixReader
    from dispread.ocr.dotmatrix_font import CLASSES
    from dispread.ocr.dotmatrix_sampling import normalized, sample_image
    from dispread.ocr.dotmatrix_templates import build_templates

    rng = np.random.default_rng(seed)
    samples = {c: [] for c in CLASSES}
    for text in TRAIN_TEXTS * 6:
        img = render(text, blur=rng.uniform(0.3, 1.0))
        img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
        n = normalized(sample_image(img, GRID, range(9)))
        for i, ch in enumerate(text):
            samples[ch].append(n[i])
    return DotMatrixReader(build_templates(samples, ("synthetisch",)))


def embed(text_or_crop, frame_size=FRAME_SIZE, origin=ORIGIN):
    """400x160-Anzeige als BGR-Vollbild; `QUAD` bildet sie 1:1 zurueck."""
    crop = render(text_or_crop) if isinstance(text_or_crop, str) else text_or_crop
    frame = np.full((frame_size[1], frame_size[0]), 200, np.uint8)
    x, y = origin
    frame[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
