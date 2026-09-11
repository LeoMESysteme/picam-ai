# Status — Stand 2026-09-11

Wird **überschrieben**, nicht angehängt. Verlauf und Messaufbauten stehen in
[project_history.md](project_history.md) und [lab_journal.md](lab_journal.md).
Die volle Entstehungsgeschichte dieser Sitzung (mehrere Bedienerrückmeldungs-
Runden, je mit Problem/Änderung/Konsequenz) steht im `CHANGELOG.md`; dieser
Abschnitt beschreibt nur den **aktuellen** Endzustand.

## Sofort zu wissen

Diese Sitzung hat ausschliesslich `scripts/repo-maintenance.sh` (plus
`CHANGELOG.md` und diese Datei) geändert — kein `src/`, kein `Konzept.md`,
keine Hardware angefasst, kein Server lief. Auftrag: der unbeaufsichtigte
Cron-Wrapper (aus der Vorsitzung, Commit `82f63ff`) commitete bisher auch
dann, wenn der `claude -p`-Lauf mittendrin starb (Exit-Code wurde erfasst,
aber nie geprüft; der Fallback-Zweig für eine nicht parsebare Commit-Message
commitete sogar mit einer generischen Nachricht statt abzubrechen), und
kannte nur den bei Cron-Start ausgecheckten Branch (`master`). Beides
behoben — Details im CHANGELOG-Eintrag „2026-09-11". Letzter committeter
Stand vor dieser Sitzung: `ac5c5f4`.

**Fremdänderung im selben Arbeitsbaum, nicht von dieser Sitzung:**
`.claude/settings.json` liegt unabhängig davon uncommittet im Baum, dazu
mehrere unversionierte Node/Playwright-Dateien (`.github/`, `package.json`,
`package-lock.json`, `playwright.config.ts`, `tests/example.spec.ts`) sowie
eine Änderung an `.gitignore` — nicht von dieser Sitzung angelegt, nicht
angefasst oder geprüft. Wer als Nächstes committet, sollte das im Blick
behalten.

## Implementierter Stand — aktueller Bedienablauf

**Workbench-Editor** (seit `64b1f90` committet, in dieser Sitzung nicht
verändert):

**Sitzungsstart:** Eine geladene, bereits bestätigte Profilgeometrie wird
für die laufende Sitzung auf `confirmed=false` zurückgesetzt (nur die
Laufzeitkopie — die gespeicherte Profildatei bleibt unverändert,
`roi`/`roi_quad`/`ocr_box` bleiben als Startpunkt erhalten). Das reaktiviert
die volle Kandidatensuche auf dem Livebild und sperrt den `run`-Modus, bis
in dieser Sitzung aktiv erneut bestätigt wurde (Konzept.md §4: Bestätigung
ist der Akt eines Menschen, jetzt auch nach einem Neustart durchgesetzt).

**Editor, zweistufiger Ablauf** (`E`/Doppelklick öffnet ihn weiterhin;
`Escape` bricht jederzeit vollständig ab):

- **Stufe A (ROI):** die laufende Kandidatensuche zeigt mehrere dünne,
  einzeln anklickbare Vorschlagsboxen (`freeze()` liefert die volle Liste,
  nicht nur die beste Vermutung — mit einmaligem Nachsuchlauf, falls nach
  einer Bestätigung in derselben Sitzung keine Kandidaten mehr
  zwischengespeichert sind). Zwei TUI-Knöpfe (✓/✎) an der aktiven Box: ✎
  schaltet in einen Bearbeiten-Modus (Körper verschieben, Ecken ziehen —
  wird währenddessen zu ✕ zum Abbrechen), ✓ übernimmt die Position und ruft
  serverseitig `ocr.suggest` für diese Position auf.
- **Stufe B (OCR):** dieselbe ✓/✎-Logik an der vorgeschlagenen OCR-Box. Ein
  Klick auf die jetzt inaktive ROI-Box führt zurück zu Stufe A, ohne die
  Kandidatensuche neu zu starten. ✓ sendet den bestehenden `roi`-Op
  (Quad+OCR-Box zusammen, im `annotate`-Modus zusätzlich das unveränderte
  Ground-Truth-Textfeld) — weiterhin die einzige Stelle, an der `confirmed`
  wahr wird und die Erkennungsvorschau (unverändert, bereits vorher
  implementiert) automatisch startet.
