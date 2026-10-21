# Messpfad live: Tempo, Übergangsstatus und Abschluss — Implementation Plan

> **Stand 2026-10-21 abends: erledigt** (Commits `bebb8a4` … `fb1dde0`, in `master`).
> Abweichungen: Task 3 Step 6 setzt die OpenCV-Threads einmal in `dispread serve`
> statt je Lauf (Review, Wettlauf mit Kamerathreads). Task 3 Step 8 ist durch den
> 12-min-Lauf `live-20261021T144605Z` abgedeckt (29,8 Bilder/s, ≤ 55,6 °C, keine
> Unterspannung, kein Aussetzer); Prozess-CPU und Drosselbits wurden dabei nicht
> eigens aufgezeichnet. Offen bleibt der Toleranzlauf mit Werteplan (TODO.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den bisherigen Stand von `feat/messpfad-live` heute dokumentiert nach `master` bringen und die Worktrees aufräumen. Dann den Live-Leser auf die volle Kamerarate (30 Bilder/s) bringen, ohne den Pi zu überlasten, und Bilder während eines Wertwechsels als TRANSITION statt UNREADABLE kennzeichnen.

**Architecture:** Der Dot-Matrix-Leser verbringt laut Profil (2026-10-21, echter Crop) ≈ 60 % der Zeit im Zeichenvergleich, einer Python-Schleife über Zeichen × Verschiebungen, und ≈ 35 % in der punktweisen Abtastung. Beides wird vektorisiert, die Entscheidungen bleiben identisch. Der Übergangsstatus entsteht im `ReleaseGate`, nur aus Leser-Diagnosen und dem letzten freigegebenen Zellentext; ein Wert wird dabei nie freigegeben.

**Tech Stack:** Python 3.13, numpy, OpenCV, pytest, Node (live.js), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-12-messpfad-live-design.md`, `Konzept.md` §7 (Zustände gültig/Übergang/unlesbar/veraltet; „nachvollziehbares Verhalten während eines Anzeigewechsels“; „Ziffernwechsel können unvollständige oder überlagerte Zeichen erzeugen“). Befunde und Entscheidungen: `.superpowers/sdd/2026-10-21-lesesperre/progress.md` (lokal).

## Global Constraints

- Konzept §7: Unlesbares ablehnen statt raten. Ein Wert wird nur VALID, wenn der Leser ihn selbst annimmt und das Gate ihn bestätigt (`confirm_frames=2`).
- Leserentscheidungen (`best`, `text`, `reason`, `d_best`, `d_second`, `margin`) bleiben nach der Beschleunigung **identisch**. Toleranz für Abstände: 1e-5 relativ. Bei Gleichstand muss dieselbe Zeichenreihenfolge herauskommen wie in `CLASSES`.
- Pi-Schutz (Nutzervorgabe 2026-10-21: „auf keinen Fall hängen oder crashen“):
  - Die Live-Sitzung liest weiter immer nur das neueste Bild, es entsteht keine Warteschlange.
  - OpenCV-Threads im Live-Lauf begrenzen.
  - Abnahme: Prozess-CPU ≤ 150 % (von 400 %), SoC-Temperatur < 75 °C, `vcgencmd get_throttled` = `0x0` über 60 s.
- Python-Texte deutsch ohne Umlaute, HTML/JS mit Umlauten. Immer `PYTHONPATH=src`. Codex committet nicht; der Controller committet nach Review.
- Tests vor dem Commit: nur die betroffenen Tests plus Node plus Playwright. Die volle Suite läuft danach im Hintergrund, vor jedem Merge nach `master` einmal vollständig.
- `var/` nie verändern (nur lesen).
- Nach dem Hänger am 2026-10-21 um 14:08 (Watchdog-Neustart während der vollen Suite; Ursache unbekannt, kein persistentes Journal) laufen volle Suiten nur noch abgeschottet: `systemd-run --user --scope -p MemoryMax=3G -p MemorySwapMax=0 -p CPUQuota=300%` mit `nice -n 10`. Dazu protokolliert `~/pi-monitor.log` Last, Speicher, Swap und Temperatur alle 5 s.

## Review Focus

1. **Gleichstände im Zeichenvergleich:** Zwei Zeichen mit (fast) gleichem Abstand dürfen nach der Vektorisierung nicht die Rangfolge tauschen. Test: synthetischer Gleichstand, und Äquivalenz auf allen echten Setup-Crops unter `var/live/*/setup`.
2. **Dauerlast:** 60 s Live-Lesen bei 30 Bilder/s ohne steigende Latenz und ohne Drosselung. Test: Benchmark-Skript mit CPU-, Temperatur- und Drosselmessung (Task 3).
3. **Hand vor der Anzeige:** muss UNREADABLE bleiben, nicht TRANSITION. Test: viele unlesbare Zellen oder verlorene Nachführung bleiben UNREADABLE (Task 4).
4. **Langer Übergang:** Nach mehr als 1 s ohne VALID darf nicht mehr TRANSITION gemeldet werden, sondern UNREADABLE und später STALE. Test in Task 4.
5. **Anderer Leser:** Der 7-Segment-Leser ohne Zelldiagnosen behält das alte Verhalten. Test in Task 4.

---

### Task 1: Doku zum Stand 2026-10-21 (vor dem Merge)

**Files:**
- Modify: `docs/status.md`, `docs/VALIDATION.md`, `docs/lab_journal.md`, `TODO.md`

- [x] **Step 1:** `docs/status.md` auf den Stand 2026-10-21 bringen. Inhalt:
  - Lesesperre und Testlauf (L1), schwankende Ziffern (L2), Licht-Hinweis und angepasste Toleranz (L3).
  - Bedienerläufe heute:
    - Testlauf: Vermutungen richtig, `tracking_lost` 0.
    - Toleranzlauf ×1,41: 304/318 VALID.
    - Strenger Lauf 79 s: 911/1168 VALID, 67 Wertwechsel alle erfasst, 14,7 gelesene Bilder/s, Leser 53 ms/Bild.
  - Offen: Toleranz-Validierung gegen Referenzaufzeichnung, Referenzlauf, GSVmulti (OQ-07), UI-Überarbeitung.
- [x] **Step 2:** `docs/VALIDATION.md` bekommt einen Eintrag „2026-10-21 — Messpfad live: Bedienerläufe am Aufbau“ mit den Zahlen aus Step 1. Ausdrücklich dazu: kein formaler Abnahme-Lauf, Toleranz nicht validiert.
- [x] **Step 3:** `docs/lab_journal.md`: Eintrag am Ende anhängen. Inhalt: Ziel, Aufbau, Beobachtungen (Schattenkante der Kamera, Punkttiefe 0,39–0,41 gegen 0,67–0,69; schräge Kamera; schwankende letzte Ziffer), was offen ist.
- [x] **Step 4:** `TODO.md`, Block „Messpfad live (aktiv)“: Punkt „UI/UX-Überarbeitung der Werkbank (nicht prod-ready), erst wenn der Messpfad weitgehend fertig ist“ ergänzen.
- [x] **Step 5:** `./.venv/bin/python scripts/oq-index.py --check` muss Exit 0 liefern. Den Doku-Build führt der Controller aus (`mkdocs build --strict`, falls vorhanden; sonst Doku-Tests).
- [x] **Step 6:** Commit „Doku: Stand Messpfad live 2026-10-21“.

### Task 2: Merge nach `master` und Worktree-Aufräumen (Controller)

- [x] **Step 1:** `git fetch origin`; `git log --oneline HEAD..origin/master` prüfen. Ist `master` weiter, `origin/master` in den Branch mergen, Konflikte lösen und die betroffenen Tests laufen lassen.
- [x] **Step 2:** Die volle Suite muss auf dem Merge-Stand grün sein. Zuletzt grün bei `b0d6f1a`: 1489 passed. Erneut laufen lassen, wenn sich seit `b0d6f1a` Code geändert hat.
- [x] **Step 3:** `git push origin HEAD:master`, nur als Fast-Forward, kein Force. Danach den Docs-Runner bzw. CI-Status prüfen.
- [x] **Step 4:** Bestandsaufnahme mit `git worktree list`. Je Worktree erfassen:
  - Branch;
  - in `origin/master` enthalten (`git merge-base --is-ancestor`)?
  - uncommittete Änderungen (`git -C <wt> status --porcelain`)?
  - letzter Commit.
- [x] **Step 5:** Nur Worktrees entfernen, die vollständig gemergt und sauber sind: `git worktree remove <pfad>`, danach den gemergten lokalen Branch löschen (`git branch -d`). `git worktree prune`. Alles andere wird mit Begründung dem Nutzer gemeldet.
  - Nie entfernen: den Haupt-Checkout, Worktrees mit Änderungen, ungemergte Branches.
  - Den Haupt-Checkout (`~/picam-ai`, hinter `origin/master`, mit uncommitteter Tour-Arbeit) nicht anfassen; nur melden.
- [x] **Step 6:** Ergebnis im Ledger festhalten.

### Task 3: Leser auf 30 Bilder/s

**Files:**
- Modify: `src/dispread/ocr/dotmatrix_templates.py` (`distance`, `_best_per_class`, `_decide`, `classify`; vorberechnete gestapelte Vorlagen)
- Modify: `src/dispread/ocr/dotmatrix_sampling.py` (`dot_centers`, `sample_image`: alle Zellen × Verschiebungen in einem `_bilinear`-Aufruf)
- Modify: `src/dispread/ocr/dotmatrix.py` (gestapelte Vorlagen einmal im Konstruktor bauen)
- Modify: `src/dispread/live/session.py` (OpenCV-Threads für den Lauf begrenzen, siehe Step 6)
- Modify: `scripts/live-reader-benchmark.py` (CPU-, Temperatur- und Drosselmessung, Zielrate)
- Test: `tests/test_dotmatrix_reader.py`, `tests/test_dotmatrix_templates*.py` (per grep finden), `tests/test_live_session.py`, `tests/test_live_benchmark*.py` (per grep finden)

**Interfaces:**
- Produces: `classify(vectors, t, d_max_factor=1.0) -> CellDecision` mit unveränderter Signatur und Rückgabe. Neu: `stack_templates(t: Templates) -> StackedTemplates`, ein Dataclass mit `classes: tuple[str, ...]`, `mean: np.ndarray (C, 40)` und `inv_std: np.ndarray (C, 40)`. `DotMatrixReader` hält es als `self._stacked`.
- `sample_image(gray, grid, cells) -> SampledImage` bleibt unverändert, Werte gleich bis 1e-4.

- [x] **Step 1: Äquivalenztest schreiben** (failing, weil `stack_templates` fehlt). Die alte Implementierung wird als Referenz in den Test kopiert:

```python
def _reference_best_per_class(vectors, mean, std):
    out = {}
    for ch in mean:
        ds = [float(np.sqrt(np.mean(((v - mean[ch]) / np.maximum(std[ch], SIGMA_FLOOR)) ** 2))) for v in vectors]
        j = int(np.argmin(ds))
        out[ch] = (ds[j], j)
    return out

def test_vectorized_classification_matches_reference_on_real_and_synthetic_cells(reader):
    rng = np.random.default_rng(1)
    t = reader._t
    for _ in range(200):
        vectors = rng.uniform(0, 1, (len(SHIFTS), 40)).astype(np.float32)
        ref = _reference_best_per_class(vectors, t.mean, t.std)
        new = classify(vectors, t)
        order = sorted(ref, key=lambda c: ref[c][0])
        assert new.best == order[0] and new.second == order[1]
        assert new.d_best == pytest.approx(ref[order[0]][0], rel=1e-5)
        assert new.shift_index == ref[order[0]][1]
```

  Dazu ein Test mit echten Crops, übersprungen, falls `var/live` fehlt: Über alle `var/live/*/setup/{still,stability}.png` mit `proposal.json` liest der Leser alt und neu, und die Zellentscheidungen sind identisch. Den Vergleich mit der alten Implementierung macht der Test per Monkeypatch; vom alten Code bleibt nur die Referenzkopie im Test.

- [x] **Step 2:** Test laufen lassen und das erwartete FAIL sehen.
- [x] **Step 3: Zeichenvergleich vektorisieren.** `stack_templates` baut `mean (C,40)` und `inv_std = 1/np.maximum(std, SIGMA_FLOOR)` in der Reihenfolge von `t.mean`. In `_decide` dann: `d = np.sqrt(np.mean(((vectors[None,:,:] - mean[:,None,:]) * inv_std[:,None,:])**2, axis=2))` mit Form (C, S). Je Klasse `argmin` über S. Die Reihenfolge der Klassen ergibt sich aus einem stabilen Sortieren (`np.argsort(kind="stable")`) nach Abstand, damit Gleichstände dieselbe Reihenfolge wie bisher behalten (`sorted` über dict-Reihenfolge ist ebenfalls stabil). Rechengenauigkeit: float32 wie bisher.
- [x] **Step 4: Abtastung vektorisieren.** `dot_centers` für alle Zellen und `SHIFTS` als ein Array der Form (cells, S, 40, 2) aufbauen, dann je ein `_bilinear` auf `smooth` und `closed` aufrufen und auf (cells, S, 40) zurückformen. Test: Gleichheit mit der alten Schleife bis 1e-4 auf einem echten Crop und auf einem synthetischen Bild.
- [x] **Step 5:** Die bestehenden Sicherheitstests müssen unverändert grün sein: `test_sweep_richtig_oder_abgelehnt_nie_falsch`, `test_sweep_mit_hoechster_toleranz_nie_falsch` und alle Lesertests.
- [x] **Step 6: Pi-Schutz.** `LiveSession.start()` setzt `cv2.setNumThreads(LIVE_CV_THREADS)` mit `LIVE_CV_THREADS = 2` als Konstante in `dispread/live/__init__.py`; `stop()` stellt den vorherigen Wert wieder her. Test mit einem Fake für `cv2.setNumThreads` und `getNumThreads`.
- [x] **Step 7: Benchmark.** `scripts/live-reader-benchmark.py` ergänzen:
  - Messung über die Laufzeit: Prozess-CPU in % (aus `/proc/self/stat` bzw. `os.times`), SoC-Temperatur (`/sys/class/thermal/thermal_zone0/temp`) und `vcgencmd get_throttled`, falls vorhanden.
  - Ausgabe: gelesene Bilder/s, Median und p90 der Lesezeit.
  - Exit ≠ 0, wenn die Grenzen aus den Global Constraints verletzt sind.
  - Test für die Auswertungsfunktion mit fiktiven Messwerten.
- [x] **Step 8:** Am Aufbau misst der Controller oder der Nutzer, nicht Codex. Bei laufender Werkbank 60 s Live-Lesen über die lokale Steuerung, oder das Benchmark-Skript auf gespeicherten Frames. Ziel: ≥ 28 gelesene Bilder/s, `dropped_frames` im Median 0, Grenzen eingehalten.
- [x] **Step 9:** CHANGELOG-Punkt mit den Zahlen vorher und nachher; Commit.

### Task 4: Übergangsstatus bei Wertwechseln

**Files:**
- Modify: `src/dispread/validate.py` (`GateConfig`, `ReleaseGate.evaluate`)
- Modify: `src/dispread/workbench/static/live.js` (TRANSITION mit Grund `anzeige_wechselt` → „Wert wechselt“)
- Test: `tests/test_gate_und_referenz.py` (bzw. die vorhandene Gate-Testdatei), `tests/live_client.test.mjs`

**Interfaces:**
- Consumes: `ReadResult.diagnostics["cells"]`, je Zelle `text` (angenommenes Zeichen oder None) und `reason` (L2).
- Produces: `GateConfig.transition_max_cells: int = 3`, `GateConfig.transition_window_ns: int = 1_000_000_000`. Reject-Grund `"anzeige_wechselt"` als ERSTER Grund, die bisherigen Gründe dahinter.

- [x] **Step 1: Failing Tests:**
  1. Nach einem VALID-Wert `+0.60997` liefert ein Bild mit nur Zelle 7 unlesbar und den Zellen 0–6 gleich dem letzten gültigen Zellentext → `TRANSITION` mit Gründen `("anzeige_wechselt", "unreadable_cells:1", …)`, `value` None.
  2. Mehr als 3 unlesbare Zellen → `UNREADABLE`, wie bei der Hand.
  3. Eine lesbare Zelle weicht vom letzten gültigen Zellentext ab (ein Wechsel in mehreren Stellen, eine nur teilweise erkannt) → `TRANSITION` nur, wenn alle *lesbaren* Zellen entweder gleich dem alten Zellentext sind oder genau in den unlesbaren Positionen liegen. Sonst UNREADABLE. Konkrete Regel: jede lesbare Zelle muss gleich der alten sein.
  4. Letzter VALID-Wert älter als 1 s → `UNREADABLE`, nach `stale_after_ns` → `STALE`.
  5. Nach `interrupt()` (Nachführung verloren) und bei Gründen wie `tracking_lost:*`, `low_contrast`, `state:*`, `unit_mismatch:*` → nie TRANSITION.
  6. Ohne `cells` in den Diagnosen (7-Segment) bleibt das alte Verhalten.
- [x] **Step 2:** Tests laufen lassen und das erwartete FAIL sehen.
- [x] **Step 3: Implementieren.**
  - Das Gate merkt sich bei jedem VALID den Zellentext der lesbaren Zellen (`[c["text"] for c in cells]`) als `_last_valid_cells`; `interrupt()` und `reset()` löschen ihn.
  - Im Ablehnungszweig gilt TRANSITION nur, wenn alle der folgenden Bedingungen erfüllt sind:
    - Alle Gründe stammen aus der Menge `{unreadable_cells:*, low_segment_margin, decimal_point_unknown, sign_region_unreadable, no_value}`.
    - `cells` sind vorhanden, und es gibt höchstens `transition_max_cells` Zellen mit `text is None`.
    - Jede lesbare Zelle ist gleich `_last_valid_cells` an derselben Position.
    - `capture_ns - _last_valid_ns <= transition_window_ns`.
  - Dann: `status=TRANSITION`, Gründe `("anzeige_wechselt", *reasons)`; `_candidate` wird verworfen wie bisher; `_last_valid_ns` bleibt unverändert.
- [x] **Step 4:** Die Gate-, Session- und Live-Tests sowie der Sweep müssen grün sein.
- [x] **Step 5:** `live.js`: TRANSITION mit erstem Grund `anzeige_wechselt` → Überschrift „TRANSITION“, Detail „Wert wechselt“. Dazu ein Node-Test.
- [x] **Step 6:** CHANGELOG-Punkt; Anleitung Kapitel 10, Satz zu TRANSITION; Commit.

### Task 5: Referenzaufzeichnung im Live-Lauf und Abgleich

Zweck: Mit dem GSV-2AS als Wahrheit belegen, ob VALID-Werte stimmen. Daraus folgen die Validierung der angepassten Toleranz (TODO.md), der VALID-Anteil, die Verzögerung je Wertwechsel und der Anteil TRANSITION/UNREADABLE. Es ist **kein Training**: Der Leser bleibt unverändert. Beschriftete Bilder für späteres Nachlernen sind ein eigener, späterer Schritt.

**Files:**
- Create: `src/dispread/live/reference.py`: Leser des seriellen GSV-2AS-Stroms für die Laufzeit einer Sitzung.
- Modify: `src/dispread/live/session.py`, `src/dispread/live/service.py`, `src/dispread/workbench/live_api.py`, `static/live.html` + `live.js`
- Create: `scripts/live-reference-eval.py`: Abgleich `records.jsonl` gegen `reference.jsonl`.
- Test: `tests/test_live_reference.py`, `tests/test_live_reference_eval.py`, Erweiterungen in `tests/test_live_service.py`, `tests/test_live_session.py`, `tests/test_live_api.py`, `tests/live_client.test.mjs`

**Interfaces:**
- Consumes:
  - aus `scripts/sync-record.py` und `scripts/gsv-registers.py`: Zeilenlesen, Telegramm-Parsing und `set norm`/`set dpoint`-Kodierung. Das gemeinsame Stück wird nach `src/dispread/gsv2as_serial.py` verschoben, nicht kopiert; beide Skripte importieren es danach.
  - `cell_text_from_telegram`, `records.to_boottime_ns`, die Zeitkalibrierung aus `session.json`.
  - aus `scripts/gate-label.py`: Schutzintervall M = 695 ms (Festlegung 2026-09-23) und `telegram_to_display_text`.
- Produces:
  - `ReferenceRecorder(port_opener, out_path, *, clock=time.clock_gettime_ns(CLOCK_BOOTTIME))` mit `start()`, `stop() -> dict` (Zeilen, Parsefehler, Lücken > 1 s) und `latest() -> dict | None`.
  - `reference.jsonl` je Zeile: `{"t_boottime_ns", "raw", "cell_text", "value"}`.

- [x] **Step 1: Failing Tests für `ReferenceRecorder`** mit einem Fake-Port:
  - Zeilen werden mit BOOTTIME-Stempel geschrieben.
  - Eine Teilzeile am Anfang wird verworfen.
  - Ein Parsefehler zählt, beendet aber nicht.
  - `stop()` schließt den Port und liefert die Zählung.
  - **Schreibt nie** auf den Port, außer im Normplan aus Step 3. Der Test prüft, dass `write` sonst nie aufgerufen wird.
- [x] **Step 2:** Implementieren:
  - Eigener Thread mit Lese- und Schreibtrennung wie in `sync-record.py`, damit `readline` nie auf das Dateisystem wartet.
  - Der Port wird nur während eines Laufs gehalten. Die Einrichtung öffnet ihn wie bisher selbst, Einrichtung und Lauf schließen sich ohnehin aus.
- [x] **Step 3: Optionaler Normplan** (`norm_schedule=[(faktor, sekunden), …]`):
  - Derselbe Prozess stellt die Werte über `set norm` um. Ein zweiter Prozess auf demselben Port würde Bytes stehlen.
  - Jeder Befehl wird mit BOOTTIME-Stempel in `commands.jsonl` protokolliert.
  - Danach wird der Ausgangswert zurückgestellt: Wiederherstellungspunkt wie in `sync-record.py`, Prüfung von `EEnow = 0`.
  - Faktorbereich 0,15…1 580 000.
  - Test mit Fake-Port: Byte-Folge gleich der aus `sync-record.py`, Rückstellung auch bei Abbruch.
  - Nur nach ausdrücklicher Bedienerwahl auf der Seite. Konzept und AGENTS: kein Erfinden von Protokollen; nur die belegten Befehle 16/17.
- [x] **Step 4: Service, API und Seite.**
  - `start_run(..., reference=True|False, norm_schedule=None)`. Vorgabe ist `reference=True`, wenn ein GSV-2AS am Port antwortet; sonst läuft der Lauf ohne Referenz und meldet „ohne Referenz“.
  - `session.json` bekommt `reference`: Pfad, Zeilen, Parsefehler, Lücken, Normplan.
  - Auf der Seite: Häkchen „Referenz vom GSV-2AS mitschreiben“ (Vorgabe an) und ein optionales Feld „Werteplan (set norm), z. B. 1:20,2:20,0.5:20“ mit Hinweis „schreibt auf das Gerät (RAM, nicht EEPROM)“.
  - Beim Normplan startet der Lauf erst nach einer Bestätigungsfrage.
- [x] **Step 5: `scripts/live-reference-eval.py <run-dir>`.**
  - Für jedes VALID-Record wird der Aufnahmezeitpunkt per `to_boottime_ns` mit dem Versatz aus `session.json` umgerechnet. Danach wird der Referenzwert gesucht, der in `[t − M, t]` gültig war.
  - Gültig bedeutet: Der letzte Telegrammwechsel liegt mindestens M vor t. Wechsel innerhalb des Schutzintervalls zählen als „unentschieden“, nicht als Fehler.
  - Ausgabe als Text und `--json`:
    - **Fehllesungen**: VALID ≠ Referenz, außerhalb des Schutzintervalls. Muss 0 sein, sonst Exit 1.
    - VALID-Anteil je Zustand der Anzeige, getrennt nach stabil und im Wechsel.
    - Verzögerung vom Referenzwechsel bis zum ersten VALID des neuen Werts, als Median und p90.
    - Anteil TRANSITION und UNREADABLE an Wechseln.
    - `tolerance_frames` und Fehllesungen unter Toleranz getrennt ausgewiesen.
  - Tests mit synthetischen `records.jsonl` und `reference.jsonl`: korrekter Lauf ergibt 0 Fehler; eine eingebaute Fehllesung ergibt Exit 1; ein Wechsel im Schutzintervall ergibt „unentschieden“; fehlender Versatz in `session.json` führt zur Ablehnung (CLAUDE.md: ohne Versatz wird abgelehnt).
- [x] **Step 6:** Doku:
  - Anleitung Kapitel 10 mit Abschnitt „Referenzaufzeichnung und Abgleich“.
  - TODO-Punkt zur Toleranz-Validierung auf diese Werkzeuge verweisen.
  - CHANGELOG.
  - Commit.

### Task 6: Abschluss des Tages

- [x] **Step 1:** Die volle Suite auf dem Stand nach Task 3 und 4 laufen lassen.
- [x] **Step 2:** Messung am Aufbau aus Task 3, Step 8, mit Nutzerlauf **mit Referenzaufzeichnung** (Task 5):
  - Bilder/s;
  - Anteil TRANSITION gegen UNREADABLE bei Wechseln;
  - `live-reference-eval.py`: 0 Fehllesungen.
  - Einmal streng und einmal mit Toleranz. Das Toleranz-Ergebnis geht in VALIDATION ein.
- [x] **Step 3:** Zweiter Merge nach `master` (Fast-Forward-Push), Ledger, `docs/status.md`.
