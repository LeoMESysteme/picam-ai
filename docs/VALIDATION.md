# Validierung — Messwerte und Abnahmekriterien

Jede Zahl hier trägt Datum, Datensatz und Verweis auf den Lauf. Aufbau und
Deutung von Experimenten gehören nach [lab_journal.md](lab_journal.md).

⚠️ **Die Erkennungskennzahlen stammen bisher überwiegend von synthetischem
Material.** Seit 2026-09-21 existiert ein realer Proben-Bestand aus dem
Sammelmodus (73 lesbare Proben, 2 Geräte, siehe unten „2026-09-21 —
Dataset-Benchmark"), aber **beide Geräte stehen auf `split=development`,
keines auf `heldout`** — nach Konzept.md §9 ist damit weiterhin **kein**
Testergebnis erreichbar, nur eine Entwicklungsmessung. Ein Datensatz mit
breiterer Gerätevielfalt bleibt offen ([OQ-04](open-questions.md)).
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

## 2026-09-11 — Ausgangsmessung `sevenseg/2` auf allen gelabelten realen Annotationen

**Datensatz:** `var/workbench/annotations/` enthält inzwischen **neun**
Annotationen, nicht die in [OQ-25](open-questions.md) und `docs/status.md`
genannten zwei. Sechs davon tragen einen getippten `ground_truth_text`; eine
weitere liegt noch im alten Schema ohne `layout` und ist nicht auswertbar.

⚠️ **Alle sechs stammen von einer einzigen Geräteinstanz** (4 Stellen, 2
Nachkommastellen, ohne Vorzeichenstelle, `digit_gap_ratio=0,65`, Einheit `V`)
mit drei verschiedenen angezeigten Werten. Nach Konzept.md §9 und der
Splitregel der ROADMAP ist das ein **Entwicklungssatz, kein Testset**. Keine
Zahl hier belegt eine Trefferquote.

**Verfahren:** Je Annotation mit dem gespeicherten `roi_quad` auf 400×160
entzerrt, mit der gespeicherten `ocr_box` geschnitten (`crop_box`) — exakt der
Weg aus `Controller._read()`.

| Annotation | Sollwert | gelesen | Kontrast | min_margin |
| --- | --- | --- | --- | --- |
| `23a1e009` | 28,80 | `28.80` | 0,497 | 0,478 |
| `6ffc561b` | 11,00 | `11.00` | 0,419 | 0,278 |
| `8a18ee05` | 11,00 | `110?` — **abgelehnt** | 0,398 | 0,210 |
| `9359eb9a` | 12,76 | `12.76` | 0,525 | 0,619 |
| `b1375256` | 28,80 | `28.80` | 0,428 | 0,570 |
| `fdc840cd` | 28,80 | `28.80` | 0,515 | 0,749 |

```
korrekt = 5     falsch angenommen = 0     abgelehnt = 1
```

**Die maßgebliche Zahl ist die mittlere: null falsche Annahmen.** Sie ist ab
jetzt die Nichtregressionsbedingung für jede Decoder-Änderung — gegen eine
Ausgangszahl von null blockiert bereits eine einzige falsche Annahme.

### Ursache der einen Ablehnung, direkt nachgemessen

Punktmessungen je Segment in `8a18ee05` (Sollwert der letzten Stelle ist `0`,
also sechs aktive Segmente):

```
Stelle 3   a:AN 0,42  b:AN 0,60  c:AN 0,44  d:AN 0,53  e:AN 0,38  f:AN 0,54  g:aus 0,28
Stelle 2   a:AN 0,59  b:AN 0,85  c:AN 0,69  d:AN 0,81  e:AN 0,58  f:AN 0,77  g:aus 0,26
```

Stelle 3 leuchtet als Ganzes schwächer als Stelle 2. Die eine globale Schwelle
aus `segment_threshold()` liegt zwangsläufig zwischen beiden Niveaus und reißt
das tatsächlich leuchtende `e` (0,38) mit ab. Das ist **Ursache (1) aus
[OQ-23](open-questions.md), unabhängig erneut bestätigt** — diesmal an einer
Stelle-zu-Stelle-Differenz statt an einer Streuung innerhalb einer Stelle.

### Drei Kandidatenänderungen, prototypisch gegen dieselben Bilder gemessen

Der Prototyp lag im Sitzungs-Scratchpad und wurde **nicht** ins Repo
übernommen — er war Entscheidungsgrundlage, kein Baustein.

| Variante | korrekt | falsch | abgelehnt |
| --- | --- | --- | --- |
| A — Ist-Stand: Punktabtastung, eine globale Schwelle | 5 | 0 | 1 |
| B — Panelbezug je Stelle, Otsu innerhalb der Zelle | 5 | 0 | 1 |
| D — Panelbezug je Stelle, Schwelle als Anteil der Zellspanne | 5 | 0 | 1 |
| E — Segmentflächen statt Punkte, Profil-Defaults 0,16/0,10 | 3 | 0 | 3 |
| C — erste Fassung der Flächenmessung, ohne Trennungsprüfung | 0 | **1** | 5 |

Drei Befunde:

1. **Die Entscheidungsregel allein ändert nichts.** Variante B punktet exakt
   wie der Ist-Stand. Otsu *innerhalb* einer Zelle wählt bei sechs aktiven und
   einem inaktiven Segment den falschen Schnitt: es maximiert die gewichtete
   Zwischenklassenvarianz und bevorzugt deshalb einen ausgewogenen 4:3-Schnitt
   gegenüber dem richtigen 6:1-Schnitt.
2. **Variante D repariert ein Bild und zerbricht ein anderes.** Sie liest
   `8a18ee05` korrekt, dekodiert dafür `6ffc561b` Stelle 0 als `7` statt `1`.
   Sichtbar wurde das nur, weil eine andere Stelle desselben Bildes `?` wurde.
   Siehe den neuen Befund in OQ-23.
3. **Flächige Segmentmessung ist mit den heutigen Profilwerten schlechter.**
   `thickness_ratio=0,16` und `inset_ratio=0,10` sind nie kalibriert worden.
   Sweep über beide, Variante D als Entscheidungsregel:

   ```
   thickness=0,12  inset=0,10   korrekt=5  falsch=0  abgelehnt=1
   thickness=0,20  inset=0,05   korrekt=5  falsch=0  abgelehnt=1
   thickness=0,25  inset=0,00   korrekt=4  falsch=0  abgelehnt=2
   thickness=0,16  inset=0,05   korrekt=4  falsch=0  abgelehnt=2
   thickness=0,16  inset=0,10   korrekt=3  falsch=0  abgelehnt=3   <- heutiger Default
   ```

**Der wichtigste Befund dieser Messreihe ist nicht eine Zahl, sondern ihre
Mehrdeutigkeit:** zwei weit auseinanderliegende Parametersätze (0,12/0,10 und
0,20/0,05) erreichen dieselbe Punktzahl. Sechs Bilder eines Geräts
unterbestimmen die Geometrie. Daraus folgt für
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md):
die Messvorrichtung kommt vor jeder Decoder-Änderung, und eine automatische
Rasteranpassung muss auf **Trennschärfe** optimieren, nicht auf bloße
Übereinstimmung.

## Ausgangsmessung `sevenseg/2` auf den realen Annotationen (2026-09-11)

Die Zahlen oben in diesem Abschnitt stammen aus einem Sitzungs-Scratchpad
ohne Werkzeug im Repo. Mit Task 3 des Plans existiert jetzt ein
wiederholbares Werkzeug dafür: `src/dispread/benchmark.py`
(`evaluate_set`/`evaluate_annotation`) und die dünne CLI
`scripts/ocr-benchmark.py`. Lauf:

```
./.venv/bin/python scripts/ocr-benchmark.py --annotations var/workbench/annotations
```

Ergebnis, deckungsgleich mit der obigen Handmessung:

```
auswertbar: 6  uebersprungen: 3
korrekt=5  falsch angenommen=0  abgelehnt=1
  Ablehnungsgruende:
    unreadable_cells: 1
  [abgelehnt] annotation:8a18ee05e31241b9b6702c5bb904ec97 (Geraet default): soll=1100
```

**Von neun Annotationen unter `var/workbench/annotations/` sind sechs
auswertbar** — drei fehlt entweder `ground_truth_text` oder `profile.layout`
(darunter `0dd69042…`, die einzige Altannotation ohne `layout`) und werden
von `evaluate_annotation` übersprungen, nicht stillschweigend als falsch oder
korrekt gezählt.

⚠️ **Alle sechs auswertbaren Annotationen stammen von einer einzigen
Geräteinstanz.** Nach Konzept.md §9 und der Splitregel der ROADMAP
(`assert_disjoint_devices`, erzwungen als Test in `tests/test_benchmark.py`)
ist dieser Satz damit ausdrücklich ein **Entwicklungssatz, kein Testsatz** —
er belegt keine Trefferquote über Geräte hinweg und darf nicht als eine
gelesen werden.

Die Metrik ist eine Leserzahl, keine Gate-Zahl: die Freigabe (`validate.py`)
kann gegenüber diesen Zahlen nur zusätzlich ablehnen, nie zusätzlich
annehmen — die gemessene Rate falscher Annahmen (hier: 0) ist die
konservative Obergrenze dessen, was nach der Freigabe beim Bediener ankommen
könnte.

## 2026-09-11 — Autofit (`fit_layout`) gegen dieselben sechs Annotationen (Task 4)

Task 4 des Plans
[PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md)
ersetzt das manuelle Justieren von `digit_gap_ratio`, `sign_cell_ratio`,
`thickness_ratio` und `inset_ratio` durch eine Suche, die aus einem einmal
getippten Sollwert unter allen exakt passenden Parametersätzen den mit der
größten Trennschärfe (`min_margin`) wählt (`src/dispread/ocr/autofit.py`).

