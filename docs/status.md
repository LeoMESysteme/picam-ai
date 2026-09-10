# Status — Stand 2026-09-10, spät

Wird **überschrieben**, nicht angehängt. Verlauf und Messaufbauten stehen in
[project_history.md](project_history.md) und [lab_journal.md](lab_journal.md).
Die volle Entstehungsgeschichte dieser Sitzung (mehrere Bedienerrückmeldungs-
Runden, je mit Problem/Änderung/Konsequenz) steht im `CHANGELOG.md`; dieser
Abschnitt beschreibt nur den **aktuellen** Endzustand.

## Sofort zu wissen

Der aktuelle Arbeitsbaum steht auf Branch `test/clahe-ocr-accuracy` (von
`master` abgezweigt, mit dem gesamten unten beschriebenen, noch **nicht
committeten** Stand). Ausgangspunkt der Sitzung:
[PLAN_2026-09-10-workbench-editor.md](PLAN_2026-09-10-workbench-editor.md),
danach `PLANNED_FEATURES.md`s „NEXT FEATURE (priority high)", danach ein
separater Strang zur eigentlichen OCR-Genauigkeit (Bedienerfrage "ocr is
still bad") — Details im `CHANGELOG.md`. Der letzte committete Stand auf
`master` ist `82f63ff`. Kein Server lief während dieser Sitzung; es gibt
keinen laufenden Prozess mit ungespeicherter Konfiguration zu
berücksichtigen. **Nichts davon ist committet — das Committen auf dieser
Branch (und später der Merge nach `master`) ist zwar für den validierten
CLAHE-Schritt ausdrücklich freigegeben, aber noch nicht ausgeführt; wer als
Nächstes daran weiterarbeitet, sollte vor dem Commit den vollständigen Diff
gegen die untenstehende Beschreibung gegenprüfen.**

**Fremdänderung im selben Arbeitsbaum, nicht von dieser Sitzung:** Neben den
eigenen Änderungen liegen unabhängig davon `.claude/settings.json` sowie die
neuen, nicht versionierten Dateien `scripts/repo-maintenance.sh` und
`scripts/repo-maintenance-prompt.md` uncommittet im Baum — eine per Cron
geplante unbeaufsichtigte `claude -p`-Doku-Pflegeroutine (siehe CHANGELOG
„abends"-Eintrag). Nicht angefasst oder geprüft; wer als Nächstes committet,
sollte das im Blick behalten, damit sich ein späterer Cron-Lauf nicht mit
noch offener manueller Arbeit überschneidet.

## Implementierter Stand — aktueller Bedienablauf

**Sitzungsstart:** Eine geladene, bereits bestätigte Profilgeometrie wird für
die laufende Sitzung auf `confirmed=false` zurückgesetzt (nur die
Laufzeitkopie — die gespeicherte Profildatei bleibt unverändert,
`roi`/`roi_quad`/`ocr_box` bleiben als Startpunkt erhalten). Das reaktiviert
die volle Kandidatensuche auf dem Livebild und sperrt den `run`-Modus, bis in
dieser Sitzung aktiv erneut bestätigt wurde (Konzept.md §4: Bestätigung ist
der Akt eines Menschen, jetzt auch nach einem Neustart durchgesetzt).

**Editor, zweistufiger Ablauf** (`E`/Doppelklick öffnet ihn weiterhin;
`Escape` bricht jederzeit vollständig ab):

- **Stufe A (ROI):** die laufende Kandidatensuche zeigt mehrere dünne,
  einzeln anklickbare Vorschlagsboxen (`freeze()` liefert die volle Liste,
  nicht nur die beste Vermutung — mit einmaligem Nachsuchlauf, falls nach
  einer Bestätigung in derselben Sitzung keine Kandidaten mehr
  zwischengespeichert sind). Zwei TUI-Knöpfe (✓/✎) an der aktiven Box: ✎
  schaltet in einen Bearbeiten-Modus (Körper verschieben, Ecken ziehen — wird
  währenddessen zu ✕ zum Abbrechen), ✓ übernimmt die Position und ruft
  serverseitig `ocr.suggest` für diese Position auf.
- **Stufe B (OCR), jetzt mit Mehrkandidatenauswahl (neu in dieser Sitzung):**
  `ocr.suggest` liefert nicht mehr einen Einzelvorschlag, sondern bis zu fünf
  nach Blobfläche geordnete, überlappungsdeduplizierte Kandidaten
  (`fit_ocr_box_candidates`, `vision.py`). Die Workbench zeichnet alle als
  dünne Umrisse; ein Klick auf einen davon übernimmt ihn als aktive
  `ocr_box` (analog zur ROI-Kandidatenauswahl). Rang 1 ist weiterhin
  vorausgewählt. Dieselbe ✓/✎-Logik wie zuvor an der aktiven OCR-Box. Ein
  Klick auf die jetzt inaktive ROI-Box führt zurück zu Stufe A, ohne die
  Kandidatensuche neu zu starten. ✓ sendet den bestehenden `roi`-Op
  (Quad+OCR-Box zusammen, im `annotate`-Modus zusätzlich das unveränderte
  Ground-Truth-Textfeld) — weiterhin die einzige Stelle, an der `confirmed`
  wahr wird und die Erkennungsvorschau automatisch startet.
  - Die Singular-Funktion `fit_ocr_box` (genutzt z. B. von `publish()`s
    Vergleichssuche) betrachtet unverändert **nur** den flächengrössten
    Kandidaten und liefert `None` statt eines schwächeren Rückfalls — diese
    Sicherheitseigenschaft ist eigens gegengeprüft
    (`test_fit_ocr_box_never_falls_through_to_a_weaker_candidate`).
  - **Breitenabhängiger Schliess-Kernel (neu):** `_ocr_close_kernel` koppelt
    die vertikale Kernel-Reichweite der Blob-Erkennung zusätzlich an die
    erwartete Zellenbreite (`OCR_CLOSE_WIDTH_RATIO = 0,15`, empirisch
    gegen elf Sweep-Werte, vier synthetische Fälle, ein rekonstruiertes
    schmales Layout und sieben reale Annotationen bestimmt — siehe
    [VALIDATION.md](VALIDATION.md)). Behebt die bisher dokumentierte Grenze,
    dass eine "1" bei wenigen, breiten Ziffernzellen in zwei Blobs zerfällt
    (IoU 0,510→0,799), ohne die bestehenden Fälle zu regressieren. Ohne
    Layout weiterhin bitidentisch zur bisherigen quadratischen Formel.
- **Race-Condition-Fix (Auslöser der vorherigen Umbaurunde, unverändert
  gültig):** während eine Vermutungs-/Bestätigungsanfrage läuft
  (`editing.pending`), ignoriert die Zeigereingabe auf dem Canvas vollständig
  und alle vier Knöpfe sind deaktiviert. `ocr.suggest` rechnet seine
  OpenCV-Arbeit ausserhalb des Locks (mirror von `publish()`s Muster).
- Entfernt (vorherige Umbaurunde): `R` (Hinweisrechteck), `G`
  (Rahmenwechsel), `Shift+Pfeile` (Eckenverschiebung), `Strg+Enter`
  (Bestätigung) sowie der dafür gebaute `roi.suggest`-Controller-Op.
  `fit_quad_in_region`/`fit_ocr_box`/`fit_ocr_box_candidates` selbst
  bleiben — `publish()`s auf die bestätigte ROI eingegrenzte Vergleichssuche
  nutzt `fit_quad_in_region` weiterhin.

**Vergleichssuche nach Bestätigung** (unverändert gegenüber der vorherigen
Sitzung): `publish()` sucht ausserhalb des `run`-Modus gedrosselt
(`CANDIDATE_INTERVAL_S = 1,0 s`) mit `fit_quad_in_region(image,
config["roi"], layout=...)` — auf die bestätigte ROI eingegrenzt, mit
Mindestüberdeckungsfilter `MIN_HINT_OVERLAP = 0,2` gegen ein unbeteiligtes
Objekt am Rand des aufgeweiteten Suchfensters. Kosten: ~8,0 ms/Bild Leerlauf,
~12,5 ms/Bild im Suchfall, `run`-Modus unverändert ohne jede Suche —
[VALIDATION.md](VALIDATION.md).

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

Beide geplanten Commits aus `PLANNED_FEATURES.md`s „NEXT FEATURE" sind damit
umgesetzt: Mehrkandidaten-OCR-Vorschlag und breitenabhängiger Schliess-Kernel
— beide unabhängig voneinander revertierbar (reine Vorschlags-/Kernel-Logik,
keine Änderung an `manual_roi` als Primärpfad).

## Live-Messpfad-Genauigkeit (neu, laufender Strang)

Auf Bedienerrückmeldung ("das ocr ist noch immer nicht akkurat") begonnener,
separater Strang zur eigentlichen Werte-Lesegenauigkeit (`sevenseg.py`), nicht
mehr nur zur Editor-Bedienung oben.

**Umgesetzt:** neue Datei `tests/test_sevenseg_real_annotations.py` lässt
`SevenSegmentReader.read()` automatisch gegen jede reale Annotation mit
getipptem `ground_truth_text` laufen (`_discover_ground_truth_annotations`,
sammelt selbst ein — wächst mit jeder neuen `annotate`-Aufnahme mit, keine
Codeänderung nötig; hat das während dieser Sitzung bereits bewiesen, siehe
unten). Die anfängliche Datenlücke (die beiden aus [OQ-23](open-questions.md)
bekannten Bugbelegbilder trugen kein `ground_truth_text`) wurde geschlossen —
`ground_truth_text: "11,00"` wurde beiden nachträglich hinzugefügt, visuell
selbst gegen `image.png` bestätigt.

**Versucht und bewusst verworfen:** ein Pro-Zelle-Schwellwert-Fix in
`SevenSegmentReader.read()` (eigene Otsu-Schwelle je Ziffernzelle statt
gepoolt, mit Rückfall auf die gepoolte Schwelle bei zu geringem
Zellkontrast). Bestand alle 28 bestehenden Sicherheitstests, scheiterte
aber an einer **während der Validierung automatisch neu entdeckten realen
Annotation** (`fdc840cd...`, vom Harness ohne Codeänderung sofort erfasst —
der Harness hat hier also bereits genau seinen Zweck erfüllt): zwei echte
`8`-Stellen kippten auf `6`, weil eine zellinterne Otsu-Schwelle auf nur
sieben Messwerten ein einzelnes, minimal dunkleres Segment (Abtastartefakt)
fälschlich isolierte. Strukturelles Problem, keine falsch gewählte
Konstante — eine 6-aktiv/1-inaktiv-Aufteilung ist selbst ein gültiges
Ziffernmuster, sieben Messwerte je Zelle reichen nicht, um echte
Bimodalität von Rauschen zu unterscheiden. `sevenseg.py` deshalb
**unverändert** (`git checkout`), kein sicherheitskritischer Kompromiss
ausgeliefert. Volle Herleitung: [VALIDATION.md](VALIDATION.md),
[lab_journal.md](lab_journal.md), OQ-23.

**Umgesetzt und behalten: CLAHE (`apply_enhance`) im Live-Pfad, jetzt auch im
echten Messpfad standardmäßig aktiv.** Eine bereits vorhandene, aber im
Live-Pfad hart deaktivierte Funktion (`rectify.enhance()`, lokaler
Kontrastausgleich) — bisher nur mit einer unvalidierten Docstring-Vorsicht
ausgeschlossen, nie gegen die tatsächlichen Degradationsfälle gemessen.
`apply_enhance=True` fest in `Controller._read` (Workbench-Vorschau, sendet
nichts) sowie als `PipelineConfig.apply_enhance`-Feld verfügbar gemacht.
Gemessen (Details [VALIDATION.md](VALIDATION.md)): keine Regression an allen
28 Sicherheitstests und allen sechs realen Annotationen; deutliche
Verbesserung der Unschärfe-Ablehnungsgrenze (synthetisch, σ=12/15: vorher
teils/vollständig abgelehnt, jetzt 40/40 korrekt) und leichte Verbesserung
bei Glanz (stille Fehlablesungen 2→1 von 40) — in keinem gemessenen Fall
eine neue stille Fehlablesung. `rectify()`s Docstring entsprechend
korrigiert.

`PipelineConfig.apply_enhance` stand zunächst auf Default `False` (nur die
Workbench-Vorschau profitierte, der tatsächliche sendende Messpfad aus
`Pipeline.process` nicht). Nach eigener Gegenprüfung (volle Testsuite plus
`examples/16_end_to_end_headless.py` mit dem neuen Default, 40/40 korrekt,
0 still falsch, keine Regression) auf `True` umgestellt — bleibt ein
expliziter, auf `False` rücksetzbarer Konfigurationswert. `rectify`-Kosten
mit CLAHE gegengemessen: p50 ≈ 2 552 µs, in derselben Größenordnung wie die
Messung ohne CLAHE vom 2026-09-07 (Perspektivverzerrung dominiert die
Stufe), siehe [TIMING.md](TIMING.md)-Update.

**Damit bleibt der eigentliche, in OQ-23 dokumentierte Fehlermodus (gepoolte
Schwelle scheitert an einer echt dunkleren Ziffernstelle) weiterhin
offen** — CLAHE gleicht Kontrast nur lokal innerhalb einer Kachel an, die
Schwelle selbst bleibt global gepoolt; an der realen Annotation
`8a18ee05...` liest der Leser mit CLAHE unverändert `110?` statt `11.00`.
Eine tragfähigere Richtung bräuchte eine "aus"-Referenz aus einer
robusteren, zellübergreifenden Schätzung statt aus sieben Punkten pro Zelle,
und dafür mehr reale, gezielt unterschiedlich beleuchtete Vergleichsdaten
als aktuell vorhanden — nicht an zwei Beispielen zu kalibrieren
(AGENTS.md/Konzept.md §7). Aktueller Stand gegen alle auswertbaren realen
Annotationen: 5 von 6 lesen korrekt, 1 (`8a18ee05...`) ist als
`xfail(strict=True)` markiert statt versteckt.

Ebenfalls recherchiert und verworfen: ein ML-Modell zur periodischen
Kamera-Drift-Erkennung (separate Anfrage, nicht Teil der Genauigkeitsfrage
selbst) — kein bestehendes Modell passt (alle Kandidaten sind auf
Alltagsfotos fremder Displaytypen trainiert, IMX500-Konvertierung fehlt
weiterhin lokal, OQ-11); empfohlen wurde stattdessen, das bereits vorhandene
`fit_quad_in_region` periodisch gegen die zuletzt bestätigte `roi_quad`
laufen zu lassen — noch nicht umgesetzt, da nicht angefragt.

## Verifiziert

```text
./.venv/bin/pytest -q                                      127 passed, 1 xfailed
./.venv/bin/ruff check src tests examples                  All checks passed!
node --check src/dispread/workbench/static/workbench.js    erfolgreich
```

Der eine `xfail` ist bewusst (`8a18ee05...`, siehe „Live-Messpfad-Genauigkeit"
oben) — `strict=True`, schlägt also fehl statt unbemerkt grün zu werden.

Gegenüber dem committeten Stand `abe9427`: neue/aktualisierte Tests decken
Klickpriorität und Default-`ocr_box` am Controller, `fit_quad_in_region`
(achsparalleles/gekipptes synthetisches Panel, kein Kandidat,
Layout-Seitenverhältnis-Aufweitung, Ablenkerobjekt außerhalb des
Hinweisbereichs), `fit_ocr_box`/`fit_ocr_box_candidates` (vier synthetische
Layout-/Wertkombinationen, leerer Crop, IoU-Qualität gegen ein gepolstertes
ROI, gestapelte Zwei-Zeilen-Anzeige, Sicherheits-Regressionstest gegen
stillen Rückfall auf einen schwächeren Kandidaten), `ocr.suggest` inklusive
eines Lock-Freigabe-Tests (deckt die Race-Condition-Behebung ab) und der
neuen Plural-Antwortform, Ground-Truth-Feld in `annotation.json`, die auf die
bestätigte ROI eingegrenzte Vergleichssuche, die erzwungene erneute
Bestätigung beim Sitzungsstart, sowie `freeze()`s vollständige
Kandidatenliste. Der entfernte `roi.suggest`-Op hat einen Regressionstest,
der seine Abwesenheit pinnt. Neu: ein schmales 3-stelliges Layout ohne
Nachkommastelle dauerhaft in der `fit_ocr_box`-Parametrisierung, pinnt die
Behebung der bisherigen Schliess-Kernel-Grenze. Die real-annotationsbasierten
Tests sammeln ihre Eingabeordner jetzt automatisch ein
(`_discover_annotations` in `tests/test_workbench.py` statt einer festen
Pfadliste) — sie laufen inzwischen gegen alle sieben brauchbaren realen
Annotationen unter `var/workbench/annotations/` statt nur zwei, und werden
sauber übersprungen (nicht als Fehler), falls dieser (nicht versionierte)
Ordner leer ist oder fehlt.

**Reale Validierung durchgeführt** (siehe [VALIDATION.md](VALIDATION.md)):
`fit_quad_in_region` trifft die bestätigte `roi_quad` beider realer
Annotationsbilder mit IoU ≈ 0,91. `fit_ocr_box_candidates` bietet an
denselben zwei Bildern den tatsächlich gewünschten Kandidaten jetzt
nachweisbar in der Liste an (Rang 1, IoU 0,543/0,568) — ein direkter
Fortschritt gegenüber der vorherigen Einzelfunktions-Messung (IoU 0,0 an
beiden Bildern). Die zugrundeliegende Haupt-/Nebenanzeige-Verwechslung
(Konzept.md §7) bleibt strukturell ungelöst, jetzt aber eine
Bedienerauswahl statt eines stillen Fehlgriffs. Neuer Update-Eintrag
[OQ-25](open-questions.md). Kein automatisch übernommener Wert ist davon
betroffen — jeder Vorschlag bleibt bis zum expliziten ✓-Klick unbestätigt.

Zusätzlich gegen alle sieben verfügbaren realen Annotationen gemessen (nicht
nur die ursprünglichen zwei): bester Kandidaten-IoU zwischen 0,543 und 0,890
je nach Aufnahme, keiner davon durch den neuen Schliess-Kernel verändert
(bitidentisch zur Baseline bei `OCR_CLOSE_WIDTH_RATIO = 0,15`) — die
Kernel-Änderung wirkt gezielt nur auf Layouts mit ausreichend breiten Zellen,
keine der bisherigen realen Geometrien fällt in diesen Bereich.

**Playwright-MCP-Browserautomatisierung geprüft und verworfen** (siehe
[OQ-21](open-questions.md)-Update): das verfügbare MCP-Plugin erzwingt den
`chrome`-Kanal, dessen Installation in dieser Umgebung `sudo` verlangt; auch
nach erfolgreicher Installation des sudo-freien Chromium-Pakets bleibt das
Tool auf den nicht vorhandenen `chrome`-Kanal fixiert. Andere Ursache als der
ältere Chromium-Headless-Befund, gleiches Ergebnis: kein automatisierter
Browsertest in dieser Umgebung möglich. Es bleibt bei der Python-Testsuite
plus manueller Bedienprüfung.

## Offene reale Abnahme

Manuelle Bedienprüfung im echten Browser steht für den gesamten Editor-Ablauf
weiterhin aus (Kandidat anklicken — jetzt auch für OCR-Kandidaten, nicht nur
ROI —, ✎/✓-Zyklus an ROI und OCR-Box, Stufenübergang und Rücksprung, das
ursprünglich gemeldete Bugszenario gezielt nachstellen, `annotate`-
Eingabefeld, erzwungene erneute Bestätigung nach Neustart, Knopf-
Positionierung bei Fenstergrößenänderung, speziell: Klick auf einen dünnen
OCR-Kandidatenumriss muss die fette Auswahl exakt an derselben Stelle zeigen)
— nicht aus `file://`- oder synthetischen Tests ableitbar, Teil von
[OQ-21](open-questions.md)/[OQ-24](open-questions.md), die weiterhin offen
bleiben (kein Server lief in dieser Sitzung, keine neue Abnahme möglich).

Unverändert offen: BK-5491B-VFD-Rastererkennung ([OQ-23](open-questions.md)),
GSVmulti-Telegrammformat ([OQ-01](open-questions.md)/[OQ-07](open-questions.md)),
RS-232-Transceiver ([OQ-09](open-questions.md)), RP2040-Bridge-Fehler
([OQ-22](open-questions.md), bei Raspberry Pi gemeldet, kein Fix ohne Reboot
verifiziert; Maintainer hat geantwortet, Cmdline-Rücksetzungstest und
probeweise Testkernel-Installation für das nächste Wartungsfenster
vorgemerkt — bewusst nicht während dieser laufenden Entwicklungssitzung
ausgeführt). Referenzwerte bleiben außerhalb von Reader und Gate.
