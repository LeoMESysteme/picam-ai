"""Offline-Nachweis darf fehlende Eingaben nicht als Erfolg melden."""

import importlib.util
import sys
from pathlib import Path


def test_missing_requested_setup_returns_failure(tmp_path, monkeypatch):
    script = Path(__file__).parents[1] / 'scripts/r13-stability-eval.py'
    spec = importlib.util.spec_from_file_location('r25_eval', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, 'argv', [str(script), '--live-root', str(tmp_path),
                                    '--run', 'missing', '--output', str(tmp_path / 'out')])
    assert module.main() != 0
    assert (tmp_path / 'out/summary.json').is_file()


def test_calibration_counts_live_usable_share_separately_from_probe():
    import numpy as np

    script = Path(__file__).parents[1] / 'scripts/r13-stability-eval.py'
    spec = importlib.util.spec_from_file_location('r25_eval_calibration', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # First eight predicted stable; later one of four is below the runtime threshold.
    peaks = np.array([[0.9, 0.9]]*8 + [[0.8, 0.7], [0.8, 0.8], [0.8, 0.9], [0.7, 0.9]])
    usable = np.ones(peaks.shape, dtype=bool)
    usable[-2, 1] = False  # Ambiguous despite a high peak.
    result = module.calibration_stats(peaks, usable, probe_count=8, min_peak=0.75)
    assert result['holdout_usable_share'] == [0.75, 0.5]
    assert result['all_usable_share'] == [11/12, 10/12]
    assert result['holdout_frames'] == 4


def test_probe_translation_preserves_raw_pixel_values():
    import numpy as np

    script = Path(__file__).parents[1] / 'scripts/r13-stability-eval.py'
    spec = importlib.util.spec_from_file_location('r25_eval_pixels', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = np.arange(60, dtype=np.uint8).reshape(6, 10)
    shifted = module.integer_align(raw, (2, -1))
    np.testing.assert_array_equal(shifted[1:, :-2], raw[:-1, 2:])
    assert set(np.unique(shifted)) <= set(np.unique(raw)) | {0}


def test_missing_shifted_window_is_not_counted_as_usable():
    import numpy as np

    from dispread.live.frame_tracking import FrameTrackingConfig

    script = Path(__file__).parents[1] / 'scripts/r13-stability-eval.py'
    spec = importlib.util.spec_from_file_location('r25_eval_window', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gray = np.random.default_rng(13).integers(0, 255, (80, 80), dtype=np.uint8)
    patch = gray[33:48, 33:48]
    assert module.region_match(gray, (40, 40), patch, FrameTrackingConfig())[1]
    assert module.region_match(gray, (1000, 40), patch, FrameTrackingConfig()) == (0.0, False)
