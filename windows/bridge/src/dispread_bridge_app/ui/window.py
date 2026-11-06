"""Hauptfenster, Tray und Controller-Anbindung."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel, QMenu, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from . import texts, theme
from .port import ControllerPort
from .setup_view import SetupView
from .status_view import Flyout, StatusView
from .widgets import button


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
    def __init__(self, text: str, parent=None):
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
        self.keep_button = button(texts.EXIT_KEEP, True, name='exit_keep')
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
        self._unsubscribe = controller.subscribe(self._bridge.event.emit)
        self._build_tray()
        self._flyout = None
        self.refresh()

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
        r, w, c = self.controller.snapshot(), self.controller.worker_status(), self.controller.context()
        locked = self._locked(c, w)
        self.status_view.update_from(r, w, c, locked)
        if c.setup is not None and c.mode == 'setup':
            self.setup_view.update_from(r, w, c, locked)
            self.stack.setCurrentWidget(self.setup_view)
        else:
            self.stack.setCurrentWidget(self.status_view)
        self.setup_view.setEnabled(not locked)
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
        from datetime import datetime
        self.status_view.add_entry(texts.event_entry(event, now=datetime.now().strftime('%H:%M:%S')))
        self.refresh()

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
        sig.callback = finished
        self.pool.start(task)

    def _mode(self) -> str:
        route = self.controller.context().route or ''
        return 'uart' if route.startswith('UART') else 'network'

    def do_action(self, aid: str) -> None:
        c, ctl = self.controller.context(), self.controller
        if aid in ('connect', 'reconnect', 'next_connect'):
            self._call(ctl.connect, self._mode(), None)
        elif aid in ('stop_retry', 'disconnect'):
            self._call(ctl.disconnect)
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
        elif aid in ('next', 'back'):
            self._call(ctl.setup_step, aid)
        elif aid in ('goto_pairing', 'new_code'):
            self._call(ctl.setup_step, 'pairing')
        elif aid == 'manual_pair':
            self._call(ctl.open_manual_pair)
        elif aid == 'set_port_pair':
            self._call(ctl.set_port_pair, self._ports.get('bridge_port'), self._ports.get('gsv_port'))
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

    def _flyout_show(self, view: texts.ChipView, anchor: QWidget) -> None:
        if self._flyout is not None:
            self._flyout.close()
        fly = Flyout(view, self)
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
        v = texts.ChipView('switch', 'Gekoppelte Pi', '', 'info',
                           details=tuple((n, f'{i} · {when}') for n, i, when in c.paired), hint=texts.PI_SWITCH_NOTE)
        self._flyout_show(v, self.stack.currentWidget().header.switch_button)

    def _show_details(self) -> None:
        c = self.controller.context()
        v = texts.ChipView('details', 'Details', '', 'info', details=(
            ('App', c.version or '–'), ('Brückenseite', c.bridge_port or '–'), ('Gegenport', c.gsv_port or '–'),
            ('Pi-ID', c.pi_id or '–'), ('Protokoll', c.protocol or '–'), ('Journal', texts.JOURNAL_DETAILS)))
        self._flyout_show(v, self.status_view.details_button)

    # ---------------------------------------------------------------- Beenden
    def build_exit_dialog(self) -> ExitDialog:
        c = self.controller.context()
        text = texts.EXIT_TEXT_ACTIVE if (c.release and not c.dut_locked) else texts.EXIT_TEXT_LOCKED
        return ExitDialog(text, self)

    def _confirm_exit_dialog(self) -> bool:
        dlg = self.build_exit_dialog()
        dlg.exec()
        return dlg.confirmed

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
