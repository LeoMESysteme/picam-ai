#!/usr/bin/env python3
"""Sitzung fuer die automatische Ernte einrichten - Task 3 aus
docs/superpowers/plans/2026-09-23-ernte-phase1.md, `focus` aus dem
StreamCam-Umstieg (Task 4, 2026-09-25).

Aufruf: `assist` fuehrt Fokus-Sweep, frisches Standbild, automatische
Punktraster-Anpassung, Qualitaetspruefungen und Stabilitaetsbild aus. Danach
die Overlays ansehen und den Vorschlag mit `confirm` bestaetigen. `propose`
und `focus` bleiben fuer einzelne Einrichtungsschritte verfuegbar.
Mit `--templates` und `--templates-sha256` meldet `assist` zusaetzlich die
Lesequote und Ablehnungsgruende des eingefrorenen Dot-Matrix-Lesers.

Aufruf:

    ./.venv/bin/python scripts/harvest-setup.py assist \\
        --out setup --device-id gsv2as-01 --session-id lauf1

    ./.venv/bin/python scripts/harvest-setup.py focus \\
        --out var/diagnostics/lauf1/setup

    ./.venv/bin/python scripts/harvest-setup.py propose \\
        --frame var/diagnostics/lauf1/frames/frame_000001.jpg \\
        --hint-box 0.49,0.30,0.34,0.14 \\
        --camera-settings var/diagnostics/lauf1/setup/camera-settings.json \\
        --device-id gsv2as-01 --session-id lauf1 \\
        --out var/diagnostics/lauf1/setup

    ./.venv/bin/python scripts/harvest-setup.py confirm \\
        --proposal var/diagnostics/lauf1/setup/proposal.json \\
        --resolution-threshold-px 2.0 --confirmed-by bediener \\
        --out var/diagnostics/lauf1/setup/profile.json

`focus` faehrt einen Software-Fokus-Sweep (`dispread.focus_sweep.sweep_focus`)
direkt ueber `cv2.VideoCapture` (1920x1080, YUYV, 30 fps - noch ohne
bestaetigten `CameraSettings`-Vertrag, den ermittelt dieser Schritt erst),
friert danach Belichtung und Weissabgleich ein und schreibt die gefundenen
Werte als `CameraSettings` (siehe `dispread.camera_settings`) nach
`camera-settings.json` - das ist die Kamera-Grundlage, die `propose`
zwingend braucht (`--camera-settings`) und die im bestaetigten Profil landet
(Version 3: Bildpixel = native Pixel, StreamCam ohne ScalerCrop/Binning,
Zoom fest 100).

`assist` liest den neunstelligen Zellentext aus dem GSV-2AS-Eingang
(`/dev/ttyUSB0`, 38400 Baud), oder mit `--cell-text` bzw.
`--cell-text-file` aus einer Offline-Vorgabe. Die Rasterversatzpruefung
braucht diesen Text; ein FEHLER verhindert den Vorschlag.

`propose` schlaegt Quad und Zeichenzellenraster vor (Quad ueber
`glass_quad_in_region`, sofern nicht `--quad` gesetzt ist - ein Fehlschlag ist
ein Fehler, kein Rateversuch) und misst die Punktspaltenbreite im Quellbild
(`source_dot_column_px`, Aufloesungs-Gate, Entscheidung 3 des Plans). Es
schreibt einen maschinenlesbaren Vorschlag (`proposal.json`) und
Bediener-Overlays (`overlay_source.png`, `overlay_rectified.png`, bei
`--auto-quad` auch `overlay_sampling.png`). `--auto-quad` verlangt ebenfalls
einen Offline-Zellentext fuer die Rasterversatzpruefung.

## Quaderkennung: `glass_quad_in_region` statt `lcd_quad_in_region`

Vorgabe ist `dispread.glassquad.glass_quad_in_region`: hue-eingeschraenkte
Segmentierung (Referenzfarbton aus dem Zentrum der Hinweisbox geschaetzt) plus
echter Vierpunktquad-Fit (Kantengeraden ausgeglichen, kein `minAreaRect`).
`dispread.workbench.vision.lcd_quad_in_region` (reine Saettigungsschwelle,
`minAreaRect`-Hypothese) bleibt nur als **dokumentierter Rueckfall** hinter
`--detector saturation-only` erreichbar: am GSV-2AS ist auch das Gehaeuse
gesaettigt-blaeulich (gemessen an frame_000412.jpg), die Saettigungsmaske
haengt dort das ganze Gehaeuse ans Quad, und `minAreaRect` kann ein
perspektivisches Trapez (Kamera nicht frontal, Task 6: 30/45 Grad) ohnehin
nicht abbilden. Der Rueckfall existiert nur fuer den Fall, dass ein Geraet
keinen brauchbaren Zentrums-Farbton liefert (z. B. weisses statt farbiges
Backlight) - fuer den GSV-2AS ist er nicht die richtige Wahl.

`confirm` erzeugt daraus ein `SessionProfile` (Task 1). Ein ungeprueftes
Default-Raster (`grid_source == "default_even_split"`) wird nur mit
`--accept-default-grid` uebernommen (Bediener soll ein reines Startraster
nicht versehentlich durchwinken). Liegt die gemessene Punktspaltenbreite
unter der Schwelle, wird trotzdem ein Profil geschrieben (mit
`resolution_ok=False`), aber mit Exit 3 - `import-harvest.py` (Task 5) lehnt
solche Profile ab.

Reiner Einrichtungscode, Stil an `gate-label.py` angelehnt. `propose` und
`confirm` oeffnen weder Kamera noch seriellen Port - sie lesen nur ein
bereits aufgenommenes Bild bzw. den `focus`-Vorschlag. `focus` und `assist`
oeffnen die Kamera direkt (`_open_camera_io`, per Monkeypatch ersetzbar);
`assist` liest ohne Offline-Vorgabe auch den seriellen Eingang.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from dispread.camera_settings import (
    STREAMCAM_MODEL,
    STREAMCAM_USB_ID,
    CameraSettings,
    load_camera_settings,
)
from dispread.charcells import CharGrid, source_dot_column_px
from dispread.dotlattice import evaluate_quad, fit_lattice
from dispread.focus_sweep import sharpness, sweep_focus
from dispread.frames.uvc_source import (
    UvcError,
    UvcSource,
    find_uvc_device,
    v4l2_get_controls,
    v4l2_set_controls,
)
from dispread.glassquad import glass_quad_in_region
from dispread.gsv2as_cell_text import cell_text_from_telegram, validate_offline_cell_text
from dispread.lattice_offsets import refine_quad
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.rectify import rectify
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile
from dispread.setup_checks import RESOLUTION_ERROR_PX, check_setup, diagnose_reader, raster_offset_check
from dispread.setup_hint import find_green_hint_box
from dispread.setup_overlays import draw_sampling_overlay, draw_source_overlay
from dispread.workbench.vision import lcd_quad_in_region

#: Fixe Wartezeit nach dem Umschalten auf automatische Belichtung/Weiss-
#: abgleich (`focus`), bevor die Werte zurueckgelesen werden - kein Regler,
#: die Automatik braucht eine Sekundenbruchteile bis Sekunden dauernde
#: Einschwingzeit (Auftrag).
WHITE_BALANCE_SETTLE_S = 3.0

#: Anzahl Zeichenzellen des GSV-2AS-Displays (HD44780, 16 x 1). Kein
#: CLI-Regler - die Geometrie des angeschlossenen Geraets ist keine freie Wahl.
N_CELLS = 16
DEFAULT_TARGET_SIZE = (400, 160)
# `gsv2as_v1`: Trennzelle und drei Abschlusszellen sind immer leer.
GSV2AS_EMPTY_CELLS = (8, 13, 14, 15)


class SetupError(ValueError):
    """Fehlerhafte Eingabe (CLI-Werte, Datei-Inhalt) - fuehrt zu Exit 2."""


def _parse_float_list(value: str, count: int, name: str) -> list[float]:
    parts = value.split(",")
    if len(parts) != count:
        raise SetupError(f"{name}: erwarte {count} kommagetrennte Zahlen, bekam {len(parts)} ({value!r})")
    try:
        return [float(p) for p in parts]
    except ValueError as exc:
        raise SetupError(f"{name}: keine Zahlen in {value!r}") from exc


def _parse_quad(value: str) -> list[list[float]]:
    values = _parse_float_list(value, 8, "--quad")
    return [[values[i], values[i + 1]] for i in range(0, 8, 2)]


def _parse_hint_box(value: str) -> tuple[float, float, float, float]:
    x, y, w, h = _parse_float_list(value, 4, "--hint-box")
    if not all(math.isfinite(v) for v in (x, y, w, h)) or x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1.000001 or y + h > 1.000001:
        raise SetupError("--hint-box muss eine endliche normierte Box x,y,w,h innerhalb des Bildes sein")
    return x, y, w, h


def _parse_grid(value: str, target_size: tuple[int, int]) -> CharGrid:
    left, pitch, top, bottom = _parse_float_list(value, 4, "--grid")
    grid = CharGrid(n_cells=N_CELLS, left=left, pitch=pitch, top=top, bottom=bottom)
    grid.validate(*target_size)
    return grid


def _parse_target_size(value: str) -> tuple[int, int]:
    try:
        width_s, height_s = value.lower().split("x")
        return int(width_s), int(height_s)
    except ValueError as exc:
        raise SetupError(f"--target-size: erwarte BREITExHOEHE, bekam {value!r}") from exc


def _default_grid(target_size: tuple[int, int]) -> CharGrid:
    """Startraster: 16 gleich breite Zellen ueber die ganze Zielbreite/-hoehe.

    Ausdruecklich als ungeprueft markiert (`grid_source == "default_even_split"`,
    siehe `run_propose`) - `confirm` verlangt `--accept-default-grid`, um ihn
    trotzdem zu uebernehmen (Task 3, Interfaces).
    """
    width, height = target_size
    return CharGrid(n_cells=N_CELLS, left=0.0, pitch=width / N_CELLS, top=0.0, bottom=float(height))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sitzung fuer die automatische Ernte einrichten (Ernte Phase 1, Task 3)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    propose = sub.add_parser("propose", help="Quad- und Rastervorschlag aus einem Einzelbild erzeugen")
    propose.add_argument("--frame", type=Path, required=True, help="Einzelbild (z. B. aus einer Aufzeichnung)")
    propose.add_argument(
        "--hint-box",
        required=True,
        help="normierte achsparallele Box x,y,w,h wie bei manual_roi - nur genutzt, wenn --quad fehlt",
    )
    propose.add_argument("--device-id", required=True)
    propose.add_argument("--session-id", required=True)
    propose.add_argument("--out", type=Path, required=True, help="Zielverzeichnis fuer proposal.json und Overlays")
    propose.add_argument("--quad", default=None, help="x1,y1,x2,y2,x3,y3,x4,y4 in Quellbildpixeln, ersetzt die Suche")
    propose.add_argument("--auto-quad", action="store_true", help="Quad ueber das Punktraster automatisch bestimmen")
    propose.add_argument("--cell-text", help="bekannter Text der ersten neun Anzeigezellen fuer die Rasterversatzpruefung")
    propose.add_argument("--cell-text-file", type=Path, help="UTF-8-Datei mit dem Text der ersten neun Anzeigezellen")
    propose.add_argument("--grid", default=None, help="left,pitch,top,bottom im entzerrten Bild, ersetzt den Default")
    propose.add_argument("--target-size", default="400x160", help="Groesse des entzerrten Bildes, Vorgabe 400x160")
    propose.add_argument(
        "--camera-settings",
        type=Path,
        required=True,
        help=(
            "camera-settings.json aus 'harvest-setup.py focus' - die StreamCam-Einstellungen, "
            "die diese Sitzung reproduzieren muss (Profil v3, Pflichtfeld 'camera'). "
            "--frame muss genau settings.size gross sein."
        ),
    )
    propose.add_argument(
        "--detector",
        choices=("glass", "saturation-only"),
        default="glass",
        help=(
            "Quaderkennung, wenn --quad fehlt. 'glass' (Vorgabe) schraenkt auf den am Zentrum der "
            "Hinweisbox gemessenen Farbton ein und passt ein echtes Vierpunkt-Trapez an. "
            "'saturation-only' ist der dokumentierte Rueckfall auf lcd_quad_in_region (reine "
            "Saettigungsschwelle, minAreaRect) - am GSV-2AS nicht die richtige Wahl (siehe Docstring)."
        ),
    )

    confirm = sub.add_parser("confirm", help="Vorschlag zum SessionProfile bestaetigen")
    confirm.add_argument("--proposal", type=Path, required=True)
    confirm.add_argument(
        "--resolution-threshold-px",
        type=float,
        required=True,
        help="Schwelle fuer die Punktspaltenbreite im Quellbild - KEIN Vorgabewert (Entscheidung 3 des Plans)",
    )
    confirm.add_argument("--confirmed-by", required=True)
    confirm.add_argument("--out", type=Path, required=True)
    confirm.add_argument(
        "--override-reason",
        help="begruendete Uebersteuerung bei FEHLER in den Einrichtungspruefungen",
    )
    confirm.add_argument(
        "--accept-default-grid",
        action="store_true",
        help="erlaubt, ein ungeprueftes Default-Raster (grid_source=default_even_split) zu bestaetigen",
    )
    focus = sub.add_parser(
        "focus", help="Fokus per Software-Sweep bestimmen, Belichtung/Weissabgleich einfrieren"
    )
    focus.add_argument("--out", type=Path, required=True, help="Zielverzeichnis fuer camera-settings.json/control.png")
    focus.add_argument(
        "--hint-box",
        default=None,
        help="normierte Box x,y,w,h - ROI fuer die Schaerfemessung, Vorgabe: mittleres Drittel",
    )
    focus.add_argument("--device", default=None, help="/dev/videoN - Vorgabe: Erkennung ueber die USB-ID")
    focus.add_argument("--settle-s", type=float, default=1.0, help="Wartezeit nach jedem Fokuswert vor der Messung")

    assist = sub.add_parser("assist", help="Fokus, Standbilder, Punktraster und Qualitaetspruefungen in einem Lauf")
    assist.add_argument("--out", type=Path, required=True, help="Zielverzeichnis fuer Bilder, Vorschlag und Overlays")
    assist.add_argument("--device-id", required=True)
    assist.add_argument("--session-id", required=True)
    assist.add_argument("--hint-box", help="normierte Box x,y,w,h; ohne Angabe wird gruenes Glas gesucht")
    assist.add_argument("--stability-s", type=float, default=30.0, help="Abstand der zwei Standbilder in Sekunden, mindestens 30")
    assist.add_argument("--device", default=None, help="Kamerageraet fuer focus und Standbilder")
    assist.add_argument("--templates", type=Path, help="eingefrorene Vorlagendatei fuer optionales Gegenlesen")
    assist.add_argument("--templates-sha256", help="erwartete SHA-256-Pruefsumme der Vorlagendatei")
    assist.add_argument("--cell-text", help="Offline: bekannter Text der ersten neun Anzeigezellen")
    assist.add_argument("--cell-text-file", type=Path, help="Offline: UTF-8-Datei mit dem Text der ersten neun Anzeigezellen")
    assist.add_argument("--serial-port", default="/dev/ttyUSB0", help="serieller GSV-2AS-Eingang, Vorgabe /dev/ttyUSB0")
    assist.add_argument("--baudrate", type=int, default=38400, help="Baudrate des GSV-2AS-Eingangs, Vorgabe 38400")

    return parser


def _offline_cell_text(args: argparse.Namespace) -> str | None:
    """Resolve one explicit offline source before opening hardware."""
    direct = getattr(args, "cell_text", None)
    path = getattr(args, "cell_text_file", None)
    if direct is not None and path is not None:
        raise SetupError("--cell-text und --cell-text-file sind nicht kombinierbar")
    if path is not None:
        try:
            direct = path.read_text(encoding="utf-8").rstrip("\r\n")
        except (OSError, UnicodeError) as exc:
            raise SetupError(f"Zellentext-Datei {path}: {exc}") from exc
    if direct is None:
        return None
    try:
        return validate_offline_cell_text(direct)
    except ValueError as exc:
        raise SetupError(f"Zellentext: {exc}") from exc


def _serial_cell_text(port: Any) -> str:
    """Read a fresh incoming DUT telegram, then map it to physical cells."""
    if hasattr(port, "reset_input_buffer"):
        port.reset_input_buffer()
    line = port.readline().rstrip(b"\r\n")
    try:
        return cell_text_from_telegram(line)
    except ValueError as exc:
        raise SetupError(f"GSV-2AS-Zellentext aus seriellem Strom unlesbar: {exc}") from exc


def _mask_changed_cells(before: str, after: str) -> tuple[str, str]:
    """Only cells unchanged in both observations may inform geometry."""
    if len(before) != len(after):
        raise SetupError("Serieller Zellentext hat unterschiedliche Laenge")
    shared = "".join(left if left == right else "?" for left, right in zip(before, after, strict=True))
    return shared, shared


def _capture_with_serial_text(capture: Any, port: Any) -> tuple[np.ndarray, str]:
    """Bracket one still with fresh telegrams and mask changes during capture."""
    before = _serial_cell_text(port)
    image = capture()
    after = _serial_cell_text(port)
    return image, _mask_changed_cells(before, after)[0]


def _heldout_improves(old_check: Any, new_check: Any) -> bool:
    """Require a strictly smaller worst measured offset on the held-out still."""
    keys = ("max_abs_dx_cols", "max_abs_dy_rows")
    old = [old_check.metrics.get(key) for key in keys]
    new = [new_check.metrics.get(key) for key in keys]
    if any(value is None or not math.isfinite(value) for value in (*old, *new)):
        return False
    return max(new) < max(old) - 0.02 and all(after <= before + 0.01 for before, after in zip(old, new, strict=True))


def run_propose(args: argparse.Namespace) -> int:
    try:
        cell_text = _offline_cell_text(args)
        if args.auto_quad and cell_text is None and getattr(args, "offset_check", None) is None:
            raise SetupError("--auto-quad verlangt --cell-text oder --cell-text-file fuer Rasterversatz 2j")
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        camera_settings = load_camera_settings(args.camera_settings)
    except (OSError, ValueError) as exc:
        print(f"--camera-settings {args.camera_settings}: {exc}", file=sys.stderr)
        return 2

    image = cv2.imread(str(args.frame))
    if image is None:
        print(f"Bild nicht lesbar: {args.frame}", file=sys.stderr)
        return 2
    height, width = image.shape[:2]
    settings_width, settings_height = camera_settings.size
    if (width, height) != (settings_width, settings_height):
        print(
            f"--frame {args.frame} ist {width}x{height}, camera-settings.json verlangt aber "
            f"{settings_width}x{settings_height} - Bild passt nicht zu den Kameraeinstellungen dieser Sitzung.",
            file=sys.stderr,
        )
        return 2

    fit = None
    try:
        target_size = _parse_target_size(args.target_size)
        if cell_text is not None and (target_size != DEFAULT_TARGET_SIZE or args.grid):
            raise SetupError("Rasterversatz 2j verlangt 400x160 und das feste Punktraster ohne --grid")

        if args.auto_quad:
            if args.quad or args.grid or target_size != DEFAULT_TARGET_SIZE:
                raise SetupError("--auto-quad verlangt das feste 400x160-Raster und ist nicht mit --quad/--grid kombinierbar")
            hint_box = _parse_hint_box(args.hint_box)
            fit = getattr(args, "precomputed_fit", None)
            if fit is None:
                fit = fit_lattice(image, hint_box, empty_cells=GSV2AS_EMPTY_CELLS)
            if isinstance(fit, str):
                print(f"Punktraster abgelehnt: {fit}", file=sys.stderr)
                return 2
            quad = fit.quad
        elif args.quad:
            quad = _parse_quad(args.quad)
        else:
            hint_box = _parse_hint_box(args.hint_box)
            if args.detector == "glass":
                # Quellbildpixel direkt (siehe dispread.glassquad).
                found = glass_quad_in_region(image, hint_box)
                quad = [list(p) for p in found] if found is not None else None
            else:
                # lcd_quad_in_region liefert normierte Koordinaten (Bruchteil
                # von Breite/Hoehe); SessionProfile.quad und
                # source_dot_column_px erwarten Quellbildpixel (CharGrid-Tests,
                # Task 1) - deshalb hier zurueckskaliert.
                normalized = lcd_quad_in_region(image, hint_box)
                quad = [[x * width, y * height] for x, y in normalized] if normalized is not None else None
            if quad is None:
                print(
                    f"Kein Quad im Hinweisbereich gefunden (--detector {args.detector}) - kein "
                    "automatischer Vorschlag, es wird nicht geraten (Task 3, propose).",
                    file=sys.stderr,
                )
                return 2

        if fit is None and cell_text is not None:
            hint_box = _parse_hint_box(args.hint_box)
            fit = evaluate_quad(image, hint_box, quad, empty_cells=GSV2AS_EMPTY_CELLS)
            if isinstance(fit, str):
                raise SetupError(f"Vorgegebenes Quad abgelehnt: {fit}")

        if fit is not None:
            grid = CharGrid(n_cells=N_CELLS, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0)
            grid_source = "dot_lattice"
        elif args.grid:
            grid = _parse_grid(args.grid, target_size)
            grid_source = "operator_provided"
        else:
            grid = _default_grid(target_size)
            grid_source = "default_even_split"
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    # Aufloesungs-Gate misst im Quellbild (Entscheidung 3). `source_dot_column_px`
    # bildet die Zellecken ueber die inverse Homographie mit den geometrischen
    # Zielecken [[0,0],[w,0],[w,h],[0,h]] ab (siehe dispread.charcells,
    # dieselbe Eckordnung wie `_order_quad`). `rectify()` unten warpt dagegen
    # mit den Ecken [[0,0],[w-1,0],[w-1,h-1],[0,h-1]] (Pixelmittelpunkt-
    # Konvention fuer `cv2.warpPerspective`). Der Unterschied liegt bei
    # ueblichen Zielgroessen deutlich unter einem Pixel und wird hier bewusst
    # nicht angeglichen: das Gate soll die etwas laengere, geometrische Kante
    # messen, nie eine zu kurze.
    min_px = source_dot_column_px(grid, quad, target_size)

    # StreamCam (Task 4, Profil v3): kein ScalerCrop, kein Sensor-Binning -
    # Bildpixel = native Pixel. Das Aufloesungs-Gate misst deshalb direkt im
    # Quellbild, ohne Umrechnung: native_scale ist immer 1.0.
    native_scale = 1.0
    min_native_dot_column_px = min_px

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    checks = None
    if fit is not None:
        stability_image = getattr(args, "stability_image_bgr", None)
        offset_check = getattr(args, "offset_check", None)
        if offset_check is None:
            offset_check = raster_offset_check([(image, cell_text)], quad)
        if offset_check.status == "FEHLER":
            print(f"Rasterversatz 2j: FEHLER — {offset_check.reason or offset_check.metrics}", file=sys.stderr)
            return 2
        checks = getattr(args, "precomputed_checks", None)
        if checks is None:
            checks = check_setup(
                image, fit,
                stability_image_bgr=stability_image,
                stability_elapsed_s=getattr(args, "stability_elapsed_s", None),
                offset_check=offset_check,
            )
        if checks.overall == "FEHLER":
            print("Einrichtungspruefung meldet FEHLER; kein Vorschlag", file=sys.stderr)
            return 2

    proposal = {
        "frame": str(args.frame),
        "device_id": args.device_id,
        "session_id": args.session_id,
        "quad": quad,
        "target_size": list(target_size),
        "grid": grid.to_dict(),
        "grid_source": grid_source,
        "scaler_crop": None,
        "min_source_dot_column_px": min_px,
        "native_scale": native_scale,
        "min_native_dot_column_px": min_native_dot_column_px,
        "camera": camera_settings.to_dict(),
    }
    if checks is not None:
        checks_dict = checks.to_dict()
        raster_result = checks_dict.get("checks", {}).get("rasterversatz")
        if (cell_text is not None or getattr(args, "offset_check", None) is not None) and (
            not isinstance(raster_result, dict) or raster_result.get("status") not in {"OK", "WARNUNG"}
        ):
            print("Einrichtungspruefung ohne gueltigen rasterversatz; kein Vorschlag", file=sys.stderr)
            return 2
        reader_check = getattr(args, "reader_check", None)
        if reader_check is not None:
            checks_dict["checks"]["gegenlesen"] = reader_check.to_dict()
            if reader_check.status == "WARNUNG" and checks_dict["overall"] == "OK":
                checks_dict["overall"] = "WARNUNG"
        proposal["setup_checks"] = checks_dict
    (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")

    if fit is not None:
        overlay_source = draw_source_overlay(image, fit, proposal["setup_checks"]["overall"])
    else:
        overlay_source = image.copy()
        quad_pts = np.array(quad, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(overlay_source, [quad_pts], isClosed=True, color=(0, 0, 255), thickness=2)
    cv2.imwrite(str(out_dir / "overlay_source.png"), overlay_source)

    crop = rectify(image, quad, target_size=target_size)
    if fit is not None:
        edge_cells = tuple(checks.checks["kanten"].cells)
        cv2.imwrite(str(out_dir / "overlay_sampling.png"), draw_sampling_overlay(crop.image, edge_cells=edge_cells))
    overlay_rectified = crop.image
    if overlay_rectified.ndim == 2:
        overlay_rectified = cv2.cvtColor(overlay_rectified, cv2.COLOR_GRAY2BGR)
    else:
        overlay_rectified = overlay_rectified.copy()
    for i, (x, y, w, h) in enumerate(grid.cell_boxes()):
        cv2.rectangle(overlay_rectified, (x, y), (x + w, y + h), (0, 255, 0), 1)
        cv2.putText(
            overlay_rectified, str(i), (x + 1, max(y + 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1
        )
    cv2.imwrite(str(out_dir / "overlay_rectified.png"), overlay_rectified)

    print(f"Bild: {args.frame} ({width}x{height})")
    print(f"Quad (Quellbildpixel): {quad}")
    print(f"Raster: {grid_source} ({grid.n_cells} Zellen, pitch={grid.pitch:.2f}px)")
    print(f"min_source_dot_column_px: {min_px:.3f}  (native_scale=1.0, StreamCam ohne ScalerCrop/Binning)")
    print(f"Vorschlag geschrieben: {out_dir / 'proposal.json'}")
    overlays = [out_dir / 'overlay_source.png', out_dir / 'overlay_rectified.png']
    if fit is not None:
        overlays.append(out_dir / 'overlay_sampling.png')
    print(f"Overlays: {', '.join(map(str, overlays))}")
    return 0


def run_confirm(args: argparse.Namespace) -> int:
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))

    override_reason = args.override_reason
    if override_reason is not None:
        override_reason = override_reason.strip()
        if not override_reason:
            print("--override-reason muss einen nichtleeren Grund enthalten.", file=sys.stderr)
            return 2

    setup_checks = proposal.get("setup_checks")
    if "setup_checks" in proposal:
        if (
            not isinstance(setup_checks, dict)
            or not isinstance(setup_checks.get("overall"), str)
            or setup_checks["overall"] not in {"OK", "WARNUNG", "FEHLER", "NICHT_GEPRUEFT"}
        ):
            print("setup_checks im Vorschlag sind ungueltig (overall fehlt oder ist unbekannt).", file=sys.stderr)
            return 2
        named_checks = setup_checks.get("checks")
        if not isinstance(named_checks, dict) or any(
            not isinstance(check, dict)
            or (
                not (isinstance(check.get("status"), str) and check["status"] in {"OK", "WARNUNG", "FEHLER"})
                and not (name == "stabilitaet" and "status" in check and check["status"] is None)
            )
            for name, check in named_checks.items()
        ):
            print("setup_checks im Vorschlag enthalten ungueltige Einzelpruefungen.", file=sys.stderr)
            return 2
        if setup_checks["overall"] == "NICHT_GEPRUEFT" and named_checks:
            print("NICHT_GEPRUEFT darf keine durchgefuehrten Einzelpruefungen enthalten.", file=sys.stderr)
            return 2
        failing_checks = [name for name, check in named_checks.items() if check["status"] == "FEHLER"]
        if (setup_checks["overall"] == "FEHLER" or failing_checks) and override_reason is None:
            names = ", ".join(failing_checks) if failing_checks else "Gesamturteil"
            print(
                f"Einrichtungspruefungen mit FEHLER: {names}. "
                "Nur mit --override-reason und ausdruecklicher Begruendung bestaetigen.",
                file=sys.stderr,
            )
            return 2
        setup_checks = dict(setup_checks)
    else:
        setup_checks = {"overall": "NICHT_GEPRUEFT", "checks": {}}

    raster_check = setup_checks["checks"].get("rasterversatz")
    if (raster_check is None or raster_check["status"] not in {"OK", "WARNUNG"}) and override_reason is None:
        print("rasterversatz muss OK oder WARNUNG sein; sonst --override-reason angeben.", file=sys.stderr)
        return 2
    if override_reason is not None:
        setup_checks["override_reason"] = override_reason

    if proposal.get("grid_source") == "default_even_split" and not args.accept_default_grid:
        print(
            "Raster ist der ungeprueft uebernommene Default-Split (grid_source=default_even_split). "
            "--accept-default-grid setzen, um ihn trotzdem zu bestaetigen (Task 3, confirm).",
            file=sys.stderr,
        )
        return 2

    if "camera" not in proposal:
        print(
            "Vorschlag ohne Kameraeinstellungen (IMX500-Vorschlag?) - propose mit "
            "--camera-settings neu ausfuehren",
            file=sys.stderr,
        )
        return 2
    camera_settings = CameraSettings.from_dict(proposal["camera"])

    # Task 10 (Ausrichtungspruefung Ernte <-> Profilbild): das Profilbild
    # selbst muss vorhanden sein, sonst kann kein SHA-256 geschrieben werden
    # und import-harvest.py haette spaeter nichts, wogegen es die Ernte
    # ausrichten koennte - kein Profil ohne diesen Beleg (kein stilles
    # Uebernehmen, AGENTS.md).
    frame_path = Path(proposal["frame"])
    if not frame_path.is_file():
        print(
            f"Vorschlag verweist auf ein fehlendes Bild ({frame_path}) - reference_frame kann "
            "nicht geschrieben werden (Task 10, Ausrichtungspruefung).",
            file=sys.stderr,
        )
        return 2
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

    resolution_ok = min_native_px >= args.resolution_threshold_px

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
        resolution_threshold_px=args.resolution_threshold_px,
        resolution_ok=resolution_ok,
        confirmed_by=args.confirmed_by,
        confirmed_at_utc=datetime.now(UTC).isoformat(),
        camera=camera_settings,
        reference_frame=reference_frame,
        setup_checks=setup_checks,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    profile.save(args.out)

    print(f"Sitzungsprofil geschrieben: {args.out}")
    print(
        f"min_source_dot_column_px={min_px:.3f}  native_scale={native_scale:.4f}  "
        f"min_native_dot_column_px={min_native_px:.3f}  Schwelle={args.resolution_threshold_px}  "
        f"resolution_ok={resolution_ok}"
    )
    if not resolution_ok:
        print(
            "WARNUNG: Aufloesung unter der Schwelle. Das Profil ist geschrieben, aber "
            "import-harvest.py lehnt es ab (Entscheidung 3 des Plans).",
            file=sys.stderr,
        )
        return 3
    return 0


@dataclass
class _CameraIO:
    """Hardware-Zugriffspunkt fuer `focus` - `_open_camera_io` ist die
    einzige Stelle, die echt Kamera/`v4l2-ctl` anfasst; Tests ersetzen die
    ganze Funktion per Monkeypatch (nie echte Hardware in Tests, AGENTS.md).

    `capture` ist die bereits fuer den Fokus-Sweep geoeffnete und
    konfigurierte Aufnahme (1920x1080, YUYV, 30 fps) - direkt gelesen.
    `capture_factory`/`set_controls`/`get_controls` werden unveraendert an
    den abschliessenden `UvcSource`-Schritt weitergereicht, damit der nicht
    ein zweites Mal eigene Hardware-Funktionen aufruft."""

    device: str
    capture: Any
    capture_factory: Any
    set_controls: Any
    get_controls: Any
    #: M-1 final-review.md: der abschliessende `UvcSource`-Kontrollschritt in
    #: `run_focus` prueft `device` jetzt gegen die sysfs-USB-ID - hier
    #: injizierbar, damit Tests keine echte Hardware/kein echtes `/sys`
    #: brauchen (`device` ist in Tests nur ein Platzhalterstring).
    sysfs_root: Path = Path("/sys/class/video4linux")


def _open_camera_io(device: str | None) -> _CameraIO:
    """Oeffnet die StreamCam direkt (1920x1080, YUYV, 30 fps) - noch ohne
    einen bestaetigten `CameraSettings`-Vertrag, den soll `focus` erst
    ermitteln. Immer echte Hardware/echtes `v4l2-ctl` (`cv2` ist hier bereits
    Modul-Top-Level importiert, siehe oben - kein Lazy-Import noetig, dieses
    Skript ist kein Teil von `dispread.frames`)."""
    dev = device or find_uvc_device(STREAMCAM_USB_ID)
    capture = cv2.VideoCapture(dev, cv2.CAP_V4L2)
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    capture.set(cv2.CAP_PROP_FPS, 30)
    return _CameraIO(
        device=dev,
        capture=capture,
        capture_factory=lambda d: cv2.VideoCapture(d, cv2.CAP_V4L2),
        set_controls=v4l2_set_controls,
        get_controls=v4l2_get_controls,
    )


def _measurement_roi(gray: np.ndarray, hint_box: tuple[float, float, float, float] | None) -> np.ndarray:
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


def run_focus(args: argparse.Namespace) -> int:
    try:
        hint_box = _parse_hint_box(args.hint_box) if args.hint_box else None
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    io = _open_camera_io(args.device)

    def measure(focus: int) -> float:
        io.set_controls(io.device, [("focus_absolute", focus)])
        time.sleep(args.settle_s)
        for _ in range(3):
            io.capture.read()
        ok, frame = io.capture.read()
        if not ok:
            raise UvcError(f"kein Bild von {io.device} (Fokus-Sweep)")
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return sharpness(_measurement_roi(gray, hint_box))

    try:
        io.set_controls(io.device, [("focus_automatic_continuous", 0)])
        best_focus, sweep_log = sweep_focus(measure)
        io.set_controls(io.device, [("auto_exposure", 3), ("white_balance_automatic", 1)])
        time.sleep(WHITE_BALANCE_SETTLE_S)
        readback = io.get_controls(
            io.device, ["exposure_time_absolute", "white_balance_temperature", "gain"]
        )
    finally:
        io.capture.release()

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
        device=io.device,
    )

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "camera": settings.to_dict(),
        "focus_sweep": [[f, s] for f, s in sweep_log],
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    (out_dir / "camera-settings.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Kontrollschritt: dieselbe injizierbare Schnittstelle wie oben, kein
    # zweites eigenes Hardware-Oeffnen (siehe `_CameraIO`-Docstring). Das
    # ist der Vertragstest fuer `settings` selbst - setzt und prueft ALLE
    # Regler (Automatiken, feste, und die eben ermittelten), nicht nur den
    # Fokus.
    source = UvcSource(
        settings,
        device=io.device,
        capture_factory=io.capture_factory,
        set_controls=io.set_controls,
        get_controls=io.get_controls,
        sysfs_root=io.sysfs_root,
    )
    source.open()
    try:
        frame = next(iter(source.frames()))
        cv2.imwrite(str(out_dir / "control.png"), frame.image)
    finally:
        source.close()

    print(f"Bester Fokus: {best_focus}")
    print(f"Kameraeinstellungen geschrieben: {out_dir / 'camera-settings.json'}")
    print(f"Kontrollbild: {out_dir / 'control.png'}")
    return 0


def _capture_fresh_still(io: _CameraIO, *, discard: int = 10) -> np.ndarray:
    """Gepufferte Bilder verwerfen; danach genau ein neues Bild uebernehmen."""
    for _ in range(discard):
        ok, _image = io.capture.read()
        if not ok:
            raise UvcError(f"kein Bild von {io.device} beim Leeren des Kamerapuffers")
    ok, image = io.capture.read()
    if not ok or image is None:
        raise UvcError(f"kein frisches Standbild von {io.device}")
    return image


def _print_setup_checks(checks: dict[str, Any]) -> None:
    print("Einrichtungspruefungen:")
    for name, result in checks["checks"].items():
        print(f"  {name}: {result['status'] or 'nicht geprueft'} — {result['metrics']}")
    print(f"Gesamturteil: {checks['overall']}")


def _validate_reader_templates(path: Path, expected_sha256: str) -> None:
    """Pruefsumme und Leserkompatibilitaet vor dem Kamerastart pruefen."""
    try:
        DotMatrixReader.from_file(path, expected_sha256)
    except (OSError, ValueError) as exc:
        raise SetupError(f"Vorlagendatei {path} kann der Leser nicht verwenden: {exc}") from exc


def run_assist(args: argparse.Namespace) -> int:
    if not math.isfinite(args.stability_s) or args.stability_s < 30.0:
        print("--stability-s muss endlich und mindestens 30 Sekunden betragen", file=sys.stderr)
        return 2
    if (args.templates is None) != (args.templates_sha256 is None):
        print("--templates und --templates-sha256 muessen zusammen angegeben werden", file=sys.stderr)
        return 2
    if args.templates is not None:
        try:
            _validate_reader_templates(args.templates, args.templates_sha256)
        except SetupError as exc:
            print(f"Einrichtungsassistent abgebrochen: {exc}", file=sys.stderr)
            return 2
    if args.hint_box is not None:
        try:
            hint_box = _parse_hint_box(args.hint_box)
        except SetupError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    else:
        hint_box = None
    try:
        offline_text = _offline_cell_text(args)
    except SetupError as exc:
        print(f"Einrichtungsassistent abgebrochen: {exc}", file=sys.stderr)
        return 2
    if offline_text is None and (not args.serial_port or args.baudrate <= 0):
        print("Serieller GSV-2AS-Port und positive Baudrate erforderlich", file=sys.stderr)
        return 2

    focus_args = argparse.Namespace(out=args.out, hint_box=args.hint_box, device=args.device, settle_s=1.0)
    try:
        focus_rc = run_focus(focus_args)
    except (OSError, ValueError, UvcError, cv2.error) as exc:
        print(f"Fokus-Sweep abgebrochen: {exc}", file=sys.stderr)
        return 2
    if focus_rc != 0:
        return focus_rc
    serial_port = None
    try:
        if offline_text is None:
            import serial

            serial_port = serial.Serial(args.serial_port, args.baudrate, timeout=2.0)
        settings = load_camera_settings(args.out / "camera-settings.json")
        io = _open_camera_io(args.device)
        try:
            if hasattr(io.capture, "isOpened") and not io.capture.isOpened():
                raise UvcError(f"{io.device}: Kamera nicht zu oeffnen")
            io.set_controls(io.device, settings.ordered_controls())
            if serial_port is None:
                first = _capture_fresh_still(io)
                first_text = offline_text
            else:
                first, first_text = _capture_with_serial_text(lambda: _capture_fresh_still(io), serial_port)
            first_captured_at = time.monotonic()
            if first.shape[:2] != (settings.size[1], settings.size[0]):
                raise SetupError("Standbild passt nicht zur Kameraaufloesung")
            args.out.mkdir(parents=True, exist_ok=True)
            if not cv2.imwrite(str(args.out / "still.png"), first):
                raise SetupError("still.png konnte nicht geschrieben werden")
            if hint_box is None:
                hint_box = find_green_hint_box(first)
                if hint_box is None:
                    raise SetupError("Kein gruener Bereich mit Punktstruktur gefunden; bitte --hint-box angeben")
            fit = fit_lattice(first, hint_box, empty_cells=GSV2AS_EMPTY_CELLS)
            if isinstance(fit, str):
                raise SetupError(f"Punktraster abgelehnt: {fit}; Hinweisbox pruefen oder --hint-box angeben")
            prechecks = check_setup(first, fit)
            _print_setup_checks(prechecks.to_dict())
            precheck_failures = [name for name, result in prechecks.checks.items()
                                 if getattr(result, "status", None) == "FEHLER" and name != "raster"]
            if precheck_failures:
                raise SetupError("Vorpruefung meldet FEHLER; Stabilitaetsmessung nicht gestartet")
            time.sleep(args.stability_s)
            if serial_port is None:
                second = _capture_fresh_still(io)
                second_text = offline_text
            else:
                second, second_text = _capture_with_serial_text(lambda: _capture_fresh_still(io), serial_port)
            stability_elapsed_s = time.monotonic() - first_captured_at
            first_text, second_text = _mask_changed_cells(first_text, second_text)
            if second.shape != first.shape:
                raise SetupError("Zweites Standbild hat eine andere Bildgroesse")
            if not cv2.imwrite(str(args.out / "stability.png"), second):
                raise SetupError("stability.png konnte nicht geschrieben werden")
            frame_texts = [(first, first_text), (second, second_text)]
            original_quad = fit.quad
            try:
                # refine_quad liest ROM-Glyphen direkt; maskierte Zellen haben
                # keine bekannte Glyphe und duerfen den Fit nicht beeinflussen.
                # Fuer 2j unten bleibt der maskierte Text unveraendert.
                refinement_text = first_text.replace("?", " ")
                candidate_quad, _history = refine_quad(
                    [(first, refinement_text)], original_quad,
                    CharGrid(n_cells=N_CELLS, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0),
                    DEFAULT_TARGET_SIZE,
                )
                old_heldout = raster_offset_check([(second, second_text)], original_quad)
                new_heldout = raster_offset_check([(second, second_text)], candidate_quad)
                if _heldout_improves(old_heldout, new_heldout):
                    revised = evaluate_quad(first, hint_box, candidate_quad, empty_cells=GSV2AS_EMPTY_CELLS)
                    if isinstance(revised, str):
                        raise SetupError(f"Verbessertes Raster-Quad abgelehnt: {revised}; kein Vorschlag")
                    fit = revised
                    print("Raster-Quad nachgefuehrt: zurueckgehaltenes Standbild verbessert")
            except SetupError:
                raise
            except (ValueError, cv2.error) as exc:
                print(f"Raster-Quad nicht nachgefuehrt: {exc}")
            offset_check = raster_offset_check(frame_texts, fit.quad)
            _print_setup_checks({"overall": offset_check.status,
                                 "checks": {"rasterversatz": offset_check.to_dict()}})
            if offset_check.status == "FEHLER":
                raise SetupError("Rasterversatz 2j meldet FEHLER; kein Vorschlag")
            final_checks = check_setup(
                first, fit, stability_image_bgr=second,
                stability_elapsed_s=stability_elapsed_s, offset_check=offset_check,
            )
            if final_checks.overall == "FEHLER":
                _print_setup_checks(final_checks.to_dict())
                raise SetupError("Abschliessende Einrichtungspruefung meldet FEHLER; kein Vorschlag")
            reader_check = None
            if args.templates is not None:
                reader_check = diagnose_reader(
                    (first, second), fit.quad, args.templates, args.templates_sha256,
                )
        finally:
            io.capture.release()
    except (OSError, ValueError, UvcError, SetupError, ImportError) as exc:
        print(f"Einrichtungsassistent abgebrochen: {exc}", file=sys.stderr)
        return 2
    finally:
        if serial_port is not None:
            serial_port.close()

    propose_args = argparse.Namespace(
        frame=args.out / "still.png",
        hint_box=",".join(f"{value:.8f}" for value in hint_box),
        camera_settings=args.out / "camera-settings.json",
        device_id=args.device_id,
        session_id=args.session_id,
        out=args.out,
        quad=None,
        auto_quad=True,
        grid=None,
        target_size="400x160",
        detector="glass",
        cell_text=offline_text,
        precomputed_fit=fit,
        stability_image_bgr=second,
        stability_elapsed_s=stability_elapsed_s,
        reader_check=reader_check,
        offset_check=offset_check,
        precomputed_checks=final_checks,
    )
    rc = run_propose(propose_args)
    if rc != 0:
        return rc
    checks = json.loads((args.out / "proposal.json").read_text(encoding="utf-8"))["setup_checks"]
    _print_setup_checks(checks)
    print(f"Standbilder: {args.out / 'still.png'}, {args.out / 'stability.png'}")
    print(f"Overlays: {args.out / 'overlay_source.png'}, {args.out / 'overlay_sampling.png'}")
    print(
        "Nach Sichtpruefung bestaetigen: ./.venv/bin/python scripts/harvest-setup.py confirm "
        f"--proposal {args.out / 'proposal.json'} --resolution-threshold-px {RESOLUTION_ERROR_PX} "
        f"--confirmed-by BEDIENER --out {args.out / 'profile.json'}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "propose":
        return run_propose(args)
    if args.command == "confirm":
        return run_confirm(args)
    if args.command == "focus":
        return run_focus(args)
    if args.command == "assist":
        return run_assist(args)
    raise AssertionError(f"unbekanntes Kommando {args.command!r}")  # von argparse ausgeschlossen


if __name__ == "__main__":
    sys.exit(main())
