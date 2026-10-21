import json
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from dispread.frames import Frame
from dispread.live import diagnostics as diag
from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus
from dispread.track import TrackResult


def sample(sequence=1, lost=False):
    frame = Frame(sequence, np.arange(600, dtype=np.uint8).reshape(10, 20, 3),
                  Timestamp(sequence, TimeBaseKind.SYNTHETIC), 'fake', raw_metadata={'sequence': 42})
    record = ValueRecord(sequence, frame.capture_timestamp, None, None, ValueStatus.UNREADABLE,
                         0.0, 'test', None, None,
                         reject_reasons=('tracking_lost:abdeckung' if lost else 'unlesbar',))
    track = TrackResult(None if lost else ((0, 0), (19, 0), (19, 9), (0, 9)), 2.0, 0.5,
                        0.1 if lost else 0.9, 'abdeckung' if lost else None)
    return frame, record, track


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setattr(diag.shutil, 'disk_usage', lambda root: SimpleNamespace(free=2_000_000_000))
    monkeypatch.setattr(diag, 'read_mem_available', lambda: 2_000_000_000, raising=False)
    staging = tmp_path / 'shm'
    staging.mkdir()
    now = [0.0]
    recorder = diag.DiagnosticRecorder(tmp_path / 'session' / 'run-01', enabled=True,
                                       staging_root=staging, monotonic=lambda: now[0])
    recorder.start(profile_sha256='p' * 64, reference_sha256='r' * 64)
    yield recorder, now
    recorder.stop()
    assert recorder.wait(3)


def observe(recorder, sequence=1, lost=False, **kw):
    recorder.observe(*sample(sequence, lost), owner_sequence=sequence + 100, mode='rahmenbereiche', **kw)


def rows(recorder):
    return [json.loads(line) for line in (recorder.out_dir / 'diagnose' / 'images.jsonl').read_text().splitlines()]


def test_loss_recovery_periodic_and_each_mark_with_raw_pixels(recorder):
    rec, now = recorder
    observe(rec)
    now[0] = 30
    observe(rec, 2)
    now[0] = 30.1
    observe(rec, 3, True)
    now[0] = 30.9
    observe(rec, 4, True)
    now[0] = 31.1
    observe(rec, 5, True)
    now[0] = 31.2
    observe(rec, 6)
    rec.mark(1)
    now[0] += 2
    rec.mark(2)
    now[0] += 0.1
    observe(rec, 7, True)
    rec.stop()
    assert rec.wait(3)
    entries = rows(rec)
    assert [e['trigger'] for e in entries] == [
        'periodic', 'tracking_loss', 'tracking_loss', 'tracking_recovered', 'operator_mark',
        'operator_mark', 'tracking_loss']
    assert [e['frame_sequence'] for e in entries] == [2, 3, 5, 6, 6, 6, 7]
    entry = entries[1]
    assert entry['owner_sequence'] == 103 and entry['camera_sequence'] == 42
    assert entry['capture_timestamp'] == sample(3)[0].capture_timestamp.to_dict()
    assert entry['tracking'] == {'mode': 'rahmenbereiche', 'reason': 'abdeckung', 'score': 0.1,
                                 'shift': 2.0, 'rotation_deg': 0.5, 'quad': None}
    assert entry['status'] == 'unreadable' and entry['reject_reasons'] == ['tracking_lost:abdeckung']
    assert entry['profile_sha256'] == 'p' * 64 and entry['reference_frame_sha256'] == 'r' * 64
    for entry in entries:
        assert np.array_equal(cv2.imread(str(rec.out_dir / 'diagnose' / entry['image'])), sample()[0].image)
    status = rec.status()
    assert status['saved'] == 7 and status['copied']
    assert not rec.copying and not rec.staging.exists()
    assert status['bytes'] == sum(p.stat().st_size for p in (rec.out_dir / 'diagnose').iterdir())


