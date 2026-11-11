"""UX2 Runde UI-2: Moduswahl, Einstellungen, ValidatedField, Einrichtung verlassen, UART direkt (D1–D4),
Session-Erzeugung, Nachbesserungen aus UI-1."""
import os
import re
import time
from dataclasses import replace
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DISPREAD_UI_MOTION', '0')

import pytest
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.fake import FakeController
from dispread_bridge_app.ui.port import MODES, CheckResult
from dispread_bridge_app.ui.widgets import CopyField, ValidatedField
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QLineEdit, QPushButton
from PySide6.QtWidgets import QWidget as QWidget_

UI = Path(__file__).resolve().parents[1] / 'src' / 'dispread_bridge_app' / 'ui'


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    made = []

    def _make(state='B1', dark=False, size=(440, 720), first_run_modes=False, **attrs):
        fc = FakeController(state)
        for k, v in attrs.items():
            setattr(fc, k, v)
        w = MainWindow(fc, dark=dark, first_run_modes=first_run_modes)
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
    """Pool leerlaufen lassen. Nicht ``waitForDone``: das hält die GIL, Python-Aufgaben stünden dann still."""
    QTest.qWait(ms)
    end = time.monotonic() + 8
    while w.pool.activeThreadCount() and time.monotonic() < end:
        QTest.qWait(10)
    QTest.qWait(ms)


def texts_of(widget) -> str:
    return ' | '.join(lab.text() for lab in widget.findChildren(QLabel))


# ---------------------------------------------------------------- ValidatedField
class _Deferred:
    """Ausführer, der Ergebnisse erst auf Zuruf zustellt (Reihenfolge im Test steuerbar)."""

    def __init__(self):
        self.pending = []

    def __call__(self, fn, args, done):
        self.pending.append((fn, args, done))

    def finish(self, i):
        fn, args, done = self.pending[i]
        done(fn(*args), None)


def test_validated_field_drops_stale_results_and_shows_ok_only_after_check(app):
    run = _Deferred()
    edit = QLineEdit()
    f = ValidatedField(edit, lambda v: CheckResult('ok', f'{v} geprüft') if v == 'pi.local' else
                       CheckResult('err', 'Name nicht auflösbar', 'Schreibweise prüfen'), runner=run, debounce_ms=0)
    f.show()
    assert f.state == 'idle' and f.icon.isHidden() and not f.ok
    edit.setText('pi.loca')
    edit.setText('pi.local')
    assert f.state == 'checking' and not f.ok and f.ring.isVisibleTo(f)       # kein ok vor der Prüfung
    run.finish(1)                       # neueste Prüfung zuerst fertig
    assert f.state == 'ok' and f.ok and f.message.text() == 'pi.local geprüft'
    run.finish(0)                       # die ältere, veraltete kommt danach: verworfen
    assert f.state == 'ok' and f.dropped == 1 and f.result.message == 'pi.local geprüft'
    edit.setText('x.invalid')
    assert f.state == 'checking' and not f.ok                                  # Änderung verwirft das alte ok
    run.finish(2)
    assert f.state == 'err' and f.detail.text() == 'Schreibweise prüfen' and not f.detail.isHidden()
    assert 'Name nicht auflösbar' in edit.accessibleDescription() and 'Schreibweise' in edit.accessibleDescription()
    edit.setText('')
    assert f.state == 'idle' and f.message.isHidden()


def test_validated_field_waits_500_ms_after_typing(app):
    run = _Deferred()
    edit = QLineEdit()
    f = ValidatedField(edit, lambda v: CheckResult('ok', 'gut'), runner=run)
    assert f.debounce_ms == 500
    edit.setText('a')
    edit.setText('ab')
    assert f.state == 'pending' and not run.pending
    QTest.qWait(650)
    assert len(run.pending) == 1 and run.pending[0][1] == ('ab',)


