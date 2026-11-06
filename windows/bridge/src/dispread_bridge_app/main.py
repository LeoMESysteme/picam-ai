"""Einstieg der Windows-App. GUI-Importe erst nach freeze_support/Einzelinstanz."""
from __future__ import annotations

import multiprocessing
import sys
import threading


def stop_for_session_end(controller) -> None:
    """Abmelden/Standby: Übertragung über den Port beenden, nie über den Worker direkt."""
    try:
        controller.request_exit(True)
    except Exception:
        controller.disconnect()


def _watch_activation(instance, signal_emit, stop: threading.Event) -> threading.Thread:
    def loop():
        while not stop.is_set():
            try:
                if instance.wait_for_activation(1):
                    signal_emit()
            except Exception:
                return
    t = threading.Thread(target=loop, name='activation-watch', daemon=True)
    t.start()
    return t


def run(argv=None, *, instance=None, controller_factory=None, exec_loop=True, on_window=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if instance is None:
        from .instance import SingleInstance
        instance = SingleInstance()
    if not instance.activate_or_acquire():
        return 0                      # zweiter Start: Aktivierung ist signalisiert, kein Fenster
    from PySide6.QtCore import QObject, Signal
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([sys.argv[0]])
    from .ui.window import MainWindow
    if controller_factory is None:
        if '--demo-ui' in argv:
            from .ui.fake import FakeController
            controller = FakeController(_demo_state(argv))
        else:
            from .app_controller import AppController
            from .devices import WindowsDevices
            controller = AppController(devices=WindowsDevices())
    else:
        controller = controller_factory()
    window = MainWindow(controller)
    window.show()
    profile_path = _profile_arg(argv)
    if profile_path:
        window.open_profile_path(profile_path)      # Dateizuordnung .dispread: Pfad als Argument

    class _Act(QObject):
        raise_window = Signal()
    act = _Act()
    act.raise_window.connect(window.restore)
    stop = threading.Event()
    _watch_activation(instance, act.raise_window.emit, stop)

    if sys.platform == 'win32':
        app.commitDataRequest.connect(lambda *_: stop_for_session_end(controller))
        _install_power_filter(app, controller)
    if on_window:
        on_window(window)
    if not exec_loop:
        stop.set()
        return 0
    code = app.exec()
    stop_for_session_end(controller)      # Beenden über jeden Weg: Worker sicher stoppen
    stop.set()
    instance.close()
    return code


def _profile_arg(argv) -> str | None:
    for a in argv:
        if not a.startswith('-') and a.lower().endswith('.dispread'):
            return a
    return None


def _demo_state(argv) -> str:
    for a in argv:
        if a.startswith('--state='):
            return a.split('=', 1)[1]
    return 'B1'


def _install_power_filter(app, controller) -> None:
    """WM_POWERBROADCAST (Standby) -> Worker-Stop über den Port; nur Windows."""
    from PySide6.QtCore import QAbstractNativeEventFilter

    class _Filter(QAbstractNativeEventFilter):
        def nativeEventFilter(self, event_type, message):
            if event_type == b'windows_generic_MSG':
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == 0x0218 and msg.wParam == 0x4:   # PBT_APMSUSPEND
                    stop_for_session_end(controller)
            return False, 0
    app._power_filter = _Filter()
    app.installNativeEventFilter(app._power_filter)


def main() -> int:
    multiprocessing.freeze_support()
    return run()


if __name__ == '__main__':
    raise SystemExit(main())
