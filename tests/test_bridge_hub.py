import json

import pytest

from dispread.bridge.hub import BridgeHub
from dispread.bridge.output_state import RELEASE_BLOCK, OutputState
from dispread.bridge.protocol import decode_v2, encode_v2
from dispread.bridge.resources import SerialPortLease
from dispread.gsv_bridge import demo_records


def request(hub, lease, kind='poll', **changes):
    return dict(version=2, type=kind, request_id='req', pi_id=hub.pi_id,
                client_id=lease.client_id, lease_id=lease.lease_id,
                run_id=hub.status()['run_id'], **changes)


def test_two_clients_cannot_own_same_run(tmp_path):
    hub = BridgeHub('pi', tmp_path)
    first = hub.attach('pc1', 'network')
    with pytest.raises(ValueError, match='occupied'):
        hub.attach('pc2', 'network')
    hub.detach(first.lease_id)
    assert hub.attach('pc2', 'network').lease_id != first.lease_id


def test_lease_heartbeat_boundary_and_no_poll(tmp_path):
    now = [0.0]
    hub = BridgeHub('pi', tmp_path, clock=lambda: now[0])
    state = OutputState(tmp_path / 'run', demo=True)
    state.start()
    hub.bind_run(state.run_id, state)
    lease = hub.attach('pc', 'network')
    state.publish(next(demo_records(1)))
    now[0] = 4.999
    result = hub.exchange(lease.lease_id, request(hub, lease, 'heartbeat'))
    assert result['type'] == 'heartbeat'
    assert hub.exchange(lease.lease_id, request(hub, lease))['type'] == 'record'
    now[0] = 9.999
    with pytest.raises(ValueError, match='expired'):
        hub.exchange(lease.lease_id, request(hub, lease, 'heartbeat'))
    hub.close()
    state.stop()


def test_pairing_does_not_unlock_dut(tmp_path):
    hub = BridgeHub('pi', tmp_path)
    state = OutputState(tmp_path / 'run')
    state.start()
    hub.bind_run(state.run_id, state)
    lease = hub.attach('pc', 'network')
    assert hub.exchange(lease.lease_id, request(hub, lease))['release_block'] == RELEASE_BLOCK
    hub.close()
    state.stop()


def test_demo_request_is_refused_during_real_run(tmp_path):
    hub = BridgeHub('pi', tmp_path)
    hub.reserve_real_run('run')
    hub.attach('pc', 'network')
    with pytest.raises(ValueError, match='real run'):
        hub.start_demo('pc', 'network', count=1)
    hub.release_real_run('wrong')
    assert hub.status()['run_id'] == 'run'
    hub.release_real_run('run')


def test_uart_prepare_conflicts_with_direct_serial(tmp_path):
    leases = SerialPortLease(tmp_path)
    leases.acquire('/dev/ttyAMA0', 'direct', 'serial')
    with pytest.raises(ValueError, match='occupied'):
        SerialPortLease(tmp_path).acquire('/dev/ttyAMA0', 'bridge', 'uart')
    leases.release('wrong')
    with pytest.raises(ValueError):
        SerialPortLease(tmp_path).acquire('/dev/ttyAMA0', 'bridge', 'uart')
    leases.release('direct')


def test_reference_port_is_never_opened(tmp_path):
    alias = tmp_path / 'alias'
    alias.symlink_to('/dev/ttyUSB0')
    for path in ['/dev/ttyUSB0', str(alias)]:
        with pytest.raises(ValueError, match='reference'):
            SerialPortLease(tmp_path / 'locks').acquire(path, 'test', 'serial')


def test_reconnect_does_not_repeat_uncertain_number(tmp_path):
    hub = BridgeHub('pi', tmp_path)
    state = OutputState(tmp_path / 'run', demo=True)
    state.start()
    hub.bind_run(state.run_id, state)
    state.publish(next(demo_records(1)))
    first = hub.attach('pc', 'network')
    assert hub.exchange(first.lease_id, request(hub, first))['type'] == 'record'
    hub.detach(first.lease_id)
    second = hub.attach('pc', 'network')
    result = hub.exchange(second.lease_id, request(hub, second))
    assert decode_v2(encode_v2(result))['type'] == 'idle'
    state.stop()
    assert 'unconfirmed' in [json.loads(line)['event'] for line in (state.out_dir / 'output.jsonl').read_text().splitlines()]