def test_validated_field_failed_check_is_error_never_ok(app):
    def boom(v):
        raise OSError('geheim: token=abc')
    f = ValidatedField(QLineEdit(), boom, debounce_ms=0)
    f.editor.setText('x')
    assert f.state == 'err' and f.result.message == texts.CHECK_FAILED and 'token' not in f.message.text()


def test_combo_field_checks_immediately_on_selection(app):
    run = _Deferred()
    cb = QComboBox()
    cb.addItem('Bitte wählen …')
    cb.addItem('COM9 – FTDI', 'COM9')
    f = ValidatedField(cb, lambda p: CheckResult('ok', f'{p} bereit'), runner=run)
    cb.setCurrentIndex(1)
    assert run.pending and run.pending[0][1] == ('COM9',) and f.state == 'checking'


# ---------------------------------------------------------------- Moduswahl
def test_modes_window_three_cards_active_badge_and_arrow_keys(win):
    fc, w = win('B10')
    w.status_view.header.mode_button.click()
    settle(w)
    mw = w.tool_windows['modes']
    assert mw.isVisible() and tuple(mw.cards) == MODES
    net = mw.cards['network']
    assert net.findChild(QLabel, 'badge_active') is not None and net.radio.isChecked()
    assert all(c.findChild(QLabel, 'badge_active') is None for k, c in mw.cards.items() if k != 'network')
    assert not mw.switch_button.isEnabled()                       # aktiver Weg: nichts zu wechseln
    assert '460800 Baud' in texts_of(mw.cards['uart_bridge'])     # Rate aus dem Kontext, nicht fest im Text
    net.radio.setFocus(Qt.FocusReason.TabFocusReason)
    QTest.keyClick(net.radio, Qt.Key.Key_Up)
    assert mw.selected == 'uart_bridge' and mw.cards['uart_bridge'].property('selected') is True
    assert mw.switch_button.isEnabled() and mw.switch_button.property('accent') is True
    assert not mw.hint.isHidden()                                 # nicht eingerichtet: Wechsel startet Einrichtung
    mw.switch_button.click()
    settle(w)
    assert ('select_mode', 'uart_bridge') in fc.calls and not mw.isVisible()


def test_modes_window_locked_during_transmission(win):
    fc, w = win('B1')                                             # Worker aktiv
    w.do_action('open_modes')
    settle(w)
    mw = w.tool_windows['modes']
    assert mw.findChild(QWidget_, 'modes_locked') is not None
    for k in ('uart_direct', 'uart_bridge'):
        assert not mw.cards[k].radio.isEnabled() and mw.cards[k].reason_label.text() == 'Erst Übertragung beenden'
    assert not mw.switch_button.isEnabled()
    w._select_mode('uart_direct')                                 # trotzdem versucht: Controller lehnt ab
    settle(w)
    assert mw.isVisible() and mw.error == 'mode_locked'
    assert texts.ERROR_TEXT['mode_locked'][0] in texts_of(mw)


def test_modes_open_by_themselves_once_on_first_start(win):
    fc, w = win('first_run', first_run_modes=True)
    settle(w)
    mw = w.tool_windows.get('modes')
    assert mw is not None and mw.isVisible() and mw.selected is None
    mw.close()
    w.refresh()
    settle(w)
    assert not mw.isVisible()                                     # einmal pro Start
    _, w2 = win('first_run')                                      # Testschalter aus: nicht von selbst
    assert 'modes' not in w2.tool_windows
    _, w3 = win('B10', first_run_modes=True)                      # Weg gewählt: nicht von selbst
    assert 'modes' not in w3.tool_windows


def test_not_set_up_bar_starts_setup_by_choosing_a_way(win):
    fc, w = win('Bnone')
    bar = w.status_view.infobar
    assert bar.bar is not None and bar.bar.title == texts.NOT_SET_UP_TITLE
    assert bar.action_ids == ('start_setup',)
    bar.buttons[0].click()
    settle(w)
    assert w.tool_windows['modes'].isVisible()


