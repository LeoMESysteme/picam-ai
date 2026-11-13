"""Injected kernel model tests are distinct from real Windows proof gates."""
import sys

import pytest


class Kernel:
    def __init__(self, sid='S-1-5-21-1'):
        self.sid, self.mutexes, self.events, self.names = sid, set(), {}, []
    def user_sid(self):
        return self.sid
    def event(self, name, sid):
        self.names.append((name, sid))
        self.events.setdefault(name, False)
        return ('event', name)
    def mutex(self, name, sid):
        self.names.append((name, sid))
        exists = name in self.mutexes
        self.mutexes.add(name)
        return ('mutex-existing' if exists else 'mutex-owner', name), exists
    def signal(self, handle):
        self.events[handle[1]] = True
    def wait(self, handle, timeout_ms):
        result = self.events[handle[1]]
        self.events[handle[1]] = False
        return result
    def close(self, handle):
        if handle[0] == 'mutex-owner':
            self.mutexes.remove(handle[1])


def test_second_start_signals_activation_without_acquiring_or_killing_owner():
    from dispread_bridge_app.instance import SingleInstance
    kernel = Kernel()
    first, second = SingleInstance(native=kernel), SingleInstance(native=kernel)
    assert first.activate_or_acquire()
    assert not second.activate_or_acquire()
    assert first.wait_for_activation(0)
    assert not first.wait_for_activation(0)
    first.close()
    third = SingleInstance(native=kernel)
    assert third.activate_or_acquire()
    third.close()


def test_instance_is_bound_to_windows_user_sid():
    from dispread_bridge_app.instance import SingleInstance
    kernel = Kernel()
    first = SingleInstance(native=kernel)
    assert first.activate_or_acquire()
    kernel.sid = 'S-1-5-21-2'
    other_user = SingleInstance(native=kernel)
    assert other_user.activate_or_acquire()
    assert all(sid in name and name.startswith('Global\\') for name, sid in kernel.names)
    first.close()
    other_user.close()


def test_native_adapter_is_lazy_and_fails_closed_off_windows():
    from dispread_bridge_app.instance import SingleInstance
    instance = SingleInstance()
    if sys.platform != 'win32':
        with pytest.raises(OSError, match='Windows'):
            instance.activate_or_acquire()


def test_failed_activation_signal_does_not_claim_instance():
    from dispread_bridge_app.instance import SingleInstance
    class Broken(Kernel):
        def signal(self, handle):
            raise OSError('denied')
    kernel = Broken()
    first = SingleInstance(native=kernel)
    assert first.activate_or_acquire()
    with pytest.raises(OSError):
        SingleInstance(native=kernel).activate_or_acquire()
    assert first.activate_or_acquire()
    first.close()


@pytest.mark.skipif(sys.platform != 'win32', reason='requires real Windows kernel, not a fake')
def test_windows_native_second_process_activates_owner():
    import subprocess

    from dispread_bridge_app.instance import SingleInstance
    with SingleInstance() as first:
        assert first.activate_or_acquire()
        result = subprocess.run([sys.executable, '-c',
            'from dispread_bridge_app.instance import SingleInstance; '
            's=SingleInstance(); print(s.activate_or_acquire()); s.close()'],
            check=True, capture_output=True, text=True, timeout=10)
        assert result.stdout.strip() == 'False'
        assert first.wait_for_activation(1)
