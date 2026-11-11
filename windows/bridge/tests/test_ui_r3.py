"""UX2 Runde 3 (Gestaltung): Bewegung und Neuaufbau, Fehler aus Teil B, Wertfeld, Zustand über Form,
Session-Checkliste, Textbudget."""
import os
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DISPREAD_UI_MOTION', '0')
os.environ.setdefault('DISPREAD_UI_FIRST_RUN_MODES', '0')

import pytest
from dispread_bridge_app.ui import texts, tooltips
from dispread_bridge_app.ui.fake import STATES, FakeController
from dispread_bridge_app.ui.widgets import Badge
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QStyle, QToolButton, QWidget

UI = Path(__file__).resolve().parents[1] / 'src' / 'dispread_bridge_app' / 'ui'


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    made = []

    def _make(state='B1', dark=False, size=(440, 720)):
        fc = FakeController(state)
        w = MainWindow(fc, dark=dark, first_run_modes=False)
        w.resize(*size)
        w.show()
        made.append(w)
        settle(w)
        return fc, w
    yield _make
    for w in made:
        settle(w, 10)
        w.force_close()
        w.deleteLater()
    QApplication.processEvents()


def settle(w, ms=40):
    QTest.qWait(ms)
    end = time.monotonic() + 8
    while w.pool.activeThreadCount() and time.monotonic() < end:
        QTest.qWait(10)
    QTest.qWait(ms)


def texts_of(widget) -> str:
    return ' | '.join(lab.text() for lab in widget.findChildren(QLabel))


# ================================================================ R3-5 Neuaufbau ohne Verlust
def test_setup_rebuild_keeps_typed_endpoint_and_focus(win):
    fc, w = win('E3')
    sv = w.setup_view
    edit = sv.endpoint_edit
    assert edit is not None
    edit.setFocus(Qt.FocusReason.OtherFocusReason)
    edit.setText('pi.local')
    edit.setCursorPosition(3)
    before = id(edit)
    data = dict(fc.context().setup.data, found_items=(('https://pi.local', 'aus dem Profil', True),),
                choices={'found': ('https://pi.local',)})
    fc.set(context=replace(fc.context(), setup=replace(fc.context().setup, data=data)))
    w.refresh()
    settle(w)
    assert id(sv.endpoint_edit) != before                       # es wurde wirklich neu aufgebaut …
    assert sv.endpoint_edit.text() == 'pi.local'                # … und der Text blieb
    assert sv.focusWidget() is sv.endpoint_edit and sv.endpoint_edit.cursorPosition() == 3


def test_setup_rebuild_keeps_pairing_code_and_fingerprint_check(win):
    fc, w = win('E2b')
    sv = w.setup_view
    sv.checks['fp_ok'].setChecked(True)
    sv.code_edit.setText('x' * 43)
    ctx = fc.context()
    fc.set(context=replace(ctx, setup=replace(ctx.setup, data=dict(ctx.setup.data, extra='1'))))
    w.refresh()
    settle(w)
    assert sv.code_text() == 'x' * 43 and sv.checked('fp_ok')


def test_setup_new_profile_drops_fingerprint_confirmation(win):
    fc, w = win('E2b')
    sv = w.setup_view
    sv.checks['fp_ok'].setChecked(True)
    fc.set(context=replace(fc.context(), fingerprint='ffff 0000'))
    w.refresh()
    settle(w)
    assert not sv.checked('fp_ok')


def test_rescan_without_hits_says_nothing_found_and_keeps_text(win):
    fc, w = win('E3')
    sv = w.setup_view
    sv.endpoint_edit.setText('pi.local')
    w.do_action('rescan')
    settle(w)
    assert ('rescan',) in fc.calls
    assert sv.endpoint_edit.text() == 'pi.local'
    assert texts.EMPTY_CHOICE['found'] == 'Nichts gefunden'
    assert any(lab.text() == 'Nichts gefunden' for lab in sv.findChildren(QLabel))