# ---------------------------------------------------------------- Einstellungen
def test_settings_free_edits_with_checked_takeover(win):
    fc, w = win('B10')
    w.status_view.settings_button.click()
    settle(w)
    sw = w.tool_windows['settings']
    assert sw.isVisible() and not sw.locked
    for title in ('Weg', 'Pi', 'Ports', 'GSVmulti-Session', 'Protokolle', 'Über'):
        assert title in texts_of(sw)
    edit = sw.findChild(QLineEdit, 'settings_endpoint_edit')
    take = sw.findChild(QPushButton, 'settings_endpoint_apply')
    assert edit is not None and not take.isEnabled()
    edit.setText('gibtsnicht.example')
    QTest.qWait(600)
    settle(w)
    assert sw.fields['endpoint'].state == 'err' and not take.isEnabled()
    edit.setText('pi.local')
    QTest.qWait(600)
    settle(w)
    assert sw.fields['endpoint'].ok and take.isEnabled()
    take.click()
    settle(w)
    assert ('select_endpoint', 'pi.local', True) in fc.calls
    assert sw._saved_until.get('endpoint', 0) > time.monotonic() - 1        # „Gespeichert“ bestätigt


def test_settings_port_pair_applies_only_after_accepted_check(win):
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    g = sw.findChild(QComboBox, 'settings_gsv_port')
    assert g is not None and g.currentData() == 'COM5'
    g.setCurrentIndex(g.findData('COM4'))                         # gleich wie Brückenseite: keine Prüfung
    settle(w)
    assert not any(c[0] == 'set_port_pair' for c in fc.calls)
    sw = w.tool_windows['settings']
    g = sw.findChild(QComboBox, 'settings_gsv_port')
    g.setCurrentIndex(g.findData('COM1'))                         # vorhanden, kein com0com-Paar: warn, übernommen
    settle(w)
    assert ('check_port_pair', 'COM4', 'COM1') in fc.calls and ('set_port_pair', 'COM4', 'COM1') in fc.calls
    assert texts.SETTINGS_PORTS_NOTE in texts_of(w.tool_windows['settings'])


def test_settings_locked_while_transmitting_but_values_copyable(win):
    fc, w = win('B1')
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    assert sw.locked and sw.findChild(QLineEdit, 'settings_endpoint_edit') is None
    assert sw.findChild(QComboBox, 'settings_gsv_port') is None
    assert texts.SETTINGS_LOCKED in texts_of(sw)
    names = {f.name_label.text(): f for f in sw.findChildren(CopyField)}
    for n in ('Pi-ID', 'Endpunkt', 'TLS-Fingerabdruck (SHA-256)', 'Brückenseite', 'GSVmulti-Seite'):
        assert n in names and not names[n].copy_button.isHidden(), n
    for name in ('settings_modes', 'settings_change_setup'):
        b = sw.findChild(QPushButton, name)
        assert not b.isEnabled() and b.toolTip() == texts.REASON_TRANSMISSION_FIRST


def test_settings_change_setup_reruns_setup(win):
    fc, w = win('B10')
    w.do_action('open_settings')
    settle(w)
    w.tool_windows['settings'].findChild(QPushButton, 'settings_change_setup').click()
    settle(w)
    assert ('setup_step', 'change_setup') in fc.calls


def test_settings_session_export_result_not_green_and_hints(win, tmp_path):
    fc, w = win('B10')
    w.pick_session = lambda name: str(tmp_path / name)
    w.do_action('open_settings')
    settle(w)
    sw = w.tool_windows['settings']
    assert texts.SINGLE_CHANNEL_WARNING in texts_of(sw)         # Einkanal-Vorlage auf Brückenweg
    sw.findChild(QPushButton, 'settings_make_session').click()
    settle(w)
    call = [c for c in fc.calls if c[0] == 'export_session_file'][0]
    assert call[1] == tmp_path / 'GSVmulti_Pruefstand3HalleA_COM5.ucf'           # Standardname GSVmulti_<Pi>_<COMx>
    assert call[2] == 'COM5'
    sw = w.tool_windows['settings']
    shown = texts_of(sw)
    assert texts.SESSION_DONE in shown and texts.SESSION_NOT_ACCEPTED in shown
    assert texts.autoscale_hint('COM5') in shown and 'Kanal 5_1' in shown
    assert sw.findChild(QWidget_, 'record_hidden') is None                    # Normalfall: kein Pflichthinweis
    assert any(f.value == str(call[1]) for f in sw.findChildren(CopyField))
    assert not w.status_view.busy_bar.busy


