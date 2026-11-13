# Rahmenprüfung und Rasterbestimmung — Codex-Bericht

Stand: 2026-11-13. **Aufgaben 1–3 umgesetzt, offline geprüft und jeweils von Astra ohne offene Befunde freigegeben.**

Auftrag: Aufgaben 1–3 aus dem [Handoff](../../superpowers/handoffs/2026-11-13-codex-rahmen-raster.md).
Implementierung durch Codex-Subagenten, Aufgabenreviews durch Astra mit Reasoning `high`.
Arbeitszweig `fix/rahmen-raster`, Ausgangsstand `fab15a93f0f2300fb8a4d8ca7c9a0e605e3236f5`.
Änderungen bleiben uncommittiert im Worktree. Kamera, laufender Werkbankdienst,
andere Worktrees und die Eingabedaten wurden nicht verändert.

## Aufgabe 1 — Fokuszustand und Nachführdiagnose

**Umgesetzt und von Astra ohne offene Befunde freigegeben.**

- Reale Laufstarts prüfen die Schärfe nach dem Kameraneustart zweiseitig gegen
  die Einrichtungsreferenz. Das vorläufige Band beträgt 0,95–1,05.
  Fehlende oder ungültige Referenzen, Prüffehler und verbleibende Abweichungen
  lehnen den Start mit Bedienermeldung ab.
- Erfolgreiche Vergleiche sind ebenfalls im Status und Inspektor sichtbar.
  Abgelehnte Starts erhalten einen eigenen abgeschlossenen Auditvertrag
  `live-start-rejection/1`; die Aufbewahrung erkennt ihn, der Wiki-Importer
  überspringt ihn ausdrücklich. Ein späterer erfolgreicher Start oder eine neue
  Einrichtung erledigt den aktiven Warnhinweis, das Audit bleibt erhalten.
- Zweitversuchsanteil und Maßstabsstatistik erscheinen in Status und
  `session.json`. Zähler und Nenner beziehen sich auf dieselben
  Tracking-Beobachtungen, auch bei einem Auditfehler. Das Maßstabsfenster ist auf
  die letzten 10.000 Zweitfits begrenzt und mit Stichproben- und Gesamtzahl benannt.
- Die Residualgrenzen 0,35/0,65 px und die Tracking-Entscheidungen bleiben
  unverändert. Keine Ausreißerverwerfung, kein Halten einer ungeprüften Lage.

| Offline-Replay | Diagnosebilder | Zweitfits | Median Maßstab | Abweichungen vom gespeicherten Urteil |
| --- | ---: | ---: | ---: | ---: |
| 11.11., `103604Z` | 222 | 134 | 0,999769 | 0 |
| 11.11., `122753Z` | 222 | 143 | 1,000126 | 0 |
| 13.11., `113119Z` | 216 | 216 | 1,001807 | 0 |

Die Diagnosebilder sind an Zustandswechseln ausgewählt, keine repräsentative
Stichprobe aller Laufbilder. Die 14 auswertbaren Fokusstarts vom 13.11. zeigen
nahe 1,0 Endverhältnisse von 0,982–1,026; die Problemfälle liegen bei 0,650 und
1,397. Ein erfolgreicher Lauf bei 1,418 zeigt ausdrücklich, dass das neue Band
auch gute Starts sperren kann. In 52 Entwicklungsarchiv-Sessions fehlten
vergleichbare gespeicherte Fokusstartwerte. **Das Band ist ein konservativer
Gleichheitsfilter, keine Hardwarekalibrierung und kein Kausalnachweis für
Fokusatmung. OQ-74 bleibt offen.**

Geänderte Produktdateien: `live/setup.py`, `live/service.py`, `live/session.py`,
`workbench/static/live/run/inspector.js` und `alerts.js` unter `src/dispread/`,
sowie `scripts/wiki_sessions.py`. Außerdem wurden `tests/live_ui_server.py` und die Golden-Datei
`tests/fixtures/live_output_disabled/session.json` an die Diagnosefelder angepasst;
bytegenaue Ausgabeprüfungen bleiben erhalten. Dazu Regressionen für Setup, Dienst,
Trackingstatistik, Aufbewahrung, Import und Browserstatus.

Prüfbelege: 333 Service-/Storage-/Importertests bestanden; zusätzliche gezielte
Fokus-, Statistik- und Statusübergangstests sowie die 216-Bilder-Regression
bestanden. Der integrierte Browsercheck bestand mit 289 Node-Tests und drei
Python-Tests für den gesonderten Workbench-Harness.

