# Installer P0a — Codex-Bericht, 2026-11-14

Auftrag: `docs/superpowers/handoffs/2026-11-14-codex-installer-p0.md`, Aufgaben 1–5.
Worktree: `installer-p0`, Branch `feat/installer-p0`. **Keine Commits erstellt.**
Die Änderungen liegen vollständig zur Prüfung im Arbeitsbaum.

## Rahmen und Ergebnis

Alle fünf Implementierungsaufgaben sind umgesetzt. Keine Ausführung von apt,
sudo, Installer oder Dienstskript gegen den echten Rechner; keine Kamera oder
UART geöffnet, kein Zugriff auf den laufenden Werkbank-Dienst. `var/`, die
verlinkten venvs und andere Worktrees wurden nicht schreibend benutzt.
Diensttests laufen in temporären Repo-Kopien mit Attrappen für systemd,
Journal, Linger, Live-Status und curl. Reale TLS-Testzertifikate entstehen nur
unter pytest-Temporärverzeichnissen. Keine Oberfläche geändert.

Die volle Python-Suite bleibt wie beauftragt bei Claude. Fünf vorhandene
Sockettests und die Doku-Browserprüfung unterliegen den unten dokumentierten
Umgebungsgrenzen. Installation auf einem zweiten Pi und reale Dienstabnahme
sind weiterhin erforderlich; Paketliste und Skripte sind keine solche Abnahme.

## Aufgabe 1 — Paketliste und Installer (L1)

Dateien: `packaging/apt-packages.txt`, `scripts/install-workbench.sh`,
`tests/test_install_workbench.py`, `docs/dependencies.md`, `README.md`.

- Ein kommentiertes Manifest deckt Drittmodule aus `src/` ab, einschließlich
  dynamischem `zeroconf`-Import. Ergänzt insbesondere NumPy, OpenCV, pySerial,
  V4L2-Werkzeuge sowie lokale Buildwerkzeuge und Dienstvoraussetzungen.
- Nur fehlende Pakete gehen an apt. Vorhandene venv/Editable-Installation
  werden erkannt; beim unveränderten zweiten Lauf entfallen apt, venv-Erzeugung
  und pip-Installation. Editable-Prüfung: Projektversion, Checkout-URL und
  vorhandener CLI-Einstieg. Ein anderer Checkout wird nicht als passend erkannt.
- `--system-site-packages`, `--no-deps`, zusätzlich `--no-build-isolation`;
  Setuptools/Wheel kommen aus Debian. Eine vorhandene venv ohne Systempakete
  wird nicht umgebaut. Python ≥ 3.13 bleibt Voraussetzung.
- Gruppen, UART0-Boot-Eintrag, serielle Konsole und Getty werden nur gelesen.
  Abweichungen nennen manuelle Befehle. Nicht lesbare Konsolen-Konfiguration
  wird als unbekannt gemeldet, nicht als erfolgreich geprüft. Der Boot-Eintrag
  ist keine Auswertung aller bedingten Raspberry-Pi-Konfigurationsabschnitte.
- Folgeschritte: Identität → expliziter TLS-Host → Dienst → Profilexport.
- Tesseract bleibt **optional**: `live` nutzt den Dot-Matrix-Leser; der alte
  Controller lädt `TesseractReader` erst bei Auswahl von `tesseract_cli`.
  Dafür werden bei Bedarf `tesseract-ocr` und `tesseract-ocr-eng` benötigt.
- `curl` ist die zusätzliche deklarierte Dienstprüf-Abhängigkeit. Es prüft
  `/live` nach Neustart, ohne Zugangsdaten und ohne Vertrauensprüfung.

Tests: **2 bestanden** (Manifest/Importabdeckung, `bash -n`). Der Installer
wurde auftragsgemäß ausschließlich statisch geprüft; kein behaupteter
Laufzeitnachweis der Idempotenz oder apt-Verfügbarkeit auf einem frischen Pi.

## Aufgabe 2 — Portable Produktskripte (L10)

Dateien: `scripts/camera-commissioning.sh`, `tests/test_product_script_paths.py`.

