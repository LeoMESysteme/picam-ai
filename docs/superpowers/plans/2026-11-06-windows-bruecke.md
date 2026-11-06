# Windows-Brücke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows-Anwendung mit eigener Laufzeit, Qt-Einrichtung, UART/Netzwerk, gekoppelter Pi-Verbindung und nachgewiesener GSVmulti-Sessionerzeugung liefern.

**Architecture:** Bestehenden Python-Brückenkern weiterverwenden, Windows-Abhängigkeiten getrennt paketieren. Pi-Dienst ergänzt Geräteidentität, Kopplung und WSS/UART-Protokoll v2; die Windows-GUI steuert einen unabhängig testbaren Kern. Nachweise vor GUI-Ausbau, keine Aufhebung der DUT-Sperre.

**Tech Stack:** Python >=3.13, PySide6/Qt, pySerial, aiohttp, etablierte Kryptografie, PyInstaller und Inno Setup; Windows 11 x64 zuerst.

**Spec:** [Freigegebene Spezifikation](../specs/2026-11-06-windows-bruecke-design.md), Nutzerfreigabe am 06.11.2026.

## Global Constraints

- Windows 11 x64 zuerst; gebündelte fest getestete Laufzeit, keine Änderung von System-Python/PATH/Visual Studio.
- Online-Downloads bei Einrichtung erlaubt; installierter UART-/LAN-Betrieb braucht kein Internet.
- Pi-Python ausschließlich Projekt-`.venv` mit `--system-site-packages`, Projektinstallation `--no-deps`; Windows-Abhängigkeiten getrennt.
- Keine Mittelung/Referenzkorrektur, keine Altwerte unmarkiert, unbekannte Eingaben ablehnen; DUT-Brückenwerte bleiben gesperrt.
- Provisional und Zeitbasen in jedem Runartefakt; SYNTHETIC ist kein Alters-/Latenznachweis; Unsicherheit unbekannt = None.
- Kurzlebiges Kopplungsangebot: 256 Bit, maximal fünf Minuten, einmalig; dauerhaft getrennte Pi- und Client-Identität.
- Konfiguration/Transport/Pi im Lauf nicht still wechseln; Audit vor Publish, begrenzte Puffer, Invalidierungsbarriere erhalten.
- UI deutsch, Tastatur/DPI; COM-ACK ist kein GSVmulti-Empfangsnachweis; keine Schutzfunktion abschalten.
- Jede Aufgabe mit src-/scripts-/systemd-Änderung schreibt CHANGELOG im selben Commit; neue Abhängigkeiten in dependencies.md und passenden Paket-/Installationsdateien.
- Vor letztem Commit jeder Ausführungssession status.md neu schreiben. Hardware sofort im Laborjournal und Diagnose, Messzahlen zusätzlich in VALIDATION.
- Bekannte fremde Änderungen im vorhandenen Worktree erhalten. Vor Ausführung aktuellen Stand prüfen und geeigneten isolierten Checkout wählen; kein Merge/master/Deploy aus diesem Plan automatisch.

## Review Focus

1. Übertragenes/veraltetes Profil oder SD-Klon: falschen Pi trotz gleicher Adresse/Name ablehnen (P2, P3).
2. Netzmodus und UART-Bereitschaft konkurrieren mit direkter UART-Ausgabe auf ttyAMA0: genau ein Besitzer, keine Referenzportöffnung (P4).
3. COM-Schreiben erfolgreich, ACK oder Prozess verloren: keine blinde Wiederholung; ungelöste Invalidierung bleibt wirksam (P1, W2).
4. Bestehendes Portpaar durch andere Anwendung genutzt oder UAC verweigert: keine fremden Ressourcen ändern, Installation fortsetzbar (N2, W3).
5. Nur Python 3.7, Proxy, volle Platte oder unbekannte GSVmulti-Version: konkrete Fehlermeldung, kein falsches Bereit/Empfang bestätigt (N1, N3, W1, W4).

## Ausführung in drei Teilplänen

| Reihenfolge | Teilplan | Eigenständig prüfbares Ergebnis |
| --- | --- | --- |
| A | [Machbarkeitsnachweise](2026-11-06-windows-bruecke-nachweise.md) | Windows-Paket ohne Python, VCOM-Adapter mit realem Installationsbeleg, belegte Sessionvorlage |
| B | [Pi und Protokoll](2026-11-06-windows-bruecke-pi.md) | Profil/Kopplung und gekoppelter Dienst mit simuliertem Client, ohne Qt |
| C | [Windows-Anwendung](2026-11-06-windows-bruecke-windows.md) | GUI/Installer auf dem nachgewiesenen Kern und echte Ende-zu-Ende-Abnahme |

A zuerst. B kann ohne echten VCOM-Treiber mit Fake-Clients geprüft werden;
C nutzt die Nachweise aus A und den Vertrag aus B. Kein größeres GUI-Paket,
solange N1–N3 nicht bestanden sind. Fehlt externer Windows-Zugang/Treiber-
oder Sessionnachweis, Ergebnis konkret als blockiert dokumentieren und nur
unabhängige Aufgaben fortsetzen. Keine unbelegte kostenlose/kommerzielle
Treiberalternative auswählen.

Vorhandene CI läuft auf Forgejo mit Label `picam-docs` auf dem Pi.
Windows-Prüfung zunächst über reproduzierbare lokale PowerShell-Befehle;
für CI später eigener Windows-Host-Runner mit Label `picam-windows-x64`.
Kein `windows-latest` auf dem Pi annehmen, kein neuer `.forgejo/workflows/`-
Ordner, der bestehende `.github/workflows/`-Jobs abschalten würde.

## Gemeinsame Schnittstellen und Dateien

