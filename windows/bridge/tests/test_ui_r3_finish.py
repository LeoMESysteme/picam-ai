"""Gestaltungsrunde 3, Abschluss: offene Oberflächenpunkte aus dem Smoketest 13.11. (TODO.md).

Schritt 5 neutral, Strecke als Bild, Ordner der Session, Kachel-Zweitzeilen, Journal mit Abbruch/Stopp,
Session passt nicht zum Lauf, ruhiger Puls, Taktzähler/Format, UART direkt ohne Portpaar, Erneut prüfen,
Kopplung je Weg, Testsession merken, Portpaar-Prüfung unabhängig von der Reihenfolge.
"""
import os
import time
from dataclasses import replace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DISPREAD_UI_MOTION', '0')
os.environ.setdefault('DISPREAD_UI_FIRST_RUN_MODES', '0')

import pytest
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.fake import STATES, FakeController
from dispread_bridge_app.ui.port import CheckResult, UiContext
from dispread_bridge_app.ui.window import MainWindow
from dispread_bridge_app.worker import WorkerStatus
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit

from dispread.bridge.types import BridgeEvent


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    made = []

    def _make(state='B1', size=(440, 720)):
        fc = FakeController(state)
        w = MainWindow(fc, dark=False, first_run_modes=False)
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


def spec_of(state):
    return texts.setup_spec(STATES[state][2])


# ---------------------------------------------------------------- Schritt 5
def test_step5_success_is_neutral_and_names_port_and_count():
    spec = spec_of('E5done')
    info = [b for b in spec['blocks'] if b[0] == 'info'][0]
    assert info[1] == 'info'                                       # neutral, nicht warn
    assert info[2] == '600 von 600 Werten an COM5 übergeben'
    assert 'prüft die Brücke nicht' in info[3]                     # ehrlich: kein Empfangsnachweis


def test_step5_short_keeps_integration_wording_and_actions():
    spec = spec_of('E5short')
    info = spec['blocks'][0]
    assert info[1] == 'err' and info[2] == 'Unvollständig: 588 von 600, 12 fehlen'
    assert [b[1] for b in info[4]] == ['export_diagnostics']
    assert any(b[0] == 'button' and b[2] == 'start_demo_check' for b in spec['blocks'])


# ---------------------------------------------------------------- Kacheln
def test_tile_second_lines_have_at_most_three_words():
    for key in ('B1', 'B1tr', 'B1tick', 'B1mismatch', 'B2', 'B3', 'B4a', 'B5', 'Bdirect', 'blocked'):
        r, w, c = STATES[key]
        for chip in texts.chips(r, w, c):
            assert len(chip.sub.split()) <= 3, (key, chip.key, chip.sub)


def test_uart_direct_components_name_only_the_adapter():
    r, w, c = STATES['Bdirect']
    r = replace(r, components='manual_pair')
    c = replace(c, bridge_port='COM7', gsv_port='COM9')
    comp = texts.chips(r, w, c)[0]
    flat = repr(comp)
    assert 'COM7' not in flat and '↔' not in flat
    assert ('USB-Adapter', 'COM9') in comp.details


def test_tick_counter_and_format_in_tiles():
    r, w, c = STATES['B1tick']
    chips = {v.key: v for v in texts.chips(r, w, c)}
    assert chips['forward'].sub == '1342 Takte'
    assert ('Takte an COM', '1342') in chips['forward'].details and ('davon ungültig', '17') in chips['forward'].details
    assert ('Format der Session', 'Vierkanal') in chips['gsv'].details
    assert ('Format des Laufs', 'Vierkanal') in chips['gsv'].details
    disturbed = replace(w, tick_disturbed=True)
    assert {v.key: v for v in texts.chips(r, disturbed, c)}['forward'].word == 'Takt gestört'


def test_ticks_never_hide_a_demo_or_a_failure():
    r, w, c = STATES['B5']
    w = WorkerStatus('running', True, True, None, ticks_written=10)
    assert {v.key: v for v in texts.chips(r, w, c)}['forward'].sub == 'Demo-Werte'


# ---------------------------------------------------------------- Session passt nicht
def test_session_format_mismatch_warns_and_offers_remake_in_run_format():
    r, w, c = STATES['B1mismatch']
    gsv = texts.chips(r, w, c)[5]
    assert (gsv.word, gsv.tone) == ('Session passt nicht', 'warn') and gsv.warn
    bar = texts.action_bar(r, w, c)
    assert bar.kind == 'warn' and bar.buttons[0][1] == 'make_session:4ch'
    assert len(bar.text) <= 70


