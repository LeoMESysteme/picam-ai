# Übergabe Qt-Oberfläche an Codex (AppController)

Stand 2026-11-06, Branch `feat/bruecke-ui` (BQ1). Nur offscreen unter Linux geprüft, keine Windows-Abnahme.
**Das Paket `windows/bridge/src/dispread_bridge_app/ui/` ändert Codex nicht** (UI bleibt bei Claude).
Codex implementiert nur den Port (`ui/port.py`) im AppController und baut `controller.py`; `main.py` bekommt die Fabrik per Parameter (`run(controller_factory=...)`).

## Port-Vertrag (vorhanden)
`load_profile(raw: bytes) -> Readiness` · `install_components() -> InstallResult` · `connect(mode: 'network'|'uart', selected_device_id=None)` · `disconnect()` · `export_session(settings, destination: Path)` · `begin_demo_check(confirmed_test_session: bool)` · `request_exit(confirmed: bool) -> bool` · `subscribe(cb: Callable[[BridgeEvent], None]) -> Callable[[], None]` (Rückgabe = Abmeldefunktion).
Lesezugriffe **nicht blockierend** (aus Zwischenspeicher, GUI-Thread ruft sie bei jedem Refresh): `snapshot() -> Readiness`, `worker_status() -> WorkerStatus | None`, `context() -> UiContext`.

## `UiContext` (alle Felder frozen; fehlender Wert = `None`/leer, die UI zeigt „–“ statt Beispielwerte)
- `pi_name`, `pi_id`, `route` („Netzwerk (LAN)“ / „UART (USB-Adapter)“), `endpoint`, `fingerprint`, `protocol`: aus dem geladenen Profil / ConnectionManager.
- `dut_locked` (Default True = sicher), `last_report`: **vom Pi** (Hello/Poll), nie lokal geraten. `release`: Text nur nach bestandener Windows-Abnahme, sonst `None`.
- `run_id`, `waiting_for_run`, `demo`, `retry_in_s`, `com_issue` (`busy|write_failed|unclear`, nur Demo): aus Worker/Connection.
- `bridge_port`, `gsv_port`: tatsächliches Portpaar (Installer). `session_name`, `session_confirmed` (Bedienerbestätigung), `receipt: Receipt` (`proven=True` **nur** nach Testdateivergleich), `last_ack`.
- `mode` (`operate|setup`) und `setup: SetupState(step, variant, data)`: Einrichtungszustand (Varianten E1…E5 in `ui/texts.py:SETUP`; `data` überschreibt Platzhalter wie `peer_fingerprint`, `test_sha256`).
- `switch_locked`, `paired`, `journal` (Startinhalt, spätere Einträge kommen über `subscribe`), `version`.

## Fehlende Port-Methoden (UI ruft sie bisher nicht; Aktion landet in `MainWindow.unhandled`)
Vorschlag, alle blockierend erlaubt (UI ruft sie über QThreadPool):
- `pair(code: str, fingerprint_confirmed: bool) -> None` (Aktion `pair`)
- `select_pi(pi_id: str) -> None` (nur im Zustand ohne Übertragung)
- `list_adapters() -> list[DeviceInfo]` / `select_adapter(device_id: str)`; Netzwerkliste `discover_pis()`
- `export_diagnostics(destination: Path) -> Path` (ohne Zugangsdaten)
- `verify_test_file(path: Path) -> GsvTestResult` (Plan W4.5, setzt `receipt.proven`)
- `export_session(settings: SessionSettings, destination: Path)`: UI übergibt vorläufig `{'gsv_port': ...}`; bitte `SessionSettings` (Plan W4) aus `context()` ableiten lassen oder Signatur ohne `settings` anbieten.
- Neustart (`restart`) und Navigation (Schritt vor/zurück) hält bisher nur die UI.

## Threading-Vertrag
`subscribe`-Callbacks dürfen aus **jedem Thread** (Workerthread) kommen; die UI marshallt per Qt-Signal in den GUI-Thread. Callbacks nie blockieren. Event-Details werden nie angezeigt (nur `kind`/`code`), trotzdem keine Zugangsdaten in `detail`. Nicht-Lesemethoden laufen im Pool-Thread, dürfen blockieren (Worker-Stop bis 2 s), müssen aber thread-sicher sein. `request_exit(True)` muss den Worker über `BridgeWorker.stop()` beenden; Rückgabe `True` beendet die App. Abmelden/Standby ruft `request_exit(True)` (Fallback `disconnect()`).

## Nur auf Windows prüfbar
Windows-Farbschema/Akzent, Segoe UI Variable, Hochkontrast, 100/150/200 % DPI, Tray-Symbole und -Hinweis, WM_POWERBROADCAST/Abmelden, Einzelinstanz mit echtem Kernel, Dialogwirkung. `ui/fake.py` + `--demo-ui [--state=B3]` zur Sichtprüfung.

## Bekannt offen
Mock-Beispieldaten in `texts.SETUP` (gefundene Pi in E3, Adapter COM6/COM7, Fortschritt in E5run, Dateiname in E5ok) bis Entdeckung/Test sie liefern; Profil-Drag&Drop, Scrim, Hochkontrast-Palette fehlen.