Das Kameraskript verwendet `<eigene Repo-Wurzel>/.venv/bin/python`, auch bei
Aufruf aus einem anderen Arbeitsverzeichnis. Diagnose-Ausgabepfade bleiben
unverändert. Der Wächter prüft automatisch alle Produktskripte und `src/` auf
Entwickler-Home und festes Benutzerkonto. Herstellerdomain `me-systeme.de`
ist ausdrücklich kein Benutzerkonto.

Begründete Ausnahmeliste (im Test selbst):

| Muster/Datei | Grund |
| --- | --- |
| `forgejo-*` | CI-Runner des Entwicklungsservers |
| `wiki-*`, `wiki_*` | Wiki-Wartung, Server und Session-Export |
| `repo-maintenance*` | Entwicklungs-Repository-Wartung |
| `picam-codex-*` | Codex-Runner und Auth-Synchronisierung |
| `docs-maintenance*` | Doku-Wartung auf Forgejo |
| `check-auth-protected.sh` | Entwicklungsserver-OAuth-Prüfung |
| `dotmatrix-grid-probe.py` | Historisches Offline-Rasterexperiment mit Agenten-Artefaktpfad; kein Produktskript |
| `src/dispread/workbench/static/login.html` | UI/Firmenname, vom Auftrag ausdrücklich ausgenommen |

Tests: neuer Pfadwächter **1 bestanden**; vorhandener Entwicklungsdatenwächter
**1 bestanden**. Kameradiagnose nur `bash -n`, kein Hardwarelauf.

## Aufgabe 3 — Gemeinsame Vorgaben (L7)

Neue Dateien: `src/dispread/hardware_ports.py`, `src/dispread/defaults.py`,
`tests/test_product_defaults.py`.
Verwender: `gsv_transport.py`, `bridge/uart.py`, `live/output.py`,
`sink/serial_out.py`, `gsv_bridge.py`, `live/__init__.py`, `workbench/cli.py`,
`scripts/gsv-publisher-demo.py`, `scripts/gsvmulti-demo-sender.py`.

| Vorgabe | Wert/Vertrag bleibt |
| --- | --- |
| `GSV_UART_PORT` | `/dev/ttyAMA0` |
| `DIRECT_UART_BAUD` | 115200, direkte UserDefined-/COM-Ausgabe |
| `WORKBENCH_DATA_DIR` | `var/workbench` |
| `LIVE_DATA_DIR` | `var/live`, alter Import aus `dispread.live` bleibt möglich |
| `TLS_DIR`, `TLS_CERT`, `TLS_KEY` | Aus Werkbankdaten abgeleitet, bisherige Namen |
| `BRIDGE_DIR` | `var/workbench/bridge` |
| `SERVE_PORT` | 8080 |

`bridge/baud.py` bleibt separat: `UART_BAUD`/`LEGACY_UART_BAUD` beschreiben
den Brückentransport, nicht den direkten Ausgang. Zahlen in Listen erlaubter
Baudraten sind keine zweiten Defaultdefinitionen. Die CLI-Pfade bleiben
CWD-relativ; kein Wechsel auf `paths.VAR` oder `/var/lib/dispread`.

Tests: **12 neue bestanden**. Die erste gemeinsame Regression ergab
**252 bestanden / 5 gescheitert** inklusive dieser 12 Tests; die fünf
Socketfälle wurden einzeln wiederholt und sind unten als Sandbox-Sperren
aufgeführt. Abschließende Regression siehe Prüfprotokoll.

## Aufgabe 4 — Benutzerdienst im Repo (L2)

Dateien: `scripts/werkbank-dienst.sh`, `tests/test_werkbank_dienst.py`,
`src/dispread/workbench/cli.py`, `docs/anleitung/10-kamera-livevorschau.md`.

- `start|stop|restart|status|logs`, Pflicht `--host`/`--port`, bestehender
  Unitname `dispread-werkbank-bruecke`, überschreibbar mit `--unit`.
- Repo-relative Defaults, explizites Arbeitsverzeichnis und Quellpfad;
  Daten, Socket, Identitätsverzeichnis und Endpunkt überschreibbar.
  URLs entstehen aus Host/Port, bei IPv6 mit Klammern. Pfade mit Leerzeichen
  sind in den Attrappentests abgedeckt.
- Eigenes Socketverzeichnis 0700. Symlink als direktes Socket-Elternverzeichnis
  oder fremder Eigentümer wird abgelehnt.
