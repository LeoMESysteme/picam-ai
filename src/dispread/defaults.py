"""Bestehende Werkbank-Vorgaben, unveraendert relativ zum Arbeitsverzeichnis.

Keine Aufloesung gegen paths.ROOT/VAR: Die Vereinheitlichung des Pfadmodells
ist eine separate Entscheidung (Installer-Spec L6).
"""

from pathlib import Path

WORKBENCH_DATA_DIR = Path('var/workbench')
LIVE_DATA_DIR = Path('var/live')
TLS_DIR = WORKBENCH_DATA_DIR / 'tls'
TLS_CERT = TLS_DIR / 'cert.pem'
TLS_KEY = TLS_DIR / 'key.pem'
BRIDGE_DIR = WORKBENCH_DATA_DIR / 'bridge'
SERVE_PORT = 8080
