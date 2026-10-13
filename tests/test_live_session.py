import hashlib
import json
import threading

import cv2
import pytest
from dotmatrix_helpers import GRID, QUAD, embed, synthetic_reader

from dispread.camera_settings import CameraSettings
from dispread.detect.manual_roi import ManualRoiLocator
from dispread.frames import Frame
from dispread.live.clock import ClockLog
from dispread.live.session import CameraLost, LiveConfig, LiveSession, StartRefused
from dispread.records import TimeBaseKind, Timestamp, ValueStatus
from dispread.session_profile import SessionProfile

_CAMERA = CameraSettings(model="logitech_streamcam", usb_id="046d:0893", size=(800, 400), fourcc="YUYV", fps=30,
                         controls={"focus_absolute": 48, "exposure_time_absolute": 156,
                                   "white_balance_temperature": 4600, "gain": 10})


class FakeOwner:
    source_id = "fake"

    def __init__(self, images):
        self.items = [(i, img) for i, img in enumerate(images, start=1)]
        self.running = True

    def wait_newer(self, after, timeout):
        newer = [item for item in self.items if item[0] > after]
        if not newer:
            return None
        seq, image = newer[0]
        ts = Timestamp(value_ns=seq * 33_333_333, base=TimeBaseKind.V4L2_MONOTONIC)
        return seq, Frame(frame_sequence=seq, image=image, capture_timestamp=ts, source_id="fake")

    def status(self):
        return {"running": self.running, "error": None if self.running else "kein Bild", "frames": len(self.items),
                "gaps": 0, "source": {"device": "/dev/fake"}}


def _files(tmp_path, *, reference_ok=True):
    still = tmp_path / "still.png"
    cv2.imwrite(str(still), embed("+ 1.2345 "))
    digest = hashlib.sha256(still.read_bytes()).hexdigest() if reference_ok else "0" * 64
    profile = SessionProfile(
        schema_version=3, device_id="gsv-sensor-161a", session_id="live-test", quad=QUAD, target_size=(400, 160),
        grid=GRID, scaler_crop=None, min_source_dot_column_px=5.0, native_scale=1.0,
        min_native_dot_column_px=5.0, resolution_threshold_px=2.6, resolution_ok=True,
        confirmed_by="tester", confirmed_at_utc="2026-10-12T12:00:00+00:00", camera=_CAMERA,
        reference_frame={"path": str(still), "sha256": digest},
    )
    profile.save(tmp_path / "profile.json")
    calibration = tmp_path / "timing.json"
    calibration.write_text(json.dumps({
        "schema_version": 1, "camera_usb_id": "046d:0893", "guard_margin_ms": 325.9,
        "display_offset_ms": 89.6, "measured_at_utc": "2026-09-29T00:00:00+00:00", "sources": [],
    }))
    templates = tmp_path / "templates.json"
    templates.write_text("{}")
    return tmp_path / "profile.json", LiveConfig(templates=templates, templates_sha256="x", calibration=calibration)


def _session(tmp_path, images, *, reference_ok=True, **kw):
    profile_path, config = _files(tmp_path, reference_ok=reference_ok)
    offsets = iter(range(1000, 2000))
    return LiveSession(
        FakeOwner(images), profile_path, config, tmp_path / "run",
        reader_factory=lambda _p, _s: synthetic_reader(),
        locator_factory=lambda _ref, quad: ManualRoiLocator(tuple(tuple(p) for p in quad)),
        clock=ClockLog(measure=lambda: next(offsets), monotonic_ns=lambda: 0),
        **kw,
    )


