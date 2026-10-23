import copy
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from frame_tracking_helpers import reference_scene, tracking_block
from test_live_setup import _CAMERA, _proposal

from dispread.live import setup as live_setup
from dispread.live.frame_tracking import RegionProposal, propose_regions


def _propose(tmp_path, *, blank=False, live_tracking=True, assigned_points=(), rejected_points=(), edge_cells=(),
             stability=False, cell_text=None):
    image, quad = reference_scene()
    if blank:
        image[:] = 120
    frame = tmp_path / "still.png"
    cv2.imwrite(str(frame), image)
    fit = SimpleNamespace(quad=quad, assigned_points=assigned_points, rejected_points=rejected_points)
    checks = SimpleNamespace(
        overall="OK", checks={"kanten": SimpleNamespace(cells=edge_cells)},
        to_dict=lambda: {"overall": "OK", "checks": {"rasterversatz": {"status": "OK"}}},
    )
    proposal = live_setup.propose_with_fit(
        image, fit=fit, frame_path=frame, camera_settings=replace(_CAMERA, size=image.shape[1::-1]),
        device_id="gsv", session_id="session", out_dir=tmp_path,
        offset_check=SimpleNamespace(status="OK"), final_checks=checks, setup_attempt=2, live_tracking=live_tracking,
        stability_image_bgr=image.copy() if stability else None,
        cell_text=cell_text,
    )
    return image, quad, proposal


def test_region_edits_preserve_lattice_evidence_after_proposal_reload(tmp_path):
    assigned = [[500, 375], [600, 410], [700, 445]]
    rejected = [[550, 390], [650, 425]]
    _, _, proposal = _propose(tmp_path, assigned_points=assigned, rejected_points=rejected, edge_cells=(2, 7))
    original = cv2.imread(str(tmp_path / 'overlay_source.png'))
    sampling = tmp_path / 'overlay_sampling.png'
    sampling_bytes, sampling_mtime = sampling.read_bytes(), sampling.stat().st_mtime_ns
    # Editing must also work from the serialized proposal, without the original fit object.
    proposal = json.loads((tmp_path / 'proposal.json').read_text())
    unchanged = np.ones(original.shape[:2], dtype=bool)
    block = proposal['live_tracking']
    for region in block['proposal']['regions']:
        x, y = region['centre']
        radius = region['size'] // 2 + block['config']['search_radius_px'] + block['config']['interpolation_guard_px']
        unchanged[y-radius:y+radius+1, x-radius:x+radius+1] = False
    for index in (0, 1):
        proposal = live_setup.edit_regions(proposal, add=[], remove=[index], out_dir=tmp_path,
                                           at_utc='2026-10-21T10:00:00+00:00')
        edited = cv2.imread(str(tmp_path / 'overlay_source.png'))
        assert proposal['setup_checks']['overall'] == 'OK'
        for x, y in assigned + rejected:
            np.testing.assert_array_equal(edited[y-3:y+4, x-3:x+4], original[y-3:y+4, x-3:x+4])
        np.testing.assert_array_equal(edited[:26, :150], original[:26, :150])  # Verdict label.
        # Outside the original region windows, every pixel (including the yellow quad) is preserved.
        np.testing.assert_array_equal(edited[unchanged], original[unchanged])
        assert not np.array_equal(edited, original)  # Removed regions really disappear.
        assert sampling.read_bytes() == sampling_bytes
        assert sampling.stat().st_mtime_ns == sampling_mtime


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


def test_automatic_regions_record_selection_origin(tmp_path):
    _, _, proposal = _propose(tmp_path)
    assert proposal['live_tracking']['auswahl'] == 'automatisch'
    assert proposal['live_tracking']['edits'] == []


