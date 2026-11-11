"""FakeController: spielt die Zustände des Mocks ab (Tests und ``--demo-ui``)."""
from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import replace
from pathlib import Path

from dispread.bridge.types import BridgeEvent
from dispread_bridge_app.readiness import Readiness
from dispread_bridge_app.worker import WorkerStatus

from .port import (
    MODES,
    CheckResult,
    JournalEntry,
    ModeInfo,
    PortChoice,
    Receipt,
    SessionExport,
    SetupState,
    UiContext,
)

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
                          ('Prüfstand 3 – Halle A', 'pi-d21a77e6', 'zuletzt gestern')),
                  route_mode='network', activity_seq=1, uart_baud=460800, gsv_baud=115200,
                  session_template='Session-COM8.ucf')


_DATA = dict(peer_fingerprint='a3f9 0c1d 7b42 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 55e0 1b6c 9a46 3f02',
             test_sha256='9f2c 41ab 07d3 e58a 19d6 f03c 84ab 2e71 5c0d b8f4 63a9 d127 0e5b c3f8 9a46 71de')


def _setup(variant, step, **kw):
    pre = (dict(pi_name=None, route=None, route_mode=None, activity_seq=0)
           if variant in ('E1', 'E1uac', 'E1restart', 'E1ok', 'E2') else dict(activity_seq=0))
    if variant in ('E3uart', 'E3uart2', 'E3fail'):
        pre = dict(route='UART (USB-Adapter)', route_mode='uart_bridge', adapter_port='COM9', adapter_present=True,
                   activity_seq=0)
    pre['setup_leavable'] = variant not in ('E1', 'E1uac', 'E1restart', 'E1ok', 'E2')
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
    'B1tr': (replace(_OK, output='test_release', next_action=None), WorkerStatus('running', True, True, None, demo_only=False),
             replace(_BASE, test_release=True, forwarded=128, omitted=5,
                     last_ack='COM-Weitergabe bestätigt – kein GSVmulti-Empfangsnachweis',
                     journal=(J('14:41:09', 'Wert ausgelassen', 'ungültig oder veraltet – nichts an COM geschrieben', tone='warn'),
                              J('14:40:02', 'Testfreigabe: 128 Werte weitergegeben',
                                'COM-Weitergabe · nicht abgenommen · kein GSVmulti-Empfangsnachweis', tone='warn'),
                              J('14:38:11', 'Testfreigabe aktiv (Lauf 7)', 'echte Werte, nicht abgenommen', tone='warn')) + _HEUTE)),
    'B2': (_OK, _RUN, replace(_BASE, waiting_for_run=True, run_id=None)),
    'B3': (replace(_OK, peer='backoff', output='unavailable', com='unknown', next_action='reconnect'),
           None, replace(_BASE, retry_in_s=4, last_report='14:32:20')),
    'B3c': (replace(_OK, peer='connecting', output='unavailable', com='unknown', next_action=None),
            None, replace(_BASE, last_report='')),
    'B4a': (_OK, _RUN, replace(_BASE, demo=True, com_issue='busy')),
    'B4b': (_OK, _RUN, replace(_BASE, demo=True, com_issue='write_failed')),
    'B4c': (_OK, _RUN, replace(_BASE, demo=True, com_issue='unclear')),
    'B5': (_OK, _RUN, replace(_BASE, demo=True)),
    'B10': (replace(_OK, peer='disconnected', output='unavailable', com='unknown'), None,
            replace(_BASE, pi_name='Prüfstand 3 – Halle A', pi_id='pi-d21a77e6', session_confirmed=False)),
    'Bdirect': (replace(_OK, adapter='ready', peer='disconnected', output='unavailable', com='unknown',
                        next_action=None), None,
                replace(_BASE, route='UART direkt (COM9)', route_mode='uart_direct', adapter_port='COM9',
                        adapter_present=True, run_id=None, journal=(), activity_seq=0)),
    'E3ok_run': (_OK, _RUN, replace(_setup('E3ok', 3)[2])),
    'E3_run': (_OK, _RUN, replace(_setup('E3', 3)[2], setup=SetupState(3, 'E3', dict(
        found_items=(('https://pi.local', 'aus dem Profil', True),), choices={'found': ('https://pi.local',)})))),
    'E4locked_run': (_OK, _RUN, replace(_setup('E4locked', 4)[2])),
    'E1ok_run': (_OK, _RUN, replace(_setup('E1ok', 1)[2])),
    'E2ok_run': (_OK, _RUN, replace(_setup('E2ok', 2)[2])),
    'E5_run': (_OK, _RUN, replace(_setup('E5', 5)[2])),
    'E5busy': (replace(_OK, output='blocked', next_action='dut_release_blocked'), _RUN, replace(_setup('E5busy', 5)[2])),
    'blocked': (_OK, WorkerStatus('blocked', False, False, 'unknown_delivery'), _BASE),
    'usb_missing': (replace(_OK, adapter='unavailable', peer='disconnected', output='unavailable',
                            com='unknown', next_action='adapter_unavailable'), None,
                    replace(_BASE, route='UART (USB-Adapter)', route_mode='uart_bridge', adapter_port='COM9',
                            adapter_present=False)),
    'E1': _setup('E1', 1), 'E1uac': _setup('E1uac', 1), 'E1restart': _setup('E1restart', 1),
    'E1ok': _setup('E1ok', 1), 'E2': _setup('E2', 2), 'E2b': _setup('E2b', 2), 'E2exp': _setup('E2exp', 2),
    'E2bad': _setup('E2bad', 2), 'E2ok': _setup('E2ok', 2), 'E3': _setup('E3', 3), 'E3uart': _setup('E3uart', 3),
    'E3uart2': _setup('E3uart2', 3), 'E3ok': _setup('E3ok', 3), 'E3fail': _setup('E3fail', 3),
    'E4': _setup('E4', 4), 'E4ok': _setup('E4ok', 4), 'E4unk': _setup('E4unk', 4), 'E5': _setup('E5', 5),
    'E5run': _setup('E5run', 5), 'E5file': _setup('E5file', 5), 'E5ok': _setup('E5ok', 5),
    'E5bad': _setup('E5bad', 5),
}


