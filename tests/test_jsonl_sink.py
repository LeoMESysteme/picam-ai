"""Unbegrenzte Auditdatei je Live-Lauf und begrenzte Standardrotation."""

import json
from dataclasses import replace

from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.sink.jsonl import JsonlSink


def record(sequence):
    return ValueRecord(frame_sequence=sequence, capture_timestamp=Timestamp(0, TimeBaseKind.SYNTHETIC),
                       value=1.0, unit='mV/V', status=ValueStatus.VALID, confidence=0.0, profile_id='test',
                       trigger_sequence=None, result_timestamp=None)


def test_disabled_rotation_preserves_records_and_append(tmp_path):
    path = tmp_path / 'records.jsonl'
    sink = JsonlSink(path, max_bytes=0)
    sink.open()
    try:
        for sequence in range(20):
            assert sink.emit(record(sequence)).t_complete_ns is not None
    finally:
        sink.close()
    sink.open()
    sink.emit(replace(record(20), raw_text='+1.0'))
    sink.close()
    assert [json.loads(line)['frame_sequence'] for line in path.read_text().splitlines()] == list(range(21))
    assert list(tmp_path.iterdir()) == [path]
    assert sink.health().errors == 0


def test_default_rotation_is_bounded_and_therefore_unsuitable_for_complete_live_audits(tmp_path):
    path = tmp_path / 'records.jsonl'
    sink = JsonlSink(path)
    assert sink.max_bytes == 64 * 1024 * 1024 and sink.keep == 5
    sink.max_bytes = 1
    sink.open()
    try:
        for sequence in range(7):
            sink.emit(record(sequence))
    finally:
        sink.close()
    assert len(list(tmp_path.iterdir())) == 6
    assert json.loads(path.with_suffix('.jsonl.5').read_text())['frame_sequence'] == 2