@pytest.mark.parametrize('run, sess', [(None, '1ch'), ('4ch', None), ('4ch', '4ch')])
def test_no_mismatch_claim_without_both_formats_known(run, sess):
    r, w, c = STATES['B1tr']
    c = replace(c, run_format=run, session_format=sess)
    assert texts.session_mismatch(c) == ''
    assert texts.chips(r, w, c)[5].word != 'Session passt nicht'


def test_remake_session_passes_the_run_format(win, tmp_path):
    fc, w = win('B1mismatch')
    w.pick_session = lambda name: str(tmp_path / name)
    calls = []
    fc.export_session_file = lambda dest, port=None, fmt=None: calls.append((port, fmt)) or None
    w.do_action('make_session:4ch')
    settle(w)
    assert calls == [('COM5', '4ch')]


# ---------------------------------------------------------------- Strecke, Session-Ordner
def test_bridge_route_shows_both_ports_as_value_fields(win):
    fc, w = win('B1')
    route = w.status_view.bridge_route
    assert route.isVisibleTo(w) and not w.status_view.route.isVisibleTo(w)
    assert [f.value for f in route.fields] == ['COM4', 'COM5']
    fc2, w2 = win('Bdirect')
    assert not w2.status_view.bridge_route.isVisibleTo(w2) and w2.status_view.route.isVisibleTo(w2)


def test_session_panel_shows_folder_and_labelled_open_folder(win, tmp_path):
    fc, w = win('E4session')
    w.pick_session = lambda name: str(tmp_path / name)
    w.do_action('make_session')
    settle(w, 100)
    sv = w.setup_view
    ob = sv.buttons['open_session_folder']
    assert ob.text() == texts.OPEN_FOLDER
    values = [lab.text().replace('\u200b', '') for lab in sv.content.findChildren(QLabel)]
    assert str(tmp_path) in values and 'GSVmulti_Pruefstand2_COM5.ucf' in ' '.join(values)
    opened = []
    w.open_folder = opened.append
    ob.click()
    assert opened == [str(tmp_path)]


def test_record_hidden_is_required_after_restart_for_a_four_channel_session(win):
    fc, w = win('E4locked_run')
    c = fc.context()
    fc.set(context=replace(c, session_format='4ch', setup=replace(c.setup, data=dict(
        c.setup.data, session_path='C:\\Users\\Labor\\GSVmulti_Pi_COM5.ucf'))))
    w.refresh()
    settle(w)
    assert 'record_hidden_ok' in w.setup_view.checks          # Pflicht auch ohne Export dieser Laufzeit


# ---------------------------------------------------------------- Journal
def test_journal_names_interruption_tick_gap_and_output_changes():
    rec = texts.event_entry(BridgeEvent('recovering', 'connection_unavailable', None, None, {}))
    assert rec.title == 'Verbindung unterbrochen' and rec.fault
    gap = texts.event_entry(BridgeEvent('tick_disturbed', 'tick_gap_unfilled', None, None, {}))
    assert gap.title == 'Takt gestört' and gap.tone == 'err'
    out = texts.event_entry(BridgeEvent('connection', 'peer_output_changed', '7', None, dict(output='ended')))
    assert out.title == 'Lauf auf dem Pi beendet' and out.sub == 'Lauf 7'
    stop = texts.event_entry(BridgeEvent('stopped', 'stopped', None, None, {}))
    assert stop.title == 'Übertragung gestoppt'
    uart = texts.event_entry(BridgeEvent('connection', 'uart_frame_invalid', None, None, {}))
    assert uart.title == 'UART-Nachricht gestört' and 'Kabel' in uart.sub


def _controller(tmp_path):
    from test_app_controller import make
    return make(tmp_path, demo_count=600, demo_rate_hz=10)


def test_controller_journals_demo_end_and_interruption(tmp_path):
    c = _controller(tmp_path)
    with c._lock:
        c._demo_started, c._written, c._demo_ended, c._demo_noted = True, 588, False, False
    c._emit(BridgeEvent('exchange', 'ended', None, None, dict(outcome='ended')))
    top = c.context().journal[0]
    assert top.title == 'Empfangstest beendet: 588 von 600 übergeben' and top.sub == '12 fehlen' and top.fault
    c2 = _controller(tmp_path / 'b')
    with c2._lock:
        c2._demo_started, c2._written, c2._demo_ended, c2._demo_noted = True, 123, False, False
    c2._emit(BridgeEvent('connection', 'uart_frame_invalid', None, None, {}))
    titles = [e.title for e in c2.context().journal[:2]]
    assert titles == ['Empfangstest unterbrochen: 123 von 600 übergeben', 'UART-Nachricht gestört']
    c2._emit(BridgeEvent('stopped', 'stopped', None, None, {}))
    assert sum(e.title.startswith('Empfangstest unterbrochen') for e in c2.context().journal) == 1   # einmal je Test


