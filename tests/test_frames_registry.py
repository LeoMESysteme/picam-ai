import pytest

from dispread.frames import known_schemes, open_source


def test_known_schemes_hat_v4l2_nicht_picamera2_oder_imx500():
    schemes = known_schemes()
    assert "v4l2" in schemes
    assert "picamera2" not in schemes
    assert "imx500" not in schemes


def test_picamera2_ist_ausser_betrieb():
    with pytest.raises(ValueError, match="IMX500 ausser Betrieb seit 2026-09-25"):
        open_source("picamera2://?size=2028x1520")
    with pytest.raises(ValueError, match="docs/project_history.md"):
        open_source("picamera2://?size=2028x1520")


def test_imx500_ist_ausser_betrieb():
    with pytest.raises(ValueError, match="IMX500 ausser Betrieb seit 2026-09-25"):
        open_source("imx500://?rpk=x")
    with pytest.raises(ValueError, match="docs/project_history.md"):
        open_source("imx500://?rpk=x")


def test_v4l2_braucht_settings():
    with pytest.raises(ValueError, match="settings"):
        open_source("v4l2:///dev/video8")
