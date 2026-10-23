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
from dataclasses import dataclass
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
from dispread.rectify import rectify
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile
from dispread.setup_checks import check_setup, diagnose_reader, display_defect_check, raster_offset_check
from dispread.setup_hint import find_green_hint_box
from dispread.setup_overlays import draw_sampling_overlay, draw_source_overlay
from dispread.workbench.fields import REASONS

GSV2AS_EMPTY_CELLS = (8, 13, 14, 15)
N_CELLS = 16
DEFAULT_TARGET_SIZE = (400, 160)
LATTICE_GRID = CharGrid(n_cells=N_CELLS, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0)
WHITE_BALANCE_SETTLE_S = 3.0
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
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUDRATE = 38400

HintBox = tuple[float, float, float, float]
CellTextSource = Callable[[Callable[[], np.ndarray]], tuple[np.ndarray, str]]


class SetupError(ValueError):
    """Einrichtung abgebrochen; die Meldung ist fuer den Bediener."""


class SetupInputError(SetupError):
    """Ungueltige Eingabe statt eines Konflikts mit dem Einrichtungszustand."""


class SetupCamera(Protocol):
    device: str

    def set_controls(self, controls: list[tuple[str, int]]) -> None: ...

    def get_controls(self, names: list[str]) -> dict[str, int]: ...

    def fresh_still(self, discard: int = 10) -> np.ndarray: ...


def mean_still(cam: SetupCamera, frames: int = 8, discard: int = 10) -> np.ndarray:
    """Frische aufeinanderfolgende Standbilder in float32 mitteln."""
    if frames < 1:
        raise SetupError("Standbildmittelung braucht mindestens ein Bild")
    first = cam.fresh_still(discard=discard)
    if frames == 1:
        return first
    total = first.astype(np.float32)
    for _ in range(frames - 1):
        total += cam.fresh_still(discard=0)
    return np.rint(total / frames).astype(np.uint8)


def offline_text_source(text: str) -> CellTextSource:
    """Zellentext vom Bediener: fuer jedes Standbild derselbe Text."""
    return lambda capture: (capture(), text)


def serial_text_source(port: Any) -> CellTextSource:
    """Zellentext vom GSV-2AS: jedes Standbild mit frischen Telegrammen geklammert."""
    return lambda capture: capture_with_text(capture, port)


def measurement_roi(gray: np.ndarray, hint_box: tuple[float, float, float, float] | None) -> np.ndarray:
    """ROI fuer die Schaerfemessung: `hint_box` (normiert x,y,w,h) oder, ohne
    Angabe, das mittlere Drittel in beiden Achsen."""
    height, width = gray.shape[:2]
    if hint_box is None:
        x0, x1 = width // 3, 2 * width // 3
        y0, y1 = height // 3, 2 * height // 3
    else:
        bx, by, bw, bh = hint_box
        x0, y0 = int(round(bx * width)), int(round(by * height))
        x1, y1 = int(round((bx + bw) * width)), int(round((by + bh) * height))
    return gray[y0:y1, x0:x1]


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


