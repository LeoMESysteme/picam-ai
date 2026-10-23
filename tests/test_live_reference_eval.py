import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / 'scripts/live-reference-eval.py'


def fixture_run(tmp_path, *, wrong=False, missing_offset=False):
    session = {'clock_offset_boottime_minus_monotonic_ns': {'start': 100, 'end': 100},
               'timing_calibration': {'display_offset_ms': 89.6},
               'summary': {'tolerance_frames': 1}, 'reader_tolerance': {'factor': 1.44}}
    if missing_offset:
        session.pop('clock_offset_boottime_minus_monotonic_ns')
    (tmp_path / 'session.json').write_text(json.dumps(session))
    refs = [{'t_boottime_ns': int(t * 1e9), 'raw': f'+0{v}.2345 mV/V',
             'cell_text': f'+ {v}.2345 ', 'value': v + .2345}
            for t, v in [(0, 1), (.5, 1), (1, 1), (1.5, 2), (2, 2), (2.5, 2), (3, 2)]]
    records = []
    for t, state, text in [(1, 'valid', '+1.2345'), (1.6, 'valid', '+1.2345'),
                           (1.7, 'transition', None), (1.8, 'unreadable', None),
                           (2.3, 'valid', '+2.2345' if not wrong else '+9.9999')]:
        records.append({'status': state, 'raw_text': text, 'unit': 'mV/V',
                        'value': float(text) if text else None,
                        'capture_timestamp': {'value_ns': int(t * 1e9)-100, 'base': 'v4l2_monotonic'}})
    for name, rows in [('records', records), ('reference', refs)]:
        (tmp_path / f'{name}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return tmp_path


def test_correct_guarded_and_delayed_values(tmp_path):
    spec = importlib.util.spec_from_file_location('reference_eval', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.evaluate(fixture_run(tmp_path))
    assert result['misreads'] == 0 and result['undecided_valid'] == 1
    assert result['compared_valid'] == 2
    assert result['latency_ms']['median'] == pytest.approx(800)
    assert result['latency_ms']['p90'] == pytest.approx(800)
    assert result['changing']['by_status'] == {'valid': 1, 'transition': 1, 'unreadable': 1}
    assert result['changing']['transition_share'] == pytest.approx(1/3)
    assert result['tolerance_frames'] == 1


@pytest.mark.parametrize('wrong,missing,code', [(False, False, 0), (True, False, 1), (False, True, 2)])
def test_cli_exit_codes(tmp_path, wrong, missing, code):
    fixture_run(tmp_path, wrong=wrong, missing_offset=missing)
    result = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path), '--json'],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == code, result.stdout + result.stderr
    if code != 2:
        data = json.loads(result.stdout)
        assert data['misreads'] == int(wrong)
        assert data['misreads_tolerance_run'] == int(wrong)
    else:
        assert 'Versatz' in result.stderr or 'clock_offset' in result.stderr