_PORTS = (PortChoice('COM4', 'COM4 – com0com Brückenseite', 'com0com', False),
          PortChoice('COM5', 'COM5 – com0com GSVmulti-Seite', 'com0com', False),
          PortChoice('COM1', 'COM1 – Kommunikationsanschluss', 'other', None),
          PortChoice('COM9', 'COM9 – FTDI USB Serial', 'usb_serial', False, 'FTDIBUS\\VID_0403+PID_6001+A10KX3QZ'))
_KNOWN_HOSTS = {'pi.local': 'ok', '192.168.10.24': 'ok', 'pruefstand2.tail1234.ts.net': 'ok',
                'pi-alt.local': 'fingerprint'}
_HOST = re.compile(r'^(?:wss?://|https?://)?([A-Za-z0-9.-]+)(?::(\d{1,5}))?/?$')
_CONTENTS = (('summary.json', 'Version, Bereitschaft, Worker-Zustand, Weg, Portpaar und Zähler der Übergaben '
                              'je Ergebnis'),
             ('details.jsonl', 'Ereignisprotokoll der App – Zugangsdaten redigiert, keine Messwerte'))
_SESSION_PLACEHOLDER = '; Platzhalter der Demo-Oberfläche – keine GSVmulti-Session\r\n[ch1]\r\nComNr={n}\r\n'


