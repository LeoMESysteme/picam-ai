import dataclasses
import json
from pathlib import Path

import pytest

from dispread.camera_settings import CameraSettings
from dispread.charcells import CharGrid
from dispread.layout import CharLayout
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile

_CAMERA = CameraSettings(
    model="logitech_streamcam", usb_id="046d:0893", size=(1920, 1080),
    fourcc="YUYV", fps=30,
    controls={"focus_absolute": 48, "exposure_time_absolute": 166,
              "white_balance_temperature": 5261, "gain": 11},
)


def _profile_v2():
    """Wie vor dem StreamCam-Umstieg: `schema_version=2`, `camera=None`."""
    return SessionProfile(
        schema_version=2, device_id="gsv2as-01", session_id="s1",
        quad=[[1, 2], [3, 4], [5, 6], [7, 8]], target_size=(400, 160),
        grid=CharGrid(n_cells=16, left=2.0, pitch=24.0, top=8.0, bottom=150.0),
        scaler_crop=None, min_source_dot_column_px=2.2, native_scale=1.0,
        min_native_dot_column_px=2.2, resolution_threshold_px=2.0,
        resolution_ok=True, confirmed_by="bediener", confirmed_at_utc="2026-09-23T12:00:00+00:00")


def _profile():
    """Aktuelles Profil v3 mit `camera`."""
    return dataclasses.replace(_profile_v2(), schema_version=PROFILE_SCHEMA_VERSION, camera=_CAMERA)


def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "profile.json"
    _profile().save(p)
    assert SessionProfile.load(p) == _profile()


def test_v2_profile_still_loads_with_camera_none(tmp_path):
    """Echte v2-Profile (import-harvest, dataset loader, training) bleiben
    ohne Migration ladbar - `camera` ist dann `None`."""
    p = tmp_path / "profile.json"
    _profile_v2().save(p)
    loaded = SessionProfile.load(p)
    assert loaded.camera is None
    assert loaded == _profile_v2()


def test_v2_to_dict_has_no_camera_key():
    """Re-Speichern/Hashen eines v2-Profils darf sich nicht aendern - kein
    'camera'-Schluessel, wenn `camera is None`."""
    d = _profile_v2().to_dict()
    assert "camera" not in d


def test_v3_to_dict_has_camera_key():
    d = _profile().to_dict()
    assert d["camera"] == _CAMERA.to_dict()


# --- reference_frame (Task 10, Ausrichtungspruefung) -----------------------

_REFERENCE_FRAME = {"path": "var/diagnostics/sc2-still/frames/frame_000014.png", "sha256": "a" * 64}


def test_reference_frame_roundtrip(tmp_path):
    p = tmp_path / "profile.json"
    profile = dataclasses.replace(_profile(), reference_frame=_REFERENCE_FRAME)
    profile.save(p)
    loaded = SessionProfile.load(p)
    assert loaded.reference_frame == _REFERENCE_FRAME
    assert loaded == profile


def test_reference_frame_defaults_to_none():
    assert _profile().reference_frame is None


def test_to_dict_has_no_reference_frame_key_when_none():
    d = _profile().to_dict()
    assert "reference_frame" not in d


def test_to_dict_has_reference_frame_key_when_set():
    profile = dataclasses.replace(_profile(), reference_frame=_REFERENCE_FRAME)
    d = profile.to_dict()
    assert d["reference_frame"] == _REFERENCE_FRAME


def test_setup_checks_roundtrip(tmp_path):
    checks = {
        "overall": "FEHLER",
        "checks": {
            "reflection": {"status": "FEHLER", "metrics": {"contrast": 8.3}, "cells": [8]},
        },
        "override_reason": "Aufstellung wurde separat geprueft",
    }
    profile = dataclasses.replace(_profile(), setup_checks=checks)
    path = tmp_path / "profile.json"
    profile.save(path)
    assert SessionProfile.load(path).setup_checks == checks
    assert json.loads(path.read_text())["setup_checks"] == checks


_DIAGNOSTICS = Path(__file__).parents[1] / "var/diagnostics"
_EXISTING_PROFILES = sorted(
    path for path in [*_DIAGNOSTICS.glob("*-profile"), *_DIAGNOSTICS.glob("*-profile/profile.json"),
                      *_DIAGNOSTICS.glob("*-profile-regrid1.json")]
    if path.is_file()
)