⚠️ **Dieselbe eine Geräteinstanz wie oben.** Diese Zahlen belegen keine
Trefferquote über Geräte hinweg, siehe Warnhinweis im vorigen Abschnitt.

**Verfahren, bewusst anders als die Ausgangsmessung oben:** Start ist ein
`DisplayLayout` mit den **Defaultwerten** von `digit_gap_ratio` /
`sign_cell_ratio` / `thickness_ratio` / `inset_ratio`, nicht die vom Bediener
bereits bestätigte Geometrie — sonst würde der Versuch messen, wie gut der
Bediener war, nicht den Autofit. `digits`/`decimals`/`has_sign` kommen wie
immer aus dem getippten Sollwert. Übergeben wird der volle rektifizierte
400×160-Ausschnitt (`rectify(...).image`) plus die gespeicherte `ocr_box` —
**nicht** der damit bereits ausgeschnittene Leserausschnitt: `fit_layout`
verschiebt/skaliert die `ocr_box` selbst und ihr Rückgabewert ist nur relativ
zum vollen Crop sinnvoll. Das Messskript im Plan-Brief schneidet die Box vor
dem Aufruf ein zweites Mal heraus — hier korrigiert, siehe Docstring des
Messskripts.

| Annotation | Sollwert | `matched` | Trennschärfe (Zweitbester) | flach | gefunden gap/dicke/rand | Hand gap/dicke |
| --- | --- | --- | --- | --- | --- | --- |
| `23a1e009` | 28,80 | True | 0,669 (0,669) | **True** | 0,80 / 0,16 / 0,10 | 0,65 / 0,16 |
| `6ffc561b` | 11,00 | True | 0,278 (0,278) | **True** | 0,65 / 0,16 / 0,10 | 0,65 / 0,16 |
| `8a18ee05` | 11,00 | **False** | — | — | (Eingabelayout unverändert) | 0,65 / 0,16 |
| `9359eb9a` | 12,76 | True | 0,650 (0,650) | **True** | 0,65 / 0,16 / 0,10 | 0,65 / 0,16 |
| `b1375256` | 28,80 | True | 0,656 (0,656) | **True** | 0,65 / 0,16 / 0,10 | 0,65 / 0,16 |
| `fdc840cd` | 28,80 | True | 0,749 (0,749) | **True** | 0,65 / 0,16 / 0,10 | 0,65 / 0,16 |

```
matched = 5   nicht matched = 1   davon flach = 5 von 5 matched
```

**Zu den drei im Plan genannten Fragen:**

1. **`8a18ee05` (heute in Task 3 abgelehnt) wird auch vom Autofit nicht
   gelöst** — `fit_layout` meldet ehrlich `matched=False` und liefert das
   unveränderte Eingabelayout zurück. Aus rund 100 deterministisch geprüften
   Parametersätzen dekodiert keiner den Sollwert `11,00` exakt. Das ist
   konsistent mit der bereits in Task 3 nachgemessenen Ursache (eine globale
   Segmentschwelle reißt das schwächer leuchtende `e` von Stelle 3 mit ab) —
   diese Ursache liegt im Dekoder selbst (`segment_threshold`), nicht in der
   Rastergeometrie, und ist durch Geometrieanpassung folgerichtig nicht
   behebbar. Autofit löst also **nicht** von sich aus das Problem, das bisher
   der Decoder-Änderung zugeschrieben wurde.
2. Die restlichen fünf Annotationen finden ein passendes Raster; keine
   liefert eine stillschweigend falsche Geometrie (nicht direkt prüfbar ohne
   ein zweites, unabhängiges Bewertungsbild pro Annotation — hier nur
   indirekt daran, dass die gefundenen `digit_gap_ratio`-Werte bei vier von
   fünf exakt der vom Bediener bestätigten Geometrie entsprechen).
3. **`flach=True` bei allen fünf gefundenen Rastern, nicht nur gelegentlich.**
   Ursache dafür ist strukturell und mit `_box_candidates`/Parameter-Sonden
   direkt nachgewiesen, nicht nur vermutet: `DisplayLayout.cell_boxes()` und
   `.sign_box()` — die einzige Geometrie, die der Leser (`SevenSegmentReader`)
   tatsächlich abtastet — verwenden `thickness_ratio` und `inset_ratio`
   **überhaupt nicht**; beide Felder wirken ausschließlich auf den
   *synthetischen Zeichner* (`render_display`). Jede Änderung dieser beiden
   Parameter ist für die Bewertungsfunktion deshalb bei jedem Bild ein exaktes
   Unentschieden (`score` bitidentisch) — das erklärt auch die schon in der
   vorigen Messreihe dieser Sitzung gefundene Mehrdeutigkeit
   `thickness=0,20/inset=0,05` vs. `thickness=0,12/inset=0,10`. `flach=True`
   ist hier also weniger ein Aussage über die konkrete Anzeige als ein
   Hinweis, dass zwei der vier gesuchten Parameter für die aktuelle
   Leser-Geometrie wirkungslos sind. Das ist eine Beobachtung dieser
   Session, keine Korrektur — die Kandidatenmenge wurde **nicht** nachträglich
   verkleinert, um diesen Befund zu vermeiden. Für spätere Sitzungen: entweder
   `thickness_ratio`/`inset_ratio` auch in die Lesegeometrie einbeziehen, oder
   sie aus dem Autofit-Suchraum entfernen und als reine Zeichenparameter
   dokumentieren.

## 2026-09-11 — QuadTracker-Nachführung auf realen Bildern (Task 6)

Laufzeitmessung des `QuadTracker.update()` auf realen 960×720-Bildern aus
`var/workbench/annotations/8a18ee05e31241b9b6702c5bb904ec97` (RND-Labornetzteil,
7-Segment-Display mit Layout 4/2/ohne Vorzeichen). Je 200 Aufrufe nach einem
Warmluafen, gemessen mit `time.perf_counter()` in `CLOCK_MONOTONIC`,
`simulate=False` (echter Bildpfad, keine Kamera, aber echter Decoder):

| Größe | Wert |
| --- | ---: |
| Median | **2.63 ms** |
| P95 | **2.82 ms** |
| Max | 3.50 ms |

**Entscheidung für Task 7:** Der Median liegt deutlich unter der 10-ms-Schwelle.
Die Nachführung läuft bei jedem Frame (nicht gedrosselt), analog zur
Kandidatensuche im `run`-Modus ohne `CANDIDATE_INTERVAL_S`-Throttling. Bei 15 fps
Bildrate ist der Nachführungsaufwand <5 % der pro-Frame-Zeit.

## 2026-09-21 — Dataset-Benchmark: erster echter Lauf gegen den Sammelmodus-Bestand

`scripts/dataset-benchmark.py --samples var/workbench/datasets --split
development --deskew both --diagnose 2`, gegen den vollständigen
Sammelmodus-Bestand zum Zeitpunkt des Laufs: **77 Proben, 2 Geräte** (RND-Lab,
BK Precision), **73 lesbar, 4 unlesbar**. Beide Geräte stehen auf
`split=development`, keines auf `heldout` — alle Zahlen hier sind
**Entwicklungszahlen**, kein Konzept-§9-Testergebnis. Aufbau/Deutung siehe
`docs/lab_journal.md`, 2026-09-21; Deutung der Segmentgeometrie in
[OQ-23](open-questions.md), der `fit_quad_in_region`-Befund in
[OQ-25](open-questions.md).

**Phase A (Passbarkeit/Diagnose, ausdrücklich kein Erkennungswert):** grobe
Rahmenvorsuche (~36 Geometrie-Kandidaten je Probe) + `fit_layout` je lesbarer
Probe einzeln.

| Gerät | lesbar | gefittet (achsparallel) | kein Quad (achsparallel) | gefittet (entzerrt) | kein Quad (entzerrt) |
| --- | ---: | ---: | ---: | ---: | ---: |
| RND-Lab | 40 | 0 | 0 | 0 | **40** |
| BK Precision | 33 | 0 | 0 | 0 | **33** |
| **gesamt** | **73** | **0** | **0** | **0** | **73** |

Achsparallel: jede der 73 Proben bekommt ein Quad, aber **kein einziges**
Raster dekodiert den Sollwert exakt — 0/73. Entzerrt: `fit_quad_in_region`
liefert für **keine einzige** der 73 Proben überhaupt ein Quad (0/73 vor der
Rastersuche); siehe OQ-25-Update, mutmaßlich weil die von Hand gezogenen
Sammelmodus-Zielboxen deutlich großzügiger sind als die engeren
`roi_quad`-Hinweise, gegen die die Funktion 2026-09-10 gemessen wurde.

**Segmentdiagnose (Beispiele, unbestätigter Rahmen, achsparallel):**
`0b5eaacf...` (BK, soll `-000.13`) — Stelle 1 (Sollziffer `0`) hat **kein**
Segment über der Schwelle (Werte 0,12–0,16, Kontrast zu gering). `0282bca7...`
(RND-Lab, soll `25.36`) — Stelle 2 (Sollziffer `3` = a,b,c,d,g) misst
a,b,f,g aktiv: zwei von fünf Segmenten falsch, kein Rauschen. Kein
einheitlicher Fehlertyp über beide Beispiele.

