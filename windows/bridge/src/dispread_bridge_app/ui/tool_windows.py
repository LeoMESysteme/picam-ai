"""Werkzeugfenster (UX2): nicht modal, nativer Rahmen, Besitzer = Hauptfenster.

Ersetzt die früheren Popup-Flyouts: Kachel-Details, Schloss-Erklärung, gekoppelte Pi,
Info und „Protokolle exportieren“. Höchstens eine Instanz je Art; die Position gilt je Art für
die Laufzeit.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import texts, theme
from .widgets import Badge, InfoIcon, ProgressRing, StateIcon, ValueField, badge_row, button, format_fingerprint


def label(text: str, role: str = 'body', wrap: bool = True) -> QLabel:
    lab = theme.set_typo(QLabel(text), role)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    if wrap:
        lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    return lab


def section(title: str, info: str = '') -> tuple[QWidget, QVBoxLayout]:
    """Abschnitt-Überschrift (mit ⓘ für die Erklärung) und Karte darunter (Feldname-über-Wert-Liste)."""
    box = QWidget()
    outer = QVBoxLayout(box)
    outer.setContentsMargins(0, 4, 0, 0)
    outer.setSpacing(6)
    head = QHBoxLayout()
    head.setContentsMargins(0, 0, 0, 0)
    head.setSpacing(6)
    head.addWidget(label(title, 'section', wrap=False), 0)
    if info:
        head.addWidget(InfoIcon(info, f'Erklärung {title}'), 0, Qt.AlignmentFlag.AlignVCenter)
    head.addStretch(1)
    outer.addLayout(head)
    card = QFrame()
    card.setProperty('section', True)
    inner = QVBoxLayout(card)
    inner.setContentsMargins(14, 10, 8, 12)
    inner.setSpacing(10)
    outer.addWidget(card)
    return box, inner


def note_line(tone: str, text: str, name: str = '') -> QWidget:
    """Hinweiszeile: Statussymbol + Text (Word-Beside-Color), nicht schließbar. ``info`` = neutral."""
    w = QWidget()
    if name:
        w.setObjectName(name)
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    lay.addWidget(StateIcon(tone, 16), 0, Qt.AlignmentFlag.AlignTop)
    lay.addWidget(label(text, 'caption' if tone == 'info' else 'body'), 1)
    return w


def field(name: str, value: str, copy: bool | None = None) -> QWidget:
    """Technischer Wert als ValueField; Fingerabdruck in Vierergruppen, nie gekürzt."""
    copyable = (name in texts.TECH_FIELDS) if copy is None else copy
    display = format_fingerprint(value) if name.startswith('TLS') else None
    return ValueField(name, value, display=display, copyable=copyable, mono=copyable)


class _Content(QWidget):
    """Inhalt im Bildlaufbereich: Höhe kommt aus heightForWidth, nicht aus der schmalsten Umbruchbreite."""

    def minimumSizeHint(self):
        return QSize(0, 0)


class ToolWindow(QDialog):
    """Basis aller Werkzeugfenster. Esc und der native Schließen-Knopf blenden es aus."""
    closed = Signal()
    _positions: dict[str, QPoint] = {}
    MIN_W = 360

    def __init__(self, kind: str, title: str, owner: QWidget):
        flags = (Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint | Qt.WindowType.WindowCloseButtonHint)
        super().__init__(owner, flags)
        self.kind = kind
        self.setObjectName(f'tool_{kind}')
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowTitle(title)
        self.setMinimumWidth(self.MIN_W)
        self.setSizeGripEnabled(False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName('tool_scroll')
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll, 1)
        self.foot = QFrame()
        self.foot.setObjectName('footer')
        self.foot_lay = QHBoxLayout(self.foot)
        self.foot_lay.setContentsMargins(16, 10, 16, 10)
        self.foot_lay.setSpacing(8)
        self.foot.hide()
        outer.addWidget(self.foot)
        self.content: QWidget | None = None
        self.body: QVBoxLayout | None = None
        self._key = object()
        self._values = None
        self._refresh: Callable | None = None
        self._graveyard: list = []
        self._new_content()

    def _new_content(self) -> None:
        old = self.scroll.takeWidget()
        if old is not None:
            old.hide()
            self._graveyard.append(old)            # Python-Wrapper leben, bis Qt aufgeräumt hat
            old.deleteLater()
            QTimer.singleShot(500, self._graveyard.clear)
        self.content = _Content()
        self.content.setObjectName('tool_content')
        self.body = QVBoxLayout(self.content)
        self.body.setContentsMargins(16, 14, 16, 16)
        self.body.setSpacing(12)
        self.scroll.setWidget(self.content)

    def set_content(self, key, build: Callable[[QVBoxLayout], Callable | None], values=None) -> bool:
        """Baut den Inhalt nur bei geändertem Aufbau (``key``) neu; Kopierhäkchen und Auswahl bleiben.

        ``build`` darf eine Funktion ``refresh(values)`` liefern. Ändern sich bei gleichem Aufbau nur die
        ``values`` (Zähler, Zeiten), tauscht sie nur die Texte der vorhandenen Widgets aus: kein Neuaufbau,
        kein Flackern. Ohne ``refresh`` gehört alles Veränderliche in den Schlüssel (Neuaufbau)."""
        if key == self._key:
            if values is None or values == self._values:
                return False
            self._values = values
            if self._refresh is not None:
                self._refresh(values)
                self._fit(only_if_changed=True)
            return False
        self._key, self._values = key, values
        bar = self.scroll.verticalScrollBar()
        pos = bar.value()
        # Tausch und Einpassen unsichtbar: ohne Zwischenbild (leeres Fenster, Größensprung).
        self.setUpdatesEnabled(False)
        try:
            self._new_content()
            self._refresh = build(self.body)
            self.body.addStretch(1)
            self._fit(only_if_changed=True)
            bar.setValue(pos)
        finally:
            self.setUpdatesEnabled(True)
        QTimer.singleShot(0, lambda: bar.setValue(pos))        # Bildlaufposition bleibt über einen Neuaufbau
        if self.isVisible():                      # neue Kinder zeigt Qt erst verzögert: danach erneut einpassen
            QTimer.singleShot(0, lambda: self._fit(only_if_changed=True))
        return True

    def _fit(self, only_if_changed: bool = False) -> None:
        """Höhe nach Inhalt (heightForWidth, nach dem Polieren der Stile), höchstens Bildschirmhöhe − 48 px.
        ``only_if_changed``: nicht anfassen, wenn die Höhe schon stimmt (kein Resize, kein Neulayout)."""
        if self.content is None:
            return
        width = max(self.MIN_W, self.width() if self.isVisible() else 380)
        self.content.ensurePolished()
        lay = self.body
        lay.invalidate()
        lay.activate()
        h = lay.totalHeightForWidth(width) if lay.hasHeightForWidth() else -1
        if h < 0:
            h = lay.totalSizeHint().height()
        if not self.foot.isHidden():
            h += self.foot.sizeHint().height()
        screen = self._available()
        target = min(h + 2, max(200, screen.height() - self.SCREEN_MARGIN))
        if only_if_changed and self.isVisible() and (self.width(), self.height()) == (width, target):
            return
        self.resize(width, target)
        self._clamp()

    SCREEN_MARGIN = 48          # Fensterhöhe höchstens verfügbare Bildschirmhöhe − 48 px (Titelleiste, Rand)

    def _available(self):
        owner = self.parentWidget()
        return (owner.screen() if owner is not None else self.screen()).availableGeometry()

    def _clamp(self) -> None:
        """Position in die verfügbare Fläche des Bildschirms klemmen (nie halb außerhalb)."""
        scr = self._available()
        fg = self.frameGeometry()
        w, h = max(fg.width(), self.width()), max(fg.height(), self.height())
        x = min(max(fg.x(), scr.left()), max(scr.left(), scr.right() + 1 - w))
        y = min(max(fg.y(), scr.top()), max(scr.top(), scr.bottom() + 1 - h))
        if (x, y) != (fg.x(), fg.y()):
            self.move(self.x() + x - fg.x(), self.y() + y - fg.y())

    def present(self) -> None:
        """Zeigen; ist es schon offen, nach vorn holen."""
        pos = self._positions.get(self.kind)
        if not self.isVisible():
            owner = self.parentWidget()
            if pos is not None:
                self.move(pos)
            elif owner is not None:
                g = owner.frameGeometry()
                scr = owner.screen().availableGeometry()
                x = g.right() + 8 if g.right() + 8 + self.width() <= scr.right() else max(scr.left(), g.left() - 8
                                                                                           - self.width())
                self.move(x, g.top())
        first = not self.isVisible()
        self.show()
        self._clamp()
        self.raise_()
        self.activateWindow()
        if first:
            QTimer.singleShot(0, self._fit)

    def moveEvent(self, e):
        super().moveEvent(e)
        if self.isVisible():
            self._positions[self.kind] = self.pos()

    def hideEvent(self, e):
        self._positions[self.kind] = self.pos()
        super().hideEvent(e)
        self.closed.emit()


# ---------------------------------------------------------------- Inhalte
def chip_structure(view: texts.ChipView) -> tuple:
    """Alles, was beim Kachel-Detailfenster den Aufbau bestimmt. Die reinen Texte (Zähler, Untertitel,
    Werte) gehören nicht dazu: sie ändern sich je Takt und werden in ``build_chip_detail`` nur getauscht."""
    return ('chip', view.key, view.tone, bool(view.sub), bool(texts.CHIP_HELP.get(view.key)),
            view.warn == texts.SINGLE_CHANNEL_WARNING, bool(view.warn), bool(view.hint),
            tuple((k, v in texts.EMPTY_VALUES) for k, v in view.details), view.actions)


def chip_values(view: texts.ChipView) -> tuple:
    return (view.name, view.word, view.sub, view.warn, view.hint, tuple(v for _, v in view.details))


def build_chip_detail(view: texts.ChipView, body: QVBoxLayout, on_action: Callable[[str], None]) -> Callable:
    """Baut das Detailfenster einer Kachel; liefert ``refresh(chip_values)`` für Textänderungen bei gleichem Aufbau."""
    head = QHBoxLayout()
    head.setSpacing(8)
    icon = QLabel()
    icon.setPixmap(theme.icon_pixmap(texts.CHIP_ICON.get(view.key, 'info'), 'text', 20))
    head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    name_label = label(view.name, 'title')
    head.addWidget(name_label, 1)
    body.addLayout(head)
    st = QHBoxLayout()
    st.setSpacing(8)
    st.addWidget(StateIcon(view.tone, 16), 0, Qt.AlignmentFlag.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(2)
    word_label = label(view.word, 'body_strong')
    col.addWidget(word_label)
    sub_label = None
    if view.sub:
        sub_label = label(view.sub, 'caption')
        col.addWidget(sub_label)
    st.addLayout(col, 1)
    body.addLayout(st)
    help_text = texts.CHIP_HELP.get(view.key, '')
    if help_text:
        body.addWidget(label(help_text))
    warn_label = None
    if view.warn == texts.SINGLE_CHANNEL_WARNING:
        body.addWidget(badge_row(Badge(texts.BADGE_SINGLE_CHANNEL, view.warn, name='chip_warn')))
    elif view.warn:                      # z. B. „Session passt nicht“: Achtung mit Satz, kein Abzeichen
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(StateIcon('warn', 16), 0, Qt.AlignmentFlag.AlignTop)
        warn_label = label(view.warn)
        row.addWidget(warn_label, 1)
        body.addLayout(row)
    fields: list[ValueField] = []
    if view.details:
        box, inner = section('Werte')
        for k, v in view.details:
            f = field(k, v)
            fields.append(f)
            inner.addWidget(f)
        body.addWidget(box)
    for text_, aid, enabled, reason in view.actions:
        b = button(text_, name='tool_action')
        b.setEnabled(enabled)
        if not enabled:
            b.setToolTip(reason)
            body.addWidget(label(reason, 'caption'))
        b.clicked.connect(lambda _=False, a=aid: on_action(a))
        body.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
    hint_label = None
    if view.hint:
        hint_label = label(view.hint, 'caption')
        body.addWidget(hint_label)

    def refresh(values: tuple) -> None:
        name, word, sub, warn, hint, detail_values = values
        name_label.setText(name)
        word_label.setText(word)
        if sub_label is not None:
            sub_label.setText(sub)
        if warn_label is not None:
            warn_label.setText(warn)
        if hint_label is not None:
            hint_label.setText(hint)
        for f, v in zip(fields, detail_values, strict=False):
            f.set_value(v, format_fingerprint(v) if f.name_label.text().startswith('TLS') else None)
    return refresh


def build_lock(body: QVBoxLayout) -> None:
    head = QHBoxLayout()
    head.setSpacing(8)
    icon = QLabel()
    icon.setPixmap(theme.icon_pixmap('lock_closed', 'text', 20))
    head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    head.addWidget(label(texts.LOCK_TITLE, 'title'), 1)
    body.addLayout(head)
    body.addWidget(label(texts.LOCK_TEXT))


def paired_structure(ctx, locked: bool) -> tuple:
    return ('paired', tuple((name, pi_id) for name, pi_id, _ in ctx.paired), ctx.pi_id, locked)


def paired_values(ctx) -> tuple:
    return tuple(when for _, _, when in ctx.paired)


def build_paired(ctx, body: QVBoxLayout, on_action: Callable[[str], None], locked: bool | None = None) -> Callable:
    """``locked``: Wechsel gesperrt (Übertragung läuft); ohne Angabe gilt ``ctx.switch_locked``.
    Liefert ``refresh(paired_values)`` für wechselnde Zeitangaben („zuletzt vor 2 Stunden“)."""
    body.addWidget(label(texts.PAIRED_TITLE, 'title'))
    free = not (ctx.switch_locked if locked is None else locked)
    when_labels: list[QLabel | None] = []
    for name, pi_id, when in ctx.paired:
        card = QFrame()
        card.setProperty('section', True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 8, 12)
        lay.setSpacing(6)
        lay.addWidget(label(name, 'body_strong'))
        when_label = label(texts.CURRENT_PI if pi_id == ctx.pi_id else when, 'caption')
        when_labels.append(None if pi_id == ctx.pi_id else when_label)
        lay.addWidget(when_label)
        lay.addWidget(field('Pi-ID', pi_id))
        if pi_id != ctx.pi_id:
            b = button(texts.SWITCH_PI, name='switch_pi')
            b.setEnabled(free)
            if not free:
                b.setToolTip(texts.REASON_TRANSMISSION_FIRST)
                lay.addWidget(label(texts.REASON_TRANSMISSION_FIRST, 'caption'))
            b.clicked.connect(lambda _=False, i=pi_id: on_action(f'switch_pi:{i}'))
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(card)
    body.addWidget(label(texts.PI_SWITCH_NOTE, 'caption'))

    def refresh(whens: tuple) -> None:
        for lab, when in zip(when_labels, whens, strict=False):
            if lab is not None:
                lab.setText(when)
    return refresh


class InfoContent:
    """Info: nur „Über“ (Version, Kanal, Protokoll, Lauf-ID, Pi-ID); alles Einstellbare steht in den Einstellungen.

    Aufbau und Werte getrennt: ändert sich nur ein Wert (z. B. neue Lauf-ID), tauscht ``refresh`` den Text im
    vorhandenen Feld; ein Feld, das neu auftaucht oder verschwindet, ändert ``structure`` und baut neu."""

    @staticmethod
    def structure(ctx) -> tuple:
        return ('info', bool(ctx.version), bool(ctx.channel), bool(ctx.protocol), bool(ctx.run_id), bool(ctx.pi_id))

    @staticmethod
    def values(ctx) -> tuple:
        return (ctx.version or '–', ctx.channel or '', ctx.protocol or '–', ctx.run_id or '', ctx.pi_id or '')

    def __init__(self, ctx, body: QVBoxLayout, on_action: Callable[[str], None]):
        body.addWidget(label(texts.APP_TITLE, 'title'))
        box, inner = section(texts.INFO_ABOUT)
        v = self.values(ctx)
        self.fields: dict[int, ValueField] = {}
        inner_fields = [(0, 'Version', v[0], None), (1, 'Kanal', v[1], False), (2, 'Protokoll', v[2], None),
                        (3, 'Lauf-ID', v[3], None), (4, 'Pi-ID', v[4], None)]
        for i, name, val, copy in inner_fields:
            if i in (1, 3, 4) and not val:
                continue
            f = field(name, val, copy=copy)
            self.fields[i] = f
            inner.addWidget(f)
        body.addWidget(box)
        b = button(texts.INFO_OPEN_SETTINGS, name='open_settings')
        b.clicked.connect(lambda: on_action('open_settings'))
        body.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(label(texts.ICON_CREDIT, 'caption'))

    def refresh(self, values: tuple) -> None:
        for i, f in self.fields.items():
            f.set_value(values[i])


class ExportWindow(ToolWindow):
    """„Protokolle exportieren“: sagt vorher, was drin ist; danach Häkchen, Pfad, Ordner öffnen."""
    save_requested = Signal()
    open_folder = Signal(str)

    def __init__(self, owner: QWidget):
        super().__init__('export', texts.EXPORT_LOGS, owner)
        self.contents: tuple[tuple[str, str], ...] | None = None
        self.state = 'idle'               # idle | saving | done | failed
        self.path: Path | None = None
        self.save_button = button(texts.EXPORT_SAVE, True, name='export_save')
        self.save_button.clicked.connect(self.save_requested)
        self.ring = ProgressRing(16)
        self.ring.hide()
        self.busy_label = label(texts.EXPORT_SAVING, 'caption', wrap=False)
        self.busy_label.hide()
        self.close_button = button(texts.CLOSE, name='export_close')
        self.close_button.clicked.connect(self.close)
        self.close_button.hide()
        self.foot_lay.addWidget(self.ring)
        self.foot_lay.addWidget(self.busy_label)
        self.foot_lay.addStretch(1)
        self.foot_lay.addWidget(self.save_button)
        self.foot_lay.addWidget(self.close_button)
        self.foot.show()
        self._render()

    def set_contents(self, contents) -> None:
        self.contents = tuple(contents) if contents is not None else ()
        self._render()

    def set_state(self, state: str, path: Path | None = None) -> None:
        self.state, self.path = state, path
        busy = state == 'saving'
        self.ring.setVisible(busy)
        self.busy_label.setVisible(busy)
        self.save_button.setEnabled(not busy)
        done = state == 'done'
        # Nach dem Speichern ist „Schließen“ die nächste Aktion (Akzent), „Erneut speichern …“ bleibt Standard.
        self.save_button.setText(texts.EXPORT_SAVE_AGAIN if state in ('done', 'failed') else texts.EXPORT_SAVE)
        self.save_button.setProperty('accent', not done)
        self.close_button.setVisible(done)
        self.close_button.setProperty('accent', done)
        for b in (self.save_button, self.close_button):
            b.style().unpolish(b)
            b.style().polish(b)
        if done:
            self.close_button.setDefault(True)
        self._render()

    def _render(self) -> None:
        self.set_content((self.contents, self.state, str(self.path)), self._build)

    def _build(self, body: QVBoxLayout) -> None:
        body.addWidget(label(texts.EXPORT_LOGS, 'title'))
        if self.state in ('done', 'failed'):
            row = QHBoxLayout()
            row.setSpacing(8)
            ic = QLabel()
            ic.setObjectName('export_done_icon')
            ic.setPixmap(theme.icon_pixmap('checkmark', 'ok', 20) if self.state == 'done'
                         else theme.status_pixmap('err', 16))
            ic.setAccessibleName(texts.SCREEN_READER['ok' if self.state == 'done' else 'err'])
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(texts.EXPORT_DONE if self.state == 'done' else texts.EXPORT_FAILED,
                                'body_strong'), 1)
            body.addLayout(row)
            if self.state == 'done' and self.path is not None:
                body.addWidget(ValueField(texts.EXPORT_PATH, str(self.path)))
                b = button(texts.OPEN_FOLDER, name='open_folder')
                b.setIcon(theme.icon('folder_open', 'text', 16))
                b.clicked.connect(lambda: self.open_folder.emit(str(self.path.parent)))
                body.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
            elif self.state == 'failed':
                body.addWidget(label(texts.EXPORT_FAILED_TEXT, 'caption'))
        body.addWidget(label(texts.EXPORT_LEAD, 'body_strong'))
        if self.contents is None:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(ProgressRing(16))
            row.addWidget(label(texts.EXPORT_LOADING, 'caption'), 1)
            body.addLayout(row)
        elif not self.contents:
            body.addWidget(label(texts.EXPORT_UNKNOWN, 'caption'))
        else:
            box = QFrame()
            box.setProperty('section', True)
            lay = QVBoxLayout(box)
            lay.setContentsMargins(14, 10, 14, 12)
            lay.setSpacing(10)
            for name, what in self.contents:
                col = QVBoxLayout()
                col.setSpacing(2)
                col.addWidget(label(name, 'data'))
                col.addWidget(label(what, 'caption'))
                lay.addLayout(col)
            body.addWidget(box)
        body.addWidget(label(texts.EXPORT_NOTE, 'caption'))


__all__ = ['ToolWindow', 'ExportWindow', 'InfoContent', 'build_chip_detail', 'build_lock', 'build_paired',
           'chip_structure', 'chip_values', 'paired_structure', 'paired_values',
           'field', 'label', 'note_line', 'section']