def test_r3_no_step_transition_animation_code():
    for f in UI.glob('*.py'):
        src = f.read_text(encoding='utf-8')
        assert 'slide_in(' not in src and 'fade_in(' not in src and 'ColorFlash' not in src


# ================================================================ R3-6 Fehler aus Teil B
def test_tooltips_are_boxes_with_300_ms_delay_and_max_320_px(app, win):
    win('B1')
    assert app.style().styleHint(QStyle.StyleHint.SH_ToolTip_WakeUpDelay) == tooltips.DELAY_MS == 300
    long = 'Ein langer Erklärungstext mit vielen Wörtern. ' * 12
    html = tooltips.box_html(long)
    assert html.startswith('<table width="320"')
    short = tooltips.box_html('Kurz')
    assert int(short.split('"')[1]) < 120 and '<table' in short
    assert tooltips.box_html('a <b>b</b>').count('<b>') == 1            # Rich Text bleibt Rich Text
    assert '&lt;' in tooltips.box_html('x < y')                       # reiner Text wird maskiert


def test_tooltip_filter_shows_box_for_every_widget(win, monkeypatch):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QHelpEvent
    _, w = win('B1')
    shown = []
    monkeypatch.setattr(tooltips, 'show', lambda text, pos, widget=None: shown.append(text))
    btn = w.status_view.settings_button
    QApplication.sendEvent(btn, QHelpEvent(QHelpEvent.Type.ToolTip, QPoint(3, 3), QPoint(0, 0)))
    assert shown == [texts.SETTINGS]


def test_tool_window_height_and_position_stay_on_screen(win):
    from dispread_bridge_app.ui.tool_windows import ToolWindow
    _, w = win('B1')
    tw = ToolWindow('big', 'Groß', w)
    avail = w.screen().availableGeometry()
    tw.set_content('k', lambda body: [body.addWidget(QLabel('Zeile\n' * 4)) for _ in range(120)])
    ToolWindow._positions['big'] = avail.bottomRight()               # weit außerhalb gemerkt
    tw.present()
    QTest.qWait(80)
    assert tw.height() <= avail.height() - ToolWindow.SCREEN_MARGIN
    fg = tw.frameGeometry()
    assert fg.left() >= avail.left() and fg.top() >= avail.top()
    assert fg.right() <= avail.right() and fg.bottom() <= avail.bottom()
    tw.close()


def test_enter_triggers_focused_buttons_icon_buttons_and_tiles(win):
    fc, w = win('B1')
    sv = w.status_view
    hits = []
    sv.action.connect(hits.append)
    sv.settings_button.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(sv.settings_button, Qt.Key.Key_Return)
    assert hits[-1] == 'open_settings'
    sv.export_button.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(sv.export_button, Qt.Key.Key_Enter)
    assert hits[-1] == 'export_diagnostics'
    opened = []
    sv.chip_clicked.connect(opened.append)
    sv.chips[0].setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(sv.chips[0], Qt.Key.Key_Return)
    QTest.qWait(30)
    assert opened == [0]


def test_enter_in_tool_window_clicks_focused_button_not_the_default(win):
    fc, w = win('B1')
    w.do_action('export_diagnostics')
    settle(w)
    ew = w.tool_windows['export']
    w.pick_save = lambda: ''                                         # kein echter Dateidialog
    saves = []
    ew.save_requested.connect(lambda: saves.append(1))
    ew.save_button.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(ew.save_button, Qt.Key.Key_Return)
    assert saves == [1]
    closes = []
    ew.close_button.show()
    ew.close_button.clicked.connect(lambda: closes.append(1))
    ew.close_button.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(ew.close_button, Qt.Key.Key_Return)
    assert closes == [1] and saves == [1]


