"""Vorpruefung einer Display-Aufstellung aus Standbild und Punktraster-Anpassung.

Die Ampelwerte sind Vorabwerte. Kennzahlen werden unveraendert mitgegeben,
damit der Befund bei spaeterer Kalibrierung erneut bewertet werden kann.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from dispread.charcells import CharGrid, source_dot_column_px
from dispread.frame_alignment import estimate_quad_shift
from dispread.layout import CharLayout
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.ocr.dotmatrix_sampling import SHIFTS, SampledImage, sample_image
from dispread.rectify import rectify

# Vorabwerte, aus den Aufstellungen vom 2026-09-29.
TARGET_SIZE = (400, 160)
GRID = CharGrid(16, 0.0, 25.0, 160.0 / 9.0, 160.0)
POINT_CONTRAST_ERROR = 15.0
POINT_CONTRAST_WARNING = 17.0
EDGE_WARNING = 6.0
EDGE_ERROR = 8.0
EDGE_OCCUPIED_WARNING = 16.0
EDGE_OCCUPIED_ERROR = 20.0
EDGE_BACKGROUND_PERCENTILE = 99.0
EDGE_BLANK_RELATIVE_HIGHPASS = 0.5
EDGE_BLANK_ABSOLUTE_HIGHPASS = 10.0
SATURATED_ERROR = 0.02
GLARE_BRIGHTNESS_ABOVE_BACKGROUND = 35.0
GLARE_BLOB_AREA_ERROR = 100
RESOLUTION_ERROR_PX = 2.6
RESOLUTION_WARNING_PX = 3.2
RMS_COLS_ERROR = 0.25
RMS_ROWS_ERROR = 0.3
ASSIGNED_FRACTION_ERROR = 0.8
BIAS_WARNING = 0.08
STABILITY_MIN_ELAPSED_S = 30.0
STABILITY_ERROR_PX = 0.5
STABILITY_WARNING_PX = 0.2
BORDER_DARK_RATIO_ERROR = 0.7
BLANK_CELLS = (8, 13, 14, 15)


@dataclass(frozen=True)
class CheckResult:
    status: str | None
    metrics: dict[str, Any]
    cells: tuple[int, ...] = ()
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {'status': self.status, 'metrics': self.metrics}
        if self.cells:
            result['cells'] = list(self.cells)
        if self.reason is not None:
            result['reason'] = self.reason
        return result


@dataclass(frozen=True)
class SetupChecks:
    overall: str
    checks: dict[str, CheckResult] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {'overall': self.overall, 'checks': {name: check.to_dict() for name, check in self.checks.items()}}


def _gray(image_bgr: np.ndarray) -> np.ndarray:
    if image_bgr is None or image_bgr.dtype != np.uint8 or image_bgr.ndim not in (2, 3):
        raise ValueError('Standbild muss ein lesbares uint8-Graubild oder BGR-Bild sein')
    if image_bgr.ndim == 2:
        return image_bgr
    if image_bgr.shape[2] != 3:
        raise ValueError('Standbild muss drei BGR-Kanaele haben')
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)


def _point_contrast(gray: np.ndarray, quad: np.ndarray) -> float:
    # Claudes Handmass: Quellbildpixel und Isotropie in Quellbildkoordinaten.
    floating = gray.astype(np.float32)
    signal = cv2.GaussianBlur(floating, (0, 0), 6)
    signal -= cv2.GaussianBlur(floating, (0, 0), 0.8)
    mask = np.zeros(gray.shape, np.uint8)
    cv2.fillConvexPoly(mask, np.round(quad).astype(np.int32), 255)
    values = signal[mask > 0]
    if not values.size:
        raise ValueError('Quad liegt ausserhalb des Standbilds')
    return float(np.percentile(values, 99))


def _edge_check(warped_gray: np.ndarray) -> CheckResult:
    # Ein heller Morphologie-Schluss fuellt dunkle Glyphenpunkte. Kandidaten
    # fuer Leerzellen kommen unabhaengig vom Leser aus dem Hochpasssignal.
    gray = warped_gray.astype(np.float32)
    highpass = cv2.GaussianBlur(gray, (0, 0), 5) - cv2.GaussianBlur(gray, (0, 0), 0.8)
    peak = [float(np.percentile(highpass[25:140, k * 25:(k + 1) * 25], 99)) for k in range(16)]
    median_peak = float(np.median(sorted(peak)[4:12]))
    blank_limit = max(EDGE_BLANK_ABSOLUTE_HIGHPASS, EDGE_BLANK_RELATIVE_HIGHPASS * median_peak)
    background = cv2.morphologyEx(warped_gray, cv2.MORPH_CLOSE, np.ones((5, 9), np.uint8)).astype(np.float32)
    horizontal_step = np.abs(background[25:140, 8:] - background[25:140, :-8])
    scores = []
    for k in range(16):
        # Beide Werte eines Paares liegen mit 2 px Abstand zum Zellrand.
        # Sonst fliesst die Nachbarglyphe in die Leerzellenpruefung ein.
        region = horizontal_step[:, 25 * k + 2:25 * (k + 1) - 10]
        scores.append(float(np.max(np.percentile(region, 75, axis=0))))
    # Fuer belegte Zellen: obere Helligkeitshuelse entlang der Punktzeilen.
    # Die Addition des Hochpasses hebt dunkle Glyphen an; eine breite
    # Spiegelkante bleibt als Hintergrundstufe sichtbar. Der hohe Perzentil-
    # Wert nimmt die hellen Luecken zwischen den Punktzeilen.
    envelope = np.percentile((gray + highpass)[25:140], EDGE_BACKGROUND_PERCENTILE, axis=0)
    envelope = cv2.GaussianBlur(envelope[None].astype(np.float32), (0, 0), 1)[0]
    step = np.abs(envelope[8:] - envelope[:-8])
    occupied_scores = []
    for k in range(16):
        values = step[k * 25 + 2:(k + 1) * 25 - 10]
        occupied_scores.append(float(np.max(values)))
    flagged = tuple(k for k in range(16) if (
        scores[k] > EDGE_WARNING if peak[k] < blank_limit
        else occupied_scores[k] > EDGE_OCCUPIED_WARNING
    ))
    severe = any((scores[k] > EDGE_ERROR if peak[k] < blank_limit
                  else occupied_scores[k] > EDGE_OCCUPIED_ERROR) for k in flagged)
    status = 'FEHLER' if severe else 'WARNUNG' if flagged else 'OK'
    return CheckResult(status, {'cell_step': scores, 'cell_occupied_step': occupied_scores,
                                'cell_highpass': peak, 'blank_limit': blank_limit,
                                'max_blank_step': max((scores[k] for k in flagged if peak[k] < blank_limit), default=0.0)},
                       flagged)


def _border_check(sampled: SampledImage) -> CheckResult:
    """Sucht dunkle, vom Rahmen verdeckte aeussere Punktreihen in Leerzellen."""
    raw = sampled.raw[:, SHIFTS.index((0, 0)), :].reshape(16, 8, 5)
    ratios: dict[int, dict[str, float]] = {}
    flagged: list[int] = []
    # Zelle 0 traegt normalerweise das Plus. Dessen Querstrich betrifft nur
    # eine Zeile; der Median der Randspalte kann dennoch geprueft werden.
    # Die Randzeilen vergleichen wir dort nur, wenn die Zelle innen leer ist.
    first_inner = raw[0, 1:7, 1:5]
    first_blank = np.percentile(first_inner, 10) >= 0.9 * np.median(first_inner)
    for cell in (0, *BLANK_CELLS):
        dots = raw[cell]
        interior = max(1.0, float(np.median(dots[1:6, :])))
        measures = {} if cell == 0 and not first_blank else {
            'row_0': float(np.median(dots[0, :])) / interior,
            'row_6': float(np.median(dots[6, :])) / interior,
        }
        if cell == 0:
            measures['column_0'] = float(np.median(dots[:, 0])) / max(
                1.0, float(np.median(dots[:, 1:3])))
        if cell == 15:
            measures['column_4'] = float(np.median(dots[:, 4])) / max(
                1.0, float(np.median(dots[:, 2:4])))
        ratios[cell] = measures
        if min(measures.values()) < BORDER_DARK_RATIO_ERROR:
            flagged.append(cell)
    minimum = min(value for measures in ratios.values() for value in measures.values())
    return CheckResult('FEHLER' if flagged else 'OK',
                       {'minimum_border_ratio': minimum, 'border_ratios': ratios}, tuple(flagged))


def diagnose_reader(frames: Sequence[np.ndarray], quad: list[list[float]],
                    template_path: Path, template_sha256: str) -> CheckResult:
    """Liest Standbilder mit geprueften Vorlagen; nutzt keinen Sollwert."""
    if not frames:
        raise ValueError('Mindestens ein Standbild ist fuer das Gegenlesen erforderlich')
    reader = DotMatrixReader.from_file(Path(template_path), template_sha256)
    layout = CharLayout(grid=GRID, unit='')
    reasons: dict[str, int] = {}
    read_count = 0
    for frame in frames:
        crop = rectify(frame, quad, target_size=TARGET_SIZE).image
        result = reader.read(crop, layout)
        if result.value is not None:
            read_count += 1
        else:
            reason = str(result.diagnostics.get('reject_reason') or 'unbekannt')
            reasons[reason] = reasons.get(reason, 0) + 1
    count = len(frames)
    severe_rejections = reasons.get('format', 0) + reasons.get('zelle_unbekannt', 0)
    return CheckResult('WARNUNG' if severe_rejections > count / 2 else 'OK',
                       {'frames': count, 'read_count': read_count,
                        'read_rate': read_count / count, 'rejection_reasons': reasons})


def _glare_check(warped_gray: np.ndarray) -> CheckResult:
    saturated = float((warped_gray >= 250).mean())
    background = float(np.median(warped_gray[20:145]))
    bright = (warped_gray[20:145, :225] > background + GLARE_BRIGHTNESS_ABOVE_BACKGROUND).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(bright)
    blob_area = int(stats[1:, cv2.CC_STAT_AREA].max()) if n > 1 else 0
    status = 'FEHLER' if saturated > SATURATED_ERROR or blob_area >= GLARE_BLOB_AREA_ERROR else 'OK'
    return CheckResult(status, {'saturated_fraction': saturated, 'bright_blob_area_px': blob_area})


def _raster_check(fit: Any) -> CheckResult:
    assigned = fit.n_assigned / fit.n_dots if fit.n_dots else 0.0
    max_bias = max((abs(float(v)) for v in (*fit.row_bias, *fit.cell_bias)), default=0.0)
    metrics = {'n_dots': fit.n_dots, 'n_assigned': fit.n_assigned, 'assigned_fraction': assigned,
               'rms_cols': fit.rms_cols, 'rms_rows': fit.rms_rows, 'cells': list(fit.cells),
               'row_bias': list(fit.row_bias), 'cell_bias': list(fit.cell_bias), 'max_abs_bias': max_bias}
    if fit.rms_cols > RMS_COLS_ERROR or fit.rms_rows > RMS_ROWS_ERROR or assigned < ASSIGNED_FRACTION_ERROR:
        status = 'FEHLER'
    elif max_bias > BIAS_WARNING:
        status = 'WARNUNG'
    else:
        status = 'OK'
    return CheckResult(status, metrics)


def _stability_check(image_bgr: np.ndarray, second: np.ndarray | None,
                     elapsed_s: float | None, quad: list[list[float]]) -> CheckResult:
    if second is None:
        return CheckResult(None, {'elapsed_s': None, 'max_corner_shift_px': None}, reason='nicht_durchgefuehrt')
    if elapsed_s is None or elapsed_s < STABILITY_MIN_ELAPSED_S:
        return CheckResult('FEHLER', {'elapsed_s': elapsed_s, 'max_corner_shift_px': None},
                           reason='abstand_zu_kurz')
    _gray(second)
    estimate = estimate_quad_shift(image_bgr, second, quad)
    shift = estimate.max_corner_shift_px if estimate.reliable else None
    metrics = {'elapsed_s': elapsed_s, 'max_corner_shift_px': shift, 'reliable': estimate.reliable}
    if not estimate.reliable:
        return CheckResult('WARNUNG', metrics, reason=estimate.reason)
    status = 'FEHLER' if shift > STABILITY_ERROR_PX else 'WARNUNG' if shift > STABILITY_WARNING_PX else 'OK'
    return CheckResult(status, metrics)


def check_setup(image_bgr: np.ndarray, lattice_fit: Any, *,
                stability_image_bgr: np.ndarray | None = None,
                stability_elapsed_s: float | None = None) -> SetupChecks:
    """Prueft eine Aufstellung; Stabilitaet bleibt optional bis zum zweiten Bild.

    `lattice_fit` folgt dem `LatticeFit`-Vertrag aus `dispread.dotlattice`.
    Eine fehlende Kennzahl wird nicht mit einem Vorgabewert ersetzt.
    """
    gray = _gray(image_bgr)
    quad = np.asarray(lattice_fit.quad, dtype=np.float32)
    if quad.shape != (4, 2) or not np.isfinite(quad).all():
        raise ValueError('Quad muss vier endliche Eckpunkte enthalten')
    quality = (lattice_fit.n_dots, lattice_fit.n_assigned, lattice_fit.rms_cols,
               lattice_fit.rms_rows, *lattice_fit.row_bias, *lattice_fit.cell_bias)
    if not np.isfinite(quality).all() or lattice_fit.rms_cols < 0 or lattice_fit.rms_rows < 0:
        raise ValueError('Ungueltige Kennzahlen im Rasterbefund')
    if lattice_fit.n_dots < 0 or lattice_fit.n_assigned < 0 or lattice_fit.n_assigned > lattice_fit.n_dots:
        raise ValueError('Ungueltige Punktzahlen im Rasterbefund')
    warped = rectify(image_bgr, lattice_fit.quad, target_size=TARGET_SIZE).image
    warped_gray = _gray(warped)
    sampled = sample_image(warped_gray, GRID, tuple(range(16)))
    contrast = _point_contrast(gray, quad)
    contrast_status = ('FEHLER' if contrast < POINT_CONTRAST_ERROR else
                       'WARNUNG' if contrast < POINT_CONTRAST_WARNING else 'OK')
    resolution = float(source_dot_column_px(GRID, lattice_fit.quad, TARGET_SIZE))
    resolution_status = ('FEHLER' if resolution < RESOLUTION_ERROR_PX else
                         'WARNUNG' if resolution < RESOLUTION_WARNING_PX else 'OK')
    checks = {
        'kontrast': CheckResult(contrast_status, {'punktkontrast': contrast,
                                                 'leser_kontrast': sampled.contrast}),
        'kanten': _edge_check(warped_gray),
        'rahmen': _border_check(sampled),
        'glanz': _glare_check(warped_gray),
        'aufloesung': CheckResult(resolution_status, {'min_source_dot_column_px': resolution}),
        'raster': _raster_check(lattice_fit),
        'stabilitaet': _stability_check(image_bgr, stability_image_bgr,
                                      stability_elapsed_s, lattice_fit.quad),
    }
    statuses = {check.status for check in checks.values()}
    overall = 'FEHLER' if 'FEHLER' in statuses else 'WARNUNG' if 'WARNUNG' in statuses else 'OK'
    return SetupChecks(overall, checks)
