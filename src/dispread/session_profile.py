"""Sitzungsprofil fuer die automatische Ernte (Ernte Phase 1, Task 1).

Ein `SessionProfile` haelt fest, was der Bediener einmal je Aufnahmesitzung
bestaetigt hat: Quad, Zeichenzellenraster, Kameraeinstellungen (ab Version 3)
und den Befund des Aufloesungs-Gates (Entscheidung 3 in
docs/superpowers/plans/2026-09-23-ernte-phase1.md). Es wird als JSON
gespeichert und ist der Vertrag zwischen `harvest-setup.py`, `harvest.py` und
`import-harvest.py`.

Version 3 (StreamCam-Umstieg 2026-09-25): Bildpixel = native Pixel (StreamCam,
Zoom fest 100) - `scaler_crop` und ein `native_scale != 1.0` gibt es an dieser
Kamera nicht mehr, `camera` (`dispread.camera_settings.CameraSettings`) ist
stattdessen Pflicht. `scaler_crop`/`native_scale` bleiben als Felder erhalten,
damit Version 2 unveraendert ladbar bleibt (`camera is None`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dispread.camera_settings import CameraSettings
from dispread.charcells import CharGrid

#: Aktuelle Schemaversion. Erhoehen bei jeder inkompatiblen Aenderung des
#: JSON-Formats. `load` akzeptiert alle Versionen in `SUPPORTED_SCHEMA_VERSIONS`,
#: alles andere ist ein harter Abbruch (kein Rateversuch an einer Migration).
#:
#: 2 (Bug 2, Orchestrator 2026-09-23): `min_source_dot_column_px` misst im
#: OUTPUT-Bild - mit einem ScalerCrop, der schmaler ist als der Output des
#: Sensormodus, skaliert der ISP hoch, das Gate war damit zu optimistisch.
#: Neu: `native_scale` und `min_native_dot_column_px` (Pixel je Punktspalte
#: in NATIVEN, unbeschnittenen Sensorpixeln). Version 1 hatte noch keine
#: bestaetigten Profile im Umlauf, deshalb keine Migration - `load` weist
#: Version 1 ab.
#:
#: 3 (StreamCam-Umstieg 2026-09-25): IMX500/Picamera2 sind ausser Betrieb, die
#: Logitech StreamCam (USB/UVC) kennt weder ScalerCrop noch Sensor-Binning -
#: Bildpixel = native Pixel (StreamCam, Zoom fest 100). Neues Pflichtfeld
#: `camera` (`CameraSettings`, siehe `dispread.camera_settings`): was die
#: Sitzung an der Kamera eingestellt hatte, muss die Ernte reproduzieren
#: koennen. `scaler_crop` bleibt als Feld erhalten (v2-Kompatibilitaet), ist
#: bei v3 aber immer `None`, und `native_scale` immer `1.0` - beides wird
#: beim Laden geprueft, kein stillschweigendes Ignorieren eines v2-Feldes,
#: das die StreamCam nicht mehr kennt. Echte v2-Profile bleiben ungeaendert
#: ladbar (`camera is None`), es gibt keine Migration v2 -> v3 (die Kamera
#: hat komplett gewechselt, es gibt nichts zu migrieren).
PROFILE_SCHEMA_VERSION = 3

#: Von `load` akzeptierte Schemaversionen. Alles ausserhalb -> `ValueError`.
SUPPORTED_SCHEMA_VERSIONS = (2, 3)

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
    #: Neu in Version 3, letztes Feld (Default `None` fuer v2-Kompatibilitaet
    #: im Konstruktor). `None` heisst "v2-Profil, keine Kameraeinstellungen
    #: hinterlegt" - `to_dict()` laesst den Schluessel dann ganz weg, damit
    #: sich das Re-Speichern/Hashen bestehender v2-Profile nicht aendert.
    camera: CameraSettings | None = None

    def to_dict(self) -> dict:
        d = {
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
        if self.camera is not None:
            d["camera"] = self.camera.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> SessionProfile:
        scaler_crop = d["scaler_crop"]
        camera = d.get("camera")
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
            camera=CameraSettings.from_dict(camera) if camera is not None else None,
        )

    def save(self, path: Path) -> None:
        """Schreibt das Profil atomar (tmp-Datei + `os.replace`)."""
        path = Path(path)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        os.replace(tmp_path, path)

    @classmethod
    def load(cls, path: Path) -> SessionProfile:
        """Laedt ein Profil. Wirft `ValueError` bei unbekannter Schemaversion,
        fehlendem Feld, einem v3-Profil ohne `camera` oder einem v3-Profil mit
        einem `scaler_crop`/`native_scale`, das die StreamCam nicht kennt."""
        d = json.loads(Path(path).read_text())
        # Versionsabgleich VOR der Feldpruefung: ein Dokument einer alten
        # (oder zu neuen) Schemaversion soll an der Version scheitern ("neu
        # einrichten"), nicht an einem verwirrenden "Feld fehlt" fuer ein
        # Feld, das diese Version nie kannte (Bug 2, schema_version 1 -> 2).
        schema_version = d.get("schema_version")
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unbekannte schema_version {schema_version} in {path}, "
                f"unterstuetzt: {SUPPORTED_SCHEMA_VERSIONS}. Keine automatische "
                "Migration vorgesehen - Sitzung mit harvest-setup.py neu einrichten."
            )
        for field_name in _REQUIRED_FIELDS:
            if field_name not in d:
                raise ValueError(f"Feld '{field_name}' fehlt im Sitzungsprofil {path}")
        if schema_version == 3:
            if "camera" not in d:
                raise ValueError(
                    f"Feld 'camera' fehlt im Sitzungsprofil {path} - Profil v3 "
                    "verlangt die Kameraeinstellungen der Sitzung (StreamCam-Umstieg)."
                )
            if d.get("scaler_crop") is not None:
                raise ValueError(
                    f"Sitzungsprofil {path}: scaler_crop muss bei Profil v3 None sein "
                    "(die StreamCam kennt kein ScalerCrop)."
                )
            if d.get("native_scale") != 1.0:
                raise ValueError(
                    f"Sitzungsprofil {path}: native_scale muss bei Profil v3 1.0 sein "
                    "(Bildpixel = native Pixel, StreamCam ohne Sensor-Binning)."
                )
        return cls.from_dict(d)
