#!/usr/bin/env python3
"""Sitzung fuer die automatische Ernte einrichten - Task 3 aus
docs/superpowers/plans/2026-09-23-ernte-phase1.md.

Aufruf (zwei Unterbefehle):

    ./.venv/bin/python scripts/harvest-setup.py propose \\
        --frame var/diagnostics/lauf1/frames/frame_000001.jpg \\
        --hint-box 0.49,0.30,0.34,0.14 \\
        --device-id gsv2as-01 --session-id lauf1 \\
        --out var/diagnostics/lauf1/setup

    ./.venv/bin/python scripts/harvest-setup.py confirm \\
        --proposal var/diagnostics/lauf1/setup/proposal.json \\
        --resolution-threshold-px 2.0 --confirmed-by bediener \\
        --out var/diagnostics/lauf1/setup/profile.json

`propose` schlaegt Quad und Zeichenzellenraster vor (Quad ueber
`glass_quad_in_region`, sofern nicht `--quad` gesetzt ist - ein Fehlschlag ist
ein Fehler, kein Rateversuch) und misst die Punktspaltenbreite im Quellbild
(`source_dot_column_px`, Aufloesungs-Gate, Entscheidung 3 des Plans). Es
schreibt einen maschinenlesbaren Vorschlag (`proposal.json`) und zwei
Bediener-Overlays (`overlay_source.png`, `overlay_rectified.png`).

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

Reiner Einrichtungscode, Stil an `gate-label.py` angelehnt. Bestaetigt der
Bediener nichts, oeffnet dieses Skript weder Kamera noch seriellen Port -
es liest nur ein bereits aufgenommenes Bild.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from dispread.charcells import CharGrid, source_dot_column_px
from dispread.glassquad import glass_quad_in_region
from dispread.rectify import rectify
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile
from dispread.workbench.vision import lcd_quad_in_region

#: Anzahl Zeichenzellen des GSV-2AS-Displays (HD44780, 16 x 1). Kein
#: CLI-Regler - die Geometrie des angeschlossenen Geraets ist keine freie Wahl.
N_CELLS = 16
DEFAULT_TARGET_SIZE = (400, 160)


class SetupError(ValueError):
    """Fehlerhafte Eingabe (CLI-Werte, Datei-Inhalt) - fuehrt zu Exit 2."""


def _compute_native_scale(
    *,
    scaler_crop_actual: tuple[int, int, int, int] | None,
    sensor_mode_size: tuple[int, int],
    sensor_array_size: tuple[int, int],
    output_size: tuple[int, int],
) -> float:
    """Bug 2 (Orchestrator 2026-09-23): `source_dot_column_px` misst im
    OUTPUT-Bild (z. B. 960x720). Ist der `ScalerCrop` schmaler als der
    Output des gewaehlten Sensormodus (2x2-gebinnt, z. B. 2028x1520 aus
    4056x3040), skaliert der ISP hoch - das Gate war damit zu optimistisch.

    `binning = sensor_array_size.width / sensor_mode_size.width` (z. B.
    4056/2028 = 2). Ohne Crop (`scaler_crop_actual is None`) gilt die volle
    Sensorbreite (`sensor_array_size[0]`) als Crop-Breite - das ist der
    Fall "kein Crop gesetzt, Sensor-Vorgabe (voller Array) bleibt aktiv"
    aus sync-record.py.

    `native_scale = min(1, (crop_w/binning) / output_width)` - nie > 1: ohne
    Crop oder mit einem Crop breiter als der Output skaliert der ISP nur
    herunter, nie hoch, das Gate bleibt dann bei der rohen Messung."""
    crop_w = scaler_crop_actual[2] if scaler_crop_actual is not None else sensor_array_size[0]
    binning = sensor_array_size[0] / sensor_mode_size[0]
    native_crop_w = crop_w / binning
    output_w = output_size[0]
    return min(1.0, native_crop_w / output_w)


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


def _parse_scaler_crop(value: str) -> tuple[int, int, int, int]:
    values = _parse_float_list(value, 4, "--scaler-crop")
    ints = tuple(round(v) for v in values)
    if any(v <= 0 for v in ints[2:]) or any(v < 0 for v in ints[:2]):
        raise SetupError(f"--scaler-crop: X,Y muessen >= 0 und W,H > 0 sein, bekam {value!r}")
    return ints  # type: ignore[return-value]


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
    propose.add_argument("--grid", default=None, help="left,pitch,top,bottom im entzerrten Bild, ersetzt den Default")
    propose.add_argument("--target-size", default="400x160", help="Groesse des entzerrten Bildes, Vorgabe 400x160")
    propose.add_argument("--scaler-crop", default=None, help="X,Y,W,H - nur zur Ablage im Vorschlag, nichts wird gesetzt")
    propose.add_argument(
        "--session-json",
        type=Path,
        default=None,
        help=(
            "session.json einer sync-record.py-Kameraaufzeichnung (Bug 2): liefert "
            "scaler_crop_actual, sensor_mode_size, sensor_array_size fuer das native "
            "Aufloesungs-Gate. Ohne diese Option bleibt native_scale in proposal.json "
            "leer, und confirm verlangt dann --assume-native-scale."
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
        "--accept-default-grid",
        action="store_true",
        help="erlaubt, ein ungeprueftes Default-Raster (grid_source=default_even_split) zu bestaetigen",
    )
    confirm.add_argument(
        "--assume-native-scale",
        type=float,
        default=None,
        help=(
            "Bug 2: nur wenn proposal.json kein native_scale hat (propose ohne "
            "--session-json). Explizite Uebersteuerung, z. B. 1.0 - wird NICHT "
            "angenommen, das Fehlen ist ein harter Abbruch (Exit 2)."
        ),
    )

    return parser


def run_propose(args: argparse.Namespace) -> int:
    image = cv2.imread(str(args.frame))
    if image is None:
        print(f"Bild nicht lesbar: {args.frame}", file=sys.stderr)
        return 2
    height, width = image.shape[:2]

    try:
        target_size = _parse_target_size(args.target_size)

        if args.quad:
            quad = _parse_quad(args.quad)
        else:
            hint_box = tuple(_parse_float_list(args.hint_box, 4, "--hint-box"))
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

        if args.grid:
            grid = _parse_grid(args.grid, target_size)
            grid_source = "operator_provided"
        else:
            grid = _default_grid(target_size)
            grid_source = "default_even_split"

        scaler_crop = _parse_scaler_crop(args.scaler_crop) if args.scaler_crop else None
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

    # Bug 2: min_px ist im Quellbild gemessen - das ist genau das OUTPUT-Bild
    # der Kamera (`args.frame`, hier bereits als `image`/`width`/`height`
    # geladen), nicht das entzerrte Zielbild. --session-json liefert die
    # Sensorgeometrie, um daraus native_scale/min_native_dot_column_px zu
    # rechnen; ohne die Option bleiben beide `None` (confirm verlangt dann
    # --assume-native-scale).
    native_scale: float | None = None
    min_native_dot_column_px: float | None = None
    session_json_path: str | None = None
    if args.session_json is not None:
        session_json_path = str(args.session_json)
        session_data = json.loads(args.session_json.read_text(encoding="utf-8"))
        session_scaler_crop = session_data.get("scaler_crop_actual")
        session_sensor_mode_size = session_data.get("sensor_mode_size")
        session_sensor_array_size = session_data.get("sensor_array_size")
        if session_sensor_mode_size is not None and session_sensor_array_size is not None:
            native_scale = _compute_native_scale(
                scaler_crop_actual=tuple(session_scaler_crop) if session_scaler_crop is not None else None,
                sensor_mode_size=tuple(session_sensor_mode_size),
                sensor_array_size=tuple(session_sensor_array_size),
                output_size=(width, height),
            )
            min_native_dot_column_px = min_px * native_scale
        else:
            print(
                f"WARNUNG: --session-json {args.session_json} enthaelt kein "
                "sensor_mode_size/sensor_array_size (z. B. --source synthetic oder "
                "vor Bug 2 aufgezeichnet) - natives Aufloesungs-Gate bleibt "
                "unbestimmt, confirm verlangt dann --assume-native-scale.",
                file=sys.stderr,
            )

    out_dir = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    proposal = {
        "frame": str(args.frame),
        "device_id": args.device_id,
        "session_id": args.session_id,
        "quad": quad,
        "target_size": list(target_size),
        "grid": grid.to_dict(),
        "grid_source": grid_source,
        "scaler_crop": list(scaler_crop) if scaler_crop is not None else None,
        "min_source_dot_column_px": min_px,
        "session_json": session_json_path,
        "native_scale": native_scale,
        "min_native_dot_column_px": min_native_dot_column_px,
    }
    (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")

    overlay_source = image.copy()
    quad_pts = np.array(quad, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(overlay_source, [quad_pts], isClosed=True, color=(0, 0, 255), thickness=2)
    cv2.imwrite(str(out_dir / "overlay_source.png"), overlay_source)

    crop = rectify(image, quad, target_size=target_size)
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
    print(f"min_source_dot_column_px: {min_px:.3f}")
    if native_scale is not None:
        print(f"native_scale: {native_scale:.4f}  min_native_dot_column_px: {min_native_dot_column_px:.3f}")
    else:
        print("native_scale: unbestimmt (kein --session-json oder ohne sensor_mode_size/sensor_array_size)")
    print(f"Vorschlag geschrieben: {out_dir / 'proposal.json'}")
    print(f"Overlays: {out_dir / 'overlay_source.png'}, {out_dir / 'overlay_rectified.png'}")
    return 0


def run_confirm(args: argparse.Namespace) -> int:
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))

    if proposal.get("grid_source") == "default_even_split" and not args.accept_default_grid:
        print(
            "Raster ist der ungeprueft uebernommene Default-Split (grid_source=default_even_split). "
            "--accept-default-grid setzen, um ihn trotzdem zu bestaetigen (Task 3, confirm).",
            file=sys.stderr,
        )
        return 2

    grid = CharGrid.from_dict(proposal["grid"])
    target_size = tuple(proposal["target_size"])
    scaler_crop_value = proposal.get("scaler_crop")
    scaler_crop = tuple(scaler_crop_value) if scaler_crop_value is not None else None
    min_px = float(proposal["min_source_dot_column_px"])

    # Bug 2: das Gate prueft gegen min_native_dot_column_px, nie gegen die
    # rohe Output-Bild-Messung min_px. proposal.json traegt beide schon
    # vorgerechnet, wenn propose ein --session-json bekam - sonst ist
    # --assume-native-scale die einzige (bewusst explizite) Uebersteuerung.
    native_scale = proposal.get("native_scale")
    min_native_px = proposal.get("min_native_dot_column_px")
    if native_scale is None:
        if args.assume_native_scale is None:
            print(
                "Fehler: proposal.json enthaelt kein native_scale (propose lief ohne "
                "--session-json oder ohne sensor_mode_size/sensor_array_size darin). "
                "Mit --assume-native-scale explizit uebersteuerbar, z. B. 1.0 "
                "(Bug 2, docs/superpowers/plans/2026-09-23-ernte-phase1.md).",
                file=sys.stderr,
            )
            return 2
        native_scale = args.assume_native_scale
        min_native_px = min_px * native_scale
    native_scale = float(native_scale)
    min_native_px = float(min_native_px)

    resolution_ok = min_native_px >= args.resolution_threshold_px

    profile = SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        device_id=proposal["device_id"],
        session_id=proposal["session_id"],
        quad=[list(p) for p in proposal["quad"]],
        target_size=target_size,
        grid=grid,
        scaler_crop=scaler_crop,
        min_source_dot_column_px=min_px,
        native_scale=native_scale,
        min_native_dot_column_px=min_native_px,
        resolution_threshold_px=args.resolution_threshold_px,
        resolution_ok=resolution_ok,
        confirmed_by=args.confirmed_by,
        confirmed_at_utc=datetime.now(UTC).isoformat(),
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "propose":
        return run_propose(args)
    if args.command == "confirm":
        return run_confirm(args)
    raise AssertionError(f"unbekanntes Kommando {args.command!r}")  # von argparse ausgeschlossen


if __name__ == "__main__":
    sys.exit(main())