def test_settings_record_hidden_required_is_warn_with_operator_check(win, tmp_path):
    fc, w = win('B10', record_hidden=True)
    w.pick_session = lambda name: str(tmp_path / name)
    w.do_action('open_settings')
    settle(w)
    w.do_action('make_session')
    settle(w)
    sw = w.tool_windows['settings']
    box = sw.findChild(QWidget_, 'record_hidden')
    assert box is not None and box.property('kind') == 'warn'                  # Achtung, nie grün
    assert texts.RECORD_HIDDEN in texts_of(box)
    cb = box.findChild(QCheckBox, 'record_hidden_ok')
    cb.setChecked(True)
    assert w.record_hidden_confirmed                                           # Bedienerangabe, kein Beleg


def test_session_export_failure_names_problem_and_next_action(win, tmp_path):
    fc, w = win('B10')

    def fail(dest, port=None):
        from dispread_bridge_app.app_controller import AppError
        raise AppError('session_write_failed')
    fc.export_session_file = fail
    w.pick_session = lambda name: str(tmp_path / name)
    w.do_action('open_settings')
    settle(w)
    w.do_action('make_session')
    settle(w)
    assert w.session_state.state == 'failed'
    assert texts.ERROR_TEXT['session_write_failed'][1] in texts_of(w.tool_windows['settings'])


def test_single_channel_warning_only_on_bridge_ways_with_one_channel():
    c = FakeController('B1').context()
    assert texts.single_channel_warning(c) == texts.SINGLE_CHANNEL_WARNING
    assert texts.single_channel_warning(replace(c, session_channels=None)) == ''
    assert texts.single_channel_warning(replace(c, session_channels=4)) == ''
    assert texts.single_channel_warning(replace(c, route_mode='uart_direct')) == ''
    assert texts.gsv_channel('COM8') == '8_1' and texts.gsv_channel(None) is None


def test_gsv_tile_detail_carries_single_channel_warning(win):
    fc, w = win('B1')
    w.status_view.chips[5].click()
    settle(w)
    assert texts.SINGLE_CHANNEL_WARNING in texts_of(w.tool_windows['chip'])


# ---------------------------------------------------------------- Einrichtung
def test_leave_setup_button_only_when_leavable(win):
    fc, w = win('E2b')
    b = w.setup_view.leave_button
    assert b.isVisibleTo(w) and b.toolTip() == texts.LEAVE_SETUP == b.accessibleName()
    b.click()
    settle(w)
    assert ('leave_setup',) in fc.calls and w.stack.currentWidget() is w.status_view
    _, w2 = win('E1')
    assert not w2.setup_view.leave_button.isVisibleTo(w2)


def test_setup_fields_check_endpoint_and_pairing_code(win):
    fc, w = win('E3')
    sv = w.setup_view
    sv.endpoint_edit.setText('pi.local')
    QTest.qWait(600)
    settle(w)
    assert sv.fields['endpoint'].ok and ('check_endpoint', 'pi.local') in fc.calls
    fc2, w2 = win('E2b')
    sv2 = w2.setup_view
    sv2.code_edit.setText('123')
    settle(w2)
    assert sv2.fields['pairing_code'].state == 'err'
    assert all('123' not in repr(c) for c in fc2.calls)                       # Code nie aufgezeichnet


def test_rescan_is_icon_button_with_ring_while_searching(win):
    fc, w = win('E3')
    sv = w.setup_view
    b = sv.buttons['rescan']
    assert b.icon_name == 'arrow_sync' and b.toolTip() == texts.RESCAN_TIP
    sv.set_searching(True)
    assert b.isHidden() and sv._search_buttons[0][1].isVisibleTo(w)
    sv.set_searching(False)
    b.click()
    settle(w)
    assert ('rescan',) in fc.calls and not sv.searching and not sv.buttons['rescan'].isHidden()


