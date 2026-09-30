"""`scripts/profile-regrid.py still`: Rasterversatz auf Standbildern vor der
Ernte messen und korrigieren (synthetisch, ohne Kamera)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from test_lattice_offsets import GRID, SIZE, TRUE_QUAD, _source_image

SCRIPT = Path(__file__).parents[1] / "scripts" / "profile-regrid.py"
_spec = importlib.util.spec_from_file_location("profile_regrid", SCRIPT)
profile_regrid = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = profile_regrid
_spec.loader.exec_module(profile_regrid)


def _setup(tmp_path: Path, quad) -> tuple[Path, Path]:
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(6):
        cv2.imwrite(str(frames / f"frame_{i:06d}.png"), _source_image("+0.46781 "))
    proposal = tmp_path / "proposal.json"
    proposal.write_text(
        json.dumps({"quad": np.asarray(quad).tolist(), "grid": GRID.to_dict(), "target_size": list(SIZE)})
    )
    return frames, proposal


def test_still_text_marks_changing_cells_as_skipped():
    assert profile_regrid._still_text("+0.4678? ") == "+0.4678  "
    assert profile_regrid._still_text("+1.2") == "+1.2     "


def test_still_measure_true_quad_ok(tmp_path):
    frames, proposal = _setup(tmp_path, TRUE_QUAD)
    rc = profile_regrid.main(["still", "--quad-from", str(proposal), "--frames", str(frames), "--text", "+0.4678? "])
    assert rc == 0


def test_still_sheared_quad_fails_and_is_corrected(tmp_path, capsys):
    wrong = TRUE_QUAD.copy()
    wrong[3, 0] -= 8.0
    frames, proposal = _setup(tmp_path, wrong)
    base = ["still", "--quad-from", str(proposal), "--frames", str(frames), "--text", "+0.4678? "]
    assert profile_regrid.main(base) == 3
    out_quad = tmp_path / "quad.json"
    assert profile_regrid.main([*base, "--out-quad", str(out_quad)]) == 0
    refined = np.asarray(json.loads(out_quad.read_text()))
    assert np.abs(refined - TRUE_QUAD).max() < 1.5
    assert '--quad "' in capsys.readouterr().out