def focus_camera(
    cam: SetupCamera,
    hint_box: HintBox | None,
    *,
    start_focus: int = DEFAULT_FOCUS_START,
    info: Callable[[str], None] | None = None,
    settle_s: float = 1.0,
    sleep: Callable[[float], None] | None = None,
) -> tuple[CameraSettings, FocusMeasurements]:
    """Grob bergsteigen, fein aufsteigend; jede Messung von unten anfahren.

    Nach Endpruefung Automatiken einschwingen lassen und Werte fest uebernehmen.
    Fokus 0 bleibt ausgeschlossen, weil keine Anfahrt von unten moeglich ist.
    """
    sleep = sleep or time.sleep
    last_focus = None

    def measure(focus: int) -> float:
        nonlocal last_focus
        if focus <= 0:
            raise SetupError("Fokus 0 ist nicht von unten erreichbar - Einrichtung neu starten")
        # Auch die erste (unbekannte) Lage und ein erneutes Setzen derselben
        # Lage normalisieren. So fahren Endpruefung und Retry sicher von unten an.
        if last_focus is None or focus <= last_focus:
            cam.set_controls([("focus_absolute", max(0, focus - FOCUS_BACKLASH_MARGIN))])
            sleep(min(settle_s, FOCUS_STABILITY_TIMEOUT_S))
        cam.set_controls([("focus_absolute", focus)])
        last_focus = focus
        deadline = time.monotonic() + FOCUS_STABILITY_TIMEOUT_S
        sleep(min(settle_s, FOCUS_STABILITY_TIMEOUT_S))
        previous = None
        while True:
            try:
                frame = cam.fresh_still(discard=3)
            except UvcError as exc:
                raise UvcError(f"kein Bild von {cam.device} (Fokus-Sweep)") from exc
            gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = sharpness(measurement_roi(gray, hint_box))
            if previous is not None and abs(score - previous) <= abs(previous) * FOCUS_STABILITY_TOLERANCE:
                return score
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return score
            previous = score
            sleep(min(FOCUS_SAMPLE_INTERVAL_S, remaining))

    cam.set_controls([("focus_automatic_continuous", 0)])
    if info is not None:
        info("Fokus: Bergsteigen")
    best_focus, sweep_log = climb_focus(
        measure, start=start_focus, lo=1,
        on_fallback=(lambda: info("Fokus: Vollsweep (Rueckfall)")) if info is not None else None,
    )
    best_measured = max(score for _, score in sweep_log)
    verified = measure(best_focus)
    attempts = 1
    if not verified >= FOCUS_VERIFY_RATIO * best_measured:
        verified = measure(best_focus)
        attempts = 2
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
    sleep(WHITE_BALANCE_SETTLE_S)
    readback = cam.get_controls(["exposure_time_absolute", "white_balance_temperature", "gain"])
    settings = CameraSettings(
        model=STREAMCAM_MODEL,
        usb_id=STREAMCAM_USB_ID,
        size=(1920, 1080),
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
    info: Callable[[str], None] = lambda _message: None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> AssistResult:
    """Zwei Standbilder mit Zellentext, Punktraster, 2j und Setup-Pruefungen.

    Wirft `SetupError` mit Bedienertext, sobald ein Schritt FEHLER meldet.
    `on_attempt` erhaelt attempt (ab 1), still (still/stability) und masked
    direkt nach der Aufnahme und erneut nach der bilduebergreifenden Maske.
    Nach der Startsuche folgt fit (Ablehnungsgrund oder "ok"); spaetere
    Maskenupdates erhalten diesen Eintrag in der Diagnose.
    Bei Aufnahmefehlern: masked=None und error mit dem Abbruchgrund.
    """
    sleep = sleep or time.sleep
    monotonic = monotonic or time.monotonic
    if not math.isfinite(stability_s) or stability_s < min_stability_s:
        raise SetupError(f"Stabilitaetsmessung muss mindestens {min_stability_s:.0f} Sekunden dauern")
    if fit_attempts < 1:
        raise SetupError("Startsuche braucht mindestens einen Versuch")

    def capture() -> np.ndarray:
        return mean_still(cam, stack_frames)

    def capture_text(attempt: int, still: str) -> tuple[np.ndarray, str]:
        try:
            return cell_text(capture)
        except Exception as exc:  # noqa: BLE001 - abgebrochene Aufnahme fuer Diagnose sichern
            if on_attempt is not None:
                on_attempt({"attempt": attempt, "still": still, "masked": None, "error": str(exc)})
            raise

    explicit_hint_box = hint_box
    for attempt in range(1, fit_attempts + 1):
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
        hint_box = explicit_hint_box if explicit_hint_box is not None else find_green_hint_box(first)
        if hint_box is None:
            if attempt < fit_attempts:
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
    prechecks = check_setup(first, fit)
    report(prechecks.to_dict())
    precheck_failures = [
        name for name, result in prechecks.checks.items()
        if getattr(result, "status", None) == "FEHLER" and name != "raster"
    ]
    if precheck_failures:
        raise SetupError("Vorpruefung meldet FEHLER; Stabilitaetsmessung nicht gestartet")
    sleep(stability_s)
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
    stability_elapsed_s: float | None = None,
    stability_min_elapsed_s: float = MIN_STABILITY_S,
    setup_attempt: int | None = None,
    reader_check: Any = None,
    live_tracking: bool = False,
) -> dict:
    """Punktraster-Vorschlag; Rahmenpruefung nur bei ausdruecklichem Live-Opt-in."""
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
        tracking_proposal = propose_regions(image, quad)
        checks_dict["checks"]["nachfuehrung"] = {
            "status": "OK" if tracking_proposal.ok else "FEHLER",
            "reason": "; ".join(REASONS[reason] for reason in tracking_proposal.reasons) or None,
            "metrics": tracking_proposal.metrics,
        }
        if not tracking_proposal.ok:
            checks_dict["overall"] = "FEHLER"
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


def edit_regions(proposal: dict, *, add: list, remove: list, out_dir: Path, at_utc: str) -> dict:
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
    tracking = proposal_from_regions(image, proposal["quad"], add, FrameTrackingConfig.from_dict(block["config"]),
                                     kept_centres=[centre for _, centre in kept])
    results = tracking.metrics["centre_results"]
    for (index, centre), result in zip(kept, results[:len(kept)], strict=True):
        if not result["ok"]:
            raise SetupError(
                f"Beibehaltener Rahmenbereich {index} am Mittelpunkt {centre} "
                f"abgelehnt ({result['reason']}) - neu einrichten"
            )
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
    checks["nachfuehrung"] = {
        "status": "OK" if tracking.ok else "FEHLER",
        "reason": "; ".join(REASONS[reason] for reason in tracking.reasons) or None,
        "metrics": tracking.metrics,
    }
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
