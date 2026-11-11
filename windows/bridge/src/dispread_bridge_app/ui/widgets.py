"""Wiederverwendbare Bausteine: Statussymbol, Kopf, InfoBar, Fußleiste, Symbolknopf, Wertfeld,
Fortschritt, Herzschlag, Farbblitz und Überblendung (UX2)."""
from __future__ import annotations

import time

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import texts, theme


class InfoIcon(QLabel):
    """ⓘ: die Erklärung steht im Tooltip (Box), nicht im Fließtext. Nur Mauszeiger; für Screenreader als Beschreibung."""

    def __init__(self, tip: str, name: str = 'Erklärung', size: int = 16, parent=None):
        super().__init__(parent)
        self.setObjectName('info_icon')
        self.setFixedSize(size, size)
        self.setPixmap(theme.icon_pixmap('info', 'text2', size))
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.set_tip(tip, name)

    def set_tip(self, tip: str, name: str | None = None) -> None:
        self.setToolTip(tip)
        self.setAccessibleDescription(tip)
        if name:
            self.setAccessibleName(name)
        # Nie ein elternloses Widget zeigen: es würde kurz ein eigenes Fenster (Blitzfenster)
        if not tip:
            self.hide()
        elif self.parent() is not None:
            self.show()


class Badge(QFrame):
    """Abzeichen für eine wiederkehrende Einschränkung („nicht abgenommen“, „Demo“, „Einkanal“ …): Umriss
    ``stroke_strong``, 9-pt-Beschriftung, Radius 4, nie grün. Die Erklärung steht im ⓘ im Abzeichen."""

    def __init__(self, text: str, tip: str = '', parent=None, name: str = ''):
        super().__init__(parent)
        self.setProperty('badgeBox', True)
        self.setObjectName(name or 'badge_box')
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 1, 3 if tip else 6, 1)
        lay.setSpacing(3)
        self.label = QLabel(text)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setProperty('badgeText', True)
        lay.addWidget(self.label)
        self.info = InfoIcon(tip, f'Erklärung {text}', size=14)
        lay.addWidget(self.info)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        if tip:
            self.setToolTip(tip)
        self.setAccessibleName(text)
        self.setAccessibleDescription(tip)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)           # Umriss selbst zeichnen: unabhängig von der Stylesheet-Kaskade des Besitzers
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(theme.tokens()['stroke_strong']), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
        p.end()


def badge_row(*badges: Badge) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    for b in badges:
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
    lay.addStretch(1)
    return w


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

    def keyPressEvent(self, e):
        # Enter löst den fokussierten Knopf aus (Windows-Verhalten), nicht nur die Leertaste; auch Symbolknöpfe,
        # Kacheln und Knöpfe in Werkzeugfenstern (der Dialog-Standardknopf bekommt die Taste dann nicht mehr).
        if (e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not e.isAutoRepeat()
                and isinstance(self, QAbstractButton) and self.isEnabled()):
            e.accept()
            self.click()
            return
        super().keyPressEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.hasFocus() and self._key_focus:
            paint_focus(self)


class FocusPushButton(_FocusMixin, QPushButton):
    pass


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