def test_direct_serial_sink_participates_in_shared_lease(tmp_path, monkeypatch):
    import serial

    from dispread.sink.protocol.user_defined import UserDefinedFormatter
    from dispread.sink.serial_out import SerialSink
    opened = []
    monkeypatch.setattr(serial, 'Serial', lambda *a, **kw: opened.append(a))
    leases = SerialPortLease()
    leases.acquire('/dev/ttyAMA0', 'prepared', 'uart')
    try:
        with pytest.raises(ValueError, match='occupied'):
            SerialSink('/dev/ttyAMA0', UserDefinedFormatter()).open()
        assert opened == []
    finally:
        leases.release('prepared')


def test_invalid_barrier_survives_lease_change_and_wrong_ack(tmp_path):
    from dataclasses import replace

    from dispread.records import ValueStatus
    hub = BridgeHub('pi', tmp_path)
    state = OutputState(tmp_path / 'run', demo=True)
    state.start()
    hub.bind_run(state.run_id, state)
    invalid = replace(next(demo_records(2)), value=None, status=ValueStatus.UNREADABLE, reject_reasons=('test',))
    state.publish(invalid)
    first = hub.attach('pc', 'network')
    record = hub.exchange(first.lease_id, request(hub, first))
    hub.detach(first.lease_id)
    second = hub.attach('pc', 'network')
    repeated = hub.exchange(second.lease_id, request(hub, second))
    assert repeated['barrier_id'] == record['barrier_id']
    ack = request(hub, second, 'ack', frame_sequence=invalid.frame_sequence,
                  barrier_id=repeated['barrier_id'], outcome='written')
    with pytest.raises(ValueError):
        hub.exchange(second.lease_id, {**ack, 'request_id': 'wrong'})
    with pytest.raises(ValueError):
        hub.exchange(second.lease_id, {**ack, 'run_id': 'wrong'})
    assert hub.exchange(second.lease_id, ack)['type'] == 'idle'
    state.publish(list(demo_records(2))[1])
    assert hub.exchange(second.lease_id, request(hub, second))['barrier_id'] is None
    hub.close()
    state.stop()


def test_serial_lease_excludes_other_process(tmp_path):
    import os
    import subprocess
    import sys
    leases = SerialPortLease(tmp_path)
    leases.acquire('/dev/ttyAMA0', 'parent', 'serial')
    code = '''from pathlib import Path
from dispread.bridge.resources import SerialPortLease
import sys
try:
    SerialPortLease(Path(sys.argv[1])).acquire('/dev/ttyAMA0', 'child', 'uart')
except ValueError:
    sys.exit(23)
'''
    try:
        child = subprocess.run([sys.executable, '-c', code, str(tmp_path)], env={**os.environ, 'PYTHONPATH': 'src'},
                               capture_output=True, timeout=5)
        assert child.returncode == 23, child.stderr.decode()
    finally:
        leases.release('parent')


def test_shared_windows_import_chain_needs_no_posix_modules():
    import os
    import subprocess
    import sys
    code = '''import builtins
original = builtins.__import__
def portable(name, *args, **kwargs):
    if name in ('fcntl', 'pwd'):
        raise ImportError('POSIX unavailable')
    return original(name, *args, **kwargs)
builtins.__import__ = portable
import dispread.gsv_bridge
import dispread.gsv_transport
import dispread.bridge.resources
'''
    child = subprocess.run([sys.executable, '-c', code], env={**os.environ, 'PYTHONPATH': 'src'},
                           capture_output=True, timeout=5)
    assert child.returncode == 0, child.stderr.decode()


def test_local_prepare_without_network_or_client_identity(tmp_path):
    import asyncio

    from dispread.workbench.server import handle_local_op
    called = []
    class Hub:
        def prepare_uart(self):
            called.append(True)
            return {'uart_prepared': True, 'connected': False}
    response = asyncio.run(handle_local_op('bridge.prepare-uart', {}, None, None, Hub()))
    assert response.status == 200 and called == [True]
    assert json.loads(response.body)['connected'] is False


def test_local_prepare_cli_calls_only_authorized_local_socket(monkeypatch, capsys):
    from dispread.workbench import cli
    calls = []
    async def call(op, args=None, socket_path=None):
        calls.append((op, socket_path))
        return {'uart_prepared': True}
    monkeypatch.setattr(cli, 'request', call)
    assert cli.main(['bridge', 'prepare-uart', '--socket', '/tmp/private/control.sock']) == 0
    assert calls == [('bridge.prepare-uart', '/tmp/private/control.sock')]
    assert json.loads(capsys.readouterr().out)['uart_prepared'] is True


