import tempfile
from pathlib import Path

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


def _make_sysfs_video_node(v4l_root, usb_root, *, name, index, vendor, product):
    usb = usb_root / f"usb-{name}"
    iface = usb / f"usb-{name}:1.0"
    iface.mkdir(parents=True)
    (usb / "idVendor").write_text(vendor + "\n")
    (usb / "idProduct").write_text(product + "\n")
    d = v4l_root / name
    d.mkdir(parents=True)
    (d / "index").write_text(str(index) + "\n")
    (d / "device").symlink_to(iface)


#: M-1 final-review.md: `UvcSource.open()` prueft ein explizit vorgegebenes
#: `device=` jetzt gegen die sysfs-USB-ID (siehe `device_usb_id`). Damit die
#: uebrigen Tests in dieser Datei (die "/dev/video8" nur als Platzhalter
#: nutzen, nicht als echten Geraeteknoten) unveraendert funktionieren, legt
#: `make_source` einen passenden Fake-sysfs-Baum an - einmalig fuer den
#: gesamten Testlauf dieser Datei, nicht pro Test (kein echtes `/sys`).
_DEFAULT_SYSFS_ROOT = Path(tempfile.mkdtemp(prefix="uvc-sysfs-"))
_make_sysfs_video_node(
    _DEFAULT_SYSFS_ROOT, _DEFAULT_SYSFS_ROOT / "usb", name="video8", index=0, vendor="046d", product="0893"
)


class FakeCapture:
    def __init__(self, stamps_ms, size=(1920, 1080)):
        self.props = {}
        self.stamps = list(stamps_ms)
        self.size = size
        self.released = False
        self.current = 0.0
        self._opened = True

    def isOpened(self):
        return self._opened

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
                      set_controls=set_controls, get_controls=get_controls,
                      sysfs_root=_DEFAULT_SYSFS_ROOT), calls


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


def test_ruecklese_abweichung_bei_automatik_bricht_ab(tmp_path):
    """final-review.md I-2: nicht nur die vier SETTABLE_CONTROLS werden
    zurueckgelesen, auch die Automatiken (MODE_CONTROLS) und die festen Werte
    (FIXED_CONTROLS) - ein Treiber, der focus_automatic_continuous trotz
    --set-ctrl=...=0 auf 1 belaesst, muss auffliegen."""
    cap = FakeCapture([1.0])
    src, _ = make_source(cap, readback={"focus_automatic_continuous": 1})
    with pytest.raises(UvcError, match="focus_automatic_continuous.*0.*1"):
        src.open()
    assert cap.released


def test_ruecklese_abweichung_bei_zoom_bricht_ab():
    cap = FakeCapture([1.0])
    src, _ = make_source(cap, readback={"zoom_absolute": 110})
    with pytest.raises(UvcError, match="zoom_absolute.*100.*110"):
        src.open()
    assert cap.released


def test_controls_readback_enthaelt_alle_regler():
    cap = FakeCapture([1.0])
    src, _ = make_source(cap)
    src.open()
    expected_names = {n for n, _ in SETTINGS.ordered_controls()}
    assert set(src.describe()["controls_readback"]) == expected_names
    assert expected_names == {
        "focus_automatic_continuous", "auto_exposure", "white_balance_automatic",
        "power_line_frequency", "zoom_absolute", "pan_absolute", "tilt_absolute",
        "focus_absolute", "exposure_time_absolute", "white_balance_temperature", "gain",
    }


def test_nicht_oeffenbare_kamera_bricht_klar_ab():
    """M-2 final-review.md (Ledger #3): `capture.isOpened() == False` (Geraet
    belegt oder nicht da) muss klar als 'nicht zu oeffnen' gemeldet werden,
    nicht als '0x0'-Aufloesungsfehler (der auf USB2/Format hindeuten wuerde)."""
    cap = FakeCapture([1.0])
    cap._opened = False
    src, _ = make_source(cap)
    with pytest.raises(UvcError, match="nicht zu oeffnen"):
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


def test_explizites_device_gegen_abweichende_usb_id_bricht_ab(tmp_path):
    """M-1 final-review.md: `--camera-device`/`device=` wird gegen die
    sysfs-USB-ID des Knotens geprueft, nicht blind uebernommen."""
    v4l_root = tmp_path / "v4l"
    usb_root = tmp_path / "usb"
    _make_sysfs_video_node(v4l_root, usb_root, name="video8", index=0, vendor="1234", product="5678")

    cap = FakeCapture([1.0])
    src, _ = make_source(cap)
    src._sysfs_root = v4l_root
    src._device_arg = "/dev/video8"
    with pytest.raises(UvcError, match="1234:5678"):
        src.open()
    assert not cap.released  # capture wurde noch gar nicht erst erzeugt


def test_explizites_device_mit_passender_usb_id_oeffnet():
    """Der Normalfall (`make_source`s Standard-sysfs-Fixture passt bereits)
    - Gegenprobe zu obigem Abweichungstest."""
    cap = FakeCapture([1.0])
    src, _ = make_source(cap)
    src.open()
    assert src.device == "/dev/video8"


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
