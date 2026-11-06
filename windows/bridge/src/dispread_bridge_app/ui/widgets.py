"""Kleine wiederverwendbare Bausteine: Statussymbol, Kopf, InfoBar, Fußleiste."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from . import texts, theme


def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


class StateIcon(QLabel):
    """Symbol der Statusstufe; trägt das Wort als Screenreader-Name."""

    def __init__(self, tone='info', size=16, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.tone = tone
        self.setPixmap(theme.status_pixmap(tone, self._size))
        self.setAccessibleName(texts.SCREEN_READER.get(tone, ''))


class FocusFrame(QWidget):
    """Mixin-artiges Hilfswidget: zeichnet den doppelten Fluent-Fokusrahmen."""


def paint_focus(w: QWidget, painter_target=None) -> None:
    t = theme.tokens()
    p = QPainter(painter_target or w)
    r = w.rect().adjusted(1, 1, -1, -1)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(t['focus_outer']), 2))
    p.drawRoundedRect(r, 4, 4)
    p.setPen(QPen(QColor(t['focus_inner']), 1))
    p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 3, 3)
    p.end()


_KEY_FOCUS = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)


class _FocusMixin:
    """Fokusrahmen nur bei Tastaturfokus (Fluent)."""
    _key_focus = False

    def focusInEvent(self, e):
        self._key_focus = e.reason() in _KEY_FOCUS
        super().focusInEvent(e)
        self.update()

    def focusOutEvent(self, e):
        self._key_focus = False
        super().focusOutEvent(e)
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.hasFocus() and self._key_focus:
            paint_focus(self)


class FocusPushButton(_FocusMixin, QPushButton):
    def keyPressEvent(self, e):
        # Enter löst den fokussierten Knopf aus (Windows-Verhalten), nicht nur die Leertaste
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not e.isAutoRepeat():
            self.click()
            return
        super().keyPressEvent(e)


class FocusToolButton(_FocusMixin, QToolButton):
    pass


def button(label: str, accent=False, parent=None, name='') -> FocusPushButton:
    b = FocusPushButton(label, parent)
    b.setProperty('accent', accent)
    b.setAutoDefault(False)
    if accent:
        b.setDefault(False)
    if name:
        b.setObjectName(name)
    return b


class Header(QWidget):
    """Name · Weg, Zustandssatz, DUT-Sperrzeile, Schloss."""
    lock_clicked = Signal()
    switch_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = QLabel()
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.RichText)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.lock_button = FocusToolButton()
        self.lock_button.setObjectName('lock')
        self.lock_button.setProperty('flat', True)
        self.lock_button.setIcon(theme.glyph_icon('lock'))
        self.lock_button.setAccessibleName(texts.LOCK_TITLE)
        self.lock_button.setToolTip(texts.LOCK_TITLE)
        self.lock_button.clicked.connect(self.lock_clicked)
        self.switch_button = FocusToolButton()
        self.switch_button.setObjectName('switch')
        self.switch_button.setProperty('flat', True)
        self.switch_button.setIcon(theme.glyph_icon('chevron'))
        self.switch_button.setAccessibleName('Pi wechseln')
        self.switch_button.setToolTip('Pi wechseln')
        self.switch_button.clicked.connect(self.switch_clicked)
        top.addWidget(self.title, 1)
        top.addWidget(self.switch_button, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(self.lock_button, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.head_icon = StateIcon()
        self.headline = QLabel()
        self.headline.setWordWrap(True)
        self.headline.setProperty('strong', True)
        self.headline.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        row.addWidget(self.head_icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.headline, 1)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.dut_icon = StateIcon('warn')
        self.dut = QLabel()
        self.dut.setWordWrap(True)
        self.dut.setProperty('caption', True)
        self.dut.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        row2.addWidget(self.dut_icon, 0, Qt.AlignmentFlag.AlignTop)
        row2.addWidget(self.dut, 1)
        lay.addLayout(row2)

    def update_from(self, ctx, headline: texts.Headline, locked: bool, allow_switch=True) -> None:
        name, route = texts.head_title(ctx)
        t = theme.tokens()
        if route:
            html = (f'<span style="font-size:15pt;font-weight:600">{escape(name)}</span>'
                    f' <span style="color:{t["text2"]}">· {escape(route)}</span>')
        else:
            html = f'<span style="font-size:15pt;font-weight:600">{escape(name)}</span>'
        self.title.setText(html)
        self.title.setToolTip(name)
        self.head_icon.set_tone(headline.tone)
        self.headline.setText(headline.text)
        text, tone = texts.dut_line(ctx)
        self.dut.setText(text)
        self.dut_icon.set_tone(tone)
        self.lock_button.setVisible(locked)
        self.switch_button.setVisible(allow_switch and not locked and len(ctx.paired) > 1)


class InfoBar(QFrame):
    action = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('bar', True)
        self.setProperty('kind', 'info')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        self.state_icon = StateIcon()
        lay.addWidget(self.state_icon, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setProperty('strong', True)
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setProperty('secondary', False)
        self.btn_row = QHBoxLayout()
        self.btn_row.setSpacing(8)
        self.btn_row.addStretch(1)
        col.addWidget(self.title_label)
        col.addWidget(self.text_label)
        col.addLayout(self.btn_row)
        lay.addLayout(col, 1)
        # Zwei feste Knöpfe: Wegwerf-Widgets mit Python-Unterklasse stürzen PySide beim Neuzeichnen ab
        self._secondary = button('', name='bar_secondary')
        self._primary = button('', True, name='bar_primary')
        self.btn_row.addWidget(self._secondary)
        self.btn_row.addWidget(self._primary)
        self._aids = ['', '']
        self._secondary.clicked.connect(lambda: self.action.emit(self._aids[0]))
        self._primary.clicked.connect(lambda: self.action.emit(self._aids[1]))
        self.buttons: list[QPushButton] = []
        self.bar: texts.ActionBar | None = None
        self._secondary.hide()
        self._primary.hide()

    @property
    def action_ids(self):
        return self.bar.action_ids if self.bar else ()

    def set_bar(self, bar: texts.ActionBar | None) -> None:
        if bar is not None and bar == self.bar and not self.isHidden():
            return
        self.bar = bar
        self.buttons = []
        self._secondary.hide()
        self._primary.hide()
        if bar is None:
            self.hide()
            return
        self.setProperty('kind', bar.kind)
        repolish(self)
        self.state_icon.set_tone(bar.kind)
        self.title_label.setText(bar.title)
        self.text_label.setText(bar.text)
        self.text_label.setVisible(bool(bar.text))
        slots = {True: self._primary, False: self._secondary}
        for label, aid, primary in bar.buttons:
            b = slots[primary] if (primary or len(bar.buttons) > 1) else self._primary
            b.setText(label)
            self._aids[1 if b is self._primary else 0] = aid
            b.show()
            self.buttons.append(b)
        self.show()


def footer_frame() -> tuple[QFrame, QHBoxLayout]:
    f = QFrame()
    f.setObjectName('footer')
    lay = QHBoxLayout(f)
    lay.setContentsMargins(16, 10, 16, 10)
    lay.setSpacing(8)
    return f, lay
