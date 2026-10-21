"""Gemeinsamer Referenzabgleich fuer Live-Audit und sync-record-Replay."""

from __future__ import annotations

import bisect
from collections import Counter
from statistics import median

from dispread.gsv2as_cell_text import cell_text_from_telegram
from dispread.records import to_boottime_ns

GUARD_NS = 695_000_000
MAX_GAP_NS = 1_000_000_000


def _text(text):
    return ''.join((text or '').split())


def _distribution(counts):
    total = counts.total()
    return {'frames': total, 'by_status': dict(counts),
            'valid_share': counts['valid'] / total if total else None,
            'transition_share': counts['transition'] / total if total else None,
            'unreadable_share': counts['unreadable'] / total if total else None,
            'stale_share': counts['stale'] / total if total else None}


def validate_reference_session(session):
    """Sitzung vor jedem Zugriff auf ihre Referenzdateien pruefen."""
    if session.get('test_run'):
        raise ValueError('Testlauf: keine freigegebenen Messwerte fuer einen Referenznachweis')
    audit = session.get('reference', {})
    if audit.get('dropped_oldest'):
        raise ValueError('Referenzaudit unvollstaendig: Queue-Ueberlauf')


def evaluate_records(session, reference, records):
    """Nur nachtraeglich vergleichen; Referenz geht nie an Leser oder Gate."""
    validate_reference_session(session)
    audit = session.get('reference', {})
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
    tracking_losses = {key: Counter() for key in counts}
    displays = {}
    compared = undecided = uncovered = errors = 0
    first_valid = {}
    gap_ends = [b for _, b in gaps]
    # Records chronologisch pruefen; keine Reihenfolge aus Dateisystemzeiten ableiten.
    previous_t = None
    for record in records:
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
        tracking_losses[group].update(reason.split(':', 1)[1] for reason in record.get('reject_reasons', ())
                                      if reason.startswith('tracking_lost:'))
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
        **{key: {**_distribution(value), 'tracking_loss_reasons': dict(tracking_losses[key])}
           for key, value in counts.items()},
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
