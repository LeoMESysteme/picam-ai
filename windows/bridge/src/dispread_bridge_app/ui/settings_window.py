"""Einstellungen-Fenster (UX2): Weg · Pi · Ports · GSVmulti-Session · Protokolle · Über.

Werte stehen als Wertfeld (grau, kopierbar). Endpunkt, Portpaar und Adapter werden mit ``ValidatedField`` echt geprüft
und erst nach bestandener Prüfung über die vorhandenen Controller-Methoden übernommen; „Gespeichert“
bestätigt es. Während einer Übertragung sind Weg, Pi und Ports schreibgeschützt (Schloss + Grund).
"""
from __future__ import annotations

import string
import time
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QComboBox, QFrame, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

from . import texts, theme
from .session_panel import SessionPanel, checklist_items
from .status_view import SegButton
from .tool_windows import ToolWindow, field, label, section
from .widgets import (
    Badge,
    IconButton,
    InfoIcon,
    ProgressRing,
    SavedNote,
    StateIcon,
    ValidatedField,
    badge_row,
    button,
    repolish,
    run_now,
)


@dataclass
class SessionState:
    """Ergebnis von „Session-Datei erzeugen …“ (Laufzeit, gehört dem Hauptfenster)."""
    state: str = 'idle'              # idle | saving | done | failed
    export: object | None = None     # SessionExport
    code: str | None = None          # AppError-Code bei failed


def lock_row(reason: str = texts.SETTINGS_LOCKED) -> QWidget:
    """Abzeichen „schreibgeschützt“ mit ⓘ (Grund): kein Absatz, nie grün."""
    w = badge_row(Badge(texts.BADGE_READONLY, reason, name='badge_readonly'))
    w.setObjectName('settings_lock')
    return w


def session_mode_port(ctx) -> str | None:
    return ctx.adapter_port if ctx.route_mode == 'uart_direct' else ctx.gsv_port


_UMLAUT = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}


def ascii_name_part(text: str) -> str:
    """Nur ``A-Za-z0-9_-``: Umlaute umschrieben, alles andere entfernt (Dateiname für GSVmulti)."""
    out = ''.join(_UMLAUT.get(ch, ch) for ch in text)
    return ''.join(ch for ch in out if ch in string.ascii_letters + string.digits + '_-')


def session_default_name(ctx, port: str) -> str:
    pi = ascii_name_part(ctx.pi_name or 'Pi') or 'Pi'
    return f'GSVmulti_{pi}_{ascii_name_part(port) or "COM"}.ucf'


