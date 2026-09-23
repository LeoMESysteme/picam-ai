"""Vierpunktquad der beleuchteten LCD-Glasflaeche finden (Ernte Phase 1,
Nachbesserung zu Task 3, docs/superpowers/plans/2026-09-23-ernte-phase1.md).

`dispread.workbench.vision.lcd_quad_in_region` trennt Glas vom Rahmen ueber
eine reine Saettigungsschwelle - das reicht bei den beiden bislang gemessenen
Geraeten (siehe dortige Docstring-Messwerte), scheitert aber am GSV-2AS: sein
Gehaeuse ist selbst gesaettigt-blaeulich. Gemessen an
`var/diagnostics/offset-norm-101440/frames/frame_000412.jpg`: die Hinweisbox
hat Hue-Mittel 93 (Gehaeuse dominiert die Flaeche), waehrend das Zentrum
(das Glas) Hue~43 (gelbgruen) hat - eine reine Saettigungsmaske haengt dort
das gesamte Gehaeuse an das Quad. Diese Funktion engt den Farbton daher
zusaetzlich auf den am Zentrum der Hinweisbox gemessenen Wert ein (der
Bediener zielt mit der Hinweisbox auf die Anzeige, nicht das Gehaeuse), statt
den Farbton eines Geraetetyps hart zu codieren.

`minAreaRect` (wie `lcd_quad_in_region` es nutzt) passt eine gedrehte
RECHTECK-Hypothese an - das bildet ein perspektivisches Trapez (Kamera nicht
frontal, siehe Task 6: 30/45 Grad) grundsaetzlich nicht ab. Diese Funktion
passt stattdessen ein allgemeines Vierpunktquad an: `approxPolyDP` auf die
Konturhuelle, dann Sub-Pixel-Verfeinerung durch Geradenausgleich je Kante
(die vier Kantenlinien werden geschnitten, das ergibt die Eckpunkte).

Ein schlechter Fit liefert `None`, nie eine geratene Naeherung - dieselbe
Regel wie bei `lcd_quad_in_region`.
"""

from __future__ import annotations

import cv2
import numpy as np

from dispread.detect import Quad
from dispread.rectify import _order_quad

#: Mindestsaettigung/-helligkeit, damit ein Pixel ueberhaupt als leuchtendes
#: Glas in Frage kommt - unvalidierte Vorabdefaults, wie bei
#: `lcd_quad_in_region` (dortiges OQ-36 gilt sinngemaess auch hier).
_MIN_SATURATION = 60
_MIN_VALUE = 40
#: Hue-Toleranz in OpenCV-Hue-Einheiten (0..179, zirkulaer) um den am Zentrum
#: gemessenen Farbton.
_HUE_TOLERANCE = 18
#: Seitenlaenge des Zentrumspatches relativ zur Hinweisbox, aus dem der
#: Referenzfarbton geschaetzt wird.
_CENTER_FRACTION = 0.2
#: Flaechenverhaeltnis Quad/rohe Kontur, ausserhalb dessen der Fit verworfen
#: wird (Task-Vorgabe).
_AREA_RATIO_RANGE = (0.9, 1.1)
#: Mindestzahl Konturpunkte je Kante, damit ein Geradenausgleich dort
#: ueberhaupt sinnvoll ist.
_MIN_EDGE_POINTS = 8


def glass_quad_in_region(image_bgr: np.ndarray, hint_box: tuple[float, float, float, float]) -> Quad | None:
    """Vierpunktquad der leuchtenden Glasflaeche innerhalb `hint_box`.

    `hint_box` ist die normierte achsparallele Box `[x, y, w, h]`, wie bei
    `manual_roi`/`lcd_quad_in_region`. Rueckgabe ist ein geordnetes Vierpunktquad
    (oben-links, oben-rechts, unten-rechts, unten-links - `_order_quad`-Ordnung)
    in vollen Quellbildpixeln, oder `None`, wenn kein plausibles Glas gefunden
    wird. Es wird nicht geraten: ein knapper/zweideutiger Fund liefert `None`.
    """
    height, width = image_bgr.shape[:2]
    hint_x, hint_y, hint_w, hint_h = hint_box
    left, top = int(round(hint_x * width)), int(round(hint_y * height))
    right, bottom = int(round((hint_x + hint_w) * width)), int(round((hint_y + hint_h) * height))
    if right - left < 8 or bottom - top < 8:
        return None

    region = image_bgr[top:bottom, left:right]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    region_h, region_w = region.shape[:2]

    center_hue = _center_hue(hsv, region_w, region_h)
    if center_hue is None:
        return None

    mask = _hue_mask(hsv, center_hue)
    contour = _center_touching_contour(mask, region_w / 2.0, region_h / 2.0)
    if contour is None:
        return None

    quad_local = _fit_quad(contour)
    if quad_local is None:
        return None

    contour_area = cv2.contourArea(contour)
    quad_area = cv2.contourArea(quad_local.astype(np.float32))
    if contour_area <= 0 or quad_area <= 0:
        return None
    ratio = quad_area / contour_area
    lo, hi = _AREA_RATIO_RANGE
    if not (lo <= ratio <= hi):
        return None
    if not cv2.isContourConvex(np.round(quad_local).astype(np.int32)):
        return None

    quad_full = quad_local + np.array([left, top], dtype=np.float64)
    ordered = _order_quad([tuple(p) for p in quad_full])
    return tuple(tuple(float(v) for v in p) for p in ordered)