def test_insufficient_space_disables_only_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr(diag.shutil, 'disk_usage', lambda root: SimpleNamespace(
        free=diag.MAX_BYTES + diag.SPACE_MARGIN_BYTES - 1))
    rec = diag.DiagnosticRecorder(tmp_path / 'run', enabled=True, staging_root=tmp_path)
    rec.start(profile_sha256='p', reference_sha256='r')
    observe(rec, lost=True)
    assert not rec.status()['enabled'] and 'Platz' in rec.status()['reason']
    assert not rec.staging.exists()


def test_marks_before_first_frame_are_bounded_and_keep_numbers(recorder):
    rec, now = recorder
    for n in range(10, 10 + diag.QUEUE_SIZE + 2):
        now[0] += 2
        rec.mark(n)
    observe(rec)
    rec.stop()
    assert rec.wait(3)
    assert [e['mark'] for e in rows(rec)] == list(range(10, 10 + diag.QUEUE_SIZE))
    assert rec.status()['dropped_queue'] == 2


def test_mark_without_any_frame_reports_dropped_image_at_stop(recorder):
    rec, _ = recorder
    rec.mark(1)
    rec.stop()
    assert rec.wait(3)
    assert rec.status()['dropped_queue'] == 1 and rec.status()['saved'] == 0


@pytest.mark.parametrize('limit', ['images', 'bytes'])
def test_both_limits_are_hard(recorder, monkeypatch, limit):
    rec, _ = recorder
    monkeypatch.setattr(diag, 'MAX_IMAGES' if limit == 'images' else 'MAX_BYTES', 1)
    observe(rec, lost=True)
    rec.mark(1)
    rec.stop()
    assert rec.wait(3)
    status = rec.status()
    assert status['saved'] == (1 if limit == 'images' else 0)
    assert status['dropped_limit'] == (1 if limit == 'images' else 2)
    assert status['bytes'] <= diag.MAX_BYTES


def test_queue_drops_new_and_stop_does_not_wait_for_encoder(recorder, monkeypatch):
    rec, now = recorder
    entered, release = threading.Event(), threading.Event()
    encode = diag.cv2.imencode

    def slow(*args):
        entered.set()
        assert release.wait(3)
        return encode(*args)

    monkeypatch.setattr(diag.cv2, 'imencode', slow)
    try:
        observe(rec, lost=True)
        assert entered.wait(1)
        for n in range(diag.QUEUE_SIZE + 3):
            now[0] += 2
            rec.mark(n)
        start = time.monotonic()
        rec.stop()
        assert time.monotonic() - start < 2.0
        assert rec.copying and not rec.wait(0.01)
        assert rec.status()['dropped_queue'] == 3
    finally:
        release.set()
    assert rec.wait(3)
    assert [e.get('mark') for e in rows(rec)[1:]] == list(range(diag.QUEUE_SIZE))


def test_encoding_error_is_counted_and_first_error_kept(recorder, monkeypatch):
    rec, _ = recorder
    errors = iter(['Encoder kaputt', 'weiterer Fehler'])
    monkeypatch.setattr(diag.cv2, 'imencode', lambda *args: (_ for _ in ()).throw(OSError(next(errors))))
    observe(rec, lost=True)
    rec.mark(1)
    rec.stop()
    assert rec.wait(3)
    assert rec.status()['write_errors'] == 2
    assert 'Encoder kaputt' in rec.status()['first_error']
    assert rec.status()['saved'] == 0


def test_raw_snapshot_survives_reused_source_buffer(recorder, monkeypatch):
    rec, _ = recorder
    entered, release = threading.Event(), threading.Event()
    encode = diag.cv2.imencode

    def slow(*args):
        entered.set()
        assert release.wait(3)
        return encode(*args)

    monkeypatch.setattr(diag.cv2, 'imencode', slow)
    frame, record, track = sample(lost=True)
    expected = frame.image.copy()
    try:
        rec.observe(frame, record, track, owner_sequence=5, mode='ecc_alt')
        assert entered.wait(1)
        frame.image[:] = 0
        rec.stop()
    finally:
        release.set()
    assert rec.wait(3)
    entry = rows(rec)[0]
    assert np.array_equal(cv2.imread(str(rec.out_dir / 'diagnose' / entry['image'])), expected)


