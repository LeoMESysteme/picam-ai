#!/usr/bin/env python3
"""Run the independent installer from a checkout or unpacked release."""
import sys
from pathlib import Path

if sys.version_info < (3, 9):  # noqa: UP036 -- bootstrap intentionally supports older OS Python
    raise SystemExit('Installer braucht Python >= 3.9; Produkt braucht Python >= 3.13.')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
from picam_installer.engine import main

raise SystemExit(main())
