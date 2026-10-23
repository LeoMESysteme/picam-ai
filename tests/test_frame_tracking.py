"""Rahmenstruktur statt wechselnder Zeichen; ausschliesslich feste Testbilder."""

import json
import os
from pathlib import Path
from statistics import median
from time import perf_counter

import cv2
import numpy as np
import pytest

from dispread.live.frame_tracking import FrameTracker, FrameTrackingConfig, propose_regions
from dispread.track import QuadTracker

FIXTURES = Path(__file__).parent / "fixtures" / "r13"


@pytest.fixture(scope="module")
def scene():
    metadata = json.loads((FIXTURES / "r13-fixtures.json").read_text())
    reference = cv2.imread(str(FIXTURES / "reference.jpg"))
    quad = np.asarray(metadata["quad"])
    config = FrameTrackingConfig()
    proposal = propose_regions(reference, quad, config)
    assert proposal.ok, (proposal.reasons, proposal.metrics)
    return reference, quad, config, proposal, FrameTracker(reference, quad, proposal, config)


def close_quad(result, expected, tolerance=1.0):
    assert result.quad is not None, result
    assert np.max(np.linalg.norm(np.asarray(result.quad) - expected, axis=1)) <= tolerance
    assert 0 <= result.score <= 1


def mask_polygon(image, polygon):
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.rint(polygon).astype(np.int32)], 255)
    return mask != 0


@pytest.mark.parametrize("factor", ["1_0", "2_0", "0_5", "5_0", "10_0"])
def test_faktorwechsel_bleibt_geometrisch_stabil(scene, factor):
    _, quad, _, _, tracker = scene
    close_quad(tracker.update(cv2.imread(str(FIXTURES / f"faktor-{factor}.jpg"))), quad)


@pytest.mark.parametrize("factor", ["1_0", "2_0", "0_5", "5_0", "10_0"])
@pytest.mark.parametrize("change", ["brightness_0.8", "brightness_0.7", "blur_3x3"])
def test_freeze_licht_und_schaerfe(scene, factor, change):
    _, quad, _, _, tracker = scene
    image = cv2.imread(str(FIXTURES / f"faktor-{factor}.jpg"))
    if change == "blur_3x3":
        image = cv2.GaussianBlur(image, (3, 3), 0)
    else:
        image = (image.astype(float) * float(change.split("_")[1])).astype(np.uint8)
    close_quad(tracker.update(image), quad)


def _freeze_lcd(strong_sides):
    # 20 Graustufen sind oberhalb der harten 18er-Grenze, aber nicht stark.
    image = np.full((400, 600), 80, np.uint8)
    image[100:300, 100:500] = 100
    if 0 in strong_sides:
        image[:100] = 20
    if 1 in strong_sides:
        image[:, 500:] = 20
    if 2 in strong_sides:
        image[300:] = 20
    if 3 in strong_sides:
        image[:, :100] = 20
    quad = np.array([[130, 130], [470, 130], [470, 270], [130, 270]], dtype=float)
    return image, quad


@pytest.mark.parametrize("strong_sides", [[], [0, 2]])
def test_freeze_schwache_oder_nur_parallele_seiten_ungeeignet(strong_sides):
    image, quad = _freeze_lcd(strong_sides)
    proposal = propose_regions(image, quad)
    assert not proposal.ok
    assert "lcd_rand_fehlt" in proposal.reasons
    assert proposal.metrics["edge_sides_strong"] == strong_sides
    assert proposal.metrics["edge_sides_weak"] == [side for side in range(4) if side not in strong_sides]
    assert proposal.metrics["edge_points_per_side"] == [18 if side in strong_sides else 0 for side in range(4)]
    assert all(edge.magnitude >= 36 for edge in proposal.edges)


def test_freeze_schwache_seite_mit_einzelnen_starken_punkten_ignoriert():
    image, quad = _freeze_lcd([0, 1, 3])
    image[300:, 210:250] = 20
    proposal = propose_regions(image, quad)
    assert proposal.metrics["edge_sides_strong"] == [0, 1, 3]
    assert proposal.metrics["edge_sides_weak"] == [2]
    assert 0 < proposal.metrics["edge_points_per_side"][2] < 6
    tracker = FrameTracker(image, quad, proposal)
    changed = image.copy()
    changed[300:, 210:250] = 80
    assert tracker._edges_visible(changed, np.eye(2), np.zeros(2))


def test_freeze_alle_starken_seiten_bleiben_pflicht():
    image, quad = _freeze_lcd([0, 1, 2, 3])
    proposal = propose_regions(image, quad)
    assert proposal.metrics["edge_sides_strong"] == [0, 1, 2, 3]
    tracker = FrameTracker(image, quad, proposal)
    changed = image.copy()
    changed[290:310, 100:500] = 100
    assert not tracker._edges_visible(changed, np.eye(2), np.zeros(2))


def test_kandidat_lcd_rand_erlaubt_lichtabhaengige_kantenlage():
    image, quad = _freeze_lcd([0, 1, 3])
    tracker = FrameTracker(image, quad, propose_regions(image, quad))
    # Nur die Grauwertkante wandert; die vorhergesagte Geometrie bleibt gleich.
    changed = cv2.warpAffine(image, np.float32([[1, 0, 2], [0, 1, 0]]), image.shape[1::-1])
    assert tracker._edges_visible(changed, np.eye(2), np.zeros(2))


@pytest.mark.parametrize("factor", ["2_0", "5_0"])
def test_ecc_reproduziert_inhaltsabhaengigen_verlust(scene, factor):
    reference, quad, *_ = scene
    result = QuadTracker(reference, quad).update(cv2.imread(str(FIXTURES / f"faktor-{factor}.jpg")))
    assert result.quad is None
    assert result.reason == "low_score"


def test_kleine_verschiebung_und_drehung(scene):
    reference, quad, _, _, tracker = scene
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), 0.5, 1)
    matrix[:, 2] += (6, -3)
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    expected = cv2.transform(quad.reshape(-1, 1, 2), matrix).reshape(-1, 2)
    close_quad(tracker.update(moved), expected, 2)


@pytest.mark.parametrize("display_moves", [True, False])
def test_display_und_hintergrund_getrennt(scene, display_moves):
    reference, quad, _, proposal, tracker = scene
    matrix = np.float32([[1, 0, 6], [0, 1, -3]])
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    inside = mask_polygon(reference, proposal.outer_limit)
    image = reference.copy()
    image[inside if display_moves else ~inside] = moved[inside if display_moves else ~inside]
    close_quad(tracker.update(image), quad + ((6, -3) if display_moves else (0, 0)), 2)


@pytest.mark.parametrize("hidden", [False, True])
def test_zeichenbereich_hat_keinen_einfluss(scene, hidden):
    reference, quad, _, proposal, tracker = scene
    image = reference.copy()
    zone = mask_polygon(image, proposal.character_zone)
    # Verdeckte Zeichen muss der Leser ablehnen; Rahmentracking darf funktionieren.
    other = cv2.imread(str(FIXTURES / "faktor-5_0.jpg"))
    image[zone] = 120 if hidden else other[zone]
    close_quad(tracker.update(image), quad)


def test_teilverdeckung_niemals_falsche_geometrie(scene):
    reference, quad, config, proposal, tracker = scene
    image = reference.copy()
    for region in proposal.regions[:2]:
        x, y = map(int, region.centre)
        r = config.patch_size // 2 + config.search_radius_px + 2
        image[y-r:y+r+1, x-r:x+r+1] = 0
    # Zwei echte Rahmenfenster verdeckt; ausreichend verteilte Merkmale bleiben.
    close_quad(tracker.update(image), quad)


def test_verdeckung_und_bewegung_ausserhalb_suche(scene):
    reference, _, config, _, tracker = scene
    assert tracker.update(np.zeros_like(reference)).quad is None
    matrix = np.float32([[1, 0, config.search_radius_px * 4], [0, 1, 0]])
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    assert tracker.update(moved).quad is None


