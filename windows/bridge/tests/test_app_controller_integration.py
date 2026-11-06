"""AppController gegen den echten Pi-Teil (TLS, Kopplung, Hub) auf localhost, Fake-COM.

Prüft keine Windows-API (DPAPI, Treiber, Instanzschutz) und kein GSVmulti.
"""
import asyncio
import json
import time
from dataclasses import asdict

import pytest
from aiohttp import web
from dispread_bridge_app.app_controller import AppController
from dispread_bridge_app.ui import texts

from dispread.bridge.hub import BridgeHub
from dispread.bridge.identity import DeviceIdentity
from dispread.bridge.output_state import RELEASE_BLOCK, OutputState
from dispread.bridge.pairing import PairingStore
from dispread.bridge.routes import add_bridge_routes
from dispread.bridge.types import BridgeProfile
from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus


class Protector:
    def __init__(self):
        self.v = {}

    def protect(self, raw):
        k = bytes([len(self.v) + 1]) * 8
        self.v[k] = raw
        return k

    def unprotect(self, raw):
        return self.v[raw]


class FakeCom:
    def __init__(self):
        self.payloads, self.closed, self.port = [], False, None

    def write(self, payload):
        self.payloads.append(payload)
        return len(payload)

    def close(self):
        self.closed = True


def wait_for(pred, timeout=8):
    end = time.monotonic() + timeout
    while not pred():
        assert time.monotonic() < end, 'condition not reached'
        time.sleep(.02)


def record(n):
    return ValueRecord(n, Timestamp(n, TimeBaseKind.SYNTHETIC), float(n), 'mV/V', ValueStatus.VALID, 1.0, 'demo',
                       None, None, raw_text=f'+{n}.0', reject_reasons=())


@pytest.fixture(scope='module')
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp('ai-id'), 'ai-pi')


def run_rig(tmp_path, identity, exercise, demo_count=10):
    async def main():
        store = PairingStore(tmp_path / 'pairing')
        hub = BridgeHub(identity.pi_id, tmp_path / 'pi-audit', identity=identity, pairing_store=store)
        app = web.Application()
        add_bridge_routes(app, identity, store, hub, lambda request: True)
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=.2)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0, ssl_context=identity.tls_context())
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        com = FakeCom()
        ctl = AppController(tmp_path / 'app', protector=Protector(), com_factory=lambda p: com,
                            list_ports=lambda: ['COM4', 'COM5'], discover=lambda eps: (),
                            demo_count=demo_count, demo_rate_hz=20)
        endpoint = f'https://127.0.0.1:{port}'
        raw = json.dumps(dict(asdict(BridgeProfile(1, identity.pi_id, 'Integration-Pi', identity.certificate_pem,
                                                   identity.fingerprint, (endpoint,), 2, None)),
                              endpoints=[endpoint])).encode()
        states = []

        def bind(*, demo=True):
            state = OutputState(tmp_path / f'run-{len(states)}', demo=demo)
            state.start()
            hub.bind_run(state.run_id, state)
            states.append(state)
            return state
        try:
            await asyncio.to_thread(exercise, ctl, com, store, raw, bind, identity)
        finally:
            await asyncio.to_thread(ctl.request_exit, True)
            await asyncio.sleep(.05)
            await runner.cleanup()
            hub.close()
            for s in states:
                s.stop()
    asyncio.run(main())


def connect_and_pair(ctl, store, raw):
    ctl.set_port_pair('COM4', 'COM5')
    ctl.load_profile(raw)
    offer = store.create_offer('network', ctl.client_id)
    ctl.pair(offer, True)
    ctl.connect('network')
    wait_for(lambda: ctl.snapshot().peer == 'authenticated')
    return offer


def test_demo_of_ten_values_reaches_fake_com_and_ui_says_demo_only(tmp_path, identity):
    def check(ctl, com, store, raw, bind, identity):
        offer = connect_and_pair(ctl, store, raw)
        token = ctl._credentials.load(identity.pi_id, 'network', expected_pin=identity.fingerprint)
        assert token and token != offer                        # Token landet im Store, gebunden an den Pin
        wait_for(lambda: ctl.worker_status() is not None and ctl.worker_status().active)
        assert com.payloads == []                              # Verbinden startet nichts
        ctl.begin_demo_check(True)
        wait_for(lambda: len(com.payloads) == 10)
        ctx, r, w = ctl.context(), ctl.snapshot(), ctl.worker_status()
        assert ctx.demo and ctx.dut_locked and ctx.receipt is None
        chips = {c.key: c for c in texts.chips(r, w, ctx)}
        assert chips['output'].word == 'Demo-Werte' and chips['output'].tone == 'warn'
        assert chips['forward'].word == 'Bestätigt' and 'Demo' in chips['forward'].sub
        assert chips['gsv'].word != 'Empfang belegt'
        assert texts.dut_line(ctx)[0] == texts.DUT_LOCK_LINE
        assert any(e.title == 'Weitergabe' for e in ctl.context().journal)
        assert ctx.last_ack.startswith('COM-Weitergabe bestätigt')
        for path in (tmp_path / 'app').rglob('*'):
            if path.is_file():
                assert offer.encode() not in path.read_bytes() and token.encode() not in path.read_bytes()
    run_rig(tmp_path, identity, check)


def test_dut_block_from_pi_shows_lock_and_writes_nothing(tmp_path, identity):
    def check(ctl, com, store, raw, bind, identity):
        connect_and_pair(ctl, store, raw)
        state = bind(demo=False)
        state.publish(record(1))
        wait_for(lambda: ctl.snapshot().output == 'blocked')
        r, w, ctx = ctl.snapshot(), ctl.worker_status(), ctl.context()
        assert (r.output, r.next_action) == ('blocked', 'dut_release_blocked')
        assert state.status()['release_block'] == RELEASE_BLOCK
        assert ctx.dut_locked and com.payloads == []
        out = {c.key: c for c in texts.chips(r, w, ctx)}['output']
        assert out.word == 'DUT gesperrt'
        assert texts.dut_line(ctx)[0] == texts.DUT_LOCK_LINE
    run_rig(tmp_path, identity, check)


def test_exit_stops_worker_and_releases_connection(tmp_path, identity):
    def check(ctl, com, store, raw, bind, identity):
        connect_and_pair(ctl, store, raw)
        wait_for(lambda: ctl.worker_status() is not None and ctl.worker_status().active)
        assert ctl.request_exit(True) is True
        wait_for(lambda: not ctl.worker_status().active)
        assert ctl.snapshot().peer == 'disconnected' and com.closed
    run_rig(tmp_path, identity, check)
