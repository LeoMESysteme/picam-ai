import copy
import hashlib
from dataclasses import replace
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from frame_tracking_helpers import reference_scene, tracking_block
from test_live_setup import _CAMERA, _proposal

from dispread.live import setup as live_setup
from dispread.live.frame_tracking import RegionProposal, propose_regions


def _propose(tmp_path, *, blank=False, live_tracking=True):
    image, quad = reference_scene()
    if blank:
        image[:] = 120
    frame = tmp_path / "still.png"
    cv2.imwrite(str(frame), image)
    fit = SimpleNamespace(quad=quad, assigned_points=[], rejected_points=[])
    checks = SimpleNamespace(
        overall="OK", checks={"kanten": SimpleNamespace(cells=[])},
        to_dict=lambda: {"overall": "OK", "checks": {"rasterversatz": {"status": "OK"}}},
    )
    proposal = live_setup.propose_with_fit(
        image, fit=fit, frame_path=frame, camera_settings=replace(_CAMERA, size=image.shape[1::-1]),
        device_id="gsv", session_id="session", out_dir=tmp_path,
        offset_check=SimpleNamespace(status="OK"), final_checks=checks, setup_attempt=2, live_tracking=live_tracking,
    )
    return image, quad, proposal


@pytest.mark.parametrize("blank", [False, True])
def test_proposal_binds_regions_to_still_and_shows_check(tmp_path, blank):
    image, quad, proposal = _propose(tmp_path, blank=blank)
    block = proposal["live_tracking"]
    assert block["version"] == 1 and block["method"] == "rahmenbereiche"
    assert isinstance(block["proposal_revision"], str) and block["proposal_revision"]
    assert block["frame_sha256"] == hashlib.sha256((tmp_path / "still.png").read_bytes()).hexdigest()
    assert RegionProposal.from_dict(block["proposal"]) == propose_regions(image, quad)
    check = proposal["setup_checks"]["checks"]["nachfuehrung"]
    assert check["status"] == ("FEHLER" if blank else "OK")
    assert proposal["setup_checks"]["overall"] == check["status"]
    if blank:
        assert "Rahmenbereiche" in check["reason"]
    else:
        profile = live_setup.confirm_proposal(proposal, confirmed_by="Tester", resolution_threshold_px=2.6)
        assert profile.live_tracking == block
        block["proposal"]["regions"].clear()
        assert profile.live_tracking["proposal"]["regions"]  # Keine geteilte mutable Auswahl.


@pytest.mark.parametrize("tamper", ["hash", "version", "method"])
def test_confirmation_refuses_unbound_tracking(tmp_path, tamper):
    proposal = _proposal(tmp_path)
    image, quad = reference_scene()
    proposal["live_tracking"] = tracking_block(image, quad, tmp_path / "still.png")
    proposal["live_tracking"][{"hash": "frame_sha256", "version": "version", "method": "method"}[tamper]] = "wrong"
    with pytest.raises(live_setup.SetupError, match="Rahmenbereiche passen nicht zum Einrichtungsbild - neu einrichten"):
        live_setup.confirm_proposal(proposal, confirmed_by="Tester", resolution_threshold_px=2.6)


def test_override_failed_tracking_confirms_without_regions(tmp_path):
    _, _, proposal = _propose(tmp_path, blank=True)
    with pytest.raises(live_setup.SetupError, match="FEHLER"):
        live_setup.confirm_proposal(proposal, confirmed_by="Tester", resolution_threshold_px=2.6)
    profile = live_setup.confirm_proposal(
        proposal, confirmed_by="Tester", resolution_threshold_px=2.6, override_reason="Nur Diagnose",
    )
    assert profile.live_tracking is None
    assert profile.setup_checks["override_reason"] == "Nur Diagnose"


def test_overlay_marks_exact_patches_search_windows_edges_and_legend(tmp_path, monkeypatch):
    image, quad = reference_scene()
    proposal = propose_regions(image, quad)
    original_image, original_proposal = image.copy(), copy.deepcopy(proposal)
    labels = []
    put_text = cv2.putText

    def text(image, label, *args, **kwargs):
        labels.append(label)
        return put_text(image, label, *args, **kwargs)

    monkeypatch.setattr(cv2, "putText", text)
    live_setup.write_overlays(image, quad, live_setup.LATTICE_GRID, tmp_path, tracking_proposal=proposal)
    overlay = cv2.imread(str(tmp_path / "overlay_source.png"))
    cfg = proposal.config
    for region in proposal.regions:
        x, y = region.centre
        h = region.size // 2
        r = h + cfg["search_radius_px"] + cfg["interpolation_guard_px"]
        assert not np.array_equal(overlay[y-h, x-h], image[y-h, x-h])
        assert not np.array_equal(overlay[y-r, x-r], image[y-r, x-r])
    for edge in proposal.edges:
        x, y = np.rint(edge.point).astype(int)
        assert not np.array_equal(overlay[y, x], image[y, x])
    assert any("Rahmenbereiche" in label for label in labels)
    assert any("Suchfenster" in label for label in labels)
    assert any("LCD-Rand" in label for label in labels)
    assert proposal == original_proposal
    np.testing.assert_array_equal(image, original_image)


def test_repeated_attempt_number_gets_a_fresh_proposal_revision(tmp_path):
    _, _, first = _propose(tmp_path)
    _, _, second = _propose(tmp_path)
    assert first["setup_attempt"] == second["setup_attempt"] == 2
    assert first["live_tracking"]["proposal_revision"] != second["live_tracking"]["proposal_revision"]


def test_harvest_proposal_keeps_checks_confirmation_and_overlay_bytes(tmp_path, monkeypatch):
    """Harvest's default call must never propose or draw live tracking regions."""
    image, quad = reference_scene()
    image[:] = 120  # Live tracking would fail on this still.
    frame = tmp_path / "still.png"
    cv2.imwrite(str(frame), image)
    fit = SimpleNamespace(quad=quad, assigned_points=[], rejected_points=[])
    expected_checks = {"overall": "OK", "checks": {"rasterversatz": {"status": "OK"}}}
    checks = SimpleNamespace(overall="OK", checks={"kanten": SimpleNamespace(cells=[])},
                             to_dict=lambda: copy.deepcopy(expected_checks))

    def forbidden(*args, **kwargs):
        pytest.fail("Harvest must not propose tracking regions")

    monkeypatch.setattr(live_setup, "propose_regions", forbidden)
    proposal = live_setup.propose_with_fit(
        image, fit=fit, frame_path=frame, camera_settings=replace(_CAMERA, size=image.shape[1::-1]),
        device_id="gsv", session_id="harvest", out_dir=tmp_path,
        offset_check=SimpleNamespace(status="OK"), final_checks=checks,
    )
    assert "live_tracking" not in proposal
    assert proposal["setup_checks"] == expected_checks
    profile = live_setup.confirm_proposal(proposal, confirmed_by="Tester", resolution_threshold_px=2.6)
    assert profile.live_tracking is None
    baseline = tmp_path / "before-r13-2"
    baseline.mkdir()
    overlays = live_setup.write_overlays(image, quad, live_setup.LATTICE_GRID, baseline,
                                         fit=fit, overall="OK", edge_cells=())
    assert overlays
    for overlay in overlays:
        assert (tmp_path / overlay.name).read_bytes() == overlay.read_bytes()
