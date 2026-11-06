import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dispread_bridge_app import main as appmain
from dispread_bridge_app.ui.fake import FakeController


class FakeInstance:
    def __init__(self, first):
        self.first, self.closed = first, False

    def activate_or_acquire(self):
        return self.first

    def wait_for_activation(self, timeout_s=0):
        return False

    def close(self):
        self.closed = True


def test_second_start_exits_without_window():
    made = []
    code = appmain.run(['--demo-ui'], instance=FakeInstance(False), controller_factory=lambda: made.append(1) or FakeController(),
                       exec_loop=False)
    assert code == 0 and made == []


def test_first_start_builds_window_and_hooks():
    shown = []
    code = appmain.run(['--demo-ui'], instance=FakeInstance(True), controller_factory=None, exec_loop=False,
                       on_window=shown.append)
    assert code == 0 and len(shown) == 1
    shown[0].force_close()


def test_session_end_stops_worker_via_port():
    fc = FakeController()
    appmain.stop_for_session_end(fc)
    assert ('disconnect',) in fc.calls or ('request_exit', True) in fc.calls
