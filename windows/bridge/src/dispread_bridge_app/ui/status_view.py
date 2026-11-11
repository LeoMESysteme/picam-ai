"""Betriebsansicht: Zustand oben, Journal darunter."""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListView,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
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
    IconButton,
    IndeterminateBar,
    InfoBar,
    StateIcon,
    paint_focus,
    toolbar_frame,
)


def _fit_words(label: QLabel, raw: str, avail: int) -> None:
    """Weiche Trennstellen nur, wenn ein Wort sonst nicht in die Kachel passt (schmal, große Schrift)."""
    fm = QFontMetrics(label.font())
    too_long = any(fm.horizontalAdvance(tok) > avail for tok in raw.split())
    text = texts.hyphenate(raw) if too_long else raw
    if label.text() != text:
        label.setText(text)


class Chip(FocusToolButton):
    """Prüfpunkt-Kachel: Komponenten-Symbol, Name, Info-Symbol (Erklärung), Statussymbol + Wort, Zweitzeile.

    Ein Klick öffnet das Detailfenster; Zustandswechsel werden ohne Farbblitz sofort gezeigt.
    Symbol, Name und Info-Symbol stehen in einer Zeile; nur wenn ein Name dort nicht passt, stehen die
    Namen aller Kacheln in eigener Zeile."""
    PAD_L, PAD_R, GAP_NAME, GAP_INFO = 6, 4, 4, 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('chip', True)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(self.PAD_L, 6, self.PAD_R, 8)
        lay.setSpacing(3)
        self.top = QHBoxLayout()
        self.top.setSpacing(0)
        self.comp_icon = QLabel()
        self.comp_icon.setFixedSize(16, 16)
        self.name = theme.set_typo(QLabel(), 'caption')
        self.info_icon = QLabel()
        self.info_icon.setObjectName('chip_info')
        self.info_icon.setFixedSize(16, 16)
        self.info_icon.setPixmap(theme.icon_pixmap('info', 'text2', 16))
        self.info_icon.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.top.addWidget(self.comp_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self.top.addSpacing(self.GAP_NAME)
        self.top.addWidget(self.name, 1, Qt.AlignmentFlag.AlignVCenter)
        self.top.addSpacing(self.GAP_INFO)
        self.top.addWidget(self.info_icon, 0, Qt.AlignmentFlag.AlignTop)
        self.name_row = QHBoxLayout()           # schmale Kachel: Name in eigener Zeile
        self.name_row.setSpacing(0)
        row = QHBoxLayout()
        row.setSpacing(4)
        self.state_icon = StateIcon(size=16)
        self.word = theme.set_typo(QLabel(), 'caption_strong')
        self.word.setWordWrap(True)
        row.addWidget(self.state_icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.word, 1)
        self.sub = theme.set_typo(QLabel(), 'caption')
        self.sub.setWordWrap(True)
        lay.addLayout(self.top)
        lay.addLayout(self.name_row)
        lay.addLayout(row)
        lay.addWidget(self.sub)
        lay.addStretch(1)
        for w in (self.comp_icon, self.name, self.word, self.sub, self.state_icon):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Das Info-Symbol bleibt für den Mauszeiger erreichbar (Tooltip); Klicks reicht QLabel an die Kachel weiter.
        self.view: texts.ChipView | None = None
        self._inline = True
        self._spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_view(self, v: texts.ChipView) -> None:
        prev = self.view
        if v == prev:
            return
        self.view = v
        if prev is None or prev.key != v.key:
            self.comp_icon.setPixmap(theme.icon_pixmap(texts.CHIP_ICON.get(v.key, 'info'), 'text2', 16))
        self.name.setText(v.name)
        self.state_icon.set_tone(v.tone)
        self.word.setText(v.word)
        self.sub.setText(v.sub)
        self.sub.setVisible(bool(v.sub))
        help_text = texts.CHIP_HELP.get(v.key, '')
        self.info_icon.setToolTip(help_text)
        self.info_icon.setAccessibleName(f'Erklärung {v.name}')
        self.info_icon.setVisible(bool(help_text))
        self.setToolTip(f'{v.word}' + (f' – {v.sub}' if v.sub else ''))
        self.setAccessibleName(f'{v.name}: {texts.SCREEN_READER[v.tone]} {v.word}' + (f', {v.sub}' if v.sub else ''))
        self.setAccessibleDescription(help_text)

    def _set_inline(self, inline: bool) -> None:
        if inline == self._inline:
            return
        self._inline = inline
        if inline:
            self.name_row.removeWidget(self.name)
            self.top.removeItem(self._spacer)
            self.top.insertWidget(2, self.name, 1, Qt.AlignmentFlag.AlignVCenter)
        else:
            self.top.removeWidget(self.name)
            self.top.insertItem(2, self._spacer)
            self.name_row.addWidget(self.name, 1)

    def fits_inline(self, width: int) -> bool:
        """Passt der Name neben Komponenten- und Info-Symbol? Sonst steht er in eigener Zeile."""
        return 16 + self.GAP_NAME + self.name.sizeHint().width() + self.GAP_INFO + 16 <= width - self.PAD_L - self.PAD_R

    def needed_height(self, width: int, inline: bool | None = None) -> int:
        inner = width - self.PAD_L - self.PAD_R
        self._set_inline(self.fits_inline(width) if inline is None else inline)
        h = 14 + max(16, self.name.sizeHint().height() if self._inline else 16)
        if not self._inline:
            h += self.name.sizeHint().height() + 3
        _fit_words(self.word, self.view.word if self.view else '', inner - 20)
        _fit_words(self.sub, self.view.sub if self.view else '', inner)
        ww = self.word.heightForWidth(inner - 20)
        h += 3 + max(16, ww if ww > 0 else self.word.sizeHint().height())
        if self.sub.isVisibleTo(self):
            h += 3 + self.sub.heightForWidth(inner)
        return h


class DirectRoute(QFrame):
    """Weg „UART direkt“ als Bild (B-19): USB-Adapter → Wertfeld mit dem Port → GSVmulti. So ist auf einen Blick
    erkennbar, dass GSVmulti den Port direkt liest; die Brücke steht nicht dazwischen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('direct_route')
        self.setProperty('card', True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        self.adapter_icon = QLabel()
        self.adapter_icon.setPixmap(theme.icon_pixmap('usb_stick', 'text', 20))
        self.adapter_state = StateIcon('info', 16)
        self.adapter_word = theme.set_typo(QLabel(), 'caption_strong')
        self.adapter_word.setWordWrap(True)
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(self.adapter_icon, 0, Qt.AlignmentFlag.AlignHCenter)
        left.addWidget(theme.set_typo(QLabel(texts.ROUTE_ADAPTER), 'caption'), 0, Qt.AlignmentFlag.AlignHCenter)
        st = QHBoxLayout()
        st.setSpacing(4)
        st.addStretch(1)
        st.addWidget(self.adapter_state)
        st.addWidget(self.adapter_word)
        st.addStretch(1)
        left.addLayout(st)
        self.port_slot = QWidget()
        self.port_slot.setMinimumWidth(96)
        PortLay = QVBoxLayout(self.port_slot)
        PortLay.setContentsMargins(0, 0, 0, 0)
        self._port_lay = PortLay
        self._port_value = None
        gsv = QVBoxLayout()
        gsv.setSpacing(4)
        gi = QLabel()
        gi.setPixmap(theme.icon_pixmap('data_line', 'text', 20))
        gsv.addWidget(gi, 0, Qt.AlignmentFlag.AlignHCenter)
        gsv.addWidget(theme.set_typo(QLabel(texts.ROUTE_GSV), 'caption'), 0, Qt.AlignmentFlag.AlignHCenter)
        gsv.addWidget(theme.set_typo(QLabel(texts.ROUTE_READS), 'caption_strong'), 0, Qt.AlignmentFlag.AlignHCenter)
        arrows = []
        for _ in range(2):
            a = QLabel()
            a.setPixmap(theme.icon_pixmap('arrow_forward', 'text2', 20))
            arrows.append(a)
        lay.addLayout(left, 1)
        lay.addWidget(arrows[0], 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.port_slot, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(arrows[1], 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(gsv, 1)
        self.setAccessibleName(texts.ROUTE_ACCESSIBLE)

    def set_state(self, port: str | None, present: bool | None) -> None:
        from .widgets import ValueField
        if port != self._port_value:
            self._port_value = port
            while self._port_lay.count():
                it = self._port_lay.takeAt(0)
                if it.widget() is not None:
                    it.widget().deleteLater()
            self.port_field = ValueField('', port or texts.NOT_SET, copyable=bool(port))
            self._port_lay.addWidget(self.port_field)
        tone, word = {True: ('ok', texts.ROUTE_PRESENT), False: ('warn', texts.ROUTE_MISSING)}.get(
            present, ('info', texts.ROUTE_UNKNOWN))
        self.adapter_state.set_tone(tone)
        self.adapter_word.setText(word)
        self.setAccessibleDescription(f'{texts.ROUTE_ADAPTER} {port or ""}: {word} – {texts.ROUTE_GSV} {texts.ROUTE_READS}')


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


class _HeadBody(QWidget):
    """Inhalt des Kopfbereichs. Qt meldet für Layouts mit umbrechenden Texten als Mindesthöhe die Höhe bei der
    kleinsten Breite (Kopfzeile: 100 px statt 73 px bei 416 px). Der Bildlaufbereich nähme die als Mindesthöhe und
    ließe eine Lücke im Kopf. Darum hier die Höhe bei der tatsächlichen Breite."""

    def minimumSizeHint(self):
        lay = self.layout()
        if lay is None:
            return super().minimumSizeHint()
        w = max(self.width(), lay.totalMinimumSize().width())
        h = lay.totalHeightForWidth(w) if lay.hasHeightForWidth() else lay.totalMinimumSize().height()
        return QSize(lay.totalMinimumSize().width(), h)


class _HeadScroll(QScrollArea):
    """Bildlaufbereich für den Kopf (Zustand, Hinweis, Kacheln): will genau seine Inhaltshöhe bei der aktuellen
    Breite, gibt aber nach, damit das Journal darunter seine Mindesthöhe behält. Dann scrollt der Kopf."""

    def sizeHint(self):
        w = self.widget()
        width = max(10, (self.width() or 380) - 2 * self.frameWidth())
        h = 0
        if w is not None and w.layout() is not None:
            lay = w.layout()
            h = lay.totalHeightForWidth(width) if lay.hasHeightForWidth() else lay.totalSizeHint().height()
        return QSize(width, h + 2 * self.frameWidth())

    def minimumSizeHint(self):
        return QSize(0, 72)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if e.size().width() != e.oldSize().width():
            self.updateGeometry()                   # Höhenwunsch hängt von der Breite ab


class StatusView(QWidget):
    action = Signal(str)
    lock_clicked = Signal()
    switch_clicked = Signal()
    chip_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.body_widget = _HeadBody()
        self.body_widget.setObjectName('status_body')
        body = QVBoxLayout(self.body_widget)
        body.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        body.setContentsMargins(12, 12, 12, 4)
        body.setSpacing(12)
        self.header = Header()
        self.header.lock_clicked.connect(self.lock_clicked)
        self.header.switch_clicked.connect(self.switch_clicked)
        self.header.mode_clicked.connect(lambda: self.action.emit('open_modes'))
        body.addWidget(self.header)
        self.infobar = InfoBar()
        self.infobar.action.connect(self.action)
        body.addWidget(self.infobar)
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(8)
        self.chips: list[Chip] = []
        for i in range(6):
            c = Chip()
            c.setObjectName(f'chip{i}')
            grid.addWidget(c, i // 3, i % 3)
            self.chips.append(c)
            c.clicked.connect(lambda _=False, n=i: QTimer.singleShot(0, lambda: self._chip_clicked(n)))
        self.chip_grid = grid
        body.addLayout(grid)
        self.route = DirectRoute()
        self.route.hide()
        body.addWidget(self.route)
        self.journal_box = QWidget()
        self.journal_box.setObjectName('journal_box')
        jl = QVBoxLayout(self.journal_box)
        jl.setContentsMargins(12, 4, 12, 12)
        jl.setSpacing(12)
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
        jl.addLayout(seg_row)
        self.model = JournalModel()
        self.journal = JournalView()
        self.journal.setModel(self.model)
        self.empty_label = QLabel(texts.NO_FAULTS)
        self.empty_label.setProperty('secondary', True)
        self.empty_label.setProperty('caption', True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.empty_label.setContentsMargins(8, 24, 8, 0)
        self.empty_label.setWordWrap(True)
        self.empty_frame = QFrame()                 # leeres Journal: derselbe Kartenrahmen wie das gefüllte
        self.empty_frame.setObjectName('journal_empty')
        self.empty_frame.setProperty('card', True)
        ef = QVBoxLayout(self.empty_frame)
        ef.setContentsMargins(0, 0, 0, 0)
        ef.addWidget(self.empty_label)
        self.empty_frame.setMinimumHeight(150)
        jl.addWidget(self.journal, 1)
        jl.addWidget(self.empty_frame, 1)
        self.empty_frame.hide()
        self.journal.setMinimumHeight(150)
        scroll = _HeadScroll()                      # bei 380x560 passt nicht alles: dann scrollt der Kopfbereich
        scroll.setObjectName('status_scroll')
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.body_widget)
        self.body_widget.installEventFilter(self)
        scroll.installEventFilter(self)
        self.scroll = scroll
        self.busy_bar = IndeterminateBar()          # laufende Aufgabe ohne eigenen Platz (Export, Session)
        self.busy_bar.setObjectName('busy_bar')
        root.addWidget(self.busy_bar)
        root.addWidget(scroll, 0)
        root.addWidget(self.journal_box, 1)
        self.journal_box.setMinimumHeight(150 + 12 + 40 + 16)
        foot, fl = toolbar_frame()
        self.settings_button = IconButton('settings', texts.SETTINGS, name='settings')
        self.export_button = IconButton('document_arrow_down', texts.EXPORT_LOGS, name='export')
        self.details_button = IconButton('info', texts.INFO, name='details')
        self.exit_button = IconButton('power', texts.EXIT_TIP, name='exit_bridge')
        self.version_label = QLabel()
        self.version_label.setObjectName('version')
        theme.set_typo(self.version_label, 'caption')
        self.version_label.setWordWrap(True)
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.version_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        fl.addWidget(self.settings_button)
        fl.addWidget(self.export_button)
        fl.addWidget(self.details_button)
        fl.addSpacing(8)
        fl.addWidget(self.version_label, 1)
        fl.addSpacing(4)
        fl.addWidget(self.exit_button)
        self.channel_label = QLabel()
        self.channel_label.setProperty('strong', True)
        self.channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_label.setWordWrap(True)
        self.channel_label.hide()
        root.addWidget(self.channel_label)
        root.addWidget(foot)
        self.toolbar = foot
        self.settings_button.clicked.connect(lambda: self.action.emit('open_settings'))
        self.export_button.clicked.connect(lambda: self.action.emit('export_diagnostics'))
        self.details_button.clicked.connect(lambda: self.action.emit('details'))
        self.exit_button.clicked.connect(lambda: self.action.emit('exit_bridge'))
        self.open_chip: int | None = None
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
        h = self.header
        return [h.mode_button, h.switch_button, self.lock_button, *self.infobar.buttons, *self.chips, self.seg_all,
                self.seg_faults, self.journal, self.settings_button, self.export_button, self.details_button,
                self.exit_button]

    def update_from(self, readiness, worker, ctx, locked: bool, configured: bool | None = None) -> None:
        self.header.update_from(ctx, texts.headline(readiness, worker, ctx), locked, peer=readiness.peer,
                                badges=texts.header_badges(readiness, ctx))
        self.infobar.set_bar(texts.action_bar(readiness, worker, ctx, configured))
        direct = ctx.route_mode == 'uart_direct'
        for chip, view in zip(self.chips, texts.chips(readiness, worker, ctx), strict=False):
            chip.set_view(view)
            chip.setVisible(not direct)               # UART direkt: die Strecke als Bild statt „nicht benutzt“-Kacheln
        self.route.setVisible(direct)
        if direct:
            self.route.set_state(ctx.adapter_port, ctx.adapter_present)
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
        self.empty_frame.setVisible(empty)
        self.journal.setVisible(not empty)

    def add_entry(self, entry: JournalEntry) -> None:
        self.model.add_first(entry)
        self._update_counts()

    def _filter(self, faults: bool) -> None:
        self.model.set_only_faults(faults)
        self._update_counts()

    def _set_chip_heights(self, w: int) -> None:
        inline = all(c.fits_inline(w) for c in self.chips)
        for row in (self.chips[:3], self.chips[3:]):
            h = max(c.needed_height(w, inline) for c in row)
            for c in row:
                c.setFixedHeight(h)

    def fit_chips(self) -> None:
        """Gleich hohe Kacheln je Reihe; der Name steht in allen sechs gleich (neben dem Symbol oder darunter).

        Zuerst mit der Breite ohne Bildlaufleiste rechnen; nur wenn der Kopf dann nicht in den Bereich passt
        (Leiste nötig), mit der tatsächlichen Breite. So pendelt die Leiste nicht zwischen beiden Zuständen."""
        m = self.body_widget.layout().contentsMargins()
        gaps = 2 * self.chip_grid.horizontalSpacing()
        full = (self.scroll.width() - 2 * self.scroll.frameWidth() - m.left() - m.right() - gaps) // 3
        self._set_chip_heights(max(10, full))
        if self.scroll.sizeHint().height() > self.scroll.height():
            self._set_chip_heights(max(10, min(c.width() for c in self.chips)))
        self.scroll.updateGeometry()

    def eventFilter(self, obj, e):
        if obj in (self.body_widget, self.scroll) and e.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.fit_chips)          # Bildlaufleiste erscheint/verschwindet: neu einpassen
        return super().eventFilter(obj, e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fit_chips()

    def showEvent(self, e):
        super().showEvent(e)
        self.fit_chips()

    def _chip_clicked(self, n: int) -> None:
        """Kachel öffnet das Detailfenster; die gewählte Kachel trägt den Akzentrand, solange es offen ist."""
        self.mark_open_chip(n)
        self.chip_clicked.emit(n)

    def mark_open_chip(self, n: int | None) -> None:
        self.open_chip = n
        for i, c in enumerate(self.chips):
            c.setChecked(i == n)
