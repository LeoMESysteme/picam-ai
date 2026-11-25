"""Werkzeugfenster flackern nicht: bei gleichem Aufbau werden nur Texte getauscht (Befund Windows 1.0.0)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace

import pytest
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.fake import FakeController
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtWidgets import QApplication, QLabel


@pytest.fixture(scope='session')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make(app):
    made = []

    def _make(state='B1tr'):
        fc = FakeController(state)
        w = MainWindow(fc, dark=False)
        w.show()
        made.append(w)
        return fc, w
    yield _make
    for w in made:
        w.force_close()
        w.deleteLater()
    QApplication.processEvents()


def texts_of(win):
    return [lab.text() for lab in win.content.findChildren(QLabel)]


def open_forward(w):
    n = next(i for i, c in enumerate(w.status_view.chips) if c.view.key == 'forward')
    w._show_chip(n)
    QApplication.processEvents()
    return w.tool_windows['chip']


def test_counter_update_keeps_widgets_and_updates_text(make):
    fc, w = make('B1tr')
    win = open_forward(w)
    content = win.content
    assert any('128' in t for t in texts_of(win)), texts_of(win)
    labels_before = win.content.findChildren(QLabel)
    for n in range(129, 140):
        fc.set(context=replace(fc.context(), forwarded=n))
        w.refresh()
        assert win.content is content                      # nicht neu gebaut
    assert win.content.findChildren(QLabel) == labels_before
    assert any('139' in t for t in texts_of(win)) and not any('128' in t for t in texts_of(win))


def test_no_new_content_widget_or_resize_for_value_change(make):
    fc, w = make('B1tr')
    win = open_forward(w)
    built = []
    orig = win._new_content
    win._new_content = lambda: (built.append(1), orig())[1]
    size = win.size()
    fc.set(context=replace(fc.context(), forwarded=777))
    w.refresh()
    assert built == [] and win.size() == size


def test_copy_confirmation_survives_value_update(make):
    fc, w = make('B1tr')
    win = open_forward(w)
    from dispread_bridge_app.ui.widgets import ValueField
    vf = [f for f in win.content.findChildren(ValueField) if f._copyable]
    assert vf
    vf[0].copy()
    assert vf[0].confirming
    fc.set(context=replace(fc.context(), forwarded=900))
    w.refresh()
    assert vf[0].confirming and vf[0].parent() is not None


def test_structure_change_rebuilds(make):
    fc, w = make('B1tr')
    win = open_forward(w)
    content = win.content
    n = next(i for i, c in enumerate(w.status_view.chips) if c.view.key == 'forward')
    fc.set(context=replace(fc.context(), test_release=False, waiting_for_run=True, run_id=None))
    fc.set(readiness=replace(fc.snapshot(), output='locked'))
    w.refresh()
    QApplication.processEvents()
    assert w.status_view.chips[n].view.word != 'Übergeben'
    assert win.content is not content
    assert any(w.status_view.chips[n].view.word in t for t in texts_of(win))


def test_rebuild_swaps_without_visible_intermediate(make):
    fc, w = make('B1tr')
    win = open_forward(w)
    states = []
    orig = win.setUpdatesEnabled
    win.setUpdatesEnabled = lambda on: (states.append(on), orig(on))[1]
    win.set_content(('x',), lambda body: body.addWidget(QLabel('neu')))
    assert states == [False, True]


def test_info_value_change_updates_in_place(make):
    fc, w = make('B1tr')
    fc.set(context=replace(fc.context(), run_id='r-1', pi_id='pi-1'))
    w.refresh()
    w._show_details()
    QApplication.processEvents()
    win = w.tool_windows['info']
    content = win.content
    fc.set(context=replace(fc.context(), run_id='r-2'))
    w.refresh()
    from dispread_bridge_app.ui.widgets import ValueField
    assert win.content is content and 'r-2' in [f.value for f in win.content.findChildren(ValueField)]
    fc.set(context=replace(fc.context(), run_id=None))        # Feld verschwindet: Aufbau ändert sich
    w.refresh()
    assert win.content is not content


def test_paired_time_text_updates_in_place(make):
    fc, w = make('B1tr')
    c = fc.context()
    fc.set(context=replace(c, paired=(('Pi A', 'pi-a', 'vor 2 Stunden'), ('Pi B', 'pi-b', 'vor 3 Stunden')),
                           pi_id='pi-a'))
    w.refresh()
    w._show_switch()
    QApplication.processEvents()
    win = w.tool_windows['paired']
    content = win.content
    fc.set(context=replace(fc.context(), paired=(('Pi A', 'pi-a', 'vor 2 Stunden'), ('Pi B', 'pi-b', 'vor 4 Stunden'))))
    w.refresh()
    assert win.content is content and 'vor 4 Stunden' in texts_of(win)
    assert texts.CURRENT_PI in texts_of(win)
