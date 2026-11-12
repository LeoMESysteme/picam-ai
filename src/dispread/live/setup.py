"""Einrichtung einer Punktraster-Anzeige (GSV-Sensor, Displaytech 161A).

Aus `scripts/harvest-setup.py` (assist/focus/propose/confirm) verlagert,
damit Kommandozeile und Werkbank dieselbe Implementierung nutzen
(Spec 2026-10-12 §1). Kein Kamerazugriff hier: alles laeuft ueber
`SetupCamera`, das die Kommandozeile mit einer direkten Aufnahme und die
Werkbank mit `CameraOwner` erfuellt.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import uuid
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol

import cv2
import numpy as np

from dispread.camera_settings import STREAMCAM_MODEL, STREAMCAM_USB_ID, CameraSettings
from dispread.charcells import CharGrid, source_dot_column_px
from dispread.dotlattice import evaluate_quad, fit_lattice
from dispread.focus_sweep import DEFAULT_FOCUS_START, FocusMeasurements, climb_focus, sharpness
from dispread.frames.uvc_source import UvcError
from dispread.gsv2as_cell_text import cell_text_from_telegram
from dispread.lattice_offsets import refine_quad
from dispread.live.frame_tracking import FrameTrackingConfig, RegionProposal, proposal_from_regions, propose_regions
from dispread.live.texts import REASONS
from dispread.rectify import rectify
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile
from dispread.setup_checks import check_setup, diagnose_reader, display_defect_check, raster_offset_check
from dispread.setup_hint import GREEN_HUE_MAX, GREEN_HUE_MIN, MIN_SATURATION, MIN_VALUE, find_green_hint_box
from dispread.setup_overlays import draw_sampling_overlay, draw_source_overlay

GSV2AS_EMPTY_CELLS = (8, 13, 14, 15)
N_CELLS = 16
DEFAULT_TARGET_SIZE = (400, 160)
LATTICE_GRID = CharGrid(n_cells=N_CELLS, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0)
WHITE_BALANCE_SETTLE_S = 3.0
FOCUS_SOURCE_SIZE = (1920, 1080)
# Vorabwerte: p80 gruener Boxpixel liegt an 12 Standbildern hoechstens 4 Graustufen
# neben dem entzerrten Glas-p80 (Laborjournal 2026-10-28, R13-20).
EXPOSURE_TARGET = 130.0
EXPOSURE_BAND = (115.0, 150.0)
EXPOSURE_STEPS = (100, 200, 300)  # 50 Hz, 10/20/30 ms bei 30 fps.
EXPOSURE_GAIN_RANGE = (0, 128)  # konservativer Bereich, keine Geraeteabfrage noetig.
EXPOSURE_MAX_ROUNDS = 4
EXPOSURE_SETTLE_S = 0.3
# Fokus: alle 0.3 s pruefen, hoechstens 5 s ab Setzen (inklusive Einschwingen).
# Zwei aufeinanderfolgende Schaerfen duerfen relativ zum Vorgaenger um 5 % abweichen.
FOCUS_SAMPLE_INTERVAL_S = 0.3
FOCUS_STABILITY_TIMEOUT_S = 5.0
FOCUS_STABILITY_TOLERANCE = 0.05
FOCUS_VERIFY_RATIO = 0.85  # Endlage muss mindestens 85 % der besten Suchmessung erreichen.
# StreamCam: 2-3 Schritte Hysterese (2026-10-23); 12 Schritte Reserve.
# Unterhalb 12 wird der Anfahrpunkt auf 0 begrenzt; Ziel 0 ist nicht von unten erreichbar.
FOCUS_BACKLASH_MARGIN = 12
MIN_STABILITY_S = 30.0
# OQ-74: Die Fokussuche misst auf der gruenen LCD-Hinweisbox statt auf dem
# festen mittleren Bilddrittel. Kleiner Rand je Seite: Auf den 16 Paketbildern
# vom 2026-11-11 bleibt die Box bei Gauss-Unschaerfe bis sigma 3 zu >= 99 %
# gleich; 5 % Rand fangen eine auf dem Vorabbild leicht verschobene Box ab.
FOCUS_ROI_MARGIN_FRACTION = 0.05
# Endpruefung nach dem letzten Kameraneustart: helligkeitsnormierte Schaerfe
# (Laplace-Varianz / ROI-Mittel^2) gegen die beste Suchprobe. 0,85 ist die
# Toleranz derselben Lage bei gleicher Belichtung (FOCUS_VERIFY_RATIO). Die
# Belichtung der Suche ist aber nicht die Endbelichtung; Verstaerkungsrauschen,
# Gamma und Clipping normiert der Quotient nicht weg. Vorabwert 0,6 mit Abstand
# zu beiden Seiten; an den Paketen nicht kalibrierbar (keine Einzelbilder vor
# und nach dem Neustart), siehe OQ-74. Die neue Instrumentierung liefert die
# Daten fuer eine Kalibrierung.
FOCUS_END_RATIO = 0.6
# Diagnoseausschnitt der Fokusbilder: ROI mit 25 % Rand je Seite (< 1 MB PNG).
FOCUS_DIAGNOSTIC_MARGIN_FRACTION = 0.25
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUDRATE = 38400

HintBox = tuple[float, float, float, float]
CellTextSource = Callable[[Callable[[], np.ndarray]], tuple[np.ndarray, str]]


class SetupError(ValueError):
    """Einrichtung abgebrochen; die Meldung ist fuer den Bediener."""


class SetupCancelled(SetupError):
    """Kooperativer Abbruch durch den Bediener."""

    def __init__(self) -> None:
        super().__init__("Einrichtung abgebrochen")


def check_cancelled(should_stop: Callable[[], bool] | None) -> None:
    if should_stop is not None and should_stop():
        raise SetupCancelled()


class SetupInputError(SetupError):
    """Ungueltige Eingabe statt eines Konflikts mit dem Einrichtungszustand."""


class SetupCamera(Protocol):
    device: str

    def set_controls(self, controls: list[tuple[str, int]]) -> None: ...

    def get_controls(self, names: list[str]) -> dict[str, int]: ...

    def fresh_still(self, discard: int = 10) -> np.ndarray: ...


def mean_still(cam: SetupCamera, frames: int = 8, discard: int = 10, *,
               captured_frames: list[np.ndarray] | None = None) -> np.ndarray:
    """Frische Bilder mitteln; auf Wunsch ungemittelte Kopien im RAM behalten."""
    if frames < 1:
        raise SetupError("Standbildmittelung braucht mindestens ein Bild")
    first = cam.fresh_still(discard=discard)
    if captured_frames is not None:
        captured_frames.append(first.copy())
    if frames == 1:
        return first
    total = first.astype(np.float32)
    for _ in range(frames - 1):
        frame = cam.fresh_still(discard=0)
        if captured_frames is not None:
            captured_frames.append(frame.copy())
        total += frame
    return np.rint(total / frames).astype(np.uint8)


def offline_text_source(text: str) -> CellTextSource:
    """Zellentext vom Bediener: fuer jedes Standbild derselbe Text."""
    return lambda capture: (capture(), text)


def serial_text_source(port: Any) -> CellTextSource:
    """Zellentext vom GSV-2AS: jedes Standbild mit frischen Telegrammen geklammert."""
    return lambda capture: capture_with_text(capture, port)


def measurement_roi_pixels(size: tuple[int, int], hint_box: HintBox | None) -> list[int]:
    """Derselbe Messbereich als x,y,w,h in Pixeln des Kamerabildes."""
    width, height = size
    if hint_box is None:
        x0, x1 = width // 3, 2 * width // 3
        y0, y1 = height // 3, 2 * height // 3
    else:
        bx, by, bw, bh = hint_box
        x0, y0 = int(round(bx * width)), int(round(by * height))
        x1, y1 = int(round((bx + bw) * width)), int(round((by + bh) * height))
    return [x0, y0, x1 - x0, y1 - y0]


def measurement_roi(gray: np.ndarray, hint_box: HintBox | None) -> np.ndarray:
    """Hinweisbox oder mittleres Drittel fuer die Schaerfemessung."""
    height, width = gray.shape[:2]
    x, y, w, h = measurement_roi_pixels((width, height), hint_box)
    return gray[y:y + h, x:x + w]


def pad_hint_box(box: HintBox, margin: float) -> HintBox:
    """Normierte Box je Seite um `margin` ihrer Groesse erweitern, auf das Bild begrenzt."""
    bx, by, bw, bh = box
    x0, y0 = max(0.0, bx - margin * bw), max(0.0, by - margin * bh)
    x1, y1 = min(1.0, bx + bw * (1 + margin)), min(1.0, by + bh * (1 + margin))
    return x0, y0, x1 - x0, y1 - y0


def focus_hint_box(image: np.ndarray | None) -> HintBox | None:
    """Fokus-ROI aus der gruenen LCD-Hinweisbox (OQ-74), `None` ohne Box.

    Dieselbe Quelle wie die spaetere Einrichtung (`find_green_hint_box`), auf
    einem Vorabbild vor der Fokussuche. Ohne Box misst die Suche auf dem
    mittleren Drittel; das meldet `focus_check` als WARNUNG.
    """
    if image is None or image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        return None
    box = find_green_hint_box(image)
    return None if box is None else pad_hint_box(box, FOCUS_ROI_MARGIN_FRACTION)


def focus_diagnostic_crop(frame: np.ndarray, hint_box: HintBox | None) -> tuple[np.ndarray, list[int]]:
    """Fokus-ROI mit Rand als Diagnoseausschnitt; Rechteck x,y,w,h in Bildpixeln."""
    height, width = frame.shape[:2]
    x, y, w, h = measurement_roi_pixels((width, height), hint_box)
    mx, my = round(FOCUS_DIAGNOSTIC_MARGIN_FRACTION * w), round(FOCUS_DIAGNOSTIC_MARGIN_FRACTION * h)
    x0, y0 = max(0, x - mx), max(0, y - my)
    x1, y1 = min(width, x + w + mx), min(height, y + h + my)
    return frame[y0:y1, x0:x1], [x0, y0, x1 - x0, y1 - y0]


def hint_glass_level(image: np.ndarray, hint_box: HintBox) -> float | None:
    """p80 gruener Boxpixel: dunkle Punkte und helle Umgebung ausnehmen.

    Die Farbgrenzen entsprechen der Hinweisboxsuche. Ihr Sicherheitsrand
    darf keine helle Umgebung in den Glaspegel einbringen.
    """
    region = measurement_roi(image, hint_box)
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    green = cv2.inRange(hsv, (GREEN_HUE_MIN, MIN_SATURATION, MIN_VALUE), (GREEN_HUE_MAX, 255, 255))
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    values = gray[green > 0]
    return float(np.percentile(values, 80)) if values.size else None


def adjust_exposure(
    cam: SetupCamera, settings: CameraSettings, *, apply: Callable[[CameraSettings], None],
    sleep: Callable[[float], None] | None = None, info: Callable[[str], None] | None = None,
    on_round: Callable[[dict], None] | None = None,
) -> tuple[CameraSettings, dict[str, Any]]:
    """Anzeige statt Gesamtbild messen, hoechstens vier feste Reglerpaare pruefen.

    `apply` uebernimmt alle festen Regler via Kamera-Neustart wie nach Fokus.
    Erst 30 ms bevorzugen, dann Gain; bei zu hellem Glas und Gain 0 verkuerzen.
    Gain-Sekante nur aus eigenen Messungen bei gleicher Belichtung; bis dahin
    vorsichtig 1 Graustufe/Schritt annehmen. Keine Hardwarekennlinie behauptet.
    Die beste gemessene Einstellung wird auch bei Boxverlust zurueckgestellt.
    `on_round` meldet gemessene Pegel samt Reglern, einschliesslich Ausgangspegel.
    """
    sleep = sleep or time.sleep

    def measure() -> tuple[float | None, HintBox | None]:
        sleep(EXPOSURE_SETTLE_S)
        image = mean_still(cam)
        box = find_green_hint_box(image)
        return (hint_glass_level(image, box) if box is not None else None), box

    level, box = measure()
    audit: dict[str, Any] = {
        'initial_level': level, 'initial_controls': dict(settings.controls),
        'percentile': 80, 'region': 'green_pixels_in_hint_box',
        'target': EXPOSURE_TARGET, 'target_band': list(EXPOSURE_BAND),
        'gain_range': list(EXPOSURE_GAIN_RANGE), 'rounds': [], 'achieved': False,
        'reason': None, 'initial_hint_box': box,
    }
    current = best = settings
    best_level = level
    observations = [(settings, level)]
    low, high = EXPOSURE_BAND

    def report_round() -> None:
        # Ohne gemessenen Pegel gibt es keine gueltige Probe fuer die Kurve.
        if on_round is not None and level is not None:
            on_round({"level": float(level), "controls": dict(current.controls)})

    report_round()

    def rank(value: float) -> tuple[float, float]:
        # Ein erreichter Bandrand geht vor einem knapp verfehlten Band.
        return max(low - value, 0.0, value - high), abs(value - EXPOSURE_TARGET)

    def allowed(candidate: CameraSettings) -> bool:
        return (candidate.controls['exposure_time_absolute'] in EXPOSURE_STEPS
                and EXPOSURE_GAIN_RANGE[0] <= candidate.controls['gain'] <= EXPOSURE_GAIN_RANGE[1])

    def next_candidate(source: CameraSettings, measured_level: float) -> CameraSettings:
        exposure, gain = source.controls['exposure_time_absolute'], source.controls['gain']
        tried_300 = any(s.controls['exposure_time_absolute'] == 300 for s, _ in observations)
        if not allowed(source) and measured_level > high:
            # Unzulaessiger Automatikwert und schon zu hell: zuerst die naechst
            # kuerzere zulaessige Stufe, nicht auf 30 ms verlaengern (Review R13-20).
            exposure = max(s for s in EXPOSURE_STEPS if s <= max(EXPOSURE_STEPS[0], exposure))
            gain = min(128, max(0, gain))
        elif not allowed(source) or (measured_level < low and not tried_300):
            exposure, gain = 300, min(128, max(0, gain))
        elif measured_level > high and gain == 0:
            exposure = max(100, exposure - 100)
        else:
            slope = 1.0
            for previous, previous_level in reversed(observations):
                delta = gain - previous.controls['gain']
                if previous.controls['exposure_time_absolute'] == exposure and delta and previous_level is not None:
                    measured_slope = (measured_level - previous_level) / delta
                    if measured_slope > 0:
                        slope = measured_slope
                    break
            gain = min(128, max(0, round(gain + (EXPOSURE_TARGET - measured_level) / slope)))
        return replace(source, controls={**source.controls, 'exposure_time_absolute': exposure, 'gain': gain})

    if level is None:
        audit['reason'] = 'keine_gruene_hinweisbox'
    else:
        for _ in range(EXPOSURE_MAX_ROUNDS):
            if low <= level <= high and allowed(current):
                break
            candidate = next_candidate(current, level)
            reused = set()
            # Beim Verkuerzen kann das Ausgangspaar wieder auftauchen.
            # Dessen Pegel wiederverwenden und Gain weiterregeln, statt einen
            # erreichbaren Fall als Wiederholung abzubrechen. Keine neue Messrunde.
            while known := next(((s, v) for s, v in observations if s.controls == candidate.controls), None):
                key = (candidate.controls['exposure_time_absolute'], candidate.controls['gain'])
                if key in reused:
                    audit['reason'] = 'reglergrenze_oder_wiederholung'
                    break
                reused.add(key)
                candidate = next_candidate(*known)
            if audit['reason'] is not None:
                break
            apply(candidate)
            current = candidate
            level, box = measure()
            observations.append((current, level))
            audit['rounds'].append({'controls': dict(current.controls), 'level': level, 'hint_box': box})
            report_round()
            if info is not None:
                info(f"Belichtung: {current.controls['exposure_time_absolute']}, "
                     f"Gain {current.controls['gain']}, Glaspegel {level}")
            if level is None:
                audit['reason'] = 'gruene_hinweisbox_verloren'
                break
            if not allowed(best) or rank(level) < rank(best_level):
                best, best_level = current, level
        if current != best:
            if allowed(best):
                apply(best)
            else:
                # Ein unzulaessiger Automatik-Ausgangswert darf nach Boxverlust
                # nicht erneut gesetzt werden. Der letzte feste Wert bleibt;
                # ohne Messung seines Glases gibt es keinen gueltigen Endpegel.
                best, best_level = current, level
        audit['achieved'] = best_level is not None and low <= best_level <= high and allowed(best)
        if not audit['achieved'] and audit['reason'] is None:
            audit['reason'] = 'zielband_nach_vier_runden_nicht_erreicht'
    audit.update(selected_controls=dict(best.controls), final_level=best_level)
    return best, audit


def serial_cell_text(port: Any) -> str:
    """Read a fresh incoming DUT telegram, then map it to physical cells."""
    if hasattr(port, "reset_input_buffer"):
        port.reset_input_buffer()
        port.readline()  # Moeglicherweise unvollstaendige erste Zeile verwerfen.
    line = port.readline().rstrip(b"\r\n")
    try:
        return cell_text_from_telegram(line)
    except ValueError as exc:
        raise SetupError(f"GSV-2AS-Zellentext aus seriellem Strom unlesbar: {exc}") from exc


def mask_changed_cells(before: str, after: str) -> tuple[str, str]:
    """Only cells unchanged in both observations may inform geometry."""
    if len(before) != len(after):
        raise SetupError("Serieller Zellentext hat unterschiedliche Laenge")
    shared = "".join(left if left == right else "?" for left, right in zip(before, after, strict=True))
    return shared, shared


def capture_with_text(
    capture: Any, port: Any, *, on_text: Callable[[str | None, str | None, int], None] | None = None,
    info: Callable[[str], None] | None = None, max_tries: int = 5,
) -> tuple[np.ndarray, str]:
    """Wartet auf eine ruhige Aufnahme; meldet Klammer und Versuchszahl des benutzten Bildes."""
    if max_tries < 1:
        raise SetupError("Standbildaufnahme braucht mindestens einen Versuch")
    before = after = None
    tries = 1
    try:
        for tries in range(1, max_tries + 1):
            before = after = None
            before = serial_cell_text(port)
            image = capture()
            after = serial_cell_text(port)
            masked = mask_changed_cells(before, after)[0]
            if before == after or tries == max_tries:
                return image, masked
            if info is not None:
                info("Standbild: Anzeige hat sich waehrend der Aufnahme geaendert, "
                     f"neuer Versuch {tries + 1}/{max_tries}")
    finally:
        if on_text is not None:
            on_text(before, after, tries)


def heldout_improves(old_check: Any, new_check: Any) -> bool:
    """Require a strictly smaller worst measured offset on the held-out still."""
    keys = ("max_abs_dx_cols", "max_abs_dy_rows")
    old = [old_check.metrics.get(key) for key in keys]
    new = [new_check.metrics.get(key) for key in keys]
    if any(value is None or not math.isfinite(value) for value in (*old, *new)):
        return False
    return max(new) < max(old) - 0.02 and all(after <= before + 0.01 for before, after in zip(old, new, strict=True))


class _FocusProbe:
    """Eine Fokuslage messen: von unten anfahren, warten, bis die Schaerfe steht.

    `frame` und `mean` gehoeren zur zuletzt zurueckgegebenen Messung (Bild und
    mittlere ROI-Helligkeit). `should_stop` bricht zwischen Proben und
    innerhalb von Wartezeiten alle hoechstens 0,5 s ab.
    """

    def __init__(self, cam: SetupCamera, hint_box: HintBox | None, *, settle_s: float,
                 sleep: Callable[[float], None], should_stop: Callable[[], bool] | None, label: str) -> None:
        self.cam, self.hint_box, self.settle_s = cam, hint_box, settle_s
        self.sleep, self.should_stop, self.label = sleep, should_stop, label
        self.last_focus: int | None = None
        self.frame: np.ndarray | None = None
        self.mean: float | None = None

    def wait(self, seconds: float) -> None:
        if self.should_stop is None:
            self.sleep(seconds)
            return
        check_cancelled(self.should_stop)
        while seconds > 0:
            interval = min(0.5, seconds)
            self.sleep(interval)
            check_cancelled(self.should_stop)
            seconds -= interval

    def measure(self, focus: int) -> float:
        check_cancelled(self.should_stop)
        if focus <= 0:
            raise SetupError("Fokus 0 ist nicht von unten erreichbar - Einrichtung neu starten")
        # Auch die erste (unbekannte) Lage und ein erneutes Setzen derselben
        # Lage normalisieren. So fahren Endpruefung und Retry sicher von unten an.
        if self.last_focus is None or focus <= self.last_focus:
            self.cam.set_controls([("focus_absolute", max(0, focus - FOCUS_BACKLASH_MARGIN))])
            self.wait(min(self.settle_s, FOCUS_STABILITY_TIMEOUT_S))
        self.cam.set_controls([("focus_absolute", focus)])
        self.last_focus = focus
        return self._stable_score(time.monotonic() + FOCUS_STABILITY_TIMEOUT_S)

    def measure_here(self) -> float:
        """Ohne die Linse zu bewegen messen (Lage nach einem Kameraneustart)."""
        check_cancelled(self.should_stop)
        return self._stable_score(time.monotonic() + FOCUS_STABILITY_TIMEOUT_S)

    def _stable_score(self, deadline: float) -> float:
        self.wait(min(self.settle_s, FOCUS_STABILITY_TIMEOUT_S))
        previous = None
        while True:
            check_cancelled(self.should_stop)
            try:
                frame = self.cam.fresh_still(discard=3)
            except UvcError as exc:
                raise UvcError(f"kein Bild von {self.cam.device} ({self.label})") from exc
            gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            roi = measurement_roi(gray, self.hint_box)
            score = sharpness(roi)
            self.frame, self.mean = frame, float(np.mean(roi)) if roi.size else 0.0
            if previous is not None and abs(score - previous) <= abs(previous) * FOCUS_STABILITY_TOLERANCE:
                return score
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return score
            previous = score
            self.wait(min(FOCUS_SAMPLE_INTERVAL_S, remaining))


def _focus_ratio(score: float, mean: float | None, best: float, best_mean: float | None) -> float:
    """Schaerfe relativ zur besten Suchprobe, helligkeitsnormiert wenn moeglich.

    Laplace-Varianz skaliert mit dem Quadrat eines Helligkeitsfaktors, das
    ROI-Mittel linear; der Quotient Varianz/Mittel^2 haengt daher nicht von
    einer reinen Helligkeitsskalierung ab. Ohne Mittelwerte: Rohquotient.
    """
    if best <= 0:
        return 0.0
    if mean is None or best_mean is None:
        return score / best
    return (score / max(mean, 1.0) ** 2) / (best / max(best_mean, 1.0) ** 2)


def check_focus_after_restart(
    cam: SetupCamera,
    hint_box: HintBox | None,
    sweep: FocusMeasurements,
    *,
    settle_s: float = 1.0,
    sleep: Callable[[float], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    info: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]] | None:
    """OQ-74: Schaerfe nach dem letzten Kameraneustart auf derselben ROI pruefen.

    Erst ohne Linsenbewegung messen. Liegt die normierte Schaerfe unter
    `FOCUS_END_RATIO` der besten Suchprobe, einmal von unten neu setzen
    (Automatik aus, dann Anfahrpunkt, dann Ziel). Bleibt sie darunter:
    WARNUNG mit Bedienertext, kein stilles Weiter. Rueckgabe: Bericht und
    Bilder (`nach_neustart`, ggf. `nach_neusetzen`); `None`, wenn die Suche
    keine Endpruefung hinterlassen hat.
    """
    verify = getattr(sweep, "focus_verify", None)
    if not verify or not len(sweep):
        return None
    best_focus, best_score = max(sweep, key=lambda pair: pair[1])
    best_mean = getattr(sweep, "roi_means", {}).get(best_focus)
    if info is not None:
        info("Fokus nach Kameraneustart pruefen")
    result, frames = _check_lens_after_restart(
        cam, hint_box, int(verify["target"]), best_score, best_mean, settle_s=settle_s, sleep=sleep,
        should_stop=should_stop, info=info, label="Fokus-Endpruefung",
    )
    result.update(best_focus=best_focus, best_measured=best_score, best_roi_mean=best_mean)
    if result["status"] == "WARNUNG":
        result["reason"] = (
            f"Fokus nach Kameraneustart unscharf: {100 * result['reapproach']['ratio']:.0f} % der besten "
            f"Suchschärfe (Grenze {100 * FOCUS_END_RATIO:.0f} %), auch nach Neusetzen von unten. "
            "Bild auf Schärfe prüfen und gegebenenfalls neu einrichten")
    elif result["reapproach"] is not None:
        result["reason"] = (f"Fokus nach Kameraneustart neu gesetzt (vorher "
                            f"{100 * result['after_restart']['ratio']:.0f} %, danach "
                            f"{100 * result['reapproach']['ratio']:.0f} % der besten Suchschärfe)")
    return result, frames


def _check_lens_after_restart(
    cam: SetupCamera, roi_box: HintBox | None, target: int, ref_score: float, ref_mean: float | None, *,
    settle_s: float, sleep: Callable[[float], None] | None, should_stop: Callable[[], bool] | None,
    info: Callable[[str], None] | None, label: str,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Gemeinsamer Kern: ohne Bewegung messen, unter der Schwelle einmal von unten neu setzen."""
    probe = _FocusProbe(cam, roi_box, settle_s=settle_s, sleep=sleep or time.sleep, should_stop=should_stop,
                        label=label)
    after = probe.measure_here()
    frames = {"nach_neustart": probe.frame}
    ratio = _focus_ratio(after, probe.mean, ref_score, ref_mean)
    result: dict[str, Any] = {
        "target": target, "threshold_ratio": FOCUS_END_RATIO,
        "normierung": "laplace_varianz_durch_roi_mittel_quadrat",
        "after_restart": {"score": after, "roi_mean": probe.mean,
                          "raw_ratio": after / ref_score if ref_score else 0.0, "ratio": ratio},
        "reapproach": None, "status": "OK", "reason": None,
    }
    if ratio >= FOCUS_END_RATIO:
        return result, frames
    if info is not None:
        info(f"Fokus nach Kameraneustart {100 * ratio:.0f} % - Absolutwert von unten neu setzen")
    # CLAUDE.md StreamCam: Automatik zuerst aus, dann Absolutwert.
    cam.set_controls([("focus_automatic_continuous", 0)])
    again = probe.measure(target)
    frames["nach_neusetzen"] = probe.frame
    again_ratio = _focus_ratio(again, probe.mean, ref_score, ref_mean)
    result["reapproach"] = {
        "score": again, "roi_mean": probe.mean, "raw_ratio": again / ref_score if ref_score else 0.0,
        "ratio": again_ratio,
        # Gleiche Belichtung wie direkt nach dem Neustart: Wirkung des Neustarts selbst.
        "restart_effect": after / again if again > 0 else None,
    }
    if again_ratio < FOCUS_END_RATIO:
        result["status"] = "WARNUNG"
    return result, frames