def test_arrow_keys_switch_mode_cards(win):
    fc, w = win('B10')
    w.do_action('open_modes')
    settle(w)
    mw = w.tool_windows['modes']
    mw.cards['network'].radio.setFocus(Qt.FocusReason.TabFocusReason)
    assert mw.selected == 'network'
    order = list(mw.cards)
    QTest.keyClick(mw.cards['network'].radio, Qt.Key.Key_Down)
    nxt = order[(order.index('network') + 1) % 3]
    assert mw.selected == nxt and mw.cards[nxt].radio.isChecked()
    QTest.keyClick(mw.cards[nxt].radio, Qt.Key.Key_Up)
    assert mw.selected == 'network'
    QTest.keyClick(mw.cards['network'].radio, Qt.Key.Key_Left)       # wie „hoch“
    assert mw.selected == order[order.index('network') - 1]


def test_demo_next_and_back_walk_the_setup_flow(win):
    fc, w = win('E1')
    seen = []
    for _ in range(4):
        w.do_action('next')
        settle(w)
        seen.append(fc.context().setup.variant)
    assert seen == ['E2b', 'E3', 'E4locked', 'E5']
    w.do_action('back')
    settle(w)
    assert fc.context().setup.variant == 'E4locked'
    fc2, w2 = win('D1')
    seen = []
    for _ in range(3):
        w2.do_action('next')
        settle(w2)
        seen.append(fc2.context().setup.variant)
    assert seen == ['D2', 'D3', 'D4']
    w2.do_action('next')                                             # letzter Schritt: Einrichtung beendet
    settle(w2)
    assert fc2.context().setup is None and fc2.context().mode == 'operate'


def test_tray_exit_brings_window_to_front_before_the_dialog(win):
    fc, w = win('B1')
    w.hide()
    seen = []
    w.confirm_exit = lambda: seen.append(w.isVisible()) or False
    w.exit_bridge_from_tray()
    assert seen == [True]


def test_exit_dialog_is_shown_raised(win):
    _, w = win('B1')
    dlg = w.build_exit_dialog()
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    assert dlg.isVisible()
    dlg.reject()


def test_mode_switch_when_only_connected_disconnects_after_confirmation(win):
    fc, w = win('B1')                                                # verbunden, DUT gesperrt: keine Übertragung
    assert not texts.is_transmitting(fc.context())
    w.do_action('open_modes')
    settle(w)
    mw = w.tool_windows['modes']
    assert all(c.radio.isEnabled() for c in mw.cards.values())
    asked = []
    w.confirm_mode_switch = lambda: asked.append(1) or False
    w._select_mode('uart_direct')
    settle(w)
    assert asked == [1] and not [c for c in fc.calls if c[0] in ('disconnect', 'select_mode')]
    w.confirm_mode_switch = lambda: asked.append(2) or True
    w._select_mode('uart_direct')
    settle(w)
    names = [c[0] for c in fc.calls if c[0] in ('disconnect', 'select_mode')]
    assert names == ['disconnect', 'select_mode']
    assert asked == [1, 2]


def test_mode_switch_locked_only_during_real_transmission_with_disconnect_button(win):
    fc, w = win('B1x')                                               # Freigabe mit Lauf = Übertragung
    assert texts.is_transmitting(fc.context())
    w.do_action('open_modes')
    settle(w)
    mw = w.tool_windows['modes']
    for k in ('uart_direct', 'uart_bridge'):
        card = mw.cards[k]
        assert not card.radio.isEnabled() and card.disconnect_button is not None
        assert card.reason_label.text()
    assert mw.cards['network'].disconnect_button is None
    asked = []
    w.confirm_disconnect = lambda: asked.append(1) or True
    mw.cards['uart_direct'].disconnect_button.click()
    settle(w)
    assert asked == [1] and ('disconnect',) in fc.calls


@pytest.mark.parametrize('state,expect', [('B1', False), ('B1x', True), ('B1tr', True), ('B5', True)])
def test_is_transmitting(state, expect):
    assert texts.is_transmitting(STATES[state][2]) is expect


