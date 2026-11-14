# Raster-Baseline (offline, 2026-11-13)

Archivierter Vorbereitungsbericht: die damaligen Scratch-Pfade, Logdateien und Reproduktionsbefehle beschreiben den Ursprungslauf und sind nicht die heutige Schnittstelle. Aktuelle Befehle und die verpflichtende Codehash-Prüfung stehen in der benachbarten README. Ergebnisdateien und Manifest liegen hier; die Originalausgabe wurde nicht verändert.

Auswertung abgeschlossen; siehe `run-0.log` bis `run-2.log` und `results.jsonl` und `baseline-shard-*.jsonl`. Keine Hardware oder Dienste benutzt, `var` und Entwicklungsmedium nur gelesen. Die vollständige Inventur `manifest.jsonl` verzeichnet jeden Bildpfad, Bildgröße, Bild-SHA-256 und SHA-256 der jeweils danebenliegenden `cell-text.json`. Vor Variantenlauf Manifest unverändert halten und Hashes überprüfen.

## Korpus

74 `var/live/*/setup/still*.png`, davon genau 65 bis einschließlich `live-20261113T130253Z` (Handoff-Korpus) und neun spätere Dateien. Zusätzlich 16 Dateien aus `/mnt/ssd/picam-dev/regression/2026-11-11` für OQ-69: alle 16 sind mit je einem Bild und der jeweiligen Textdatei unter `var/live` bytegleich (SHA-256). Insgesamt 90 Pfade, 74 verschiedene Bilder. `stability.png` ist nicht Bestandteil des Korpus; nummerierte `still-versuch-N.png` schon. Keine frühere, nicht gespeicherte Versuchsbilder hinzuerfinden.

## Verfahren

`evaluate.py` verwendet `find_green_hint_box`, `fit_lattice(..., empty_cells=(8,13,14,15))`, speichert Hinweisbox, vollständige Fit-Kennzahlen und Quad oder den finalen Ablehnungsgrund. Ein serieller Text wird nur dem passenden Versuch zugeordnet: `still-versuch-N.png` zu Versuch N, `still.png` zum letzten Versuch. Das folgt `_keep_attempt_still` in `src/dispread/live/setup.py`. Bei vollständigem seriellen Text wird ergänzend `raster_offset_check` protokolliert. Texte sind Prüfbelege, keine Korrektur oder DUT-Ausgabe. Die Liste `manifest.jsonl` enthält Hashes, die Ergebniszeilen zusätzlich den Bildhash und das ausgewählte Label. Ergebnisse enthalten keine internen abgelehnten Startkandidaten: Ablehnungsgrund ist das Endergebnis von `fit_lattice`.

Code-Stand `fab15a93f0f2300fb8a4d8ca7c9a0e605e3236f5`; der geladene `dotlattice.py`-SHA-256 ist `a76963dc6965a11227229299d8da8137d1ec5f2f380205dcb8ffde5a9caa2841`, `setup_hint.py` `c753a4468abc7230333f3321568fd5b1c3aeb0f21adfa027d9054e2381feeb32`, `setup_checks.py` `22696f6b660bca71c6a87b24debd07accd8b262ed17cb8e0fbae70895ee2091f`. In `dispread/` liegt die eingefrorene Scratch-Kopie. Erste fünf Zeilen `results.jsonl` entstanden vor der Aufteilung; die übrigen verteilt auf drei Shards, jeweils OpenCV mit einem Thread. Alle 90 Pfade sind vorhanden; 16 Duplikate wurden anhand identischer Bild- und Textdateihashes übernommen.

## Unabhängige Prüfung neuer Fits

Für jedes neue Quad Bild und zugehörigen seriellen Versuchstext heranziehen. `raster_offset_check([(image, text)], quad)` liefert unabhängige ROM-Punktversätze, Abdeckung und Status. Zusätzlich `diagnose_reader` wie in `tests/test_dotlattice_setup_2026_11_11.py` auf Widersprüche prüfen und Zellzuordnung sowie einzelne Punktspalten im Originalbild/Overlay gegen den Text kontrollieren; ein Versatz um eine ganze Zelle oder eine Punktspalte darf nicht als korrekt gelten. Die Offsetprüfung allein ist kein Beweis für die gesamte Zeichenzuordnung; Warnung, fehlende Abdeckung, `?`, fehlender oder nicht-serieller Text bleiben ungeprüft. Wo keine solche Prüfung möglich ist, höchstens als plausibel kennzeichnen und nicht als richtig zählen. Eine bestätigte Voraufnahme derselben unveränderten Aufstellung kann zusätzlich als Geometrieanker dienen, muss aber mit Herkunft und Bewegungsvorbehalt benannt werden; ein neuer Fit selbst ist keine unabhängige Sollgeometrie.

OQ-69-Tests dokumentieren vier seriell gegengelesene Referenzquads (`154403Z`, `154459Z`, `155404Z`, `162902Z`) sowie Vergleichsfälle. Für die drei `130253Z`-Bilder ist laut Recherche `121656Z` derselben Aufstellung ein zusätzlicher Referenzanker; keine ergebnisabgeleitete Sollgeometrie behaupten. Die beiden bestehenden Fits `20261026T082712Z` und `20261026T083418Z` sind Gegenproben für B1; deren Erhalt mit tatsächlichem Quadabstand prüfen. Für A1 echte belegte Leerzellen als Negativfälle aus `tests/test_dotlattice.py` erneut prüfen. Vorhandene Fits werden paarweise anhand maximalen euklidischen Eckabstands verglichen; >1 px ist gesondert zu untersuchen. A1, B1 und A1+B1 getrennt auswerten.

## Reproduktion und Varianten

