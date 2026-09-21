# Status — Stand 2026-09-21

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Diese Sitzung (2026-09-21) hat zunächst die als hohe Priorität markierte
UX-Vereinfachung des Datensatz-Sammelmodus umgesetzt (siehe unten,
„Sammelmodus-UX vereinfacht"), direkt danach — beim ersten echten
Sammeldurchlauf durch den Nutzer selbst — einen zweiten, schwereren Fund:
**„Prüfsatz exportieren" lieferte 0 Bilder**, obwohl 46 reale Proben
gespeichert waren (siehe „Vertreterauswahl fehlte in der Oberfläche"
unten), und danach einen dritten, unabhängigen Fund: **`dispread serve`
reagierte auf kein Strg+C mehr** (siehe „Serve liess sich nicht beenden"
unten — kein Kamera-/OQ-22-Problem, eine reine Nebenläufigkeitslücke im
Shutdown). Alles direkt auf `master`, kein eigener Worktree — der
Sammelmodus selbst war bereits vorher nach `master` gemergt.

Vorherige Sitzung (2026-09-18): Branch `feature/dataset-collection` (eigener
Worktree `/home/me-systeme/picam-ai-dataset-collection`), abgezweigt von
`master` HEAD `41a4241`, danach nach `master` gemergt. Der ursprüngliche
Implementierungsplan (`docs/superpowers/plans/2026-09-18-dataset-collection-handoff.md`)
wurde vollständig eingelesen, die Aufgaben/Abnahmekriterien übernommen und die
Datei danach wie vom Nutzer gewünscht gelöscht (nicht committet).

Umgesetzt (2026-09-18): Aufgaben 1–6 aus diesem Plan, jede mit eigenem Commit,
jeweils mit CHANGELOG-Eintrag im selben Commit. Die laufende
Produktions-Workbench (Prozess auf diesem Pi aktiv, siehe unten) wurde in
keiner der beiden Sitzungen angefasst — nur Dateien bearbeitet.

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

* **Nachschliff nach Advisor-Review:** eine unabhängige Zweitprüfung nach
  Aufgabe 7 fand vier Lücken gegen den eigenen Exportvertrag — synthetische
  Proben liefen ungefiltert in den Export, ein Absturz zwischen
  `sample.json`-Schreiben und `rename()` hätte ein liegen gebliebenes
  Temp-Verzeichnis als fertige Probe (sogar als möglichen Gruppenvertreter im
  Export) mitgezählt, `identity_evidence` fehlte vollständig, und das
  64-MiB-Aufnahmebudget zählte fälschlich auch bereits gespeicherte Aufnahmen
  mit. Alle vier behoben, sechs neue Tests, siehe CHANGELOG.

## Verifiziert

```text
./.venv/bin/pytest -q                                      291 passed, 2 skipped
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

## Tatsächlich offene Abnahmen (Stand 2026-09-18-Sitzung, weiterhin gültig)

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

## Sammelmodus-UX vereinfacht (2026-09-21)

Nutzerrückmeldung nach erstem Kontakt mit der Oberfläche: "die oberfläche zum
datensatz aufnehmen ist zu unverständlich und umständlich". Ursache (im Code
bestätigt): es gab **keine Möglichkeit, ein bereits angelegtes Gerät
auszuwählen** — die Oberfläche zeigte nur ein "neues Gerät anlegen"-Formular,
was nach einem Neuladen faktisch zwang, Geräte neu anzulegen. Dazu standen
Geräteformular, Situationsformular, Aufnahmeknopf, Label-Editor und Export
alle undifferenziert flach untereinander, ohne Hinweis, welcher Schritt
gerade dran ist.

Umgesetzt wie im zuvor abgestimmten Bounded-Design:

1. Neuer Read-Endpunkt `DatasetStore.list_devices()` +
   `dataset.device.list`-Kommando (analog zu `summary()`), sortiert nach
   Anzeigename, inklusive der Situationsgruppen je Gerät.
2. Schrittgesteuerte Oberfläche (`static/dataset.js`, `static/index.html`)
   statt flacher Liste: drei Karten, nur die aktuelle aufgeklappt, erledigte
   klappen zu einer Einzeiler-Zusammenfassung mit "ändern"-Knopf zusammen.
   Schritt 1 (Gerät) per `<select>`, letzte Option öffnet das bestehende
   "neues Gerät"-Formular. Schritt 2 (Situation) zeigt vorhandene Situationen
   zum Fortsetzen plus "neue Situation"; bei genau einer vorhandenen
   Situation automatisch übersprungen. Schritt 3 (Aufnahme) ist unverändert
   in der Mechanik, aber einzig sichtbar sobald Gerät+Situation gewählt sind,
   mit Kopfzeile "Gerät: X · Situation: Y".
3. Echte `<label>`s statt reiner Platzhaltertexte; Modell/Familie/Technologie
   wandern im Geräteformular hinter ein `<details>` "Weitere Angaben".
4. Export unverändert als feste Zeile am Ende.

Ändert keinen bestehenden Kommando-/Endpunktvertrag außer der einen neuen
Leseoperation — reine UI-Restrukturierung. Die Schrittentscheidung "genau
eine Situation → automatisch fortsetzen" wurde als reine Funktion
`chooseInitialGroup` extrahiert und in `tests/dataset_client.test.mjs`
getestet (0/1/mehrere Situationen), statt nur im ungetesteten DOM-Code zu
stecken. Verifiziert: `./.venv/bin/pytest -q` (295 passed), `ruff check`
(all checks passed), `node --check` auf `dataset.js`/`workbench.js`,
`node tests/dataset_client.test.mjs` (alle Prüfungen bestanden), sowie ein
neuer HTTP-Test, dass `/command` mit `dataset.device.list` tatsächlich eine
JSON-Liste liefert (nicht nur ein Dict wie die übrigen `dataset.*`-Befehle).
**Nicht verifiziert:** ein echter interaktiver Klick-Durchlauf im Browser —
dieselbe Ursache wie OQ-21/OQ-34, die DOM-Verdrahtung (Sichtbarkeit,
Button-Handler) bleibt insofern ungetestet gegenüber echtem
Bedienerverhalten. **Genau dieser blinde Fleck hat den nächsten Fund
verursacht** (siehe unten) — die neue Schrittoberfläche selbst war nicht das
Problem, aber sie hat den Nutzer zum ersten Mal wirklich sammeln lassen, und
erst dabei ist der Exportfehler aufgefallen.

## Vertreterauswahl fehlte in der Oberfläche (2026-09-21, direkt danach)

Der Nutzer hat nach der UX-Vereinfachung tatsächlich gesammelt: zwei Geräte,
5 Situationen, 46 reale Proben. **„Prüfsatz exportieren" lieferte trotzdem
0 Bilder.**

**Ursache:** `DatasetStore._export_locked()` schließt eine Situation mit
mehr als einer Probe komplett aus, solange keine davon ausdrücklich als
Vertreter markiert ist (Grund `group_without_selection` — verhindert, dass
zufällig eine von mehreren Wiederholungen automatisch "die" Probe wird). Das
dafür nötige Backend (`DatasetStore.select_sample`/`dataset.select`) gibt es
seit Aufgabe 5 (2026-09-18) — es wurde aber **nie mit einem Knopf in der
Oberfläche verdrahtet**, in keiner der bisherigen Sitzungen. Jede Situation
mit mehr als einer Aufnahme war seit Einführung des Sammelmodus faktisch
nicht exportierbar, das ist erst jetzt beim ersten echten Mehrfach-Sammeln
aufgefallen.

**Behoben (Phase 1, mit Nutzer abgestimmt):** Neue Zeile "als Vertreter
dieser Situation markieren" direkt nach "Speichern und weiter" in Schritt 3
(`static/dataset.js`, `static/index.html`), ruft den bestehenden
`dataset.select`-Befehl für die soeben gespeicherte Probe auf. Bewusst
minimal — markiert nur die zuletzt gespeicherte Probe, keine nachträgliche
Auswahl älterer Proben. Neuer HTTP-Test
`test_marking_a_sample_as_representative_makes_the_group_exportable`
belegt: ohne Auswahl 0 exportierte Bilder, nach `dataset.select` 1.
`296 passed`, `ruff check` sauber, `node --check`/`dataset_client.test.mjs`
unverändert grün.

**Phase 2, vom Nutzer bewusst vertagt statt jetzt mitgebaut:** eine
Übersicht/Galerie je Situation, in der auch ältere Proben nachträglich als
Vertreter markiert werden können, inklusive einer Ansicht des
Entwicklungs-/Abschlusstestbestands mit der Möglichkeit, Proben zwischen
beiden zu verschieben, falls nötig. Noch nicht begonnen.

**Für den Nutzer wichtig, sofort:** die bereits vor diesem Fix gespeicherten
46 Proben sind weiterhin vorhanden, aber in ihren jeweiligen Situationen
weiterhin ohne Vertreter (der neue Knopf wirkt nur auf künftige Speicherungen).
Um eine bestehende Situation exportierbar zu machen, muss aktuell noch
einmal in dieser Situation aufgenommen und gespeichert werden, dann direkt
per neuem Knopf als Vertreter markiert — bis Phase 2 (Galerie) eine
rückwirkende Auswahl erlaubt.

**Nachschliff, unmittelbar danach:** Nutzerbefund "ich kann in dispread
keinen 'Vertreter' für eine Situation festlegen" — der neue Knopf war real
unsichtbar. Ursache: `#dataset-representative` war im Markup als Kind von
`#dataset-editor` verschachtelt; `afterSave()` versteckt `#dataset-editor`,
bevor es den Vertreter-Knopf einblenden will — ein versteckter Vorfahre
blendet aber jedes Kind mit aus, egal was dessen eigenes `hidden`-Attribut
sagt. Der Knopf existierte im DOM, die Logik (inkl. `dataset.select`-Aufruf)
lief korrekt, er war nur nicht sichtbar. Behoben: als Geschwister von
`#dataset-editor` verschoben. Neue Struktur-Prüfung in
`tests/dataset_client.test.mjs` (am alten, fehlerhaften Markup verifiziert,
dass sie tatsächlich anschlägt) — keiner der vorherigen JS- oder
HTTP-Tests hätte das auffangen können, da keiner tatsächliche
DOM-Sichtbarkeit prüft.

## Serve liess sich nicht beenden (2026-09-21, dritter Fund dieser Sitzung)

Nutzerbefund: `dispread serve` reagierte auf kein Strg+C mehr — auch nach
vielen Versuchen. Live-Diagnose am tatsächlich hängenden Prozess auf dem Pi
(`/proc`-Thread-Zustände, `gdb`, `py-spy`, siehe unten für die Beweisketten)
ergab: **kein Kamera-/OQ-22-Problem.** Alle Threads standen im Zustand `S`
(unterbrechbar), keiner in `D` — SIGINT wurde korrekt verarbeitet, `serve()`
lief bis zum Ende der eigenen `finally`-Kette vollständig durch (HTTPS-Port
7777 bereits geschlossen, `py-spy dump` zeigte den Hauptthread schon in
`threading._shutdown`/`concurrent.futures.thread._python_exit`) — der
Prozess blieb trotzdem für immer hängen, weit außerhalb von `serve()` selbst.

**Ursache:** Nebenläufigkeitslücke, nicht Hardware. Die alte Reihenfolge in
`serve()`s `finally`-Block schloss `terminals.close()` **vor**
`runner.cleanup()`/`unix.cleanup()` ab. Solange der HTTPS-Server (bzw. der
lokale Steuersocket) noch Verbindungen annahm, konnte zwischen dem Setzen
von `stop` und diesem Zeitpunkt ein neues `POST /terminals` (eine über die
Werkbank-Oberfläche angelegte Shell) `terminals.close()` entgehen. Deren
Reap-Task (`asyncio.to_thread(subprocess.wait)`) blockierte dauerhaft einen
Worker-Thread des asyncio-Default-Executors — und genau den joint
`asyncio.run()` bei seinem eigenen, nicht unterbrechbaren Abbau, lange nachdem
`serve()` selbst schon zurückgekehrt und der Signal-Handler damit weg war.
Jedes weitere Strg+C traf ins Leere, weil zu diesem Zeitpunkt gar kein
Event-Loop mit Signal-Handler mehr existierte.

**Behoben:** `finally`-Block in `src/dispread/workbench/server.py` ruft
jetzt `runner.cleanup()`/`unix.cleanup()` (stoppt beide
Verbindungsannahmen) **vor** `terminals.close()`. Neuer Test
`test_serve_stops_accepting_connections_before_closing_terminals`
(`tests/test_workbench.py`) prüft die Reihenfolge end-to-end gegen den
echten `serve()`-Ablauf, deterministisch über den lokalen Steuersocket
(`server.stop`) statt über ein zeitlich unzuverlässiges HTTP-Rennen.

**Der zuvor hängende Prozess auf dem Lab-Pi** wurde risikofrei mit
`SIGKILL` beendet, nachdem bestätigt war, dass alle eigenen Aufräumschritte
(`runner.cleanup`/`terminals.close`/`controller.close`/Socket- und
Lock-Datei) bereits vollständig durchgelaufen waren — Port 7777 war schon
frei, kein Kamerathread mehr aktiv, kein `D`-Zustand. Kein Datenverlust
möglich, da die eigentliche Aufräumarbeit der Anwendung längst erledigt war;
nur die Python-interne Executor-Verwaltung hing noch.

## Nächste Schritte

1. **Phase 2 der Vertreterauswahl:** Übersicht/Galerie je Situation zum
   nachträglichen Markieren älterer Proben, plus eine Ansicht des
   Entwicklungs-/Abschlusstestbestands mit Verschiebemöglichkeit — vom
   Nutzer für diese Sitzung bewusst vertagt, aber die aktuell direkteste
   Möglichkeit, echten Sammelfortschritt zu machen.
2. Fehlende Bedingungen an den bestehenden Geräten nachholen (aktuell
   overall fehlend: `multiline`; je Gerät auch `decimal`/`negative` bzw.
   `angled`/`dim`/`distance` — siehe `dataset.summary()`).
3. Mehr Geräte mit unterschiedlicher Familie/Technologie anlegen (aktuell
   nur `gsva`/`BK_Precision`, beide LED) — die Exportziele verlangen
   mindestens 6 verifizierte Geräte, 3 Familien, LED **und** LCD.
4. Split bewusst wählen: aktuell stehen beide Geräte auf „Entwicklung" —
   für das 30-Situationen-Abschlusstestziel braucht es Geräte mit Split
   `heldout`, festgelegt **vor** der ersten Aufnahme.
5. **Reale Browserabnahme der Schrittoberfläche** (OQ-34/OQ-21) —
   insbesondere: Gerät aus der Liste wählen nach Neuladen, Situationsauswahl
   bei mehreren vorhandenen Situationen, automatisches Überspringen bei
   genau einer Situation, "ändern"-Knöpfe, neuer "als Vertreter
   markieren"-Knopf.
