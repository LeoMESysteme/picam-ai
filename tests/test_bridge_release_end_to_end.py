"""R1: bestätigte Testfreigabe echter Werte Ende zu Ende auf Linux (UART-pty und lokales TLS).

Echter LiveSession-Lauf aus synthetischen Bildern -> PairedOutputPublisher ->
BridgeHub -> UartListener (pty statt /dev/ttyAMA0) bzw. TLS-WSS-Route ->
ConnectionManager/SerialTransport -> BridgeWorker/BridgeSession -> Fake-COM.
Kein Windows-, Treiber- oder GSVmulti-Nachweis, keine Abnahme.
Aufruf: PYTHONPATH=src:windows/bridge/src.
"""
import json

import pytest

pytest.importorskip('dispread_bridge_app')
pytest.importorskip('serial')

from bridge_release_harness import barrier_order_holds, run_release  # noqa: E402

from dispread.bridge.identity import DeviceIdentity  # noqa: E402
from dispread.bridge.output_state import RELEASE_BLOCK  # noqa: E402
from dispread.live.output import BRIDGE_RELEASE_NOTE  # noqa: E402


@pytest.fixture(scope='module')
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp('r1-identity'), 'r1-pi')


def _assert_released(result, transport):
    m = result['metrics']
    assert m['valid_published'] > 0 and m['written'] > 0, m
    assert m['invalid_written'] == 0, m           # nur VALID an COM
    assert m['bytes_exact'], m                    # byte-genau wie UART direkt (TelegramFormatter P4-3)
    assert m['in_order'], m
    assert m['barriers_omitted'] >= 1, m          # Wertwechsel -> TRANSITION -> Barriere
    assert barrier_order_holds(result['pi_events'])
    assert all(payload.startswith(b'%') and payload.endswith(b'\r\n') and b'NaN' not in payload
               for _, _, payload in result['writes'])
    assert all(a.outcome == 'written' for a in result['attempts'])
    stage, snapshot, status = result['readiness'][1]
    assert (snapshot.output, snapshot.next_action, snapshot.gsv) == ('test_release', None, 'unconfirmed')
    assert status.demo_only is False
    after = result['readiness'][-1]
    assert after[1].output in ('output_off', 'ended') and after[2].demo_only is True
    output = result['session']['output']
    assert output['acknowledged_unaccepted'] is True and output['acknowledged_at_utc']
    assert output['release'] == 'test_unaccepted' and output['release_block'] is None
    assert output['acceptance'] == 'fehlt' and output['formatter']['provisional'] is True
    assert output['status']['release_note'] == BRIDGE_RELEASE_NOTE
    assert output['transport'] == transport
    assert result['session']['run_id'] == result['pi_events'][0]['run_id']
    if transport == 'uart':
        assert set(result['opened']) == {'/dev/ttyAMA0'} or result['opened'][0].endswith('ttyAMA0')


@pytest.mark.slow
@pytest.mark.parametrize('transport', ['uart', 'tcp'])
def test_confirmed_test_release_delivers_valid_values_to_com(tmp_path, identity, transport):
    result = run_release(tmp_path, identity, transport=transport, rate_hz=10, duration_s=4)
    _assert_released(result, transport)


@pytest.mark.slow
@pytest.mark.parametrize('transport', ['uart', 'tcp'])
def test_without_confirmation_nothing_reaches_com(tmp_path, identity, transport):
    result = run_release(tmp_path, identity, transport=transport, rate_hz=10, duration_s=2, ack=False)
    m = result['metrics']
    assert m['valid_published'] > 0 and m['written'] == 0 and result['writes'] == []
    assert result['attempts'] == ()
    stage, snapshot, status = result['readiness'][1]
    assert (snapshot.output, snapshot.next_action) == ('blocked', 'dut_release_blocked')
    assert status.demo_only is True
    output = result['session']['output']
    assert output['acknowledged_unaccepted'] is False and output['release_block'] == RELEASE_BLOCK
    assert not any(e['event'] == 'offered' for e in result['pi_events'])


# Messgrößen (Brief R1 Punkt 5): >= 30 s je Rate. Wanduhr-Laufzeit, daher
# `timing` (bei -n übersprungen): PYTHONPATH=src:windows/bridge/src pytest -m timing -s.
@pytest.mark.timing
@pytest.mark.parametrize('rate_hz', [10, 20])
@pytest.mark.parametrize('transport,bytes_per_s', [('uart', None), ('uart', 115200 / 10), ('tcp', None)],
                         ids=['uart-pty', 'uart-115200', 'tls'])
def test_measure_latency_and_lost_values(tmp_path, identity, transport, bytes_per_s, rate_hz):
    result = run_release(tmp_path, identity, transport=transport, rate_hz=rate_hz, duration_s=30,
                         bytes_per_s=bytes_per_s)
    print('\nR1-MESSUNG ' + json.dumps(result['metrics'], ensure_ascii=False))
    m = result['metrics']
    assert m['invalid_written'] == 0 and m['bytes_exact'] and m['in_order'], m
    assert barrier_order_holds(result['pi_events'])