# ================================================================ R3-1 Wertfeld
def test_value_field_click_and_keyboard_copy_with_1_2_s_check(app):
    from dispread_bridge_app.ui.widgets import ValueField
    f = ValueField('Port', 'COM9')
    f._reset.setInterval(60)
    f.show()
    assert ValueField.CONFIRM_MS == 1200 and f.box.property('valueField') is True
    QTest.mouseClick(f.box, Qt.MouseButton.LeftButton)
    assert QGuiApplication.clipboard().text() == 'COM9' and f.confirming
    QTest.qWait(120)
    assert not f.confirming
    QGuiApplication.clipboard().setText('x')
    f.box.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(f.box, Qt.Key.Key_Return)
    assert QGuiApplication.clipboard().text() == 'COM9'
    empty = ValueField('Pi-ID', '–')
    assert empty.copy_button.isHidden() and empty.value_label.property('empty') is True


@pytest.mark.parametrize('dark', (False, True))
def test_value_field_ground_token(app, dark):
    from dispread_bridge_app.ui import theme
    theme.apply_theme(app, dark)
    assert theme.tokens()['field'] == ('#323232' if dark else '#ededed')
    assert 'QFrame[valueField="true"]' in theme.qss(theme.tokens())
    theme.apply_theme(app, False)


def test_no_values_inside_sentences_in_setup_texts():
    for variant, spec in texts.SETUP.items():
        for blk in spec['blocks']:
            if blk[0] == 'info':
                assert '{' not in blk[3] or variant in ('E5done',), (variant, blk[3])


# ================================================================ R3-4 Zustand über Form
def test_validated_field_border_state_and_icon_before_message(app):
    from dispread_bridge_app.ui.port import CheckResult
    from dispread_bridge_app.ui.widgets import ValidatedField
    e = QLineEdit()
    f = ValidatedField(e, lambda v: CheckResult('err', 'Name nicht auflösbar', 'Schreibweise prüfen'), debounce_ms=0)
    f.show()
    e.setText('x')
    assert e.property('vstate') == 'err'
    row = f.msg_row.layout()
    assert row.itemAt(0).widget() is f.status_slot and row.itemAt(1).widget() is f.message     # Symbol davor
    assert f.icon.isVisibleTo(f) and f.message.text() == 'Name nicht auflösbar'
    assert f.detail_icon.toolTip() == 'Schreibweise prüfen'
    e.setText('')
    assert e.property('vstate') == ''


def test_pairing_code_has_eye_button_instead_of_text(win):
    fc, w = win('E2b')
    sv = w.setup_view
    assert sv.code_edit.echoMode() == QLineEdit.EchoMode.Password and sv.eye_action is not None
    assert 'Code anzeigen' not in texts_of(sv) and 'code_show' not in sv.checks
    sv.eye_action.trigger()
    assert sv.code_edit.echoMode() == QLineEdit.EchoMode.Normal and sv.eye_action.toolTip() == texts.CODE_HIDE
    sv.code_edit.setText('abc')
    ctx = fc.context()
    fc.set(context=replace(ctx, setup=replace(ctx.setup, data=dict(ctx.setup.data, extra='1'))))
    w.refresh()
    settle(w)
    assert sv.code_edit.echoMode() == QLineEdit.EchoMode.Normal            # Zustand überlebt den Neuaufbau


def test_locked_main_action_has_reason_in_tooltip_and_short_line(win):
    fc, w = win('E2b')
    sv = w.setup_view
    b = sv.buttons['pair']
    assert not b.isEnabled() and b.toolTip() == 'Erst Fingerabdruck bestätigen, Code eingeben'
    fc2, w2 = win('E5')
    assert not w2.setup_view.buttons['start_demo_check'].isEnabled()
    assert w2.setup_view.buttons['start_demo_check'].toolTip() == 'Erst die Testsession bestätigen'


def test_leave_button_is_labelled(win):
    _, w = win('E3')
    b = w.setup_view.leave_button
    assert b.text() == 'Verlassen' and b.toolTip() == texts.LEAVE_TIP and isinstance(b, QPushButton)


