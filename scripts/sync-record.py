#!/usr/bin/env python3
"""Kamerabilder und den seriellen GSV-Strom derselben Sitzung gemeinsam
aufzeichnen - duenne Huelle um `dispread.calibration.record`.

Die Logik steht seit 2026-11-20 im Paket (dort auch die vollstaendige
Beschreibung), damit `picam kalibrieren` sie bei der Inbetriebnahme ohne
Entwicklungs-Checkout nutzen kann. Dieses Skript setzt nur die
Entwicklungsvorgaben ein: Eingabepfade ueber `_devdata.input_path`, Ausgabe
ohne `--output` nach `_devdata.diagnostic_output()`. Aufruf und Verhalten
sind unveraendert:

    ./.venv/bin/python scripts/sync-record.py --duration 30 \\
        --output var/diagnostics/lauf1
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from _devdata import diagnostic_output, input_path  # noqa: E402

from dispread.calibration import record as _record  # noqa: E402

# Bisherige Skript-API (Konstanten, Hilfsfunktionen) weiter anbieten.
globals().update({name: value for name, value in vars(_record).items() if not name.startswith("__")})

DEFAULT_OUTPUT_ROOT = diagnostic_output()


def parse_args(argv: list[str] | None = None):
    return _record.parse_args(argv, input_type=input_path)


def run(args) -> int:
    return _record.run(args, default_output_root=diagnostic_output())


def main(argv: list[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
