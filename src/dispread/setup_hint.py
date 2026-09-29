"""Hinweisbereich aus gruener Displaybeleuchtung vorsichtig vorschlagen."""

from __future__ import annotations

import cv2
import numpy as np

# Vorabwerte, aus den Aufstellungen vom 2026-09-29. Fehlt die gruenliche
# Flaeche, wird eine Bediener-Hinweisbox verlangt statt eine Lage zu raten.
GREEN_HUE_MIN = 30
GREEN_HUE_MAX = 90
MIN_SATURATION = 45
MIN_VALUE = 45
MIN_AREA_FRACTION = 0.002
MIN_WIDTH_FRACTION = 0.08
MIN_HEIGHT_FRACTION = 0.02
HINT_MARGIN_FRACTION = 0.10
# Vorabwerte, aus den Aufstellungen vom 2026-09-29: Die gruen leuchtende
# Glasflaeche ist vertikal groesser als die 7 Punktzeilen. Diese Anteile
# beschneiden den Farbkontur-Vorschlag auf den inneren Punktbereich.
HINT_TOP_TRIM_FRACTION = 0.10
HINT_BOTTOM_TRIM_FRACTION = 0.20
DOT_DEPTH_MIN = 8.0
DOT_COMPONENTS_MIN = 8
DOT_COMPONENT_AREA_MAX = 100


def _has_dot_structure(gray: np.ndarray, x: int, y: int, w: int, h: int) -> bool:
    """Kleine dunkle Inseln im Inneren der Farbkontur suchen."""
    margin_x = min(max(5, round(w * 0.02)), w // 4)
    margin_y = min(max(5, round(h * 0.02)), h // 4)
    inner = gray[y + margin_y:y + h - margin_y, x + margin_x:x + w - margin_x]
    if inner.size == 0:
        return False
    smooth = cv2.GaussianBlur(inner, (0, 0), 3).astype(np.float32)
    fine = cv2.GaussianBlur(inner, (0, 0), 0.7).astype(np.float32)
    binary = (smooth - fine > DOT_DEPTH_MIN).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    dot_count = sum(1 for area in stats[1:count, cv2.CC_STAT_AREA] if 1 <= area <= DOT_COMPONENT_AREA_MAX)
    return dot_count >= DOT_COMPONENTS_MIN


def find_green_hint_box(image_bgr: np.ndarray) -> tuple[float, float, float, float] | None:
    """Normierte Box `(x,y,w,h)` oder `None` bei fehlender Gruenflaeche."""
    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        return None
    height, width = image_bgr.shape[:2]
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    mask = cv2.inRange(
        hsv,
        (GREEN_HUE_MIN, MIN_SATURATION, MIN_VALUE),
        (GREEN_HUE_MAX, 255, 255),
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if (
            cv2.contourArea(contour) >= MIN_AREA_FRACTION * width * height
            and w >= MIN_WIDTH_FRACTION * width
            and h >= MIN_HEIGHT_FRACTION * height
            and _has_dot_structure(gray, x, y, w, h)
        ):
            candidates.append((w * h, x, y, w, h))
    if not candidates:
        return None
    _, x, y, w, h = max(candidates)
    mx, my = HINT_MARGIN_FRACTION * w, HINT_MARGIN_FRACTION * h
    x0 = max(0.0, x - mx)
    y0 = max(0.0, y - my)
    x1 = min(float(width), x + w + mx)
    y1 = min(float(height), y + h + my)
    span_y = y1 - y0
    y0 += HINT_TOP_TRIM_FRACTION * span_y
    y1 -= HINT_BOTTOM_TRIM_FRACTION * span_y
    return x0 / width, y0 / height, (x1 - x0) / width, (y1 - y0) / height
