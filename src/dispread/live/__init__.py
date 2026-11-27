"""Live-Messpfad: Kamera, Einrichtung und Dot-Matrix-Lesen in der Werkbank.

Spec: docs/superpowers/specs/2026-10-12-messpfad-live-design.md. Dieses Paket
enthaelt keinen Web-Code; die Werkbank steuert es nur.
"""

from __future__ import annotations

from pathlib import Path

from dispread.defaults import LIVE_DATA_DIR as LIVE_DATA_DIR
from dispread.sensors import SensorDefinition, get_sensor

_DEFAULT_SENSOR = get_sensor()
_LEGACY_NAME = "templates-stufe2c-2026-09-30.json"
_LEGACY_TEMPLATE_SUFFIXES = (
    Path("src/dispread/data", _LEGACY_NAME).parts,
    Path("var/dotmatrix", _LEGACY_NAME).parts,
)

#: Eingefrorene Vorlagen Stufe 2c (Abnahme 3, 215/0/0).
DEFAULT_TEMPLATES = _DEFAULT_SENSOR.templates_path
DEFAULT_TEMPLATES_SHA256 = _DEFAULT_SENSOR.templates.sha256
#: Pflicht beim Start einer Live-Sitzung; wird aufgezeichnet, nicht angewandt.
DEFAULT_CALIBRATION = Path("var/calibration/timing-streamcam.json")
#: OpenCV-Threads fuer `dispread serve`, einmal beim Start gesetzt
#: (workbench/server.py), damit der Pi bedienbar bleibt.
LIVE_CV_THREADS = 2
RELEASE_NOTICE = _DEFAULT_SENSOR.release_notice


def resolve_templates_path(definition: SensorDefinition, configured: Path | None) -> Path:
    """Waehlt die Paketvorlage auch fuer fehlende Pfade aelterer Installationen."""
    if configured is None or definition.id != _DEFAULT_SENSOR.id:
        return definition.templates_path
    if (definition.id == _DEFAULT_SENSOR.id
            and any(configured.parts[-len(suffix):] == suffix for suffix in _LEGACY_TEMPLATE_SUFFIXES)
            and not configured.exists()):
        return definition.templates_path
    return configured