- **Race-Condition-Fix (der eigentliche Auslöser dieser Umbaurunde):**
  während eine Vermutungs-/Bestätigungsanfrage läuft (`editing.pending`),
  ignoriert die Zeigereingabe auf dem Canvas vollständig und alle vier
  Knöpfe sind deaktiviert. Vorher konnte ein Klick auf die ROI-Box während
  der (durch eine unnötig innerhalb des Controller-Locks laufende
  OpenCV-Suche verlangsamten) Wartezeit die gerade eintreffende Vermutung
  mit der alten bestätigten Geometrie überschreiben — exakt der gemeldete
  Bug. `ocr.suggest` rechnet seine OpenCV-Arbeit jetzt ausserhalb des Locks
  (mirror von `publish()`s bereits bestehendem Muster).
- Entfernt: `R` (Hinweisrechteck), `G` (Rahmenwechsel), `Shift+Pfeile`
  (Eckenverschiebung), `Strg+Enter` (Bestätigung) sowie der dafür gebaute
  `roi.suggest`-Controller-Op. `fit_quad_in_region`/`fit_ocr_box` selbst
  bleiben — `publish()`s auf die bestätigte ROI eingegrenzte Vergleichssuche
  (siehe unten) nutzt `fit_quad_in_region` weiterhin.

**Vergleichssuche nach Bestätigung** (unabhängig vom obigen Editor-Umbau,
bleibt bestehen): `publish()` sucht ausserhalb des `run`-Modus gedrosselt
(`CANDIDATE_INTERVAL_S = 1,0 s`) mit `fit_quad_in_region(image,
config["roi"], layout=...)` — auf die bestätigte ROI eingegrenzt, mit
Mindestüberdeckungsfilter `MIN_HINT_OVERLAP = 0,2` gegen ein unbeteiligtes
Objekt am Rand des aufgeweiteten Suchfensters (Bedienerbefund: eine erste,
ungegrenzte Version schlug andere Bildschirme im Bild vor). Kosten: ~8,0 ms/
Bild Leerlauf, ~12,5 ms/Bild im Suchfall, `run`-Modus unverändert ohne jede
Suche — [VALIDATION.md](VALIDATION.md).

`annotate`-Aufnahmen speichern weiterhin zusätzlich einen vom Bediener
getippten `ground_truth_text` (rein additiv, keine Schema-Version).

Alles ausdrücklich **Workbench-Editorhilfe**, nicht die
`contour_heuristic`/`imx500_detector`/`RegionTracker`-Lokalisierung aus der
ROADMAP-P0-Zeile — die bleibt unverändert offen. `manual_roi` bleibt
Primärpfad; jede Geometrie muss weiterhin über einen expliziten ✓-Klick
bestätigt werden, nie automatisch übernommen.

Unverändert gültig aus vorherigen Sitzungen: zweistufige OCR-Kalibrierung
(`roi_quad`/`ocr_box`), Bildpfad-Entkopplung, OCR-Drosselung, `dispread stop`,
RP2040-Power-Zyklus-Budget (OQ-22).

**Unbeaufsichtigte Doku-Pflege** (`scripts/repo-maintenance.sh`, diese
Sitzung geändert): per `@reboot`-Cron ruft ein Wrapper `claude -p` mit festem
Prompt (`scripts/repo-maintenance-prompt.md`, `--disallowedTools
"Bash,Agent,WebFetch,WebSearch"`) einmal je lokalem Branch auf. Commit nur,
wenn ausschliesslich `docs/`/`CHANGELOG.md` geändert wurden **und** eine
parsebare Commit-Message-Markierung vorliegt — jede andere Abweichung
(Exit-Status ungleich 0 mit Änderungen, Fremdpfad, fehlende Markierung) gilt
als toter/gescheiterter Lauf: gezielter `git stash push -- docs
CHANGELOG.md` plus ein `branch: <name>`-Eintrag in
`~/.local/state/picam-ai-maintenance/needs-review`, der **nur diesen
Branch** bei künftigen Läufen überspringt, bis ein Mensch die Zeile entfernt.
Andere Branches laufen unbeeinflusst weiter. Branches mit identischem
`docs/`+`CHANGELOG.md`-Baum werden übersprungen (kein dreifacher Commit
derselben Korrektur). Noch kein scharfer Cron-Lauf beobachtet — nur gegen
Scratch-Repos mit einem Fake-`claude`-Binary verifiziert (siehe CHANGELOG).

