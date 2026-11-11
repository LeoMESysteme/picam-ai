# GSVmulti fester Takt mit Vierkanal-Telegramm – Umsetzungsplan

> **Für ausführende Agents:** Aufgabe für Aufgabe abarbeiten, jeweils mit TDD (RED zuerst). Fortschritt im Ledger `.superpowers/sdd/2026-11-11-gsvmulti-takt/progress.md`.

**Ziel:** Der Pi sendet pro Takt (1–10 Hz, Vorgabe 10) genau ein Telegramm `%wert;gültig;takt;zeit` an GSVmulti, über alle drei Wege. Ungültige Takte sind markiert, verlorene Takte werden auf Windows mit Fehlwertzeilen aufgefüllt.

**Spec:** [2026-11-11-gsvmulti-takt-vierkanal-design.md](../specs/2026-11-11-gsvmulti-takt-vierkanal-design.md), freigegeben am 2026-11-11 (F1–F5).

**Worktree:** `.worktrees/bruecke-ui`, Branch `feat/bruecke-ui`.
- Codex nur für Backend (B1, B2).
- Werkbank-UI an einen Claude-Subagenten (U1).
- Die UI der Windows-App gehört der Session picam-ai-65 (Branch `feat/bruecke-ux`); Anforderungen in W1.

## Globale Vorgaben (aus der Spec)

- **Format-ID** `gsvmulti_userdefined_4ch_v1`, `InvalidValuePolicy.MARK_RECORD`.
- **Fehlwert** genau `99999999.0`. Nie Exponent, `NaN` oder `Inf`, weder im Fehlwert noch in einem echten Wert.
- **Trennzeichen** `;`, **Präfix** `%`, **Zeilenende** `\r\n`.
- **Feldreihenfolge** Wert; gültig (1/0); Takt (ab 1); Zeit (Unix-s, `%.6f`).
- **Takt** am Pi aus der Monotonuhr, fester Raster, kein Aufholen. Gültig nur, wenn der jüngste VALID-Datensatz nach dem vorigen Takt erfasst wurde und jünger als `max_frame_age_ms` ist (F1).
- **Kein gültiger Wert zweimal.** Kein historisches Nachsenden von Werten. Auffüllen nur mit Fehlwertzeilen, höchstens 50 Takte (F2).
- **Baudrate** der Pi↔Windows-UART kommt ausschließlich aus `dispread.bridge.baud.UART_BAUD` (Branch `feat/bruecke-ux`, eed58fc). Keine eigene Konstante. Bis zum Merge bleibt `uart.py` unverändert.
- **Einkanal-Ausgabe** bleibt wählbar, mit Warnung (F3). Vorgabe wird der Vierkanal-Takt.
- **Unverändert** bleiben ValueRecord, Pi-Audit, Testfreigabe (Bestätigung pro Lauf) und die Regel, dass ein Testlauf keine externe Ausgabe erzeugt.

## Prüfschwerpunkte

1. **Jitter und Verspätung:** Ein Takt verpasst seinen Zeitpunkt (Pi unter Last). Erwartet: kein Doppeltakt, kein Aufholen; die Lücke ist in der Taktnummer sichtbar und wird auf Windows aufgefüllt.
2. **Lauf endet mitten im Takt:** Kein halbes Telegramm. Der letzte Takt ist vollständig oder fehlt.
3. **Testfreigabe ohne Haken:** Es geht kein einziger Takt an COM, auch keine Fehlwertzeile.
4. **Ein Wert sieht wie der Fehlwert aus** (`99999999.0` als echter Anzeigetext): Er wird abgelehnt (UNREADABLE) und nie als gültig gesendet.
5. **Uhrsprung der Pi-REALTIME während des Laufs** (NTP-Schritt): Der Zeitkanal nutzt den Versatz vom Laufstart weiter, und `session.json` vermerkt den Sprung.

---

### B1 (Codex): Formatter, Pi-Takt und Zeitkanal; Ausgabeweg „UART direkt“

**Dateien:**
- `src/dispread/sink/protocol/userdefined_4ch.py` (neu)
- `src/dispread/records.py` (`InvalidValuePolicy.MARK_RECORD`)
- `src/dispread/live/tick.py` (neu, Taktgeber)
- `src/dispread/live/output.py` (P4-3 `serial`: `format: '1ch'|'4ch'`, `rate_hz`)
- `src/dispread/live/session.py` (Zeitversatz REALTIME−MONOTONIC und NTP-Status bei Laufstart, Taktstatistik am Ende)

**Tests:**
- `tests/test_userdefined_4ch.py`
- `tests/test_live_tick.py`
- `tests/test_live_output.py`
- `tests/test_live_session.py`

**Schnittstellen:**
- `TickFormatter.format_tick(tick: Tick) -> bytes`
- `Tick(seq: int, valid: bool, value_text: str | None, time_unix_ns: int, frame_sequence: int | None)`
- `Ticker(rate_hz, clock_ns, max_frame_age_ns).on_record(record)` und `.due(now_ns) -> Tick | None`

Schritte:
1. **RED, Formatter:**
   - gültig → `%0.63956;1;7;1794397184.232361\r\n`
   - ungültig → `%99999999.0;0;8;…`
   - Anzeigetext mit Exponent oder `99999999.0` → ValueError bzw. Ablehnung
   - Ausgabe immer ASCII
