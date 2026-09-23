"""`scripts/harvest.py` - Faktorplan und Ernte-Lauf (Ernte Phase 1, Task 4).

Deckt `plan_factors`, `build_schedule` und `run` ab. `run` orchestriert
`sync-record.py` und `gate-label.py` als Subprozesse - hier immer mit
gepatchtem `subprocess.run`, es wird nie eine echte Kamera oder ein
serieller Port angefasst.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from dispread.charcells import CharGrid
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile

SCRIPT = Path(__file__).parents[1] / "scripts" / "harvest.py"


def _load_harvest_module():
    spec = importlib.util.spec_from_file_location("_harvest_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


harvest = _load_harvest_module()


def _profile(*, resolution_ok=True, scaler_crop=(1000, 800, 1600, 1200)):
    return SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        device_id="gsv2as-01",
        session_id="s1",
        quad=[[1, 2], [3, 4], [5, 6], [7, 8]],
        target_size=(400, 160),
        grid=CharGrid(n_cells=16, left=2.0, pitch=24.0, top=8.0, bottom=150.0),
        scaler_crop=scaler_crop,
        min_source_dot_column_px=2.2,
        resolution_threshold_px=2.0,
        resolution_ok=resolution_ok,
        confirmed_by="bediener",
        confirmed_at_utc="2026-09-23T12:00:00+00:00",
    )


# --- plan_factors ---------------------------------------------------------


def test_plan_factors_deterministic():
    a = harvest.plan_factors(10, seed=42)
    b = harvest.plan_factors(10, seed=42)
    assert a == b


def test_plan_factors_different_seed_differs():
    a = harvest.plan_factors(10, seed=1)
    b = harvest.plan_factors(10, seed=2)
    assert a != b


def test_plan_factors_length_and_range():
    factors = harvest.plan_factors(20, seed=7, lo=0.5, hi=9000.0)
    assert len(factors) == 20
    for f in factors:
        assert 0.5 <= f <= 9000.0
        assert 0.15 <= f <= 1_580_000.0


def test_plan_factors_min_step_ratio():
    factors = harvest.plan_factors(30, seed=99)
    for prev, cur in zip(factors[:-1], factors[1:], strict=True):
        ratio = max(prev, cur) / min(prev, cur)
        assert ratio >= 1.3 - 1e-9


# --- build_schedule ---------------------------------------------------------


def test_build_schedule_format():
    schedule = harvest.build_schedule([1.0, 2.5, 9000.0], hold_s=4.0)
    assert schedule == "1:4,2.5:4,9000:4"


def test_build_schedule_parses_back(tmp_path):
    """Der erzeugte String muss sich mit sync-record.py's eigenem Parser lesen lassen."""
    sync_record_spec = importlib.util.spec_from_file_location(
        "_sync_record_for_harvest_test", Path(__file__).parents[1] / "scripts" / "sync-record.py"
    )
    sync_record = importlib.util.module_from_spec(sync_record_spec)
    sync_record_spec.loader.exec_module(sync_record)

    factors = harvest.plan_factors(5, seed=3)
    schedule = harvest.build_schedule(factors, hold_s=4.0)
    parsed = sync_record._parse_norm_schedule(schedule)
    assert [f for f, _hold in parsed] == pytest.approx(factors, rel=1e-9)
    assert all(hold == 4.0 for _f, hold in parsed)


# --- run ---------------------------------------------------------------


def _ok_result(returncode=0, stdout="", stderr=""):
    class _R:
        pass

    r = _R()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_run_rejects_resolution_not_ok(tmp_path):
    profile_path = tmp_path / "profile.json"
    _profile(resolution_ok=False).save(profile_path)
    with patch.object(harvest.subprocess, "run") as mock_run:
        with pytest.raises(harvest.HarvestError):
            harvest.run(
                profile_path=profile_path,
                out_dir=tmp_path / "out",
                n_steps=3,
                hold_s=4.0,
                seed=1,
                port="/dev/ttyUSB0",
            )
        mock_run.assert_not_called()


