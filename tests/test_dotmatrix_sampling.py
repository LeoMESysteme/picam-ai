"""Tests fuer Abtastung, Normierung und Verschiebungssuche (Dot-Matrix-Leser)."""

from __future__ import annotations

import numpy as np
from dotmatrix_helpers import GRID, render

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import rom_vector
from dispread.ocr.dotmatrix_sampling import (
    MIN_CONTRAST,
    SHIFTS,
    dot_centers,
    normalized,
    sample_image,
)


def test_nine_shifts():
    assert len(SHIFTS) == 9 and (0, 0) in SHIFTS


def test_dot_centers_first_cell():
    c = dot_centers(GRID, 0)
    assert c.shape == (40, 2)
    assert np.allclose(c[0], (10 + 24 / 6 * 0.5, 40 + 80 / 8 * 0.5))


def test_normalized_matches_rom_at_zero_shift():
    img = render("+0.60972 ")
    s = sample_image(img, GRID, range(9))
    n = normalized(s)
    zero = SHIFTS.index((0, 0))
    assert n.shape == (9, 9, 40)
    for i, ch in enumerate("+0.60972 "):
        assert np.abs(n[i, zero] - rom_vector(ch)).max() < 0.35
    assert s.contrast > MIN_CONTRAST


def test_blank_display_has_low_contrast_and_no_nan():
    img = np.full((160, 400), 180, np.uint8)
    s = sample_image(img, GRID, range(9))
    assert s.contrast < MIN_CONTRAST
    assert np.isfinite(normalized(s)).all()


def test_shift_at_image_border_does_not_raise():
    grid = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    img = render("+0.60972 ", grid=grid)
    s = sample_image(img, grid, range(9))
    assert s.raw.shape == (9, 9, 40)


def test_normalized_ink_override_prevents_noise_amplification_on_blank_subset():
    """Final-Fix 3: eine Zellenteilmenge ohne eigene Ziffern (z. B. die drei
    'Rest'-Zellen) hat praktisch keinen eigenen Kontrast - ihr eigener
    Tintenpegel liegt nahe am Hintergrund, `depth` faellt auf den Bodenwert
    und verstaerkt Rauschen zu einem Scheinmuster statt einer sauberen
    Leerzelle. Mit dem global (an echten Ziffern) gemessenen Tintenpegel
    ueberschrieben bleibt die Teilmenge sauber nahe Null."""
    text = "+0.60972 "
    img = render(text)
    img = np.clip(img.astype(np.float32) + np.random.default_rng(3).normal(0, 3, img.shape), 0, 255).astype(
        np.uint8
    )
    digits = sample_image(img, GRID, range(9))
    blanks = sample_image(img, GRID, (13, 14, 15))
    zero = SHIFTS.index((0, 0))

    own = normalized(blanks)
    assert own[:, zero].max() > 0.5  # eigener Tintenpegel: Rauschen an den Clip getrieben

    shared = normalized(blanks, ink=digits.ink)
    assert shared[:, zero].max() < 0.35  # uebernommener Tintenpegel: sauber leer


def test_normalized_default_is_per_cell_ink_and_override_is_global():
    """Seit `ink_per_cell_v1` (2026-09-29) misst `normalized(s)` den
    Punktpegel je Zelle (Verlauf ueber die Zeile). Mit `ink=` bleibt das
    globale Verhalten fuer die Leerzellenpruefung erhalten."""
    img = render("+0.60972 ")
    s = sample_image(img, GRID, range(9))
    assert np.array_equal(normalized(s), normalized(s, ink=None))
    zero = SHIFTS.index((0, 0))
    # gleichmaessige Tinte: beide Wege liefern dasselbe Muster
    assert np.abs(normalized(s)[:, zero] - normalized(s, ink=s.ink)[:, zero]).max() < 0.1


def _ink_gradient_image(text: str, left_ink: float, right_ink: float) -> np.ndarray:
    """Hintergrund konstant, Punktschwaerze faellt ueber die Zeile ab - wie
    beim LCD unter wechselndem Blickwinkel (Aufstellung `sc3`), NICHT
    multiplikativ mit dem Hintergrund."""
    bg = 200.0
    img = render(text, bg=255, ink=0).astype(np.float32) / 255.0  # 1 = Hintergrund, 0 = Punkt
    w = img.shape[1]
    ink = np.linspace(left_ink, right_ink, w, dtype=np.float32)[None, :]
    out = bg * img + ink * (1.0 - img)
    return np.clip(out, 0, 255).astype(np.uint8)


def test_normalized_per_cell_ink_follows_ink_gradient_across_row():
    text = "+0.60972 "
    img = _ink_gradient_image(text, left_ink=40.0, right_ink=140.0)
    s = sample_image(img, GRID, range(9))
    zero = SHIFTS.index((0, 0))

    per_cell = normalized(s)[:, zero]
    global_ = normalized(s, ink=s.ink)[:, zero]
    for i, ch in enumerate(text):
        on = rom_vector(ch) >= 0.5
        if on.any():
            assert per_cell[i][on].mean() > 0.8, (i, ch, per_cell[i][on].mean())
        assert np.abs(per_cell[i] - rom_vector(ch)).max() < 0.35, (i, ch)
    # Gegenprobe: der globale Pegel laesst die blassen Zellen rechts absinken
    on7 = rom_vector("2") >= 0.5
    assert global_[7][on7].mean() < 0.8
    assert per_cell[7][on7].mean() - global_[7][on7].mean() > 0.1


