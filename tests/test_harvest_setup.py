"""`scripts/harvest-setup.py` - Task 3 (`propose`/`confirm`) und Task 4
(`focus`, Profil v3, StreamCam-Umstieg).

Test-first: jeder Test hier muss scheitern, bevor das Skript existiert. Das
synthetische Bild ist ein graues Bild mit einem gesaettigten gruenen
Rechteck (16 Zellen mit je einem 5x8-Punktmuster), das per Homographie in
ein leicht geneigtes Vierpunktquad projiziert wird - genau der Fall, fuer den
`lcd_quad_in_region` gebaut ist (hinterleuchtete Zeichen-LCD).

Muster fuer das Laden des Skripts per importlib aus `tests/test_gate_label.py`.

`focus` wird nie gegen echte Hardware getestet (AGENTS.md) - `_open_camera_io`
wird komplett per Monkeypatch ersetzt, `time.sleep` ebenso (sonst wuerde die
Testsuite die realen Wartezeiten des Sweeps/der Weissabgleich-Einschwingzeit
mitmachen).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from dispread.camera_settings import STREAMCAM_MODEL, STREAMCAM_USB_ID, CameraSettings
from dispread.charcells import CharGrid
from dispread.session_profile import SessionProfile

SCRIPT = Path(__file__).parents[1] / "scripts" / "harvest-setup.py"

_spec = importlib.util.spec_from_file_location("harvest_setup", SCRIPT)
harvest_setup = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = harvest_setup  # dataclasses braucht das Modul in sys.modules
_spec.loader.exec_module(harvest_setup)


# Vierpunktquad in Quellbildpixeln, Reihenfolge oben-links, oben-rechts,
# unten-rechts, unten-links - dieselbe Ordnung, die `lcd_quad_in_region`
# zurueckgeben soll. Ein um 6 Grad gedrehtes (nicht allgemein perspektivisch
# verzerrtes) Rechteck: `lcd_quad_in_region` passt intern ein `minAreaRect`
# (eine gedrehte RECHTECK-Hypothese) an die gefundene Kontur an - ein
# allgemeines, geschertes Parallelogramm wuerde davon systematisch abweichen,
# eine reine Drehung (rechte Winkel bleiben erhalten) nicht.
QUAD_GT = [[129.46, 79.53], [527.27, 121.34], [510.54, 280.47], [112.73, 238.66]]
CANVAS_SIZE = (640, 360)  # (Breite, Hoehe)
HINT_BOX = "0.14375,0.16389,0.710938,0.669444"  # umschliesst QUAD_GT mit etwas Rand


def _build_synthetic_scene() -> np.ndarray:
    """Graues Bild mit einem leicht geneigten, gesaettigt-gruenen Rechteck
    (16 Zellen, je ein dunkles 5x8-Punktmuster) - via Homographie aus einem
    flachen 400x160-Kanvas projiziert, genau wie `rectify()`/`propose` es
    spaeter wieder entzerren wuerden."""
    canvas_w, canvas_h = CANVAS_SIZE
    canvas = np.full((canvas_h, canvas_w, 3), 128, dtype=np.uint8)

    flat_w, flat_h = 400, 160
    flat = np.zeros((flat_h, flat_w, 3), dtype=np.uint8)
    flat[:, :] = (0, 180, 0)  # gesaettigtes Gruen wie die Hintergrundbeleuchtung
    pitch = flat_w / 16
    for i in range(16):
        x0 = int(i * pitch) + 4
        for row in range(8):
            for col in range(5):
                cv2.circle(flat, (x0 + col * 3, 20 + row * 15), 1, (0, 0, 0), -1)

    src_pts = np.array([[0, 0], [flat_w, 0], [flat_w, flat_h], [0, flat_h]], dtype=np.float32)
    dst_pts = np.array(QUAD_GT, dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(flat, matrix, (canvas_w, canvas_h), flags=cv2.INTER_NEAREST)
    mask = cv2.warpPerspective(
        np.full((flat_h, flat_w), 255, dtype=np.uint8),
        matrix,
        (canvas_w, canvas_h),
        flags=cv2.INTER_NEAREST,
    )
    canvas[mask > 0] = warped[mask > 0]
    return canvas


def _build_synthetic_scene_asymmetric() -> np.ndarray:
    """Wie `_build_synthetic_scene`, aber mit einem asymmetrischen Merkmal:
    Zelle 0 (die am weitesten links liegende) ist vollstaendig schwarz
    ausgefuellt, alle anderen Zellen bleiben einfarbig gesaettigt-gruen ohne
    Punktmuster.

    `_build_synthetic_scene` benutzt in jeder der 16 Zellen dasselbe 5x8-
    Punktmuster - ein Links-Rechts-Tausch der Eckenzuordnung waere darin
    unsichtbar, weil das gespiegelte Bild pixelgleich zum unveraenderten
    waere. Diese Szene hat genau ein unterscheidbares Merkmal an einem
    bekannten Rand, damit eine falsch orientierte Entzerrung (Spiegelung
    oder Vertauschung der Eckenreihenfolge) den Test tatsaechlich zum
    Scheitern bringt.
    """
    canvas_w, canvas_h = CANVAS_SIZE
    canvas = np.full((canvas_h, canvas_w, 3), 128, dtype=np.uint8)

    flat_w, flat_h = 400, 160
    flat = np.zeros((flat_h, flat_w, 3), dtype=np.uint8)
    flat[:, :] = (0, 180, 0)  # gesaettigtes Gruen wie die Hintergrundbeleuchtung
    pitch = flat_w / 16
    marker_width = int(pitch)
    flat[:, :marker_width] = (0, 0, 0)  # Zelle 0 (ganz links) komplett schwarz

    src_pts = np.array([[0, 0], [flat_w, 0], [flat_w, flat_h], [0, flat_h]], dtype=np.float32)
    dst_pts = np.array(QUAD_GT, dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    warped = cv2.warpPerspective(flat, matrix, (canvas_w, canvas_h), flags=cv2.INTER_NEAREST)
    mask = cv2.warpPerspective(
        np.full((flat_h, flat_w), 255, dtype=np.uint8),
        matrix,
        (canvas_w, canvas_h),
        flags=cv2.INTER_NEAREST,
    )
    canvas[mask > 0] = warped[mask > 0]
    return canvas


def _camera_settings(*, size: tuple[int, int] = CANVAS_SIZE) -> CameraSettings:
    return CameraSettings(
        model=STREAMCAM_MODEL,
        usb_id=STREAMCAM_USB_ID,
        size=size,
        fourcc="YUYV",
        fps=30,
        controls={
            "focus_absolute": 48,
            "exposure_time_absolute": 157,
            "white_balance_temperature": 4600,
            "gain": 32,
        },
    )


def _write_camera_settings(tmp_path: Path, *, size: tuple[int, int] = CANVAS_SIZE, name: str = "camera-settings.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps({"camera": _camera_settings(size=size).to_dict()}), encoding="utf-8")
    return path


def _dummy_proposal(tmp_path: Path, *, grid_source: str, min_px: float = 4.0, with_camera: bool = True) -> dict:
    grid = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    proposal = {
        "frame": str(tmp_path / "frame.png"),
        "device_id": "gsv2as-01",
        "session_id": "s1",
        "quad": QUAD_GT,
        "target_size": [400, 160],
        "grid": grid.to_dict(),
        "grid_source": grid_source,
        "scaler_crop": None,
        "min_source_dot_column_px": min_px,
        "native_scale": 1.0,
        "min_native_dot_column_px": min_px,
    }
    if with_camera:
        proposal["camera"] = _camera_settings().to_dict()
    return proposal


def test_propose_finds_quad_and_writes_files(tmp_path):
    canvas = _build_synthetic_scene()
    frame_path = tmp_path / "frame.png"
    cv2.imwrite(str(frame_path), canvas)
    camera_settings_path = _write_camera_settings(tmp_path)
    out_dir = tmp_path / "session"

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
            "--camera-settings",
            str(camera_settings_path),
            "--device-id",
            "gsv2as-01",
            "--session-id",
            "s1",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0

    proposal = json.loads((out_dir / "proposal.json").read_text())
    assert (out_dir / "overlay_source.png").exists()
    assert (out_dir / "overlay_rectified.png").exists()
    assert proposal["grid_source"] == "default_even_split"
    assert proposal["device_id"] == "gsv2as-01"
    assert proposal["session_id"] == "s1"
    assert proposal["min_source_dot_column_px"] > 0
    assert proposal["native_scale"] == 1.0
    assert proposal["min_native_dot_column_px"] == pytest.approx(proposal["min_source_dot_column_px"])
    assert proposal["scaler_crop"] is None
    assert proposal["camera"] == _camera_settings().to_dict()

    found_quad = proposal["quad"]
    assert len(found_quad) == 4
    for (fx, fy), (gx, gy) in zip(found_quad, QUAD_GT, strict=True):
        assert abs(fx - gx) <= 3
        assert abs(fy - gy) <= 3


def test_propose_rejects_frame_size_mismatch(tmp_path):
    canvas = _build_synthetic_scene()
    frame_path = tmp_path / "frame.png"
    cv2.imwrite(str(frame_path), canvas)
    # Kameraeinstellungen fuer eine ANDERE Groesse als das Bild (640x360).
    camera_settings_path = _write_camera_settings(tmp_path, size=(1920, 1080))
    out_dir = tmp_path / "session"

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
            "--camera-settings",
            str(camera_settings_path),
            "--device-id",
            "gsv2as-01",
            "--session-id",
            "s1",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 2
    assert not (out_dir / "proposal.json").exists()


def test_propose_rejects_missing_camera_settings(tmp_path):
    canvas = _build_synthetic_scene()
    frame_path = tmp_path / "frame.png"
    cv2.imwrite(str(frame_path), canvas)
    out_dir = tmp_path / "session"

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
            "--camera-settings",
            str(tmp_path / "does-not-exist.json"),
            "--device-id",
            "gsv2as-01",
            "--session-id",
            "s1",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 2
    assert not (out_dir / "proposal.json").exists()


def test_propose_rectified_image_is_not_mirrored(tmp_path):
    """`overlay_rectified.png` muss den dunklen Marker aus Zelle 0 links
    zeigen, nicht rechts - Regressionstest gegen eine vertauschte
    Eckenreihenfolge zwischen `lcd_quad_in_region`/`glass_quad_in_region`
    und `rectify()` (beide muessen dieselbe oben-links/oben-rechts/unten-
    rechts/unten-links-Konvention aus `dispread.rectify._order_quad`
    benutzen). Der bestehende `test_propose_finds_quad_and_writes_files`
    prueft nur die Quad-Koordinaten, nicht die Bildorientierung, und sein
    Punktmuster ist in jeder Zelle identisch - eine Spiegelung waere dort
    unsichtbar."""
    # `--quad` statt Suche: der Marker (Zelle 0, komplett schwarz) hat keine
    # Saettigung und waere fuer `glass_quad_in_region`s huegestuetzte Maske
    # selbst ein Ausschluss (Glas vs. Rahmen) statt eines Merkmals *innerhalb*
    # des Glases - das ist ein eigenes, hier nicht zu testendes Detektionsver-
    # halten. Mit `--quad` wird die bekannte Zielgeometrie direkt vorgegeben,
    # das isoliert die Frage auf Eckenreihenfolge -> Entzerrung.
    canvas = _build_synthetic_scene_asymmetric()
    frame_path = tmp_path / "frame.png"
    cv2.imwrite(str(frame_path), canvas)
    camera_settings_path = _write_camera_settings(tmp_path)
    out_dir = tmp_path / "session"
    quad_arg = ",".join(f"{x:.4f},{y:.4f}" for x, y in QUAD_GT)

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
            "--quad",
            quad_arg,
            "--camera-settings",
            str(camera_settings_path),
            "--device-id",
            "gsv2as-01",
            "--session-id",
            "s1",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0

    rectified = cv2.imread(str(out_dir / "overlay_rectified.png"))
    gray = cv2.cvtColor(rectified, cv2.COLOR_BGR2GRAY)
    width = gray.shape[1]
    left_quarter = gray[:, : width // 4]
    right_quarter = gray[:, -width // 4 :]
    # Der schwarze Marker liegt in Zelle 0 (links) - links muss deutlich
    # dunkler sein als rechts. Bei vertauschter Eckenzuordnung (Spiegelung)
    # laege der Marker stattdessen rechts, und die Ungleichung kippt.
    assert left_quarter.mean() < right_quarter.mean() - 15, (
        f"links={left_quarter.mean():.1f} rechts={right_quarter.mean():.1f} "
        "- Marker aus Zelle 0 liegt nicht links, Bild vermutlich gespiegelt/falsch orientiert"
    )


def test_propose_fails_without_guessing_when_no_quad_found(tmp_path):
    # Rein grauer Hintergrund - keine gesaettigte Flaeche, also kein Quad.
    canvas = np.full((*CANVAS_SIZE[::-1], 3), 128, dtype=np.uint8)
    frame_path = tmp_path / "frame.png"
    cv2.imwrite(str(frame_path), canvas)
    camera_settings_path = _write_camera_settings(tmp_path)
    out_dir = tmp_path / "session"

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
            "--camera-settings",
            str(camera_settings_path),
            "--device-id",
            "gsv2as-01",
            "--session-id",
            "s1",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 2
    assert not (out_dir / "proposal.json").exists()


def test_confirm_below_threshold_ok_above_threshold_rejected(tmp_path):
    proposal = _dummy_proposal(tmp_path, grid_source="operator_provided", min_px=4.0)
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    out_ok = tmp_path / "ok" / "profile.json"
    rc_ok = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "3.5",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_ok),
        ]
    )
    assert rc_ok == 0
    profile_ok = SessionProfile.load(out_ok)
    assert profile_ok.resolution_ok is True
    assert profile_ok.min_source_dot_column_px == pytest.approx(4.0)
    assert profile_ok.schema_version == 3
    assert profile_ok.camera == _camera_settings()
    assert profile_ok.scaler_crop is None
    assert profile_ok.native_scale == pytest.approx(1.0)

    out_bad = tmp_path / "bad" / "profile.json"
    rc_bad = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "4.5",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_bad),
        ]
    )
    assert rc_bad == 3
    profile_bad = SessionProfile.load(out_bad)
    assert profile_bad.resolution_ok is False


def test_confirm_without_threshold_fails_argparse(tmp_path):
    proposal = _dummy_proposal(tmp_path, grid_source="operator_provided")
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        harvest_setup.main(
            [
                "confirm",
                "--proposal",
                str(proposal_path),
                "--confirmed-by",
                "bediener",
                "--out",
                str(tmp_path / "profile.json"),
            ]
        )
    assert exc_info.value.code == 2


def test_confirm_rejects_unconfirmed_default_grid(tmp_path):
    proposal = _dummy_proposal(tmp_path, grid_source="default_even_split")
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    out_path = tmp_path / "profile.json"

    rc = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "1.0",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 2
    assert not out_path.exists()

    rc_accepted = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "1.0",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_path),
            "--accept-default-grid",
        ]
    )
    assert rc_accepted == 0
    assert out_path.exists()


def test_confirm_rejects_proposal_without_camera(tmp_path):
    """Ein IMX500-Vorschlag von vor dem StreamCam-Umstieg (kein 'camera') -
    harter Abbruch statt eines Profils ohne Kameraeinstellungen."""
    proposal = _dummy_proposal(tmp_path, grid_source="operator_provided", with_camera=False)
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    out_path = tmp_path / "profile.json"

    rc = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "1.0",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 2
    assert not out_path.exists()


# --- focus ------------------------------------------------------------


def _checkerboard(size: int = 240, cell: int = 8) -> np.ndarray:
    row = (np.arange(size) // cell) % 2
    pattern = (np.logical_xor(row[:, None], row[None, :]).astype(np.uint8)) * 255
    return cv2.cvtColor(pattern, cv2.COLOR_GRAY2BGR)


_SHARP_BASE = _checkerboard()


def _frame_for_focus(focus: int, best_focus: int = 48) -> np.ndarray:
    """Schaerfe (Laplace-Varianz) ist bei `focus == best_focus` maximal und
    faellt mit wachsendem Abstand monoton - genau das Signal, das ein echter
    Fokus-Sweep vorfaende."""
    distance = abs(focus - best_focus)
    if distance == 0:
        return _SHARP_BASE.copy()
    k = 1 + 2 * min(distance, 15)  # ungerade Kernelgroesse, waechst mit dem Abstand
    return cv2.GaussianBlur(_SHARP_BASE, (k, k), 0)


class _FakeCapture:
    def __init__(self, state: dict, *, width: int = 1920, height: int = 1080):
        self._state = state
        self._width = width
        self._height = height
        self._pos_msec = 0.0

    def set(self, prop, value):  # noqa: ARG002 - Breite/Hoehe kommen aus dem Konstruktor
        pass

    def get(self, prop):
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return self._width
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return self._height
        if prop == cv2.CAP_PROP_POS_MSEC:
            self._pos_msec += 33.3
            return self._pos_msec
        return 0.0

    def read(self):
        return True, _frame_for_focus(self._state.get("focus_absolute", 0))

    def release(self):
        pass


def _make_fake_camera_io():
    state = {
        "focus_absolute": 0,
        "exposure_time_absolute": 157,
        "white_balance_temperature": 4600,
        "gain": 32,
    }
    capture = _FakeCapture(state)

    def fake_set_controls(device, controls):  # noqa: ARG001
        for name, value in controls:
            state[name] = value

    def fake_get_controls(device, names):  # noqa: ARG001
        return {name: state[name] for name in names}

    return SimpleNamespace(
        device="/dev/video0",
        capture=capture,
        capture_factory=lambda d: capture,  # noqa: ARG005 - dieselbe Aufnahme, kein zweites Oeffnen
        set_controls=fake_set_controls,
        get_controls=fake_get_controls,
    ), state


def test_focus_writes_camera_settings_with_best_focus(tmp_path, monkeypatch):
    fake_io, state = _make_fake_camera_io()
    monkeypatch.setattr(harvest_setup, "_open_camera_io", lambda device: fake_io)
    monkeypatch.setattr(harvest_setup.time, "sleep", lambda seconds: None)

    out_dir = tmp_path / "focus"
    rc = harvest_setup.main(["focus", "--out", str(out_dir), "--settle-s", "0"])
    assert rc == 0

    data = json.loads((out_dir / "camera-settings.json").read_text())
    assert data["camera"]["controls"]["focus_absolute"] == 48
    assert data["camera"]["controls"]["exposure_time_absolute"] == 157
    assert data["camera"]["controls"]["white_balance_temperature"] == 4600
    assert data["camera"]["controls"]["gain"] == 32
    assert data["camera"]["model"] == STREAMCAM_MODEL
    assert data["camera"]["size"] == [1920, 1080]
    assert len(data["focus_sweep"]) > 0
    assert "created_at_utc" in data
    assert (out_dir / "control.png").exists()
    # Nach `focus` steht die Automatik wieder auf manuell (`auto_exposure=3`
    # ist der v4l2-Wert fuer manuelle Belichtung mit Weissabgleich-Automatik
    # kurzzeitig aktiviert, danach fixiert `UvcSource.open()` alles wieder
    # auf die festen Werte aus `settings.controls`/MODE_CONTROLS).
    assert state["focus_automatic_continuous"] == 0
    assert state["white_balance_automatic"] == 0
