---
weg: bedienen
hide:
  - toc
---
# Glossar

Jeder Begriff, der in diesem Projekt eine engere Bedeutung hat als im
Alltag. Nach Themen gegliedert; mit JavaScript als A–Z-Ansicht mit Filter.

## Projekt und Fachliches

### Anzeigeart

Art der Geräteanzeige, für die ein passender Erkenner gewählt werden soll. Sie kann nach Bestätigung im Geräteprofil festgehalten werden; welche Anzeigearten freigegeben werden, ist noch zu prüfen.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

### ASCII-Streaming

Fortlaufende Übertragung von Werten als ASCII-Datenstrom. Einer der zu unterscheidenden GSVmulti-Schnittstellenfälle; weder CSV-Dateiimport noch Geräteemulation belegen seine Unterstützung.

*Weg:* Entwickeln · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### CSV-Dateiimport

Übernahme von Werten aus einer CSV-Datei. Im Konzept ein eigener Schnittstellenfall neben ASCII-Streaming und Geräteemulation; daraus folgt keine Unterstützung beliebiger serieller CSV-Datenströme durch GSVmulti.

*Weg:* Entwickeln · *Quelle:* [Konzept](../../Konzept.md)

### Dezimalpunkt

Zur Messwertinterpretation gehörendes Zeichen für die Dezimalstelle. Ein übersehener Punkt ist ein kritischer Lesefehler; seine sichere Erkennung gehört zu den geforderten Freigabekriterien.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### DUT

*Device under Test*, der Prüfling. Das Gerät, dessen Anzeige gelesen
wird. Sein Wert wird **nie** anhand der Referenz korrigiert.

*Weg:* Bedienen · *Auch:* Device under Test · *Quelle:* [Konzept §7](../../Konzept.md)

### Dynamische Vergleiche

Vergleiche zeitlich veränderlicher DUT- und Referenzwerte. Dabei sind die Displayverzögerung und ihre Schwankung besonders kritisch; ein Aufnahmezeitstempel allein bezeichnet noch nicht den internen DUT-Messzeitpunkt.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Einheit

Zum Zahlenwert gehörende Maßeinheit, deren richtige Zuordnung der Bediener bestätigen soll. Eine falsche Einheit zählt zu den kritischen Fehlern; der interne Datensatz sieht eine erkannte oder bestätigte Einheit vor.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

### Emulation eines GSV-Geräts

Nachbildung einer GSV-Geräteanbindung als möglicher GSVmulti-Schnittstellenfall. Der Adapter muss dafür gegebenenfalls auch Gerätekommandos beantworten; die nötige Spezifikation liegt noch nicht vor.

*Weg:* Entwickeln · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### Geräteidentifikation

Identifikation des angebundenen Geräts, die für die GSVmulti-Anbindung zusammen mit Initialisierungskommandos zu klären ist. Automatisch erkannte Geräteidentitäten müssen außerdem zuverlässig geprüft werden.

*Weg:* Entwickeln · *Quelle:* [Konzept](../../Konzept.md)

### GSVmulti

Die Auswertesoftware von ME-Systeme, die die Werte
zeitgestempelt entgegennehmen soll. Das akzeptierte serielle Telegramm ist
unbekannt ([OQ-01](../open-questions.md), [OQ-07](../open-questions.md)).

*Weg:* Bedienen · *Quelle:* [GSVmulti-Protokoll](../GSVMULTI_PROTOCOL.md)

### Hauptanzeige

Die im Aufbau auszulesende Anzeige, die eindeutig und formatfüllend im Bild erscheinen soll. Der Live-Pfad kennzeichnet die bestätigte Anzeige mit `main`; diese Kennzeichnung allein verhindert keine Verwechslung.

*Weg:* Bedienen · *Quelle:* [Optischer Aufbau](../OPTICAL_SETUP.md)

### Messbereich

Zum Gerät gehörende Bereichsangabe, die der Bediener bei der Einrichtung gegebenenfalls bestätigen soll. Zusammen mit Einheit und Dezimalformat gehört sie zur eindeutigen Interpretation der ausgewählten Anzeige.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

### Messverstärker

Die Geräteklasse (GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI,
AST). Beispielgeräte, kein zugesicherter Umfang: welche Typen freigegeben
werden, ist [OQ-04](../open-questions.md).

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Nebenanzeige

Zusätzliche Anzeige, die nicht mit der auszulesenden Hauptanzeige verwechselt werden darf. Lokalisierungskandidaten können dafür den Hinweis `secondary` tragen; der Hinweis allein erkennt keine Verwechslung.

*Weg:* Bedienen · *Quelle:* [Optischer Aufbau](../OPTICAL_SETUP.md)

### OQ-nn

*Open Question*. Nummerierte Unbekannte in
[../open-questions.md](../open-questions.md). Jede hat einen Vorabdefault, eine
Zuständigkeit und einen Zielort für die Antwort. Einträge werden **nie
gelöscht**, nur auf `geklärt` gesetzt.

*Weg:* Entwickeln · *Auch:* Open Question · *Quelle:* [Offene Fragen](../open-questions.md)

### Referenz

Die Kalibriermaschine bzw. das Normal. Zeitlich mit dem DUT
zuzuordnen, aber strikt getrennt vom Erkennungspfad (Konzept §7).

*Weg:* Bedienen · *Quelle:* [Konzept §7](../../Konzept.md)

### Sperrgerät

Geräteinstanz, die vor jeder Entwicklung zurückgehalten und
erst in der Abnahme einmalig ausgewertet wird. Mindestens zwei.

*Weg:* Bedienen · *Quelle:* [Validierung](../VALIDATION.md)

### Statische Kalibrierpunkte

Kalibrierpunkte mit stabilem Zustand, für die ein gemeinsames stabiles Zeitfenster zur Zuordnung von DUT und Referenz geeignet sein kann. Ob statische Punkte oder dynamische Verläufe erfasst werden sollen, ist vorab festzulegen.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Überlauf

Ungültiger Betriebszustand der Anzeige, der erkannt und von der Zahlenfreigabe ausgeschlossen werden muss. Im Messpfad gehört er neben Menü und Hold zu den blockierenden Statusflags.

*Weg:* Bedienen · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

### Vorzeichen

Zur Zahl gehörendes Plus- oder Minuszeichen. Ein fehlendes Minuszeichen ist ein kritischer Fehler; sichere Vorzeichenerkennung ist deshalb ein gefordertes Freigabekriterium.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Zahlenformat

Bestätigte Regel zur Darstellung der angezeigten Zahl, die ein wiederverwendbares Geräteprofil festhalten kann. Nur ein erlaubtes Zahlenformat zusammen mit bestätigter Einheit erfüllt die entsprechenden Freigabeanforderungen.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

## Bildverarbeitung

### `ambiguous_with`

Feld der `GlyphEvidence` für andere Zeichen, die zur Messung passen könnten. Beim Segmentleser benennt es nahe Kandidaten zu einem unbekannten Segmentmuster; daraus wird keine Ziffer geraten.

*Weg:* Entwickeln · *Quelle:* [Kette verstehen](01-kette-verstehen.md)

### Autofit

Anpassung der Segmentraster-Geometrie an einen einmal eingetippten Anzeigewert auf dem Bestätigungsbild. Gesucht wird ein exakt passender Parametersatz mit hoher Trennschärfe; passt keiner, wird das gemeldet.

*Weg:* Entwickeln · *Quelle:* [OCR-API](../../api/ocr.md)

### `cell_boxes`

Methode für Zellrechtecke im entzerrten Bild als `(x, y, w, h)`. `DisplayLayout` liefert die Ziffernzellen ohne Vorzeichenstelle; `CharGrid` liefert die Zeichenzellen seines bestätigten Rasters.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `CharGrid`

Regelmäßiges Zeichenzellenraster einer Punktmatrix-Anzeige im entzerrten Bild. Es beschreibt unter anderem Zellzahl, linken Rand, Zellabstand und vertikale Grenzen; der Bediener bestätigt es je Sitzung.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `CharLayout`

Bestätigtes Punktraster-Layout für den Dot-Matrix-Leser mit Raster, Einheit und Formatregel. `from_profile()` lehnt unbestätigte Profile und Profile ohne bestandenes Auflösungs-Gate ab.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### CLAHE

*Contrast Limited Adaptive Histogram Equalization*. Lokale
Kontrastanhebung. In `rectify.enhance()` verfügbar, standardmäßig **aus**:
sie verändert die Helligkeiten, aus denen die Segmentevidenz entsteht.

*Weg:* Konfigurieren · *Auch:* Contrast Limited Adaptive Histogram Equalization · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### `classified_cells`

Feld des `CharLayout`, das die Anzahl der zu klassifizierenden Wertzellen bestimmt. Im dokumentierten Dot-Matrix-Pfad sind dies die Zellen 0–8; die Restleerzellen werden getrennt geprüft.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `digit_gap_ratio`

Layoutschlüssel für den Zwischenraum vor den Ziffernstellen als Anteil einer Zellenbreite. Er lässt reale Abstände zwischen Ziffern im Segmentraster berücksichtigen.

*Weg:* Konfigurieren · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `DisplayLayout`

Zahlenformat und Geometrie einer Siebensegment-Anzeige. Beschreibt unter anderem Ziffernzahl, Nachkommastellen und separate Vorzeichenstelle; im Betrieb stammt es aus dem bestätigten Geräteprofil.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### Displaylokalisierung

Bestimmen des Anzeigebereichs im Kamerabild. Das Konzept sieht automatische Vorschläge vor; im aktiven Live-Pfad wird die vom Menschen bestätigte Geometrie nachgeführt. Ein Fund allein ist keine Bestätigung.

*Weg:* Entwickeln · *Quelle:* [Lokalisierungs-API](../../api/detect.md)

### `DotMatrixReader`

Aktiver Leser für die GSV-2AS-Anzeige mit bestätigtem Punktraster und geprüften Vorlagen. Prüft Wertzellen, Restleerzellen und Zahlenformat; negative Werte und andere Geräte sind damit nicht freigegeben.

*Weg:* Entwickeln · *Quelle:* [OCR-API](../../api/ocr.md)

### ECC

