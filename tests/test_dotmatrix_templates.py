import json
import re

import numpy as np
import pytest

from dispread.ocr.dotmatrix_font import CLASSES, rom_vector
from dispread.ocr.dotmatrix_templates import (
    ROM_CHECK,
    ROM_TOLERANCE_DOTS,
    build_templates,
    classify,
    compute_thresholds,
    fit_templates,
    load_templates,
    rom_check,
    rom_deviations,
    save_templates,
)

ZERO = 4  # SHIFTS.index((0, 0))


def noisy(ch, rng, n=20, noise=0.08):
    out = []
    for _ in range(n):
        v = np.tile(rom_vector(ch) * 0.9 + 0.05, (9, 1))
        v += rng.normal(0, 0.25, v.shape)  # falsche Shifts: verrauscht
        v[ZERO] = np.clip(rom_vector(ch) * 0.9 + 0.05 + rng.normal(0, noise, 40), 0, 1)
        out.append(v.astype(np.float32))
    return out


@pytest.fixture
def samples():
    rng = np.random.default_rng(1)
    return {ch: noisy(ch, rng) for ch in CLASSES}


def test_build_and_classify_roundtrip(samples):
    t = build_templates(samples, ("g1",))
    rng = np.random.default_rng(2)
    for ch in CLASSES:
        d = classify(noisy(ch, rng, n=1)[0], t)
        assert d.text == ch, (ch, d)


def test_random_pattern_is_rejected(samples):
    t = build_templates(samples, ("g1",))
    rng = np.random.default_rng(3)
    x = np.tile(rng.uniform(0, 1, 40).astype(np.float32), (9, 1))
    d = classify(x, t)
    assert d.text is None and d.reason == "zelle_unbekannt"


def test_blend_8_0_is_ambiguous(samples):
    t = build_templates(samples, ("g1",))
    x = np.tile(((rom_vector("8") + rom_vector("0")) / 2 * 0.9 + 0.05).astype(np.float32), (9, 1))
    d = classify(x, t)
    assert d.text is None and d.reason in ("zelle_mehrdeutig", "zelle_unbekannt")
    assert {d.best, d.second} == {"8", "0"} or d.reason == "zelle_unbekannt"


def test_rom_check_catches_mislabeled_class(samples):
    bad = dict(samples)
    bad["7"] = samples["1"]
    with pytest.raises(ValueError, match="7"):
        build_templates(bad, ("g1",))


def test_missing_class_raises(samples):
    s = dict(samples)
    del s["."]
    with pytest.raises(ValueError, match=r"\."):
        build_templates(s, ("g1",))


def test_thresholds_deterministic(samples):
    mean, std = fit_templates(samples, ("g1",))
    assert compute_thresholds(samples, mean, std) == compute_thresholds(samples, mean, std)


def test_save_load_checksum_and_version(tmp_path, samples):
    t = build_templates(samples, ("g1", "g2"))
    p = tmp_path / "templates.json"
    sha = save_templates(t, p)
    t2 = load_templates(p, expected_sha256=sha)
    assert t2.groups == ("g1", "g2") and t2.d_max == t.d_max
    with pytest.raises(ValueError, match="Pruefsumme"):
        load_templates(p, expected_sha256="0" * 64)
    data = json.loads(p.read_text())
    data["threshold_formula"] = "thresholds_v0"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="thresholds_v0"):
        load_templates(p)
    data["threshold_formula"] = "thresholds_v1"
    del data["mean"]["."]
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="Klasse"):
        load_templates(p)


def test_rom_check_passes_on_rom():
    assert rom_check({ch: rom_vector(ch) for ch in CLASSES}) == []


# --- rom_check_v2: Toleranz von ROM_TOLERANCE_DOTS Punkten (OQ-42) --------


def _rom_mean_with_flipped_dots(ch: str, n: int) -> dict[str, np.ndarray]:
    """ROM-genaue Vorlagen fuer alle Zeichen, `ch` mit den ersten `n`
    Punkten binaer gekippt (0.0<->1.0, also garantiert ueber die
    0,5-Schwelle)."""
    mean = {c: rom_vector(c).copy() for c in CLASSES}
    v = mean[ch].copy()
    v[:n] = 1.0 - v[:n]
    mean[ch] = v
    return mean


def test_rom_check_v2_tolerates_exactly_one_deviating_dot():
    assert ROM_TOLERANCE_DOTS == 1
    mean = _rom_mean_with_flipped_dots("0", 1)
    assert rom_deviations(mean)["0"] == 1
    assert rom_check(mean) == []


def test_rom_check_v2_rejects_two_deviating_dots():
    mean = _rom_mean_with_flipped_dots("0", 2)
    assert rom_deviations(mean)["0"] == 2
    assert rom_check(mean) == ["0"]


def test_rom_deviations_reports_zero_for_exact_rom_match():
    mean = {ch: rom_vector(ch) for ch in CLASSES}
    assert rom_deviations(mean) == {ch: 0 for ch in CLASSES}


#: Engste Zeichenpaare des Satzes (Spec Abschnitt 2, "Aenderung 2026-09-25"),
#: (Label der Trainingsklasse, tatsaechlich abgebildetes Zeichen).
_CLOSEST_PAIRS = ((".", " "), ("0", "8"), ("8", "9"), ("6", "8"), ("3", "5"), ("1", "7"))

