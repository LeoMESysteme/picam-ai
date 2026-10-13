"""Einrichtung einer Punktraster-Anzeige (GSV-Sensor, Displaytech 161A).

Aus `scripts/harvest-setup.py` (assist/focus/propose/confirm) verlagert,
damit Kommandozeile und Werkbank dieselbe Implementierung nutzen
(Spec 2026-10-12 §1). Kein Kamerazugriff hier: alles laeuft ueber
`SetupCamera`, das die Kommandozeile mit einer direkten Aufnahme und die
Werkbank mit `CameraOwner` erfuellt.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from dispread.camera_settings import STREAMCAM_MODEL, STREAMCAM_USB_ID, CameraSettings
from dispread.charcells import CharGrid
from dispread.dotlattice import evaluate_quad, fit_lattice
from dispread.focus_sweep import sharpness, sweep_focus
from dispread.frames.uvc_source import UvcError
from dispread.gsv2as_cell_text import cell_text_from_telegram
from dispread.lattice_offsets import refine_quad
from dispread.setup_checks import check_setup, diagnose_reader, raster_offset_check
from dispread.setup_hint import find_green_hint_box

GSV2AS_EMPTY_CELLS = (8, 13, 14, 15)
N_CELLS = 16
DEFAULT_TARGET_SIZE = (400, 160)
LATTICE_GRID = CharGrid(n_cells=N_CELLS, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0)
WHITE_BALANCE_SETTLE_S = 3.0
MIN_STABILITY_S = 30.0
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUDRATE = 38400

HintBox = tuple[float, float, float, float]
CellTextSource = Callable[[Callable[[], np.ndarray]], tuple[np.ndarray, str]]


class SetupError(ValueError):
    """Einrichtung abgebrochen; die Meldung ist fuer den Bediener."""


class SetupCamera(Protocol):
    device: str

    def set_controls(self, controls: list[tuple[str, int]]) -> None: ...

    def get_controls(self, names: list[str]) -> dict[str, int]: ...

    def fresh_still(self, discard: int = 10) -> np.ndarray: ...


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


def capture_with_text(capture: Any, port: Any) -> tuple[np.ndarray, str]:
    """Bracket one still with fresh telegrams and mask changes during capture."""
    before = serial_cell_text(port)
    image = capture()
    after = serial_cell_text(port)
    return image, mask_changed_cells(before, after)[0]


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
    settle_s: float = 1.0,
    sleep: Callable[[float], None] | None = None,
) -> tuple[CameraSettings, list[tuple[int, float]]]:
    """Fokus-Sweep, danach Automatiken kurz einschwingen lassen und deren
    Werte als feste Regler uebernehmen (wie bisher `run_focus`)."""
    sleep = sleep or time.sleep

    def measure(focus: int) -> float:
        cam.set_controls([("focus_absolute", focus)])
        sleep(settle_s)
        try:
            frame = cam.fresh_still(discard=3)
        except UvcError as exc:
            raise UvcError(f"kein Bild von {cam.device} (Fokus-Sweep)") from exc
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return sharpness(measurement_roi(gray, hint_box))

    cam.set_controls([("focus_automatic_continuous", 0)])
    best_focus, sweep_log = sweep_focus(measure)
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


def assist_measure(
    cam: SetupCamera,
    *,
    cell_text: CellTextSource,
    expected_size: tuple[int, int],
    out_dir: Path,
    hint_box: HintBox | None = None,
    stability_s: float = MIN_STABILITY_S,
    templates: Path | None = None,
    templates_sha256: str | None = None,
    report: Callable[[dict], None] = lambda _checks: None,
    info: Callable[[str], None] = lambda _message: None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> AssistResult:
    """Zwei Standbilder mit Zellentext, Punktraster, 2j und Setup-Pruefungen.

    Wirft `SetupError` mit Bedienertext, sobald ein Schritt FEHLER meldet."""
    sleep = sleep or time.sleep
    monotonic = monotonic or time.monotonic
    if not math.isfinite(stability_s) or stability_s < MIN_STABILITY_S:
        raise SetupError(f"Stabilitaetsmessung muss mindestens {MIN_STABILITY_S:.0f} Sekunden dauern")
    first, first_text = cell_text(cam.fresh_still)
    first_captured_at = monotonic()
    if first.shape[:2] != (expected_size[1], expected_size[0]):
        raise SetupError("Standbild passt nicht zur Kameraaufloesung")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(out_dir / "still.png"), first):
        raise SetupError("still.png konnte nicht geschrieben werden")
    if hint_box is None:
        hint_box = find_green_hint_box(first)
        if hint_box is None:
            raise SetupError("Kein gruener Bereich mit Punktstruktur gefunden; bitte --hint-box angeben")
    fit = fit_lattice(first, hint_box, empty_cells=GSV2AS_EMPTY_CELLS)
    if isinstance(fit, str):
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
    second, second_text = cell_text(cam.fresh_still)
    stability_elapsed_s = monotonic() - first_captured_at
    first_text, second_text = mask_changed_cells(first_text, second_text)
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
        raise SetupError("Rasterversatz 2j meldet FEHLER; kein Vorschlag")
    final_checks = check_setup(
        first, fit, stability_image_bgr=second,
        stability_elapsed_s=stability_elapsed_s, offset_check=offset_check,
    )
    if final_checks.overall == "FEHLER":
        report(final_checks.to_dict())
        raise SetupError("Abschliessende Einrichtungspruefung meldet FEHLER; kein Vorschlag")
    reader_check = None
    if templates is not None:
        reader_check = diagnose_reader((first, second), fit.quad, templates, templates_sha256)
    return AssistResult(
        first=first, second=second, first_text=first_text, second_text=second_text, hint_box=hint_box,
        fit=fit, offset_check=offset_check, final_checks=final_checks, reader_check=reader_check,
        stability_elapsed_s=stability_elapsed_s,
    )