def _module():
    spec = importlib.util.spec_from_file_location('reference_eval', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_numeric_value_must_also_match_reference(tmp_path):
    fixture_run(tmp_path)
    path = tmp_path / 'records.jsonl'
    records = [json.loads(line) for line in path.read_text().splitlines()]
    for r in records:
        r['value'] = float(r['raw_text']) if r['status'] == 'valid' else None
    records[-1]['value'] = 99.0
    path.write_text(''.join(json.dumps(r)+'\n' for r in records))
    assert _module().evaluate(tmp_path)['misreads'] == 1


def test_suppressed_records_are_non_valid_even_without_session_marker(tmp_path):
    fixture_run(tmp_path)
    path = tmp_path / 'records.jsonl'
    records = [json.loads(line) for line in path.read_text().splitlines()]
    for record in records:
        if record['status'] == 'valid':
            record.update(status='unreadable', value=None, reject_reasons=['testlauf_keine_freigabe'])
    _write_rows(path, records)
    result = _module().evaluate(tmp_path)
    assert result['compared_valid'] == result['undecided_valid'] == result['uncovered_valid'] == 0
    assert result['stable']['by_status'] == {'unreadable': 2}
    assert result['changing']['by_status'] == {'unreadable': 2, 'transition': 1}
    assert result['latency_ms']['n'] == 0


def test_dropped_reference_audit_is_not_a_validation(tmp_path):
    fixture_run(tmp_path)
    path = tmp_path / 'session.json'
    session = json.loads(path.read_text())
    session['reference'] = {'enabled': True, 'dropped_oldest': 1}
    path.write_text(json.dumps(session))
    with pytest.raises(ValueError, match='unvollstaendig'):
        _module().evaluate(tmp_path)


@pytest.mark.parametrize('session,reason', [
    ({'test_run': {'testlauf': True}, 'reference': {'dropped_oldest': 1}}, 'Testlauf'),
    ({'reference': {'dropped_oldest': 1}}, 'Queue-Ueberlauf'),
])
def test_session_rejection_precedes_missing_reference(tmp_path, capsys, session, reason):
    (tmp_path / 'session.json').write_text(json.dumps(session))
    assert _module().main([str(tmp_path)]) == 2
    assert reason in capsys.readouterr().err


def _write_rows(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def test_change_after_gap_has_no_measurable_latency_or_change_shares(tmp_path):
    fixture_run(tmp_path)
    refs = [{'t_boottime_ns': int(t * 1e9), 'raw': f'+0{v}.2345 mV/V',
             'cell_text': f'+ {v}.2345 ', 'value': v + .2345}
            for t, v in [(0, 1), (.5, 1), (1, 1), (3, 2), (3.5, 2), (4, 2), (4.5, 2), (5, 2)]]
    records = [{'status': 'valid', 'raw_text': '+2.2345', 'value': 2.2345, 'unit': 'mV/V',
                'capture_timestamp': {'value_ns': int(t * 1e9) - 100, 'base': 'v4l2_monotonic'}}
               for t in [3.05, 4.5]]
    _write_rows(tmp_path / 'reference.jsonl', refs)
    _write_rows(tmp_path / 'records.jsonl', records)
    result = _module().evaluate(tmp_path)
    assert result['changes_after_gap'] == 1
    assert result['changes_after_gap_note'] == 'Wechsel nach Telegrammluecke (Werteplan): Verzoegerung nicht messbar'
    assert result['latency_ms'] == {'median': None, 'p90': None, 'n': 0, 'changes_without_valid': 0}
    assert result['changing']['frames'] == 0
    assert result['uncovered_valid'] == 1
    assert result['undecided_valid'] == 0
    assert result['compared_valid'] == 1


def test_parse_error_masks_previous_telegram_through_next_valid_plus_guard(tmp_path):
    fixture_run(tmp_path)
    path = tmp_path / 'reference.jsonl'
    refs = [json.loads(line) for line in path.read_text().splitlines()]
    refs.insert(2, {'t_boottime_ns': 750_000_000, 'raw': 'bad',
                    'cell_text': None, 'value': None, 'error': 'invalid telegram'})
    _write_rows(path, refs)
    session_path = tmp_path / 'session.json'
    session = json.loads(session_path.read_text())
    session['reference'] = {'parse_errors': 1, 'lines': len(refs), 'dropped_oldest': 0}
    session_path.write_text(json.dumps(session))
    records = [{'status': 'valid', 'raw_text': '+9.9999', 'value': 9.9999, 'unit': 'mV/V',
                'capture_timestamp': {'value_ns': int(t * 1e9) - 100, 'base': 'v4l2_monotonic'}}
               for t in [.5, .6, 1.69, 1.8, 2.3, 3.1]]
    _write_rows(tmp_path / 'records.jsonl', records)
    result = _module().evaluate(tmp_path)
    assert result['uncovered_valid'] == 4
    assert result['undecided_valid'] == 1
    assert result['compared_valid'] == 1 and result['misreads'] == 1


def test_continuous_change_measures_first_valid_inside_guard(tmp_path):
    fixture_run(tmp_path)
    records_path = tmp_path / 'records.jsonl'
    records = [json.loads(line) for line in records_path.read_text().splitlines()]
    records[1].update(raw_text='+2.2345', value=2.2345)
    _write_rows(records_path, records)
    result = _module().evaluate(tmp_path)
    assert result['latency_ms']['median'] == pytest.approx(100)
    assert result['changes_after_gap'] == 0
    assert result['undecided_valid'] == 1 and result['uncovered_valid'] == 0


def test_initial_and_trailing_parse_errors_have_no_coverage(tmp_path):
    fixture_run(tmp_path)
    path = tmp_path / 'reference.jsonl'
    refs = [json.loads(line) for line in path.read_text().splitlines()]
    refs[0] = {'t_boottime_ns': 0, 'raw': 'bad', 'cell_text': None, 'value': None, 'error': 'invalid'}
    refs[-1] = {**refs[0], 't_boottime_ns': 3_000_000_000}
    _write_rows(path, refs)
    records = [{'status': 'valid', 'raw_text': '+1.2345', 'value': 1.2345, 'unit': 'mV/V',
                'capture_timestamp': {'value_ns': int(t * 1e9) - 100, 'base': 'v4l2_monotonic'}}
               for t in [.6, 2.5, 2.8]]
    _write_rows(tmp_path / 'records.jsonl', records)
    result = _module().evaluate(tmp_path)
    assert result['uncovered_valid'] == 3 and result['undecided_valid'] == 0


def test_latency_does_not_bridge_an_intervening_gap(tmp_path):
    fixture_run(tmp_path)
    refs = [{'t_boottime_ns': int(t * 1e9), 'raw': f'+0{v}.2345 mV/V',
             'cell_text': f'+ {v}.2345 ', 'value': v + .2345}
            for t, v in [(0, 1), (.5, 1), (1, 2), (1.1, 2), (3, 2), (3.5, 2), (4, 2), (4.5, 2)]]
    _write_rows(tmp_path / 'reference.jsonl', refs)
    _write_rows(tmp_path / 'records.jsonl', [
        {'status': 'valid', 'raw_text': '+2.2345', 'value': 2.2345, 'unit': 'mV/V',
         'capture_timestamp': {'value_ns': 4_000_000_000 - 100, 'base': 'v4l2_monotonic'}}])
    result = _module().evaluate(tmp_path)
    assert result['latency_ms'] == {'median': None, 'p90': None, 'n': 0, 'changes_without_valid': 1}
    assert result['changes_after_gap'] == 0