@pytest.mark.parametrize("repeated", [False, True])
def test_ungeeignete_struktur_wird_abgelehnt(repeated):
    yy, xx = np.indices((400, 800))
    image = (((xx // 4 + yy // 4) % 2) * 200).astype(np.uint8) if repeated else np.full((400, 800), 100, np.uint8)
    proposal = propose_regions(image, ((200, 170), (600, 170), (600, 230), (200, 230)), FrameTrackingConfig())
    assert not proposal.ok
    assert "zu_wenig_rahmenbereiche" in proposal.reasons


def test_raumlicht_aus_niemals_falsche_geometrie(scene):
    reference, quad, _, proposal, tracker = scene
    image = reference.astype(float)
    # Das gespeicherte LCD-Randmodell begrenzt die weiterhin beleuchtete Glasflaeche.
    glass = cv2.convexHull(np.float32([edge.point for edge in proposal.edges])).reshape(-1, 2)
    outside = ~mask_polygon(reference, glass)
    image[outside] *= 0.2
    image += np.random.default_rng(13).normal(0, 2, image.shape)
    result = tracker.update(np.clip(image, 0, 255).astype(np.uint8))
    if result.quad is not None:
        close_quad(result, quad, 2)


def test_zustandslos_nach_verlust(scene):
    reference, quad, config, proposal, tracker = scene
    tracker.update(np.zeros_like(reference))
    assert tracker.update(reference) == FrameTracker(reference, quad, proposal, config).update(reference)


def test_alle_gelesenen_suchpixel_sind_sicher(scene):
    reference, _, config, proposal, _ = scene
    allowed = mask_polygon(reference, proposal.outer_limit) & ~mask_polygon(reference, proposal.character_zone)
    r = config.patch_size // 2 + config.search_radius_px + 1
    for region in proposal.regions:
        x, y = map(int, region.centre)
        assert allowed[y-r:y+r+1, x-r:x+r+1].all()


def test_lcd_rand_unabhaengig_erforderlich(scene):
    reference, _, config, proposal, tracker = scene
    image = np.zeros_like(reference)
    # Alle Matchingfenster exakt erhalten, den uebrigen LCD-Rand verdecken.
    r = config.patch_size // 2 + config.search_radius_px + 1
    for region in proposal.regions:
        x, y = map(int, region.centre)
        image[y-r:y+r+1, x-r:x+r+1] = reference[y-r:y+r+1, x-r:x+r+1]
    result = tracker.update(image)
    assert result.quad is None
    assert result.reason == "lcd_rand_fehlt"


@pytest.mark.skipif("CI" in os.environ, reason="Pi-Laufzeit nur ausserhalb CI")
def test_laufzeit_unter_10_ms(scene):
    reference, _, _, _, tracker = scene
    tracker.update(reference)
    times = []
    for _ in range(31):
        start = perf_counter()
        tracker.update(reference)
        times.append((perf_counter() - start) * 1000)
    elapsed = median(times)
    print(f"Rahmentracker Median: {elapsed:.3f} ms")
    assert elapsed < 10


def test_neue_gruende_haben_bedientexte():
    from dispread.workbench.fields import REASONS

    reasons = {"zu_wenig_rahmenbereiche", "rahmenbereiche_einseitig", "zu_wenig_rahmenmerkmale",
               "rahmen_mehrdeutig", "rahmen_unstimmig", "lcd_rand_fehlt", "rahmenbereiche_ohne_reserve",
               "bildgroesse_abweichend", "vorschlag_ungeeignet"}
    assert reasons <= REASONS.keys()
    assert all(REASONS[reason][0].islower() for reason in reasons)


@pytest.mark.parametrize("changes", [
    {"patch_size": 14}, {"search_radius_px": 0}, {"min_peak": 0}, {"ambiguity_limit": 1},
    {"min_regions": 1}, {"min_spread_px": 0}, {"edge_required_sides": 0},
    {"edge_required_share": 0}, {"edge_magnitude_fraction": 0}, {"edge_min_points_per_side": 0},
    {"ransac_tolerance_px": 0}, {"max_shift_px": -1}, {"max_rotation_deg": -1},
    {"interpolation_guard_px": 0}, {"edge_min_offset_px": 10},
])
def test_ungueltige_pruefgrenzen_werden_abgelehnt(changes):
    with pytest.raises(ValueError):
        FrameTrackingConfig(**changes)


def test_vorschlag_liefert_streuungszahlen(scene):
    _, _, _, proposal, _ = scene
    assert len(proposal.metrics["local_min_px"]) == len(proposal.metrics["local_max_px"]) == 2
    assert min(proposal.metrics["local_max_px"]) >= 20
    assert max(proposal.metrics["local_min_px"]) <= -20


@pytest.mark.parametrize("kind,expected_reason", [("shift", "shift_out_of_bounds"), ("rotation", "rotation_out_of_bounds")])
def test_bewegungsgrenzen_werden_durchgesetzt(scene, kind, expected_reason):
    reference, quad, _, _, _ = scene
    config = FrameTrackingConfig(max_shift_px=2) if kind == "shift" else FrameTrackingConfig(max_rotation_deg=0.2)
    proposal = propose_regions(reference, quad, config)
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), 0 if kind == "shift" else 0.5, 1)
    if kind == "shift":
        matrix[:, 2] += (6, -3)
    image = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    result = FrameTracker(reference, quad, proposal, config).update(image)
    assert result.quad is None
    assert result.reason == expected_reason


def test_bewegung_knapp_ausserhalb_suchfenster_wird_abgelehnt(scene):
    reference, _, config, _, tracker = scene
    matrix = np.float32([[1, 0, config.search_radius_px + 1], [0, 1, 0]])
    image = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    assert tracker.update(image).quad is None


@pytest.mark.parametrize("dy", [2.0, 2.5, 3.0])
def test_einzelner_verschobener_fernseitiger_inlier_kippt_quad_nicht(scene, dy):
    # rev4: alle rechten Fenster bis auf den fernsten gewaehlten Hebel verdeckt.
    reference, quad, config, proposal, tracker = scene
    image = reference.copy()
    radius = config.patch_size // 2 + config.search_radius_px
    from dispread.live.frame_tracking import _axes

    local_sources = (tracker.sources - quad.mean(axis=0)) @ _axes(quad).T
    anchor = tuple(tracker.sources[np.argmax(local_sources[:, 0])].astype(int))
    assert local_sources[:, 0].max() >= config.min_spread_px
    for region in proposal.regions:
        x, y = region.centre
        local = (np.array([x, y]) - quad.mean(axis=0)) @ _axes(quad).T
        if local[0] >= config.min_spread_px and (x, y) != anchor:
            image[y-radius:y+radius+1, x-radius:x+radius+1] = 128
    x, y = anchor
    window = reference[y-radius-5:y+radius+6, x-radius-5:x+radius+6]
    shifted = cv2.warpAffine(window, np.float32([[1, 0, 0], [0, 1, dy]]), window.shape[1::-1],
                             borderMode=cv2.BORDER_REPLICATE)
    image[y-radius:y+radius+1, x-radius:x+radius+1] = shifted[5:-5, 5:-5]
    result = tracker.update(image)
    if result.quad is not None:
        close_quad(result, quad)
    else:
        assert result.reason == "rahmen_unstimmig"


@pytest.mark.slow
@pytest.mark.parametrize("scenario", ["rev2", "local_shift"])
def test_seed_verdeckung_und_bewegung_niemals_mehr_als_ein_pixel(scene, scenario):
    reference, quad, config, proposal, tracker = scene
    rng = np.random.default_rng(0)
    kept = 0
    for trial in range(300):
        image = reference.copy()
        for index in rng.choice(len(proposal.regions), rng.integers(1, 9), replace=False):
            x, y = proposal.regions[index].centre
            if scenario == "rev2":
                dx, dy = rng.integers(-8, 9, 2)
                image[y+dy-6:y+dy+6, x+dx-6:x+dx+6] = int(rng.integers(0, 256))
            else:
                radius = config.patch_size // 2 + config.search_radius_px
                if rng.random() < 0.5:
                    image[y-radius:y+radius+1, x-radius:x+radius+1] = int(rng.integers(0, 256))
                else:
                    window = reference[y-radius-5:y+radius+6, x-radius-5:x+radius+6]
                    dx, dy = rng.uniform(-4, 4, 2)
                    shifted = cv2.warpAffine(window, np.float32([[1, 0, dx], [0, 1, dy]]), window.shape[1::-1])
                    image[y-radius:y+radius+1, x-radius:x+radius+1] = shifted[5:-5, 5:-5]
        angle_limit, shift_limit = (1, 6) if scenario == "rev2" else (2.5, 10)
        matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), float(rng.uniform(-angle_limit, angle_limit)), 1)
        matrix[:, 2] += rng.uniform(-shift_limit, shift_limit, 2)
        moved = cv2.warpAffine(image, matrix, image.shape[1::-1])
        expected = cv2.transform(quad.reshape(-1, 1, 2), matrix).reshape(-1, 2)
        result = tracker.update(moved)
        if result.quad is not None:
            error = float(np.linalg.norm(np.asarray(result.quad) - expected, axis=1).max())
            assert error <= 1.0, (scenario, trial, error, result)
            kept += 1
    assert kept > 0  # Ein Tracker, der alles ablehnt, erfuellt diese Regression nicht.


