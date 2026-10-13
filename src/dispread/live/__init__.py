"""Live-Messpfad: Kamera, Einrichtung und Dot-Matrix-Lesen in der Werkbank.

Spec: docs/superpowers/specs/2026-10-12-messpfad-live-design.md. Dieses Paket
enthaelt keinen Web-Code; die Werkbank steuert es nur.
"""

from __future__ import annotations

from pathlib import Path

#: Eingefrorene Vorlagen Stufe 2c (Abnahme 3, 215/0/0).
DEFAULT_TEMPLATES = Path("var/dotmatrix/templates-stufe2c-2026-09-30.json")
DEFAULT_TEMPLATES_SHA256 = "6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a"
#: Pflicht beim Start einer Live-Sitzung; wird aufgezeichnet, nicht angewandt.
DEFAULT_CALIBRATION = Path("var/calibration/timing-streamcam.json")
LIVE_DATA_DIR = Path("var/live")
RELEASE_NOTICE = (
    "Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V — "
    "andere Lichtquellen und Geräte nicht geprüft."
)
