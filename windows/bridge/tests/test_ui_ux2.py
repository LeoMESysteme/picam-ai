"""UX2 Runde UI-1: Symbole, Bausteine, Kopf, Kacheln, Werkzeugfenster, Protokoll-Export, Fake-Port."""
import os
import re
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DISPREAD_UI_MOTION', '0')

import pytest
from dispread_bridge_app.ui import icons, texts, theme
from dispread_bridge_app.ui.fake import FakeController
from dispread_bridge_app.ui.port import MODES
from dispread_bridge_app.ui.tool_windows import ToolWindow
from dispread_bridge_app.ui.widgets import CopyField, IconButton
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPushButton, QToolButton

UI = Path(__file__).resolve().parents[1] / 'src' / 'dispread_bridge_app' / 'ui'


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    made = []

    def _make(state='B1', dark=False, size=(440, 720)):
        fc = FakeController(state)
        w = MainWindow(fc, dark=dark)
        w.resize(*size)
        w.show()
        made.append(w)
        QTest.qWait(30)
        return fc, w
    yield _make
    for w in made:
        w.force_close()
        w.deleteLater()
    QApplication.processEvents()


def settle(w, ms=50):
    QTest.qWait(ms)
    w.pool.waitForDone(5000)
    QTest.qWait(80)


def texts_of(widget) -> str:
    return ' | '.join(lab.text() for lab in widget.findChildren(QLabel))


# ---------------------------------------------------------------- Symbole
def test_embedded_icons_are_plain_svg_paths_only():
    assert icons.VERSION == '1.1.344' and icons.PACKAGE == '@fluentui/svg-icons'
    for name, svg in icons.SVG.items():
        assert re.fullmatch(r'<svg xmlns="http://www.w3.org/2000/svg" width="(\d+)" height="\1" viewBox="0 0 \1 \1">'
                            r'(<path d="[0-9A-Za-z .,\-]+"/>)+</svg>', svg), name
        assert 'script' not in svg.lower() and 'href' not in svg.lower()


def test_license_notice_present():
    notice = (UI.parents[2] / 'THIRD_PARTY_NOTICES.md').read_text('utf-8')
    assert 'MIT License' in notice and 'Copyright (c) 2020 Microsoft Corporation' in notice and '1.1.344' in notice
    assert 'MIT' in (UI / 'icons.py').read_text('utf-8').split('"""')[1]


@pytest.mark.parametrize('dark', [False, True])
def test_icons_render_tinted_from_tokens(app, dark):
    theme.apply_theme(app, dark)
    want = QColor(theme.tokens()['text2'])
    for name in [k for k in icons.SVG if '@' not in k]:
        pm = theme.icon_pixmap(name, 'text2', 16, 2.0)
        assert not pm.isNull() and pm.width() == 32, name
        img = pm.toImage()
        colors = {img.pixelColor(x, y).rgb() & 0xFFFFFF for x in range(32) for y in range(32)
                  if img.pixelColor(x, y).alpha() == 255}
        assert want.rgb() & 0xFFFFFF in colors, name
    assert theme.icon_pixmap('copy', 'text2', 16, 2.0) is theme.icon_pixmap('copy', 'text2', 16, 2.0)   # Cache
    for tone in ('ok', 'warn', 'err', 'info', 'unclear', 'unused'):
        assert not theme.status_pixmap(tone, 16).isNull()
    with pytest.raises(KeyError):
        theme.icon_pixmap('gibt_es_nicht')


def test_no_unicode_glyph_buttons_and_no_popup_anywhere(win):
    for f in UI.glob('*.py'):
        src = f.read_text('utf-8')
        assert 'Qt.Popup' not in src and 'WindowType.Popup' not in src, f.name
        assert "'×'" not in src, f.name
    fc, w = win('B1')
    w.status_view.chips[0].click()
    w._show_details()
    QTest.qWait(50)
    for top in QApplication.topLevelWidgets():
        # Auswahllisten von QComboBox (Qt-eigener Container) sind kein Flyout-Ersatz und erlaubt
        assert ((top.windowFlags() & Qt.WindowType.Popup) != Qt.WindowType.Popup or top.inherits('QMenu')
                or top.metaObject().className() == 'QComboBoxPrivateContainer')
    for b in w.findChildren(QPushButton) + w.findChildren(QToolButton):
        assert not (len(b.text().strip()) == 1 and not b.text().strip().isalnum()), b.objectName()