# ================================================================ R3-3 Session
def test_session_checklist_and_badges_in_setup(win, tmp_path):
    fc, w = win('E4session')
    fc.record_hidden = True
    sv = w.setup_view
    assert 'session_ok' in sv.checks and 'record_hidden_ok' not in sv.checks
    w.pick_session = lambda name: str(tmp_path / name)
    w.do_action('make_session')
    settle(w)
    sv = w.setup_view
    assert {'record_hidden_ok', 'autoscale_ok', 'session_ok'} <= set(sv.checks)
    assert not sv.next_button.isEnabled()
    badges = {b.label.text(): b for b in sv.findChildren(Badge)}
    assert badges['Einkanal'].info.toolTip() == texts.SINGLE_CHANNEL_WARNING          # wörtlich
    assert badges['nicht abgenommen'] and badges['Pflicht']
    assert sv.buttons['open_session_folder'].toolTip() == texts.OPEN_FOLDER
    assert sv.buttons['make_session'].toolTip() == texts.SESSION_AGAIN
    for k in ('record_hidden_ok', 'session_ok'):
        sv.checks[k].setChecked(True)
    assert sv.next_button.isEnabled()


def test_session_panel_in_settings_has_no_port_or_baud_rows(win, tmp_path):
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    labels = texts_of(sw)
    assert texts.SESSION_PORT not in labels and 'Übertragung' not in labels
    assert sw.findChild(QPushButton, 'btn_make_session') is not None


# ================================================================ R3-2 Textbudget
def test_normal_operation_has_no_infobar_and_no_running_text(win):
    fc, w = win('B1')
    sv = w.status_view
    assert sv.infobar.isHidden()
    assert sv.header.dut.text() == texts.DUT_LOCK_LINE
    assert 'GSVmulti erhält absichtlich keine Messwerte' in sv.header.dut_info.toolTip()
    badges = {b.label.text(): b for b in sv.header.findChildren(Badge)}
    assert badges['Einkanal'].info.toolTip() == texts.SINGLE_CHANNEL_WARNING
    assert 'Weitergabe ist nicht Empfang' in badges['kein Empfangsnachweis'].info.toolTip()
    fc2, w2 = win('B2')
    assert w2.status_view.infobar.isHidden()


def test_tile_second_lines_are_short_in_every_demo_state():
    for key, (r, wk, c) in STATES.items():
        if key.startswith(('E', 'D')) and key not in ('E3ok_run', 'E3_run', 'E4locked_run', 'E1ok_run', 'E2ok_run',
                                                      'E5_run', 'E5busy'):
            continue
        for chip in texts.chips(r, wk, c):
            assert len(chip.sub.split()) <= 4, (key, chip.key, chip.sub)


def test_infobar_texts_stay_short_in_every_demo_state():
    for key, (r, wk, c) in STATES.items():
        bar = texts.action_bar(r, wk, c, None)
        if bar is not None:
            assert len(bar.text) <= 100, (key, bar.text)


def test_test_release_line_replaces_lock_line_with_info_for_the_rest(win):
    fc, w = win('B1tr')
    h = w.status_view.header
    assert h.dut.text() == texts.TEST_RELEASE_LINE and len(texts.TEST_RELEASE_LINE) <= 70
    assert 'unmarkiert' in h.dut_info.toolTip()
    names = {b.label.text() for b in h.findChildren(Badge)}
    assert {'Testfreigabe', 'nicht abgenommen'} <= names


# ================================================================ B-09 / B-18 / B-19
def test_combobox_ignores_wheel_without_focus_and_is_strong_focus(win):
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QComboBox
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    cb = sw.findChild(QComboBox, 'settings_gsv_port')
    assert cb.focusPolicy() == Qt.FocusPolicy.StrongFocus
    before = cb.currentIndex()
    ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                     Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(cb, ev)
    assert cb.currentIndex() == before