@pytest.mark.parametrize("source", _EXISTING_PROFILES, ids=lambda path: str(path.relative_to(_DIAGNOSTICS)))
def test_existing_profile_resaves_byte_identically(tmp_path, source):
    profile = SessionProfile.load(source)
    original = json.loads(source.read_text())
    assert (profile.setup_checks is not None) == ("setup_checks" in original)
    target = tmp_path / "profile.json"
    profile.save(target)
    assert target.read_bytes() == source.read_bytes()


def test_v2_profile_without_reference_frame_still_loads(tmp_path):
    """v2-Profile kennen das Feld nicht - muss weiterhin ohne Migration
    ladbar bleiben, `reference_frame` dann `None` (wie `camera` bei v2)."""
    p = tmp_path / "profile.json"
    _profile_v2().save(p)
    loaded = SessionProfile.load(p)
    assert loaded.reference_frame is None


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
    d = _profile_v2().to_dict()
    del d["native_scale"]
    del d["min_native_dot_column_px"]
    d["schema_version"] = 1
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="schema_version"):
        SessionProfile.load(p)


def test_load_rejects_schema_version_4(tmp_path):
    """Noch unbekannte, zukuenftige Version - genauso ein harter Abbruch wie
    eine zu alte."""
    p = tmp_path / "profile.json"
    d = _profile().to_dict()
    d["schema_version"] = 4
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="schema_version"):
        SessionProfile.load(p)


def test_schema_version_2_requires_native_scale_fields(tmp_path):
    p = tmp_path / "profile.json"
    d = _profile_v2().to_dict()
    del d["native_scale"]
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="native_scale"):
        SessionProfile.load(p)


def test_v3_requires_camera_field(tmp_path):
    p = tmp_path / "profile.json"
    d = _profile_v2().to_dict()  # hat kein "camera"
    d["schema_version"] = 3
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="camera"):
        SessionProfile.load(p)


def test_v3_rejects_camera_null(tmp_path):
    """M-3 final-review.md: `"camera": null` ist vom fehlenden Schluessel
    nicht zu unterscheiden - beides muss abgelehnt werden, sonst laedt
    `camera=None` still durch und harvest.py meldet faelschlich
    'IMX500-Profil (schema_version 2)'."""
    p = tmp_path / "profile.json"
    d = _profile().to_dict()
    d["camera"] = None
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="camera"):
        SessionProfile.load(p)


def test_v2_rejects_foreign_camera_key(tmp_path):
    """Ledger #8 final-review.md: ein v2-Dokument mit einem (fremden)
    'camera'-Schluessel darf nicht an harvests Waechter `camera is None`
    vorbeikommen - sonst wuerde scaler_crop des v2-Profils still ignoriert."""
    p = tmp_path / "profile.json"
    d = _profile_v2().to_dict()
    d["camera"] = _CAMERA.to_dict()
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="camera"):
        SessionProfile.load(p)


def test_v3_rejects_non_none_scaler_crop(tmp_path):
    p = tmp_path / "profile.json"
    d = _profile().to_dict()
    d["scaler_crop"] = [0, 0, 10, 10]
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="scaler_crop"):
        SessionProfile.load(p)


def test_v3_rejects_native_scale_other_than_one(tmp_path):
    p = tmp_path / "profile.json"
    d = _profile().to_dict()
    d["native_scale"] = 0.5
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="native_scale"):
        SessionProfile.load(p)


# --- CharLayout.from_profile: unbestaetigte Profile abweisen (Final-Fix 2) -


def test_char_layout_from_profile_builds_layout_from_confirmed_profile():
    layout = CharLayout.from_profile(_profile(), unit="mV/V")
    assert layout.grid == _profile().grid
    assert layout.unit == "mV/V"


def test_char_layout_from_profile_rejects_resolution_not_ok():
    profile = dataclasses.replace(_profile(), resolution_ok=False)
    with pytest.raises(ValueError, match="resolution_ok"):
        CharLayout.from_profile(profile, unit="mV/V")


def test_char_layout_from_profile_rejects_empty_confirmed_by():
    profile = dataclasses.replace(_profile(), confirmed_by="")
    with pytest.raises(ValueError, match="confirmed_by"):
        CharLayout.from_profile(profile, unit="mV/V")
