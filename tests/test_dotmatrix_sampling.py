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
    shadow_coefficients,
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
        assert np.allclose(normalized(s, remove_shadow=False), normalized(s, ink=s.ink)), text


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
    assert np.allclose(normalized(s, remove_shadow=False), normalized(s, ink=s.ink))


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


# --- bg_closing_v1: Hintergrund je Punkt (2026-09-29, Abnahmebefund ab2) -------


def _wedge_image(text: str, *, darkening: float = 0.22, center_x: float = 222.0) -> np.ndarray:
    """Wie Aufstellung `ab2`: schwacher Punktkontrast (Tiefe 0,3) und ein
    weicher dunkler Keil (Glasspiegelung) von oben rechts in die Leerzelle 8
    (x 202-226 bei `GRID`) und weiter nach rechts - multiplikativ, Staerke
    `darkening` im Keil, weicher Uebergang ueber ~2 Punktspalten."""
    img = render(text, bg=200, ink=140).astype(np.float32)
    h, w = img.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    # Keilkante: diagonal, oben weiter links als unten
    edge = (xs - center_x) / 4.0 + (70.0 - ys) / 10.0
    gain = 1.0 - darkening / (1.0 + np.exp(-edge))
    return np.clip(img * gain, 0, 255).astype(np.uint8)


def test_bg_closing_blank_cell_under_reflection_wedge_stays_blank():
    """Abnahmebefund `ab2` (VALIDATION.md 2026-09-29): Ein Hintergrund je
    Zelle kam aus dem hellen Teil, der dunkle Keil las sich als Punktmuster
    (bis 0,88). Mit Hintergrund je Punkt bleibt die Leerzelle leer."""
    text = "+0.60972 "
    s = sample_image(_wedge_image(text), GRID, range(9))
    zero = SHIFTS.index((0, 0))
    n = normalized(s)
    assert n[8, zero].max() < 0.35, n[8, zero].reshape(8, 5).round(2)
    for i, ch in enumerate(text[:8]):
        assert np.abs(n[i, zero] - rom_vector(ch)).max() < 0.35, (i, ch)


def test_bg_closing_counterexample_cell_background_reads_wedge_as_ink():
    """Gegenprobe zum Test oben: mit dem alten Hintergrund je Zelle (ein
    Wert, `background_dots=None`) erscheint derselbe Keil als Tinte - der
    Testaufbau bildet den Befund also wirklich ab."""
    from dataclasses import replace

    s = sample_image(_wedge_image("+0.60972 "), GRID, range(9))
    zero = SHIFTS.index((0, 0))
    old = normalized(replace(s, background_dots=None))
    assert old[8, zero].max() > 0.5


def test_bg_closing_vertical_gradient_keeps_top_row_of_blank_cell_clean():
    """Auch in guten Aufstellungen ist Zeile 0 oft dunkler (Schatten der
    Blende); mit einem Hintergrund je Zelle stand sie in Leerzellen bei
    0,07-0,16. Hintergrund je Punkt gleicht das aus."""
    text = "+0.60972 "
    img = render(text, bg=200, ink=140).astype(np.float32)
    h = img.shape[0]
    gain = np.linspace(0.85, 1.0, h, dtype=np.float32)[:, None]
    s = sample_image(np.clip(img * gain, 0, 255).astype(np.uint8), GRID, range(9))
    zero = SHIFTS.index((0, 0))
    assert normalized(s)[8, zero].max() < 0.15


def test_bg_closing_background_dots_shape_and_uniform_image():
    img = np.full((160, 400), 180, np.uint8)
    s = sample_image(img, GRID, range(9))
    assert s.background_dots is not None
    assert s.background_dots.shape == s.raw.shape
    assert np.allclose(s.background_dots, 180.0, atol=0.5)


def test_bg_closing_is_the_recorded_normalization():
    from dispread.ocr.dotmatrix_sampling import NORMALIZATION

    assert NORMALIZATION == "bg_closing_shadow_v1"


# --- bg_closing_shadow_v1: Punktschatten abziehen (2026-09-30, Abnahme 2) -----