def test_jeder_inlier_muss_stabilen_fit_tragen(scene, monkeypatch):
    # Isoliert die Leave-one-out-Regel: genug Streuung, aber ein einflussreicher Treffer.
    from dispread.live import frame_tracking as ft

    reference, _, _, _, tracker = scene
    target = tracker.sources.copy()
    target[1] += (0, 2)
    original_peak = ft._peak
    calls = iter(enumerate(target - tracker.sources + tracker.config.search_radius_px))

    def biased_peak(response, config):
        _, peak, ambiguous = original_peak(response, config)
        index, position = next(calls)
        return position, peak if index in (0, 1, 2, 3, 4, 7) else 0.0, ambiguous

    monkeypatch.setattr(ft, "_peak", biased_peak)
    result = tracker.update(reference)
    assert result.quad is None
    assert result.reason == "rahmen_unstimmig"


def _force_region_targets(monkeypatch, tracker, targets):
    from dispread.live import frame_tracking as ft

    positions = iter(targets - tracker.sources + tracker.config.search_radius_px)
    monkeypatch.setattr(ft, "_peak", lambda response, config: (next(positions), 1.0, False))


@pytest.mark.parametrize("kind", ["rms", "max"])
def test_kandidat_unstimmige_inlier_trotz_stabilem_fit_ablehnen(scene, monkeypatch, kind):
    from dispread.live import frame_tracking as ft

    reference, _, config, _, tracker = scene
    target = tracker.sources.copy()
    if kind == "rms":
        target[:, 1] += np.where(np.arange(len(target)) % 2, 0.5, -0.5)
    else:
        target[0, 1] += 0.8
    rotation, translation, inliers = ft._ransac(tracker.sources, target, config)
    assert inliers.all()
    residuals = np.linalg.norm(tracker.sources @ rotation.T + translation - target, axis=1)
    rms, maximum = np.sqrt(np.mean(residuals**2)), residuals.max()
    assert (rms > 0.35 and maximum < 0.65) if kind == "rms" else (rms < 0.35 and maximum > 0.65)
    # Streuung und Leave-one-out bestehen: erst die neue Residualregel lehnt ab.
    expected = tracker.quad @ rotation.T + translation
    for index in range(len(target)):
        keep = np.arange(len(target)) != index
        r, t = ft._rigid(tracker.sources[keep], target[keep])
        assert np.linalg.norm(tracker.quad @ r.T + t - expected, axis=1).max() < 0.5
    _force_region_targets(monkeypatch, tracker, target)
    result = tracker.update(reference)
    assert result.quad is None
    assert result.reason == "rahmen_unstimmig"


@pytest.mark.parametrize("dx,dy,angle", [(3.5, 0, 0), (0, 3.5, 0), (0, 0, 1.0)])
def test_kandidat_einstimmige_falsche_bewegung_direkt_ablehnen(scene, monkeypatch, dx, dy, angle):
    reference, quad, _, _, tracker = scene
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
    matrix[:, 2] += (dx, dy)
    target = tracker.sources @ matrix[:, :2].T + matrix[:, 2]
    _force_region_targets(monkeypatch, tracker, target)
    result = tracker.update(reference)
    assert result.quad is None
    assert result.reason == "lcd_rand_fehlt"


@pytest.mark.parametrize("field", ["max_inlier_rms_px", "max_inlier_residual_px"])
@pytest.mark.parametrize("value", [0.0, -0.1, float("nan"), float("inf")])
def test_kandidat_residualgrenzen_muessen_endlich_positiv_sein(field, value):
    with pytest.raises(ValueError):
        FrameTrackingConfig(**{field: value})


@pytest.mark.parametrize("field", ["max_inlier_rms_px", "max_inlier_residual_px"])
@pytest.mark.parametrize("margin", [-1e-6, 0.0, 1e-6])
def test_kandidat_residualgrenzen_sind_inklusiv(scene, monkeypatch, field, margin):
    from dataclasses import replace

    from dispread.live import frame_tracking as ft

    reference, quad, config, _, tracker = scene
    target = tracker.sources.copy()
    target[:, 1] += np.where(np.arange(len(target)) % 2, 0.5, -0.5)
    rotation, translation, inliers = ft._ransac(tracker.sources, target, config)
    assert inliers.all()
    residuals = np.linalg.norm(tracker.sources @ rotation.T + translation - target, axis=1)
    threshold = np.sqrt(np.mean(residuals**2)) if field == "max_inlier_rms_px" else residuals.max()
    config = replace(config, max_inlier_rms_px=1.0, max_inlier_residual_px=1.0)
    config = replace(config, **{field: float(threshold + margin)})
    proposal = propose_regions(reference, quad, config)
    tracker = FrameTracker(reference, quad, proposal, config)
    _force_region_targets(monkeypatch, tracker, target)
    result = tracker.update(reference)
    if margin < 0:
        assert result.quad is None
        assert result.reason == "rahmen_unstimmig"
    else:
        close_quad(result, quad)


@pytest.mark.slow
def test_kandidat_zufall_bewegung_teilverdeckung_und_lokaler_bias(scene, record_property):
    from collections import Counter

    reference, quad, config, proposal, tracker = scene
    rng = np.random.default_rng(1307)
    radius = config.patch_size // 2 + config.search_radius_px
    reasons, errors = Counter(), []
    for trial in range(400):
        image = reference.copy()
        for index in rng.choice(len(proposal.regions), rng.integers(1, 9), replace=False):
            x, y = proposal.regions[index].centre
            if rng.random() < 0.5:
                dx, dy = rng.integers(-8, 9, 2)
                image[y+dy-6:y+dy+6, x+dx-6:x+dx+6] = int(rng.integers(0, 256))
            else:
                direction = rng.uniform(-np.pi, np.pi)
                bias = rng.uniform(0, 4) * np.array([np.cos(direction), np.sin(direction)])
                window = reference[y-radius-5:y+radius+6, x-radius-5:x+radius+6]
                shifted = cv2.warpAffine(window, np.float32([[1, 0, bias[0]], [0, 1, bias[1]]]),
                                         window.shape[1::-1], borderMode=cv2.BORDER_REPLICATE)
                image[y-radius:y+radius+1, x-radius:x+radius+1] = shifted[5:-5, 5:-5]
        matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), float(rng.uniform(-2.5, 2.5)), 1)
        matrix[:, 2] += rng.uniform(-10, 10, 2)
        moved = cv2.warpAffine(image, matrix, image.shape[1::-1])
        expected = quad @ matrix[:, :2].T + matrix[:, 2]
        result = tracker.update(moved)
        reasons[result.reason or "ok"] += 1
        if result.quad is not None:
            error = float(np.linalg.norm(np.asarray(result.quad) - expected, axis=1).max())
            assert error <= 1.0, (trial, error, result)
            errors.append(error)
    assert errors
    record_property("safety_sweep", json.dumps({"seed": 1307, "trials": 400, "reasons": dict(reasons),
                                               "max_accepted_corner_error_px": max(errors)}))


