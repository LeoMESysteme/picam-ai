"""Der echte AppController: erfüllt ``ui.port.ControllerPort`` mit dem Backend-Kern.

Keine eigene Transport-, Zahlenformat- oder Bereitschaftslogik: Profil (strikter
Parser), ConnectionManager, BridgeWorker, DeliveryJournal und CredentialStore
kommen aus dem Kern. Der Controller hält nur App-Zustand (Client-ID, Profil,
Weg, Endpunkt, Portpaar, Einrichtungsschritt) und übersetzt ihn für die UI.

Grundsätze: Kopplungscode nur im Speicher (nie gespeichert, nie protokolliert);
kein stiller Wechsel von Weg/Pi; ein Portpaar wird nie erzeugt oder geändert,
nur ein vorhandenes ausdrücklich übernommen; unbekannt = gesperrt.
"""
from __future__ import annotations

import json
import math
import os
import queue
import threading
import time
import uuid
import zipfile
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from dispread.bridge.baud import UART_BAUD
from dispread.bridge.protocol import parse_profile
from dispread.bridge.types import BridgeEvent, BridgeProfile

from .connection import ConnectionManager
from .credentials import CredentialStore
from .delivery_journal import DeliveryJournal, DiagnosticStore
from .input_checks import InputChecks
from .port_inventory import PortInventory, serial_ports
from .readiness import Readiness
from .session_export import GSVMULTI_BAUD, TEMPLATE_CHANNELS, TEMPLATE_ID, generate_session
from .session_templates import SessionTemplateError, active_session_template
from .types import InstallResult, PortPair, valid_port_name
from .ui.port import MODES, CheckResult, JournalEntry, ModeInfo, SessionExport, SetupState, UiContext
from .vcom import VcomAdapter, VcomUnverifiedError
from .worker import BridgeWorker, WorkerStatus

STATE_VERSION = 1
JOURNAL_MAX = 500
DIAG_QUEUE_MAX = 1000
DIAG_FLUSH_S = 0.5
CODE_LIFETIME_S = 300
DEV_BUILD = 'Entwicklungsstand'
_FIRST = Readiness('ready', 'unknown', 'disconnected', 'unavailable', 'unknown', 'unconfirmed', 'connect')


