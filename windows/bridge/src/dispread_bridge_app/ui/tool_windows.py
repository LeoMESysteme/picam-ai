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
    QCheckBox,
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
from .widgets import CopyField, ProgressRing, StateIcon, button, format_fingerprint


def label(text: str, role: str = 'body', wrap: bool = True) -> QLabel:
    lab = theme.set_typo(QLabel(text), role)
    lab.setWordWrap(wrap)
    lab.setTextFormat(Qt.TextFormat.PlainText)
    if wrap:
        lab.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    return lab


def section(title: str) -> tuple[QWidget, QVBoxLayout]:
    """Abschnitt-Überschrift mit Karte darunter (Feldname-über-Wert-Liste)."""
    box = QWidget()
    outer = QVBoxLayout(box)
    outer.setContentsMargins(0, 4, 0, 0)
    outer.setSpacing(6)
    outer.addWidget(label(title, 'section'))
    card = QFrame()
    card.setProperty('section', True)
    inner = QVBoxLayout(card)
    inner.setContentsMargins(14, 10, 8, 12)
    inner.setSpacing(10)
    outer.addWidget(card)
    return box, inner


def field(name: str, value: str, copy: bool | None = None) -> QWidget:
    """Technischer Wert als CopyField; Fingerabdruck in Vierergruppen, nie gekürzt."""
    copyable = (name in texts.TECH_FIELDS) if copy is None else copy
    display = format_fingerprint(value) if name.startswith('TLS') else None
    return CopyField(name, value, display=display, copyable=copyable, mono=copyable)


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

    def set_content(self, key, build: Callable[[QVBoxLayout], None]) -> bool:
        """Baut den Inhalt nur neu, wenn sich die Daten geändert haben (Kopierhäkchen, Auswahl bleiben)."""
        if key == self._key:
            return False
        self._key = key
        self._new_content()
        build(self.body)
        self.body.addStretch(1)
        self._fit()
        if self.isVisible():                      # neue Kinder zeigt Qt erst verzögert: danach erneut einpassen
            QTimer.singleShot(0, self._fit)
        return True

    def _fit(self) -> None:
        """Höhe nach Inhalt (heightForWidth, nach dem Polieren der Stile), höchstens 80 % des Bildschirms."""
        owner = self.parentWidget()
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
        screen = (owner.screen() if owner is not None else self.screen()).availableGeometry()
        self.resize(width, min(h + 2, int(screen.height() * 0.8)))

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
def build_chip_detail(view: texts.ChipView, body: QVBoxLayout, on_action: Callable[[str], None]) -> None:
    head = QHBoxLayout()
    head.setSpacing(8)
    icon = QLabel()
    icon.setPixmap(theme.icon_pixmap(texts.CHIP_ICON.get(view.key, 'info'), 'text', 20))
    head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    head.addWidget(label(view.name, 'title'), 1)
    body.addLayout(head)
    st = QHBoxLayout()
    st.setSpacing(8)
    st.addWidget(StateIcon(view.tone, 16), 0, Qt.AlignmentFlag.AlignTop)
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(label(view.word, 'body_strong'))
    if view.sub:
        col.addWidget(label(view.sub, 'caption'))
    st.addLayout(col, 1)
    body.addLayout(st)
    help_text = texts.CHIP_HELP.get(view.key, '')
    if help_text:
        body.addWidget(label(help_text))
    if view.details:
        box, inner = section('Werte')
        for k, v in view.details:
            inner.addWidget(field(k, v))
        body.addWidget(box)
    for text_, aid, enabled, reason in view.actions:
        b = button(text_, name='tool_action')
        b.setEnabled(enabled)
        if not enabled:
            b.setToolTip(reason)
            body.addWidget(label(reason, 'caption'))
        b.clicked.connect(lambda _=False, a=aid: on_action(a))
        body.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
    if view.hint:
        body.addWidget(label(view.hint, 'caption'))


def build_lock(body: QVBoxLayout) -> None:
    head = QHBoxLayout()
    head.setSpacing(8)
    icon = QLabel()
    icon.setPixmap(theme.icon_pixmap('lock_closed', 'text', 20))
    head.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
    head.addWidget(label(texts.LOCK_TITLE, 'title'), 1)
    body.addLayout(head)
    body.addWidget(label(texts.LOCK_TEXT))


