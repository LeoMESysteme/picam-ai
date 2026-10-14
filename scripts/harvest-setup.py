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

`focus` sucht per Bergsteigen (`dispread.focus_sweep.climb_focus`, Vollsweep bei flachem Start)
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
import json
import math
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from dispread.camera_settings import (
    STREAMCAM_USB_ID,
    load_camera_settings,
)
from dispread.charcells import CharGrid, source_dot_column_px
from dispread.dotlattice import evaluate_quad, fit_lattice
from dispread.frames.uvc_source import (
    UvcError,
    UvcSource,
    find_uvc_device,
    v4l2_get_controls,
    v4l2_set_controls,
)
from dispread.glassquad import glass_quad_in_region
from dispread.gsv2as_cell_text import validate_offline_cell_text
from dispread.live import setup as live_setup
from dispread.live.setup import (
    DEFAULT_TARGET_SIZE,
    GSV2AS_EMPTY_CELLS,
    N_CELLS,
    SetupError,
)
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.setup_checks import RESOLUTION_ERROR_PX
from dispread.workbench.vision import lcd_quad_in_region


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
            # evaluate_quad prueft mit Float32; vorgegebene Ecken unveraendert speichern.
            fit = replace(fit, quad=quad)

        if fit is not None:
            grid = live_setup.LATTICE_GRID
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

    out_dir = args.out
    if fit is not None:
        try:
            proposal = live_setup.propose_with_fit(
                image, fit=fit, frame_path=args.frame, camera_settings=camera_settings,
                device_id=args.device_id, session_id=args.session_id, out_dir=out_dir,
                cell_text=cell_text, offset_check=getattr(args, "offset_check", None),
                final_checks=getattr(args, "precomputed_checks", None),
                stability_image_bgr=getattr(args, "stability_image_bgr", None),
                stability_elapsed_s=getattr(args, "stability_elapsed_s", None),
                reader_check=getattr(args, "reader_check", None),
            )
        except SetupError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        min_px = proposal["min_source_dot_column_px"]
    else:
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
        native_scale = 1.0
        min_native_dot_column_px = min_px
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
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
        live_setup.write_overlays(image, quad, grid, out_dir, target_size=target_size)

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
    try:
        profile = live_setup.confirm_proposal(
            proposal,
            confirmed_by=args.confirmed_by,
            resolution_threshold_px=args.resolution_threshold_px,
            override_reason=args.override_reason,
            accept_default_grid=args.accept_default_grid,
        )
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    profile.save(args.out)

    print(f"Sitzungsprofil geschrieben: {args.out}")
    print(
        f"min_source_dot_column_px={profile.min_source_dot_column_px:.3f}  native_scale={profile.native_scale:.4f}  "
        f"min_native_dot_column_px={profile.min_native_dot_column_px:.3f}  Schwelle={args.resolution_threshold_px}  "
        f"resolution_ok={profile.resolution_ok}"
    )
    if not profile.resolution_ok:
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


class _IoSetupCamera:
    """`SetupCamera` ueber die direkt geoeffnete Aufnahme der Kommandozeile."""

    def __init__(self, io: _CameraIO) -> None:
        self._io = io
        self.device = io.device

    def set_controls(self, controls):
        self._io.set_controls(self._io.device, list(controls))

    def get_controls(self, names):
        return self._io.get_controls(self._io.device, list(names))

    def fresh_still(self, discard: int = 10):
        return _capture_fresh_still(self._io, discard=discard)


def run_focus(args: argparse.Namespace) -> int:
    try:
        hint_box = _parse_hint_box(args.hint_box) if args.hint_box else None
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    io = _open_camera_io(args.device)
    try:
        settings, sweep_log = live_setup.focus_camera(_IoSetupCamera(io), hint_box, settle_s=args.settle_s)
    finally:
        io.capture.release()
    best_focus = settings.controls["focus_absolute"]

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "camera": settings.to_dict(),
        "focus_sweep": [[f, s] for f, s in sweep_log],
        "focus_method": sweep_log.focus_method,
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
            text_source = (
                live_setup.offline_text_source(offline_text)
                if serial_port is None
                else live_setup.serial_text_source(serial_port)
            )
            result = live_setup.assist_measure(
                _IoSetupCamera(io),
                cell_text=text_source,
                expected_size=settings.size,
                out_dir=args.out,
                hint_box=hint_box,
                stability_s=args.stability_s,
                templates=args.templates,
                templates_sha256=args.templates_sha256,
                report=_print_setup_checks,
                info=print,
                sleep=time.sleep,
                monotonic=time.monotonic,
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
        hint_box=",".join(f"{value:.8f}" for value in result.hint_box),
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
        precomputed_fit=result.fit,
        stability_image_bgr=result.second,
        stability_elapsed_s=result.stability_elapsed_s,
        reader_check=result.reader_check,
        offset_check=result.offset_check,
        precomputed_checks=result.final_checks,
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