def _paste_region_motion(reference, proposal, radius, matrix, indices):
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    image = reference.copy()
    for index in indices:
        x, y = proposal.regions[index].centre
        image[y-radius:y+radius+1, x-radius:x+radius+1] = moved[y-radius:y+radius+1, x-radius:x+radius+1]
    return image


@pytest.mark.slow
def test_kandidat_gemeinsam_falsche_rahmenbewegung_dokumentierte_grenze(scene, record_property):
    # Physikalisch unplausibler Sonderfall rev9: alle Fenster luegen, Glas steht.
    reference, quad, config, proposal, tracker = scene
    radius = config.patch_size // 2 + config.search_radius_px
    reasons, errors, worst = {}, [], None
    for angle in np.linspace(-1.2, 1.2, 13):
        for dx in np.linspace(-4, 4, 17):
            for dy in np.linspace(-4, 4, 17):
                matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), float(angle), 1)
                matrix[:, 2] += (dx, dy)
                image = _paste_region_motion(reference, proposal, radius, matrix, range(len(proposal.regions)))
                result = tracker.update(image)
                reason = result.reason or "ok"
                reasons[reason] = reasons.get(reason, 0) + 1
                if result.quad is not None:
                    error = float(np.linalg.norm(np.asarray(result.quad) - quad, axis=1).max())
                    if not errors or error > max(errors):
                        worst = [float(angle), float(dx), float(dy)]
                    errors.append(error)
    # Die grobe Randpruefung ist ausdruecklich kein Ein-Pixel-Genauigkeitsbeleg.
    assert max(errors) > 1.0
    record_property("all_regions_wrong", json.dumps({"trials": sum(reasons.values()), "reasons": reasons,
                                                    "max_accepted_corner_error_px": max(errors),
                                                    "worst_angle_dx_dy": worst}))


@pytest.mark.parametrize("direction", ["x+", "x-", "y+", "y-", "angle+", "angle-"])
def test_kandidat_grobe_randgrenze_bei_direkter_falscher_bewegung(scene, monkeypatch, record_property, direction):
    reference, quad, _, _, tracker = scene
    rotation = direction.startswith("angle")
    sign = 1 if direction.endswith("+") else -1
    values = np.arange(0, 1.51, 0.01) if rotation else np.arange(0, 6.01, 0.05)
    kept, rejected = [], []
    for value in values:
        angle = sign * value if rotation else 0.0
        matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), float(angle), 1)
        if not rotation:
            matrix[0 if direction.startswith("x") else 1, 2] += sign * value
        _force_region_targets(monkeypatch, tracker, tracker.sources @ matrix[:, :2].T + matrix[:, 2])
        result = tracker.update(reference)
        if result.quad is None:
            assert result.reason == "lcd_rand_fehlt"
            rejected.append(float(value))
        else:
            kept.append(float(value))
    assert kept and rejected
    assert max(kept) < min(rejected)  # Auf diesem Raster keine spaetere Wiederannahme.
    record_property("direct_wrong_motion", json.dumps({"direction": direction, "unit": "deg" if rotation else "px",
                                                      "step": 0.01 if rotation else 0.05,
                                                      "last_kept": max(kept), "rejected_from": min(rejected),
                                                      "tested_to": float(values[-1])}))


@pytest.mark.parametrize("subset", ["right", "left", "bottom", "top"])
@pytest.mark.parametrize("axis, sign", [(0, 1), (0, -1), (1, 1), (1, -1)])
def test_kandidat_koordinierter_lokaler_bias_niemals_falsche_geometrie(scene, subset, axis, sign, record_property):
    # rev6/rev9: Eine ganze Seite meldet eine andere Bewegung als der Rest.
    from dispread.live import frame_tracking as ft

    reference, quad, config, proposal, tracker = scene
    local = (tracker.sources - quad.mean(axis=0)) @ ft._axes(quad).T
    half_axis = 0 if subset in ("right", "left") else 1
    half_sign = 1 if subset in ("right", "bottom") else -1
    indices = np.flatnonzero(half_sign * local[:, half_axis] > 20)
    radius = config.patch_size // 2 + config.search_radius_px
    errors = []
    for angle in (-0.4, 0, 0.4):
        for bias in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0):
            matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
            matrix[axis, 2] += sign * bias
            image = _paste_region_motion(reference, proposal, radius, matrix, indices)
            result = tracker.update(image)
            if result.quad is not None:
                close_quad(result, quad)
                errors.append(float(np.linalg.norm(np.asarray(result.quad) - quad, axis=1).max()))
    record_property("half_bias", json.dumps({"half": subset, "axis": axis, "sign": sign,
                                            "accepted": len(errors), "max_error_px": max(errors, default=None)}))


@pytest.mark.parametrize("dx,dy,angle", [(4.0, 0, 0), (0, 4.0, 0), (0, 0, 1.2)])
def test_lcd_rand_verwirft_falsche_bewegung(scene, dx, dy, angle):
    reference, quad, config, proposal, tracker = scene
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
    matrix[:, 2] += (dx, dy)
    gray = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    assert not tracker._edges_visible(gray, matrix[:, :2], matrix[:, 2])
    # Rahmenpatches melden die falsche Bewegung; der unabhaengige LCD-Rand bleibt.
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    image = reference.copy()
    radius = config.patch_size // 2 + config.search_radius_px
    for region in proposal.regions:
        x, y = region.centre
        image[y-radius:y+radius+1, x-radius:x+radius+1] = moved[y-radius:y+radius+1, x-radius:x+radius+1]
    result = tracker.update(image)
    assert result.quad is None
    assert result.reason == "lcd_rand_fehlt"


@pytest.mark.parametrize("angle", [-0.5, 0.5])
def test_drehvorzeichen_wie_ecc(scene, angle):
    reference, quad, _, _, tracker = scene
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    result = tracker.update(moved)
    close_quad(result, cv2.transform(quad.reshape(-1, 1, 2), matrix).reshape(-1, 2))
    # Bildkoordinaten y nach unten: positiver OpenCV-Winkel ergibt negativen Tracker-Winkel.
    assert result.rotation_deg == pytest.approx(-angle, abs=0.1)
    assert np.sign(result.rotation_deg) == np.sign(QuadTracker(reference, quad).update(moved).rotation_deg)


@pytest.mark.parametrize("order", [[3, 2, 1, 0], [3, 0, 1, 2]])
def test_quadreihenfolge_normalisiert_intern_und_erhaelt_ausgabe(scene, order):
    reference, quad, config, proposal, tracker = scene
    reordered = quad[order]
    other = propose_regions(reference, reordered, config)
    assert other.regions == proposal.regions
    assert other.edges == proposal.edges
    assert other.character_zone == proposal.character_zone
    # Auch ein fuer die kanonische Reihenfolge gebauter Vorschlag gehoert zum selben Quad.
    alternative = FrameTracker(reference, reordered, proposal, config)
    own = FrameTracker(reference, reordered, other, config)
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), 0.5, 1)
    matrix[:, 2] += (3, -2)
    moved = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    expected = np.asarray(tracker.update(moved).quad)[order]
    assert np.asarray(alternative.update(moved).quad) == pytest.approx(expected)
    assert own.update(moved) == alternative.update(moved)


@pytest.mark.parametrize("bad_quad", [
    [[0, 0], [1, 0], [2, 0], [3, 0]],
    [[0, 0], [2, 0], [0.5, 0.5], [0, 2]],
    [[0, 0], [2, 2], [2, 0], [0, 2]],
    [[0, 0], [2, 0], [2, float("nan")], [0, 2]],
    [[0, 0], [2, 0], [2, float("inf")], [0, 2]],
    [[0, 0], [2, 0], [2, 0], [0, 2]],
])
def test_ungueltiges_quad_vor_opencv_ablehnen(scene, bad_quad):
    reference, _, config, proposal, _ = scene
    with pytest.raises(ValueError):
        propose_regions(reference, bad_quad, config)
    with pytest.raises(ValueError):
        FrameTracker(reference, bad_quad, proposal, config)


