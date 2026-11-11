"""Einstellungen-Fenster (UX2): Weg · Pi · Ports · GSVmulti-Session · Protokolle · Über.

Werte stehen als CopyField. Endpunkt, Portpaar und Adapter werden mit ``ValidatedField`` echt geprüft
und erst nach bestandener Prüfung über die vorhandenen Controller-Methoden übernommen; „Gespeichert“
bestätigt es. Während einer Übertragung sind Weg, Pi und Ports schreibgeschützt (Schloss + Grund).
"""
from __future__ import annotations

import string
import time
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from . import texts, theme
from .tool_windows import ToolWindow, field, label, note_line, section
from .widgets import CopyField, IconButton, ProgressRing, SavedNote, StateIcon, ValidatedField, button, run_now


@dataclass
class SessionState:
    """Ergebnis von „Session-Datei erzeugen …“ (Laufzeit, gehört dem Hauptfenster)."""
    state: str = 'idle'              # idle | saving | done | failed
    export: object | None = None     # SessionExport
    code: str | None = None          # AppError-Code bei failed


def lock_row(reason: str = texts.SETTINGS_LOCKED) -> QWidget:
    w = QWidget()
    w.setObjectName('settings_lock')
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    ic = QLabel()
    ic.setFixedSize(16, 16)
    ic.setPixmap(theme.icon_pixmap('lock_closed', 'text2', 16))
    ic.setAccessibleName('Gesperrt')
    lay.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
    lay.addWidget(label(reason, 'caption'), 1)
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


def record_hidden_box(path: str, confirmed: set, on_change=None) -> QWidget:
    """Pflichtschritt in GSVmulti (steht nicht in der Session): Achtung, nicht wegklickbar, nie grün.
    Der Haken ist eine Bedienerbestätigung, kein Beleg."""
    w = QFrame()
    w.setObjectName('record_hidden')
    w.setProperty('bar', True)
    w.setProperty('kind', 'warn')
    lay = QVBoxLayout(w)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(8)
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(StateIcon('warn', 16), 0, Qt.AlignmentFlag.AlignTop)
    row.addWidget(label(texts.RECORD_HIDDEN), 1)
    lay.addLayout(row)
    crow = QHBoxLayout()
    crow.setContentsMargins(26, 0, 0, 0)
    crow.setSpacing(8)
    cb = QCheckBox()
    cb.setObjectName('record_hidden_ok')
    cb.setAccessibleName(texts.RECORD_HIDDEN_OK)
    cb.setChecked(path in confirmed)

    def toggled(on):
        (confirmed.add if on else confirmed.discard)(path)
        if on_change:
            on_change(on)
    cb.toggled.connect(toggled)
    crow.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
    lab = label(texts.RECORD_HIDDEN_OK)
    lab.mousePressEvent = lambda e: cb.toggle()
    crow.addWidget(lab, 1)
    lay.addLayout(crow)
    return w