[Replay, Rohzahlen und Quellenhashes](../../quellen/nachfuehrung-recherche-2026-11-13/README.md) ·
[Astra-Freigabe Aufgabe 1](reviews/task-1-astra-final.md).

## Aufgabe 2 — Leerzellengrenze A1

**Umgesetzt und von Astra ohne offene Befunde freigegeben.**

`src/dispread/dotlattice.py` zählt Randminima im letzten Viertel eines
Punktspaltenabstands vor der Nachbarzelle nicht mehr als Leerzellenbelegung.
Die beobachteten Randminima liegen lediglich 0,01–0,04 Spalten vor der Grenze.
Regulär zugeordnete Leerzellenpunkte und die Mitte der Lückenspalte bleiben
geprüft; die Gegenprobe mit belegter Spalte 5 bleibt abgelehnt.
Die Unterkantenbehandlung wurde in dieser Variante nicht verändert.

| Bestand | Baseline: Fits | Nur A1: Fits |
| --- | ---: | ---: |
| Ursprüngliche 65 Standbilder | 58 | 61 |
| Erweiterter Bestand mit 74 Standbildern | 64 | 69 |
| 16 OQ-69-Pfade, identische Bild-/Textduplikate | 16 | 16 |

Alle 80 vorher erfolgreichen Pfade bleiben erfolgreich. Der maximale
Eckabstand beträgt 0,5224298058 px bei `121656Z/still.png`; die übrigen 79 Fits
sind exakt unverändert. Die fünf neuen Fits wurden einzeln gegen den zugehörigen
seriellen Versuchstext, den Leser und sichtgeprüfte Zell-/Punkt-Overlays geprüft.
Dabei wurde kein falscher neuer Fit im geprüften Korpus festgestellt.
Ihre ROM-Offsetwarnungen von 0,154–0,206 Spalten bleiben erhalten; das ist keine
allgemeine Geräte- oder Messfreigabe.

Im ursprünglichen Korpus entstehen drei neue Fits; zwei weitere stammen aus
späteren Bildern. Die frühere pauschale Angabe „+5“ gilt daher nicht für A1
allein im ursprünglichen 65er-Bestand. `115232Z/still-versuch-1` und
`130253Z/still.png` brauchen zusätzlich die Unterkantenkorrektur.

Geändert: `dotlattice.py`, `tests/test_dotlattice_setup_2026_11_13.py`,
`tests/test_raster_corpus_preflight.py` und das dauerhafte Belegpaket.
Die neuen Bildregressionen bestanden mit 5 Tests, die gesonderte OQ-69-Datei
mit 17 Tests und die Evaluator-Regressionen mit 9 Tests. Ein vorheriger
kombinierter 70-Test-Lauf endete ohne Abschlussnachweis und wird ausdrücklich
nicht als bestanden gezählt.

Die Auswertung prüft Quellhash, vollständigen Manifestbestand und sämtliche
Bild-/Textdateihashes vor Resume und Shardfilter. Cache-Ergebnisse eines anderen
Quellstands werden abgelehnt. Ein früherer Variantenlauf hatte durch den
Python-Suchpfad versehentlich die Baseline geladen; seine Ergebnisse wurden
verworfen. Astra hat die gültigen 90 Eingabepfade, Hashes, Ergebnisse und sechs
Overlays unabhängig geprüft.

[Korpus, Reproduktion und Einzelbelege](../../quellen/raster-recherche-2026-11-13/korpus/README.md) ·
[Astra-Freigabe Aufgabe 2](reviews/task-2-astra-final.md).

## Aufgabe 3 — Unterkantenannahme B1

**Umgesetzt und von Astra einschließlich Tests und vollständiger Offline-Evidenz
ohne offene Befunde freigegeben.**

Nach drei tatsächlichen `keine_startlage`-Ergebnissen der ursprünglichen Suche
wird bei unterschiedlichen Hough-Richtungen eine zweite Unterkantenannahme mit
unveränderten Fit- und Eindeutigkeitsprüfungen versucht. Bestehende Fits,
Mehrdeutigkeiten und andere Ablehnungen werden nicht überschrieben. Einfache
Neigungs-, Längen- oder Lagegrenzen trennen die Problemfälle nicht von den beiden
bisher erfolgreichen Gegenproben vom 26.10. Eine pauschale Gleichsetzung von
Ober- und Unterkante sowie eine unbedingte doppelte Suche wurden verworfen.

