"""AppController gegen Fakes (Transport, COM, Geräte, DPAPI); kein Windows nötig."""
import json
import logging
import threading
import time
import zipfile
from dataclasses import asdict

import pytest
from dispread_bridge_app.app_controller import AppController, AppError
from dispread_bridge_app.transports import TransportError
from dispread_bridge_app.types import DeviceInfo
from dispread_bridge_app.ui import texts
from dispread_bridge_app.worker import WorkerStatus

from dispread.bridge.identity import DeviceIdentity
from dispread.bridge.types import BridgeProfile

CODE = 'Q' * 43


class Protector:
    def __init__(self):
        self.v = {}

    def protect(self, raw):
        k = bytes([len(self.v) + 1]) * 8
        self.v[k] = raw
        return k

    def unprotect(self, raw):
        return self.v[raw]


@pytest.fixture(scope='module')
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp('ac-id'), 'ac-pi')


def profile_bytes(identity, offer=None, endpoints=('https://127.0.0.1:9',)):
    p = BridgeProfile(1, identity.pi_id, 'Prüfstand 2', identity.certificate_pem, identity.fingerprint,
                      endpoints, 2, offer)
    return json.dumps(dict(asdict(p), endpoints=list(endpoints))).encode()


class HangTransport:
    """Bleibt im Verbinden: wirft nach Abbruch."""
    def __init__(self, seen, profile, cancel):
        seen.append(profile)
        cancel.wait(5)
        raise TransportError('cancelled')


def make(tmp_path, **kw):
    seen = []

    def factory(profile, client_id, mode, credential, device, cancel):
        return HangTransport(seen, profile, cancel)
    kw.setdefault('transport_factory', factory)
    kw.setdefault('list_ports', lambda: ['COM3', 'COM4', 'COM5'])
    kw.setdefault('com_factory', lambda port: pytest.fail('COM darf hier nicht geöffnet werden'))
    kw.setdefault('protector', Protector())
    kw.setdefault('network_diagnostics', lambda: None)
    c = AppController(tmp_path / 'app', **kw)
    c.seen = seen
    return c


class FakeWorker:
    def __init__(self, manager, com_factory, journal, emit, status=None):
        self.status = status or WorkerStatus('idle', False, False, None)
        self.started = self.stopped = 0

    def start(self): self.started += 1
    def stop(self): self.stopped += 1
    def is_active(self): return self.status.active


def test_profile_load_shows_name_and_fingerprint(tmp_path, identity):
    c = make(tmp_path)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    ctx = c.context()
    assert ctx.pi_name == 'Prüfstand 2' and ctx.pi_id == identity.pi_id
    groups = ctx.fingerprint.split()
    assert len(groups) == 16 and all(len(g) == 4 for g in groups)
    assert ''.join(groups) == identity.fingerprint


def test_invalid_profile_is_rejected_with_code(tmp_path):
    c = make(tmp_path)
    with pytest.raises(AppError) as e:
        c.load_profile(b'{"schema": 1}')
    assert e.value.code == 'profile_invalid'
    assert c.context().pi_name is None


def test_pairing_needs_confirmation_and_code_is_never_persisted_or_logged(tmp_path, identity, caplog):
    caplog.set_level(logging.DEBUG)
    c = make(tmp_path)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    with pytest.raises(AppError) as e:
        c.pair(CODE, False)
    assert e.value.code == 'fingerprint_unconfirmed'
    with pytest.raises(AppError) as e:
        c.pair('zu-kurz', True)
    assert e.value.code == 'code_invalid'
    c.pair(CODE, True)
    c.connect('network')
    deadline = time.monotonic() + 3
    while not c.seen and time.monotonic() < deadline:
        time.sleep(.01)
    assert c.seen[0].pairing_offer == CODE            # der Kern bekommt den Code
    c.disconnect()
    for path in (tmp_path / 'app').rglob('*'):
        if path.is_file():
            assert CODE.encode() not in path.read_bytes()
    assert CODE not in caplog.text
    c2 = make(tmp_path)                                # Neustart: Code ist weg
    c2.connect('network')
    time.sleep(.1)
    assert c2.seen[-1].pairing_offer is None
    c2.disconnect()


