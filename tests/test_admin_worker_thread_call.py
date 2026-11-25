"""thread_call: Hook-Fehler werden protokolliert statt verschluckt; gescheiterte Rückfragen gelten als abgelehnt."""
import logging
import threading

from dispread.admin.views.worker_screen import ScreenHooks, WorkerScreen


class _App:
    def __init__(self, fail=()):
        self.fail, self.lines = fail, []

    def call_from_thread(self, fn, *args):
        if fn.__name__ in self.fail:
            raise ValueError('kaputt')
        fn(*args)


class _Screen:
    thread_call = WorkerScreen.thread_call

    def __init__(self, fail=()):
        self.app, self.gone, self.lines = _App(fail), threading.Event(), []

    def log_line(self, text, err=False):
        self.lines.append((text, err))


def test_hook_error_is_logged_and_shown_not_swallowed(caplog):
    s = _Screen(fail=('boom',))

    def boom():
        pass
    with caplog.at_level(logging.ERROR):
        assert s.thread_call(boom) is False
        assert s.thread_call(s.log_line, 'weiter', False) is True      # der Worker läuft weiter
    assert any('boom' in r.getMessage() for r in caplog.records)
    assert s.lines[0][1] is True and 'Anzeigefehler (boom)' in s.lines[0][0]
    assert s.lines[-1] == ('weiter', False)


def test_closing_app_stays_silent(caplog):
    s = _Screen(fail=('log_line',))
    s.gone.set()
    with caplog.at_level(logging.ERROR):
        assert s.thread_call(s.log_line, 'x') is False
    assert not caplog.records


def test_failed_confirm_counts_as_not_confirmed(caplog):
    s = _Screen()

    def ask(**kw):
        raise RuntimeError('Rückfrage kaputt')
    s.ask = ask
    s.set_phase = lambda phase: s.lines.append(('phase', False))
    hooks = ScreenHooks(s)
    with caplog.at_level(logging.ERROR):
        assert hooks.confirm('Titel', ['x'], None) is False
    assert not any(t == 'phase' for t, _ in s.lines)
    assert any('nicht bestätigt' in t for t, _ in s.lines)


def test_failed_open_ask_counts_as_not_confirmed():
    s = _Screen(fail=('open_ask',))

    def open_ask(spec):
        pass
    s.open_ask = open_ask
    s.gone = threading.Event()
    s.ask = lambda **kw: WorkerScreen.ask(s, **kw)
    s.OK_LABEL, s.ASK_DANGER = 'OK', False
    s.set_phase = lambda p: None
    assert ScreenHooks(s).confirm('Titel', [], None) is False
