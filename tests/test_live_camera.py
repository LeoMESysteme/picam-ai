import threading
import time

import numpy as np
import pytest

from dispread.frames import Frame
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
    assert threading.active_count() >= 1