def test_complete_demo_end_is_neutral(tmp_path):
    c = _controller(tmp_path)
    with c._lock:
        c._demo_started, c._written, c._demo_ended, c._demo_noted = True, 600, False, False
    c._emit(BridgeEvent('exchange', 'ended', None, None, dict(outcome='ended')))
    top = c.context().journal[0]
    assert top.title == 'Empfangstest beendet: 600 von 600 übergeben' and top.tone == 'info' and not top.fault


# ---------------------------------------------------------------- Puls
def test_heartbeat_pulse_is_slow_and_not_restarted(app, monkeypatch):
    from dispread_bridge_app.ui import theme
    from dispread_bridge_app.ui.widgets import HeartbeatDot
    from PySide6.QtCore import QAbstractAnimation
    monkeypatch.setattr(theme, 'motion_enabled', lambda: True)
    h = HeartbeatDot(20)
    h.show()
    assert h.PULSE_MS >= 800 and h.MIN_GAP_S >= 1.5
    h.set_contact(True, 1)
    h.set_contact(True, 2)
    assert h._anim.state() == QAbstractAnimation.State.Running
    started = h._last_pulse
    for seq in range(3, 13):                        # 10 Hz Austausch: kein Neustart, kein Flackern
        h.set_contact(True, seq)
    assert h._last_pulse == started and h.pulses == 11
    h.hide()


# ---------------------------------------------------------------- Prüfen, Kopplung, Haken
def test_recheck_button_appears_after_error_and_reruns_the_check(app):
    from dispread_bridge_app.ui.widgets import ValidatedField
    calls = []

    def check(v):
        calls.append(v)
        return CheckResult('err', 'Adapter fehlt', 'Einstecken')
    e = QLineEdit()
    f = ValidatedField(e, check, debounce_ms=0, name='field_adapter')
    f.show()
    e.setText('COM6')
    assert f.state == 'err' and f.recheck_button.isVisibleTo(f) and calls == ['COM6']
    f.recheck_button.click()
    assert calls == ['COM6', 'COM6']                 # ohne Umweg über einen anderen Port
    f.check = lambda v: CheckResult('ok', 'Adapter bereit')
    f.recheck_button.click()
    assert f.state == 'ok' and not f.recheck_button.isVisibleTo(f)


def test_pairing_is_shown_per_route():
    r, w, c = STATES['B1tr']
    pi = texts.chips(r, w, c)[2]
    assert ('Kopplung Netzwerk', 'gekoppelt') in pi.details and ('Kopplung UART', 'nicht gekoppelt') in pi.details
    spec = spec_of('E2b_route')
    assert spec['blocks'][0][1] == 'Kopplung je Weg'
    assert spec_of('E2b')['blocks'][0][1] != 'Kopplung je Weg'          # unbekannt bzw. gleich: keine Zeile


def test_unknown_pairing_is_not_claimed():
    assert texts.pairing_rows(UiContext()) == ()


def test_separate_test_session_check_is_remembered(win):
    fc, w = win('E5')
    sv = w.setup_view
    sv.checks['test_session_ok'].setChecked(True)
    w.do_action('back')
    settle(w)
    w.do_action('next')
    settle(w)
    assert sv.variant[0] == 'E5' and sv.checks['test_session_ok'].isChecked()
    assert sv.buttons['start_demo_check'].isEnabled()


def test_port_pair_check_is_the_same_in_both_orders():
    from dispread_bridge_app.input_checks import InputChecks

    class Port:
        def __init__(self, port):
            self.port, self.kind = port, 'com0com'

    class Handle:
        def close(self):
            pass

    checks = InputChecks(lambda: [Port('COM4'), Port('COM5')], lambda: (),
                         port_opener=lambda **kw: Handle())
    a, b = checks.port_pair('COM4', 'COM5'), checks.port_pair('COM5', 'COM4')
    assert (a.state, a.message, a.detail) == (b.state, b.message, b.detail)
    assert 'Reihenfolge' in a.detail


def test_exit_dialog_says_transmission_ends_during_test_release(win):
    fc, w = win('B1tr')
    dlg = w.build_exit_dialog()
    assert dlg.keep_button.text() == texts.EXIT_KEEP
    assert texts.EXIT_TEXT_ACTIVE in ' '.join(lab.text() for lab in dlg.findChildren(QLabel))
    dlg.deleteLater()