def test_image_write_error_is_counted_without_partial_image(recorder, monkeypatch):
    from pathlib import Path

    rec, _ = recorder
    write_bytes = Path.write_bytes

    def fail(path, data):
        if path.suffix == '.png':
            raise OSError('RAM voll')
        return write_bytes(path, data)

    monkeypatch.setattr(Path, 'write_bytes', fail)
    observe(rec, lost=True)
    rec.stop()
    assert rec.wait(3)
    assert rec.status()['write_errors'] == 1 and rec.status()['first_error'] == 'OSError: RAM voll'
    assert rec.status()['saved'] == 0 and rec.status()['bytes'] == 0
    assert not list((rec.out_dir / 'diagnose').glob('*.png'))


@pytest.mark.parametrize('short_copy', [False, True])
def test_copy_failure_keeps_staging_and_reports_path(recorder, monkeypatch, short_copy):
    rec, _ = recorder

    def fail(src, dst):
        if short_copy:
            dst.write_bytes(b'')
        else:
            raise OSError('Ziel voll')

    monkeypatch.setattr(diag.shutil, 'copyfile', fail)
    observe(rec, lost=True)
    rec.stop()
    assert rec.wait(3)
    status = rec.status()
    assert not status['copied'] and status['first_error']
    assert rec.staging.is_dir() and status['staging'] == str(rec.staging)
    assert not rec.copying


@pytest.mark.parametrize('available,enabled', [(1_099_999_999, False), (1_100_000_000, True)])
def test_start_requires_real_memory_reserve(tmp_path, monkeypatch, available, enabled):
    monkeypatch.setattr(diag.shutil, 'disk_usage', lambda root: SimpleNamespace(free=2_000_000_000))
    rec = diag.DiagnosticRecorder(tmp_path / 'run', enabled=True, staging_root=tmp_path,
                                  memory_available=lambda: available)
    rec.start(profile_sha256='p', reference_sha256='r')
    try:
        assert rec.status()['enabled'] is enabled
        if not enabled:
            assert 'MemAvailable' in rec.status()['reason'] and '500 MB' in rec.status()['reason']
            assert not rec.staging.exists()
    finally:
        rec.stop()
        assert rec.wait(3)


def test_meminfo_reader_uses_available_not_free(tmp_path):
    meminfo = tmp_path / 'meminfo'
    meminfo.write_text('MemFree: 9999999 kB\nMemAvailable: 1234 kB\nSwapFree: 999999 kB\n')
    assert diag.read_mem_available(meminfo) == 1_263_616
    meminfo.write_text('MemFree: 9999999 kB\n')
    with pytest.raises(ValueError, match='MemAvailable'):
        diag.read_mem_available(meminfo)


def test_memory_pressure_drops_before_copy_and_checks_at_most_once_per_second(tmp_path, monkeypatch):
    available, now, reads = [2_000_000_000], [0.0], []
    def memory():
        reads.append(now[0])
        return available[0]
    monkeypatch.setattr(diag.shutil, 'disk_usage', lambda root: SimpleNamespace(free=2_000_000_000))
    rec = diag.DiagnosticRecorder(tmp_path / 'run', enabled=True, staging_root=tmp_path,
                                  monotonic=lambda: now[0], memory_available=memory)
    rec.start(profile_sha256='p', reference_sha256='r')
    try:
        available[0] = 499_999_999
        now[0] = 1.0
        observe(rec, lost=True)
        now[0] = 1.5
        rec.mark(1)
        assert rec.status()['saved'] == 0 and rec.status()['dropped_memory'] == 2
        assert reads == [0.0, 1.0]
        available[0] = 500_000_000
        now[0] = 2.0
        observe(rec, 2, True)
    finally:
        rec.stop()
        assert rec.wait(3)
    assert rec.status()['saved'] == 1 and rows(rec)[0]['frame_sequence'] == 2


