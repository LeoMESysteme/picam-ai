"""Experimenteller LCD-Fensterrand: Geometrie ohne Zeichen oder Raumlicht."""

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.live.window_tracking import WindowTracker, WindowTrackingConfig, propose_window

FIXTURES = Path(__file__).parent / "fixtures" / "r13"


@pytest.fixture(scope="module")
def scene():
    reference = cv2.imread(str(FIXTURES / "reference.jpg"))
    quad = np.asarray(json.loads((FIXTURES / "r13-fixtures.json").read_text())["quad"])
    config = WindowTrackingConfig()
    model = propose_window(reference, quad, config)
    assert model.ok, model
    return reference, quad, config, model, WindowTracker(reference, quad, model, config)


def close_quad(result, expected, tolerance=1):
    assert result.quad is not None, result
    assert np.linalg.norm(np.asarray(result.quad)-expected, axis=1).max() <= tolerance
    assert 0 <= result.score <= 1


@pytest.mark.parametrize("factor", ["1_0", "2_0", "0_5", "5_0", "10_0"])
def test_faktorwechsel(scene, factor):
    _, quad, _, _, tracker = scene
    close_quad(tracker.update(cv2.imread(str(FIXTURES / f"faktor-{factor}.jpg"))), quad)


@pytest.mark.parametrize("angle,shift", [(0, (6, -3)), (0.5, (6, -3)), (-0.5, (-2, 1))])
def test_vorwaertsbewegung(scene, angle, shift):
    reference, quad, _, _, tracker = scene
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), angle, 1)
    matrix[:, 2] += shift
    image = cv2.warpAffine(reference, matrix, reference.shape[1::-1])
    expected = cv2.transform(quad[:, None], matrix)[:, 0]
    result = tracker.update(image)
    close_quad(result, expected, 2)
    assert abs(result.rotation_deg + angle) < 0.2


@pytest.mark.parametrize("hidden", [False, True])
def test_zeichen_unabhaengig(scene, hidden):
    reference, quad, _, _, tracker = scene
    mask = np.zeros(reference.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.rint(quad).astype(np.int32), 255)
    mask = cv2.dilate(mask, np.ones((17, 17), np.uint8))
    image = reference.copy()
    image[mask != 0] = 120 if hidden else np.random.default_rng(6).integers(0, 256, image[mask != 0].shape, dtype=np.uint8)
    close_quad(tracker.update(image), quad)
    # Auch die Referenzmodellbildung darf nicht vom Zeicheninhalt abhaengen.
    alternate = propose_window(image, quad)
    assert alternate.edges == scene[3].edges


def test_simulierte_nacht(scene):
    reference, quad, _, _, tracker = scene
    # Unabhaengig am Fixture abgelesene Glas-Eckpunkte, keine Tracker-Erwartung.
    glass = np.float32([[293, 238], [901, 438], [857, 574], [237, 367]])
    mask = np.zeros(reference.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, glass.astype(np.int32), 255)
    image = reference.astype(float) * np.where(mask[:, :, None] != 0, 0.4, 0.1)
    close_quad(tracker.update(image.astype(np.uint8)), quad)


def test_verdeckung_und_zustandslosigkeit(scene):
    reference, quad, config, model, tracker = scene
    result = tracker.update(np.zeros_like(reference))
    assert result.quad is None
    assert result.reason == "fensterrand_fehlt"
    matrix = np.float32([[1, 0, 6], [0, 1, -3]])
    tracker.update(cv2.warpAffine(reference, matrix, reference.shape[1::-1]))
    close_quad(tracker.update(reference), quad)
    assert tracker.update(reference) == WindowTracker(reference, quad, model, config).update(reference)


@pytest.mark.parametrize("side", range(4))
def test_jede_seite_erforderlich(scene, side):
    reference, _, _, model, tracker = scene
    image = reference.copy()
    for edge in model.edges:
        if edge.side == side:
            cv2.circle(image, tuple(np.rint(edge.point).astype(int)), 20, (0, 0, 0), -1)
    assert tracker.update(image).quad is None


