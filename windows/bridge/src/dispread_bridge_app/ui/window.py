"""Hauptfenster, Tray und Controller-Anbindung."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction
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
from .port import ControllerPort
from .setup_view import SetupView
from .status_view import Flyout, StatusView
from .widgets import button

REFRESH_INTERVAL_MS = 200


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
    def __init__(self, controller: ControllerPort, dark: bool | None = None):
        super().__init__()
        self.controller = controller
        theme.apply_theme(QApplication.instance(), dark)
        self.setObjectName('root')
        self.setWindowTitle(texts.APP_TITLE)
        self.resize(440, 720)
        self.setMinimumSize(380, 560)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
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
        self.pick_save = lambda: QFileDialog.getSaveFileName(self, 'Diagnose speichern', 'dispread-diagnose.zip',
                                                             'ZIP (*.zip)')[0]
        self._ports: dict[str, str] = {}
        self.setAcceptDrops(True)
        self.unhandled: list[str] = []
        for v in (self.status_view, self.setup_view):
            v.action.connect(self.do_action)
            v.lock_clicked.connect(lambda: QTimer.singleShot(0, self._show_lock))
            v.switch_clicked.connect(lambda: QTimer.singleShot(0, self._show_switch))
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
        self._flyout = None
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

    def refresh(self) -> None:
        self._refresh_count += 1
        r, w, c = self.controller.snapshot(), self.controller.worker_status(), self.controller.context()
        locked = self._locked(c, w)
        self.status_view.update_from(r, w, c, locked)
        if c.setup is not None and c.mode == 'setup':
            self.setup_view.update_from(r, w, c, locked)
            self.stack.setCurrentWidget(self.setup_view)
        else:
            self.stack.setCurrentWidget(self.status_view)
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
    def _call(self, fn, *args, done=None) -> None:
        sig = _TaskSignals()
        task = _Task(fn, args, sig)
        self._tasks.add(sig)
        sig.task = task

        def finished(result, exc):
            QTimer.singleShot(0, lambda: self._tasks.discard(sig))   # nicht im eigenen Signal zerstören
            if done:
                done(result, exc)
            self.refresh()
            if exc is not None and self.stack.currentWidget() is self.setup_view:
                QTimer.singleShot(0, self.setup_view.focus_error)
        sig.callback = finished
        self.pool.start(task)

    def _mode(self) -> str:
        route = self.controller.context().route or ''
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
            dest = self.pick_save()
            if dest:
                self._call(ctl.export_diagnostics, Path(dest))
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
            self._call(ctl.set_auto_connect, aid.endswith(':on'))
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
            self._call(ctl.rescan)
        elif aid == 'entry:manual_endpoint':
            text = self.setup_view.endpoint_text()
            if text:
                self._call(ctl.select_endpoint, text, True)
        elif aid.startswith('session_ok:'):
            self._call(ctl.confirm_session, aid.endswith(':on'))
        elif aid.startswith('radio:'):
            self._radio(aid)
        elif aid.startswith(('fp_ok:', 'test_session_ok:')):
            pass                          # reine Freigabefelder der Oberfläche (Knopf-Gate)
        elif aid == 'details':
            self._show_details()
        elif aid == 'recheck' or aid == 'recheck_adapter':
            self._call(lambda: None)      # liest den Zustand neu; der Controller meldet über subscribe
        else:
            self.unhandled.append(aid)    # z. B. pair, export_diagnostics: Port hat noch keine Methode

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

    def _flyout_show(self, view: texts.ChipView, anchor: QWidget, toggle=None) -> None:
        if self._flyout is not None:
            self._flyout.close()
        fly = Flyout(view, self, toggle)
        fly.action.connect(self.do_action)
        fly.toggled.connect(lambda on: self.do_action('auto_connect:' + ('on' if on else 'off')))
        fly.closed.connect(anchor.setFocus)
        pos = anchor.mapToGlobal(anchor.rect().bottomLeft())
        fly.move(max(0, pos.x() - 200), pos.y() + 4)
        fly.show()
        fly.setFocus()
        self._flyout = fly

    def _show_lock(self) -> None:
        v = texts.ChipView('lock', texts.LOCK_TITLE, '', 'info', hint=texts.LOCK_TEXT)
        self._flyout_show(v, self.stack.currentWidget().lock_button)

    def _show_switch(self) -> None:
        c = self.controller.context()
        free = not c.switch_locked
        acts = tuple((texts.SWITCH_PI, f'switch_pi:{i}', free, texts.REASON_TRANSMISSION_FIRST)
                     for _n, i, _w in c.paired if i != c.pi_id)
        v = texts.ChipView('switch', 'Gekoppelte Pi', '', 'info',
                           details=tuple((n, f'{i} · {when}') for n, i, when in c.paired), hint=texts.PI_SWITCH_NOTE,
                           actions=acts)
        self._flyout_show(v, self.stack.currentWidget().header.switch_button)

    def _show_details(self) -> None:
        c = self.controller.context()
        v = texts.ChipView('details', 'Details', '', 'info', details=(
            ('App', c.version or '–'), ('Brückenseite', c.bridge_port or '–'), ('Gegenport', c.gsv_port or '–'),
            ('Pi-ID', c.pi_id or '–'), ('Protokoll', c.protocol or '–'), ('Journal', texts.JOURNAL_DETAILS)))
        toggle = (f'Beim Start automatisch mit {c.pi_name} verbinden', c.auto_connect) if c.pi_name else None
        self._flyout_show(v, self.status_view.details_button, toggle)

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
        if self.tray is not None:
            self.tray.hide()
        self.close()