@pytest.mark.parametrize('limit', ['images', 'bytes'])
def test_exhausted_limit_skips_snapshot_copy(recorder, monkeypatch, limit):
    rec, now = recorder
    monkeypatch.setattr(diag, 'MAX_IMAGES' if limit == 'images' else 'MAX_BYTES', 0)
    attempted = threading.Event()
    original_save = rec._save
    def save(*args):
        try:
            return original_save(*args)
        finally:
            attempted.set()
    monkeypatch.setattr(rec, '_save', save)
    observe(rec, lost=True)
    # A byte-limit refusal must latch full; the image count can be checked immediately.
    if limit == 'bytes':
        assert attempted.wait(1)
    class NoCopy:
        def copy(self):
            pytest.fail('snapshot copied after diagnostic limit')
    frame, record, track = sample()
    object.__setattr__(frame, 'image', NoCopy())
    rec.observe(frame, record, track, owner_sequence=2, mode='ecc_alt')
    now[0] += 2
    rec.mark(1)
    assert rec.status()['dropped_limit'] >= 2


def test_marks_are_rate_limited_but_boundary_image_is_accepted(recorder):
    rec, now = recorder
    observe(rec)
    rec.mark(1)
    now[0] = 1.999
    rec.mark(2)
    now[0] = 2.0
    rec.mark(3)
    rec.stop()
    assert rec.wait(3)
    assert [e['mark'] for e in rows(rec)] == [1, 3]
    assert rec.status()['dropped_mark_rate'] == 1


def test_finisher_start_failure_never_escapes_and_retains_staging(recorder, monkeypatch):
    rec, _ = recorder
    observe(rec, lost=True)
    start = threading.Thread.start
    def fail_copy(thread):
        if thread.name == 'diagnose-copy':
            raise RuntimeError('kein Thread verfuegbar')
        return start(thread)
    monkeypatch.setattr(threading.Thread, 'start', fail_copy)
    rec.stop()
    assert not rec.copying
    assert rec.status()['first_error'] == 'RuntimeError: kein Thread verfuegbar'
    assert rec.staging.exists() and not rec.status()['copied']
    rec._worker.join(1)
    assert not rec._worker.is_alive()


def test_writer_blocks_until_stop_sentinel(tmp_path, monkeypatch):
    import queue

    calls, entered = [], threading.Event()
    class ObservedQueue(queue.Queue):
        def get(self, block=True, timeout=None):
            calls.append(timeout)
            entered.set()
            return super().get(block, timeout)
    monkeypatch.setattr(diag.queue, 'Queue', ObservedQueue)
    monkeypatch.setattr(diag, 'read_mem_available', lambda: 2_000_000_000, raising=False)
    monkeypatch.setattr(diag.shutil, 'disk_usage', lambda root: SimpleNamespace(free=2_000_000_000))
    rec = diag.DiagnosticRecorder(tmp_path / 'run', enabled=True, staging_root=tmp_path)
    rec.start(profile_sha256='p', reference_sha256='r')
    try:
        assert entered.wait(1)
        assert calls == [None]
    finally:
        rec.stop()
        assert rec.wait(3)


def test_copy_remains_pending_until_completion_metadata_is_saved(recorder):
    rec, _ = recorder
    entered, release = threading.Event(), threading.Event()
    def on_done():
        entered.set()
        assert release.wait(3)
    try:
        rec.stop(on_done=on_done)
        assert entered.wait(1)
        assert rec.copying and not rec.wait(0.01)
    finally:
        release.set()
        assert rec.wait(3)
