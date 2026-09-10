# Status — Stand 2026-09-10

Wird **überschrieben**, nicht angehängt. Verlauf und Messaufbauten stehen in
[project_history.md](project_history.md) und [lab_journal.md](lab_journal.md).
Die volle Entstehungsgeschichte dieser Sitzung (mehrere Bedienerrückmeldungs-
Runden, je mit Problem/Änderung/Konsequenz) steht im `CHANGELOG.md`; dieser
Abschnitt beschreibt nur den **aktuellen** Endzustand.

## Sofort zu wissen

Der noch **nicht committete** Arbeitsbaum baut die Workbench-Editor-
Bedienung für ROI/OCR-Kalibrierung vollständig um (Ausgangspunkt:
[PLAN_2026-09-10-workbench-editor.md](PLAN_2026-09-10-workbench-editor.md),
mehrfach durch reale Bedienerrückmeldung nachgezogen — Details im
`CHANGELOG.md`). Der letzte committete Stand ist `abe9427` (nur der
ursprüngliche Plan, noch keine Umsetzung). Kein Server lief während dieser
Sitzung; es gibt keinen laufenden Prozess mit ungespeicherter Konfiguration
zu berücksichtigen.

**Fremdänderung im selben Arbeitsbaum, nicht von dieser Sitzung:** Neben den
eigenen Änderungen liegen unabhängig davon `.claude/settings.json` sowie die
neuen, nicht versionierten Dateien `scripts/repo-maintenance.sh` und
`scripts/repo-maintenance-prompt.md` uncommittet im Baum — eine per Cron
geplante unbeaufsichtigte `claude -p`-Doku-Pflegeroutine (siehe CHANGELOG
„abends"-Eintrag). Nicht angefasst oder geprüft; wer als Nächstes committet,
sollte das im Blick behalten, damit sich ein späterer Cron-Lauf nicht mit
noch offener manueller Arbeit überschneidet.

## Implementierter Stand — aktueller Bedienablauf

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

## Verifiziert

```text
./.venv/bin/pytest -q                                      113 passed
./.venv/bin/ruff check src tests examples                  All checks passed!
node --check src/dispread/workbench/static/workbench.js    erfolgreich
```

Gegenüber dem committeten Stand `abe9427`: neue/aktualisierte Tests decken
Klickpriorität und Default-`ocr_box` am Controller, `fit_quad_in_region`
(achsparalleles/gekipptes synthetisches Panel, kein Kandidat,
Layout-Seitenverhältnis-Aufweitung, Ablenkerobjekt außerhalb des
Hinweisbereichs — reproduziert die "andere Bildschirme"-Rückmeldung gezielt),
`fit_ocr_box` (vier synthetische Layout-/Wertkombinationen, leerer Crop,
IoU-Qualität gegen ein gepolstertes ROI), `ocr.suggest` inklusive eines
Lock-Freigabe-Tests (deckt die eigentliche Race-Condition-Behebung ab, nicht
nur die Antwortform), Ground-Truth-Feld in `annotation.json`, die auf die
bestätigte ROI eingegrenzte Vergleichssuche, die erzwungene erneute
Bestätigung beim Sitzungsstart (samt unveränderter gespeicherter Datei und
Sperre des `run`-Modus) sowie `freeze()`s vollständige Kandidatenliste
(inkl. Nachsuchlauf-Fall). Der entfernte `roi.suggest`-Op hat einen
Regressions-Test, der seine Abwesenheit pinnt. Zwei weitere Tests laufen
gegen die realen Annotationen unter `var/workbench/annotations/` und werden
per `skipif` übersprungen, falls dieser (nicht versionierte) Ordner fehlt.

**Reale Validierung durchgeführt** (siehe [VALIDATION.md](VALIDATION.md)):
`fit_quad_in_region` trifft die bestätigte `roi_quad` beider realer
Annotationsbilder mit IoU ≈ 0,91 und ignoriert die im selben Bild sichtbaren
Monitore. `fit_ocr_box` scheitert an denselben zwei Bildern vollständig
(IoU 0,0) — Ursache ist die aus Konzept.md §7 bekannte Haupt-/Nebenanzeige-
Verwechslung (ein Netzteil mit zwei übereinanderliegenden Anzeigen `V`/`A`
in derselben bestätigten ROI) plus ein Glanzfleck in einem der beiden
Bilder; dieselbe Grenze gilt für jeden Aufrufer von `ocr.suggest`,
unabhängig davon, wodurch er ausgelöst wird. Neuer Eintrag
[OQ-25](open-questions.md). Kein automatisch übernommener Wert ist davon
betroffen — jeder Vorschlag bleibt bis zum expliziten ✓-Klick unbestätigt.

## Offene reale Abnahme

Manuelle Bedienprüfung im echten Browser steht für den gesamten neuen
Editor-Ablauf noch aus (Kandidat anklicken, ✎/✓-Zyklus an ROI und OCR-Box,
Stufenübergang und Rücksprung, das gemeldete Bugszenario gezielt
nachstellen, `annotate`-Eingabefeld, erzwungene erneute Bestätigung nach
Neustart, Knopf-Positionierung bei Fenstergrößenänderung) — nicht aus
`file://`- oder synthetischen Tests ableitbar, Teil von
[OQ-21](open-questions.md)/[OQ-24](open-questions.md), die weiterhin offen
bleiben (kein Server lief in dieser Sitzung, keine neue Abnahme möglich).

Unverändert offen: BK-5491B-VFD-Rastererkennung ([OQ-23](open-questions.md)),
GSVmulti-Telegrammformat ([OQ-01](open-questions.md)/[OQ-07](open-questions.md)),
RS-232-Transceiver ([OQ-09](open-questions.md)), RP2040-Bridge-Fehler
([OQ-22](open-questions.md), bei Raspberry Pi gemeldet, kein Fix ohne Reboot
verifiziert). Referenzwerte bleiben außerhalb von Reader und Gate.