## Verifiziert

```text
./.venv/bin/pytest -q                                      113 passed
./.venv/bin/ruff check src tests examples                  All checks passed!
bash -n scripts/repo-maintenance.sh                        erfolgreich
```

Gegenüber dem committeten Stand `ac5c5f4`: keine Python-/JS-Änderung in
dieser Sitzung, daher unveränderte Testzahl. `scripts/repo-maintenance.sh`
selbst hat keine automatisierten Tests im Projekt-Testlauf (kein
Hardwarebedarf, aber auch kein pytest-Ziel) — stattdessen manuell gegen
mehrere Scratch-Git-Repos mit einem kontrollierbaren Fake-`claude`-Binary
verifiziert: normaler Drei-Branch-Durchlauf inkl. Dedup identischer
docs-Bäume, ein Lauf mit Exit-Status ungleich 0 und liegen gebliebenen
Änderungen, ein Lauf ohne parsebare Commit-Message („getöteter" Lauf), ein
Lauf mit Fremdpfad-Änderung, sowie ein gemischter Drei-Branch-Lauf, in dem
genau ein Branch scheitert (Stash + gezielter Marker) während die beiden
anderen trotzdem committet werden und der Branch bei einem zweiten Lauf
übersprungen bleibt. Details siehe CHANGELOG-Eintrag „2026-09-11".

Aus der vorherigen Sitzung weiterhin gültig (nicht neu geprüft, keine
Codeänderung seither): `fit_quad_in_region`/`fit_ocr_box`-Testabdeckung
(Klickpriorität, Layout-Seitenverhältnis-Aufweitung, Ablenkerobjekt,
Lock-Freigabe für `ocr.suggest`, Ground-Truth-Feld, erzwungene erneute
Bestätigung beim Sitzungsstart, `freeze()`s vollständige Kandidatenliste,
Regressionstest für den entfernten `roi.suggest`-Op). **Reale Validierung**
(siehe [VALIDATION.md](VALIDATION.md)): `fit_quad_in_region` trifft die
bestätigte `roi_quad` beider realer Annotationsbilder mit IoU ≈ 0,91;
`fit_ocr_box` scheitert an denselben zwei Bildern (IoU 0,0, Haupt-/
Nebenanzeige-Verwechslung plus Glanzfleck — [OQ-25](open-questions.md)). Kein
automatisch übernommener Wert ist davon betroffen — jeder Vorschlag bleibt
bis zum expliziten ✓-Klick unbestätigt.

## Offene reale Abnahme

Manuelle Bedienprüfung im echten Browser steht für den gesamten
Workbench-Editor-Ablauf noch aus (Kandidat anklicken, ✎/✓-Zyklus an ROI und
OCR-Box, Stufenübergang und Rücksprung, das ursprünglich gemeldete
Bugszenario gezielt nachstellen, `annotate`-Eingabefeld, erzwungene erneute
Bestätigung nach Neustart, Knopf-Positionierung bei Fenstergrößenänderung)
— nicht aus `file://`- oder synthetischen Tests ableitbar, Teil von
[OQ-21](open-questions.md)/[OQ-24](open-questions.md), die weiterhin offen
bleiben (kein Server lief in dieser Sitzung, keine neue Abnahme möglich).
Zusätzlich noch offen: der erste scharfe Cron-Lauf der überarbeiteten
`repo-maintenance.sh` auf dem echten Pi (bisher nur Scratch-Repo-Tests).

Unverändert offen: BK-5491B-VFD-Rastererkennung ([OQ-23](open-questions.md)),
GSVmulti-Telegrammformat ([OQ-01](open-questions.md)/[OQ-07](open-questions.md)),
RS-232-Transceiver ([OQ-09](open-questions.md)), RP2040-Bridge-Fehler
([OQ-22](open-questions.md), bei Raspberry Pi gemeldet, kein Fix ohne Reboot
verifiziert). Referenzwerte bleiben außerhalb von Reader und Gate.
