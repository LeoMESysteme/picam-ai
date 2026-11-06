"""Abbildung der Kernwerte (Readiness-Tabelle, Maschinencodes) auf deutsche Texte."""
import re
from pathlib import Path

import pytest
from dispread_bridge_app.readiness import Readiness
from dispread_bridge_app.ui import texts
from dispread_bridge_app.ui.port import UiContext
from dispread_bridge_app.worker import WorkerStatus

SRC = Path(__file__).resolve().parents[1] / 'src' / 'dispread_bridge_app'
READY = Readiness('ready', 'not_required', 'authenticated', 'output_off', 'idle', 'unconfirmed', 'output_off')
RUN = WorkerStatus('running', True, True, None)
CTX = UiContext(pi_name='Pi', pi_id='p', route='Netzwerk')


def out_chip(r, w=RUN, ctx=CTX):
    return texts.chips(r, w, ctx)[3]


@pytest.mark.parametrize('output, action, word', [
    ('output_off', 'output_off', 'Keine Ausgabe'),
    ('blocked', 'dut_release_blocked', 'DUT gesperrt'),
    ('blocked', 'peer_release_blocked', 'Gesperrt (Pi)'),
    ('ended', 'run_ended', 'Lauf beendet'),
    ('unavailable', 'peer_output_unknown', 'Unbekannt'),
])
def test_core_output_table_maps_to_german_chip(output, action, word):
    r = Readiness('ready', 'not_required', 'authenticated', output, 'idle', 'unconfirmed', action)
    chip = out_chip(r, None)
    assert chip.word == word and chip.tone in ('info', 'warn')
    assert out_chip(r).word == word


def test_demo_only_stays_demo_and_never_dut_release():
    r = Readiness('ready', 'not_required', 'authenticated', 'demo_only', 'driver_ready', 'unconfirmed', None)
    assert out_chip(r, RUN, UiContext(demo=True)).word == 'Demo-Werte'
    assert texts.dut_line(UiContext(demo=True))[0] == texts.DUT_LOCK_LINE


def test_ended_headline_and_explanations():
    r = Readiness('ready', 'not_required', 'authenticated', 'ended', 'idle', 'unconfirmed', 'run_ended')
    assert texts.headline(r, None, CTX).text == 'Verbunden – Lauf beendet'
    for code in ('output_off', 'dut_release_blocked', 'peer_release_blocked', 'run_ended', 'peer_output_unknown'):
        what, nxt = texts.explain_code(code)
        assert what != 'Unbekannt' and nxt


def test_every_backend_machine_code_has_a_german_text():
    codes = set()
    for f in SRC.glob('*.py'):
        codes |= set(re.findall(r"(?:TransportError|ConnectionError|CredentialError)\('([a-z_]+)'\)", f.read_text('utf-8')))
    codes |= {'unknown_invalidation', 'unknown_delivery', 'audit_failed', 'connection_failed'}
    missing = sorted(c for c in codes if texts.explain_code(c)[0] == 'Unbekannt')
    assert missing == []


def test_unknown_code_is_unknown_with_code_in_details():
    assert texts.explain_code('neu_im_kern_42') == ('Unbekannt', 'Code: neu_im_kern_42')
    r = Readiness('ready', 'unknown', 'disconnected', 'unavailable', 'unknown', 'unconfirmed', 'neu_im_kern_42')
    bar = texts.action_bar(r, None, CTX)
    assert bar.title == 'Unbekannt' and 'neu_im_kern_42' in bar.text
    pi = texts.chips(r, None, CTX)[2]
    assert ('Code', 'neu_im_kern_42') in pi.details


def test_setup_texts_contain_no_mock_sample_values():
    flat = repr(texts.SETUP)
    for sample in ('192.168.10.24', 'prüfstand2.local', 'COM6', 'COM7', '312 von 600', 'GSVmulti_Test_Prüfstand2.txt',
                   'Port 3'):
        if sample in flat:
            # nur die Fake-Zustände E5file/E5ok/E5bad dürfen noch Beispiele tragen (nicht vom Controller erreichbar)
            assert all(sample not in repr(texts.SETUP[k]) for k in
                       ('E1', 'E1manual', 'E1ok', 'E2', 'E2b', 'E3', 'E3uart', 'E3uart2', 'E3err', 'E4locked',
                        'E5', 'E5run', 'E5done')), sample


def test_session_export_text_is_manual_instruction():
    ctx = UiContext(gsv_port='COM5', setup=__import__('dispread_bridge_app.ui.port', fromlist=['x']).SetupState(
        4, 'E4locked', {}))
    flat = repr(texts.setup_spec(ctx)['blocks'])
    assert 'Automatische Session noch nicht freigegeben' in flat
    assert 'In GSVmulti den Kanal auf COM5 115200 8N1 einstellen' in flat and '{' not in flat.replace('{}', '')
