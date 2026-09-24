import pytest

from dispread.validate import GateConfig, default_gate_config


def test_sevenseg_unchanged():
    assert default_gate_config("sevenseg") == GateConfig()
    assert default_gate_config("sevenseg", confirm_frames=3).confirm_frames == 3


def test_dotmatrix_relies_on_reader_thresholds():
    cfg = default_gate_config("dotmatrix", expected_unit="mV/V")
    assert cfg.min_margin == 0.0 and cfg.min_contrast == 0.0
    assert cfg.expected_unit == "mV/V"


def test_unknown_backend():
    with pytest.raises(ValueError):
        default_gate_config("foo")
