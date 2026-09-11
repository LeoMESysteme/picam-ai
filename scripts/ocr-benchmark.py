#!/usr/bin/env python3
"""Erkennungsqualitaet messen. Schreibt nichts in die Doku - das macht ein Mensch.

Aufruf:
    ./.venv/bin/python scripts/ocr-benchmark.py --annotations var/workbench/annotations
    ./.venv/bin/python scripts/ocr-benchmark.py --dev 'var/workbench/clips/a*' --test 'var/workbench/clips/b*'

Erster Aufruf wertet jedes Unterverzeichnis von `--annotations` aus (Clips
oder Annotationen, gemischt) und druckt einen Gesamtbericht.

Zweiter Aufruf nimmt zwei Glob-Muster fuer Entwicklungs- und Testsatz,
erzwingt vorher `assert_disjoint_devices` (Splitgrenze ist die
Geraeteinstanz, siehe `dispread.benchmark`) und druckt beide Berichte
getrennt.

Die Zahlen hier sind Leserzahlen, keine Gate-Zahlen - siehe Docstring von
`dispread.benchmark`. Ob und wie eine Messung in `docs/VALIDATION.md`
festgehalten wird, entscheidet ein Mensch; dieses Skript schreibt dort
nichts.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dispread.benchmark import assert_disjoint_devices, directories_from_glob, evaluate_set
from dispread.ocr.sevenseg import SevenSegmentReader


def _print_report(label: str, report: dict) -> None:
    print(f"== {label} ==")
    print(f"auswertbar: {report['evaluated']}  uebersprungen: {len(report['skipped'])}")
    for path in report["skipped"]:
        print(f"  uebersprungen: {path}")
    print(
        f"korrekt={report['correct']}  falsch angenommen={report['wrong']}  "
        f"abgelehnt={report['rejected']}"
    )
    if report["wrong_classes"]:
        print("  Fehlerklassen (falsch angenommen):")
        for klasse, count in sorted(report["wrong_classes"].items()):
            print(f"    {klasse}: {count}")
    if report["reject_classes"]:
        print("  Ablehnungsgruende:")
        for reason, count in sorted(report["reject_classes"].items()):
            print(f"    {reason}: {count}")
    for outcome in report["outcomes"]:
        if outcome.wrong or outcome.rejected:
            flag = "FALSCH" if outcome.wrong else "abgelehnt"
            print(f"  [{flag}] {outcome.source_id} (Geraet {outcome.device_id}): soll={outcome.expected}")
            for example in outcome.examples:
                print(f"      {example}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--annotations",
        type=Path,
        help="Verzeichnis mit Clip- oder Annotationsunterordnern (var/workbench/annotations o.ae.)",
    )
    parser.add_argument("--dev", help="Glob-Muster fuer den Entwicklungssatz")
    parser.add_argument("--test", help="Glob-Muster fuer den Testsatz")
    args = parser.parse_args()

    if args.annotations and (args.dev or args.test):
        parser.error("--annotations schliesst --dev/--test aus - ein Aufruf, ein Satz")
    if bool(args.dev) != bool(args.test):
        parser.error("--dev und --test muessen zusammen angegeben werden")
    if not args.annotations and not args.dev:
        parser.error("Entweder --annotations oder --dev/--test angeben")

    reader = SevenSegmentReader()

    if args.annotations:
        directories = sorted(p for p in args.annotations.iterdir() if p.is_dir())
        report = evaluate_set(directories, reader)
        _print_report(str(args.annotations), report)
        return 0

    development = directories_from_glob(args.dev)
    test = directories_from_glob(args.test)
    if not development:
        parser.error(f"--dev Muster traf kein Verzeichnis: {args.dev!r}")
    if not test:
        parser.error(f"--test Muster traf kein Verzeichnis: {args.test!r}")

    try:
        assert_disjoint_devices(development, test)
    except ValueError as exc:
        print(f"FEHLER: {exc}", file=sys.stderr)
        return 1

    _print_report(f"Entwicklungssatz ({args.dev})", evaluate_set(development, reader))
    _print_report(f"Testsatz ({args.test})", evaluate_set(test, reader))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
