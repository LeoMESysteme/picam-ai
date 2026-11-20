#!/usr/bin/env python3
"""Ende-zu-Ende-Versatz zwischen Telegramm und Anzeige, photometrisch -
duenne Huelle um `dispread.calibration.offset`.

Die Auswertung steht seit 2026-11-20 im Paket (dort auch Methode, Formel fuer
M und Vorzeichenkonvention), damit `picam kalibrieren` sie bei der
Inbetriebnahme nutzen kann. Dieses Skript setzt nur die Entwicklungs-
Eingabeorte (`_devdata.input_path`) ein; Aufruf, Bericht und Statistik sind
unveraendert:

    scripts/display-offset.py <aufnahme> --profile <profile.json>
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from _devdata import input_path  # noqa: E402

from dispread.calibration import offset as _offset  # noqa: E402

# Bisherige Skript-API (Funktionen, Konstanten) weiter anbieten.
globals().update({name: value for name, value in vars(_offset).items() if not name.startswith("__")})


def build_arg_parser():
    return _offset.build_arg_parser(input_type=input_path)


def run(args):
    args.session_dir = input_path(args.session_dir)
    return _offset.run(args)


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run(args)
    print(_offset.format_summary(result))
    print(f"\nJSON: {result['_out_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