class SettingsWindow(ToolWindow):
    action = Signal(str)                 # open_modes | change_setup | export_diagnostics | make_session | …
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
        self.errors: dict[str, str] = {}
        self._saved_until: dict[str, float] = {}
        self.fields: dict[str, ValidatedField] = {}
        self.notes: dict[str, SavedNote] = {}
        self.auto_box: QCheckBox | None = None
        self.take_over: QWidget | None = None

    def bind(self, check_fns: dict, runner, confirmed: set) -> None:
        self.check_fns, self.runner, self.record_hidden_confirmed = dict(check_fns), runner, confirmed

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
        key = ('settings', ctx.route_mode, ctx.route, locked, ctx.pi_name, ctx.pi_id, ctx.endpoint, ctx.fingerprint,
               ctx.auto_connect, len(ctx.paired) > 1, ctx.bridge_port, ctx.gsv_port, ctx.adapter_port,
               ctx.adapter_present, ctx.uart_baud, ctx.gsv_baud, ctx.version, ctx.channel, ctx.protocol, ctx.run_id,
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
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label(title, 'caption_strong'))
        col.addWidget(label(text, 'caption'))
        row.addLayout(col, 1)
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
        self._build_way(body, c)
        self._build_pi(body, c)
        self._build_ports(body, c)
        self._build_session(body, c)
        box, inner = section(texts.SETTINGS_LOGS)
        inner.addWidget(label(texts.SETTINGS_LOGS_TEXT, 'caption'))
        b = button(texts.SETTINGS_LOGS_BUTTON, name='settings_export')
        b.setIcon(theme.icon('document_arrow_down', 'text', 16))
        b.clicked.connect(lambda: self.action.emit('export_diagnostics'))
        inner.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(box)
        box, inner = section(texts.SETTINGS_ABOUT)
        inner.addWidget(field('Version', c.version or '–'))
        if c.channel:
            inner.addWidget(field('Kanal', c.channel, copy=False))
        inner.addWidget(field('Protokoll', c.protocol or '–'))
        if c.run_id:
            inner.addWidget(field('Lauf-ID', c.run_id))
        inner.addWidget(label(texts.ICON_CREDIT, 'caption'))
        body.addWidget(box)

    def _build_way(self, body, c) -> None:
        box, inner = section(texts.SETTINGS_WAY)
        box.setObjectName('settings_way')
        if self.locked:
            inner.addWidget(lock_row(texts.SETTINGS_LOCKED_SHORT))
        row = QHBoxLayout()
        row.setSpacing(8)
        mode = c.route_mode
        if mode in texts.MODE_TEXT:
            ic = QLabel()
            ic.setFixedSize(20, 20)
            ic.setPixmap(theme.icon_pixmap(texts.MODE_ICON[mode], 'text', 20))
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            name, text = texts.mode_text(mode, c)
        else:
            name, text = texts.MODE_NONE, texts.NOT_SET_UP_NO_WAY
        row.addWidget(label(name, 'body_strong'), 1)
        inner.addLayout(row)
        inner.addWidget(label(text, 'caption'))
        b = button(texts.SETTINGS_CHOOSE_WAY, name='settings_modes')
        b.clicked.connect(lambda: self.action.emit('open_modes'))
        ch = button(texts.CHANGE_SETUP, name='settings_change_setup')
        ch.clicked.connect(lambda: self.action.emit('change_setup'))
        for x in (b, ch):                          # untereinander: passt auch bei 360 px ohne Abschneiden
            x.setEnabled(not self.locked)
            if self.locked:
                x.setToolTip(texts.REASON_TRANSMISSION_FIRST)
            inner.addWidget(x, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(box)

    def _build_pi(self, body, c) -> None:
        box, inner = section(texts.SETTINGS_PI)
        box.setObjectName('settings_pi')
        if c.route_mode == 'uart_direct':
            inner.addWidget(label(texts.SETTINGS_DIRECT_PI, 'caption'))
            body.addWidget(box)
            return
        if self.locked:
            inner.addWidget(lock_row(texts.SETTINGS_LOCKED_SHORT))
        inner.addWidget(field('Name', c.pi_name or '–', copy=False))
        inner.addWidget(field('Pi-ID', c.pi_id or '–'))
        editable = (not self.locked and c.pi_name and c.route_mode in (None, 'network')
                    and 'endpoint' in self.check_fns)
        if editable:
            e = QLineEdit(c.endpoint or '')
            e.setObjectName('settings_endpoint_edit')
            e.setAccessibleName(texts.SETTINGS_ENDPOINT)
            current = c.endpoint or ''
            f = self._field(e, 'endpoint', lambda: (e.text().strip() if e.text().strip() != current else None),
                            label=texts.SETTINGS_ENDPOINT)
            inner.addWidget(f)
            row = QHBoxLayout()
            row.setSpacing(8)
            take = button(texts.SETTINGS_TAKE_OVER, name='settings_endpoint_apply')
            take.setEnabled(False)
            take.clicked.connect(lambda: f.ok and self.apply.emit('endpoint', e.text().strip()))
            f.result_changed.connect(lambda _r: take.setEnabled(f.ok) if _valid(take) else None)
            e.returnPressed.connect(lambda: take.click() if take.isEnabled() else None)
            self.take_over = take
            row.addWidget(take)
            row.addWidget(self._note('endpoint'))
            row.addStretch(1)
            inner.addLayout(row)
            self._error_line(inner, 'endpoint')
        else:
            inner.addWidget(field('Endpunkt', c.endpoint or '–'))
        inner.addWidget(field('TLS-Fingerabdruck (SHA-256)', c.fingerprint or '–'))
        if c.pi_name:
            row = QHBoxLayout()
            row.setSpacing(8)
            cb = QCheckBox()
            cb.setObjectName('auto_connect')
            text_ = texts.AUTO_CONNECT.format(pi=c.pi_name)
            cb.setAccessibleName(text_)
            cb.setChecked(c.auto_connect)
            cb.toggled.connect(lambda on: self.action.emit('auto_connect:' + ('on' if on else 'off')))
            row.addWidget(cb, 0, Qt.AlignmentFlag.AlignTop)
            lab = label(text_)
            lab.mousePressEvent = lambda e: cb.toggle()
            row.addWidget(lab, 1)
            inner.addLayout(row)
            note = self._note('auto')
            note.layout().setContentsMargins(28, 0, 0, 0)
            inner.addWidget(note)
            self.auto_box = cb
        if len(c.paired) > 1:
            b = button(texts.PAIRED_TITLE + ' …', name='show_paired')
            b.clicked.connect(lambda: self.action.emit('show_paired'))
            inner.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        body.addWidget(box)

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
        box, inner = section(texts.SETTINGS_PORTS)
        box.setObjectName('settings_ports')
        title_row = box.layout().itemAt(0).widget()
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        box.layout().removeWidget(title_row)
        head.addWidget(title_row, 1)
        rescan = IconButton('arrow_sync', texts.RESCAN_PORTS_TIP, name='settings_rescan')
        rescan.clicked.connect(lambda: self.action.emit('settings_rescan'))
        head.addWidget(rescan, 0, Qt.AlignmentFlag.AlignVCenter)
        box.layout().insertLayout(0, head)
        direct = c.route_mode == 'uart_direct'
        if self.locked:
            inner.addWidget(lock_row(texts.SETTINGS_LOCKED_SHORT))
        if not direct:
            if self.locked or 'port_pair' not in self.check_fns or not self.ports:
                inner.addWidget(field('Brückenseite', c.bridge_port or texts.NOT_SET))
                inner.addWidget(field('GSVmulti-Seite', c.gsv_port or texts.NOT_SET))
                if not self.locked and not self.ports:
                    inner.addWidget(label(texts.NO_PORTS, 'caption'))
            else:
                editor = QWidget()
                el = QVBoxLayout(editor)
                el.setContentsMargins(0, 0, 0, 0)
                el.setSpacing(4)
                a = self._port_combo('bridge_port', texts.PORT_BRIDGE, self.ports, c.bridge_port)
                g = self._port_combo('gsv_port', texts.PORT_GSV, self.ports, c.gsv_port)
                for lab, cb in ((texts.PORT_BRIDGE, a), (texts.PORT_GSV, g)):
                    el.addWidget(label(lab, 'caption'))
                    el.addWidget(cb)
                cur = (c.bridge_port, c.gsv_port)

                def value():
                    pair = (a.currentData(), g.currentData())
                    return pair if all(pair) and pair[0] != pair[1] and pair != cur else None
                f = self._field(editor, 'port_pair', value)
                for cb in (a, g):
                    cb.currentIndexChanged.connect(lambda _i, f=f: f.schedule(immediate=True))
                f.result_changed.connect(lambda r, f=f: self._applied('ports', f, f.value()))
                inner.addWidget(f)
                inner.addWidget(self._note('ports'))
                self._error_line(inner, 'ports')
                inner.addWidget(label(texts.SETTINGS_PORTS_NOTE, 'caption'))
        if direct or c.route_mode == 'uart_bridge' or c.adapter_port:
            if self.locked or 'adapter' not in self.check_fns or not self.adapters:
                inner.addWidget(field('USB-Adapter', c.adapter_port or texts.NOT_SET))
                if not self.locked and not self.adapters:
                    inner.addWidget(label(texts.NO_ADAPTER, 'caption'))
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
            inner.addWidget(field('UART Pi ↔ Brücke', f'{c.uart_baud} Baud', copy=False))
        if c.gsv_baud:
            inner.addWidget(field('GSVmulti-Seite (Session)', f'{c.gsv_baud} Baud', copy=False))
        body.addWidget(box)

    def _applied(self, kind: str, f: ValidatedField, value) -> None:
        """Bestandene Prüfung (ok oder warn) übernimmt sofort; ein Fehler übernimmt nichts."""
        if f.accepted and value is not None:
            self.apply.emit(kind, value)

    def _build_session(self, body, c) -> None:
        box, inner = section(texts.SETTINGS_SESSION)
        box.setObjectName('settings_session')
        port = session_mode_port(c)
        inner.addWidget(label(texts.SESSION_WHAT, 'caption'))
        warn = texts.single_channel_warning(c)
        if warn:
            inner.addWidget(note_line('warn', warn, 'single_channel_warning'))
        inner.addWidget(field(texts.SESSION_PORT, port or texts.NOT_SET, copy=bool(port)))
        if c.gsv_baud:
            inner.addWidget(field('Übertragung', texts.baud_text(c.gsv_baud), copy=False))
        s = self.session
        if s.state == 'saving':
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(ProgressRing(16))
            row.addWidget(label(texts.SESSION_SAVING, 'caption'), 1)
            inner.addLayout(row)
        elif s.state == 'done' and s.export is not None:
            row = QHBoxLayout()
            row.setSpacing(8)
            ic = QLabel()
            ic.setObjectName('session_done_icon')
            ic.setPixmap(theme.icon_pixmap('checkmark', 'text', 16))      # erzeugt ≠ abgenommen: nie grün
            ic.setAccessibleName(texts.SCREEN_READER['info'])
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label(texts.SESSION_DONE, 'body_strong'), 1)
            inner.addLayout(row)
            path = str(s.export.path)
            inner.addWidget(CopyField(texts.SESSION_PATH, path))
            inner.addWidget(label(texts.SESSION_NOT_ACCEPTED, 'caption'))
            if s.export.record_hidden_required:
                inner.addWidget(record_hidden_box(path, self.record_hidden_confirmed))
            hint = texts.autoscale_hint(s.export.port)
            if hint:
                inner.addWidget(note_line('info', hint, 'autoscale_hint'))
            ob = button(texts.OPEN_FOLDER, name='settings_open_folder')
            ob.setIcon(theme.icon('folder_open', 'text', 16))
            ob.clicked.connect(lambda: self.action.emit('open_folder:' + str(s.export.path.parent)))
            inner.addWidget(ob, 0, Qt.AlignmentFlag.AlignLeft)
            inner.addWidget(label(texts.SESSION_HOWTO.format(port=s.export.port), 'caption'))
        elif s.state == 'failed':
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(StateIcon('err', 16), 0, Qt.AlignmentFlag.AlignTop)
            title, text = texts.explain_code(s.code)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(label(f'{texts.SESSION_FAILED} – {title}', 'caption_strong'))
            col.addWidget(label(text, 'caption'))
            row.addLayout(col, 1)
            inner.addLayout(row)
        b = button(texts.SESSION_AGAIN if s.state == 'done' else texts.SESSION_MAKE, name='settings_make_session')
        b.setEnabled(bool(port) and s.state != 'saving')
        if not port:
            b.setToolTip(texts.SESSION_NO_PORT)
        b.clicked.connect(lambda: self.action.emit('make_session'))
        inner.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        if not port:
            inner.addWidget(label(texts.SESSION_NO_PORT, 'caption'))
        body.addWidget(box)


def _valid(obj) -> bool:
    try:
        import shiboken6
        return shiboken6.isValid(obj)
    except Exception:
        return True


__all__ = ['ascii_name_part', 'SessionState', 'SettingsWindow', 'record_hidden_box', 'session_default_name', 'session_mode_port']
