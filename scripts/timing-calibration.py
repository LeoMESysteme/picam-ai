#!/usr/bin/env python3
"""Baut eine Timing-Kalibrierung aus `display-offset.py`-Berichten
(`offset-analyse.json`) und speichert sie (Ernte StreamCam-Umstieg, Task 5).

M (`--guard-margin-ms` fuer `gate-label.py`/`harvest.py`) war fuer die IMX500
fest auf 695 ms gemessen (CLAUDE.md) - mit der StreamCam ist das
kameraspezifisch und muss neu gemessen werden. `harvest.py` verlangt seit dem
Umstieg eine Kalibrierungsdatei mit zur Kamera passender USB-ID, dieses
Skript erzeugt sie aus einem oder mehreren Berichten von
`scripts/display-offset.py`. Die Logik steht seit 2026-11-20 in
`dispread.calibration.build` (auch fuer `picam kalibrieren`).

Beispiel:
    scripts/timing-calibration.py session1/offset-analyse/offset-analyse.json \\
        --out var/calibration/timing-streamcam.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _devdata import input_path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dispread.calibration.build import build_calibration, summary_lines  # noqa: E402
from dispread.camera_settings import STREAMCAM_USB_ID  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "reports", nargs="+", type=input_path, help="Ein oder mehrere offset-analyse.json-Dateien"
    )
    parser.add_argument("--out", type=Path, required=True, help="Zielpfad der Kalibrierungsdatei")
    parser.add_argument(
        "--camera-usb-id",
        default=STREAMCAM_USB_ID,
        help=f"Kamera-USB-ID, fuer die kalibriert wird (Vorgabe: {STREAMCAM_USB_ID})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        calibration = build_calibration(args.reports, args.out, camera_usb_id=args.camera_usb_id)
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2
    print("\n".join(summary_lines(calibration, args.out)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