@pytest.mark.parametrize("mismatch", ["image", "quad", "config", "shape"])
def test_vorschlag_an_referenz_quad_und_config_gebunden(scene, mismatch):
    from dataclasses import replace

    reference, quad, config, proposal, _ = scene
    image = reference.copy()
    if mismatch == "image":
        image[0, 0] = 0
    elif mismatch == "quad":
        quad = quad + (1, 0)
    elif mismatch == "config":
        config = replace(config, min_peak=0.8)
    elif mismatch == "shape":
        image = image[:-1]
    with pytest.raises(ValueError, match="Vorschlag"):
        FrameTracker(image, quad, proposal, config)


def test_vorschlag_speichert_herkunft(scene):
    from dataclasses import asdict
    from hashlib import sha256

    reference, quad, config, proposal, _ = scene
    assert proposal.config == asdict(config)
    assert np.array_equal(proposal.normalised_quad, quad)
    assert proposal.reference_shape == reference.shape[:2]
    assert proposal.reference_sha256 == sha256(cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY).tobytes()).hexdigest()


def test_randfenster_wird_uebersprungen_niemals_gewrappt(scene):
    from dataclasses import replace

    from dispread.live.frame_tracking import FrameRegion

    reference, quad, config, proposal, _ = scene
    border = FrameRegion((2, 2), config.patch_size)
    extended = replace(proposal, regions=(border, *proposal.regions))
    close_quad(FrameTracker(reference, quad, extended, config).update(reference), quad)
    only_border = replace(proposal, regions=(border,))
    result = FrameTracker(reference, quad, only_border, config).update(reference)
    assert result.quad is None
    assert result.reason == "zu_wenig_rahmenmerkmale"


@pytest.mark.parametrize("variant", ["gray", "bgra"])
def test_uint8_gray_bgr_bgra_identisch(scene, variant):
    reference, quad, config, proposal, tracker = scene
    image = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY if variant == "gray" else cv2.COLOR_BGR2BGRA)
    other = propose_regions(image, quad, config)
    assert other.regions == proposal.regions
    assert other.edges == proposal.edges
    assert FrameTracker(image, quad, proposal, config).update(image) == tracker.update(reference)


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.uint16])
def test_unsupported_bildtyp_eindeutig_ablehnen(scene, dtype):
    reference, quad, config, proposal, tracker = scene
    image = reference.astype(dtype)
    for operation in (lambda: propose_regions(image, quad, config),
                      lambda: FrameTracker(image, quad, proposal, config), lambda: tracker.update(image)):
        with pytest.raises(ValueError, match="uint8"):
            operation()


@pytest.mark.parametrize("bad_shape", [(20,), (20, 30, 2), (20, 30, 1), (0, 30)])
def test_unsupported_bildform_eindeutig_ablehnen(scene, bad_shape):
    reference, quad, config, _, tracker = scene
    image = np.zeros(bad_shape, np.uint8)
    with pytest.raises(ValueError):
        propose_regions(image, quad, config)
    with pytest.raises(ValueError):
        tracker.update(image)


def test_bildgroesse_und_ungeeigneter_vorschlag_mit_eigenem_grund(scene):
    from dataclasses import replace

    reference, quad, config, proposal, tracker = scene
    assert tracker.update(reference[:-1]).reason == "bildgroesse_abweichend"
    unsuitable = replace(proposal, ok=False, reasons=("lcd_rand_fehlt",))
    assert FrameTracker(reference, quad, unsuitable, config).update(reference).reason == "vorschlag_ungeeignet"


def test_vorschlag_erkennt_einseitige_rahmenbereiche(scene):
    reference, quad, config, _, _ = scene
    image = reference.copy()
    yy, xx = np.indices(image.shape[:2])
    axis = (quad[1] + quad[2] - quad[0] - quad[3]) / 2
    right = (xx-quad[:, 0].mean())*axis[0] + (yy-quad[:, 1].mean())*axis[1] > 0
    image[right] = 128
    proposal = propose_regions(image, quad, config)
    assert not proposal.ok
    assert "rahmenbereiche_einseitig" in proposal.reasons
    assert len(proposal.regions) >= config.min_regions


def test_vorschlag_erkennt_fehlenden_lcd_rand(scene):
    reference, quad, config, original, _ = scene
    image = np.zeros_like(reference)
    radius = config.patch_size // 2 + config.search_radius_px + 1
    for region in original.regions:
        x, y = region.centre
        image[y-radius:y+radius+1, x-radius:x+radius+1] = reference[y-radius:y+radius+1, x-radius:x+radius+1]
    proposal = propose_regions(image, quad, config)
    assert not proposal.ok
    assert "lcd_rand_fehlt" in proposal.reasons
    assert len(proposal.regions) >= config.min_regions


def test_proposal_json_roundtrip_preserves_fixture_results(scene):
    from dispread.live.frame_tracking import RegionProposal

    reference, quad, config, proposal, tracker = scene
    encoded = json.dumps(proposal.to_dict(), allow_nan=False)
    restored = RegionProposal.from_dict(json.loads(encoded))
    assert restored == proposal
    restored_config = FrameTrackingConfig.from_dict(json.loads(json.dumps(config.to_dict())))
    assert restored_config == config
    replay = FrameTracker(reference, quad, restored, restored_config)
    for path in sorted(FIXTURES.glob("*.jpg")):
        image = cv2.imread(str(path))
        assert replay.update(image) == tracker.update(image), path
    assert replay.update(reference * 0) == tracker.update(reference * 0)


@pytest.mark.parametrize("name,default", FrameTrackingConfig().to_dict().items())
def test_config_json_rejects_wrong_field_types(name, default):
    data = FrameTrackingConfig().to_dict()
    data[name] = float(default) if type(default) is int else int(default)
    with pytest.raises(ValueError, match="Typ"):
        FrameTrackingConfig.from_dict(data)


def test_config_json_rejects_bool_as_integer():
    data = FrameTrackingConfig().to_dict()
    data["interpolation_guard_px"] = True  # True == 1 must not pass.
    with pytest.raises(ValueError, match="Typ"):
        FrameTrackingConfig.from_dict(data)


def test_r11_proposal_preserves_frozen_lcd_model():
    saved = json.loads((FIXTURES / 'r13-r11-fixed-proposal.json').read_text())['proposal']
    image = cv2.imread(str(FIXTURES / 'reference.jpg'))
    proposal = propose_regions(image, saved['normalised_quad'])
    assert proposal.to_dict()['edges'] == saved['edges']
    assert proposal.config['ambiguity_limit'] == saved['config']['ambiguity_limit']


def test_manual_regions_preserve_automatic_checks_and_edge_model(scene):
    from dispread.live import frame_tracking

    image, quad, config, automatic, _ = scene
    centres = [region.centre for region in automatic.regions]
    manual = frame_tracking.proposal_from_regions(image, quad, centres, config)
    assert manual.regions == automatic.regions
    assert manual.edges == automatic.edges
    assert manual.ok and manual.reasons == automatic.reasons
    assert manual.reference_sha256 == automatic.reference_sha256
    assert all(result['ok'] for result in manual.metrics['centre_results'])
    fewer = frame_tracking.proposal_from_regions(image, quad, centres[:2], config)
    assert fewer.reasons == ('zu_wenig_rahmenbereiche', 'rahmenbereiche_einseitig')


@pytest.mark.parametrize('distance', [1, 2, 3])
@pytest.mark.parametrize('direction', [(1, 0), (-1, 0), (0, 1), (0, -1)])
def test_manual_regions_snap_to_real_corner(scene, distance, direction):
    from dispread.live.frame_tracking import proposal_from_regions

    image, quad, config, automatic, _ = scene
    x, y = automatic.regions[0].centre
    neighbour = (x + distance * direction[0], y + distance * direction[1])
    proposal = proposal_from_regions(image, quad, [neighbour], config)
    assert proposal.regions == automatic.regions[:1]
    assert proposal.metrics['centre_results'] == [
        {'requested_centre': list(neighbour), 'centre': [x, y], 'used_centre': [x, y], 'ok': True, 'reason': None},
    ]


