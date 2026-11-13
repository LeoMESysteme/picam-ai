# Kleine Backend-Punkte — Bericht 2026-11-13

Auftrag: [Handoff, Aufgaben 1–4](../../superpowers/handoffs/2026-11-13-codex-kleine-backend.md).
Worktree `kleine-backend`, Branch `fix/kleine-backend`; Ausgangszustand sauber.
**Nicht committet.** Kein Hardwarezugriff, kein Deployment, keine Änderung an
`var/`, laufendem Werkbank-Dienst oder anderen Worktrees. Keine Abhängigkeit neu
installiert. Für den Doku-Build nur lokalen, ignorierten Symlink
`.venv-docs -> ../../.venv-docs` ergänzt (vorhandene Umgebung mitbenutzt).

## Aufgabe 1 — Zähler bei Abbruch

**Dateien:** `src/dispread/gsv_bridge.py`,
`windows/bridge/src/dispread_bridge_app/worker.py`,
`windows/bridge/tests/test_worker.py`.

**Befund:** COM-Schreiben und dauerhafter Journalbeleg entstehen vor dem ACK.
`_DataLink.send(ack)` wartet auch auf die Pi-Antwort. Erst danach meldete der
Worker `written` an den Controller. Nimmt der Pi die Quittung an, aber die Antwort
geht verloren, fehlt der letzte bereits geschriebene Wert im App-Zähler.
Dieser reproduzierte Mechanismus erklärt 123 gegen 124; den konkreten historischen
Ablauf beweist er ohne damaligen vollständigen Mitschnitt nicht.

**Fix:** Callback `on_written` nach dauerhaftem COM-Beleg und vor dem ACK-Austausch.
Der Worker veröffentlicht daraus die bestehende Meldung; der spätere Austausch
zählt nicht erneut. Re-ACKs lösen keine weitere Meldung aus. Gilt auch für
empfangene Vierkanaltakte; Füllzeilen behalten ihre eigenen Statistiken. Pi-Zählung unverändert.

**Tests:** Zwei Abbruchvarianten (ACK angekommen/verloren): Journal `written`,
genau eine COM-Zeile, App-Zähler 1. Vor Fix beide rot (Zähler 0). Re-ACK in gleicher
und neuer Session zählt nicht doppelt. Worker/Controller zunächst 91 grün;
finaler gemeinsamer Prüfstand unten. Pi-Dateien gezielt: 90 grün, vier Socket-Sperren.

**Grenze/Textwunsch:** „An den COM-Treiber weitergegeben: n Werte“;
„Kein Empfangsnachweis von GSVmulti“. Bei verlorenem ACK-Hinweg können App und Pi
weiterhin abweichen: lokale COM-Belege versus eingegangene Quittungen.

## Aufgabe 2 — Diagnoseexport

**Dateien:** `delivery_journal.py`, `app_controller.py` unter
`windows/bridge/src/dispread_bridge_app/`; zugehörige `test_delivery_journal.py`
und `test_app_controller.py`.

- Jede neue Zeile: `app_start` (zufällige 32-stellige Hexkennung einmal je Prozess),
  `route` und verfügbare `port`, `bridge_port`, `gsv_port`. Kontext beim Einreihen,
  vorhandene Schreibsummen je Weg/Portpaar getrennt. Spätere Wechsel verfälschen ihn nicht.
- `ts`: Unix-Zeit des Diagnose-Schreibens. `ts_time_base: unix_realtime` gilt auch
  für `first_ts`/`last_ts`; vorhandene monotone `t_ns` behalten ihre Zeitbasis.
  Keine Latenzbehauptung daraus.
- ZIP: `summary.json`, `details.jsonl` (aktueller Start), `details-previous.jsonl`
  (ältere und Legacy-Starts). Beide Detaildateien bleiben jeweils im Bytebudget.
  Gemeinsame Original-Aufbewahrung weiterhin höchstens 64 MiB / sieben Tage.
  Vollständig heißt alle **noch aufbewahrten** Ereignisse, mit vorhandenen
  Schreibsummen und neuer Leerlaufverdichtung; kein unbegrenzter Langzeitstart.