def test_saved_note_after_step_taken_over(win):
    fc, w = win('E2b')
    sv = w.setup_view
    n = sv.saved_note.shown_count
    fc.set_state('E2ok')
    w.refresh()
    assert sv.saved_note.shown_count == n + 1 and sv.saved_note.isVisibleTo(w)
    fc.set_state('E3')
    w.refresh()
    assert sv.saved_note.shown_count == n + 2


def test_direct_d1_requires_real_adapter_check(win):
    fc, w = win('D1')
    sv = w.setup_view
    assert sv.step_header.steps == texts.STEPS_DIRECT and len(sv.step_header.steps) == 4
    assert not sv.next_button.isEnabled() and sv.next_reason.text()
    fc2, w2 = win('D1sel')
    sv2 = w2.setup_view
    settle(w2)
    assert ('check_adapter', 'COM9') in fc2.calls and sv2.fields['adapter'].ok
    assert sv2.next_button.isEnabled()


def test_direct_d2_wiring_uses_gsvmulti_baud_not_bridge_uart(win):
    fc, w = win('D2')
    shown = texts_of(w.setup_view)
    assert '115200 Baud, 8N1' in shown and '460800' not in shown
    _, w2 = win('D2missing')
    assert 'fehlt' in texts_of(w2.setup_view)


def test_direct_d3_session_for_adapter_port_then_next(win, tmp_path):
    fc, w = win('D3')
    sv = w.setup_view
    assert not sv.next_button.isEnabled()
    w.pick_session = lambda name: str(tmp_path / name)
    sv.buttons['make_session'].click()
    settle(w)
    assert ('export_session_file', tmp_path / 'GSVmulti_Pi_COM9.ucf', 'COM9') in fc.calls
    assert sv.next_button.isEnabled() and texts.SESSION_DONE in texts_of(sv)
    assert texts.SINGLE_CHANNEL_WARNING not in texts_of(sv)                  # UART direkt: kein Brückenweg


def test_direct_d3_record_hidden_gates_next_until_confirmed(win, tmp_path):
    fc, w = win('D3', record_hidden=True)
    sv = w.setup_view
    w.pick_session = lambda name: str(tmp_path / name)
    sv.buttons['make_session'].click()
    settle(w)
    assert 'record_hidden_ok' in sv.checks and not sv.next_button.isEnabled()
    assert sv.next_reason.text() == texts.RECORD_HIDDEN_GATE
    sv.checks['record_hidden_ok'].setChecked(True)
    assert sv.next_button.isEnabled()


def test_bridge_session_step_has_real_button(win, tmp_path):
    fc, w = win('E4session')
    sv = w.setup_view
    b = sv.buttons['make_session']
    assert b.text() == texts.SESSION_MAKE and b.isEnabled()
    w.pick_session = lambda name: str(tmp_path / name)
    b.click()
    settle(w)
    assert ('export_session_file', tmp_path / 'GSVmulti_Pruefstand2_COM5.ucf', 'COM5') in fc.calls
    assert texts.SESSION_DONE in texts_of(sv) and texts.SINGLE_CHANNEL_WARNING in texts_of(sv)


def test_new_error_codes_name_problem_and_next_action():
    for code in ('mode_locked', 'adapter_required', 'session_required', 'session_port_invalid',
                 'session_write_failed', 'setup_changed'):
        title, text = texts.explain_code(code)
        assert title != 'Unbekannt' and text, code


def test_no_fixed_baud_rates_in_ui_texts():
    for f in ('texts.py', 'setup_view.py', 'settings_window.py', 'mode_window.py', 'tool_windows.py', 'window.py'):
        src = (UI / f).read_text('utf-8')
        assert not re.search(r'\b(115200|460800)\b', src), f