def test_manual_snapping_chooses_strongest_not_nearest_local_maximum(scene):
    from dispread.live.frame_tracking import proposal_from_regions

    image, quad, config, _, _ = scene
    # Fixture has a weaker local maximum at (296,249), closer to this click.
    strength = cv2.cornerMinEigenVal(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), 3, 3)
    assert strength[249, 296] == cv2.dilate(strength, np.ones((3, 3), np.uint8))[249, 296]
    assert strength[249, 296] < strength[247, 292]
    proposal = proposal_from_regions(image, quad, [(294, 249)], config)
    assert [region.centre for region in proposal.regions] == [(292, 247)]
    assert proposal.metrics['centre_results'][0]['used_centre'] == [292, 247]


@pytest.mark.parametrize('kept', [(235, 127), (309, 150)])
def test_kept_centres_are_checked_exactly_while_new_centres_snap(scene, kept):
    from dispread.live.frame_tracking import proposal_from_regions

    image, quad, config, _, _ = scene
    proposal = proposal_from_regions(image, quad, [(899, 434)], config, kept_centres=[kept])
    assert [region.centre for region in proposal.regions] == [kept, (900, 434)]
    assert proposal.metrics['centre_results'] == [
        {'requested_centre': list(kept), 'centre': list(kept), 'used_centre': list(kept), 'ok': True, 'reason': None},
        {'requested_centre': [899, 434], 'centre': [900, 434], 'used_centre': [900, 434], 'ok': True, 'reason': None},
    ]


@pytest.mark.parametrize('offset', [(-4, 0), (-5, 0), (-6, 0), (-3, -3)])
def test_manual_regions_do_not_snap_beyond_radius_on_uniform_frame(offset):
    from dispread.live.frame_tracking import proposal_from_regions

    image = np.full((400, 800), 100, dtype=np.uint8)
    quad = ((200, 170), (600, 170), (600, 230), (200, 230))
    cv2.rectangle(image, (250, 140), (256, 146), 220, -1)
    assert proposal_from_regions(image, quad, [(250, 140)]).regions
    result = proposal_from_regions(image, quad, [(250+offset[0], 140+offset[1])])
    assert not result.regions
    assert result.metrics['centre_results'][0]['reason'] == 'zu_wenig_struktur'
    assert result.metrics['centre_results'][0]['used_centre'] is None


@pytest.mark.parametrize('corner_y', [142, 162])
def test_manual_snapping_rechecks_character_mask_on_used_centre(corner_y):
    from dispread.live.frame_tracking import proposal_from_regions

    image = np.full((400, 800), 100, dtype=np.uint8)
    quad = ((200, 170), (600, 170), (600, 230), (200, 230))
    # y=142: footprint enters the excluded zone; y=162: centre itself does.
    # The requested centre is outside the character polygon in both cases.
    cv2.rectangle(image, (400, corner_y), (406, corner_y+6), 220, -1)
    proposal = proposal_from_regions(image, quad, [(400, corner_y-2)])
    assert not proposal.regions
    assert proposal.metrics['centre_results'] == [
        {'requested_centre': [400, corner_y-2], 'centre': [400, corner_y], 'used_centre': [400, corner_y],
         'ok': False, 'reason': 'im_zeichenbereich'},
    ]


def test_manual_regions_report_each_rejection(scene):
    from dispread.live import frame_tracking

    image, quad, _, automatic, _ = scene
    image = image.copy()
    good = automatic.regions[0].centre
    centres = [good, good, tuple(np.rint(quad.mean(axis=0)).astype(int)), (1, 1), (100, 100)]
    for x, y in centres[2:]:
        image[max(0, y-5):y+12, max(0, x-5):x+12] = 100
        cv2.rectangle(image, (int(x), int(y)), (int(x)+6, int(y)+6), (220, 220, 220), -1)
    proposal = frame_tracking.proposal_from_regions(image, quad, centres)
    assert proposal.regions == automatic.regions[:1]
    assert [r['reason'] for r in proposal.metrics['centre_results']] == [
        None, 'zu_nah', 'im_zeichenbereich', 'am_bildrand', 'ausserhalb_rahmenband',
    ]


