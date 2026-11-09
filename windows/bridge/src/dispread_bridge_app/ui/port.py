"""Schmale Schnittstelle zwischen Oberfläche und Controller.

Der echte AppController (Plan W4) erfüllt diesen Port. Die Oberfläche kennt
nichts anderes. Lesezugriffe (``snapshot``, ``worker_status``, ``context``)
müssen nicht blockieren und dürfen aus dem GUI-Thread laufen (zwischengespeicherter
Zustand). Alle anderen Aufrufe können blockieren und werden von der
Oberfläche über einen Thread-Pool abgesetzt.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from dispread.bridge.types import BridgeEvent
from dispread_bridge_app.readiness import Readiness
from dispread_bridge_app.worker import WorkerStatus


@dataclass(frozen=True)
class JournalEntry:
    time: str
    title: str
    sub: str = ''
    duration: str = ''
    tone: str = 'info'        # ok | warn | err | info
    day: str = 'Heute'
    fault: bool = False       # zählt im Filter "Störungen"


@dataclass(frozen=True)
class Receipt:
    """Ergebnis des Empfangstests. ``proven`` nur nach Testdatei-Vergleich."""
    proven: bool
    label: str = ''           # z. B. "Test 14:02 (Demo), 600/600"
    filename: str = ''
    sha256: str = ''
    demo: bool = True


@dataclass(frozen=True)
class SetupState:
    step: int                 # 1..5
    variant: str              # Schlüssel in texts.SETUP, z. B. "E2b"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UiContext:
    """Anzeigekontext, den Readiness/WorkerStatus nicht tragen."""
    pi_name: str | None = None
    route: str | None = None                # "Netzwerk (LAN)" / "UART (USB-Adapter)"
    run_id: str | None = None
    mode: str = 'operate'                   # operate | setup
    setup: SetupState | None = None
    dut_locked: bool = True                 # Sperrzustand vom Pi (Hello); unbekannt = gesperrt
    release: str | None = None              # künftig: "Ausgabe freigegeben am …"
    demo: bool = False
    waiting_for_run: bool = False
    retry_in_s: int | None = None
    test_release: bool = False              # Testfreigabe des Pi aktiv (R1): echte Werte, nicht abgenommen
    forwarded: int = 0                      # Testfreigabe: an den Port übergebene Werte dieses Laufs
    omitted: int = 0                        # Testfreigabe: ausgelassene (ungültige/veraltete) Werte
    com_issue: str | None = None            # busy | write_failed | unclear (nur Demo)
    bridge_port: str | None = None      # echter Wert vom Portpaar; None = nicht festgelegt
    gsv_port: str | None = None
    session_name: str | None = None
    session_confirmed: bool = False
    receipt: Receipt | None = None
    switch_locked: bool = False
    version: str | None = None          # App-Version; None = unbekannt
    channel: str | None = None          # z. B. "Interner Testbuild - nicht qualifiziert"
    pi_id: str = ''
    endpoint: str = ''
    fingerprint: str = ''
    protocol: str | None = None
    paired: tuple[tuple[str, str, str], ...] = ()   # (Name, Pi-ID, zuletzt)
    journal: tuple[JournalEntry, ...] = ()
    last_report: str = ''
    last_ack: str = 'keine'
    code_remaining_s: int | None = None     # Kopplungscode gespeichert: Restgültigkeit; None = kein Code
    auto_connect: bool = False              # "Beim Start automatisch verbinden"


class ControllerPort(Protocol):
    def load_profile(self, raw: bytes) -> Readiness: ...
    def install_components(self) -> Any: ...
    def connect(self, mode: str, selected_device_id: str | None = None) -> None: ...
    def disconnect(self) -> None: ...
    def export_session(self, settings: Any, destination: Path) -> Any: ...
    def begin_demo_check(self, confirmed_test_session: bool) -> None: ...
    def request_exit(self, confirmed: bool) -> bool: ...
    def subscribe(self, callback: Callable[[BridgeEvent], None]) -> Any: ...
    def pair(self, code: str, fingerprint_confirmed: bool) -> None: ...
    def select_route(self, mode: str) -> None: ...
    def select_endpoint(self, endpoint: str, manual: bool = False) -> None: ...
    def select_adapter(self, device_id: str) -> None: ...
    def set_port_pair(self, bridge_port: str, gsv_port: str) -> None: ...
    def open_manual_pair(self) -> None: ...
    def rescan(self) -> None: ...
    def confirm_session(self, on: bool) -> None: ...
    def setup_step(self, direction: str) -> None: ...      # next | back | restart | pairing | finish | change_setup
    def export_diagnostics(self, destination: Path) -> Path: ...
    def set_auto_connect(self, on: bool) -> None: ...
    def auto_connect_at_start(self) -> bool: ...
    def switch_pi(self, pi_id: str) -> None: ...
    # nicht blockierende Lesezugriffe
    def snapshot(self) -> Readiness: ...
    def worker_status(self) -> WorkerStatus | None: ...
    def context(self) -> UiContext: ...
