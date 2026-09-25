"""Timing-Kalibrierung fuer die StreamCam (Task 5, StreamCam-Umstieg 2026-09-25).

Der Schutzabstand M (`--guard-margin-ms`, den `gate-label.py`/`harvest.py`
nutzen, um Frames rund um einen Anzeigewechsel zu verwerfen) war fuer die
IMX500 fest auf 695 ms gemessen (CLAUDE.md, `docs/VALIDATION.md` 2026-09-23).
Mit der neuen Kamera ist dieser Wert nicht mehr gueltig - er muss je Kamera
neu gemessen werden (`scripts/display-offset.py`) und wird hier als eigene
Kalibrierungsdatei mit der zugehoerigen Kamera-USB-ID festgehalten.
`harvest.py` verlangt diese Datei und lehnt eine Kalibrierung fuer eine
andere Kamera ab (kein Erfinden ueber Geraete hinweg, kein stiller
Ruecksprung auf 695 ms).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

from dispread.paths import VAR

#: Aktuelle Schemaversion. `load_calibration` akzeptiert nur genau diese.
CALIBRATION_SCHEMA_VERSION = 1

#: Vorgabepfad relativ zur Projektwurzel (`dispread.paths.VAR` = <repo>/var,
#: per DISPREAD_VAR ueberschreibbar - nicht das Arbeitsverzeichnis).
DEFAULT_CALIBRATION_PATH = VAR / "calibration" / "timing-streamcam.json"

_REQUIRED_FIELDS = (
    "schema_version",
    "camera_usb_id",
    "guard_margin_ms",
    "display_offset_ms",
    "measured_at_utc",
    "sources",
)


@dataclass(frozen=True, slots=True)
class TimingCalibration:
    """Gemessener Schutzabstand M und Anzeigeversatz fuer eine Kamera.

    `sources` haelt fest, aus welchen `display-offset.py`-Berichten der Wert
    stammt (Pfad + sha256), damit eine Kalibrierung nachvollziehbar bleibt.
    """

    camera_usb_id: str
    guard_margin_ms: float
    display_offset_ms: float
    measured_at_utc: str
    sources: tuple[dict, ...]
    schema_version: int = CALIBRATION_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "camera_usb_id": self.camera_usb_id,
            "guard_margin_ms": self.guard_margin_ms,
            "display_offset_ms": self.display_offset_ms,
            "measured_at_utc": self.measured_at_utc,
            "sources": [dict(source) for source in self.sources],
        }

    def save(self, path: Path) -> None:
        """Schreibt die Kalibrierung atomar (tmp-Datei + `os.replace`) und
        legt das Elternverzeichnis an, falls es fehlt."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp_path, path)


def load_calibration(path: Path) -> TimingCalibration:
    """Laedt eine Timing-Kalibrierung.

    `ValueError` bei fehlender Datei, falscher `schema_version`, fehlendem
    Feld oder einem `guard_margin_ms`, das nicht endlich oder <= 0 ist - ein
    kaputter Schutzabstand darf nie stillschweigend durchrutschen.
    """
    path = Path(path)
    try:
        text = path.read_text()
    except FileNotFoundError as exc:
        raise ValueError(f"Timing-Kalibrierung {path} nicht gefunden") from exc

    d = json.loads(text)

    schema_version = d.get("schema_version")
    if schema_version != CALIBRATION_SCHEMA_VERSION:
        raise ValueError(
            f"Unbekannte schema_version {schema_version!r} in {path}, "
            f"unterstuetzt: {CALIBRATION_SCHEMA_VERSION}. Neu kalibrieren mit "
            "scripts/timing-calibration.py."
        )

    missing_fields = [field_name for field_name in _REQUIRED_FIELDS if field_name not in d]
    if missing_fields:
        raise ValueError(f"Timing-Kalibrierung {path}: fehlende Felder {', '.join(missing_fields)}")

    guard_margin_ms = d["guard_margin_ms"]
    if (
        not isinstance(guard_margin_ms, (int, float))
        or isinstance(guard_margin_ms, bool)
        or not math.isfinite(guard_margin_ms)
        or guard_margin_ms <= 0
    ):
        raise ValueError(
            f"Timing-Kalibrierung {path}: guard_margin_ms muss endlich und > 0 "
            f"sein, ist {guard_margin_ms!r}"
        )

    return TimingCalibration(
        camera_usb_id=d["camera_usb_id"],
        guard_margin_ms=float(guard_margin_ms),
        display_offset_ms=float(d["display_offset_ms"]),
        measured_at_utc=d["measured_at_utc"],
        sources=tuple(dict(source) for source in d["sources"]),
        schema_version=schema_version,
    )


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def calibration_from_offset_reports(
    reports: list[Path], camera_usb_id: str, measured_at_utc: str
) -> TimingCalibration:
    """Baut eine `TimingCalibration` aus `display-offset.py`-Berichten
    (`offset-analyse.json`).

    Betrachtet alle Populationen (ueber alle uebergebenen Berichte) mit
    `detected=True` und `M_s != None`. `guard_margin_ms = 1000 * max(M_s)`
    - der groesste gemessene Wert, wie am 2026-09-23 vom Nutzer vor jeder
    Ernte festgelegt (`docs/VALIDATION.md`). `display_offset_ms` ist
    `1000 * delta_s` derselben Population (nicht neu gemittelt).

    `ValueError`, wenn keine Population `detected=True` mit einem `M_s`
    liefert - dann gibt es nichts zu kalibrieren.
    """
    best_population: dict | None = None
    for report_path in reports:
        data = json.loads(Path(report_path).read_text())
        for population in data.get("populations", []):
            if not population.get("detected"):
                continue
            m_s = population.get("M_s")
            if m_s is None:
                continue
            if best_population is None or m_s > best_population["M_s"]:
                best_population = population

    if best_population is None:
        raise ValueError(
            "calibration_from_offset_reports: keine Population mit "
            "detected=True und gesetztem M_s in den uebergebenen Berichten "
            f"({[str(r) for r in reports]}) - keine Kalibrierung ableitbar."
        )

    sources = tuple(
        {"offset_json": str(report_path), "sha256": _sha256_of(report_path)}
        for report_path in reports
    )

    return TimingCalibration(
        camera_usb_id=camera_usb_id,
        guard_margin_ms=1000.0 * best_population["M_s"],
        display_offset_ms=1000.0 * best_population["delta_s"],
        measured_at_utc=measured_at_utc,
        sources=sources,
    )
