"""Betriebsansicht: Zustand oben, Journal darunter."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QSizePolicy,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from . import texts, theme
from .port import JournalEntry
from .widgets import (
    FocusPushButton,
    FocusToolButton,
    Header,
    InfoBar,
    StateIcon,
    button,
    footer_frame,
    paint_focus,
)


class Chip(FocusToolButton):
    """Prüfpunkt: Name, Symbol + Statuswort, optionale Unterzeile."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('chip', True)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)
        self.name = QLabel()
        self.name.setProperty('secondary', True)
        self.name.setProperty('caption', True)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.state_icon = StateIcon(size=14)
        self.word = QLabel()
        self.word.setProperty('caption', True)
        self.word.setProperty('strong', True)
        self.word.setWordWrap(True)
        row.addWidget(self.state_icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.word, 1)
        self.sub = QLabel()
        self.sub.setProperty('caption', True)
        self.sub.setProperty('secondary', True)
        self.sub.setWordWrap(True)
        lay.addWidget(self.name)
        lay.addLayout(row)
        lay.addWidget(self.sub)
        lay.addStretch(1)
        for w in (self.name, self.word, self.sub, self.state_icon):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.view: texts.ChipView | None = None

    def set_view(self, v: texts.ChipView) -> None:
        self.view = v
        self.name.setText(v.name)
        self.state_icon.set_tone(v.tone)
        self.word.setText(v.word)
        self.sub.setText(v.sub)
        self.sub.setVisible(bool(v.sub))
        self.setAccessibleName(f'{v.name}: {texts.SCREEN_READER[v.tone]} {v.word}' + (f', {v.sub}' if v.sub else ''))

    def needed_height(self, width: int) -> int:
        inner = width - 16
        h = 12 + self.name.sizeHint().height()
        h += max(self.state_icon.height(), self.word.heightForWidth(inner - 18) if self.word.heightForWidth(inner - 18) > 0
                 else self.word.sizeHint().height()) + 2
        if self.sub.isVisibleTo(self):
            h += self.sub.heightForWidth(inner) + 2
        return h


