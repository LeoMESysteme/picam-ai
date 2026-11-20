"""Timing-Kalibrierung aus `offset`-Berichten bauen und speichern.

Seit 2026-11-20 im Paket (vorher nur `scripts/timing-calibration.py`, das
jetzt diese Funktionen aufruft). Die Regel selbst steht unveraendert in
`dispread.timing_calibration.calibration_from_offset_reports`: groesstes M
ueber alle als `detected` markierten Populationen, Kamera-Herkunft je Bericht
geprueft, Quellen mit sha256.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from dispread.timing_calibration import TimingCalibration, calibration_from_offset_reports


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_calibration(
    reports: list[Path], out: Path, *, camera_usb_id: str, measured_at_utc: str | None = None
) -> TimingCalibration:
    """Kalibrierung aus den Berichten bauen und atomar nach `out` schreiben.

    `ValueError` (aus `calibration_from_offset_reports`), wenn kein Bericht
    eine erkannte Population mit M liefert oder ein Bericht von einer anderen
    Kamera stammt - dann wird nichts geschrieben."""
    calibration = calibration_from_offset_reports(
        [Path(report) for report in reports],
        camera_usb_id=camera_usb_id,
        measured_at_utc=measured_at_utc or utc_now_iso(),
    )
    calibration.save(Path(out))
    return calibration


def summary_lines(calibration: TimingCalibration, out: Path) -> list[str]:
    lines = [
        f"M = {calibration.guard_margin_ms:.1f} ms (Kamera {calibration.camera_usb_id})",
        f"Anzeigeversatz = {calibration.display_offset_ms:.1f} ms",
    ]
    for source in calibration.sources:
        lines.append(f"  Quelle: {source['offset_json']} (sha256 {source['sha256'][:12]}...)")
    lines.append(f"Geschrieben: {out}")
    return lines
