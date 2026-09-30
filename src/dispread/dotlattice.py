"""Punktraster-Homographie fuer die 16-stellige LCD-Anzeige.

Alle Werte fuer Guetegrenzen sind Vorabwerte aus den Aufstellungen vom
2026-09-29. Unklare Rasterlagen werden abgelehnt.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

_PITCH = 25.0
_PH = _PITCH / 6.0
_TOP = 160.0 / 9.0
_PV = 160.0 / 9.0
# Quadecken bezeichnen wie in rectify die Mittelpunkte der Randpixel.
# CharGrid-Grenzen und Punktabstaende bleiben kontinuierlich bei 400/160.
_CORNERS = np.float32([[[0, 0], [399, 0], [399, 159], [0, 159]]])
_MIN_ASSIGNED = 70  # Vorabwert, aus den Aufstellungen vom 2026-09-29.
_MAX_RMS_COLS = 0.2  # Vorabwert, aus den Aufstellungen vom 2026-09-29.
_MAX_RMS_ROWS = 0.25  # Vorabwert, aus den Aufstellungen vom 2026-09-29.
_SAME_QUAD_PX = 3.0  # Vorabwert, aus den Aufstellungen vom 2026-09-29.
_MIN_ASSIGNMENT_MARGIN = 5  # Vorabwert, aus den Aufstellungen vom 2026-09-29.


@dataclass(frozen=True)
class LatticeFit:
    quad: list[list[float]]
    n_dots: int
    n_assigned: int
    rms_cols: float
    rms_rows: float
    cells: tuple[int, ...]
    row_bias: tuple[float, ...]
    cell_bias: tuple[float, ...]
    assigned_points: tuple[tuple[float, float], ...] = ()
    rejected_points: tuple[tuple[float, float], ...] = ()


def _lat(c: np.ndarray, r: np.ndarray) -> np.ndarray:
    return np.column_stack(((c + 0.5) * _PH, _TOP + (r + 0.5) * _PV)).astype(np.float32)


def _warp_points(points: np.ndarray, h: np.ndarray) -> np.ndarray:
    return cv2.perspectiveTransform(points.astype(np.float32)[None], h)[0]


def _assignment(src: np.ndarray, h: np.ndarray, col_tol: float = 0.3, row_tol: float = 0.4):
    target = _warp_points(src, h)
    col = target[:, 0] / _PH - 0.5
    row = (target[:, 1] - _TOP) / _PV - 0.5
    c, r = np.rint(col), np.rint(row)
    ok = (
        (np.abs(col - c) < col_tol)
        & (np.abs(row - r) < row_tol)
        & (r >= 0)
        & (r <= 6)
        & (c >= 0)
        & (c < 96)
        & ((c % 6) != 5)
    )
    return ok, c.astype(int), r.astype(int)


def _plus_coverage(ok: np.ndarray, c: np.ndarray, r: np.ndarray) -> int:
    """Zaehlt verschiedene Treffer des stets vorhandenen Pluszeichens."""
    wanted = {(2, 1), (2, 2), (2, 4), (2, 5)} | {(i, 3) for i in range(5)}
    return len(wanted.intersection(zip(c[ok].tolist(), r[ok].tolist(), strict=True)))


def _plus_shape(ok: np.ndarray, c: np.ndarray, r: np.ndarray) -> bool:
    found = set(zip(c[ok].tolist(), r[ok].tolist(), strict=True))
    vertical = sum((2, row) in found for row in (1, 2, 4, 5))
    return any((i, 3) in found for i in (0, 1)) and any(
        (i, 3) in found for i in (3, 4)
    ) and vertical >= 3


def _plus_anchors(
    src: np.ndarray, left: float, width: float, *, pitch_scale: float = 1.0,
) -> list[tuple[int, np.ndarray, np.ndarray, np.ndarray]]:
    """Sucht Plus-Mitte und lokale Punktperioden direkt im Quellbild."""
    anchors = []
    approximate_pitch = pitch_scale * width / (1.2 * 96)
    row_tolerance2 = max(1.8, 0.38 * approximate_pitch) ** 2
    stem_tolerance2 = max(2.5, 0.5 * approximate_pitch) ** 2
    possible = src[src[:, 0] < left + 0.17 * width]
    for left_dot in possible:
        delta = src - left_dot
        ends = delta[
            (delta[:, 0] >= 4 * 0.6 * approximate_pitch)
            & (delta[:, 0] <= 4 * 1.8 * approximate_pitch)
            & (np.abs(delta[:, 1]) <= max(8, 1.2 * approximate_pitch))
        ]
        for span in ends:
            hv = span / 4
            if not 0.7 * approximate_pitch <= hv[0] <= 1.7 * approximate_pitch:
                continue
            p = left_dot + span / 2
            row = p + np.arange(-2, 3)[:, None] * hv
            row_hits = np.min(np.sum((row[:, None] - src[None]) ** 2, axis=2), axis=1) <= row_tolerance2
            if row_hits.sum() < 3:
                continue
            delta = src - p
            one_step = delta[
                (delta[:, 1] >= 0.55 * approximate_pitch)
                & (delta[:, 1] <= 3.2 * approximate_pitch)
                & (np.abs(delta[:, 0]) <= 0.6 * approximate_pitch)
            ]
            two_steps = delta[
                (delta[:, 1] >= 1.1 * approximate_pitch)
                & (delta[:, 1] <= 6.4 * approximate_pitch)
                & (np.abs(delta[:, 0]) <= 1.0 * approximate_pitch)
            ] / 2
            vs = np.concatenate((one_step, two_steps))
            for vv in vs:
                if vv[1] < 0.85 * approximate_pitch:
                    continue
                stem = p + np.array([-2, -1, 1, 2])[:, None] * vv
                stem_hits = np.min(np.sum((stem[:, None] - src[None]) ** 2, axis=2), axis=1) <= stem_tolerance2
                score = int(row_hits.sum() + stem_hits.sum())
                if score >= 6 and stem_hits.sum() >= 3:
                    offsets = np.float32([(-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (0, -2), (0, -1), (0, 1), (0, 2)])
                    predicted = p + offsets[:, :1] * hv + offsets[:, 1:] * vv
                    distances = np.sum((predicted[:, None] - src[None]) ** 2, axis=2)
                    nearest = np.argmin(distances, axis=1)
                    hit = distances[np.arange(9), nearest] <= stem_tolerance2
                    design = np.column_stack((np.ones(hit.sum()), offsets[hit]))
                    fitted = np.linalg.lstsq(design, src[nearest[hit]], rcond=None)[0]
                    anchors.append((score, fitted[0], fitted[1], fitted[2]))
    anchors.sort(key=lambda item: item[0], reverse=True)
    distinct = []
    for item in anchors:
        if all(np.linalg.norm(item[1] - old[1]) > max(2, 0.4 * approximate_pitch) for old in distinct):
            distinct.append(item)
        if len(distinct) >= 8:
            break
    return distinct


def _has_minus_sign(src: np.ndarray, left: float, width: float) -> bool:
    """Erkennt einen linken Querbalken ohne senkrechte Plus-Punkte."""
    pitch = width / (1.2 * 96)
    sign_left = left + width / 12
    sign_dots = src[(src[:, 0] >= sign_left) & (src[:, 0] <= sign_left + 5 * pitch)]
    if len(sign_dots) < 5:
        return False
    sign_middle = float(np.median(sign_dots[:, 1]))
    possible = src[src[:, 0] < left + 0.17 * width]
    lines: list[tuple[np.ndarray, float]] = []
    for start in possible:
        delta = src - start
        ends = delta[
            (delta[:, 0] >= 4 * 0.6 * pitch)
            & (delta[:, 0] <= 4 * 1.8 * pitch)
            & (np.abs(delta[:, 1]) <= max(8, 1.2 * pitch))
        ]
        for span in ends:
            step = span / 4
            if not 0.7 * pitch <= step[0] <= 1.7 * pitch:
                continue
            row = start + np.arange(5)[:, None] * step
            hits = np.min(np.sum((row[:, None] - src[None]) ** 2, axis=2), axis=1)
            center = start + 2 * step
            # Nur die Vorzeichenzelle ist beweiskraeftig. Waagerechte
            # Punktreihen spaeterer Ziffern duerfen kein Minus belegen.
            if (np.count_nonzero(hits <= max(1.8, 0.38 * pitch) ** 2) == 5
                    and center[0] < left + 0.13 * width
                    and abs(center[1] - sign_middle) <= 2 * pitch):
                lines.append((center, float(step[0])))
    if not lines:
        return False
    for center, step in lines:
        delta = src - center
        stem = (
            (np.abs(delta[:, 0]) <= 0.6 * step)
            & (np.abs(delta[:, 1]) >= 0.7 * step)
            & (np.abs(delta[:, 1]) <= 4 * step)
        )
        if np.any(stem):
            return False
    return True


def _quad_score(src: np.ndarray, quad: np.ndarray) -> float:
    h = cv2.getPerspectiveTransform(quad.astype(np.float32), _CORNERS[0])
    target = _warp_points(src, h)
    col = target[:, 0] / _PH - 0.5
    row = (target[:, 1] - _TOP) / _PV - 0.5
    c, r = np.rint(col), np.rint(row)
    valid = (c >= 0) & (c < 96) & ((c % 6) != 5) & (r >= 0) & (r <= 6)
    dc = (col - c) / 0.18
    dr = (row - r) / 0.23
    return float(np.exp(-0.5 * (dc[valid] ** 2 + dr[valid] ** 2)).sum())


def _optimize_quad(src: np.ndarray, start: np.ndarray) -> np.ndarray:
    """Lokale Subpixel-Suche der Quadecken anhand aller Quellbildpunkte."""
    q = start.astype(np.float32).copy()
    best = _quad_score(src, q)
    for step in (2.0, 1.0, 0.5, 0.25):
        for _ in range(2):
            changed = False
            for corner in range(4):
                for axis in range(2):
                    for direction in (-1, 1):
                        trial = q.copy()
                        trial[corner, axis] += direction * step
                        if not cv2.isContourConvex(trial):
                            continue
                        score = _quad_score(src, trial)
                        if score > best + 1e-4:
                            best = score
                            q = trial
                            changed = True
            if not changed:
                break
    return q


def _quad_distance(a: LatticeFit, b: LatticeFit) -> float:
    return float(np.max(np.linalg.norm(np.asarray(a.quad) - np.asarray(b.quad), axis=1)))


def _select_unambiguous_fit(
    viable: list[LatticeFit], *, same_quad_px: float = _SAME_QUAD_PX,
) -> LatticeFit | str:
    """Gruppiert gleiche Endlagen und verwirft knapp konkurrierende Lagen."""
    if not viable:
        return "keine_startlage"
    ordered = sorted(viable, key=lambda fit: fit.n_assigned, reverse=True)
    representatives: list[LatticeFit] = []
    for fit in ordered:
        if not any(_quad_distance(fit, rep) <= same_quad_px for rep in representatives):
            representatives.append(fit)
    winner = representatives[0]
    # Gegen alle Originalfits pruefen: eine nichttransitive Nahekette darf
    # keinen von der Siegerlage verschiedenen Konkurrenten verstecken.
    for fit in ordered[1:]:
        if _quad_distance(winner, fit) > same_quad_px:
            if winner.n_assigned - fit.n_assigned < _MIN_ASSIGNMENT_MARGIN:
                return "startlage_mehrdeutig"
    return winner


def _source_candidates(image_bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    height, width = image_bgr.shape[:2]
    lo, hi = quad.min(axis=0), quad.max(axis=0)
    pad = 0.1 * (hi - lo)
    x0, y0 = np.maximum(np.floor(lo - pad).astype(int), 0)
    x1, y1 = np.minimum(np.ceil(hi + pad).astype(int), (width, height))
    if x1 <= x0 or y1 <= y0:
        return np.empty((0, 2), np.float32)
    gray = cv2.cvtColor(image_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.float32)
    smooth = cv2.GaussianBlur(gray, (0, 0), 0.7)
    depth = cv2.GaussianBlur(gray, (0, 0), 6) - smooth
    yy, xx = np.where((smooth == cv2.erode(smooth, np.ones((3, 3), np.uint8))) & (depth > 8))
    return np.column_stack((xx + x0, yy + y0)).astype(np.float32)


def _lattice_candidates(image_bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Erkennt LCD-Punkte im entzerrten Bild und gibt Quellkoordinaten zurueck."""
    scale = 2
    w, hh = 400 * scale, 160 * scale
    hr = cv2.getPerspectiveTransform(
        quad.astype(np.float32),
        np.float32([[0, 0], [w - 1, 0], [w - 1, hh - 1], [0, hh - 1]]),
    )
    gray = cv2.cvtColor(
        cv2.warpPerspective(image_bgr, hr, (w, hh), flags=cv2.INTER_CUBIC),
        cv2.COLOR_BGR2GRAY,
    ).astype(np.float32)
    sx = (w - 1) / np.linalg.norm(quad[1] - quad[0])
    sy = (hh - 1) / np.linalg.norm(quad[3] - quad[0])
    if not (0.5 < sx < 30 and 0.5 < sy < 30):
        return np.empty((0, 2), np.float32)
    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=0.7 * sx, sigmaY=0.7 * sy)
    depth = cv2.GaussianBlur(gray, (0, 0), sigmaX=6 * sx, sigmaY=6 * sy) - blurred
    kernel = np.ones((int(2 * round(1.2 * sy) + 1), int(2 * round(1.2 * sx) + 1)), np.uint8)
    minimum = cv2.erode(blurred, kernel)
    yy, xx = np.where((blurred == minimum) & (depth > 8))
    return _warp_points(np.column_stack((xx, yy)).astype(np.float32), np.linalg.inv(hr))