Bildregistrierung für die Nachführung: Jedes neue Bild wird gegen das Bestätigungsbild verglichen, nicht gegen das vorherige Bild. Zu große Bewegung oder geringe Bildähnlichkeit führen zur Ablehnung.

*Weg:* Entwickeln · *Quelle:* [Projekt-Tour](../uebersicht/projekt-tour.md)

### Entzerren / Rectify

Das Anzeigenviereck auf ein achsparalleles Rechteck
fester Größe abbilden (`rectify.rectify()`). Feste Zielgröße, weil der
Segmentleser gegen ein Raster abtastet.

*Weg:* Entwickeln · *Auch:* Entzerren, Rectify · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### `exposure_ok`

Abgeleitete grobe Belichtungsprüfung des `DisplayCrop` aus den Anteilen gesättigter und sehr dunkler Bildpunkte. Ihre Schwellen sind Vorabdefaults, keine allgemeine Freigabe des Aufbaus.

*Weg:* Entwickeln · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### `GlyphEvidence`

Belege für eine einzelne gelesene Stelle: Zeichen, Konfidenz, mögliche Alternativen und Marge. Beim Siebensegment-Leser gehört die gemessene Segmentbelegung dazu; fehlende Evidenz darf nicht durch Gesamtkonfidenz ersetzt werden.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### Homographie

Die 3×3-Abbildung zwischen Bildviereck und entzerrtem
Ausschnitt. Wird im `DisplayCrop` mitgeführt, damit man einzelne Segmente für
Diagnosebilder zurückprojizieren kann.

*Weg:* Entwickeln · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### IoU

*Intersection over Union*, Flächenüberlappung zweier Regionen. Maß
dafür, ob eine Lokalisierung getroffen hat.

*Weg:* Entwickeln · *Auch:* Intersection over Union · *Quelle:* [Lokalisierungs-API](../../api/detect.md)

### `ManualRoiLocator`

Locator, der ein vorgegebenes bestätigtes Viereck als Kandidaten zurückliefert. Er wertet das Bild nicht aus und prüft selbst nicht, ob die Anzeige seit der Bestätigung verrutscht ist.

*Weg:* Entwickeln · *Quelle:* [Lokalisierungs-API](../../api/detect.md)

### OCR

Optische Zeichenerkennung zum Lesen von Ziffern, Vorzeichen, Dezimalpunkt, Einheit und Statusanzeigen. Das Projekt trennt dieses Lesen von Lokalisierung und Freigabe; ein erkannter Text allein genügt nicht.

*Weg:* Entwickeln · *Quelle:* [Konzept](../../Konzept.md)

### Otsu

Schwellwertverfahren, das den Schnitt maximaler
Zwischenklassenvarianz sucht. Hier **nicht** über alle Bildpunkte, sondern über
die gepoolten Segmentmessungen — Begründung im Docstring von
`sevenseg.segment_threshold()`.

*Weg:* Entwickeln · *Quelle:* [OCR-API](../../api/ocr.md)

### `polarity`

Layoutschlüssel für die Anzeigepolarität: `bright_on_dark` bezeichnet helle Segmente auf dunklem Grund, `dark_on_bright` dunkle auf hellem Grund. Die Auswahl kommt aus dem bestätigten Profil.

*Weg:* Konfigurieren · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Quad

Vier Eckpunkte einer Anzeige im Bildkoordinatensystem, im
Uhrzeigersinn ab oben links.

*Weg:* Entwickeln · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### `QuadTracker`

Nachführung eines bestätigten Anzeigenvierecks gegen das Bestätigungsbild. Der aktuelle Tracker berücksichtigt auch den Zifferninhalt; große Wertwechsel können deshalb zum Verlust der Nachführung führen.

*Weg:* Entwickeln · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### ROI

*Region of Interest*, der Anzeigebereich. Im Primärpfad **bestätigt**
(vom Bediener, Konzept §4), nicht gefunden.

*Weg:* Bedienen · *Auch:* Region of Interest, Anzeigebereich · *Quelle:* [Konzept §4](../../Konzept.md)

### Schärfe

Varianz des Laplace-Operators. Nur innerhalb
**eines** Aufbaus vergleichbar, nie als absolute Güte.

*Weg:* Konfigurieren · *Auch:* sharpness · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### Segmentevidenz

Die gemessene Helligkeit jedes der sieben Segmente je
Stelle, plus `margin`. Sie erklärt Entscheidungen des Siebensegment-Lesers.
Der Live-Pfad am GSV-2AS verwendet stattdessen Punktraster und Vorlagenabstände
des `DotMatrixReader`.

*Weg:* Entwickeln · *Quelle:* [OCR-API](../../api/ocr.md)

### `SevenSegmentReader`

Leser für Siebensegment-Anzeigen mit Evidenz je Segment. Teilt den entzerrten Ausschnitt nach dem Profilraster auf und lehnt unbekannte Segmentmuster ab. Im Projekt dient er auch den synthetischen Übungen.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### `sign_box`

Methode des `DisplayLayout` für das Rechteck der separaten Vorzeichenstelle. Gibt `None` zurück, wenn das Layout keine Vorzeichenstelle vorsieht; deren Lesbarkeit wird getrennt vom erkannten Minus geprüft.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Sättigung

Anteil der Bildpunkte ≥ 250. Maß für
Überstrahlung; treibt das `glare`-Flag.

*Weg:* Konfigurieren · *Auch:* saturated_fraction · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### `TesseractReader`

Implementierter OCR-Leser, der Tesseract als Unterprozess aufruft. Er liefert derzeit keine mit dem Segment-Gate vergleichbaren Kontrast- und Margendiagnosen; die Standard-Gates lehnen entsprechend ab.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### `TrackedQuadLocator`

Live-Adapter für die Nachführung der bestätigten Anzeige. Liefert bei Grenzverletzung oder zu geringer Bildähnlichkeit keinen Kandidaten; die Pipeline dokumentiert dann unmittelbar `UNREADABLE`.

*Weg:* Entwickeln · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### `tracking_lost`

Kennzeichnung eines Nachführungsverlusts mit angehängtem Grund. Die Pipeline erzeugt dabei `UNREADABLE` ohne Zahlenwert. `low_score` kann derzeit auch nach großen Wertwechseln auftreten, weil der Tracker den Zifferninhalt nutzt.

*Weg:* Entwickeln · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

## Kette und Verträge

### `anzeige_wechselt`

Ablehnungsgrund für kurzzeitige Mischziffern nach einer Freigabe. Nur wenn die lesbaren Zellen zum letzten freigegebenen Wert passen und Anzahl sowie Zeitfenster eingehalten sind, gilt `TRANSITION` ohne Zahlenwert.

*Weg:* Bedienen · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

### `awaiting_confirmation`

Grund für `TRANSITION`, solange noch nicht genug aufeinanderfolgende Bilder denselben Wert bestätigen. Der Live-Pfad verlangt zwei gleiche Bilder; ein Zahlenwert wird bis dahin nicht freigegeben.

*Weg:* Bedienen · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

### `contrast`

Lesediagnose für den gemessenen Kontrast, die zusammen mit `min_margin` und `unreadable_cells` zum faktischen Gate-Vertrag gehört. Fehlende messbare Evidenz darf ein Backend nicht durch eine erfundene Qualitätsangabe ersetzen.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### `decimal_point_detected`

Eigenes Feld des Leseergebnisses für den Dezimalpunktbefund. Ein optisch erkannter Punkt muss von einer Profilannahme unterscheidbar bleiben; beim Segmentleser ist die optische Prüfung noch offen.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### `decimal_point_index`

Eigenes Feld des `ReadResult` für die Position des Dezimalpunkts. `DisplayLayout.decimal_point_index()` liefert die profilseitig festgelegte Position oder `None`, wenn sie erkannt werden muss.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `declares_confidence_calibrated`

Eigenschaft des Leser-Vertrags: Gibt an, ob Konfidenz gegen echte Fehlerraten kalibriert ist. Bleibt `False`, solange keine Kalibriermessung in der Validierungsdokumentation belegt ist.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### `display_not_located`

Ablehnungsgrund der allgemeinen Pipeline, wenn kein Anzeigenkandidat vorliegt. Es entsteht `UNREADABLE` ohne Zahlenwert; die Freigabe wird für diesen Fall nicht aufgerufen.

*Weg:* Bedienen · *Quelle:* [Lokalisierung ohne Bediener](07-lokalisierung.md)

### `DisplayCandidate`

Lokalisierungskandidat mit Viereck, Score, Locator-Kennung und optionalem Rollenhinweis. Die allgemeine Pipeline prüft die Rolle nicht selbst; ein Kandidat ist noch keine Bestätigung der richtigen Anzeige.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `DisplayCrop`

Entzerrter Bildausschnitt mit Quellviereck, Homographie und Qualitätsmaßen. Führt Schärfe sowie Anteile gesättigter und sehr dunkler Bildpunkte für die Diagnose mit.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `DisplayLocator`

Schnittstellenvertrag zum Finden von Anzeigenkandidaten in einem `Frame`. Ein leeres Tupel ist zulässig und bedeutet „nicht gefunden“; die Pipeline erzeugt daraus einen ungültigen Datensatz.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `Frame`

Kamerabild mit Sequenznummer, Aufnahmezeitstempel und Quellenkennung. Enthält BGR- oder Graustufenbilddaten sowie verfügbare Kamera- und Rohmetadaten; `is_time_bearing` kennzeichnet die zeitliche Verwertbarkeit.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `frames_confirmed`

Feld der Freigabeentscheidung und des Datensatzes für die Anzahl der Bilder, die einen Wert bestätigt haben. Zusammen mit der Bestätigungszeitspanne macht es die Mehrbildbestätigung nachvollziehbar.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `FrameSource`

Schnittstellenvertrag einer Bildquelle mit Öffnen, Schließen und Frame-Iterator. `source_id`, Fähigkeiten und Beschreibung kennzeichnen Herkunft und Grenzen; die Beschreibung gehört ins Runartefakt.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### Freigabe / Gate {#freigabe-gate}

`ReleaseGate` entscheidet aus Leseergebnis, Profil und
eigener Historie über `VALID | TRANSITION | UNREADABLE | STALE`. Bekommt
strukturell keinen Referenzwert.