Die begrenzte Suche prüft bei einem bereits erfolgreichen ersten Fit keine
konkurrierende alternative Lage. Das ist eine dokumentierte Einschränkung,
kein Beweis globaler Eindeutigkeit. Die Abnahmeprüfungen bleiben unverändert.

| Bestand | Baseline | Nur B1 | Nur A1 | A1+B1 |
| --- | ---: | ---: | ---: | ---: |
| Ursprüngliche 65 Standbilder | 58 | 59 | 61 | 63 |
| Erweiterter Bestand mit 74 Standbildern | 64 | 66 | 69 | 72 |
| Alle 90 Pfade einschließlich 16 Duplikaten | 80 | 82 | 85 | 88 |

Kein bisheriger Fit geht verloren. Die maximale Eckverschiebung gegen Baseline
beträgt für B1 0 px, für A1+B1 0,5224298058 px. Die beiden Gegenproben vom 26.10.
bleiben exakt erhalten. Gegen A1 sind sämtliche bereits erfolgreichen Quads
exakt identisch; damit bleiben die fünf A1-Einzelgegenprüfungen anwendbar.

Die drei zusätzlichen Fits gegenüber A1 wurden separat geprüft:

| Bild | Serieller Text | Leser | ROM-Offset | Sichtprüfung |
| --- | --- | --- | --- | --- |
| `115232Z/still-versuch-1` | `+0.70502` | OK | OK, max. 0,13079 Spalten | Zell-/Punktlage passend |
| `142321Z/still-versuch-1` | `+0.60297` | OK | OK, max. 0,06445 Spalten | Zell-/Punktlage passend |
| `130253Z/still.png` | `+0.62969` | OK | **WARNUNG**, max. 0,18066 Spalten | Zell-/Punktlage passend |

Die ersten beiden Fits entstehen auch mit B1 allein und sind quadidentisch zur
Kombination. Die Offsetwarnung des dritten bleibt erhalten. Insgesamt wurde
unter den acht neuen Fits gegenüber Baseline keine falsche Zell- oder
Punktspaltenlage festgestellt; sechs tragen weiterhin eine Offsetwarnung.
Eine fehlende Startlage und eine Mehrdeutigkeit bleiben abgelehnt.

Geändert: `src/dispread/dotlattice.py`,
`tests/test_dotlattice_setup_2026_11_13.py`,
`tests/test_dotlattice_start_bench.py` und das Korpus-/Recherchepaket.
Die beiden Problemfälle wurden rot/grün geprüft; zwei Oktober-Gegenproben,
18 Ablauf-/Ablehnungstests und sechs zusätzliche Guard-/Zweitlauf-Fälle bestanden.
Die sechs nach der Gesamtsuite-Sammlung ergänzten Fälle wurden separat geprüft.

Beide Varianten enthalten vollständig je 90 Ergebniszeilen mit geprüften
Eingabe-, Label- und Quellhashes sowie Vergleichsdateien. Die sechs
Auswertungsprozesse wurden zur Entlastung der Gesamtsuite angehalten und wieder
fortgesetzt. Der Sammelshell-Warteprozess meldete dabei **Exit 143**, nicht 0.
Die vollständig vorliegenden 180 Ergebniszeilen und fehlerfreien Shardlogs sind
getrennte, unabhängig nachprüfbare Evidenz. Alle sechs Prozesse sind beendet.
Die Auswertungsdauer unter Parallelbelastung ist keine Performancemessung.

[Korpus, Vergleiche und Overlays](../../quellen/raster-recherche-2026-11-13/korpus/README.md) ·
[Astra-Freigabe Aufgabe 3](reviews/task-3-astra-final.md).

## Gesamtprüfung

Die vollständige Suite wurde einmal ausgeführt:

```bash
PYTHONPATH=src DISPREAD_DEV_DATA=/mnt/ssd/picam-dev ./.venv/bin/pytest -q -n 4
```

Ergebnis: **4219 bestanden, 6 fehlgeschlagen, 20 übersprungen, 2 xfailed**,
Exit 1. Der Lauf wird nicht nachträglich als insgesamt grün bezeichnet.

- Vier Fehler betrafen veraltete Fake-/Golden-Diagnosefelder. Sie sind korrigiert;
  alle vier betroffenen Fälle und vier Nachbartests bestehen. Astra hat den
  Nachtrag freigegeben und unveränderte bytegenaue Records-/Session-/No-TX-
  Prüfungen bestätigt.
