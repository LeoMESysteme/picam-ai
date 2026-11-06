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
import os
import threading
import uuid
import zipfile
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from dispread.bridge.protocol import parse_profile
from dispread.bridge.types import BridgeEvent, BridgeProfile

from .connection import ConnectionManager
from .credentials import CredentialStore
from .delivery_journal import DeliveryJournal, DiagnosticStore
from .readiness import Readiness
from .types import InstallResult, PortPair, valid_port_name
from .ui.port import SetupState, UiContext
from .vcom import VcomAdapter, VcomUnverifiedError
from .worker import BridgeWorker, WorkerStatus

STATE_VERSION = 1
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


def _list_ports_default() -> list[str]:
    from serial.tools import list_ports
    return sorted((p.device for p in list_ports.comports() if valid_port_name(p.device)),
                  key=lambda n: int(n[3:]))


def _open_com(port: str):
    from serial import Serial
    return Serial(port, 115200, bytesize=8, parity='N', stopbits=1, timeout=1, write_timeout=2)


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
                 list_ports: Callable | None = None, discover: Callable | None = None,
                 manager_factory: Callable | None = None, worker_factory: Callable | None = None,
                 network_diagnostics=None, version: str | None = None, build_info=None,
                 demo_count: int = 600, demo_rate_hz: float = 10.0):
        self.data_dir = Path(data_dir) if data_dir else default_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._devices = devices
        self._vcom = vcom if vcom is not None else VcomAdapter()
        self._transport_factory = transport_factory
        self._com_factory = com_factory or _open_com
        self._list_ports = list_ports or _list_ports_default
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
        self._entries: deque = deque(maxlen=200)
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
        self._demo_started = False
        self._written = 0
        self._com_issue: str | None = None
        self._last_ack = 'keine'
        self._last_contact = ''
        self._exited = False
        # persistiert
        self._profile: BridgeProfile | None = None
        self._route: str | None = None
        self._endpoint: str | None = None
        self._adapter_id: str | None = None
        self._pair: PortPair | None = None
        self._session_confirmed = False
        self._setup_done = False
        self._overview = False
        self._step = 1
        self.client_id = ''
        self._load_state()

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
        self._endpoint = data.get('endpoint') if isinstance(data.get('endpoint'), str) else None
        self._adapter_id = data.get('adapter_id') if isinstance(data.get('adapter_id'), str) else None
        self._session_confirmed = data.get('session_confirmed') is True
        self._setup_done = data.get('setup_done') is True and self._profile is not None and self._pair is not None
        self._step = 1 if self._pair is None else (2 if self._profile is None else 3)
        self._save_state()

    def _save_state(self) -> None:
        profile = None
        if self._profile is not None:
            profile = asdict(replace(self._profile, pairing_offer=None))   # Angebot nie speichern
            profile['endpoints'] = list(profile['endpoints'])
        data = dict(version=STATE_VERSION, client_id=self.client_id, profile=profile, route=self._route,
                    endpoint=self._endpoint, adapter_id=self._adapter_id,
                    port_pair=None if self._pair is None else dict(bridge_port=self._pair.bridge_port,
                                                                    gsv_port=self._pair.gsv_port),
                    session_confirmed=self._session_confirmed, setup_done=self._setup_done)
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
        """Nie werfen: ein Fehler hier darf den Worker nicht in audit_failed treiben."""
        try:
            self._diag.append(event)
        except Exception:
            pass
        try:
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

    def _note(self, event: BridgeEvent) -> None:
        from .ui import texts
        with self._lock:
            now = datetime.now().strftime('%H:%M:%S')
            if event.kind == 'connection' and event.code == 'authenticated':
                self._last_contact = now
            if event.kind == 'exchange':
                outcome = (event.detail or {}).get('outcome')
                if outcome == 'written':
                    self._written += 1
                    self._com_issue = None
                    self._last_ack = 'COM-Weitergabe bestätigt – kein GSVmulti-Empfangsnachweis'
                elif outcome == 'failed':
                    self._com_issue = 'write_failed'
                elif outcome in ('unknown', 'unconfirmed', 'stopped'):
                    self._com_issue = 'unclear'
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
            self._offer = profile.pairing_offer          # nur im Speicher
            self._profile = replace(profile, pairing_offer=None)
            self._candidates = ()
            if self._endpoint not in profile.endpoints:
                self._endpoint = profile.endpoints[0] if profile.endpoints else None
            self._connect_attempted = False
            self._setup_done = False
            if self._step < 2 and self._pair is not None:
                self._step = 2
            self._save_state()
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
            self._step = 3

    def _is_paired(self) -> bool:
        if self._profile is None:
            return False
        try:
            return any(self._credentials.load(self._profile.pi_id, m,
                                              expected_pin=self._profile.certificate_sha256)
                       for m in ('network', 'uart'))
        except Exception:
            return False

    # ------------------------------------------------------------ Komponenten / Portpaar
    @_reports
    def install_components(self) -> InstallResult:
        """Nur Inventur. Ein Portpaar wird nie erzeugt; ohne verifizierten Treiberanbieter
        bleibt nur die ausdrückliche manuelle Angabe."""
        try:
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
        with self._lock:
            self._manual_open = True

    @_reports
    def set_port_pair(self, bridge_port: str, gsv_port: str) -> None:
        """Vorhandenes Paar angeben: manuell, nicht von der App geprüft."""
        try:
            pair = PortPair('manual', bridge_port, gsv_port, False)
        except ValueError:
            raise AppError('portpair_invalid') from None
        if self._worker is not None and self._worker.is_active():
            raise AppError('transmission_active')
        if not {bridge_port, gsv_port} <= set(self._list_ports()):
            raise AppError('portpair_invalid')
        with self._lock:
            self._pair = pair
            self._save_state()

    # ------------------------------------------------------------ Weg
    def select_route(self, mode: str) -> None:
        if mode not in ('network', 'uart'):
            raise AppError('transport_unsupported')
        if self._worker is not None and self._worker.is_active():
            raise AppError('transmission_active')
        with self._lock:
            self._route = mode
            self._save_state()

    @_reports
    def select_endpoint(self, endpoint: str, manual: bool = False) -> None:
        from .transports import TransportError, resolve_endpoints
        endpoint = endpoint.strip()
        if manual and '://' not in endpoint:
            endpoint = 'https://' + endpoint
        try:
            resolve_endpoints(endpoint)
        except (TransportError, ValueError):
            raise AppError('endpoint_unsupported') from None
        with self._lock:
            self._endpoint, self._route = endpoint, 'network'
            self._save_state()

    @_reports
    def select_adapter(self, device_id: str) -> None:
        with self._lock:
            self._adapter_id, self._route = device_id, 'uart'
            self._save_state()

    def rescan(self) -> None:
        """Adapter, COM-Ports und Netzkandidaten neu lesen (blockiert)."""
        if self._devices is not None:
            try:
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
            if selected_device_id:
                self._adapter_id = selected_device_id
            self._save_state()
            self._connect_attempted = True
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
        """Gesperrt (N3): keine Datei, nur die manuelle Anleitung in der UI."""
        raise AppError('automatic_export_blocked')

    def confirm_session(self, on: bool) -> None:
        with self._lock:
            self._session_confirmed = bool(on)
            self._save_state()

    # ------------------------------------------------------------ Einrichtungsschritte
    @_reports
    def setup_step(self, direction: str) -> None:
        if direction == 'next' and self._step == 3 and not (
                self._manager is not None and self._manager.snapshot().peer == 'authenticated'):
            self.connect(self._route or 'network', None)      # „Verbinden“; keine Demo, keine Messung
            return
        with self._lock:
            if direction == 'back':
                self._step = max(1, self._step - 1)
            elif direction == 'overview':
                self._overview = True
            elif direction == 'resume':
                self._overview, self._setup_done = False, False
            elif direction == 'pairing':
                self._setup_done, self._overview, self._step = False, False, 2
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
        self._setup_done, self._step = True, 5
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
        if step == 1:
            if self._pair is not None:
                return 'E1ok', d
            if self._manual_open or self._vcom_unverified:
                ports = tuple(self._safe_ports())
                d.update(ports=ports, choices={'bridge_port': ports, 'gsv_port': ports},
                         unverified=self._vcom_unverified)
                return 'E1manual', d
            return 'E1', d
        if step == 2:
            if self._profile is None:
                return 'E2', d
            if self._is_paired():
                return 'E2ok', d
            return 'E2b', d
        if step == 3:
            return self._variant_route(r, d)
        if step == 4:
            d['session_confirmed'] = self._session_confirmed
            return 'E4locked', d
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

    def _run_active(self, r: Readiness) -> bool:
        """Ein Lauf des Pi (Messlauf oder fremde Demo), den wir nicht selbst gestartet haben."""
        return r.peer == 'authenticated' and r.output in ('blocked', 'demo_only') and not self._demo_started

    def _safe_ports(self):
        try:
            return self._list_ports()
        except Exception:
            return ()

    def _variant_route(self, r: Readiness, d: dict) -> tuple[str, dict]:
        route = self._route or 'network'
        if r.peer == 'authenticated':
            return 'E3ok', d
        failed = (self._connect_attempted and r.peer in ('disconnected', 'backoff')
                  and r.next_action not in (None, 'connect', 'reconnect', 'disconnected')) or r.peer == 'backoff'
        if failed:
            d['code'] = r.next_action
            return 'E3err', d
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
        route = {'network': 'Netzwerk', 'uart': 'UART (USB-Adapter)'}.get(self._route or '', None)
        demo = authenticated and r.output == 'demo_only'
        with self._lock:
            journal = tuple(self._entries)
            com_issue = self._com_issue if demo else None
            data = dict(data, notice=self._notice)
            return UiContext(
                pi_name=p.name if p else None, route=route, run_id=run_id,
                mode='operate' if (self._setup_done or self._overview) else 'setup',
                setup=SetupState(self._step, variant, data),
                dut_locked=True,                         # nie freigegeben: Abnahme fehlt (OQ-06/OQ-47)
                demo=demo, waiting_for_run=authenticated and r.output == 'output_off',
                com_issue=com_issue,
                bridge_port=pair.bridge_port if pair else None, gsv_port=pair.gsv_port if pair else None,
                session_name=None, session_confirmed=self._session_confirmed, receipt=None,
                switch_locked=bool(w is not None and w.active),
                version=self._version, channel=self._channel, pi_id=p.pi_id if p else '',
                endpoint=(self._endpoint or '') if self._route != 'uart' else 'UART (USB-Adapter)',
                fingerprint=format_fingerprint(p.certificate_sha256) if p else '',
                protocol='Version 2' if p else None,
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
                       route=self._route, port_pair=None if self._pair is None else
                       dict(bridge_port=self._pair.bridge_port, gsv_port=self._pair.gsv_port, manual=True),
                       journal=dict(attempts=len(attempts), by_outcome=counts,
                                    unresolved=len(self._journal_open().unresolved())))
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('summary.json', json.dumps(summary, indent=2))
            z.writestr('details.jsonl', self._diag.export())
        return destination

    @_reports
    def request_exit(self, confirmed: bool) -> bool:
        if not confirmed:
            return False
        self._stop_all()
        if self._journal is not None:
            try:
                self._journal.close()
            except Exception:
                pass
            self._journal = None
        self._exited = True
        return True
