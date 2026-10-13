from datetime import UTC, datetime

import numpy as np
import pytest

from dispread.camera_settings import CameraSettings
from dispread.live import setup as live_setup


class FakeSetupCamera:
    device = "/dev/fake"

    def __init__(self, image):
        self.image = image
        self.controls = []

    def set_controls(self, controls):
        self.controls.append(list(controls))

    def get_controls(self, names):
        values = {"exposure_time_absolute": 156, "white_balance_temperature": 4600, "gain": 10}
        return {n: values[n] for n in names}

    def fresh_still(self, discard=10):
        return self.image


def test_focus_camera_turns_autofocus_off_first_and_reads_back(monkeypatch):
    monkeypatch.setattr(live_setup, "sweep_focus", lambda measure: (48, [(48, measure(48))]))
    cam = FakeSetupCamera(np.full((1080, 1920, 3), 128, np.uint8))
    settings, sweep = live_setup.focus_camera(cam, None, settle_s=0, sleep=lambda _s: None)
    assert cam.controls[0] == [("focus_automatic_continuous", 0)]
    assert cam.controls[1] == [("focus_absolute", 48)]
    assert cam.controls[2] == [("auto_exposure", 3), ("white_balance_automatic", 1)]
    assert settings.controls == {
        "focus_absolute": 48, "exposure_time_absolute": 156, "white_balance_temperature": 4600, "gain": 10,
    }
    assert settings.device == "/dev/fake" and sweep[0][0] == 48


def test_offline_text_source_returns_capture_and_text():
    image = np.zeros((2, 2, 3), np.uint8)
    assert live_setup.offline_text_source("ABC")(lambda: image) == (image, "ABC")


def test_mask_changed_cells_rejects_length_mismatch():
    with pytest.raises(live_setup.SetupError, match="Laenge"):
        live_setup.mask_changed_cells("ab", "abc")


def test_assist_rejects_short_stability(tmp_path):
    cam = FakeSetupCamera(np.zeros((1080, 1920, 3), np.uint8))
    with pytest.raises(live_setup.SetupError, match="30"):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("x"), expected_size=(1920, 1080),
            out_dir=tmp_path, stability_s=5.0,
        )


def test_assist_rejects_wrong_still_size(tmp_path):
    cam = FakeSetupCamera(np.zeros((720, 1280, 3), np.uint8))
    with pytest.raises(live_setup.SetupError, match="Kameraaufloesung"):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("x"), expected_size=(1920, 1080), out_dir=tmp_path,
        )


_CAMERA = CameraSettings(model="logitech_streamcam", usb_id="046d:0893", size=(1920, 1080), fourcc="YUYV",
                         fps=30, controls={"focus_absolute": 48, "exposure_time_absolute": 156,
                                           "white_balance_temperature": 4600, "gain": 10})


def _proposal(tmp_path, overall="OK", raster="OK"):
    frame = tmp_path / "still.png"
    frame.write_bytes(b"png")
    return {
        "frame": str(frame), "device_id": "gsv-sensor-161a", "session_id": "live-test",
        "quad": [[0, 0], [400, 0], [400, 160], [0, 160]], "target_size": [400, 160],
        "grid": live_setup.LATTICE_GRID.to_dict(), "grid_source": "dot_lattice", "scaler_crop": None,
        "min_source_dot_column_px": 5.0, "native_scale": 1.0, "min_native_dot_column_px": 5.0,
        "camera": _CAMERA.to_dict(),
        "setup_checks": {"overall": overall, "checks": {"rasterversatz": {"status": raster}}},
    }


def test_confirm_builds_confirmed_profile(tmp_path):
    timestamp = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    profile = live_setup.confirm_proposal(_proposal(tmp_path), confirmed_by="Leonhard Hentschke",
                                          resolution_threshold_px=2.6, now=lambda: timestamp)
    assert profile.confirmed_by == "Leonhard Hentschke" and profile.resolution_ok
    assert profile.camera == _CAMERA and profile.reference_frame["path"].endswith("still.png")
    assert profile.confirmed_at_utc == timestamp.isoformat()


def test_confirm_refuses_fehler_without_override(tmp_path):
    with pytest.raises(live_setup.SetupError, match="FEHLER"):
        live_setup.confirm_proposal(_proposal(tmp_path, overall="FEHLER"), confirmed_by="x",
                                    resolution_threshold_px=2.6)


def test_confirm_refuses_empty_name(tmp_path):
    with pytest.raises(live_setup.SetupError, match="Name"):
        live_setup.confirm_proposal(_proposal(tmp_path), confirmed_by="  ", resolution_threshold_px=2.6)