def test_icon_button_requires_tooltip_and_has_accessible_name(app):
    b = IconButton('settings', 'Einstellungen')
    assert b.toolTip() == b.accessibleName() == 'Einstellungen'
    assert (b.width(), b.height()) == (32, 32) and b.property('flat') is True
    assert b.focusPolicy() != Qt.FocusPolicy.NoFocus
    with pytest.raises(ValueError):
        IconButton('settings', '')


# ---------------------------------------------------------------- Bausteine
def test_motion_switch_follows_environment(monkeypatch):
    monkeypatch.setenv(theme.MOTION_ENV, '0')
    assert theme.motion_enabled() is False
    monkeypatch.setenv(theme.MOTION_ENV, '1')
    assert theme.motion_enabled() is True


def test_copy_field_copies_raw_value_and_confirms(app):
    fp = 'a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de'
    f = CopyField('TLS-Fingerabdruck (SHA-256)', fp, display=fp.replace(' 19d6', '\n19d6'))
    f._reset.setInterval(60)
    f.show()
    f.copy_button.click()
    assert QGuiApplication.clipboard().text() == fp                       # vollständig, nie gekürzt
    assert f.confirming and f.copy_button.toolTip() == texts.COPIED and f.copy_button.icon_name == 'checkmark'
    QTest.qWait(150)
    assert not f.confirming and f.copy_button.icon_name == 'copy' and f.copy_button.toolTip() == texts.COPY_TIP
    assert f.value_label.property('typo') == 'data' and f.name_label.property('typo') == 'caption'
    empty = CopyField('Pi-ID', '–')
    assert empty.copy_button.isHidden()


def test_typography_roles_as_qss_property(app):
    lab = theme.set_typo(QLabel('x'), 'section')
    assert lab.property('typo') == 'section'
    data = theme.set_typo(QLabel('COM4'), 'data')
    assert data.property('mono') is True and data.font().styleHint() == data.font().StyleHint.Monospace
    sheet = theme.qss(theme.LIGHT)
    for role in theme.TYPO:
        assert f'QLabel[typo="{role}"]' in sheet


# ---------------------------------------------------------------- Kopf
def test_header_mode_button_heartbeat_and_dut_line(win):
    fc, w = win('B1')
    h = w.status_view.header
    assert h.mode_button.label.text() == 'Netzwerk' and 'Netzwerk (LAN)' in h.mode_button.toolTip()
    assert h.title.text() == 'Prüfstand 2'
    assert h.heartbeat.isVisibleTo(w) and h.heartbeat.contact and not h.ring.isVisibleTo(w)
    assert 'nichts über die Weitergabe' in h.heartbeat.toolTip()
    before = h.heartbeat.pulses
    fc.tick()
    QTest.qWait(300)
    assert h.heartbeat.pulses == before + 1
    w.refresh()
    assert h.heartbeat.pulses == before + 1                  # nur bei neuem activity_seq, nie beim Neuzeichnen
    assert texts.DUT_LOCK_LINE in h.dut.text() and h.dut.isVisibleTo(w)
    h.mode_button.click()
    settle(w)
    assert w.tool_windows['modes'].isVisible() and 'open_modes' not in w.unhandled


@pytest.mark.parametrize('state', ('B3', 'B3c'))
def test_connecting_or_backoff_shows_ring_instead_of_heartbeat(win, state):
    _, w = win(state)
    h = w.status_view.header
    assert h.ring.isVisibleTo(w) and not h.heartbeat.isVisibleTo(w)


def test_without_contact_heartbeat_rests_hollow_and_neutral(win):
    _, w = win('B10')
    h = w.status_view.header
    assert h.heartbeat.isVisibleTo(w) and not h.heartbeat.contact


def test_mode_button_without_chosen_way(win):
    _, w = win('B1')
    from dataclasses import replace
    fc = w.controller
    fc.set(context=replace(fc.context(), route_mode=None, route=None))
    w.refresh()
    assert w.status_view.header.mode_button.label.text() == texts.MODE_NONE
    fc.set(context=replace(fc.context(), route_mode='uart_direct'))
    w.refresh()
    assert w.status_view.header.mode_button.label.text() == 'UART direkt'


@pytest.mark.parametrize('state', ('B1', 'B1tr', 'B3', 'B3c', 'Bdirect', 'usb_missing', 'E2b'))
def test_dut_lock_line_in_every_state(win, state):
    _, w = win(state)
    view = w.stack.currentWidget()
    assert view.dut_label.isVisibleTo(w) and view.dut_label.text()