def test_reference_alias_is_rejected_before_serial_open(tmp_path, monkeypatch):
    import serial

    from dispread.sink.protocol.user_defined import UserDefinedFormatter
    from dispread.sink.serial_out import SerialSink
    alias = tmp_path / 'alias'
    alias.symlink_to('/dev/ttyUSB0')
    def forbidden(*args, **kwargs):
        pytest.fail('reference serial opener must never be called')
    monkeypatch.setattr(serial, 'Serial', forbidden)
    with pytest.raises(ValueError, match='reference'):
        SerialSink(str(alias), UserDefinedFormatter()).open()


def test_audit_io_never_holds_hub_registry_lock(tmp_path):
    import threading
    hub = BridgeHub('pi', tmp_path)
    state = OutputState(tmp_path / 'run', demo=True)
    state.start()
    hub.bind_run(state.run_id, state)
    state.publish(next(demo_records(1)))
    lease = hub.attach('pc', 'network')
    entered, release, status_done = threading.Event(), threading.Event(), threading.Event()
    original = state._event
    def event(kind, **kwargs):
        if kind == 'offered':
            entered.set()
            assert release.wait(2)
        original(kind, **kwargs)
    state._event = event
    poller = threading.Thread(target=lambda: hub.exchange(lease.lease_id, request(hub, lease)))
    poller.start()
    assert entered.wait(1)
    snapshot = threading.Thread(target=lambda: (hub.status(), status_done.set()))
    snapshot.start()
    try:
        assert status_done.wait(.5)
    finally:
        release.set()
        snapshot.join(1)
        poller.join(1)
        hub.close()
        state.stop()


@pytest.mark.parametrize('change', ['replace', 'expire'])
def test_delayed_demo_request_cannot_cross_lease_boundary(tmp_path, monkeypatch, change):
    import threading

    now = [0.0]
    hub = BridgeHub('pi', tmp_path / 'audit', clock=lambda: now[0])
    old = hub.attach('pc', 'network')
    entered, resume = threading.Event(), threading.Event()
    original = hub.start_demo
    errors = []
    def paused(*args, **kwargs):
        entered.set()
        assert resume.wait(2)
        return original(*args, **kwargs)
    monkeypatch.setattr(hub, 'start_demo', paused)
    message = dict(version=2, type='demo_request', request_id='demo', pi_id='pi', client_id='pc',
                   run_id=None, transport='network', count=100, rate_hz=10)
    def exchange():
        try:
            hub.exchange(old.lease_id, message)
        except Exception as exc:
            errors.append(exc)
    worker = threading.Thread(target=exchange)
    worker.start()
    try:
        assert entered.wait(1)
        if change == 'replace':
            hub.detach(old.lease_id)
            current = hub.attach('pc', 'network')
        else:
            current = old
            now[0] = 5.0
        before = vars(current).copy()
        resume.set()
        worker.join(1)
        assert not worker.is_alive()
        assert len(errors) == 1 and isinstance(errors[0], ValueError)
        assert hub._lease is current and vars(current) == before
        assert hub.status()['run_id'] is None
        assert not (tmp_path / 'audit').exists()
    finally:
        resume.set()
        worker.join(1)
        hub.close()


def test_demo_end_does_not_overtake_the_last_value(tmp_path):
    """A demo of N values must be offered N times even if the client polls late:
    ``ended`` may not discard the final, still unoffered value (BQ5, 599 of 600)."""
    import time

    hub = BridgeHub('pi', tmp_path)
    lease = hub.attach('pc', 'network')
    hub.exchange(lease.lease_id, dict(version=2, type='demo_request', request_id='d', pi_id='pi',
                                      client_id='pc', run_id=None, transport='network', count=3, rate_hz=50))
    run_id = hub.status()['run_id']
    time.sleep(.3)                      # the client is late; the demo has produced all three values
    offered = []
    for number in range(6):
        message = dict(request(hub, lease), request_id=f'p{number}', run_id=run_id)
        reply = hub.exchange(lease.lease_id, message)
        if reply['type'] != 'record':
            break
        offered.append(reply['record']['frame_sequence'])
        hub.exchange(lease.lease_id, dict(message, type='ack', outcome='written',
                                          frame_sequence=offered[-1], barrier_id=reply['barrier_id']))
    assert offered == [2]               # latest-value semantics: the final value is still delivered
    deadline = time.monotonic() + 3
    while hub.status()['run_id'] is not None and time.monotonic() < deadline:
        time.sleep(.02)
    assert hub.status()['run_id'] is None
    hub.close()
