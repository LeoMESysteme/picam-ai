"""B2: Vierkanal-Takt über die Brücke Ende zu Ende auf Linux (UART-pty und lokales TLS).

10 Hz im Zeitraffer (virtuelle Pi-Taktuhr mit Gegendruck) über >= 6000 Takte, mit unlesbaren und dunklen Phasen,
Pi-Aussetzern (verpasste Takte) und Windows-Staus (Takte älter als das
Fenster gehen verloren und werden aufgefüllt). Kein Windows-, Treiber- oder
GSVmulti-Nachweis, keine Abnahme. Aufruf: PYTHONPATH=src:windows/bridge/src.
Messwerte: ``pytest -s -k b2_ticks`` druckt ``B2-MESSUNG {...}``.
"""
import json

import pytest

pytest.importorskip('serial')

from bridge_tick_harness import run_session_ticks, run_ticks  # noqa: E402

from dispread.bridge.identity import DeviceIdentity  # noqa: E402


@pytest.fixture(scope='module')
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp('b2-identity'), 'b2-pi')


def assert_tick_contract(m):
    assert m['lines_equal_ticks'] and m['sequence_complete'], m          # Zeilenzahl = Taktzahl
    assert m['ticks'] == m['pi_total'] + m['pi_missed'], m
    assert m['pi_accounted'] and m['pi_queued'] == 0 and m['pi_unconfirmed'] == 0, m
    assert m['tick_bytes_exact'] and m['fill_bytes_exact'] and m['filled_matches_pi'], m  # Auffüllung
    assert m['filled'] == m['pi_missed'] + m['pi_lost'], m
    assert m['valid_unique'] and m['valid_frames_increasing'] and m['valid_fresh'], m      # nie doppelt
    assert m['unfilled_gaps'] == [] and m['worker']['tick_disturbed'] is False, m
    assert m['worker']['ticks_written'] == m['pi_acknowledged'], m
    assert m['worker']['ticks_filled'] == m['filled'], m


# Zeitraffer mit Gegendruck (virtuelle Pi-Taktuhr): lastunabhängig und exakt.
@pytest.mark.slow
@pytest.mark.parametrize('transport', ['uart', 'tcp'])
def test_b2_ticks_6000_with_invalid_phases_and_lost_ticks(tmp_path, identity, transport):
    m = run_ticks(tmp_path, identity, transport=transport, ticks=6000)
    print('\nB2-MESSUNG ' + json.dumps(m, ensure_ascii=False))
    assert_tick_contract(m)
    assert m['ticks'] >= 6000
    assert m['pi_missed'] == 3 + 7 + 1, m            # künstliche Pi-Aussetzer, exakt aufgefüllt
    assert m['pi_lost_reasons'] == {'window': 2 * (60 - 50)}, m   # zwei Staus über das Fenster
    assert 0 < m['valid_lines'] < m['ticks'] and m['pi_invalid'] > 0, m


@pytest.mark.slow
def test_b2_gap_above_window_is_not_filled_and_marked_disturbed(tmp_path, identity):
    # Stau über 120 Takte: der Pi hält nur 50, Windows sieht einen Sprung um 71 (> 50).
    m = run_ticks(tmp_path, identity, transport='uart', ticks=400, jumps={}, stalls=(100,), stall_ticks=120)
    assert m['pi_lost_reasons'] == {'window': 70}, m
    assert m['unfilled_gaps'] == [[171, 70]] or m['unfilled_gaps'] == [(171, 70)], m
    assert m['worker']['tick_disturbed'] is True and m['filled'] == 0, m
    assert m['lines'] == m['ticks'] - 70 and not m['lines_equal_ticks'], m   # gestört, sichtbar
    assert m['tick_bytes_exact'] and m['valid_unique'], m


