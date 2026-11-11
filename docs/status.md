# Status und Übergabe — 2026-11-11

Auftrag `.superpowers/sdd/2026-11-11-bruecke-ux2/codex-session-catalog.md`
im vorhandenen Worktree `bruecke-ux` (`feat/bruecke-ux`) umgesetzt. Alle
Änderungen bleiben uncommittet. Kein Merge, Push, Deployment, Hardwareeingriff
oder neue Abhängigkeit. Der parallel bearbeitete UI-Bereich wurde durch diesen
Auftrag nicht verändert; bestehende Änderungen in `app_controller.py` bleiben
neben den gezielten Exportanpassungen erhalten.

Der exportierbare Vorlagenkatalog steht zentral in `session_templates.py`:

- `bruecke-session-com8-20261106`: `Session-COM8.ucf`, `single_value`,
  `active`, ein Kanal, keiner ausgeblendet, kein Aufnahmehinweis erforderlich.
- `bruecke-session-4ch-hidden-20261111`: `versuch2b-session-hidden.ucf`,
  `gsvmulti_userdefined_4ch_v1`, `prepared`, vier Kanäle, drei ausgeblendet,
  „Record Hidden Channels“ erforderlich.

SHA-256 und Herkunft sind im Code gepinnt, die neue Paketdatei entspricht dem
Original und dessen `SHA256SUMS`. Kanalzahl, Sichtbarkeit und Baudrate werden
beim Laden aus der Datei gelesen. Alle Katalogvorlagen müssen dieselbe Baudrate
tragen (derzeit 115200). `ACTIVE_SESSION_TEMPLATE` wählt die reguläre Vorlage;
zusätzlich muss ihr Status `active` sein. Der öffentliche Export bietet keine
Vorlagenauswahl. Vorbereitete Vorlagen benötigen den Entwicklereinstieg mit
`allow_prepared=True`. Die Aktivierung bleibt eine geprüfte Codeänderung.

Portersetzung ändert ausschließlich `ComNr`/`Name` in jedem `[chN]` und
`UserDevice.ComNo`; die Kanalnummer im Namen kommt aus `Input`. Sonstige Bytes,
Zeilenenden und Reihenfolge bleiben erhalten. COM8 ist für beide Vorlagen
byte-identisch zum jeweiligen Beleg, COM4 ändert bei vier Kanälen genau neun
Zeilen. `SessionExport` trägt die abgeleiteten Kanal-/Aufnahmehinweise; Diagnose-
und Kontextlogik bleiben unverändert. Beide PyInstaller-Specs paketieren beide
Dateien; das bestehende setuptools-Muster erfasst sie ebenfalls. Erkannte
Archivoriginale bleiben vom exportierbaren Katalog getrennt.

Prüfstand:

- Angeforderte fünf Testdateien: **141 bestanden, ein natives Windows-Gate
  übersprungen**. Einschließlich separater Prozessprüfung der späteren
  Vierkanal-Aktivierung mit Export- und Kontextmetadaten.
- Ruff, `git diff --check`, OQ-Index, Tour-Fakten und Wiki-Check bestanden.
- Unabhängiges Review: keine kritischen, wichtigen oder kleinen Befunde.
- Gesamte Brücken-Suite: **589 bestanden, vier übersprungen, 14 fehlgeschlagen**.
  Dreizehn Fälle in `test_app_controller_integration.py` und `test_transports.py`
  benötigen Sockets, die die Sandbox verbietet (`PermissionError: [Errno 1]`);
  dazu gehört der Versionswächter, der schon `network_unavailable` erhält.
  Ein Unterprozessfall in `test_worker.py` findet das Brückenpaket ohne
  `PYTHONPATH` nicht; separat mit `PYTHONPATH=src:../../src` bestanden.
  Alle Fehlernamen und die vollständige Dateiliste stehen im Abschlussbericht
  `.superpowers/sdd/2026-11-11-bruecke-ux2/codex-session-catalog-abschluss.txt`.

Offen bleibt die Senderumstellung von Pi/Brücke auf das Vierkanalformat sowie
die anschließende Windows-/GSVmulti-Abnahme. `prepared` wird hier nicht aktiviert.
„Record Hidden Channels“ muss in GSVmulti selbst eingeschaltet werden; die UCF
kann diese Einstellung nicht speichern. Die vorherigen UX2-Backend- und
parallelen UI-Arbeiten bleiben eigenständige Aufträge; Details des ursprünglichen
Backend-Abschlusses stehen in
`.superpowers/sdd/2026-11-11-bruecke-ux2/codex-backend-abschluss.txt`.
## Auftrag

