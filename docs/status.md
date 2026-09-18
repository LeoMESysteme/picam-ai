# Status — Stand 2026-09-18

Wird **überschrieben**, nicht angehängt. Verlauf und Messaufbauten stehen in
[project_history.md](project_history.md) und [lab_journal.md](lab_journal.md).
Die volle Entstehungsgeschichte dieser Sitzung (Task-für-Task, je mit
Implementierung → Review → ggf. Fix-Runde → Re-Review) steht im
`CHANGELOG.md`; dieser Abschnitt beschreibt nur den **aktuellen** Endzustand.

## Sofort zu wissen

Diese Sitzung hat
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md)
vollständig abgearbeitet, auf Branch `ocr-selbstkalibrierung`: alle 12 Tasks
sind jetzt erledigt oder geprüft-und-bewusst-gesperrt. Das Ergebnis ist ein
zusammenhängendes Selbstkalibrierungs-Feature-Set für die Workbench:
Clipaufnahme (`replay://`-Sessions), ein dreigeteiltes Benchmark-Werkzeug,
Rastergeometrie-Autofit aus einem einmal getippten Sollwert, begrenzte
Nachführung einer bestätigten Anzeige, und Anzeigepolarität (LED/LCD) im
Profil. Kein `Konzept.md`, keine `ValueRecord`-/Telegrammänderung — die
Nicht-Ziele des Plans wurden eingehalten.

**Task-Stand im Einzelnen:**

