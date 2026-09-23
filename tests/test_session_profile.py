import json

import pytest

from dispread.charcells import CharGrid
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile


def _profile():
    return SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION, device_id="gsv2as-01", session_id="s1",
        quad=[[1, 2], [3, 4], [5, 6], [7, 8]], target_size=(400, 160),
        grid=CharGrid(n_cells=16, left=2.0, pitch=24.0, top=8.0, bottom=150.0),
        scaler_crop=None, min_source_dot_column_px=2.2, native_scale=1.0,
        min_native_dot_column_px=2.2, resolution_threshold_px=2.0,
        resolution_ok=True, confirmed_by="bediener", confirmed_at_utc="2026-09-23T12:00:00+00:00")


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "profile.json"
    _profile().save(p)
    assert SessionProfile.load(p) == _profile()


def test_load_rejects_unknown_schema(tmp_path):
    p = tmp_path / "profile.json"
    _profile().save(p)
    d = json.loads(p.read_text())
    d["schema_version"] = 99
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        SessionProfile.load(p)


def test_load_rejects_schema_version_1(tmp_path):
    """Bug 2: Version 1 kannte noch kein native_scale-Gate - kein
    stillschweigendes Weiterlaufen, klare Meldung statt KeyError. Ein
    echtes Version-1-Dokument haette 'native_scale'/'min_native_dot_column_px'
    gar nicht erst als Feld, aber schon der Versionsabgleich muss abbrechen,
    bevor ueberhaupt nach diesen Feldern gesucht wird."""
    p = tmp_path / "profile.json"
    d = _profile().to_dict()
    del d["native_scale"]
    del d["min_native_dot_column_px"]
    d["schema_version"] = 1
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="schema_version"):
        SessionProfile.load(p)


def test_schema_version_2_requires_native_scale_fields(tmp_path):
    p = tmp_path / "profile.json"
    d = _profile().to_dict()
    del d["native_scale"]
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="native_scale"):
        SessionProfile.load(p)
