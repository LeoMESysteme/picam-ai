#!/usr/bin/env python3
"""Leserlaufzeit auf dem Pi 5 messen (Plan Messpfad live, Task 1).

Liest ein gespeichertes Standbild mit Quad und Raster aus einem
`proposal.json` wiederholt durch Entzerren + Dot-Matrix-Leser und gibt
Median, p95 und Maximum in Millisekunden aus. Keine Kamera noetig.

    ./.venv/bin/python scripts/live-reader-benchmark.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

from dispread.charcells import CharGrid
from dispread.layout import CharLayout
from dispread.live import DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256
from dispread.live.benchmark import time_read_chain
from dispread.ocr.dotmatrix import DotMatrixReader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--still", type=Path, default=Path("var/diagnostics/sc7-assist/still.png"))
    parser.add_argument("--proposal", type=Path, default=Path("var/diagnostics/sc7-assist/proposal.json"))
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--templates-sha256", default=DEFAULT_TEMPLATES_SHA256)
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args(argv)
    image = cv2.imread(str(args.still))
    if image is None:
        print(f"Bild nicht lesbar: {args.still}", file=sys.stderr)
        return 2
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    layout = CharLayout(grid=CharGrid.from_dict(proposal["grid"]), unit="mV/V")
    reader = DotMatrixReader.from_file(args.templates, args.templates_sha256)
    stats = time_read_chain(reader, image, proposal["quad"], layout, repeats=args.repeats)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
