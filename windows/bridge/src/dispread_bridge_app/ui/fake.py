"""FakeController: spielt die Zustände des Mocks ab (Tests und ``--demo-ui``)."""
from __future__ import annotations

import threading
from dataclasses import replace

from dispread.bridge.types import BridgeEvent
from dispread_bridge_app.readiness import Readiness
from dispread_bridge_app.worker import WorkerStatus

from .port import JournalEntry, Receipt, SetupState, UiContext

J = JournalEntry
_FP = 'a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de'
_HEUTE = (
    J('14:32:07', 'Neuer Lauf erkannt', 'Lauf 7 · DUT-Ausgabe gesperrt', tone='ok'),
    J('14:31:55', 'Pi-Lauf beendet', 'Lauf 6'),
    J('14:12:40', 'Verbindung unterbrochen', 'wieder verbunden · Netzwerk (LAN), gleicher Pi', '4 s', 'warn', fault=True),
    J('14:05:12', 'Lauf 6 verbunden – Ausgabe gesperrt', 'Windows-Abnahme fehlt · keine Werte an COM geschrieben'),
    J('13:58:30', 'Pi verbunden (Identität geprüft)', 'Prüfstand 2 · pi-4b7e09c1', tone='ok'),
    J('13:58:29', 'Brücke gestartet', 'Version 0.1.0.dev0', tone='ok'),
    J('17:02:11', 'Brücke beendet', 'Auf Wunsch des Bedieners', day='Gestern'),
    J('16:20:03', 'COM4 (Brückenseite): Schreibfehler', 'Demo · Wert nicht erneut gesendet · weiter mit dem nächsten Wert',
      '1 Wert', 'warn', 'Gestern', True),
    J('15:44:51', 'Pi antwortet nicht', 'wieder verbunden · Versuche nach 1, 2, 4, 8 s', '14 s', 'err', 'Gestern', True),
    J('15:10:02', 'Pi verbunden (Identität geprüft)', 'Prüfstand 2 · pi-4b7e09c1', tone='ok', day='Gestern'),
)
_OK = Readiness('ready', 'not_required', 'authenticated', 'demo_only', 'driver_ready', 'unconfirmed', None)
_IDLE = WorkerStatus('idle', False, False, None)
_RUN = WorkerStatus('running', True, True, None)
_BASE = UiContext(bridge_port='COM4', gsv_port='COM5', version='0.1.0.dev0', protocol='Version 2',
                  pi_name='Prüfstand 2', route='Netzwerk (LAN)', run_id='7', pi_id='pi-4b7e09c1',
                  endpoint='wss://192.168.10.24 (LAN, Beispiel)', fingerprint=_FP,
                  last_report='Leerlauf, Ausgabe gesperrt – es werden keine Werte an COM geschrieben',
                  session_name='GSVmulti_Prüfstand2_COM5.ucf', session_confirmed=True, journal=_HEUTE,
                  paired=(('Prüfstand 2', 'pi-4b7e09c1', 'zuletzt vor 2 Stunden'),
                          ('Prüfstand 3 – Halle A', 'pi-d21a77e6', 'zuletzt gestern')))


_DATA = dict(peer_fingerprint='a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 55e0 1b6c 9a46 3f02',
             test_sha256='9f2c 41ab 07d3 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de')


def _setup(variant, step, **kw):
    pre = dict(pi_name=None, route=None) if variant in ('E1', 'E1uac', 'E1restart', 'E1ok', 'E2') else {}
    if variant in ('E3uart', 'E3uart2', 'E3fail'):
        pre = dict(route='UART (USB-Adapter)')
    return (replace(_OK, peer='disconnected', output='unavailable', com='unknown'), None,
            replace(_BASE, mode='setup', setup=SetupState(step, variant, dict(_DATA)), **pre, **kw))


