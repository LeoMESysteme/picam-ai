# Windows-Brücke: Machbarkeitsnachweise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows-Laufzeitpaket, Treiber-/Portpaarverwaltung und Sessionvorlage vor größerem GUI-Ausbau nachweisen.

**Architecture:** Kleine ausführbare Proben und systemnahe Adapter mit injizierbarer Windows-Schnittstelle. Nachweise speichern Versionen, Hashes und Originale; keine Freigabe aus bloßem Installer-Exitcode.

**Tech Stack:** Windows 11 x64, Python >=3.13/PySide6, pySerial, PyInstaller, com0com als erster Prüf-Kandidat.

**Spec:** [Freigegebener Entwurf](../specs/2026-11-06-windows-bruecke-design.md); [Hauptplan und gemeinsame Regeln](2026-11-06-windows-bruecke.md).

## Global Constraints

- Gebündelte Laufzeit; bestehendes Python/PATH/Visual Studio erhalten, keine Qt-Abhängigkeit in Pi-venv.
- Pi-Python nur Projekt-`.venv`, `--system-site-packages`, Installation `--no-deps`; Windows in eigener Build-Umgebung.
- Keine Treiber-/HVCI-Umgehung; fremde Paare/Treiber nicht entfernen; Adminarbeiten nur nach Zielsystemfreigabe.
- Keine Sessionkodierung erfinden; bestätigte GSVmulti-Vorlage und echter Roundtrip nötig.
- Demo/provisional=true, time_claim=false für synthetische Versuche. Produktive DUT-Brücke bleibt gesperrt.
- src-/scripts-Änderungen mit CHANGELOG; Abhängigkeiten dokumentieren; Hardware/Messung sofort in Laborjournal/VALIDATION.

## Stand der technischen Vorarbeit 06.11.2026

N1: Build-/Hash-/Importverträge lokal geprüft (79 Tests einschließlich
Bestandsregression; ein echter Windows-Test übersprungen). N2: 48 Adaptertests
bestanden; der echte Treiberprovider bleibt unverifiziert und verweigert
Systemänderungen. N3: Originalbelege und Inspektion durch 17 Tests geprüft;
`gsv_version=None`, keine freigegebenen Änderungsfelder, Roundtrip false.
Alle drei externen Gates bleiben offen. Kein neuer Windows-/Hardwareversuch.

## Review Focus

- Python 3.7 als einziger Systeminterpreter (N1).
- Geblockter Download oder abgebrochene Paketierung (N1).
- Fremdes genutztes Paar und fehlende Administratorrechte (N2).
- Erfolgreicher Installer bei defekten PnP-Geräten (N2).
- Datei lässt sich erzeugen, GSVmulti übernimmt Filter/Einheit aber nicht (N3).

### N1: Reproduzierbares Windows-Laufzeitpaket

**Files:** Create `windows/bridge/pyproject.toml`, `windows/bridge/requirements-build.in`, `windows/bridge/requirements-build.lock`, `windows/bridge/requirements-runtime.lock`, `windows/bridge/src/dispread_bridge_app/__init__.py`, `windows/bridge/src/dispread_bridge_app/probe_main.py`, `windows/bridge/packaging/bridge.spec`, `windows/bridge/build.ps1`, `windows/bridge/tests/test_packaging.py`; modify `docs/dependencies.md` and `.gitignore` ausschließlich für eigene Windows-Buildartefakte.

**Interfaces:** `probe_main.main(argv: list[str] | None = None) -> int`; `--self-test` gibt ein JSON-Objekt mit `runtime_version`, `qt_platform`, `bridge_import_ok`, `system_python_used` aus, danach Exit. `build.ps1 -SelfTest` produziert Ordnerpaket plus `build-manifest.json` mit Quellcommit/Hashes/Versionen. Kein Produkt-GUI-Entwurf in dieser Probe.

