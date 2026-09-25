# Dot-Matrix-Leser für die GSV-2AS-Anzeige — Entwurf

**Stand:** 2026-09-24, mit dem Nutzer abschnittsweise abgestimmt.
**Bezug:** Plan Ernte Phase 1, Entscheidung 1 („Zellen-Klassifikator je
Zeichenzelle, klassisch, mit Ablehnung") und Entscheidung 2 (Raster vom
Bediener bestätigt); gescheiterter Anker-Gate im Plan
`2026-09-22-dotmatrix-backend.md`; Konzept.md §7; AGENTS.md „Nicht
verhandelbar".

## Ziel und Erfolgskriterium

Ein Leser, der die 16×1-Punktraster-Anzeige (Displaytech 161A,
HD44780-kompatibel, 5×8 Punkte je Zelle) des GSV-2AS aus dem entzerrten
Bild liest und im Zweifel ablehnt.

**Erfolg (vom Nutzer festgelegt):** Auf Aufstellungen, die weder Training
noch Entwicklung gesehen haben, **0 falsch freigegebene Werte** bei
**höchstens 20 % Ablehnung**. Die Fehlerrate wird mit oberer
95-%-Vertrauensgrenze berichtet, gezählt über **Plateaus**, nicht Bilder.

## Nicht Teil dieses Schritts

