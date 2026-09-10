# Validierung — Messwerte und Abnahmekriterien

Jede Zahl hier trägt Datum, Datensatz und Verweis auf den Lauf. Aufbau und
Deutung von Experimenten gehören nach [lab_journal.md](lab_journal.md).

⚠️ **Die Erkennungskennzahlen stammen bisher von synthetischem Material.** Es
existiert noch kein Datensatz echter Geräte ([OQ-04](open-questions.md)).
Konzept.md §9 ist ausdrücklich: synthetische Daten ergänzen, sie zählen **nie**
zum Testset. Technische Kamerastream-Tests sind gesondert gekennzeichnet und
belegen keine Erkennungszuverlässigkeit im Realbetrieb.

## Fehlerklassen — getrennt zu zählen

Eine hohe Zeichenquote genügt nach Konzept.md §10 nicht. Maßgeblich ist der
**vollständige Datensatz** einschließlich Vorzeichen, Dezimalpunkt, Einheit und
Zeitbezug.

| Klasse | Definition | Gewicht |
| --- | --- | --- |
| `wrong_digit` | mindestens eine Ziffer falsch, Format korrekt | kritisch |
| `missing_sign` | Vorzeichen nicht erkannt oder fälschlich erkannt | **kritisch, eigene Quote** |
| `wrong_decimal_point` | Dezimalpunkt fehlt, zusätzlich oder an falscher Stelle | **kritisch, eigene Quote** |
| `wrong_unit` | Einheit falsch erkannt oder falsch bestätigt | kritisch |
| `display_confusion` | Neben- statt Hauptanzeige gelesen | **kritisch, eigene Quote** |
| `wrong_state` | Überlauf, Menü oder Hold als gültiger Wert gelesen | kritisch |
| `stale_unmarked` | veralteter Wert als gültig ausgegeben | **kritisch, Zielwert 0** |
| `false_reject` | korrekt lesbarer Wert abgelehnt | Verfügbarkeitsproblem, nicht Sicherheitsproblem |
| `missed_record` | Datensatz ausgelassen | Verfügbarkeit |

Zwei Kennzahlen sind nicht verhandelbar: die **Rate unerkannter
Fehlablesungen** (als `VALID` ausgegeben, aber falsch) und die **Rate der
Falschablehnungen**. Nur die erste ist metrologisch gefährlich, nur die zweite
ist praktisch störend.

## Messreihe 2026-09-07 — 7-Segment-Dekoder auf synthetischem Material

Lauf: `examples/16_end_to_end_headless.py`, Backend `sevenseg` v2, Layout
5 Stellen / 2 Nachkommastellen / Einheit N, 40 Frames je Zeile, Ausschnitt
400×160. Wertfolge enthält bewusst echte Sprünge und Vorzeichenwechsel.

| Störung | korrekt | abgelehnt | **still falsch** |
| --- | --- | --- | --- |
| unverändert | 40 | 0 | **0** |
| Rauschen σ=0,3 | 40 | 0 | **0** |
| Unschärfe σ=3 | 40 | 0 | **0** |
| Unschärfe σ=8 | 40 | 0 | **0** |
| Unschärfe σ=10 | 40 | 0 | **0** |
| Unschärfe σ=12 | 17 | 23 | **0** |
| Unschärfe σ=15 | 0 | 40 | **0** |
| **Glanz 0,9** | 3 | 35 | **2** |
| Perspektive 6 % | 0 | 40 | **0** |

Deutung:

* **Rauschen und Unschärfe sind beherrschbar und degradieren gutartig.** Bis
  σ=10 keine Abweichung, ab σ=12 kippt der Dekoder in die Ablehnung (17
  korrekt, 23 abgelehnt), ab σ=15 lehnt er vollständig ab — und in keiner
  Stufe entsteht eine stille Fehlablesung. Das ist die gewünschte Richtung des
  Versagens.
