# ruff: noqa: F811
"""BQ6: Bedienung glätten (Usability-Review). Texte, Zustände und Layout bei 380x560."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace

import pytest
from dispread_bridge_app.app_controller import AppError
from dispread_bridge_app.readiness import Readiness
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.fake import FakeController
from dispread_bridge_app.ui.port import SetupState, UiContext
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QProgressBar,
    QPushButton,
    QToolButton,
)
from test_app_controller import (  # noqa: F401
    CODE,
    FakeWorker,
    identity,  # noqa: F401
    make,
    profile_bytes,
)

from dispread.bridge.types import BridgeEvent


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def fake_win(app):
    made = []

    def _make(state, size=(440, 720)):
        fc = FakeController(state)
        w = MainWindow(fc, dark=False)
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


@pytest.fixture
def real(app, tmp_path, identity):  # noqa: F811
    made = []

    def _make(**kw):
        c = make(tmp_path, **kw)
        w = MainWindow(c, dark=False)
        w.show()
        made.append((c, w))
        return c, w
    _make.profile = profile_bytes(identity)
    yield _make
    for c, w in made:
        c.request_exit(True)
        w.force_close()
        w.deleteLater()
    QApplication.processEvents()


def settle(w):
    QTest.qWait(50)
    w.pool.waitForDone(5000)
    QTest.qWait(100)


def flat(spec):
    return repr(spec['blocks'])


def labels(w):
    return ' | '.join(lab.text() for lab in w.findChildren(QLabel))


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _ctx(variant, step, data=None, **kw):
    return UiContext(pi_name='Prüfstand 2', pi_id='pi-1', bridge_port='COM7', gsv_port='COM8', route='Netzwerk',
                     setup=SetupState(step, variant, data or {}), **kw)


# ---- 1/2: Schritt 3 Verbinden, Backoff, Fehler
def test_connecting_shows_progress_and_cancel_instead_of_connect():
    spec = texts.setup_spec(_ctx('E3', 3, dict(connecting=True)))
    assert any(b[0] == 'progress_busy' and 'Verbindung zu Prüfstand 2 wird aufgebaut' in b[1] for b in spec['blocks'])
    assert spec['next'] == 'Abbrechen' and spec['next_action'] == 'cancel_connect' and spec['freeze']


def test_backoff_in_setup_names_next_attempt_and_hides_duplicate_foot_button():
    spec = texts.setup_spec(replace(_ctx('E3', 3, dict(backoff=True, code='connection_unavailable')), retry_in_s=4))
    bar = spec['blocks'][0]
    assert bar[0] == 'livebar' and 'Pi antwortet nicht – nächster Versuch in 4 s' in bar[2]
    assert spec['next'] is None


@pytest.mark.parametrize('code, action, shows', [
    ('pairing_refused', 'new_code', 'Kopplung abgelehnt'),
    ('peer_invalid', 'open_profile', 'Unter dieser Adresse antwortet ein anderer Pi als im Profil. '
                                     'Adresse oder Profil prüfen.'),
    ('connection_unavailable', 'reconnect', 'Pi nicht erreichbar')])
def test_error_bar_sits_above_selection_with_code_specific_action(code, action, shows):
    spec = texts.setup_spec(_ctx('E3', 3, dict(code=code, found_items=(('https://x', 'aus dem Profil', True),),
                                              choices={'found': ('https://x',)})))
    kinds = [b[0] for b in spec['blocks']]
    assert kinds[0] == 'info' and spec['blocks'][0][1] == 'err'
    assert shows in repr(spec['blocks'][0])
    assert [b[1] for b in spec['blocks'][0][4]] == [action]
    assert 'radios' in kinds and 'entry' in kinds               # Weg und Adresse bleiben bedienbar
    assert (spec['next'] is None) == (action in ('reconnect', 'new_code'))


def test_failed_connect_does_not_hide_the_selection_in_the_controller(real):
    c, w = real(manager_factory=_failing_manager('peer_invalid'), worker_factory=FakeWorker)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(real.profile)
    c._step = 3
    c.connect('network')
    ctx = c.context()
    assert ctx.setup.variant == 'E3' and ctx.setup.data['code'] == 'peer_invalid'
    w.refresh()
    assert w.setup_view.endpoint_edit is not None
    c.select_endpoint('https://127.0.0.1:9')
    assert 'code' not in c.context().setup.data               # neue Auswahl räumt den alten Fehler ab


def _failing_manager(code, peer='disconnected'):
    class M:
        def __init__(self, profile, client_id, credentials, devices, **kw): pass
        def set_worker(self, w): pass
        def connect(self, mode, selected=None): pass
        def disconnect(self): pass
        def snapshot(self):
            return Readiness('ready', 'not_required', peer, 'unavailable', 'idle', 'unconfirmed', code)
    return M


def test_connecting_state_in_window_cancels_and_never_starts_twice(real):
    c, w = real()
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(real.profile)
    c._step = 3
    c.connect('network')
    w.refresh()
    sv = w.setup_view
    assert c.snapshot().peer == 'connecting'
    assert sv.next_button.text() == 'Abbrechen' and sv.findChildren(QProgressBar)
    assert sv.findChildren(QProgressBar)[0].maximum() == 0           # unbestimmt
    n = len(c.seen)
    c.setup_step('next')                                           # kein zweiter Verbindungsaufbau
    QTest.qWait(100)
    assert len(c.seen) == n and c._manager is not None and c.snapshot().peer == 'connecting'
    sv.next_button.click()
    settle(w)
    assert c.snapshot().peer == 'disconnected'


def test_backoff_countdown_comes_from_the_known_schedule(tmp_path, identity):
    clock = Clock()
    c = make(tmp_path, clock=clock, manager_factory=_failing_manager('connection_unavailable', 'backoff'),
             worker_factory=FakeWorker)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.connect('network')
    ev = BridgeEvent('connection', 'connection_unavailable', None, None, {})
    c._emit(ev)
    assert c.context().retry_in_s == 1
    clock.t += 2
    assert c.context().retry_in_s is None                          # der Versuch läuft
    c._emit(ev)
    assert c.context().retry_in_s == 2
    for _ in range(6):
        c._emit(ev)
    assert c.context().retry_in_s == 8


# ---- 3: Kopplungscode
def test_pair_button_gate_helper_enter_and_show_toggle(fake_win):
    fc, w = fake_win('E2b')
    sv = w.setup_view
    btn = sv.buttons['pair']
    assert btn.text() == 'Code übernehmen' and not btn.isEnabled()
    assert 'Erst Fingerabdruck bestätigen und Code eingeben' in labels(sv)
    sv.checks['fp_ok'].setChecked(True)
    assert not btn.isEnabled()                                   # Code fehlt noch
    sv.code_edit.setText(CODE)
    assert btn.isEnabled()
    from PySide6.QtWidgets import QLineEdit
    assert sv.code_edit.echoMode() == QLineEdit.EchoMode.Password
    sv.checks['code_show'].setChecked(True)
    assert sv.code_edit.echoMode() == QLineEdit.EchoMode.Normal
    QTest.keyClick(sv.code_edit, Qt.Key.Key_Return)
    settle(w)
    assert ('pair', True) in fc.calls


def test_enter_in_code_field_does_nothing_while_gate_closed(fake_win):
    fc, w = fake_win('E2b')
    w.setup_view.code_edit.setText(CODE)
    QTest.keyClick(w.setup_view.code_edit, Qt.Key.Key_Return)
    settle(w)
    assert not [c for c in fc.calls if c[0] == 'pair']


def test_code_lifetime_hint_and_real_expiry(tmp_path, identity):
    clock = Clock()
    c = make(tmp_path, clock=clock)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c._step = 2
    c.pair(CODE, True)
    ctx = c.context()
    assert ctx.setup.step == 3 and ctx.code_remaining_s == 300
    clock.t += 125
    spec = texts.setup_spec(c.context())
    assert 'Code gespeichert – gekoppelt wird beim Verbinden, jetzt gleich (Code noch 2:55 gültig).' in flat(spec)
    clock.t += 200
    ctx = c.context()
    assert ctx.setup.variant == 'E2exp' and ctx.setup.step == 2 and ctx.code_remaining_s is None
    assert c._offer is None                                      # Code wirklich verworfen
    assert 'Code abgelaufen – in der Werkbank einen neuen erzeugen' in flat(texts.setup_spec(ctx))
    c.setup_step('pairing')
    assert c.context().setup.variant == 'E2b'


def test_step2_to_3_moves_focus_to_connect(real):
    c, w = real()
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(real.profile)
    c._step = 2
    w.refresh()
    sv = w.setup_view
    sv.checks['fp_ok'].setChecked(True)
    sv.code_edit.setText(CODE)
    w.activateWindow()
    sv.buttons['pair'].click()
    settle(w)
    assert c.context().setup.step == 3
    assert sv.next_button.text() == 'Verbinden'
    QTest.qWait(50)
    assert sv.next_button.hasFocus() or QApplication.focusWidget() is sv.next_button or not w.isActiveWindow()


# ---- 4: spätere Änderungen
def test_e1ok_offers_change_pair_and_e2ok_offers_other_profile(fake_win):
    fc, w = fake_win('E1ok')
    assert 'change_pair' in w.setup_view.buttons
    w.setup_view.buttons['change_pair'].click()
    settle(w)
    assert ('open_manual_pair',) in fc.calls
    fc.set_state('E2ok')
    w.refresh()
    assert w.setup_view.buttons['open_profile'].text() == 'Anderes Profil öffnen …'


def test_changes_are_disabled_with_reason_while_connected(fake_win):
    fc, w = fake_win('E1ok_run')
    b = w.setup_view.buttons['change_pair']
    assert not b.isEnabled() and 'Erst Verbindung trennen' in b.toolTip()
    fc.set_state('E2ok_run')
    w.refresh()
    b = w.setup_view.buttons['open_profile']
    assert not b.isEnabled() and 'Erst Verbindung trennen' in b.toolTip()


def test_change_pair_in_controller_reopens_port_choice_with_current_pair(real):
    c, w = real()
    c.set_port_pair('COM4', 'COM5')
    assert c.context().setup.variant == 'E1ok'
    c.open_manual_pair()
    ctx = c.context()
    assert ctx.setup.variant == 'E1manual'
    w.refresh()
    assert w.setup_view.combos['bridge_port'].currentText() == 'COM4'
    c.set_port_pair('COM3', 'COM5')
    assert c.context().setup.variant == 'E1ok'


def test_footer_setup_button_goes_to_overview_step_one(tmp_path, identity):
    c = make(tmp_path, manager_factory=_failing_manager('x'), worker_factory=FakeWorker)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c._step = 5
    c.setup_step('finish')
    assert c.context().mode == 'operate'
    c.setup_step('change_setup')
    ctx = c.context()
    assert ctx.mode == 'setup' and ctx.setup.step == 1 and ctx.setup.variant == 'E1ok'


def test_status_toolbar_settings_and_change_setup_action(fake_win):
    fc, w = fake_win('B1')
    b = w.status_view.settings_button
    assert b.toolTip() == 'Einstellungen' and b.accessibleName() == 'Einstellungen' and b.isVisibleTo(w)
    b.click()
    settle(w)
    assert 'open_settings' in w.unhandled          # Einstellungen-Fenster folgt in Runde UI-2
    w.do_action('change_setup')                    # „Einrichtung ändern“ lebt dort weiter
    settle(w)
    assert ('setup_step', 'change_setup') in fc.calls


def test_paired_window_offers_switch_only_when_free(fake_win):
    fc, w = fake_win('B1')
    w._show_switch()
    QTest.qWait(50)
    win = w.tool_windows['paired']
    btns = [b for b in win.findChildren(QPushButton) if b.text() == 'Zu diesem Pi wechseln']
    assert len(btns) == 1 and btns[0].isEnabled()
    btns[0].click()
    settle(w)
    assert ('switch_pi', 'pi-d21a77e6') in fc.calls
    fc2, w2 = fake_win('B1x')                       # Übertragung läuft: Wechsel gesperrt, mit Grund
    w2._show_switch()
    QTest.qWait(50)
    b = [b for b in w2.tool_windows['paired'].findChildren(QPushButton) if b.text() == 'Zu diesem Pi wechseln'][0]
    assert not b.isEnabled() and 'Erst Übertragung beenden' in b.toolTip()


# ---- 5: GSVmulti-Einstellungen
def test_step4_card_states_the_verified_settings():
    spec = texts.setup_spec(_ctx('E4locked', 4))
    s = flat(spec)
    for needle in ('UserDef', 'COM8', '115200 Baud, 8N1', '1 Kanal', 'mV/V', '10 Hz', '%',
                   'Muster: Session aus dem Testlauf vom 06.11.2026 (nur Port anpassen)',
                   'Legen Sie eine neue Testsession an und speichern Sie sie unter eigenem Namen.',
                   'In GSVmulti einstellen'):
        assert needle in s, needle
    assert 'Trennzeichen' not in s and 'Filter' not in s


# ---- 6: Betrieb im echten Lauf
def test_real_run_bar_chip_and_lifesign(fake_win):
    fc, w = fake_win('B1')
    r, wk, c = fc.snapshot(), fc.worker_status(), replace(fc.context(), last_report='14:32:20')
    bar = texts.action_bar(r, wk, c)
    assert bar.kind == 'info' and bar.title == 'Lauf 7 läuft.'
    assert 'GSVmulti erhält absichtlich keine Messwerte – die DUT-Ausgabe ist gesperrt (Windows-Abnahme fehlt). ' \
           'Das ist kein Fehler.' in bar.text
    assert 'Letzte Antwort vom Pi: 14:32:20' in bar.text
    gsv = texts.chips(r, wk, c)[5]
    assert gsv.sub == 'erhält im Lauf keine Werte' and 'bestätigt' not in gsv.word.lower()
    assert 'Letzte Antwort' not in texts.action_bar(r, wk, replace(c, last_report='Leerlauf …')).text
    assert w.status_view.infobar.isVisibleTo(w)


# ---- 7: Neustart
def _stored(tmp_path, identity, **kw):
    c = make(tmp_path, manager_factory=_failing_manager('x', 'authenticated'), worker_factory=FakeWorker, **kw)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c._step = 5
    c.setup_step('finish')
    c.request_exit(True)
    return c


def _restart(tmp_path, **kw):
    connects = []

    class M:
        def __init__(self, profile, client_id, credentials, devices, **k): connects.append(profile.endpoints)
        def set_worker(self, w): pass
        def connect(self, mode, selected=None): connects.append(mode)
        def disconnect(self): pass
        def snapshot(self):
            return Readiness('ready', 'not_required', 'disconnected', 'unavailable', 'idle', 'unconfirmed', 'connect')
    c = make(tmp_path, manager_factory=M, worker_factory=FakeWorker, **kw)
    c.connects = connects
    return c


def test_restart_after_finished_setup_shows_not_connected_with_primary_button(tmp_path, identity):
    _stored(tmp_path, identity)
    c = _restart(tmp_path)
    ctx = c.context()
    assert ctx.mode == 'operate'
    bar = texts.action_bar(c.snapshot(), None, ctx)
    assert bar.title == 'Nicht verbunden.' and bar.buttons == (('Mit Prüfstand 2 verbinden', 'connect', True),)


def test_auto_connect_defaults_on_after_setup_and_never_runs_a_demo(tmp_path, identity):
    _stored(tmp_path, identity)
    c = _restart(tmp_path)
    c._is_paired = lambda: True
    assert c.context().auto_connect is True
    assert c.auto_connect_at_start() is True
    assert 'network' in c.connects and not c._demo_started
    c.set_auto_connect(False)
    c2 = _restart(tmp_path)
    c2._is_paired = lambda: True
    assert c2.context().auto_connect is False and c2.auto_connect_at_start() is False and not c2.connects


def test_auto_connect_needs_finished_setup(tmp_path, identity):
    c = _restart(tmp_path)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    assert c.auto_connect_at_start() is False and not c.connects


def test_auto_connect_checkbox_in_info_window(fake_win):
    fc, w = fake_win('B1')
    w._show_details()
    QTest.qWait(50)
    win = w.tool_windows['info']
    box = [b for b in win.findChildren(QCheckBox)][0]
    box.setChecked(True)
    settle(w)
    assert ('set_auto_connect', True) in fc.calls
    assert 'automatisch mit Prüfstand 2 verbinden' in labels(win)
    assert 'Gespeichert' in labels(win) and w._info.saved_row.isVisibleTo(win)


def test_window_requests_auto_connect_once_at_start(fake_win):
    fc, w = fake_win('B10')
    w.auto_connect_at_start()
    settle(w)
    assert fc.calls.count(('auto_connect_at_start',)) == 1


# ---- 8: Mindestgröße
STATES_380 = ('B1', 'B2', 'B3', 'B10', 'E1', 'E2', 'E2b', 'E3', 'E3uart', 'E4locked_run', 'E5busy', 'E5')


@pytest.mark.parametrize('state', STATES_380)
def test_no_clipped_buttons_or_labels_at_minimum_size(fake_win, state):
    fc, w = fake_win(state, (380, 560))
    QTest.qWait(80)
    view = w.stack.currentWidget()
    for b in view.findChildren(QPushButton):
        if b.isVisibleTo(w) and b.objectName() not in ('bar_secondary', 'bar_primary') or (
                b.isVisibleTo(w) and b.parentWidget() is not None):
            assert b.width() >= b.sizeHint().width() - 1, (state, b.objectName(), b.text())
    foot = view.findChild(QFrame, 'toolbar') or view.findChild(QFrame, 'footer')
    btns = [b for b in foot.findChildren(QPushButton) + foot.findChildren(QToolButton) if b.isVisibleTo(w)]
    for i, a in enumerate(btns):
        for b in btns[i + 1:]:
            ra, rb = a.geometry(), b.geometry()
            if a.parentWidget() is b.parentWidget():
                assert not ra.intersects(rb), (state, a.text(), b.text())
        assert a.mapTo(foot, a.rect().topLeft()).x() + a.width() <= foot.width(), (state, a.text())
    for lab in view.findChildren(QLabel):
        if lab.isVisibleTo(w) and lab.wordWrap() and lab.width() > 20 and lab.text():
            assert lab.height() >= lab.heightForWidth(lab.width()) - 2, (state, lab.text()[:40])


@pytest.mark.parametrize('state', ('B3', 'E3', 'E2b'))
def test_info_bar_buttons_stay_inside_the_bar(fake_win, state):
    from dispread_bridge_app.ui.widgets import InfoBar
    fc, w = fake_win(state, (380, 560))
    QTest.qWait(80)
    for bar in w.stack.currentWidget().findChildren(InfoBar):
        if not bar.isVisibleTo(w):
            continue
        assert bar.height() >= bar.layout().totalHeightForWidth(bar.width()) - 2, state
        for b in bar.findChildren(QPushButton):
            if b.isVisibleTo(w):
                assert b.geometry().bottom() <= bar.height(), (state, b.text())


def test_checkbox_text_wraps_and_toggles_by_click(fake_win):
    fc, w = fake_win('E5', (380, 560))
    sv = w.setup_view
    cb = sv.checks['test_session_ok']
    lab = [x for x in sv.findChildren(QLabel) if x.text() == 'Ich verwende eine getrennte GSVmulti-Testsession.'][0]
    assert lab.wordWrap()
    QTest.mouseClick(lab, Qt.MouseButton.LeftButton)
    assert cb.isChecked()


# ---- 9: Schritt 1
def test_unverified_pair_check_hint_and_two_combos(real):
    c, w = real()
    c._vcom_unverified = c._manual_open = True
    w.refresh()
    sv = w.setup_view
    assert 'Automatische Prüfung ist in dieser Version nicht verfügbar – wählen Sie Ihr Paar ' \
           '(z. B. com0com COM7 ↔ COM8).' in labels(sv)
    assert set(sv.combos) == {'bridge_port', 'gsv_port'}
    a, b = sv.combos['bridge_port'], sv.combos['gsv_port']
    assert isinstance(a, QComboBox) and a.accessibleName() and b.accessibleName()
    assert not sv.buttons['set_port_pair'].isEnabled()
    a.setCurrentText('COM3')
    items = {b.itemText(i): b.model().item(i).isEnabled() for i in range(b.count())}
    assert items['COM3'] is False and items['COM4'] is True               # gleiche Ports nicht zulassen
    b.setCurrentText('COM5')
    assert sv.buttons['set_port_pair'].isEnabled()


def test_weiter_takes_over_the_choice(real):
    c, w = real()
    c.open_manual_pair()
    w.refresh()
    sv = w.setup_view
    sv.combos['bridge_port'].setCurrentText('COM3')
    sv.combos['gsv_port'].setCurrentText('COM5')
    assert sv.next_button.isEnabled()
    sv.next_button.click()
    settle(w)
    assert c.context().setup.step == 2 and c.context().bridge_port == 'COM3'


def test_weiter_is_grey_with_reason_until_ports_chosen(real):
    c, w = real()
    c.open_manual_pair()
    w.refresh()
    sv = w.setup_view
    assert not sv.next_button.isEnabled() and 'Erst beide COM-Ports wählen' in sv.next_reason.text()
    assert not sv.next_reason.isHidden()


# ---- 10: Fehler bei Weiter, Pflichthaken
def test_error_on_next_scrolls_to_the_bar_and_focuses_it(real):
    c, w = real()
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(real.profile)
    c._step = 2
    w.refresh()
    w.activateWindow()
    sv = w.setup_view
    sv.scroll.verticalScrollBar().setValue(sv.scroll.verticalScrollBar().maximum())
    sv.next_button.click()
    settle(w)
    assert sv.error_bar is not None and sv.error_bar.isVisibleTo(w)
    assert 'Pi nicht gekoppelt' in sv.error_bar.title_label.text()
    assert sv.scroll.verticalScrollBar().value() == 0
    assert sv.error_bar.hasFocus() or not w.isActiveWindow()


def test_next_is_grey_with_reason_until_the_required_check_is_set(fake_win):
    fc, w = fake_win('E4locked_run')
    sv = w.setup_view
    assert not sv.next_button.isEnabled()
    assert 'Erst bestätigen, dass GSVmulti eingestellt ist' in sv.next_reason.text() and not sv.next_reason.isHidden()
    sv.checks['session_ok'].setChecked(True)
    assert sv.next_button.isEnabled() and sv.next_reason.isHidden()


# ---- 11: Beenden
def test_exit_dialog_says_cancel_when_nothing_is_transmitted(fake_win):
    fc, w = fake_win('B1')
    assert w.build_exit_dialog().keep_button.text() == 'Abbrechen'
    fc2, w2 = fake_win('B1x')
    assert w2.build_exit_dialog().keep_button.text() == 'Weiter übertragen'


def test_visible_exit_action_in_footer(fake_win):
    for state in ('B1',):
        fc, w = fake_win(state)
        view = w.stack.currentWidget()
        b = view.exit_button
        assert b.accessibleName() == b.toolTip() == 'Brücke beenden …' and b.isVisibleTo(w)
        asked = []
        w.confirm_exit = lambda a=asked: a.append(1) or False
        b.click()
        settle(w)
        assert asked or state == 'E2b'       # ohne Verbindung wird direkt beendet (nächster Test)


def test_exit_button_without_connection_quits_without_dialog(fake_win):
    fc, w = fake_win('E2')
    w.stack.currentWidget().exit_button.click()
    settle(w)
    assert ('request_exit', True) in fc.calls


# ---- 12: Schritt 5 mit Lauf
def test_step5_with_run_texts(fake_win):
    fc, w = fake_win('E5busy')
    assert 'Diese Ansicht aktualisiert sich selbst, sobald der Lauf endet.' in labels(w.setup_view)
    assert w.setup_view.next_button.text() == 'Ohne Test beenden'


# ---- 13: Backoff-Leiste
def test_backoff_bar_has_stop_automation_and_one_sentence(fake_win):
    fc, w = fake_win('B3')
    bar = texts.action_bar(fc.snapshot(), fc.worker_status(), fc.context())
    assert ('Automatik stoppen', 'stop_retry', False) in bar.buttons
    assert bar.text.count('. ') == 0 and bar.text.endswith('.')
    pi = texts.chips(fc.snapshot(), fc.worker_status(), fc.context())[2]
    assert '1, 2, 4, 8 s' in pi.hint


# ---- 14: Neustart mitten in der Einrichtung
def test_restart_mid_setup_leads_with_saved_progress(tmp_path, identity):
    c = make(tmp_path)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c2 = _restart(tmp_path)
    ctx = c2.context()
    assert ctx.setup.step == 3 and ctx.setup.data.get('resumed')
    assert texts.setup_spec(ctx)['lead'] == \
        'Schritt 3 von 5: Verbindung neu herstellen (Ihr Fortschritt bis hier ist gespeichert).'
    c2.connect('network')
    assert texts.setup_spec(c2.context())['lead'] == 'Schritt 3 von 5: Weg zum Pi wählen.'


# ---- 15: Portpaar manuell im Betrieb
def test_manual_pair_chip_is_info_with_ports_and_yellow_only_for_open_error():
    r = Readiness('manual_pair', 'not_required', 'authenticated', 'output_off', 'idle', 'unconfirmed', None)
    ctx = UiContext(pi_name='P', bridge_port='COM7', gsv_port='COM8')
    comp = texts.chips(r, None, ctx)[0]
    assert (comp.word, comp.tone) == ('Portpaar COM7 ↔ COM8', 'info')
    bad = texts.chips(r, None, replace(ctx, demo=True, com_issue='busy'))[0]
    assert bad.tone == 'warn'


def test_controller_notice_error_is_raised_as_app_error(real):
    c, _ = real()
    with pytest.raises(AppError):
        c.setup_step('next')


def test_b1tr_shows_test_release_and_shot(fake_win):
    from pathlib import Path
    fc, w = fake_win('B1tr')
    QTest.qWait(50)
    texts_all = ' '.join(lbl.text() for lbl in w.findChildren(QLabel))
    assert 'Testfreigabe aktiv' in texts_all and 'nicht abgenommen' in texts_all
    assert '128 Werte an COM4 übergeben' in texts_all
    assert 'GSVmulti erhält absichtlich keine Messwerte' not in texts_all
    out = Path('/home/me-systeme/picam-ai/.superpowers/sdd/2026-11-06-bruecke-ui/shots')
    if out.is_dir():
        w.grab().save(str(out / 'r2-app-B1-testfreigabe.png'))