class ModeButton(FocusToolButton):
    """Moduswahl im Kopf: Symbol des Wegs, Kurzname, Chevron. Öffnet das Moduswahl-Fenster."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('mode_button')
        self.setProperty('mode', True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(6)
        self.way_icon = QLabel()
        self.label = theme.set_typo(QLabel(), 'body')
        self.chevron = QLabel()
        self.chevron.setPixmap(theme.icon_pixmap('chevron_down', 'text2', 16))
        for w in (self.way_icon, self.label, self.chevron):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignVCenter)
        self._view = None

    def set_view(self, name: str, icon: str | None, tip: str) -> None:
        if (name, icon, tip) == self._view:
            return
        self._view = (name, icon, tip)
        self.label.setText(name)
        self.way_icon.setVisible(icon is not None)
        if icon:
            self.way_icon.setPixmap(theme.icon_pixmap(icon, 'text', 20))
        self.setToolTip(tip)
        self.setAccessibleName(f'{name} – Weg wählen' if icon else name)
        self.updateGeometry()

    def sizeHint(self):
        return self.layout().sizeHint()

    def minimumSizeHint(self):
        return self.layout().minimumSize()


class Header(QWidget):
    """Pi-Name · Moduswahl · Schloss; Herzschlag + Zustandssatz; DUT-Sperrzeile (Pflicht)."""
    lock_clicked = Signal()
    switch_clicked = Signal()
    mode_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(4)
        self.title = theme.set_typo(QLabel(), 'title')
        self.title.setWordWrap(True)
        self.title.setTextFormat(Qt.TextFormat.PlainText)
        self.title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.mode_button = ModeButton()
        self.mode_button.clicked.connect(self.mode_clicked)
        self.switch_button = IconButton('arrow_swap', texts.PI_SWITCH_TIP, name='switch')
        self.switch_button.clicked.connect(self.switch_clicked)
        self.lock_button = IconButton('lock_closed', texts.LOCK_TITLE, name='lock')
        self.lock_button.clicked.connect(self.lock_clicked)
        top.addWidget(self.title, 1)
        top.addWidget(self.mode_button, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(self.switch_button, 0, Qt.AlignmentFlag.AlignTop)
        top.addWidget(self.lock_button, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(8)
        line_h = QFontMetrics(theme.typo_font('body_strong')).height()
        self.heartbeat = HeartbeatDot(line_h)
        self.ring = ProgressRing(16)
        self.ring.setAccessibleName(texts.HEARTBEAT_BUSY)
        self.ring.setToolTip(texts.HEARTBEAT_BUSY)
        self.ring.hide()
        self._busy = False
        self.ring.gone.connect(self._sync_beat)
        slot = QWidget()
        slot.setFixedWidth(16)
        sl = QHBoxLayout(slot)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.heartbeat, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        sl.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.pulse_slot = slot
        self.head_icon = StateIcon()                 # nur bei Achtung/Fehler: Word-Beside-Color
        self._icon_fx = QGraphicsOpacityEffect(self.head_icon)    # Herzschlag-Puls auf dem Symbol (Deckkraft)
        self._icon_fx.setOpacity(1.0)
        self.head_icon.setGraphicsEffect(self._icon_fx)
        self._icon_anim = _ease_anim(self, 0.0, 1.0, 250)
        self._icon_anim.valueChanged.connect(lambda v: self._icon_fx.setOpacity(0.35 + 0.65 * float(v)))
        self.icon_pulses = 0
        self.headline = theme.set_typo(QLabel(), 'body_strong')
        self.headline.setWordWrap(True)
        self.headline.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.headline.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        row.addWidget(slot, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.head_icon, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self.headline, 1)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.dut_icon = StateIcon('warn')
        self.dut = QLabel()
        self.dut.setProperty('caption', True)               # Sperrzeile in Textfarbe, nicht sekundär
        self.dut.setWordWrap(True)
        self.dut.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        row2.addWidget(self.dut_icon, 0, Qt.AlignmentFlag.AlignTop)
        row2.addWidget(self.dut, 1)
        self.dut_info = InfoIcon('', 'Erklärung zur Sperrzeile')
        row2.addWidget(self.dut_info, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(row2)
        self.badges = QWidget()
        self.badges_lay = QHBoxLayout(self.badges)
        self.badges_lay.setContentsMargins(0, 0, 0, 0)
        self.badges_lay.setSpacing(6)
        self._badges_key: tuple = ()
        self.badges.hide()
        lay.addWidget(self.badges)
        lay.addStretch(1)      # überzählige Höhe nach unten, nicht zwischen die Zeilen

    def _sync_beat(self) -> None:
        """Punkt erst, wenn der Ring (Mindestanzeigedauer) wirklich weg ist: nie beide übereinander."""
        try:
            self.heartbeat.setVisible(not self._busy and not self.ring.isVisibleTo(self.pulse_slot))
        except RuntimeError:
            pass

    def _pulse_icon(self) -> None:
        self.icon_pulses += 1
        if theme.motion_enabled() and self.head_icon.isVisible():
            self._icon_anim.stop()
            self._icon_anim.start()

    def set_badges(self, items: tuple[tuple[str, str], ...]) -> None:
        """Abzeichen (Einschränkungen) unter der Sperrzeile; Neuaufbau nur bei geänderter Liste."""
        if items == self._badges_key:
            return
        self._badges_key = items
        while self.badges_lay.count():
            it = self.badges_lay.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        for text, tip in items:
            b = Badge(text, tip, name='badge_' + text.replace(' ', '_'))
            self.badges_lay.addWidget(b, 0)
            repolish(b)
        self.badges_lay.addStretch(1)
        self.badges.setVisible(bool(items))

    def update_from(self, ctx, headline: texts.Headline, locked: bool, allow_switch=True, peer: str | None = None,
                    allow_mode=True, badges: tuple = ()) -> None:
        name, _route = texts.head_title(ctx)
        self.title.setText(name)
        self.title.setToolTip(name)
        self.mode_button.set_view(*texts.mode_view(ctx))
        self.mode_button.setVisible(allow_mode)
        busy = peer in ('connecting', 'backoff')
        # Nur der farbige Punkt steht vor dem Zustandssatz (kein zweites Symbol); Ring nur bei Aufbau/Backoff.
        self.head_icon.hide()
        self.pulse_slot.setVisible(True)
        self.heartbeat.set_tone(
            ('err' if headline.tone == 'err' else 'warn' if headline.tone == 'warn' else 'ok')
            if peer == 'authenticated' else 'info')
        self.headline.setText(headline.text)
        self.ring.setVisible(busy)
        tip = texts.HEARTBEAT_RETRY if peer == 'backoff' else texts.HEARTBEAT_BUSY
        self.ring.setToolTip(tip)
        self.ring.setAccessibleName(tip)
        self._busy = busy
        self._sync_beat()
        self.heartbeat.set_contact(peer == 'authenticated', ctx.activity_seq)
        text, tone = texts.dut_line(ctx)
        self.dut.setText(text)
        self.dut_icon.set_tone(tone)
        self.dut_info.set_tip(texts.dut_info(ctx))
        self.set_badges(badges)
        self.lock_button.setVisible(locked)
        self.switch_button.setVisible(allow_switch and not locked and len(ctx.paired) > 1 and ctx.route_mode != 'uart_direct')

class InfoBar(QFrame):
    action = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('bar', True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)   # Knöpfe stapeln statt Breite erzwingen
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
        self.btn_row.setContentsMargins(0, 6, 0, 0)
        col.addWidget(self.title_label)
        col.addWidget(self.text_label)
        self.btn_col = QVBoxLayout()
        self.btn_col.setSpacing(6)
        self.btn_col.setContentsMargins(0, 6, 0, 0)
        col.addLayout(self.btn_row)
        col.addLayout(self.btn_col)
        lay.addLayout(col, 1)
        self._stacked = False
        # Zwei feste Knöpfe: Wegwerf-Widgets mit Python-Unterklasse stürzen PySide beim Neuzeichnen ab
        self._secondary = button('', name='bar_secondary')
        self._primary = button('', True, name='bar_primary')
        self.btn_row.addStretch(1)
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

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._arrange()
        if self.layout() is not None:
            self.layout().invalidate()      # Textumbruch neu rechnen: sonst bleibt die Zeilenzahl der alten Breite stehen
        self._fit_height()

    def _fit_height(self) -> None:
        """Mindesthöhe nach heightForWidth: umbrechender Text darf die Knöpfe nie überdecken."""
        lay = self.layout()
        h = lay.totalHeightForWidth(self.width()) if lay is not None else 0
        if h > 0 and h != self.minimumHeight():
            self.setMinimumHeight(h)

    def _arrange(self) -> None:
        """Passen die Knöpfe nicht nebeneinander, werden sie untereinander gestapelt (380 px)."""
        shown = [b for b in (self._secondary, self._primary) if not b.isHidden()]
        need = sum(b.sizeHint().width() for b in shown) + 8 * max(0, len(shown) - 1)
        avail = self.width() - 24 - 10 - 16 - 2
        stack = len(shown) > 1 and need > avail
        if stack == self._stacked:
            return
        self._stacked = stack
        for b in (self._secondary, self._primary):
            self.btn_row.removeWidget(b)
            self.btn_col.removeWidget(b)
        if stack:
            for b in (self._primary, self._secondary):         # Hauptaktion oben
                self.btn_col.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
        else:
            self.btn_row.addWidget(self._secondary)
            self.btn_row.addWidget(self._primary)

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
        top = 6 if self.buttons else 0
        self.btn_row.setContentsMargins(0, top, 0, 0)
        self.btn_col.setContentsMargins(0, top, 0, 0)
        self.setMinimumHeight(0)
        if self.parent() is not None:
            self.show()          # elternlos nie zeigen (Blitzfenster); beim Einhängen wird sie sichtbar
        self._arrange()
        self._fit_height()


def footer_frame() -> tuple[QFrame, QHBoxLayout]:
    f = QFrame()
    f.setObjectName('footer')
    lay = QHBoxLayout(f)
    lay.setContentsMargins(16, 10, 16, 10)
    lay.setSpacing(8)
    return f, lay


def footer_frame2() -> tuple[QFrame, QHBoxLayout, QHBoxLayout]:
    """Fuß mit zwei Zeilen: Aktionen oben, Version/„Beenden …“ unten (passt in 380 px)."""
    f = QFrame()
    f.setObjectName('footer')
    outer = QVBoxLayout(f)
    outer.setContentsMargins(16, 10, 16, 8)
    outer.setSpacing(6)
    row1, row2 = QHBoxLayout(), QHBoxLayout()
    row1.setSpacing(8)
    row2.setSpacing(8)
    outer.addLayout(row1)
    outer.addLayout(row2)
    return f, row1, row2


# ================================================================ UX2-Bausteine
class IconButton(FocusToolButton):
    """Flacher Symbolknopf 32 × 32. Tooltip und Screenreader-Name sind Pflicht."""

    def __init__(self, icon_name: str, tooltip: str, parent=None, name='', color_key='text', icon_size=20):
        super().__init__(parent)
        if not tooltip:
            raise ValueError('IconButton braucht einen Tooltip (Screenreader-Name)')
        self.setProperty('flat', True)
        self.setFixedSize(32, 32)
        self.setIconSize(QSize(icon_size, icon_size))
        self._icon_size = icon_size
        self.set_icon(icon_name, color_key)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if name:
            self.setObjectName(name)

    def set_icon(self, icon_name: str, color_key: str = 'text') -> None:
        self.icon_name, self.color_key = icon_name, color_key
        self.setIcon(theme.icon(icon_name, color_key, self._icon_size))


def _ease_anim(parent, start, end, ms: int) -> QVariantAnimation:
    a = QVariantAnimation(parent)
    a.setStartValue(start)
    a.setEndValue(end)
    a.setDuration(ms)
    a.setEasingCurve(QEasingCurve.Type.OutCubic)
    return a


def pop_icon(button: QAbstractButton, size: int) -> None:
    """Symbolwechsel mit 150 ms Skalierung (nur mit Bewegung; sonst sofort Endzustand)."""
    if not theme.motion_enabled() or not button.isVisible():
        button.setIconSize(QSize(size, size))
        return
    a = _ease_anim(button, max(8, size - 6), size, 150)
    a.valueChanged.connect(lambda v: button.setIconSize(QSize(int(v), int(v))))
    a.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def _breakable(text: str) -> str:
    """Pfade und lange Kennungen dürfen an Trennern umbrechen (Anzeige; kopiert wird der Rohwert)."""
    out = []
    for ch in text:
        out.append(ch)
        if ch in '\\/_.-:':
            out.append('​')
    return ''.join(out)


def format_fingerprint(fp: str) -> str:
    """Vierergruppen, vier Gruppen je Zeile, nie gekürzt."""
    groups = fp.split()
    if len(groups) < 5:
        return fp
    return '\n'.join(' '.join(groups[i:i + 4]) for i in range(0, len(groups), 4))


class ValueField(QFrame):
    """Wertfeld (R3-1): jeder veränderliche Wert steht in einem grauen Feld, damit man sieht, dass er sich
    ändern kann und kein fester Text ist (COM-Port, Pfad, Baudrate, Frequenz, Pi-ID, Endpunkt, Fingerabdruck …).

    Grund ``field`` (hell ``mica2``, dunkel ``ctrl``), Radius 4, Polster 3/8, Cascadia Mono 9 pt. Der Bezeichner
    steht darüber oder (``inline``) davor in ``text2``. Kopieren: Klick auf das Feld oder das Kopiersymbol, das
    bei Hover/Fokus rechts erscheint; danach 1,2 s ein Häkchen."""
    copied = Signal(str)
    CONFIRM_MS = 1200

    def __init__(self, label: str, value: str, parent=None, display: str | None = None, copyable=True,
                 mono=True, inline=False, label_width: int = 0):
        super().__init__(parent)
        self.value = value
        self.setObjectName('copy_field')
        self.setProperty('valueFieldRow', True)
        self._copyable = bool(copyable and value not in texts.EMPTY_VALUES)
        outer = QVBoxLayout(self) if not inline else QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2 if not inline else 8)
        self.name_label = theme.set_typo(QLabel(label), 'caption')
        self.name_label.setWordWrap(True)
        self.name_label.setTextFormat(Qt.TextFormat.PlainText)
        if inline:
            self.name_label.setSizePolicy(QSizePolicy.Policy.Fixed if label_width else QSizePolicy.Policy.Minimum,
                                          QSizePolicy.Policy.Preferred)
            if label_width:
                self.name_label.setFixedWidth(label_width)
        # --- das Feld selbst
        self.box = _ValueBox(self)
        bl = QHBoxLayout(self.box)
        bl.setContentsMargins(8, 3, 4, 3)
        bl.setSpacing(4)
        self.value_label = QLabel(display if display is not None else _breakable(value))
        theme.set_typo(self.value_label, 'data' if mono else 'body')
        self.value_label.setWordWrap(True)
        self.value_label.setTextFormat(Qt.TextFormat.PlainText)
        self.value_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.value_label.setAccessibleName(f'{label}: {value}')
        self.value_label.setProperty('empty', value in texts.EMPTY_VALUES)
        bl.addWidget(self.value_label, 1, Qt.AlignmentFlag.AlignVCenter)
        self.copy_button = IconButton('copy', f'{label} {texts.COPY_TIP.lower()}', parent=self.box, name='copy',
                                      color_key='text2', icon_size=16)
        self.copy_button.setFixedSize(22, 22)
        self.copy_button.setToolTip(texts.COPY_TIP)
        self.copy_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)        # das Feld selbst nimmt den Fokus
        self.copy_button.clicked.connect(self.copy)
        if not self._copyable:
            self.copy_button.hide()
        bl.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignTop)
        self.box.setProperty('copyable', self._copyable)
        if self._copyable:
            self.box.setCursor(Qt.CursorShape.PointingHandCursor)
            self.box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.box.setToolTip(texts.COPY_TIP)
            self.box.clicked.connect(self.copy)
            self.box.setAccessibleName(f'{label}: {value} – {texts.COPY_TIP}')
        self._reset = QTimer(self)
        self._reset.setSingleShot(True)
        self._reset.setInterval(self.CONFIRM_MS)
        self._reset.timeout.connect(self._restore)
        self._idle_icon(False)
        self.box.hover_changed.connect(self._idle_icon)
        if inline:
            outer.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignTop)
            outer.addWidget(self.box, 1)
        else:
            outer.addWidget(self.name_label)
            outer.addWidget(self.box)
        self.name_label.setVisible(bool(label))

    def _idle_icon(self, active: bool) -> None:
        """Kopiersymbol nur bei Hover/Fokus sichtbar (Platz bleibt reserviert, der Text springt nicht)."""
        if self._reset.isActive():
            return
        self.copy_button.setIcon(theme.icon('copy', 'text2', 16) if active else QIcon())

    @property
    def confirming(self) -> bool:
        return self._reset.isActive()

    def copy(self) -> None:
        if not self._copyable:
            return
        QGuiApplication.clipboard().setText(self.value)
        self.copy_button.set_icon('checkmark', 'ok')
        self.copy_button.setToolTip(texts.COPIED)
        self.copy_button.setAccessibleName(texts.COPIED)
        self._reset.start()        # nur Symbolwechsel: sicher sichtbar, ohne Skalierungsanimation
        self.copied.emit(self.value)

    def _restore(self) -> None:
        self.copy_button.set_icon('copy', 'text2')
        self.copy_button.setToolTip(texts.COPY_TIP)
        self.copy_button.setAccessibleName(f'{self.name_label.text()} {texts.COPY_TIP.lower()}')
        self._idle_icon(self.box.underMouse() or self.box.hasFocus())


class _ValueBox(_FocusMixin, QFrame):
    """Die graue Fläche des Wertfelds; kopierbar = klickbar und per Tastatur erreichbar (Enter/Leertaste)."""
    clicked = Signal()
    hover_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty('valueField', True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def enterEvent(self, e):
        super().enterEvent(e)
        self.hover_changed.emit(True)

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.hover_changed.emit(self.hasFocus())

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.hover_changed.emit(True)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.hover_changed.emit(self.underMouse())

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.property('copyable') and self.rect().contains(e.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space) and self.property('copyable'):
            e.accept()
            self.clicked.emit()
            return
        super().keyPressEvent(e)


class ProgressRing(QWidget):
    """Unbestimmter Fortschrittsring (16/20 px, Akzent). Läuft nur sichtbar und mit Bewegung.

    Mindestanzeigedauer 400 ms (mit Bewegung): ein Ring, der nach 50 ms wieder verschwindet, wirkt wie ein
    Flackern. ``setVisible(False)`` wird dann bis zum Ablauf der Mindestdauer aufgeschoben."""
    MIN_MS = 400
    gone = Signal()                 # tatsächlich ausgeblendet (nach der Mindestdauer)

    def __init__(self, size: int = 16, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0.0
        self._shown_at = 0.0
        self._pending_hide = QTimer(self)
        self._pending_hide.setSingleShot(True)
        self._pending_hide.timeout.connect(lambda: QWidget.setVisible(self, False))
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(360.0)
        self._anim.setDuration(1000)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._turn)
        self.setAccessibleName('Wird ausgeführt')

    @property
    def running(self) -> bool:
        return self._anim.state() == QAbstractAnimation.State.Running

    def _turn(self, v) -> None:
        self._angle = float(v)
        self.update()

    def setVisible(self, visible: bool) -> None:
        if visible:
            self._pending_hide.stop()
            if self.isHidden():
                self._shown_at = time.monotonic()
            super().setVisible(True)
            return
        if self.isHidden():
            return
        left = self.MIN_MS / 1000 - (time.monotonic() - self._shown_at)
        if theme.motion_enabled() and left > 0 and not self._pending_hide.isActive():
            self._pending_hide.start(int(left * 1000) + 1)       # Mindestanzeigedauer abwarten
            return
        if not self._pending_hide.isActive():
            super().setVisible(False)

    def showEvent(self, e):
        super().showEvent(e)
        if self._shown_at == 0.0:
            self._shown_at = time.monotonic()
        if theme.motion_enabled():
            self._anim.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._anim.stop()
        self.gone.emit()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = max(1.5, self.width() / 8)
        r = QRectF(w / 2, w / 2, self.width() - w, self.height() - w)
        track = QColor(theme.tokens()['stroke'])
        p.setPen(QPen(track, w))
        p.drawEllipse(r)
        pen = QPen(QColor(theme.tokens()['accent']), w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, int((90 - self._angle) * 16), int(-100 * 16))
        p.end()


class IndeterminateBar(QWidget):
    """2-px-Ladebalken für laufende Aufgaben ohne eigenen Platz. Nur sichtbar, solange gearbeitet wird."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._pos = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(-0.3)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1200)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._move)
        self._jobs = 0
        self.setAccessibleName('Wird ausgeführt')
        self.hide()

    @property
    def busy(self) -> bool:
        return self._jobs > 0

    def begin(self) -> None:
        self._jobs += 1
        self.show()

    def end(self) -> None:
        self._jobs = max(0, self._jobs - 1)
        if not self._jobs:
            self.hide()

    def _move(self, v) -> None:
        self._pos = float(v)
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        if theme.motion_enabled():
            self._anim.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._anim.stop()

    def paintEvent(self, e):
        p = QPainter(self)
        acc = QColor(theme.tokens()['accent'])
        if not self.running_animation:
            p.fillRect(self.rect(), acc)          # ohne Bewegung: ruhiger, voller Balken
        else:
            x = int(self._pos * self.width())
            p.fillRect(x, 0, int(0.3 * self.width()), self.height(), acc)
        p.end()

    @property
    def running_animation(self) -> bool:
        return self._anim.state() == QAbstractAnimation.State.Running


