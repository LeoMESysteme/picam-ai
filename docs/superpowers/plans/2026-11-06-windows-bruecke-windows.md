# Windows-Brücke: Anwendung und Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ohne Terminal von Installation über Pi-Verbindung bis zu einer passenden, tatsächlich geprüften GSVmulti-Testsession führen.

**Architecture:** Qt-Ansichten konsumieren Zustandsmodell und Ereignisse des Brückenkerns. Geräte-/Treiberadapter aus N2, Sessionevidenz aus N3 und v2-Vertrag aus P1–P4 werden wiederverwendet; GUI besitzt keine zweite Transportlogik.

**Tech Stack:** Gebündeltes Python >=3.13/PySide6/pySerial, Windows-PnP und geschützter Benutzerspeicher, PyInstaller/Inno Setup; Windows 11 x64.

**Spec:** [Freigegebener Entwurf](../specs/2026-11-06-windows-bruecke-design.md); [Hauptplan](2026-11-06-windows-bruecke.md).

## Global Constraints

- N1/N2/N3-Nachweise vor größerem GUI-Ausbau; fehlende externe Nachweise bleiben sichtbar offen.
- Kein System-Python/PATH ändern; Standardnutzer im Betrieb, Installation/Systemarbeiten gesondert autorisiert.
- Keine automatische Pi-/Transportumschaltung, keine Messung starten oder Einrichtung bestätigen.
- COM-ACK ist Treiberweitergabe; kein Empfangs-/Messfreigabenachweis. DUT-Werte gesperrt.
- Demo/provisional und TimeBaseKind erhalten; unbekannte Unsicherheit None; keine ungepaarten Hostuhren subtrahieren.
- Eigene Dateien committen, CHANGELOG/Abhängigkeiten/Sessionstatus mitführen; Windows-Artefakte nicht vom Pi-Build behaupten.

## Review Focus

- Profil von falschem Pi oder abgelaufene Kopplung nach Netzwechsel (W1).
- Zwei identische Adapter ohne Seriennummer (W1).
- Prozessabbruch nach COM-write vor ACK bzw. Auditfehler (W2).
- Teilinstallation, belegtes fremdes Paar oder abgelehnte UAC (W3).
- Sessiondatei erzeugt ohne tatsächliche Übernahme in GSVmulti (W4).

## Lokaler Backendstand 06.11.2026

W1 und W2 einschließlich gemeinsamen Wiederanlaufs sind lokal implementiert;
W3 besitzt portable Installer-/Updateadapter. Abschließender betroffener Lauf:
430 bestanden, vier native Windows-Gates übersprungen. Reale DPAPI/DACL,
Instanz-/Freezeprüfung, native Treiber-/Deploymentanbieter und Produktpaket
bleiben offen. W4 und sichtbare Workbench-Anbindung übernimmt Claude.
Gemischte Schritte mit Windows-/GUI-Abnahme bleiben unten deshalb offen;
die [Übergabe](../handoffs/2026-11-06-windows-bruecke-claude.md) benennt die
vorhandenen APIs und die fehlenden Nachweise. Kein fertiger Produktinstaller.

### W1: Verbindung, geschützter Speicher und Bereitschaftsmodell

**Files:** Create `windows/bridge/src/dispread_bridge_app/connection.py`, `credentials.py`, `readiness.py`, `transports.py`; create `windows/bridge/tests/test_connection.py`, `test_credentials.py`, `test_readiness.py`; consume N2 devices.py/vcom.py and P1 protocol/types.

**Interfaces:** `ConnectionManager(profile: BridgeProfile, client_id: str, credentials, devices, transport_factory, emit)` with `connect(mode: str, selected_device_id: str | None=None)`, `disconnect()`, `cancel()`, `snapshot()->Readiness`; `CredentialStore.save(pi_id, transport, token)`, `load(pi_id, transport)->str|None`, `remove(pi_id, transport)`; `Readiness(components: str, adapter: str, peer: str, output: str, com: str, gsv: str, next_action: str|None)` mit unabhängigem GSV-Empfangsstatus. Transportadapter exponiert `send/receive/close`, ist vom Qt-Thread getrennt.

