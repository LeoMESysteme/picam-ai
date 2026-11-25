"""Journal der Statusansicht: Abgleich mit dem Controller statt Einmalübernahme (Befund Windows 1.0.0)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace

import pytest
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.fake import FakeController
from dispread_bridge_app.ui.port import JournalEntry as J
from dispread_bridge_app.ui.window import MainWindow
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication


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


def entries(n, start=0, fault=False):
    return tuple(J(f'10:{i % 60:02d}:00', f'Eintrag {i}', fault=fault) for i in range(start + n - 1, start - 1, -1))


def push(fc, w, journal):
    fc.set(context=replace(fc.context(), journal=tuple(journal)))
    w.refresh()


def titles(model):
    return [model.index(r).data() for r in range(model.rowCount())]


def watch(model):
    ev = {'reset': 0, 'insert': 0, 'remove': 0, 'changed': 0}
    model.modelReset.connect(lambda: ev.__setitem__('reset', ev['reset'] + 1))
    model.rowsInserted.connect(lambda *_: ev.__setitem__('insert', ev['insert'] + 1))
    model.rowsRemoved.connect(lambda *_: ev.__setitem__('remove', ev['remove'] + 1))
    model.dataChanged.connect(lambda *_: ev.__setitem__('changed', ev['changed'] + 1))
    return ev


def test_new_entries_arrive_after_the_first(make):
    fc, w = make('B1')
    sv = w.status_view
    base = tuple(fc.context().journal)
    push(fc, w, (J('15:00:00', 'Neu 1'),) + base)
    push(fc, w, (J('15:00:05', 'Neu 2'),) + (J('15:00:00', 'Neu 1'),) + base)
    assert sv.model.total == len(base) + 2
    assert titles(sv.model)[:2] == ['Heute', 'Neu 2']
    assert sv.count_label.text().startswith(f'{len(base) + 2} Einträge')


def test_counter_row_replaced_without_reset(make):
    fc, w = make('B1tr')
    sv = w.status_view
    ev = watch(sv.model)
    j = tuple(fc.context().journal)
    new_first = J('14:41:30', '129 Werte weitergegeben', 'x')
    push(fc, w, (new_first,) + j[1:])
    assert ev['reset'] == 0 and ev['changed'] >= 1 and ev['insert'] == 0 and ev['remove'] == 0
    assert '129 Werte weitergegeben' in titles(sv.model)
    assert sv.model.total == len(j)


def test_no_change_touches_nothing(make):
    fc, w = make('B1tr')
    ev = watch(w.status_view.model)
    w.refresh()
    w.refresh()
    assert ev == {'reset': 0, 'insert': 0, 'remove': 0, 'changed': 0}


def test_front_insert_without_reset(make):
    fc, w = make('B1tr')
    ev = watch(w.status_view.model)
    j = tuple(fc.context().journal)
    push(fc, w, (J('15:00:00', 'Vorn'),) + j)
    assert ev['reset'] == 0 and ev['insert'] >= 1
    assert titles(w.status_view.model)[1] == 'Vorn'


def test_truncation_at_the_end(make):
    fc, w = make('B1')
    sv = w.status_view
    push(fc, w, entries(30))
    assert sv.model.total == 30
    ev = watch(sv.model)
    push(fc, w, entries(30, start=1))             # ein neuer vorn, ältester fällt hinten heraus
    assert ev['reset'] == 0 and sv.model.total == 30
    assert titles(sv.model)[1] == 'Eintrag 30' and 'Eintrag 0' not in titles(sv.model)


def test_day_headers(make):
    fc, w = make('B1')
    sv = w.status_view
    push(fc, w, (J('09:00', 'a'), J('08:00', 'b'), J('23:00', 'c', day='Gestern'), J('22:00', 'd', day='Gestern')))
    assert titles(sv.model) == ['Heute', 'a', 'b', 'Gestern', 'c', 'd']
    push(fc, w, (J('09:30', 'n'), J('09:00', 'a'), J('08:00', 'b'), J('23:00', 'c', day='Gestern'),
                 J('22:00', 'd', day='Gestern')))
    assert titles(sv.model) == ['Heute', 'n', 'a', 'b', 'Gestern', 'c', 'd']
    push(fc, w, (J('09:30', 'n'), J('09:00', 'a')))
    assert titles(sv.model) == ['Heute', 'n', 'a']


def test_fault_filter_gets_new_faults_and_counter(make):
    fc, w = make('B1')
    sv = w.status_view
    push(fc, w, (J('10:00', 'ok'),))
    assert sv.seg_faults.text() == 'Störungen'
    sv.seg_faults.click()
    assert sv.empty_label.text() == texts.NO_FAULTS and sv.model.rowCount() == 0
    push(fc, w, (J('10:05', 'kaputt', tone='err', fault=True), J('10:00', 'ok')))
    assert sv.seg_faults.isChecked() and sv.model.only_faults
    assert titles(sv.model) == ['Heute', 'kaputt'] and not sv.empty_frame.isVisible()
    assert sv.seg_faults.text() == 'Störungen 1'
    push(fc, w, (J('10:06', 'noch eins', tone='err', fault=True), J('10:05', 'kaputt', tone='err', fault=True),
                 J('10:00', 'ok')))
    assert sv.seg_faults.text() == 'Störungen 2' and sv.model.rowCount() == 3
    sv.seg_all.click()
    assert sv.model.rowCount() == 1 + 3 and sv.count_label.text().startswith('3 Einträge')


def test_empty_state_texts(make):
    fc, w = make('B1')
    sv = w.status_view
    push(fc, w, ())
    assert sv.empty_label.text() == texts.NO_EVENTS and sv.empty_frame.isVisible()
    push(fc, w, (J('10:00', 'ok'),))
    assert not sv.empty_frame.isVisible() and sv.journal.isVisible()


def test_pi_change_resets_to_top(make):
    fc, w = make('B1')
    sv = w.status_view
    push(fc, w, entries(60))
    sv.journal.verticalScrollBar().setValue(sv.journal.verticalScrollBar().maximum())
    fc.set(context=replace(fc.context(), pi_name='Anderer Pi', journal=entries(3)))
    w.refresh()
    assert sv.model.total == 3 and sv.journal.verticalScrollBar().value() == 0


def test_scroll_position_stays_when_reading_further_down(make):
    fc, w = make('B1')
    sv = w.status_view
    push(fc, w, entries(80))
    QApplication.processEvents()
    j = sv.journal
    bar = j.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    QApplication.processEvents()
    top = j.indexAt(QPoint(4, 1))
    before = top.data()
    off = j.visualRect(top).top()
    for k in range(3):                       # neue Einträge vorn
        push(fc, w, entries(3, start=80 + k * 3) + entries(80))
    QApplication.processEvents()
    top2 = j.indexAt(QPoint(4, 1))
    assert top2.data() == before and abs(j.visualRect(top2).top() - off) <= 1


def test_at_top_new_row_is_visible(make):
    fc, w = make('B1')
    sv = w.status_view
    push(fc, w, entries(80))
    QApplication.processEvents()
    assert sv.journal.verticalScrollBar().value() == 0
    push(fc, w, (J('11:00', 'Ganz neu'),) + entries(80))
    QApplication.processEvents()
    assert sv.journal.verticalScrollBar().value() == 0
    assert sv.journal.visualRect(sv.model.index(1)).top() >= 0
