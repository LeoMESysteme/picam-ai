# Status — Stand 2026-09-18

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Branch `feature/dataset-collection` (eigener Worktree
`/home/me-systeme/picam-ai-dataset-collection`), abgezweigt von `master` HEAD
`41a4241`. Noch **nicht** nach `master` gemergt, kein Push. Der ursprüngliche
Implementierungsplan (`docs/superpowers/plans/2026-09-18-dataset-collection-handoff.md`)
wurde vollständig eingelesen, die Aufgaben/Abnahmekriterien übernommen und die
Datei danach wie vom Nutzer gewünscht gelöscht (nicht committet).

Umgesetzt: Aufgaben 1–6 aus diesem Plan, jede mit eigenem Commit, jeweils mit
CHANGELOG-Eintrag im selben Commit. `master` selbst ist unberührt — die
laufende Produktions-Workbench (Prozess auf diesem Pi aktiv, siehe unten)
wurde nicht angefasst.

## Was gebaut wurde

* **Aufgabe 1 — Geräte, Samples, Persistenz:** `src/dispread/workbench/datasets.py`,
  `DatasetStore`. UUID-Geräteregistrierung mit Revisionszähler und
  Split-Sperre nach der ersten Aufnahme, Unabhängigkeitsgruppen, atomare/
  idempotente Sample-Speicherung (temporäres Verzeichnis + `rename`),
  unveränderlicher Export mit Abdeckungs-/Ausschlussbericht.
* **Aufgabe 2 — Rohbildaufnahme ohne Kalibrierung:** `dataset_capture.py`
  (`CaptureRegistry`, eigene Tokens, max. zwei offene Aufnahmen, 64 MiB,
  10 Minuten Ablauf), dünne `Controller`-Anbindung über neue
  `dataset.*`-Kommandos. Capture/Save fassen `self.config`, `self.tracker`,
  `self.reading` und den Gate-Zustand nicht an.
* **Nachschliff:** `dataset.save`/`dataset.export` laufen jetzt wie
  `ocr.suggest`/`layout.autofit` **vor** `Controller.lock` — ein blockierter
  Save hält `status`/`stream.mjpg`/`publish()` nicht mehr auf
  (`DatasetStore` hat dafür ein eigenes `threading.Lock()`).
* **Aufgabe 3 — Endpunkte:** `/dataset/captures/{token}.jpg`,
  `/dataset/exports/{id}.zip` — authentifiziert, IDs serverseitig aufgelöst,
  Export-ZIP über `asyncio.to_thread`.
* **Aufgabe 4 — Browserablauf:** `static/dataset.js` (eigener Namespace,
  eigenes `csrf`), neuer „Datensatz sammeln"-Bereich in `index.html`. Zielbox-
  Umrechnung (Letterboxing, DPR-unabhängig) als reine, testbare Funktion.
* **Aufgabe 5 — Gruppen/Ähnlichkeit/Fortschritt:** Ähnlichkeitswarnung
  innerhalb einer Situation (Heuristik, [OQ-33](open-questions.md)),
  blockiert bis begründet bestätigt; `summary()` zählt lesbare/unlesbare
  Proben nur noch real (nicht synthetisch) und meldet fehlende Bedingungen
  je Gerät/gesamt als Lücke.
* **Aufgabe 6 — Loaderintegration:** Export dedupliziert Bildhashes jetzt
  über den *gesamten* Export (nicht nur je Situation). Neues
  `scripts/check-dataset-export.py`: lokale Prüfung immer, optional gegen den
  **echten** externen Experiment-Loader
  (`codex/automatic-seven-segment`, Commit `6a18bdf`,
  `src/dispread/experimental/evaluation.py::load_manifest`) in einem
  separaten Prozess mit dessen eigener venv. `tests/test_dataset_export.py`
  nutzt dafür ein bereits lizenziertes Realbild aus dem Experiment.