def quad_focus_reference(images: Any, quad: Any, size: tuple[int, int], *, source: str) -> dict[str, Any] | None:
    """Schaerfereferenz fuer den Laufstart: Median ueber Bilder, ROI = Begrenzungsrechteck des Quads.

    Am besten Einzelbilder (die Stabilitaetsaufnahme der Einrichtung), weil der
    Laufstart Einzelbilder misst. Ein Mittelbild hat weniger Rauschen und damit
    eine kleinere Laplace-Varianz; es kann nur zu milde, nie zu strenge Urteile geben.
    """
    width, height = size
    points = np.asarray(quad, dtype=float).reshape(-1, 2)
    x0, y0 = max(0, int(np.floor(points[:, 0].min()))), max(0, int(np.floor(points[:, 1].min())))
    x1, y1 = min(width, int(np.ceil(points[:, 0].max()))), min(height, int(np.ceil(points[:, 1].max())))
    if x1 <= x0 or y1 <= y0 or not len(images):
        return None
    scores, means = [], []
    for image in images:
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        roi = gray[y0:y1, x0:x1]
        scores.append(sharpness(roi))
        means.append(float(np.mean(roi)))
    return {"roi_pixels": [x0, y0, x1 - x0, y1 - y0],
            "roi_box": [x0 / width, y0 / height, (x1 - x0) / width, (y1 - y0) / height],
            "score": float(np.median(scores)), "roi_mean": float(np.median(means)),
            "frames": len(scores), "quelle": source}