def _center_hue(hsv: np.ndarray, region_w: float, region_h: float) -> float | None:
    """Referenzfarbton aus einem Patch um das Zentrum der Hinweisbox."""
    cx_i, cy_i = int(region_w / 2.0), int(region_h / 2.0)
    half_w = max(2, int(region_w * _CENTER_FRACTION / 2))
    half_h = max(2, int(region_h * _CENTER_FRACTION / 2))
    patch = hsv[max(0, cy_i - half_h) : cy_i + half_h, max(0, cx_i - half_w) : cx_i + half_w]
    if patch.size == 0:
        return None
    center_sat = float(np.median(patch[:, :, 1]))
    if center_sat < _MIN_SATURATION:
        # Zentrum selbst nicht gesaettigt genug - kein Glas erkennbar, nicht raten.
        return None
    return float(np.median(patch[:, :, 0]))


def _hue_mask(hsv: np.ndarray, center_hue: float) -> np.ndarray:
    hue = hsv[:, :, 0].astype(np.int16)
    diff = np.abs(hue - int(round(center_hue)))
    hue_diff = np.minimum(diff, 180 - diff)
    mask = (
        (hue_diff <= _HUE_TOLERANCE) & (hsv[:, :, 1] >= _MIN_SATURATION) & (hsv[:, :, 2] >= _MIN_VALUE)
    ).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return mask


def _center_touching_contour(mask: np.ndarray, cx: float, cy: float) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    # Die Hinweisbox zielt per Konstruktion auf die Anzeige (Bedienervorgabe) -
    # die richtige Komponente ist die, die das Zentrum beruehrt, nicht
    # zwingend die flaechenmaessig groesste (das Gehaeuse kann groesser sein).
    touching = [c for c in contours if cv2.pointPolygonTest(c, (cx, cy), False) >= 0]
    if not touching:
        return None
    return max(touching, key=cv2.contourArea)


def _fit_quad(contour: np.ndarray) -> np.ndarray | None:
    """Vierpunktquad ueber `approxPolyDP` auf die Konturhuelle, danach
    Sub-Pixel-Verfeinerung je Kante."""
    hull = cv2.convexHull(contour)
    perimeter = cv2.arcLength(hull, True)
    if perimeter <= 0:
        return None

    approx = None
    for frac in np.linspace(0.005, 0.25, 40):
        candidate = cv2.approxPolyDP(hull, frac * perimeter, True)
        if len(candidate) == 4:
            approx = candidate.reshape(4, 2).astype(np.float64)
            break
    if approx is None:
        return None

    corners = _order_quad([tuple(p) for p in approx]).astype(np.float64)
    refined = _refine_corners(contour.reshape(-1, 2).astype(np.float64), corners)
    return refined if refined is not None else corners


def _point_segment_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ap, ab = p - a, b - a
    ab_len2 = float(np.dot(ab, ab))
    if ab_len2 == 0:
        return float(np.linalg.norm(ap))
    t = float(np.clip(np.dot(ap, ab) / ab_len2, 0.0, 1.0))
    return float(np.linalg.norm(p - (a + t * ab)))


def _line_intersection(
    line_a: tuple[float, float, float, float], line_b: tuple[float, float, float, float]
) -> tuple[float, float] | None:
    vx1, vy1, x1, y1 = line_a
    vx2, vy2, x2, y2 = line_b
    denom = vx1 * vy2 - vy1 * vx2
    if abs(denom) < 1e-9:
        return None
    t = ((x2 - x1) * vy2 - (y2 - y1) * vx2) / denom
    return x1 + t * vx1, y1 + t * vy1


def _refine_corners(points: np.ndarray, corners: np.ndarray) -> np.ndarray | None:
    """Konturpunkte den vier Kanten des Naeherungsquads zuordnen, je Kante
    eine Gerade ausgleichen und benachbarte Geraden schneiden - liefert
    Sub-Pixel-Ecken und bildet ein echtes Trapez ab (anders als
    `minAreaRect`)."""
    edges = [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    buckets: list[list[np.ndarray]] = [[] for _ in range(4)]
    for p in points:
        distances = [_point_segment_distance(p, a, b) for a, b in edges]
        buckets[int(np.argmin(distances))].append(p)

    lines: list[tuple[float, float, float, float]] = []
    for bucket in buckets:
        if len(bucket) < _MIN_EDGE_POINTS:
            return None
        pts = np.array(bucket, dtype=np.float32)
        vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).ravel()
        lines.append((float(vx), float(vy), float(x0), float(y0)))

    refined = []
    for i in range(4):
        corner = _line_intersection(lines[i - 1], lines[i])
        if corner is None:
            return None
        refined.append(corner)
    refined_arr = np.array(refined, dtype=np.float64)

    # Grobe Plausibilitaet: eine entartete (fast parallele) Kantenkonstellation
    # kann Schnittpunkte weit ausserhalb des Naeherungsquads liefern - dann
    # lieber die unverfeinerte Naeherung behalten als eine schlechte
    # Extrapolation.
    max_shift = float(np.max(np.linalg.norm(refined_arr - corners, axis=1)))
    if max_shift > 0.15 * cv2.arcLength(corners.astype(np.float32), True):
        return None
    return refined_arr