Für einen frischen Lauf der eingefrorenen Baseline aus dem Worktree (Dateinamen mit eindeutigem Variantennamen; je Shard einmal, nacheinander oder parallel):

```bash
RASTER_VARIANT=baseline_neu RASTER_SHARD=0 RASTER_SHARDS=3 PYTHONPATH=.superpowers/sdd/2026-11-13-codex-rahmen-raster/raster-baseline DISPREAD_DEV_DATA=/mnt/ssd/picam-dev ./.venv/bin/python .superpowers/sdd/2026-11-13-codex-rahmen-raster/raster-baseline/evaluate.py
# Ebenso RASTER_SHARD=1 und =2.
```

Für eine Variante vor dem Start eine eigene, unveränderliche Kopie von `src/dispread` im Scratch-Verzeichnis anlegen, diese Kopie als `PYTHONPATH` verwenden, eigenen `RASTER_VARIANT` setzen und den Quell-Hash jeder Ergebniszeile prüfen. Pro Shard werden fertige Pfade wiederverwendet; bei anderer Hypothese stets einen neuen Variantennamen verwenden. `compare.py '.../results.jsonl,.../baseline-shard-*.jsonl' '.../a1-shard-*.jsonl'` verlangt identische Pfade, Bildhashes und ausgewählte Labels; es meldet Eckabstände und markiert neue Fits zur unabhängigen Prüfung. Da die aktuelle Ausgangsauswertung noch die älteren Namen `results.jsonl` und `baseline-shard-*.jsonl` nutzt, diese beim Vergleich als Baseline angeben. Das Skript identifiziert keine richtige Geometrie und ersetzt die Wahrheitsprüfung nicht. Bei Unterbrechung denselben Variantennamen und dieselbe Shardzahl verwenden; schon bestehende `results.jsonl` wird bei der Baseline ebenfalls berücksichtigt. Der Evaluator prüft Bild- und Textdateihash gegen das Manifest.

Die laufende Baseline speichert Offsetprüfungen für verfügbare vollständige serielle Labels. Bei neuen Varianten ist diese teure Prüfung im Evaluator standardmäßig aus; `RASTER_CHECK_OFFSET=1` schaltet sie ein. Bereits geprüfte unveränderte Fits übernehmen den Baseline-Befund. Neue oder verschobene Fits danach gezielt unabhängig prüfen; keine vollständige Offset-/Reader-Auswertung aller alten Fits wiederholen.

`check_truth.py RESULTS_JSONL PFADFRAGMENT...` führt Offset- und Readerprüfung gezielt auf bereits gespeicherten Quads aus, ohne Fits zu wiederholen. Es prüft den Bildhash vor der Auswertung und weist unvollständige oder fehlende serielle Labels als ungeprüft aus. Vergleichs- und Prüfergebnisse erfordern weiterhin Sichtprüfung der Zell- und Punktzuordnung; Textdateihash gegen Manifest prüfen.

Bytegleiche Bilder mit bytegleichen Zellentextdateien werden shardübergreifend wiederverwendet; `reused_from` nennt den ursprünglichen Pfad. Varianten erhalten jeweils ihren eigenen Cache. Laufzeitumgebung: Python 3.13.5, OpenCV 4.10.0, NumPy 2.2.4.

## Ergebnis der Baseline

Der Lauf beendete sich mit Exit-Code 0; Ergebnismenge und Manifest enthalten exakt dieselben 90 eindeutigen Pfade, 16 mit ausgewiesener Cache-Herkunft. `compare.py` wurde auf dem Teilbestand gegen sich selbst geprüft; `check_truth.py` lieferte für `20261023T123820Z` Offset `OK` und Reader `OK`.

| Umfang | Fits | `keine_startlage` | `startlage_mehrdeutig` |
| --- | ---: | ---: | ---: |
| 65 ursprüngliche Stillbilder | 58 | 6 | 1 |
| 74 aktuelle Stillbilder | 64 | 9 | 1 |
| 16 OQ-69-Pfade (Duplikate) | 16 | 0 | 0 |
| 90 Pfade insgesamt | 80 | 9 | 1 |

Unter den ursprünglichen 65 sind die drei `130253Z`-Bilder, `115232Z/still-versuch-1`, `121656Z/still-versuch-1` und `20261026T083033Z/still.png` als `keine_startlage` abgelehnt; `20261023T123623Z/still.png` ist mehrdeutig. Im später hinzugekommenen Bestand werden `132755Z/still-versuch-1`, `132755Z/still-versuch-2` und `142321Z/still-versuch-1` abgelehnt. Die Rohzeilen enthalten die genauen Quads und Qualitätswerte sämtlicher Fits.

Über alle 90 Pfade (einschließlich Duplikate und Ablehnungen) wurden 48 Offsetprüfungen `OK`, acht `WARNUNG` und 34 nicht ausgeführt; letzteres schließt sämtliche Ablehnungen und unvollständige oder fehlende serielle Labels ein. Das ist keine Erfolgsquote für Wahrheit. Vier der OQ-69-Pfade tragen `?` im seriellen Maskentext und wurden hier vorsichtig nicht automatisch geprüft. Für die 16 OQ-Pfade gab es elf `OK`, eine `WARNUNG` und vier nicht ausgeführte Offsetprüfungen.

Die beiden kritischen 26.10.-Fälle liefern Baseline-Fits; `082712Z` hat Offset `WARNUNG`, `083418Z` kein hier automatisch geprüftes vollständiges Textlabel. `121656Z/still.png` hat ebenfalls Offset `WARNUNG`. Die Fitquads sind Vergleichswerte für Verschiebung und keinesfalls unabhängig gewonnene Sollgeometrien. Ein Bild mit Warnung oder fehlendem Text wird nicht automatisch als geometrisch korrekt zertifiziert.