def check_focus_at_run_start(
    cam: SetupCamera, reference: dict[str, Any] | None, *, target: int, settle_s: float = 1.0,
    sleep: Callable[[float], None] | None = None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]] | None:
    """OQ-74: Nach dem Kameraneustart am Laufstart die Schaerfe gegen die Einrichtung pruefen.

    ROI ist das bestaetigte Anzeige-Viereck (`quad_focus_reference`), Normierung
    wie in der Einrichtung. Unter der Schwelle einmal von unten neu setzen;
    bleibt sie darunter: WARNUNG mit sichtbarem Text. Der Lauf startet trotzdem,
    die Freigabe bleibt unberuehrt. `None` ohne Referenz.
    """
    if not reference:
        return None
    result, frames = _check_lens_after_restart(
        cam, tuple(reference["roi_box"]), int(target), float(reference["score"]), reference.get("roi_mean"),
        settle_s=settle_s, sleep=sleep, should_stop=None, info=None, label="Fokuspruefung Laufstart",
    )
    result.update(reference=deepcopy(reference), text=None)
    if result["status"] == "WARNUNG":
        result["text"] = (f"Bild nach Kamerastart unschärfer als bei der Einrichtung "
                          f"({100 * result['reapproach']['ratio']:.0f} %) – Fokus prüfen")
    elif result["reapproach"] is not None:
        result["text"] = (f"Fokus nach Kamerastart neu gesetzt (vorher {100 * result['after_restart']['ratio']:.0f} %, "
                          f"danach {100 * result['reapproach']['ratio']:.0f} % der Einrichtungsschärfe)")
    return result, frames


