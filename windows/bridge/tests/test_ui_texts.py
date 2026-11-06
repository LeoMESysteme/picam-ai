"""Wahrheitsregeln der Texte, ohne Qt-Fenster."""
from dataclasses import replace

from dispread_bridge_app.readiness import Readiness
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.fake import STATES
from dispread_bridge_app.ui.port import Receipt, UiContext
from dispread_bridge_app.worker import WorkerStatus

from dispread.bridge.types import BridgeEvent


def chips(key):
    r, w, c = STATES[key]
    return {x.key: x for x in texts.chips(r, w, c)}


def test_never_all_six_chips_green_under_dut_lock():
    for key, (r, w, c) in STATES.items():
        if c.mode == 'setup' or not c.dut_locked:
            continue
        tones = [x.tone for x in texts.chips(r, w, c)]
        assert tones != ['ok'] * 6, key
        assert chips(key)['output'].tone != 'ok', key


def test_dut_lock_line_in_every_state():
    for key, (_r, _w, c) in STATES.items():
        text, tone = texts.dut_line(c)
        if c.dut_locked:
            assert text == texts.DUT_LOCK_LINE and tone == 'warn', key


def test_worker_code_overrules_connected_pi():
    r, w, c = STATES['blocked']
    assert r.peer == 'authenticated'
    h = texts.headline(r, w, c)
    assert h.tone == 'err' and 'gestoppt' in h.text
    cv = chips('blocked')
    assert cv['output'].tone == 'err' and cv['forward'].tone == 'err'
    assert cv['pi'].tone != 'ok'
    assert texts.action_bar(r, w, c).kind == 'err'


def test_output_not_ready_is_not_connected_ok():
    r, _, c = STATES['B1']
    w = WorkerStatus('connection_failed', False, False, None)
    assert texts.headline(r, w, c).tone != 'ok'


def test_receipt_proven_only_with_test_proof():
    r, w, c = STATES['B1']
    assert chips('B1')['gsv'].tone == 'info'
    assert chips('B1')['gsv'].sub == 'Empfang nicht nachgewiesen'
    unproven = replace(c, receipt=Receipt(False, 'Test 14:02'))
    assert {x.key: x for x in texts.chips(r, w, unproven)}['gsv'].tone != 'ok'
    # der Worker selbst belegt nie Empfang
    w2 = WorkerStatus('running', True, True, None, gsv_receipt_confirmed=True)
    assert {x.key: x for x in texts.chips(r, w2, c)}['gsv'].tone != 'ok'
    proven = chips('B1t')['gsv']
    assert proven.tone == 'ok' and proven.word == 'Empfang belegt'


def test_forwarding_is_not_gsv_receipt_and_absent_under_lock():
    fw = chips('B1')['forward']
    assert fw.word == 'Keine Weitergabe' and fw.tone == 'info'
    assert chips('B5')['forward'].word == 'Bestätigt'
    assert chips('B5')['gsv'].word != 'Empfang belegt'


def test_unknown_values_are_neutral_unknown():
    r = Readiness('???', '???', '???', '???', '???', '???', None)
    c = UiContext(pi_name='X')
    views = texts.chips(r, None, c)
    for v in views[:5]:
        assert v.word in ('Unbekannt', 'Keine Weitergabe') and v.tone == 'info', v
    assert texts.headline(r, None, c) == texts.Headline('Unbekannt', 'info')


def test_usb_missing_and_pi_waiting_have_distinct_actions():
    ru, wu, cu = STATES['usb_missing']
    rw, ww, cw = STATES['B2']
    a, b = texts.action_bar(ru, wu, cu), texts.action_bar(rw, ww, cw)
    assert a.action_ids and (b is None or a.action_ids != b.action_ids)
    assert b is None or a.title != b.title
    assert texts.headline(ru, wu, cu).text != texts.headline(rw, ww, cw).text


def test_bar_has_at_most_two_buttons():
    for key, (r, w, c) in STATES.items():
        bar = texts.action_bar(r, w, c)
        assert bar is None or len(bar.buttons) <= 2, key


def test_b1_headlines_match_mock():
    r, w, c = STATES['B1']
    assert texts.headline(r, w, c).text == 'Verbunden – Lauf 7 läuft, keine Werteausgabe'
    r, w, c = STATES['B3']
    assert texts.headline(r, w, c).text == 'Pi antwortet nicht – Versuch in 4 s'
    r, w, c = STATES['B4a']
    assert texts.headline(r, w, c).text == 'Demo: Weitergabe gestört – COM4 belegt'


def test_event_entry_hides_details():
    e = BridgeEvent('connection', 'backoff', None, None, {'token': 'secret'})
    entry = texts.event_entry(e, now='14:00:00')
    assert entry.fault and 'secret' not in repr(entry)


def test_setup_variants_cover_mock_states():
    for k in ('E1', 'E1uac', 'E1restart', 'E1ok', 'E2', 'E2b', 'E2exp', 'E2bad', 'E2ok', 'E3', 'E3uart', 'E3uart2',
              'E3ok', 'E3fail', 'E4', 'E4ok', 'E4unk', 'E5', 'E5run', 'E5file', 'E5ok', 'E5bad'):
        assert k in texts.SETUP and k in STATES


def test_context_has_no_invented_real_values():
    c = UiContext()
    assert c.bridge_port is None and c.gsv_port is None and c.protocol is None and c.version is None
    r = Readiness('ready', 'not_required', 'authenticated', 'demo_only', 'driver_ready', 'unconfirmed', None)
    cv = {x.key: x for x in texts.chips(r, None, c)}
    flat = repr(cv)
    assert 'COM4' not in flat and 'COM5' not in flat and 'Version 2' not in flat
    assert ('Brückenseite', 'nicht festgelegt') in cv['forward'].details
    busy = replace(c, demo=True, com_issue='busy')
    assert 'COM' not in texts.headline(r, None, busy).text
    assert 'COM' not in texts.action_bar(r, None, busy).title


def test_setup_spec_fills_ports_from_context_not_examples():
    from dispread_bridge_app.ui.port import SetupState
    spec = texts.setup_spec(UiContext(setup=SetupState(4, 'E4')))
    assert 'COM4' not in repr(spec) and '{bridge_port}' not in repr(spec)
    spec = texts.setup_spec(UiContext(bridge_port='COM9', gsv_port='COM8', setup=SetupState(4, 'E4')))
    assert 'COM9' in repr(spec) and 'COM8' in repr(spec)