* **Reflexionen sind der gefährliche Fall.** Bei starkem Glanz entstehen 2 von
  40 stillen Fehlablesungen — also Werte, die als `VALID` ausgegeben und
  trotzdem falsch sind. Das deckt sich mit Konzept.md §9, das Reflexionen als
  Hauptproblem des optischen Aufbaus nennt. Erste Gegenmaßnahme ist bereits
  implementiert: der Leser meldet den Anteil gesättigter Bildpunkte, und ab 2 %
  setzt er das Flag `glare`, das die Freigabe blockiert. Das hat die stillen
  Fehlablesungen von 13 auf 2 gesenkt. Die verbleibenden 2 sind **nicht**
  gelöst.
  → **Konsequenz für den Aufbau:** Abschirmung und Beleuchtung sind keine
  Feinarbeit, sondern Voraussetzung. Siehe [OPTICAL_SETUP.md](OPTICAL_SETUP.md).
* **Perspektive führt zur vollständigen Ablehnung**, weil die bestätigte ROI
  nicht mehr passt. Das ist korrektes Verhalten des `manual_roi`-Pfads — die
  Wiederfindung ist Aufgabe der Lokalisierung bzw. des Trackings.

### Betriebszustände und Segmentausfall

| Fall | Ergebnis |
| --- | --- |
| Überlauf (alle Stellen zeigen `-`) | Flag `overflow`, kein Zahlenwert |
| Segmentausfall (Stelle 2, Segment b) | abgelehnt; Kandidaten `2` und `6` als Evidenz festgehalten |
| Anzeige nicht lokalisierbar | `unreadable`, danach `stale` — nie `valid` |

## Nachweise gegen die „stillen" Fehlermodi aus Konzept §7

Diese Fehlermodi werden nicht „vermieden", sondern jeder hat einen Test, der
fehlschlägt, wenn das System sie zeigt. Alle in
`tests/test_gate_und_referenz.py`.

| Fehlermodus | Test | Stand |
| --- | --- | --- |
| Altwert läuft unmarkiert weiter | `test_nach_verlust_wird_der_wert_veraltet_nicht_weitergefuehrt`, `test_verdeckte_anzeige_liefert_keinen_gueltigen_datensatz` | ✅ grün |
| Plausibilitätsregeln glätten echte Sprünge | `test_echte_spruenge_werden_nicht_geglaettet` (Sprung 1,0 → 500,0 → −500,0 kommt unverändert durch) | ✅ grün |
| Referenz korrigiert den DUT-Wert | `test_referenzwert_kann_die_erkennung_nicht_beeinflussen` (identischer Lauf mit um 20 % verfälschtem Referenzwert → identische Datensätze), `test_leser_bekommt_den_referenzwert_nicht_als_parameter` (strukturelle Sperre über die Signatur) | ✅ grün |
| Konfidenz als Fehlerwahrscheinlichkeit missverstanden | `test_konfidenz_ist_nicht_als_kalibriert_deklariert` — `declares_confidence_calibrated` bleibt `False`, solange keine Kalibriermessung existiert | ✅ grün |
| Mehrbildbestätigung verschweigt ihre Verzögerung | `test_mehrbildbestaetigung_meldet_ihre_zeitspanne` — `confirmation_span_ns` steht im Datensatz | ✅ grün |

Noch **nicht** abgedeckt: Übereinstimmung zweier Leser als Scheinbeweis
(braucht das Tesseract-Backend, [OQ-15](open-questions.md)), und der
Reliability-Plot der Konfidenz gegen echte Fehlerraten (braucht reale Daten).

## Datensatzaufbau

* **Splitgrenze ist die Geräteinstanz, nie der Frame.** Konzept §9 warnt
  ausdrücklich vor Nachbarframes derselben Aufnahme in Training und Test.
  Durchzusetzen als Gruppensplit über `device_instance_id`, mit einem Test, der
  bei Verletzung fehlschlägt.
* **Sperrgeräte:** mindestens zwei Geräteinstanzen, bevorzugt ein ganzer
  Hersteller, werden vor jeder Entwicklung gesperrt und **einmalig** in der
  Abnahme ausgewertet. Kein Tuning, keine Schwellenanpassung, keine
  Fehleranalyse darauf.
* **Maßstab für „genug Daten"** ist nicht die Frame-Anzahl, sondern die
  Abdeckung: alle Ziffern × Positionen, Vorzeichen, jede Dezimalpunktposition,
  jede Einheit, Überlauf, Menü, Anzeigewechsel, Reflexion, Unschärfe,
  angeschnittenes Display, jede Displaytechnik.

