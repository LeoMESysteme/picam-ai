# Task 2 A1 — abschließendes unabhängiges Review nach Fixrunde 1

Stand: 2026-11-13. Dieses Re-Review prüft ausschließlich `task-2-fix1.diff` und den ursprünglichen Befund A1-R1. Das vollständige Erstreview steht in `task-2-astra-review.md`.

**Spezifikation: MÄNGELFREI FREIGEGEBEN im geprüften Task-2-Umfang.**

**Qualität: MÄNGELFREI FREIGEGEBEN im geprüften Task-2-Umfang.**

Keine offenen Findings. A1-R1 (P2) ist behoben. Die Freigabe ist ein Code-/Evidenzreview; sie behauptet weder universelle Erkennungsfehlerfreiheit noch eine formale Kalibrierabnahme.

## Prüfung der Korrektur

`evaluate.py` gleicht vor Ausgabeöffnung und Wiederverwendung die gesamte entdeckte Pfadmenge mit dem Manifest ab. Es prüft anschließend die aktuellen Bild- und Textdateihashes jedes Pfads, unabhängig von Shardzuordnung und vorhandenen Ergebniszeilen. Damit kann weder ein fehlender Pfad noch ein bereits erledigter veränderter Eingang den bisherigen Skip umgehen.

Die Validierung gespeicherter Zeilen aller Variantenshards verlangt nun explizit den richtigen Quellhash und Manifest-Bildhash; ein Cachetreffer wird ebenfalls validiert. Abgeschnittene eigene Ausgabedateien werden abgelehnt. Die dokumentierte Behandlung einer gerade geschriebenen Schlusszeile eines anderen Shards ist vom Resume der eigenen Datei getrennt. Die README entspricht dem korrigierten Verhalten.

Die neun neuen Tests prüfen die konkrete Fehleroberfläche: fehlender und zusätzlicher Eingang, geändertes bereits erledigtes Bild/Label, falscher/fehlender Quellhash eines anderen Shards, unveränderter Resume, geänderter Eingang außerhalb des eigenen Shards und unvollständige eigene Ausgabe. Worker-/Parentnachweis: **9 passed in 11.21 s, Exit 0**, Ruff bestanden. Keine neuen Fehler im Fixdiff gefunden.

## Eigene gezielte Nachprüfung

Das echte Skript wurde mit richtigem A1-Quellhash über `runpy` ausgeführt. Eingangsabweichungen und Ausgabe wurden ausschließlich im Speicher simuliert; Fits waren durch eine sofort fehlschlagende Ersatzfunktion gesperrt.

- Leere Dateierkennung gegen echtes 90-Pfade-Manifest: ausdrücklich `manifest path mismatch`.
- Geändertes bereits erledigtes Bild: ausdrücklich `manifest mismatch`.
- Geänderte Textdatei eines bereits erledigten Bilds: ausdrücklich `manifest mismatch`.
- Unveränderter tatsächlicher A1-Resume: reguläres Ende, kein Fit, Ausgabe ausschließlich in `StringIO`.

Zusätzlich SHA-256 und Dateigrößen aller **23** im ursprünglichen Reviewdiff aufgeführten Ergebnis-, Quellen- und Bildartefakte erneut geprüft: unverändert. Die aktuelle Produktdatei ist weiterhin bytegleich mit dem bereits geprüften eingefrorenen A1-Code (`e302dc3b89ed406a8dba8ddd51f77068a86b38c7946c7c63d73b8c3facbe2645`). Deshalb gelten die unabhängig geprüften Ergebnisse weiter: 80 Alt-Fits erhalten, maximal 0,5224298058 px Drift, fünf neue Fits mit passenden eigenen seriellen Labels und geprüften Overlays. ROM-Warnungen bleiben Warnungen; B1 wurde nicht verändert.

## Abgrenzung der Integration

Der separate OQ-69-Lauf ist mit **17 passed in 127.16 s, Exit 0** belegt. Der frühere kombinierte 70-Test-Lauf hat weiterhin keinen Abschlussnachweis und wird nicht als bestanden gezählt. Vollsuite nach Task 3 und Doku-/Browserprüfungen bleiben wie vereinbart beim Parent. Dieses Review nimmt deren Ergebnis nicht vorweg.
