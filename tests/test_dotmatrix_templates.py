import json

import numpy as np
import pytest

from dispread.ocr.dotmatrix_font import CLASSES, rom_vector
from dispread.ocr.dotmatrix_templates import (
    build_templates,
    classify,
    compute_thresholds,
    fit_templates,
    load_templates,
    rom_check,
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