## Abnahmekriterien

Werden **vor** der Abnahme festgelegt (Konzept §10) und brauchen
[OQ-02](open-questions.md) und [OQ-04](open-questions.md) als Eingang. Die Form
steht jetzt fest, damit später nur Zahlen eingesetzt werden:

* Rate unerkannter Fehlablesungen auf Sperrgeräten ≤ *X* — anzugeben mit
  statistischer Obergrenze, keine „99,x %"-Angabe ohne Konfidenzintervall.
* Falschablehnungsrate ≤ *Y* bei ordnungsgemäßem optischem Aufbau.
* Zeitbezug: Gesamtunsicherheit (siehe [TIMING.md](TIMING.md)) ≤ *OQ-02-Wert*,
  mit Nachweis pro Einzelbeitrag.
* Alle Tests gegen die stillen Fehlermodi bestanden.
* Einrichtungsdauer je Gerätewechsel ≤ *Z*, gemessen mit echten Laboranten.
  Zu berücksichtigen: 6,8 s IMX500-Warmlauf kommen hinzu.
* 72-h-Dauerlauf ohne unmarkierten Altwert und ohne Speicherwachstum.

## 2026-09-08 — Technischer Kamerastream-Smoke-Test

Reale Kameraaufnahme, **kein Datensatz zur Display-Erkennungsvalidierung**.
Beginn: 2026-09-08T10:31:59.111530+00:00 (UTC). Aufbau/Deutung:
[Laborjournal](lab_journal.md), Eintrag „Kameravorschau über lokalen HTTP-Stream“.
Artefakte: `var/examples/17_camera_display_preview/diagnostic.json`,
`camera.log`, `preview.jpg`.

| Größe | Ergebnis |
| --- | --- |
| Bildgröße | 960 × 720 Pixel |
| Angeforderte Bildrate | 15 Bilder/s |
| Letzte geprüfte Bildnummer | 50 |
| Mittlere JPEG-Verarbeitungsrate seit erstem Bild | 15,0 Bilder/s, CLOCK_MONOTONIC |
| Erstes übertragenes Diagnose-JPEG | 45.813 Bytes |
| Status bei letzter Abfrage | live, kein Kamerafehler |
| Beenden per SIGTERM | Exit 0, kein erzwungenes Kill |

Die Verarbeitungsrate ist keine Kamera-zu-Browser-Latenz. Windows/SSH und
Erkennungsqualität an echten Anzeigen sind noch nicht abgenommen.

## 2026-09-08 — Workbench-Kameradienst nach Modularisierung

Reale Kamera, technischer Kurztest ohne Erkennungsabnahme. Ergebnisabfrage
2026-09-08T12:03:21.753165+00:00 (UTC). Artefakt:
`var/workbench/diagnostics/camera-smoke.json`; Aufbau im Laborjournal.

| Größe | Ergebnis |
| --- | --- |
| Stream | 960×720 RGB888, 15 fps angefordert |
| Letzte Bildnummer | 25 |
| Software-Verarbeitungsrate | 14,8 Bilder/s, CLOCK_MONOTONIC |
| Ist-Belichtung | 24.631 µs |
| Ist-Verstärkung | 1,4992679 |
| Ist-FrameDuration | 66.657 µs |
| SensorTimestamp | 18.366.022.890.000 ns, SENSOR_BOOTTIME |
| Zeitstempelsemantik / Unsicherheit | unbekannt / None |
| Fehler / Beenden | keiner / Thread beendet |

Keine Aussage über End-to-End-Latenz oder Qualität von Auto-Setup/Erkennung.

## 2026-09-08 — Fokus- und Schärfemessung (technisch)

Reale Kameraaufnahme, **kein Datensatz zur Display-Erkennungsvalidierung** —
im Bild war ein Monitor, keine Messverstärkeranzeige. Beginn:
2026-09-08T13:14:49.641331+00:00 (UTC). Aufbau und Deutung:
[Laborjournal](lab_journal.md), Eintrag „Fokusdiagnose und blockierter Sensor".
Artefakte: `var/workbench/diagnostics/focus-probe.json`, `focus-960x720.jpg`,
`focus-2028x1520.jpg`.