- [x] W1.1 RED: falsche Pi-ID/Pin, abgelaufenes Zertifikat/Offer, falsche Protokollversion und anderer Transport abweisen. `test_same_hostname_different_pi_never_reconnects` und `test_matching_adapter_without_unique_serial_needs_selection` müssen keine COM-Weitergabe auslösen.
- [x] W1.2 Verbindungszustandsmaschine mit abbrechbaren Hintergrundoperationen implementieren. Netzwerk = gekoppelte WSS-Verbindung mit geprüftem Pin/Gültigkeit; UART = echter signierter Hello. DiscoveryCandidate ist unbestätigt, bis Identität geprüft. Backoff 1/2/4/8 s, auf 8 s begrenzt; keine aktive Transportumschaltung.
- [ ] W1.3 Credentials benutzergebunden mit Windows-Schutz speichern, Dateirechte und Logredaktion testen. Kein Token in GSV-Datei, Profilexport oder Fehlerdialog. `test_other_windows_user_cannot_reuse_credentials` muss erneute Kopplung statt ungeschützter Ersatzablage verlangen.
- [ ] W1.4 RED/GREEN: USB-Abziehen/Wiederanschluss mit COM6→COM9, mDNS-Ausfall mit explizitem Endpunkt, Tailscale abgemeldet, Uhrfehler, Cancel während Backoff. „Adapter erkannt, Pi antwortet nicht“ darf keine konkrete fehlende Leitung behaupten.
- [ ] W1.5 `./.build-venv/Scripts/python.exe -m pytest -q windows/bridge/tests/test_connection.py windows/bridge/tests/test_credentials.py windows/bridge/tests/test_readiness.py`. Echte DPAPI-/Windows-API-Tests getrennt von Fake-Unit-Tests kennzeichnen.
- [x] W1.6 Reinen Verbindungskern plus Tests/Doku/CHANGELOG committen; noch keine produktive Ausgabe.

### W2: Auditierter Brückenworker und kontrolliertes Lebensende

**Files:** Create `windows/bridge/src/dispread_bridge_app/worker.py`, `delivery_journal.py`, `instance.py`; modify `src/dispread/gsv_bridge.py` nur für benötigte injizierbare Ereignis-/Abbruchnaht, ohne Formatter/Freigabe abzuschwächen; create `windows/bridge/tests/test_worker.py`, `test_delivery_journal.py`, `test_instance.py`; extend `tests/test_gsv_bridge.py`.

**Interfaces:** `BridgeWorker(connection, com_factory, journal, emit)` with `start()`, `stop()`, `is_active()->bool`; verwendet `BridgeSession.exchange()` über validierten v2/v1-Datenadapter. `DeliveryJournal.begin_attempt(pi_id, run_id, frame_sequence, barrier_id, payload: bytes)->str`, `finish_attempt(attempt_id, outcome: str)`, `unresolved()->tuple`, `should_emit(...)->bool`; Schlüssel enthält Pi/Run/Frame/Barriere. `SingleInstance.activate_or_acquire()->bool` schützt eine Appinstanz pro Windows-Benutzer; Port-/Runexklusivität kommt zusätzlich aus OS und Pi-Lease.

- [x] W2.1 RED mit Fake-COM: `test_kill_after_write_before_ack_does_not_resend_numeric`, `test_partial_write_is_unknown_not_success`, `test_full_disk_before_intent_prevents_write`, `test_audit_failure_after_write_stops_and_marks_unknown`. GSV-Empfang darf nie aus erfolgreichem COM-Schreiben abgeleitet werden.
- [x] W2.2 Persistentes Journal mit bestätigtem Intent vor COM und Ergebnis danach implementieren (SQLite-Transaktionen oder gleichwertig nachweisbarer dauerhafter Speicher). COM-Aufruf und Journaladapter über die bestehende BridgeSession nahtlos verbinden; einmalige Formatierung und keine zweite Zahlenerkennung. Crash zwischen Ergebnis und ACK: vorhandenes Ergebnis quittieren, keine Zahl erneut schreiben.
- [x] W2.3 Unklare Zahlenübergabe nicht wiederholen. Unbestätigte Invalidierung getrennt halten; solange deren Auflösung nicht durch geprüfte idempotente Regel gedeckt ist, Ausgabe blockieren statt gültige Zahlen an ihr vorbeizulassen. `test_unknown_invalidation_blocks_new_valid_after_restart` prüft diese Grenze. Keine Exactly-once-Zusage bei unbestätigtem COM-Erfolg. `test_slow_uart_keeps_latest_bounded` prüft mit langsamer 115200-Baud-Strecke begrenzten Speicher und dass aktuelle Zahlen nicht hinter einer historischen Queue warten.
- [ ] W2.4 Workerstop, GUI-Abbruch, zweiter Appstart und Leaseverlust testen. Bestehendes Fenster aktivieren; Minimieren hält Worker aktiv; explizites Beenden/Abmelden/Suspend unterbricht erkennbar. Keine laufende GSVmulti-Instanz zwangsweise schließen.
- [ ] W2.5 Windows-Detaildiagnose auf maximal 64 MiB/7 Tage begrenzen und transparent anzeigen; Run-Audit bis expliziter Bereinigung erhalten. Volle Platte führt zu `audit_failed` und gestoppter COM-Ausgabe, nicht zu stiller Löschung. Diagnoseexport redigiert Secrets. Globale Laufaufbewahrung bleibt OQ-60.
- [ ] W2.6 `./.build-venv/Scripts/python.exe -m pytest -q windows/bridge/tests/test_worker.py windows/bridge/tests/test_delivery_journal.py windows/bridge/tests/test_instance.py`; Pi-Regression `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_gsv_bridge.py tests/test_gsv_transport.py`. Echten Prozessabbruch auf Test-Portpaar protokollieren.
- [x] W2.7 Kern/Journaldoku/CHANGELOG committen. Keine Kamera-/Referenzänderung und keine Freigabe von DUT-Werten.