def test_manual_port_pair_is_marked_and_validated(tmp_path):
    c = make(tmp_path)
    assert c.snapshot().components == 'missing'
    for bad in (('COM4', 'COM4'), ('COM4', 'COM9'), ('x', 'COM5')):
        with pytest.raises(AppError) as e:
            c.set_port_pair(*bad)
        assert e.value.code == 'portpair_invalid'
    c.set_port_pair('COM4', 'COM5')
    ctx = c.context()
    assert (ctx.bridge_port, ctx.gsv_port) == ('COM4', 'COM5')
    assert c.snapshot().components == 'manual_pair'
    chip = texts.chips(c.snapshot(), None, ctx)[0]
    # Runde 3: Zustandswort in der Kachel, das Paar als Wert in der Zweitzeile (Textbudget R3-2)
    assert (chip.word, chip.sub) == ('Portpaar manuell', 'COM4 ↔ COM5') and chip.tone == 'info'


def test_install_components_never_creates_a_pair(tmp_path):
    c = make(tmp_path)
    result = c.install_components()
    assert result.error_code == 'vcom_unverified' and result.pair is None
    assert c.context().setup.variant == 'E1manual'
    assert c.context().setup.data['ports'] == ('COM3', 'COM4', 'COM5')


def test_connect_needs_profile_and_port_pair(tmp_path, identity):
    c = make(tmp_path)
    with pytest.raises(AppError) as e:
        c.connect('network')
    assert e.value.code == 'profile_required'
    c.load_profile(profile_bytes(identity))
    with pytest.raises(AppError) as e:
        c.connect('network')
    assert e.value.code == 'portpair_required'


def test_demo_only_after_explicit_action(tmp_path, identity):

    from dispread_bridge_app.readiness import Readiness

    class M:
        def __init__(self, profile, client_id, credentials, devices, **kw):
            self.demo = []
            self.connected = None

        def set_worker(self, w): pass
        def connect(self, mode, selected=None): self.connected = (mode, selected)
        def disconnect(self): pass
        def snapshot(self): return Readiness('ready', 'not_required', 'authenticated', 'output_off', 'idle',
                                             'unconfirmed', 'output_off')
        def start_demo(self, count, rate): self.demo.append((count, rate))

    c = make(tmp_path, manager_factory=M, worker_factory=FakeWorker, demo_count=10, demo_rate_hz=20)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.connect('network')
    time.sleep(.2)
    assert c._manager.demo == []                      # Verbinden startet keine Demo
    assert c._worker.started == 1                     # Worker erst nach Authentifizierung
    with pytest.raises(AppError) as e:
        c.begin_demo_check(False)
    assert e.value.code == 'demo_not_confirmed' and c._manager.demo == []
    c.begin_demo_check(True)
    assert c._manager.demo == [(10, 20)]
    assert c.context().waiting_for_run


def test_worker_failure_overrules_paired_pi(tmp_path, identity):
    status = WorkerStatus('blocked', False, False, 'unknown_delivery')
    c = make(tmp_path, worker_factory=lambda m, f, j, e: FakeWorker(m, f, j, e, status))
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.connect('network')
    r, w, ctx = c.snapshot(), c.worker_status(), c.context()
    assert r.next_action == 'unknown_delivery' and r.output == 'blocked'
    assert texts.headline(r, w, ctx).text.startswith('Übertragung gestoppt')
    assert texts.headline(r, w, ctx).tone == 'err'
    c.disconnect()


def test_dut_lock_is_always_set(tmp_path):
    ctx = make(tmp_path).context()
    assert ctx.dut_locked is True and ctx.release is None and ctx.receipt is None
    assert texts.dut_line(ctx)[0] == texts.DUT_LOCK_LINE


def test_exit_stops_worker_and_disconnects(tmp_path, identity):
    c = make(tmp_path, worker_factory=FakeWorker)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.connect('network')
    worker = c._worker
    assert c.request_exit(False) is False and worker.stopped == 0
    assert c.request_exit(True) is True
    assert worker.stopped >= 1


def test_state_survives_restart_with_stable_client_id(tmp_path, identity):
    c = make(tmp_path)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.select_route('uart')
    first = c.client_id
    c2 = make(tmp_path)
    assert c2.client_id == first
    ctx = c2.context()
    assert ctx.pi_name == 'Prüfstand 2' and ctx.bridge_port == 'COM4' and ctx.route.startswith('UART')
    state = json.loads((tmp_path / 'app' / 'state.json').read_text())
    assert state['version'] == 1 and state['profile']['pairing_offer'] is None


