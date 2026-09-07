"""Synthetische 7-Segment-Anzeigen erzeugen.

Zweck: die Pipeline ohne Kamera und ohne Pruefling entwickeln und testen, mit
bekanntem Sollwert. Die Stoerungen (Rauschen, Glanz, Perspektive, Unschaerfe,
Multiplex-Teilsegmente) bilden die in Konzept.md §9 genannten Faelle nachweisbar
ab.

Die Zeitbasis ist SYNTHETIC und traegt damit ausdruecklich keine Zeitaussage -
aus diesen Frames darf keine Latenzangabe abgeleitet werden.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import cv2
import numpy as np

from dispread.frames.types import Capability, Frame
from dispread.layout import DIGIT_SEGMENTS, DisplayLayout
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics

#: Farben eines typischen roten LED-Displays (BGR).
PANEL_BGR = (18, 18, 22)
SEGMENT_ON_BGR = (60, 60, 245)
SEGMENT_OFF_BGR = (30, 30, 45)


def _segment_rects(
    x: int, y: int, w: int, h: int, thickness: int, inset: int
) -> dict[str, tuple[int, int, int, int]]:
    """Segmentrechtecke einer Ziffernzelle als (x1, y1, x2, y2)."""
    mid = y + h // 2
    ht = thickness // 2
    left, right = x + inset, x + w - inset
    top, bottom = y + inset, y + h - inset
    return {
        "a": (left + thickness, top, right - thickness, top + thickness),
        "g": (left + thickness, mid - ht, right - thickness, mid + ht),
        "d": (left + thickness, bottom - thickness, right - thickness, bottom),
        "f": (left, top + thickness, left + thickness, mid - ht),
        "b": (right - thickness, top + thickness, right, mid - ht),
        "e": (left, mid + ht, left + thickness, bottom - thickness),
        "c": (right - thickness, mid + ht, right, bottom - thickness),
    }


def render_display(
    value: float,
    layout: DisplayLayout,
    size: tuple[int, int] = (480, 200),
    *,
    dropout_segments: set[tuple[int, str]] | None = None,
    overflow: bool = False,
) -> tuple[np.ndarray, str, tuple[int, int, int, int]]:
    """Eine Anzeige zeichnen.

    Gibt (Bild, angezeigter Text, Ziffernbereich) zurueck. Der Ziffernbereich
    (x, y, w, h) umfasst Vorzeichen- und Ziffernstellen, aber nicht die
    Einheitenzeile - er entspricht dem, was der Bediener nach Konzept.md §4 als
    ROI bestaetigt und was der Rectifier an den Leser weitergibt.

    `dropout_segments` laesst einzelne Segmente aus - das simuliert einen
    Segmentausfall bzw. Multiplex-Flimmern und ist der Fall, an dem sich die
    Ablehnung bewaehren muss.
    """
    width, height = size
    img = np.zeros((height, width, 3), np.uint8)
    img[:] = PANEL_BGR
    dropout = dropout_segments or set()

    # Zeichenflaeche mit Rand; unten Platz fuer die Einheit.
    pad_x = int(width * 0.04)
    pad_y = int(height * 0.10)
    unit_h = int(height * 0.22) if layout.unit else 0
    area_w = width - 2 * pad_x
    area_h = height - 2 * pad_y - unit_h

    cell_w = area_w / layout.n_cells
    thickness = max(2, int(cell_w * layout.thickness_ratio))
    inset = max(1, int(cell_w * layout.inset_ratio))

    if overflow:
        # Ueberlauf: alle Ziffernstellen zeigen nur das Mittelsegment.
        digits_text = "-" * layout.digits
    else:
        digits_text = layout.format_value(value)

    # Vorzeichenstelle.
    if layout.has_sign:
        sw = int(cell_w * layout.sign_cell_ratio)
        sx = pad_x
        if value < 0 and not overflow:
            bar_y = pad_y + area_h // 2
            cv2.rectangle(
                img,
                (sx + inset, bar_y - thickness // 2),
                (sx + sw - inset, bar_y + thickness // 2),
                SEGMENT_ON_BGR,
                -1,
            )

    # Ziffernstellen.
    x_start = pad_x + (cell_w * layout.sign_cell_ratio if layout.has_sign else 0.0)
    dp_index = layout.decimal_point_index()
    for i, ch in enumerate(digits_text):
        cx = int(x_start + i * cell_w)
        rects = _segment_rects(cx, pad_y, int(cell_w), area_h, thickness, inset)
        active = frozenset("g") if ch == "-" else DIGIT_SEGMENTS.get(ch, frozenset())
        for seg, (x1, y1, x2, y2) in rects.items():
            on = seg in active and (i, seg) not in dropout
            cv2.rectangle(img, (x1, y1), (x2, y2), SEGMENT_ON_BGR if on else SEGMENT_OFF_BGR, -1)
        # Dezimalpunkt nach dieser Stelle.
        if dp_index is not None and i == dp_index and not overflow:
            r = max(2, thickness // 2)
            cv2.circle(img, (cx + int(cell_w) - inset // 2, pad_y + area_h - r), r, SEGMENT_ON_BGR, -1)

    if layout.unit:
        cv2.putText(
            img,
            layout.unit,
            (width - pad_x - int(cell_w * 0.9), height - pad_y // 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            unit_h / 40.0,
            SEGMENT_ON_BGR,
            2,
            cv2.LINE_AA,
        )

    if overflow:
        shown = "-" * layout.digits
    else:
        decimals = layout.decimals if layout.decimals is not None else 0
        shown = f"{value:.{decimals}f}"

    # Der Ziffernbereich ist genau die Flaeche, in der oben gezeichnet wurde.
    # Innerhalb davon stimmt das Raster mit DisplayLayout.cell_boxes ueberein.
    digit_area = (pad_x, pad_y, int(round(area_w)), int(area_h))
    return img, shown, digit_area


def _distort(
    img: np.ndarray,
    rng: np.random.Generator,
    *,
    noise: float,
    glare: float,
    perspective: float,
    blur: float,
) -> np.ndarray:
    out = img
    h, w = out.shape[:2]

    if perspective > 0:
        d = perspective / 100.0 * min(w, h)
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = src + rng.uniform(-d, d, src.shape).astype(np.float32)
        m = cv2.getPerspectiveTransform(src, dst)
        out = cv2.warpPerspective(out, m, (w, h), borderValue=PANEL_BGR)

    if glare > 0:
        overlay = np.zeros_like(out, np.float32)
        cx, cy = rng.uniform(0.2, 0.8) * w, rng.uniform(0.2, 0.8) * h
        axes = (int(w * rng.uniform(0.12, 0.3)), int(h * rng.uniform(0.08, 0.2)))
        cv2.ellipse(overlay, (int(cx), int(cy)), axes, rng.uniform(0, 180), 0, 360, (255, 255, 255), -1)
        overlay = cv2.GaussianBlur(overlay, (0, 0), sigmaX=w * 0.03)
        out = np.clip(out.astype(np.float32) + overlay * glare, 0, 255).astype(np.uint8)

    if blur > 0:
        out = cv2.GaussianBlur(out, (0, 0), sigmaX=max(0.1, blur))

    if noise > 0:
        n = rng.normal(0, noise * 40.0, out.shape)
        out = np.clip(out.astype(np.float32) + n, 0, 255).astype(np.uint8)

    return out


class SyntheticSource:
    """Generierte Anzeigen mit bekanntem Sollwert.

    Der Sollwert steht in `raw_metadata["ground_truth"]`. Damit koennen
    Beispiele und Tests die Erkennung gegen die Wahrheit auswerten, ohne dass
    die Pipeline selbst je den Sollwert sieht.
    """

    def __init__(
        self,
        *,
        kind: str = "seven-seg",
        digits: int = 5,
        decimals: int = 2,
        unit: str = "N",
        noise: float = 0.0,
        glare: float = 0.0,
        perspective: float = 0.0,
        blur: float = 0.0,
        count: int | None = None,
        seed: int = 0,
        size: tuple[int, int] = (480, 200),
    ) -> None:
        if kind != "seven-seg":
            raise ValueError(f"unbekannte synthetische Anzeigeart {kind!r}")
        self.layout = DisplayLayout(digits=digits, decimals=decimals, unit=unit)
        self.noise = noise
        self.glare = glare
        self.perspective = perspective
        self.blur = blur
        self.count = count
        self.seed = seed
        self.size = size
        self._rng = np.random.default_rng(seed)
        self._seq = 0

    # -- FrameSource ------------------------------------------------------
    def open(self) -> None:
        self._rng = np.random.default_rng(self.seed)
        self._seq = 0

    def close(self) -> None:
        pass

    @property
    def source_id(self) -> str:
        return f"synthetic:seven-seg:seed{self.seed}"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.SEEK})

    def describe(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "timebase": TimeBaseKind.SYNTHETIC.value,
            "carries_time_information": False,
            "layout": self.layout.to_dict(),
            "distortions": {
                "noise": self.noise,
                "glare": self.glare,
                "perspective": self.perspective,
                "blur": self.blur,
            },
            "seed": self.seed,
        }

    def values(self) -> Iterator[float]:
        """Wertfolge: Rampe mit Vorzeichenwechsel und echten Spruengen.

        Echte Spruenge gehoeren bewusst dazu - Konzept.md §7 verlangt, dass
        Plausibilitaetsregeln sie nicht stillschweigend glaetten. Ein Test kann
        das nur pruefen, wenn Spruenge im Material vorkommen.
        """
        i = 0
        while self.count is None or i < self.count:
            phase = i % 40
            if phase < 15:
                yield round(-12.5 + phase * 1.7, 2)
            elif phase < 20:
                yield 0.0
            elif phase == 20:
                yield 87.31  # echter Sprung
            elif phase < 30:
                yield round(87.31 - (phase - 20) * 3.3, 2)
            else:
                yield round(-0.05 * (phase - 30), 2)
            i += 1

    def frames(self) -> Iterator[Frame]:
        for value in self.values():
            img, text, digit_area = render_display(value, self.layout, self.size)
            img = _distort(
                img,
                self._rng,
                noise=self.noise,
                glare=self.glare,
                perspective=self.perspective,
                blur=self.blur,
            )
            self._seq += 1
            yield Frame(
                frame_sequence=self._seq,
                image=img,
                capture_timestamp=Timestamp(
                    value_ns=time.monotonic_ns(),
                    base=TimeBaseKind.SYNTHETIC,
                    semantics=TimestampSemantics.UNKNOWN,
                ),
                source_id=self.source_id,
                raw_metadata={
                    "ground_truth": {
                        "value": value,
                        "unit": self.layout.unit,
                        "text": text,
                    },
                    # Der Ziffernbereich, den der Bediener bestaetigen wuerde.
                    # Bei Perspektivverzerrung stimmt er nicht mehr exakt -
                    # dann muss die Lokalisierung ihn wiederfinden.
                    "digit_area": digit_area,
                },
            )
