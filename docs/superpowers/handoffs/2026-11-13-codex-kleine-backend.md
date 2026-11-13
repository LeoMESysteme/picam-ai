# Handoff an Codex: kleine Backend-Punkte aus der Windows-Prüfung (2026-11-13)

**Auftraggeber:** Leonhard (bis Mittwoch 18.11. weg). **Vorbereitet von:** Claude im
autonomen Plan (`docs/superpowers/plans/2026-11-13-autonomer-arbeitsplan.md`, Punkt 3).
Codex arbeitet selbstständig, danach reviewt Claude.

## Rahmen

- **Worktree:** `/home/me-systeme/picam-ai/.worktrees/kleine-backend`, Branch `fix/kleine-backend`
  (von `feat/integration` c90f301). `.venv` und `var` sind Symlinks.
- **Tests:**
  - Windows-App (in `windows/bridge`):
    `QT_QPA_PLATFORM=offscreen PYTHONPATH=src:../../src /mnt/ssd/picam-dev/qt-venv/bin/python -m pytest -q -p no:cacheprovider tests`
    (ohne xdist, ca. 4 min)
  - Pi: `PYTHONPATH=src ./.venv/bin/pytest -q <gezielte Dateien>`
  - Lint: `PYTHONPATH=src ./.venv/bin/ruff check src tests windows/bridge/src windows/bridge/tests`
- **Nicht anfassen:**
  - den laufenden Werkbank-Dienst (`.worktrees/bruecke-run`)
  - Kamera und `/dev/ttyAMA0`
  - `var/` schreibend
  - andere Worktrees
- **UI-Texte:** Nur Backend. Wo ein neuer Text in der Oberfläche nötig wäre, nur den Code bzw.
  das Datenfeld liefern und den Wunschtext im Report nennen. UI macht Claude.
- **Commits:** Die Sandbox kann nicht committen. Änderungen im Worktree lassen und
  `REPORT-codex.md` im Worktree-Wurzelverzeichnis schreiben: je Aufgabe Dateien, was und
  warum, Tests mit Zahlen, offene Punkte.
- **Verbindlich:** `AGENTS.md` lesen (Doku-Pflicht: CHANGELOG-Eintrag je Aufgabe). Kein
  Erfinden von Protokollen. Zugangsdaten und Lauf-IDs bleiben im Diagnoseexport geschwärzt
  (`delivery_journal._PUBLIC_FIELDS`/`_PUBLIC_VALUES`).

## Hintergrund

- Prüfbericht: `docs/quellen/ux2-pruefung-2026-11-13/ux2-bericht.md` und das ZIP daneben
  (Exporte mit `details.jsonl`).
- TODO: Abschnitt „Befunde Smoketest 13.11.“ (`grep -n "Befunde Smoketest" TODO.md`).

## Aufgabe 1: Zähler im Empfangstest 123 statt 124

**Befund:** Beim Abbruch des UART-Empfangstests um 14:35 zeigte die App 123 geschriebene Werte,
das Pi-Audit 124 quittierte. Zu klären ist, ob die App einen Wert nicht zählt (z. B. den
letzten vor dem Abbruch), ob der Pi zu viel zählt oder ob beide Zahlen Verschiedenes meinen.

**Code:** `windows/bridge/src/dispread_bridge_app/app_controller.py` (`_written`, um Zeile
846–1090), Worker und `gsv_bridge.BridgeSession` (wo „geschrieben“ entsteht), Pi
`src/dispread/bridge/output_state.py` / `hub.py` (Demo-Quittung).

**Ziel:** Beide Seiten zählen dasselbe, oder die Anzeige sagt, was sie zählt. Dazu ein Test,
der einen Abbruch direkt nach einem geschriebenen Wert nachstellt.

## Aufgabe 2: `details.jsonl` brauchbar machen

**Befund:** Der Diagnoseexport (`delivery_journal.py`, `export()`) enthält seit 13.11. die Zeit
je Zeile. Es fehlen:

- der Port bzw. Weg je Zeile (welcher COM-Port, welches Portpaar, Netzwerk oder UART)
- eine Trennung nach App-Start: Der Export ist kumulativ über alle Starts, bis zu 64 MB und
  7 Tage. Leonhard braucht vor allem den aktuellen Start.
- eine Zusammenfassung des Leerlaufs: gleiche Ereignisse in Folge, z. B. Poll ohne Wert,
  blähen die Datei auf.

**Ziel:**

1. Jede Zeile trägt `route` (`network`/`uart`) und, wo vorhanden, den Port. Den Portnamen
   prüfen: Ist er nicht sensibel, kommt er auf die Freigabeliste.
2. Jede Zeile trägt eine `app_start`-Kennung (Zufalls-ID je Prozessstart, keine Nutzerdaten).
   Der Export hat zwei Teile: den aktuellen Start vollständig, ältere Starts in einer
   getrennten Datei im ZIP. Beides bleibt größenbegrenzt.
3. Aufeinanderfolgende gleichartige Leerlauf-Ereignisse werden zu einer Zeile mit `count`,
   `first_ts` und `last_ts` zusammengefasst. Beim Schreiben oder beim Export entscheiden,
   und die Wahl begründen. Fehler und Zustandswechsel werden **nie** zusammengefasst.

Tests in `windows/bridge/tests/test_delivery_journal.py`.

## Aufgabe 3: Adapterwechsel ins Journal

**Befund:** Wechselt der Bediener den USB-Seriell-Adapter oder verschwindet der Port
(abgezogen), steht davon nichts im Diagnoseexport. Bei der Fehlersuche am 13.11. war unklar,
welcher Adapter zu welchem Zeitpunkt aktiv war.

**Ziel:** Ein Journal-Ereignis bei Auswahl, Wechsel, Verschwinden und Wiederkehren des
Adapters bzw. Ports. Es enthält Weg, Port und, wenn verfügbar, die USB-VID:PID, aber keine
Seriennummer. Das Ereignis kommt auf die Freigabeliste. Test dazu.

## Aufgabe 4: dreimal `uart_timeout` beim Verbinden über UART

**Befund:** Beim Verbinden über „UART über Brücke“ meldet die App dreimal `uart_timeout` (je
2 s), bevor die Anmeldung klappt. Pi-Seite: `src/dispread/bridge/uart.py` (`UartListener`),
App-Seite: `windows/bridge/src/dispread_bridge_app/transports.py` (`SerialTransport`) und
`connection.py`.

**Mögliche Ursachen (prüfen, nicht raten):**

- Der Pi-Listener ist noch nicht `listening`, wenn die App die erste Anfrage sendet.
- Im Puffer liegen alte Bytes, z. B. von einer abgebrochenen Sitzung, und die erste Zeile
  ist deshalb Müll.
- Die App öffnet den Port und sendet, bevor der Adapter bereit ist.
- `uart_challenge` wird verworfen, weil der Pi noch eine alte Sitzung hält.

**Ziel:** Ursache mit einem Test nachstellen (Transport-Attrappe) und beheben, falls es ein
Fehler im Ablauf ist, z. B. Puffer beim Öffnen leeren oder auf `listening` warten. Lässt
sich die Ursache ohne Hardware nicht klären, im Report beschreiben, welche Messung am Aufbau
sie klärt. Keine Änderung am Rahmenformat; das ist ein eigener Spec-Entwurf
(`docs/superpowers/specs/2026-11-13-uart-pruefsumme-design.md`) und nicht Teil dieses
Auftrags.

## Abschluss

- Gezielte Tests grün, dazu die volle Windows-Suite und ruff.
- Pi-Tests nur für berührte Dateien. Die volle Pi-Suite läuft Claude.
- `REPORT-codex.md` mit dem Ergebnis je Aufgabe, Zahlen, offenen Punkten und den
  gewünschten UI-Texten.
