# Handoff an Codex: Rahmenprüfung der Nachführung und Rasterbestimmung (2026-11-13)

**Auftraggeber:** Leonhard (Projektleitung). **Vorbereitet von:** Claude, ohne Orchestrierung.
Codex arbeitet die Aufgaben selbstständig ab; danach reviewt Claude, dann entscheidet Leonhard.

## Rahmen

- **Worktree:** `/home/me-systeme/picam-ai/.worktrees/rahmen-raster`, Branch `fix/rahmen-raster`
  (abgezweigt von `feat/integration`). `.venv` und `var` sind Symlinks auf den Hauptcheckout.
- **Python:** immer `PYTHONPATH=src ./.venv/bin/python …` bzw. `PYTHONPATH=src ./.venv/bin/pytest …`.
- **Entwicklungsaufnahmen:** `DISPREAD_DEV_DATA=/mnt/ssd/picam-dev` (nur lesen).
- **Nicht anfassen:** den laufenden Werkbank-Dienst (`dispread-werkbank-bruecke`, Worktree
  `.worktrees/bruecke-run`), die Kamera, `var/` schreibend, andere Worktrees.
- **Commits:** Die Sandbox kann nicht committen. Lass alle Änderungen im Worktree liegen.
  Schreib je Aufgabe einen Abschnitt in `REPORT-codex.md` im Worktree-Wurzelverzeichnis:
  geänderte Dateien, was und warum, Testergebnisse mit Zahlen und offene Punkte.
- **Verbindlich:** `AGENTS.md` und `CLAUDE.md` lesen. Nie einen falschen Fit oder eine falsche
  Lage annehmen; Unlesbares ablehnen statt raten; keine Grenze im Messpfad ohne Beleg lockern.
  Doku-Pflicht aus `AGENTS.md` gilt (CHANGELOG-Eintrag je Aufgabe, betroffene OQ-Einträge).

## Hintergrund (bitte zuerst lesen)

- Abnahme und Stand: `TODO.md` (Abschnitt „Zuerst“ und „Befunde Smoketest 13.11.“), `docs/status.md`.
- Recherche Nachführung: `docs/quellen/nachfuehrung-recherche-2026-11-13/README.md`.
- Recherche Raster: `docs/quellen/raster-recherche-2026-11-13/README.md`.
- Läufe und Einrichtungen vom 13.11. unter `var/live/live-20261113T*/` (Belege: `session.json`,
  `run-01/diagnose/images.jsonl`, `setup/still*.png`, `setup/failure.json`, `setup/cell-text.json`).
- OQ-69/70/72/74 in `docs/open-questions.md` (`grep -n '^## OQ-69'` usw.).

## Aufgabe 1: Rahmenprüfung der Nachführung bei Fokusunterschied (zuerst)

**Befund:** Am Laufstart wird der Fokus neu gesetzt. Das Laufbild ist dann schärfer bzw.
unschärfer als das Einrichtungsbild (140 % bzw. 65 %), der Maßstab gegen die Referenz liegt bei
1,0018. Der starre Erstdurchgang in `src/dispread/live/frame_tracking.py` scheitert dadurch in
fast jedem Bild. Im Zweitdurchgang hat ein schärfeempfindlicher Fasenbereich einen festen
Versatz von 0,62 px bei der Grenze 0,65 px, also entscheidet ein Münzwurf. Das ergibt bis 60 %
`tracking_lost:rahmen_unstimmig`.

**Umsetzen (Empfehlung 1 der Recherche):**
1. Fokuszustand von Referenz und Lauf angleichen und sichtbar machen:
   - Schärfeprüfung am Laufstart zweiseitig, heute gibt es nur die Untergrenze 0,6
     (`focus_end_check`).
   - Weicht die Schärfe deutlich ab, nicht still weiterlaufen. Entweder den Fokus nachführen,
     bis das Verhältnis zur Einrichtungsschärfe in einem belegten Band liegt, oder den Lauf mit
     klarer Bedienermeldung ablehnen. Das Band an den Daten vom 13.11. und an den
     Entwicklungsaufnahmen begründen.
   - Maßstab und Anteil der Zweitversuche als eigenen Hinweis in Status und `session.json`.