2. **RED, Ticker:**
   - fester Raster, kein Aufholen nach Verspätung (verpasste Takte erhöhen `seq`, kein Doppelsenden)
   - F1: neuer Rahmen mit gleichem Wert ist gültig; ohne neuen Rahmen `gültig = 0`
   - Altersgrenze
   - Rate nur 1–10
3. **RED, `output.py`:** `format='4ch'` mit `rate_hz` sendet je Takt genau eine Zeile; `'1ch'` bleibt bytegleich wie heute (Bestandstests unverändert grün).
4. **RED, Zeitkanal:** Umrechnung über `records.to_boottime_ns` und den beim Laufstart gemessenen Versatz. `session.json` erhält `output.tick` (rate_hz, Versatz, NTP-Status, Anzahl gültig/ungültig/verpasst).
5. Umsetzen, gezielte Tests, ruff, CHANGELOG oben.

### B2 (Codex): Brücke mit Taktnachricht und Auffüllen auf Windows

**Dateien:**
- `src/dispread/bridge/{protocol.py, output_state.py, hub.py}`
- `src/dispread/gsv_bridge.py` (BridgeSession: Takt schreiben, Lücke auffüllen)
- `windows/bridge/src/dispread_bridge_app/{worker.py, readiness.py, delivery_journal.py}` (nur soweit nötig)
- `docs/BRIDGE_PROTOCOL_V2.md`

**Tests:**
- `tests/test_bridge_protocol.py`, `tests/test_bridge_output_state.py`, `tests/test_gsv_bridge.py`
- `tests/test_bridge_release_end_to_end.py` (pty und TLS, 10 Hz)
- Windows-Kerntests unter `windows/bridge/tests/`

**Schnittstellen:**
- v2-Nachricht `type: "tick"`, additiv, mit `run_id`, `seq`, `valid`, `value_text`, `time_unix_ns`, `frame_sequence`, `release`, etwa 150 Byte. Alte Clients sehen sie nie, weil der Pi `tick` nur nach Fähigkeit im Hello anbietet.
- Quittung wie heute: `written` / `failed` / `unconfirmed`.

Schritte:
1. **RED, Protokoll:** Strenges Schema für `tick`. `value_text` nur bei `valid`, Exponent, NaN und Inf werden abgelehnt.
2. **RED, Hub:**
   - Takte werden der Reihe nach angeboten, ohne latest-only-Verlust innerhalb von 50 Takten. Älter als 50 Takte gilt als verloren und wird in der Taktnummer sichtbar.
   - Ohne Testfreigabe wird kein Takt angeboten.
3. **RED, Windows:**
   - `seq` springt von n auf n+k → k−1 Fehlwertzeilen mit Nominalzeit, dann der Takt.
   - k−1 > 50 → keine Auffüllung, Status „gestört“.
   - Journal vor jedem COM-Schreiben.
4. **RED, E2E:** pty und TLS, 10 Hz über 10 min simuliert (Zeitraffer erlaubt), eingestreute ungültige Phasen.
   - Zeilenzahl = Taktzahl, Takt lückenlos.
   - Kein Wert doppelt.
   - Nur frische gültige Werte.
   - Latenz p50/p99 und verlorene Takte im Report.
5. Protokollanhang, CHANGELOG.

### U1 (Claude-Subagent): Werkbank /live

**Dateien:**
- `src/dispread/workbench/static/live/run/{output.js, start-popover.js}`
- Statusleiste und Inspektor
- `tests/live_ui_server.py`, `tests/live-ui.spec.ts`, `tests/live_*.test.mjs`

Schritte:
1. **Laufstart:** Ausgabeformat „Vierkanal-Takt (empfohlen)“ oder „Einkanal (nur gültige Werte)“. Bei Einkanal erscheint die F3-Warnung wörtlich aus der Spec.
2. **Takt:** Eingabe 1–10 Hz, Vorgabe 10, mit dem Hinweis „In GSVmulti dieselbe Frequenz einstellen“.
3. **Checkliste „In GSVmulti“:** Vierkanal-Vorlage, „Record Hidden Channels“ (Pflicht), Autoscale Y aus für 8_1.
4. **Im Lauf:** Takt, Anteil gültig, verpasste Takte.
5. Screenshots, Playwright.

### W1 (an picam-ai-65): Windows-App

- Vorlagenkatalog auf die Vierkanal-Vorlage umschalten. Das gibt picam-ai-65 erst frei, wenn B2 auf Linux grün ist **und** Leonhard zugestimmt hat.
- Einrichtung Schritt 4 mit Pflichtschritt „Record Hidden Channels“, Statusanzeige für Takt und Auffüllungen, F3-Warnung bei Einkanal.

### D1 (Controller): Doku und Abnahme

- `windows/bridge/TESTLAUF.md` F3 (Vierkanal-Lauf), `docs/GSVMULTI_PROTOCOL.md`, OQ-06/OQ-51 (Lösungsweg).
- Wiki-Abschnitt GSVmulti-Einrichtung mit „Record Hidden Channels“.
- Hardware-Nachweise 2 und 3 aus Spec §5, mit Leonhard.