def build_paired(ctx, body: QVBoxLayout, on_action: Callable[[str], None]) -> None:
    body.addWidget(label(texts.PAIRED_TITLE, 'title'))
    free = not ctx.switch_locked
    for name, pi_id, when in ctx.paired:
        card = QFrame()
        card.setProperty('section', True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 8, 12)
        lay.setSpacing(6)
        lay.addWidget(label(name, 'body_strong'))
        lay.addWidget(label(texts.CURRENT_PI if pi_id == ctx.pi_id else when, 'caption'))
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


class InfoContent:
    """Info (bisher „Details“): Version, Pi, Ports, Autostart-Schalter."""

    def __init__(self, ctx, body: QVBoxLayout, on_action: Callable[[str], None]):
        self.auto_box: QCheckBox | None = None
        self.saved: QLabel | None = None
        body.addWidget(label(texts.APP_TITLE, 'title'))
        box, inner = section('Diese Brücke')
        inner.addWidget(field('Version', ctx.version or '–'))
        if ctx.channel:
            inner.addWidget(field('Kanal', ctx.channel, copy=False))
        inner.addWidget(field('Protokoll', ctx.protocol or '–'))
        if ctx.run_id:
            inner.addWidget(field('Lauf-ID', ctx.run_id))
        body.addWidget(box)
        box, inner = section('Pi')
        inner.addWidget(field('Name', ctx.pi_name or '–', copy=False))
        inner.addWidget(field('Pi-ID', ctx.pi_id or '–'))
        inner.addWidget(field('Endpunkt', ctx.endpoint or '–'))
        inner.addWidget(field('TLS-Fingerabdruck (SHA-256)', ctx.fingerprint or '–'))
        if ctx.pi_name:
            row = QHBoxLayout()
            row.setSpacing(8)
            cb = QCheckBox()
            cb.setObjectName('auto_connect')
            text_ = texts.AUTO_CONNECT.format(pi=ctx.pi_name)
            cb.setAccessibleName(text_)
            cb.setChecked(ctx.auto_connect)
            row.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(text_), 1)
            inner.addLayout(row)
            saved = QWidget()
            sl = QHBoxLayout(saved)
            sl.setContentsMargins(28, 0, 0, 0)
            sl.setSpacing(6)
            ok = QLabel()
            ok.setPixmap(theme.icon_pixmap('checkmark', 'ok', 16))
            sl.addWidget(ok)
            self.saved = label(texts.SAVED, 'caption', wrap=False)
            sl.addWidget(self.saved)
            sl.addStretch(1)
            saved.hide()
            self.saved_row = saved
            inner.addWidget(saved)
            self.auto_box = cb
            cb.toggled.connect(lambda on: on_action('auto_connect:' + ('on' if on else 'off')))
        if len(ctx.paired) > 1:
            b = button(texts.PAIRED_TITLE + ' …', name='show_paired')
            b.clicked.connect(lambda: on_action('show_paired'))
            inner.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(box)
        box, inner = section('Ports')
        inner.addWidget(field('Brückenseite', ctx.bridge_port or texts.NOT_SET))
        inner.addWidget(field('GSVmulti-Seite', ctx.gsv_port or texts.NOT_SET))
        if ctx.adapter_port:
            inner.addWidget(field('USB-Adapter', ctx.adapter_port))
        if ctx.uart_baud:
            inner.addWidget(field('UART Pi ↔ Brücke', f'{ctx.uart_baud} Baud', copy=False))
        if ctx.gsv_baud:
            inner.addWidget(field('GSVmulti-Seite (Session)', f'{ctx.gsv_baud} Baud', copy=False))
        body.addWidget(box)
        box, inner = section('Journal')
        inner.addWidget(label(texts.JOURNAL_DETAILS))
        body.addWidget(box)
        body.addWidget(label(texts.ICON_CREDIT, 'caption'))

    def confirm_saved(self) -> None:
        """Häkchen „Gespeichert“ nach dem Speichern des Schalters, blendet nach 2 s aus."""
        if self.saved is None:
            return
        self.saved_row.show()
        QTimer.singleShot(2000, self._hide_saved)

    def _hide_saved(self) -> None:
        try:
            self.saved_row.hide()
        except RuntimeError:
            pass


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
        self.foot_lay.addWidget(self.ring)
        self.foot_lay.addWidget(self.busy_label)
        self.foot_lay.addStretch(1)
        self.foot_lay.addWidget(self.save_button)
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
                body.addWidget(CopyField(texts.EXPORT_PATH, str(self.path)))
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
           'field', 'label', 'section']
