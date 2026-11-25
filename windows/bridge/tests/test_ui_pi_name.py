"""Pi-Name sichtbar: Kopf der Statusansicht und Fenster-/Taskleistentitel, live nachgeführt."""
from dataclasses import replace

import pytest
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.fake import FakeController
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def win(app):
    made = []

    def _make(state='B1', size=(440, 720)):
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


def _rename(fc, w, name):
    fc.set(context=replace(fc._c, pi_name=name))
    w.refresh()
    QTest.qWait(20)


def test_name_in_header_and_window_title(win):
    fc, w = win('B1')
    name = fc._c.pi_name
    assert name
    assert w.stack.currentWidget() is w.status_view
    assert w.status_view.header.title.text() == name
    assert w.windowTitle() == f'{texts.APP_TITLE} – {name}'


def test_name_change_updates_both_without_rebuild(win):
    fc, w = win('B1')
    title_widget = w.status_view.header.title
    _rename(fc, w, 'Labor-Pi 7')
    assert w.status_view.header.title is title_widget
    assert title_widget.text() == 'Labor-Pi 7'
    assert w.windowTitle() == f'{texts.APP_TITLE} – Labor-Pi 7'


def test_name_not_repeated_next_to_entry_count(win):
    fc, w = win('B1')
    _rename(fc, w, 'Labor-Pi 7')
    assert 'Labor-Pi 7' not in w.status_view.count_label.text()
    assert w.status_view.count_label.text().endswith('Einträge')


def test_long_name_is_shortened_with_tooltip(win):
    fc, w = win('B1')
    long_name = 'Prüfstand mit sehr langem Namen in Halle A neben dem Kalibrierlabor'
    _rename(fc, w, long_name)
    t = w.status_view.header.title
    assert len(t.text()) <= texts.NAME_MAX and t.text().endswith('…')
    assert t.toolTip() == long_name
    assert len(w.windowTitle()) <= len(texts.APP_TITLE) + 3 + texts.NAME_MAX


def test_no_name_keeps_plain_title_and_no_empty_header(win):
    fc, w = win('B1')
    _rename(fc, w, None)
    assert w.windowTitle() == texts.APP_TITLE
    assert w.status_view.header.title.text().strip()          # Platzhaltertext statt leerer Fläche
    assert 'None' not in w.windowTitle()


def test_uart_direct_has_no_pi_name_in_title(win):
    fc, w = win('B1')
    fc.set(context=replace(fc._c, route_mode='uart_direct', adapter_port='COM9'))
    w.refresh()
    assert w.windowTitle() == texts.APP_TITLE


def test_name_fits_at_minimum_size(win):
    fc, w = win('B1', (380, 560))
    _rename(fc, w, 'Prüfstand 3 – Halle A, Reihe 12 links')
    t = w.status_view.header.title
    assert t.height() >= t.heightForWidth(t.width()) - 2
    assert t.geometry().right() <= w.status_view.header.width()
    assert isinstance(t, QLabel)