# ---------------------------------------------------------------- Kacheln
def test_tiles_have_component_icon_info_tooltip_and_state_word(win):
    _, w = win('B1')
    for chip in w.status_view.chips:
        key = chip.view.key
        assert chip.info_icon.toolTip() == texts.CHIP_HELP[key] and chip.info_icon.isVisibleTo(w)
        assert chip.accessibleDescription() == texts.CHIP_HELP[key]
        assert chip.view.word in chip.toolTip() and chip.view.word in chip.accessibleName()
        assert not chip.comp_icon.pixmap().isNull()
    assert 'nicht Empfang' in texts.CHIP_HELP['forward']
    assert 'Verbunden heißt nicht' in texts.CHIP_HELP['pi']


def test_tile_flash_only_on_real_change(win):
    fc, w = win('B1')
    chip = w.status_view.chips[2]
    n = chip.flash.count
    w.refresh()
    assert chip.flash.count == n                              # Neuzeichnen ist kein Zustandswechsel
    fc.set_state('B3')
    w.refresh()
    assert chip.flash.count == n + 1 and not chip.flash.running   # Bewegung aus: Endzustand sofort


def test_tile_heights_equal_and_nothing_clipped_at_both_sizes(win):
    for size in ((380, 560), (440, 720)):
        for state in ('B1', 'B1tr', 'B3'):
            _, w = win(state, size=size)
            QTest.qWait(60)
            sv = w.status_view
            assert len({c.height() for c in sv.chips[:3]}) == 1 and len({c.height() for c in sv.chips[3:]}) == 1
            assert len({c._inline for c in sv.chips}) == 1
            assert sv.scroll.horizontalScrollBar().maximum() == 0
            for c in sv.chips:
                assert c.mapTo(sv.body_widget, c.rect().topRight()).x() <= sv.body_widget.width()


# ---------------------------------------------------------------- Fenster
def test_chip_window_single_instance_switches_content(win):
    _, w = win('B1')
    w.status_view.chips[0].click()
    QTest.qWait(50)
    first = w.tool_windows['chip']
    w.status_view.chips[2].click()
    QTest.qWait(50)
    assert w.tool_windows['chip'] is first and first.isVisible()
    assert 'Pi-ID' in texts_of(first) and w.status_view.chips[2].isChecked() and not w.status_view.chips[0].isChecked()
    assert len([t for t in QApplication.topLevelWidgets() if isinstance(t, ToolWindow) and t.kind == 'chip'
                and t.parentWidget() is w]) == 1
    fields = [f for f in first.findChildren(CopyField) if f.name_label.text() == 'TLS-Fingerabdruck (SHA-256)']
    assert fields and fields[0].value == w.controller.context().fingerprint


def test_tool_window_remembers_position_per_kind(win):
    _, w = win('B1')
    w._show_lock()
    lock = w.tool_windows['lock']
    lock.move(123, 77)
    QTest.qWait(30)
    lock.close()
    QTest.qWait(30)
    w._show_lock()
    assert w.tool_windows['lock'] is lock and lock.pos().x() == 123 and lock.pos().y() == 77
    assert ToolWindow._positions['lock'] == lock.pos()


def test_info_window_lists_copyable_technical_values(win):
    _, w = win('B1')
    w.status_view.details_button.click()
    settle(w)
    info = w.tool_windows['info']
    names = {f.name_label.text(): f for f in info.findChildren(CopyField)}
    for n in ('Version', 'Protokoll', 'Lauf-ID', 'Pi-ID'):
        assert n in names and not names[n].copy_button.isHidden(), n
    for n in ('Endpunkt', 'TLS-Fingerabdruck (SHA-256)', 'Brückenseite', 'GSVmulti-Seite'):
        assert n not in names, n                     # steht in den Einstellungen, nicht doppelt in der Info
    assert texts.ICON_CREDIT in texts_of(info)


def test_info_window_is_about_only_and_opens_settings(win):
    _, w = win('B1')
    w._show_details()
    settle(w)
    info = w.tool_windows['info']
    assert not info.findChildren(QCheckBox)          # Autostart steht nur in den Einstellungen
    assert 'automatisch' not in texts_of(info)
    btn = [b for b in info.findChildren(QPushButton) if b.text() == texts.INFO_OPEN_SETTINGS]
    assert len(btn) == 1
    btn[0].click()
    settle(w)
    assert w.tool_windows['settings'].isVisible()


def test_toolbar_has_icons_with_names_and_no_diagnose_wording(win):
    _, w = win('B1')
    sv = w.status_view
    assert [b.toolTip() for b in (sv.settings_button, sv.export_button, sv.details_button, sv.exit_button)] == \
        ['Einstellungen', 'Protokolle exportieren', 'Info', 'Brücke beenden …']
    for b in w.findChildren(QPushButton) + w.findChildren(QToolButton):
        assert 'Diagnose' not in b.text() and 'Diagnose' not in b.accessibleName()
    bar = texts.action_bar(*_stopped())
    assert bar.buttons == (('Protokolle exportieren', 'export_diagnostics', True),)


