"""Sitzungsprofil fuer die automatische Ernte (Ernte Phase 1, Task 1).

Ein `SessionProfile` haelt fest, was der Bediener einmal je Aufnahmesitzung
bestaetigt hat: Quad, Zeichenzellenraster, ScalerCrop und den Befund des
Aufloesungs-Gates (Entscheidung 3 in
docs/superpowers/plans/2026-09-23-ernte-phase1.md). Es wird als JSON
gespeichert und ist der Vertrag zwischen `harvest-setup.py`, `harvest.py` und
`import-harvest.py`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dispread.charcells import CharGrid

#: Aktuelle Schemaversion. Erhoehen bei jeder inkompatiblen Aenderung des
#: JSON-Formats.
#:
#: 2 (Bug 2, Orchestrator 2026-09-23): `min_source_dot_column_px` misst im
#: OUTPUT-Bild - mit einem ScalerCrop, der schmaler ist als der Output des
#: Sensormodus, skaliert der ISP hoch, das Gate war damit zu optimistisch.
#: Neu: `native_scale` und `min_native_dot_column_px` (Pixel je Punktspalte
#: in NATIVEN, unbeschnittenen Sensorpixeln). Version 1 hatte noch keine
#: bestaetigten Profile im Umlauf, deshalb keine Migration - `load` weist
#: Version 1 ab.
PROFILE_SCHEMA_VERSION = 2

_REQUIRED_FIELDS = (
    "schema_version",
    "device_id",
    "session_id",
    "quad",
    "target_size",
    "grid",
    "scaler_crop",
    "min_source_dot_column_px",
    "native_scale",
    "min_native_dot_column_px",
    "resolution_threshold_px",
    "resolution_ok",
    "confirmed_by",
    "confirmed_at_utc",
)


@dataclass(frozen=True, slots=True)
class SessionProfile:
    """Vom Bediener bestaetigtes Sitzungsprofil."""

    schema_version: int
    device_id: str
    session_id: str
    quad: list[list[float]]
    target_size: tuple[int, int]
    grid: CharGrid
    scaler_crop: tuple[int, int, int, int] | None
    min_source_dot_column_px: float
    #: Bug 2: Verhaeltnis native (unbeschnittene, unbinned) Sensorpixel je
    #: Output-Pixel entlang des Punktspalten-Gates, `min(1, ...)` (nie > 1 -
    #: bei fehlendem/breitem Crop skaliert der ISP nur herunter, nie hoch).
    native_scale: float
    #: `min_source_dot_column_px * native_scale` - das ist der Wert, gegen
    #: den das Aufloesungs-Gate tatsaechlich prueft (Entscheidung 3), nicht
    #: `min_source_dot_column_px`.
    min_native_dot_column_px: float
    resolution_threshold_px: float
    resolution_ok: bool
    confirmed_by: str
    confirmed_at_utc: str

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "quad": [list(p) for p in self.quad],
            "target_size": list(self.target_size),
            "grid": self.grid.to_dict(),
            "scaler_crop": list(self.scaler_crop) if self.scaler_crop is not None else None,
            "min_source_dot_column_px": self.min_source_dot_column_px,
            "native_scale": self.native_scale,
            "min_native_dot_column_px": self.min_native_dot_column_px,
            "resolution_threshold_px": self.resolution_threshold_px,
            "resolution_ok": self.resolution_ok,
            "confirmed_by": self.confirmed_by,
            "confirmed_at_utc": self.confirmed_at_utc,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SessionProfile:
        scaler_crop = d["scaler_crop"]
        return cls(
            schema_version=d["schema_version"],
            device_id=d["device_id"],
            session_id=d["session_id"],
            quad=[list(p) for p in d["quad"]],
            target_size=tuple(d["target_size"]),
            grid=CharGrid.from_dict(d["grid"]),
            scaler_crop=tuple(scaler_crop) if scaler_crop is not None else None,
            min_source_dot_column_px=d["min_source_dot_column_px"],
            native_scale=d["native_scale"],
            min_native_dot_column_px=d["min_native_dot_column_px"],
            resolution_threshold_px=d["resolution_threshold_px"],
            resolution_ok=d["resolution_ok"],
            confirmed_by=d["confirmed_by"],
            confirmed_at_utc=d["confirmed_at_utc"],
        )

    def save(self, path: Path) -> None:
        """Schreibt das Profil atomar (tmp-Datei + `os.replace`)."""
        path = Path(path)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        os.replace(tmp_path, path)

    @classmethod
    def load(cls, path: Path) -> SessionProfile:
        """Laedt ein Profil. Wirft `ValueError` bei unbekannter Schemaversion
        oder fehlendem Feld."""
        d = json.loads(Path(path).read_text())
        # Versionsabgleich VOR der Feldpruefung: ein Dokument einer alten
        # Schemaversion soll an der Version scheitern ("neu einrichten"),
        # nicht an einem verwirrenden "Feld fehlt" fuer ein Feld, das diese
        # Version nie kannte (Bug 2, schema_version 1 -> 2).
        schema_version = d.get("schema_version")
        if schema_version != PROFILE_SCHEMA_VERSION:
            raise ValueError(
                f"Unbekannte schema_version {schema_version} in {path}, "
                f"erwartet {PROFILE_SCHEMA_VERSION}. Keine Migration vorgesehen "
                "(Bug 2: es waren noch keine bestaetigten Profile im Umlauf) - "
                "Sitzung mit harvest-setup.py neu einrichten."
            )
        for field_name in _REQUIRED_FIELDS:
            if field_name not in d:
                raise ValueError(f"Feld '{field_name}' fehlt im Sitzungsprofil {path}")
        return cls.from_dict(d)