- Gleicher unmittelbar aufeinanderfolgender Leerlauf wird **beim Export** mit
  `count`, `first_ts`, `last_ts` verdichtet. Originalzeilen bleiben auf Platte.
  Fehler, Zustandswechsel, zusätzliche Fehler-/Zustandsfelder, anderer Weg/Port/
  Start und zwischenliegende Ereignisse unterbrechen die Verdichtung.
- Strikte Freigabe `COM1` bis `COM9999`: keine Nutzerdaten, Pfade oder Beschreibungen.
  USB ausschließlich vierstellige VID:PID; keine Seriennummer, PnP-ID, Zugangsdaten
  oder Lauf-ID. Auch Altbestände werden beim Export erneut redigiert.

**Entscheidung:** Exportverdichtung erhält die Originalbelege und braucht keinen
dauerhaften Aggregat-Zwischenzustand. Alternativen in `docs/project_history.md`.

**Tests:** Starttrennung, mehrere Stores desselben Prozesses, tatsächlicher ZIP-
Inhalt, historischer Kontext trotz asynchronem Schreiben, Secret-Redigierung,
Portgrammatik, Legacy, Größenbegrenzung und Verdichtungsgrenzen. Controller/Journal
nach diesen Änderungen 71 grün; finaler Prüfstand unten.

**Grenzen/Textwunsch:** Vor Wegauswahl und bei alten Zeilen ohne Weg `route: null`;
Legacy ohne Kennung `app_start: null`. Nichts wird geraten. Textwunsch:
„Aktueller App-Start: details.jsonl; frühere Starts: details-previous.jsonl.
Details werden höchstens sieben Tage / 64 MiB aufbewahrt.“

## Aufgabe 3 — Adapter und Ports

**Dateien:** `app_controller.py`, `connection.py`, `port_inventory.py`,
`delivery_journal.py`; Tests `test_app_controller.py`, `test_connection.py`.

**Änderung:** Auswahl/Wechsel von USB-Adaptern und Portpaaren sowie Verschwinden/
Wiederkehren werden erfasst. Die bestehende zweisekündige Inventur prüft auch
gewählte virtuelle Ports. Unbekanntes Inventar gilt nicht als Abziehen;
gleichbleibende Präsenz erzeugt keine Wiederholungsmeldungen. VID:PID ohne private
Beschreibungen; beim Abziehen bleibt die zuletzt bekannte VID:PID des Adapters
erhalten. `adapter_opening` meldet den tatsächlich zum Öffnen ausgewählten Port,
auch nach COM-Umnummerierung während Wiederverbindung.

**Reviewkorrektur:** Verspätete Geräteabfrage konnte eine neue Auswahl überschreiben.
Verbindung prüft Abbruch/Generation nach der Abfrage; Controller bindet Portmeldungen
zusätzlich an die Auswahl-/Verbindungs-Epoche. Regression: COM6-Abfrage blockiert,
COM9 neu gewählt, alte Abfrage plus verspätete Meldung kehren zurück; COM9 bleibt.
Vor Fix rot, danach grün.

**Tests:** Auswahl → Wechsel → zweimal abwesend → Rückkehr für beide UART-Wege;
virtuelle Ports; Redigierung; ConnectionManager-Wiederverbindung COM6 → COM9;
verspätete Abfrage. Final Controller/Verbindung/Journal/Worker: **164 bestanden**.

**Ereigniscodes / Textwünsche für Claude (keine UI-Texte geändert):**

| Code | Textwunsch |
| --- | --- |
| `adapter_selected` | Adapter ausgewählt: {port} |
| `adapter_changed` | Adapter gewechselt: {port} |
| `adapter_disappeared` | Adapter nicht mehr vorhanden: {port} |
| `adapter_returned` | Adapter wieder vorhanden: {port} |
| `adapter_opening` | Verbindung über Adapter: {port} |
| `port_pair_selected` | Portpaar ausgewählt: {bridge_port} → {gsv_port} |
| `port_pair_changed` | Portpaar gewechselt: {bridge_port} → {gsv_port} |
| `port_disappeared` | Port nicht mehr vorhanden: {port} |
| `port_returned` | Port wieder vorhanden: {port} |

