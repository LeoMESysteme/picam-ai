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


MODES = ('uart_direct', 'uart_bridge', 'network')   # Reihenfolge der Moduswahl (UX2)


@dataclass(frozen=True)
class CheckResult:
    """Ergebnis einer echten Prüfung einer Eingabe (UX2). Nie geraten, nie Secrets im Text.

    ``state``: ``ok`` (geprüft und angenommen), ``warn`` (angenommen, aber mit Vorbehalt,
    z. B. Port vorhanden, aber kein com0com-Paar erkannt), ``err`` (abgelehnt).
    ``message`` ist ein kurzer Satz in Bedienersprache („Pi erreichbar, Zertifikat passt“),
    ``detail`` optional eine Zweitzeile mit der nächsten Aktion.
    """
    state: str
    message: str
    detail: str = ''


@dataclass(frozen=True)
class ModeInfo:
    """Zustand eines der drei Ausgabewege für das Moduswahl-Fenster (UX2)."""
    mode: str                 # uart_direct | uart_bridge | network
    configured: bool          # Einrichtung dieses Wegs abgeschlossen
    active: bool              # aktuell gewählter Weg
    status: str               # kurz, z. B. „Adapter COM9 erkannt“, „gekoppelt mit Prüfstand 2“
    tone: str = 'info'        # ok | warn | err | info (Proven-Green-Regel gilt)
    available: bool = True    # jetzt wählbar; False z. B. während einer Übertragung
    reason: str = ''          # warum nicht wählbar


@dataclass(frozen=True)
class PortChoice:
    """Ein COM-Port bzw. USB-Adapter für Auswahllisten (UX2)."""
    port: str                 # „COM7“
    label: str                # „COM7 – com0com Brückenseite“ / „COM9 – FTDI USB Serial“
    kind: str = 'other'       # com0com | usb_serial | other
    busy: bool | None = None  # True = belegt, None = unbekannt
    device_id: str | None = None   # für select_adapter (nur USB-Adapter)


@dataclass(frozen=True)
class SessionExport:
    """Erzeugte GSVmulti-Session (UX2): Kopie der belegten Vorlage, nur Port geändert."""
    path: Path
    port: str
    template_id: str
    sha256: str
    channels: int = 1                       # Kanäle der Vorlage (NumChan)
    hidden_channels: int = 0                # davon ausgeblendet (IsHidden = TRUE)
    record_hidden_required: bool = False    # Bediener muss in GSVmulti „Record Hidden Channels“ einschalten
                                            # (steht nicht in der .ucf, sonst fehlen diese Kanäle still)


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
    # --- UX2 ---
    route_mode: str | None = None           # uart_direct | uart_bridge | network; None = noch nicht gewählt
    setup_leavable: bool = False            # Einrichtung darf ohne Abschluss verlassen werden
    activity_seq: int = 0                   # zählt jeden erfolgreichen Austausch mit dem Pi (Herzschlag-Anzeige)
    uart_baud: int | None = None            # Pi↔Brücke-UART laut Profil/Konstante (eine Quelle, Anzeige)
    gsv_baud: int | None = None             # Baudrate der GSVmulti-Seite laut Session-Vorlage (Anzeige)
    adapter_port: str | None = None         # gewählter USB-UART-Adapter, z. B. „COM9“
    adapter_present: bool | None = None     # steckt der gewählte Adapter gerade? None = unbekannt
    session_template: str | None = None     # Kennung der Vorlage, aus der Sessions erzeugt werden
    session_channels: int | None = None     # Kanalzahl der aktiven Vorlage (1 = Einkanal-Ausgabe, F3-Warnung)


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
    # --- UX2 (blockierend erlaubt, laufen im Pool) ---
    def modes(self) -> tuple[ModeInfo, ...]: ...            # immer alle drei, Reihenfolge MODES
    def select_mode(self, mode: str) -> None: ...           # nicht eingerichtet → Einrichtung dieses Wegs; gesperrt → AppError('mode_locked')
    def leave_setup(self) -> None: ...                      # zurück in den Betrieb, gespeicherte Konfiguration bleibt
    def list_ports(self) -> tuple[PortChoice, ...]: ...     # alle COM-Ports mit Art/Belegung
    def list_adapters(self) -> tuple[PortChoice, ...]: ...  # nur USB-Seriell-Adapter
    def check_endpoint(self, text: str) -> CheckResult: ...         # Syntax → Namensauflösung → TCP → TLS-Fingerabdruck
    def check_port_pair(self, bridge_port: str, gsv_port: str) -> CheckResult: ...
    def check_adapter(self, port: str) -> CheckResult: ...          # vorhanden, exklusiv zu öffnen, wieder frei
    def check_pairing_code(self, code: str) -> CheckResult: ...     # nur Format, lokal, nicht blockierend
    def export_session_file(self, destination: Path, port: str | None = None) -> SessionExport: ...
    def diagnostics_contents(self) -> tuple[tuple[str, str], ...]: ...   # (Datei im ZIP, was drinsteht)
    # nicht blockierende Lesezugriffe
    def snapshot(self) -> Readiness: ...
    def worker_status(self) -> WorkerStatus | None: ...
    def context(self) -> UiContext: ...