def test_new_value_is_transition_then_valid_and_audited(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 "), embed("+ 1.2345 ")])
    session.start()
    first, second = session.step(), session.step()
    assert first.status is ValueStatus.TRANSITION and first.value is None
    assert second.status is ValueStatus.VALID and second.value == 1.2345
    assert second.capture_timestamp.base is TimeBaseKind.V4L2_MONOTONIC
    assert second.capture_timestamp.value_ns == 2 * 33_333_333
    assert second.frames_confirmed == 2
    assert second.confirmation_span_ns == 33_333_333
    summary = session.stop()
    lines = session.records_path.read_text().splitlines()
    assert len(lines) == 2 and summary["by_status"] == {"transition": 1, "valid": 1}
    assert [json.loads(line) for line in lines] == [first.to_dict(), second.to_dict()]
    data = json.loads(session.session_path.read_text())
    assert data["clock_offset_boottime_minus_monotonic_ns"]["start"] == 1000
    assert data["clock_offset_boottime_minus_monotonic_ns"]["end"] == 1001
    assert data["timing_calibration"]["applied"] is False
    assert data["timing_calibration"]["display_offset_ms"] == 89.6
    assert data["timing_calibration"]["guard_margin_ms"] == 325.9
    assert data["timing_calibration"]["sha256"] == hashlib.sha256((tmp_path / "timing.json").read_bytes()).hexdigest()
    assert data["release_notice"].startswith("Validiert nur:")


def test_unreadable_frame_is_rejected_not_guessed(tmp_path):
    blank = embed("+ 1.2345 ") * 0 + 200
    session = _session(tmp_path, [blank])
    session.start()
    record = session.step()
    assert record.status is ValueStatus.UNREADABLE and record.value is None and record.reject_reasons
    session.stop()
    assert json.loads(session.records_path.read_text()) == record.to_dict()


def test_start_refused_when_reference_still_changed(tmp_path):
    session = _session(tmp_path, [], reference_ok=False)
    with pytest.raises(StartRefused, match="Referenzbild"):
        session.start()


def test_start_refused_without_calibration(tmp_path):
    session = _session(tmp_path, [])
    (tmp_path / "timing.json").unlink()
    with pytest.raises(StartRefused, match="Timing-Kalibrierung"):
        session.start()


def test_camera_loss_ends_session_with_reason(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    session._owner.running = False
    with pytest.raises(CameraLost, match="kein Bild"):
        session.step(timeout=0.01)
    session.stop()


def test_running_camera_without_new_frame_returns_none(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    assert session.step(timeout=0.01) is None
    assert session.latest is None
    summary = session.stop()
    assert summary["frames_read"] == 0
    assert session.records_path.read_text() == ""


def test_run_records_camera_loss_and_stop_preserves_reason(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    session._owner.running = False
    session.run(threading.Event())
    assert session.end_reason == "kamera: kein Bild"
    summary = session.stop("bediener")
    assert summary["end_reason"] == "kamera: kein Bild"
    assert summary["camera_error"] == "kein Bild"
    assert json.loads(session.session_path.read_text())["summary"] == summary


def test_run_obeys_already_set_stop_event(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")])
    session.start()
    stop = threading.Event()
    stop.set()
    session.run(stop)
    assert session.latest is None
    assert session.stop()["frames_read"] == 0


def test_periodic_clock_sample_keeps_end_unset_until_stop(tmp_path):
    now = [0.0]
    session = _session(tmp_path, [embed("+ 1.2345 ")], monotonic=lambda: now[0])
    session.start()
    now[0] = 60.0
    session.step()
    data = json.loads(session.session_path.read_text())
    offsets = data["clock_offset_boottime_minus_monotonic_ns"]
    assert offsets == {"start": 1000, "end": None, "samples": [[0, 1000], [0, 1001]]}
    assert data["summary"]["frames_read"] == 1
    session.stop()
    offsets = json.loads(session.session_path.read_text())["clock_offset_boottime_minus_monotonic_ns"]
    assert offsets["end"] == 1002
    assert len(offsets["samples"]) == 3


def test_skipped_frames_are_counted_and_written_to_trace(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 4)
    session.start()
    session.step()
    session._owner.items = session._owner.items[3:]
    record = session.step()
    assert record.frame_sequence == 4
    assert record.trace.dropped_frames == 2
    assert session.latest is record
    summary = session.stop()
    assert summary["frames_read"] == 2
    assert summary["frames_skipped"] == 2


def test_start_ignores_camera_frames_from_before_start(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 ")] * 2)
    session._owner.latest = lambda: session._owner.items[0]
    session.start()
    assert session.step().frame_sequence == 2
    assert session.stop()["frames_skipped"] == 0


def test_start_refused_for_wrong_templates_checksum(tmp_path):
    profile_path, config = _files(tmp_path)
    session = LiveSession(FakeOwner([]), profile_path, config, tmp_path / "run")
    with pytest.raises(StartRefused, match="Vorlagen"):
        session.start()
    assert not session.session_path.exists()
    assert not session.records_path.exists()


def test_start_refused_for_calibration_of_another_camera(tmp_path):
    session = _session(tmp_path, [])
    calibration = tmp_path / "timing.json"
    data = json.loads(calibration.read_text())
    data["camera_usb_id"] = "wrong-camera"
    calibration.write_text(json.dumps(data))
    with pytest.raises(StartRefused, match="Timing-Kalibrierung gilt fuer"):
        session.start()
    assert not session.session_path.exists()
