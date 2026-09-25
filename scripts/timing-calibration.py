#!/usr/bin/env python3
"""Baut eine Timing-Kalibrierung aus `display-offset.py`-Berichten
(`offset-analyse.json`) und speichert sie (Ernte StreamCam-Umstieg, Task 5).

M (`--guard-margin-ms` fuer `gate-label.py`/`harvest.py`) war fuer die IMX500
fest auf 695 ms gemessen (CLAUDE.md) - mit der StreamCam ist das
kameraspezifisch und muss neu gemessen werden. `harvest.py` verlangt seit dem
Umstieg eine Kalibrierungsdatei mit zur Kamera passender USB-ID, dieses
Skript erzeugt sie aus einem oder mehreren Berichten von
`scripts/display-offset.py`.

Beispiel:
    scripts/timing-calibration.py session1/offset-analyse/offset-analyse.json \\
        --out var/calibration/timing-streamcam.json
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dispread.camera_settings import STREAMCAM_USB_ID  # noqa: E402
from dispread.timing_calibration import calibration_from_offset_reports  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "reports", nargs="+", type=Path, help="Ein oder mehrere offset-analyse.json-Dateien"
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
    measured_at_utc = datetime.now(UTC).isoformat()
    try:
        calibration = calibration_from_offset_reports(
            args.reports, camera_usb_id=args.camera_usb_id, measured_at_utc=measured_at_utc
        )
    except ValueError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 2

    calibration.save(args.out)

    print(f"M = {calibration.guard_margin_ms:.1f} ms (Kamera {calibration.camera_usb_id})")
    print(f"Anzeigeversatz = {calibration.display_offset_ms:.1f} ms")
    for source in calibration.sources:
        print(f"  Quelle: {source['offset_json']} (sha256 {source['sha256'][:12]}...)")
    print(f"Geschrieben: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
