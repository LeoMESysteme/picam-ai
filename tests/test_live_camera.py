import threading
import time

import numpy as np
import pytest
from test_uvc_source import _DEFAULT_SYSFS_ROOT, FakeCapture

from dispread.camera_settings import preview_settings
from dispread.frames import Frame
from dispread.frames.uvc_source import UvcSource
from dispread.live.camera import CameraOwner
from dispread.records import TimeBaseKind, Timestamp


def _frame(seq, ts_ns):
    ts = Timestamp(value_ns=ts_ns, base=TimeBaseKind.V4L2_MONOTONIC)
    return Frame(frame_sequence=seq, image=np.zeros((4, 4, 3), np.uint8), capture_timestamp=ts, source_id="fake")


class FakeSource:
    source_id = "fake"

    def __init__(self, stamps_ns, *, endless=False, fail_open=None):
        self.stamps = list(stamps_ns)
        self.endless = endless
        self.fail_open = fail_open
        self.read_error = None
        self.closed = False

    def open(self):
        if self.fail_open:
            raise RuntimeError(self.fail_open)

    def close(self):
        self.closed = True

    def frames(self):
        for i, ts in enumerate(self.stamps, start=1):
            yield _frame(i, ts)
        seq, ts = len(self.stamps), self.stamps[-1] if self.stamps else 0
        while self.endless:
            seq, ts = seq + 1, ts + 33_333_333
            time.sleep(0.005)
            yield _frame(seq, ts)
        self.read_error = "kein Bild innerhalb von READ_FAIL_TIMEOUT_S=2.0s"

    def describe(self):
        return {"fps": 30, "device": "/dev/fake"}

    capabilities = frozenset()


def _wait_stopped(owner, timeout=2.0):
    deadline = time.monotonic() + timeout
    while owner.status()["running"] and time.monotonic() < deadline:
        time.sleep(0.01)


def test_frames_and_gaps_are_counted_and_end_is_reported():
    source = FakeSource([33_333_333, 66_666_667, 166_666_667])
    owner = CameraOwner(lambda: source)
    owner.start()
    _wait_stopped(owner)
    status = owner.status()
    assert status["frames"] == 3 and status["gaps"] == 2
    assert status["running"] is False and "READ_FAIL_TIMEOUT_S" in status["error"]
    assert owner.latest()[0] == 3 and source.closed


def test_wait_newer_returns_newer_frames_and_stop_is_clean():
    owner = CameraOwner(lambda: FakeSource([33_333_333], endless=True))
    owner.start()
    first = owner.wait_newer(0, 1.0)
    second = owner.wait_newer(first[0], 1.0)
    assert second[0] > first[0]
    owner.stop()
    status = owner.status()
    assert status["running"] is False and status["error"] is None


def test_open_error_propagates_and_is_reported():
    owner = CameraOwner(lambda: FakeSource([], fail_open="Kamera nicht zu oeffnen (belegt?)"))
    with pytest.raises(RuntimeError, match="belegt"):
        owner.start()
    assert owner.status()["error"] == "Kamera nicht zu oeffnen (belegt?)"
    assert owner.wait_newer(0, 0.05) is None


def test_restart_swaps_source_and_keeps_owner_sequence_rising():
    owner = CameraOwner(lambda: FakeSource([33_333_333], endless=True))
    owner.start()
    before = owner.wait_newer(0, 1.0)[0]
    owner.restart(lambda: FakeSource([10], endless=True))
    after = owner.wait_newer(before, 1.0)
    assert after[0] > before
    owner.stop()


def test_control_target_only_for_sources_with_controls():
    owner = CameraOwner(lambda: FakeSource([1], endless=True))
    owner.start()
    assert owner.control_target() is None
    owner.stop()
    assert not any(thread.name == "camera-owner" and thread.is_alive() for thread in threading.enumerate())

    class ControlledSource(FakeSource):
        def set_controls(self, controls):
            self.controls = dict(controls)

        def get_controls(self, names):
            return {name: self.controls[name] for name in names}

    source = ControlledSource([1], endless=True)
    owner = CameraOwner(lambda: source)
    try:
        owner.start()
        assert owner.control_target() is source
        owner.control_target().set_controls([("focus_absolute", 40)])
        assert owner.control_target().get_controls(["focus_absolute"]) == {"focus_absolute": 40}
    finally:
        owner.stop()
    assert not any(thread.name == "camera-owner" and thread.is_alive() for thread in threading.enumerate())