- `dispread live status --socket …` ist ergänzt. Aktive Messung, Einrichtung,
  Diagnosekopie oder unbekannter Status sperren Stop/Restart; `--force` warnt.
  Ein beendeter Lauf darf trotz erhaltenem `run`-Audit gestoppt werden.
- Stopfrist 20 Sekunden in systemd, äußere Befehlsfrist 30 Sekunden;
  Timeout führt zu `reset-failed` und Fehlercode, nicht zu blindem Neustart.
- Restart wartet standardmäßig 60 Sekunden auf `/live`; Login-Redirect zählt.
  Dies ist eine Erreichbarkeitsprobe, keine Kamera-/Mess-/TLS-Vertrauensabnahme.
- Linger wird nur geprüft und mit manuellem Befehl erklärt. Keine dauerhafte
  System-Unit/Boot-Autostart eingerichtet.

Tests: **22 Diensttests bestanden**, plus expliziter CLI-Sockettest in
`test_workbench_tls.py`. Bestehende CLI-Testattrappen deckten beim ersten Lauf
unnötige neue Keywordargumente auf; Socket-Umschaltung erfolgt jetzt nur bei
expliziter Option. Danach **30 gezielte CLI-Regressionstests bestanden**.

Die Stoppsperre ist eine Statusabfrage, keine atomare Sperre gegen einen
gleichzeitigen Browser-Laufstart. Während Wartung keinen neuen Lauf starten.
Das Skript wurde **nicht** gegen die echte Unit ausgeführt.

## Aufgabe 5 — Expliziter TLS-Host und Anzeige (L8)

Dateien: `src/dispread/workbench/cli.py`, `tests/test_workbench_tls.py`,
`docs/anleitung/10-kamera-livevorschau.md`.

Ohne gültigen expliziten Host keine Verzeichniserzeugung. Fehlender Host meldet
„Adresse angeben, unter der Windows den Pi erreicht“. `init-tls --show`
liest `cert.pem` im ausgewählten Verzeichnis und zeigt SANs,
`not_after_utc` (ISO mit UTC-Offset) und `time_basis: UTC` als JSON. Kein
privater Schlüssel nötig, keine Dateiveränderung. Bestehende Zertifikate
werden beim Erzeugen weiterhin nicht überschrieben; Laufzeit bleibt 365 Tage.

Tests: **8 bestanden** in `test_workbench_tls.py` (7 TLS-Fälle + CLI-Sockettest),
einschließlich echter OpenSSL-Erzeugung im Temp-Verzeichnis. Vor Umsetzung
waren sechs neue TLS-Erwartungen rot.

Wichtig für Claude/Leonhard: Der bereits vorhandene Brückendienst benutzt
`DeviceIdentity.tls_context()`, also das gepinnte Identitätszertifikat mit
Pi-URI-SAN. Das separate `init-tls`-Zertifikat wird bei `--bridge-directory`
nicht verwendet. P0a ändert diese Identität nicht und löst deshalb keine
Browser-Namenswarnung am Brückendienst. Anleitung benennt beide Wege.
Automatische Erneuerung/30-Tage-Warnung sind weiterhin spätere Arbeit.

## Frontend-Fundstellen für Claude (unverändert)

| Datei | Fundstelle |
| --- | --- |
| `src/dispread/workbench/static/live/run/output.js:7` | Liste erlaubter Baudraten |
| `src/dispread/workbench/static/live/run/output.js:8` | `DEFAULTS`: `/dev/ttyAMA0`, 115200, `%`, TCP-Port 5000 |
| `src/dispread/workbench/static/live/practice/scenario.js:409` | Ersatzkonfiguration `/dev/ttyAMA0`, 115200 |
| `src/dispread/workbench/static/login.html:3` | Titel/Firmenname „me-systeme“ |

Später Defaultwerte aus einem Backend-Vertrag an das Frontend liefern,
statt zwei Konfigurationsquellen zu pflegen. Port 8080 wurde in diesen
Frontenddateien nicht als weitere Vorgabe gefunden.

## L6 — Entscheidungsvorlage für Leonhard