class AppError(Exception):
    """Fehler mit festem Code; die Oberfläche erklärt den Code, nie den Text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def default_data_dir() -> Path:
    base = os.environ.get('LOCALAPPDATA') or str(Path.home() / '.local' / 'share')
    return Path(base) / 'dispread-bridge'


def format_fingerprint(hexstr: str) -> str:
    """64 Hexzeichen -> 16 Vierergruppen (die UI setzt 4 je Zeile)."""
    h = hexstr.lower()
    return ' '.join(h[i:i + 4] for i in range(0, len(h), 4))


def _open_com(port: str):
    from serial import Serial
    return Serial(port, GSVMULTI_BAUD, bytesize=8, parity='N', stopbits=1, timeout=1, write_timeout=2)


def _build_label(info=None) -> tuple[str, str | None]:
    """(Fußzeile, Kanal) aus build_info (version, commit, channel); ohne Modul „Entwicklungsstand“."""
    if info is None:
        try:
            from . import build_info as info
        except ImportError:
            return DEV_BUILD, None
    if info is False:
        return DEV_BUILD, None
    version = getattr(info, 'version', None)
    if not version:
        return DEV_BUILD, None
    commit = str(getattr(info, 'commit', '') or '')[:12]
    if commit.lower() in ('', 'unbekannt', 'unknown'):
        commit = 'Quelle unbekannt'
    channel = getattr(info, 'channel', None)
    return (f'{version} · {commit}' if commit else str(version)), (str(channel) if channel else None)


def _reports(fn):
    """AppError und Backendfehler merken (UI zeigt den Code), dann weiterreichen."""
    def wrapper(self, *a, **kw):
        try:
            result = fn(self, *a, **kw)
        except AppError as e:
            self._notice = e.code
            raise
        except Exception as e:
            self._notice = getattr(e, 'code', None) or 'unknown_error'
            raise
        self._notice = None
        return result
    wrapper.__name__ = fn.__name__
    return wrapper


class AppController:
    def __init__(self, data_dir: Path | str | None = None, *, protector=None, devices=None, vcom=None,
                 transport_factory=None, com_factory: Callable | None = None,
                 resolver=None, socket_factory=None, tls_factory=None, port_opener=None,
                 list_ports: Callable | None = None, discover: Callable | None = None,
                 manager_factory: Callable | None = None, worker_factory: Callable | None = None,
                 network_diagnostics=None, version: str | None = None, build_info=None,
                 demo_count: int = 600, demo_rate_hz: float = 10.0, clock: Callable[[], float] | None = None):
        self._clock = clock or time.monotonic
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._devices = devices
        self._vcom = vcom if vcom is not None else VcomAdapter()
        self._transport_factory = transport_factory
        self._com_factory = com_factory or _open_com
        self._ports = PortInventory(list_ports or serial_ports, self._clock)
        self._checks = InputChecks(self.list_ports, self._vcom.inventory, resolver=resolver,
                                   socket_factory=socket_factory, tls_factory=tls_factory, port_opener=port_opener)
        self._presence_stop = threading.Event()
        self._discover = discover
        self._manager_factory = manager_factory or ConnectionManager
        self._worker_factory = worker_factory or BridgeWorker
        self._network_diagnostics = network_diagnostics
        label, self._channel = _build_label(build_info)
        self._version = version or label
        self._demo_count, self._demo_rate = demo_count, demo_rate_hz
        self._credentials = CredentialStore(self.data_dir / 'credentials', protector=protector)
        self._diag = DiagnosticStore(self.data_dir / 'diagnostics')
        self._journal: DeliveryJournal | None = None
        self._lock = threading.RLock()
        self._subs: list[Callable] = []
        self._entries: deque = deque(maxlen=JOURNAL_MAX)
        self._counter_entry = None           # die laufende Zaehlerzeile, solange sie oben steht
        self._last_exchange = None
        # Diagnose: Schreiben nie im Workerthread (Datei-I/O, fsync).
        self._diag_queue: queue.Queue = queue.Queue(maxsize=DIAG_QUEUE_MAX)
        self._diag_written_pending = 0
        self._diag_dropped = 0
        self._diag_stop = threading.Event()
        self._diag_thread = threading.Thread(target=self._diag_loop, name='bridge-diag-writer', daemon=True)
        self._diag_thread.start()
        self._manager = self._worker = None
        self._starter_cancel = threading.Event()
        # nur im Speicher
        self._offer: str | None = None
        self._notice: str | None = None
        self._candidates: tuple = ()
        self._adapters: tuple = ()
        self._vcom_unverified = False
        self._manual_open = False
        self._connect_attempted = False
        self._offer_at: float | None = None      # Eingabezeitpunkt des Kopplungscodes (lokal gezählt)
        self._code_expired = False
        self._editing_pair = False
        self._resumed = False
        self._bo_n, self._bo_t = 0, 0.0           # Backoff: Anzahl Fehlversuche, Zeit des letzten
        self._demo_started = False
        self._written = 0
        self._com_issue: str | None = None
        self._last_ack = 'keine'
        self._tr_active, self._tr_written, self._tr_omitted = False, 0, 0
        self._last_contact = ''
        self._exited = False
        self._activity_seq = 0
        self._setup_revision = 0
        self._paired_cached = False
        # persistiert
        self._profile: BridgeProfile | None = None
        self._route: str | None = None
        self._route_mode: str | None = None
        self._configured_modes: set[str] = set()
        self._adapter_port: str | None = None
        self._session_path: str | None = None
        self._session_port: str | None = None
        self._sessions: dict[str, dict[str, str]] = {}
        self._endpoint: str | None = None
        self._adapter_id: str | None = None
        self._pair: PortPair | None = None
        self._session_confirmed = False
        self._setup_done = False
        self._overview = False
        self._auto_connect: bool | None = None   # None = Standard (an)
        self._step = 1
        self.client_id = ''
        self._load_state()
        self._refresh_pairing()
        threading.Thread(target=self._presence_loop, name='bridge-adapter-presence', daemon=True).start()

    # ------------------------------------------------------------ UX2
    def _require_mode_unlocked(self):
        if self._worker is not None and self._worker.is_active():
            raise AppError('mode_locked')

    def _restore_session(self):
        mode = self._route_mode or 'network'
        port = self._adapter_port if mode == 'uart_direct' else self._pair.gsv_port if self._pair else None
        self._session_path = self._sessions.get(mode, {}).get(port)
        self._session_port = port if self._session_path else None

    def _refresh_mode_state(self):
        self._setup_revision += 1
        self._setup_done = self._route_mode in self._configured_modes
        self._overview = False
        self._restore_session()

    def modes(self) -> tuple[ModeInfo, ...]:
        locked = self._worker is not None and self._worker.is_active()
        with self._lock:
            present = self._ports.present(self._adapter_port)
            result = []
            for mode in MODES:
                configured = mode in self._configured_modes
                status = 'Eingerichtet' if configured else 'Nicht eingerichtet'
                tone = 'info'
                if mode == 'uart_direct' and self._adapter_port:
                    status = ('Adapter erkannt' if present else 'Adapter fehlt' if present is False
                              else 'Adapterpräsenz unbekannt')
                    tone = 'ok' if present else 'warn'
                result.append(ModeInfo(mode, configured, mode == self._route_mode, status, tone,
                                       not locked, 'Übertragung aktiv' if locked else ''))
            return tuple(result)

    @_reports
    def select_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise AppError('transport_unsupported')
        self._require_mode_unlocked()
        self._stop_all()
        with self._lock:
            self._manager = self._worker = None
            self._route_mode = mode
            self._route = {'uart_bridge': 'uart', 'network': 'network'}.get(mode)
            self._refresh_mode_state()
            self._step = 4 if mode == 'uart_direct' and self._setup_done else 1
            self._connect_attempted = False
            self._save_state()
        if mode == 'uart_direct':
            self.list_adapters()

    def leave_setup(self) -> None:
        with self._lock:
            self._overview = True
            self._save_state()

    def list_ports(self):
        return self._ports.refresh()

    def list_adapters(self):
        return tuple(p for p in self.list_ports() if p.kind == 'usb_serial')

    def _presence_loop(self):
        while not self._presence_stop.wait(2):
            if self._adapter_port is not None:
                self._ports.refresh()

    def check_endpoint(self, text: str) -> CheckResult:
        with self._lock:
            profile = self._profile
        return self._checks.endpoint(text, profile)

    def check_port_pair(self, bridge_port: str, gsv_port: str) -> CheckResult:
        if self._worker is not None and self._worker.is_active():
            pair = self._pair
            if pair and (bridge_port, gsv_port) == (pair.bridge_port, pair.gsv_port):
                return CheckResult('ok', 'Gespeichertes Portpaar wird von der Brücke verwendet.')
            return CheckResult('err', 'Übertragung aktiv.', 'Übertragung vor der Portprüfung beenden.')
        return self._checks.port_pair(bridge_port, gsv_port)

    def check_adapter(self, port: str) -> CheckResult:
        if self._worker is not None and self._worker.is_active():
            return CheckResult('err', 'Übertragung aktiv.', 'Übertragung vor der Adapterprüfung beenden.')
        with self._lock:
            baud = GSVMULTI_BAUD if self._route_mode == 'uart_direct' else (
                self._profile.uart_baud if self._profile else UART_BAUD)
        return self._checks.adapter(port, baud)

    def check_pairing_code(self, code: str) -> CheckResult:
        return self._checks.pairing_code(code)

    def _direct_step(self, direction):
        # Probes run outside the metadata lock; stale continuations cannot mutate a new setup.
        with self._lock:
            revision, step, port = self._setup_revision, self._step, self._adapter_port
        if direction == 'next' and step == 1:
            if port is None or self.check_adapter(port).state != 'ok':
                raise AppError('adapter_required')
        with self._lock:
            if (self._route_mode != 'uart_direct' or self._setup_revision != revision
                    or self._step != step or self._adapter_port != port):
                raise AppError('setup_changed')
            self._setup_revision += 1
            if direction == 'next':
                if self._step == 3 and (not self._session_path or self._session_port != self._adapter_port):
                    raise AppError('session_required')
                if self._step >= 4:
                    self._finish_direct()
                else:
                    self._step += 1
            elif direction == 'finish':
                if self._step != 4:
                    raise AppError('session_required')
                self._finish_direct()
            elif direction == 'back':
                self._step = max(1, self._step - 1)
            elif direction == 'overview':
                self._overview = True
            elif direction in ('restart', 'change_setup', 'resume'):
                self._overview, self._setup_done, self._step = False, False, 1
            self._save_state()

    def _finish_direct(self):
        if not self._adapter_port or not self._session_path or self._session_port != self._adapter_port:
            raise AppError('session_required')
        self._setup_done, self._step = True, 4
        self._configured_modes.add('uart_direct')

    @staticmethod
    def diagnostics_contents():
        return (('summary.json', 'Version, Bereitschaft, Worker-Zustand, Weg, Portpaar und Übergabezähler.'),
                ('details.jsonl', 'Ereignisprotokoll der App; Zugangsdaten redigiert, keine Messwerte.'))

    # ------------------------------------------------------------ Zustand
    @property
    def _state_path(self) -> Path:
        return self.data_dir / 'state.json'

    def _load_state(self) -> None:
        data: dict = {}
        try:
            data = json.loads(self._state_path.read_text('utf-8'))
            if data.get('version') != STATE_VERSION:
                data = {}
        except (OSError, ValueError):
            data = {}
        cid = data.get('client_id')
        if not isinstance(cid, str) or not cid:
            cid = 'win-' + uuid.uuid4().hex
        self.client_id = cid
        try:
            if data.get('profile'):
                self._profile = parse_profile(json.dumps(data['profile']).encode())
            pair = data.get('port_pair')
            if pair:
                self._pair = PortPair('manual', pair['bridge_port'], pair['gsv_port'], False)
        except (ValueError, KeyError, TypeError):
            self._profile = self._pair = None
        self._route = data.get('route') if data.get('route') in ('network', 'uart') else None
        self._route_mode = data.get('route_mode')
        if self._route_mode not in MODES:
            self._route_mode = {'uart': 'uart_bridge', 'network': 'network'}.get(self._route)
        self._adapter_port = data.get('adapter_port') if valid_port_name(data.get('adapter_port')) else None
        self._session_path = data.get('session_path') if isinstance(data.get('session_path'), str) else None
        self._session_port = data.get('session_port') if valid_port_name(data.get('session_port')) else None
        sessions = data.get('sessions')
        if isinstance(sessions, dict):
            self._sessions = {mode: {port: path for port, path in entries.items()
                                    if valid_port_name(port) and isinstance(path, str)}
                              for mode, entries in sessions.items() if mode in MODES and isinstance(entries, dict)}
        elif self._session_path and self._session_port:
            self._sessions[self._route_mode or 'network'] = {self._session_port: self._session_path}
        self._restore_session()
        configured = data.get('configured_modes', [])
        self._configured_modes = set(m for m in configured if m in MODES) if isinstance(configured, list) else set()
        self._endpoint = data.get('endpoint') if isinstance(data.get('endpoint'), str) else None
        self._adapter_id = data.get('adapter_id') if isinstance(data.get('adapter_id'), str) else None
        self._session_confirmed = data.get('session_confirmed') is True
        legacy_done = data.get('setup_done') is True and self._profile is not None and self._pair is not None
        if legacy_done and self._route_mode is None:
            self._route = self._route_mode = 'network'
        if legacy_done and self._route_mode in ('network', 'uart_bridge'):
            self._configured_modes.add(self._route_mode)
        if self._profile is None or self._pair is None:
            self._configured_modes.difference_update(('network', 'uart_bridge'))
        if not (self._adapter_port and self._sessions.get('uart_direct', {}).get(self._adapter_port)):
            self._configured_modes.discard('uart_direct')
        self._setup_done = self._route_mode in self._configured_modes
        self._auto_connect = data.get('auto_connect') if isinstance(data.get('auto_connect'), bool) else None
        self._step = 1 if self._pair is None else (2 if self._profile is None else 3)
        if self._route_mode == 'uart_direct':
            self._step = 4 if self._setup_done else 1
        self._resumed = self._step == 3 and not self._setup_done
        self._save_state()

    def _save_state(self) -> None:
        profile = None
        if self._profile is not None:
            profile = asdict(replace(self._profile, pairing_offer=None))   # Angebot nie speichern
            profile['endpoints'] = list(profile['endpoints'])
        data = dict(version=STATE_VERSION, client_id=self.client_id, profile=profile, route=self._route,
                    endpoint=self._endpoint, adapter_id=self._adapter_id, route_mode=self._route_mode,
                    configured_modes=sorted(self._configured_modes), adapter_port=self._adapter_port,
                    session_path=self._session_path, session_port=self._session_port, sessions=self._sessions,
                    port_pair=None if self._pair is None else dict(bridge_port=self._pair.bridge_port,
                                                                    gsv_port=self._pair.gsv_port),
                    session_confirmed=self._session_confirmed, setup_done=self._setup_done,
                    auto_connect=self._auto_connect)
        tmp = self._state_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data), 'utf-8')
        os.replace(tmp, self._state_path)

    # ------------------------------------------------------------ Ereignisse
    def subscribe(self, callback):
        with self._lock:
            self._subs.append(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._subs:
                    self._subs.remove(callback)
        return unsubscribe

    def _emit(self, event: BridgeEvent) -> None:
        """Nie werfen, nie blockieren: ein Fehler hier darf den Worker nicht in audit_failed treiben."""
        if event.kind == 'connection' and event.code == 'authenticated':
            self._refresh_pairing()
        try:
            if event.kind != 'activity':
                self._diag_enqueue(event)
        except Exception:
            pass
        try:
            if event.kind == 'activity':
                with self._lock:
                    self._activity_seq += 1
                    self._last_contact = datetime.now().strftime('%H:%M:%S')
            else:
                self._note(event)
        except Exception:
            pass
        with self._lock:
            subs = list(self._subs)
        for cb in subs:
            try:
                cb(event)
            except Exception:
                pass

    # ------------------------------------------------------------ Diagnose-Schreiber
    def _diag_enqueue(self, event: BridgeEvent) -> None:
        with self._lock:
            if event.kind == 'exchange' and (event.detail or {}).get('outcome') == 'written':
                self._diag_written_pending += 1          # gebuendelt: Zaehler statt Zeile je Wert
                return
        self._diag_put(event)

    def _diag_put(self, event: BridgeEvent) -> None:
        try:
            self._diag_queue.put_nowait(event)
        except queue.Full:
            with self._lock:
                self._diag_dropped += 1                  # zaehlen statt blockieren

    def _diag_collect(self) -> list[BridgeEvent]:
        extra: list[BridgeEvent] = []
        with self._lock:
            n, self._diag_written_pending = self._diag_written_pending, 0
            dropped, self._diag_dropped = self._diag_dropped, 0
        if n:
            extra.append(BridgeEvent('exchange', 'written_summary', None, None,
                                     dict(outcome='written', count=n)))
        if dropped:
            extra.append(BridgeEvent('diagnostics', 'dropped', None, None, dict(count=dropped)))
        return extra

    def _diag_write(self, events) -> None:
        for ev in events:
            try:
                self._diag.append(ev)
            except Exception:
                pass

    def _diag_loop(self) -> None:
        while True:
            try:
                batch = [self._diag_queue.get(timeout=DIAG_FLUSH_S)]
            except queue.Empty:
                batch = []
            while True:
                try:
                    batch.append(self._diag_queue.get_nowait())
                except queue.Empty:
                    break
            self._diag_write(batch + self._diag_collect())
            for _ in batch:
                self._diag_queue.task_done()
            if self._diag_stop.is_set() and self._diag_queue.empty():
                return

    def _diag_flush(self, timeout: float = 5.0) -> None:
        """Ausstehende Diagnose schreiben (Export, Beenden); begrenzt wartend."""
        deadline = threading.Event()
        t = threading.Thread(target=lambda: (self._diag_queue.join(), deadline.set()), daemon=True)
        t.start()
        deadline.wait(timeout)
        self._diag_write(self._diag_collect())

    def _note(self, event: BridgeEvent) -> None:
        from .ui import texts
        run_now = self._run_id_now() if (event.detail or {}).get('release') else None   # ausserhalb der Sperre
        with self._lock:
            now = datetime.now().strftime('%H:%M:%S')
            if event.kind in ('connection', 'exchange'):
                self._last_contact = now             # Lebenszeichen des Pi (jede Meldung zählt)
            if event.kind == 'connection' and not str(event.code or '').startswith('tailscale_'):
                m = self._manager
                peer = m.snapshot().peer if m is not None else None
                if peer == 'backoff':
                    self._bo_n += 1
                    self._bo_t = self._clock()
                elif peer != 'connecting':
                    self._bo_n = 0
            outcome = (event.detail or {}).get('outcome') if event.kind == 'exchange' else None
            test_release = (event.detail or {}).get('release') == 'test_unaccepted'
            if event.kind == 'exchange':
                if test_release and not self._tr_active:
                    self._tr_active, self._tr_written, self._tr_omitted = True, 0, 0
                    self._counter_entry = None
                    self._entries.appendleft(JournalEntry(now, f'Testfreigabe aktiv (Lauf {run_now or "?"})',
                                                          'echte Werte, nicht abgenommen', tone='warn'))
                elif not test_release and self._tr_active:
                    self._tr_active = False
                    self._counter_entry = None
                    self._entries.appendleft(JournalEntry(now, 'Ausgabe wieder gesperrt', tone='info'))
                if test_release and outcome == 'written':
                    self._tr_written += 1
                elif test_release and outcome == 'omitted':
                    self._tr_omitted += 1
                if outcome == 'written':
                    self._written += 1
                    self._com_issue = None
                    self._last_ack = 'COM-Weitergabe bestätigt – kein GSVmulti-Empfangsnachweis'
                elif outcome == 'failed':
                    self._com_issue = 'write_failed'
                elif outcome in ('unknown', 'unconfirmed', 'stopped'):
                    self._com_issue = 'unclear'
                if outcome == self._last_exchange and outcome in ('idle', 'ended'):
                    return                              # Leerlauf nie als Einzelzeilen
                self._last_exchange = outcome
            if outcome == 'written':
                # Eine laufende Zaehlerzeile, die aktualisiert statt neu angehaengt wird.
                n = self._tr_written if test_release else self._written
                entry = (JournalEntry(now, f'Testfreigabe: {n} {"Wert" if n == 1 else "Werte"} weitergegeben',
                                      'COM-Weitergabe · nicht abgenommen · kein GSVmulti-Empfangsnachweis', tone='warn')
                         if test_release else
                         JournalEntry(now, f'Demo: {n} {"Wert" if n == 1 else "Werte"} weitergegeben',
                                      'COM-Weitergabe · kein GSVmulti-Empfangsnachweis', tone='info'))
                if self._counter_entry is not None and self._entries and self._entries[0] is self._counter_entry:
                    self._entries[0] = entry
                else:
                    self._entries.appendleft(entry)
                self._counter_entry = entry
                return
            self._counter_entry = None
            self._entries.appendleft(texts.event_entry(event, now=now))

    # ------------------------------------------------------------ Profil
    @_reports
    def load_profile(self, raw: bytes) -> Readiness:
        try:
            profile = parse_profile(raw)
        except Exception:
            raise AppError('profile_invalid') from None
        if self._worker is not None and self._worker.is_active():
            raise AppError('transmission_active')
        with self._lock:
            self._setup_revision += 1
            self._offer = profile.pairing_offer          # nur im Speicher
            self._profile = replace(profile, pairing_offer=None)
            self._candidates = ()
            if self._endpoint not in profile.endpoints:
                self._endpoint = profile.endpoints[0] if profile.endpoints else None
            self._connect_attempted = False
            self._code_expired, self._offer_at, self._resumed = False, None, False
            self._setup_done = False
            self._configured_modes.difference_update(('network', 'uart_bridge'))
            if self._step < 2 and self._pair is not None:
                self._step = 2
            self._save_state()
        self._refresh_pairing()
        return self.snapshot()

    @_reports
    def pair(self, code: str, fingerprint_confirmed: bool) -> None:
        """Code gilt nur für den nächsten Verbindungsaufbau; gekoppelt wird dort."""
        if self._profile is None:
            raise AppError('profile_required')
        if not fingerprint_confirmed:
            raise AppError('fingerprint_unconfirmed')
        try:
            parse_profile(json.dumps(dict(asdict(replace(self._profile, pairing_offer=code)),
                                          endpoints=list(self._profile.endpoints))).encode())
        except Exception:
            raise AppError('code_invalid') from None
        with self._lock:
            self._offer = code
            self._offer_at = self._clock()
            self._code_expired = self._resumed = False
            self._step = 3

    def _is_paired(self) -> bool:
        return self._paired_cached

    def _refresh_pairing(self) -> None:
        # Called by background operations, never from context()/snapshot().
        with self._lock:
            profile = self._profile
        paired = False
        if profile is not None:
            try:
                paired = any(self._credentials.load(profile.pi_id, mode,
                                 expected_pin=profile.certificate_sha256) for mode in ('network', 'uart'))
            except Exception:
                pass
        with self._lock:
            if self._profile is profile:
                self._paired_cached = bool(paired)

    # ------------------------------------------------------------ Komponenten / Portpaar
    @_reports
    def install_components(self) -> InstallResult:
        """Nur Inventur. Ein Portpaar wird nie erzeugt; ohne verifizierten Treiberanbieter
        bleibt nur die ausdrückliche manuelle Angabe."""
        try:
            self.list_ports()
            pairs = self._vcom.inventory()
        except VcomUnverifiedError:
            with self._lock:
                self._vcom_unverified = self._manual_open = True
            return InstallResult('unverified', False, None, 'vcom_unverified')
        owned = [p for p in pairs if p.owned]
        if len(owned) == 1:
            with self._lock:
                self._pair = owned[0]
                self._save_state()
            return InstallResult('ready', False, owned[0], None)
        with self._lock:
            self._manual_open = True
        return InstallResult('missing', False, None, 'pair_not_found')

    def open_manual_pair(self) -> None:
        self.list_ports()
        with self._lock:
            self._manual_open = True
            self._editing_pair = self._pair is not None      # „Portpaar ändern“

    @_reports
    def set_port_pair(self, bridge_port: str, gsv_port: str) -> None:
        """Vorhandenes Paar angeben: manuell, nicht von der App geprüft."""
        try:
            pair = PortPair('manual', bridge_port, gsv_port, False)
        except ValueError:
            raise AppError('portpair_invalid') from None
        if self._worker is not None and self._worker.is_active():
            raise AppError('transmission_active')
        if not {bridge_port, gsv_port} <= {p.port for p in self.list_ports()}:
            raise AppError('portpair_invalid')
        with self._lock:
            self._setup_revision += 1
            self._pair = pair
            self._configured_modes.difference_update(('network', 'uart_bridge'))
            if self._route_mode != 'uart_direct':
                self._setup_done = False
            self._restore_session()
            self._session_confirmed = False
            self._editing_pair = False
            self._save_state()

    # ------------------------------------------------------------ Weg
    def select_route(self, mode: str) -> None:
        if mode not in ('network', 'uart'):
            raise AppError('transport_unsupported')
        if self._worker is not None and self._worker.is_active():
            raise AppError('transmission_active')
        with self._lock:
            self._route = mode
            self._route_mode = 'uart_bridge' if mode == 'uart' else 'network'
            self._refresh_mode_state()
            self._connect_attempted = False
            self._save_state()

    @_reports
    def select_endpoint(self, endpoint: str, manual: bool = False) -> None:
        from .transports import TransportError, resolve_endpoints
        self._require_mode_unlocked()
        endpoint = endpoint.strip()
        if manual and '://' not in endpoint:
            endpoint = 'https://' + endpoint
        try:
            resolve_endpoints(endpoint)
        except (TransportError, ValueError):
            raise AppError('endpoint_unsupported') from None
        with self._lock:
            previous = self._route_mode
            if endpoint != self._endpoint:
                self._configured_modes.discard('network')
            self._endpoint, self._route, self._route_mode = endpoint, 'network', 'network'
            self._refresh_mode_state()
            if previous == 'uart_direct':
                self._step = 1
            self._connect_attempted = False
            self._save_state()

    @_reports
    def select_adapter(self, device_id: str) -> None:
        self._require_mode_unlocked()
        choices = self.list_adapters()
        selected = next((p for p in choices if device_id in (p.device_id, p.port)), None)
        # The legacy wizard supplies PnP instance IDs from rescan().
        legacy = next((d for d in self._adapters if d.instance_id == device_id), None)
        port = selected.port if selected else (legacy.port if legacy else None)
        if self._route_mode == 'uart_direct' and port is None:
            raise AppError('adapter_required')
        if self._route_mode != 'uart_direct' and selected and self._devices is not None:
            adapters = tuple(self._devices.inventory())
            matches = [d for d in adapters if d.port == port and d.is_supported]
            if len(matches) != 1:
                raise AppError('adapter_required')
            device_id = matches[0].instance_id
        with self._lock:
            changed = self._adapter_port != port or self._adapter_id != device_id
            previous = self._route_mode
            if changed:
                self._configured_modes.difference_update(('uart_direct', 'uart_bridge'))
                if previous == 'uart_direct':
                    self._step = 1
            self._adapter_id, self._adapter_port = device_id, port
            if self._route_mode != 'uart_direct':
                self._route, self._route_mode = 'uart', 'uart_bridge'
            self._refresh_mode_state()
            self._connect_attempted = False
            self._save_state()

    def rescan(self) -> None:
        """Adapter, COM-Ports und Netzkandidaten neu lesen (blockiert)."""
        self.list_ports()
        if self._devices is not None:
            try:
                invalidate = getattr(self._devices, 'invalidate_pnp', None)
                if invalidate is not None:
                    invalidate()
                self._adapters = tuple(i for i in self._devices.inventory() if i.is_supported)
            except Exception:
                self._adapters = ()
        if self._profile is not None:
            try:
                if self._discover is not None:
                    found = self._discover(self._profile.endpoints)
                else:
                    from dispread.bridge.discovery import discover_with_fallback
                    found = discover_with_fallback(self._profile.endpoints, timeout_s=2)
                self._candidates = tuple(found)
            except Exception:
                self._candidates = ()

    # ------------------------------------------------------------ Verbindung
    def _profile_for_connect(self, mode: str) -> BridgeProfile:
        p = self._profile
        endpoints = p.endpoints
        if mode == 'network' and self._endpoint:
            endpoints = (self._endpoint, *[e for e in p.endpoints if e != self._endpoint])
        return replace(p, endpoints=endpoints, pairing_offer=self._offer)

    def _journal_open(self) -> DeliveryJournal:
        if self._journal is None:
            self._journal = DeliveryJournal(self.data_dir / 'delivery.sqlite')
        return self._journal

    def _com_open(self):
        return self._com_factory(self._pair.bridge_port)

    @_reports
    def connect(self, mode: str, selected_device_id: str | None = None) -> None:
        if mode not in ('network', 'uart'):
            raise AppError('transport_unsupported')
        if self._profile is None:
            raise AppError('profile_required')
        if self._pair is None:
            raise AppError('portpair_required')
        if self._worker is not None and self._worker.is_active():
            raise AppError('transmission_active')        # kein stiller Wechsel
        if mode == 'uart':
            selected_device_id = selected_device_id or self._adapter_id
        self._stop_all()
        with self._lock:
            self._route = mode
            self._route_mode = 'uart_bridge' if mode == 'uart' else 'network'
            if selected_device_id:
                self._adapter_id = selected_device_id
            self._save_state()
            self._connect_attempted, self._resumed = True, False
            self._bo_n = 0
            self._demo_started, self._written, self._com_issue = False, 0, None
            self._exited = False
            kwargs = {}
            if self._transport_factory is not None:
                kwargs['transport_factory'] = self._transport_factory
            if self._network_diagnostics is not None:
                kwargs['network_diagnostics'] = self._network_diagnostics
            manager = self._manager_factory(self._profile_for_connect(mode), self.client_id, self._credentials,
                                            self._devices, emit=self._emit, **kwargs)
            worker = self._worker_factory(manager, self._com_open, self._journal_open(), self._emit)
            manager.set_worker(worker)
            self._manager, self._worker = manager, worker
            self._starter_cancel = cancel = threading.Event()
        manager.connect(mode, selected_device_id)
        threading.Thread(target=self._start_worker_when_ready, args=(manager, worker, cancel),
                         name='bridge-worker-starter', daemon=True).start()

    def _start_worker_when_ready(self, manager, worker, cancel: threading.Event) -> None:
        """Worker erst nach authentifizierter Verbindung starten; Verbinden startet keine Demo."""
        while not cancel.wait(0.05):
            r = manager.snapshot()
            if r.peer == 'authenticated':
                if not cancel.is_set():
                    try:
                        worker.start()
                    except RuntimeError:
                        pass
                return
            if r.peer == 'disconnected' and r.next_action not in (None, 'connect'):
                return                                    # terminal; keine Selbstwiederholung

    def _stop_all(self) -> None:
        self._starter_cancel.set()
        worker, manager = self._worker, self._manager
        if worker is not None:
            worker.stop()
        elif manager is not None:
            manager.disconnect()

    @_reports
    def disconnect(self) -> None:
        self._stop_all()

    @_reports
    def begin_demo_check(self, confirmed_test_session: bool) -> None:
        if not confirmed_test_session:
            raise AppError('demo_not_confirmed')
        manager = self._manager
        if manager is None or manager.snapshot().peer != 'authenticated':
            raise AppError('not_connected')
        if self._run_active(manager.snapshot()):
            raise AppError('run_active')
        with self._lock:
            self._demo_started, self._written, self._com_issue = True, 0, None
        try:
            manager.start_demo(self._demo_count, self._demo_rate)
        except Exception as e:
            with self._lock:
                self._demo_started = False
            if getattr(e, 'code', None) in ('run_conflict', 'peer_refused', 'demo_unconfirmed'):
                raise AppError('demo_rejected') from None
            raise

    # ------------------------------------------------------------ Session
    @_reports
    def export_session(self, settings, destination: Path):
        """Compatibility entry: only the reviewed generator's port setting is allowed."""
        if not isinstance(settings, dict) or set(settings) != {'gsv_port'}:
            raise AppError('automatic_export_blocked')
        return self.export_session_file(destination, settings['gsv_port'])

    @_reports
    def export_session_file(self, destination: Path, port: str | None = None) -> SessionExport:
        from hashlib import sha256
        with self._lock:
            export_mode = self._route_mode or 'network'
            chosen = port if port is not None else (self._adapter_port if self._route_mode == 'uart_direct'
                                                    else self._pair.gsv_port if self._pair else None)
        try:
            raw = generate_session(chosen)
            template = active_session_template()
        except SessionTemplateError:
            raise AppError('session_template_invalid') from None
        except ValueError:
            raise AppError('session_port_invalid') from None
        destination = Path(destination)
        try:
            destination.write_bytes(raw)
        except OSError:
            raise AppError('session_write_failed') from None
        with self._lock:
            self._sessions.setdefault(export_mode, {})[chosen] = str(destination)
            self._restore_session()
            self._save_state()
        return SessionExport(destination, chosen, template.spec.template_id, sha256(raw).hexdigest(),
                             channels=template.channels, hidden_channels=template.hidden_channels,
                             record_hidden_required=template.record_hidden_required)

    def confirm_session(self, on: bool) -> None:
        with self._lock:
            self._session_confirmed = bool(on)
            self._save_state()

    # ------------------------------------------------------------ Einrichtungsschritte
    @_reports
    def setup_step(self, direction: str) -> None:
        if self._route_mode == 'uart_direct':
            self._direct_step(direction)
            return
        if direction == 'next' and self._step == 3 and not (
                self._manager is not None and self._manager.snapshot().peer == 'authenticated'):
            if self._worker is not None and self._worker.is_active():
                raise AppError('not_connected')        # Verbindung wird gerade wiederhergestellt; kein connect
            if self._manager is not None and self._manager.snapshot().peer == 'connecting':
                return                                  # Aufbau läuft: kein Mehrfachstart
            self.connect(self._route or 'network', None)      # „Verbinden“; keine Demo, keine Messung
            return
        with self._lock:
            if direction == 'back':
                self._step = max(1, self._step - 1)
            elif direction == 'overview':
                self._overview = True
            elif direction == 'resume':
                self._overview, self._setup_done = False, False
            elif direction == 'change_setup':
                self._overview, self._setup_done, self._step = False, False, 1
                self._editing_pair = False
            elif direction == 'pairing':
                self._setup_done, self._overview, self._step = False, False, 2
                self._code_expired = False
                self._save_state()
            elif direction == 'restart':
                self._setup_done, self._overview, self._step = False, False, 1
                self._save_state()
            elif direction == 'next':
                self._advance()
            elif direction == 'finish':
                self._finish()

    def _advance(self) -> None:
        step = self._step
        if step == 1:
            if self._pair is None:
                raise AppError('portpair_required')
            self._step = 2
        elif step == 2:
            if self._profile is None:
                raise AppError('profile_required')
            if self._offer is None and not self._is_paired():
                raise AppError('pair_required')
            self._step = 3
        elif step == 3:
            if self._manager is not None and self._manager.snapshot().peer == 'authenticated':
                self._step = 4
            else:
                raise AppError('connect_required')
        elif step == 4:
            if not self._session_confirmed:
                raise AppError('session_unconfirmed')
            self._step = 5
        elif step == 5:
            self._finish()

    def _finish(self) -> None:
        if self._route_mode is None and self._profile is not None:
            self._route = self._route_mode = 'network'
        self._setup_done, self._step = True, 5
        if self._route_mode:
            self._configured_modes.add(self._route_mode)
        self._resumed = False
        self._save_state()

    # ------------------------------------------------------------ Lesezugriffe
    def snapshot(self) -> Readiness:
        manager = self._manager
        base = manager.snapshot() if manager is not None else _FIRST
        if self._pair is None:
            components = 'missing'
        elif not self._pair.owned:
            components = 'manual_pair'
        else:
            components = 'ready'
        return replace(base, components=components)

    def worker_status(self) -> WorkerStatus | None:
        worker = self._worker
        return None if worker is None else worker.status

    def _variant(self, r: Readiness, w: WorkerStatus | None) -> tuple[str, dict]:
        step, d = self._step, {}
        if self._route_mode == 'uart_direct':
            d.update(adapter_port=self._adapter_port, adapter_present=self._ports.present(self._adapter_port),
                     adapter_items=tuple((p.label, '', p.port == self._adapter_port)
                                         for p in self._ports.cached() if p.kind == 'usb_serial'),
                     choices={'adapter': tuple(p.device_id or p.port for p in self._ports.cached()
                                               if p.kind == 'usb_serial')},
                     gsv_port=self._adapter_port, gsv_baud=GSVMULTI_BAUD,
                     session_path=self._session_path, session_template=TEMPLATE_ID)
            return f'D{min(step, 4)}', d
        if step == 1:
            if self._pair is not None and not self._editing_pair:
                return 'E1ok', d
            if self._manual_open or self._vcom_unverified:
                ports = tuple(self._safe_ports())
                d.update(ports=ports, choices={'bridge_port': ports, 'gsv_port': ports},
                         unverified=self._vcom_unverified)
                return 'E1manual', d
            return 'E1', d
        if step in (2, 3) and self._code_expiry_due(r):
            with self._lock:
                self._offer, self._offer_at, self._code_expired, self._step = None, None, True, 2
            step = 2
        if step == 2:
            if self._profile is None:
                return 'E2', d
            if self._is_paired():
                return 'E2ok', d
            if self._code_expired:
                return 'E2exp', d
            return 'E2b', d
        if step == 3:
            return self._variant_route(r, d)
        if step == 4:
            d['session_confirmed'] = self._session_confirmed
            return 'E4locked', d
        d['auto_connect'] = self._auto_effective()
        done = self._demo_started and (r.output == 'ended' or self._written >= self._demo_count)
        if self._demo_started and not done:
            d.update(progress_value=int(100 * self._written / max(1, self._demo_count)),
                     progress_text=f'{self._written} von {self._demo_count} Werten gesendet '
                                   f'({self._demo_rate:g} Hz, synthetisch)')
            return 'E5run', d
        if done:
            d['written'] = self._written
            return 'E5done', d
        if self._run_active(r):
            return 'E5busy', d
        return 'E5', d

    def _code_remaining(self) -> int | None:
        if self._offer is None or self._offer_at is None:
            return None
        return max(0, int(math.ceil(CODE_LIFETIME_S - (self._clock() - self._offer_at))))

    def _code_expiry_due(self, r: Readiness) -> bool:
        rem = self._code_remaining()
        return (rem == 0 and r.peer not in ('connecting', 'authenticated') and not self._is_paired())

    def _retry_in(self, r: Readiness) -> int | None:
        """Restzeit bis zum nächsten Versuch aus dem bekannten Backoff-Plan (1, 2, 4, 8, 8 … s)."""
        if r.peer != 'backoff' or self._bo_n < 1:
            return None
        wait = min(2 ** min(self._bo_n - 1, 3), 8)
        left = math.ceil(wait - (self._clock() - self._bo_t))
        return left if left > 0 else None

    def _auto_effective(self) -> bool:
        return True if self._auto_connect is None else self._auto_connect

    def set_auto_connect(self, on: bool) -> None:
        with self._lock:
            self._auto_connect = bool(on)
            self._save_state()

    def auto_connect_at_start(self) -> bool:
        """Gleicher Pi, gleicher Weg, gleicher Endpunkt; nie Demo, nie Wechsel."""
        if self._route_mode == 'uart_direct':
            return False
        if not (self._auto_effective() and self._setup_done and self._profile is not None
                and self._pair is not None and self._is_paired()):
            return False
        if self._worker is not None and self._worker.is_active():
            return False
        self.connect(self._route or 'network')
        return True

    @_reports
    def switch_pi(self, pi_id: str) -> None:
        if self._worker is not None and self._worker.is_active():
            raise AppError('transmission_active')
        if self._profile is None or pi_id != self._profile.pi_id:
            raise AppError('profile_required')      # nur ein Profil gespeichert: anderes Profil öffnen

    def _run_id_now(self):
        try:
            return self._manager.data_link().run_id if self._manager is not None else None
        except Exception:
            return None

    def _run_active(self, r: Readiness) -> bool:
        """Ein Lauf des Pi (Messlauf oder fremde Demo), den wir nicht selbst gestartet haben."""
        return r.peer == 'authenticated' and r.output in ('blocked', 'demo_only', 'test_release') and not self._demo_started

    def _safe_ports(self):
        return tuple(p.port for p in self._ports.cached())

    def _variant_route(self, r: Readiness, d: dict) -> tuple[str, dict]:
        route = self._route or 'network'
        if r.peer == 'authenticated':
            return 'E3ok', d
        if self._resumed:
            d['resumed'] = True
        if r.peer == 'connecting':
            d['connecting'] = True
        elif r.peer == 'backoff':
            d.update(backoff=True, code=r.next_action)
        elif (self._connect_attempted and r.peer == 'disconnected'
              and r.next_action not in (None, 'connect', 'reconnect', 'disconnected')):
            d['code'] = r.next_action                # Fehlerleiste; die Auswahl bleibt bedienbar
        if route == 'uart':
            adapters = [a for a in self._adapters if a.is_supported]
            ids = tuple(a.instance_id for a in adapters)
            d.update(adapter_items=tuple(
                (f'USB-Seriell-Adapter · {a.port or "kein COM"}', f'USB-Ort: {a.location or "unbekannt"}',
                 a.instance_id == self._adapter_id) for a in adapters), choices={'adapter': ids})
            return ('E3uart2' if len(adapters) > 1 and self._adapter_id not in ids else 'E3uart'), d
        items, ids = [], []
        if self._profile is not None:
            for ep in self._profile.endpoints:
                items.append((ep, 'aus dem Profil', ep == self._endpoint))
                ids.append(ep)
            for c in self._candidates:
                for ep in c.endpoints:
                    if ep not in ids:
                        items.append((c.name, f'{ep} · gefunden, unbestätigt', ep == self._endpoint, 'Unbestätigt'))
                        ids.append(ep)
        d.update(found_items=tuple(items), choices={'found': tuple(ids)}, manual_endpoint=self._endpoint or '')
        return 'E3', d

    def context(self) -> UiContext:
        r, w = self.snapshot(), self.worker_status()
        p, pair = self._profile, self._pair
        variant, data = self._variant(r, w)
        authenticated = r.peer == 'authenticated'
        run_id = None
        if authenticated and self._manager is not None:
            try:
                run_id = self._manager.data_link().run_id
            except Exception:
                run_id = None
        route = {'network': 'Netzwerk', 'uart_bridge': 'UART (USB-Adapter)',
                 'uart_direct': 'UART direkt'}.get(self._route_mode)
        demo = authenticated and r.output == 'demo_only'
        test_release = authenticated and r.output == 'test_release'
        with self._lock:
            journal = tuple(self._entries)
            com_issue = self._com_issue if demo else None
            data = dict(data, notice=self._notice)
            return UiContext(
                pi_name=p.name if p else None, route=route, run_id=run_id,
                mode='operate' if (self._setup_done or self._overview) else 'setup',
                setup=SetupState(self._step, variant, data),
                dut_locked=True,                         # nie freigegeben: Abnahme fehlt (OQ-06/OQ-47)
                demo=demo, test_release=test_release,
                forwarded=self._tr_written if test_release else 0, omitted=self._tr_omitted if test_release else 0,
                waiting_for_run=authenticated and r.output == 'output_off',
                com_issue=com_issue,
                bridge_port=pair.bridge_port if pair else None, gsv_port=self._adapter_port if self._route_mode == 'uart_direct' else pair.gsv_port if pair else None,
                session_name=Path(self._session_path).name if self._session_path else None, session_confirmed=self._session_confirmed, receipt=None,
                switch_locked=bool(w is not None and w.active),
                version=self._version, channel=self._channel, pi_id=p.pi_id if p else '',
                endpoint=(self._endpoint or '') if self._route != 'uart' else 'UART (USB-Adapter)',
                fingerprint=format_fingerprint(p.certificate_sha256) if p else '',
                protocol='Version 2' if p else None, retry_in_s=self._retry_in(r),
                code_remaining_s=self._code_remaining() if not self._is_paired() else None,
                auto_connect=self._auto_effective(), route_mode=self._route_mode,
                setup_leavable=True, activity_seq=self._activity_seq,
                uart_baud=p.uart_baud if p else UART_BAUD, gsv_baud=GSVMULTI_BAUD,
                adapter_port=self._adapter_port, adapter_present=self._ports.present(self._adapter_port),
                session_template=TEMPLATE_ID, session_channels=TEMPLATE_CHANNELS,
                paired=((p.name, p.pi_id, 'gekoppelt'),) if p and self._is_paired() else (),
                journal=journal, last_report=self._last_contact, last_ack=self._last_ack)

    # ------------------------------------------------------------ Diagnose / Ende
    @_reports
    def export_diagnostics(self, destination: Path) -> Path:
        """ZIP mit redigierten Details und Journal-Zählern; keine Zugangsdaten, keine Nutzdaten."""
        destination = Path(destination)
        attempts = self._journal_open().attempts()
        counts: dict[str, int] = {}
        for a in attempts:
            counts[a.outcome] = counts.get(a.outcome, 0) + 1
        r, w = self.snapshot(), self.worker_status()
        summary = dict(version=self._version, readiness=asdict(r),
                       worker=None if w is None else asdict(w),
                       route=self._route_mode, port_pair=None if self._pair is None else
                       dict(bridge_port=self._pair.bridge_port, gsv_port=self._pair.gsv_port, manual=True),
                       journal=dict(attempts=len(attempts), by_outcome=counts,
                                    unresolved=len(self._journal_open().unresolved())))
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('summary.json', json.dumps(summary, indent=2))
            self._diag_flush()
            z.writestr('details.jsonl', self._diag.export())
        return destination

    @_reports
    def request_exit(self, confirmed: bool) -> bool:
        if not confirmed:
            return False
        self._presence_stop.set()
        self._stop_all()
        self._diag_flush()
        self._diag_stop.set()
        if self._journal is not None:
            try:
                self._journal.close()
            except Exception:
                pass
            self._journal = None
        self._exited = True
        return True