class FakeController:
    def __init__(self, state: str = 'B1', heartbeat_s: float | None = None):
        self.calls: list[tuple] = []
        self._subs: list = []
        self._lock = threading.Lock()
        self.call_threads: list[int] = []
        self.set_state(state)
        self.exit_result = True
        self._beat_stop = threading.Event()
        if heartbeat_s:                       # nur --demo-ui: Herzschlag wie ein echter Pi-Austausch
            threading.Thread(target=self._beat, args=(heartbeat_s,), name='fake-heartbeat', daemon=True).start()

    def _beat(self, every: float) -> None:
        while not self._beat_stop.wait(every):
            if self._r.peer == 'authenticated':
                try:
                    self.tick()
                except RuntimeError:          # Fenster beim Beenden schon abgebaut
                    return

    def tick(self) -> None:
        """Ein erfolgreicher Austausch mit dem Pi: ``activity_seq`` zählt hoch (Herzschlag)."""
        self._c = replace(self._c, activity_seq=self._c.activity_seq + 1)
        self.emit(BridgeEvent('exchange', 'idle', None, None, dict(outcome='idle')))

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
    def load_profile(self, raw):
        self._rec('load_profile', raw)
        return self._r
    def install_components(self): self._rec('install_components')
    def connect(self, mode, selected_device_id=None): self._rec('connect', mode, selected_device_id)
    def disconnect(self): self._rec('disconnect')
    def export_session(self, settings, destination): self._rec('export_session', settings, destination)
    def begin_demo_check(self, confirmed_test_session): self._rec('begin_demo_check', confirmed_test_session)
    def pair(self, code, fingerprint_confirmed): self._rec('pair', fingerprint_confirmed)   # Code nie aufzeichnen
    def select_route(self, mode): self._rec('select_route', mode)
    def select_endpoint(self, endpoint, manual=False): self._rec('select_endpoint', endpoint, manual)
    def select_adapter(self, device_id): self._rec('select_adapter', device_id)
    def set_port_pair(self, bridge_port, gsv_port): self._rec('set_port_pair', bridge_port, gsv_port)
    def open_manual_pair(self): self._rec('open_manual_pair')
    def rescan(self): self._rec('rescan')
    def confirm_session(self, on): self._rec('confirm_session', on)
    def setup_step(self, direction): self._rec('setup_step', direction)
    def set_auto_connect(self, on): self._rec('set_auto_connect', on)
    def auto_connect_at_start(self):
        self._rec('auto_connect_at_start')
        return False
    def switch_pi(self, pi_id): self._rec('switch_pi', pi_id)
    def export_diagnostics(self, destination):
        self._rec('export_diagnostics', destination)
        return destination

    def request_exit(self, confirmed):
        self._rec('request_exit', confirmed)
        if confirmed:
            self._beat_stop.set()
        return self.exit_result if confirmed else False

    # --- UX2 (spielt plausible Zustände nach; keine echten Port- oder Netzzugriffe)
    def _active_mode(self) -> str | None:
        return self._c.route_mode

    def modes(self):
        self._rec('modes')
        active, c = self._active_mode(), self._c
        busy = self._w is not None and self._w.active
        status = {
            'network': (f'gekoppelt mit {c.pi_name}' if c.pi_name and c.endpoint else 'nicht eingerichtet',
                        'ok' if active == 'network' and self._r.peer == 'authenticated' else 'info',
                        bool(c.pi_name and c.endpoint)),
            'uart_bridge': ((f'Adapter {c.adapter_port} erkannt' if c.adapter_present else
                             f'Adapter {c.adapter_port} fehlt') if c.adapter_port and active == 'uart_bridge'
                            else 'nicht eingerichtet',
                            'err' if active == 'uart_bridge' and c.adapter_present is False else 'info',
                            active == 'uart_bridge'),
            'uart_direct': ((f'Adapter {c.adapter_port} steckt' if c.adapter_present else 'Adapter steckt nicht')
                            if active == 'uart_direct' else 'nicht eingerichtet', 'info', active == 'uart_direct'),
        }
        out = []
        for m in MODES:
            text, tone, configured = status[m]
            free = not busy or m == active
            out.append(ModeInfo(m, configured, m == active, text, tone, free,
                                '' if free else 'Erst Übertragung beenden'))
        return tuple(out)

    def select_mode(self, mode):
        self._rec('select_mode', mode)
        if mode not in MODES:
            raise ValueError(mode)
        if self._w is not None and self._w.active and mode != self._active_mode():
            from dispread_bridge_app.app_controller import AppError
            raise AppError('mode_locked')
        configured = {m.mode: m.configured for m in self.modes()}
        if configured.get(mode):
            self._c = replace(self._c, route_mode=mode)
        else:
            self._c = replace(self._c, route_mode=mode, mode='setup', setup_leavable=True,
                              setup=SetupState(1, 'E1ok', dict(_DATA)))

    def leave_setup(self):
        self._rec('leave_setup')
        self._c = replace(self._c, mode='operate', setup=None)

    def list_ports(self):
        self._rec('list_ports')
        return _PORTS

    def list_adapters(self):
        self._rec('list_adapters')
        return tuple(p for p in _PORTS if p.kind == 'usb_serial')

    def check_endpoint(self, text):
        self._rec('check_endpoint', text)
        m = _HOST.match((text or '').strip())
        if not m or (m.group(2) and not 0 < int(m.group(2)) < 65536):
            return CheckResult('err', 'Keine gültige Adresse', 'Name oder IP-Adresse, z. B. pi.local')
        host = m.group(1).lower()
        known = _KNOWN_HOSTS.get(host)
        if known == 'ok':
            return CheckResult('ok', 'Pi erreichbar, Zertifikat passt')
        if known == 'fingerprint':
            return CheckResult('err', 'Pi erreichbar, aber das Zertifikat passt nicht zum Profil',
                               'Anderer Pi oder neu installiert – Profil dieses Pi neu laden')
        if re.fullmatch(r'\d+\.\d+\.\d+\.\d+', host):
            return CheckResult('err', 'Keine Antwort auf Port 8443',
                               'Ist der Pi eingeschaltet und im selben Netz? Adresse prüfen')
        return CheckResult('err', 'Name nicht auflösbar', 'Schreibweise prüfen oder die IP-Adresse eingeben')

    def check_port_pair(self, bridge_port, gsv_port):
        self._rec('check_port_pair', bridge_port, gsv_port)
        names = {p.port: p for p in _PORTS}
        if not bridge_port or not gsv_port:
            return CheckResult('err', 'Beide Ports wählen')
        if bridge_port == gsv_port:
            return CheckResult('err', 'Brückenseite und GSVmulti-Seite müssen verschieden sein')
        missing = [p for p in (bridge_port, gsv_port) if p not in names]
        if missing:
            return CheckResult('err', f'{missing[0]} nicht vorhanden', 'Liste neu einlesen')
        if self._w is not None and self._w.active:
            return CheckResult('ok', 'Portpaar in Benutzung durch diese Brücke')
        if names[bridge_port].kind != 'com0com' or names[gsv_port].kind != 'com0com':
            return CheckResult('warn', 'Ports vorhanden, aber nicht als com0com-Paar erkannt',
                               'Nur verwenden, wenn die beiden Ports sicher verbunden sind')
        return CheckResult('ok', f'{bridge_port} ↔ {gsv_port}: com0com-Paar, frei')

    def check_adapter(self, port):
        self._rec('check_adapter', port)
        p = {q.port: q for q in _PORTS}.get(port)
        if p is None:
            return CheckResult('err', f'{port} nicht vorhanden', 'Adapter einstecken und neu suchen')
        if p.kind != 'usb_serial':
            return CheckResult('err', f'{port} ist kein USB-Seriell-Adapter')
        if p.busy:
            return CheckResult('err', f'{port} ist belegt', 'Programm schließen, das den Port hält')
        baud = self._c.uart_baud or 0
        return CheckResult('ok', f'{port} bereit' + (f' ({baud} Baud geöffnet und wieder freigegeben)' if baud else ''))

    def check_pairing_code(self, code):
        self._rec('check_pairing_code')                  # Code nie aufzeichnen
        code = (code or '').strip()
        if not code:
            return CheckResult('err', 'Code eingeben')
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', code):      # wie secrets.token_urlsafe(32) auf dem Pi
            return CheckResult('err', 'Der Code hat nicht das erwartete Format',
                               'Den Code vollständig vom Pi kopieren')
        return CheckResult('ok', 'Format stimmt')

    def export_session_file(self, destination, port=None):
        port = port or self._c.gsv_port or 'COM5'
        self._rec('export_session_file', Path(destination), port)
        data = _SESSION_PLACEHOLDER.format(n=re.sub(r'\D', '', port) or '0').encode('cp1252')
        Path(destination).write_bytes(data)         # nur im Fake: Platzhalter, keine echte Session
        return SessionExport(Path(destination), port, 'demo-placeholder', hashlib.sha256(data).hexdigest())

    def diagnostics_contents(self):
        self._rec('diagnostics_contents')
        return _CONTENTS

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