class HeartbeatDot(QWidget):
    """8-px-Punkt vor dem Zustandssatz: trägt den Zustand der Pi-Verbindung (grün nur bei authentifizierter Verbindung
    ohne Störung, gelb Achtung, rot Fehler); sagt nichts über Weitergabe oder Empfang.

    Gefüllt = Kontakt, hohl (stroke_strong) = kein Kontakt. Ein neues ``activity_seq`` löst einen
    kurzen Puls aus (250 ms, ease-out), nur mit Bewegung."""
    DOT = 8

    def __init__(self, height: int = 20, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, max(16, height))
        self.contact = False
        self.tone = 'info'
        self.seq: int | None = None
        self.pulses = 0
        self._t = 1.0
        self._anim = _ease_anim(self, 0.0, 1.0, 250)
        self._anim.valueChanged.connect(self._step)
        self._apply_text()

    def _apply_text(self) -> None:
        tip = texts.HEARTBEAT_ALIVE if self.contact else texts.HEARTBEAT_IDLE
        self.setToolTip(tip)
        self.setAccessibleName(tip)

    def _step(self, v) -> None:
        self._t = float(v)
        self.update()

    def set_tone(self, tone: str) -> None:
        """Zustand der Pi-Verbindung: ok (belegt verbunden, keine Störung), warn, err; ``info`` = neutral."""
        if tone != self.tone:
            self.tone = tone
            self.update()

    def set_contact(self, contact: bool, seq: int) -> None:
        if contact != self.contact:
            self.contact = contact
            self._apply_text()
            self.update()
        if self.seq is not None and seq != self.seq and contact:
            self.pulse()
        self.seq = seq

    def pulse(self) -> None:
        self.pulses += 1
        if theme.motion_enabled() and self.isVisible():
            self._anim.stop()
            self._anim.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._anim.stop()
        self._t = 1.0

    def paintEvent(self, e):
        t = theme.tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = self.DOT / 2
        if self.contact:
            col = QColor(t[self.tone] if self.tone in ('ok', 'warn', 'err') else t['text2'])
            if self._anim.state() == QAbstractAnimation.State.Running:
                halo = QColor(col)
                halo.setAlphaF(0.45 * (1 - self._t))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(halo)
                p.drawEllipse(c, r + 4 * self._t, r + 4 * self._t)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawEllipse(c, r, r)
        else:
            p.setPen(QPen(QColor(t['stroke_strong']), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, r - 0.6, r - 0.6)
        p.end()


def toolbar_frame() -> tuple[QFrame, QHBoxLayout]:
    """Symbolleiste am Fuß der Betriebsansicht."""
    f = QFrame()
    f.setObjectName('toolbar')
    lay = QHBoxLayout(f)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(4)
    return f, lay


# ================================================================ UX2 Runde 2: Prüfen, Gespeichert, Schrittwechsel
def _alive(obj) -> bool:
    try:
        import shiboken6
        return shiboken6.isValid(obj)
    except Exception:          # pragma: no cover - shiboken fehlt nie unter PySide6
        return True


def pop_label(lab: QLabel, name: str, color_key: str, size: int) -> None:
    """Symbol in einem QLabel mit 150 ms Skalierung setzen (ohne Bewegung: sofort)."""
    if not theme.motion_enabled() or not lab.isVisible():
        lab.setPixmap(theme.icon_pixmap(name, color_key, size))
        return
    a = _ease_anim(lab, max(8, size - 6), size, 150)
    a.valueChanged.connect(lambda v: lab.setPixmap(theme.icon_pixmap(name, color_key, int(v))))
    a.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)