def test_preview_uvc_owner_delivers_frames_and_source_status():
    capture = FakeCapture([1.0])
    source = UvcSource(
        preview_settings(), device="/dev/video8", capture_factory=lambda d: capture,
        sysfs_root=_DEFAULT_SYSFS_ROOT, apply_controls=False,
    )
    owner = CameraOwner(lambda: source)
    try:
        owner.start()
        assert owner.wait_newer(0, 1.0) is not None
        status = owner.status()
        assert status["source"]["device"] == "/dev/video8"
        assert status["source"]["controls_requested"] == {}
    finally:
        owner.stop()
        source.close()
    assert capture.released


def test_describe_failure_closes_source_and_reports_error():
    class BadDescription(FakeSource):
        def describe(self):
            raise RuntimeError("Beschreibung fehlgeschlagen")

    source = BadDescription([])
    owner = CameraOwner(lambda: source)
    with pytest.raises(RuntimeError, match="Beschreibung fehlgeschlagen"):
        owner.start()
    assert source.closed
    assert owner.status()["error"] == "Beschreibung fehlgeschlagen"
    assert owner.status()["running"] is False


class BlockingSource(FakeSource):
    def __init__(self, *, emit=True):
        super().__init__([])
        self.emit = emit
        self.reading = threading.Event()
        self.release = threading.Event()

    def frames(self):
        self.reading.set()
        if not self.release.wait(8.0):
            raise RuntimeError("Testquelle nicht freigegeben")
        if self.emit:
            yield _frame(1, 33_333_333)


class StallingSource(FakeSource):
    """Zwei einzeln abrufbare Bilder, danach blockiert der naechste Read."""

    def __init__(self):
        super().__init__([])
        self.next_frame = threading.Event()
        self.blocked = threading.Event()
        self.release = threading.Event()

    def frames(self):
        yield _frame(1, 33_333_333)
        if not self.next_frame.wait(5.0):
            return
        yield _frame(2, 66_666_666)
        self.blocked.set()
        if self.release.wait(5.0):
            yield _frame(3, 99_999_999)