def test_bewegung_und_teilverdeckung_niemals_falsche_geometrie(scene):
    reference, quad, _, model, tracker = scene
    rng = np.random.default_rng(13)
    kept = 0
    for _trial in range(300):
        image = reference.copy()
        for index in rng.choice(len(model.edges), rng.integers(1, 15), replace=False):
            x, y = model.edges[index].point
            cv2.circle(image, (round(x), round(y)), int(rng.integers(3, 15)),
                       (int(rng.integers(0, 256)),)*3, -1)
        matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), float(rng.uniform(-2.5, 2.5)), 1)
        matrix[:, 2] += rng.uniform(-10, 10, 2)
        moved = cv2.warpAffine(image, matrix, image.shape[1::-1])
        expected = cv2.transform(quad[:, None], matrix)[:, 0]
        result = tracker.update(moved)
        if result.quad is not None:
            close_quad(result, expected)
            kept += 1
    assert kept > 0


@pytest.mark.parametrize("kind,reason", [("shift", "shift_out_of_bounds"), ("rotation", "rotation_out_of_bounds")])
def test_bewegungsgrenzen(scene, kind, reason):
    reference, quad, _, _, _ = scene
    config = WindowTrackingConfig(max_shift_px=2) if kind == "shift" else WindowTrackingConfig(max_rotation_deg=0.2)
    model = propose_window(reference, quad, config)
    matrix = cv2.getRotationMatrix2D(tuple(quad.mean(axis=0)), 0.5, 1)
    matrix[:, 2] += (6, -3)
    result = WindowTracker(reference, quad, model, config).update(cv2.warpAffine(reference, matrix, reference.shape[1::-1]))
    assert result.quad is None and result.reason == reason


def test_weisse_einfassung_verschwindet_bei_nacht():
    # Grauwert staerkster Schritt: weiss->Gehaeuse. Glasrand bleibt ortsfest.
    reference = np.full((350, 800, 3), 20, np.uint8)
    cv2.rectangle(reference, (96, 96), (704, 244), (220, 220, 220), -1)
    cv2.rectangle(reference, (100, 100), (700, 240), (100, 180, 100), -1)
    quad = np.float64([[125, 125], [675, 125], [675, 215], [125, 215]])
    current = np.full_like(reference, 2)
    cv2.rectangle(current, (100, 100), (700, 240), (40, 72, 40), -1)
    model = propose_window(reference, quad)
    assert model.ok
    close_quad(WindowTracker(reference, quad, model).update(current), quad)


@pytest.mark.parametrize("side", range(4))
def test_nur_drei_seiten_im_modell_reichen_nicht(side):
    reference = np.zeros((350, 800, 3), np.uint8)
    # Lange gruene Flaeche, eine Seite ausserhalb der Referenzsuche.
    bounds = [100, 100, 700, 240]
    bounds[[1, 2, 3, 0][side]] += [-100, 100, 100, -100][side]
    cv2.rectangle(reference, tuple(bounds[:2]), tuple(bounds[2:]), (50, 150, 50), -1)
    quad = np.float64([[125, 125], [675, 125], [675, 215], [125, 215]])
    model = propose_window(reference, quad)
    assert not model.ok
    assert WindowTracker(reference, quad, model).update(reference).reason == "fensterrand_fehlt"


def test_seitenweglassen_muss_stabil_bleiben():
    reference = np.zeros((350, 800, 3), np.uint8)
    cv2.rectangle(reference, (100, 100), (700, 240), (50, 150, 50), -1)
    quad = np.float64([[125, 125], [675, 125], [675, 215], [125, 215]])
    current = reference.copy()
    cv2.rectangle(current, (700, 100), (702, 240), (50, 150, 50), -1)
    # Residuum absichtlich gelockert: erst der Seiten-Stabilitaetstest verwirft.
    config = WindowTrackingConfig(residual_limit_px=3.0, max_rms_px=2.0)
    model = propose_window(reference, quad, config)
    result = WindowTracker(reference, quad, model, config).update(current)
    assert result.quad is None and result.reason == "fensterrand_unstimmig"


def test_abtastung_bleibt_ausserhalb_zeichen_samt_interpolation(scene, monkeypatch):
    import dispread.live.window_tracking as window

    reference, quad, _, _, tracker = scene
    mask = np.zeros(reference.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, np.rint(quad).astype(np.int32), 255)
    mask = cv2.dilate(mask, np.ones((17, 17), np.uint8))
    sample = window._sample
    calls = []

    def checked_sample(gray, points):
        calls.append(True)
        lo = np.floor(points).astype(int)
        for dx in (0, 1):
            for dy in (0, 1):
                assert not mask[lo[..., 1]+dy, lo[..., 0]+dx].any()
        return sample(gray, points)

    monkeypatch.setattr(window, "_sample", checked_sample)
    assert propose_window(reference, quad).ok
    close_quad(tracker.update(reference), quad)
    assert calls