# ---------------------------------------------------------------- Nachbesserungen UI-1
def test_tiles_put_icon_and_name_on_one_line_at_440(win):
    _, w = win('B1')
    assert all(c._inline for c in w.status_view.chips)


def test_backoff_shows_ring_without_error_icon_in_headline(win):
    _, w = win('B3')
    h = w.status_view.header
    assert h.ring.isVisibleTo(w) and not h.head_icon.isVisibleTo(w)
    assert h.ring.toolTip() == texts.HEARTBEAT_RETRY


def test_export_done_moves_accent_to_close(win, tmp_path):
    fc, w = win('B1')
    w.do_action('export_diagnostics')
    settle(w)
    ex = w.tool_windows['export']
    assert ex.save_button.property('accent') is True and ex.close_button.isHidden()
    w.pick_save = lambda: str(tmp_path / 'p.zip')
    ex.save_button.click()
    settle(w)
    assert ex.close_button.isVisibleTo(ex) and ex.close_button.property('accent') is True
    assert ex.save_button.property('accent') is False and ex.save_button.text() == texts.EXPORT_SAVE_AGAIN
    ex.close_button.click()
    assert not ex.isVisible()



# ---- UART direkt: Betriebsansicht ohne Brückenaussagen
def _direct(present=True):
    from dispread_bridge_app.ui.fake import STATES
    r, w, c = STATES['Bdirect']
    return r, w, replace(c, adapter_present=present)


def test_direct_headline_and_tone():
    for present, text, tone in ((True, 'UART direkt – Adapter COM9 steckt', 'ok'),
                                (False, 'UART direkt – Adapter COM9 fehlt', 'warn'),
                                (None, 'UART direkt – Adapterzustand unbekannt', 'info')):
        r, w, c = _direct(present)
        h = texts.headline(r, w, c)
        assert (h.text, h.tone) == (text, tone)
        assert 'verbunden' not in h.text.lower() and 'Pi' not in h.text.split()


def test_direct_infobar_never_offers_connect():
    r, w, c = _direct(True)
    bar = texts.action_bar(r, w, c, configured=False)
    assert bar.kind == 'info' and 'liest COM9 direkt' in bar.title and 'zeigt nur GSVmulti' in bar.text
    assert not bar.buttons
    bar = texts.action_bar(*_direct(False), configured=False)
    assert bar.kind == 'warn' and bar.title == 'Adapter COM9 fehlt – einstecken'
    assert all('connect' not in a for a in bar.action_ids)


def test_direct_chips_and_dut_line():
    r, w, c = _direct(True)
    ch = {x.key: x for x in texts.chips(r, w, c)}
    assert ch['uart'].word == 'Adapter steckt' and ch['uart'].tone == 'ok' and ch['uart'].sub == 'COM9'
    for k in ('pi', 'output', 'forward'):
        assert (ch[k].word, ch[k].tone, ch[k].sub) == ('nicht benutzt', 'unused', 'UART direkt')
    assert ch['gsv'].sub == 'Empfang nicht nachgewiesen'
    assert all(x.tone != 'ok' for x in ch.values() if x.key not in ('components', 'uart'))   # USB-Präsenz ist belegt
    assert texts.chips(*_direct(False))[1].word == 'Adapter fehlt'
    assert texts.dut_line(c) == (texts.DIRECT_DUT_LINE, 'info')


def test_direct_view_hides_pi_switch(app):
    from dispread_bridge_app.ui.fake import STATES
    r, w, c = STATES['Bdirect']
    win = MainWindow(FakeController('Bdirect'))
    win.show()
    app.processEvents()
    assert not win.findChild(QWidget_, 'switch') or not win.findChild(QWidget_, 'switch').isVisible()


