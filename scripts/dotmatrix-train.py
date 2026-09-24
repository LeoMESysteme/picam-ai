#!/usr/bin/env python3
r"""Trainiert Vorlagen des Dot-Matrix-Lesers aus geernteten Proben (Task 7,
Training und Entwicklungsmessung Stufe 1).

Nimmt die von `scripts/dotmatrix-dataset.py` geladenen Zellen der gewaehlten
`--groups` (Sitzungen), baut je Zeichenklasse eine Vorlage
(`dispread.ocr.dotmatrix_templates.fit_templates`), prueft sie gegen den
HD44780-ROM-Zeichensatz (`rom_check`) und schreibt bei bestandener Probe
`templates.json` samt Schwellen `D_max`/`margin_min`
(`compute_thresholds`, Formel `thresholds_v1`).

Scheitert die ROM-Gegenprobe, wird **nicht** geschrieben (Exit 3) - das
deutet auf falsche Labels oder ein verschobenes Raster hin, nie auf einen
Grund, Schwellen oder ROM-Tabelle nachtraeglich anzupassen (Konzept.md §7,
AGENTS.md "Nicht verhandelbar"). Stattdessen wird je betroffener Klasse das
bei 0,5 binarisierte gelernte Muster neben dem ROM-Muster ausgegeben, damit
sich der Fehler von Auge nachvollziehen laesst.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from dispread.ocr.dotmatrix_font import CLASSES, rom_vector
from dispread.ocr.dotmatrix_templates import (
    Templates,
    binarized_pattern,
    compute_thresholds,
    fit_templates,
    rom_check,
    save_templates,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dataset_module():
    """Laedt `scripts/dotmatrix-dataset.py` (Bindestrich im Namen, kein
    normaler Import moeglich) - Muster wie `tests/test_dotmatrix_dataset.py`.
    Ueber `sys.modules` gecacht, damit `dotmatrix-train.py` und
    `dotmatrix-eval.py` in einem Testlauf nicht zweimal laden."""
    name = "dotmatrix_dataset"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / "scripts" / "dotmatrix-dataset.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_samples_by_char(samples) -> dict[str, list]:
    """Aus `CellSample`s: je Zelle 0..8 einer Probe wird ihr Vektor unter
    dem gelabelten Zeichen einsortiert (Auftrag Task 7)."""
    samples_by_char: dict[str, list] = {c: [] for c in CLASSES}
    for s in samples:
        for i in range(9):
            samples_by_char[s.cell_text[i]].append(s.vectors[i])
    return samples_by_char


def _report_rom_mismatch(mean: dict, bad: list[str]) -> None:
    print("ROM-Gegenprobe gescheitert - Labels oder Raster pruefen, keine Vorlagen geschrieben:", file=sys.stderr)
    for ch in bad:
        print(f"  Zeichen {ch!r}:", file=sys.stderr)
        print(f"    gelernt: {binarized_pattern(mean[ch])}", file=sys.stderr)
        print(f"    rom:     {binarized_pattern(rom_vector(ch))}", file=sys.stderr)


def train(samples_by_char: dict[str, list], groups: tuple[str, ...]) -> Templates | list[str]:
    """Baut die Vorlagen wie `build_templates`, gibt bei ROM-Abweichung aber
    die betroffenen Zeichen zurueck statt zu werfen - der Aufrufer
    entscheidet, wie er den Fehler meldet (hier: Muster ausgeben, Exit 3)."""
    mean, std = fit_templates(samples_by_char, groups)
    bad = rom_check(mean)
    if bad:
        _report_rom_mismatch(mean, bad)
        return bad
    d_max, margin_min = compute_thresholds(samples_by_char, mean, std)
    counts = {c: len(samples_by_char[c]) for c in CLASSES}
    return Templates(mean, std, d_max, margin_min, tuple(groups), counts)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trainiert Dot-Matrix-Vorlagen aus gewaehlten Ernte-Gruppen.")
    parser.add_argument("--dataset-root", type=Path, required=True, help="DatasetStore-Wurzelverzeichnis (nur lesen)")
    parser.add_argument("--profile-map", type=Path, required=True, help="Sitzungsprofil-Zuordnung (write-map)")
    parser.add_argument("--groups", required=True, help="Kommagetrennte Liste von Sitzungs-Gruppen, die trainiert werden")
    parser.add_argument("--out", type=Path, required=True, help="Zieldatei fuer templates.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset = _load_dataset_module()
    groups = tuple(g.strip() for g in args.groups.split(",") if g.strip())
    profile_map = dataset.read_profile_map(args.profile_map)
    stats: dict[str, int] = {}
    all_samples = dataset.load_cell_samples(args.dataset_root, profile_map, stats=stats)
    chosen = [s for s in all_samples if s.group in groups]
    missing = sorted(set(groups) - {s.group for s in chosen})
    if missing:
        print(f"Keine Proben fuer Gruppe(n): {missing}", file=sys.stderr)
    if not chosen:
        print("Keine Trainingsproben - nichts zu tun.", file=sys.stderr)
        return 2

    samples_by_char = build_samples_by_char(chosen)
    result = train(samples_by_char, groups)
    if isinstance(result, list):  # ROM-Gegenprobe gescheitert, bereits ausgegeben
        return 3

    sha = save_templates(result, args.out)
    print(f"Vorlagen geschrieben: {args.out} (sha256={sha})")
    print(f"d_max={result.d_max:.4f} margin_min={result.margin_min:.4f}")
    print("Zellen je Klasse:", json.dumps(result.counts, sort_keys=True, ensure_ascii=False))
    print("Datensatz-Zaehler:", json.dumps(stats, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
