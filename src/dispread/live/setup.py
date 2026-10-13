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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from dispread.camera_settings import STREAMCAM_MODEL, STREAMCAM_USB_ID, CameraSettings
from dispread.charcells import CharGrid, source_dot_column_px
from dispread.dotlattice import evaluate_quad, fit_lattice
from dispread.focus_sweep import sharpness, sweep_focus
from dispread.frames.uvc_source import UvcError
from dispread.gsv2as_cell_text import cell_text_from_telegram
from dispread.lattice_offsets import refine_quad
from dispread.rectify import rectify
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile
from dispread.setup_checks import check_setup, diagnose_reader, raster_offset_check
from dispread.setup_hint import find_green_hint_box
from dispread.setup_overlays import draw_sampling_overlay, draw_source_overlay

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
) -> list[Path]:
    """overlay_source.png, overlay_rectified.png und (mit Fit) overlay_sampling.png."""
    written: list[Path] = []
    if fit is not None:
        overlay_source = draw_source_overlay(image, fit, overall)
    else:
        overlay_source = image.copy()
        points = np.array(quad, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(overlay_source, [points], isClosed=True, color=(0, 0, 255), thickness=2)
    cv2.imwrite(str(out_dir / "overlay_source.png"), overlay_source)
    written.append(out_dir / "overlay_source.png")
    crop = rectify(image, quad, target_size=target_size)
    if fit is not None and edge_cells is not None:
        cv2.imwrite(str(out_dir / "overlay_sampling.png"), draw_sampling_overlay(crop.image, edge_cells=edge_cells))
        written.append(out_dir / "overlay_sampling.png")
    rectified = crop.image
    rectified = cv2.cvtColor(rectified, cv2.COLOR_GRAY2BGR) if rectified.ndim == 2 else rectified.copy()
    for i, (x, y, w, h) in enumerate(grid.cell_boxes()):
        cv2.rectangle(rectified, (x, y), (x + w, y + h), (0, 255, 0), 1)
        cv2.putText(rectified, str(i), (x + 1, max(y + 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
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
    reader_check: Any = None,
) -> dict:
    """Vorschlag aus einem Punktraster-Fit (bisher `run_propose` mit Fit)."""
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
        )
    if checks.overall == "FEHLER":
        raise SetupError("Einrichtungspruefung meldet FEHLER; kein Vorschlag")
    checks_dict = checks.to_dict()
    raster_result = checks_dict.get("checks", {}).get("rasterversatz")
    if not isinstance(raster_result, dict) or raster_result.get("status") not in {"OK", "WARNUNG"}:
        raise SetupError("Einrichtungspruefung ohne gueltigen rasterversatz; kein Vorschlag")
    if reader_check is not None:
        checks_dict["checks"]["gegenlesen"] = reader_check.to_dict()
        if reader_check.status == "WARNUNG" and checks_dict["overall"] == "OK":
            checks_dict["overall"] = "WARNUNG"
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
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    write_overlays(
        image, quad, grid, out_dir, fit=fit, overall=checks_dict["overall"],
        edge_cells=tuple(checks.checks["kanten"].cells),
    )
    return proposal


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
    )
    return profile