def test_two_identical_adapters_require_a_choice_and_no_silent_switch(tmp_path, identity):
    class Devices:
        def inventory(self):
            return (DeviceInfo('USB\\A', 'COM6', 0x403, 0x6001, None, 'Port 3', 0),
                    DeviceInfo('USB\\B', 'COM7', 0x403, 0x6001, None, 'Port 4', 0))

    c = make(tmp_path, devices=Devices())
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.select_route('uart')
    c.rescan()
    c._step = 3
    assert c.context().setup.variant == 'E3uart2'
    c.select_adapter('USB\\B')
    ctx = c.context()
    assert ctx.setup.variant == 'E3uart' and ctx.setup.data['choices']['adapter'] == ('USB\\A', 'USB\\B')
    c.connect('uart')
    assert c._manager is not None
    c.disconnect()


def test_active_transmission_blocks_route_change(tmp_path, identity):
    active = WorkerStatus('running', True, True, None)
    c = make(tmp_path, worker_factory=lambda m, f, j, e: FakeWorker(m, f, j, e, active))
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.connect('network')
    for call in (lambda: c.connect('uart'), lambda: c.select_route('uart'),
                 lambda: c.load_profile(profile_bytes(identity)), lambda: c.set_port_pair('COM3', 'COM5')):
        with pytest.raises(AppError) as e:
            call()
        assert e.value.code == 'transmission_active'
    assert c.context().switch_locked


def test_unreviewed_session_settings_stay_blocked_and_write_nothing(tmp_path):
    c = make(tmp_path)
    dest = tmp_path / 'out'
    dest.mkdir()
    with pytest.raises(AppError) as e:
        c.export_session({'gsv_port': 'COM5', 'scale': 1}, dest)
    assert e.value.code == 'automatic_export_blocked'
    assert list(dest.iterdir()) == []


def test_diagnostics_zip_has_no_secrets(tmp_path, identity):
    c = make(tmp_path)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity, offer=CODE))
    c.pair(CODE, True)
    out = c.export_diagnostics(tmp_path / 'diag.zip')
    with zipfile.ZipFile(out) as z:
        blob = b''.join(z.read(n) for n in z.namelist())
    assert CODE.encode() not in blob
    assert 'readiness' in json.loads(zipfile.ZipFile(out).read('summary.json'))


def test_events_reach_subscribers_and_journal_and_unsubscribe(tmp_path):
    from dispread.bridge.types import BridgeEvent
    c = make(tmp_path)
    got = []
    off = c.subscribe(got.append)
    ev = BridgeEvent('exchange', 'exchange', None, None, dict(outcome='written'))
    c._emit(ev)
    assert got == [ev] and c.context().last_ack.startswith('COM-Weitergabe bestätigt')
    assert c.context().journal[0].title == 'Demo: 1 Wert weitergegeben'
    off()
    c._emit(ev)
    assert len(got) == 1


def test_build_info_fields_shape_footer_and_channel(tmp_path):
    import types
    info = types.SimpleNamespace(version='0.1.0', commit='0123456789abcdef0123', build_time_utc='2026-11-06T10:00:00Z',
                                channel='Interner Testbuild - nicht qualifiziert')
    ctx = make(tmp_path, build_info=info).context()
    assert ctx.version == '0.1.0 · 0123456789ab'
    assert ctx.channel == 'Interner Testbuild - nicht qualifiziert'
    assert texts.version_label(ctx.version) == '0.1.0 · 0123456789ab'
    none = make(tmp_path / 'x', build_info=False).context()
    assert none.version == 'Entwicklungsstand' and none.channel is None


def test_unknown_commit_reads_as_unknown_source(tmp_path):
    import types
    info = types.SimpleNamespace(version='0.1.0.dev0', commit='unbekannt', channel=None)
    assert make(tmp_path, build_info=info).context().version == '0.1.0.dev0 · Quelle unbekannt'


def _connected(tmp_path, identity, output='output_off', start_error=None):
    from dispread_bridge_app.readiness import Readiness

    class M:
        def __init__(self, profile, client_id, credentials, devices, **kw):
            self.out = output
            self.demo = []

        def set_worker(self, w): pass
        def connect(self, mode, selected=None): pass
        def disconnect(self): pass

        def snapshot(self):
            return Readiness('ready', 'not_required', 'authenticated', self.out, 'idle', 'unconfirmed',
                             {'output_off': 'output_off', 'blocked': 'dut_release_blocked'}.get(self.out))

        def start_demo(self, count, rate):
            if start_error:
                raise start_error
            self.demo.append((count, rate))

    c = make(tmp_path, manager_factory=M, worker_factory=FakeWorker)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.connect('network')
    return c