2. **Keine** Grenze im Messpfad ändern (Residualgrenzen 0,35/0,65 px bleiben).
3. **Belege offline:**
   - Replay der Läufe vom 11.11. (65 % bzw. 38 % Zweitversuche) auf Maßstab.
   - Zusammenhang Fokuswert und Maßstab aus vorhandenen Daten, soweit möglich.
   - Regressionstests mit den Diagnosebildern aus `live-20261113T113119Z/run-01`.

Nicht umsetzen: k Ausreißer je Bild ausschließen, letzte Lage halten (siehe Recherche).

## Aufgabe 2: Rasterbestimmung, Fehler A (Leerzellenregel an der Zellgrenze)

**Befund:** `src/dispread/dotlattice.py` `_evaluate_fit` (um Zeile 405–420) rechnet Kandidaten
in der Lückenspalte einer Zelle der Leerzelle zu. Randminima am linken Stamm des Nachbarzeichens,
weniger als 0,3 px vor der Zellgrenze, führen so zu `leerzelle_belegt` und am Ende zu
`keine_startlage`. Betroffen sind 5 von 12 Standbildern vom 13.11.

**Umsetzen (A1):**
- Kandidaten in der Lückenspalte dicht am Nachbarpunkt nicht der Leerzelle zurechnen.
  Randabstand etwa 0,25 Spalten; den Wert begründen.
- Tests:
  - die drei Standbilder `var/live/live-20261113T130253Z/setup/still*.png` als Fixtures oder
    über `DISPREAD_DEV_DATA`
  - Gegenproben, dass echte belegte Leerzellen weiter abgelehnt werden
- Auswertung **nur mit A1**:
  - alle Standbilder unter `var/live` (65)
  - die Fehlraster aus OQ-69
  - Zielbild: keiner der bisherigen Fits wandert um mehr als 1 px, und kein neuer Fit ist falsch
    (gegen den seriellen Zellentext bzw. das Erstbild der Aufstellung prüfen)

## Aufgabe 3: Rasterbestimmung, Fehler B (falsche Unterkante)

**Befund:** In `still.png` (130253Z) entsteht in der unteren Hälfte der Hinweisbox eine einzelne
schräge Hough-Linie durch die Ziffernpunkte. Ihre Neigung ist 0,0467 statt 0,0015, und alle
Startlagen liegen dadurch mindestens 13 px daneben.

**Umsetzen (B1):** Die Unterkante nur übernehmen, wenn sie plausibel ist (Neigung nahe der
Oberkante, Länge, Lage unterhalb der Punkte), oder beide Annahmen durchsuchen.

Pauschal „Unterkante = Oberkante“ ist nicht erlaubt, weil dann zwei Einrichtungen vom 26.10.
ihren Fit verlieren. Dieselbe Auswertung wie in Aufgabe 2, **getrennt** für B1 und für A1+B1.

## Abschluss

- Gezielte Tests grün, dazu `PYTHONPATH=src ./.venv/bin/ruff check src tests`.
- Die volle Suite (`DISPREAD_DEV_DATA=/mnt/ssd/picam-dev ./.venv/bin/pytest -q -n 4`) einmal
  laufen lassen. Fehlschläge, die nur in der Sandbox auftreten (Sockets), als solche im Report
  kennzeichnen.
- `REPORT-codex.md` mit:
  - Ergebnis je Aufgabe
  - Vorher/Nachher-Zahlen
  - offene Risiken
  - der Bitte um Review durch Claude, vor allem für Aufgabe 1 (Bedienerfluss) und Aufgabe 2
    (kein falscher Fit)