def test_run_rejects_too_short_hold(tmp_path):
    profile_path = tmp_path / "profile.json"
    _profile().save(profile_path)
    with patch.object(harvest.subprocess, "run") as mock_run:
        with pytest.raises(harvest.HarvestError):
            harvest.run(
                profile_path=profile_path,
                out_dir=tmp_path / "out",
                n_steps=3,
                hold_s=1.0,  # < 2*695/1000 + 1.0 = 2.39
                seed=1,
                port="/dev/ttyUSB0",
                guard_margin_ms=695,
            )
        mock_run.assert_not_called()


def test_run_sets_exact_subprocess_arguments_with_scaler_crop(tmp_path):
    profile_path = tmp_path / "profile.json"
    _profile(scaler_crop=(1000, 800, 1600, 1200)).save(profile_path)
    out_dir = tmp_path / "out"

    def _fake_run(cmd, **kwargs):
        if "sync-record.py" in cmd[1]:
            (out_dir / "recording").mkdir(parents=True, exist_ok=True)
            return _ok_result(0)
        if "gate-label.py" in cmd[1]:
            proposal = {
                "recording": str(out_dir / "recording"),
                "guard_margin_ms": 695.0,
                "max_gap_ms": 800.0,
                "min_gap_ms": 300.0,
                "burst_spans": [],
                "images": [
                    {"image_path": "a.jpg", "telegram_text": "1.0", "label_text": "1.0"},
                    {"image_path": "b.jpg", "telegram_text": "2.0", "label_text": "2.0"},
                ],
                "summary": {
                    "frames_total": 2,
                    "labeled": 2,
                    "rejected_total": 0,
                    "rejected_by_reason": {
                        "wertwechsel_im_fenster": 0,
                        "ausserhalb_telegrammbereich": 0,
                        "letzter_lauf_ohne_folgetelegramm": 0,
                        "telegrammluecke": 0,
                        "telegrammburst": 0,
                        "keine_telegramme": 0,
                    },
                    "distinct_label_texts": 2,
                },
            }
            (out_dir / "proposal.json").write_text(json.dumps(proposal))
            return _ok_result(0)
        raise AssertionError(f"unerwarteter Aufruf: {cmd}")

    with patch.object(harvest.subprocess, "run", side_effect=_fake_run) as mock_run:
        result = harvest.run(
            profile_path=profile_path,
            out_dir=out_dir,
            n_steps=3,
            hold_s=4.0,
            seed=1,
            port="/dev/ttyUSB0",
        )

    assert mock_run.call_count == 2
    sync_cmd = mock_run.call_args_list[0].args[0]
    assert sync_cmd[0] == sys.executable
    assert sync_cmd[1].endswith("sync-record.py")
    assert "--source" in sync_cmd and sync_cmd[sync_cmd.index("--source") + 1] == "camera"
    assert "--frame-rate" in sync_cmd and sync_cmd[sync_cmd.index("--frame-rate") + 1] == "15"
    assert "--image-format" in sync_cmd and sync_cmd[sync_cmd.index("--image-format") + 1] == "jpg"
    assert "--norm-schedule" in sync_cmd
    assert "--duration" in sync_cmd
    assert "--output" in sync_cmd and sync_cmd[sync_cmd.index("--output") + 1] == str(out_dir / "recording")
    assert "--port" in sync_cmd and sync_cmd[sync_cmd.index("--port") + 1] == "/dev/ttyUSB0"
    assert "--scaler-crop" in sync_cmd
    assert sync_cmd[sync_cmd.index("--scaler-crop") + 1] == "1000,800,1600,1200"

    gate_cmd = mock_run.call_args_list[1].args[0]
    assert gate_cmd[0] == sys.executable
    assert gate_cmd[1].endswith("gate-label.py")
    assert "--recording" in gate_cmd and gate_cmd[gate_cmd.index("--recording") + 1] == str(out_dir / "recording")
    assert "--guard-margin-ms" in gate_cmd and gate_cmd[gate_cmd.index("--guard-margin-ms") + 1] == "695"
    assert "--min-gap-ms" in gate_cmd and gate_cmd[gate_cmd.index("--min-gap-ms") + 1] == "300"
    assert "--max-gap-ms" in gate_cmd and gate_cmd[gate_cmd.index("--max-gap-ms") + 1] == "800"
    assert "--output" in gate_cmd and gate_cmd[gate_cmd.index("--output") + 1] == str(out_dir / "proposal.json")

    harvest_json = json.loads((out_dir / "harvest.json").read_text())
    assert harvest_json["gap_thresholds_provisional"] is True
    assert harvest_json["seed"] == 1
    assert len(harvest_json["factors"]) == 3
    assert harvest_json["sync_record_exit_code"] == 0
    assert harvest_json["gate_label_exit_code"] == 0
    assert harvest_json["summary"] == {
        "frames_total": 2,
        "labeled": 2,
        "rejected_total": 0,
        "rejected_by_reason": {
            "wertwechsel_im_fenster": 0,
            "ausserhalb_telegrammbereich": 0,
            "letzter_lauf_ohne_folgetelegramm": 0,
            "telegrammluecke": 0,
            "telegrammburst": 0,
            "keine_telegramme": 0,
        },
        "distinct_label_texts": 2,
    }
    assert result == harvest_json


