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



def test_peer_output_mapping_uses_fixed_reasons_instead_of_external_text():
    from dispread_bridge_app.readiness import peer_output_readiness

    from dispread.bridge.output_state import RELEASE_BLOCK
    assert peer_output_readiness('output_off', None, None) == ('output_off', 'output_off')
    assert peer_output_readiness('ready', 'demo-run', None) == ('demo_only', None)
    assert peer_output_readiness('ready', 'dut-run', RELEASE_BLOCK) == ('blocked', 'dut_release_blocked')
    assert peer_output_readiness('output_off', 'dut-run', RELEASE_BLOCK) == ('blocked', 'dut_release_blocked')
    assert peer_output_readiness('ready', 'dut-run', 'token=SECRET') == ('blocked', 'peer_release_blocked')
    assert peer_output_readiness('token=SECRET', 'run', None) == ('unavailable', 'peer_output_unknown')


def test_idle_worker_preserves_peer_block_and_off_reason_but_failure_wins():
    idle = WorkerStatus('idle', False, False, None)
    for output, reason in [('output_off', 'output_off'), ('blocked', 'dut_release_blocked')]:
        base = Readiness('ready', 'ready', 'authenticated', output, 'unknown', 'unconfirmed', reason)
        combined = aggregate_readiness(base, idle)
        assert (combined.output, combined.next_action) == (output, reason)
        assert combined.com == 'idle'
        failed = aggregate_readiness(base, WorkerStatus('stopped', False, False, 'audit_failed'))
        assert (failed.output, failed.next_action) == ('blocked', 'audit_failed')
