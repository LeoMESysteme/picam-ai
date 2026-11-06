"""Qt-Fenster gegen den echten AppController (offscreen, Fakes für Transport/COM)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QRadioButton
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


def click(w, name):
    b = w.findChild(QPushButton, name)
    assert b is not None, name
    b.click()
    pump()
    w.pool.waitForDone(3000)
    pump()


def test_setup_walk_through_with_manual_port_pair_and_profile(real):
    c, w = real()
    assert c.context().mode == 'setup' and c.context().setup.variant == 'E1'
    click(w, 'btn_manual_pair')
    assert c.context().setup.variant == 'E1manual'
    radios = w.setup_view.findChildren(QRadioButton)
    assert len(radios) == 6                      # je Seite drei COM-Ports, nichts vorgewählt
    radios[0].setChecked(True)                   # Brückenseite COM3
    radios[5].setChecked(True)                   # GSVmulti-Seite COM5
    pump()
    click(w, 'btn_set_port_pair')
    assert c.snapshot().components == 'manual_pair'
    assert c.context().setup.variant == 'E1ok'
    labels = ' '.join(lab.text() for lab in w.setup_view.findChildren(type(w.setup_view.lead)))
    assert 'nicht von der App geprüft' in labels
    w.setup_view.next_button.click()
    pump()
    assert c.context().setup.step == 2 and c.context().setup.variant == 'E2'
    w.open_profile_path(str(real.profile))
    pump(300)
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
    pump(300)
    assert c.context().pi_name == 'Prüfstand 2'


def test_invalid_profile_shows_error_notice_not_exception(real, tmp_path):
    c, w = real()
    bad = tmp_path / 'bad.dispread'
    bad.write_bytes(b'{}')
    w.open_profile_path(str(bad))
    pump(300)
    assert c.context().pi_name is None
    assert c.context().setup.data['notice'] == 'profile_invalid'
    flat = ' '.join(lab.text() for lab in w.setup_view.findChildren(type(w.setup_view.lead)))
    assert 'Profil ungültig' in flat


def test_pairing_flow_from_window(real):
    c, w = real()
    c.set_port_pair('COM4', 'COM5')
    w.open_profile_path(str(real.profile))
    pump(300)
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
