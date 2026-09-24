"""`scripts/harvest-setup.py` - Task 3 aus
docs/superpowers/plans/2026-09-23-ernte-phase1.md.

Test-first: jeder Test hier muss scheitern, bevor das Skript existiert. Das
synthetische Bild ist ein graues Bild mit einem gesaettigten gruenen
Rechteck (16 Zellen mit je einem 5x8-Punktmuster), das per Homographie in
ein leicht geneigtes Vierpunktquad projiziert wird - genau der Fall, fuer den
`lcd_quad_in_region` gebaut ist (hinterleuchtete Zeichen-LCD).

Muster fuer das Laden des Skripts per importlib aus `tests/test_gate_label.py`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

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


def _dummy_proposal(
    tmp_path: Path, *, grid_source: str, min_px: float = 4.0, native_scale: float | None = 1.0
) -> dict:
    """`native_scale=1.0` (Vorgabe) ahmt propose mit --session-json und einem
    Crop nach, der breiter als der Output ist (kein Aufskalieren, siehe
    Bug 2/_compute_native_scale) - die bestehenden Gate-Tests pruefen damit
    weiterhin unveraendert min_source_dot_column_px == min_native_dot_column_px.
    `native_scale=None` simuliert propose OHNE --session-json."""
    grid = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    return {
        "frame": str(tmp_path / "frame.png"),
        "device_id": "gsv2as-01",
        "session_id": "s1",
        "quad": QUAD_GT,
        "target_size": [400, 160],
        "grid": grid.to_dict(),
        "grid_source": grid_source,
        "scaler_crop": None,
        "min_source_dot_column_px": min_px,
        "session_json": None,
        "native_scale": native_scale,
        "min_native_dot_column_px": (min_px * native_scale) if native_scale is not None else None,
    }


def test_propose_finds_quad_and_writes_files(tmp_path):
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

    found_quad = proposal["quad"]
    assert len(found_quad) == 4
    for (fx, fy), (gx, gy) in zip(found_quad, QUAD_GT, strict=True):
        assert abs(fx - gx) <= 3
        assert abs(fy - gy) <= 3


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
    out_dir = tmp_path / "session"

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
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


# --- Bug 2 (Orchestrator 2026-09-23): natives Aufloesungs-Gate -------------
#
# ScalerCrop < Output-Groesse des Sensormodus heisst der ISP skaliert hoch -
# source_dot_column_px (Quellbild = Output-Bild) ist dann zu optimistisch.
# _compute_native_scale rechnet auf native (unbeschnittene, unbinned)
# Sensorpixel zurueck; binning = sensor_array_size.width / sensor_mode_size.width.

# 2x2-gebinnter Sensormodus (CLAUDE.md: "Selected sensor format: 2028x1520").
_SENSOR_MODE_SIZE = (2028, 1520)
_SENSOR_ARRAY_SIZE = (4056, 3040)
_OUTPUT_SIZE = (960, 720)


def test_compute_native_scale_frontal_crop_matches_worked_example():
    # Aus dem Auftrag: 1195 px breiter Crop -> scale = 1195/2/960 ~= 0.622.
    scale = harvest_setup._compute_native_scale(
        scaler_crop_actual=(100, 100, 1195, 900),
        sensor_mode_size=_SENSOR_MODE_SIZE,
        sensor_array_size=_SENSOR_ARRAY_SIZE,
        output_size=_OUTPUT_SIZE,
    )
    assert scale == pytest.approx(1195 / 2 / 960, rel=1e-6)
    assert scale == pytest.approx(0.622, abs=1e-3)


def test_compute_native_scale_no_crop_is_output_limited_scale_one():
    # Kein Crop -> volle Sensorbreite (4056) als Crop-Breite - output-
    # limitiert (der ISP skaliert nur herunter), scale bleibt bei 1.0.
    scale = harvest_setup._compute_native_scale(
        scaler_crop_actual=None,
        sensor_mode_size=_SENSOR_MODE_SIZE,
        sensor_array_size=_SENSOR_ARRAY_SIZE,
        output_size=_OUTPUT_SIZE,
    )
    assert scale == pytest.approx(1.0)


def test_compute_native_scale_wide_crop_stays_capped_at_one():
    """Ein Crop breiter als der Output darf nie hochskalieren - min(1, ...)."""
    scale = harvest_setup._compute_native_scale(
        scaler_crop_actual=(0, 0, 3000, 2000),
        sensor_mode_size=_SENSOR_MODE_SIZE,
        sensor_array_size=_SENSOR_ARRAY_SIZE,
        output_size=_OUTPUT_SIZE,
    )
    assert scale == pytest.approx(1.0)


def _session_json(tmp_path: Path, *, scaler_crop_actual, sensor_mode_size, sensor_array_size) -> Path:
    path = tmp_path / "session.json"
    path.write_text(
        json.dumps(
            {
                "scaler_crop_actual": list(scaler_crop_actual) if scaler_crop_actual is not None else None,
                "sensor_mode_size": list(sensor_mode_size) if sensor_mode_size is not None else None,
                "sensor_array_size": list(sensor_array_size) if sensor_array_size is not None else None,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_propose_with_session_json_writes_native_scale_fields(tmp_path):
    canvas = _build_synthetic_scene()
    frame_path = tmp_path / "frame.png"
    cv2.imwrite(str(frame_path), canvas)
    session_json_path = _session_json(
        tmp_path,
        scaler_crop_actual=(100, 100, 1195, 900),
        sensor_mode_size=_SENSOR_MODE_SIZE,
        sensor_array_size=_SENSOR_ARRAY_SIZE,
    )
    out_dir = tmp_path / "session"

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
            "--device-id",
            "gsv2as-01",
            "--session-id",
            "s1",
            "--out",
            str(out_dir),
            "--session-json",
            str(session_json_path),
        ]
    )
    assert rc == 0
    proposal = json.loads((out_dir / "proposal.json").read_text())
    assert proposal["native_scale"] == pytest.approx(1195 / 2 / canvas.shape[1], rel=1e-6)
    assert proposal["min_native_dot_column_px"] == pytest.approx(
        proposal["min_source_dot_column_px"] * proposal["native_scale"], rel=1e-6
    )
    assert proposal["session_json"] == str(session_json_path)


def test_propose_without_session_json_leaves_native_scale_none(tmp_path):
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
    assert proposal["native_scale"] is None
    assert proposal["min_native_dot_column_px"] is None
    assert proposal["session_json"] is None


def test_propose_session_json_without_sensor_fields_leaves_native_scale_none(tmp_path):
    """z. B. eine synthetic://-Aufzeichnung: session.json existiert, aber
    sensor_mode_size/sensor_array_size sind null - kein Rateversuch."""
    canvas = _build_synthetic_scene()
    frame_path = tmp_path / "frame.png"
    cv2.imwrite(str(frame_path), canvas)
    session_json_path = _session_json(
        tmp_path, scaler_crop_actual=None, sensor_mode_size=None, sensor_array_size=None
    )
    out_dir = tmp_path / "session"

    rc = harvest_setup.main(
        [
            "propose",
            "--frame",
            str(frame_path),
            "--hint-box",
            HINT_BOX,
            "--device-id",
            "gsv2as-01",
            "--session-id",
            "s1",
            "--out",
            str(out_dir),
            "--session-json",
            str(session_json_path),
        ]
    )
    assert rc == 0
    proposal = json.loads((out_dir / "proposal.json").read_text())
    assert proposal["native_scale"] is None
    assert proposal["min_native_dot_column_px"] is None


def test_confirm_requires_assume_native_scale_when_proposal_has_none(tmp_path):
    proposal = _dummy_proposal(tmp_path, grid_source="operator_provided", min_px=4.0, native_scale=None)
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    out_path = tmp_path / "profile.json"

    rc = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "3.5",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 2
    assert not out_path.exists()


def test_confirm_accepts_explicit_assume_native_scale(tmp_path):
    proposal = _dummy_proposal(tmp_path, grid_source="operator_provided", min_px=4.0, native_scale=None)
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    out_path = tmp_path / "profile.json"

    rc = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "3.5",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_path),
            "--assume-native-scale",
            "1.0",
        ]
    )
    assert rc == 0
    profile = SessionProfile.load(out_path)
    assert profile.native_scale == pytest.approx(1.0)
    assert profile.min_native_dot_column_px == pytest.approx(4.0)
    assert profile.resolution_ok is True


def test_confirm_gate_uses_native_value_not_raw_source_value(tmp_path):
    """Kernstueck von Bug 2: min_source_dot_column_px allein wuerde die
    Schwelle bestehen, min_native_dot_column_px (mit dem gemessenen
    Beispiel-Crop, scale ~= 0.622) nicht - das Gate MUSS den nativen Wert
    pruefen, sonst waere die Aufloesung ueberschaetzt."""
    grid = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    native_scale = 1195 / 2 / 960
    min_px = 4.0
    proposal = {
        "frame": str(tmp_path / "frame.png"),
        "device_id": "gsv2as-01",
        "session_id": "s1",
        "quad": QUAD_GT,
        "target_size": [400, 160],
        "grid": grid.to_dict(),
        "grid_source": "operator_provided",
        "scaler_crop": None,
        "min_source_dot_column_px": min_px,
        "session_json": None,
        "native_scale": native_scale,
        "min_native_dot_column_px": min_px * native_scale,
    }
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
    out_path = tmp_path / "profile.json"

    # Schwelle liegt zwischen dem rohen (4.0) und dem nativen (~2.49) Wert.
    rc = harvest_setup.main(
        [
            "confirm",
            "--proposal",
            str(proposal_path),
            "--resolution-threshold-px",
            "3.0",
            "--confirmed-by",
            "bediener",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 3
    profile = SessionProfile.load(out_path)
    assert profile.resolution_ok is False
    assert profile.min_source_dot_column_px == pytest.approx(4.0)
    assert profile.min_native_dot_column_px < 3.0
