#!/usr/bin/env python3
"""Live-Audit nachtraeglich gegen Referenz pruefen; keine Leser-Korrektur.

M = 695 ms wie gate-label.py (Festlegung 2026-09-23). Das vergangene
Schutzintervall enthaelt bereits die gemessene Anzeigeverzoegerung;
display_offset_ms wird deshalb nicht nochmals abgezogen. Keine Extrapolation
ueber Aufzeichnungsende oder Telegrammluecken > 1 s (OQ-40).
"""

from __future__ import annotations

import argparse
import json
import sys

from _devdata import input_path

from dispread.live.reference_eval import evaluate_records, validate_reference_session


def _rows(path):
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def evaluate(run_dir):
    run_dir = input_path(run_dir)
    session = json.loads((run_dir / 'session.json').read_text(encoding='utf-8'))
    validate_reference_session(session)
    reference = list(_rows(run_dir / 'reference.jsonl'))
    return evaluate_records(session, reference, _rows(run_dir / 'records.jsonl'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=input_path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = evaluate(args.run_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Abgleich abgelehnt: {exc}', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Fehllesungen: {result['misreads']} / {result['compared_valid']} entschiedene VALID")
        print(f"Unentschiedene VALID: {result['undecided_valid']}")
        print(f"VALID ohne Referenzdeckung: {result['uncovered_valid']}")
        print(f"{result['changes_after_gap_note']}: {result['changes_after_gap']}")
        for key, label in [('stable', 'Stabil'), ('changing', 'Im Wechsel'), ('unknown', 'Ohne Referenzfenster')]:
            print(f"{label}: {json.dumps(result[key], ensure_ascii=False)}")
        print(f"Je Anzeigezustand: {json.dumps(result['display_states'], ensure_ascii=False)}")
        print(f"Verzoegerung (ms): {json.dumps(result['latency_ms'])}")
        print(f"Toleranzbilder: {result['tolerance_frames']}; Fehllesungen im Toleranzlauf: "
              f"{result['misreads_tolerance_run']}")
        print(result['tolerance_note'])
    return 1 if result['misreads'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
