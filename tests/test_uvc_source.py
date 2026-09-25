import cv2
import numpy as np
import pytest

from dispread.camera_settings import CameraSettings
from dispread.frames import uvc_source
from dispread.frames.uvc_source import UvcError, UvcSource, find_uvc_device, v4l2_get_controls
from dispread.records import TimeBaseKind

SETTINGS = CameraSettings.from_dict({
    "model": "logitech_streamcam", "usb_id": "046d:0893", "size": [1920, 1080],
    "fourcc": "YUYV", "fps": 30,
    "controls": {"focus_absolute": 48, "exposure_time_absolute": 166,
                 "white_balance_temperature": 5261, "gain": 11}})


class FakeCapture:
    def __init__(self, stamps_ms, size=(1920, 1080)):
        self.props = {}
        self.stamps = list(stamps_ms)
        self.size = size
        self.released = False
        self.current = 0.0

    def isOpened(self):
        return True

    def set(self, prop, value):
        self.props[prop] = value
        return True

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self.size[0])
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self.size[1])
        if prop == cv2.CAP_PROP_POS_MSEC:
            return self.current
        return self.props.get(prop, 0.0)

    def read(self):
        if not self.stamps:
            return False, None
        self.current = self.stamps.pop(0)
        return True, np.zeros((self.size[1], self.size[0], 3), np.uint8)

    def release(self):
        self.released = True


def make_source(cap, readback=None, calls=None):
    calls = calls if calls is not None else []

    def set_controls(dev, controls):
        calls.extend(controls)

    def get_controls(dev, names):
        values = dict(SETTINGS.ordered_controls())
        values.update(readback or {})
        return {n: values[n] for n in names}

    return UvcSource(SETTINGS, device="/dev/video8", capture_factory=lambda d: cap,
                      set_controls=set_controls, get_controls=get_controls), calls


def test_frames_tragen_v4l2_monotonic_und_rohwert():
    src, _ = make_source(FakeCapture([1000.0, 1033.3]))
    src.open()
    frames = list(src.frames())
    assert [f.capture_timestamp.base for f in frames] == [TimeBaseKind.V4L2_MONOTONIC] * 2
    assert frames[0].capture_timestamp.value_ns == 1_000_000_000
    assert [f.frame_sequence for f in frames] == [1, 2]


def test_automatiken_werden_zuerst_gesetzt():
    src, calls = make_source(FakeCapture([1.0]))
    src.open()
    assert [n for n, _ in calls[:3]] == [
        "focus_automatic_continuous", "auto_exposure", "white_balance_automatic",
    ]


def test_ruecklese_abweichung_bricht_ab_und_gibt_frei():
    cap = FakeCapture([1.0])
    src, _ = make_source(cap, readback={"focus_absolute": 60})
    with pytest.raises(UvcError, match="focus_absolute.*48.*60"):
        src.open()
    assert cap.released


def test_falsche_groesse_bricht_ab():
    cap = FakeCapture([1.0], size=(1280, 720))
    src, _ = make_source(cap)
    with pytest.raises(UvcError, match="1280x720"):
        src.open()


def test_null_und_rueckwaerts_zeitstempel_werden_verworfen_und_gezaehlt():
    src, _ = make_source(FakeCapture([0.0, 10.0, 9.0, 11.0]))
    src.open()
    frames = list(src.frames())
    assert [f.capture_timestamp.value_ns for f in frames] == [10_000_000, 11_000_000]
    assert src.describe()["rejected_timestamps"] == 2


def test_find_uvc_device_nimmt_index0_mit_passender_usb_id(tmp_path):
    usb = tmp_path / "usb" / "2-1"
    iface = usb / "2-1:1.0"
    iface.mkdir(parents=True)
    (usb / "idVendor").write_text("046d\n")
    (usb / "idProduct").write_text("0893\n")
    for name, idx in (("video8", "0"), ("video9", "1")):
        d = tmp_path / "v4l" / name
        d.mkdir(parents=True)
        (d / "index").write_text(idx + "\n")
        (d / "device").symlink_to(iface)
    assert find_uvc_device("046d:0893", sysfs_root=tmp_path / "v4l") == "/dev/video8"
    with pytest.raises(UvcError):
        find_uvc_device("1234:5678", sysfs_root=tmp_path / "v4l")


def test_get_controls_parst_menue_ausgabe():
    class R:
        returncode = 0
        stdout = "auto_exposure: 1 (Manual Mode)\ngain: 11\n"
        stderr = ""

    assert v4l2_get_controls(
        "/dev/video8", ["auto_exposure", "gain"], run=lambda *a, **k: R()
    ) == {"auto_exposure": 1, "gain": 11}


def test_frames_endet_nach_read_fail_timeout(monkeypatch):
    monkeypatch.setattr(uvc_source, "READ_FAIL_TIMEOUT_S", 0.05)
    src, _ = make_source(FakeCapture([]))
    src.open()
    frames = list(src.frames())
    assert frames == []
    assert src.describe()["read_error"] is not None
