# Status — Stand 2026-09-24, Übergabe nach Claude-Limit

Diese Datei wird zum Sessionende überschrieben. Historie: `CHANGELOG.md` und
`docs/project_history.md`. Arbeitsliste: [../TODO.md](../TODO.md).

## Aktueller Zweig und Zustand

Die Dot-Matrix-Arbeit liegt im Worktree `/home/me-systeme/picam-ai-ernte` auf
`feat/task-b-versatz-normierung`. Der Haupt-Checkout `/home/me-systeme/picam-ai`
steht auf `master` und enthält die beiden lokalen Chat-Exporte
`codex_main.txt` und `codex_subagent.txt`. Diese Exporte wurden nicht
versioniert. Der vollständige lokale Arbeitsverlauf liegt zusätzlich in
`.superpowers/sdd/2026-09-24-dotmatrix-reader/` (ignoriert).

Spec und Umsetzungsplan:
[Dot-Matrix-Entwurf](superpowers/specs/2026-09-24-dotmatrix-reader-design.md),
[Taskplan](superpowers/plans/2026-09-24-dotmatrix-reader.md). Tasks 1–7 sind
in zehn Commits bis `666e8a1` umgesetzt; Task 8 (echte Stufe-1-Messung und
Dokumentation) ist nicht abgeschlossen. Der ganze Zweig ist **nicht zur
Integration freigegeben**.

## Letzter fachlicher Befund

Der Datensatz hat 301 seriell gelabelte Proben in drei unabhängigen
Aufstellungen (`ernte1` 152, `auf2` 76, `auf3` 73); Vorzeichen nur `+`.
`dotmatrix-eval.py loo` brach im ersten Fold mit Exit 3 an der strengen
ROM-Gegenprobe ab: Acht gelernte Zeichenmuster wichen ab, kein
`report.json` wurde geschrieben. Die spätere Diagnose fand bei `auf3`
einen Kameraversatz zwischen Profilbestätigung und Ernte von etwa
`dx=0,3`, `dy=4,6` Quellpixeln; `ernte1` stimmte mit dem ROM überein.
Auch ohne `auf3` scheitert der Fold, der nur auf der weicheren Aufstellung
`auf2` lernt: vier Zeichen weichen um je einen Punkt ab. Eine Lockerung
der ROM-Regel wäre eine Spezifikationsentscheidung, **nicht** stillschweigend
eine Codekorrektur. Siehe [OQ-42](open-questions.md#oq-42),
[VALIDATION.md](VALIDATION.md) und [lab_journal.md](lab_journal.md).

## Uncommittete letzte Korrekturrunde

Nach dem Whole-Branch-Review begann ein Claude-Subagent die
`final-fix-brief.md`-Liste. Das API-Limit beendete ihn vor Bericht und
Nachprüfung. Im Arbeitsbaum liegen Änderungen an `src/dispread/layout.py`,
`src/dispread/ocr/dotmatrix*.py`, den drei `scripts/dotmatrix-*.py` und
sechs Testdateien. Sie betreffen Vorlagen-Prüfsumme und NaN-Werte,
unbestätigte Profile, leere Restzellen 13–15, synthetische
Störungstests und kleinere Zähler. **Diese Änderungen sind uncommittet
und nicht als fertig bewertet.** Vor dem Commit Brief gegen Diff prüfen,
Tests und Ruff laufen lassen, dann `CHANGELOG.md` im selben Commit ergänzen.
Besonders prüfen: `evaluate()` kennt nur die gespeicherten neun Zellen und
hat den im Brief verlangten Berichtshinweis dazu noch nicht; der neue
geseedete 300-Fälle-Störungstest und der Konfidenz-Docstring fehlen im
aktuellen Diff ebenfalls. Zellen 9–12 (Einheit) werden weiterhin nicht
gelesen. Der Reviewer nannte außerdem
die Konfidenz-Skala von `dotmatrix`, die ±1-Pixel-Verschiebung im entzerrten
Bild und einen veralteten OQ-17-Verweis in der Spec.

## Nächste Schritte

1. Letzte Korrekturrunde gemäß
   `.superpowers/sdd/2026-09-24-dotmatrix-reader/final-fix-brief.md`
   fertig prüfen; sicherheitskritischen NaN-/Prüfsummenpfad priorisieren.
2. `auf3` erst nach neu bestätigtem Raster wieder auswerten. Die echte
   Stufe-1-Messung bleibt am ROM-Gate; strenge Regel für `auf2` anhand
   belegter Glasbilder und [OQ-42](open-questions.md#oq-42) entscheiden.
3. Danach Task 8 aus dem Plan: `loo`- und `reader-check`-Ergebnis mit
   Gruppen, Ablehnungen, Fehlfreigaben, Plateaus und Herkunft dokumentieren.
   Erst vor Stufe 2 Vorlagen/Schwellen samt Commit und SHA-256 einfrieren.

Hardware-Hinweis: OQ-22 (RP2040-Bridge) ist offen; Kamerastarts sparen.
Das GSVmulti-Telegramm bleibt OQ-07 und `AsciiCsvFormatter` provisorisch.
Der Feature-Zweig enthält noch keine `scripts/docs-site.sh`,
`zensical.toml` oder Playwright-Dokukonfiguration; deren Gates müssen
vor einer späteren Integration auf dem zusammengeführten Stand laufen.
Auf dem Arbeitsbaum **einschließlich** der uncommitteten Korrekturrunde
liefen am 2026-09-24 `PYTHONPATH=src .../.venv/bin/pytest -q` mit
612 bestanden, 1 erwartetem Fehlschlag sowie Ruff ohne Befund.
Das bestätigt nicht die fachliche Vollständigkeit des `final-fix-brief`.