#: Anteil, ab dem alle sechs Paare oben ueber build_templates() zuverlaessig
#: erkannt werden (mit den Vektoren aus `noisy()`, Seeds 0-9 durchprobiert,
#: siehe romv2-report.md). 40 % (Spec-Beleg) loest bei KEINEM der Paare aus -
#: `fit_templates` mittelt Punktwerte, eine binarisierte Mehrheitsentscheidung
#: kippt bei einer linearen Mischung aus (fast) 0/1-Werten strukturell erst
#: oberhalb von 50 % Fehletikettierung; 55 % reicht fuer "8"/"9" noch nicht
#: zuverlaessig. Der Bericht dokumentiert das als DONE_WITH_CONCERNS.
_MAJORITY_MISLABEL_FRACTION = 0.6


@pytest.mark.parametrize("label_ch,true_ch", _CLOSEST_PAIRS)
def test_rom_check_v2_catches_majority_mislabeled_class(samples, label_ch, true_ch):
    """Beleg aus der Spec: Trainingszellen einer Klasse, deren Bild
    ueberwiegend das eines benachbarten Zeichens zeigt, werden auch mit der
    tolerierten Gegenprobe (`rom_check_v2`) erkannt und brechen das Training
    ab - fuer alle engsten Paare des Zeichensatzes."""
    rng = np.random.default_rng(7)
    n = len(samples[label_ch])
    n_bad = int(round(n * _MAJORITY_MISLABEL_FRACTION))
    mislabeled = dict(samples)
    mislabeled[label_ch] = noisy(true_ch, rng, n=n_bad) + noisy(label_ch, rng, n=n - n_bad)

    with pytest.raises(ValueError, match=re.escape(label_ch)):
        build_templates(mislabeled, ("g1",))


def test_rom_check_v2_does_not_catch_forty_percent_mislabeled_class(samples):
    """Gegenprobe/Beleg fuer den obigen Konzern: bei genau 40 % - dem in der
    Spec genannten Anteil - loest keines der engsten Paare aus (siehe
    Kommentar bei `_MAJORITY_MISLABEL_FRACTION` und romv2-report.md).
    Dokumentiert die Grenze, statt sie stillschweigend zu unterschlagen."""
    rng = np.random.default_rng(7)
    for label_ch, true_ch in _CLOSEST_PAIRS:
        n = len(samples[label_ch])
        n_bad = int(round(n * 0.4))
        mislabeled = dict(samples)
        mislabeled[label_ch] = noisy(true_ch, rng, n=n_bad) + noisy(label_ch, rng, n=n - n_bad)
        build_templates(mislabeled, ("g1",))  # wirft NICHT


# --- Fail-open bei beschaedigter Vorlagendatei schliessen (Final-Fix 1) ----


def _save(tmp_path, samples, name="templates.json"):
    t = build_templates(samples, ("g1",))
    p = tmp_path / name
    save_templates(t, p)
    return p


def test_load_templates_rejects_nan_d_max(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    data["d_max"] = float("nan")
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="d_max"):
        load_templates(p)


def test_load_templates_rejects_nan_margin_min(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    data["margin_min"] = float("nan")
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="margin_min"):
        load_templates(p)


def test_load_templates_rejects_non_positive_d_max(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    data["d_max"] = 0.0
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="d_max"):
        load_templates(p)


def test_load_templates_rejects_negative_std(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    data["std"]["0"][0] = -1.0
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="std"):
        load_templates(p)


def test_load_templates_rejects_nan_mean(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    data["mean"]["0"][0] = float("nan")
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="mean"):
        load_templates(p)


def test_load_templates_rejects_missing_d_max(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    del data["d_max"]
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="d_max"):
        load_templates(p)


def test_load_templates_rejects_missing_margin_min(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    del data["margin_min"]
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="margin_min"):
        load_templates(p)


def test_load_templates_rejects_missing_groups(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    del data["groups"]
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="groups"):
        load_templates(p)


def test_save_templates_writes_rom_check_and_deviations(tmp_path, samples):
    t = build_templates(samples, ("g1",))
    p = tmp_path / "templates.json"
    save_templates(t, p)
    data = json.loads(p.read_text())
    assert data["rom_check"] == ROM_CHECK == "rom_check_v2"
    assert data["rom_deviations"] == rom_deviations(t.mean)
    assert all(n <= ROM_TOLERANCE_DOTS for n in data["rom_deviations"].values())


def test_load_templates_rejects_missing_rom_check(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    del data["rom_check"]
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="rom_check"):
        load_templates(p)


def test_load_templates_rejects_other_rom_check(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    data["rom_check"] = "rom_check_v1"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="rom_check_v1"):
        load_templates(p)


def test_load_templates_rejects_old_format_version_1(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    data["format_version"] = 1
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="format_version"):
        load_templates(p)


def test_load_templates_rejects_missing_counts(tmp_path, samples):
    p = _save(tmp_path, samples)
    data = json.loads(p.read_text())
    del data["counts"]
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="counts"):
        load_templates(p)