@pytest.mark.parametrize('repeated', [False, True])
def test_manual_regions_reject_flat_edges_and_repetition(repeated):
    from dispread.live import frame_tracking

    yy, xx = np.indices((400, 800))
    image = (((xx // 4 + yy // 4) % 2) * 200).astype(np.uint8) if repeated else np.full((400, 800), 100, np.uint8)
    # (251, 140) is a 3x3 local maximum in the repeated checkerboard.
    proposal = frame_tracking.proposal_from_regions(image, ((200, 170), (600, 170), (600, 230), (200, 230)), [(251, 140)])
    assert proposal.metrics['centre_results'][0]['reason'] == ('mehrdeutig' if repeated else 'zu_wenig_struktur')
    assert not proposal.ok and not proposal.regions


def test_manual_masks_include_search_and_interpolation_pixel():
    from dispread.live.frame_tracking import proposal_from_regions

    image = np.full((400, 800), 100, dtype=np.uint8)
    quad = ((200, 170), (600, 170), (600, 230), (200, 230))
    # Radius 7 + 12 + 1: der Mittelpunkt liegt im Band ausserhalb der
    # Zeichen; auch der letzte Interpolationspixel muss sicher bleiben.
    for centre, reason in [((400, 142), 'im_zeichenbereich'), ((400, 129), 'ausserhalb_rahmenband')]:
        image[:] = 100
        x, y = centre
        cv2.rectangle(image, (x, y), (x+6, y+6), 220, -1)
        proposal = proposal_from_regions(image, quad, [centre])
        assert proposal.metrics['centre_results'][0]['reason'] == reason
        assert not proposal.regions
    for centre in [(400, 141), (400, 130)]:
        image[:] = 100
        x, y = centre
        cv2.rectangle(image, (x, y), (x+6, y+6), 220, -1)  # Actual corner at the exact mask boundary.
        proposal = proposal_from_regions(image, quad, [centre])
        assert proposal.metrics['centre_results'][0]['ok']


def test_manual_spacing_is_not_relaxed_and_one_dimensional_edges_fail():
    from dispread.live.frame_tracking import proposal_from_regions

    quad = ((200, 170), (600, 170), (600, 230), (200, 230))
    image = np.full((400, 800), 100, dtype=np.uint8)
    cv2.rectangle(image, (250, 140), (256, 146), 220, -1)
    cv2.rectangle(image, (277, 140), (283, 146), 220, -1)
    too_close = proposal_from_regions(image, quad, [(250, 140), (277, 140)])
    assert too_close.metrics['centre_results'][1]['reason'] == 'zu_nah'
    image[:, 270:] = 100
    cv2.rectangle(image, (278, 140), (284, 146), 220, -1)
    boundary = proposal_from_regions(image, quad, [(250, 140), (278, 140)])
    assert len(boundary.regions) == 2
    image[:] = 0
    image[:, 250:] = 255
    line = proposal_from_regions(image, quad, [(250, 140)])
    assert line.metrics['centre_results'][0]['reason'] == 'zu_wenig_struktur'


def test_r11_fixed_old_profile_update_results_are_unchanged():
    from dataclasses import asdict

    from dispread.live.frame_tracking import RegionProposal

    saved = json.loads((FIXTURES / 'r13-r11-fixed-proposal.json').read_text())
    old = saved['proposal']
    # Explizite Testmigration nur neuer Vorschlagsfelder; kein neuer Vorschlag.
    config = FrameTrackingConfig(**old['config'])
    old['config'] = config.to_dict()
    proposal = RegionProposal.from_dict(old)
    image = cv2.imread(str(FIXTURES / 'reference.jpg'))
    quad = np.asarray(proposal.normalised_quad)
    tracker = FrameTracker(image, quad, proposal, config)
    inputs = {path.name: cv2.imread(str(path)) for path in FIXTURES.glob('*.jpg')}
    inputs['black'] = image * 0
    for dx, dy, angle in [(4, -3, 0.5), (30, 0, 0), (0, 0, 4)]:
        matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
        matrix[:, 2] += (dx, dy)
        inputs[f'move_{dx}_{dy}_{angle}'] = cv2.warpAffine(image, matrix, image.shape[1::-1])
    for name, expected in saved['results'].items():
        actual = json.loads(json.dumps(asdict(tracker.update(inputs[name]))))
        assert actual == expected, name


@pytest.mark.parametrize('name', ['frame_000289.png', 'frame_000390.png', 'frame_000440.png'])
def test_r11_fixed_old_profile_accepted_dev_updates_are_unchanged(name):
    from dataclasses import asdict

    from dispread.live.frame_tracking import RegionProposal

    path = Path('var/diagnostics/r13-werteplan-20261021/frames') / name
    if not path.is_file():
        pytest.skip('lokale DEV-Bilder')
    saved = json.loads((FIXTURES / 'r13-r11-fixed-proposal.json').read_text())
    old = saved['accepted_dev']['proposal']
    config = FrameTrackingConfig(**old['config'])
    old['config'] = config.to_dict()
    proposal = RegionProposal.from_dict(old)
    reference_path = Path(saved['accepted_dev']['reference'])
    if not reference_path.is_file():
        pytest.skip('lokales DEV-Referenzbild')
    reference = cv2.imread(str(reference_path))
    tracker = FrameTracker(reference, proposal.normalised_quad, proposal, config)
    actual = json.loads(json.dumps(asdict(tracker.update(cv2.imread(str(path))))))
    assert actual['quad'] is not None, actual
    assert actual == saved['accepted_dev']['results'][name]


@pytest.mark.parametrize('second, accepted', [(0.89, True), (0.91, False), (0.96, False)])
def test_r11_proposal_hysteresis_keeps_runtime_matching_unchanged(second, accepted):
    from dispread.live import frame_tracking as ft

    response = np.zeros((25, 25), np.float32)
    response[12, 12], response[4, 4] = 1, second
    assert ft._proposal_match(response, ft.FrameTrackingConfig()) == accepted
    assert ft._peak(response, ft.FrameTrackingConfig())[2] == (second > 0.95)


def test_r11_proposal_requires_absolute_peak_margin():
    from dispread.live import frame_tracking as ft

    response = np.zeros((25, 25), np.float32)
    response[12, 12], response[4, 4] = 0.76, 0.68
    assert not ft._proposal_match(response, ft.FrameTrackingConfig())


def test_r11_manual_requires_reserve_without_moving_kept_centres(scene):
    from itertools import combinations

    from dispread.live import frame_tracking as ft

    image, quad, config, automatic, _ = scene
    centres = [region.centre for region in automatic.regions]
    # Finde eine verteilte Teilmenge mit genau drei Punkten auf einer Seite.
    chosen = next(subset for subset in combinations(centres, 6) if ft._spread(subset, quad, config))
    manual = ft.proposal_from_regions(image, quad, [], config, kept_centres=chosen)
    assert [region.centre for region in manual.regions] == list(chosen)
    assert manual.metrics['spread_ok']
    assert not manual.ok
    assert 'rahmenbereiche_ohne_reserve' in manual.reasons
    assert manual.metrics['reserve_removals'] == 2
    assert not manual.metrics['reserve_ok']
    assert automatic.ok
    for removed in combinations(range(len(centres)), 2):
        assert ft._spread([p for i, p in enumerate(centres) if i not in removed], quad, config)


def test_r11_proposal_reserve_needs_lever_arm_on_each_axis_half():
    from itertools import combinations

    from dispread.live import frame_tracking as ft

    config = FrameTrackingConfig()
    quad = np.array([[-300, -30], [300, -30], [300, 30], [-300, 30]], float)
    outer = quad * (2, 6)
    limits = ft._proposal_spread_limits(quad, outer, config)
    np.testing.assert_allclose(limits, [[210, 63], [210, 63]])
    near = [(sign_x*x, sign_y*y) for sign_x in (-1, 1) for sign_y in (-1, 1)
            for x, y in [(25, 25), (40, 30), (60, 35), (80, 40), (85, 45)]]
    assert ft._spread(near, quad, config)  # Alte 20-px-Regel wuerde Reserve melden.
    assert not ft._reserve_ok(near, quad, config, limits)
    far = [(x*4, y*3) for x, y in near]
    assert ft._reserve_ok(far, quad, config, limits)
    for removed in combinations(range(len(far)), 2):
        local = np.array([p for i, p in enumerate(far) if i not in removed])
        assert np.all((local <= -limits[0]).sum(axis=0) >= config.min_inliers_per_side)
        assert np.all((local >= limits[1]).sum(axis=0) >= config.min_inliers_per_side)


def _r11_bezel_scene(cable_width=7):
    image = np.full((600, 900), 210, np.uint8)
    cv2.rectangle(image, (100, 90), (800, 510), 35, -1)
    cv2.rectangle(image, (440, 0), (440+cable_width, 100), 35, -1)
    cv2.rectangle(image, (240, 240), (660, 360), 180, -1)
    for x in (150, 195, 705, 750):
        for y in (145, 190, 410, 455):
            cv2.rectangle(image, (x, y), (x+8, y+8), 65, -1)
    quad = np.array([[270, 265], [630, 265], [630, 335], [270, 335]], float)
    return image, quad


def test_r11_bezel_band_reaches_bevel_and_cuts_thin_cable():
    from dispread.live.frame_tracking import proposal_from_regions

    image, quad = _r11_bezel_scene()
    proposal = proposal_from_regions(image, quad, [(150, 145), (440, 40)])
    assert proposal.metrics['band_quelle'] == 'dunkler_rahmen'
    assert proposal.regions[0].centre == (150, 145)
    assert len(proposal.regions) == 1
    assert not proposal.metrics['centre_results'][1]['ok']
    assert propose_regions(image, quad).ok


def test_r11_manual_near_centre_regions_cannot_supply_x_reserve():
    from dispread.live import frame_tracking as ft

    image, quad = _r11_bezel_scene()
    centres = [(x, y) for x in (390, 420, 480, 510) for y in (145, 190, 410, 455)]
    for x, y in centres:
        cv2.rectangle(image, (x, y), (x+8, y+8), 65, -1)
    manual = ft.proposal_from_regions(image, quad, [], kept_centres=centres)
    assert [region.centre for region in manual.regions] == centres
    assert ft._spread(centres, quad, FrameTrackingConfig())
    assert not manual.ok
    assert 'rahmenbereiche_einseitig' in manual.reasons
    assert not manual.metrics['reserve_ok']
    assert manual.metrics['regions_per_axis_side'] == [[0, 8], [0, 8]]


def test_r11_automatic_and_manual_use_the_bezel_only_quality_maximum():
    from dispread.live import frame_tracking as ft
    from dispread.live.frame_tracking import proposal_from_regions

    image, quad = _r11_bezel_scene()
    image[image == 65] = 39  # Schwache Rahmenpunkte neben starken Fensterkanten.
    automatic = propose_regions(image, quad)
    assert automatic.ok, automatic.metrics
    manual = proposal_from_regions(
        image, quad, [], kept_centres=[region.centre for region in automatic.regions])
    assert manual.regions == automatic.regions
    assert (158, 153) in [region.centre for region in automatic.regions]
    _, _, mask, _, _ = ft._geometry(image, quad, FrameTrackingConfig())
    strength = cv2.cornerMinEigenVal(image, blockSize=3, ksize=3)
    # Dieser manuell gueltige Punkt faellt unter die bisherige globale
    # goodFeaturesToTrack-Schwelle, wird jetzt aber auch automatisch gefunden.
    assert strength[153, 158] < strength[mask != 0].max() * FrameTrackingConfig().bezel_corner_quality


@pytest.mark.parametrize('kind', ['border', 'area', 'small_area', 'no_enclosure'])
def test_r11_implausible_bezel_falls_back_to_fixed_band(kind):
    image, quad = _r11_bezel_scene(cable_width=70 if kind == 'border' else 7)
    if kind == 'no_enclosure':
        image[:, 100:240] = 210
    config = FrameTrackingConfig(**({'bezel_max_area_ratio': 3.0} if kind == 'area' else
                                    {'bezel_min_area_ratio': 11.8} if kind == 'small_area' else {}))
    proposal = propose_regions(image, quad, config)
    assert proposal.metrics['band_quelle'] == 'festes_band'
    assert proposal.metrics['band_rueckfallgrund']


@pytest.mark.skipif(not Path('var/live/live-20261023T124226Z/setup/still.png').exists(), reason='lokaler R11-Befund')
def test_r11_frontal_bezel_has_two_region_reserve():
    setup = Path('var/live/live-20261023T124226Z/setup')
    quad = json.loads((setup / 'proposal.json').read_text())['quad']
    proposal = propose_regions(cv2.imread(str(setup / 'still.png')), quad)
    assert proposal.ok, (proposal.reasons, proposal.metrics)
    assert proposal.metrics['band_quelle'] == 'dunkler_rahmen'
    assert proposal.metrics['reserve_ok']


def test_r11_real_left_half_bias_does_not_reproduce_centre_line_false_fit():
    from dispread.live import frame_tracking as ft

    setup = Path('var/live/live-20261023T084344Z/setup')
    if not all((setup / name).is_file() for name in ('still.png', 'proposal.json')):
        pytest.skip('lokaler R11-Reviewbefund')
    reference = cv2.imread(str(setup / 'still.png'))
    quad = np.asarray(json.loads((setup / 'proposal.json').read_text())['quad'], float)
    proposal = propose_regions(reference, quad)
    assert proposal.ok, proposal.metrics
    tracker = FrameTracker(reference, quad, proposal)
    local = (tracker.sources - quad.mean(axis=0)) @ ft._axes(quad).T
    indices = np.flatnonzero(local[:, 0] < -20)
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), -0.4, 1)
    matrix[:, 2] += (1.5, 0)
    radius = tracker.config.patch_size // 2 + tracker.config.search_radius_px
    result = tracker.update(_paste_region_motion(reference, proposal, radius, matrix, indices))
    if result.quad is not None:
        close_quad(result, quad)  # Vor dem Fix 2.956 px akzeptierter Eckfehler.


@pytest.mark.parametrize('session', ['live-20261023T124226Z', 'live-20261014T172340Z'])
@pytest.mark.parametrize('width', [60, 90])
def test_r11_textured_dark_bar_touching_real_bezel_falls_back(session, width):
    from dispread.live import frame_tracking as ft

    setup = Path('var/live') / session / 'setup'
    if not (setup / 'still.png').is_file() or not (setup / 'proposal.json').is_file():
        pytest.skip('lokale R11-Standbilder')
    image = cv2.imread(str(setup / 'still.png'))
    quad = ft._normalise_quad(json.loads((setup / 'proposal.json').read_text())['quad'])
    clean = propose_regions(image, quad)
    assert clean.metrics['band_quelle'] == 'dunkler_rahmen'
    # Reviewer exp5.py: strukturierter dunkler Balken, 350x120 px schraeg abwaerts.
    x0, y0 = int(quad[:, 0].mean()) + 200, int(quad[:, 1].max()) + 150
    ends = np.array([[x0, y0], [x0+350, y0+120]])
    bar = np.zeros(image.shape[:2], np.uint8)
    cv2.line(bar, tuple(ends[0]), tuple(ends[1]), 255, width)
    image[bar != 0] = 40
    for t in np.linspace(0.3, 1.0, 6):
        cx, cy = (ends[0] + t * (ends[1]-ends[0])).astype(int)
        cv2.rectangle(image, (cx-3, cy-3), (cx+3, cy+3), (90, 90, 90), -1)
    proposal = propose_regions(image, quad)
    assert proposal.metrics['band_quelle'] == 'festes_band'
    assert proposal.metrics['band_rueckfallgrund'] == 'rahmenform_unplausibel'
    assert proposal.metrics['band_soliditaet'] < 0.97
    _, _, mask, _, fixed = ft._geometry(ft._gray(image), quad, FrameTrackingConfig())
    np.testing.assert_array_equal(mask, fixed)
    assert all(not bar[y, x] for x, y in (region.centre for region in proposal.regions))


@pytest.mark.parametrize('x, accepted', [(121, False), (122, True)])
def test_r11_bezel_windows_include_erosion_and_interpolation_guard(x, accepted):
    from dispread.live.frame_tracking import proposal_from_regions

    image, quad = _r11_bezel_scene()
    cv2.rectangle(image, (x, 300), (x+8, 308), 65, -1)
    proposal = proposal_from_regions(image, quad, [(x, 300)])
    assert proposal.metrics['band_quelle'] == 'dunkler_rahmen'
    assert bool(proposal.regions) == accepted
    if not accepted:
        assert proposal.metrics['centre_results'][0]['reason'] == 'ausserhalb_rahmenband'


@pytest.mark.parametrize('changes', [
    {'proposal_ambiguity_limit': 0.95}, {'proposal_ambiguity_limit': 0.0},
    {'proposal_min_peak_margin': 0.0}, {'proposal_min_peak_margin': 1.0},
    {'reserve_regions': 1}, {'bezel_opening_px': 14}, {'bezel_erosion_px': 0},
    {'bezel_min_area_ratio': 1.0}, {'bezel_max_area_ratio': 2.0},
    {'bezel_threshold_margin': 0.0}, {'bezel_corner_quality': 0.03},
    {'bezel_min_solidity': 0.0}, {'bezel_min_solidity': 1.01},
    {'proposal_lever_arm_fraction': 0.0}, {'proposal_lever_arm_fraction': 1.0},
])
def test_r11_proposal_config_rejects_unsafe_limits(changes):
    with pytest.raises(ValueError):
        FrameTrackingConfig(**changes)


def test_r11_old_tracking_config_requires_new_setup():
    old = json.loads((FIXTURES / 'r13-r11-fixed-proposal.json').read_text())['proposal']['config']
    with pytest.raises(ValueError, match='Unvollstaendige'):
        FrameTrackingConfig.from_dict(old)


def test_r11_additional_bezel_structure_must_localise_known_half_pixel_motion():
    from dispread.live import frame_tracking as ft

    image = cv2.cvtColor(cv2.imread(str(FIXTURES / 'reference.jpg')), cv2.COLOR_BGR2GRAY)
    # Selbst-eindeutige Ecken: bekannte Halb-Pixel-Bewegungen lokalisieren
    # die beiden ersten um >0.3 / >0.15 px falsch, die dritte bleibt <0.1 px.
    assert not ft._bezel_motion_ok(image, (891, 325), FrameTrackingConfig())
    assert not ft._bezel_motion_ok(image, (518, 503), FrameTrackingConfig())
    assert ft._bezel_motion_ok(image, (853, 316), FrameTrackingConfig())


@pytest.mark.skipif(not Path('var/diagnostics/r13-werteplan-20261021/frames/frame_000440.png').exists(),
                    reason='lokale DEV-Bilder')
@pytest.mark.parametrize('name', ['frame_000289.png', 'frame_000390.png', 'frame_000440.png'])
def test_r11_new_proposal_preserves_dev_availability(name):
    reference = cv2.imread('var/live/live-20261021T151835Z/setup/still.png')
    quad = json.loads(Path('var/live/live-20261021T151835Z/profile.json').read_text())['quad']
    proposal = propose_regions(reference, quad)
    tracker = FrameTracker(reference, quad, proposal)
    result = tracker.update(cv2.imread(str(Path('var/diagnostics/r13-werteplan-20261021/frames') / name)))
    close_quad(result, quad)