def test_settings_have_no_way_section_but_autostart_and_theme(win):
    from dispread_bridge_app.ui import theme
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    assert sw.findChild(QWidget, 'settings_way') is None and sw.findChild(QWidget, 'settings_general') is not None
    assert sw.auto_box is not None and texts.AUTO_CONNECT in texts_of(sw)
    sw.theme_buttons['dark'].click()
    settle(w)
    assert theme.is_dark() and theme.stored_preference() is True
    sw = w.tool_windows['settings']
    sw.theme_buttons['light'].click()
    settle(w)
    assert not theme.is_dark() and theme.stored_preference() is False
    sw.theme_buttons['system'].click()
    settle(w)
    assert theme.stored_preference() is None


def test_endpoint_is_readonly_value_field_with_pen_then_check_button(win):
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    e = sw.findChild(QLineEdit, 'settings_endpoint_edit')
    pen = sw.take_over
    assert e.isReadOnly() and e.placeholderText() == texts.ENDPOINT_PLACEHOLDER and 'Übernehmen' not in texts_of(sw)
    assert isinstance(pen, QToolButton) and pen.toolTip() == texts.ENDPOINT_EDIT
    pen.click()
    assert not e.isReadOnly() and pen.toolTip() == texts.ENDPOINT_SAVE and not pen.isEnabled()
    e.setText('gibtsnicht.example')
    QTest.qWait(600)
    settle(w)
    assert e.property('vstate') == 'err' and not pen.isEnabled()
    e.setText('pi.local')
    QTest.qWait(600)
    settle(w)
    assert pen.isEnabled()
    pen.click()
    settle(w)
    assert ('select_endpoint', 'pi.local', True) in fc.calls and e.isReadOnly()


def test_settings_port_pair_same_port_is_an_error_not_silent(win):
    from PySide6.QtWidgets import QComboBox
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    g = sw.findChild(QComboBox, 'settings_gsv_port')
    g.setCurrentIndex(g.findData('COM4'))
    settle(w)
    assert sw.fields['port_pair'].state == 'err'
    assert not any(c[0] == 'set_port_pair' for c in fc.calls)


def test_settings_apply_does_not_rebuild_the_window(win):
    from PySide6.QtWidgets import QComboBox
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    content = sw.content
    g = sw.findChild(QComboBox, 'settings_gsv_port')
    g.setCurrentIndex(g.findData('COM1'))
    settle(w)
    assert ('set_port_pair', 'COM4', 'COM1') in fc.calls
    assert sw.content is content


def test_paired_button_is_icon_button(win):
    from dispread_bridge_app.ui.widgets import IconButton
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    b = w.tool_windows['settings'].findChild(IconButton, 'show_paired')
    assert b is not None and b.toolTip().startswith(texts.PAIRED_TITLE)


def test_radio_rows_are_clickable_as_a_whole(win):
    fc, w = win('E3uart')
    sv = w.setup_view
    rb = sv.radio_buttons[0]
    row = rb.parentWidget()
    other = sv.radio_buttons[1]
    QTest.mouseClick(other.parentWidget(), Qt.MouseButton.LeftButton)
    assert other.isChecked() and row is not other.parentWidget()


def test_uart_direct_shows_route_picture_instead_of_unused_tiles(win):
    fc, w = win('Bdirect')
    sv = w.status_view
    assert sv.route.isVisibleTo(w) and not any(c.isVisibleTo(w) for c in sv.chips)
    assert sv.route.port_field.value == 'COM9' and sv.route.adapter_word.text() == texts.ROUTE_PRESENT
    assert 'nicht benutzt' not in ' '.join(lab.text() for lab in sv.findChildren(QLabel) if lab.isVisibleTo(w))
    fc2, w2 = win('B1')
    assert not w2.status_view.route.isVisibleTo(w2) and all(c.isVisibleTo(w2) for c in w2.status_view.chips)