| Größe | 960 × 720 | 2028 × 1520 |
| --- | --- | --- |
| Laplace-Varianz, Median aus 8 Bildern | 11,53 | 8,24 |
| Laplace-Varianz, Spanne | 11,32 – 11,63 | 8,13 – 8,32 |
| Tenengrad, Median | 1.406,75 | 372,6 |
| Kontrast (P95−P5)/255 | 0,886 | 0,890 |
| Gesättigter Anteil | 0,058 | 0,058 |
| Mittlere Helligkeit | 0,581 | 0,579 |
| Ist-Belichtung / Verstärkung (Automatik) | 33.044 µs / 2,032 | 33.044 µs / 2,032 |

**Fokus-Controls der IMX500: keine.** `Picamera2.camera_controls` liefert 29
Controls, davon **null** mit `Af`, `Lens` oder `Focus` im Namen. `Sharpness`
ist ISP-Nachschärfung. Softwareseitige Fokusverstellung ist damit ausgeschlossen.

Die Schärfewerte sind **relativ** und nur innerhalb desselben Bildinhalts und
derselben Streamgröße vergleichbar; die Zahl fällt mit steigender Auflösung
allein durch die Normierung. Sie belegen kein Erkennungsergebnis. Der
gesättigte Anteil von 5,8 % liegt über der 2-%-Glanzschwelle aus
[OPTICAL_SETUP.md](OPTICAL_SETUP.md). Bei 33 ms Belichtung ist Bewegungsunschärfe
nicht ausgeschlossen; die trennende Messung mit kurzer Belichtung steht aus
([OQ-22](open-questions.md) blockiert sie bis zum Reboot).

## 2026-09-08 — Unschärfeform aus Lichtreflexen (technisch)

Reale Aufnahme, **kein Erkennungsdatensatz**. Vollbild 4056×3040 von 15:31:41
Ortszeit. Aufbau und Methode: [Laborjournal](lab_journal.md), Eintrag
„Unschärfeform gemessen".

| Reflex | Hauptachse | Nebenachse | Verhältnis |
| --- | --- | --- | --- |
| 1 | 50,1 px | 43,3 px | 1,16 |
| 2 | 48,7 px | 34,2 px | 1,42 |
| 3 | 35,0 px | 29,2 px | 1,20 |
| 4 | 34,2 px | 25,8 px | 1,33 |
| 5 | 29,4 px | 23,9 px | 1,23 |
| **Median** | **35,0 px** | **29,2 px** | **1,20** |

Laplace-Varianz Vollbild 22,26, Bildmitte 12,39.

**Deutung:** runde Scheiben statt Striche ⇒ **Defokussierung**. Bewegungsunschärfe
wäre in einer gemeinsamen Richtung gestreckt (Verhältnis deutlich über 1,8) und
ist damit ausgeschlossen. Die Zahlen belegen keine Erkennungsleistung.

## 2026-09-08 — Fokus eingestellt, Bildqualität im Anzeigebereich (technisch)

Reale Aufnahme eines **BK Precision 5491B** Tischmultimeters, nicht eines
GSV-Messverstärkers — technische Abnahme der Bildkette, **kein
Erkennungsdatensatz**. Stream 960×720 RGB888, Belichtungsautomatik. Aufbau:
[Laborjournal](lab_journal.md), Eintrag „Fokus eingestellt". Artefakt:
`var/workbench/diagnostics/fokus-erreicht-960x720.jpg`.

Schärfeverlauf beim mechanischen Fokussieren, Laplace-Varianz über das ganze
Bild, jeweils bester Wert einer Sitzung:

| Zustand | Wert |
| --- | --- |
| Ausgangslage (Objektiv unberührt) | 11,53 |
| nach erstem Drehen | 75,0 |
| nach weiterem Drehen | **216,6** |

Im Anzeigebereich des gespeicherten Bildes:

