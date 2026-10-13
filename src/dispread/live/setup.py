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
from typing import Any, Protocol

import cv2
import numpy as np

from dispread.camera_settings import STREAMCAM_MODEL, STREAMCAM_USB_ID, CameraSettings
from dispread.charcells import CharGrid
from dispread.focus_sweep import sharpness, sweep_focus
from dispread.frames.uvc_source import UvcError
from dispread.gsv2as_cell_text import cell_text_from_telegram

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