def refine(
    image_bgr: np.ndarray,
    h_init: np.ndarray,
    *,
    empty_cells: tuple[int, ...] = (),
) -> LatticeFit | str:
    """Verfeinert eine grobe Quellbild-zu-Raster-Homographie iterativ."""
    h = np.asarray(h_init, np.float64).copy()
    if h.shape != (3, 3) or not np.isfinite(h).all() or abs(np.linalg.det(h)) < 1e-12:
        return "keine_startlage"
    src = np.empty((0, 2), np.float32)
    for _ in range(10):
        quad = _warp_points(_CORNERS[0], np.linalg.inv(h))
        if not np.isfinite(quad).all():
            return "anpassung_divergiert"
        src = _lattice_candidates(image_bgr, quad)
        if len(src) < _MIN_ASSIGNED:
            return "zu_wenige_punkte"
        ok, c, r = _assignment(src, h)
        if np.count_nonzero(ok) < _MIN_ASSIGNED:
            return "zu_wenige_punkte"
        h_new, _ = cv2.findHomography(src[ok], _lat(c[ok], r[ok]), 0)
        if h_new is None or not np.isfinite(h_new).all():
            return "anpassung_divergiert"
        delta = float(np.max(np.linalg.norm(_warp_points(_CORNERS[0], np.linalg.inv(h_new)) - quad, axis=1)))
        h = h_new
        if delta < 0.005:
            break
    quad = _warp_points(_CORNERS[0], np.linalg.inv(h))
    src = _lattice_candidates(image_bgr, quad)
    return _evaluate_fit(image_bgr, h, src, quad, empty_cells=empty_cells)