*Weg:* Konfigurieren · *Auch:* Freigabe, Gate, ReleaseGate · *Quelle:* [Freigabe-API](../../api/validate.md)

### `GateConfig`

Konfiguration der Freigaberegeln, unter anderem für Qualitätsgrenzen und Mehrbildbestätigung. Die Schwellen sind Vorabdefaults; reale Freigabegrenzen bleiben offen. Leser liefern dabei keine automatisch vergleichbaren Margen.

*Weg:* Konfigurieren · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

### `GateDecision`

Ergebnis der Freigabe mit Status, Qualitätskennzahl, Ablehnungsgründen, bestätigter Bildzahl und Bestätigungszeitspanne. Bei einem anderen Status als `VALID` sind die Ablehnungsgründe nie leer.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### Konfidenz {#konfidenz}

Qualitätsmaß des jeweiligen Lesers; das Gate begrenzt `min_margin` nach oben auf 1.

*Weg:* Konfigurieren · *Quelle:* [Freigabe-API](../../api/validate.md)

Beim Segmentleser ist die Marge normiert, beim Dot-Matrix-Leser stammt sie aus der Vorlagenskala. Werte verschiedener Leser sind deshalb nicht unmittelbar vergleichbar. **Keine Fehlerwahrscheinlichkeit** (Konzept §7).

### Marge {#marge}

Beim Segmentleser ist `margin` der Abstand der knappsten Segmentmessung zur Entscheidungsschwelle, normiert 0..1.

*Weg:* Konfigurieren · *Auch:* margin · *Quelle:* [OCR-API](../../api/ocr.md)

Beim Dot-Matrix-Leser ist sie der kleinere verbleibende Abstand zur erlaubten Vorlagendistanz und zur geforderten Klassentrennung; diese Skala ist nicht normiert. Klein = knapp entschieden.

### Mehrbildbestätigung {#mehrbildbestaetigung}

*N* aufeinanderfolgende Frames müssen denselben Wert
zeigen (`GateConfig.confirm_frames`). Kostet Zeit, die als
`confirmation_span_ns` dokumentiert wird.

*Weg:* Konfigurieren · *Quelle:* [Freigabe-API](../../api/validate.md)

### `min_margin`

Diagnoseschlüssel für die kleinste vom Leser gemeldete Marge. Gehört mit Kontrast und Anzahl unlesbarer Zellen zum Gate-Vertrag; die Segment- und Dot-Matrix-Skalen sind nicht unmittelbar vergleichbar.

*Weg:* Entwickeln · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

### `Pipeline`

Verdrahtung der Verarbeitung vom Frame über Lokalisierung, Entzerrung, Lesen und Freigabe bis zu Datensatz und Senken. Erhält keinen Referenzwert; ein fehlender Kandidat wird direkt als `UNREADABLE` dokumentiert.

*Weg:* Entwickeln · *Quelle:* [Pipeline-API](../../api/pipeline.md)

### `raw_text`

Textrepräsentation des Lesers, getrennt vom Zahlenwert. Der aktuelle Dot-Matrix-Leser speichert die geparste Zahl mit Pluszeichen, keine vollständige Abschrift aller Displayzellen; bei Ablehnung bleibt der Text leer.

*Weg:* Entwickeln · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

### `ReadResult`

Leseergebnis vor der Freigabeentscheidung. Hält Text und Zahlenwert sowie Vorzeichen-, Dezimalpunkt- und Einheitenbefunde getrennt; enthält Betriebszustände, Belege je Stelle und Lesediagnosen.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `reject_reasons`