class Flyout(QFrame):
    closed = Signal()

    def __init__(self, view: texts.ChipView, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setProperty('popup', True)
        self.setObjectName('flyout')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        head = QHBoxLayout()
        t = QLabel(view.name if view.key != 'pi' else 'Pi – technische Werte')
        t.setProperty('strong', True)
        head.addWidget(t, 1)
        self.close_button = button('×', name='flyout_close')
        self.close_button.setAccessibleName('Details schließen')
        self.close_button.setProperty('flat', True)
        self.close_button.clicked.connect(self.close)
        head.addWidget(self.close_button)
        lay.addLayout(head)
        for k, v in view.details:
            kl = QLabel(k)
            kl.setProperty('secondary', True)
            kl.setProperty('caption', True)
            lay.addWidget(kl)
            vl = QLabel(v)
            vl.setWordWrap(True)
            vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if k.startswith('TLS'):
                vl.setFont(theme.make_font(9, mono=True))
                vl.setProperty('mono', True)
            lay.addWidget(vl)
        if view.hint:
            h = QLabel(view.hint)
            h.setWordWrap(True)
            h.setProperty('secondary', True)
            h.setProperty('caption', True)
            lay.addSpacing(4)
            lay.addWidget(h)
        self.setFixedWidth(340)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def hideEvent(self, e):
        super().hideEvent(e)
        self.closed.emit()


class JournalModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self._all: list[JournalEntry] = []
        self._rows: list = []
        self.only_faults = False

    def set_entries(self, entries) -> None:
        self._all = list(entries)
        self._rebuild()

    def add_first(self, entry: JournalEntry) -> None:
        self._all.insert(0, entry)
        self._rebuild()

    def set_only_faults(self, on: bool) -> None:
        self.only_faults = on
        self._rebuild()

    @property
    def total(self) -> int:
        return len(self._all)

    @property
    def fault_count(self) -> int:
        return sum(1 for e in self._all if e.fault)

    def _rebuild(self) -> None:
        self.beginResetModel()
        rows, last = [], None
        for e in self._all:
            if self.only_faults and not e.fault:
                continue
            if e.day != last:
                rows.append(e.day)
                last = e.day
            rows.append(e)
        self._rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return row if isinstance(row, str) else row.title
        if role == Qt.ItemDataRole.UserRole:
            return row
        if role == Qt.ItemDataRole.AccessibleTextRole:
            if isinstance(row, str):
                return row
            return f'{row.time}, {texts.SCREEN_READER.get(row.tone, "")} {row.title}. {row.sub} {row.duration}'
        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled


class JournalDelegate(QStyledItemDelegate):
    TIME_W, ICON_W, PAD = 62, 26, 12

    def _fonts(self):
        return (theme.make_font(9, tabular=True), theme.make_font(10.5), theme.make_font(9),
                theme.make_font(9, theme.QFont.Weight.DemiBold))

    def _layout(self, rect_w, entry):
        ft, fm, fs, fd = self._fonts()
        dur_w = QFontMetrics(fd).horizontalAdvance(entry.duration) + 16 if entry.duration else 0
        text_w = rect_w - 2 * self.PAD - self.TIME_W - self.ICON_W - dur_w
        title_h = QFontMetrics(fm).boundingRect(0, 0, text_w, 1000, Qt.TextFlag.TextWordWrap, entry.title).height()
        sub_h = (QFontMetrics(fs).boundingRect(0, 0, text_w, 1000, Qt.TextFlag.TextWordWrap, entry.sub).height()
                 if entry.sub else 0)
        return text_w, dur_w, title_h, sub_h

    def sizeHint(self, option, index):
        row = index.data(Qt.ItemDataRole.UserRole)
        w = option.rect.width() or 380
        if isinstance(row, str):
            return QSize(w, 30)
        _, _, th, sh = self._layout(w, row)
        return QSize(w, th + sh + 14)

    def paint(self, p: QPainter, option, index):
        row = index.data(Qt.ItemDataRole.UserRole)
        t = theme.tokens()
        r = option.rect
        ft, fm, fs, fd = self._fonts()
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if isinstance(row, str):
            p.setFont(theme.make_font(9, theme.QFont.Weight.DemiBold))
            p.setPen(QColor(t['text2']))
            p.drawText(r.adjusted(self.PAD, 8, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, row)
            p.restore()
            return
        text_w, dur_w, th, sh = self._layout(r.width(), row)
        p.setFont(ft)
        p.setPen(QColor(t['text2']))
        p.drawText(QRect(r.x() + self.PAD, r.y() + 8, self.TIME_W, 18), Qt.AlignmentFlag.AlignLeft, row.time)
        p.drawPixmap(r.x() + self.PAD + self.TIME_W, r.y() + 8, theme.status_pixmap(row.tone, 16))
        x = r.x() + self.PAD + self.TIME_W + self.ICON_W
        p.setFont(fm)
        p.setPen(QColor(t['text']))
        p.drawText(QRect(x, r.y() + 6, text_w, th), Qt.TextFlag.TextWordWrap, row.title)
        if row.sub:
            p.setFont(fs)
            p.setPen(QColor(t['text2']))
            p.drawText(QRect(x, r.y() + 6 + th, text_w, sh), Qt.TextFlag.TextWordWrap, row.sub)
        if row.duration:
            p.setFont(fd)
            p.setPen(QColor(t['text']))
            p.drawText(QRect(r.right() - self.PAD - dur_w, r.y() + 8, dur_w, 18), Qt.AlignmentFlag.AlignRight,
                       row.duration)
        p.setPen(QColor(t['stroke']))
        p.drawLine(r.x() + 1, r.bottom(), r.right() - 1, r.bottom())
        p.restore()


class JournalView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('journal')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setUniformItemSizes(False)
        self.setItemDelegate(JournalDelegate(self))
        self.setAccessibleName('Ereignisjournal')
        self._key_focus = False

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.doItemsLayout()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._key_focus:
            paint_focus(self.viewport())

    def focusInEvent(self, e):
        self._key_focus = e.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason)
        super().focusInEvent(e)
        self.viewport().update()

    def focusOutEvent(self, e):
        self._key_focus = False
        super().focusOutEvent(e)
        self.viewport().update()


class SegButton(FocusPushButton):
    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            sibling = self.property('sibling')
            if sibling is not None:
                sibling.setChecked(True)
                sibling.setFocus(Qt.FocusReason.TabFocusReason)
                return
        super().keyPressEvent(e)


class StatusView(QWidget):
    action = Signal(str)
    lock_clicked = Signal()
    switch_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        body = QVBoxLayout()
        body.setContentsMargins(16, 12, 16, 12)
        body.setSpacing(12)
        self.header = Header()
        self.header.lock_clicked.connect(self.lock_clicked)
        self.header.switch_clicked.connect(self.switch_clicked)
        body.addWidget(self.header)
        self.infobar = InfoBar()
        self.infobar.action.connect(self.action)
        body.addWidget(self.infobar)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        self.chips: list[Chip] = []
        for i in range(6):
            c = Chip()
            c.setObjectName(f'chip{i}')
            grid.addWidget(c, i // 3, i % 3)
            self.chips.append(c)
            c.clicked.connect(lambda _=False, n=i: QTimer.singleShot(0, lambda: self._open_flyout(n)))
        self.chip_grid = grid
        body.addLayout(grid)
        seg_row = QHBoxLayout()
        seg = QFrame()
        seg.setObjectName('segmented')
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(2, 2, 2, 2)
        sl.setSpacing(0)
        self.seg_all, self.seg_faults = SegButton('Alle'), SegButton('Störungen')
        self.seg_all.setObjectName('seg_all')
        self.seg_faults.setObjectName('seg_faults')
        for b in (self.seg_all, self.seg_faults):
            b.setProperty('seg', True)
            b.setCheckable(True)
            sl.addWidget(b)
        self.seg_all.setProperty('sibling', self.seg_faults)
        self.seg_faults.setProperty('sibling', self.seg_all)
        self.seg_all.setChecked(True)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.group.addButton(self.seg_all)
        self.group.addButton(self.seg_faults)
        self.seg_faults.toggled.connect(self._filter)
        self.count_label = QLabel()
        self.count_label.setProperty('secondary', True)
        self.count_label.setProperty('caption', True)
        seg_row.addWidget(seg)
        seg_row.addStretch(1)
        seg_row.addWidget(self.count_label)
        body.addLayout(seg_row)
        self.model = JournalModel()
        self.journal = JournalView()
        self.journal.setModel(self.model)
        self.empty_label = QLabel(texts.NO_FAULTS)
        self.empty_label.setProperty('secondary', True)
        self.empty_label.setProperty('caption', True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.empty_label.setContentsMargins(0, 24, 0, 0)
        self.empty_label.setWordWrap(True)
        body.addWidget(self.journal, 1)
        body.addWidget(self.empty_label, 1)
        self.empty_label.hide()
        root.addLayout(body, 1)
        foot, fl = footer_frame()
        self.export_button = button('Diagnose exportieren', name='export')
        self.details_button = button('Details', name='details')
        self.setup_button = button('Einrichtung', name='setup')
        self.version_label = QLabel()
        self.version_label.setProperty('secondary', True)
        self.version_label.setProperty('caption', True)
        fl.addWidget(self.export_button)
        fl.addWidget(self.details_button)
        fl.addWidget(self.setup_button)
        fl.addStretch(1)
        fl.addWidget(self.version_label)
        self.channel_label = QLabel()
        self.channel_label.setProperty('strong', True)
        self.channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_label.setWordWrap(True)
        self.channel_label.hide()
        root.addWidget(self.channel_label)
        root.addWidget(foot)
        self.export_button.clicked.connect(lambda: self.action.emit('export_diagnostics'))
        self.details_button.clicked.connect(lambda: self.action.emit('details'))
        self.setup_button.clicked.connect(lambda: self.action.emit('resume_setup'))
        self.flyout: Flyout | None = None
        self._pi_name = None
        self.lock_button = self.header.lock_button
        self.dut_label = self.header.dut
        self.headline_label = self.header.headline
        self._set_tab_order()

    @property
    def lock_visible(self) -> bool:
        return self.lock_button.isVisibleTo(self)

    def _set_tab_order(self) -> None:
        seq = self.focus_chain()
        for a, b in zip(seq, seq[1:], strict=False):
            QWidget.setTabOrder(a, b)

    def focus_chain(self) -> list[QWidget]:
        return [self.lock_button, *self.infobar.buttons, *self.chips, self.seg_all, self.seg_faults, self.journal,
                self.export_button, self.details_button]

    def update_from(self, readiness, worker, ctx, locked: bool) -> None:
        self.header.update_from(ctx, texts.headline(readiness, worker, ctx), locked)
        self.infobar.set_bar(texts.action_bar(readiness, worker, ctx))
        for chip, view in zip(self.chips, texts.chips(readiness, worker, ctx), strict=False):
            chip.set_view(view)
        self.version_label.setText(texts.version_label(ctx.version))
        self.channel_label.setText(ctx.channel or '')
        self.channel_label.setVisible(bool(ctx.channel))
        if ctx.pi_name != self._pi_name or self.model.total == 0:
            self.model.set_entries(ctx.journal)
            self._pi_name = ctx.pi_name
        self._update_counts()
        self._set_tab_order()
        self.fit_chips()

    def _update_counts(self) -> None:
        n = self.model.total
        pi = f' · {self._pi_name}' if self._pi_name and self._pi_name != 'Prüfstand 2' else ''
        self.count_label.setText(f'{n} Einträge{pi}')
        empty = self.model.rowCount() == 0
        self.empty_label.setText(texts.NO_FAULTS if self.model.only_faults and self.model.total else texts.NO_EVENTS)
        self.empty_label.setVisible(empty)
        self.journal.setVisible(not empty)

    def add_entry(self, entry: JournalEntry) -> None:
        self.model.add_first(entry)
        self._update_counts()

    def _filter(self, faults: bool) -> None:
        self.model.set_only_faults(faults)
        self._update_counts()

    def fit_chips(self) -> None:
        for row in (self.chips[:3], self.chips[3:]):
            w = max(10, row[0].width())
            h = max(c.needed_height(w) for c in row)
            for c in row:
                c.setFixedHeight(h)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fit_chips()

    def showEvent(self, e):
        super().showEvent(e)
        self.fit_chips()

    def _open_flyout(self, n: int) -> None:
        chip = self.chips[n]
        if self.flyout is not None:
            self.flyout.close()
        if self.flyout is None or not chip.isChecked():
            pass
        if not chip.isChecked():
            return
        for i, c in enumerate(self.chips):
            if i != n:
                c.setChecked(False)
        fly = Flyout(chip.view, self)
        self.flyout = fly
        fly.closed.connect(lambda c=chip: (c.setChecked(False), c.setFocus()))
        pos = chip.mapToGlobal(chip.rect().bottomLeft())
        fly.move(pos.x(), pos.y() + 4)
        fly.show()
        fly.setFocus()
