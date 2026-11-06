"""Qt-Fenster gegen den echten AppController (offscreen, Fakes für Transport/COM)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QRadioButton
from test_app_controller import (  # noqa: F401  (identity-Fixture unten)
    CODE,
    identity,  # noqa: F401
    make,
    profile_bytes,
)


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def real(app, tmp_path, identity):  # noqa: F811
    made = []

    def _make():
        c = make(tmp_path)
        w = MainWindow(c, dark=False)
        w.show()
        made.append((c, w))
        return c, w
    _make.profile = tmp_path / 'pi.dispread'
    _make.profile.write_bytes(profile_bytes(identity))
    yield _make
    for c, w in made:
        c.request_exit(True)
        w.force_close()
        w.deleteLater()
    QApplication.processEvents()


def pump(ms=400):
    QTest.qWait(ms)


def settle(w):
    pump(50)
    w.pool.waitForDone(5000)
    pump(100)


def wait_until(pred, timeout=5000):
    import time
    end = time.monotonic() + timeout / 1000
    while not pred():
        assert time.monotonic() < end, 'erwartete Ansicht nicht erreicht'
        QTest.qWait(20)


def click(w, name):
    b = w.findChild(QPushButton, name)
    assert b is not None, name
    b.click()
    settle(w)


def test_setup_walk_through_with_manual_port_pair_and_profile(real):
    c, w = real()
    assert c.context().mode == 'setup' and c.context().setup.variant == 'E1'
    click(w, 'btn_manual_pair')
    wait_until(lambda: len(w.setup_view.findChildren(QRadioButton)) == 6 and not w.pool.activeThreadCount())
    assert c.context().setup.variant == 'E1manual'
    radios = w.setup_view.findChildren(QRadioButton)
    assert len(radios) == 6                      # je Seite drei COM-Ports, nichts vorgewählt
    radios[0].setChecked(True)                   # Brückenseite COM3
    radios[5].setChecked(True)                   # GSVmulti-Seite COM5
    click(w, 'btn_set_port_pair')
    wait_until(lambda: c.context().setup.variant == 'E1ok')
    assert c.snapshot().components == 'manual_pair'
    assert c.context().setup.variant == 'E1ok'
    labels = ' '.join(lab.text() for lab in w.setup_view.findChildren(type(w.setup_view.lead)))
    assert 'nicht von der App geprüft' in labels
    w.setup_view.next_button.click()
    wait_until(lambda: c.context().setup.variant == 'E2' and w.setup_view.variant[0] == 'E2')
    w.open_profile_path(str(real.profile))
    wait_until(lambda: c.context().setup.variant == 'E2b' and w.setup_view.variant[0] == 'E2b' and 'pair' in w.setup_view.buttons)
    assert c.context().setup.variant == 'E2b' and c.context().pi_name == 'Prüfstand 2'
    # Koppeln bleibt aus, bis der Fingerabdruck bestätigt ist
    assert not w.setup_view.buttons['pair'].isEnabled()


def test_drag_and_drop_opens_profile(real):
    c, w = real()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(real.profile))])
    ev = QDropEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    w.dropEvent(ev)
    settle(w)
    assert c.context().pi_name == 'Prüfstand 2'


def test_invalid_profile_shows_error_notice_not_exception(real, tmp_path):
    c, w = real()
    bad = tmp_path / 'bad.dispread'
    bad.write_bytes(b'{}')
    w.open_profile_path(str(bad))
    settle(w)
    assert c.context().pi_name is None
    assert c.context().setup.data['notice'] == 'profile_invalid'
    flat = ' '.join(lab.text() for lab in w.setup_view.findChildren(type(w.setup_view.lead)))
    assert 'Profil ungültig' in flat


def test_pairing_flow_from_window(real):
    c, w = real()
    c.set_port_pair('COM4', 'COM5')
    w.open_profile_path(str(real.profile))
    settle(w)
    c.setup_step('next') if c.context().setup.step == 1 else None
    assert c.context().setup.variant == 'E2b'
    w.refresh()
    w.setup_view.checks['fp_ok'].setChecked(True)
    w.setup_view.code_edit.setText(CODE)
    click(w, 'btn_pair')
    assert c.context().setup.step == 3
    assert CODE not in repr(c.context())


def test_footer_shows_development_state_without_build_info(real):
    c, w = real()
    assert w.status_view.version_label.text() == texts.version_label('Entwicklungsstand') == 'Entwicklungsstand'


def test_operate_mode_after_finish_shows_status_view(real):
    c, w = real()
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(real.profile.read_bytes())
    c.setup_step('finish')
    w.refresh()
    assert c.context().mode == 'operate'
    assert w.stack.currentWidget() is w.status_view
    assert w.status_view.dut_label.text() == texts.DUT_LOCK_LINE


def test_footer_shows_channel_when_build_info_present(real):
    c, w = real()
    from dataclasses import replace
    c.context = lambda ctx=c.context(): replace(ctx, channel='Interner Testbuild - nicht qualifiziert')
    w.refresh()
    assert w.status_view.channel_label.text() == 'Interner Testbuild - nicht qualifiziert'
    assert not w.status_view.channel_label.isHidden()


def test_empty_journal_shows_calm_empty_state(real):
    c, w = real()
    sv = w.status_view
    assert sv.model.rowCount() == 0 and not sv.empty_label.isHidden()
    assert sv.empty_label.text() == texts.NO_EVENTS and sv.count_label.text().startswith('0 Einträge')


def test_step_bar_hides_labels_at_380_and_shows_them_inside_geometry_at_440(real):
    c, w = real()
    sh = w.setup_view.step_header
    w.resize(380, 720)
    wait_until(lambda: sh.width() <= 380 and sh.width() > 300)
    assert not sh.labels_visible()                     # 12 px passen nicht: nur Kreise
    assert sh.height() == 30
    assert sh.LABEL_PT >= 9                            # nie unter die Lesbarkeitsgrenze
    for i in range(1, 6):
        assert sh.circle_rect(i).right() <= sh.width() and sh.circle_rect(i).left() >= 0
    w.resize(440, 720)
    wait_until(lambda: sh.width() > 400)
    assert sh.labels_visible() and sh.height() == 54
    boxes = sh._label_boxes()
    assert all(x0 >= 0 and x1 <= sh.width() for x0, x1 in boxes)
    assert all(b[0] - a[1] >= 4 for a, b in zip(boxes, boxes[1:], strict=False))


def test_step_circle_tooltip_names_the_step(real):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QHelpEvent
    c, w = real()
    sh = w.setup_view.step_header
    shown = []
    import dispread_bridge_app.ui.setup_view as sv
    orig = sv.QToolTip.showText
    sv.QToolTip.showText = lambda pos, text, widget=None, *a: shown.append(text)
    try:
        r = sh.circle_rect(3).center().toPoint()
        QApplication.sendEvent(sh, QHelpEvent(QHelpEvent.Type.ToolTip, r, QPoint(0, 0)))
    finally:
        sv.QToolTip.showText = orig
    assert shown == ['Schritt 3: Verbinden']


def test_inventory_rows_have_caption_label_and_body_value(real):
    c, w = real()
    labels = {lab.text(): lab for lab in w.setup_view.findChildren(QLabel)}
    key = labels['Windows']
    assert key.property('caption') is True and key.property('secondary') is True
    value = labels['Windows 11, 64 Bit – unterstützt']
    assert not value.property('caption')
    assert 'Unterstützte Windows-Version' not in labels and 'Installiert' not in labels
    assert labels['Brücke'].property('caption') is True
