import os
import threading

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from dispread_bridge_app.ui.fake import FakeController
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from dispread.bridge.types import BridgeEvent


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make(app):
    made = []

    def _make(state='B1', dark=False):
        fc = FakeController(state)
        w = MainWindow(fc, dark=dark)
        w.show()
        made.append(w)
        return fc, w
    yield _make
    for w in made:
        w.force_close()
        w.deleteLater()
    QApplication.processEvents()


def pump(ms=50):
    QTest.qWait(ms)


def test_sizes(make):
    _, w = make()
    assert (w.width(), w.height()) == (440, 720)
    assert (w.minimumWidth(), w.minimumHeight()) == (380, 560)


def test_b1_content(make):
    _, w = make()
    s = w.status_view
    assert s.headline_label.text() == 'Verbunden – Lauf 7 läuft, keine Werteausgabe'
    assert 'DUT-Ausgabe gesperrt' in s.dut_label.text() and s.dut_label.isVisibleTo(w)
    assert len(s.chips) == 6
    assert len({c.height() for c in s.chips[:3]}) == 1 and len({c.height() for c in s.chips[3:]}) == 1


def test_dut_line_visible_in_setup_and_every_state(make):
    for st in ('B1', 'B2', 'B3', 'B5', 'E1', 'E2b', 'E5'):
        _, w = make(st)
        view = w.stack.currentWidget()
        assert view.dut_label.isVisibleTo(w), st
        assert texts_lock in view.dut_label.text()


texts_lock = 'DUT-Ausgabe gesperrt'


def test_setup_state_shows_setup_view(make):
    _, w = make('E2b')
    assert w.stack.currentWidget() is w.setup_view
    assert w.setup_view.step_header.current == 2


def test_click_chip_opens_flyout_and_escape_closes(make):
    _, w = make()
    chip = w.status_view.chips[2]
    QTest.mouseClick(chip, Qt.LeftButton)
    pump()
    assert w.status_view.flyout is not None and w.status_view.flyout.isVisible()
    QTest.keyClick(w.status_view.flyout, Qt.Key_Escape)
    pump()
    assert not w.status_view.flyout.isVisible()


def test_segmented_filters_faults(make):
    _, w = make()
    s = w.status_view
    all_rows = s.journal.model().rowCount()
    s.seg_faults.click()
    assert 0 < s.journal.model().rowCount() < all_rows
    assert 'Störungen' in s.count_label.text() or 'Einträge' in s.count_label.text()


def test_tab_order_head_bar_chips_filter_journal_footer(make):
    _, w = make('B3')
    s = w.status_view
    s.lock_button if s.lock_button.focusPolicy() else s.chips[0]
    start = s.focus_chain()
    names = [x.objectName() for x in start]
    assert names.index('bar_primary') < names.index('chip0') < names.index('chip5') \
        < names.index('seg_all') < names.index('journal') < names.index('export') < names.index('details')


def test_enter_triggers_primary_action(make):
    fc, w = make('B3')
    btn = w.status_view.infobar.buttons[-1]
    btn.setFocus()
    QTest.keyClick(btn, Qt.Key_Return)
    pump(150)
    assert ('connect', 'network', None) in fc.calls


def test_closed_window_needs_explicit_worker_exit(make):
    fc, w = make()
    w.close()
    pump()
    assert w.isHidden()
    assert not [c for c in fc.calls if c[0] in ('request_exit', 'disconnect')]


def test_minimize_keeps_worker_active(make):
    fc, w = make()
    w.showMinimized()
    pump()
    assert not [c for c in fc.calls if c[0] in ('request_exit', 'disconnect')]
    assert fc.worker_status().active


def test_tray_hint_only_once(make):
    _, w = make()
    w.close()
    w.show()
    w.close()
    assert w.tray_hint_count == 1


def test_tray_state_and_tooltip_follow_headline(make):
    fc, w = make('B1')
    assert w.tray_state == 'normal' and w.tray_tooltip() == 'Verbunden – Lauf 7 läuft, keine Werteausgabe'
    fc.set_state('B3')
    w.refresh()
    assert w.tray_state == 'err' and w.tray_tooltip().startswith('Pi antwortet nicht')
    fc.set_state('B4a')
    w.refresh()
    assert w.tray_state == 'warn'


def test_busy_run_locks_configuration(make):
    _, w = make('B1x')
    assert w.status_view.lock_button.isVisibleTo(w)
    assert w.setup_view.isEnabled()      # Navigation/Export bleiben; nur Konfigurationsfelder werden je Schritt gesperrt
    assert w.status_view.lock_button.accessibleName() == 'Pi-Wechsel gesperrt'
    assert w.status_view.lock_button.focusPolicy() != Qt.NoFocus


def test_exit_dialog_default_keeps_transmitting(make):
    fc, w = make('B1')
    dlg = w.build_exit_dialog()
    assert dlg.keep_button.isDefault()
    assert dlg.text_label.text().startswith('Die Verbindung zum Pi endet')
    dlg.show()
    QTest.keyClick(dlg, Qt.Key_Escape)
    assert dlg.result() == 0 and not dlg.confirmed
    fc2, w2 = make('B1x')
    assert w2.build_exit_dialog().text_label.text() == 'Die Übertragung an GSVmulti endet. Der Lauf auf dem Pi läuft weiter.'


def test_exit_after_confirm_calls_request_exit(make):
    fc, w = make('B1')
    w.confirm_exit = lambda: True
    w.exit_bridge()
    pump(200)
    assert ('request_exit', True) in fc.calls


def test_exit_declined_does_nothing(make):
    fc, w = make('B1')
    w.confirm_exit = lambda: False
    w.exit_bridge()
    pump(100)
    assert not [c for c in fc.calls if c[0] == 'request_exit']


def test_events_from_foreign_thread_land_in_gui_thread(make):
    fc, w = make()
    seen = []
    w.on_event_hook = lambda ev: seen.append(threading.get_ident())
    t = threading.Thread(target=lambda: fc.emit(BridgeEvent('connection', 'backoff', None, None, {})))
    t.start()
    t.join()
    pump(100)
    assert seen == [threading.get_ident()]
    assert w.status_view.journal.model().rowCount() > 0


def test_controller_calls_leave_gui_thread(make):
    fc, w = make('B3')
    w.do_action('reconnect')
    pump(200)
    assert fc.call_threads and all(t != threading.get_ident() for t in fc.call_threads)


def test_dark_theme_applies(make):
    _, w = make(dark=True)
    assert w.palette().window().color().name() == '#202020'