def _stopped():
    from dispread_bridge_app.worker import WorkerStatus
    fc = FakeController('B1')
    return fc.snapshot(), WorkerStatus('blocked', False, False, 'unknown_delivery'), fc.context()


def test_export_window_shows_contents_then_saves_and_opens_folder(win, tmp_path):
    fc, w = win('B1')
    w.status_view.export_button.click()
    settle(w)
    ex = w.tool_windows['export']
    assert ex.isVisible() and ('diagnostics_contents',) in fc.calls
    shown = texts_of(ex)
    assert 'summary.json' in shown and 'details.jsonl' in shown and 'kein Gesundheitscheck' in shown
    dest = tmp_path / 'protokolle.zip'
    w.pick_save = lambda: str(dest)
    opened = []
    w.open_folder = opened.append
    ex.save_button.click()
    settle(w)
    assert ('export_diagnostics', dest) in fc.calls and ex.state == 'done'
    fields = ex.findChildren(CopyField)
    assert fields and fields[0].value == str(dest)
    folder = [b for b in ex.findChildren(QPushButton) if b.text() == texts.OPEN_FOLDER][0]
    folder.click()
    assert opened == [str(tmp_path)]
    assert not w.status_view.busy_bar.busy and w.status_view.busy_bar.isHidden()


def test_export_cancelled_save_dialog_changes_nothing(win):
    fc, w = win('B1')
    w.do_action('export_diagnostics')
    settle(w)
    w.pick_save = lambda: ''
    w.tool_windows['export'].save_button.click()
    settle(w)
    assert not [c for c in fc.calls if c[0] == 'export_diagnostics'] and w.tool_windows['export'].state == 'idle'


def test_hidden_windows_stop_animations(win, monkeypatch):
    monkeypatch.setenv(theme.MOTION_ENV, '1')
    _, w = win('B3')
    ring = w.status_view.header.ring
    QTest.qWait(30)
    assert ring.running
    w.hide()
    QTest.qWait(30)
    assert not ring.running


# ---------------------------------------------------------------- Fake-Port (UX2)
def test_fake_port_checks_and_modes(tmp_path):
    fc = FakeController('B1')
    assert tuple(m.mode for m in fc.modes()) == MODES
    assert [m.mode for m in fc.modes() if m.active] == ['network']
    assert fc.check_endpoint('pi.local').state == 'ok'
    bad = fc.check_endpoint('gibtsnicht.example')
    assert bad.state == 'err' and bad.message == 'Name nicht auflösbar' and bad.detail
    assert fc.check_endpoint('').state == 'err'
    assert fc.check_port_pair('COM4', 'COM4').state == 'err'
    assert fc.check_pairing_code('x' * 43).state == 'ok' and fc.check_pairing_code('123').state == 'err'
    assert all(p.kind == 'usb_serial' for p in fc.list_adapters())
    out = fc.export_session_file(tmp_path / 'GSVmulti_Test_COM5.ucf')
    assert out.path.read_bytes() and out.port == 'COM5' and len(out.sha256) == 64
    assert [n for n, _ in fc.diagnostics_contents()] == ['summary.json', 'details.jsonl']
    idle = FakeController('B10')
    idle.select_mode('uart_direct')
    assert idle.context().mode == 'setup' and idle.context().route_mode == 'uart_direct'
    idle.leave_setup()
    assert idle.context().mode == 'operate'


def test_all_six_tile_icons_and_three_way_icons_exist():
    for name in list(texts.CHIP_ICON.values()) + list(texts.MODE_ICON.values()) + [
            'settings', 'document_arrow_down', 'info', 'power', 'copy', 'checkmark', 'dismiss', 'arrow_sync',
            'lock_closed', 'chevron_down', 'folder_open']:
        assert name in icons.SVG, name



def test_tile_words_get_soft_hyphens_only_when_too_narrow(win):
    assert texts.hyphenate('Testfreigabe') == 'Test­freigabe'
    assert texts.hyphenate('nicht abgenommen').replace('­', '') == 'nicht abgenommen'
    _, wide = win('B1tr', size=(440, 720))
    out = wide.status_view.chips[3]
    assert '­' not in out.word.text() or out.word.width() < out.word.fontMetrics().horizontalAdvance('Testfreigabe')
    assert '­' not in out.accessibleName()