def focus_check(roi: dict[str, Any], end_check: dict[str, Any] | None) -> dict[str, Any]:
    """Pruefzeile `fokus` fuer den Einrichtungsbericht (OQ-74)."""
    status, reasons = "OK", []
    if roi.get("quelle") != "lcd_hinweis":
        status = "WARNUNG"
        reasons.append("Fokus ohne LCD-Hinweis gemessen (mittleres Bilddrittel). Einrichtung erneut starten; "
                       "dann misst die Fokussuche auf der Anzeige")
    if end_check is not None:
        if end_check.get("status") == "WARNUNG":
            status = "WARNUNG"
        if end_check.get("reason"):
            reasons.append(end_check["reason"])
    check: dict[str, Any] = {"status": status, "metrics": {"roi": deepcopy(roi), "endpruefung": deepcopy(end_check)}}
    if reasons:
        check["reason"] = "; ".join(reasons)
    return check


def focus_camera(
    cam: SetupCamera,
    hint_box: HintBox | None,
    *,
    start_focus: int = DEFAULT_FOCUS_START,
    info: Callable[[str], None] | None = None,
    settle_s: float = 1.0,
    sleep: Callable[[float], None] | None = None,
    on_sample: Callable[[int, float], None] | None = None,
    on_fallback: Callable[[], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[CameraSettings, FocusMeasurements]:
    """Grob bergsteigen, fein aufsteigend; jede Messung von unten anfahren.

    Nach Endpruefung Automatiken einschwingen lassen und Werte fest uebernehmen.
    Fokus 0 bleibt ausgeschlossen, weil keine Anfahrt von unten moeglich ist.
    `on_sample` meldet Suchproben, nicht die getrennte Endpruefung.
    `on_fallback` meldet den Wechsel zum Vollsweep. `should_stop` bricht
    zwischen Proben und innerhalb von Wartezeiten alle hoechstens 0,5 s ab.
    """
    sleep = sleep or time.sleep
    check_cancelled(should_stop)
    probe = _FocusProbe(cam, hint_box, settle_s=settle_s, sleep=sleep, should_stop=should_stop,
                        label="Fokus-Sweep")
    roi_means: dict[int, float] = {}

    def measure(focus: int) -> float:
        score = probe.measure(focus)
        roi_means[focus] = probe.mean
        return score

    cam.set_controls([("focus_automatic_continuous", 0)])
    if info is not None:
        info("Fokus: Bergsteigen")

    def fallback() -> None:
        if info is not None:
            info("Fokus: Vollsweep (Rueckfall)")
        if on_fallback is not None:
            on_fallback()

    best_focus, sweep_log = climb_focus(
        measure, start=start_focus, lo=1, on_fallback=fallback, on_sample=on_sample,
    )
    check_cancelled(should_stop)
    best_measured = max(score for _, score in sweep_log)
    sweep_log.roi_means = roi_means
    verified = probe.measure(best_focus)
    attempts = 1
    if not verified >= FOCUS_VERIFY_RATIO * best_measured:
        verified = probe.measure(best_focus)
        attempts = 2
    # Bild der Endpruefung: letzter Stand vor dem Kameraneustart (OQ-74).
    sweep_log.verify_frame, sweep_log.verify_roi_mean = probe.frame, probe.mean
    if not verified >= FOCUS_VERIFY_RATIO * best_measured:
        raise SetupError(
            f"Fokus nicht stabil: Schaerfe {verified:.1f} von {best_measured:.1f} erreicht - Einrichtung neu starten"
        )
    sweep_log.focus_verify = {
        "target": best_focus, "best_measured": best_measured, "verified": verified, "attempts": attempts,
        "approach": "from_below", "backlash_margin": FOCUS_BACKLASH_MARGIN,
    }
    if info is not None:
        info(f"Fokus geprueft: Schaerfe {verified:.1f} von {best_measured:.1f}")
    cam.set_controls([("auto_exposure", 3), ("white_balance_automatic", 1)])
    probe.wait(WHITE_BALANCE_SETTLE_S)
    readback = cam.get_controls(["exposure_time_absolute", "white_balance_temperature", "gain"])
    settings = CameraSettings(
        model=STREAMCAM_MODEL,
        usb_id=STREAMCAM_USB_ID,
        size=FOCUS_SOURCE_SIZE,
        fourcc="YUYV",
        fps=30,
        controls={
            "focus_absolute": best_focus,
            "exposure_time_absolute": readback["exposure_time_absolute"],
            "white_balance_temperature": readback["white_balance_temperature"],
            "gain": readback["gain"],
        },
        device=cam.device,
    )
    return settings, sweep_log


def _keep_attempt_still(out_dir: Path, attempt: int) -> None:
    """Mittelbild eines abgelehnten Versuchs behalten, bevor der naechste still.png schreibt.

    Umbenennen statt neu kodieren: keine Rechenlast, keine JPEG-/PNG-Neukodierung.
    still.png bleibt das Bild des zuletzt verwendeten Versuchs. Diagnosefehler
    aendern den Einrichtungsausgang nicht.
    """
    try:
        (out_dir / "still.png").replace(out_dir / f"still-versuch-{attempt}.png")
    except OSError:
        pass


@dataclass
class AssistResult:
    first: np.ndarray
    second: np.ndarray
    first_text: str
    second_text: str
    hint_box: HintBox
    fit: Any
    offset_check: Any
    final_checks: Any
    reader_check: Any | None
    stability_elapsed_s: float
    setup_attempt: int
    stability_frames: tuple[np.ndarray, ...] = ()


def assist_measure(
    cam: SetupCamera,
    *,
    cell_text: CellTextSource,
    expected_size: tuple[int, int],
    out_dir: Path,
    hint_box: HintBox | None = None,
    stability_s: float = MIN_STABILITY_S,
    min_stability_s: float = MIN_STABILITY_S,
    stack_frames: int = 1,
    fit_attempts: int = 1,
    on_attempt: Callable[[dict], None] | None = None,
    templates: Path | None = None,
    templates_sha256: str | None = None,
    reference_kind: str = "eingabe",
    report: Callable[[dict], None] = lambda _checks: None,
    on_phase: Callable[[str, int], None] = lambda _phase, _attempt: None,
    on_wait: Callable[[float, float], None] = lambda _elapsed, _total: None,
    info: Callable[[str], None] = lambda _message: None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> AssistResult:
    """Zwei Standbilder mit Zellentext, Punktraster, 2j und Setup-Pruefungen.

    Wirft `SetupError` mit Bedienertext, sobald ein Schritt FEHLER meldet.
    `on_attempt` erhaelt attempt (ab 1), still (still/stability) und masked
    direkt nach der Aufnahme und erneut nach der bilduebergreifenden Maske.
    Nach der Startsuche folgt fit (Ablehnungsgrund oder "ok"); spaetere
    Maskenupdates erhalten diesen Eintrag in der Diagnose.
    Bei Aufnahmefehlern: masked=None und error mit dem Abbruchgrund.
    `on_phase` meldet Unterphase und Suchversuch (ab 1); `on_wait` die
    bereits geschlafene Zeit nach jeder Scheibe von hoechstens 0,5 s.
    """
    sleep = sleep or time.sleep
    monotonic = monotonic or time.monotonic
    if not math.isfinite(stability_s) or stability_s < min_stability_s:
        raise SetupError(f"Stabilitaetsmessung muss mindestens {min_stability_s:.0f} Sekunden dauern")
    if fit_attempts < 1:
        raise SetupError("Startsuche braucht mindestens einen Versuch")

    stability_frames: list[np.ndarray] = []

    def capture_text(attempt: int, still: str) -> tuple[np.ndarray, str]:
        def capture() -> np.ndarray:
            # Bei einem erneuten seriell geklammerten Versuch nur die Bilder
            # behalten, aus denen das tatsaechlich verwendete Mittel entsteht.
            stability_frames.clear()
            image = mean_still(cam, stack_frames,
                               captured_frames=stability_frames if still == "stability" else None)
            if still == "still":
                phase("zelltext", attempt)
            return image

        try:
            return cell_text(capture)
        except Exception as exc:  # noqa: BLE001 - abgebrochene Aufnahme fuer Diagnose sichern
            if on_attempt is not None:
                on_attempt({"attempt": attempt, "still": still, "masked": None, "error": str(exc)})
            raise

    def phase(name: str, attempt: int) -> None:
        check_cancelled(should_stop)
        on_phase(name, attempt)
        check_cancelled(should_stop)

    explicit_hint_box = hint_box
    for attempt in range(1, fit_attempts + 1):
        phase("mitteln", attempt)
        if stack_frames != 1 or fit_attempts != 1:
            info(f"Punktraster-Startsuche: Versuch {attempt}/{fit_attempts} ({stack_frames} Bilder)")
        first, first_text = capture_text(attempt, "still")
        first_captured_at = monotonic()
        if on_attempt is not None:
            on_attempt({"attempt": attempt, "still": "still", "masked": first_text})
        if first.shape[:2] != (expected_size[1], expected_size[0]):
            raise SetupError("Standbild passt nicht zur Kameraaufloesung")
        out_dir.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(out_dir / "still.png"), first):
            raise SetupError("still.png konnte nicht geschrieben werden")
        phase("raster", attempt)
        hint_box = explicit_hint_box if explicit_hint_box is not None else find_green_hint_box(first)
        if hint_box is None:
            if attempt < fit_attempts:
                _keep_attempt_still(out_dir, attempt)
                continue
            raise SetupError("Kein gruener Bereich mit Punktstruktur gefunden; bitte --hint-box angeben")
        fit = fit_lattice(first, hint_box, empty_cells=GSV2AS_EMPTY_CELLS)
        if on_attempt is not None:
            on_attempt({"attempt": attempt, "still": "still", "masked": first_text,
                        "fit": fit if isinstance(fit, str) else "ok"})
        if not isinstance(fit, str):
            break
        if attempt == fit_attempts:
            raise SetupError(f"Punktraster abgelehnt: {fit}; Hinweisbox pruefen oder --hint-box angeben")
        _keep_attempt_still(out_dir, attempt)
    prechecks = check_setup(first, fit)
    report(prechecks.to_dict())
    precheck_failures = []
    for name, result in prechecks.checks.items():
        if getattr(result, "status", None) == "FEHLER" and name != "raster":
            cells = getattr(result, "cells", ())
            if cells:
                label = "Zelle" if len(cells) == 1 else "Zellen"
                name += f" ({label} {', '.join(str(cell) for cell in cells)})"
            # OQ-72: Messwert und Abhilfe gleich in der Abbruchmeldung nennen.
            reason = getattr(result, "reason", None)
            if reason:
                name += f" - {reason}"
            precheck_failures.append(name)
    if precheck_failures:
        raise SetupError(f"Vorpruefung meldet FEHLER: {', '.join(precheck_failures)}; "
                         "Stabilitaetsmessung nicht gestartet")
    phase("stabilitaet", attempt)
    waited = 0.0
    while waited < stability_s:
        interval = min(0.5, stability_s - waited)
        check_cancelled(should_stop)
        sleep(interval)
        check_cancelled(should_stop)
        waited += interval
        on_wait(waited, stability_s)
    phase("zweites_standbild", attempt)
    second, second_text = capture_text(attempt, "stability")
    stability_elapsed_s = monotonic() - first_captured_at
    if on_attempt is not None:
        on_attempt({"attempt": attempt, "still": "stability", "masked": second_text})
    reader_frame_texts = [(first, first_text), (second, second_text)]
    first_text, second_text = mask_changed_cells(first_text, second_text)
    if on_attempt is not None:
        on_attempt({"attempt": attempt, "still": "still", "masked": first_text})
        on_attempt({"attempt": attempt, "still": "stability", "masked": second_text})
    if second.shape != first.shape:
        raise SetupError("Zweites Standbild hat eine andere Bildgroesse")
    if not cv2.imwrite(str(out_dir / "stability.png"), second):
        raise SetupError("stability.png konnte nicht geschrieben werden")
    phase("gegenlesen", attempt)
    frame_texts = [(first, first_text), (second, second_text)]
    original_quad = fit.quad
    try:
        # refine_quad liest ROM-Glyphen direkt; maskierte Zellen haben keine
        # bekannte Glyphe und duerfen den Fit nicht beeinflussen.
        refinement_text = first_text.replace("?", " ")
        candidate_quad, _history = refine_quad(
            [(first, refinement_text)], original_quad, LATTICE_GRID, DEFAULT_TARGET_SIZE,
        )
        old_heldout = raster_offset_check([(second, second_text)], original_quad)
        new_heldout = raster_offset_check([(second, second_text)], candidate_quad)
        if heldout_improves(old_heldout, new_heldout):
            revised = evaluate_quad(first, hint_box, candidate_quad, empty_cells=GSV2AS_EMPTY_CELLS)
            if isinstance(revised, str):
                raise SetupError(f"Verbessertes Raster-Quad abgelehnt: {revised}; kein Vorschlag")
            fit = revised
            info("Raster-Quad nachgefuehrt: zurueckgehaltenes Standbild verbessert")
    except SetupError:
        raise
    except (ValueError, cv2.error) as exc:
        info(f"Raster-Quad nicht nachgefuehrt: {exc}")
    offset_check = raster_offset_check(frame_texts, fit.quad)
    report({"overall": offset_check.status, "checks": {"rasterversatz": offset_check.to_dict()}})
    if offset_check.status == "FEHLER":
        first_offset = raster_offset_check([frame_texts[0]], fit.quad)
        second_offset = raster_offset_check([frame_texts[1]], fit.quad)
        if first_offset.status != "FEHLER" and second_offset.status == "FEHLER":
            raise SetupError(
                "Anzeige hat sich zwischen den Standbildern geaendert (2j: erstes Standbild passt zum Zellentext, "
                "zweites nicht). Zellentext-Feld leer lassen - der Wert wird dann vom GSV-2AS gelesen - "
                "oder schwankende Ziffern mit ? markieren, z. B. +0.4678?"
            )
        raise SetupError("Rasterversatz 2j meldet FEHLER; kein Vorschlag")
    final_checks = check_setup(
        first, fit, stability_image_bgr=second,
        stability_elapsed_s=stability_elapsed_s, offset_check=offset_check,
        stability_min_elapsed_s=min_stability_s,
    )
    if final_checks.overall == "FEHLER":
        report(final_checks.to_dict())
        raise SetupError("Abschliessende Einrichtungspruefung meldet FEHLER; kein Vorschlag")
    reader_check = None
    if templates is not None:
        reader_check = diagnose_reader(reader_frame_texts, fit.quad, templates, templates_sha256,
                                       reference_kind=reference_kind)
    return AssistResult(
        first=first, second=second, first_text=first_text, second_text=second_text, hint_box=hint_box,
        fit=fit, offset_check=offset_check, final_checks=final_checks, reader_check=reader_check,
        stability_elapsed_s=stability_elapsed_s, setup_attempt=attempt,
        stability_frames=tuple(stability_frames),
    )


def write_overlays(
    image: np.ndarray,
    quad,
    grid: CharGrid,
    out_dir: Path,
    *,
    target_size: tuple[int, int] = DEFAULT_TARGET_SIZE,
    fit: Any = None,
    overall: str | None = None,
    edge_cells: tuple[int, ...] | None = None,
    tracking_proposal: RegionProposal | None = None,
    write_sampling: bool = True,
    display_defects: list | tuple = (),
) -> list[Path]:
    """overlay_source.png, overlay_rectified.png und (mit Fit) overlay_sampling.png."""
    written: list[Path] = []
    if fit is not None:
        overlay_source = draw_source_overlay(image, fit, overall)
    else:
        overlay_source = image.copy()
        points = np.array(quad, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(overlay_source, [points], isClosed=True, color=(0, 0, 255), thickness=2)
    if tracking_proposal is not None:
        if overlay_source.ndim == 2:
            overlay_source = cv2.cvtColor(overlay_source, cv2.COLOR_GRAY2BGR)
        config = tracking_proposal.config
        for region in tracking_proposal.regions:
            x, y = region.centre
            h = region.size // 2
            r = h + config["search_radius_px"] + config["interpolation_guard_px"]
            cv2.rectangle(overlay_source, (x-r, y-r), (x+r, y+r), (255, 180, 0), 1)
            cv2.rectangle(overlay_source, (x-h, y-h), (x+h, y+h), (255, 0, 255), 1)
        for edge in tracking_proposal.edges:
            point = tuple(np.rint(edge.point).astype(int))
            cv2.circle(overlay_source, point, 2, (0, 160, 255), -1)
        for row, (label, color) in enumerate((
            ("Rahmenbereiche", (255, 0, 255)),
            ("Suchfenster inkl. Interpolation", (255, 180, 0)),
            ("LCD-Randpunkte", (0, 160, 255)),
        )):
            cv2.putText(overlay_source, label, (8, 42 + row*20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    crop = rectify(image, quad, target_size=target_size)
    if display_defects:
        if overlay_source.ndim == 2:
            overlay_source = cv2.cvtColor(overlay_source, cv2.COLOR_GRAY2BGR)
        inverse = np.linalg.inv(np.asarray(crop.homography).reshape(3, 3))
        points = np.asarray([d['rectified'] for d in display_defects], np.float32).reshape(-1, 1, 2)
        source_points = cv2.perspectiveTransform(points, inverse).reshape(-1, 2)
        for defect, point in zip(display_defects, source_points, strict=True):
            x, y = np.rint(point).astype(int)
            cv2.circle(overlay_source, (x, y), 5, (0, 180, 255), 1)
            cv2.putText(overlay_source, f"Z{defect['cell']} {defect['kind']}", (x + 6, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 180, 255), 1)
    cv2.imwrite(str(out_dir / "overlay_source.png"), overlay_source)
    written.append(out_dir / "overlay_source.png")
    if write_sampling and fit is not None and edge_cells is not None:
        cv2.imwrite(str(out_dir / "overlay_sampling.png"), draw_sampling_overlay(crop.image, edge_cells=edge_cells))
        written.append(out_dir / "overlay_sampling.png")
    rectified = crop.image
    rectified = cv2.cvtColor(rectified, cv2.COLOR_GRAY2BGR) if rectified.ndim == 2 else rectified.copy()
    for i, (x, y, w, h) in enumerate(grid.cell_boxes()):
        cv2.rectangle(rectified, (x, y), (x + w, y + h), (0, 255, 0), 1)
        cv2.putText(rectified, str(i), (x + 1, max(y + 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
    for defect in display_defects:
        x, y = np.rint(defect['rectified']).astype(int)
        cv2.circle(rectified, (x, y), 4, (0, 180, 255), 1)
        cv2.putText(rectified, f"Z{defect['cell']} {defect['kind']}", (x + 5, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 180, 255), 1)
    cv2.imwrite(str(out_dir / "overlay_rectified.png"), rectified)
    written.append(out_dir / "overlay_rectified.png")
    return written


def propose_with_fit(
    image: np.ndarray,
    *,
    fit: Any,
    frame_path: Path,
    camera_settings: CameraSettings,
    device_id: str,
    session_id: str,
    out_dir: Path,
    cell_text: str | None = None,
    offset_check: Any = None,
    final_checks: Any = None,
    stability_image_bgr: np.ndarray | None = None,
    stability_images: tuple[np.ndarray, ...] = (),
    stability_elapsed_s: float | None = None,
    stability_min_elapsed_s: float = MIN_STABILITY_S,
    setup_attempt: int | None = None,
    reader_check: Any = None,
    live_tracking: bool = False,
    exposure_adjust: dict[str, Any] | None = None,
    focus_check: dict[str, Any] | None = None,
) -> dict:
    """Punktraster-Vorschlag; Rahmenpruefung nur bei ausdruecklichem Live-Opt-in.

    `focus_check` (aus `focus_check()`) erscheint als erste Pruefzeile `fokus`.
    """
    height, width = image.shape[:2]
    if (width, height) != tuple(camera_settings.size):
        sw, sh = camera_settings.size
        raise SetupError(
            f"Bild ist {width}x{height}, camera-settings.json verlangt aber {sw}x{sh} - "
            "Bild passt nicht zu den Kameraeinstellungen dieser Sitzung."
        )
    if offset_check is None and cell_text is None:
        raise SetupError("Rasterversatz 2j verlangt einen Zellentext")
    quad = fit.quad
    grid = LATTICE_GRID
    min_px = source_dot_column_px(grid, quad, DEFAULT_TARGET_SIZE)
    if offset_check is None:
        offset_check = raster_offset_check([(image, cell_text)], quad)
    if offset_check.status == "FEHLER":
        raise SetupError(f"Rasterversatz 2j: FEHLER — {offset_check.reason or offset_check.metrics}")
    checks = final_checks
    if checks is None:
        checks = check_setup(
            image, fit, stability_image_bgr=stability_image_bgr,
            stability_elapsed_s=stability_elapsed_s, offset_check=offset_check,
            stability_min_elapsed_s=stability_min_elapsed_s,
        )
    if checks.overall == "FEHLER":
        raise SetupError("Einrichtungspruefung meldet FEHLER; kein Vorschlag")
    checks_dict = checks.to_dict()
    raster_result = checks_dict.get("checks", {}).get("rasterversatz")
    if not isinstance(raster_result, dict) or raster_result.get("status") not in {"OK", "WARNUNG"}:
        raise SetupError("Einrichtungspruefung ohne gueltigen rasterversatz; kein Vorschlag")
    if exposure_adjust is not None:
        exposure_check = checks_dict['checks'].setdefault('belichtung', {'status': 'OK', 'metrics': {}})
        exposure_check['metrics']['exposure_adjust'] = deepcopy(exposure_adjust)
        if not exposure_adjust['achieved']:
            exposure_check['status'] = 'WARNUNG'
            final_level = exposure_adjust.get('final_level')
            too_bright = final_level is not None and final_level > EXPOSURE_BAND[1]
            exposure_check.setdefault('reason', 'Automatischer Belichtungsabgleich ohne bestätigtes Zielband: ' + (
                'Display zu hell, helle Lichtquelle oder Reflex abschatten und neu einrichten' if too_bright else
                'Kamera näher stellen oder helle Umgebung abdecken und neu einrichten'))
            if checks_dict['overall'] == 'OK':
                checks_dict['overall'] = 'WARNUNG'
    if focus_check is not None:
        checks_dict["checks"] = {"fokus": deepcopy(focus_check), **checks_dict["checks"]}
        if focus_check["status"] == "WARNUNG" and checks_dict["overall"] == "OK":
            checks_dict["overall"] = "WARNUNG"
    if reader_check is not None:
        checks_dict["checks"]["gegenlesen"] = reader_check.to_dict()
        if reader_check.status == "FEHLER":
            checks_dict["overall"] = "FEHLER"
        elif reader_check.status == "WARNUNG" and checks_dict["overall"] == "OK":
            checks_dict["overall"] = "WARNUNG"
    tracking_proposal = None
    if live_tracking:
        stills = [image] if stability_image_bgr is None else [image, stability_image_bgr]
        defects = display_defect_check(stills, quad, grid=grid, cell_text=cell_text)
        checks_dict['checks']['displayfehler'] = defects.to_dict()
        if defects.status == 'WARNUNG' and checks_dict['overall'] == 'OK':
            checks_dict['overall'] = 'WARNUNG'
        tracking_proposal = propose_regions(image, quad, stability_image=stability_image_bgr,
                                            stability_images=stability_images)
        if stability_image_bgr is None:
            tracking_proposal = replace(tracking_proposal, ok=False,
                                        reasons=(*tracking_proposal.reasons, "rahmenbereiche_zweitbild_fehlt"))
        # R13-25: Reserve nur mit Ersatz ohne Lagekonsistenz erreichbar.
        # Bestaetigung bleibt moeglich (Konzept §4), Risiko wird benannt.
        # Welche Bereiche das sind, steht in den Kennzahlen, damit eine
        # manuelle Korrektur die WARNUNG nicht verliert.
        _bind_fallback_regions(tracking_proposal, _fallback_centres(tracking_proposal.metrics, bound=False))
        checks_dict["checks"]["nachfuehrung"] = _tracking_check(tracking_proposal)
        if not tracking_proposal.ok:
            checks_dict["overall"] = "FEHLER"
        elif checks_dict["checks"]["nachfuehrung"]["status"] == "WARNUNG" and checks_dict["overall"] == "OK":
            checks_dict["overall"] = "WARNUNG"
    # OQ-74: Schaerfereferenz fuer die Pruefung nach dem Kameraneustart am Laufstart.
    if stability_images:
        focus_reference = quad_focus_reference(stability_images, quad, (width, height),
                                               source="stabilitaet_einzelbilder")
    else:
        focus_reference = quad_focus_reference(
            [image if stability_image_bgr is None else stability_image_bgr], quad, (width, height),
            source="mittelbild")
    proposal = {
        "frame": str(frame_path),
        "device_id": device_id,
        "session_id": session_id,
        "quad": quad,
        "target_size": list(DEFAULT_TARGET_SIZE),
        "grid": grid.to_dict(),
        "grid_source": "dot_lattice",
        "scaler_crop": None,
        "min_source_dot_column_px": min_px,
        "native_scale": 1.0,
        "min_native_dot_column_px": min_px,
        "camera": camera_settings.to_dict(),
        "setup_checks": checks_dict,
    }
    if focus_reference is not None:
        proposal["focus_reference"] = focus_reference
    if tracking_proposal is not None:
        proposal["overlay_evidence"] = {
            "quad": quad, "assigned_points": fit.assigned_points, "rejected_points": fit.rejected_points,
            "edge_cells": list(checks.checks["kanten"].cells), "overall": checks_dict["overall"],
        }
        proposal["live_tracking"] = {
            "version": 1, "method": "rahmenbereiche", "config": tracking_proposal.config,
            "proposal": tracking_proposal.to_dict(),
            "frame_sha256": hashlib.sha256(Path(frame_path).read_bytes()).hexdigest(),
            "proposal_revision": uuid.uuid4().hex,
            "auswahl": "automatisch", "edits": [],
        }
        if stability_image_bgr is not None:
            # assist_measure hat das gemittelte Bild bereits geschrieben.
            # Nur dessen unveraenderte Datei binden, keine Einzelbilder ablegen.
            out_dir.mkdir(parents=True, exist_ok=True)
            stability_path = out_dir / "stability.png"
            if stability_path.exists():
                saved = cv2.imread(str(stability_path), cv2.IMREAD_UNCHANGED)
                if saved is None or not np.array_equal(saved, stability_image_bgr):
                    raise SetupError("Stabilitaetsbild abweichend vom aufgenommenen Bild - neu einrichten")
            elif not cv2.imwrite(str(stability_path), stability_image_bgr):
                raise SetupError("Stabilitaetsbild konnte nicht gespeichert werden")
            proposal["live_tracking"]["stability_frame"] = {
                "path": str(stability_path), "sha256": hashlib.sha256(stability_path.read_bytes()).hexdigest(),
            }
    if setup_attempt is not None:
        proposal["setup_attempt"] = setup_attempt
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    write_overlays(
        image, quad, grid, out_dir, fit=fit, overall=checks_dict["overall"],
        edge_cells=tuple(checks.checks["kanten"].cells),
        **({"tracking_proposal": tracking_proposal} if tracking_proposal is not None else {}),
        display_defects=checks_dict['checks'].get('displayfehler', {}).get('metrics', {}).get('defects', []),
    )
    return proposal


def _fallback_centres(metrics: dict, *, bound: bool = True) -> list[list[int]]:
    """Mittelpunkte der Ersatzbereiche ohne Lagekonsistenz (R13-25).

    Massgeblich sind die Ersatzkennzahlen der letzten Stufe
    (``stability_consistency_px`` = None). Nach einer manuellen Korrektur
    fehlen diese; dann wird die gebundene Liste unveraendert weitergefuehrt
    (``bound``).
    """
    if bound and "stability_fallback_centres" in metrics:
        return [list(centre) for centre in metrics["stability_fallback_centres"]]
    if (metrics.get("stability_replacements") and "stability_consistency_px" in metrics
            and metrics["stability_consistency_px"] is None):
        return [list(item["new_centre"]) for item in metrics["stability_replacements"]]
    return []


def _bind_fallback_regions(tracking: Any, fallback: list[list[int]]) -> None:
    """Ersatzliste und den davon noch im Satz stehenden Teil in die Kennzahlen schreiben."""
    tracking.metrics["stability_fallback_centres"] = fallback
    tracking.metrics["stability_fallback_remaining"] = [
        list(region.centre) for region in tracking.regions if list(region.centre) in fallback
    ]


def _tracking_check(tracking: Any) -> dict:
    """nachfuehrung: FEHLER vor WARNUNG (Ersatz ohne Lagekonsistenz im Satz) vor OK."""
    unchecked = bool(tracking.metrics.get("stability_fallback_remaining"))
    return {
        "status": "FEHLER" if not tracking.ok else "WARNUNG" if unchecked else "OK",
        "reason": ("; ".join(REASONS[reason] for reason in tracking.reasons)
                   or (REASONS["rahmenbereiche_ersatz_ohne_lagekonsistenz"] if unchecked else None)),
        "metrics": tracking.metrics,
    }


def edit_regions(proposal: dict, *, add: list, remove: list, out_dir: Path, at_utc: str,
                 stability_images: tuple[np.ndarray, ...] = ()) -> dict:
    """Auswahl am unveraenderten Standbild pruefen und neu versionieren."""
    if "overlay_evidence" not in proposal:
        raise SetupError("Vorschlag ohne Overlay-Belege - neu einrichten")
    block = proposal["live_tracking"]
    current = block["proposal"]["regions"]
    if not isinstance(add, list) or not isinstance(remove, list) or not (add or remove):
        raise SetupInputError("Bereichsaenderung braucht Listen add und remove mit mindestens einer Aenderung")
    if (any(type(index) is not int or not 0 <= index < len(current) for index in remove)
            or len(set(remove)) != len(remove)):
        raise SetupInputError("Ungueltiger oder doppelter Bereichsindex")
    if len(current) - len(remove) + len(add) > 24:
        raise SetupInputError("Hoechstens 24 Rahmenbereiche erlaubt")
    if len(block.get("edits", [])) + len(add) + len(remove) > 50:
        raise SetupError("Hoechstens 50 Bereichsaenderungen je Vorschlag erlaubt - neu einrichten")
    for point in add:
        if (not isinstance(point, list) or len(point) != 2
                or any(type(value) not in (int, float) or (type(value) is float and not math.isfinite(value))
                       for value in point)):
            raise SetupInputError("Bereich braucht zwei endliche Pixelkoordinaten")
    frame = Path(proposal["frame"])
    if not frame.is_file() or hashlib.sha256(frame.read_bytes()).hexdigest() != block["frame_sha256"]:
        raise SetupError("Einrichtungsbild fehlt oder wurde geaendert - neu einrichten")
    image = cv2.imread(str(frame))
    if image is None:
        raise SetupError("Einrichtungsbild nicht lesbar - neu einrichten")
    height, width = image.shape[:2]
    if any(not (0 <= x < width and 0 <= y < height) for x, y in add):
        raise SetupInputError("Bereichskoordinaten liegen ausserhalb des Quellbilds")
    kept = [(index, region["centre"]) for index, region in enumerate(current) if index not in remove]
    if "stability_frame" not in block:
        raise SetupError("Stabilitaetsbild fuer Bereichspruefung fehlt - neu einrichten")
    proof = block["stability_frame"]
    stability_path = Path(proof["path"])
    if (not stability_path.is_file()
            or hashlib.sha256(stability_path.read_bytes()).hexdigest() != proof["sha256"]):
        raise SetupError("Stabilitaetsbild fehlt oder wurde geaendert - neu einrichten")
    stability_image = cv2.imread(str(stability_path))
    if stability_image is None:
        raise SetupError("Stabilitaetsbild nicht lesbar - neu einrichten")
    if len(stability_images) < 8:
        raise SetupError("Stabilitaets-Einzelbilder fuer Bereichspruefung fehlen (mindestens 8) - neu einrichten")
    tracking = proposal_from_regions(image, proposal["quad"], add, FrameTrackingConfig.from_dict(block["config"]),
                                     kept_centres=[centre for _, centre in kept], stability_images=stability_images)
    results = tracking.metrics["centre_results"]
    for (index, centre), result in zip(kept, results[:len(kept)], strict=True):
        if not result["ok"]:
            raise SetupError(
                f"Beibehaltener Rahmenbereich {index} am Mittelpunkt {centre} "
                f"abgelehnt ({result['reason']}) - neu einrichten"
            )
    # Ersatzbereiche ohne Lagekonsistenz bleiben ueber alle Korrekturen
    # benannt; die WARNUNG entfaellt erst, wenn keiner mehr im Satz steht.
    # Gleiche Mittelpunkte zaehlen auch nach Entfernen und Wiederhinzufuegen.
    _bind_fallback_regions(tracking, _fallback_centres(block["proposal"]["metrics"]))
    updated = deepcopy(proposal)
    new_block = updated["live_tracking"]
    new_block.update(proposal=tracking.to_dict(), proposal_revision=uuid.uuid4().hex, auswahl="manuell")
    edits = [{"action": "remove", "index": index, "centre": current[index]["centre"],
              "requested_centre": current[index]["centre"], "used_centre": current[index]["centre"], "at_utc": at_utc}
             for index in remove]
    edits.extend({"action": "add", "requested_centre": point, "at_utc": at_utc, **result}
                 for point, result in zip(add, results[len(kept):], strict=True))
    new_block["edits"] = block.get("edits", []) + edits
    checks = updated["setup_checks"]["checks"]
    checks["nachfuehrung"] = _tracking_check(tracking)
    updated["setup_checks"]["overall"] = max(
        (check["status"] for check in checks.values()), key={"OK": 0, "WARNUNG": 1, "FEHLER": 2}.__getitem__,
    )
    evidence = updated["overlay_evidence"]
    evidence["overall"] = updated["setup_checks"]["overall"]
    write_overlays(image, updated["quad"], CharGrid.from_dict(updated["grid"]), out_dir,
                   target_size=tuple(updated["target_size"]), fit=SimpleNamespace(**evidence),
                   overall=evidence["overall"], edge_cells=tuple(evidence["edge_cells"]),
                   tracking_proposal=tracking, write_sampling=False,
                   display_defects=checks.get('displayfehler', {}).get('metrics', {}).get('defects', []))
    (out_dir / "proposal.json").write_text(json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8")
    return updated


def confirm_proposal(
    proposal: dict,
    *,
    confirmed_by: str,
    resolution_threshold_px: float,
    override_reason: str | None = None,
    accept_default_grid: bool = False,
    now: Callable[[], datetime] | None = None,
) -> SessionProfile:
    """Vorschlag pruefen und ein bestaetigtes Sitzungsprofil bauen."""
    if not confirmed_by or not confirmed_by.strip():
        raise SetupError("Name des Bestaetigenden fehlt")
    now = now or (lambda: datetime.now(UTC))

    if override_reason is not None:
        override_reason = override_reason.strip()
        if not override_reason:
            raise SetupError("--override-reason muss einen nichtleeren Grund enthalten.")

    setup_checks = proposal.get("setup_checks")
    if "setup_checks" in proposal:
        if (
            not isinstance(setup_checks, dict)
            or not isinstance(setup_checks.get("overall"), str)
            or setup_checks["overall"] not in {"OK", "WARNUNG", "FEHLER", "NICHT_GEPRUEFT"}
        ):
            raise SetupError("setup_checks im Vorschlag sind ungueltig (overall fehlt oder ist unbekannt).")
        named_checks = setup_checks.get("checks")
        if not isinstance(named_checks, dict) or any(
            not isinstance(check, dict)
            or (
                not (isinstance(check.get("status"), str) and check["status"] in {"OK", "WARNUNG", "FEHLER"})
                and not (name == "stabilitaet" and "status" in check and check["status"] is None)
            )
            for name, check in named_checks.items()
        ):
            raise SetupError("setup_checks im Vorschlag enthalten ungueltige Einzelpruefungen.")
        if setup_checks["overall"] == "NICHT_GEPRUEFT" and named_checks:
            raise SetupError("NICHT_GEPRUEFT darf keine durchgefuehrten Einzelpruefungen enthalten.")
        failing_checks = [name for name, check in named_checks.items() if check["status"] == "FEHLER"]
        if (setup_checks["overall"] == "FEHLER" or failing_checks) and override_reason is None:
            names = ", ".join(failing_checks) if failing_checks else "Gesamturteil"
            raise SetupError(
                f"Einrichtungspruefungen mit FEHLER: {names}. "
                "Nur mit --override-reason und ausdruecklicher Begruendung bestaetigen."
            )
        setup_checks = dict(setup_checks)
    else:
        setup_checks = {"overall": "NICHT_GEPRUEFT", "checks": {}}

    raster_check = setup_checks["checks"].get("rasterversatz")
    if (raster_check is None or raster_check["status"] not in {"OK", "WARNUNG"}) and override_reason is None:
        raise SetupError("rasterversatz muss OK oder WARNUNG sein; sonst --override-reason angeben.")
    if override_reason is not None:
        setup_checks["override_reason"] = override_reason

    if proposal.get("grid_source") == "default_even_split" and not accept_default_grid:
        raise SetupError(
            "Raster ist der ungeprueft uebernommene Default-Split (grid_source=default_even_split). "
            "--accept-default-grid setzen, um ihn trotzdem zu bestaetigen (Task 3, confirm)."
        )

    if "camera" not in proposal:
        raise SetupError(
            "Vorschlag ohne Kameraeinstellungen (IMX500-Vorschlag?) - propose mit "
            "--camera-settings neu ausfuehren"
        )
    camera_settings = CameraSettings.from_dict(proposal["camera"])

    # Task 10 (Ausrichtungspruefung Ernte <-> Profilbild): das Profilbild
    # selbst muss vorhanden sein, sonst kann kein SHA-256 geschrieben werden
    # und import-harvest.py haette spaeter nichts, wogegen es die Ernte
    # ausrichten koennte - kein Profil ohne diesen Beleg (kein stilles
    # Uebernehmen, AGENTS.md).
    frame_path = Path(proposal["frame"])
    if not frame_path.is_file():
        raise SetupError(
            f"Vorschlag verweist auf ein fehlendes Bild ({frame_path}) - reference_frame kann "
            "nicht geschrieben werden (Task 10, Ausrichtungspruefung)."
        )
    reference_frame = {
        "path": str(frame_path),
        "sha256": hashlib.sha256(frame_path.read_bytes()).hexdigest(),
    }
    live_tracking = proposal.get("live_tracking")
    if live_tracking is not None:
        if (not isinstance(live_tracking, dict) or live_tracking.get("version") != 1
                or live_tracking.get("method") != "rahmenbereiche"
                or live_tracking.get("frame_sha256") != reference_frame["sha256"]):
            raise SetupError("Rahmenbereiche passen nicht zum Einrichtungsbild - neu einrichten")
        tracking_check = setup_checks["checks"].get("nachfuehrung", {})
        if override_reason is not None and tracking_check.get("status") == "FEHLER":
            live_tracking = None
        else:
            live_tracking = deepcopy(live_tracking)

    grid = CharGrid.from_dict(proposal["grid"])
    target_size = tuple(proposal["target_size"])
    min_px = float(proposal["min_source_dot_column_px"])

    # StreamCam (Profil v3): kein ScalerCrop, native_scale immer 1.0 - propose
    # schreibt beide Felder schon so, hier nur noch uebernehmen.
    native_scale = float(proposal["native_scale"])
    min_native_px = float(proposal["min_native_dot_column_px"])

    resolution_ok = min_native_px >= resolution_threshold_px

    profile = SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        device_id=proposal["device_id"],
        session_id=proposal["session_id"],
        quad=[list(p) for p in proposal["quad"]],
        target_size=target_size,
        grid=grid,
        scaler_crop=None,
        min_source_dot_column_px=min_px,
        native_scale=native_scale,
        min_native_dot_column_px=min_native_px,
        resolution_threshold_px=resolution_threshold_px,
        resolution_ok=resolution_ok,
        confirmed_by=confirmed_by,
        confirmed_at_utc=now().isoformat(),
        camera=camera_settings,
        reference_frame=reference_frame,
        setup_checks=setup_checks,
        live_tracking=live_tracking,
    )
    return profile
