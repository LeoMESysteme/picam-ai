"""Laufzeit der Lesekette (Entzerren + Dot-Matrix-Leser) messen.

Bestimmt, wie viele Bilder je Sekunde die Live-Sitzung lesen kann. Die
Sitzung liest immer das neueste Bild und ueberspringt aeltere (Spec §2) -
diese Messung sagt, wie viele das sind.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Sequence

import numpy as np

from dispread.layout import CharLayout
from dispread.ocr import ValueReader
from dispread.rectify import rectify


def time_read_chain(
    reader: ValueReader,
    image: np.ndarray,
    quad: Sequence[Sequence[float]],
    layout: CharLayout,
    *,
    repeats: int = 50,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> dict:
    durations: list[float] = []
    result = None
    for _ in range(repeats):
        t0 = clock()
        crop = rectify(image, quad, target_size=(400, 160))
        result = reader.read(crop.image, layout)
        durations.append((clock() - t0) / 1e6)
    durations.sort()
    p95_index = max(0, round(0.95 * len(durations)) - 1)
    return {
        "repeats": repeats,
        "median_ms": statistics.median(durations),
        "p95_ms": durations[p95_index],
        "max_ms": durations[-1],
        "last_value": None if result is None else result.value,
        "last_reject": None if result is None else result.diagnostics.get("reject_reason"),
    }