Zielbox/Label erreichen nirgends `ValueRecord`, `ReleaseGate`,
`TelegramFormatter` oder den Tracker — reine Entwicklungs-/Prüfdaten, wie im
Plan gefordert. Strukturentscheidung dazu in `project_history.md`
(2026-09-18, „eigener Rohbild-Sammelpfad statt Lockerung von `roi`/`clip.start`").

## Verifiziert

```text
./.venv/bin/pytest -q                                      286 passed, 2 skipped
./.venv/bin/ruff check src tests examples scripts           All checks passed!
node --check src/dispread/workbench/static/workbench.js     Exit 0
node --check src/dispread/workbench/static/dataset.js       Exit 0
git diff --check                                            sauber
```

Bestehende ROI-/Clip-/OCR-/Tracking-/Serial-Regressionstests laufen
unverändert mit (keine der bestehenden Dateien wurde inhaltlich geändert
außer additiven `controller.py`-Erweiterungen).

Die zwei Skips sind vorbestehend (`node` browserclient-Regressionen,
umgebungsabhängig, unverändert seit `master`).

## Bedienanleitung

`docs/anleitung/11-datensatz-sammeln.md` — bewusst außerhalb der
Nummerierung 0–9 des Lernpfads (analog Kapitel 10), da es einen fertigen
Prototyp beschreibt statt einer Bauaufgabe. `08-datensatz-sammeln.md` aus dem
ursprünglichen Plantext war bereits durch `08-ocr-backends.md` belegt — die
nächste freie Nummer wurde stattdessen verwendet.

## Tatsächlich offene Abnahmen dieser Sitzung

* **Realer interaktiver Browserdurchlauf** (Geräteanlage → Aufnahme → Box/Wert
  → Speichern → zweite Situation → Neustart → Export) hat **nicht**
  stattgefunden — [OQ-34](open-questions.md), selbe Ursache wie
  [OQ-21](open-questions.md): der headless Chromium dieser Umgebung lädt auch
  einfache lokale HTTP-Seiten nicht zuverlässig. Abgedeckt stattdessen durch
  reine Geometrietests (`tests/dataset_client.test.mjs`) und
  Endpunkttests (`tests/test_dataset_api.py`).
* **Reale Kameraabnahme** wurde in dieser Sitzung nicht durchgeführt: ein
  `dispread serve`-Prozess läuft bereits auf diesem Pi (aktiver
  Kamerabesitzer, PID zum Zeitpunkt der Prüfung ermittelt) — es wurde
  bewusst keine zweite Kamera-Session versucht und keine aktive Nutzung
  unterbrochen (siehe Hardware-Risikohinweis in AGENTS.md/CLAUDE.md).
* **Ähnlichkeitsschwellwert** (`SIMILARITY_THRESHOLD = 0.02`) ist ein
  unvalidierter Vorabdefault — [OQ-33](open-questions.md).
* **30 unabhängige reale Abschlusstestbilder** über mindestens sechs
  Geräten/drei Familien/LED+LCD (Sammelziel, in `coverage.json`/
  `dataset.export` als Zielwert hinterlegt) sind naturgemäß noch nicht
  erreicht — das ist Aufgabe des tatsächlichen Sammelbetriebs, ausdrücklich
  **nicht** Teil dieser Implementierungsaufgabe.

Keiner dieser Punkte blockiert das bereits Gebaute; alle sind ehrlich als
offen markiert statt stillschweigend als erledigt behandelt.

## Unverändert aus vorherigen Sitzungen

`master` (Branch `ocr-selbstkalibrierung` bereits gemergt, siehe CHANGELOG):
Live-Workbench, manuelle ROI/Anzeigeraster, referenzwertgestütztes Autofit,
begrenzte Nachführung (`QuadTracker`), LED/LCD-Polarität, Clipaufnahme mit
Schreibfehlerunterscheidung (`write_failures`). **Task 11 bleibt gesperrt**
(Konzept-Sperrbedingungen für eine Decoderänderung weiterhin nicht erfüllt) —
der Sammelmodus dieser Sitzung hebt das nicht auf und ändert keine
Freigaberegeln.

Separates abgeschlossenes Erkennungsexperiment: Branch
`codex/automatic-seven-segment`, Commit `6a18bdf`, Worktree
`/home/me-systeme/picam-ai-auto-seven-segment` — diese Sitzung hat dessen
Loader **verwendet** (siehe oben), aber keinen seiner Modelle/Runner
importiert und keine neue OCR-Messung erzeugt.

## Nächste Schritte

Kein automatischer Merge/Push. Vor einem Merge nach `master`: reale
Browserabnahme (OQ-34/OQ-21) nachholen, sobald ein funktionierender Browser-
Testweg existiert oder ein Mensch die Bedienung manuell abnimmt.