def test_normalized_per_cell_falls_back_to_global_with_too_few_inked_cells():
    for text in ("+        ", "+0       "):
        s = sample_image(render(text), GRID, range(9))
        assert np.allclose(normalized(s), normalized(s, ink=s.ink)), text


def test_normalized_per_cell_blank_cells_stay_blank_under_gradient():
    text = "+0.60972 "
    img = _ink_gradient_image(text, left_ink=40.0, right_ink=140.0)
    img = np.clip(img.astype(np.float32) + np.random.default_rng(1).normal(0, 3, img.shape), 0, 255).astype(np.uint8)
    s = sample_image(img, GRID, range(9))
    zero = SHIFTS.index((0, 0))
    assert normalized(s)[8, zero].max() < 0.35  # Zelle 8 ist ' '


def test_normalized_survives_multiplicative_illumination_gradient():
    text = "+0.60972 "
    img = render(text)
    w = img.shape[1]
    gain = np.linspace(1.0, 0.4, w, dtype=np.float32)
    gradient_img = np.clip(img.astype(np.float32) * gain[None, :], 0, 255).astype(np.uint8)
    s = sample_image(gradient_img, GRID, range(9))
    n = normalized(s)
    zero = SHIFTS.index((0, 0))
    for i, ch in enumerate(text):
        assert np.abs(n[i, zero] - rom_vector(ch)).max() < 0.35


def _synthetic_sampled(depths: list[float], seed: int = 0, n_dark: int = 20):
    """SampledImage mit Hintergrund 200 je Zelle; `depths[i] > 0` setzt in
    Zelle i `n_dark` Punkte auf 200 * (1 - depth), der Rest ist Hintergrund
    plus Rauschen (1 Grauwert). Reviewbefund 2026-09-29."""
    from dispread.ocr.dotmatrix_sampling import SampledImage

    rng = np.random.default_rng(seed)
    n = len(depths)
    raw = 200.0 + rng.normal(0, 1.0, (n, len(SHIFTS), 40))
    for i, d in enumerate(depths):
        if d > 0:
            raw[i, :, :n_dark] = 200.0 * (1 - d) + rng.normal(0, 1.0, (len(SHIFTS), n_dark))
    raw = raw.astype(np.float32)
    zero = SHIFTS.index((0, 0))
    background = np.percentile(raw[:, zero, :], 80.0, axis=1).astype(np.float32)
    ink = float(np.percentile(raw[:, zero, :], 3.0))
    ref = float(np.median(background))
    return SampledImage(raw, background, ink, (ref - ink) / ref, 0.0)


def test_normalized_per_cell_two_inked_cells_do_not_amplify_noise_in_blank_cells():
    """Zwei nah beieinander liegende Zellen mit Zeichen duerfen keine Gerade
    aufspannen, die Leerzellen auf eine winzige Tiefe extrapoliert (vor dem
    Fix: Tiefe 0,003, Rauschen bis 1,0 verstaerkt). Mit nur 5 dunklen
    Punkten je Zelle liegt der globale Pegel fast am Hintergrund - solche
    Bilder lehnt der Leser schon ueber `MIN_CONTRAST` ab; die Normierung
    darf dann nicht schlechter sein als der globale Weg."""
    s = _synthetic_sampled([0.5, 0.25, 0, 0, 0, 0, 0, 0, 0], n_dark=5)
    assert s.contrast < MIN_CONTRAST
    assert np.allclose(normalized(s), normalized(s, ink=s.ink))


def test_normalized_per_cell_blank_cells_between_inked_cells_stay_blank():
    """Genug Kontrast, Zeichen in drei Zellen, dazwischen und dahinter
    Leerzellen: die Leerzellen bleiben leer."""
    s = _synthetic_sampled([0.5, 0.45, 0, 0.3, 0, 0, 0, 0, 0], n_dark=20)
    assert s.contrast >= MIN_CONTRAST
    zero = SHIFTS.index((0, 0))
    n = normalized(s)
    for i in (2, 4, 5, 6, 7, 8):
        assert n[i, zero].max() < 0.35, (i, n[i, zero].max())


def test_normalized_per_cell_blank_cells_keep_global_depth_even_with_steep_fit():
    """Auch mit genug Zellen fuer eine Anpassung: Zellen ohne eigenes Zeichen
    (fuehrende Leerzellen, Zelle 8) bekommen den globalen Pegel, keine
    extrapolierte Tiefe."""
    s = _synthetic_sampled([0.6, 0, 0, 0.5, 0.4, 0.3, 0.2, 0.15, 0], n_dark=5)
    zero = SHIFTS.index((0, 0))
    n = normalized(s)
    for i in (1, 2, 8):
        assert n[i, zero].max() < 0.35, (i, n[i, zero].max())