# ---------------------------------------------------------------- Korrekturrunde A (Windows-Prüfung)
def test_paired_window_switch_locked_during_transmission(win):
    fc, w = win('B1')                                  # Lauf aktiv: Wechsel gesperrt
    ctx = fc.context()
    fc.set(context=replace(ctx, paired=(('Prüfstand 2', ctx.pi_id, 'jetzt'), ('Halle A', 'pi-d21a77e6', 'gestern'))))
    w._show_switch()
    settle(w)
    pw = w.tool_windows['paired']
    assert pw.windowTitle() == f'{texts.PAIRED_TITLE} – {texts.APP_TITLE}'
    b = [x for x in pw.findChildren(QPushButton) if x.text() == texts.SWITCH_PI]
    assert len(b) == 1 and not b[0].isEnabled() and b[0].toolTip() == texts.REASON_TRANSMISSION_FIRST
    fc.set_state('B10')
    fc.set(context=replace(fc.context(), paired=(('A', fc.context().pi_id, 'jetzt'), ('B', 'pi-x', 'gestern'))))
    w.refresh()
    settle(w)
    b = [x for x in pw.findChildren(QPushButton) if x.text() == texts.SWITCH_PI]
    assert len(b) == 1 and b[0].isEnabled()


def test_direct_uart_adapter_present_is_ok_everywhere(win):
    fc, w = win('Bdirect')
    chip = next(c for c in w.status_view.chips if c.view.key == 'uart')
    assert chip.view.word == 'Adapter steckt' and chip.view.tone == 'ok'
    assert texts.headline(fc.snapshot(), fc.worker_status(), fc.context()).tone == 'ok'
    _, w2 = win('D2')
    assert 'steckt' in texts_of(w2.setup_view)
    fc3, w3 = win('usb_missing')
    fc3.set_state('Bdirect')
    fc3.set(context=replace(fc3.context(), adapter_present=False))
    w3.refresh()
    chip = next(c for c in w3.status_view.chips if c.view.key == 'uart')
    assert chip.view.tone == 'warn'


def test_main_actions_gated_while_problem_open(win):
    # E3: Adressprüfung err -> „Verbinden“ gesperrt, mit sichtbarem Grund
    fc, w = win('E3')
    sv = w.setup_view
    sv.endpoint_edit.setText('gibtsnicht.example')
    QTest.qWait(600)
    settle(w)
    assert sv.fields['endpoint'].state == 'err'
    assert not sv.next_button.isEnabled() and sv.next_reason.isVisibleTo(w) and sv.next_reason.text()
    sv.endpoint_edit.setText('pi.local')
    QTest.qWait(600)
    settle(w)
    assert sv.fields['endpoint'].ok and sv.next_button.isEnabled()
    # E3uart ohne Adapter gesperrt, mit Adapter frei
    fc2, w2 = win('E3uart')                            # Demo-Zustand: kein Adapter in der Liste
    assert not w2.setup_view.next_button.isEnabled() and w2.setup_view.next_reason.text() == texts.GATE_NO_ADAPTER
    st = fc2.context().setup
    data = dict(st.data, adapter_items=(('COM9 – FTDI USB Serial', '', True),), adapter_port='COM9')
    fc2.set(context=replace(fc2.context(), setup=replace(st, data=data)))
    w2.refresh()
    settle(w2)
    assert w2.setup_view.fields['adapter'].ok and w2.setup_view.next_button.isEnabled()
    # D2 mit fehlendem Adapter: „Weiter“ gesperrt
    _, w3 = win('D2missing')
    assert not w3.setup_view.next_button.isEnabled() and w3.setup_view.next_reason.text() == texts.GATE_ADAPTER_MISSING
    _, w4 = win('D2')
    assert w4.setup_view.next_button.isEnabled()
    # E2b: leerer oder falscher Code sperrt „Weiter“ und „Code übernehmen“
    _, w5 = win('E2b')
    sv5 = w5.setup_view
    assert not sv5.next_button.isEnabled() and not sv5.buttons['pair'].isEnabled()
    sv5.checks['fp_ok'].setChecked(True)
    sv5.code_edit.setText('123')
    settle(w5)
    assert sv5.fields['pairing_code'].state == 'err'
    assert not sv5.next_button.isEnabled() and not sv5.buttons['pair'].isEnabled()