def test_stream_stall_uses_last_delivery_and_stays_latched_until_restart(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    source = StallingSource()
    owner = CameraOwner(lambda: source)
    owner.start()
    try:
        first = owner.wait_newer(0, 1.0)
        now[0] = 101.5
        source.next_frame.set()
        assert source.blocked.wait(1.0)
        second = owner.wait_newer(first[0], 1.0)
        assert second is not None
        now[0] = 103.49
        assert owner.status().get('stalled') is False
        assert owner.status()['error'] is None
        now[0] = 103.51
        status = owner.status()
        assert status['running'] is True
        assert status['stalled'] is True
        assert 'Streamstillstand' in status['error'] and '2.0' in status['error']
        with pytest.raises(RuntimeError, match='Kamera.*hängt.*warten.*stecken'):
            owner.start()
        # Auch ein noch nicht abgeholtes Bild darf nach Ablauf nicht als neu gelten.
        assert owner.wait_newer(0, 0.01) is None
        assert owner.stop(timeout=0.02) is False
        with pytest.raises(RuntimeError, match='Kamera.*hängt.*warten.*stecken'):
            owner.restart()
        assert not source.closed
        source.release.set()
        assert owner.stop(timeout=1.0) is True
        assert owner.latest()[0] == second[0]  # spaetes Bild verworfen
        assert status['error'] in owner.status()['error']
        assert 'Lesethread' in owner.status()['error']
        assert owner.status()['stalled'] is True
        owner.restart(lambda: FakeSource([1], endless=True))
        assert owner.wait_newer(second[0], 1.0) is not None
        assert owner.status()['stalled'] is False
        assert owner.status()['error'] is None
    finally:
        source.next_frame.set()
        source.release.set()
        owner.stop(timeout=1.0)


@pytest.mark.parametrize('restart', [False, True])
def test_start_grace_before_first_frame_is_reset_on_restart(monkeypatch, restart):
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    source = BlockingSource()
    owner = CameraOwner(lambda: FakeSource([1]) if restart else source)
    if restart:
        owner.start()
        _wait_stopped(owner)
        now[0] = 200.0
        owner.restart(lambda: source)
    else:
        owner.start()
    try:
        assert source.reading.wait(1.0)
        started = now[0]
        now[0] = started + 2.01
        assert owner.status()['stalled'] is False
        now[0] = started + 4.99
        assert owner.status()['stalled'] is False
        now[0] = started + 5.01
        assert owner.status()['stalled'] is True
        assert 'Streamstillstand' in owner.status()['error']
    finally:
        source.release.set()
        owner.stop(timeout=1.0)


def test_late_frame_cannot_hide_unpolled_stall(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    source = BlockingSource()
    owner = CameraOwner(lambda: source)
    owner.start()
    try:
        assert source.reading.wait(1.0)
        now[0] = 105.01
        source.release.set()
        _wait_stopped(owner)
        assert owner.latest() is None
        assert owner.status()['stalled'] is True
    finally:
        source.release.set()
        owner.stop(timeout=1.0)


def test_first_delivery_after_two_seconds_is_accepted_then_uses_stall_timeout(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])

    class SlowStartSource(BlockingSource):
        def frames(self):
            self.reading.set()
            if self.release.wait(5.0):
                yield _frame(1, 33_333_333)
                blocked.set()
                finish.wait(5.0)

    blocked, finish = threading.Event(), threading.Event()
    source = SlowStartSource()
    owner = CameraOwner(lambda: source)
    owner.start()
    try:
        assert source.reading.wait(1.0)
        now[0] = 104.9
        source.release.set()
        assert blocked.wait(1.0)
        assert owner.wait_newer(0, 1.0) is not None
        now[0] = 106.89
        assert owner.status()['stalled'] is False
        now[0] = 106.91
        assert owner.status()['stalled'] is True
    finally:
        source.release.set()
        finish.set()
        owner.stop(timeout=1.0)


@pytest.mark.parametrize("action", ["stop", "restart"])
def test_blocked_reader_refuses_restart_and_keeps_single_source(action):
    source = BlockingSource()
    opened = []

    def factory():
        opened.append(source)
        return source

    owner = CameraOwner(factory)
    owner.start()
    assert source.reading.wait(1.0)
    try:
        if action == "stop":
            assert owner.stop(timeout=0.01) is False
            assert owner.status()["running"] is False
            with pytest.raises(RuntimeError, match="Lesethread.*nicht beendet"):
                owner.start()
            with pytest.raises(RuntimeError, match="Lesethread.*nicht beendet"):
                owner.restart()
        else:
            with pytest.raises(RuntimeError, match="Lesethread.*nicht beendet"):
                owner.restart()
        assert len(opened) == 1
    finally:
        source.release.set()
        owner.stop(timeout=1.0)
    assert source.closed


def test_rejected_restart_before_stall_deadline_reports_blocked_reader(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])
    source = StallingSource()
    owner = CameraOwner(lambda: source)
    stop_owner = owner.stop
    # Die echte Stop-Logik bleibt erhalten, nur die Join-Frist wird verkürzt.
    monkeypatch.setattr(owner, 'stop', lambda: stop_owner(timeout=0.01))
    owner.start()
    try:
        assert owner.wait_newer(0, 1.0) is not None
        now[0] = 100.5
        with pytest.raises(RuntimeError, match='Neustart abgelehnt'):
            owner.restart()
        status = owner.status()
        assert status['running'] is False
        assert status['stalled'] is True
        assert 'Lesethread' in status['error'] and 'Kamera hängt' in status['error']
        now[0] = 120.0
        assert owner.status() == status
        assert owner.wait_newer(0, 0.1) is None
        assert not source.closed
        source.next_frame.set()
        source.release.set()
        assert stop_owner(timeout=1.0)
        assert owner.latest()[0] == 1
        assert owner.status()['error'] == status['error']
    finally:
        source.next_frame.set()
        source.release.set()
        stop_owner(timeout=1.0)


@pytest.mark.parametrize('read_error,rejected', [
    ('kein Bild innerhalb von READ_FAIL_TIMEOUT_S=2.0s', 0),
    (None, 3),
    ('read liefert False', 3),
])
def test_stall_keeps_source_diagnostics_even_when_source_finishes_later(monkeypatch, read_error, rejected):
    now = [100.0]
    monkeypatch.setattr(time, 'monotonic', lambda: now[0])

    class DiagnosedSource(BlockingSource):
        rejected_timestamps = 7

        def frames(self):
            yield _frame(1, 33_333_333)
            self.reading.set()
            if self.release.wait(5.0):
                self.read_error = read_error
                self.rejected_timestamps += rejected

    source = DiagnosedSource()
    owner = CameraOwner(lambda: source)
    owner.start()
    try:
        assert source.reading.wait(1.0)
        now[0] = 102.1
        assert owner.status()['stalled'] is True
        source.release.set()
        _wait_stopped(owner)
        error = owner.status()['error']
        assert 'Streamstillstand' in error
        if read_error:
            assert read_error in error
        if rejected:
            assert 'rejected_timestamps=3' in error
        else:
            assert 'rejected_timestamps' not in error
        with pytest.raises(RuntimeError, match='Erneutes Öffnen fehlgeschlagen'):
            owner.restart(lambda: FakeSource([], fail_open='Erneutes Öffnen fehlgeschlagen'))
        # Auch ein fehlgeschlagener Verbindungsversuch darf die genauere
        # Stillstandsursache erst nach einem erfolgreichen Start löschen.
        assert error in owner.status()['error']
        assert 'Erneutes Öffnen fehlgeschlagen' in owner.status()['error']
    finally:
        source.release.set()
        owner.stop(timeout=1.0)