**Grenze:** Präsenz ist eine Inventarbeobachtung. Sehr kurzes Abziehen zwischen
zwei Inventuren kann unerkannt bleiben; kein elektrischer Nachweis.

## Aufgabe 4 — Drei UART-Timeouts beim Anmelden

**Datei:** `windows/bridge/tests/test_transports.py`. Kein Produktionsfix am
Transport/Listener, kein Rahmenformat geändert.

`test_uart_startup_hypotheses_against_listener_without_hardware` verbindet echten
`SerialTransport` über Byte-Attrappe mit Challenge/Auth des echten `UartListener`.
App-Zeit simuliert, keine Last-abhängige Schlafdauer.

| Szenario | Ergebnis |
| --- | --- |
| sauberer Start | Anmeldung erfolgreich |
| alte Pi-Sitzung/Lease | neue Challenge löst alte Lease; Anmeldung erfolgreich |
| Listener nimmt noch keine Bytes an | `uart_timeout` nach simulierten 2 s |
| Adapter nimmt Schreibauftrag an, sendet noch keine Bytes | `uart_timeout` nach simulierten 2 s |
| unvollständige alte Zeile im Pi-Eingang | erste Challenge verworfen, `uart_timeout` |
| unvollständige alte Zeile im App-Eingang | `uart_frame_invalid`, kein Timeout |

**Tests:** **6 bestanden**. Nach Wegfall der simulierten Störung gelingt die nächste
Anmeldung. Das charakterisiert mögliche Ursachen, erklärt aber nicht die Zahl
drei am 13.11. Pauschales Pufferleeren oder Warten wäre ein unbelegter Fix.

