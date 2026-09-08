#!/usr/bin/env python3
"""Kompatibler Einstieg in die authentifizierte Kamera-Workbench.

Einmalig: ./.venv/bin/dispread init-tls
Start:    ./.venv/bin/python examples/17_camera_display_preview.py
Anmeldung ueber HTTPS mit dem Linux-Passwort von me-systeme.
"""

import sys

from dispread.workbench.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["serve", *sys.argv[1:]]))
