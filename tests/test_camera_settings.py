import json

import pytest

from dispread.camera_settings import CameraSettings, load_camera_settings

GOOD = {
    "model": "logitech_streamcam", "usb_id": "046d:0893", "size": [1920, 1080],
    "fourcc": "YUYV", "fps": 30,
    "controls": {"focus_absolute": 48, "exposure_time_absolute": 166,
                 "white_balance_temperature": 5261, "gain": 11},
}


def test_roundtrip():
    s = CameraSettings.from_dict(GOOD)
    assert CameraSettings.from_dict(s.to_dict()) == s
    assert s.size == (1920, 1080)


def test_reihenfolge_automatiken_zuerst():
    names = [n for n, _ in CameraSettings.from_dict(GOOD).ordered_controls()]
    assert names[:3] == ["focus_automatic_continuous", "auto_exposure", "white_balance_automatic"]
    assert names.index("focus_absolute") > names.index("focus_automatic_continuous")
    assert ("zoom_absolute", 100) in CameraSettings.from_dict(GOOD).ordered_controls()


@pytest.mark.parametrize("mutate", [
    lambda d: d["controls"].pop("gain"),
    lambda d: d["controls"].update(zoom_absolute=200),
    lambda d: d["controls"].update(gain="11"),
    lambda d: d.pop("usb_id"),
])
def test_ungueltig_wird_abgelehnt(mutate):
    d = json.loads(json.dumps(GOOD))
    mutate(d)
    with pytest.raises(ValueError):
        CameraSettings.from_dict(d)


def test_load_braucht_camera_block(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps({"camera": GOOD}))
    assert load_camera_settings(p).usb_id == "046d:0893"
    p.write_text(json.dumps(GOOD))
    with pytest.raises(ValueError, match="camera"):
        load_camera_settings(p)