* **Tasks 1–9:** gebaut, getestet, reviewt — siehe CHANGELOG für die
  Einzelfunde. Nennenswert:
  - Task 1: `src/dispread/frames/replay_source.py`, `CLIP_SCHEMA_VERSION=1`.
  - Task 2: Clipaufnahme im Controller (`clip.start`/`clip.stop`), inkl. eines
    in der Fix-Runde behobenen Deadlocks in `_clip_stop()`.
  - Task 3: `src/dispread/benchmark.py` + `scripts/ocr-benchmark.py` —
    Baseline auf den sechs gelabelten realen Annotationen: **5 korrekt, 0
    falsch, 1 abgelehnt** (siehe [VALIDATION.md](VALIDATION.md)).
  - Task 4: `src/dispread/ocr/autofit.py`, `fit_layout` — Fund:
    `thickness_ratio`/`inset_ratio` sind für den aktuellen
    Punktabtast-Decoder strukturell wirkungslos (nie gelesen in
    `sevenseg.py`); zwei gleich gut punktende, unterschiedliche
    Parametersätze am realen Datensatz gefunden ([OQ-28](open-questions.md)).
  - Task 5: Autofit in der Workbench-UI verdrahtet, Einrichtung per
    getipptem Wert statt nur per Regler.
  - Task 6/7: `src/dispread/track.py`, `QuadTracker` — begrenzte
    ECC-Nachregistrierung eines bestätigten Quads, immer gegen die
    Bestätigungsreferenz, nie Frame-zu-Frame (Drift-Vermeidung); in
    `Controller.publish()`/`_read()` eingebunden, `tracking_lost` blockiert
    die Freigabe (`GateConfig.blocking_flags`).
  - Task 8: Nachführungsgüte sichtbar — `reading.track`-Zeile in der
    Einstelltabelle, dritte Overlay-Farbe im Livebild; Review fand und behob
    einen Absturz (`kind="text"` statt `"info"` ließ `dispread tui`
    crashen — siehe [OQ-32](open-questions.md) für die verbleibende Lücke).
  - Task 9: `DisplayLayout.polarity` (LED/LCD) — schließt OQ-13 Fall 2. Fall 1
    (Anzeige zeigt ausschließlich „8") bleibt offen, unverändertes,
    unabhängiges Problem. Self-Review fand zusätzlich, dass
    `saturated_fraction` auf dem für `dark_on_bright` umgekehrten Bild
    berechnet wurde und eine echte Reflexion verschluckte — behoben, eigener
    Commit.
* **Task 10:** war bereits erledigt — reiner Doku-Task, dessen Inhalt in den
  Eröffnungscommit dieses Plans eingeflossen war.
* **Task 11 (Messänderung am Decoder): bleibt gesperrt.** Direkt vor Task 12
  erneut gegen die realen Daten geprüft:
  `var/workbench/annotations/` hat 9 Einträge (`ground_truth_text` ∈
  {11,00 / 12,76 / 28,80} plus unlabeled), `var/workbench/clips/` hat **4
  reale, persistente Clips** (je 75 Frames, `device_id="RND Lab"`, Werte
  {0.000, 28,80}) — echte, zwischen Sitzungen aufgenommene Daten aus dem
  Tagesbetrieb der Workbench, keine Testartefakte (automatisierte
  Task-Implementierer dieses Plans arbeiteten ausschließlich mit pytests
  `tmp_path`). Kombiniert bleibt es bei **einer** Geräteinstanz. Die
  Sperrbedingungen aus dem Plan: Bedingung 1 (≥ 6 Geräteinstanzen/≥ 3
  Displaytypen) und Bedingung 2 (2 vorab gesperrte Instanzen) **nicht
  erfüllt**; Bedingung 3 (≥ 8 Werte inkl. Vorzeichenwerten und 0/8 an jeder
  Ziffernstelle) **nicht erfüllt** (~4 verschiedene Werte); Bedingung 4
  (Werkzeug für disjunkten Split) existiert, ist mit einer Instanz aber
  gegenstandslos; Bedingung 5 (Task 3's Baseline-Messung) **erfüllt**. Kein
  Code für Task 11 angefasst.
* **Task 12 (dieser Task):** Doku-Abschluss — `project_history.md`,
  `open-questions.md` (OQ-26–OQ-32), `ROADMAP.md`, `CLAUDE.md`, diese Datei.

**Neue Erkenntnis, wert es hier festzuhalten:** Die echte Clipaufnahme aus
Task 2 wird inzwischen tatsächlich im Laborbetrieb genutzt — die vier realen
Clips unter `var/workbench/clips/` sind der erste Beleg dafür, dass reale
Datensammlung für ROADMAP-P2 begonnen hat. Das Werkzeug-Problem ist damit
gelöst, das Diversitätsproblem (eine Geräteinstanz) nicht.

**Nebenbei, unabhängig von diesem Plan:** Ein `docs-cleanup`-Durchlauf auf
`master` prüfte die Projektdokumentation gegen den aktuellen Code und fand
**nichts Korrekturbedürftiges** — `master` blieb von der Arbeit an diesem
Plan unberührt (diese lief ausschließlich auf `ocr-selbstkalibrierung`).

## Implementierter Stand

Die Verarbeitungskette (siehe `CLAUDE.md`, Abschnitt „Aufbau") hat jetzt eine
zusätzliche, austauschbare Trennstelle `track` zwischen `rectify` und `ocr/`:
`QuadTracker` registriert eine bestätigte Anzeige innerhalb enger Grenzen neu
nach, bevor gelesen wird. `frames/` kennt jetzt zwei lauffähige Schemata
(`synthetic://`, `replay://`); `picamera2://`, `imx500://`, `folder://`,
`video://` bleiben `ImportError`.

Alles Bisherige aus früheren Sitzungen bleibt unverändert gültig: zweistufige
manuelle ROI-/OCR-Box-Kalibrierung, Bildpfad-Entkopplung, OCR-Drosselung,
`dispread stop`, RP2040-Power-Zyklus-Budget ([OQ-22](open-questions.md)),
`manual_roi` als Primärpfad — kein automatisch übernommener Wert ohne
expliziten ✓-Klick, auch nicht durch Autofit oder Nachführung.

## Verifiziert

```text
./.venv/bin/pytest -q                                      173 passed
./.venv/bin/ruff check src tests examples scripts           All checks passed!
```

Reale Messungen aus dieser Sitzung stehen in [VALIDATION.md](VALIDATION.md):
Benchmark-Baseline (Task 3), Autofit gegen die sechs Annotationen (Task 4),
Nachführung auf realen Bildern (Task 6). Manuelle Browser-/Hardwareabnahme
(Clipaufnahme am echten Gerät, Kalibrierschritt im Browser, Nachführung bei
echtem Kamerastoß während eines Laufs) steht weiterhin aus —
[OQ-21](open-questions.md)/[OQ-24](open-questions.md).

## Offene reale Abnahme

* Kalibrierschritt (Autofit) und Clipaufnahme im echten Browser gegen eine
  angeschlossene Kamera — nicht aus `synthetic://`-/`replay://`-Tests
  ableitbar ([OQ-21](open-questions.md)/[OQ-24](open-questions.md)).
* Nachführungsverhalten, wenn die Kamera während eines laufenden Betriebs
  tatsächlich angestoßen wird — [OQ-26](open-questions.md).
* BK-5491B-VFD-Rastererkennung ([OQ-23](open-questions.md)), GSVmulti-
  Telegrammformat ([OQ-01](open-questions.md)/[OQ-07](open-questions.md)),
  RS-232-Transceiver ([OQ-09](open-questions.md)), RP2040-Bridge-Fehler
  ([OQ-22](open-questions.md), bei Raspberry Pi gemeldet, kein Fix ohne
  Reboot verifiziert) — unverändert offen, von dieser Sitzung nicht berührt.

## Neu erkannte offene Punkte aus dieser Sitzung

Die Reviews von Task 5, 7 und 8 deckten vier weitere Unbekannte auf, die
über die drei im Plan selbst schon benannten (OQ-26–OQ-28) hinausgehen. Alle
sieben stehen jetzt in [open-questions.md](open-questions.md), Status
`offen`:

* [OQ-26](open-questions.md) — Nachführungsschwellen (`max_shift`,
  `max_rotation_deg`, `min_score`) unvalidiert an echten Geräten.
* [OQ-27](open-questions.md) — Rasterfeinschliff je Bild bewusst nicht
  gebaut.
* [OQ-28](open-questions.md) — Eindeutigkeit der Autofit-Geometrie
  (`flat_optimum`) an echten Geräten ungeprüft.
* [OQ-29](open-questions.md) — `calibrated_on`/`calibrated_on_frame_sequence`
  wird beim Autofit-Treffer gesetzt, nicht erst bei der Bestätigung —
  Auswirkung auf `clip.json`-Provenienz begrenzt, nicht auf `ValueRecord`.
* [OQ-30](open-questions.md) — `roi`-Op committet die Bestätigung, bevor der
  `QuadTracker` aufgebaut wird — selbstlimitierend (FIFO-Frame-Cache),
  Ursprungszustand bei Fehlschlag.
* [OQ-31](open-questions.md) — möglicher Stale-Zustand, wenn nach einem
  Autofit-Lauf manuell über die Regler der Einstelltabelle editiert wird,
  bevor bestätigt wird — vermutet, nicht gefixt, nicht testabgedeckt.
* [OQ-32](open-questions.md) — `edit_row()`/`_row()` haben keinen sicheren
  Fallback für einen unbekannten `kind` — der akute Absturz (Task 8) ist
  gefixt, die zugrunde liegende Lücke nicht.

Keiner dieser Punkte blockiert etwas Bereits-Gebautes; alle sind Kandidaten
für künftige Aufgaben.