def test_run_omits_scaler_crop_without_profile_value(tmp_path):
    profile_path = tmp_path / "profile.json"
    _profile(scaler_crop=None).save(profile_path)
    out_dir = tmp_path / "out"

    def _fake_run(cmd, **kwargs):
        if "sync-record.py" in cmd[1]:
            (out_dir / "recording").mkdir(parents=True, exist_ok=True)
            return _ok_result(0)
        (out_dir / "proposal.json").write_text(json.dumps({"images": []}))
        return _ok_result(0)

    with patch.object(harvest.subprocess, "run", side_effect=_fake_run) as mock_run:
        harvest.run(
            profile_path=profile_path,
            out_dir=out_dir,
            n_steps=2,
            hold_s=4.0,
            seed=1,
            port="/dev/ttyUSB0",
        )
    sync_cmd = mock_run.call_args_list[0].args[0]
    assert "--scaler-crop" not in sync_cmd


def test_run_aborts_when_sync_record_fails(tmp_path):
    profile_path = tmp_path / "profile.json"
    _profile().save(profile_path)
    out_dir = tmp_path / "out"

    def _fake_run(cmd, **kwargs):
        return _ok_result(returncode=2, stderr="boom")

    with patch.object(harvest.subprocess, "run", side_effect=_fake_run) as mock_run:
        with pytest.raises(harvest.HarvestError):
            harvest.run(
                profile_path=profile_path,
                out_dir=out_dir,
                n_steps=2,
                hold_s=4.0,
                seed=1,
                port="/dev/ttyUSB0",
            )
    assert mock_run.call_count == 1  # gate-label wird nicht mehr aufgerufen
    assert not (out_dir / "harvest.json").exists()


def test_run_aborts_when_gate_label_fails(tmp_path):
    profile_path = tmp_path / "profile.json"
    _profile().save(profile_path)
    out_dir = tmp_path / "out"

    def _fake_run(cmd, **kwargs):
        if "sync-record.py" in cmd[1]:
            (out_dir / "recording").mkdir(parents=True, exist_ok=True)
            return _ok_result(0)
        return _ok_result(returncode=1, stderr="gate boom")

    with patch.object(harvest.subprocess, "run", side_effect=_fake_run) as mock_run:
        with pytest.raises(harvest.HarvestError):
            harvest.run(
                profile_path=profile_path,
                out_dir=out_dir,
                n_steps=2,
                hold_s=4.0,
                seed=1,
                port="/dev/ttyUSB0",
            )
    assert mock_run.call_count == 2
    assert not (out_dir / "harvest.json").exists()