- [ ] N1.1 Windows-Test `test_frozen_probe_without_system_python`: auf sauberer VM Paket kopieren, `PATH` ohne Python, Probe ausführen; Exit 0, `bridge_import_ok=True`, `system_python_used=False`. Python-3.7-VM unverändert ebenfalls bestehen. Noch fehlendes Artefakt muss RED ergeben.
- [ ] N1.2 Importtest gegen `dispread.gsv_bridge` und verborgene QApplication schreiben; Qt-Windows-Plugin muss aus Paket kommen, keine Kamera-/PAM-/cv2-/numpy-Imports. Beispielassertion: `assert not ({'cv2','numpy','PAM'} & set(loaded_modules))`.
- [x] N1.3 Buildskript in bestehender Projektstruktur anlegen: Windows-Architektur und Build-Python >=3.13 vorab prüfen, isolierte Build-venv verwenden, nur Windows-/leichte Brückenmodule bündeln. Auf Pi keine Windows-EXE erzeugen. Getestete konkrete Abhängigkeitsstände erst nach erfolgreichem Probe-Build mit Hashes sperren; keine ungetestete Qt/Python-Kombination festschreiben.
- [x] N1.4 `test_build_rejects_unverified_download` und `test_build_reports_missing_runtime` ergänzen; vollständiges Release-Artefakt erst nach Manifest-/Hashprüfung umbenennen, fehlgeschlagener Build überschreibt kein letztes gutes Paket.
- [ ] N1.5 Windows: `./.build-venv/Scripts/python.exe -m pytest -q windows/bridge/tests/test_packaging.py`; Paket auf zwei VM-Zuständen aus N1.1 testen. Tatsächliche Befehle/Versionen und Ergebnis in `docs/VALIDATION.md`/Laborjournal, Buildrezept in `windows/bridge/README.md` sichern.
- [ ] N1.6 Eigene Dateien, Abhängigkeitsdoku und CHANGELOG committen. Gate N1 nur mit echten Windows-Ergebnissen grün; fehlender Windows-Host ist dokumentierte Voraussetzung, kein PASS.

### N2: VCOM-/USB-Adapter und Installationsnachweis

**Files:** Create `windows/bridge/src/dispread_bridge_app/types.py`, `windows/bridge/src/dispread_bridge_app/devices.py`, `windows/bridge/src/dispread_bridge_app/vcom.py`, `windows/bridge/tests/test_devices.py`, `windows/bridge/tests/test_vcom.py`, `windows/bridge/probes/check_vcom.ps1`, `docs/quellen/windows-bridge-vcom-2026-11-06.md`; modify Windows-Lockdateien nur wenn Adapter weitere Abhängigkeiten braucht.

**Interfaces:** `DeviceInfo(instance_id: str, port: str | None, vid: int | None, pid: int | None, serial: str | None, location: str | None, pnp_error: int | None)`; `WindowsDevices.inventory() -> tuple[DeviceInfo, ...]` über injizierbare PnP-/Portabfrage. `VcomAdapter.inventory() -> tuple[PortPair, ...]`, `ensure_pair(existing: PortPair | None) -> InstallResult`, `probe_pair(pair: PortPair) -> bool`. Windows-Typen in `dispread_bridge_app.types`: `PortPair(pair_id: str, bridge_port: str, gsv_port: str, owned: bool)`, `InstallResult(state: str, reboot_required: bool, pair: PortPair | None, error_code: str | None)`. N2 produziert diese Typen auch für W1/W3; sie gehören nicht in den Pi-Vertrag.