@pytest.mark.slow
@pytest.mark.parametrize('transport', ['uart', 'tcp'])
def test_b2_live_session_four_channel_over_bridge(tmp_path, identity, transport):
    from dispread.live.output import BRIDGE_4CH_RELEASE_NOTE

    result = run_session_ticks(tmp_path, identity, transport=transport, duration_s=3)
    snapshot, status = result['readiness']
    assert snapshot.output == 'test_release' and status.demo_only is False
    lines = [payload for _, payload in result['writes']]
    seqs = [int(line.split(b';')[2]) for line in lines]
    output = result['session']['output']
    tick = output['status']['tick']
    assert seqs == list(range(1, tick['seq'] + 1)) and tick['seq'] >= 25          # Zeilenzahl = Taktzahl
    assert tick['acknowledged'] + tick['lost'] + tick['unconfirmed'] == tick['total'] and tick['queued'] == 0
    assert all(line.startswith(b'%') and line.endswith(b'\r\n') and line.count(b';') == 3 for line in lines)
    valid = [line for line in lines if line.split(b';')[1] == b'1']
    assert valid and len(valid) < len(lines)            # Wertwechsel -> TRANSITION -> Fehlwerttakte
    assert output['format'] == '4ch' and output['rate_hz'] == 10 and output['status']['config']['format'] == '4ch'
    assert output['formatter']['format_id'] == 'gsvmulti_userdefined_4ch_v1'
    assert output['formatter']['provisional'] is True
    assert output['status']['release_note'] == BRIDGE_4CH_RELEASE_NOTE
    assert output['tick']['time_base'] == 'unix_realtime_from_monotonic' and output['tick']['provisional']
    assert output['acknowledged_unaccepted'] is True and output['release'] == 'test_unaccepted'
    assert result['worker'].ticks_written == tick['acknowledged']


@pytest.mark.slow
@pytest.mark.parametrize('transport', ['uart', 'tcp'])
def test_b2_without_confirmation_not_a_single_tick_reaches_com(tmp_path, identity, transport):
    result = run_session_ticks(tmp_path, identity, transport=transport, ack=False, duration_s=1.5)
    assert result['writes'] == [] and result['attempts'] == ()          # auch keine Fehlwertzeile
    snapshot, status = result['readiness']
    assert (snapshot.output, snapshot.next_action) == ('blocked', 'dut_release_blocked')
    tick = result['session']['output']['status']['tick']
    assert tick['total'] == 0 and tick['offered'] == 0
    assert not any(e['event'].startswith('tick') and e['event'] != 'tick_end' for e in result['pi_events'])


# Saubere Latenz ohne Zeitraffer, Staus und Aussetzer (Wanduhr, daher ``timing``):
# PYTHONPATH=src:windows/bridge/src pytest -m timing -s -k b2_realtime
@pytest.mark.timing
@pytest.mark.parametrize('transport,bytes_per_s', [('uart', None), ('tcp', None)], ids=['uart-pty', 'tls'])
def test_b2_realtime_latency_10hz(tmp_path, identity, transport, bytes_per_s):
    m = run_ticks(tmp_path, identity, transport=transport, ticks=600, realtime=True, jumps={}, stalls=(),
                  bytes_per_s=bytes_per_s)
    print('\nB2-ECHTZEIT ' + json.dumps(m, ensure_ascii=False))
    assert_tick_contract(m)


# Leitungskapazität UART (pty gedrosselt auf 8N1-Bytes/s): nur Messung, keine
# Zusicherung; die Baudrate selbst gehört zu feat/bruecke-ux (bridge/baud.py).
@pytest.mark.timing
@pytest.mark.parametrize('baud', [115200, 460800])
def test_b2_uart_capacity_10hz(tmp_path, identity, baud):
    m = run_ticks(tmp_path, identity, transport='uart', ticks=600, realtime=True, jumps={}, stalls=(),
                  bytes_per_s=baud / 10)
    print('\nB2-UART-KAPAZITAET ' + json.dumps(m, ensure_ascii=False))
    assert m['valid_unique'] and m['tick_bytes_exact'] and m['fill_bytes_exact'], m
    if baud >= 460800:
        assert_tick_contract(m)