def run_now(fn, args, done) -> None:
    """Standard-Ausführer ohne Thread-Pool (Bausteintests). Das Hauptfenster setzt seinen Pool ein."""
    try:
        result, exc = fn(*args), None
    except Exception as e:  # noqa: BLE001 - Text nie anzeigen, nur „Prüfung nicht möglich“
        result, exc = None, e
    done(result, exc)


class ValidatedField(QWidget):
    """Eingabe oder Auswahl mit Statusfläche rechts und Meldungszeile darunter (UX2).

    ``check(value)`` ist eine echte, blockierende Prüfung des Controllers (``check_*``); sie läuft über
    ``runner(fn, args, done)`` im Thread-Pool. Getippt wird 500 ms nach der letzten Eingabe geprüft, eine
    Auswahl sofort. Jede Änderung verwirft das alte Ergebnis (Sequenznummer): ``ok`` erscheint nur nach
    einer bestandenen Prüfung genau des angezeigten Werts. Leer = kein Status.
    """
    result_changed = Signal(object)          # CheckResult | None
    DEBOUNCE_MS = 500
    STATES = ('idle', 'pending', 'checking', 'ok', 'warn', 'err')

    def __init__(self, editor: QWidget, check, value=None, runner=None, label: str = '', debounce_ms=None,
                 parent=None, name: str = '', label_role: str = 'body_strong', label_tip: str = ''):
        super().__init__(parent)
        if name:
            self.setObjectName(name)
        self.editor, self.check = editor, check
        self.runner = runner or run_now
        self._value = value
        self.state, self.result, self.checked_value = 'idle', None, None
        self.seq = 0
        self.dropped = 0                       # verworfene, veraltete Ergebnisse (Test/Diagnose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        if label:
            self.label = theme.set_typo(QLabel(label), label_role)
            self.label.setWordWrap(True)
            lrow = QHBoxLayout()
            lrow.setSpacing(6)
            lrow.addWidget(self.label, 0)
            if label_tip:
                lrow.addWidget(InfoIcon(label_tip, f'Erklärung {label}'), 0, Qt.AlignmentFlag.AlignVCenter)
            lrow.addStretch(1)
            lay.addLayout(lrow)
        else:
            self.label = None
        lay.addWidget(editor)
        # Zustand über Form (R3-4): Feldrand in Statusfarbe; das Symbol steht VOR der einzeiligen Meldung darunter
        self.msg_row = QWidget()
        mr = QHBoxLayout(self.msg_row)
        mr.setContentsMargins(0, 0, 0, 0)
        mr.setSpacing(6)
        self.ring = ProgressRing(16)
        self.ring.setAccessibleName(texts.CHECKING)
        self.ring.hide()
        self.ring.gone.connect(lambda: self._sync_icon())
        self.icon = QLabel()
        self.icon.setFixedSize(16, 16)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.hide()
        slot = QWidget()
        slot.setFixedSize(16, 16)
        sl = QHBoxLayout(slot)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignCenter)
        self.status_slot = slot
        self.message = theme.set_typo(QLabel(), 'caption_strong')
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.detail_icon = InfoIcon('', 'Erklärung zur Meldung')     # Erklärung/Abhilfe im ⓘ statt als zweite Zeile
        mr.addWidget(slot, 0, Qt.AlignmentFlag.AlignTop)
        mr.addWidget(self.message, 1)
        mr.addWidget(self.detail_icon, 0, Qt.AlignmentFlag.AlignTop)
        self.msg_row.hide()
        lay.addWidget(self.msg_row)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start)
        self.debounce_ms = self.DEBOUNCE_MS if debounce_ms is None else debounce_ms
        from PySide6.QtWidgets import QComboBox, QLineEdit
        if isinstance(editor, QLineEdit):
            editor.textChanged.connect(lambda _t: self.schedule())
        elif isinstance(editor, QComboBox):
            editor.currentIndexChanged.connect(lambda _i: self.schedule(immediate=True))

    # --- Wert
    def value(self):
        if self._value is not None:
            return self._value() if callable(self._value) else self._value
        from PySide6.QtWidgets import QComboBox, QLineEdit
        if isinstance(self.editor, QLineEdit):
            return self.editor.text().strip()
        if isinstance(self.editor, QComboBox):
            data = self.editor.currentData()
            return data if data is not None else (self.editor.currentText() if self.editor.currentIndex() > 0
                                                  else None)
        return None

    def set_value(self, value) -> None:
        """Fester Wert (z. B. gewählter Adapter aus dem Kontext): bei Änderung sofort prüfen."""
        if value == (self._value() if callable(self._value) else self._value) and self.state != 'idle':
            return
        self._value = value
        self.schedule(immediate=True)

    @property
    def ok(self) -> bool:
        return self.state == 'ok' and self.checked_value == self.value()

    @property
    def accepted(self) -> bool:
        """ok oder warn – geprüft und (mit Vorbehalt) angenommen."""
        return self.state in ('ok', 'warn') and self.checked_value == self.value()

    # --- Ablauf
    def schedule(self, immediate: bool = False) -> None:
        self.seq += 1                          # jedes ausstehende Ergebnis ist ab jetzt veraltet
        self._timer.stop()
        self.result = self.checked_value = None
        v = self.value()
        if v in (None, '', ()):
            self._show('idle')
            return
        if immediate or self.debounce_ms <= 0:
            self._start()
        else:
            self._show('pending')
            self._timer.start(self.debounce_ms)

    def recheck(self) -> None:
        self.schedule(immediate=True)

    def _start(self) -> None:
        v = self.value()
        if v in (None, '', ()):
            self._show('idle')
            return
        seq = self.seq
        self._show('checking')
        args = tuple(v) if isinstance(v, tuple) else (v,)
        self.runner(self.check, args, lambda r, e, s=seq, val=v: self._done(s, val, r, e))

    def _done(self, seq: int, value, result, exc) -> None:
        if not _alive(self):
            return
        if seq != self.seq:
            self.dropped += 1                  # Eingabe hat sich inzwischen geändert: verwerfen
            return
        from .port import CheckResult
        if exc is not None or not isinstance(result, CheckResult) or result.state not in ('ok', 'warn', 'err'):
            result = CheckResult('err', texts.CHECK_FAILED, texts.CHECK_FAILED_DETAIL)
        self.result, self.checked_value = result, value
        self._show(result.state)
        self.result_changed.emit(result)

    def _sync_icon(self) -> None:
        """Ergebnissymbol erst, wenn der Ring (Mindestanzeigedauer) wirklich verschwunden ist: nie beide übereinander."""
        try:
            self.icon.setVisible(self.state in ('ok', 'warn', 'err') and not self.ring.isVisibleTo(self.status_slot))
        except RuntimeError:
            pass

    def _paint_editor(self, state: str) -> None:
        """Rand des Feldes in der Statusfarbe (Eigenschaft ``vstate`` für das QSS), auch bei zusammengesetzten Editoren."""
        from PySide6.QtWidgets import QComboBox, QLineEdit
        value = state if state in ('ok', 'warn', 'err') else ''
        targets = [self.editor] if isinstance(self.editor, (QLineEdit, QComboBox)) else \
            self.editor.findChildren(QComboBox) + self.editor.findChildren(QLineEdit)
        for w in targets:
            if w.property('vstate') != value:
                w.setProperty('vstate', value)
                repolish(w)

    def _show(self, state: str) -> None:
        prev = self.state
        self.state = state
        self.ring.setVisible(state == 'checking')
        self._sync_icon()
        if state == 'ok':
            if prev != 'ok':
                pop_label(self.icon, 'checkmark', 'ok', 16)
            self.icon.setAccessibleName(texts.SCREEN_READER['ok'])
        elif state in ('warn', 'err'):
            self.icon.setPixmap(theme.status_pixmap(state, 16))
            self.icon.setAccessibleName(texts.SCREEN_READER[state])
        r = self.result if state in ('ok', 'warn', 'err') else None
        msg = r.message if r else (texts.CHECKING if state == 'checking' else '')
        detail = r.detail if (r and state in ('warn', 'err')) else ''
        self.message.setText(msg)
        self.message.setProperty('typo', 'caption' if state == 'checking' else 'caption_strong')
        repolish(self.message)
        self.detail_icon.set_tip(detail)
        self.status_slot.setVisible(state in ('checking', 'ok', 'warn', 'err'))
        self.msg_row.setVisible(bool(msg))
        self._paint_editor(state)
        desc = ' '.join(x for x in ((texts.SCREEN_READER.get(state, '') if r else ''), msg, detail) if x)
        self.editor.setAccessibleDescription(desc)
        self.setAccessibleDescription(desc)
        if state in ('idle', 'pending', 'checking'):
            self.result_changed.emit(None)


class SavedNote(QWidget):
    """Kurze Bestätigungszeile „Gespeichert“ mit Häkchen; blendet nach 2 s aus."""
    SHOW_MS = 2000

    def __init__(self, text: str | None = None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.icon = QLabel()
        self.icon.setFixedSize(16, 16)
        self.icon.setAccessibleName(texts.SCREEN_READER['ok'])
        self.label = theme.set_typo(QLabel(text or texts.SAVED), 'caption')
        lay.addWidget(self.icon)
        lay.addWidget(self.label)
        lay.addStretch(1)
        self.shown_count = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade)
        self.hide()

    def flash(self, ms: int | None = None) -> None:
        self.shown_count += 1
        self.setGraphicsEffect(None)
        self.show()
        pop_label(self.icon, 'checkmark', 'ok', 16)
        self._timer.start(self.SHOW_MS if ms is None else ms)

    @property
    def active(self) -> bool:
        return self._timer.isActive()

    def _fade(self) -> None:
        if not theme.motion_enabled():
            self.hide()
            return
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b'opacity', self)
        a.setStartValue(1.0)
        a.setEndValue(0.0)
        a.setDuration(150)                     # Ausgang schneller als Eingang
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(self.hide)
        a.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