STATES: dict[str, tuple] = {
    'B1': (_OK, _RUN, _BASE),
    'B1t': (_OK, _RUN, replace(_BASE, receipt=Receipt(True, 'Test 14:02 (Demo), 600/600',
                                                      'GSVmulti_Test_Prüfstand2.txt', demo=True))),
    'B1x': (_OK, _RUN, replace(_BASE, dut_locked=False, release='Ausgabe freigegeben am TT.MM.JJJJ '
                               '(Abnahme-ID: Platzhalter)', last_ack='COM-Weitergabe bestätigt (Bild 18342) – '
                                                                       'kein GSVmulti-Empfangsnachweis',
                               switch_locked=True)),
    'B2': (_OK, _RUN, replace(_BASE, waiting_for_run=True, run_id=None)),
    'B3': (replace(_OK, peer='backoff', output='unavailable', com='unknown', next_action='reconnect'),
           None, replace(_BASE, retry_in_s=4, last_report='14:32:20')),
    'B4a': (_OK, _RUN, replace(_BASE, demo=True, com_issue='busy')),
    'B4b': (_OK, _RUN, replace(_BASE, demo=True, com_issue='write_failed')),
    'B4c': (_OK, _RUN, replace(_BASE, demo=True, com_issue='unclear')),
    'B5': (_OK, _RUN, replace(_BASE, demo=True)),
    'B10': (replace(_OK, peer='disconnected', output='unavailable', com='unknown'), None,
            replace(_BASE, pi_name='Prüfstand 3 – Halle A', pi_id='pi-d21a77e6', session_confirmed=False)),
    'blocked': (_OK, WorkerStatus('blocked', False, False, 'unknown_delivery'), _BASE),
    'usb_missing': (replace(_OK, adapter='unavailable', peer='disconnected', output='unavailable',
                            com='unknown', next_action='adapter_unavailable'), None,
                    replace(_BASE, route='UART (USB-Adapter)')),
    'E1': _setup('E1', 1), 'E1uac': _setup('E1uac', 1), 'E1restart': _setup('E1restart', 1),
    'E1ok': _setup('E1ok', 1), 'E2': _setup('E2', 2), 'E2b': _setup('E2b', 2), 'E2exp': _setup('E2exp', 2),
    'E2bad': _setup('E2bad', 2), 'E2ok': _setup('E2ok', 2), 'E3': _setup('E3', 3), 'E3uart': _setup('E3uart', 3),
    'E3uart2': _setup('E3uart2', 3), 'E3ok': _setup('E3ok', 3), 'E3fail': _setup('E3fail', 3),
    'E4': _setup('E4', 4), 'E4ok': _setup('E4ok', 4), 'E4unk': _setup('E4unk', 4), 'E5': _setup('E5', 5),
    'E5run': _setup('E5run', 5), 'E5file': _setup('E5file', 5), 'E5ok': _setup('E5ok', 5),
    'E5bad': _setup('E5bad', 5),
}


class FakeController:
    def __init__(self, state: str = 'B1'):
        self.calls: list[tuple] = []
        self._subs: list = []
        self._lock = threading.Lock()
        self.call_threads: list[int] = []
        self.set_state(state)
        self.exit_result = True

    def set_state(self, key: str) -> None:
        self._r, self._w, self._c = STATES[key]

    def set(self, readiness=None, worker='keep', context=None) -> None:
        if readiness is not None:
            self._r = readiness
        if worker != 'keep':
            self._w = worker
        if context is not None:
            self._c = context

    def _rec(self, name, *a):
        self.call_threads.append(threading.get_ident())
        self.calls.append((name, *a))

    # Port
    def load_profile(self, raw): self._rec('load_profile', raw); return self._r
    def install_components(self): self._rec('install_components')
    def connect(self, mode, selected_device_id=None): self._rec('connect', mode, selected_device_id)
    def disconnect(self): self._rec('disconnect')
    def export_session(self, settings, destination): self._rec('export_session', settings, destination)
    def begin_demo_check(self, confirmed_test_session): self._rec('begin_demo_check', confirmed_test_session)

    def request_exit(self, confirmed):
        self._rec('request_exit', confirmed)
        return self.exit_result if confirmed else False

    def subscribe(self, callback):
        self._subs.append(callback)
        return lambda: self._subs.remove(callback)

    def snapshot(self): return self._r
    def worker_status(self): return self._w
    def context(self): return self._c

    def emit(self, event: BridgeEvent) -> None:
        """Aus beliebigem Thread aufrufbar, wie der echte Workerthread."""
        for cb in list(self._subs):
            cb(event)