def test_setup_footer_is_single_row_with_power_icon(win):
    from PySide6.QtWidgets import QFrame
    for width in (380, 440):
        for state in ('E2b', 'E5busy', 'E3'):
            _, w = win(state, size=(width, 560))
            sv = w.setup_view
            ys = {b.mapTo(sv, b.rect().center()).y() for b in (sv.export_button, sv.back_button, sv.next_button,
                                                                   sv.exit_button) if b.isVisibleTo(sv)}
            assert max(ys) - min(ys) <= 4, (state, width, ys)
            assert sv.exit_button.toolTip() == texts.EXIT_TIP == sv.exit_button.accessibleName()
            assert sv.exit_button.geometry().right() <= sv.width()
            assert isinstance(sv.exit_button.parentWidget(), QFrame)


def test_pi_id_is_mono_in_pairing_card(win):
    _, w = win('E2b')
    pid = w.setup_view.findChildren(QLabel)
    lab = next(x for x in pid if x.text() == w.controller.context().pi_id)
    assert lab.property('mono') is True


def test_german_single_quotes_are_balanced():
    ui = Path(__file__).resolve().parents[1] / 'src' / 'dispread_bridge_app' / 'ui'
    for f in ui.glob('*.py'):
        src = f.read_text('utf-8')
        assert src.count('‚') == src.count('‘'), f.name
        for bad in ('’', '‛', "‚’"):
            assert bad not in src, (f.name, repr(bad))
    assert '‚Autoscale Y‘' in texts.AUTOSCALE_HINT


def test_header_shows_only_status_icon_when_warn_and_pulses_it(win):
    fc, w = win('B1tr')
    h = w.status_view.header
    assert h.head_icon.isVisibleTo(w) and not h.pulse_slot.isVisibleTo(w)
    n = h.icon_pulses
    fc.tick()
    w.refresh()
    assert h.icon_pulses == n + 1
    fc.set_state('B1')
    w.refresh()
    assert not h.head_icon.isVisibleTo(w) and h.pulse_slot.isVisibleTo(w)


def test_empty_journal_has_card_frame(win):
    _, w = win('Bdirect')
    sv = w.status_view
    assert sv.model.rowCount() == 0
    assert sv.empty_frame.isVisibleTo(w) and sv.empty_frame.property('card') is True
    assert sv.empty_frame.minimumHeight() >= 150


def test_journal_keeps_min_height_at_380x560(win):
    _, w = win('B1', size=(380, 560))
    sv = w.status_view
    settle(w)
    assert sv.journal.height() >= 150


def test_session_file_name_is_ascii():
    from types import SimpleNamespace

    from dispread_bridge_app.ui.settings_window import ascii_name_part, session_default_name
    ctx = SimpleNamespace(pi_name='Prüfstand 2')
    assert session_default_name(ctx, 'COM5') == 'GSVmulti_Pruefstand2_COM5.ucf'
    assert ascii_name_part('Straße äöü ÄÖÜ -_ .:*') == 'Strasseaeoeue AeOeUe'.replace(' ', '') + '-_'
    assert session_default_name(SimpleNamespace(pi_name='Halle Ä/3 – neu'), 'COM10').isascii()
    assert session_default_name(SimpleNamespace(pi_name=None), 'COM3') == 'GSVmulti_Pi_COM3.ucf'


def test_head_has_no_gap_and_no_scrollbar_at_440x720(win):
    from dispread_bridge_app.ui.status_view import StatusView
    for state in ('B1', 'B1tr', 'B3'):
        _fc, w = win(state)
        sv = w.findChild(StatusView)
        assert not sv.scroll.verticalScrollBar().isVisible(), state
        body = sv.body_widget
        head = sv.header
        dut_bottom = head.mapTo(body, head.dut.geometry().bottomLeft()).y()
        assert sv.infobar.y() - dut_bottom <= 16 or not sv.infobar.isVisible(), state
        assert head.height() <= head.layout().totalHeightForWidth(head.width()) + 1, state
