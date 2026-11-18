"""Moduswahl-Fenster (UX2): drei Wege als Karten untereinander, Radio-Semantik, „Wechseln“ im Fuß."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QRadioButton, QVBoxLayout, QWidget

from . import texts, theme
from .port import ModeInfo
from .tool_windows import ToolWindow, label
from .widgets import InfoBar, InfoIcon, ProgressRing, StateIcon, button, repolish


class ModeCard(QFrame):
    """Karte eines Wegs: Name, ein Satz, Status. Die ausführliche Erklärung (mit Baudraten) steht im ⓘ.
    Klick irgendwo auf die Karte wählt sie (wie ihr Auswahlknopf)."""
    disconnect_clicked = Signal()

    def __init__(self, info: ModeInfo, ctx, parent=None):
        super().__init__(parent)
        self.info = info
        self.setObjectName(f'mode_{info.mode}')
        self.setProperty('card', True)
        self.setProperty('selected', False)
        self.setProperty('dimmed', not info.available)
        name, detail = texts.mode_text(info.mode, ctx)
        text = texts.MODE_LINE[info.mode]
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(10)
        self.radio = QRadioButton()
        self.radio.setObjectName(f'radio_{info.mode}')
        self.radio.setEnabled(info.available)
        acc = f'{name}. {info.status}' + (f'. {texts.MODE_ACTIVE}' if info.active else '')
        if not info.available and info.reason:
            acc += f'. Nicht wählbar: {info.reason}'
        self.radio.setAccessibleName(acc)
        self.radio.setAccessibleDescription(f'{text} {detail}')
        lay.addWidget(self.radio, 0, Qt.AlignmentFlag.AlignTop)
        icon = QLabel()
        icon.setFixedSize(20, 20)
        icon.setPixmap(theme.icon_pixmap(texts.MODE_ICON[info.mode], 'text' if info.available else 'text2', 20))
        lay.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.name_label = label(name, 'body_strong')
        head.addWidget(self.name_label, 1)
        self.info_icon = InfoIcon(detail, f'Erklärung {name}')
        head.addWidget(self.info_icon, 0, Qt.AlignmentFlag.AlignTop)
        if info.active:
            badge = QLabel(texts.MODE_ACTIVE)
            badge.setObjectName('badge_active')
            badge.setProperty('badge', True)           # Rand + Text, kein Grün: aktiv heißt nicht belegt
            head.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        col.addLayout(head)
        col.addWidget(label(text, 'caption'))
        st = QHBoxLayout()
        st.setSpacing(6)
        st.addWidget(StateIcon(info.tone, 16), 0, Qt.AlignmentFlag.AlignTop)
        self.status_label = label(info.status, 'caption_strong')
        st.addWidget(self.status_label, 1)
        col.addLayout(st)
        if not info.available and info.reason:
            rr = QHBoxLayout()
            rr.setSpacing(6)
            lock = QLabel()
            lock.setFixedSize(16, 16)
            lock.setPixmap(theme.icon_pixmap('lock_closed', 'text2', 16))
            rr.addWidget(lock, 0, Qt.AlignmentFlag.AlignTop)
            self.reason_label = label(info.reason, 'caption')
            rr.addWidget(self.reason_label, 1)
            self.disconnect_button = button(texts.MODE_DISCONNECT, name=f'mode_disconnect_{info.mode}')
            self.disconnect_button.clicked.connect(self.disconnect_clicked)
            rr.addWidget(self.disconnect_button, 0, Qt.AlignmentFlag.AlignTop)
            col.addLayout(rr)
        else:
            self.reason_label = None
            self.disconnect_button = None
        lay.addLayout(col, 1)
        for w in self.findChildren(QLabel):
            if w is not self.info_icon:                # das ⓘ bleibt für den Mauszeiger erreichbar
                w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_selected(self, on: bool) -> None:
        if self.property('selected') != on:
            self.setProperty('selected', on)
            repolish(self)

    def mousePressEvent(self, e):
        if self.radio.isEnabled() and e.button() == Qt.MouseButton.LeftButton:
            self.radio.setChecked(True)
            self.radio.setFocus(Qt.FocusReason.MouseFocusReason)
            e.accept()
            return
        super().mousePressEvent(e)


class ModesWindow(ToolWindow):
    """Drei Karten aus ``controller.modes()``; „Wechseln“ ruft ``select_mode`` im Pool."""
    switch_requested = Signal(str)
    change_setup = Signal()
    disconnect_requested = Signal()

    def __init__(self, owner: QWidget):
        super().__init__('modes', f'{texts.MODES_TITLE} – {texts.APP_TITLE}', owner)
        self.modes: tuple[ModeInfo, ...] | None = None
        self.ctx = None
        self.error: str | None = None
        self.busy = False
        self.selected: str | None = None
        self.cards: dict[str, ModeCard] = {}
        self.group: QButtonGroup | None = None
        self.cancel_button = button(texts.MODE_CANCEL, name='modes_cancel')
        self.switch_button = button(texts.MODE_SWITCH, True, name='modes_switch')
        self.cancel_button.clicked.connect(self.close)
        self.switch_button.setDefault(True)             # Enter in einer Karte wechselt (Dialog-Standardknopf)
        self.switch_button.clicked.connect(self._switch)
        self.ring = ProgressRing(16)
        self.ring.hide()
        self.foot_lay.addWidget(self.ring)
        self.foot_lay.addStretch(1)
        self.foot_lay.addWidget(self.cancel_button)
        self.foot_lay.addWidget(self.switch_button)
        self.foot.show()
        self._render()

    def set_state(self, modes, ctx, error: str | None = None) -> None:
        self.modes = tuple(modes) if modes is not None else None
        self.ctx = ctx
        self.error = error
        self._render()

    def transmitting(self) -> bool:
        """Nur echte Übertragung sperrt den Wechsel; eine bloße Verbindung wird nach Bestätigung getrennt."""
        return texts.is_transmitting(self.ctx) if self.ctx is not None else False

    def effective_modes(self) -> tuple[ModeInfo, ...]:
        """Der Controller sperrt bei jedem aktiven Worker; die Oberfläche sperrt nur bei Übertragung."""
        if self.modes is None:
            return ()
        if self.transmitting():
            return tuple(m if m.active else replace(m, available=False, reason=m.reason or texts.MODE_LOCKED_REASON)
                         for m in self.modes)
        return tuple(replace(m, available=True, reason='') for m in self.modes)

    def set_busy(self, on: bool) -> None:
        self.busy = on
        self.ring.setVisible(on)
        self._update_foot()

    def _render(self) -> None:
        ctx = self.ctx
        key = (self.modes, self.error, self.transmitting(),
               None if ctx is None else (ctx.uart_baud, ctx.gsv_baud))
        self.set_content(key, self._build)
        self._update_foot()

    def _build(self, body) -> None:
        self.cards = {}
        body.addWidget(label(texts.MODES_TITLE, 'title'))
        if self.error:
            bar = InfoBar()
            title, text = texts.explain_code(self.error)
            bar.set_bar(texts.ActionBar('err', title, text))
            bar.setObjectName('modes_error')
            body.addWidget(bar)
        if self.modes is None:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(ProgressRing(16))
            row.addWidget(label(texts.MODE_LOADING, 'caption'), 1)
            body.addLayout(row)
            return
        modes = self.effective_modes()
        self.group = QButtonGroup(self.content)
        self.group.setExclusive(True)
        active = next((m.mode for m in modes if m.active), None)
        if self.selected not in {m.mode for m in modes if m.available}:
            self.selected = active if active in {m.mode for m in modes if m.available} else None
        for m in modes:
            card = ModeCard(m, self.ctx)
            self.cards[m.mode] = card
            if card.disconnect_button is not None:
                card.disconnect_clicked.connect(self.disconnect_requested)
            card.radio.installEventFilter(self)       # Pfeiltasten wechseln die Karte
            self.group.addButton(card.radio)
            card.radio.setChecked(m.mode == self.selected)
            card.set_selected(m.mode == self.selected)
            card.radio.toggled.connect(lambda on, mode=m.mode: on and self._select(mode))
            body.addWidget(card)
        self.hint = label(texts.MODE_UNCONFIGURED_HINT, 'caption')
        self.hint.setObjectName('modes_hint')
        body.addWidget(self.hint)
        locked = any(not m.available for m in modes)
        self.change_button = button(texts.CHANGE_SETUP, name='modes_change_setup')
        self.change_button.setEnabled(bool(active) and not locked)
        if locked:
            self.change_button.setToolTip(texts.REASON_TRANSMISSION_FIRST)
        self.change_button.clicked.connect(self.change_setup)
        body.addWidget(self.change_button, 0, Qt.AlignmentFlag.AlignLeft)       # erst einhängen, dann sichtbar machen
        self.change_button.setVisible(bool(active))          # ohne aktiven Weg gibt es nichts erneut zu durchlaufen
        self._update_hint()

    def eventFilter(self, obj, e):
        """Pfeil hoch/links = vorige, runter/rechts = nächste wählbare Karte (B-08)."""
        if e.type() == QEvent.Type.KeyPress and e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left,
                                                          Qt.Key.Key_Right):
            order = [k for k, c in self.cards.items() if c.radio.isEnabled()]
            cur = next((k for k, c in self.cards.items() if c.radio is obj), None)
            if cur in order and len(order) > 1:
                step = -1 if e.key() in (Qt.Key.Key_Up, Qt.Key.Key_Left) else 1
                nxt = order[(order.index(cur) + step) % len(order)]
                self.cards[nxt].radio.setChecked(True)
                self.cards[nxt].radio.setFocus(Qt.FocusReason.TabFocusReason)
                return True
        return super().eventFilter(obj, e)

    def _select(self, mode: str) -> None:
        self.selected = mode
        for k, c in self.cards.items():
            c.set_selected(k == mode)
        self._update_hint()
        self._update_foot()

    def _info(self, mode: str | None) -> ModeInfo | None:
        return next((m for m in self.effective_modes() if m.mode == mode), None)

    def _update_hint(self) -> None:
        info = self._info(self.selected)
        try:
            self.hint.setVisible(bool(info and not info.configured and not info.active))
        except (AttributeError, RuntimeError):
            pass

    def _update_foot(self) -> None:
        info = self._info(self.selected)
        ok = bool(info and info.available and not info.active and not self.busy)
        self.switch_button.setEnabled(ok)
        self.switch_button.setToolTip('' if ok else texts.MODE_IS_ACTIVE if info and info.active else '')

    def _switch(self) -> None:
        if self.selected and self.switch_button.isEnabled():
            self.switch_requested.emit(self.selected)


__all__ = ['ModeCard', 'ModesWindow']