| Größe | Wert | Zielmarke |
| --- | --- | --- |
| Ziffernhöhe | **≈ 37 px** | ≥ 30 px ([OPTICAL_SETUP.md](OPTICAL_SETUP.md)) |
| Laplace-Varianz | 480,2 | — |
| Kontrast (P95−P5)/255 | 0,749 | — |
| Gesättigter Anteil | **0,0000** | < 0,02 (Glanzschwelle) |
| Helligkeit | 0,392 | — |
| Fläche des Anzeigebereichs | 15,0 % des Bildes | — |

Ganzes Bild: Laplace-Varianz 221,9, gesättigter Anteil 0,0471 — die Sättigung
liegt außerhalb der Anzeige (weißes Papier, Umgebung), nicht im Display.

**Bewertung:** Die 960×720-Konfiguration erreicht an diesem Gerät und Abstand
die Ziffernhöhen-Zielmarke ohne `ScalerCrop`. Damit ist eine frühere Schätzung
in dieser Datei korrigiert: die Rechnung „960×720 liefert nur ~24 px" galt für
10 mm Ziffern bei 30 cm und trifft dieses Gerät nicht. Die Zahlen belegen
Bildqualität, **keine** Erkennungsleistung — dafür fehlt weiter ein echter
Gerätedatensatz ([OQ-04](open-questions.md)).

## 2026-09-09 — Erste Workbench-OCR-Prüfung an einem realen VFD-Bild

Kein kalibrierter Datensatz und keine Abnahme. Aufbau und Deutung:
[Laborjournal](lab_journal.md), Eintrag „Workbench-OCR: synthetischer Rundlauf
und erster VFD-Befund". Backend `sevenseg/2`, Layout 5 Stellen / 2
Nachkommastellen / Vorzeichen / bestätigte Einheit `mV`, Ausschnitt 400×160.
Die manuelle Wahrheit wurde nur nach der Erkennung verglichen und war kein
Parameter von Leser oder Gate.

| Quelle | Erwartung | Rohtext | Gate | Ergebnis |
| --- | --- | --- | --- | --- |
| synthetischer Integrationstest | `-012.34 mV` | `-012.34` | `valid` | Wert −12,34; `released=false` |
| gespeichertes BK-5491B-Realbild | `-000.13 mV` | `777?7` | `unreadable` | kein Wert; `unreadable_cells:1`, `no_value` |
| laufender Stream, 30 verschiedene Frames | nicht bestätigt | `?????` in 30/30 | `unreadable` in 30/30 | kein Wert; kein verwertbarer Gerätetest |

Beim gespeicherten Realbild: Crop-Schärfe 88,37, Segmentkontrast 0,4602,
kleinste Marge 0,6495, gesättigter Anteil 0,0000. Die feste
Segmentpunktgeometrie passt nicht zur VFD-Schrift; insbesondere ist die `1`
schmaler/anders positioniert als im synthetischen Generator. Die korrekte
Sicherheitsreaktion ist belegt — keine Ausgabe eines geratenen Zahlenwerts —,
nicht aber reale Lesefähigkeit. Weiterarbeit: [OQ-23](open-questions.md).

Der laufende Stream wurde ohne Streamneustart oder Geometrieänderung über die
bereits aktive Workbench geprüft (Sequenzen 34329–34358). Seine aktuelle Szene
konnte nicht visuell bestätigt werden; die aus dem älteren Bild übernommene ROI
hatte Crop-Schärfe 1,57. Deshalb gehen diese 30 Ablehnungen in keine
Erkennungsquote ein. Das aktive Profil wurde anschließend vollständig auf den
vorherigen Defaultzustand zurückgesetzt.

Artefakte:
`var/workbench/diagnostics/ocr-bk5491b-offline.jpg` und
`ocr-bk5491b-offline.json`. Die Bildquelle trägt `FILE_MTIME`; daraus wird
keine Zeit- oder Latenzaussage abgeleitet. Konfidenz bleibt unkalibriert,
`formatter_provisional=true` ist im Runartefakt festgehalten.

## 2026-09-09 — Workbench-Verarbeitungsbudget nach ROI-Umbau

Reiner Offline-Durchsatztest auf dem Pi, kein Kamerazeit- oder
End-to-End-Latenztest. Quelle war das gespeicherte 960×720-BK-Bild mit
`FILE_MTIME`; Dauer gemessen über je 100 Aufrufe mit `time.perf_counter()` in
CLOCK_MONOTONIC. Aufbau und Deutung im [Laborjournal](lab_journal.md).