def test_step4_needs_manual_confirmation_then_step5(tmp_path, identity):
    c = _connected(tmp_path, identity)
    c._step = 4
    spec = texts.setup_spec(c.context())
    assert 'UserDef' in repr(spec['blocks']) and 'COM5' in repr(spec['blocks'])
    with pytest.raises(AppError) as e:
        c.setup_step('next')
    assert e.value.code == 'session_unconfirmed'
    c.confirm_session(True)
    c.setup_step('next')
    assert c.context().setup.step == 5


def test_running_measurement_blocks_demo_with_clear_text(tmp_path, identity):
    c = _connected(tmp_path, identity, output='blocked')
    c._step = 5
    assert c.context().setup.variant == 'E5busy'
    with pytest.raises(AppError) as e:
        c.begin_demo_check(True)
    assert e.value.code == 'run_active'
    assert 'Auf dem Pi läuft ein Messlauf.' in texts.explain_code('run_active')[0]


@pytest.mark.parametrize('code', ['run_conflict', 'peer_refused', 'demo_unconfirmed'])
def test_demo_rejection_codes_map_to_run_explanation(tmp_path, identity, code):
    from dispread_bridge_app.connection import ConnectionError as CE
    c = _connected(tmp_path, identity, start_error=CE(code))
    c._step = 5
    with pytest.raises(AppError) as e:
        c.begin_demo_check(True)
    assert e.value.code == 'demo_rejected'
    assert 'Messlauf' in ' '.join(texts.explain_code('demo_rejected'))


def test_overview_and_resume_switch_mode_without_finishing_setup(tmp_path, identity):
    c = _connected(tmp_path, identity)
    assert c.context().mode == 'setup'
    c.setup_step('overview')
    assert c.context().mode == 'operate'
    c.setup_step('resume')
    assert c.context().mode == 'setup'
    c._step = 5
    c.setup_step('finish')
    assert c.context().mode == 'operate'


def test_step3_next_with_active_worker_never_reconnects(tmp_path, identity):
    active = WorkerStatus('recovering', True, False, None)
    c = make(tmp_path, worker_factory=lambda m, f, j, e: FakeWorker(m, f, j, e, active))
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c.connect('network')
    c._step = 3
    with pytest.raises(AppError) as e:
        c.setup_step('next')
    assert e.value.code == 'not_connected'                  # nicht transmission_active, kein connect


# ---- BQ4: _emit blockiert nicht, Diagnose gebuendelt, Journal verdichtet
def _ev(outcome, kind='exchange'):
    from dispread.bridge.types import BridgeEvent
    return BridgeEvent(kind, outcome, None, None, dict(outcome=outcome))


def test_emit_returns_immediately_with_slow_store(tmp_path):
    import time
    c = make(tmp_path)
    gate = threading.Event()

    class Slow:
        def append(self, ev):
            gate.wait(5)
        def export(self):
            return b''
    c._diag = Slow()
    t = time.monotonic()
    for _ in range(50):
        c._emit(_ev('failed'))
    assert time.monotonic() - t < 0.2
    gate.set()


def test_emit_overflow_counts_instead_of_blocking(tmp_path, monkeypatch):
    import time

    from dispread_bridge_app import app_controller as ac
    monkeypatch.setattr(ac, 'DIAG_QUEUE_MAX', 3)
    c = make(tmp_path)
    gate = threading.Event()

    class Slow:
        def __init__(self):
            self.got = []
        def append(self, ev):
            gate.wait(5)
            self.got.append(ev)
        def export(self):
            return b''
    slow = c._diag = Slow()
    t = time.monotonic()
    for _ in range(20):
        c._emit(_ev('failed'))
    assert time.monotonic() - t < 0.2
    assert c._diag_dropped > 0
    gate.set()
    c._diag_flush()
    assert any(e.kind == 'diagnostics' and e.detail['count'] > 0 for e in slow.got)


def test_written_events_are_summarised_in_diagnostics(tmp_path):
    c = make(tmp_path)
    got = []
    c._diag = type('S', (), {'append': lambda self, ev: got.append(ev), 'export': lambda self: b''})()
    for _ in range(500):
        c._emit(_ev('written'))
    c._diag_flush()
    written = [e for e in got if e.kind == 'exchange']
    assert len(written) <= 2 and sum(e.detail['count'] for e in written) == 500