class SettingsWindow(ToolWindow):
    action = Signal(str)                 # open_modes | change_setup | export_diagnostics | make_session | …
    theme_changed = Signal(str)          # system | light | dark
    apply = Signal(str, object)          # (endpoint|ports|adapter, Wert) – nur nach bestandener Prüfung

    def __init__(self, owner: QWidget):
        super().__init__('settings', f'{texts.SETTINGS} – {texts.APP_TITLE}', owner)
        self.check_fns: dict = {}
        self.runner = run_now
        self.ctx = None
        self.locked = False
        self.ports: tuple = ()
        self.adapters: tuple = ()
        self.session = SessionState()
        self.record_hidden_confirmed: set[str] = set()
        self.checklist_done: set[str] = set()
        self.errors: dict[str, str] = {}
        self._saved_until: dict[str, float] = {}
        self.fields: dict[str, ValidatedField] = {}
        self.notes: dict[str, SavedNote] = {}
        self.auto_box: QCheckBox | None = None
        self.take_over: QWidget | None = None
        self.panel = None

    def bind(self, check_fns: dict, runner, confirmed: set, checklist_done: set | None = None) -> None:
        self.check_fns, self.runner, self.record_hidden_confirmed = dict(check_fns), runner, confirmed
        if checklist_done is not None:
            self.checklist_done = checklist_done

    # ------------------------------------------------------------ Zustand
    def update_from(self, ctx, locked: bool, ports=None, adapters=None, session: SessionState | None = None) -> None:
        self.ctx, self.locked = ctx, locked
        if ports is not None:
            self.ports = tuple(ports)
        if adapters is not None:
            self.adapters = tuple(adapters)
        if session is not None:
            self.session = session
        s = self.session
        edited = (None, None, None, None) if not locked else (ctx.endpoint, ctx.bridge_port, ctx.gsv_port,
                                                            ctx.adapter_port)     # freie Felder zeigen schon den Eingabewert
        key = ('settings', ctx.route_mode, ctx.route, locked, ctx.pi_name, ctx.pi_id, *edited, ctx.fingerprint,
               ctx.auto_connect, len(ctx.paired) > 1, ctx.adapter_present, theme.stored_preference(), ctx.uart_baud, ctx.gsv_baud, ctx.version, ctx.channel, ctx.protocol, ctx.run_id,
               ctx.session_template, ctx.session_name, self.ports, self.adapters, s.state,
               None if s.export is None else (str(s.export.path), s.export.record_hidden_required), s.code,
               tuple(sorted(self.errors.items())))
        self.set_content(key, self._build)

    def mark_saved(self, kind: str) -> None:
        """Übernahme bestätigt: Häkchen „Gespeichert“ für 2 s, auch über einen Neuaufbau hinweg."""
        self.errors.pop(kind, None)
        self._saved_until[kind] = time.monotonic() + SavedNote.SHOW_MS / 1000
        note = self.notes.get(kind)
        try:
            if note is not None:
                note.flash()
        except RuntimeError:
            pass

    def show_error(self, kind: str, code: str | None) -> None:
        self.errors[kind] = code or 'unknown_error'
        if self.ctx is not None:
            self.update_from(self.ctx, self.locked)

    def _note(self, kind: str) -> SavedNote:
        n = SavedNote()
        n.setObjectName(f'saved_{kind}')
        self.notes[kind] = n
        left = self._saved_until.get(kind, 0) - time.monotonic()
        if left > 0.05:
            QTimer.singleShot(0, lambda n=n, ms=int(left * 1000): n.flash(ms) if _valid(n) else None)
        return n

    def _error_line(self, inner: QVBoxLayout, kind: str) -> None:
        code = self.errors.get(kind)
        if not code:
            return
        title, text = texts.explain_code(code)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(StateIcon('err', 16), 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(label(title, 'caption_strong'), 1)
        row.addWidget(InfoIcon(text, f'Erklärung {title}'), 0, Qt.AlignmentFlag.AlignTop)
        inner.addLayout(row)

    def _field(self, editor, name: str, value, **kw) -> ValidatedField:
        f = ValidatedField(editor, self.check_fns[name], value=value, runner=self.runner, name=f'settings_{name}',
                           label_role='caption', **kw)
        self.fields[name] = f
        return f

    # ------------------------------------------------------------ Aufbau
    def _build(self, body: QVBoxLayout) -> None:
        c = self.ctx
        self.fields, self.notes, self.auto_box, self.take_over = {}, {}, None, None
        body.addWidget(label(texts.SETTINGS, 'title'))
        if self.locked:
            body.addWidget(lock_row())
        self._build_theme(body)
        self._build_general(body, c)
        self._build_pi(body, c)
        self._build_ports(body, c)
        self._build_session(body, c)
        box, inner = section(texts.SETTINGS_LOGS, texts.SETTINGS_LOGS_TEXT)
        b = button(texts.SETTINGS_LOGS_BUTTON, name='settings_export')
        b.setIcon(theme.icon('document_arrow_down', 'text', 16))
        b.clicked.connect(lambda: self.action.emit('export_diagnostics'))
        inner.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(box)
        box, inner = section(texts.SETTINGS_ABOUT, texts.ICON_CREDIT)
        inner.addWidget(field('Version', c.version or '–'))
        if c.channel:
            inner.addWidget(field('Kanal', c.channel, copy=False))
        inner.addWidget(field('Protokoll', c.protocol or '–'))
        if c.run_id:
            inner.addWidget(field('Lauf-ID', c.run_id))
        body.addWidget(box)

    def _build_general(self, body, c) -> None:
        """Autostart und Darstellung. Der Weg wird nur über den Knopf im Kopf gewählt (keine doppelten Optionen)."""
        if not (c.pi_name and c.route_mode != 'uart_direct'):
            return
        box, inner = section(texts.SETTINGS_GENERAL)
        box.setObjectName('settings_general')
        row = QHBoxLayout()
        row.setSpacing(8)
        cb = QCheckBox()
        cb.setObjectName('auto_connect')
        cb.setAccessibleName(texts.AUTO_CONNECT)
        cb.setChecked(c.auto_connect)
        cb.toggled.connect(lambda on: self.action.emit('auto_connect:' + ('on' if on else 'off')))
        row.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
        lab = label(texts.AUTO_CONNECT)
        lab.mousePressEvent = lambda e: cb.toggle()
        row.addWidget(lab, 1)
        inner.addLayout(row)
        note = self._note('auto')
        note.layout().setContentsMargins(28, 0, 0, 0)
        inner.addWidget(note)
        self.auto_box = cb
        body.addWidget(box)

    def _build_theme(self, body) -> None:
        """Darstellung (erster Abschnitt): Automatisch/Hell/Dunkel, lokal gespeichert, wirkt sofort."""
        box, inner = section(texts.SETTINGS_THEME)
        box.setObjectName('settings_theme')
        seg = QFrame()
        seg.setObjectName('segmented')
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(2, 2, 2, 2)
        sl.setSpacing(0)
        group = QButtonGroup(seg)
        cur = {True: 'dark', False: 'light'}.get(theme.stored_preference(), 'system')
        self.theme_buttons = {}
        for mode, text in (('system', texts.THEME_SYSTEM), ('light', texts.THEME_LIGHT), ('dark', texts.THEME_DARK)):
            b = SegButton(text)
            b.setObjectName(f'theme_{mode}')
            b.setProperty('seg', True)
            # gewählt = fett: Breite für die fette Schrift reservieren, sonst wird „Automatisch“ abgeschnitten
            b.setMinimumWidth(max(80, QFontMetrics(theme.typo_font('body_strong')).horizontalAdvance(text) + 36))
            b.setCheckable(True)
            b.setChecked(mode == cur)
            group.addButton(b)
            sl.addWidget(b)
            b.clicked.connect(lambda _=False, m=mode: self.theme_changed.emit(m))
            self.theme_buttons[mode] = b
        inner.addWidget(seg, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(box)

    def _build_pi(self, body, c) -> None:
        box, inner = section(texts.SETTINGS_PI)
        box.setObjectName('settings_pi')
        if c.route_mode == 'uart_direct':
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(label(texts.DIRECT_UNUSED, 'caption_strong'), 0)
            row.addWidget(InfoIcon(texts.SETTINGS_DIRECT_PI, 'Erklärung Pi'), 0)
            row.addStretch(1)
            inner.addLayout(row)
            body.addWidget(box)
            return
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name_row.addWidget(field('Name', c.pi_name or '–', copy=False), 1)
        if len(c.paired) > 1:
            pb = IconButton('arrow_swap', texts.PAIRED_TITLE, name='show_paired')
            pb.clicked.connect(lambda: self.action.emit('show_paired'))
            name_row.addWidget(pb, 0, Qt.AlignmentFlag.AlignBottom)
        inner.addLayout(name_row)
        inner.addWidget(field('Pi-ID', c.pi_id or '–'))
        editable = (not self.locked and c.pi_name and c.route_mode in (None, 'network')
                    and 'endpoint' in self.check_fns)
        if editable:
            self._build_endpoint(inner, c)
        else:
            inner.addWidget(field('Endpunkt', c.endpoint or '–'))
        inner.addWidget(field('TLS-Fingerabdruck (SHA-256)', c.fingerprint or '–'))
        body.addWidget(box)

    def _build_endpoint(self, inner, c) -> None:
        """Endpunkt: schreibgeschütztes Wertfeld, Stift zum Bearbeiten, dann Haken „Bestätigen und speichern“."""
        current = c.endpoint or ''
        inner.addWidget(label(texts.SETTINGS_ENDPOINT, 'caption'))
        e = QLineEdit(current)
        e.setObjectName('settings_endpoint_edit')
        e.setAccessibleName(texts.SETTINGS_ENDPOINT)
        e.setPlaceholderText(texts.ENDPOINT_PLACEHOLDER)
        e.setReadOnly(True)
        e.setProperty('mono', True)
        e.setFont(theme.make_font(9, mono=True))
        f = self._field(e, 'endpoint', lambda: (e.text().strip() if not e.isReadOnly() and e.text().strip() != current
                                                  else None))
        f.label = None
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(f, 1, Qt.AlignmentFlag.AlignTop)
        pen = IconButton('edit', texts.ENDPOINT_EDIT, name='settings_endpoint_apply')
        row.addWidget(pen, 0, Qt.AlignmentFlag.AlignTop)
        self.take_over = pen
        state = {'editing': False}

        def sync(_r=None):
            if _valid(pen) and state['editing']:
                pen.setEnabled(f.ok)

        def stop(save: bool):
            state['editing'] = False
            if not save:
                e.setText(current)
            e.setReadOnly(True)
            repolish(e)
            pen.set_icon('edit', 'text')
            pen.setToolTip(texts.ENDPOINT_EDIT)
            pen.setAccessibleName(texts.ENDPOINT_EDIT)
            pen.setEnabled(True)

        def click():
            if not state['editing']:
                state['editing'] = True
                e.setReadOnly(False)
                repolish(e)
                e.setFocus()
                pen.set_icon('checkmark', 'text')
                pen.setToolTip(texts.ENDPOINT_SAVE)
                pen.setAccessibleName(texts.ENDPOINT_SAVE)
                pen.setEnabled(f.ok)
            elif f.ok:
                value = e.text().strip()
                stop(True)
                self.apply.emit('endpoint', value)
        pen.clicked.connect(click)
        f.result_changed.connect(sync)
        e.returnPressed.connect(lambda: pen.click() if state['editing'] and pen.isEnabled() else None)
        self._endpoint_stop = stop
        inner.addLayout(row)
        inner.addWidget(self._note('endpoint'))
        self._error_line(inner, 'endpoint')

    def _port_combo(self, name: str, heading: str, choices, current) -> QComboBox:
        cb = QComboBox()
        cb.setObjectName(f'settings_{name}')
        cb.setAccessibleName(heading)
        cb.addItem(texts.PORT_CHOOSE)
        for p in choices:
            cb.addItem(p.label, p.port)
        idx = cb.findData(current) if current else -1
        if idx > 0:
            cb.setCurrentIndex(idx)
        return cb

    def _build_ports(self, body, c) -> None:
        box, inner = section(texts.SETTINGS_PORTS, texts.SETTINGS_PORTS_NOTE)
        box.setObjectName('settings_ports')
        head = box.layout().itemAt(0).layout()
        rescan = IconButton('arrow_sync', texts.RESCAN_PORTS_TIP, name='settings_rescan')
        rescan.clicked.connect(lambda: self.action.emit('settings_rescan'))
        head.addWidget(rescan, 0, Qt.AlignmentFlag.AlignVCenter)
        direct = c.route_mode == 'uart_direct'
        if not direct:
            if self.locked or 'port_pair' not in self.check_fns or not self.ports:
                inner.addWidget(field('Brückenseite', c.bridge_port or texts.NOT_SET))
                inner.addWidget(field('GSVmulti-Seite', c.gsv_port or texts.NOT_SET))
                if not self.locked and not self.ports:
                    inner.addWidget(label(texts.NO_PORTS, 'caption_strong'))
            else:
                editor = QWidget()
                el = QVBoxLayout(editor)
                el.setContentsMargins(0, 0, 0, 0)
                el.setSpacing(4)
                a = self._port_combo('bridge_port', texts.PORT_BRIDGE, self.ports, c.bridge_port)
                g = self._port_combo('gsv_port', texts.PORT_GSV, self.ports, c.gsv_port)
                for lab, tip, cb in ((texts.PORT_BRIDGE, texts.PORT_BRIDGE_TIP, a), (texts.PORT_GSV, texts.PORT_GSV_TIP, g)):
                    cb.setToolTip(tip)
                    el.addWidget(label(lab, 'caption'))
                    el.addWidget(cb)
                cur = (c.bridge_port, c.gsv_port)

                def value():
                    pair = (a.currentData(), g.currentData())
                    return pair if all(pair) and pair != cur else None     # auch „gleicher Port“: err, kein stilles Übernehmen
                f = self._field(editor, 'port_pair', value)
                for cb in (a, g):
                    cb.currentIndexChanged.connect(lambda _i, f=f: f.schedule(immediate=True))
                f.result_changed.connect(lambda r, f=f: self._applied('ports', f, f.value()))
                inner.addWidget(f)
                inner.addWidget(self._note('ports'))
                self._error_line(inner, 'ports')
        if direct or c.route_mode == 'uart_bridge' or c.adapter_port:
            if self.locked or 'adapter' not in self.check_fns or not self.adapters:
                inner.addWidget(field('USB-Adapter', c.adapter_port or texts.NOT_SET))
                if not self.locked and not self.adapters:
                    inner.addWidget(label(texts.NO_ADAPTER, 'caption_strong'))
            else:
                cb = self._port_combo('adapter', texts.ADAPTER, self.adapters, c.adapter_port)
                ids = {p.port: (p.device_id or p.port) for p in self.adapters}
                cur = c.adapter_port

                def avalue():
                    port = cb.currentData()
                    return port if port and port != cur else None
                f = self._field(cb, 'adapter', avalue, label=texts.ADAPTER)
                f.result_changed.connect(lambda r, f=f: self._applied('adapter', f, ids.get(f.value())))
                inner.addWidget(f)
                inner.addWidget(self._note('adapter'))
                self._error_line(inner, 'adapter')
        if c.uart_baud and not direct:
            inner.addWidget(field('Rate UART Pi ↔ Brücke', f'{c.uart_baud} Baud', copy=False))
        if c.gsv_baud:      # eigener Bezeichner: „GSVmulti-Seite“ ist schon der Port
            inner.addWidget(field('Rate GSVmulti-Seite', f'{c.gsv_baud} Baud', copy=False))
        body.addWidget(box)

    def _applied(self, kind: str, f: ValidatedField, value) -> None:
        """Bestandene Prüfung (ok oder warn) übernimmt sofort; ein Fehler übernimmt nichts."""
        if f.accepted and value is not None:
            self.apply.emit(kind, value)

    def _build_session(self, body, c) -> None:
        box, inner = section(texts.SETTINGS_SESSION, texts.SESSION_WHAT)
        box.setObjectName('settings_session')
        port = session_mode_port(c)
        st = self.session
        exp = st.export if st.state == 'done' else None
        path = str(exp.path) if exp is not None else None
        if st.state == 'saving':
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(ProgressRing(16))
            row.addWidget(label(texts.SESSION_SAVING, 'caption'), 1)
            inner.addLayout(row)
        else:
            items = checklist_items(port, path, bool(exp is not None and exp.record_hidden_required))
            states = {'record_hidden_ok': path in self.record_hidden_confirmed,
                      'autoscale_ok': f'autoscale_ok|{path}' in self.checklist_done,
                      'open_ok': f'open_ok|{path}' in self.checklist_done}
            panel = SessionPanel(port=exp.port if exp is not None else port, path=path,
                                 single_channel=bool(texts.single_channel_warning(c)), items=items, states=states,
                                 show_port=False)
            panel.action.connect(self.action)
            panel.toggled.connect(lambda key, on, p=path: self._checklist_toggled(key, on, p))
            self.panel = panel
            inner.addWidget(panel)
        if st.state == 'failed':
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(StateIcon('err', 16), 0, Qt.AlignmentFlag.AlignTop)
            title, text = texts.explain_code(st.code)
            row.addWidget(label(f'{texts.SESSION_FAILED} – {title}', 'caption_strong'), 1)
            row.addWidget(InfoIcon(text, f'Erklärung {title}'), 0, Qt.AlignmentFlag.AlignTop)
            inner.addLayout(row)
        body.addWidget(box)

    def _checklist_toggled(self, key: str, on: bool, path: str | None) -> None:
        if key == 'record_hidden_ok':
            (self.record_hidden_confirmed.add if on else self.record_hidden_confirmed.discard)(path)
        else:
            (self.checklist_done.add if on else self.checklist_done.discard)(f'{key}|{path}')


def _valid(obj) -> bool:
    try:
        import shiboken6
        return shiboken6.isValid(obj)
    except Exception:
        return True


__all__ = ['ascii_name_part', 'SessionState', 'SettingsWindow', 'session_default_name', 'session_mode_port']