def test_region_edit_without_overlay_evidence_requires_new_setup_without_writes(tmp_path):
    _, _, proposal = _propose(tmp_path)
    del proposal['overlay_evidence']
    original = copy.deepcopy(proposal)
    artifacts = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    with pytest.raises(live_setup.SetupError, match='Vorschlag ohne Overlay-Belege - neu einrichten'):
        live_setup.edit_regions(proposal, add=[], remove=[0], out_dir=tmp_path, at_utc='2026-10-21T10:00:00+00:00')
    assert proposal == original
    assert {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == artifacts


def test_region_edit_persists_requested_and_snapped_centres(tmp_path):
    _, _, proposal = _propose(tmp_path)
    centre = proposal['live_tracking']['proposal']['regions'][0]['centre']
    requested = [centre[0]-1, centre[1]]
    updated = live_setup.edit_regions(proposal, add=[requested], remove=[0], out_dir=tmp_path,
                                       at_utc='2026-10-21T10:00:00+00:00')
    persisted = json.loads((tmp_path / 'proposal.json').read_text())
    for result in (updated['live_tracking']['edits'][-1],
                   persisted['live_tracking']['proposal']['metrics']['centre_results'][-1]):
        assert result['requested_centre'] == requested
        assert result['used_centre'] == centre
        assert result['centre'] == centre
        assert result['ok']


@pytest.mark.parametrize(('requested', 'centre', 'initial_remove'), [
    ([314, 251], [314, 248], [0]),  # Snapping again would move this to (312,247).
    ([524, 467], [524, 464], []),  # Snapping again would reject (526,464) as ambiguous.
])
def test_kept_manual_centre_stays_exact_through_unrelated_remove_and_add(tmp_path, requested, centre, initial_remove):
    _, _, proposal = _propose(tmp_path)
    proposal = live_setup.edit_regions(proposal, add=[requested], remove=initial_remove, out_dir=tmp_path,
                                       at_utc='2026-10-21T10:00:00+00:00')
    regions = proposal['live_tracking']['proposal']['regions']
    assert regions[-1]['centre'] == centre
    assert proposal['live_tracking']['edits'][-1]['ok']
    removed = regions[0]['centre']
    expected = [region['centre'] for region in regions[1:]]

    # Reload between edits, as another request does: no in-memory provenance is needed.
    proposal = json.loads((tmp_path / 'proposal.json').read_text())
    proposal = live_setup.edit_regions(proposal, add=[], remove=[0], out_dir=tmp_path,
                                       at_utc='2026-10-21T10:00:01+00:00')
    assert [region['centre'] for region in proposal['live_tracking']['proposal']['regions']] == expected
    assert proposal['live_tracking']['proposal']['metrics']['centre_results'][-1] == {
        'requested_centre': centre, 'centre': centre, 'used_centre': centre, 'ok': True, 'reason': None,
    }

    proposal = json.loads((tmp_path / 'proposal.json').read_text())
    proposal = live_setup.edit_regions(proposal, add=[[removed[0]-1, removed[1]]], remove=[], out_dir=tmp_path,
                                       at_utc='2026-10-21T10:00:02+00:00')
    assert proposal['live_tracking']['edits'][-1]['ok']
    assert [region['centre'] for region in proposal['live_tracking']['proposal']['regions']] == expected + [removed]
    persisted = json.loads((tmp_path / 'proposal.json').read_text())
    assert persisted['live_tracking']['proposal'] == proposal['live_tracking']['proposal']


def test_kept_automatic_centres_stay_exact_through_remove_and_add(tmp_path):
    _, _, proposal = _propose(tmp_path)
    original = proposal['live_tracking']['proposal']['regions']
    removed = original[0]['centre']
    for add, remove, expected in (([], [0], original[1:]), ([removed], [], original[1:] + original[:1])):
        proposal = live_setup.edit_regions(proposal, add=add, remove=remove, out_dir=tmp_path,
                                           at_utc='2026-10-21T10:00:00+00:00')
        assert proposal['live_tracking']['proposal']['regions'] == expected
        assert all(result['ok'] and result['requested_centre'] == result['used_centre']
                   for result in proposal['live_tracking']['proposal']['metrics']['centre_results'])


@pytest.mark.parametrize(('centre', 'reason'), [([1, 1], 'am_bildrand'), ([291, 247], 'zu_wenig_struktur')])
def test_failed_kept_centre_is_reported_without_moving_or_writing(tmp_path, centre, reason):
    _, _, proposal = _propose(tmp_path)
    # Simulate inconsistent stored evidence: a kept centre must fail explicitly,
    # even when a nearby snapped centre would pass on the same image.
    proposal['live_tracking']['proposal']['regions'][0]['centre'] = centre
    original = copy.deepcopy(proposal)
    artifacts = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    with pytest.raises(live_setup.SetupError, match=rf'Beibehaltener Rahmenbereich 0.*{reason}') as error:
        live_setup.edit_regions(proposal, add=[], remove=[1], out_dir=tmp_path, at_utc='2026-10-21T10:00:00+00:00')
    assert str(centre) in str(error.value)
    assert proposal == original
    assert {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == artifacts


@pytest.mark.parametrize('other_status', ['WARNUNG', 'FEHLER'])
def test_region_edits_preserve_other_failed_or_warning_checks(tmp_path, other_status):
    _, _, proposal = _propose(tmp_path)
    proposal['setup_checks']['checks']['gegenlesen'] = {'status': other_status}
    proposal['setup_checks']['overall'] = other_status
    updated = live_setup.edit_regions(proposal, add=[], remove=[0], out_dir=tmp_path,
                                       at_utc='2026-10-21T10:00:00+00:00')
    assert updated['setup_checks']['overall'] == other_status
    assert updated['setup_checks']['checks']['gegenlesen']['status'] == other_status
    assert proposal['live_tracking']['auswahl'] == 'automatisch'
    assert proposal['live_tracking']['edits'] == []  # Eingabe bleibt unveraendert.


def test_region_edit_limit_includes_rejected_attempts_and_accepts_50th(tmp_path):
    _, _, proposal = _propose(tmp_path)
    proposal['live_tracking']['edits'] = [{'action': 'add'}] * 49
    updated = live_setup.edit_regions(proposal, add=[[1, 1]], remove=[], out_dir=tmp_path,
                                       at_utc='2026-10-21T10:00:00+00:00')
    assert len(updated['live_tracking']['edits']) == 50
    assert updated['live_tracking']['edits'][-1]['reason'] == 'zu_wenig_struktur'
    with pytest.raises(live_setup.SetupError, match='50'):
        live_setup.edit_regions(updated, add=[], remove=[0], out_dir=tmp_path, at_utc='2026-10-21T10:00:01+00:00')


def test_region_count_limit_accepts_24_requested_centres_but_refuses_25(tmp_path):
    _, _, proposal = _propose(tmp_path)
    assert len(proposal['live_tracking']['proposal']['regions']) == 12
    updated = live_setup.edit_regions(proposal, add=[[1, 1]] * 12, remove=[], out_dir=tmp_path,
                                       at_utc='2026-10-21T10:00:00+00:00')
    assert len(updated['live_tracking']['proposal']['metrics']['centre_results']) == 24
    with pytest.raises(live_setup.SetupError, match='24'):
        live_setup.edit_regions(proposal, add=[[1, 1]] * 13, remove=[], out_dir=tmp_path,
                                at_utc='2026-10-21T10:00:00+00:00')


@pytest.mark.parametrize('point', [
    [-1, 100], [-0.1, 100], [100, -1], [100, -0.1],
    [1280, 100], [100, 780], [1e300, 100], [100, 1e300], [-1e300, 100], [100, -1e300],
])
def test_region_edits_reject_outside_source_before_storing_anything(tmp_path, point):
    _, _, proposal = _propose(tmp_path)
    original = copy.deepcopy(proposal)
    files = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    # A valid first point must not be stored either when any point is invalid.
    with pytest.raises(live_setup.SetupError, match='ausserhalb.*Quellbild'):
        live_setup.edit_regions(proposal, add=[[1, 1], point], remove=[], out_dir=tmp_path,
                                at_utc='2026-10-21T10:00:00+00:00')
    assert proposal == original
    assert {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == files


def test_displayfehler_only_in_live_proposal_and_uses_all_stills(tmp_path):
    _, _, live = _propose(tmp_path, stability=True)
    check = live['setup_checks']['checks']['displayfehler']
    assert check['status'] == 'OK'
    assert check['metrics']['stills'] == 2
    _, _, harvest = _propose(tmp_path, live_tracking=False)
    assert 'displayfehler' not in harvest['setup_checks']['checks']


def test_displayfehler_receives_known_blank_setup_cells(tmp_path, monkeypatch):
    from dispread.setup_checks import CheckResult

    def check(images, quad, *, grid, cell_text):
        assert len(images) == 2
        assert cell_text == '+ 1.23?5 '
        return CheckResult('OK', {'defects': [], 'stills': len(images)})

    monkeypatch.setattr(live_setup, 'display_defect_check', check)
    _propose(tmp_path, stability=True, cell_text='+ 1.23?5 ')
