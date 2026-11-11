"""Hauptfenster, Tray und Controller-Anbindung."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from . import texts, theme
from .mode_window import ModesWindow
from .port import ControllerPort
from .settings_window import SessionState, SettingsWindow, session_default_name, session_mode_port
from .setup_view import SetupView
from .status_view import StatusView
from .tool_windows import ExportWindow, InfoContent, ToolWindow, build_chip_detail, build_lock, build_paired
from .widgets import button, fade_in

REFRESH_INTERVAL_MS = 200
FIRST_RUN_ENV = 'DISPREAD_UI_FIRST_RUN_MODES'     # "0": Moduswahl beim ersten Start nicht selbst öffnen (Tests)
CHECKS = {'endpoint': 'check_endpoint', 'port_pair': 'check_port_pair', 'adapter': 'check_adapter',
          'pairing_code': 'check_pairing_code'}


class _EventBridge(QObject):
    """Wohnt im GUI-Thread; Signal aus dem Workerthread wird queued zugestellt."""
    event = Signal(object)


class _TaskSignals(QObject):
    """Wohnt im GUI-Thread. Der Rückruf läuft über einen Slot dieses Objekts, damit Qt
    ihn in den GUI-Thread zustellt (ein nacktes Lambda liefe im Workerthread)."""
    done = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.callback = None
        self.done.connect(self._relay)

    @Slot(object, object)
    def _relay(self, result, exc):
        if self.callback:
            self.callback(result, exc)


class _Task(QRunnable):
    def __init__(self, fn, args, signals):
        super().__init__()
        self.setAutoDelete(False)
        self.fn, self.args, self.signals = fn, args, signals
    def run(self):
        try:
            result, exc = self.fn(*self.args), None
        except Exception as e:  # Fehlertext nie anzeigen (Zugangsdaten), nur Klasse
            result, exc = None, e
        self.signals.done.emit(result, exc)


class ExitDialog(QDialog):
    def __init__(self, text: str, parent=None, transmitting: bool = True):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True)
        self.confirmed = False
        self.setProperty('card', True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        title = QLabel(texts.EXIT_TITLE)
        title.setProperty('subtitle', True)
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        lay.addWidget(title)
        lay.addWidget(self.text_label)
        row = QHBoxLayout()
        row.addStretch(1)
        self.quit_button = button(texts.EXIT_QUIT, name='exit_quit')
        self.keep_button = button(texts.EXIT_KEEP if transmitting else texts.EXIT_CANCEL, True, name='exit_keep')
        self.keep_button.setDefault(True)
        row.addWidget(self.quit_button)
        row.addWidget(self.keep_button)
        lay.addLayout(row)
        self.keep_button.clicked.connect(self.reject)
        self.quit_button.clicked.connect(self._quit)
        self.setFixedWidth(360)
        self.keep_button.setFocus()

    def _quit(self):
        self.confirmed = True
        self.accept()


class MainWindow(QWidget):
    def __init__(self, controller: ControllerPort, dark: bool | None = None, first_run_modes: bool | None = None):
        super().__init__()
        self.controller = controller
        theme.apply_theme(QApplication.instance(), dark)
        self.setObjectName('root')
        self.setWindowTitle(texts.APP_TITLE)
        self.resize(440, 720)
        self.setMinimumSize(380, 560)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(4)          # Prüfungen (≤ 3 s) dürfen Aktionen nicht aufhalten
        self._tasks: set = set()
        self.status_view, self.setup_view = StatusView(), SetupView()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.status_view)
        self.stack.addWidget(self.setup_view)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self._really_closing = False
        self.tray_hint_count = 0
        self.tray_state = 'normal'
        self._tray_tip = ''
        self.on_event_hook = None
        self.confirm_exit = self._confirm_exit_dialog
        self.confirm_disconnect = self._confirm_disconnect_dialog
        self.pick_file = lambda: QFileDialog.getOpenFileName(self, 'Profil öffnen', '', 'Profil (*.dispread)')[0]
        self.pick_folder = lambda: QFileDialog.getExistingDirectory(self, 'Ordner für die Session')
        self.pick_save = lambda: QFileDialog.getSaveFileName(
            self, texts.EXPORT_DIALOG, f'GSVmulti-Bruecke-Protokolle-{time.strftime("%Y%m%d-%H%M")}.zip',
            'ZIP (*.zip)')[0]
        self.open_folder = lambda path: QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.pick_session = lambda name: QFileDialog.getSaveFileName(
            self, texts.SESSION_DIALOG, name, 'GSVmulti-Session (*.ucf)')[0]
        # UX2 Runde 2: Moduswahl, Einstellungen, Prüfungen, Session
        self.first_run_modes = (os.environ.get(FIRST_RUN_ENV, '1').strip() != '0') if first_run_modes is None \
            else first_run_modes
        self._first_run_checked = False
        self._modes = None
        self._modes_key = None
        self.port_choices: tuple = ()
        self.adapter_choices: tuple = ()
        self.session_state = SessionState()
        self.record_hidden_confirmed: set[str] = set()
        self.setup_view.bind(self.check_fns(), self._run)
        self.setup_view.record_hidden_confirmed = self.record_hidden_confirmed
        self._ports: dict[str, str] = {}
        self.setAcceptDrops(True)
        self.unhandled: list[str] = []
        for v in (self.status_view, self.setup_view):
            v.action.connect(self.do_action)
            v.lock_clicked.connect(lambda: QTimer.singleShot(0, self._show_lock))
            v.switch_clicked.connect(lambda: QTimer.singleShot(0, self._show_switch))
        self.status_view.chip_clicked.connect(self._show_chip)
        self.tool_windows: dict[str, ToolWindow] = {}
        self._info: InfoContent | None = None
        self._bridge = _EventBridge(self)
        self._bridge.event.connect(self._on_event, Qt.ConnectionType.QueuedConnection)
        # Ereignisse koaleszieren: hoechstens ein refresh() je REFRESH_INTERVAL_MS.
        self._refresh_dirty = False
        self._refresh_count = 0
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self._flush_refresh)
        self._unsubscribe = controller.subscribe(self._bridge.event.emit)
        self._build_tray()
        self._ticking = False
        self._tick = QTimer(self)                  # Countdowns (Backoff, Code) ticken sekündlich
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()
        self.refresh()

    def _on_tick(self) -> None:
        if self._ticking and not self._refresh_timer.isActive():
            self.refresh()

    def auto_connect_at_start(self) -> None:
        """Einmal nach dem Start: verbindet nur, wenn der Controller es erlaubt (gleicher Pi, Weg, Endpunkt)."""
        self._call(self.controller.auto_connect_at_start)

    # ---------------------------------------------------------------- Tray
    def _build_tray(self) -> None:
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(theme.tray_icon('normal'), self)
        menu = QMenu()
        a_open = QAction('Öffnen', menu)
        a_open.triggered.connect(self.restore)
        a_quit = QAction('Brücke beenden…', menu)
        a_quit.triggered.connect(self.exit_bridge)
        menu.addAction(a_open)
        menu.addAction(a_quit)
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.restore() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def tray_tooltip(self) -> str:
        return self._tray_tip

    def restore(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ---------------------------------------------------------------- Zustand
    def _locked(self, ctx, worker) -> bool:
        return bool(ctx.switch_locked or (worker is not None and worker.active))

    def check_fns(self) -> dict:
        """Echte Prüfungen des Controllers (laufen im Pool); fehlt eine, entfällt die Statusanzeige."""
        return {k: getattr(self.controller, m) for k, m in CHECKS.items() if hasattr(self.controller, m)}

    def configured(self, c) -> bool | None:
        """Ist der aktive Weg fertig eingerichtet? None = unbekannt (Moduswahl noch nicht gelesen)."""
        if self._modes is None:
            return None
        if c.route_mode is None:
            return False
        return next((m.configured for m in self._modes if m.mode == c.route_mode), None)

    def refresh(self) -> None:
        self._refresh_count += 1
        r, w, c = self.controller.snapshot(), self.controller.worker_status(), self.controller.context()
        locked = self._locked(c, w)
        self.status_view.update_from(r, w, c, locked, configured=self.configured(c))
        before = self.stack.currentWidget()
        if c.setup is not None and c.mode == 'setup':
            self.setup_view.update_from(r, w, c, locked)
            self.stack.setCurrentWidget(self.setup_view)
        else:
            self.stack.setCurrentWidget(self.status_view)
        if self.stack.currentWidget() is not before:
            fade_in(self.stack.currentWidget())
        self._refresh_tool_windows(r, w, c, locked)
        self._fetch_modes(c, locked)
        self._ticking = c.retry_in_s is not None or c.code_remaining_s is not None
        h = texts.headline(r, w, c)
        self.tray_state = {'err': 'err', 'warn': 'warn'}.get(h.tone, 'normal')
        self._tray_tip = h.text
        if self.tray is not None:
            self.tray.setIcon(theme.tray_icon(self.tray_state))
            self.tray.setToolTip(h.text)

    def _on_event(self, event) -> None:
        assert threading.current_thread() is threading.main_thread() or QApplication.instance().thread() is \
            self.thread()
        if self.on_event_hook:
            self.on_event_hook(event)
        # Das Journal fuehrt der Controller (verdichtet, begrenzt); refresh() liest es.
        if self._refresh_timer.isActive():
            self._refresh_dirty = True        # nur markieren, der Timer zeichnet nach
            return
        self.refresh()
        self._refresh_timer.start()

    def _flush_refresh(self) -> None:
        if self._refresh_dirty:
            self._refresh_dirty = False
            self.refresh()
            self._refresh_timer.start()

    # ---------------------------------------------------------------- Aktionen
    def _run(self, fn, args, done) -> None:
        """Controller-Aufruf im Pool ohne Neuzeichnen (Prüfungen); ``done(result, exc)`` im GUI-Thread."""
        sig = _TaskSignals()
        task = _Task(fn, tuple(args), sig)
        self._tasks.add(sig)
        sig.task = task

        def finished(result, exc):
            QTimer.singleShot(0, lambda: self._tasks.discard(sig))   # nicht im eigenen Signal zerstören
            done(result, exc)
        sig.callback = finished
        self.pool.start(task)

    def _call(self, fn, *args, done=None) -> None:
        def finished(result, exc):
            if done:
                done(result, exc)
            self.refresh()
            if exc is not None and self.stack.currentWidget() is self.setup_view:
                QTimer.singleShot(0, self.setup_view.focus_error)
        self._run(fn, args, finished)

    def _mode(self) -> str:
        c = self.controller.context()
        if c.route_mode in ('uart_bridge', 'network'):
            return 'uart' if c.route_mode == 'uart_bridge' else 'network'
        route = c.route or ''
        return 'uart' if route.startswith('UART') else 'network'

    def do_action(self, aid: str) -> None:
        c, ctl = self.controller.context(), self.controller
        if aid in ('connect', 'reconnect', 'next_connect'):
            self._call(ctl.connect, self._mode(), None)
        elif aid == 'stop_retry':
            self._call(ctl.disconnect)
        elif aid == 'disconnect':
            if self._transmitting() and not self.confirm_disconnect():
                return
            self._call(ctl.disconnect)
        elif aid == 'overview':
            self._call(ctl.setup_step, 'overview')
        elif aid == 'resume_setup':
            self._call(ctl.setup_step, 'resume')
        elif aid == 'install':
            self._call(ctl.install_components)
        elif aid == 'open_profile':
            path = self.pick_file()
            if path:
                self.open_profile_path(path)
        elif aid == 'export_session':
            dest = self.pick_folder()
            if dest:
                self._call(ctl.export_session, {'gsv_port': c.gsv_port}, Path(dest))
        elif aid == 'start_demo_check':
            self._call(ctl.begin_demo_check, self.setup_view.checked('test_session_ok'))
        elif aid == 'export_diagnostics':
            self._show_export()
        elif aid == 'show_paired':
            self._show_switch()
        elif aid == 'pair':
            self._call(ctl.pair, self.setup_view.code_text(), self.setup_view.checked('fp_ok'))
        elif aid == 'next' and self.setup_view.variant and self.setup_view.variant[0] == 'E1manual' \
                and all(self.setup_view.selected_ports()):
            bp, gp = self.setup_view.selected_ports()      # „Weiter“ übernimmt die Auswahl

            def take():
                ctl.set_port_pair(bp, gp)
                ctl.setup_step('next')
            self._call(take)
        elif aid in ('next', 'back'):
            self._call(ctl.setup_step, aid)
        elif aid == 'cancel_connect':
            self._call(ctl.disconnect)
        elif aid == 'change_pair':
            self._call(ctl.open_manual_pair)
        elif aid == 'change_setup':
            self._call(ctl.setup_step, 'change_setup')
        elif aid == 'exit_bridge':
            self.exit_bridge()
        elif aid.startswith('auto_connect:'):
            info = self._info

            def saved(_result, exc):
                if exc is None and info is not None and info is self._info:
                    info.confirm_saved()
                win = self.tool_windows.get('settings')
                if exc is None and win is not None:
                    win.mark_saved('auto')
            self._call(ctl.set_auto_connect, aid.endswith(':on'), done=saved)
        elif aid.startswith('switch_pi:'):
            self._call(ctl.switch_pi, aid.split(':', 1)[1])
        elif aid.startswith('code_show:'):
            pass
        elif aid in ('goto_pairing', 'new_code'):
            self._call(ctl.setup_step, 'pairing')
        elif aid == 'manual_pair':
            self._call(ctl.open_manual_pair)
        elif aid == 'set_port_pair':
            self._call(ctl.set_port_pair, *self.setup_view.selected_ports())
        elif aid == 'rescan':
            self.setup_view.set_searching(True)

            def searched(_r, _e):
                self.setup_view.set_searching(False)
                self._fetch_ports()
            self._call(ctl.rescan, done=searched)
        elif aid in ('list_ports', 'settings_rescan'):
            self._fetch_ports(refresh=True)
        elif aid == 'entry:manual_endpoint':
            text = self.setup_view.endpoint_text()
            if text:
                self._call(ctl.select_endpoint, text, True)
        elif aid.startswith('session_ok:'):
            self._call(ctl.confirm_session, aid.endswith(':on'))
        elif aid.startswith('radio:'):
            self._radio(aid)
        elif aid.startswith(('fp_ok:', 'test_session_ok:', 'record_hidden_ok:')):
            pass                          # reine Freigabefelder der Oberfläche (Knopf-Gate)
        elif aid == 'details':
            self._show_details()
        elif aid == 'recheck' or aid == 'recheck_adapter':
            self._call(lambda: None)      # liest den Zustand neu; der Controller meldet über subscribe
        elif aid == 'open_modes':
            self._show_modes()
        elif aid == 'open_settings':
            self._show_settings()
        elif aid == 'leave_setup':
            self._call(ctl.leave_setup)
        elif aid == 'start_setup':
            if c.route_mode is None:
                self._show_modes()        # erst den Weg wählen
            else:
                self._call(ctl.setup_step, 'resume')
        elif aid == 'make_session':
            self._make_session()
        elif aid.startswith('open_session_folder:'):
            self.open_folder(str(Path(aid.split(':', 1)[1]).parent))
        elif aid.startswith('open_folder:'):
            self.open_folder(aid.split(':', 1)[1])
        else:
            self.unhandled.append(aid)

    def _radio(self, aid: str) -> None:
        _, name, idx = aid.split(':')
        idx, ctl = int(idx), self.controller
        if name == 'way':
            self._call(ctl.select_route, ('network', 'uart')[idx])
            return
        setup = ctl.context().setup
        ids = ((setup.data.get('choices') or {}).get(name) or ()) if setup else ()
        if idx >= len(ids):
            return
        if name == 'found':
            self._call(ctl.select_endpoint, ids[idx], False)
        elif name == 'adapter':
            self._call(ctl.select_adapter, ids[idx])
        elif name in ('bridge_port', 'gsv_port'):
            self._ports[name] = ids[idx]

    def open_profile_path(self, path: str) -> None:
        """Profil aus Datei (Dialog, Drag&Drop, Dateizuordnung); der Kern prüft strikt."""
        def read() -> bytes:
            try:
                with open(path, 'rb') as f:
                    return f.read(256 * 1024 + 1)
            except OSError:
                return b''
        self._call(lambda: self.controller.load_profile(read()))

    def dragEnterEvent(self, e):
        if any(u.toLocalFile().lower().endswith('.dispread') for u in e.mimeData().urls()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        for u in e.mimeData().urls():
            if u.toLocalFile().lower().endswith('.dispread'):
                self.open_profile_path(u.toLocalFile())
                e.acceptProposedAction()
                return

    # ---------------------------------------------------------------- Werkzeugfenster
    def tool_window(self, kind: str, title: str, cls=ToolWindow) -> ToolWindow:
        """Höchstens eine Instanz je Art; erneutes Öffnen holt das vorhandene Fenster nach vorn."""
        win = self.tool_windows.get(kind)
        if win is None:
            win = cls(self) if cls is not ToolWindow else ToolWindow(kind, title, self)
            self.tool_windows[kind] = win
            if kind == 'chip':
                win.closed.connect(self._chip_window_closed)
        win.setWindowTitle(title)
        return win

    def _chip_window_closed(self) -> None:
        n = self.status_view.open_chip
        self.status_view.mark_open_chip(None)
        if n is not None and self.stack.currentWidget() is self.status_view:
            self.status_view.chips[n].setFocus()

    def _show_chip(self, n: int) -> None:
        win = self.tool_window('chip', self.status_view.chips[n].view.name)
        self._fill_chip(win, n)
        win.present()
        self.status_view.mark_open_chip(n)

    def _fill_chip(self, win: ToolWindow, n: int) -> None:
        view = self.status_view.chips[n].view
        if view is None:
            return
        win.setWindowTitle(f'{view.name} – {texts.APP_TITLE}')
        win.set_content(('chip', view), lambda body: build_chip_detail(view, body, self._tool_action))

    def _tool_action(self, aid: str) -> None:
        self.do_action(aid)

    def _show_lock(self) -> None:
        win = self.tool_window('lock', texts.LOCK_TITLE)
        win.set_content('lock', build_lock)
        win.present()

    def _show_switch(self) -> None:
        win = self.tool_window('paired', texts.PAIRED_TITLE)
        self._fill_paired(win, self.controller.context())
        win.present()

    def _fill_paired(self, win: ToolWindow, c) -> None:
        win.set_content(('paired', c.paired, c.pi_id, c.switch_locked),
                        lambda body: build_paired(c, body, self._tool_action))

    def _show_details(self) -> None:
        win = self.tool_window('info', f'{texts.INFO} – {texts.APP_TITLE}')
        self._fill_info(win, self.controller.context())
        win.present()

    def _info_key(self, c) -> tuple:
        return ('info', c.version, c.channel, c.protocol, c.run_id, c.pi_name, c.pi_id, c.endpoint, c.fingerprint,
                c.paired, c.bridge_port, c.gsv_port, c.adapter_port, c.uart_baud, c.gsv_baud)

    def _fill_info(self, win: ToolWindow, c) -> None:
        def build(body):
            self._info = InfoContent(c, body, self._tool_action)
        win.set_content(self._info_key(c), build)

    def _show_export(self) -> None:
        win = self.tool_window('export', f'{texts.EXPORT_LOGS} – {texts.APP_TITLE}', ExportWindow)
        if not getattr(win, '_wired', False):
            win._wired = True
            win.save_requested.connect(self._export_save)
            win.open_folder.connect(lambda path: self.open_folder(path))
        if win.state != 'saving':
            win.set_state('idle')
        win.present()
        fn = getattr(self.controller, 'diagnostics_contents', None)
        if fn is None:
            win.set_contents(())
            return

        def done(result, exc):
            win.set_contents(() if exc is not None or not result else result)
        self._call(fn, done=done)

    def _export_save(self) -> None:
        win = self.tool_windows.get('export')
        dest = self.pick_save()
        if not dest or win is None:
            return
        win.set_state('saving')
        self.status_view.busy_bar.begin()

        def done(result, exc):
            self.status_view.busy_bar.end()
            if exc is not None:
                win.set_state('failed')
            else:
                win.set_state('done', Path(result) if result else Path(dest))
        self._call(self.controller.export_diagnostics, Path(dest), done=done)

    # ---------------------------------------------------------------- Moduswahl (UX2)
    def _fetch_modes(self, c, locked, force: bool = False) -> None:
        """Moduswahl-Zustand im Pool lesen, wenn sich Weg, Einrichtung oder Sperre geändert haben."""
        fn = getattr(self.controller, 'modes', None)
        if fn is None:
            return
        key = (c.route_mode, c.mode, None if c.setup is None else (c.setup.step, c.setup.variant), locked,
               c.adapter_port, c.adapter_present, c.pi_id, c.endpoint, c.bridge_port, c.gsv_port)
        if key == self._modes_key and not force:
            return
        self._modes_key = key

        def done(result, exc):
            if exc is not None or result is None:
                return
            changed = tuple(result) != self._modes
            self._modes = tuple(result)
            if self.first_run_modes and not self._first_run_checked:
                self._first_run_checked = True
                ctx = self.controller.context()
                if ctx.route_mode is None and not any(m.configured for m in self._modes):
                    self._show_modes()       # erster Start ohne Weg: einmal pro Start
            win = self.tool_windows.get('modes')
            if win is not None and win.isVisible():
                win.set_state(self._modes, self.controller.context(), win.error)
            if changed:
                self.refresh()
        self._run(fn, (), done)

    def _show_modes(self) -> None:
        win = self.tool_window('modes', f'{texts.MODES_TITLE} – {texts.APP_TITLE}', ModesWindow)
        if not getattr(win, '_wired', False):
            win._wired = True
            win.switch_requested.connect(self._select_mode)
            win.change_setup.connect(lambda: (win.close(), self.do_action('change_setup')))
        c = self.controller.context()
        win.set_state(self._modes, c, None)
        win.present()
        self._fetch_modes(c, self._locked(c, self.controller.worker_status()), force=True)

    def _select_mode(self, mode: str) -> None:
        win = self.tool_windows.get('modes')
        if win is not None:
            win.set_busy(True)

        def done(_result, exc):
            self._modes_key = None
            if win is None:
                return
            win.set_busy(False)
            if exc is not None:
                win.set_state(self._modes, self.controller.context(), getattr(exc, 'code', None) or 'unknown_error')
            else:
                win.close()
        self._call(self.controller.select_mode, mode, done=done)

    # ---------------------------------------------------------------- Einstellungen (UX2)
    def _fetch_ports(self, refresh: bool = False) -> None:
        """COM-Ports und USB-Adapter im Pool lesen (Auswahllisten mit Bezeichnung)."""
        ctl = self.controller
        if not hasattr(ctl, 'list_ports'):
            return

        def read():
            ports = tuple(ctl.list_ports())
            adapters = tuple(ctl.list_adapters()) if hasattr(ctl, 'list_adapters') else ()
            return ports, adapters

        def done(result, exc):
            if exc is None and result is not None:
                self.port_choices, self.adapter_choices = result
                self.setup_view.port_labels = {p.port: p.label for p in self.port_choices}
            self.refresh()
        self._run(read, (), done)

    def _show_settings(self) -> None:
        win = self.tool_window('settings', f'{texts.SETTINGS} – {texts.APP_TITLE}', SettingsWindow)
        if not getattr(win, '_wired', False):
            win._wired = True
            win.bind(self.check_fns(), self._run, self.record_hidden_confirmed)
            win.action.connect(self._tool_action)
            win.apply.connect(self._settings_apply)
        self._fill_settings(win, self.controller.context())
        win.present()
        self._fetch_ports()

    def _fill_settings(self, win, c, locked: bool | None = None) -> None:
        if locked is None:
            locked = self._locked(c, self.controller.worker_status())
        win.update_from(c, locked, self.port_choices, self.adapter_choices, self.session_state)

    def _settings_apply(self, kind: str, value) -> None:
        ctl, win = self.controller, self.tool_windows.get('settings')
        fn = {'endpoint': lambda v: ctl.select_endpoint(v, True), 'ports': lambda v: ctl.set_port_pair(*v),
              'adapter': ctl.select_adapter}.get(kind)
        if fn is None:
            return

        def done(_result, exc):
            if win is None:
                return
            if exc is None:
                win.mark_saved(kind)
            else:
                win.show_error(kind, getattr(exc, 'code', None))
        self._call(fn, value, done=done)

    # ---------------------------------------------------------------- Session (UX2)
    def _make_session(self) -> None:
        """Speichern-Dialog, dann ``export_session_file`` im Pool; Ergebnis in Einrichtung und Einstellungen."""
        c = self.controller.context()
        port = session_mode_port(c)
        if not port or self.session_state.state == 'saving':
            return
        dest = self.pick_session(session_default_name(c, port))
        if not dest:
            return
        self.session_state = SessionState('saving')
        self.setup_view.session_busy = True
        self.status_view.busy_bar.begin()
        self.refresh()

        def done(result, exc):
            self.status_view.busy_bar.end()
            self.setup_view.session_busy = False
            if exc is not None or result is None:
                self.session_state = SessionState('failed', None, getattr(exc, 'code', None) or 'session_write_failed')
            else:
                self.session_state = SessionState('done', result)
                self.setup_view.session_export = result
        self._call(self.controller.export_session_file, Path(dest), port, done=done)

    def _refresh_tool_windows(self, r, w, c, locked) -> None:
        """Offene Fenster folgen dem Zustand; neu gebaut wird nur bei geänderten Daten."""
        win = self.tool_windows.get('chip')
        if win is not None and win.isVisible() and self.status_view.open_chip is not None:
            self._fill_chip(win, self.status_view.open_chip)
        win = self.tool_windows.get('paired')
        if win is not None and win.isVisible():
            self._fill_paired(win, c)
        win = self.tool_windows.get('info')
        if win is not None and win.isVisible():
            self._fill_info(win, c)
        win = self.tool_windows.get('lock')
        if win is not None and win.isVisible() and not locked:
            win.close()
        win = self.tool_windows.get('settings')
        if win is not None and win.isVisible():
            self._fill_settings(win, c, locked)
        win = self.tool_windows.get('modes')
        if win is not None and win.isVisible():
            win.set_state(self._modes, c, win.error)

    # ---------------------------------------------------------------- Beenden
    def build_exit_dialog(self) -> ExitDialog:
        c = self.controller.context()
        text = texts.EXIT_TEXT_ACTIVE if (c.release and not c.dut_locked) else texts.EXIT_TEXT_LOCKED
        return ExitDialog(text, self, transmitting=bool(c.release and not c.dut_locked))

    def _confirm_exit_dialog(self) -> bool:
        dlg = self.build_exit_dialog()
        dlg.exec()
        return dlg.confirmed

    def _confirm_disconnect_dialog(self) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, texts.DISCONNECT_TITLE, texts.DISCONNECT_TEXT,
                          QMessageBox.StandardButton.NoButton, self)
        c = self.controller.context()
        keep = box.addButton(texts.EXIT_KEEP if (c.release and not c.dut_locked) else texts.EXIT_CANCEL,
                             QMessageBox.ButtonRole.RejectRole)
        box.addButton('Trennen', QMessageBox.ButtonRole.AcceptRole)
        box.setDefaultButton(keep)
        box.exec()
        return box.clickedButton() is not keep

    def _transmitting(self) -> bool:
        w, r = self.controller.worker_status(), self.controller.snapshot()
        return bool((w is not None and w.active) or r.peer == 'authenticated')

    def exit_bridge(self) -> None:
        """Einziger Weg, die Brücke zu beenden: Tray-Menü oder dieser Aufruf."""
        if self._transmitting() and not self.confirm_exit():
            return

        def done(result, exc):
            if result:
                self.force_close()
                QApplication.instance().quit()
        self._call(self.controller.request_exit, True, done=done)

    def closeEvent(self, e):
        if self._really_closing:
            super().closeEvent(e)
            return
        e.ignore()
        self.hide()      # Schließen = in den Tray; Worker läuft weiter
        if self.tray_hint_count == 0:
            self.tray_hint_count = 1
            if self.tray is not None:
                self.tray.showMessage(texts.TRAY_HINT_TITLE, texts.TRAY_HINT, QSystemTrayIcon.MessageIcon.Information)

    def force_close(self) -> None:
        self._really_closing = True
        try:
            self._unsubscribe()
        except Exception:
            pass
        self.pool.waitForDone(2000)
        for win in self.tool_windows.values():
            win.close()
        if self.tray is not None:
            self.tray.hide()
        self.close()