Neue reine Brückenmodule unter `src/dispread/bridge/`; bestehende
`gsv_bridge.py`, `gsv_transport.py`, `records.py` und Formatter bleiben
kompatibel. Windows-Produktpaket unter `windows/bridge/`, Importname
`dispread_bridge_app`. Tests der reinen Komponenten unter `tests/`,
Windows-/Qt-Tests unter `windows/bridge/tests/`.

Gemeinsame Transportnamen im v2-Vertrag: `uart|network`. Bestehender
Live-Konfigurationswert `tcp` wird in der v2-Integration explizit auf
`network` abgebildet; kein zweites gleichzeitiges Backend. v1 bleibt
benannter Demo-/Entwicklungsweg. Bestehende Ausgabe `serial` bleibt die
getrennte, ausdrücklich bestätigte direkte UART-Ausgabe.

P1 definiert die gemeinsamen frozen Dataclasses `BridgeProfile`, `PeerHello`,
`BridgeEvent` unter `dispread.bridge.types`. Windows-Typen `PortPair` und
`InstallResult` entstehen in N2 unter `dispread_bridge_app.types`,
`SessionSettings`/`SessionExport` in W4 dort. Felder stehen in den
jeweiligen Produzentenaufgaben. GUI konsumiert nur diese Typen; keine
zweite Port-/Zustandslogik in Widgets. Schnittstellenänderung: erst alle
betroffenen Aufgaben und Tests mitziehen, dann Code ändern.

## Umsetzungsstand 06.11.2026

P1-Kern umgesetzt und geprüft. N1-Build-, N2-Geräte-/Portpaar- und
N3-Vorlagenprüfung als lokal testbare Grundlagen vorhanden. Deren echte
Windows-/Treiber-/GSVmulti-Gates bleiben offen; N3 blockiert den automatischen
Sessionexport. Weitere Backend-Aufgaben laufen im isolierten Arbeitszweig.
Dies ist keine fertige EXE oder Ende-zu-Ende-Abnahme.

## Endabnahme G1

**Files:** `tests/test_bridge_end_to_end.py`, `windows/bridge/tests/test_installed_e2e.py`, `docs/VALIDATION.md`, `docs/lab_journal.md`, `docs/status.md`, `TODO.md`, `CHANGELOG.md`, `docs/dependencies.md`.

**Interfaces:** Konsumiert `BridgeHub`, `ConnectionManager`, Sessiongenerator
und signiertes Release-Artefakt aus P4/W1/W3/W4. Keine neue Messfreigabe-API.

- [ ] G1.1 Regression zuerst: bestehenden `tests/test_gsv_bridge.py`, `test_gsv_transport.py`, `test_live_output.py`, `test_live_service.py`, `test_live_api.py` ohne neue Hardware laufen lassen; Bestand und Fehler festhalten.
- [ ] G1.2 Integrationstests schreiben: falsche Identität/zweiter Client, Demo-Invalidierung vor jüngstem VALID, Kanalabbruch, Schreibfehler und Neustart. `test_dut_stays_locked_after_successful_pairing` muss `COM payloads == []` und sichtbaren Release-Block prüfen.
- [ ] G1.3 RED/GREEN für neue Integration: `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_bridge_end_to_end.py`; keine grünen Mocks als Windows-Nachweis darstellen.
- [ ] G1.4 Signiertes Paket auf frischer Windows-11-x64-VM ohne Python installieren; UAC/Neustart/Reparatur/Deinstallation prüfen, mit Python-3.7- und Mehrversions-VM wiederholen. Hardwaretreiber nur auf dafür freigegebenen Zielsystemen.
- [ ] G1.5 Zwei Pi, UART und LAN sowie Tailscale getrennt mit festem synthetischem Stimulus prüfen; Original-GSVmulti-Dateien gegen Quell-/COM-Audit vergleichen. Abziehen, Prozessabbruch, Standby und neue Run-ID kontrolliert aufnehmen; unklare Übergaben dürfen nicht als exakt einmal behauptet werden.
- [ ] G1.6 30-minütige Brücken-Demoläufe je freigegebenem Weg, Versions-/Treiber-/Hashbelege und Daten-/Ungültig-/Ausfallprüfung dokumentieren. Reale DUT-Freigabe bleibt separates OQ-06/OQ-47-Verfahren; dieser Plan entsperrt sie nicht.
- [ ] G1.7 Ganze betroffene Unit-/Windows-Suite, Ruff für geänderte Python-Dateien, Workbench-Playwright nach UI-Integration, `./scripts/docs-site.sh build -s` und vor Merge die Docs-Playwright-Suite ausführen. Keine vorhandene flaky Prüfung still ignorieren.
- [ ] G1.8 Eigene Dateien gezielt committen, status.md überschreiben; abschließendes Review über den gesamten Änderungszweig. Veröffentlichung/Produktivinstallation und Merge benötigen eigene Nutzerfreigabe für das konkrete Artefakt.

## Selbstprüfung des Plans

Spec §§1–4: N1/N2/W3; §§5–7: P1/P2/P3/P4/W1;
§8: N2/P4/W1; §9: P1/P4/W2; §10: W4;
§11: N3/W4; §12: W2/W3/W4; §13: alle Gates und G1.
Fünf Review-Fokusfälle sind den genannten Regressionen zugeordnet.
Drei Teilpläne halten die prüfbaren Grenzen getrennt; konkrete Tools/
Protokolldetails sind Entwurfsentscheidungen innerhalb der freigegebenen Spec.
Ausführung durch Codex mit Subagents freigegeben; EXE-GUI und sichtbare
Workbench-Anbindung bleiben nach Nutzeranweisung Claude vorbehalten.