**Messauftrag:** [OQ-77](../../open-questions.md#oq-77), neu erfasst, Index erzeugt.
Beim nächsten autorisierten Aufbauversuch Portöffnung, `listening`, Challenge/
Proof je Sender und Empfänger und Auth-Abschluss erfassen: lokale monotone Zeit
samt Prozesskennung plus UTC, unbekannte Unsicherheit `None`. Nur Ereignisarten
und Bytezahlen, keine Rohtelegramme oder Zugangsdaten. Kernel-Fehlerzähler vorher/
nachher. Frisch vorbereiteter Listener gegen Wiederanmeldung nach Abbruch;
falls nötig Sendebeginn elektrisch messen. **Hardwareursache bleibt offen.**

## Prüfung und Übergabe

Vorgeschriebene Umgebungen und Befehle:

```sh
# cwd windows/bridge, ohne xdist
QT_QPA_PLATFORM=offscreen PYTHONPATH=src:../../src /mnt/ssd/picam-dev/qt-venv/bin/python -m pytest -q -p no:cacheprovider tests
# cwd Worktree
PYTHONPATH=src ./.venv/bin/pytest -q tests/test_gsv_bridge.py tests/test_bridge_output_state.py tests/test_bridge_uart.py
PYTHONPATH=src ./.venv/bin/ruff check src tests windows/bridge/src windows/bridge/tests
./scripts/docs-site.sh build -s
npx --no-install playwright test -c playwright.docs.config.ts
```

- **Gezielte Windows-Suite:** 164 bestanden (Controller, Verbindung, Journal, Worker).
- **UART-Hypothesen:** 6 bestanden.
- **Pi gezielt:** 90 bestanden, vier Sandbox-`EPERM`-Fehler:
  `test_socket_framing_preserves_first_complete_reply`,
  `test_actual_socket_publisher_preserves_invalid_barrier_before_valid`,
  `test_actual_socket_lost_ack_does_not_replay_on_reconnect`,
  `test_publisher_demo_subprocess_reaches_bridge_with_exact_finite_count`.
  Erster Test einzeln wiederholt: erneut `EPERM`. Ohne diese vier:
  **90 bestanden, 4 abgewählt**. Keine Last-Wackler, Tests nicht abgeschwächt.
- **Ruff / Diff-Whitespace:** sauber. **OQ-Index:** erzeugt.
  **Tour-Fakten / Wiki-Prüfung:** sauber; keine dargestellten Szenen/Werte geändert.
- **Doku-Build streng:** erfolgreich, „No issues found“; nach Bericht/Status nochmals
  erfolgreich (7,27 s; erster Build 35,71 s).
- **Doku-Playwright:** kein Test gestartet, HTTP-Server scheitert an Sandbox-
  `PermissionError: [Errno 1] Operation not permitted`; vor Merge nachholen.
- **Unabhängiges Review:** ein wichtiger Befund (verspätete Geräteabfrage), durch
  rot/grün belegten Regressionstest behoben. Keine kritischen Befunde. Hardware-
  UART-Ursache, Windows-Treiber und GSVmulti-Empfang nicht beurteilt.
- **Volle Windows-Suite:** **655 bestanden, 4 übersprungen, 13 fehlgeschlagen**
  in 310,18 s. Lauf vor dem zusätzlichen Review-Regressionstest. Zwölf Fehler
  beim lokalen HTTP-/TLS-Testserver (`could not bind on any address`), ein weiterer
  beim Aiohttp-Versionsschutz (`network_unavailable` statt `components_unsupported`).
  Wiederholung dieses Tests mit `PYTHONASYNCIODEBUG=1` belegt die Sandbox-Ursache:
  Asyncio kann sein Self-Pipe-Socket nicht beschreiben (`EPERM`), daher erreicht
  der Coroutine-Aufruf den Versionsschutz nicht. Ebenfalls wiederholt: erster
  Controller-Integrationstest, unverändert Bind-Fehler. **Keine Last-Wackler**.
- **Breiter Abschlusslauf nach Review:** **656 bestanden, 4 übersprungen,
  13 abgewählt**, 204,28 s. Die oben einzeln benannten Sandbox-Fälle wurden per
  `-k` ausgeschlossen; kein Test verändert/übersprungen markiert, um Grün zu erzeugen.
  Nach der letzten kleinen Initialisierungsanpassung (Diagnosethread erst nach
  Initialisierung von Weg/Portdaten starten) zusätzlich Controllerdatei:
  **39 bestanden**, 3,85 s. Keine beobachteten Last-Wackler.

Die 13 Fehler der vollständigen Windows-Suite, vor Merge außerhalb der
Socket-Sperre erneut auszuführen:

| Datei | Test | Fälle |
| --- | --- | ---: |
| `test_app_controller_integration.py` | `test_demo_of_ten_values_reaches_fake_com_and_ui_says_demo_only` | 1 |
| dieselbe | `test_dut_block_from_pi_shows_lock_and_writes_nothing` | 1 |
| dieselbe | `test_exit_stops_worker_and_releases_connection` | 1 |
| `test_transports.py` | `test_real_wss_pairs_and_exchanges_against_reviewed_hub` | 1 |
| dieselbe | `test_actual_tls_peer_pin_is_checked_before_authorization_headers` | 1 |
| dieselbe | `test_real_wss_redirect_never_follows_configured_path` | 1 |
| dieselbe | `test_real_wss_refuses_expired_or_uart_scoped_offer` (`expired`, `wrong_transport`) | 2 |
| dieselbe | `test_unreviewed_aiohttp_version_fails_closed_before_connection` | 1 |
| dieselbe | `test_changed_certificate_same_pi_never_receives_saved_token_before_fresh_pairing` (`False`/`True` × `legacy`/`original_pin`) | 4 |

Temporäre Logs: `/tmp/kleine-backend-windows.log`,
`/tmp/kleine-backend-windows-final.log`, `/tmp/kleine-backend-windows-recheck.log`,
`/tmp/kleine-backend-asyncio-debug.log`, `/tmp/kleine-backend-docs-final.log`.

Keine Hardware-/Kalibriermessung: `VALIDATION.md`/`lab_journal.md` werden nicht mit
synthetischen Unit-Tests als Messbeleg gefüllt. Vier Changelog-Einträge,
strukturelle Entscheidungen, OQ-77 samt Index und überschriebener Sessionstatus
sind geliefert. Claude übernimmt Integration und UI-Texte.