Nur B1 aus dem [Vierkanal-Taktplan](superpowers/plans/2026-11-11-gsvmulti-takt-vierkanal.md)
im Worktree `/home/me-systeme/picam-ai/.worktrees/bruecke-ui`, Branch
`feat/bruecke-ui`, Basis `08ac9b9cc818c013de10e6cee6579d372607d59e`.
Kein Commit; der Controller übernimmt Commit und Integration.

## Lieferstand

`gsvmulti_userdefined_4ch_v1`, `InvalidValuePolicy.MARK_RECORD`, `Tick`,
`Ticker` und `TickTimebase` umgesetzt. UART direkt nimmt `format: '4ch'`
mit `rate_hz` 1–10 (Vorgabe 10) an. Fester Monotonraster ohne Aufholen;
frische neue Bilder dürfen gültig gesendet werden, derselbe Rahmen nie
zweimal. Ungültige Takte tragen genau `99999999.0` und Gültigkeit 0.
Reservierter Fehlwert-Anzeigetext wird vor dem Audit UNREADABLE.

Zeitumrechnung über `records.to_boottime_ns`, geprüftes BOOTTIME-Paar und
geklammert gemessenen REALTIME−MONOTONIC-Startversatz. Der Versatz bleibt
im Lauf eingefroren; `session.json.output.tick` hält Taktursprung, Zähler,
NTP-Status und Uhrsprungerkennung fest. Absolute Zeitunsicherheit bleibt
`null`, Zeitsemantik wegen OQ-43 provisional. Keine Windows-Synchronität
behauptet. Bestätigung bleibt vor jedem Portzugriff Pflicht; Testläufe
bleiben ohne externe Ausgabe.

Alter Einkanalvertrag ohne `format` und explizites `format: '1ch'` behalten
die bisherigen Bytes. U1 muss `format: '4ch'` als neue Vorgabe senden.
Bestandstests unverändert; neue Tests nur in neuen Dateien bzw. angehängt.
Keine Hardware, Dienste oder Frontend-Dateien geändert.

## Prüfstand

TDD-RED/GREEN für Formatter, Ticker, UART-Sender, Sessionzeit und
Sentinel-Ablehnung; Prüfschwerpunkte 1–5 für B1 abgedeckt. Unabhängiges
statisches Review: keine Critical-, Important- oder Minor-Befunde.
`ruff check src tests` und `git diff --check` bestanden.

Erster vollständiger angeforderter Lauf: 687 bestanden, fünf vorhandene
API-Tests scheitern an `PermissionError: Operation not permitted` beim
Anlegen eines TCP-Sockets. Isoliert ohne Projektimport bestätigt: bereits
`socket.socket(AF_INET, SOCK_STREAM)` wird in dieser Sandbox verweigert.
Keine Tests abgeschwächt. Abschlusslauf auf endgültigem Codezustand:
**689 bestanden, dieselben fünf fehlgeschlagen**, 285,18 s. Betroffen in
`tests/test_live_api.py`:

- `test_preview_mjpg_parts_carry_hud_headers`
- `test_status_carries_csrf_and_notice`
- `test_setup_passes_cell_text_and_errors_become_409`
- `test_unknown_overlay_is_404`
- `test_run_start_forwards_output_configuration`

Breiterer Lauf mit `-n 2` abgebrochen; geordneter Gesamtlauf mit `-x`:
63 bestanden, erster Fehler
`tests/test_bridge_end_to_end.py::test_dut_stays_locked_after_successful_pairing`
wegen gesperrtem localhost-Bind. Keine vollständig grüne Suite behauptet;
Socket-Tests müssen außerhalb dieser Einschränkung erneut laufen. Vor einem
Merge bleiben außerdem die in AGENTS.md vorgeschriebenen Doku-Build-/Browserchecks
beim Controller; hier wurde kein Merge vorgenommen.

## Übergabe und offene Arbeit

B2 (kompakte Brückennachricht, Windows-Auffüllen und UART/TLS-E2E), U1/W1
(Oberflächen, F3-Warnung, Vorlagen/„Record Hidden Channels“) und echte
Hardware-/GSVmulti-Abnahme bleiben offen. Direkter UART füllt verlorene
Takte nicht auf; die Taktnummer zeigt Lücken.

Ausführlicher Bericht mit exakten U1-Feldern liegt im Worktree unter
`.superpowers/sdd/2026-11-11-gsvmulti-takt/b1-report.md`, Ledger daneben.
Die Sandbox erlaubt keinen Schreibzugriff auf den angeforderten Zielordner
`/home/me-systeme/picam-ai/.superpowers/sdd/2026-11-11-gsvmulti-takt/`;
der Controller muss beide Dateien dorthin übernehmen.