### W3: Fortsetzbarer Installer, Reparatur und Update

**Files:** Create `windows/bridge/src/dispread_bridge_app/install.py`, `admin_helper.py`, `updates.py`, `windows/bridge/packaging/setup.iss`, `windows/bridge/packaging/release-manifest.schema.json`, `windows/bridge/tests/test_install.py`, `test_updates.py`; extend `build.ps1`; create `.github/workflows/windows-bridge.yml` erst mit tatsächlich bereitgestelltem Windows-Runner; modify `docs/dependencies.md`, `windows/bridge/README.md`.

**Interfaces:** `Installer.ensure_components(request, devices, vcom)->InstallResult`, `resume_install(state_path: Path)->InstallResult`; privilegierter Helfer nimmt nur erlaubte strukturierte Aktionen `inventory/create_pair/repair_owned_pair/remove_unused_owned_pair` entgegen. `UpdateManager.check(manifest_bytes: bytes)->ReleaseInfo`, `install(release, *, output_active: bool)->InstallResult`; `ReleaseInfo(version: str, source_commit: str, artifacts: tuple, signature: bytes)`. Schlüssel/Hosting sind externe Release-Voraussetzungen, keine Testdaten im Produkt.

- [ ] W3.1 RED: Signatur-/Hashfehler, Proxy-/Downloadabbruch, knapper Platz, Reboot und Cancel hinterlassen fortsetzbaren Zustand; `test_uac_denial_keeps_previous_working_install`, `test_uninstall_preserves_borrowed_pair_and_audits`, `test_update_while_output_active_is_refused` konkret prüfen.
- [ ] W3.2 Setup-EXE mit unveränderlichem Release-Manifest und beschränktem Helfer bauen. Standardinstallation nach Program Files, Benutzerkonfiguration/Logs getrennt; Runtime läuft normal, nicht erhöht. Admin-Helfer nur aus vertrauenswürdig installiertem Paket starten, keine beliebigen Kommandos/Dateipfade aus Profilen annehmen.
- [ ] W3.3 N2-Komponenten idempotent einrichten, Rechte/Neustart erklären; kein Security-Abschalten oder neues Paar bei jeder Reparatur. Vorherige Version erhalten und Konfiguration versioniert migrieren; nach fehlgeschlagenem Update kontrolliert zurückkehren. Benutzer muss über aktive Ausgabe/noch offene Logs informiert bleiben.
- [ ] W3.4 Release-Artefakte auf Windows bauen/signieren und manifestieren. Neue Forgejo-Jobdatei benutzt nur `picam-windows-x64`, keine Pi-Runner-/Systempaketänderungen. Ohne Runner/Signierung nur klar markierter interner Build über dokumentiertes `build.ps1`; kein erfolgreicher Produktrelease-Status.
- [ ] W3.5 `./.build-venv/Scripts/python.exe -m pytest -q windows/bridge/tests/test_install.py windows/bridge/tests/test_updates.py`; echtes Setup auf frischer VM, verweigerte UAC, Reboot und zweimalige Reparatur prüfen. Hashes/Signaturen/PnP-Ergebnisse als Artefakte sichern.
- [x] W3.6 Installer/Build/Abhängigkeitsdoku/CHANGELOG committen. Veröffentlichen oder Installation auf realem Arbeits-PC nur innerhalb konkret autorisierter Aktion.

### W4: Sessiongenerator und Qt-Einrichtungsoberfläche

**Files:** Create `windows/bridge/src/dispread_bridge_app/session_export.py`, `controller.py`, `gsv_test_capture.py`, `main.py`, `ui/window.py`, `ui/setup_page.py`, `ui/connection_page.py`, `ui/status_page.py`, `windows/bridge/tests/test_session_export.py`, `test_ui.py`; extend Windows `types.py`, bestehendes `session_templates.py`; extend Workbench-Anleitung aus P4 und `tests/live-ui.spec.ts` bei geänderter Verknüpfung.

