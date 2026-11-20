"""Farbpaletten der picam-Konsole: vollständig, gültig, lesbar."""

from __future__ import annotations

import pytest
from textual.color import Color

from dispread.admin import ui


def contrast(a: str, b: str) -> float:
    """WCAG-Kontrast zweier Farben (Alpha wird ignoriert)."""

    def lum(value: str) -> float:
        color = Color.parse(value)

        def channel(c: int) -> float:
            c = c / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b)

    high, low = sorted((lum(a), lum(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


PALETTES = list(ui.PALETTES.values())
TEXT_ROLES = ('text', 'text_soft', 'text_muted', 'accent', 'ok', 'warn', 'fail', 'unknown')
BACKGROUNDS = ('canvas', 'surface', 'raised', 'band')


@pytest.mark.parametrize('palette', PALETTES, ids=lambda p: p.name)
def test_palette_tokens_are_valid_colors(palette):
    for role, value in palette.colors().items():
        Color.parse(value)  # wirft bei ungültigen Werten
        assert value.startswith('#'), role
    assert set(palette.variables()) == {'picam-' + k.replace('_', '-') for k in palette.colors()}


@pytest.mark.parametrize('palette', PALETTES, ids=lambda p: p.name)
def test_text_is_readable_on_every_surface(palette):
    for role in TEXT_ROLES:
        for background in BACKGROUNDS:
            ratio = contrast(getattr(palette, role), getattr(palette, background))
            assert ratio >= 4.5, f'{palette.name}: {role} auf {background} nur {ratio:.2f}:1'


@pytest.mark.parametrize('palette', PALETTES, ids=lambda p: p.name)
def test_controls_and_focus_are_distinct(palette):
    p = palette
    assert contrast(p.on_accent, p.accent_strong) >= 4.5      # aktiver Tab, Knopf mit Fokus
    assert contrast(p.on_accent_deep, p.accent_deep) >= 4.5   # Marke, Hauptknopf
    assert contrast(p.text, p.control) >= 4.5                 # Knopfbeschriftung
    assert contrast(p.text, p.field) >= 4.5 and contrast(p.text, p.field_focus) >= 4.5
    assert contrast(p.select_fg, p.select_bg) >= 4.5
    assert contrast(p.accent_strong, p.raised) >= 3.0          # Fokusrand am Abschnitt
    assert contrast(p.disabled_fg, p.disabled_bg) >= 3.0
    # Stufen sichtbar, aber weich: Grund < Abschnitt < hervorgehoben, ohne harte Sprünge
    assert 1.03 <= contrast(p.canvas, p.surface) <= 1.4
    assert 1.03 <= contrast(p.surface, p.raised) <= 1.4


def test_palette_from_env_names_and_aliases():
    assert ui.palette_from_env('A') is ui.SCHIEFER
    assert ui.palette_from_env('petrol') is ui.PETROL
    assert ui.palette_from_env(' Hell ') is ui.HELL
    assert ui.palette_from_env('unbekannt').name == ui.DEFAULT_PALETTE
    assert ui.palette_from_env('').name == ui.DEFAULT_PALETTE


def test_theme_carries_palette_variables():
    theme = ui.make_theme(ui.HELL)
    assert theme.dark is False
    assert theme.variables['picam-surface'] == ui.HELL.surface
    assert theme.background == ui.HELL.canvas


@pytest.mark.parametrize('palette', PALETTES, ids=lambda p: p.name)
def test_inset_values_and_badges_are_readable(palette):
    p = palette
    # eingelassene Werte: Wert und Einheit lesbar, Feld vom Grund unterscheidbar
    for role in ('text', 'text_muted', 'accent', 'ok', 'warn', 'fail'):
        assert contrast(getattr(p, role), p.inset) >= 4.5, role
    assert contrast(p.surface, p.inset) >= 1.2
    assert contrast(p.canvas, p.inset) >= 1.08
    # Abzeichen: Statusfarbe auf ihrer Tönung
    for tone, tint in (('ok', 'tint_ok'), ('warn', 'tint_warn'), ('fail', 'tint_fail'), ('off', 'tint_off'),
                       ('unknown', 'tint_off'), ('accent_strong', 'tint_info')):
        assert contrast(getattr(p, tone), getattr(p, tint)) >= 4.5, tone


def test_icons_have_single_cell_glyphs_and_ascii_fallback(monkeypatch):
    from rich.cells import cell_len

    from dispread.admin import widgets
    banned = set('✔⚙⏸⏹ℹ⚠⚡')
    for name, (glyph, plain) in widgets.ICONS.items():
        assert cell_len(glyph) == 1 and glyph not in banned, name
        assert plain.isascii() and plain, name
    monkeypatch.setenv('PICAM_ASCII', '1')
    assert widgets.icon('camera') == 'o'
    assert widgets.badge('ok', 'läuft', 'on').plain == ' * läuft '
