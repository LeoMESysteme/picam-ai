import json

import pytest

from dispread.bridge.hub import BridgeHub
from dispread.bridge.publisher import PairedOutputPublisher
from dispread.gsv_bridge import demo_records
from dispread.gsv_transport import OutputConfig


def test_unconfigured_publisher_cannot_fall_back_to_raw_tcp(tmp_path):
    publisher = PairedOutputPublisher(OutputConfig(transport='tcp'), tmp_path, hub=None)
    with pytest.raises(ValueError, match='configured'):
        publisher.start()


def test_publisher_binds_reserved_run_and_keeps_dut_locked(tmp_path):
    hub = BridgeHub('pi', tmp_path)
    hub.reserve_real_run('fresh')
    publisher = PairedOutputPublisher(OutputConfig(transport='tcp'), tmp_path / 'run', hub=hub, run_id='fresh')
    publisher.start()
    assert publisher.metadata()['run_id'] == 'fresh'
    assert publisher.status()['release_block']
    publisher.publish(next(demo_records(1)))
    publisher.stop()
    assert hub.status()['real_run']  # only service may release measurement reservation
    hub.release_real_run('fresh')
    assert hub.status()['run_id'] is None


def test_demo_request_uses_separate_audit_and_run_id(tmp_path):
    hub = BridgeHub('pi', tmp_path)
    hub.attach('pc', 'network')
    run_id = hub.start_demo('pc', 'network', count=1, rate_hz=100)
    hub._demo_thread.join(1)
    meta = json.loads((tmp_path / 'demo' / run_id / 'demo.json').read_text())
    assert meta['demo'] is True and meta['provisional'] is True and meta['time_claim'] is False
    next_id = hub.start_demo('pc', 'network', count=1, rate_hz=100)
    assert run_id != next_id
    hub.close()


def test_close_during_demo_startup_cancels_late_worker(tmp_path, monkeypatch):
    import threading
    hub = BridgeHub('pi', tmp_path)
    hub.attach('pc', 'network')
    bound, release = threading.Event(), threading.Event()
    original = hub.bind_run
    def pause(*args, **kwargs):
        original(*args, **kwargs)
        bound.set()
        assert release.wait(2)
    monkeypatch.setattr(hub, 'bind_run', pause)
    starter = threading.Thread(target=lambda: hub.start_demo('pc', 'network', count=100, rate_hz=100))
    starter.start()
    assert bound.wait(1)
    try:
        hub.close()
        release.set()
        starter.join(1)
        hub._demo_thread.join(.2)
        assert not hub._demo_thread.is_alive()
    finally:
        release.set()
        hub._demo_stop.set()
        starter.join(1)
        if hub._demo_thread:
            hub._demo_thread.join(1)


def test_demo_ends_when_owning_client_detaches(tmp_path):
    hub = BridgeHub('pi', tmp_path)
    lease = hub.attach('pc', 'network')
    hub.start_demo('pc', 'network', count=100, rate_hz=.001)
    try:
        hub.detach(lease.lease_id)
        hub._demo_thread.join(.5)
        assert not hub._demo_thread.is_alive()
        assert hub.status()['run_id'] is None
    finally:
        hub.close()


def test_silent_expired_lease_stops_slow_demo(tmp_path):
    now = [0.0]
    hub = BridgeHub('pi', tmp_path, clock=lambda: now[0])
    hub.attach('pc', 'network')
    hub.start_demo('pc', 'network', count=100, rate_hz=.001)
    try:
        now[0] = 5.0
        hub._demo_thread.join(.5)
        assert not hub._demo_thread.is_alive()
        assert hub.status()['run_id'] is None
    finally:
        hub.close()