@pytest.mark.parametrize("order", [[1, 2, 3, 0], [0, 3, 2, 1]])
def test_originale_quadreihenfolge(scene, order):
    reference, quad, config, _, _ = scene
    quad = quad[order]
    model = propose_window(reference, quad, config)
    close_quad(WindowTracker(reference, quad, model, config).update(reference), quad)


@pytest.mark.parametrize("change", ["image", "quad", "config"])
def test_modell_gebunden(scene, change):
    from dataclasses import replace

    reference, quad, config, model, _ = scene
    if change == "image":
        reference = reference.copy()
        reference[0, 0] = (0, 255, 0)
    elif change == "quad":
        quad = quad+1
    else:
        config = replace(config, search_radius_px=15)
    with pytest.raises(ValueError, match="passt nicht"):
        WindowTracker(reference, quad, model, config)


@pytest.mark.parametrize("changes", [{"search_radius_px": 0}, {"max_rms_px": float("nan")},
                                     {"min_points_per_side": 0}, {"character_margin_px": 7},
                                     {"samples_per_side": True}])
def test_ungueltige_config(changes):
    with pytest.raises(ValueError):
        WindowTrackingConfig(**changes)


def test_verdecktes_fenster_bei_sichtbarem_gehaeuse(scene):
    reference, _, _, model, tracker = scene
    image = reference.copy()
    hull = cv2.convexHull(np.float32([edge.point for edge in model.edges]))
    mask = np.zeros(image.shape[:2], np.uint8)
    cv2.fillConvexPoly(mask, hull.astype(np.int32), 255)
    mask = cv2.dilate(mask, np.ones((15, 15), np.uint8))
    image[mask != 0] = 0
    assert tracker.update(image).quad is None


def test_polaritaet_umgekehrt_wird_abgelehnt(scene):
    reference, _, _, _, tracker = scene
    assert tracker.update(255-reference).quad is None


@pytest.mark.filterwarnings("error")
def test_profile_am_bildrand_werden_sauber_abgelehnt():
    image = np.zeros((100, 100, 3), np.uint8)
    quad = np.float64([[5, 5], [95, 5], [95, 95], [5, 95]])
    model = propose_window(image, quad)
    assert not model.ok
    assert WindowTracker(image, quad, model).update(image).quad is None


@pytest.mark.parametrize("dtype", [np.float32, np.uint16])
def test_ungueltiger_bildtyp_vor_abtastung(scene, dtype):
    reference, quad, config, model, tracker = scene
    with pytest.raises(ValueError):
        propose_window(reference.astype(dtype), quad, config)
    with pytest.raises(ValueError):
        WindowTracker(reference.astype(dtype), quad, model, config)
    with pytest.raises(ValueError):
        tracker.update(reference.astype(dtype))


def test_bgra_ignoriert_alpha_und_bildwechsel_lehnt_ab(scene):
    reference, quad, config, model, tracker = scene
    bgra = cv2.cvtColor(reference, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = np.random.default_rng(7).integers(0, 256, reference.shape[:2], dtype=np.uint8)
    assert tracker.update(bgra) == tracker.update(reference)
    other = WindowTracker(bgra, quad, model, config)
    assert other.update(reference) == tracker.update(reference)
    assert tracker.update(reference[:-1]).reason == "fensterrand_fehlt"
    assert tracker.update(cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)).reason == "fensterrand_fehlt"


def test_graubild_ohne_moduswechsel():
    reference = np.zeros((350, 800), np.uint8)
    cv2.rectangle(reference, (100, 100), (700, 240), 180, -1)
    quad = np.float64([[125, 125], [675, 125], [675, 215], [125, 215]])
    model = propose_window(reference, quad)
    assert model.ok
    image = cv2.warpAffine(reference, np.float32([[1, 0, 6], [0, 1, -3]]), reference.shape[1::-1])
    close_quad(WindowTracker(reference, quad, model).update(image), quad+(6, -3))
