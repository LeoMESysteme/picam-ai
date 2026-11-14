"""Schrift: nie ohne generischen Fallback (Windows löst sonst auf Serif/Times)."""
import os
import re
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from dispread_bridge_app.ui import theme
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel

UI = Path(__file__).resolve().parents[1] / 'src' / 'dispread_bridge_app' / 'ui'


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('dark', [False, True])
def test_every_qss_font_family_has_segoe_and_generic_fallback(dark):
    sheet = theme.qss(theme.DARK if dark else theme.LIGHT)
    decls = re.findall(r'font-family:\s*([^;]+);', sheet)
    assert decls
    for d in decls:
        mono = 'monospace' in d
        assert mono or ('Segoe UI' in d and d.strip().endswith('sans-serif')), d
        assert not mono or 'Consolas' in d
    base = re.search(r'\nQWidget \{[^}]*font-family:[^}]*\}', sheet)
    assert base and 'Segoe UI Variable Text' in base.group(0) and 'sans-serif' in base.group(0)


def test_no_qss_font_rule_without_family_chain_for_text_widgets():
    sheet = theme.qss(theme.LIGHT)
    assert 'serif' not in re.sub(r'sans-serif', '', sheet).lower()


@pytest.mark.parametrize('mono', [False, True])
def test_make_font_has_family_list_and_style_hint(app, mono):
    f = theme.make_font(10, mono=mono)
    assert f.families() == (theme.MONO_FAMILIES if mono else theme.FONT_FAMILIES)
    assert f.styleHint() == (QFont.StyleHint.Monospace if mono else QFont.StyleHint.SansSerif)


def test_no_raw_qfont_construction_outside_theme():
    for f in UI.glob('*.py'):
        if f.name == 'theme.py':
            continue
        assert 'QFont(' not in f.read_text('utf-8'), f.name
        assert 'setFamily(' not in f.read_text('utf-8'), f.name


def test_mono_labels_carry_property_for_qss(app):
    from dispread_bridge_app.ui.setup_view import fingerprint_label
    lab = fingerprint_label('aaaa bbbb cccc dddd')
    assert isinstance(lab, QLabel) and lab.property('mono') is True
    assert lab.font().styleHint() == QFont.StyleHint.Monospace