Live-Bildquelle `picamera2://`, Anbindung an die Werkbank-Oberfläche,
automatische Rasterfindung, weitere Gerätetypen, negative Werte (siehe
„Vorzeichen").

## 1. Aufbau

| Baustein | Aufgabe |
| --- | --- |
| `src/dispread/ocr/dotmatrix.py` — `DotMatrixReader` | erfüllt `ValueReader`; liest ein entzerrtes Bild mit einem `CharLayout` |
| `CharLayout` (in `src/dispread/layout.py` oder eigenem Modul) | bestätigtes `CharGrid`, Einheit aus dem Profil, Anzeigeformat; ersetzt für diesen Leser das 7-Segment-`DisplayLayout` |
| `templates.json` (versioniert, mit Prüfsumme) | je Zeichen `0`–`9`, `.`, `+`, Leerzelle: 40 Mittelwerte, 40 Streuungen, Herkunft (Gruppen-IDs, Zahl der Zellen), Schwellen `D_max`, `margin_min`, Formelversion |
| `scripts/dotmatrix-train.py` | baut Vorlagen und Schwellen aus gewählten `independence_group`s |
| `scripts/dotmatrix-eval.py` | Entwicklungsmessung (Stufe 1) und Abnahmelauf (Stufe 2) |
| `src/dispread/validate.py` | Qualitätsschwellen je Leser statt fest auf 7-Segment-Kennzahlen |

Der Leser bekommt wie jeder `ValueReader` **nie** den Referenzwert. Er lernt
im Betrieb nicht nach; `templates.json` ist eingefroren.

**Formatregel (GSV-2AS, dieses Gerät):** Zelle 0 Vorzeichen; danach ein
Zahlenblock aus 8 Zellen mit genau 6 Ziffern und genau einem Punkt, wobei
führende Nullen des Ganzzahlteils als Leerzellen erscheinen (0–2 belegt,
OQ-41, Regel `gsv2as_leading_zero_v2`), die Ziffer vor dem Punkt nie; eine
Leerzelle; Einheit `mV/V` (aus dem Profil, nicht gelesen, OQ-17); Rest
leer. Verletzt das Gelesene die Regel, wird der ganze Wert abgelehnt.

## 2. Messen und Entscheiden

1. **Punktmitten:** aus dem Profil-Raster; Spaltenbreite = `pitch/6`,
   Zeilenhöhe = `(bottom − top)/8`.
2. **Abtastung:** gewichteter Mittelwert um jede Punktmitte (Radius als
   Anteil der Spaltenbreite, fest im Code).
3. **Normierung je Bild:** Hintergrund- und Punktpegel robust aus allen
   Zellen des Bildes; Punktwert 0 = Hintergrund, 1 = voll dunkel.
4. **Verschiebungssuche:** je Zelle ±1 natives Pixel (umgerechnet in
   entzerrte Pixel über `native_scale`), gleich für alle Klassen.
5. **Abstand:** zu jeder Vorlage, je Punkt mit der gelernten Streuung
   gewichtet (diagonale Mahalanobis-Distanz).
6. **Zelle abgelehnt**, wenn `d_best > D_max` (`zelle_unbekannt`) oder
   `d_second − d_best < margin_min` (`zelle_mehrdeutig`).
7. **Bild abgelehnt** bei zu geringem Punktkontrast (`kontrast`),
   Sättigung im Glas (`ueberbelichtet`), Formatverletzung (`format`) oder
   Vorzeichenzelle ≠ `+` (`vorzeichen`).
8. **Beleg je Zelle** (`GlyphEvidence`): bestes Zeichen, `ambiguous_with`,
   `margin` = Abstand zur näheren Ablehnungsgrenze; `segments` bleibt
   `None` (das Feld ist für boolesche 7-Segment-Messungen), die 40
   Punktwerte je Zelle stehen in `ReadResult.diagnostics["cells"]`.

**Vorzeichen:** Es gibt keine negativen Beispiele (Firmware 1.3.07). Der
Leser kennt nur `+`; alles andere in Zelle 0 lehnt den Wert ab. **Negative
Werte werden nie ausgegeben**, bis es echte Beispiele gibt — als
Einschränkung dokumentiert.

**ROM-Gegenprobe beim Training:** Jede gelernte Vorlage wird bei 0,5
binarisiert und mit dem HD44780-Standardzeichensatz (ROM A00, 5×7 plus
leere Cursorzeile) verglichen. Jede Abweichung bricht das Training ab —
sie deutet auf falsche Labels oder ein verschobenes Raster.

**Änderung 2026-09-25 — `rom_check_v2` (Nutzerentscheidung, OQ-42), vor
der ersten Stufe-1-Messung festgelegt:** Je Zeichen darf die binarisierte
Vorlage in **höchstens einem Punkt** vom ROM-Muster abweichen; zwei oder mehr
Abweichungen bei einem Zeichen brechen das Training ab. Begründung: Der
kleinste Abstand zweier Zeichen des Satzes beträgt 4 Punkte (`.` gegen
Leerzelle, dann `0`/`8`, `6`/`8`, `8`/`9` mit 6); ein vertauschtes Label
verschiebt eine Vorlage deshalb um mehrere Punkte und fällt weiterhin auf.
Eine einzelne Abweichung ist bei weicher Schärfe beobachtet (Aufstellung
`auf2`, VALIDATION.md 2026-09-24) und kein Hinweis auf ein falsches Label.
Die Toleranz gilt nur für die Gegenprobe; Schwellenformel und Leser bleiben
unverändert. Beleg im Test: Falsch gelabelte Trainingszellen (≥ 40 % der
Zellen einer Klasse) werden auch mit `rom_check_v2` erkannt. Die Version der
Gegenprobe steht in `templates.json` und im Bericht.

## 3. Messung und Abnahme (vorab festgelegt)

**Daten für Stufe 1:** die 301 seriell geernteten Proben des Geräts
`gsv-sensor-161a` in drei Gruppen — `ernte1` (152, enthält Ernte 2, gleiche
Aufstellung), `auf2` (76), `auf3` (73). Raster und Quad kommen aus dem
Profil der Aufstellung (`var/diagnostics/<aufstellung>-profile/profile.json`,
Zuordnung über `label_origin_detail.session_id`). Die 11 manuell gelabelten
Proben des Geräts „GSV" haben kein bestätigtes Raster und sind **nicht**
Teil der Messung — als Lücke benannt. Mehrkamera-/Multimeter-Proben anderer
Geräte sind nicht Gegenstand dieses Lesers.

**Nachverfolgbarkeit:** Der Import legt künftig Quad, Raster und Profil-
Prüfsumme in `label_origin_detail` ab, damit eine Probe ohne Nebendatei
auswertbar ist; für die 301 vorhandenen Proben wird die Zuordnung einmalig
als Datei `var/diagnostics/dotmatrix-profile-map.json` festgehalten.

**Stufe 1 — Entwicklungsmessung (Diagnose):** Jeweils eine Gruppe
zurückgehalten, auf den übrigen gelernt (3 Durchgänge). Schwellen je
Durchgang nur aus den Trainingsgruppen:

* `D_max = 1,25 × p99,5` der Abstände richtiger Zuordnungen,
* `margin_min = max(0,2 × Median(d_second − d_best) richtiger Zuordnungen,
  1,25 × größtes (d_second − d_best) einer Fehlzuordnung im Training)`.

Berichtet je Durchgang: richtig / falsch freigegeben / abgelehnt je Grund,
Verwechslungsmatrix je Zeichen, Zahl der Plateaus, Herkunftsmischung,
„Vorzeichen ungeprüft". Nachbesserungen an Abtastung und Normierung sind in
Stufe 1 erlaubt und werden im CHANGELOG und lab_journal dokumentiert; die
Schwellenformel selbst wird nicht nachträglich verändert — eine Änderung
wäre eine neue, versionierte Formel mit Begründung.

**Stufe 2 — Abnahme (einmalig):**

1. Code-Commit, `templates.json`-Prüfsumme und Formelversion einfrieren
   und in VALIDATION.md eintragen, **bevor** neue Daten entstehen.
2. Mindestens **2 neue Aufstellungen** ernten (andere Winkel, anderes
   Licht, eine davon gern mit anderer Schärfe), die keine Vorlage und keine
   Entwicklungsmessung gesehen hat.
3. Leser einmal darüber laufen lassen.
4. **Bestanden:** 0 falsch freigegebene Werte und ≤ 20 % abgelehnte Bilder.
5. Fehlerrate mit oberer 95-%-Grenze (Clopper-Pearson) über Plateaus.
6. **Nicht bestanden:** keine Nachbesserung an denselben Aufstellungen; sie
   gehen ins Training, eine neue Abnahme braucht neue Aufstellungen.

**Einordnung:** Mit 2–3 Testaufstellungen zu je ≈ 30 Plateaus liegt die
Obergrenze bei 0 Fehlern bei etwa 3–5 %. Eine belastbar kleine Zahl braucht
viele Aufstellungen; das wird in jedem Bericht so genannt.

## 4. Fehlerbehandlung

* Fehlende, falsch versionierte oder in der Prüfsumme abweichende
  `templates.json`: Leser startet nicht, kein stiller Rückfall.
* Profil ohne bestätigtes Raster oder mit `resolution_ok=False`: abgewiesen.
* Jede Ablehnung trägt einen benannten Grund (`zelle_unbekannt`,
  `zelle_mehrdeutig`, `kontrast`, `ueberbelichtet`, `format`, `vorzeichen`),
  sichtbar im Messbericht und im `PipelineTrace`.
* `declares_confidence_calibrated = False`; `margin` ist ein Beleg, keine
  Fehlerwahrscheinlichkeit.
* `ReleaseGate`: der Dot-Matrix-Leser liefert `contrast` (Punktkontrast)
  und `min_margin` (kleinster Zellen-`margin`) mit eigener, je Leser
  konfigurierter Schwelle; für `sevenseg` bleibt das Verhalten unverändert.

## 5. Tests (ohne Kamera)

* Synthetische Zellen aus den ROM-Bitmustern mit Unschärfe, Rauschen und
  Verschiebung: richtig oder abgelehnt, nie falsch.
* Unbekanntes Zeichen (`°`, Zufallsmuster) → `zelle_unbekannt`.
* Mischung `8`/`0` → `zelle_mehrdeutig`.
* Formatverletzungen (zwei Punkte, Leerzelle mitten in der Zahl, sieben
  Ziffern, drei führende Leerzellen) → `format`.
* `-` in Zelle 0 → `vorzeichen`.
* ROM-Gegenprobe erkennt eine absichtlich falsch gelabelte Trainingszelle.
* Schwellenformel deterministisch; ein Test belegt, dass Proben der
  zurückgehaltenen Gruppe die Schwellen nicht beeinflussen.
* Bestehende `sevenseg`- und `ReleaseGate`-Tests unverändert grün.
* Regressionstest auf echten Zellen nur, soweit Bilder im Repo liegen
  dürfen; sonst als Lücke benannt.