Heute existieren drei Bezüge: CLI/Live mit `var/...` relativ zum CWD,
`paths.py` mit Repo-/Umgebungsvariablen sowie `/etc/dispread`, `/var/lib/dispread`,
`/run/dispread`; zusätzlich der CLI-Socket unter `/tmp/dispread-<uid>`.
P0a zentralisiert nur Werte. Der Dienst macht seinen CWD explizit und setzt
einen eigenen Socket unter der Repo-Wurzel; manuelle CLI-Aufrufe behalten ihren
bisherigen Pfadvertrag. Das sind noch keine migrierten Laufzeitpfade.

| Möglichkeit | Nutzen | Kosten/Risiko |
| --- | --- | --- |
| Repo-relativ, CWD für Dienst festsetzen (P0a) | Kleine Änderung, bestehende Aufrufe erhalten | Daten bleiben an Checkout gebunden; geteiltes `var` bei Worktrees bewusst handhaben |
| Ein konfigurierbarer Datenroot, über `paths.py`/Konfigurationsobjekt | Code und Daten trennbar, Updates/mehrere Instanzen klar | Explizite Migration und Vorrangregeln nötig |
| Feste Systempfade `/etc`, `/var/lib`, `/run` | Klassischer Systemdienstbetrieb | Installationsort, Besitzer, Rechte und Dienstart müssen zuerst entschieden werden |

Empfehlung für die nächste beschlossene Stufe: **ein konfigurierbarer Datenroot**,
aber erst nach Entscheidung über Installationsort und Benutzer-/Systemdienst.
Danach `paths.py` als Resolver mit dokumentierter Priorität (explizite
CLI-Option → Konfiguration → vereinbarter Default) einsetzen. Nicht einfach
die vorhandenen `paths.py`-Defaults übernehmen: Das verschiebt Bestandsdaten.

Vor einer Umstellung festlegen und testen:

1. Getrennte Wurzeln für Code, persistente Daten, Konfiguration und flüchtigen
   Socket; Bedeutung von relativen Konfigurationspfaden ausdrücklich definieren.
2. Einmaliger, überprüfbarer Transfer vorhandener Werkbank-/Live-Daten,
   Identität/Kopplungen, Zertifikate und Timing-Kalibrierung. Identität nicht
   automatisch neu provisionieren und keine Daten automatisch löschen.
3. Verhalten bei Worktrees, symlinktem `var`, anderem CWD, neuer Adresse,
   Windows-Importen und Rückwechsel auf die vorige Version.
4. Vorlagenlieferung (L4), Kalibrierungsübernahme (L5), TLS-Identitätsbezug und
   Datenaufbewahrung separat entscheiden; dies sind keine neuen P0a-Defaults.

## Prüfprotokoll und Grenzen

- Neue Tests + bestehender Pfadwächter + Tour-Fakten: **51 bestanden**.
  `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_werkbank_dienst.py tests/test_workbench_tls.py tests/test_product_defaults.py tests/test_install_workbench.py tests/test_product_script_paths.py tests/test_no_dev_data_in_src.py tests/test_tour_facts.py --tb=short`
- CLI-Regression: **30 bestanden, 265 abgewählt**.
  `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_live_api.py tests/test_workbench.py tests/test_bridge_identity.py -k 'cli or default_and_override or local_cli or serve_parser' --tb=short`
- Transport-/Ausgaberegression: **240 bestanden, genau 5 Socketfälle abgewählt**.
  Dateien: `test_gsv_transport.py`, `test_gsv_bridge.py`, `test_live_output.py`,
  `test_bridge_uart.py`, `test_gsvmulti_demo_sender.py`; ausgeführt mit
  `PYTHONPATH=src ./.venv/bin/pytest -q … --tb=short` und je einem
  `--deselect=<vollständige Node-ID>` für die unten aufgelisteten fünf Fälle.
- Serial-/Gate-Regression: **79 bestanden**.
  `PYTHONPATH=src ./.venv/bin/pytest -q tests/test_userdefined_formatter.py tests/test_gate_und_referenz.py --tb=short`
- Zusammen **400 bestandene Tests** in den vier abschließenden Gruppen,
  ohne doppelte Zählung früherer Rot-/Grün-/Wiederholungsläufe.