Maschinenlesbare Gründe für eine Ablehnung oder einen Übergang. Jeder `ValueRecord` mit Status ungleich `VALID` muss mindestens einen Grund tragen; sie sind der erste Anlaufpunkt bei der Fehlersuche.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Senke / Sink {#senke-sink}

Ausgabe (`JsonlSink`, `SerialSink`). Zählt Fehler statt zu
werfen und liefert je Datensatz einen `TxReceipt`.

*Weg:* Entwickeln · *Auch:* Senke, Sink · *Quelle:* [Ausgabe-API](../../api/sink.md)

### `sign_detected`

Minuszeichenbefund des `ReadResult`. Er wird getrennt von der Auswertbarkeit des Vorzeichenbereichs geführt, damit ein unsichtbares Vorzeichen nicht stillschweigend als positiver Wert behandelt wird.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `sign_region_readable`

Feld des `ReadResult`, das angibt, ob der Vorzeichenbereich überhaupt auswertbar war. Ein unlesbarer Bereich muss zur Ablehnung führen und darf nicht als fehlendes Minus interpretiert werden.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `STALE` {#stale}

Es gibt **keinen** aktuellen Wert mehr (nach
`stale_after_ns` ohne Freigabe). Trägt keinen Zahlenwert.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `status_flags`

Betriebszustände im Leseergebnis, etwa `overflow`, `menu`, `hold` und `glare`. Blockierende Flags verhindern die gültige Zahlenfreigabe und bleiben im Gate `UNREADABLE`.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `TelegramFormatter`

Schnittstellenvertrag für die Umsetzung eines `ValueRecord` in Bytes. `format()` darf `None` zurückgeben, wenn der Datensatz entfällt. Die Formatfähigkeiten kennzeichnen ungeprüfte Formate als provisorisch.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `TRANSITION` {#transition}

Die Anzeige wechselt bzw. die Bestätigung läuft noch. Aussage
über die Anzeige, kein Systemfehler.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Trennstelle {#trennstelle}

Eine der sechs Nahtstellen aus Konzept §3. Fünf sind `typing.Protocol`;
die Freigabe setzt die konkrete Klasse `ReleaseGate` um. Siehe
[Kapitel 2](02-vertraege.md).

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `TxReceipt` {#tx-receipt}

Was tatsächlich über die Leitung ging: Sendezeit, Bytes,
Format, Retries. Bewusst getrennt vom `ValueRecord`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### `unit_source`

Diagnose zur Herkunft der Einheit: `read` bedeutet gelesen, `profile` aus dem Profil übernommen. Die Herkunft muss sichtbar bleiben, damit eine bestätigte Einstellung nicht als optische Erkennung erscheint.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### `unit_text`

Eigenständiges Einheitenfeld des `ReadResult`. Muss zusammen mit der Herkunftsdiagnose betrachtet werden: Beim Dot-Matrix-Leser stammt die Einheit aus dem bestätigten Profil und wird nicht gelesen.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `UNREADABLE` {#unreadable}

Gerade nicht lesbar. Trägt keinen Zahlenwert.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `unreadable_cells`

Lesediagnose für die Anzahl unlesbarer Zellen. Gehört zum faktischen Gate-Vertrag; liefert ein Backend keine belastbare Evidenz, darf daraus keine Freigabe durch Raten entstehen.

*Weg:* Entwickeln · *Quelle:* [Weitere OCR-Backends](08-ocr-backends.md)

### `VALID`

Status eines freigegebenen Werts. Er allein hebt eine Testlaufmarkierung nicht auf: Ein Testlauf kann einzelne VALID-Records enthalten, deren Messnutzung durch die Laufkennzeichnung untersagt bleibt.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `ValueReader`

Schnittstellenvertrag zum Lesen eines Ausschnitts mit bestätigtem Layout. Liefert `ReadResult`; die Signatur erlaubt weder Referenzwert noch Historie oder letzten Wert als Eingabe.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `ValueRecord` {#value-record}

Der interne Datensatz (Konzept §8): was das System erkannt
hat. Neun Pflichtfelder, `frozen`, verlustfrei serialisierbar.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `ValueSink`

Schnittstellenvertrag der Ausgabe mit `emit()` und `health()`. Übertragungsfehler werden gezählt und als fehlgeschlagener `TxReceipt` zurückgegeben, damit sie den Messbetrieb nicht anhalten oder unbemerkt verschwinden.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

## Zeit

### `capture_timestamp`

Aufnahmezeit des Bilds mit Zeitbasis, physikalischer Bedeutung und Unsicherheit. Sie bleibt im `ValueRecord` erhalten und wird nicht durch eine Verarbeitungszeit ersetzt.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `CLOCK_BOOTTIME`

Zeit seit dem Booten, inklusive Suspend.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

Das war die Zeitbasis des `SensorTimestamp` der inzwischen außer Betrieb genommenen IMX500 (Messung 2026-09-07). Vergleiche über Reboot-Grenzen hinweg sind sinnlos — deshalb `boot_id` ins Session-Manifest. Für die aktive StreamCam siehe [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md).

### `CLOCK_MONOTONIC`

Monoton steigende Zeit ohne Sprünge. Domäne aller
Verarbeitungsmarken im `PipelineTrace`.

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### `ClockLog`

Protokolliert im Live-Lauf den Versatz `BOOTTIME` minus `MONOTONIC` zu Beginn, periodisch und beim Abschluss. Die Proben stehen in `session.json`; sie klären nicht die physikalische Bedeutung des Kamerastempels.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### `confirmation_span_ns`

Dokumentierte Zeitspanne der Mehrbildbestätigung im Datensatz. Sie macht die Bestätigungsverzögerung sichtbar; die Aufnahmezeit wird dafür weder pauschal halbiert noch verändert.

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### Displayaktualisierung

Erneuerung der sichtbaren Geräteanzeige. Ein höherer Sendetakt erzeugt keine zusätzlichen unabhängigen Messwerte, wenn die Anzeige langsamer aktualisiert; wiederholte Beobachtungen sind nicht automatisch neue interne DUT-Messungen.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Displayverzögerung

Verzögerung zwischen internem DUT-Messzeitpunkt und sichtbarer Anzeige. Ihre Schwankung ist für dynamische Vergleiche kritisch; ein Aufnahmezeitstempel allein beseitigt diesen Beitrag nicht.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Drift

Zeitliche Veränderung des Versatzes zwischen Pi-Uhr und Referenzuhr. Messung M6 soll Offset und Drift bestimmen; der verbleibende Driftbeitrag gehört ins Unsicherheitsbudget.

*Weg:* Bedienen · *Quelle:* [Zeitbezug](../TIMING.md)

### `FILE_MTIME`

Zeitbasis eines aus der Dateizeit abgeleiteten Stempels. Sie ist keine belastbare Aufnahmezeit und erlaubt keine reale Latenz- oder Synchronitätsaussage; auch Replay macht sie nicht zeittragend.

*Weg:* Entwickeln · *Quelle:* [Aufnahme und Replay](06-kamera-aufnahme-replay.md)

### Haltezeit

Dauer, für die ein angezeigter Wert stehen bleibt. Im Zeitmessprogramm wird sie zusammen mit der Displayaktualisierung je Gerätetyp in M5 untersucht; sie gehört zu den Beiträgen des Unsicherheitsbudgets.

*Weg:* Bedienen · *Quelle:* [Zeitbezug](../TIMING.md)

### Latenz vs. Zeitunsicherheit

Latenz ist eine Verzögerung (korrigierbar,
wenn bekannt); Zeitunsicherheit ist die *Streuung* der Zuordnung. Eine kleine
Latenz garantiert keine kleine Unsicherheit. Grundsatz aus
[../TIMING.md](../TIMING.md).

*Weg:* Bedienen · *Auch:* Latenz, Zeitunsicherheit · *Quelle:* [Zeitbezug](../TIMING.md)

### M1 … M8

Das Messprogramm zum Zeitbezug in
[../TIMING.md](../TIMING.md). Wichtigste: **M8** (nutzt GSVmulti den
gelieferten Aufnahmezeitstempel?) und **M5** (Displayaktualisierung und
Haltezeit, vermutlich der dominierende Term).

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### Offset

Versatz zwischen Zeitbasen, etwa `BOOTTIME` minus `MONOTONIC`. Er wird je Aufnahme gemessen; bei einer Zeitzuordnung sind der Versatz, seine Streuung und unbekannte systematische Reste getrennt zu behandeln.

*Weg:* Bedienen · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### `PipelineTrace`

Verarbeitungsmarken eines Frames in `CLOCK_MONOTONIC`. Ihre Differenzen liefern Stufenrechenzeiten; sie belegen nicht automatisch den Abstand zwischen interner DUT-Messung und Referenzmessung.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### Reaktionszeit

In der nachträglichen Live-Referenzauswertung gemessene Reaktion auf einen Wertwechsel. Sie ist keine Aussage über den internen DUT-Messzeitpunkt und ersetzt kein Unsicherheitsbudget.

*Weg:* Bedienen · *Quelle:* [Zeitbezug](../TIMING.md)

### `REPLAY_RECORDED`

Zeitbasis einer erhaltenen Aufnahmezeit im Replay. Sie trägt die Zeitinformation der ursprünglichen Aufnahme, nicht des Abspielens; Voraussetzung sind belastbare Aufnahmemetadaten.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### `result_timestamp`

Zeitpunkt der Fertigstellung des Datensatzes. Die aktuelle Pipeline liest `MONOTONIC`, übernimmt aber die Basis des Frames; außerhalb des V4L2-Pfads ist diese Kennzeichnung nicht zuverlässig. Für Rechenzeiten dienen die Trace-Marken.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Schutzintervall

Gemessener Abstand um Anzeigewechsel, der serielle Auto-Labels vor unsicherer Zuordnung schützt. Er berücksichtigt Telegramm-zu-Glas-Versatz, Mischzeit und Streuung; er ist kein vollständiges Unsicherheitsbudget der DUT-Messung.

*Weg:* Konfigurieren · *Quelle:* [Zeitbezug](../TIMING.md)

### Semantik

Worauf sich ein Zeitstempel physikalisch
bezieht: Belichtungsbeginn, -mitte, Auslese-Ende, Host-Abholung. Steht auf
`UNKNOWN`, bis Messung M2 es belegt.

*Weg:* Entwickeln · *Auch:* TimestampSemantics · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `SensorTimestamp`

Zeitstempel aus den libcamera-Metadaten.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### `SYNTHETIC`

Zeitbasis generierter Bilder ohne reale Aufnahme- oder Synchronitätszeit. Daraus darf keine reale Latenzaussage entstehen; Rechenzeitmessungen sind ausdrücklich als solche zu kennzeichnen.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### `Timestamp`

Datensatz für einen Zeitpunkt: Nanosekundenwert, Zeitbasis, physikalische Bedeutung und Unsicherheit. Eine noch nicht gemessene Unsicherheit ist `None`; für eine Zeitaussage müssen auch Domänen und Umrechnung passen.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### Timing-Kalibrierung

Messung des Gesamtversatzes zwischen seriellem Telegramm und sichtbarer Anzeige samt Schutzintervall. Der Live-Lauf dokumentiert die Kalibrierdatei mit Prüfsumme, wendet den Versatz aber nicht auf Aufnahmezeiten an.

*Weg:* Bedienen · *Quelle:* [Zeitbezug](../TIMING.md)

### `to_boottime_ns`

Zentrale Umrechnung von Aufnahmezeitstempeln nach `BOOTTIME`. Für V4L2 verlangt sie gemessene Start- und Endversätze der Session; fehlende Angaben oder ein auffälliger Versatzwechsel führen zur Ablehnung.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### Trigger

Optionales gemeinsames Ereignis für die zeitliche Zuordnung. Ein erfasstes GPIO-Ereignis synchronisiert allein weder die Kamerabelichtung noch die interne DUT-Messung.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Unsicherheit

`None`, solange ungemessen. **Nie 0**;
das wäre eine Falschaussage.

*Weg:* Entwickeln · *Auch:* uncertainty_ns · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Unsicherheitsbudget

Getrennte Bilanz der Beiträge zur zeitlichen Zuordnung, von interner DUT-Messung bis Übertragung. Die Vorlage wird durch M1–M7 gefüllt und trennt korrigierbare systematische Beiträge von Streuung.

*Weg:* Bedienen · *Quelle:* [Zeitbezug](../TIMING.md)

### `V4L2_MONOTONIC`

Zeitbasis des unverändert gespeicherten V4L2-Pufferzeitstempels der aktiven StreamCam. Sie ist zeittragend; für `BOOTTIME` braucht es den gemessenen Versatz. Die physikalische Stempelsemantik bleibt offen.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### Zeilenweise Auslesung

Zeitversatz zwischen Sensorzeilen beim Auslesen eines Bilds. Messung M3 soll diesen Beitrag bestimmen; die Budgetvorlage führt Zeilenposition mal Zeit je Zeile als systematischen Anteil, bislang ohne Messwert.

*Weg:* Bedienen · *Quelle:* [Zeitbezug](../TIMING.md)

### Zeitbasis

Herkunft und Belastbarkeit: `V4L2_MONOTONIC`, `SENSOR_BOOTTIME` und `REPLAY_RECORDED` tragen eine Zeitaussage, `SYNTHETIC` und `FILE_MTIME` nicht (`carries_time_information`).

*Weg:* Entwickeln · *Auch:* TimeBaseKind · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

Für die nötige BOOTTIME-Umrechnung und die offene Stempelsemantik siehe [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md).

## Schnittstellen und Hardware

### `.rpk`

Gepacktes Modell für den IMX500. Die 23 mitgelieferten sind
COCO-/ImageNet-Modelle und für Displays unbrauchbar. Der **Packager** ist auf
dem Pi vorhanden, der **Converter** für eigene Modelle nicht
([OQ-11](../open-questions.md)).

*Weg:* Entwickeln · *Quelle:* [Offene Fragen](../open-questions.md#oq-11)

### `/dev/ttyAMA0`

Vorgesehener UART-Datenport für die noch offene GSVmulti-Ausgabe; die elektrische Anbindung ist nicht freigegeben (OQ-09).

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

Die serielle GSV-2AS-Referenz nutzt am aktuellen Aufbau `/dev/ttyUSB0`. **`/dev/serial0`** zeigt auf `ttyAMA10` und ist der 3-Pin-Debug-Header, **nicht** der Nutzdatenport.

### `/dev/ttyAMA10`

Serieller Port am 3-Pin-Debug-Header des Pi, auf den `/dev/serial0` zeigt. Er ist ausdrücklich nicht der vorgesehene Nutzdatenport für die GSVmulti-Ausgabe.

*Weg:* Konfigurieren · *Auch:* /dev/serial0 · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### `/dev/ttyUSB0`

Port des dokumentierten PL2303-USB-RS232-Adapters für den eingehenden GSV-2AS-Referenzstrom. Er wird für Datenernte und optionale Live-Referenzaufzeichnung genutzt und ist kein GSVmulti-Ausgang.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### 8N1

Serielles Zeichenformat der dokumentierten GSV-2AS-Verbindung: Das Referenzgerät wird mit 38400 Baud und 8N1 gelesen. Diese Geräteeinstellung legt das noch unbekannte GSVmulti-Ausgabeformat nicht fest.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### ASCII

Textausgabeformat des GSV-2AS als Alternative zur Binärausgabe. Laut Geräteanleitung entspricht die ausgegebene Zeichenkette der Displayanzeige; damit ist die Annahme durch GSVmulti noch nicht belegt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Baudrate

Geschwindigkeitsparameter der seriellen Verbindung. Für den GSV-2AS-Referenzeingang sind 38400 Baud dokumentiert; die passende Einstellung des geplanten GSVmulti-Ausgangs ist weiterhin offen.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Binärformat

Alternative zur ASCII-Ausgabe des GSV-2AS: fünf Byte je Messwert mit 24 Bit. Das Ausgabeformat wird am Gerät per `Set Mode` umgeschaltet; die dokumentierte Laborreferenz wurde auf ASCII umgestellt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### CAM/DISP0

Historischer Kameraanschluss der inzwischen außer Betrieb genommenen Raspberry Pi AI Camera am Pi 5. Die aktuelle Logitech StreamCam wird über USB angebunden.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Galvanische Trennung

Elektrische Isolation der seriellen Verbindung, deren Eignung für den Laboraufbau noch zu bewerten ist. Sie ist nicht bereits durch einen Pegelwandler oder die funktionierende Referenzaufzeichnung nachgewiesen.

*Weg:* Bedienen · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### GNDC

Bezeichnung der Masse für RS232 und RS422 an Klemme A der fünfpoligen GSV-2AS-Schraubklemme. Sie gehört zum dokumentierten seriellen Geräteanschluss.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### GPIO

Pi-Anschlüsse mit 3,3-V-Pegeln. Sie dürfen nicht direkt an RS-232 angeschlossen werden: Der nötige Transceiver muss sowohl die Pegelwandlung als auch die Invertierung erledigen.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### GSV-2AS

Messverstärker des dokumentierten Laboraufbaus. Sein serieller ASCII-Strom dient über einen USB-RS232-Adapter als getrennte Referenz für Datenernte und optionale Live-Aufzeichnung; er belegt keine GSVmulti-Kompatibilität.

*Weg:* Bedienen · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### IMX500

Sony-Sensor der Raspberry Pi AI Camera, mit
On-Sensor-Inferenz. Seit 2026-09-25 außer Betrieb. Historisch gemessen:
6,8 s Warmlauf beim ersten `.rpk`-Upload, 15,0 Inferenzen/s.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Logitech StreamCam

Seit 2026-09-25 aktive USB-3-Kamera des Projekts mit USB-ID `046d:0893`. Sie ersetzt die Raspberry Pi AI Camera und wird über UVC/V4L2 angebunden.

*Weg:* Bedienen · *Auch:* StreamCam · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### PL2303

Chipsatz des dokumentierten USB-RS232-Adapters am GSV-2AS-Referenzeingang. Die Verbindung erscheint als `/dev/ttyUSB0` und wird mit 38400 Baud, 8N1 gelesen.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Polarisationsfilter

Optischer Filter, der Spiegelungen reduzieren kann. Sein Einfluss auf den LCD-Kontrast muss am Aufbau geprüft werden; eine falsche Orientierung kann die Anzeige unlesbar machen.

*Weg:* Bedienen · *Quelle:* [Optischer Aufbau](../OPTICAL_SETUP.md)

### `provisional`

Flag in `FormatterCapabilities`: das Format wurde **nicht**
gegen eine echte Spezifikation geprüft. Gehört in jedes Runartefakt. Beim
`AsciiCsvFormatter` immer `True`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### `pty`

Pseudoterminal-Paar (`os.openpty()`). Gegenstelle für die serielle
Ausgabe ohne Hardware.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### Raspberry Pi 5

Rechnerplattform des Projekts. Am dokumentierten Laborgerät sind die aktive StreamCam und die serielle Referenz angebunden; der vorgesehene GSVmulti-Ausgang benötigt weiterhin eine geklärte elektrische Anbindung.

*Weg:* Bedienen · *Auch:* Pi 5 · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Raspberry Pi AI Camera

Historisches Kameramodul mit Sony IMX500 und Inferenz im Sensor. Seit 2026-09-25 außer Betrieb und durch die Logitech StreamCam ersetzt; seine Fokus- und Anschlussangaben gelten nicht für die aktive USB-Kamera.

*Weg:* Bedienen · *Auch:* AI Camera · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### RS-232 / Transceiver

Pi-GPIO-Pegel dürfen **nicht** direkt an RS-232;
es braucht einen Pegelwandler, galvanische Trennung ist zu bewerten
([OQ-09](../open-questions.md)).

*Weg:* Bedienen · *Auch:* RS-232, Transceiver · *Quelle:* [Offene Fragen](../open-questions.md#oq-09)

### RS-485

Im Konzept neben RS-232 genannte mögliche elektrische Schnittstelle für eine UART-Anbindung mit passendem Transceiver. Eine solche GSVmulti-Ausgangsstrecke ist damit noch nicht freigegeben.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### RS422

Neben RS232 dokumentierte Schnittstelle an der fünfpoligen GSV-2AS-Schraubklemme. Die Belegung unterscheidet Rx−, Tx−, Rx+ und Tx+; der aktuelle Referenzaufbau verwendet den USB-RS232-Adapter.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Rx

Empfangsleitung der seriellen Verbindung. Am GSV-2AS liegt Rx auf Klemme B; beim Anschluss an den PC wird sie mit dessen TX-Leitung gekreuzt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Set Mode

GSV-2-Gerätebefehl 38 zum Umschalten des Ausgabeformats zwischen Binär und ASCII. Die dokumentierte Änderung des Laborgeräts auf ASCII ist persistent und überlebt das Ausschalten.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Telegramm

Die Bytes eines Datensatzes auf der seriellen Leitung, erzeugt
von einem `TelegramFormatter`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### Tx

Sendeleitung der seriellen Verbindung. Am GSV-2AS liegt Tx auf Klemme C; beim Anschluss an den PC wird sie mit dessen RX-Leitung gekreuzt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### UART

Serielle Anschlussmöglichkeit des Pi. Für die geplante Ausgabe nach GSVmulti ist `/dev/ttyAMA0` vorgesehen; für RS-232 oder RS-485 ist ein passender Transceiver nötig.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### USB-RS232-Adapter

Adapter zwischen USB am Pi und der RS232-Schnittstelle des Messverstärkers. Im aktuellen Referenzpfad wird ein PL2303 an `/dev/ttyUSB0` verwendet; der vorgesehene UART-Ausgang bleibt davon getrennt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### UVC

USB-Kameraanbindung der aktiven Logitech StreamCam. Die Bildquelle `v4l2://` verlangt bestätigte Geräteeinstellungen einschließlich USB-ID, Bildformat, Bildrate und Kamerareglern.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### V4L2

Kamerazugriff für die aktive StreamCam über `v4l2://`. Der Live-Pfad nutzt bestätigte Kameraeinstellungen; die historischen Picamera2- und IMX500-Schemata werden gezielt abgelehnt.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Virtueller USB-COM-Port

Mögliche USB-Geräteschnittstelle zum Empfänger. Dafür verlangt das Konzept eine geeignete USB-Device- oder Bridge-Lösung; diese Funktion darf am Pi 5 nicht pauschal vorausgesetzt werden.

*Weg:* Entwickeln · *Quelle:* [Konzept](../../Konzept.md)

## Python und Werkzeuge

### ABI

Binäre Kompatibilität der zusammen gebauten Systempakete. Eine per pip installierte NumPy-Kopie kann das gegen System-NumPy gebaute OpenCV brechen; deshalb bleiben die betreffenden Debian-Pakete in der Projekt-venv sichtbar.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### `aiohttp`

Python-Bibliothek für die Netzwerkdienste der Workbench: HTTPS, MJPEG, WebSockets und Unix-Socket-API. Sie kommt aus dem Debian-Paket `python3-aiohttp` und gehört zu den zusätzlichen Workbench-Abhängigkeiten.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### CLI

Bedienung über Konsolenbefehle. Vorhanden ist die Workbench-CLI mit Live-Steuerung; die frei kombinierbare Pipeline-CLI mit Quelle, Geräteprofil und Senken ist weiterhin eine Bauaufgabe. `dispread run` ist kein verfügbarer Unterbefehl.

*Weg:* Entwickeln · *Quelle:* [CLI](05-cli.md)

### Docstring

Dokumentation im Python-Quelltext. Modul-Docstrings sollen hier das Warum mit Konzept- oder OQ-Verweis erklären; beim Doku-Build entstehen aus den Docstrings unter `src/dispread` die API-Seiten.

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

Erzeugung der API-Seiten: [API-Referenz](../../api/index.md).

### Editierbarer Install

Das Paket wird aus `src/`
importiert statt kopiert. Trägt einen absoluten Pfad in der `.pth`-Datei; ein
umbenanntes Projektverzeichnis bricht ihn ([Kapitel 0](00-werkzeuge.md)).

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

Installation mit: `./.venv/bin/pip install --no-deps -e .`.

### Einsprungpunkt

Zuordnung eines Konsolenbefehls zu einer Python-Funktion. `pyproject.toml` verbindet `dispread` mit `dispread.workbench.cli:main`; der Befehl startet damit die separate Workbench-CLI.

*Weg:* Entwickeln · *Quelle:* [CLI](05-cli.md)

### `frozen` Datenklasse

Nach dem Erzeugen unveränderlich. Alle
Ergebnisobjekte hier. Änderung nur als neues Objekt
(`dataclasses.replace`).

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Generator

Funktion mit `yield`. Alle `frames()`-Methoden sind Generatoren,
damit nicht der ganze Datensatz im Speicher liegt.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Lazy Import

Import erst innerhalb der Funktion. In `frames/__init__.py`
die Voraussetzung dafür, dass ein fehlendes `picamera2` die anderen Quellen
nicht unbenutzbar macht.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Mock-Modus

Standardmodus der Tests ohne Hardware. `tests/conftest.py` überspringt darin Tests mit den Markierungen `hardware` oder `serial`; neue Tests gehören grundsätzlich in diesen Pfad, sofern sie keine physische Kamera oder UART brauchen.

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

### NumPy

Array-Bibliothek für Bildaufbereitung und Segmentanalyse. Der Messkern verwendet das Debian-Systempaket `python3-numpy`; eine zusätzliche PyPI-Kopie in der Projekt-venv würde die Systemkopie überschatten.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

Einsatz in der Bildverarbeitung: [Konzept](../../Konzept.md).

### OpenCV

Bildverarbeitungsbibliothek für Entzerrung und Bildaufbereitung, in Python als `cv2` eingebunden. Die aktive UVC-Bildquelle öffnet OpenCV erst beim Öffnen der Kamera; verwendet wird das Debian-Systempaket `python3-opencv`.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### `pip`

Installationswerkzeug für Python-Pakete. Im Projekt installiert es das eigene Paket mit `--no-deps -e .`; pytest und Ruff dürfen in die venv, die dokumentierten Systembibliotheken dürfen dort keine PyPI-Kopie erhalten.

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

### `Protocol`

Strukturelle Typisierung: passende Methoden genügen, kein
Erben nötig. Mit `@runtime_checkable` ist `isinstance()` möglich und wird in
Tests als Konformitätsprüfung benutzt.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `pyproject.toml`

Projektdatei mit Paketabhängigkeiten, Konsolen-Einsprungpunkt und Ruff-Konfiguration. `dependencies = []` ist hier Absicht, damit pip keine Kopien der benötigten Debian-Systembibliotheken installiert.

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

Der registrierte Konsolenbefehl: [CLI](05-cli.md).

### `pyserial`

Python-Bibliothek für die serielle Ausgabe des Messkerns. Sie wird als Debian-Paket `python3-serial` bereitgestellt; beim Import heißt das Modul `serial` und soll aus dem Systempaketpfad aufgelöst werden.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### `pytest`

Testwerkzeug des Projekts, aufgerufen über `./.venv/bin/pytest`. Der Standardlauf nutzt den Mock-Modus ohne Hardware; der Exit-Code und die Zusammenfassung zeigen das Ergebnis, nicht eine festgeschriebene Testanzahl.

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

### Quellen-Registry

Zuordnung von Quell-URIs zu Bildquellen in `dispread.frames`. Ein bekannter URI-Eintrag garantiert keine fertige Implementierung: `folder://` ist registriert, das zugehörige Modul fehlt derzeit noch.

*Weg:* Entwickeln · *Auch:* URI-Registry · *Quelle:* [Eigene Bildquelle](03-erste-bildquelle-folder.md)

### Ruff

Linter für Python-Stil und Importordnung. Die Regeln stehen in `pyproject.toml`; geprüft wird über `./.venv/bin/ruff check src tests examples`. Bei Erfolg meldet das Werkzeug `All checks passed!`.

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

### `slots=True`

Feste Attributmenge, weniger Speicher, und ein Tippfehler
bei einer Zuweisung fliegt auf.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `StrEnum`

Enum, dessen Mitglieder Strings sind. Erlaubt direkte
JSON-Serialisierung über `.value`.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `subprocess`

Python-Anbindung für externe Programmaufrufe. Das Projekt spricht Tesseract über dessen CLI mit `subprocess` an; dafür wird keine zusätzliche `pytesseract`-Abhängigkeit installiert.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### `--system-site-packages` / `--no-deps`

Die venv-Regel des Projekts:
Systempakete sichtbar lassen, keine PyPI-Kopien von `numpy`/`cv2`/`pyserial`
darüberlegen. Begründung in [../dependencies.md](../dependencies.md).

*Weg:* Entwickeln · *Auch:* --system-site-packages, --no-deps · *Quelle:* [Abhängigkeiten](../dependencies.md)

### venv

Python-Umgebung für Projektpaket und Entwicklungswerkzeuge. Die Projekt-`.venv` muss Debian-Systempakete sehen; absolute Pfade in ihren Startskripten und Installationsdateien machen sie beim Verschieben des Repos reparaturbedürftig.

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

## Messung, Daten und Abnahme

### Abdeckung

Umfang der im Datensatz vertretenen Ziffernpositionen, Vorzeichen, Dezimalpunkte, Einheiten, Betriebszustände, Störungen und Displaytechniken. Maßstab für ausreichende Daten ist diese Vielfalt, nicht die Frame-Anzahl.

*Weg:* Bedienen · *Quelle:* [Validierung](../VALIDATION.md)

### Abnahmekriterien

Vor der Abnahme festzulegende Grenzen für Fehlablesungen, Falschablehnungen, Zeitbezug und Betrieb. Die Platzhalter in der Validierung sind keine erreichten Grenzwerte; geprüft wird auf zuvor gesperrten Geräten.

*Weg:* Bedienen · *Quelle:* [Validierung](../VALIDATION.md)

### Audit-Log

Vollständiges JSONL-Protokoll der ValueRecords, auch wenn kein Wert freigegeben wurde. Es hält fest, was die Kette erkannt hat; tatsächlich gesendete Bytes werden davon getrennt im `TxReceipt` dokumentiert.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Auto-Label

Automatisch aus dem seriellen Gerätestrom zugeordnetes Trainingslabel. Die zeitliche Absicherung nutzt ein gemessenes Schutzintervall; diese Anzeigezuordnung belegt nicht die interne DUT-Verzögerung.

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### Entwicklungsdaten

Material, das während der Entwicklung für Schwellenwahl und Fehleranalyse genutzt wird. Solche Geräte zählen anschließend nicht als unberührte Abnahmegeräte; Entwicklungsbelege ersetzen keine unabhängige Abnahme.

*Weg:* Bedienen · *Quelle:* [Daten und Abnahme](../uebersicht/daten-und-abnahme.md)

### Falschablehnung

Ablehnung eines korrekt lesbaren Werts. Sie mindert die Verfügbarkeit und muss getrennt von als gültig ausgegebenen falschen Werten ausgewertet werden.

*Weg:* Bedienen · *Quelle:* [Daten und Abnahme](../uebersicht/daten-und-abnahme.md)

### Fehlerklassen

Getrennte Zählkategorien für falsche Ziffern, Vorzeichen, Dezimalpunkte, Einheiten, Anzeigenverwechslung, Betriebszustand, unmarkierte Altwerte und Verfügbarkeitsfehler. Eine hohe Zeichenquote ersetzt diese Auswertung nicht.

*Weg:* Bedienen · *Quelle:* [Validierung](../VALIDATION.md)

### Geräteinstanz

Ein konkretes physisches Gerät als Einheit der Datentrennung. Benachbarte Frames oder neue Aufnahmen desselben Geräts sind keine unabhängigen Geräteproben; die Splitgrenze liegt deshalb bei der Instanz.

*Weg:* Bedienen · *Quelle:* [Daten und Abnahme](../uebersicht/daten-und-abnahme.md)

### Gruppensplit

Trennung von Trainings- und Testmaterial nach physischer Geräteinstanz statt nach einzelnen Frames. Sie verhindert, dass benachbarte Bilder derselben Aufnahme beide Seiten der Auswertung besetzen.

*Weg:* Entwickeln · *Quelle:* [Validierung](../VALIDATION.md)

### Label

Zur Probe gespeicherte Beurteilung der sichtbaren Anzeige. Im Sammelmodus wird lesbarer Text einschließlich Vorzeichen und Dezimalzeichen eingetippt oder die Probe als unlesbar beziehungsweise unsicher markiert; kein OCR-Vorschlag.

*Weg:* Bedienen · *Quelle:* [Datensatz sammeln](11-datensatz-sammeln.md)

### `label_origin`

Herkunftsmerkmal eines Datensatzlabels: `manual` oder `serial_ascii`. Seit Schema 2 ist es Pflicht und wird beim Export erhalten; serielle Labels brauchen zusätzliche Belege zu Quelle, Schutzintervall und Plateau.

*Weg:* Entwickeln · *Quelle:* [Displaybus und Labelherkunft](../DISPLAYBUS_TAP.md)

### `records.jsonl`

Audit-Datei der Pipelineentscheidungen eines Live-Laufs. Sie kann auch im Testlauf einzelne `VALID`-Records enthalten; für die Messnutzung müssen `TESTLAUF.json` und die Laufmarkierung in `session.json` mit ausgewertet werden.

*Weg:* Bedienen · *Quelle:* [Daten und Abnahme](../uebersicht/daten-und-abnahme.md)

### `reference.jsonl`

Separate Aufzeichnung des seriellen GSV-2AS-Stroms mit `BOOTTIME`-Empfangsstempeln. Sie dient als Gegenprobe zum optischen Wert desselben Geräts und ist keine unabhängige Kalibrierreferenz.

*Weg:* Bedienen · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

### `session.json`

Laufmetadaten mit Profil-, Vorlagen- und Kalibrierprüfsummen, Kameraeinstellungen, Gate-Konfiguration und Uhrenversatz. Testlauf und angepasste Lesetoleranz sind dort gesondert markiert.

*Weg:* Bedienen · *Quelle:* [Pipeline-API](../../api/pipeline.md)

### Situation

Gruppe von Datensatzaufnahmen für einen bewusst geänderten Aufbau, etwa Blickwinkel oder Entfernung. Wiederholungsaufnahmen bleiben in derselben Gruppe; eine neue Uhrzeit allein erzeugt keine unabhängige Situation.

*Weg:* Bedienen · *Quelle:* [Datensatz sammeln](11-datensatz-sammeln.md)

### Statistische Obergrenze

Für die Abnahme geforderte obere Grenze der Quote unerkannter Fehlablesungen. Null beobachtete Fehler allein reichen nicht als Zusage für beliebige Geräte; Nenner und Geräteinstanzen sind mit anzugeben.

*Weg:* Bedienen · *Quelle:* [Daten und Abnahme](../uebersicht/daten-und-abnahme.md)

### Synthetische Daten

Generierte Bilder für Funktionsprüfungen und gezielte Fehlerfälle. Sie ergänzen reale Daten, zählen aber nie zum realen Testset und belegen keine Trefferquote an realen Geräten.

*Weg:* Bedienen · *Quelle:* [Validierung](../VALIDATION.md)

### `TESTLAUF.json`

Datei zur Kennzeichnung eines Laufs mit übergangener Lesesperre. Der gesamte Lauf liefert keine freigegebenen Messwerte, auch wenn einzelne Pipeline-Records `VALID` melden; die technische Sperre im Audit ist noch unvollständig.

*Weg:* Bedienen · *Quelle:* [Kamera-Livevorschau](10-kamera-livevorschau.md)

### Unerkannte Fehlablesung

Ein als gültig freigegebener Wert, der gegenüber dem unabhängig erfassten Anzeigewert falsch ist. Dieser kritische Fehlermodus braucht eine eigene Rate samt Nenner und statistischer Obergrenze für die Abnahme.

*Weg:* Bedienen · *Quelle:* [Daten und Abnahme](../uebersicht/daten-und-abnahme.md)

### Vertreter

Für den Export ausgewählte Probe einer Situation. Bei genau einer Aufnahme wird sie automatisch verwendet; bei mehreren ohne ausdrückliche Auswahl exportiert die gesamte Situation kein Bild.

*Weg:* Bedienen · *Quelle:* [Datensatz sammeln](11-datensatz-sammeln.md)

### Zielbox

Grobe rechteckige Markierung der gewünschten Zahlenzeile im Sammelmodus, ohne Segmentraster oder Ziffernzellen. Sie ist Prüfdatenmaterial und gelangt nicht in Leser, Freigabe, Tracker oder serielle Ausgabe.

*Weg:* Bedienen · *Quelle:* [Datensatz sammeln](11-datensatz-sammeln.md)

## Werkbank und Bedienung

### Auto-Setup

Einstellhilfe der älteren Workbench: Sie bewertet Kamerakombinationen über mehrere Bilder und bietet einen übernehmbaren Vorschlag. Im Server mit gemeinsamem Kamerabesitzer erfolgt die Kamerabedienung über `/live`.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Bedienbestätigung

Namentliche Bestätigung von Einrichtung, Einheit und Format auf `/live`. Erst danach werden Profil und Bestätigung gespeichert; FEHLER sperrt sie, WARNUNG verlangt eine ausdrückliche Kenntnisnahme.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `cell-text.json`

Datei im Live-Einrichtungsordner mit ursprünglichem und maskiertem Zellentext sowie dessen Quelle. Sie macht nachvollziehbar, welche schwankenden Zellen beim Gegenlesen ausgenommen wurden.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `commands.jsonl`

Protokoll eines Live-Werteplans mit jedem Befehlsbyte und seiner BOOTTIME-Zeit. Es entsteht zusätzlich zur getrennten Referenzaufzeichnung und dokumentiert die Eingriffe am GSV-2AS.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `confirmation.json`

Datei der namentlichen Bedienbestätigung neben dem bestätigten Live-Profil. Sie hält unter anderem eine ausdrücklich angenommene angepasste Lesetoleranz fest; diese bleibt nicht validiert.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Datensatz-Sammelmodus

Geführter Werkbankablauf zum Sammeln realer Prüfbilder mit Gerät, Situation, Zielbox und sichtbarem Text. Er benötigt kein Produktionsprofil und ändert keine Freigaberegeln des Messpfads.

*Weg:* Bedienen · *Quelle:* [Datensatz sammeln](11-datensatz-sammeln.md)

### `dispread live`

Lokale Steuerbefehle für Live-Status, Einrichtung, Kameraneuverbindung und Laufstopp über den privaten Socket. Bestätigung und Laufstart sind darüber nicht möglich; sie verlangen die angemeldete Oberfläche.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `dispread serve`

Startet den Werkbankserver mit geschützter Oberfläche und Live-Seite. Während der Serverlaufzeit hält der gemeinsame Kamerabesitzer die StreamCam auch nach einem Messlaufstopp belegt.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `dispread stop`

Beendet den Werkbankserver über den privaten lokalen Unix-Socket. Der Befehl unterscheidet sich von `dispread live stop`, das nur den Messlauf stoppt; die Web-API bietet keinen Fernabschaltbefehl.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `dispread tui`

Terminalansicht der Workbench-Einstelltabelle, etwa für SSH. Zeilen, Optionen und Aktionen stammen aus derselben Quelle wie im Browser; `q` verlässt die Ansicht, ohne die Kamera zu beenden.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `failure.json`

Fehlerdatei im Live-Einrichtungsordner mit Abbruchschritt, Grund und UTC-Zeit. Sie dokumentiert einen gescheiterten Einrichtungsschritt neben den Bildern und Berichten.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Fokus-Sweep

Suche nach dem schärfsten Fokuswert im geführten Ernte-Assistenten. Sie steht vor den beiden zeitlich getrennten Standbildern und der Anpassung des Punktrasters.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Gegenlesen

Prüfung des Lesers an Einrichtungsstandbildern gegen deren Referenztext. Unmaskierte Zellen müssen lesbar sein und übereinstimmen; ein Widerspruch sperrt Bestätigung und Lauf. Der Referenztext korrigiert keinen Messwert.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `harvest-setup.py`

Geführter Ernte-Assistent: `assist` sucht Fokus und Raster und erzeugt einen Vorschlag mit Kontrollbildern. Erst `confirm` bestätigt diesen als Sitzungsprofil; die Einrichtungshilfe belegt keine allgemeine Gerätefreigabe.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Lesesperre

Sperre des normalen Live-Laufstarts bei fehlendem oder nicht erfolgreichem Gegenlesen. Bei WARNUNG kann die Einrichtung bestätigt werden; ein Widerspruch zur Referenz sperrt auch die Bestätigung.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `/live`

Geschützte Live-Seite der Werkbank für StreamCam-Einrichtung, namentliche Bestätigung und Messlauf. Sie liest mit dem Dot-Matrix-Leser; ein Lauf setzt passende Vorlagen und gültige Timing-Kalibrierung voraus.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `proposal.json`

Vorschlag des Ernte-Assistenten nach Standbildern, Rasteranpassung und Prüfungen. Zusammen mit den Overlays dient er der menschlichen Kontrolle; erst die Bestätigung macht daraus ein Sitzungsprofil.

*Weg:* Bedienen · *Quelle:* [Projekt-Tour](../uebersicht/projekt-tour.md)

### Rückstellpunkt

Gespeicherter Registerzustand des GSV-2AS, gegen den ein Werteplan vor dem Schreiben geprüft wird und zu dem er beim Stoppen zurückkehrt. Nach Stromausfall oder `kill -9` ist eine manuelle Rückstellung nötig.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Testlauf

Ausdrücklich markierter Live-Lauf, der die Lesesperre zu Testzwecken übergeht. Alle Daten des Laufordners sind von Messungen auszuschließen: Auch mögliche VALID-Records heben die Testmarkierung nicht auf; die Auditsperre ist unvollständig.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Werteplan

Zusätzlich bestätigte Folge von Normierungsfaktoren und Haltezeiten für kontrollierte GSV-2AS-Wertwechsel. Er verlangt einen gültigen Rückstellpunkt; beim Stoppen werden die Ausgangswerte zurückgeschrieben und geprüft.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Workbench

Bedienoberfläche mit Kamerabild, Log und Bash-Tabs. `/live` steuert Einrichtung und Messlauf; die ältere Werkbankseite erhält gedrosselte Bilder desselben Kamerabesitzers, ihr Modus `run` bleibt ein Vorschauzustand.

*Weg:* Bedienen · *Auch:* Werkbank · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### Zellentext

Erwarteter Text der ersten neun Anzeigezellen bei der Live-Einrichtung, seriell gelesen oder manuell eingegeben. Acht Zeichen werden um eine leere neunte Zelle ergänzt; `?` maskiert schwankende Zellen beim Gegenlesen.

*Weg:* Bedienen · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

## Konfiguration

### `AeEnable`

Historischer IMX500-/Picamera2-Regler für die Belichtungsautomatik der älteren Workbench. Ausschalten übernimmt die aktuellen Istwerte als Startpunkt und entsperrt Belichtungszeit und Verstärkung; kein StreamCam-Control.

*Weg:* Konfigurieren · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `AnalogueGain`

Historischer IMX500-/Picamera2-Regler für die Verstärkung in der älteren Workbench. Bei ausgeschalteter Belichtungsautomatik einstellbar; die aktuelle StreamCam verwendet andere UVC-Control-Namen.

*Weg:* Konfigurieren · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `camera.json`

Explizite Einstellungsdatei für die aktive `v4l2://`-Quelle. Sie beschreibt die StreamCam nach dem CameraSettings-Vertrag mit USB-ID, Bildformat, Bildrate und bestätigten Fokus-, Belichtungs-, Weißabgleich- und Verstärkungsreglern.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### `camera_auto_detect`

Historische Boot-Konfiguration der IMX500-Anbindung. Sie prüft die Kameraanschlüsse nur beim Booten; nachträgliches Anstecken wurde erst durch einen Neustart erkannt. Sie gehört nicht zum aktuellen USB-StreamCam-Ablauf.

*Weg:* Konfigurieren · *Quelle:* [Kamera-Inbetriebnahme](../CAMERA_COMMISSIONING.md)

### `CameraSettings`

Vertrag für die Einstellungen, die die UVC-Quelle an der StreamCam setzt und zurückliest. Die vier aufbauspezifischen Regler sind Pflicht; fehlende oder zusätzliche Regler werden abgelehnt, fehlende Werte nicht geraten.

*Weg:* Konfigurieren · *Quelle:* [Bildquellen-API](../../api/frames.md)

### `confirm_frames`

Anzahl übereinstimmender Bilder vor einer Freigabe. Der Live-Pfad verlangt zwei; der allgemeine GateConfig-Default ist eins. Die Mehrbildbestätigung verzögert die Freigabe, glättet aber keine echten Messwertsprünge.

*Weg:* Konfigurieren · *Quelle:* [Projekt-Tour](../uebersicht/projekt-tour.md)

### `decimals`

Zahl der Nachkommastellen im DisplayLayout. `None` bedeutet einen freien, zu erkennenden Dezimalpunkt. In der älteren Segmentleser-Vorschau führt „unbestimmt“ ohne optische Punktprüfung zur Ablehnung statt zur automatischen Erkennung.

*Weg:* Konfigurieren · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

Weitere Bedeutung des Felds: [DisplayLayout-Vertrag](../../api/vertraege.md).

### `digits`

Anzahl der Ziffernstellen im DisplayLayout, ohne die separat behandelte Vorzeichenstelle. Die ältere Workbench bietet dafür 3–8 Stellen; ihr Segmentleser liest gegen dieses konfigurierte Raster.

*Weg:* Konfigurieren · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

Auswahl in der Oberfläche: [Kamera-Workbench](10-kamera-livevorschau.md).

### `expected_unit`

Erwartete Einheit aus dem bestätigten Profil in GateConfig. Sie wird bei der Freigabe geprüft; sie ist keine anhand der Referenz nachträglich korrigierte Einheit.

*Weg:* Konfigurieren · *Quelle:* [Freigabe-API](../../api/validate.md)

### `ExposureTime`

Historischer IMX500-/Picamera2-Regler für die Belichtungszeit in Mikrosekunden. In der älteren Workbench bei aktiver Belichtungsautomatik gesperrt; die aktuelle StreamCam nutzt UVC-Regler.

*Weg:* Konfigurieren · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `exposure_time_absolute`

Aufbauspezifischer UVC-Belichtungsregler der StreamCam. Einer der vier verpflichtenden Regler im CameraSettings-Profil; die Quelle setzt ihn nach dem Abschalten der Automatik und den festen Kamerareglern.

*Weg:* Konfigurieren · *Quelle:* [Bildquellen-API](../../api/frames.md)

### `focus_absolute`

Fester UVC-Fokuswert der StreamCam im CameraSettings-Profil. Für reproduzierbare Aufnahmen wird die Fokusautomatik ausgeschaltet und der gesetzte Fokuswert zurückgelesen.

*Weg:* Konfigurieren · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `focus_automatic_continuous`

UVC-Regler für die kontinuierliche Fokusautomatik der StreamCam. CameraSettings schaltet ihn vor den weiteren Reglern aus; der aufbauspezifische Fokus kommt anschließend aus dem Profil.

*Weg:* Konfigurieren · *Quelle:* [Bildquellen-API](../../api/frames.md)

### `gain`

Aufbauspezifischer UVC-Verstärkungsregler der StreamCam im CameraSettings-Profil. Er gehört zu den vier verpflichtenden Reglern und wird nach den Automatik- und festen Reglern gesetzt.

*Weg:* Konfigurieren · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Geräteprofil

Geplanter dauerhafter Vertrag für bestätigte Displayannahmen wie Layout, Einheit, Bildgröße und ROI. Ein allgemeiner ProfileStore samt config/profiles-Schema fehlt; das vorhandene SessionProfile beschreibt dagegen eine einzelne Aufstellung.

*Weg:* Konfigurieren · *Quelle:* [Geräteprofile](04-geraeteprofile.md)

### `has_sign`

Angabe im DisplayLayout, ob eine eigene Vorzeichenstelle vorhanden ist. Diese wird unabhängig von den Ziffernstellen geprüft; das Layout stammt aus dem bestätigten Profil und wird nicht erraten.

*Weg:* Konfigurieren · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `profile.json`

Datei des bestätigten Profils einer Live-Sitzung, neben confirmation.json im Sitzungsordner. Sie ersetzt keinen allgemeinen ProfileStore für wiederkehrende Geräte; ältere Workbench-Profile liegen getrennt unter var/workbench/profiles/.

*Weg:* Konfigurieren · *Quelle:* [Geräteprofile](04-geraeteprofile.md)

### `reader_tolerance`

Metadaten der ausdrücklich angenommenen angepassten Lesetoleranz in Bestätigung und Lauf. Der Faktor verlangt eine serielle Gegenprobe in dieser Aufstellung und bleibt nicht validiert; er ist keine allgemeine Messfreigabe.

*Weg:* Konfigurieren · *Quelle:* [Kamera-Workbench](10-kamera-livevorschau.md)

### `SessionProfile`

Profil einer bestätigten Ernte- oder Live-Aufstellung mit Kamera, Punktraster und Referenzbild. Es entsteht durch Ernte-Bestätigung oder auf `/live` und ist vom noch geplanten dauerhaften Geräteprofil zu unterscheiden.

*Weg:* Konfigurieren · *Quelle:* [Geräteprofile](04-geraeteprofile.md)

### `sign_cell_ratio`

Breite der Vorzeichenstelle als Anteil einer Ziffernzelle im DisplayLayout. Der Parameter beschreibt die Rastergeometrie; die Vorzeichenstelle bleibt getrennt von den Ziffernstellen.

*Weg:* Konfigurieren · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `stale_after_ns`

Frist ohne neue Freigabe, nach der das Gate einen Wert als STALE behandelt, in Nanosekunden. Der Default beträgt 500 ms. Blockierende Zustandsflags wie Trackingverlust bleiben im Audit unmittelbar UNREADABLE.

*Weg:* Konfigurieren · *Quelle:* [Freigabe-API](../../api/validate.md)

### `white_balance_temperature`

Aufbauspezifischer UVC-Weißabgleichsregler der StreamCam im CameraSettings-Profil. Er ist verpflichtend; die Weißabgleichsautomatik wird vor dem Setzen der Profilregler ausgeschaltet.

*Weg:* Konfigurieren · *Quelle:* [Bildquellen-API](../../api/frames.md)

## Doku und Projektpflege

### Anime.js

Animationslaufzeit für Projekt-Tour und räumlichen Ebenenwechsel der Roadmap. Das Wiki verwendet die vorhandene lokale Kopie unter `docs-site/assets/vendor/`; dafür braucht es weder einen CDN-Abruf noch einen npm-Build-Schritt.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### API-Referenz

Beim Bauen direkt aus den Docstrings unter `src/dispread` erzeugte Code-Dokumentation. Signaturen und Docstrings spiegeln den Code; die einleitenden Texte ordnen dessen aktuellen Einsatz entlang der Verarbeitungskette ein.

*Weg:* Entwickeln · *Quelle:* [API-Überblick](../../api/index.md)

### `CHANGELOG.md`

Änderungshistorie für nach außen sichtbare Änderungen. Ein neuer Eintrag steht oben und beschreibt Problem, Änderung und Konsequenz; bei Änderungen unter `src/` ist er Pflicht.

*Weg:* Entwickeln · *Quelle:* [Anleitungsübersicht](README.md)

Zweck der Datei: [Dokumentationsübersicht](../README.md).

### `docs-site.sh`

Skript zum Bauen der Doku und für die lokale Vorschau. `build -s` gehört zur Prüfung vor dem Merge, `serve` startet die Vorschau; vor beiden wird die OQ-Übersicht gegen TODO und offene Fragen geprüft.

*Weg:* Entwickeln · *Quelle:* [Doku-Hosting und Pflege](../HOSTING.md)

### `lab_journal.md`

Fortlaufendes Laborjournal für Aufbau, Beobachtung und Deutung je Experiment. Auch Fehlversuche gehören hinein; die Datei wird um Einträge ergänzt und bewahrt den Versuchsverlauf.

*Weg:* Entwickeln · *Quelle:* [Dokumentationsübersicht](../README.md)

### `mkdocstrings`

Werkzeug zur Erzeugung der API-Referenz aus Python-Docstrings. Es gehört mit `mkdocstrings-python` zu den gepinnten Doku-Abhängigkeiten in der eigenen `.venv-docs` und ist keine Laufzeitabhängigkeit des Messpfads.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### `oq-index.py`

Generator der Übersicht in `docs/open-questions.md`. Nach Änderungen an OQ-Titeln, Status oder aktiven Aufgaben und OQ-Verweisen in TODO wird er ausgeführt; die Reihenfolge von „Jetzt“ folgt den unerledigten TODO-Aufgaben.

*Weg:* Entwickeln · *Quelle:* [Doku-Hosting und Pflege](../HOSTING.md)

### Playwright

Browserprüfwerkzeug für die Doku-Seite. Die Suite `tests/docs-site.spec.ts` prüft die interaktive Ansicht; vor dem Merge wird sie mit `npx playwright test -c playwright.docs.config.ts` ausgeführt.

*Weg:* Entwickeln · *Quelle:* [Doku-Hosting und Pflege](../HOSTING.md)

### Projekt-Tour

Animierte Einführung in das Projekt mit einzeln anwählbaren Schritten und Links zur Doku. Die Bühne zeigt schematische Abläufe; ihre Beispielwerte sind keine Messergebnisse. Konzept, Messpfad und API bleiben maßgeblich.

*Weg:* Bedienen · *Quelle:* [Projekt-Tour](../uebersicht/projekt-tour.md)

### `project_history.md`

Projektgeschichte für Entscheidungen, die aus dem Code allein nicht ersichtlich sind. Ein Eintrag hält Problem, Entscheidung, Begründung, Alternativen und Konsequenz fest.

*Weg:* Entwickeln · *Quelle:* [Dokumentationsübersicht](../README.md)

### Roadmap

Phasenplan P0–P8 mit harten Exit-Kriterien und belegtem Stand. Gebaute Werkzeuge oder einzelne Nachweise ersetzen keine vollständige Systemabnahme; die projektweite Arbeitsreihenfolge steht in TODO.

*Weg:* Entwickeln · *Quelle:* [Roadmap](../ROADMAP.md)

### `status.md`

Momentaufnahme des aktuellen Projektstands mit Blockern und den nächsten drei Schritten. Diese Datei wird neu geschrieben und überschrieben, statt einen fortlaufenden Verlauf anzuhängen.

*Weg:* Entwickeln · *Quelle:* [Dokumentationsübersicht](../README.md)

### `TODO.md`

Arbeitsliste der aktiven Aufgaben. Ihre Reihenfolge bestimmt den projektweiten Arbeitsablauf und die Anzeige „Jetzt“ in der OQ-Übersicht; diese Kennzeichnung ist kein eigener OQ-Status.

*Weg:* Entwickeln · *Quelle:* [Doku-Hosting und Pflege](../HOSTING.md)

Projektweite Reihenfolge: [Roadmap](../ROADMAP.md).

### `tour-facts.py`

Prüfskript für die Fakten der Projekt-Tour. Die Vorabprüfung des Doku-Pflegeablaufs ruft es mit `--check` auf; bei Abweichungen bricht der Job vor dem Codex-Aufruf ab und nennt die betroffenen Tour-Schritte.

*Weg:* Entwickeln · *Quelle:* [Doku-Hosting und Pflege](../HOSTING.md)

### `VALIDATION.md`

Nachweisdokument für Fehlerklassen, Messreihen und Abnahmekriterien. Es sammelt Belege gegen die stillen Fehlermodi aus Konzept §7 und dient zur Bewertung des belegten Erkennungsumfangs.

*Weg:* Entwickeln · *Quelle:* [Dokumentationsübersicht](../README.md)

### Zensical

Werkzeug zum Erzeugen der statischen Doku-Seite aus `docs/` und den Markdown-Dateien im Projektwurzelverzeichnis. Seine Build-Abhängigkeiten liegen in der getrennten `.venv-docs`, nicht in der Projekt-venv des Messpfads.

*Weg:* Entwickeln · *Quelle:* [Abhängigkeiten](../dependencies.md)

### `zensical.toml`

Konfigurationsdatei der Doku-Seite. Darin werden die Ziele für Begriffsvorschauen gezielt aktiviert; zusätzliche Ziele brauchen kurze Zielabschnitte und einen passenden Browsertest.

*Weg:* Konfigurieren · *Quelle:* [Doku-Hosting und Pflege](../HOSTING.md)
