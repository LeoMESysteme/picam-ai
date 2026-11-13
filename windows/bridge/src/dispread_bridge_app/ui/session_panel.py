"""Session-Ergebnis und Checkliste „In GSVmulti einstellen“ (R3-3), gemeinsam für Einrichtung und Einstellungen.

Eine Ergebniszeile (neutrales Häkchen, Wertfeld mit Pfad, Symbolknöpfe „Ordner öffnen“ und „Neu erzeugen“),
darunter je Punkt ein Kontrollkästchen mit kurzem Text und ⓘ. Keine Anleitungsprosa: Erklärungen stehen im ⓘ.
Ein Haken ist eine Bedienerbestätigung, kein Beleg – nie grün.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import texts, theme
from .tool_windows import label
from .widgets import Badge, IconButton, InfoIcon, ValueField, badge_row, button


class ChecklistItem(QWidget):
    """Kontrollkästchen mit kurzem Text, optional „Pflicht“-Abzeichen und ⓘ; Klick auf den Text schaltet um."""

    def __init__(self, text: str, tip: str, key: str, checked: bool, required: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName(f'item_{key}')
        self.required = required
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.check = QCheckBox()
        self.check.setObjectName(f'check_{key}')
        self.check.setAccessibleName(text)
        self.check.setChecked(checked)
        self.text_label = label(text, 'body')
        self.text_label.mousePressEvent = lambda e: self.check.toggle() if self.check.isEnabled() else None
        lay.addWidget(self.check, 0, Qt.AlignmentFlag.AlignTop)
        lay.addWidget(self.text_label, 1)
        self.info = InfoIcon(tip, f'Erklärung: {text}')
        lay.addWidget(self.info, 0, Qt.AlignmentFlag.AlignTop)
        if required:
            self.badge = Badge(texts.CHECK_REQUIRED, texts.CHECK_REQUIRED_TIP, name='badge_required')
            lay.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        else:
            self.badge = None


class SessionPanel(QWidget):
    """Inhalt der Session-Karte. ``items`` ist die Liste der Checklistenpunkte (Schlüssel, Text, ⓘ, Pflicht)."""
    action = Signal(str)
    toggled = Signal(str, bool)

    def __init__(self, *, port: str | None, path: str | None, single_channel: bool, items: list, states: dict,
                 show_port: bool = True, parent=None):
        super().__init__(parent)
        self.checks: dict[str, QCheckBox] = {}
        self.buttons: dict[str, IconButton] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        if path:
            folder, fname = _split_path(path)
            row = QHBoxLayout()
            row.setSpacing(8)
            ic = QLabel()
            ic.setObjectName('session_done_icon')
            ic.setPixmap(theme.icon_pixmap('checkmark', 'text', 16))     # erzeugt ≠ abgenommen: nie grün
            ic.setAccessibleName(texts.SCREEN_READER['info'])
            ic.setToolTip(texts.SESSION_DONE)
            iw = QVBoxLayout()
            iw.setContentsMargins(0, 0, 0, 0)
            iw.addSpacing(22)                                   # auf Höhe der ersten Zeile des Wertfelds
            iw.addWidget(ic)
            iw.addStretch(1)
            row.addLayout(iw)
            row.addWidget(ValueField(texts.SESSION_PATH, fname), 1)
            again = IconButton('arrow_sync', texts.SESSION_AGAIN, name='btn_make_session')
            again.setEnabled(bool(port))
            again.clicked.connect(lambda: self.action.emit('make_session'))
            row.addWidget(again, 0, Qt.AlignmentFlag.AlignBottom)
            lay.addLayout(row)
            # Ordner sichtbar und mit beschriftetem Knopf erreichbar (Prüfung 13.11.: „wo liegt die Datei?“)
            frow = QHBoxLayout()
            frow.setSpacing(8)
            frow.addSpacing(24)
            frow.addWidget(ValueField(texts.SESSION_FOLDER, folder), 1)
            ob = button(texts.OPEN_FOLDER, name='btn_open_session_folder')
            ob.setIcon(theme.icon('folder_open', 'text', 16))
            ob.setToolTip(texts.OPEN_FOLDER)
            ob.clicked.connect(lambda: self.action.emit('open_session_folder:' + path))
            frow.addWidget(ob, 0, Qt.AlignmentFlag.AlignBottom)
            lay.addLayout(frow)
            self.buttons.update(open_session_folder=ob, make_session=again)
        if port and show_port:
            lay.addWidget(ValueField(texts.SESSION_PORT, port))
        elif not port and not path:
            lay.addWidget(label(texts.SESSION_NO_PORT, 'caption'))
        badges = [Badge(texts.BADGE_NOT_ACCEPTED, texts.SESSION_NOT_ACCEPTED, name='badge_not_accepted')] if path else []
        if single_channel:
            badges.append(Badge(texts.BADGE_SINGLE_CHANNEL, texts.SINGLE_CHANNEL_WARNING, name='badge_single_channel'))
        if badges:
            lay.addWidget(badge_row(*badges))
        if not path:
            head = QHBoxLayout()
            head.setSpacing(8)
            mk = button(texts.SESSION_MAKE, True, name='btn_make_session')
            mk.setEnabled(bool(port))
            if not port:
                mk.setToolTip(texts.SESSION_NO_PORT)
            mk.clicked.connect(lambda: self.action.emit('make_session'))
            self.buttons['make_session'] = mk
            head.addWidget(mk, 0)
            head.addWidget(InfoIcon(texts.SESSION_WHAT, 'Erklärung Session-Datei'), 0, Qt.AlignmentFlag.AlignVCenter)
            head.addStretch(1)
            lay.addLayout(head)
        if items:
            lay.addWidget(label(texts.CHECKLIST_TITLE, 'caption_strong'))
            for key, text, tip, required in items:
                it = ChecklistItem(text, tip, key, bool(states.get(key)), required)
                self.checks[key] = it.check
                it.check.toggled.connect(lambda on, k=key: self.toggled.emit(k, on))
                lay.addWidget(it)


def _split_path(path: str) -> tuple[str, str]:
    """(Ordner, Dateiname) für Windows- und Posix-Pfade; ohne Trenner: kein Ordner bekannt."""
    norm = path.replace('\\', '/')
    if '/' not in norm:
        return '–', path
    i = max(path.rfind('\\'), path.rfind('/'))
    return path[:i] or path[:i + 1], path[i + 1:]


def checklist_items(port: str | None, path: str | None, record_hidden_required: bool,
                    confirm_key: str | None = None) -> list:
    """Punkte der Checkliste: (Schlüssel, Text, ⓘ, Pflicht). Pflicht nur bei ausgeblendeten Kanälen."""
    items = []
    if path and record_hidden_required:
        items.append(('record_hidden_ok', texts.CHECK_RECORD_HIDDEN, texts.RECORD_HIDDEN, True))
    ch = texts.gsv_channel(port)
    if path and ch:
        items.append(('autoscale_ok', texts.CHECK_AUTOSCALE.format(channel=ch),
                      texts.AUTOSCALE_HINT.format(channel=ch), False))
    howto = texts.SESSION_HOWTO.format(port=port or '–')
    if confirm_key:
        items.append((confirm_key, texts.CHECK_OPEN_SESSION if path else texts.CHECK_MANUAL, howto, False))
    elif path:
        items.append(('open_ok', texts.CHECK_OPEN_SESSION, howto, False))
    return items


__all__ = ['ChecklistItem', 'SessionPanel', 'checklist_items']