| Pfad | Dauer je Bild | rechnerischer Durchsatz |
| --- | ---: | ---: |
| ROI unbestätigt, einschließlich Vollbild-Kandidatensuche | 30,837 ms | 32,4 Bilder/s |
| ROI bestätigt, OCR-Vorschau auf 5 Hz begrenzt | 5,801 ms | 172,4 Bilder/s |
| ROI bestätigt, OCR künstlich in jedem Bild erzwungen | 9,515 ms | 105,1 Bilder/s |

Die Zahlen belegen die lokale Rechenentlastung, nicht die Reaktionszeit im
Windows-Browser. Ein Nebenläufigkeitstest hält die Kandidatensuche künstlich an
und belegt, dass `snapshot()` währenddessen in unter 50 ms zurückkehrt. Der
isolierte simulierte Dienst ließ sich über `dispread stop` vollständig beenden.
Die reale Browser-/Kameraabnahme bleibt [OQ-24](open-questions.md).

## 2026-09-10 — Kosten der wieder aktivierten, gedrosselten Kandidatensuche

Bedienerrückmeldung: Nach einem Neustart mit bereits bestätigter ROI lief die
Vollbild-Kandidatensuche (gelbe Boxen) nie mehr — kein visueller Hinweis mehr,
ob die geladene Geometrie noch zur aktuellen Szene passt. Sie läuft jetzt
außerhalb des `run`-Modus gedrosselt weiter (`CANDIDATE_INTERVAL_S = 1.0`,
`controller.py`). Reiner Offline-Durchsatztest auf demselben gespeicherten
960×720-Realbild wie die Messung vom 2026-09-09 (`fokus-erreicht-960x720.jpg`),
je 100 Aufrufe mit `time.perf_counter()`, `CLOCK_MONOTONIC`, `simulate=True`
(kein Kamerazeit- oder End-to-End-Latenztest):

| Pfad | Dauer je Bild |
| --- | ---: |
| bestätigt, `setup`, Drosselfenster noch nicht abgelaufen (Suche übersprungen) | 8,3–9,0 ms |
| bestätigt, `setup`, Drosselfenster künstlich bei jedem Bild abgelaufen (Suche jedes Mal fällig) | 16,6 ms |
| bestätigt, `run`-Modus (Suche nie fällig, unabhängig vom Drosselfenster) | 8,3 ms |

Bei `CANDIDATE_INTERVAL_S = 1,0 s` und 15 fps zahlt höchstens jedes 15. Bild
die höhere Kandidatensuche-Kosten (~16,6 ms statt ~8,3 ms) — im Mittel rund
0,55 ms/Bild zusätzlich, weit unter der mit OQ-24 behobenen
Vollbildsuche-pro-Bild-Kosten von 30,837 ms/Bild. Der `run`-Modus bleibt davon
komplett unberührt. Absolutwerte hier (~8,3 ms Grundkosten) liegen über der
2026-09-09-Messung (5,801 ms) desselben Bildpfads ohne Kandidatensuche; beide
Messungen liefen auf demselben Pi, aber zu unterschiedlichen Zeitpunkten ohne
kontrollierte Gegenprobe — die Differenz ist nicht auf diese Änderung
zurückgeführt, da der übersprungene Zweig strukturell unverändert ist.

## 2026-09-10, spätabends — Vergleichssuche auf die bestätigte ROI eingegrenzt

Direkte Bedienerrückmeldung auf die vorige Messung: Die wiederhergestellte
Vergleichssuche schlug am realen Prüfstand (RND-Labornetzteil mit den
Anzeigen `V`/`A`, zwei Monitore im Hintergrund, weitere Messgeräte) andere
Bildschirme im Bild statt der bestätigten Anzeige vor. Ursache: Sie rief
weiterhin `find_display_candidates` (Vollbildsuche) auf, nur gedrosselt statt
bei jedem Bild. Jetzt `fit_quad_in_region` mit `config["roi"]` als
Suchfenster-Hinweis, zusätzlich mit neuem Mindestüberdeckungsfilter
`MIN_HINT_OVERLAP = 0,2` (`vision.py`) gegen ein unbeteiligtes Objekt am Rand
des aufgeweiteten Suchfensters.

