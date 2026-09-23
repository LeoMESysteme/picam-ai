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


def _dummy_proposal(tmp_path: Path, *, grid_source: str, min_px: float = 4.0) -> dict:
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
