"""Vorpruefung einer Display-Aufstellung aus Standbild und Punktraster-Anpassung.

Die Ampelwerte sind Vorabwerte. Kennzahlen werden unveraendert mitgegeben,
damit der Befund bei spaeterer Kalibrierung erneut bewertet werden kann.

Die Kantenpruefung vergleicht in Leerzellen Hintergrundwerte im Abstand
von 8 px. Vor einer belegten Nachbarzelle bleibt das rechte Vergleichspixel
mindestens 6 px vor der Zellgrenze, damit Schliessung und optische
Unschaerfe der Nachbarglyphe keine Spiegelkante vortaeuschen; vor einer
Leerzelle und in Zelle 15 gilt das bisherige Fenster (3 px), damit an
Grenzen zwischen Leerzellen keine Erkennungsluecke entsteht. Belegte Zellen nutzen eine eigene
Helligkeitshuelse; die Vorabgrenzen bleiben fuer beide Masse getrennt.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from dispread.charcells import CharGrid, source_dot_column_px
from dispread.frame_alignment import estimate_quad_shift
from dispread.gsv2as_cell_text import last_place_step
from dispread.lattice_offsets import FULL, HALVES, max_abs_offset, measure_offsets, median_offsets
from dispread.layout import CharLayout
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.ocr.dotmatrix_sampling import SHIFTS, SampledImage, background_opening, raw_cell_depths, sample_image
from dispread.rectify import rectify
from dispread.sensors import SensorDefinition, get_sensor
from dispread.sensors.definitions import CHAR_NUMBER_FORMAT_RULE

_DEFAULT_SENSOR = get_sensor()
_DISPLAY = _DEFAULT_SENSOR.display

# Vorabwerte, aus den Aufstellungen vom 2026-09-29.
TARGET_SIZE = _DISPLAY.lattice.target_size
GRID = CharGrid.from_display(_DISPLAY)
POINT_CONTRAST_ERROR = 15.0
POINT_CONTRAST_WARNING = 17.0
# Vorabgrenze 2026-10-28: gute Aufstellungen p80 >=112, dunkle <=98.
# Keine obere Grenze aus diesen Daten ableitbar; Saettigung prueft glanz.
EXPOSURE_WARNING_BELOW = 105.0
EDGE_WARNING = 6.0
EDGE_ERROR = 8.0
EDGE_OCCUPIED_WARNING = 16.0
EDGE_OCCUPIED_ERROR = 20.0
EDGE_BACKGROUND_PERCENTILE = 99.0
EDGE_BLANK_RELATIVE_HIGHPASS = 0.5
EDGE_BLANK_ABSOLUTE_HIGHPASS = 10.0
# Exklusives Fenster fuer x vor einer belegten Nachbarzelle: x+8 endet bei
# 19, also 6 px vor Zellgrenze 25. Die Schliessungsbreite 9 wirkt +/-4 px,
# dazu kommt optische Unschaerfe. Gemessen an sc3-6, ab1/ab2 und den
# Live-Bildern 2026-10-28 (110248Z, 113959Z, 114104Z): Nachbareffekt
# entfaellt, ab2 bleibt als WARNUNG sichtbar.
EDGE_BLANK_STEP_WINDOW = (2, 12)
# Vor einer Leerzelle oder am Ende: bisheriges Fenster bis 25 - 10 (x+8 bis
# 3 px vor der Grenze), damit dort keine neue Erkennungsluecke entsteht.
EDGE_BLANK_STEP_FREE_RIGHT = 10
SATURATED_ERROR = 0.02
GLARE_BRIGHTNESS_ABOVE_BACKGROUND = 35.0
GLARE_BLOB_AREA_ERROR = 100
RESOLUTION_ERROR_PX = 2.6
RESOLUTION_WARNING_PX = 3.2
RMS_COLS_ERROR = 0.25
RMS_ROWS_ERROR = 0.3
ASSIGNED_FRACTION_ERROR = 0.8
BIAS_WARNING = 0.08
OFFSET_WARNING = 0.15  # Vorabwert: Punktspalten bzw. Punktzeilen.
OFFSET_ERROR = 0.25  # Vorabwert: Punktspalten bzw. Punktzeilen.
OFFSET_MIN_CELLS = 3
STABILITY_MIN_ELAPSED_S = 30.0
STABILITY_ERROR_PX = 0.5
STABILITY_WARNING_PX = 0.2
BORDER_DARK_RATIO_ERROR = 0.7
BLANK_CELLS = _DISPLAY.empty_cells


def _glass_defects(image: np.ndarray, quad, grid: CharGrid, blank_cells: Sequence[int]) -> list[dict]:
    """Kleine helle/dunkle Residuen ausschliesslich in bekannten Leerzellen.

    Vorabgrenzen in Grauwerten: Oeffnungsresiduum > 4 UND > 8 ueber
    lokalem Glaspegel (15-px-Median), dunkles Schlussresiduum > 8.
    Der Median wird innerhalb jeder Leerzelle geschaetzt: dort gibt es
    keine regulaeren dunklen Punkte, die ihn nach unten ziehen. Belegte
    Nachbarzellen gehen auch in die Morphologie nicht ein. In belegten
    Zellen waeren helle Punktzwischenraeume nicht von Kratzern trennbar.
    Gauss sigma=0,5 unterdrueckt Einzelpixelrauschen.
    Komponenten von mindestens 3 Pixeln bis 1 Punktflaeche und maximal
    1,5 Punktabstaenden je Achse; keine langen Rahmen-/Reflexkanten.
    Die bilduebergreifende Pruefung verlangt zusaetzlich einen ausreichend
    grossen Anker (0,1 Punktflaechen), um Rauschspitzen auszuschliessen.
    Das ist ein Hinweis, keine Fehlerdiagnose und keine Lesefreigabe.
    """
    gray = _gray(rectify(image, quad, target_size=TARGET_SIZE).image)
    col = grid.pitch / (grid.dot_columns + grid.gap_columns)
    row = (grid.bottom - grid.top) / 8
    kernel = np.ones((2 * int(row / 2) + 1, 2 * int(col / 2) + 1), np.uint8)
    defects = []
    for cell in blank_cells:
        x0 = max(0, int(grid.left + cell * grid.pitch))
        x1 = min(gray.shape[1], int(grid.left + (cell + 1) * grid.pitch))
        y0 = max(0, int(grid.top))
        y1 = min(gray.shape[0], int(grid.bottom))
        region = gray[y0:y1, x0:x1]
        if not region.size:
            continue
        smooth = cv2.GaussianBlur(region.astype(np.float32), (0, 0), 0.5)
        glass = cv2.medianBlur(region, 15).astype(np.float32)
        bright = smooth - background_opening(smooth, grid)
        dark = cv2.morphologyEx(smooth, cv2.MORPH_CLOSE, kernel) - smooth
        for kind, signal in (('hell', bright), ('dunkel', dark)):
            eligible = signal > (4.0 if kind == 'hell' else 8.0)
            if kind == 'hell':
                eligible &= smooth - glass > 8.0
            # Erst nach der Schaetzung die Suchraender ausnehmen; sonst
            # veraendert die Randfortsetzung den Median neben dem Kratzer.
            mask = np.zeros(region.shape, np.uint8)
            interior = np.s_[int(grid.top + 0.25 * row) - y0:int(grid.bottom - 0.25 * row) - y0, 2:-2]
            mask[interior] = eligible[interior]
            n, labels, stats, centres = cv2.connectedComponentsWithStats(mask)
            for label in range(1, n):
                _, _, width, height, area = stats[label]
                if not (3 <= area <= col * row
                        and width <= 1.5 * col and height <= 1.5 * row):
                    continue
                x, y = centres[label] + [x0, y0]
                defects.append({
                    'cell': cell, 'kind': kind, 'area_px': int(area),
                    'dot_position': [float((x - grid.left - cell * grid.pitch) / col - 0.5),
                                     float((y - grid.top) / row - 0.5)],
                    'rectified': [float(x), float(y)],
                    'strength': float(signal[labels == label].max()),
                })
    return defects


def display_defect_check(images: Sequence[np.ndarray], quad, *, grid: CharGrid = GRID,
                         cell_text: str | None = None) -> CheckResult:
    """Nur ortsfeste Befunde in ALLEN Standbildern desselben Setup-Versuchs.

    Zuordnung je Art/Zelle innerhalb 0,35 Punktspalten und 0,2 Punktzeilen
    zu einem festen Anker; kein Wandern durch paarweise Verkettung.
    Mindestens ein Bild muss einen Anker >= 0,1 Punktflaechen liefern.
    In jedem weiteren Bild genuegen 3 zusammenhaengende Residualpixel an
    dieser Stelle: Rauschen darf einen echten Kratzer fragmentieren,
    fehlende oder wandernde Stoerungen gelten weiter nicht als ortsfest.
    Beide Arten nur in Pflicht-Leerzellen 8/13-15 und expliziten Leerzeichen
    des Setup-Zellentexts. Dieser muss fuer alle Standbilder gelten;
    wechselnde/unbekannte Zellen bleiben '?', niemals Leerzeichen.
    """
    from dispread.live.texts import DISPLAY_DEFECT_HINT

    if not images:
        raise ValueError('Displayfehlerpruefung braucht mindestens ein Standbild')
    blank_cells = tuple(sorted({cell for cell in BLANK_CELLS if cell < grid.n_cells}
                               | {i for i, ch in enumerate(cell_text or '') if ch == ' ' and i < grid.n_cells}))
    observations = [_glass_defects(image, quad, grid, blank_cells) for image in images]
    min_anchor_area = 0.1 * grid.pitch / (grid.dot_columns + grid.gap_columns) * (grid.bottom - grid.top) / 8

    def same_position(a, b):
        return (a['cell'] == b['cell'] and a['kind'] == b['kind']
                and abs(a['dot_position'][0] - b['dot_position'][0]) <= 0.35
                and abs(a['dot_position'][1] - b['dot_position'][1]) <= 0.2)

    fixed = []
    for defect in (d for frame in observations for d in frame if d['area_px'] >= min_anchor_area):
        if any(same_position(defect, d) for d in fixed):
            continue
        matches = [[d for d in frame if same_position(defect, d)] for frame in observations]
        if all(matches):
            fixed.append({**defect, 'strength': min(max(d['strength'] for d in frame) for frame in matches)})
    return CheckResult('WARNUNG' if fixed else 'OK', {'stills': len(images), 'defects': fixed},
                       tuple(sorted({d['cell'] for d in fixed})), DISPLAY_DEFECT_HINT if fixed else None)


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
    pitch = round(GRID.pitch)
    peak = [float(np.percentile(highpass[25:140, k * pitch:(k + 1) * pitch], 99)) for k in range(GRID.n_cells)]
    median_peak = float(np.median(sorted(peak)[4:12]))
    blank_limit = max(EDGE_BLANK_ABSOLUTE_HIGHPASS, EDGE_BLANK_RELATIVE_HIGHPASS * median_peak)
    background = cv2.morphologyEx(warped_gray, cv2.MORPH_CLOSE, np.ones((5, 9), np.uint8)).astype(np.float32)
    horizontal_step = np.abs(background[25:140, 8:] - background[25:140, :-8])
    blank_start, blank_stop = EDGE_BLANK_STEP_WINDOW
    scores = []
    for k in range(GRID.n_cells):
        # Links bleiben 2 px Rand. Rechts mindestens 6 px fuer x+8, aber nur
        # vor einer belegten Nachbarzelle: deren weichgezeichnete Glyphe
        # wuerde sonst in den Befund einfliessen. Vor einer Leerzelle (und in
        # Zelle 15) bleibt das alte Fenster, sonst entstuende dort ein blinder
        # Bereich fuer echte Kanten an der Zellgrenze.
        neighbour_occupied = k < GRID.n_cells - 1 and peak[k + 1] >= blank_limit
        stop = pitch * k + blank_stop if neighbour_occupied else pitch * (k + 1) - EDGE_BLANK_STEP_FREE_RIGHT
        region = horizontal_step[:, pitch * k + blank_start:stop]
        scores.append(float(np.max(np.percentile(region, 75, axis=0))))
    # Fuer belegte Zellen: obere Helligkeitshuelse entlang der Punktzeilen.
    # Die Addition des Hochpasses hebt dunkle Glyphen an; eine breite
    # Spiegelkante bleibt als Hintergrundstufe sichtbar. Der hohe Perzentil-
    # Wert nimmt die hellen Luecken zwischen den Punktzeilen.
    envelope = np.percentile((gray + highpass)[25:140], EDGE_BACKGROUND_PERCENTILE, axis=0)
    envelope = cv2.GaussianBlur(envelope[None].astype(np.float32), (0, 0), 1)[0]
    step = np.abs(envelope[8:] - envelope[:-8])
    occupied_scores = []
    for k in range(GRID.n_cells):
        values = step[k * pitch + 2:(k + 1) * pitch - 10]
        occupied_scores.append(float(np.max(values)))
    flagged = tuple(k for k in range(GRID.n_cells) if (
        scores[k] > EDGE_WARNING if peak[k] < blank_limit
        else occupied_scores[k] > EDGE_OCCUPIED_WARNING
    ))
    severe = any((scores[k] > EDGE_ERROR if peak[k] < blank_limit
                  else occupied_scores[k] > EDGE_OCCUPIED_ERROR) for k in flagged)
    status = 'FEHLER' if severe else 'WARNUNG' if flagged else 'OK'
    details = []
    for k in flagged:
        blank = peak[k] < blank_limit
        value = scores[k] if blank else occupied_scores[k]
        error_limit = EDGE_ERROR if blank else EDGE_OCCUPIED_ERROR
        warning_limit = EDGE_WARNING if blank else EDGE_OCCUPIED_WARNING
        details.append({'cell': k, 'art': 'leer' if blank else 'belegt', 'stufe': value,
                        'status': 'FEHLER' if value > error_limit else 'WARNUNG',
                        'grenze': error_limit if value > error_limit else warning_limit})
    return CheckResult(status, {'cell_step': scores, 'cell_occupied_step': occupied_scores,
                                'cell_highpass': peak, 'blank_limit': blank_limit,
                                'max_blank_step': max((scores[k] for k in flagged if peak[k] < blank_limit), default=0.0),
                                'flagged_cells': details},
                       flagged, _edge_reason(status, details))


# OQ-72: Zellrolle fuer den Bedienertext.
def _cell_position(cell: int) -> str:
    roles = _DISPLAY.roles
    if cell in roles.sign:
        return 'Vorzeichen'
    if cell in roles.number:
        return 'Zahl'
    if cell in roles.separator:
        return 'Trennzelle'
    return 'Einheit' if cell in roles.unit else 'rechts der Einheit'


def _edge_reason(status: str, details: list[dict]) -> str | None:
    """Bedienertext zur Kantenpruefung mit Zellen, Messwert, Grenze und Abhilfe (OQ-72).

    Die Pruefung misst eine Helligkeitsstufe des Glases ueber 8 px. Sie
    unterscheidet nicht, ob ein heller Reflex oder ein dunkler Schatten bzw.
    eine Spiegelung die Kante erzeugt; der Text nennt deshalb beides.
    """
    if status not in ('FEHLER', 'WARNUNG'):
        return None
    parts = []
    for detail in details:
        relation = 'Fehlergrenze' if detail['status'] == 'FEHLER' else 'Warngrenze'
        value = f"{detail['stufe']:.1f}".replace('.', ',')
        parts.append(f"Zelle {detail['cell']} ({_cell_position(detail['cell'])}) mit Stufe {value}, "
                     f"{relation} {detail['grenze']:g}")
    where = '; '.join(parts)
    if status == 'FEHLER':
        return (f'Reflex- oder Schattenkante über der Anzeige: {where}. Licht abschatten, spiegelnde '
                'Gegenstände entfernen oder Kamera leicht drehen, bis keine Kante mehr über den Zellen liegt, '
                'dann neu einrichten')
    return (f'Schwache Reflex- oder Schattenkante: {where}. Im Bild prüfen; besser Licht abschatten '
            'oder Kamerawinkel ändern')


def _border_check(sampled: SampledImage) -> CheckResult:
    """Sucht dunkle, vom Rahmen verdeckte aeussere Punktreihen in Leerzellen."""
    raw = sampled.raw[:, SHIFTS.index((0, 0)), :].reshape(GRID.n_cells, 8, 5)
    ratios: dict[int, dict[str, float]] = {}
    flagged: list[int] = []
    # Zelle 0 traegt normalerweise das Plus. Dessen Querstrich betrifft nur
    # eine Zeile; der Median der Randspalte kann dennoch geprueft werden.
    # Die Randzeilen vergleichen wir dort nur, wenn die Zelle innen leer ist.
    sign = _DISPLAY.anchor.cell
    first_inner = raw[sign, 1:7, 1:5]
    first_blank = np.percentile(first_inner, 10) >= 0.9 * np.median(first_inner)
    for cell in (sign, *BLANK_CELLS):
        dots = raw[cell]
        interior = max(1.0, float(np.median(dots[1:6, :])))
        measures = {} if cell == sign and not first_blank else {
            'row_0': float(np.median(dots[0, :])) / interior,
            'row_6': float(np.median(dots[6, :])) / interior,
        }
        if cell == sign:
            measures['column_0'] = float(np.median(dots[:, 0])) / max(
                1.0, float(np.median(dots[:, 1:3])))
        if cell == GRID.n_cells - 1:
            measures['column_4'] = float(np.median(dots[:, 4])) / max(
                1.0, float(np.median(dots[:, 2:4])))
        ratios[cell] = measures
        if min(measures.values()) < BORDER_DARK_RATIO_ERROR:
            flagged.append(cell)
    minimum = min(value for measures in ratios.values() for value in measures.values())
    return CheckResult('FEHLER' if flagged else 'OK',
                       {'minimum_border_ratio': minimum, 'border_ratios': ratios}, tuple(flagged))


def _reader_frame_reason(diag: dict, reference: str, frame_index: int) -> tuple[str | None, list[dict]]:
    """Gleiche Zell-, Masken- und Restpruefung fuer strikte Lesung und Gegenprobe."""
    cells = diag.get('cells', [])
    masked = [i for i, ch in enumerate(reference) if ch == '?']
    cell_reasons = {'zelle_unbekannt', 'zelle_mehrdeutig'}
    frame_contradictions = [
        {'frame': frame_index, 'cell': i, 'read': cells[i]['text'], 'reference': ch}
        for i, ch in enumerate(reference)
        if ch != '?' and i < len(cells) and cells[i].get('text') is not None and cells[i]['text'] != ch
    ]
    reason = diag.get('reject_reason')
    unaccepted = [i for i, ch in enumerate(reference)
                  if ch != '?' and (i >= len(cells) or cells[i].get('text') is None)]
    if frame_contradictions:
        reason = 'zelle_widerspricht_referenz'
    elif sum(ch != '?' for ch in reference[1:8]) < 5:
        reason = 'zu_wenige_vergleichbare_zellen'
    elif diag.get('blank_cells_ok') is False:
        reason = 'format'
    elif reason is None or reason in cell_reasons or (reason == 'format' and any(
            i < len(cells) and not (cells[i].get('text') or '').isdigit() for i in masked)):
        # Ein Formatfehler zaehlt nur, wenn er von einer maskierten Zelle
        # kommen kann: ungelesen oder als Nicht-Ziffer gelesen (Mischziffer
        # als ' ' oder '.'). Sonst bleibt das Standbild ungelesen.
        if not unaccepted and diag.get('blank_cells_ok') is True:
            reason = None
        else:
            reason = next((cells[i].get('reason') for i in unaccepted
                           if i < len(cells) and cells[i].get('reason')), reason or 'unbekannt')
    return reason, frame_contradictions


#: Hinweis, wenn eine von Hand eingegebene Referenz nur in der letzten Stelle um 1 abweicht.
LAST_PLACE_HINT = 'Letzte Stelle schwankte (±1) – als Schwanken gewertet'
#: Kein einziges Standbild zeigt genau den eingegebenen Wert, alle liegen ±1 in
#: der letzten Stelle daneben. Das kann Schwanken sein, aber auch ein Leser, der
#: benachbarte Ziffern verwechselt - deshalb WARNUNG statt OK (Bestaetigen bleibt
#: moeglich, mit Quittung) und keine angepasste Toleranz.
NEVER_EXACT_CODE = 'letzte_stelle_nie_exakt'
NEVER_EXACT_HINT = 'Kein Standbild zeigt genau den eingegebenen Wert (alle ±1 in der letzten Stelle)'
NEVER_EXACT_ADVICE = 'Prüfen, ob die Anzeige wirklich schwankt – sonst Wert neu eingeben.'
NEVER_EXACT_TOLERANCE = ('Angepasste Toleranz wird nicht angeboten: sie würde dieselben ±1-Lesungen liefern '
                         'und belegt nicht, dass die Anzeige wirklich schwankt.')


def _full_text(cells: list, key: str) -> str | None:
    """Zellen 0-8 als Text, wenn jede Zelle genau ein Zeichen unter `key` traegt."""
    if len(cells) < 9:
        return None
    chars = [cells[i].get(key) for i in range(9)]
    if any(not isinstance(ch, str) or len(ch) != 1 for ch in chars):
        return None
    return ''.join(chars)


def _last_place_note(diag: dict, reference: str, frame_index: int) -> dict | None:
    """Beleg fuer ein Standbild, das nur in der letzten Stelle um genau 1 von der
    von Hand eingegebenen Referenz abweicht. Nur bei voll gelesenem Standbild
    (jede Zelle gelesen, Format und Leerzellen in Ordnung) und Referenz ohne '?'."""
    if '?' in reference or diag.get('reject_reason') is not None or diag.get('blank_cells_ok') is not True:
        return None
    read = _full_text(diag.get('cells', []), 'text')
    step = None if read is None else last_place_step(reference, read)
    if step is None:
        return None
    return {'code': 'letzte_stelle_schwankt', 'frame': frame_index, 'richtung': f'{step:+d}',
            'reference': reference, 'read': read}


def _frame_verdict(diag: dict, reference: str, frame_index: int,
                   reference_kind: str) -> tuple[str | None, list[dict], dict | None]:
    """Wie `_reader_frame_reason`; bei von Hand eingegebener Referenz zaehlt ein
    Standbild, das nur in der letzten Stelle um genau 1 abweicht, als gelesen
    (mit Beleg). Die serielle Referenz gilt je Standbild exakt."""
    reason, contradictions = _reader_frame_reason(diag, reference, frame_index)
    if contradictions and reference_kind == 'eingabe':
        note = _last_place_note(diag, reference, frame_index)
        if note is not None:
            return None, [], note
    return reason, contradictions, None


def _spread_units(reference: str, texts: Sequence[str]) -> int | None:
    """Spannweite (Einheiten der letzten Stelle) der Texte um die Referenz; None,
    wenn ein Text keinen Schritt von hoechstens 1 zur Referenz hat."""
    steps = []
    for text in texts:
        step = 0 if text == reference else last_place_step(reference, text)
        if step is None:
            return None
        steps.append(step)
    return max(steps) - min(steps)


def _last_place_details(notes: list[dict]) -> str:
    return ', '.join(f"Standbild {n['frame'] + 1}: eingegeben {n['reference'][1:8].strip()}, "
                     f"gelesen {n['read'][1:8].strip()}" for n in notes if n.get('code') == 'letzte_stelle_schwankt')


def last_place_hint(notes: list[dict]) -> str:
    """Kurzer Bedienertext mit beiden Werten je betroffenem Standbild."""
    return f'{LAST_PLACE_HINT} ({_last_place_details(notes)}).'


def never_exact_hint(notes: list[dict]) -> str:
    """Bedienertext, wenn kein Standbild den eingegebenen Wert genau zeigt."""
    return f'{NEVER_EXACT_HINT} ({_last_place_details(notes)}). {NEVER_EXACT_ADVICE}'


def diagnose_reader(frames: Sequence[tuple[np.ndarray, str]], quad: list[list[float]],
                    template_path: Path, template_sha256: str, *,
                    reference_kind: str = 'eingabe', definition: SensorDefinition = _DEFAULT_SENSOR) -> CheckResult:
    """Vergleicht Zellentscheidungen mit dem Solltext, ohne Lesewerte zu korrigieren."""
    if not frames:
        raise ValueError('Mindestens ein Standbild ist fuer das Gegenlesen erforderlich')
    reader = DotMatrixReader.from_file(Path(template_path), template_sha256)
    layout = CharLayout.from_definition(definition, grid=GRID)
    generic = definition.display.format.rule == CHAR_NUMBER_FORMAT_RULE
    reasons: dict[str, int] = {}
    masked_cells: list[list[int]] = []
    contradictions: list[dict] = []
    read_count = 0
    observations = []
    verdicts = []
    depths = []
    for frame_index, (frame, reference) in enumerate(frames):
        if len(reference) != layout.classified_cells:
            raise ValueError(f'Gegenlesen braucht {layout.classified_cells} Referenzzellen' if generic
                             else 'Gegenlesen braucht neun Referenzzellen')
        masked = [i for i, ch in enumerate(reference) if ch == '?']
        masked_cells.append(masked)
        crop = rectify(frame, quad, target_size=TARGET_SIZE).image
        result = reader.read(crop, layout)
        diag = result.diagnostics
        if generic:
            cells = diag.get('cells', ())
            frame_contradictions = [
                {'frame': frame_index, 'cell': i, 'read': cell['text'], 'reference': ch}
                for i, (ch, cell) in enumerate(zip(reference, cells, strict=False))
                if cell['text'] not in (None, ch)
            ]
            reason = 'zelle_widerspricht_referenz' if frame_contradictions else diag.get('reject_reason')
            note = None
        else:
            reason, frame_contradictions, note = _frame_verdict(diag, reference, frame_index, reference_kind)
        verdicts.append([reason, frame_contradictions, note])
        observations.append([crop, reference, diag, reason])
        depths.append(raw_cell_depths(sample_image(_gray(crop), GRID, range(layout.classified_cells))).tolist())
    notes = [note for _, _, note in verdicts if note is not None]
    if notes:
        # Schwanken heisst: die Standbilder liegen hoechstens 1 Einheit der letzten
        # Stelle auseinander. Groessere Spannweite (z. B. -1 und +1 zur Referenz)
        # ist kein Schwanken - dann gilt fuer diese Standbilder wieder der Widerspruch.
        entered = notes[0]['reference']
        read_texts = [note['read'] if note is not None else entered
                      for reason, _, note in verdicts if note is not None or reason is None]
        if any(note['reference'] != entered for note in notes) or _spread_units(entered, read_texts) not in (0, 1):
            for index, verdict in enumerate(verdicts):
                if verdict[2] is not None:
                    verdict[0], verdict[1] = _reader_frame_reason(observations[index][2], observations[index][1], index)
                    verdict[2] = None
                    observations[index][3] = verdict[0]
            notes = []
    # Mindestens ein Standbild muss den eingegebenen Wert genau zeigen; sonst ist
    # "Schwanken" nicht belegt (alle gelesen, alle ±1 daneben) - WARNUNG mit
    # Beleg statt OK. Mit ungelesenen Standbildern entscheidet die Gegenprobe
    # der angepassten Toleranz (`_tolerance_proposal`).
    never_exact = bool(notes) and all(reason is None and note is not None for reason, _, note in verdicts)
    for reason, frame_contradictions, _ in verdicts:
        contradictions.extend(frame_contradictions)
        if reason is None:
            read_count += 1
        else:
            reasons[reason] = reasons.get(reason, 0) + 1
    observations = [tuple(observation) for observation in observations]
    count = len(frames)
    status = 'FEHLER' if contradictions else ('OK' if read_count == count and not never_exact else 'WARNUNG')
    metrics = {'frames': count, 'read_count': read_count,
               'read_rate': read_count / count, 'rejection_reasons': reasons,
               'masked_cells': masked_cells, 'contradictions': contradictions}
    if notes:
        # Mit NEVER_EXACT_CODE als eigenem Beleg: er landet wie die anderen ueber
        # `reference_notes` in confirmation.json.
        metrics['notes'] = notes + ([{'code': NEVER_EXACT_CODE, 'reference': notes[0]['reference'],
                                      'frames': [note['frame'] for note in notes]}] if never_exact else [])
    lighting = _lighting_finding(depths)
    if lighting is not None:
        metrics['lighting'] = lighting
        i, j = lighting['edge_between']
        metrics['hinweis'] = (
            f'Ungleichmaessige Beleuchtung auf dem Display (Kontrastsprung zwischen Zelle {i} und {j}, '
            'vermutlich Schatten oder Verschmutzung). Glas reinigen bzw. abschatten und neu einrichten.'
        )
    if never_exact:
        # Alle Standbilder gelesen, nur keins genau: eine angepasste Toleranz
        # liest dasselbe noch einmal und belegt nichts.
        metrics['tolerance'] = {'possible': False, 'factor': None, 'max_d_best': None, 'd_max': None,
                                'reason': NEVER_EXACT_CODE, 'reference_kind': reference_kind}
        metrics['hinweis'] = ' '.join(filter(None, (metrics.get('hinweis'), NEVER_EXACT_TOLERANCE)))
    elif status == 'WARNUNG' and not generic:
        tolerance = _tolerance_proposal(observations, reader, layout, template_path, template_sha256, reference_kind)
        metrics['tolerance'] = tolerance
        if tolerance['possible']:
            hint = (f"Mit angepasster Toleranz x{tolerance['factor']} liest der Leser alle Standbilder "
                    'in Uebereinstimmung mit der Referenz.')
            if reference_kind == 'eingabe':
                hint += (' Referenz von Hand eingegeben; die Anzeige war waehrend der Standbilder '
                         + ('bis auf die letzte Stelle (±1) unveraendert.'
                            if tolerance.get('anzeige_unveraendert', {}).get('letzte_stelle_schwankt')
                            else 'unveraendert.'))
            metrics['hinweis'] = ' '.join(filter(None, (metrics.get('hinweis'), hint)))
    # Belege stehen in metrics['notes'] bzw. tolerance['notes']; die Werkbank zeigt sie
    # beim Bestaetigen, die Pruefungstabelle zeigt den Grund.
    if notes and status == 'OK':
        reason = last_place_hint(notes)
    elif never_exact:
        reason = never_exact_hint(notes)
    else:
        reason = None
    return CheckResult(status, metrics, reason=reason)


def _lighting_finding(depths: list[list[float]]) -> dict | None:
    worst = None
    for values in depths:
        inked = [v for v in values if v >= 0.2]
        if len(inked) < 2:
            continue
        ratio = max(inked) / min(inked)
        # Paare benachbarter Zellen MIT Zeichen; Leer- oder blasse Zellen dazwischen
        # werden uebersprungen, damit die genannte Kante stimmt.
        inked_idx = [i for i, v in enumerate(values) if v >= 0.2]
        pairs = list(zip(inked_idx, inked_idx[1:], strict=False))
        if ratio <= 1.3 or not pairs:
            continue
        edge = max(pairs, key=lambda pair: max(values[i] for i in pair) / min(values[i] for i in pair))
        if worst is None or ratio > worst['max_ratio']:
            worst = {'depths': depths, 'max_ratio': ratio, 'edge_between': list(edge)}
    return worst


def _display_unchanged(observations) -> dict | None:
    """Beste Vermutung je vergleichbarer Zelle 1-7 ueber alle Standbilder; None ohne Lesedaten."""
    references = {reference for _, reference, _, _ in observations}
    if len(references) != 1 or len(observations) < 2:
        return None
    reference = references.pop()
    cells_compared = [i for i in range(1, 8) if reference[i] != '?']
    reads = []
    for _, _, diag, _ in observations:
        cells = diag.get('cells', [])
        if any(i >= len(cells) or not isinstance(cells[i].get('best'), str) for i in cells_compared):
            return None
        reads.append(''.join(cells[i]['best'] for i in cells_compared))
    unchanged = {'unveraendert': len(set(reads)) == 1, 'standbilder': len(reads),
                 'zellen': cells_compared, 'beste_vermutungen': reads}
    if not unchanged['unveraendert'] and cells_compared == list(range(1, 8)):
        # Springt nur die letzte Stelle um genau 1 (gleiche Punktzelle, Uebertraege
        # zaehlen mit), gilt die Anzeige als unveraendert - mit Beleg.
        texts = ['+' + read + ' ' for read in reads]
        if _spread_units(texts[0], texts) == 1:
            unchanged.update(unveraendert=True, letzte_stelle_schwankt=True)
    return unchanged


def _tolerance_proposal(observations, reader, layout, path, sha, reference_kind) -> dict:
    tolerance = {'possible': False, 'factor': None, 'max_d_best': None, 'd_max': None, 'reason': None}

    def reject(reason):
        tolerance['reason'] = reason
        return tolerance

    tolerance['reference_kind'] = reference_kind
    if reference_kind not in ('seriell', 'eingabe'):
        return reject('referenzart_unbekannt')
    if any(reason not in (None, 'zelle_unbekannt') for _, _, _, reason in observations):
        return reject('keine_reine_zellablehnung')
    if reference_kind == 'eingabe':
        # Von Hand eingegebener Wert gilt fuer alle Standbilder. Er belegt eine
        # Toleranz nur, wenn die Anzeige dabei nachweislich gleich blieb: die
        # besten Vermutungen des Lesers sind in jeder vergleichbaren Zelle
        # aller Standbilder identisch (die Gegenprobe unten prueft sie danach
        # noch gegen den Wert).
        unchanged = _display_unchanged(observations)
        if unchanged is None:
            return reject('standbild_lesedaten_fehlen')
        tolerance['anzeige_unveraendert'] = unchanged
        if not unchanged['unveraendert']:
            return reject('anzeige_veraendert')
    t = reader._t
    tolerance['d_max'] = t.d_max
    distances = []
    for _, reference, diag, _ in observations:
        cells = diag.get('cells', [])
        best_text = _full_text(cells, 'best')
        # Von Hand eingegeben: beste Vermutungen duerfen nur in der letzten Stelle um 1 abweichen.
        best_step_ok = (reference_kind == 'eingabe' and '?' not in reference and best_text is not None
                        and last_place_step(reference, best_text) is not None)
        for i, ch in enumerate(reference):
            if ch == '?':
                continue
            if i >= len(cells) or any(key not in cells[i] for key in ('best', 'd_best', 'd_second')):
                return reject('zelldiagnose_fehlt')
            cell = cells[i]
            if cell['best'] != ch and not best_step_ok:
                return reject('beste_vermutung_widerspricht_referenz')
            if not math.isfinite(cell['d_best']) or not math.isfinite(cell['d_second']):
                return reject('zelldiagnose_ungueltig')
            if cell['d_second'] - cell['d_best'] < t.margin_min:
                return reject('abstand_zur_zweitbesten_zu_klein')
            distances.append(cell['d_best'])
    maximum = max(distances)
    tolerance['max_d_best'] = maximum
    factor = max(1.0, math.ceil(round(1.25 * maximum / t.d_max * 100, 9)) / 100)
    if factor > 2.0:
        return reject('faktor_ueber_2')
    adaptive = DotMatrixReader.from_file(Path(path), sha, d_max_factor=factor)
    notes = []
    for index, (crop, reference, _, _) in enumerate(observations):
        reason, contradictions, note = _frame_verdict(adaptive.read(crop, layout).diagnostics, reference, index,
                                                      reference_kind)
        if reason is not None or contradictions:
            return reject('gegenprobe_nicht_gelesen')
        if note is not None:
            notes.append(note)
    if notes and len(notes) == len(observations):
        # Auch mit angepasster Toleranz zeigt kein Standbild genau den
        # eingegebenen Wert: Schwanken nicht belegt (NEVER_EXACT_CODE).
        return reject(NEVER_EXACT_CODE)
    if notes:
        tolerance['notes'] = notes
    tolerance.update(possible=True, factor=factor)
    return tolerance


def _glare_check(warped_gray: np.ndarray) -> CheckResult:
    saturated = float((warped_gray >= 250).mean())
    background = float(np.median(warped_gray[20:145]))
    bright = (warped_gray[20:145, :225] > background + GLARE_BRIGHTNESS_ABOVE_BACKGROUND).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(bright)
    blob_area = int(stats[1:, cv2.CC_STAT_AREA].max()) if n > 1 else 0
    status = 'FEHLER' if saturated > SATURATED_ERROR or blob_area >= GLARE_BLOB_AREA_ERROR else 'OK'
    return CheckResult(status, {'saturated_fraction': saturated, 'bright_blob_area_px': blob_area})


def _raster_check(fit: Any, offset_check: CheckResult | None = None) -> CheckResult:
    assigned = fit.n_assigned / fit.n_dots if fit.n_dots else 0.0
    max_bias = max((abs(float(v)) for v in (*fit.row_bias, *fit.cell_bias)), default=0.0)
    metrics = {'n_dots': fit.n_dots, 'n_assigned': fit.n_assigned, 'assigned_fraction': assigned,
               'rms_cols': fit.rms_cols, 'rms_rows': fit.rms_rows, 'cells': list(fit.cells),
               'row_bias': list(fit.row_bias), 'cell_bias': list(fit.cell_bias), 'max_abs_bias': max_bias}
    proxy_bad = (fit.rms_cols > RMS_COLS_ERROR or fit.rms_rows > RMS_ROWS_ERROR
                 or assigned < ASSIGNED_FRACTION_ERROR)
    independent_offset_ok = offset_check is not None and offset_check.status in ('OK', 'WARNUNG')
    if proxy_bad and not independent_offset_ok:
        status = 'FEHLER'
    elif proxy_bad or max_bias > BIAS_WARNING:
        status = 'WARNUNG'
    else:
        status = 'OK'
    return CheckResult(status, metrics)


def raster_offset_check(frames: Sequence[tuple[np.ndarray, str]], quad, *,
                        grid: CharGrid = GRID,
                        target_size: tuple[int, int] = TARGET_SIZE) -> CheckResult:
    """Prueft den Versatz von ROM-Punkten zu einem Quad anhand bekannter Zellentexte.

    Die Texte dienen nur zur Lokalisierung der Punkte. Weder Text noch daraus
    abgeleitete Messwerte werden als aktueller DUT-Wert ausgegeben.
    """
    source = {'kind': 'known_cell_text', 'frame_count': len(frames), 'text_included': False}
    metrics: dict[str, Any] = {
        'source': source, 'max_abs_dx_cols': None, 'max_abs_dy_rows': None,
        'half_cell_count': 0, 'full_cell_count': 0,
        'half_offsets': [], 'full_offsets': [], 'frame_coverage': [],
        'warning_above': OFFSET_WARNING, 'error_above': OFFSET_ERROR,
        'threshold_kind': 'Vorabwerte',
    }
    if not frames:
        return CheckResult('FEHLER', metrics, reason='keine_bilder')
    q = np.asarray(quad, dtype=np.float32)
    if q.shape != (4, 2) or not np.isfinite(q).all():
        return CheckResult('FEHLER', metrics, reason='ungueltiges_quad')
    halves = []
    full = []
    try:
        for image, cell_text in frames:
            _gray(image)
            if not isinstance(cell_text, str) or not 1 <= len(cell_text) <= grid.n_cells:
                return CheckResult('FEHLER', metrics, reason='ungueltiger_zellentext')
            known_text = cell_text.replace('?', ' ')
            halves.append(measure_offsets(image, q, grid, target_size, known_text, HALVES))
            full.append(measure_offsets(image, q, grid, target_size, known_text, FULL))
    except (TypeError, ValueError, cv2.error, KeyError) as exc:
        return CheckResult('FEHLER', metrics, reason=f'messung_unmoeglich:{type(exc).__name__}')

    # Ein lesbares Bild darf ein unlesbares zweites nicht durch das gepoolte
    # Median verdecken. Beide Standbilder muessen fuer sich belastbar sein.
    for per_half, per_full in zip(halves, full, strict=True):
        reliable_half = median_offsets([per_half])
        reliable_full = median_offsets([per_full])
        half_counts = [len({cell for cell, half in reliable_half if half == part})
                       for part in range(len(HALVES))]
        full_count = len({cell for cell, _ in reliable_full})
        metrics['frame_coverage'].append({'half_cells': half_counts, 'full_cells': full_count})
        if min(*half_counts, full_count) < OFFSET_MIN_CELLS:
            return CheckResult('FEHLER', metrics, reason='zu_wenige_belastbare_zellen_im_bild')

    half_medians = median_offsets(halves)
    full_medians = median_offsets(full)
    metrics['half_offsets'] = [
        {'cell': int(cell), 'half': int(half), 'dx_cols': dx, 'dy_rows': dy, 'count': count}
        for (cell, half), (dx, dy, count) in half_medians.items()
    ]
    metrics['full_offsets'] = [
        {'cell': int(cell), 'dx_cols': dx, 'dy_rows': dy, 'count': count}
        for (cell, _), (dx, dy, count) in full_medians.items()
    ]
    metrics['half_cell_count'] = len(half_medians)
    metrics['full_cell_count'] = len(full_medians)
    if (any(len({cell for cell, half in half_medians if half == part}) < OFFSET_MIN_CELLS
            for part in range(len(HALVES)))
            or len({cell for cell, _ in full_medians}) < OFFSET_MIN_CELLS):
        return CheckResult('FEHLER', metrics, reason='zu_wenige_belastbare_zellen')

    max_dx, _ = max_abs_offset(half_medians)
    _, max_dy = max_abs_offset(full_medians)
    metrics['max_abs_dx_cols'] = max_dx
    metrics['max_abs_dy_rows'] = max_dy
    status = ('FEHLER' if max_dx > OFFSET_ERROR or max_dy > OFFSET_ERROR else
              'WARNUNG' if max_dx > OFFSET_WARNING or max_dy > OFFSET_WARNING else 'OK')
    return CheckResult(status, metrics)


def _stability_check(image_bgr: np.ndarray, second: np.ndarray | None,
                     elapsed_s: float | None, quad: list[list[float]],
                     min_elapsed_s: float) -> CheckResult:
    if second is None:
        return CheckResult(None, {'elapsed_s': None, 'max_corner_shift_px': None}, reason='nicht_durchgefuehrt')
    if elapsed_s is None or elapsed_s < min_elapsed_s:
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
                stability_elapsed_s: float | None = None,
                offset_check: CheckResult | None = None,
                stability_min_elapsed_s: float = STABILITY_MIN_ELAPSED_S) -> SetupChecks:
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
    sampled = sample_image(warped_gray, GRID, tuple(range(GRID.n_cells)))
    contrast = _point_contrast(gray, quad)
    contrast_status = ('FEHLER' if contrast < POINT_CONTRAST_ERROR else
                       'WARNUNG' if contrast < POINT_CONTRAST_WARNING else 'OK')
    resolution = float(source_dot_column_px(GRID, lattice_fit.quad, TARGET_SIZE))
    resolution_status = ('FEHLER' if resolution < RESOLUTION_ERROR_PX else
                         'WARNUNG' if resolution < RESOLUTION_WARNING_PX else 'OK')
    glass_level = float(np.percentile(warped_gray[20:140, 5:395], 80))
    underexposed = glass_level < EXPOSURE_WARNING_BELOW
    checks = {
        'kontrast': CheckResult(contrast_status, {'punktkontrast': contrast,
                                                 'leser_kontrast': sampled.contrast}),
        'kanten': _edge_check(warped_gray),
        'rahmen': _border_check(sampled),
        'glanz': _glare_check(warped_gray),
        'belichtung': CheckResult('WARNUNG' if underexposed else 'OK',
                                  {'glaspegel': glass_level, 'percentile': 80,
                                   'warning_below': EXPOSURE_WARNING_BELOW},
                                  reason=(f'Display zu dunkel belichtet (Glaspegel {glass_level:.0f}): '
                                          'Kamera näher stellen oder helle Umgebung abdecken und neu einrichten'
                                          if underexposed else None)),
        'aufloesung': CheckResult(resolution_status, {'min_source_dot_column_px': resolution}),
        'raster': _raster_check(lattice_fit, offset_check),
        'stabilitaet': _stability_check(image_bgr, stability_image_bgr,
                                      stability_elapsed_s, lattice_fit.quad, stability_min_elapsed_s),
    }
    if offset_check is not None:
        checks['rasterversatz'] = offset_check
    statuses = {check.status for check in checks.values()}
    overall = 'FEHLER' if 'FEHLER' in statuses else 'WARNUNG' if 'WARNUNG' in statuses else 'OK'
    return SetupChecks(overall, checks)