- [x] N2.1 Reine Tests mit Fake-PnP: `test_usb_without_driver_is_not_absent` (VID0403/PID6001, port=None, PnP-Fehler), `test_renumbered_usb_keeps_serial_identity` (COM6→COM9), `test_duplicate_vid_pid_needs_selection` (keine willkürliche Wahl). RED unter `pytest -q windows/bridge/tests/test_devices.py` prüfen.
- [x] N2.2 Adapter über Windows-PnP und pySerial aufbauen; Portnummer nicht als Identität behandeln. Alle systemändernden Operationen über kleine injizierbare Kommandoausführung, keine Shell-Interpolation fremder Pfade/Portnamen.
- [x] N2.3 `test_existing_busy_pair_is_not_changed`, `test_uac_denied_is_resumable`, `test_installer_exit_zero_with_pnp_error_is_failure` und `test_repair_creates_no_duplicate_pair` schreiben; Resultat muss jeweils erklärten Zustand liefern und fremde Änderungen ausschließen.
- [ ] N2.4 Ersten com0com-Kandidaten mit Paket-/Treiberhash festhalten, Installation mit erteilten Windows-Rechten durchführen, PnP und beide Übertragungsrichtungen prüfen. Vor Probe GSVmulti-Verbindung schließen und Handles danach freigeben. Aktive Schutzfunktionen und Reboot testen, keine Fremdtreiber löschen.
- [ ] N2.5 `./.build-venv/Scripts/python.exe -m pytest -q windows/bridge/tests/test_devices.py windows/bridge/tests/test_vcom.py`; reale Protokolle und konkrete Weitergabe-/Signierungsfreigabe dokumentieren. Bei Code52/HVCI-Block oder ungeklärter Verteilung Gate offen lassen; Alternative erfordert Entscheidung.
- [ ] N2.6 Adapter, Probe, Nachweis und CHANGELOG committen. Die Eignung eines einzelnen Rechners nicht als allgemeine Windows-Abnahme beschreiben.

### N3: Belegte GSVmulti-Sessionvorlage

**Files:** Create `windows/bridge/src/dispread_bridge_app/session_templates.py`, `windows/bridge/tests/test_session_templates.py`, `windows/bridge/probes/inspect_session.py`, `tests/fixtures/gsvmulti/session-templates/README.md`, darunter tatsächlich gewonnene, bereinigte Vorlagen und `manifest.json`; modify `docs/open-questions.md` nur nach neuem Beleg für OQ-53, `docs/VALIDATION.md`, `docs/lab_journal.md`.

**Interfaces:** `TemplateEvidence(template_id: str, gsv_version: str | None, source_sha256: str, allowed_fields: tuple[str, ...], roundtrip_verified: bool)`; `inspect_template(path: Path) -> TemplateEvidence`. Unterstützt wird erst die genau belegte GSVmulti-2.03-Pro-Dateiversion. Kein universeller UCF-Parser vor Nachweis.

- [ ] N3.1 In GSVmulti neue Testsession speichern. Port, Einheit/Skalierung, Rate, Präfix und Zahlenfilter jeweils einzeln ändern, Datei speichern, neu öffnen, UI-Werte und Originalbytes paarweise sichern. Zusätzlich eine originale Text-Aufzeichnung des kontrollierten Demos sichern, Feld-/Zahlen-/Einheitsformat für den späteren Empfangsprüfer belegen. Private Pfade bereinigen, Originale/Hashbelege getrennt aufbewahren. OQ-53 nicht aus nur einer Byteabweichung schließen.
- [ ] N3.2 Erst aus diesen Dateien `test_template_manifest_matches_original_hash`, `test_unknown_gsv_version_is_unsupported` und `test_roundtrip_filter_unit_scale_and_port` ableiten. Letzterer prüft belegte Feldwerte plus echten Roundtrip-Nachweis, nicht nur selbst erzeugtes XML gegen denselben Parser.
- [x] N3.3 Minimale Inspektion und Manifestvalidierung implementieren. Nicht nachgewiesene Felder werden nicht als `allowed_fields` ausgegeben; `roundtrip_verified=False` blockiert automatischen Export. Format/Endung richten sich nach echten Dateien.
- [ ] N3.4 `./.build-venv/Scripts/python.exe -m pytest -q windows/bridge/tests/test_session_templates.py`; neue Session nach kontrolliertem Portwechsel in GSVmulti öffnen und separaten Demoempfang in Originaldatei prüfen. Vorherige Nutzersession unverändert lassen.
- [ ] N3.5 Gate N3 nur nach vollständiger Feld-/Empfangsprüfung bestehen. Fehlende Dateispezifikation als konkreten Blocker ausweisen; keine Ersatzdatei als erfolgreiche Sessionerzeugung ausgeben. Fixtures, Quellen, Doku und CHANGELOG committen.