- Ruff für `src tests` sowie beide geänderten Python-Skripte: **sauber**.
- `bash -n` für Installer, Kameradiagnose und Dienstskript: **sauber**.
  `shellcheck` und `repowise` sind hier nicht im PATH verfügbar.
- `git diff --check`: **sauber**.
- `./scripts/docs-site.sh build -s`: **erfolgreich, „No issues found“**.
  OQ-Index, Tour-Fakten und Wiki-Prüfung laufen dabei mit.
- `CI=1 PATH="$PWD/.venv/bin:$PATH" npx --no-install playwright test -c playwright.docs.config.ts`:
  **vor dem ersten Browsertest blockiert**. Der konfigurierte lokale
  Python-HTTP-Server darf keinen Socket erzeugen (`PermissionError: [Errno 1]
  Operation not permitted`). Exit 1; keine Browserprüfung als bestanden
  gewertet. `CI=1` verhindert die Wiederverwendung eines womöglich parallel
  laufenden Doku-Servers; `--no-install` verhindert Paketinstallation.

Fünf Tests scheiterten beim Erzeugen lokaler Sockets mit
`PermissionError: [Errno 1] Operation not permitted`. Jeder wurde einzeln
wiederholt: jeweils identischer Fehler, **kein Lastwackler** und kein
beobachteter funktionaler Assertionfehler:

1. `tests/test_gsv_transport.py::test_tcp_actual_handshake_and_stop_release_port`
2. `tests/test_gsv_bridge.py::test_socket_framing_preserves_first_complete_reply`
3. `tests/test_gsv_bridge.py::test_actual_socket_publisher_preserves_invalid_barrier_before_valid`
4. `tests/test_gsv_bridge.py::test_actual_socket_lost_ack_does_not_replay_on_reconnect`
5. `tests/test_gsv_bridge.py::test_publisher_demo_subprocess_reaches_bridge_with_exact_finite_count`

Sie wurden nicht als grün gewertet; der abschließende ausführbare
Regressionslauf wählt genau diese fünf Fälle explizit ab. Außerhalb der Sandbox
vor Integration nachholen, ebenso Playwright. Es wurde keine
Berechtigungserweiterung beantragt. Keine nur unter Last beobachteten Wackler
in den abgeschlossenen ausführbaren Prüfgruppen; die längere Laufdauer unter
paralleler Rechnerlast wurde nicht als Produkt-Latenzmessung gewertet.

## Review, Dokumentation und bewusste Grenzen

Ein frischer Reviewer prüfte den gesamten Implementierungsstand statisch.
Keine Critical-/Important-Befunde; zwei als Minor gemeldete Hinweise wurden
wegen ihrer Wirkung auf Installationsdiagnose und Stoppschutz nachgeschärft:
unlesbare Boot-Konfiguration nicht als Konsolenfreiheit melden; aktive
Status-Testdaten vollständig machen und beendeten Lauf mit erhaltenem Audit
als erlaubten Fall ergänzen. Keine weiteren offenen Review-Befunde.

Fünf Einträge im obersten CHANGELOG-Abschnitt, README/Abhängigkeiten und
Betriebsanleitung aktualisiert. L1/L2/L7/L8/L10 im Spec als „P0a umgesetzt“
markiert, Umfang und verbleibende Grenzen erklärt. Strukturelle Entscheidungen
in `docs/project_history.md`. `docs/status.md` gemäß konkretem Handoff nur um
**eine Zeile** ergänzt. Keine Hardwaremessung; daher keine erfundenen Zahlen
in VALIDATION/Laborjournal. Keine OQs umklassifiziert, keine neue offene
Produktentscheidung außerhalb der bereits benannten L4/L5/L6 eingeführt.

Bewusste Festlegungen: konkreter Handoff begrenzt das größere Spec;
`config.toml` und Pfadmigration bleiben ausgenommen. Das historische Raster-
Experiment wird nicht zum Produktskript umgedeutet. Stoppschutz ist bei
unbekanntem Zustand konservativ. Brückenidentität wird nicht durch Browser-TLS
ersetzt. Diese Entscheidungen erhalten Bestandsverhalten; eine andere
Einstufung würde zusätzliche Migration, Kalibrierungs-/Identitätsprüfung oder
eine bewusste Lockerung der Stoppsperre erfordern.