**Interfaces:** `SessionSettings(template_id: str, gsv_port: str, baudrate: int=115200, unit: str='mV/V', scale: float=1.0, rate_hz: float=10.0)`; `SessionExport(path: Path, template_id: str, sha256: str, gsv_port: str, requires_import: bool=True)`; `export_session(evidence: TemplateEvidence, settings: SessionSettings, destination: Path)->SessionExport`. `AppController(installer, connection, worker, session_exporter)` in controller.py bietet `load_profile(raw: bytes)->Readiness`, `install_components()->InstallResult`, `connect(mode: str, selected_device_id: str | None=None)`, `disconnect()`, `export_session(settings: SessionSettings, destination: Path)->SessionExport`, `begin_demo_check(confirmed_test_session: bool)`, `request_exit(confirmed: bool)->bool`, `subscribe(callback)`. `MainWindow(controller: AppController)` konsumiert InstallResult/Readiness/BridgeEvent; keine blockierenden Port-/Netzoperationen in Widgets. `verify_test_capture(path: Path, expected_records: tuple)->GsvTestResult` in gsv_test_capture.py prüft nur das in N3 belegte Text-Exportformat; `GsvTestResult(file_sha256: str, expected_count: int, matched_count: int, matches: bool, scope: str='selected_test_file')` benennt die Beleggrenze.

- [ ] W4.1 RED: `test_unknown_version_or_unverified_template_blocks_export`, `test_export_uses_actual_virtual_peer_not_usb_port`, `test_export_never_overwrites_existing_session`, `test_file_created_does_not_imply_gsv_reception`. COM6 als USB und COM4 als virtuellen Gegenport setzen, erwartete GSV-Konfiguration = COM4.
- [ ] W4.2 Nur in N3 belegte Felder der freigegebenen Vorlage ändern; Originalvorlage unverändert halten. Neue Datei atomar und ohne Überschreiben ausgeben, genaue Import-/Öffnen-Aktion für diese Version anzeigen. Unbekannte Version erhält manuelle, als eingeschränkt benannte Anleitung; keine erfundene Sessiondatei.
- [ ] W4.3 Vor visueller Umsetzung Impeccable für diese Operate-Oberfläche nutzen. Qt-Ansichten für Komponenten → Pi/Kopplung → UART/Netz → Session → Empfangstest implementieren. Statusstufen aus Readiness getrennt anzeigen, nächste Aktion sichtbar, Details/Diagnoseexport tiefer. Keine pauschale grüne „Messfreigabe“.
- [ ] W4.4 RED/GREEN Qt-Tests mit Fake-Controller: Klick/Tab/Enter funktionieren; bestehende Verbindung bleibt beim Minimieren aktiv; `test_closed_window_needs_explicit_worker_exit`, `test_busy_run_locks_configuration`, `test_usb_missing_and_pi_waiting_have_distinct_actions`. Windows-QTest/offscreen für Logik, tatsächliche Screenshots bei 100/150/200 % Skalierung für Abnahme.
- [ ] W4.5 Empfangstest nur nach expliziter Aktion als Demo und mit separater GSVmulti-Testsession. `AppController.begin_demo_check` verlangt explizite Bestätigung einer getrennten GSVmulti-Testsession und fordert P4.start_demo über den gekoppelten Kanal an. Keine automatischen Testwerte in eine echte Messung einschleusen. Originale neue Testdatei vom Nutzer auswählen lassen, über den N3-belegten Exportparser jeden Wert/Anzahl/Reihenfolge vergleichen und Datei-Hash sichern. Status „Session erzeugt“, „Übernahme bestätigt“ und „Empfang belegt“ auseinanderhalten; letzteren nur aus kontrolliertem Originaldateivergleich ableiten. Das gilt für die kontrolliert aufgezeichnete, ausgewählte Testdatei und Konfiguration, nicht jede spätere COM-Übergabe. GSVmulti trägt dabei keine Pi-Run-ID; allein gleiche Zahlen in einer beliebigen alten Datei belegen keinen neuen Empfang. Aufnahmeablauf und Benutzerbestätigung mitprotokollieren; bei unbekanntem Dateiformat kein Erfolg.
- [ ] W4.6 `./.build-venv/Scripts/python.exe -m pytest -q windows/bridge/tests/test_session_export.py windows/bridge/tests/test_ui.py`; echten Bedienlauf ohne Terminal durchführen, neue Datei in GSVmulti öffnen und Parameter/Originalausgabe vergleichen. Vorhandene Nutzersession und realen Messlauf erhalten.
- [ ] W4.7 GUI/Generator/Anleitung/CHANGELOG committen; anschließend Hauptplan G1. Ohne echte Windows-/GSVmulti-Prüfung nicht als ausgeliefert oder abgenommen melden.