**Realbildnachweis** (`var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd`,
dieselbe Aufnahme wie oben): `Controller.publish()` mit der gespeicherten
Annotation als Profil aufgerufen, resultierendes JPEG-Overlay visuell
geprüft. Das gelbe Vergleichsquad deckt sich mit dem grünen bestätigten
`roi_quad` (beide umfassen den gesamten Netzteil-Panelbereich mit `V`- und
`A`-Anzeige) und lässt die beiden im Bild sichtbaren Computermonitore
vollständig aus.

**Synthetischer Ablenkertest** (`test_fit_quad_in_region_ignores_unrelated_objects_outside_the_hint`):
ein Prüfling mit gekappten Ecken (Rechteckigkeit < 1) neben einem kleinen,
perfekt rechteckigen Ablenkerobjekt im aufgeweiteten, aber außerhalb des
ungepolsterten Hinweisbereichs liegenden Suchfenster. Ohne
`MIN_HINT_OVERLAP`-Filter gewinnt das kleine Ablenkerobjekt (reine
Rechteckigkeit-dann-Fläche-Bewertung bevorzugt das perfekte Rechteck trotz
kleinerer Fläche) — mit Filter gewinnt der Prüfling (IoU > 0,85 gegen seine
wahre Form, 0,0 Überlappung mit dem Ablenker). Das reproduziert den
Bedienerbefund gezielt, nicht nur zufällig.

**Kostenmessung** (gleiche Methode wie oben, `fokus-erreicht-960x720.jpg`,
je 100 Aufrufe):

| Pfad | Dauer je Bild |
| --- | ---: |
| bestätigt, `setup`, Drosselfenster nicht abgelaufen (Suche übersprungen) | 8,0 ms |
| bestätigt, `setup`, Drosselfenster künstlich abgelaufen (`fit_quad_in_region` jedes Mal fällig) | 12,5 ms |
| bestätigt, `run`-Modus (Suche nie fällig) | 8,1 ms |

Günstiger als die vorige, auf `find_display_candidates` gestützte Messung
(16,6 ms im Suchfall), weil `fit_quad_in_region` nur den aufgeweiteten
Ausschnitt statt des ganzen Bildes verarbeitet. `MIN_HINT_OVERLAP` ist ein
Vorabdefault wie die übrigen `DetectionConfig`-Filter — an den zwei realen
Annotationen (dort >0,9 Überdeckung des richtigen Kandidaten) und der
synthetischen Ablenker-Szene geprüft, nicht an einer breiten Displayvielfalt
oder unterschiedlichen ROI-Größenverhältnissen validiert.

## 2026-09-10 — Automatische `roi_quad`-/`ocr_box`-Vorschläge gegen reale Annotationen

Kein Erkennungsdatensatz, sondern eine Validierung der neuen
Workbench-Editorhilfe (`fit_quad_in_region`/`fit_ocr_box`,
`src/dispread/workbench/vision.py`) aus
[PLAN_2026-09-10-workbench-editor.md](PLAN_2026-09-10-workbench-editor.md)
gegen die zwei realen Annotationen aus der Sitzung vom 2026-09-09
(`var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd`,
`.../8a18ee05e31241b9b6702c5bb904ec97` — ein Netzteil mit zwei übereinander
liegenden 7-Segment-Anzeigen `V` und `A`). Beide Bilder zeigen `11.00` auf der
oberen `V`-Anzeige; Layout 4 Stellen / 2 Nachkommastellen / kein Vorzeichen,
`digit_gap_ratio=0.65`. IoU wie in [Kapitel 7](anleitung/07-lokalisierung.md)
über Flächenmasken gerechnet, nicht vorab geschätzt.

| Funktion | Eingabe | IoU gegen bestätigte Geometrie |
| --- | --- | --- |
| `fit_quad_in_region` (`roi.suggest`) | grober Hinweis (bestätigte ROI ± 5 % Rand) auf dem Rohbild | **0,907** / **0,908** |
| `fit_ocr_box` (`ocr.suggest`) | die tatsächlich bestätigte, grosszügige `roi_quad` entzerrt | **0,0** / **0,0** |