- Zwei Tests scheiterten an Wanduhrgrenzen bei paralleler Last (Lesersweep
  30 s, UART-Leseprüfung 0,25 s). Nach Ende der Bildjobs bestanden beide isoliert:
  **2 bestanden in 11,70 s, Exit 0**. Tests und Grenzen blieben unverändert.
  Diese Fehler werden nicht als Sandboxfehler bezeichnet.
- Browserlogik: **289 Node-Tests bestanden**, dazu **3 Python-Tests** für den
  Workbench-Harness. Ein erster pauschaler Node-Aufruf hatte diesen separaten
  Harness ohne dessen notwendige Fixture aufgerufen; die korrekte getrennte
  Ausführung ist grün.
- `PYTHONPATH=src ./.venv/bin/ruff check src tests`: auch nach den ergänzten
  Testdateien bestanden. `git diff --check` und OQ-Indexprüfung sind sauber.
- `PYTHONPATH=src ./scripts/docs-site.sh build -s`: auch nach den letzten
  Text-/Verweiskorrekturen bestanden, Exit 0, „No issues found“.
- `CI=1 PATH="$PWD/.venv/bin:$PATH" npx playwright test -c playwright.docs.config.ts`:
  **91 bestanden**, Exit 0. Die anschließend präzisierten Quellenbeschriftungen
  und Verweise wurden mit dem erneuten strikten Build geprüft; Website-Logik
  und Gestaltung blieben unverändert.
- Astra-Gesamtreview: [abschließendes Reviewprotokoll](reviews/final-astra-review.md).
  Die vier Präzisierungen aus diesem Review sind umgesetzt: Erklärung der
  zweiseitigen Schärfereferenz, tatsächliche Bilddateinamen, abgeschlossene
  Auswertung und spätere statt frühere Vergleichsaufnahme. Zwei zugehörige
  Tests sowie Ruff und Diffprüfung bestanden; Zahlen und Verhalten sind
  unverändert.

Die Logs liegen (lokal auf dem Pi, nicht versioniert) unter `.superpowers/sdd/2026-11-13-codex-rahmen-raster/validation/`
(`full-pytest.log`, `isolated-time-checks.log`, `docs-playwright.log`,
`docs-build-verified.log`, `ruff-verified.log`). Arbeits- und Reviewbelege bleiben
im Worktree erhalten, weil es für diese Übergabe ausdrücklich keinen Commit gibt.
Details zum kleinen Testdaten-Nachtrag:
[Integrationsbericht](reviews/integration-fix-report.md),
[Astra-Freigabe](reviews/integration-astra-review.md).

## Dokumentation, offene Risiken und Übergabe

Der erste strikte Build deckte zwei bestehende Verweise auf nicht eingebundene
Windows-Seiten auf. `scripts/docs-site.sh` nimmt deshalb gezielt die beiden
referenzierten Belegseiten auf. In `windows/bridge/GSVMULTI-VERSUCHE.md` bleibt
ein im Checkout fehlender Recherchepfad als Text erhalten. Der erneute strikte
Build besteht; ein eigener CHANGELOG-Eintrag beschreibt diese Buildkorrektur.

`CHANGELOG.md`, `docs/VALIDATION.md`, `docs/lab_journal.md`,
`docs/project_history.md`, OQ-69/OQ-74 in `docs/open-questions.md`,
`docs/anleitung/10-kamera-livevorschau.md`, die beiden Recherchepakete,
`TODO.md` und `docs/status.md` sind aktualisiert. Der Status ist vollständig
neu geschrieben; historische OQ-Einträge wurden nicht gelöscht.

Offen bleiben die Hardwarekalibrierung des Fokusbands und ein kontrollierter
Versuch am Aufbau. Der Schärfequotient beweist keine Maßstabsursache, und das
vorläufige Band kann brauchbare Starts ablehnen. Die Rasterbelege gelten für den
angegebenen Korpus; erhaltene Offsetwarnungen sind keine allgemeine Freigabe.
Bei fehlender oder unlesbarer Eingabe wird weiterhin abgelehnt.

Bitte anschließend um Review durch Claude, besonders des Bedienerflusses aus
Aufgabe 1 und der unabhängigen Fitbelege aus Aufgaben 2 und 3. Die Entscheidung
über Übernahme und Hardwareabnahme bleibt bei Leonhard; es wurde nichts
committiert, deployt oder gemergt.