def test_journal_counter_line_updates_in_place_and_is_bounded(tmp_path):
    c = make(tmp_path)
    for _ in range(1000):
        c._emit(_ev('written'))
    j = c.context().journal
    assert len(j) == 1 and j[0].title == 'Demo: 1000 Werte weitergegeben'
    for _ in range(1000):
        c._emit(_ev('idle'))
        c._emit(_ev('failed'))
    assert len(c.context().journal) <= 500


def test_repeated_idle_is_one_journal_line(tmp_path):
    c = make(tmp_path)
    for _ in range(100):
        c._emit(_ev('idle'))
    assert [e.title for e in c.context().journal] == ['Wartet auf Messlauf']
    c._emit(_ev('written'))
    c._emit(_ev('idle'))
    assert len(c.context().journal) == 3


def test_diagnostics_export_contains_flushed_summary(tmp_path, identity):
    c = make(tmp_path)
    for _ in range(10):
        c._emit(_ev('written'))
    out = c.export_diagnostics(tmp_path / 'diag.zip')
    lines = zipfile.ZipFile(out).read('details.jsonl').decode()
    assert 'written_summary' in lines and lines.count('\n') <= 2


def _tr_ev(outcome, release=True):
    from dispread.bridge.types import BridgeEvent
    detail = dict(outcome=outcome, **({'release': 'test_unaccepted'} if release else {}))
    return BridgeEvent('exchange', outcome, None, None, detail)


def test_test_release_journal_counters_and_transitions(tmp_path):
    c = make(tmp_path)
    for _ in range(3):
        c._emit(_tr_ev('written'))
    c._emit(_tr_ev('omitted'))
    c._emit(_tr_ev('written'))
    titles = [e.title for e in c.context().journal]
    assert titles[-1].startswith('Testfreigabe aktiv (Lauf ')
    assert 'Testfreigabe: 4 Werte weitergegeben' in titles and 'Wert ausgelassen' in titles
    assert (c._tr_written, c._tr_omitted) == (4, 1)
    c._emit(_tr_ev('idle', release=False))
    assert [e.title for e in c.context().journal[:2]] == ['Wartet auf Messlauf', 'Ausgabe wieder gesperrt']
    c._emit(_tr_ev('written'))         # neue Freigabe: Zähler beginnen neu
    assert c._tr_written == 1 and c._tr_omitted == 0


def test_demo_check_ends_clearly_even_when_values_are_missing(tmp_path):
    """13.11.2026: Fortschritt blieb bei 588/600 stehen; der Pi meldete ``ended`` nie sichtbar."""
    now = [100.0]
    c = make(tmp_path, clock=lambda: now[0], demo_count=600, demo_rate_hz=10)
    from dispread_bridge_app.readiness import Readiness
    r = Readiness('ready', 'not_required', 'authenticated', 'output_off', 'idle', 'unconfirmed', 'output_off')
    c._step = 5
    with c._lock:
        c._demo_started, c._written, c._demo_ended, c._demo_t0 = True, 588, False, now[0]
    assert c._variant(r, None)[0] == 'E5run'
    c._emit(_ev('ended'))                               # Pi meldet das Ende
    variant, data = c._variant(r, None)
    assert variant == 'E5short' and (data['written'], data['count'], data['missing']) == (588, 600, 12)
    with c._lock:
        c._demo_ended = False
    now[0] += 600 / 10 + 10.5                           # ohne ``ended``: spätestens nach Dauer + Puffer
    assert c._variant(r, None)[0] == 'E5short'
    with c._lock:
        c._written = 600
    assert c._variant(r, None)[0] == 'E5done'


def test_pairing_is_judged_per_route(tmp_path, identity):
    """13.11.2026: Netzwerk-Token vorhanden, Weg UART über Brücke -> Schritt 2 sagte „gekoppelt“,
    der Verbindungsaufbau „nicht gekoppelt“; „Neuen Code eingeben“ führte im Kreis."""
    c = make(tmp_path)
    c.set_port_pair('COM4', 'COM5')
    c.load_profile(profile_bytes(identity))
    c._credentials.save(identity.pi_id, 'network', 'n' * 43, expected_pin=identity.fingerprint)
    c._refresh_pairing()
    c.select_mode('network')
    assert c._is_paired()
    c.select_mode('uart_bridge')
    assert not c._is_paired()                       # UART braucht eigene Kopplung: Codefeld zeigen
