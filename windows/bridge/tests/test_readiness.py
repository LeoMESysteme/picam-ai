from dispread_bridge_app.readiness import Readiness, aggregate_readiness
from dispread_bridge_app.worker import WorkerStatus


def test_worker_audit_failure_overrides_connected_peer_without_gsv_claim():
    base = Readiness('ready', 'not_required', 'authenticated', 'demo_only', 'unknown', 'unconfirmed', None)
    status = WorkerStatus('stopped', False, False, 'audit_failed')
    result = aggregate_readiness(base, status)
    assert result.peer == 'authenticated'
    assert result.output == 'blocked'
    assert result.next_action == 'audit_failed'
    assert result.gsv == 'unconfirmed'


def test_running_demo_worker_does_not_confirm_receiver():
    base = Readiness('ready', 'ready', 'authenticated', 'demo_only', 'unknown', 'unconfirmed', None)
    result = aggregate_readiness(base, WorkerStatus('running', True, True, None))
    assert result.output == 'demo_only'
    assert result.com == 'driver_ready'
    assert result.gsv == 'unconfirmed'