def _evaluate_fit(
    image_bgr: np.ndarray,
    h: np.ndarray,
    src: np.ndarray,
    quad: np.ndarray,
    *,
    empty_cells: tuple[int, ...],
    enforce_proxy_limits: bool = True,
) -> LatticeFit | str:
    """Prueft Rasterbelege; Ersatzmass-Grenzen gelten nur bei der Startsuche."""
    ok, c, r = _assignment(src, h)
    if np.count_nonzero(ok) < _MIN_ASSIGNED:
        return "zu_wenige_punkte"
    quad = _warp_points(_CORNERS[0], np.linalg.inv(h))
    source_dots = _source_candidates(image_bgr, quad)
    if len(source_dots) < _MIN_ASSIGNED:
        return "zu_wenige_punkte"
    source_ok, source_c, source_r = _assignment(source_dots, h)
    if not _plus_shape(source_ok, source_c, source_r):
        return "plus_nicht_gefunden"
    target_all = _warp_points(source_dots, h)
    if empty_cells:
        candidate_cell = np.floor(target_all[:, 0] / _PITCH).astype(int)
        local_x = target_all[:, 0] - candidate_cell * _PITCH
        candidate_in_cell = (
            np.isin(candidate_cell, empty_cells)
            & (local_x >= 0)
            & (local_x < _PITCH)
            & (target_all[:, 1] >= _TOP)
            & (target_all[:, 1] <= _TOP + 7 * _PV)
        )
        if np.any(candidate_in_cell) or np.any(source_ok & np.isin(source_c // 6, empty_cells)):
            return "leerzelle_belegt"
    cursor_col = target_all[:, 0] / _PH - 0.5
    cursor_row = (target_all[:, 1] - _TOP) / _PV - 0.5
    cursor_c = np.rint(cursor_col)
    cursor = (
        (np.abs(cursor_col - cursor_c) < 0.3)
        & (np.abs(cursor_row - 7) < 0.4)
        & (cursor_c >= 0)
        & (cursor_c < 96)
        & ((cursor_c % 6) != 5)
    )
    if np.any(cursor):
        return "cursorzeile_belegt"
    cells = tuple(sorted(set((c[ok] // 6).tolist())))
    if 0 not in cells or set(r[ok]) != set(range(7)):
        return "raster_unvollstaendig"
    d = _warp_points(src[ok], h) - _lat(c[ok], r[ok])
    rms_cols = float(np.sqrt(np.mean(d[:, 0] ** 2)) / _PH)
    rms_rows = float(np.sqrt(np.mean(d[:, 1] ** 2)) / _PV)
    if enforce_proxy_limits and (rms_cols > _MAX_RMS_COLS or rms_rows > _MAX_RMS_ROWS):
        return "restfehler_zu_gross"
    row_bias = tuple(float(np.mean(d[r[ok] == i, 1]) / _PV) for i in range(7))
    cell_bias = tuple(float(np.mean(d[(c[ok] // 6) == i, 0]) / _PH) for i in cells)
    if enforce_proxy_limits and max(map(abs, (*row_bias, *cell_bias))) > 0.15:
        return "bias_zu_gross"
    if not np.isfinite(quad).all():
        return "anpassung_divergiert"
    return LatticeFit(
        quad=quad.astype(float).tolist(),
        n_dots=len(src),
        n_assigned=int(ok.sum()),
        rms_cols=rms_cols,
        rms_rows=rms_rows,
        cells=cells,
        row_bias=row_bias,
        cell_bias=cell_bias,
        assigned_points=tuple(map(tuple, src[ok].astype(float).tolist())),
        rejected_points=tuple(map(tuple, src[~ok].astype(float).tolist())),
    )


def evaluate_quad(
    image_bgr: np.ndarray,
    hint_box: tuple[float, float, float, float],
    quad: np.ndarray | list[list[float]],
    *,
    empty_cells: tuple[int, ...] = (),
) -> LatticeFit | str:
    """Prueft ein vorgegebenes Quad, ohne dessen Ecken zu verschieben."""
    if image_bgr is None or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        return "ungueltiges_bild"
    _, _, w, hh = hint_box
    if not all(np.isfinite(v) for v in hint_box) or w <= 0 or hh <= 0:
        return "ungueltige_hinweisbox"
    q = np.asarray(quad, dtype=np.float32)
    if q.shape != (4, 2) or not np.isfinite(q).all() or not cv2.isContourConvex(q):
        return "keine_startlage"
    h = cv2.getPerspectiveTransform(q, _CORNERS[0])
    if not np.isfinite(h).all() or abs(np.linalg.det(h)) < 1e-12:
        return "keine_startlage"
    src = _lattice_candidates(image_bgr, q)
    # Die CLI prueft ein vorgegebenes Quad anschliessend gegen bekannten
    # Zellentext (Pruefung 2j) und check_setup. RMS/Bias sind nur Ersatzmasse
    # der textlosen automatischen Startsuche und koennen korrekte Profile
    # ablehnen; ihre Messwerte bleiben im LatticeFit erhalten.
    return _evaluate_fit(
        image_bgr, h, src, q, empty_cells=empty_cells, enforce_proxy_limits=False,
    )


def fit_lattice(
    image_bgr: np.ndarray,
    hint_box: tuple[float, float, float, float],
    *,
    seeds: list[tuple[tuple[float, float], tuple[int, int]]] | None = None,
    empty_cells: tuple[int, ...] = (),
) -> LatticeFit | str:
    """Findet das Punktraster innerhalb einer normierten Hinweisbox."""
    if image_bgr is None or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        return "ungueltiges_bild"
    x, y, w, hh = hint_box
    if not all(np.isfinite(v) for v in hint_box) or w <= 0 or hh <= 0:
        return "ungueltige_hinweisbox"
    if seeds is not None:
        if len(seeds) != 4:
            return "keine_startlage"
        src = np.float32([item[0] for item in seeds])
        c_r = np.float32([item[1] for item in seeds])
        h = cv2.getPerspectiveTransform(src, _lat(c_r[:, 0], c_r[:, 1]))
        return refine(image_bgr, h, empty_cells=empty_cells)
    return _auto_fit(image_bgr, hint_box, empty_cells=empty_cells)


def _auto_fit(
    image_bgr: np.ndarray,
    hint_box: tuple[float, float, float, float],
    *,
    empty_cells: tuple[int, ...] = (),
) -> LatticeFit | str:
    height, width = image_bgr.shape[:2]
    x, y, w, hh = hint_box
    x0, y0 = max(0, int(x * width)), max(0, int(y * height))
    x1, y1 = min(width, int((x + w) * width)), min(height, int((y + hh) * height))
    point_pitch = (x1 - x0) / (1.2 * 96)
    pixel_scale = point_pitch / 4.5
    if x1 - x0 < 80 or y1 - y0 < 20:
        return "keine_startlage"
    gray = cv2.cvtColor(image_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 30, 90)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 720, threshold=35,
        minLineLength=int((x1 - x0) * 0.35), maxLineGap=round(4 * point_pitch),
    )
    spans = []
    for xx0, yy0, xx1, yy1 in lines[:, 0] if lines is not None else []:
        dx = xx1 - xx0
        if abs(dx) > (x1 - x0) * 0.3:
            slope = (yy1 - yy0) / dx
            if abs(slope) < 0.4:
                spans.append((abs(dx), float(slope), (yy0 + yy1) / 2))
    top_lines = [entry for entry in spans if entry[2] < (y1 - y0) * 0.55]
    top = max(top_lines)[1] if top_lines else (max(spans)[1] if spans else None)
    bottom_lines = [entry for entry in spans if entry[2] > (y1 - y0) * 0.55]
    bottom = max(bottom_lines)[1] if bottom_lines else top
    # Quellbild-Minima mit Tiefe relativ zum lokalen LCD-Hintergrund.
    smooth = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 0.7)
    depth = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 6) - smooth
    minimum = cv2.erode(smooth, np.ones((3, 3), np.uint8))
    yy, xx = np.where((smooth == minimum) & (depth > 8))
    src = np.column_stack((xx + x0, yy + y0)).astype(np.float32)
    if len(src) < _MIN_ASSIGNED:
        return "zu_wenige_punkte"
    anchors = _plus_anchors(src, x0, x1 - x0)
    if not anchors:
        # Die Gruenflaeche kann breiter als das Punktraster sein. Die linke
        # Suchregion bleibt gleich, nur die angenommene Punktperiode sinkt.
        anchors = _plus_anchors(src, x0, x1 - x0, pitch_scale=0.95)
    if not anchors:
        return "vorzeichen_kein_plus" if _has_minus_sign(src, x0, x1 - x0) else "keine_startlage"
    best_anchors = [anchors[0]] + [
        item for item in anchors[1:] if item[0] >= max(8, anchors[0][0] - 1)
    ]
    if any(
        abs(item[1][1] - best_anchors[0][1][1]) > 0.3 * (y1 - y0)
        or abs(item[1][0] - best_anchors[0][1][0]) > 0.3 * (x1 - x0)
        for item in best_anchors[1:]
    ):
        return "startlage_mehrdeutig"
    anchor = min(best_anchors, key=lambda item: item[1][0])
    # Ein Plus mit einem fehlenden Quellbildpunkt darf eine zweite gueltige
    # Displaylage nicht schon vor der Rasterpruefung ausschliessen.
    candidate_anchors = [anchor]
    for item in anchors:
        if item[0] < anchor[0] - 1:
            break
        if all(
            np.linalg.norm(item[1] - old[1]) > max(6 * point_pitch, 0.1 * min(x1 - x0, y1 - y0))
            for old in candidate_anchors
        ):
            candidate_anchors.append(item)
    # Hinweisbox und Kantenrichtung liefern nur die Grobgeometrie. Die
    # Projektionen der Punktkandidaten bestimmen Zeilen- und Spaltenphase.
    bx0 = x0 + (x1 - x0) / 12
    bx1 = x1 - (x1 - x0) / 12
    by0 = y0 + (y1 - y0) / 12
    by1 = y1 - (y1 - y0) / 12
    span = bx1 - bx0
    candidates: list[tuple[float, np.ndarray, int]] = []
    # Das Plus verankert Spalte und Zeile absolut. Die lokale waagerechte
    # und senkrechte Punktperiode begrenzt die linke Kante des Quads.
    average_pitch = (bx1 - bx0) / 96
    top_slopes = [top + dt for dt in (-0.01, 0.0, 0.01)] if top is not None else np.arange(-0.18, 0.081, 0.02)
    for anchor_index, (anchor_score, p, hv, vv) in enumerate(candidate_anchors):
        if not 0.7 * average_pitch <= hv[0] <= 1.55 * average_pitch:
            continue
        for vertical_scale in (0.9, 1.0, 1.1):
            anchor_tl = p - 2.5 * hv - 4.5 * vertical_scale * vv
            anchor_bl = p - 2.5 * hv + 4.5 * vertical_scale * vv
            for st in top_slopes:
                for db in (-0.01, 0.0, 0.01):
                    sb = (bottom if bottom is not None else st) + db
                    for left_shift in (-2.0 * pixel_scale, 0.0, 2.0 * pixel_scale):
                        for up_shift in (-3.0 * pixel_scale, 0.0, 3.0 * pixel_scale):
                            tl = anchor_tl + (left_shift, up_shift)
                            bl = anchor_bl + (left_shift, up_shift)
                            for right_shift in (-4.0 * pixel_scale, 0.0, 4.0 * pixel_scale):
                                for right_edge in (bx1 - 16 * pixel_scale, bx1 - 8 * pixel_scale,
                                                   bx1, bx1 + 8 * pixel_scale):
                                    brx = right_edge + bl[0] - tl[0] + right_shift
                                    q = np.float32([
                                        tl,
                                        [right_edge, tl[1] + st * (right_edge - tl[0])],
                                        [brx, bl[1] + sb * (brx - bl[0])],
                                        bl,
                                    ])
                                    if min(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1])) < 4 * point_pitch:
                                        continue
                                    h = cv2.getPerspectiveTransform(q, _CORNERS[0])
                                    ok, c, r = _assignment(src, h)
                                    plus = _plus_coverage(ok, c, r)
                                    candidates.append((int(ok.sum()) + 8 * plus + 30 * anchor_score, h, anchor_index))
    # Ohne tragfaehigen Plus-Anker wird eine breitere Phasensuche genutzt.
    if not candidates:
        if top is None:
            top = float(anchors[0][2][1] / anchors[0][2][0])
        if bottom is None:
            bottom = top
        for dt in (-0.02, 0.0, 0.02):
            for db in (-0.02, 0.0, 0.02):
                st, sb = top + dt, bottom + db
                if st >= 0:
                    q = np.float32([[bx0, by0], [bx1, by0 + st * span], [bx1, by1], [bx0, by1 - sb * span]])
                else:
                    q = np.float32([[bx0, by0 - st * span], [bx1, by0], [bx1, by1 + sb * span], [bx0, by1]])
                if min(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1])) < 4 * point_pitch:
                    continue
                h = cv2.getPerspectiveTransform(q, _CORNERS[0])
                target = _warp_points(src, h)
                col = target[:, 0] / _PH - 0.5
                row = (target[:, 1] - _TOP) / _PV - 0.5
                # Periodensuche: Reihenphase vor Spaltenphase; die 6. Spalte
                # jeder Zelle ist leer und das Plus in Zelle 0 verankert links.
                for dy in np.arange(-1.5, 1.51, 0.15):
                    rr = row + dy
                    r = np.rint(rr).astype(int)
                    row_ok = (np.abs(rr - r) < 0.35) & (r >= 0) & (r <= 6)
                    if row_ok.sum() < _MIN_ASSIGNED:
                        continue
                    for dx in np.arange(-12, 12.01, 0.25):
                        cc = col + dx
                        c = np.rint(cc).astype(int)
                        ok = row_ok & (np.abs(cc - c) < 0.28) & (c >= 0) & (c < 96) & ((c % 6) != 5)
                        n = int(ok.sum())
                        if n < _MIN_ASSIGNED:
                            continue
                        plus = _plus_coverage(ok, c, r)
                        if plus < 5:
                            continue
                        score = n + 8 * plus + (20 if _plus_shape(ok, c, r) else 0)
                        candidates.append((score, np.array([[1, 0, dx * _PH], [0, 1, dy * _PV], [0, 0, 1]]) @ h, 0))
    if not candidates:
        return "vorzeichen_kein_plus" if _has_minus_sign(src, x0, x1 - x0) else "keine_startlage"
    candidates.sort(key=lambda item: item[0], reverse=True)
    attempted_per_anchor = [0] * len(candidate_anchors)
    attempted_quads: list[np.ndarray] = []
    viable: list[LatticeFit] = []
    for limit in (8, 16):
        for _, h, anchor_index in candidates:
            if attempted_per_anchor[anchor_index] >= limit:
                continue
            q = _warp_points(_CORNERS[0], np.linalg.inv(h))
            if any(np.max(np.linalg.norm(q - old, axis=1)) < 3 * pixel_scale for old in attempted_quads):
                continue
            attempted_quads.append(q)
            attempted_per_anchor[anchor_index] += 1
            optimized = _optimize_quad(src, q)
            result = refine(
                image_bgr, cv2.getPerspectiveTransform(optimized, _CORNERS[0]),
                empty_cells=empty_cells,
            )
            if isinstance(result, LatticeFit):
                fitted_h = cv2.getPerspectiveTransform(np.asarray(result.quad, np.float32), _CORNERS[0])
                ok, c, r = _assignment(src, fitted_h)
                if _plus_coverage(ok, c, r) >= 6 and _plus_shape(ok, c, r):
                    anchor = candidate_anchors[anchor_index]
                    if np.linalg.norm(np.asarray(result.quad)[0] - anchor[1] + 2.5 * anchor[2] + 4.5 * anchor[3]) < 9 * pixel_scale:
                        viable.append(result)
            if all(count >= limit for count in attempted_per_anchor):
                break
        if _select_unambiguous_fit(viable, same_quad_px=_SAME_QUAD_PX * pixel_scale) == "startlage_mehrdeutig":
            break
        if viable and len(candidate_anchors) == 1:
            break
    selected = _select_unambiguous_fit(viable, same_quad_px=_SAME_QUAD_PX * pixel_scale)
    if selected == "keine_startlage" and _has_minus_sign(src, x0, x1 - x0):
        return "vorzeichen_kein_plus"
    return selected
