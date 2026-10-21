#!/usr/bin/env python3
"""Live-Audit nachtraeglich gegen Referenz pruefen; keine Leser-Korrektur.

M = 695 ms wie gate-label.py (Festlegung 2026-09-23). Das vergangene
Schutzintervall enthaelt bereits die gemessene Anzeigeverzoegerung;
display_offset_ms wird deshalb nicht nochmals abgezogen. Keine Extrapolation
ueber Aufzeichnungsende oder Telegrammluecken > 1 s (OQ-40).
"""

from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median

from dispread.gsv2as_cell_text import cell_text_from_telegram
from dispread.records import to_boottime_ns

GUARD_NS = 695_000_000
MAX_GAP_NS = 1_000_000_000


def _rows(path):
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def _text(text):
    return ''.join((text or '').split())


def _distribution(counts):
    total = counts.total()
    return {'frames': total, 'by_status': dict(counts),
            'valid_share': counts['valid'] / total if total else None,
            'transition_share': counts['transition'] / total if total else None,
            'unreadable_share': counts['unreadable'] / total if total else None}


def evaluate(run_dir):
    run_dir = Path(run_dir)
    session = json.loads((run_dir / 'session.json').read_text(encoding='utf-8'))
    if session.get('test_run'):
        raise ValueError('Testlauf: keine freigegebenen Messwerte fuer einen Referenznachweis')
    audit = session.get('reference', {})
    if audit.get('dropped_oldest'):
        raise ValueError('Referenzaudit unvollstaendig: Queue-Ueberlauf')
    reference = list(_rows(run_dir / 'reference.jsonl'))
    if audit.get('lines') is not None and audit['lines'] != len(reference):
        raise ValueError('Referenzaudit unvollstaendig: Zeilenzahl passt nicht zu session.json')
    if not reference:
        raise ValueError('Keine Referenztelegramme')
    times, texts, starts, changes, gaps, values = [], [], [], [], [], []
    previous = None
    rejected = False
    changes_after_gap = 0
    for entry in reference:
        t = entry['t_boottime_ns']
        if previous is not None and t <= previous:
            raise ValueError('Referenzzeitstempel nicht streng aufsteigend')
        previous = t
        if entry.get('error'):
            if entry['cell_text'] is not None or entry['value'] is not None:
                raise ValueError('Abgelehntes Telegramm enthaelt einen Wert')
            rejected = True
            continue
        text = cell_text_from_telegram(entry['raw'])
        if text != entry['cell_text'] or float(entry['raw'].split()[0]) != entry['value']:
            raise ValueError('Referenz-Zellentext passt nicht zum Telegramm')
        interrupted = bool(times) and (rejected or t - times[-1] > MAX_GAP_NS)
        if interrupted or rejected:
            gaps.append((times[-1] if times else reference[0]['t_boottime_ns'], t))
        if not times or text != texts[-1]:
            if interrupted:
                # Burst-Lesezeit nach Pause ist kein Zeitpunkt des Wertwechsels.
                changes_after_gap += 1
            elif times:
                changes.append(t)
            start = t
        if interrupted:
            # Auch bei gleichem Wert keine erste VALID ueber eine Luecke zuordnen.
            start = t
        times.append(t)
        texts.append(text)
        values.append(entry['value'])
        starts.append(start)
        rejected = False
    if not times:
        raise ValueError('Keine gueltigen Referenztelegramme')
    if rejected:
        gaps.append((times[-1], previous))
    counts = {'stable': Counter(), 'changing': Counter(), 'unknown': Counter()}
    displays = {}
    compared = undecided = uncovered = errors = 0
    first_valid = {}
    gap_ends = [b for _, b in gaps]
    # Records chronologisch pruefen; keine Reihenfolge aus Dateisystemzeiten ableiten.
    previous_t = None
    for record in _rows(run_dir / 'records.jsonl'):
        t = to_boottime_ns(record['capture_timestamp'], session)
        if previous_t is not None and t < previous_t:
            raise ValueError('Aufnahmezeitstempel nicht aufsteigend')
        previous_t = t
        state = record['status']
        i = bisect.bisect_right(times, t) - 1
        gap_i = bisect.bisect_left(gap_ends, t - GUARD_NS)
        gap_overlap = gap_i < len(gaps) and gaps[gap_i][0] <= t
        known = i >= 0 and t <= times[-1] and not gap_overlap
        stable = known and t - starts[i] >= GUARD_NS
        group = 'stable' if stable else 'changing' if known else 'unknown'
        counts[group][state] += 1
        if known:
            key = _text(texts[i])
            displays.setdefault(key, {'stable': Counter(), 'changing': Counter()})[group][state] += 1
            matches = (_text(record.get('raw_text')) == key and record.get('unit') == 'mV/V'
                       and record.get('value') == values[i])
            if state == 'valid' and matches:
                first_valid.setdefault(starts[i], t)
        if state != 'valid':
            continue
        if not known:
            uncovered += 1
            continue
        if not stable:
            undecided += 1
            continue
        compared += 1
        if not matches:
            errors += 1
    # Der Anfang ist kein beobachteter Wechsel. Nur Wechsel mit erstem VALID.
    delays = sorted((first_valid[t] - t) / 1e6 for t in changes if t in first_valid)
    p90 = None
    if delays:
        position = (len(delays) - 1) * .9
        lo = int(position)
        p90 = delays[lo] + (delays[min(lo + 1, len(delays)-1)] - delays[lo]) * (position - lo)
    return {
        'guard_ms': GUARD_NS / 1e6, 'misreads': errors, 'compared_valid': compared,
        'undecided_valid': undecided, 'uncovered_valid': uncovered,
        'changes_after_gap': changes_after_gap,
        'changes_after_gap_note': 'Wechsel nach Telegrammluecke (Werteplan): Verzoegerung nicht messbar',
        **{key: _distribution(value) for key, value in counts.items()},
        'display_states': {key: {group: _distribution(c) for group, c in groups.items()}
                           for key, groups in displays.items()},
        'latency_ms': {'median': median(delays) if delays else None, 'p90': p90, 'n': len(delays),
                       'changes_without_valid': len(changes)-len(delays)},
        'tolerance_frames': session.get('summary', {}).get('tolerance_frames', 0),
        'reader_tolerance': session.get('reader_tolerance'),
        'misreads_tolerance_run': errors if session.get('reader_tolerance') else 0,
        'tolerance_note': 'Fehllesungen im gesamten Toleranzlauf; Einzelbilder oberhalb der alten Schwelle '
                          'sind im bisherigen Recordformat nicht markiert.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
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
