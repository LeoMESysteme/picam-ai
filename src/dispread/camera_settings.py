"""Kameraeinstellungen der Logitech StreamCam (USB/UVC, 046d:0893).

Ersetzt die IMX500-/Picamera2-Anbindung (ausser Betrieb seit 2026-09-25, siehe
docs/project_history.md). `CameraSettings` ist der Vertrag zwischen dem
Profil (Kalibrier-/Kommissionierschritt) und `UvcSource`
(src/dispread/frames/uvc_source.py): was am Geraet gesetzt werden muss, bevor
ein Frame vertrauenswuerdig ist.

Kein Erfinden von Vorgabewerten: `from_dict` verlangt genau die in
`SETTABLE_CONTROLS` gelisteten Regler, nicht mehr und nicht weniger, und
lehnt alles andere mit `ValueError` ab.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STREAMCAM_MODEL = "logitech_streamcam"
STREAMCAM_USB_ID = "046d:0893"

#: Vor allen anderen gesetzt (Automatiken aus), Reihenfolge fest.
MODE_CONTROLS: tuple[tuple[str, int], ...] = (
    ("focus_automatic_continuous", 0),
    ("auto_exposure", 1),
    ("white_balance_automatic", 0),
)

#: Feste Werte, die nicht aus dem Profil kommen (Konzept: reproduzierbarer
#: Bildausschnitt, keine Zoom-/Schwenk-Drift zwischen Sessions).
FIXED_CONTROLS: tuple[tuple[str, int], ...] = (
    ("power_line_frequency", 1),
    ("zoom_absolute", 100),
    ("pan_absolute", 0),
    ("tilt_absolute", 0),
)

#: Regler, die aus dem Profil kommen - je Aufbau/Beleuchtung unterschiedlich.
SETTABLE_CONTROLS: tuple[str, ...] = (
    "focus_absolute",
    "exposure_time_absolute",
    "white_balance_temperature",
    "gain",
)

_REQUIRED_FIELDS = ("model", "usb_id", "size", "fourcc", "fps", "controls")


@dataclass(frozen=True, slots=True)
class CameraSettings:
    """Was `UvcSource.open()` an der Kamera einstellt und zurueckliest.

    `controls` enthaelt ausschliesslich die Namen aus `SETTABLE_CONTROLS`,
    alle Pflicht - kein stillschweigender Vorgabewert bei einem fehlenden
    Regler.
    """

    model: str
    usb_id: str
    size: tuple[int, int]
    fourcc: str
    fps: int
    controls: dict[str, int]
    #: Nur Information (z.B. beim letzten Lauf verwendeter Geraetepfad) -
    #: `UvcSource` findet das Geraet selbst ueber `usb_id`, wenn dies fehlt.
    device: str | None = None

    def ordered_controls(self) -> list[tuple[str, int]]:
        """MODE_CONTROLS, dann FIXED_CONTROLS, dann SETTABLE_CONTROLS in dieser Reihenfolge."""
        settable = [(name, self.controls[name]) for name in SETTABLE_CONTROLS]
        return list(MODE_CONTROLS) + list(FIXED_CONTROLS) + settable

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "model": self.model,
            "usb_id": self.usb_id,
            "size": list(self.size),
            "fourcc": self.fourcc,
            "fps": self.fps,
            "controls": dict(self.controls),
        }
        if self.device is not None:
            d["device"] = self.device
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CameraSettings:
        """ValueError bei fehlendem Feld, fehlendem/zusaetzlichem Control, Nicht-int-Wert."""
        missing_fields = [k for k in _REQUIRED_FIELDS if k not in d]
        if missing_fields:
            raise ValueError(
                f"CameraSettings: fehlende Felder {', '.join(missing_fields)}"
            )

        controls_in = d["controls"]
        if not isinstance(controls_in, dict):
            raise ValueError(f"CameraSettings.controls ist kein Objekt: {controls_in!r}")
        expected = set(SETTABLE_CONTROLS)
        actual = set(controls_in)
        if actual != expected:
            teile = []
            fehlend = expected - actual
            zusaetzlich = actual - expected
            if fehlend:
                teile.append(f"fehlend: {', '.join(sorted(fehlend))}")
            if zusaetzlich:
                teile.append(f"zusaetzlich: {', '.join(sorted(zusaetzlich))}")
            raise ValueError(
                f"CameraSettings.controls passt nicht zu SETTABLE_CONTROLS ({'; '.join(teile)})"
            )
        for name, value in controls_in.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(
                    f"CameraSettings.controls[{name!r}] ist kein int: {value!r}"
                )

        size = d["size"]
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            raise ValueError(f"CameraSettings.size ungueltig: {size!r}")

        return cls(
            model=d["model"],
            usb_id=d["usb_id"],
            size=(int(size[0]), int(size[1])),
            fourcc=d["fourcc"],
            fps=int(d["fps"]),
            controls=dict(controls_in),
            device=d.get("device"),
        )


def load_camera_settings(path: Path) -> CameraSettings:
    """Liest eine JSON-Datei mit Top-Level-Schluessel "camera" (Profil v3 oder
    Ausgabe von harvest-setup focus). ValueError, wenn "camera" fehlt."""
    data = json.loads(Path(path).read_text())
    if "camera" not in data:
        raise ValueError(
            f"{path}: JSON-Datei enthaelt keinen Top-Level-Schluessel 'camera'"
        )
    return CameraSettings.from_dict(data["camera"])