**`roi.suggest` trifft die Displayposition zuverlässig**, wenn der
Bedienerhinweis wie vorgesehen einen groben Rahmen um das Display zieht — die
lokale Kantensuche auf dem aufgeweiteten Ausschnitt findet das Netzteilpanel
beide Male mit über 0,9 IoU gegen die tatsächlich vom Bediener bestätigte
`roi_quad`.

**`ocr_box`-Vorschlag scheitert an beiden Bildern vollständig, aus zwei
verschiedenen, dokumentierten Gründen:**

1. **Haupt-/Nebenanzeige-Verwechslung (Konzept.md §7).** Die bestätigte
   `roi_quad` umfasst grosszügig beide Anzeigen (`V` oben, `A` unten). Beide
   Zeilen liefern plausible Ziffernblobs; die untere `A`-Zeile (`0.000`, alle
   Segmente aktiv, vier gleich grosse Blobs) hat in beiden Bildern mehr
   Gesamtfläche als die obere, tatsächlich gewünschte `V`-Zeile (`11.00`, zwei
   schmale `1`-Segmente verschmelzen beim Schliessen zu einem einzigen, kleineren
   Blob). Die Funktion wählt deshalb konsequent die falsche Zeile. Ohne
   weiteren Bedienerhinweis ist das laut Konzept.md §7 strukturell nicht
   auflösbar — das ist der Grund, warum die Bestätigung ein Vorschlag bleibt
   und nie automatisch übernommen wird.
2. **Glanzfleck (Bild 1 zusätzlich).** Ein grossflächiger heller Reflex
   überlagert einen Teil der `V`-Ziffern und bildet einen eigenen, grossen
   Blob, der ohne die Zeilentrennung fälschlich mit echten Ziffernblobs
   verschmelzen würde (siehe Fallstricke unten).

Mit einer probeweise **enger** vorgeschlagenen `roi_quad` (aus `roi.suggest`
selbst statt der grosszügig bestätigten) liefert `fit_ocr_box` an beiden
Bildern `None` statt eines falschen Vorschlags — der sichere Fehlschlag statt
einer stillschweigend falschen Übernahme, aber weiterhin kein brauchbarer
Vorschlag. Neuer Eintrag [OQ-25](open-questions.md).

**Nachgezogene Implementierungskorrektur während dieser Messung:** Die
Blob-Gruppierung nach vertikaler Mitte lief zunächst gegen einen laufenden
Mittelwert und liess dadurch einen einzelnen Ausreisser (in Bild 1 der
Glanzfleck) über eine Kette benachbarter Abstände in die eigentlich falsche
Zeile hineinziehen; umgestellt auf lückenbasierte Gruppierung nach Sortierung.
Ausserdem war der Schliess-Kernel der Blob-Erkennung mit fester Grösse zu
klein, um bei berührenden Ziffernstellen (`digit_gap_ratio=0`, der
synthetische Default) eine Ziffer zuverlässig zu einem Blob statt zwei
Halbblöcken zu verschmelzen — auf einen zur Crophöhe proportionalen Kernel
(≈8 %) umgestellt. Beide Korrekturen sind allgemeine Robustheit, nicht auf
diese zwei Bilder zugeschnitten; die synthetischen Tests in
`tests/test_workbench.py` (`test_fit_ocr_box_matches_the_rendered_digit_area`)
belegen IoU > 0,6 auf vier unabhängigen Layout-/Wertkombinationen ohne
Nebenanzeige. Bekannte Grenze, an einer fünften Kombination (3 Stellen, keine
Nachkommastelle) gefunden und deshalb **nicht** in dieses Testset
aufgenommen: bei sehr schmalen Layouts (wenige, breite Ziffernzellen) kann der
Schliess-Kernel einzelne Ziffern uneinheitlich in Ober-/Unterhälfte zerfallen
lassen, sodass das flächengrößte Cluster nur einen Teil der Zeile trifft -
Docstring von `fit_ocr_box` verweist darauf, weitere reale Beispiele dieser
Layoutklasse stehen aus.