**Phase B (Leave-one-group-out-Übertragung):** 7 mögliche Faltungen (3
BK-Situationen + 4 RND-Lab-Situationen), 6 durchgeführt. Die dritte
BK-Situation (`57227b16...`, „schräg links") hat noch keine als `selected`
markierte Probe — als Lücke gemeldet (`FEHLER:` auf stderr, Exit-Code 1),
keine Ersatzwahl getroffen.

| Geometrie | Faltungen durchgeführt | davon mit Übertragungszahl |
| --- | ---: | ---: |
| achsparallel | 6 | **0** |
| entzerrt | 6 | **0** |

In **jeder** durchgeführten Faltung, beider Geometrien, meldet Phase B „kein
Raster gefunden, keine Übertragung möglich" — der Vertreter der jeweiligen
Situation passte selbst nicht (achsparallel: 0 von 36 Kandidaten dekodierte
den Sollwert exakt, 2485–2556 Leseversuche je Vertreter; entzerrt: kein Quad).
**Keine einzige Zelle dieser Messung liefert eine korrekt/falsch/abgelehnt-Zahl**
— das ist der ehrliche Befund, nicht „0 % korrekt" (Plan-Vorgabe,
„ehrliches Ausfallverhalten").

**Einzelfalldiagnose (unlesbare Proben, n=1 je Eintrag, keine Quote):** 3
BK-Precision-Proben, 1 RND-Lab-Probe — nicht gezählt, nur benannt.

**Einordnung:** Die geplante Übertragungszahl (Phase B) ist mit dem heutigen
festen relativen Segment-Abtastraster **nicht erreichbar**, weil bereits
Phase A auf keiner einzigen Probe ein passendes Raster findet — Phase B kann
also gar nicht erst starten. Die nächste sinnvolle Stufe ist eine Prüfung der
Rastergeometrie selbst (OQ-23-Update), nicht ein erneuter Lauf mit mehr
Proben.

## 2026-09-22 — Quad-Findung: `fit_quad_in_region` vs. `lcd_quad_in_region`

**Datensatz:** voller Sammelmodus-Bestand zum Zeitpunkt der Messung, **88
Proben, 3 Geräte** — die beiden LED-/VFD-Laborgeräte aus dem Lauf vom
2026-09-21 plus das seither angelegte GSV-Gerät (`87564e34…`, 11 Proben,
hinterleuchtete Farb-LCD, Displaytech 161A). Alle Geräte stehen auf
`split=development`; das bleibt eine **Entwicklungsmessung**, kein
Konzept-§9-Testergebnis.

**Aufruf:** beide Funktionen direkt mit dem aus `sample.json` normierten
`bbox` als `hint_box`, also genau so, wie `benchmark.sample_quad(deskew=True)`
es tut. Kein Rasterfit, kein OCR — gemessen wird allein, ob ein Quad
zurückkommt und wie es zur markierten Region liegt.

| Gerät | n | `fit_quad_in_region` | `lcd_quad_in_region` | Fläche/Region (Median) | Quad ragt hinaus |
| --- | ---: | ---: | ---: | ---: | ---: |
| `87564e34…` (GSV, Farb-LCD) | 11 | 7 | **11** | 0,96 | 0 |
| `4237c46d…` (RND-Lab) | 36 | 0 | 35 | 1,00 | 0 |
| `91853b73…` (BK Precision) | 41 | 0 | 41 | 0,75 (0,53–0,98) | 8 |
| **gesamt** | **88** | **7** | **87** | — | — |

**Verhältnis zum 0/73-Befund vom 2026-09-21:** Dieser ist hiermit
**reproduziert**, nicht widerlegt. Die 73 Proben von damals sind die lesbaren
Proben genau der zwei LED-/VFD-Geräte, und auf denen findet
`fit_quad_in_region` auch heute kein einziges Quad (0/36 und 0/41 über alle
Proben, lesbar wie unlesbar). Die 7 Treffer stammen ausschliesslich vom
GSV-Gerät, das zum Zeitpunkt jenes Laufs noch nicht existierte.

**Einordnung — die Trefferzahl allein ist irreführend.** `lcd_quad_in_region`
liefert bei 87 von 88 Proben *ein* Quad, aber nur beim GSV-Gerät ist es auch
brauchbar: dort deckt es im Median 0,96 der markierten Region ab und liegt
ausnahmslos innerhalb. Bei `4237c46d…` entartet es zur markierten Box selbst
(Median 1,00) und bringt damit keinerlei Entkippung; bei `91853b73…`
schwankt die Abdeckung stark und **8 von 41** Quads ragen über die markierte
Region hinaus — bei `minAreaRect` geometrisch zulässig, als Vorschlag aber
unbrauchbar. „Findet ein Quad" heisst auf nicht hinterleuchteten Anzeigen
also ausdrücklich nicht „findet die Anzeige" ([OQ-36](open-questions.md)).

Für den Produktionspfad ist das verkraftbar: dort werden ausschliesslich
GSV-LCD-Anzeigen ausgelesen (Nutzerentscheidung 2026-09-22), die beiden
anderen Geräte sind Laborvertreter.

## 2026-09-22 — Rasterverankerung auf der GSV-Zeichen-LCD (Task-2-Gate)

**Frage:** Lässt sich das 16-Zellen-Raster der Displaytech 161A pro Bild
zuverlässig anlegen? Davon hängt ab, ob ein Zellen-Vorlagenleser tragfähig ist.

**Datensatz:** die 11 bestätigten GSV-Proben (`87564e34…`), `split=development`.
Entwicklungsmessung, kein Konzept-§9-Testergebnis.

**Maß:** Anteil der extrahierten Zellen, die ihrer *eigenen* Zeichenklasse am
nächsten liegen (Klassenmittel über alle Proben, Hamming-Abstand). `space` und
`empty` zu `blank` zusammengefasst — beide sind leer und prinzipiell
ununterscheidbar. Vorab festgelegt: Entscheidungsgröße ist der **Median über
sechs Parameterkombinationen** (Zellraster 5×7 / 8×10 × Binarisierungsschwelle
0,15 / 0,25 / 0,35), nicht der beste Einzelwert.

**Drei Verankerungsverfahren, alle gemessen:**

| Verfahren | Teilung (px) | Median über 6 Kombinationen |
| --- | --- | ---: |
| Score-Suche über Kante *und* Teilung | 18 (entartet) | 19,3 % |
| Tintenausdehnung: erste bis letzte Tintenspalte = 13 Zellen | 35–43,5 | **67,9 %** |
| Autokorrelation, stärkster Peak in 25–55 px | 28–37 | 38,9 % |

Referenzwert für die Teilung: **34,4 px** — aus einem Kleinste-Quadrate-Fit
gegen die tatsächlichen Zeichenpositionen einer sauberen Probe (maximale
Abweichung 2,93 px bei 33,7 px Zellbreite).

**Ergebnis gegen das vorab gesetzte Gate:** 67,9 % liegt unter der
Abbruchgrenze von 70 %. Das Gate ist **nicht bestanden**.

**Was damit belegt ist und was nicht.** Belegt ist, dass die Zeichen auf einem
gleichmäßigen Raster sitzen: der überwachte Fit trifft die Ziffern auf ±0,5 px.
Belegt ist auch, dass die Extraktion dort, wo die Verankerung trifft, klar
erkennbare Glyphen liefert — im Kontaktabzug sind die Nullen der passenden
Proben eindeutig als Nullen lesbar. **Nicht** belegt ist, dass der Ansatz
scheitert: In drei Anläufen war jeder Rückschlag ein Werkzeugfehler
(entarteter Score; globale Otsu-Schwelle gegen einen Helligkeitsverlauf; eine
Zellreduktion, die den Punkt `.` zum Nullvektor macht; eine
Autokorrelations-Peakwahl, die systematisch an die Bereichsuntergrenze rutscht).
Ein vierter Werkzeugfehler ist nicht ausgeschlossen.

**Der belastbarste Hinweis auf die Ursache:** Die drei `1.05000`-Proben
verhalten sich durchgehend gutartig — Autokorrelationsteilung 36/37/36 px gegen
den Referenzwert 34,4, und 16 Zellen belegen 0,94 der Crop-Breite. Die
übrigen acht liegen bei 0,73–0,78. Die drei gutartigen stammen aus derselben
Aufnahmeposition. Der Sättigungs-Quad erfasst also je nach Aufnahmesituation
einen unterschiedlich grossen physischen Ausschnitt, und daran scheitert die
Verankerung — nicht am Leseverfahren. Das deckt sich mit
[OQ-36](open-questions.md) (Quad-Abdeckung 0,54–0,97 auf demselben Gerät).

### Nachtrag 2026-09-22 — vierter Verankerungsversuch: Block-Anker

**Idee:** Der Zahlenblock belegt immer 8 Zellen (Vorzeichen + 6 Ziffern +
Punkt), der Einheitsblock 4, dazwischen eine leere Zelle. Aus den beiden
Blockbreiten sollte sich die Teilung als `(Breite₈ − Breite₄) / 4` ergeben,
wobei sich der Glyphen-Einzug herauskürzt. Gewählt, weil er — anders als eine
Dezimalpunkt-Landmarke — unabhängig davon ist, wo der Punkt steht
([OQ-37](open-questions.md)).

**Zwei Befunde:**

1. *Blockerkennung:* „breiteste Lücke = Zelle 9" ist unbrauchbar. Punktraster-
   Glyphen zerfallen in 16–25 Spaltenläufe statt 13, und eine Lücke innerhalb
   von `mV/V` kann breiter sein als die echte Trennlücke (bei `17ef5739`:
   43 px gegen 42 px). Erst ein Selbstkonsistenz-Kriterium — jede Lücke
   durchprobieren, die nehmen, deren Blockteilung zur Gesamtausdehnung passt —
   verankert alle 11 Proben.
2. *Die Einzugs-Annahme hält nicht.* Die Blockteilung liegt bei **jeder**
   Probe systematisch unter der Gesamtteilung. Ursache quantifiziert an
   `17ef5739`: Zahlenblock 4,7 px eingezogen (schmales `+`), Einheitsblock
   −1,2 px (`m`/`V` füllen ihre Zellen aus). Die Differenz von ~5,9 px
   erklärt die Abweichung exakt (34,92 − 5,9/2 = 32,0; gemessen 32,00). Der
   Einzug kürzt sich nur heraus, wenn er in beiden Blöcken gleich ist — er
   ist es nicht.

**Ergebnis: 45,2 % Median** (Spanne 38,6–51,1 %), gegenüber 67,9 % beim
Tinten-Anker. Der Block-Anker ist damit **nicht** die Lösung.

**Stand nach vier Verfahren:**

| Verfahren | Verankerte Proben | Median |
| --- | ---: | ---: |
| Score-Suche über Kante und Teilung | 11/11 | 19,3 % |
| Tintenausdehnung = 13 Zellen | 11/11 | **67,9 %** |
| Autokorrelation, stärkster Peak | 11/11 | 38,9 % |
| Block-Anker mit Selbstkonsistenz | 11/11 | 45,2 % |

Das Gate (70 %) bleibt in allen vier Verfahren unerreicht.

**Methodische Grenze, die hier sichtbar wird:** Der Fehler des Block-Ankers
ist vollständig verstanden und liesse sich mit einer kalibrierten
Einzugsdifferenz korrigieren. Diese Konstante müsste aber aus denselben 11
Proben stammen, gegen die anschliessend geprüft wird — das wäre Anpassung an
die Prüfmenge, kein Nachweis. **11 Proben reichen nicht, um ein
Verankerungsverfahren gleichzeitig zu entwickeln und zu validieren**
([OQ-04](open-questions.md): breiterer Datensatz bleibt offen).

## 2026-09-22 — GSV-2AS: serieller Abgriff verifiziert, Ausgabe ist Binärformat

**Aufbau:** GSV-2AS (Startmeldung `GSV-2AS (GSV21 V1.3.07)`), Klemme A/B/C auf
einen RS232-Steckverbinder geführt, daran ein USB-RS232-Adapter
(`067b:2303`, Prolific PL2303) am Pi. Port `/dev/ttyUSB0`, eingestellt auf
**38400 8N1 raw**, ohne Handshake. **Nur gelesen — es wurde kein einziges Byte
an das Gerät gesendet.** Rohmitschnitte:
`var/diagnostics/gsv-serial-2026-09-22/capture_3s.bin` und `capture_10s.bin`
(`var/` ist gitignored).

| Grösse | Wert |
| --- | --- |
| Mitschnitt 1 | 30 Bytes in 3 s = 6 Frames |
| Mitschnitt 2 | 95 Bytes in 10 s = 19 Frames |
| Frame-Rate | **≈ 1,9 Frames/s** (19 Frames / 10 s, CLOCK_MONOTONIC über `timeout`) |
| Framing | 5 Bytes je Messwert, Synchronbyte `0x2C` bei Offset 0 in **19/19** Frames |
| Status-Byte | `0x18` in 19/19 Frames des 10-s-Laufs (SW1 **und** SW2 gesetzt); im 3-s-Lauf zunächst `0x00`, dann `0x18` |
| Rohwertbereich (24 bit) | `B8A95A` … `EF346B`, 19 distinkte Werte |

**Deutung:**

* **Der Abgriff funktioniert Ende zu Ende.** Das 5-Byte-Raster sitzt über alle
  19 Frames exakt — Baudrate, Verdrahtung und Adapter stimmen. Damit ist der
  in [OQ-38](open-questions.md) empfohlene Weg praktisch bestätigt, nicht mehr
  nur dokumentiert.
* **Das Gerät sendet im Binärformat, nicht im ASCII-Modus.** Werksseitig
  erwartet ([HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)).
* **Die Werte sind kein Stabilitätsmass.** Der Nutzer hat während des
  Mitschnitts die extern angeschlossenen Stimulatoren bewegt. Die Streuung
  über den Rohwertbereich ist also **erwünschte Reaktion**, kein Rauschen —
  und zugleich der Beleg, dass der Stream live dem Sensoreingang folgt.
* **Aus dem Binärstrom lässt sich der Anzeigewert nicht berechnen.** Die
  Anleitung: „Beim binär codierten Datenprotokoll werden die Messwerte
  normiert auf ±1 übertragen. Die Displayanzeige ergibt sich aus
  Normierungsfaktor x Messwert." Der Normierungsfaktor dieses Exemplars ist
  unbekannt. Für Ground-Truth-Labels ist deshalb der **ASCII-Modus** nötig,
  in dem die Zeichenkette laut Anleitung der Anzeige entspricht. Das ist
  genau die Kopplung, auf der [OQ-38](open-questions.md) beruht.
* **Fallstrick für einen Parser:** `0x2C` ist nur ein Synchronzeichen, kein
  reserviertes Byte — es kann auch als Datenbyte auftreten. Ein Parser muss
  über die 5-Byte-Kadenz synchronisieren, nicht über das Zeichen allein.
* **≈ 2 Hz gegen 15 fps Kamera:** auf einen Messwert kommen rund sieben
  Kamerabilder. Das verschärft die in [OQ-38](open-questions.md) offene Frage
  nach der zeitlichen Kopplung zwischen Stream und Anzeige — sie ist damit
  keine Feinheit, sondern bestimmt, wie viele Bilder pro Sollwert überhaupt
  eindeutig zuzuordnen sind.

**Nicht gemessen:** Anzeigeinhalt zum jeweiligen Frame (niemand hat das
Display dabei mitfotografiert), zeitliche Kopplung Stream ↔ Anzeige,
optische Einschwingzeit des LCD, Normierungsfaktor.

## 2026-09-22 — GSV-2AS auf ASCII-Modus umgeschaltet, Telegrammformat gemessen

**Eingriff:** Mode-Register des GSV-2AS von `0x00` auf `0x02` gesetzt (Bit 1 =
Text-Modus). Ablauf wie in der Anleitung vorgeschrieben: `stop transmission`
(35) → `clear buffer` (37) → `get mode` (39) → `set mode` (38) → `get mode`
zur Kontrolle → `start transmission` (36). Freigabe durch den Nutzer
eingeholt. **Die Änderung ist persistent** („bleibt auch nach dem Abschalten
erhalten"); Rückweg ist dasselbe mit gelöschtem Bit 1.

**Nebenbefund zum Antwortformat:** `get mode` antwortet mit **zwei** Bytes
`3B <wert>` — das führende `0x3B` ist das in der Anleitung beschriebene
Semikolon-Präfix für Registerwerte, nicht der Wert. Die Spalte „Länge der
Befehlsantwort in Bytes = 1" zählt nur das Datenbyte. Wer das Präfix als Wert
liest, bekommt `0x3B` und damit eine völlig falsche Modus-Deutung.

**Gemessener Datenstrom nach der Umschaltung** (10 s, `/dev/ttyUSB0`,
38400 8N1, CLOCK_BOOTTIME; Rohmitschnitt
`var/diagnostics/gsv-serial-2026-09-22/capture_ascii_10s.bin`):

| Grösse | Wert |
| --- | --- |
| Bytes / vollständige Zeilen | 270 / 18 |
| Zeilenrate | **1,8 Zeilen/s** (Binärmodus vorher: ≈ 1,9 Frames/s — unverändert) |
| Zeilenende | `CR LF` (`0d 0a`) |
| Zeilenlänge | 13 Zeichen, **einheitlich über alle 18 Zeilen** |
| Formattreffer `^[+-]\d\.\d{5} mV/V$` | **18/18** |
| Wertespanne (Stimulus in Ruhe) | `+0.46775` … `+0.46776` |

Beispielzeile, byteweise:

```
2b 30 2e 34 36 37 37 36 20 6d 56 2f 56 0d 0a
 +  0  .  4  6  7  7  6 SP  m  V  /  V CR LF
```

Das entspricht exakt der Formatangabe der Anleitung („Vorzeichen, 6 Stellen
mit Dezimalpunkt, Leerzeichen, Einheit, CR, LF") und der Form der 11
bestätigten Datensatzproben (6 Ziffern, 5 Nachkommastellen,
[OQ-37](open-questions.md)).

**Abgeleitet: `1.05000` im Datensatz ist der Bereichsanschlag, kein Messwert.**
Die Anleitung führt `FFFFFF` als 105 % des physikalischen Messbereichs. Rechnet
man den früher gemessenen Binärwert `B8C62C` bipolar mit Vollausschlag 1,05
um, ergibt sich `+0.46573` — und der ASCII-Strom zeigt bei praktisch gleicher
Stimuluslage `+0.46776`. Der Vollausschlag dieses Exemplars ist damit
**1,05 mV/V**, und `FFFFFF` ergibt rechnerisch **exakt `+1.05000`**. Die drei
identischen `1.05000`-Proben im Datensatz sind also mit hoher Wahrscheinlichkeit
Übersteuerung. Bestätigen liesse sich das mit einem einzigen Versuch: Stimulus
bis an den Anschlag fahren und prüfen, ob die Anzeige auf `1.05000` stehen
bleibt.

**Weiterhin nicht gemessen:** ob die Anzeige zum selben Zeitpunkt denselben
String zeigt (Inhalt laut Anleitung ja, Zeitlage ungemessen), die optische
Einschwingzeit des LCD, und das Verhalten ab 10 mV/V. Negative Werte sind mit
den vorhandenen Stimulatoren **nicht erzeugbar** (Nutzerauskunft 2026-09-22).

## 2026-09-22 — GSV-2AS: Plateau-Statistik des ASCII-Stroms (Sperrfrage Auto-Labeling)

**Frage.** Automatisches Labeln aus dem seriellen Telegramm ist nur zulässig,
wenn zum Aufnahmezeitpunkt eines Bildes feststeht, *welche* Zeichenkette auf
dem Glas steht. Die Regel dafür ist ein Schutzintervall M um jeden
Wertwechsel (Herleitung:
[superpowers/plans/2026-09-22-auto-labeling-seriell.md](superpowers/plans/2026-09-22-auto-labeling-seriell.md)).
Sie taugt nur, wenn der Strom überhaupt lange genug still steht. Zappelt die
letzte Stelle dauerhaft mit der Telegrammrate, bleibt bei realistischem M
nichts übrig, und der ganze Weg trägt nicht. Diese Messung klärt das
**vor** dem Bau des Aufzeichners.

**Aufbau.** GSV-2AS über Klemme A/B/C und USB-RS232-Adapter (PL2303) an
`/dev/ttyUSB0`, 38400 8N1, kein Handshake. Rein passiv — **an das Gerät wurde
kein Byte gesendet.** Jede vollständige Zeile mit Ankunftszeit in
CLOCK_BOOTTIME (dieselbe Domäne wie `SensorTimestamp` der Kamera). Kamera war
nicht beteiligt, kein `dispread`-Prozess lief. Der Stimulus wurde **nicht**
absichtlich bedient; in den Sekunden 20–35 ist eine Störung sichtbar (siehe
unten).

Rohmitschnitt und Auswertskript:
`var/diagnostics/gsv-serial-2026-09-22/capture_ascii_600s_timestamped.jsonl`
und `…/plateaus.py`. **`var/` ist gitignored** — die Zahlen hier sind die
dauerhafte Fassung.

**Zahlen (599,4 s, 1125 Telegramme).**

| Grösse | Wert |
| --- | --- |
| Telegrammrate | 1,88 /s |
| Abstand zwischen Telegrammen | min 502 ms · p50 553 ms · p95 555 ms · max 562 ms |
| Formatabweichungen von `^[+-]\d\.\d{5} mV/V$` | **0 von 1125** |
| Verschiedene Zeichenketten | 40 |
| Wertebereich | `+0.46714` … `+1.05000` |
| Negative Werte | 0 |
| Werte ab 10 | 0 |

**Plateaus der exakten Zeichenkette** (Lauf gleicher Werte, Ende beim nächsten
abweichenden Telegramm): 265 Stück, Dauer p50 0,56 s · p75 2,16 s ·
p90 6,40 s · max 30,36 s. 127 Plateaus ≥ 1 s, 74 ≥ 2 s, 33 ≥ 5 s. Je Plateau
p50 **1** Telegramm, p90 12, max 57.

**Ausbeute je Schutzintervall** — nutzbarer Anteil der Wanduhrzeit, daraus
labelbare Bilder pro Minute bei 15 fps:

| M | nutzbar | Anteil | Bilder/min | Plateaus |
| --- | --- | --- | --- | --- |
| 200 ms | 493,4 s | 82,3 % | 741 | 265 |
| 300 ms | 449,6 s | 75,0 % | 675 | 127 |
| 500 ms | 398,8 s | 66,5 % | 599 | 127 |
| 750 ms | 350,1 s | 58,4 % | 526 | 93 |
| 1000 ms | 311,3 s | 51,9 % | 467 | 74 |
| 1500 ms | 250,7 s | 41,8 % | 376 | 53 |
| 2000 ms | 203,9 s | 34,0 % | 306 | 43 |

**Befund.** Die Sperrfrage ist beantwortet: selbst bei einem sehr grosszügigen
M von 1 s bleibt rund die Hälfte der Wanduhrzeit nutzbar. Der Strom steht im
Ruhezustand weit länger still, als die Telegrammrate vermuten lässt —
Plateaus bis 30 s.

**Der Befund, der dabei wichtiger ist.** Diese Zahl ist **Bilder** pro Minute,
nicht **Information** pro Minute. Im Ruhezustand trägt der Strom praktisch
**eine** Zeichenkette: `+0.46776 mV/V` in 379 von 660 Telegrammen der ersten
sechs Minuten, die nächsthäufigen unterscheiden sich in **einem** Zeichen der
fünften Nachkommastelle. Eine zehnminütige Ruheaufzeichnung liefert also rund
4700 Bilder **einer** Anzeige. Nach der Split-Regel des Plans
(`independence_group` je Sitzung) ist das **eine** unabhängige Beobachtung,
nicht 4700 — genau die Grenze, die schon bei 11 Proben zum Stehen geführt hat.
Die entscheidende Grösse ist damit nicht die hier gemessene Bildrate, sondern
**verschiedene Zeichenketten je Minute bewusst gefahrenen Stimulus**, und die
ist **ungemessen**.

**Nebenbefund.** In den Sekunden 20–35 wandert der Wert bis `+1.05000` und
über `+0.56679` zurück — offenbar eine mechanische Störung am Aufbau, nicht
bedient. Die beiden `1.05000`-Telegramme sind der **erste beobachtete**
Anschlag an den Vollausschlag; bisher war die Übersteuerungsvermutung zu den
drei gleichlautenden Datensatzproben nur rechnerisch hergeleitet
([OQ-39](open-questions.md)).

**Nicht gemessen und ausdrücklich offen:** der Versatz zwischen Telegramm und
Anzeige. Ohne ihn ist M nicht bestimmt, und keine Zeile dieser Tabelle ist
eine Freigabe zum Labeln.

## 2026-09-22 — GSV-2AS: das Schutzintervall verwirft bevorzugt die Vielfalt

**Frage.** Der Nutzer berichtet, die Werte fluktuierten zwischen 0,4 und 1,05,
sobald der Stimulus bewegt wird. Bringt eine lange passive Aufzeichnung damit
die Ziffernvielfalt, die dem Datensatz fehlt?

**Aufbau.** Wie im Eintrag „Plateau-Statistik" — rein passiv, kein Byte
gesendet, 1199 s, 2250 Telegramme. Rohmitschnitt
`var/diagnostics/gsv-serial-2026-09-22/capture_ascii_1200s_fluktuation.jsonl`,
Auswertung `…/gate_diversity.py` und `…/coverage.py`.

**Zahlen.** 723 Plateaus, **217 verschiedene Zeichenketten im Rohstrom**.
Entscheidend ist aber, was das Gate davon übriglässt:

| M | Bilder/min | verschiedene Zeichenketten | Anteil der Vielfalt |
| --- | --- | --- | --- |
| 0 ms | 900 | 217 | 100 % |
| 200 ms | 683 | 217 | 100 % |
| **300 ms** | 595 | **25** | **12 %** |
| 500 ms | 504 | 25 | 12 % |
| 1000 ms | 357 | 15 | 7 % |
| 2000 ms | 208 | 4 | 2 % |

Bei M = 500 ms entfallen 96,3 % der nutzbaren Zeit auf vier praktisch gleiche
Werte (`+0.46776` … `+0.46779`).

**Befund — und er ist der Grund, den Weg zu ändern.** Das Schutzintervall
wirkt **nicht neutral**. Es kostet zwischen M = 0 und M = 500 ms nur 44 % der
Bilder, aber **88 % der verschiedenen Zeichenketten**. Der Grund ist
strukturell: die Vielfalt steckt in kurzen Ausschlägen von ein bis zwei
Telegrammen, und das Fenster verwirft jedes Plateau kürzer als 2·M. Zwischen
200 ms und 300 ms bricht die Vielfalt schlagartig ein — genau dort
unterschreitet der Telegrammabstand von 553 ms die Schwelle 2·M.

Länger aufzuzeichnen hilft dagegen nicht: der Effekt ist eine Eigenschaft der
Zeitstruktur, nicht der Stichprobengrösse. Ein bewegter Stimulus liefert
deshalb **Bilder**, aber kaum **Information**.

## 2026-09-22 — GSV-2AS: Anzeige über den Normierungsfaktor steuerbar (OQ-37 beantwortet)

**Frage.** Lässt sich die Anzeige bei **festem** Stimulus gezielt verändern,
statt auf zufällige Ausschläge zu warten? Und — das ist
[OQ-37](open-questions.md) — bleibt es bei 6 Ziffern, wenn die Anzeige über
10 geht?

**Eingriff, mit Freigabe des Nutzers.** `set norm` (16) und `set dpoint` (17)
über dieselbe RS232-Verbindung. Jeder Schritt mit Rücklesen und Prüfung des
Fehlerregisters; am Ende auf den Ausgangszustand zurückgestellt.

**Ausgangszustand, vorher ausgelesen und als Rückstellpunkt gesichert**
(`var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json`, erzeugt mit
`scripts/gsv-registers.py`):

| Register | Rohbytes | Bedeutung |
| --- | --- | --- |
| norm | `50 1B E4` = 5250020 | Faktor **1,0** |
| dpoint | `01` | Punkt nach der 1. Stelle |
| unit | `00` | mV/V |
| digits | `06` | 6 Ziffern |
| mode | `02` | Text-/ASCII-Modus |
| range | `23` = 35 | 3,5 mV/V Eingangsempfindlichkeit |
| firmware | `0D 07` | 1.3.07 |
| last_error | `A0` | „No Error (OK)" |

**Erster Befund — die Umrechnungsvorschrift ist gegen das Gerät bestätigt.**
Die Anleitung gibt für `set norm` eine Rechenvorschrift mit der Konstanten
5250020. Der ausgelesene Rohwert ist **exakt 5250020**, und der Faktor ist
nachweislich 1,0. Die Rückrechnung war damit nicht mehr nur abgeleitet.

**Zweiter Befund — `EEnow = 0`.** Das Special-Mode-Register (`Get Special
Mode`, 137) liefert `00 12`. Bit 8 (`EEnow`) ist **0**: Schreibbefehle landen
laut Anleitung „erst nach dem Ausschalten" im EEPROM. Hunderte
Normierungswechsel kosten also keine EEPROM-Zyklen.

**Dritter Befund — der ASCII-Strom folgt dem Normierungsfaktor.** Das war
bisher aus zwei Anleitungssätzen verkettet, nicht gemessen. Umstellung auf
norm = 2,0: Median des Stroms vorher `0.60661`, nachher `1.21095`,
**Verhältnis 1,9963**. Die Abweichung von 2,0 erklärt sich durch den
gleichzeitig driftenden Stimulus.

**Vierter Befund — OQ-37 ist beantwortet.** Durchlauf über 14
Normierungsfaktoren von 1,0 bis 9000, Anzeigewerte von `+0.59696` bis
`+05372.5`:

| norm | dpoint | Anzeige | Ziffern | Zellen des Zahlenblocks |
| --- | --- | --- | --- | --- |
| 1,0 | 1 | `+0.59696 mV/V` | 6 | 8 |
| 3,0 | 2 | `+01.7908 mV/V` | 6 | 8 |
| 20,0 | 3 | `+011.939 mV/V` | 6 | 8 |
| 100,0 | 3 | `+059.695 mV/V` | 6 | 8 |
| 250,0 | 4 | `+0149.24 mV/V` | 6 | 8 |
| 1500,0 | 4 | `+0895.42 mV/V` | 6 | 8 |
| 9000,0 | 5 | `+05372.5 mV/V` | 6 | 8 |

**14 von 14 Faktoren: immer genau 6 Ziffern, immer genau 8 Zellen.** Das
Format wechselt nicht, der Dezimalpunkt wandert, führende Nullen bleiben
stehen.

> **Korrektur 2026-09-23:** Die Spalte „Anzeige" oben ist der ASCII-Strom.
> Auf dem **Glas** ist die führende Null unterdrückt: `+01.7908` erscheint dort
> als `+ 1.7908`. 6 Ziffern und 8 Zellen bleiben richtig. Siehe den Eintrag
> vom 2026-09-23 und OQ-41. Damit hält die Voraussetzung des Block-Ankers der Rasterverankerung
über den gesamten Bereich — die in OQ-37 befürchtete Formatänderung tritt
nicht ein.

**Alle 14 Schritte mit Fehlercode `0xA0` („OK"), Rückstellung auf norm = 1,0 /
dpoint = 1 verifiziert.**

**Was das löst und was nicht.** Gelöst: die Anzeige ist bei festem Stimulus
gezielt und beliebig lange stabil einstellbar — der Konflikt zwischen
Vielfalt und Plateaulänge aus dem vorigen Eintrag entfällt. **Nicht** gelöst:
**negative Werte.** Die Anleitung erlaubt negative Normierung erst „ab
Firmware-Version 1.5.06"; dieses Gerät hat 1.3.07. Die Vorzeichenstelle
bleibt damit unbelegt.

### Nachtrag — hängt die Plateaulänge vom Normierungsfaktor ab?

**Sorge:** Ein hoher Faktor verstärkt die Drift des Stimulus in die sichtbaren
Stellen. Bei norm = 9000 bewegt dieselbe Drift, die `+0.59696` um einen
Zählschritt verschiebt, die Anzeige `+05372.5` um rund neun. Zerlegt das die
Plateaus, kehrt der Konflikt zwischen Vielfalt und Plateaulänge bei den hohen
Faktoren zurück — und die Sitzungsplanung müsste moderate Faktoren bevorzugen.

**Messung:** je 90 s bei norm = 1,0 / 100,0 / 1500,0, selbstrücksetzend.

| norm | Beispielanzeige | versch. | Plateau p50 | p90 | max | nutzbar bei M = 500 ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1,0 | `+0.59694 mV/V` | 33 | 0,60 s | 2,61 s | 12,25 s | 49,9 % |
| 100,0 | `+059.996 mV/V` | 2 | 1,00 s | 5,42 s | 11,85 s | 55,1 % |
| 1500,0 | `+0899.93 mV/V` | 5 | 1,00 s | 3,01 s | 5,82 s | 40,1 % |

**Befund: die Sorge trifft nicht zu.** Die Plateaulänge ist über drei
Grössenordnungen des Faktors praktisch unverändert (p50 0,6–1,0 s, nutzbare
Zeit 40–55 %). Der Grund ist einfach und war übersehen worden: die Anzeige
zeigt **immer 6 Ziffern**, also immer dieselbe *relative* Auflösung. Bei
norm = 1 entspricht die letzte Stelle 10⁻⁵ mV/V, bei norm = 1500 sind es
0,01/1500 ≈ 6,7·10⁻⁶ mV/V — dieselbe Grössenordnung. Die Verstärkung des
Werts und die Verstärkung der Auflösung heben sich auf.

**Folge:** Die Sitzungsplanung ist im Faktor frei. Die Schwankung der Spalte
„versch." (33 / 2 / 5) ist Drift des Stimulus im jeweiligen 90-s-Fenster,
kein Effekt des Faktors.

## 2026-09-23 — Kamerazweig von `sync-record.py` erstmals gegen echte Hardware erfolgreich

**Aufbau.** Pi 5, IMX500, 960×720 RGB888, Videokonfiguration; GSV-2AS im
ASCII-Modus an `/dev/ttyUSB0`, 38400 8N1. Die Kamera zeigt auf die grüne
Punktmatrix-Anzeige des GSV-2AS. Kein `stream on failed` im Kernel-Log des
laufenden Boots.

| Lauf | fps soll | Dauer | Bilder | Sequenzlücken | Bildabstand | Anlauf bis 1. Bild | Telegramme |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `smoke-095440` | 5 | 10 s | 40 | 0 | – | ≈ 2,0 s | 19 |
| `smoke15-095700` | 15 | 20 s | 284 | 0 | 66,64 ms (min 66,637 / max 66,650) | 1,10 s | 38 |
| `offset-stim-100209` (Stimulator von Hand bewegt) | 15 | 180 s | 2634 | 0 | **ein** Sprung von 2,60 s bei t ≈ 34 s | – | 337 |
| `normtest-101403` (3 Normierungsschritte) | 15 | 20 s | 284 | 0 | – | – | 29 |
| `offset-norm-101440` (24 Normierungsschritte) | 15 | 215 s | 3176 | 0 | – | – | 332 |
| `leadzero-102347` (Faktoren 20 / 250 / 9000) | 15 | 32 s | 463 | 0 | – | – | 53 |

Die 40 statt 50 Bilder im 5-fps-Lauf sind **kein** Ratenverlust, sondern der
Anlauf: das erste Bild kommt ≈ 2 s nach dem Sitzungsbeginn, danach läuft die
Rate stetig. `scripts/camera-commissioning.sh` mit der neuen
Aufnahme-Gegenprobe: Exit 0, Testaufnahme 640×480 gelungen.

**Normierungsbefehle aus `sync-record.py` (`--norm-schedule`).** In allen vier
Läufen mit Plan (3 + 24 + 3 Schritte + Vorprüfung/Rückstellung) antwortete
jeder Schreibbefehl mit `3B A0` (OK). Vorprüfung gegen den Rückstellpunkt
jedes Mal bestanden, Rückstellung auf norm = 1,0 / dpoint = 1 jedes Mal per
Rücklesen bestätigt (`restore_verification.matches_restore_point = true`).
Jeder Schreibzyklus hält den Strom an: STOP → `set norm` nach ≈ 0,75 s →
`set dpoint` nach ≈ 0,35 s → START nach ≈ 0,70 s, also **≈ 1,8 s ohne
Telegramm** je Schritt.

**Die Anzeige folgt dem Befehl innerhalb von etwa einem Bild (qualitativ).**
Bildfolge in `offset-norm-101440`, Schritt `factor=3.0`, relativ zum STOP:
`+0.60966` bei +0,6 s, **`+0.18290`** bei +0,8 s (`set norm` bei +0,753 s
wirkt, der Dezimalpunkt steht noch alt), Mischbild bei +1,0 s, `+ 1.8290` ab
+1,2 s (`set dpoint` bei +1,105 s). Eine belastbare Latenzzahl steht noch aus,
siehe unten.

**Befund — Telegramm und Anzeige unterscheiden sich in der führenden Null
(OQ-38, OQ-41).** Optisch gegengeprüft über 15 Normierungsfaktoren (1,0 bis
9000). Standbild 3 s nach dem Wiederanlauf, daneben das zeitnächste
Telegramm:

| Faktor | Telegramm | Glas |
| --- | --- | --- |
| 1,0 / 1,2 / 1,5 | `+0.60965` / `+0.73158` / `+0.91449` | identisch |
| 2,0 | `+01.2193` | `+ 1.2193` |
| 2,5 | `+01.5241` | `+ 1.5241` |
| 3,0 | `+01.8290` | `+ 1.8290` |
| 3,5 | `+02.1338` | `+ 2.1338` |
| 4,0 | `+02.4386` | `+ 2.4386` |
| 20 | `+012.193` | `+ 12.193` |
| 250 | `+0152.42` | `+ 152.42` |
| 9000 | `+05487.0` | `+ 5487.0` |

**Das Gerät unterdrückt auf dem Glas die führende Null, im Telegramm nicht.**
Das Telegramm hat an dieser Stelle eine `0`, das Glas eine leere Zelle. Die
Zellenzahl des Zahlenblocks (8) bleibt, die Punktposition stimmt, alle
übrigen Zeichen stimmen überein. Bei Werten < 1 ist die `0` vor dem Punkt
die Einerstelle und steht auf beiden Seiten.

**Korrektur des Eintrags vom 2026-09-22 („Anzeige über den
Normierungsfaktor steuerbar").** Die dortige Spalte „Anzeige" ist der
**ASCII-Strom**, nicht das Glas. Die Sätze „führende Nullen bleiben stehen"
gelten für das Telegramm und sind für die Anzeige **falsch**. Unberührt
bleiben die 6 Ziffern und die 8 Zellen: die unterdrückte Null belegt weiter
eine Zelle.

**Befund — Stillstand des ganzen Aufzeichnungsprozesses (OQ-40).** In
`offset-stim-100209` bei t ≈ 34 s hat **keiner der beiden Kanäle** etwas
geliefert. Die Kamera hatte eine Lücke von 2,60 s, die Sensorzeitstempel
bestätigen das. Der serielle Strom hatte eine Lücke von 2,38 s, danach kamen
**fünf Telegramme mit praktisch gleichem `t_boot`** (Abstände 0 / 0 / 0 /
283 ms). Die Telegramme sind nicht verloren: fünf Intervalle zu 533 ms
passen in die Lücke. Verloren sind ihre **Ankunftszeiten**. `frame_sequence`
zeigt keine Lücke, weil es ein Zähler des Skripts ist und kein Sensorzähler.
Wegen `queue=False` wurden die Bilder dazwischen stillschweigend verworfen.
Unter Kameralast, ohne diesen Stillstand, über 391 Abstände:
p50 533 ms, p95 534 ms.

### Task B — Versatz Telegramm → Glas (`scripts/display-offset.py`, Vorlagen-Projektion)

δ = Mitte des Glaswechsels (p = 0,5) minus Ankunftszeit des ersten
abweichenden Telegramms. Positiv heisst, das Glas wechselt **nach** dem
Telegramm. d_misch ist die Zeit von p = 0,1 bis p = 0,9. M kommt aus der
vorab festgeschriebenen Formel `M = |δ| + d_misch + 3·σ_δ + 40 ms`.
Rampenereignisse sind ausgeschlossen: Nur Wechsel zählen, denen mindestens
ein unverändertes Telegrammintervall vorausgeht.

| Aufzeichnung | Population | messbar | δ | σ_δ | d_misch | M |
| --- | --- | --- | --- | --- | --- | --- |
| `smoke15-095700` (Ruhe) | small | 4 / 5 | +97 ms | 14 ms | 319 ms | 499 ms |
| `offset-stim-100209` (Stimulator) | large | 8 / 8 | +80 ms | 29 ms | 324 ms | 532 ms |
| `offset-stim-100209` (Stimulator) | small | 5 / 7 | +116 ms | 60 ms | 360 ms | 695 ms |
| `offset-norm-101440` (Normierung, Ruhewechsel zwischen den Sprüngen) | small | 23 / 28 | +94 ms | 90 ms | 260 ms | 664 ms |
| `offset-norm-101440` | large (Telegramm nach Wiederanlauf) | 0 / 18 | – | – | – | nicht verwertbar |

**Selbstkontrolle bestanden:** Im Stimulatorlauf stimmen `large` und `small`
bis auf 36 ms überein. Über drei Aufzeichnungen liegt δ zwischen +80 und
+116 ms, in keiner erkannten Population ist es negativ.

**Grenzen:**
* Die Ereigniszahlen sind klein (4–23).
* Die Null-Basislinie (Pseudoereignisse in langen Plateaus) fällt nur zu
  67–83 % durch die |B−A|-Prüfung. Ein Teil der Pseudoereignisse sähe also
  messbar aus. Die Übereinstimmung der Populationen trägt die Aussage, nicht
  die Einzelprüfung.
* `large` im Normierungslauf ist wie erwartet nicht verwertbar. Das
  Telegramm-Referenzereignis setzt dort der Wiederanlauf, den Glaswechsel
  der Befehl.
* Normierungsbefehl → Glas, nur informativ: Stufe 1 (`set norm` → Zwischen-
  zustand) ergab 23 / 25 messbar, δ ≈ 0 ms, σ 58 ms. Stufe 2 (`set dpoint` →
  Endzustand) ergab 23 / 25, δ = −278 ms, σ 240 ms. Die Streuung ist zu gross
  für eine Aussage, die Zuordnung der zweiten Stufe ist ungeklärt.

**M = 695 ms**, der grösste Wert, wie vom Nutzer am 2026-09-23 vor jeder Ernte
entschieden. Festgeschrieben im Plan unter Festlegung 3.

## 2026-09-23 — Stillstand beim Aufzeichnen: Ursache gemessen, Entkopplung geprüft (OQ-40)

**Aufbau:** Wie zuvor, 960×720 bei 15 fps, JPEG auf die SD-Karte (`mmcblk0`,
ext4). Parallel lief ein unabhängiger Herzschlag-Prozess ohne
Dateizugriffe, der Aussetzer über 100 ms protokolliert. Dazu wurden
`Dirty` und `Writeback` aus `/proc/meminfo` alle 0,25 s aufgezeichnet.
Kernel: `dirty_ratio` 20, `dirty_background_ratio` 10, `dirty_expire` 30 s.
Datenrate ≈ 2,6 MB/s.

| Lauf | Aufbau | Dauer | Bildlücken > 0,2 s | serielle Unregelmässigkeiten | Herzschlag-Aussetzer | max. Writeback |
| --- | --- | --- | --- | --- | --- | --- |
| `stall-105143` | alt (Schreiben in den Erfassungsthreads) | 150 s | 4 (333 / 933 / 533 / 333 ms) | Stoss bei t ≈ 80 s (841 / 226 ms) | 0 | 130 MB |
| `stall-fix-111410` | entkoppelt | 150 s | 0; `sensor_sequence` 6…2239 lückenlos | 0 (529–536 ms) | 0 | 6 MB (keine Belastung) |
| `stall-stress-111712` | entkoppelt, dazu 2 × 300 MB `dd … conv=fsync` | 90 s | 2, **gleich den 17 gezählten Verwürfen** (Sequenzsprünge 869→879, 879→888) | **0 (532–534 ms)**, Warteschlange max. 8 | 0 | 153 MB |

**Deutung:** Alle Lücken im alten Lauf fallen in Rückschreibphasen. Der
Herzschlag hatte nie einen Aussetzer, also steht nicht das System, sondern
der schreibende Prozess. Nach der Entkopplung bleibt der serielle Zeitstempel
auch unter erzwungener Last exakt. Bilder können weiterhin verloren gehen,
wenn die Bild-Warteschlange (60) länger als ≈ 4 s nicht abfliesst. Jeder
Verlust ist aber gezählt, protokolliert und an `sensor_sequence` erkennbar.

## 2026-09-23 — OQ-22 trotz frischem Boot beim zweiten Kameralauf

**Zeitbasis:** Kernel-Journal des aktuellen Boots, Europe/Berlin.
Bootzeit 14:24:31.

| Zeit | Lauf | Ergebnis |
| --- | --- | --- |
| 15:55 | `camera-commissioning.sh`, 640×480 | Testaufnahme erfolgreich, 86 606 Byte; kein `stream on failed` |
| 15:57 | temporärer Fokuslauf, 960×720, 15 fps, `queue=False` | 0 Bilder; `imx500_power_on: failed to get led gpio`; 6 × `stream on failed in subdev`; Prozess in `futex_wait_queue` |

Zwei `Using a link rate`-Zeilen gehören zur erfolgreichen Commissioning-
Sitzung (15:55:27/15:55:29), weitere sechs zum fehlgeschlagenen Fokusstart.
Der Fokuslauf erreichte sein Bedienersignal nicht; es gab keine mechanische
Änderung und keinen Schärfewert. Ein weiches Ctrl+C beendete den hängenden
Prozess nicht. Kein weiterer Kameraversuch; Reboot nötig. Damit ist ein
Streambudget von 15 zwar weiter eine obere Schutzgrenze, aber **keine Garantie
für 15 erfolgreiche Sitzungen nach jedem Warmstart**.

**Nachtrag, zweiter Boot um 16:13:22 (Europe/Berlin):** Boot-ID
`6c6abda2-d316-40da-b557-1124431ade30`. Der erste Kamerastart dieses
Boots um 16:17:35 (960×720, 15 fps) lieferte **0 Bilder**. Vor
`stream on failed in subdev` (6 ×) stehen RP2040-Bridge-Fehler,
darunter `rp2040_gbdg_wait_until_free failed`, und
`setup of GPIO led failed: -121`. Der Fokuswert bleibt unbekannt. Die
Grenze „20–25 Starts je Boot“ erklärt diesen Fehlschlag nicht; ein
Warmreboot garantiert keine funktionierende erste Sitzung.

## 2026-09-24 — Task 6: Kamera nach Neustart, ScalerCrop, Winkel, Auflösungsschwelle

**Zeitbasis:** Kernel-Journal und `session.json` der Läufe, Europe/Berlin.
Boot-ID `b973b67f-69a7-488a-9870-9e8daea714b8`, Start gegen 09:57 nach
nächtlicher Abschaltung des Pi (ob die Versorgung dabei ganz getrennt war,
ist nicht belegt). Probe von `imx500` und `rp2040-gpio-bridge` (fw 15)
ohne Fehler.

| Lauf | Ausschnitt angefordert → tatsächlich | Dauer | Bilder | verworfen | `sensor_sequence` | max. Schleife |
| --- | --- | --- | --- | --- | --- | --- |
| `task6-100540` | keiner → 2,0,4052,3040 | 1200 s | 17 978 | 8 (Warteschlange voll, t ≈ 13,5 min) | sonst lückenlos | 1,40 s |
| `task6-crop-102651` | 1214,547,1920,1440 → 1214,546,1920,1440 | 900 s | 13 487 | 0 | lückenlos | 1,18 s |
| `task6-frontal-full` / `-crop` | keiner / 1113,614,… → 1112,614,1920,1440 | 10 / 30 s | 133 / 434 | 0 | lückenlos | — |
| `task6-45deg-full` / `-crop` | keiner / 1438,631,… → 1438,630,1920,1440 | 10 / 30 s | 134 / 434 | 0 | lückenlos | — |

Alle sechs Streamstarts dieses Boots ohne `stream on failed` und ohne
RP2040-Fehler. Sensormodus jeweils 2028×1520 (2×2-gebinnt); ein
ScalerCrop von 1920×1440 Sensorkoordinaten ergibt damit bei 960×720
`native_scale = 1,0`. Enger zuschneiden bringt keine neue Information.

**Auflösung je Stellung** (`harvest-setup.py propose --session-json`):

| Stellung (benannt) | Stellung (geschätzt) | `min_native_dot_column_px` | Quad |
| --- | --- | --- | --- |
| frontal | 0° (Bezug) | 3,359 | von Hand; automatisch 2,539, weil die Spiegelung links oben die Glaserkennung abschneidet |
| 30° | ≈ 20° | 3,338 | automatisch |
| 45° | ≈ 23° | 2,677 | von Hand; automatisch 2,869, gleiche Ursache |

Schätzung aus dem Seitenverhältnis des Glases (Breite/Höhe, frontal 4,69),
Neigung nach oben nicht herausgerechnet. „30°" und „45°" liegen also näher
beieinander als benannt.

**Deutung:** Entzerrt (`var/diagnostics/task6-rectified-alle.png`, lokal)
sind die Punkte in allen drei Stellungen einzeln erkennbar, frontal am
weichsten, obwohl dort die meisten Pixel liegen — die Schärfe bestimmt die
Trennung stärker als die Pixelzahl. Der Nutzer hat die Schwelle auf
**2,6 px** gelegt (Plan `2026-09-23-ernte-phase1.md`, Entscheidung 7).
Fokus: Laplace-Varianz im Glas stieg nach Nachstellen von ≈ 36 auf ≈ 75
(Vollbild vs. Ausschnitt nicht vergleichbar); höhere Einzelwerte stammten
von verschobener Rahmung, nicht von Schärfe.

**Nachtrag 11:11 (gleicher Boot):** Der 7. Start (`ernte1-full`, 10 s
Vollbild, 133 Bilder) lief normal, der 8. (`ernte1-crop`, ScalerCrop
880,1015,1920,1440 angefordert) lieferte 0 Bilder mit RP2040-Bridge-Fehler
und 6 × `stream on failed` (OQ-22-Nachtrag). Kein hängender Prozess.

## 2026-09-24 — Ernte 1: erste echte Ernte mit Import (Task 7)

**Zeitbasis:** `SensorTimestamp` (CLOCK_BOOTTIME) und serielle Zeitstempel
derselben Domäne; Boot `18ba46e9-02ed-40ac-8bf9-139a2fbbc136` (Neustart
durch den Nutzer nach der Blockade um 11:11). Zwei Streamstarts in diesem
Boot, beide ohne Fehler.

**Einrichtung:** ScalerCrop 880,1015,1920,1440 (tatsächlich 880,1014,…),
Quad automatisch (`glass`-Detektor, keine Spiegelung mehr), Raster vom
Bediener `left=19.5, pitch=22.9, top=44, bottom=120` (400×160 entzerrt),
`min_native_dot_column_px = 3,461` ≥ Schwelle 2,6 → `resolution_ok=True`.
Profil: `var/diagnostics/ernte1-profile/profile.json` (lokal).

**Lauf:** `harvest.py --n-steps 30 --hold-s 4.0 --seed 20260924`,
`--guard-margin-ms 695 --min-gap-ms 300 --max-gap-ms 800`
(`gap_thresholds_provisional: true`). Registerstand danach verifiziert
zurückgesetzt (`norm` [80, 27, 228], `dpoint` [1]).

| Grösse | Wert |
| --- | --- |
| Bilder gesamt | 2835, 0 verworfen |
| gelabelt (`gate-label`) | 837 |
| abgelehnt `telegrammluecke` | 1497 |
| abgelehnt `wertwechsel_im_fenster` | 487 |
| abgelehnt `ausserhalb_telegrammbereich` | 14 |
| verschiedene Zeichenketten | 31 (25 × 12, 6 × 13 Zeichen) |
| ausgewählt (≤ 3 je Plateau) | 101 |
| abgelehnt beim Import | 14 `bildguete`, 6 `zellen_inkonsistent` |
| **importiert** | **81** (Datensatz 88 → 169) |

Herkunft der neuen Proben: 100 % `serial_ascii`. Vorzeichenstelle
**ungeprüft** (nur `+`, Firmware 1.3.07). Dezimalpunkt in Zelle 2, 3, 4
oder 5. Ziffernabdeckung je Zelle (Zelle 0 = Vorzeichen, Zelle 1 = Leerzelle
bei unterdrückter Null):

| Zelle | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Ziffern | 01234589 | 0134789 | 012345679 | 013456789 | 013456789 | 0123456789 | 46789 |

**Stichprobe:** 12 zufällige gelabelte Bilder entzerrt gegen ihr Label
geprüft (`var/diagnostics/ernte1-run/stichprobe*.png`, lokal) — alle 12
stimmen Zeichen für Zeichen. Zellsoll mit Leerzelle für die unterdrückte
Null (`cell_text`, z. B. `+ 909.09 mV/V`) stimmt mit dem Glas überein.

**Auffällig:** `telegrammluecke` verwirft mehr als erwartet. Der Plan
rechnete mit ≈ 39 labelbaren Bildern je Schritt, erreicht sind ≈ 28. Der
Hauptteil der Lücken entspricht der ≈ 1,8-s-Pause je Normierungswechsel;
ob die 800-ms-Schwelle zusätzlich gute Plateaus beschneidet, ist nicht
untersucht.

## 2026-09-24 — Ernte 2 und Aufstellung 2, Analyse der Telegrammlücken

**Ernte 2** (gleiche Aufstellung und gleiches Profil wie Ernte 1, Seed
20260925, 1 Streamstart): 2835 Bilder, 845 gelabelt, 28 Zeichenketten,
88 ausgewählt, 13 `bildguete`, 4 `zellen_inkonsistent`, **71 importiert**.
Stichprobe 8/8 korrekt. Die Proben tragen dieselbe `independence_group`
und dieselbe `source_id` (`harvest:ernte1`) wie Ernte 1, weil der Import
Gruppe und Kennung aus dem Profil bildet. Die Gruppe entspricht damit der
**Aufstellung**, nicht dem einzelnen Lauf — für den Split die konservative
Richtung; die Läufe sind nur über `stored_at_utc` trennbar.

**Aufstellung 2** (schräg von links, näher, Boot `18ba46e9…`, 3 Starts):
ScalerCrop 733,344,1920,1440, Quad automatisch, Raster vom Bediener
`left=7.5, pitch=23.5, top=44, bottom=120`, `min_native_dot_column_px =
3,294`. Schärfe sichtbar weicher als Aufstellung 1, vom Nutzer bewusst so
geerntet. Seed 20260926: 2835 Bilder, 830 gelabelt, 31 Zeichenketten, 94
ausgewählt, 7 `bildguete`, 11 `zellen_inkonsistent`, **76 importiert**.
Stichprobe 8/8 korrekt.

**Stand danach:** 316 Proben, davon 228 seriell geerntet aus 75
Zeichenketten in 2 Aufstellungen. Ziffernabdeckung Zellen 3–7 vollständig;
Zelle 2 (erste Ziffer bei Werten ≥ 1) ohne `6` — log-gleichverteilte
Faktoren erzeugen Benford-verteilte Führungsziffern (`6` ≈ 7 %). Zelle 1
trägt bei Werten ≥ 1 immer die Leerzelle.

**Telegrammlücken (Ernte 1, Offline-Analyse):** Alle 1497
`telegrammluecke`-Ablehnungen stammen aus den 29 Schreibpausen der
Normierungswechsel: 772 Bilder in der Telegrammstille selbst (≈ 2,3 s je
Pause), 425 im Schutzfenster davor, 300 danach. Die seriellen Abstände sind
bimodal — 237 × ≤ 536 ms, 29 × 2305–2313 ms, dazwischen keiner —, die
800-ms-Schwelle trennt also sicher. Saubere Schritte liefern 32–33 Bilder;
der Mittelwert ≈ 28 kommt von Schritten, in denen die letzte Ziffer bei
grossem Faktor vom Messrauschen springt (`wertwechsel_im_fenster`). Die
Gate-Regel arbeitet wie festgelegt; da höchstens 3 Bilder je Plateau
importiert werden, begrenzt die Ausbeute den Datensatz nicht.

## 2026-09-24 — Aufstellung 3 und volle Ziffernabdeckung

**Aufstellung 3** (frontal, weiter weg, Boot `25aaeb7e-4305-486c-a8c3-cdf77dae34fe`,
6 Starts): Beim ersten Versuch war das Glas im Vollbild nur ≈ 100 px breit
(geschätzt 2,2 native px je Punktspalte, unter der Schwelle) — Kamera näher
gerückt. Danach 2,74 px, aber stark unscharf; die Schwelle hätte das
durchgelassen (Entscheidung 7 prüft keine Schärfe). Nachfokussiert in einer
10-min-Sitzung mit Ausschnitt; Laplace-Varianz im Glas ≈ 55 → ≈ 98, dabei
verschob sich die Kamera, das Quad wurde auf den letzten ruhigen ≈ 40 s neu
bestimmt. Raster `left=17.5, pitch=22.8, top=44, bottom=120`,
`min_native_dot_column_px = 2,760`.

Ernte mit Seed 20261160 (gewählt, weil der Plan 7 Anzeigewerte mit
führender 6 enthält — Stimulusauswahl, keine Auswertungsentscheidung):
2834 Bilder, 584 gelabelt (882 `wertwechsel_im_fenster`, viele Werte mit
springender letzter Ziffer), 30 Zeichenketten, 97 ausgewählt, 4 `bildguete`,
20 `zellen_inkonsistent`, **73 importiert**. Die Stichprobe fand den Fehler
mit zwei führenden Nullen (`+00988.5`, OQ-41-Nachtrag); die Ernte wurde mit
Regel v2 offline neu gelabelt (`proposal-v1.json` bleibt daneben) und erst
dann importiert. Die drei importierten `+988.5`-Proben tragen
`cell_text = "+  988.5 mV/V"`.

**Stand:** 389 Proben, davon 301 seriell geerntet aus **98 Zeichenketten**
in 3 Aufstellungen (`ernte1` 152, `auf2` 76, `auf3` 73). **Ziffernabdeckung
vollständig:** Zelle 2 hat 1–9 (eine 0 ist dort durch die Unterdrückung
ausgeschlossen), Zellen 3–7 alle zehn Ziffern. Vorzeichen weiter nur `+`.
