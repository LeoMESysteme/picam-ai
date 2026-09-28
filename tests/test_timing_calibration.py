"""`src/dispread/timing_calibration.py` und `scripts/timing-calibration.py`
(Task 5, StreamCam-Umstieg): Timing-Kalibrierung ersetzt das feste,
IMX500-spezifische M=695ms (CLAUDE.md) durch einen je Kamera-USB-ID
gemessenen Wert aus `display-offset.py`-Berichten.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from dispread.timing_calibration import (
    CALIBRATION_SCHEMA_VERSION,
    TimingCalibration,
    calibration_from_offset_reports,
    load_calibration,
)

_CAMERA_USB_ID = "046d:0893"
_CLI_SCRIPT = Path(__file__).parents[1] / "scripts" / "timing-calibration.py"
_MISSING = object()


def _write_session_json(session_dir: Path, *, camera: dict | None | str = _CAMERA_USB_ID) -> Path:
    """`session_dir/session.json` mit einem `camera`-Block wie ihn
    `UvcSource.describe()` liefert - genug fuer den I-3-Herkunftscheck
    (`camera.usb_id`). `camera="fehlt"` laesst den Schluessel ganz weg (v2-
    IMX500-Profil-Aequivalent), `camera=None` traegt ihn explizit als
    `null`."""
    session_dir.mkdir(parents=True, exist_ok=True)
    payload: dict = {}
    if camera == "fehlt":
        pass
    elif camera is None:
        payload["camera"] = None
    else:
        payload["camera"] = {"usb_id": camera}
    (session_dir / "session.json").write_text(json.dumps(payload))
    return session_dir


def _write_offset_report(
    path: Path,
    *,
    session_dir: Path | None = None,
    session_dir_value: str | None | object = _MISSING,
    camera: dict | None | str = _CAMERA_USB_ID,
    small_detected: bool = True,
    small_m_s: float | None = 0.36,
    small_delta_s: float | None = 0.12,
    large_detected: bool = True,
    large_m_s: float | None = 0.695,
    large_delta_s: float | None = 0.20,
) -> Path:
    """`camera` steuert den `session.json`-Kamerablock der (ggf. neu
    angelegten) `session_dir` (Vorgabe: `<path.parent>/session`) - siehe
    `_write_session_json`. `session_dir_value` ueberschreibt das
    `session_dir`-Feld im Bericht selbst (fuer den Fall "Feld fehlt ganz")."""
    if session_dir is None:
        session_dir = path.parent / "session"
    if not (session_dir / "session.json").exists():
        _write_session_json(session_dir, camera=camera)
    report: dict = {}
    if session_dir_value is _MISSING:
        report["session_dir"] = str(session_dir)
    elif session_dir_value is not None:
        report["session_dir"] = session_dir_value
    report["populations"] = [
        {
            "population": "small",
            "detected": small_detected,
            "M_s": small_m_s,
            "delta_s": small_delta_s,
        },
        {
            "population": "large",
            "detected": large_detected,
            "M_s": large_m_s,
            "delta_s": large_delta_s,
        },
    ]
    path.write_text(json.dumps(report))
    return path


def _no_detected_report(path: Path) -> Path:
    return _write_offset_report(
        path,
        small_detected=False,
        small_m_s=None,
        small_delta_s=None,
        large_detected=False,
        large_m_s=None,
        large_delta_s=None,
    )


# --- calibration_from_offset_reports ---------------------------------------


def test_calibration_from_offset_reports_takes_larger_m_s(tmp_path):
    report_path = _write_offset_report(tmp_path / "offset-analyse.json")

    calibration = calibration_from_offset_reports(
        [report_path],
        camera_usb_id=_CAMERA_USB_ID,
        measured_at_utc="2026-09-25T10:00:00+00:00",
    )

    assert calibration.guard_margin_ms == 695.0
    assert calibration.display_offset_ms == pytest.approx(200.0)
    assert calibration.camera_usb_id == _CAMERA_USB_ID
    assert calibration.schema_version == CALIBRATION_SCHEMA_VERSION
    assert len(calibration.sources) == 1
    assert calibration.sources[0]["offset_json"] == str(report_path)
    assert calibration.sources[0]["sha256"] == hashlib.sha256(report_path.read_bytes()).hexdigest()


def test_calibration_from_offset_reports_raises_without_detected_population(tmp_path):
    report_path = _no_detected_report(tmp_path / "offset-analyse.json")

    with pytest.raises(ValueError):
        calibration_from_offset_reports(
            [report_path],
            camera_usb_id=_CAMERA_USB_ID,
            measured_at_utc="2026-09-25T10:00:00+00:00",
        )


def test_calibration_from_offset_reports_ignores_non_detected_population(tmp_path):
    """Nur die detected=True-Population mit dem groesseren M_s zaehlt, auch
    wenn die andere Population ein (nicht verwendbares) M_s traegt."""
    report_path = _write_offset_report(
        tmp_path / "offset-analyse.json",
        small_detected=False,
        small_m_s=5.0,
        small_delta_s=1.0,
        large_detected=True,
        large_m_s=0.695,
        large_delta_s=0.20,
    )

    calibration = calibration_from_offset_reports(
        [report_path],
        camera_usb_id=_CAMERA_USB_ID,
        measured_at_utc="2026-09-25T10:00:00+00:00",
    )

    assert calibration.guard_margin_ms == 695.0


# --- I-3 final-review.md: Kamera-Herkunft der Berichte ----------------------


def test_calibration_from_offset_reports_ablehnt_ohne_session_dir(tmp_path):
    report_path = _write_offset_report(tmp_path / "offset-analyse.json", session_dir_value=None)

    with pytest.raises(ValueError, match="session_dir"):
        calibration_from_offset_reports(
            [report_path],
            camera_usb_id=_CAMERA_USB_ID,
            measured_at_utc="2026-09-25T10:00:00+00:00",
        )


def test_calibration_from_offset_reports_ablehnt_fehlende_session_json(tmp_path):
    report_path = _write_offset_report(
        tmp_path / "offset-analyse.json", session_dir_value=str(tmp_path / "nirgends")
    )

    with pytest.raises(ValueError, match="session.json"):
        calibration_from_offset_reports(
            [report_path],
            camera_usb_id=_CAMERA_USB_ID,
            measured_at_utc="2026-09-25T10:00:00+00:00",
        )


def test_calibration_from_offset_reports_ablehnt_ohne_camera_block(tmp_path):
    """Ein IMX500-Bericht (session.json ohne 'camera'-Schluessel ueberhaupt,
    v2-Profil-Aequivalent) darf keine StreamCam-Kalibrierung erzeugen."""
    report_path = _write_offset_report(tmp_path / "offset-analyse.json", camera="fehlt")

    with pytest.raises(ValueError, match="camera"):
        calibration_from_offset_reports(
            [report_path],
            camera_usb_id=_CAMERA_USB_ID,
            measured_at_utc="2026-09-25T10:00:00+00:00",
        )


def test_calibration_from_offset_reports_ablehnt_camera_null(tmp_path):
    report_path = _write_offset_report(tmp_path / "offset-analyse.json", camera=None)

    with pytest.raises(ValueError, match="camera"):
        calibration_from_offset_reports(
            [report_path],
            camera_usb_id=_CAMERA_USB_ID,
            measured_at_utc="2026-09-25T10:00:00+00:00",
        )


def test_calibration_from_offset_reports_ablehnt_fremde_usb_id(tmp_path):
    report_path = _write_offset_report(tmp_path / "offset-analyse.json", camera="1234:5678")

    with pytest.raises(ValueError, match="1234:5678"):
        calibration_from_offset_reports(
            [report_path],
            camera_usb_id=_CAMERA_USB_ID,
            measured_at_utc="2026-09-25T10:00:00+00:00",
        )


def test_cli_exit_2_bei_fremder_kamera(tmp_path):
    report_path = _write_offset_report(tmp_path / "offset-analyse.json", camera="1234:5678")
    out_path = tmp_path / "out" / "timing-streamcam.json"

    result = subprocess.run(
        [
            sys.executable,
            str(_CLI_SCRIPT),
            str(report_path),
            "--out",
            str(out_path),
            "--camera-usb-id",
            _CAMERA_USB_ID,
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert not out_path.exists()


# --- TimingCalibration.save / load_calibration -----------------------------


def test_save_load_roundtrip(tmp_path):
    calibration = TimingCalibration(
        camera_usb_id=_CAMERA_USB_ID,
        guard_margin_ms=695.0,
        display_offset_ms=200.0,
        measured_at_utc="2026-09-25T10:00:00+00:00",
        sources=({"offset_json": "a.json", "sha256": "abc123"},),
    )
    path = tmp_path / "calibration" / "timing-streamcam.json"

    calibration.save(path)

    assert path.is_file()
    loaded = load_calibration(path)
    assert loaded == calibration


def test_load_calibration_missing_file(tmp_path):
    with pytest.raises(ValueError):
        load_calibration(tmp_path / "does-not-exist.json")


def test_load_calibration_rejects_wrong_schema_version(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "camera_usb_id": _CAMERA_USB_ID,
                "guard_margin_ms": 695.0,
                "display_offset_ms": 200.0,
                "measured_at_utc": "2026-09-25T10:00:00+00:00",
                "sources": [],
            }
        )
    )
    with pytest.raises(ValueError):
        load_calibration(path)


def test_load_calibration_rejects_missing_field(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "camera_usb_id": _CAMERA_USB_ID,
                "guard_margin_ms": 695.0,
                "measured_at_utc": "2026-09-25T10:00:00+00:00",
                "sources": [],
            }
        )
    )
    with pytest.raises(ValueError):
        load_calibration(path)


def test_load_calibration_rejects_zero_guard_margin(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "camera_usb_id": _CAMERA_USB_ID,
                "guard_margin_ms": 0,
                "display_offset_ms": 200.0,
                "measured_at_utc": "2026-09-25T10:00:00+00:00",
                "sources": [],
            }
        )
    )
    with pytest.raises(ValueError):
        load_calibration(path)


def test_load_calibration_rejects_negative_guard_margin(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "camera_usb_id": _CAMERA_USB_ID,
                "guard_margin_ms": -1.0,
                "display_offset_ms": 200.0,
                "measured_at_utc": "2026-09-25T10:00:00+00:00",
                "sources": [],
            }
        )
    )
    with pytest.raises(ValueError):
        load_calibration(path)


def test_load_calibration_rejects_nan_guard_margin(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "camera_usb_id": _CAMERA_USB_ID,
                "guard_margin_ms": math.nan,
                "display_offset_ms": 200.0,
                "measured_at_utc": "2026-09-25T10:00:00+00:00",
                "sources": [],
            }
        )
    )
    with pytest.raises(ValueError):
        load_calibration(path)


# --- M-5 final-review.md: alle Fehler werden zu ValueError ------------------


def test_load_calibration_rejects_permission_error(tmp_path, monkeypatch):
    path = tmp_path / "calibration.json"
    path.write_text("{}")
    import dispread.timing_calibration as timing_calibration_module

    def _boom(self):
        raise PermissionError("keine Berechtigung")

    monkeypatch.setattr(Path, "read_bytes", _boom)
    with pytest.raises(ValueError):
        timing_calibration_module.load_calibration(path)


def test_load_calibration_rejects_non_object_json(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps([1, 2, 3]))
    with pytest.raises(ValueError):
        load_calibration(path)


def test_load_calibration_rejects_null_display_offset(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": CALIBRATION_SCHEMA_VERSION,
                "camera_usb_id": _CAMERA_USB_ID,
                "guard_margin_ms": 695.0,
                "display_offset_ms": None,
                "measured_at_utc": "2026-09-25T10:00:00+00:00",
                "sources": [],
            }
        )
    )
    with pytest.raises(ValueError):
        load_calibration(path)


def test_load_calibration_rejects_malformed_json(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text("{nicht json")
    with pytest.raises(ValueError):
        load_calibration(path)


# --- scripts/timing-calibration.py CLI --------------------------------------


def test_cli_writes_calibration_and_exits_0(tmp_path):
    report_path = _write_offset_report(tmp_path / "offset-analyse.json")
    out_path = tmp_path / "out" / "timing-streamcam.json"

    result = subprocess.run(
        [
            sys.executable,
            str(_CLI_SCRIPT),
            str(report_path),
            "--out",
            str(out_path),
            "--camera-usb-id",
            _CAMERA_USB_ID,
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert out_path.is_file()
    data = json.loads(out_path.read_text())
    assert data["guard_margin_ms"] == 695.0
    assert data["camera_usb_id"] == _CAMERA_USB_ID
    assert "695" in result.stdout


def test_cli_exit_2_on_value_error(tmp_path):
    report_path = _no_detected_report(tmp_path / "offset-analyse.json")
    out_path = tmp_path / "out" / "timing-streamcam.json"

    result = subprocess.run(
        [sys.executable, str(_CLI_SCRIPT), str(report_path), "--out", str(out_path)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert not out_path.exists()