def _shadow_image(text: str, *, dx_cols: float = 0.8, dy_rows: float = 0.0, strength: float = 0.4) -> np.ndarray:
    """Wie Aufstellung `ab4`: Jeder An-Punkt wirft einen um (`dx_cols`,
    `dy_rows`) Punktabstaende versetzten Schatten der Staerke `strength`
    (Anteil der Punkttiefe). Wo Schatten und Punkt sich decken, bleibt der
    Punkt voll dunkel."""
    bg, ink = 200.0, 60.0
    img = render(text, bg=int(bg), ink=int(ink)).astype(np.float32)
    col_w = GRID.pitch / (GRID.dot_columns + GRID.gap_columns)
    row_h = (GRID.bottom - GRID.top) / 8
    h, w = img.shape
    ys, xs = np.ogrid[:h, :w]
    shadow = np.zeros((h, w), bool)
    for i, ch in enumerate(text):
        v = rom_vector(ch)
        for k, (x, y) in enumerate(dot_centers(GRID, i)):
            if v[k]:
                sx, sy = x + dx_cols * col_w, y + dy_rows * row_h
                shadow |= (xs - sx) ** 2 + (ys - sy) ** 2 <= 1.4 * 1.4
    shaded = bg - strength * (bg - ink)
    img = np.where(shadow & (img > shaded), shaded, img)
    return img.astype(np.uint8)


def _off_dots_next_to_on(text: str, n: np.ndarray, direction: tuple[int, int]) -> np.ndarray:
    """Werte der Aus-Punkte, deren Nachbar in `direction` (dy, dx) an ist."""
    zero = SHIFTS.index((0, 0))
    vals = []
    for i, ch in enumerate(text):
        m = rom_vector(ch).reshape(8, 5)[:7] >= 0.5
        v = n[i, zero].reshape(8, 5)[:7]
        for y in range(7):
            for x in range(5):
                yy, xx = y + direction[0], x + direction[1]
                if not m[y, x] and 0 <= yy < 7 and 0 <= xx < 5 and m[yy, xx]:
                    vals.append(v[y, x])
    return np.asarray(vals)


TEXT_SHADOW = "+0.60972 "


def test_shadow_counterexample_without_removal_off_dots_are_dark():
    """Gegenprobe: ohne Abzug liegen die Aus-Punkte rechts neben einem
    An-Punkt deutlich ueber 0 - der Testaufbau bildet den Befund `ab4` ab."""
    s = sample_image(_shadow_image(TEXT_SHADOW), GRID, range(9))
    vals = _off_dots_next_to_on(TEXT_SHADOW, normalized(s, remove_shadow=False), (0, -1))
    assert np.mean(vals) > 0.2


def test_shadow_removed_for_off_dots_right_of_on_dots():
    s = sample_image(_shadow_image(TEXT_SHADOW), GRID, range(9))
    n = normalized(s)
    assert np.mean(_off_dots_next_to_on(TEXT_SHADOW, n, (0, -1))) < 0.08
    zero = SHIFTS.index((0, 0))
    for i, ch in enumerate(TEXT_SHADOW):
        assert np.abs(n[i, zero] - rom_vector(ch)).max() < 0.35, (i, ch)


def test_shadow_diagonal_direction_is_removed():
    """`ab3`: Schatten nach rechts unten (An-Nachbar oben und links)."""
    s = sample_image(_shadow_image(TEXT_SHADOW, dx_cols=0.6, dy_rows=0.6), GRID, range(9))
    n = normalized(s)
    for d in ((-1, 0), (0, -1), (-1, -1)):
        assert np.mean(_off_dots_next_to_on(TEXT_SHADOW, n, d)) < 0.1, d


def test_shadow_coefficients_zero_without_shadow_and_output_unchanged():
    s = sample_image(render(TEXT_SHADOW), GRID, range(9))
    zero = SHIFTS.index((0, 0))
    alphas = shadow_coefficients(normalized(s, remove_shadow=False)[:, zero])
    assert max(alphas.values()) < 0.05
    assert np.abs(normalized(s) - normalized(s, remove_shadow=False)).max() < 0.05


def test_shadow_removal_leaves_on_dots_unchanged():
    s = sample_image(_shadow_image(TEXT_SHADOW), GRID, range(9))
    before = normalized(s, remove_shadow=False)
    after = normalized(s)
    on = before >= 0.5
    assert np.array_equal(before[on], after[on])
    assert (after <= before + 1e-6).all()


def test_shadow_coefficients_need_enough_off_dots_per_direction():
    """Nur ein Zeichen: je Richtung weniger als 10 Aus-Punkte mit An-Nachbar
    -> kein Abzug in dieser Richtung (nicht aus wenigen Punkten schaetzen)."""
    s = sample_image(_shadow_image("   .     "), GRID, range(9))
    zero = SHIFTS.index((0, 0))
    alphas = shadow_coefficients(normalized(s, remove_shadow=False)[:, zero])
    assert all(a == 0.0 for a in alphas.values())


def test_shadow_global_ink_path_is_not_changed():
    """Leerzellenpruefung (`ink` gesetzt): kein Abzug."""
    s = sample_image(_shadow_image(TEXT_SHADOW), GRID, range(9))
    assert np.array_equal(normalized(s, ink=s.ink), normalized(s, ink=s.ink, remove_shadow=False))