def test_new_generation_stays_running_after_blocked_generation_ends():
    old = BlockingSource()
    new = FakeSource([10], endless=True)
    owner = CameraOwner(lambda: old)
    owner.start()
    assert old.reading.wait(1.0)
    try:
        assert owner.stop(timeout=0.01) is False
        old.release.set()
        assert owner.stop(timeout=1.0) is True
        owner.restart(lambda: new)
        assert owner.wait_newer(0, 1.0)[0] == 1
        assert owner.wait_newer(owner.latest()[0], 1.0) is not None
        assert old.closed
        assert owner.status()["running"] is True
        assert owner.status()["error"] is None
        assert owner.status()["frames"] >= 2
    finally:
        old.release.set()
        owner.stop(timeout=1.0)


def test_concurrent_starts_open_one_source_without_blocking_waiters():
    opening = threading.Event()
    release_open = threading.Event()
    second_open = threading.Event()
    second_started = threading.Event()
    sources = []
    errors = []

    class SlowOpen(FakeSource):
        def open(self):
            opening.set()
            if not release_open.wait(2.0):
                raise RuntimeError("Test-Oeffnen nicht freigegeben")

    def factory():
        if sources:
            second_open.set()
        source = SlowOpen([1], endless=True)
        sources.append(source)
        return source

    owner = CameraOwner(factory)

    def start(second=False):
        if second:
            second_started.set()
        try:
            owner.start()
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=start)
    second = threading.Thread(target=start, args=(True,))
    first.start()
    try:
        assert opening.wait(1.0)
        second.start()
        assert second_started.wait(1.0)
        assert owner.wait_newer(0, 0.01) is None
        assert not second_open.wait(0.1)
    finally:
        release_open.set()
        first.join(1.0)
        if second.ident is not None:
            second.join(1.0)
        owner.stop(timeout=1.0)
        for source in sources:
            source.endless = False
    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    assert len(sources) == 1
    assert all(source.closed for source in sources)


@pytest.mark.parametrize("action", ["stop", "restart"])
def test_waiters_wake_on_lifecycle_change_and_receive_new_frames(action):
    old, new = BlockingSource(emit=False), BlockingSource()
    owner = CameraOwner(lambda: old)
    owner.start()
    assert old.reading.wait(1.0)
    results = []
    new_results = []
    resume = threading.Event()
    entered = [threading.Event(), threading.Event()]
    done = [threading.Event(), threading.Event()]

    def wait(index):
        entered[index].set()
        results.append(owner.wait_newer(0, 2.0))
        done[index].set()
        if resume.wait(2.0):
            new_results.append(owner.wait_newer(0, 1.0))

    waiters = [threading.Thread(target=wait, args=(i,)) for i in range(2)]
    for waiter in waiters:
        waiter.start()
    try:
        assert all(event.wait(1.0) for event in entered)
        assert not any(event.wait(0.01) for event in done)
        if action == "stop":
            owner.stop(timeout=0.01)
        else:
            # Quelle endet ohne Bild, damit Stop/Restart die Wartenden weckt.
            old.release.set()
            owner.restart(lambda: new)
        assert all(event.wait(0.5) for event in done)
        assert results == [None, None]
        if action == "stop":
            old.release.set()
            owner.restart(lambda: new)
        new.release.set()
        resume.set()
        for waiter in waiters:
            waiter.join(1.0)
        assert len(new_results) == 2
        assert all(result is not None and result[0] == 1 for result in new_results)
    finally:
        resume.set()
        old.release.set()
        new.release.set()
        owner.stop(timeout=1.0)
        for waiter in waiters:
            waiter.join(1.0)
    assert all(not waiter.is_alive() for waiter in waiters)