# ================================================================ Blitzfenster (elternlose Widgets)
def test_no_foreign_top_level_windows_flash_open(app, win, tmp_path):
    """Kein Widget darf kurz als eigenes Fenster erscheinen, weil es vor dem Einhängen gezeigt wurde."""
    from dispread_bridge_app.ui.tool_windows import ToolWindow
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QDialog, QMenu

    seen: list[str] = []

    class Guard(QObject):
        def eventFilter(self, obj, e):
            if e.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
                if not isinstance(obj, (MainWindow, ToolWindow, QMenu, QDialog)) and \
                        type(obj).__name__ not in ('QTipLabel', 'QComboBoxPrivateContainer', 'QFrame') \
                        or (type(obj).__name__ == 'QFrame' and obj.objectName() != ''):
                    seen.append(f'{type(obj).__name__}:{obj.objectName()}')
            return False
    guard = Guard()
    app.installEventFilter(guard)
    try:
        for state in ('B1', 'B1tr', 'B10', 'Bdirect', 'E1', 'E2b', 'E3', 'E3uart', 'E4session', 'E5', 'D1', 'D2', 'D3',
                      'D4'):
            fc, w = win(state)
            w.pick_session = lambda name: str(tmp_path / name)
            w.pick_save = lambda: ''
            if state in ('B1', 'B10', 'Bdirect'):
                for aid in ('open_settings', 'details', 'export_diagnostics', 'open_modes'):
                    w.do_action(aid)
                    settle(w)
                w._show_chip(0)
                w._show_chip(5)
                settle(w)
                w.do_action('show_paired')
                settle(w)
            else:
                w.do_action('make_session') if state in ('E4session', 'D3') else None
                settle(w)
                for _ in range(2):
                    w.do_action('next')
                    settle(w)
    finally:
        app.removeEventFilter(guard)
    assert seen == []


# ================================================================ Hell/Dunkel-Kontraste, Herzschlag
@pytest.mark.parametrize('name,t', (('hell', 'LIGHT'), ('dunkel', 'DARK')))
def test_contrast_text_4_5_icons_3(name, t):
    from dispread_bridge_app.ui import theme
    tok = getattr(theme, t)
    for key in ('text', 'text2', 'ok', 'warn', 'err'):
        assert theme.contrast(tok[key], tok['card']) >= 4.5, (name, key)
        assert theme.contrast(tok[key], tok['mica']) >= 4.5 or key in ('text2',), (name, key)
    for key in ('ok_icon', 'warn_icon', 'err_icon'):
        assert theme.contrast(tok[key], tok['card']) >= 3.0, (name, key)
        assert theme.contrast(tok[key], tok['mica']) >= 2.6, (name, key)
    assert theme.contrast(tok['accent'], tok['card']) >= 4.5


def test_light_layers_are_visibly_separated():
    from dispread_bridge_app.ui import theme
    L = theme.LIGHT
    assert (L['card'], L['mica'], L['mica2'], L['stroke']) == ('#ffffff', '#eeeeee', '#e6e6e6', '#e0e0e0')
    assert theme.contrast(L['card'], L['mica']) > 1.1 and theme.contrast(L['card'], L['field']) > 1.1


def test_selected_card_has_soft_accent_tone(app):
    from dispread_bridge_app.ui import theme
    t = theme.apply_theme(app, False)
    assert t['select'] != t['card'] and 'background: ' + t['select'] in theme.qss(t)


def test_heartbeat_dot_carries_pi_connection_state(win):
    fc, w = win('B1')
    h = w.status_view.header
    assert h.heartbeat.tone == 'ok' and not h.head_icon.isVisibleTo(w) and h.heartbeat.isVisibleTo(w)
    assert h.heartbeat.toolTip() == 'Kontakt zum Pi – sagt nichts über Weitergabe oder Empfang'
    fc.set_state('B10')
    w.refresh()
    assert h.heartbeat.tone == 'info' and not h.heartbeat.contact
    fc.set_state('blocked')
    w.refresh()
    assert h.heartbeat.tone == 'err'
    fc.set_state('B4a')
    w.refresh()
    assert h.heartbeat.tone == 'warn'
