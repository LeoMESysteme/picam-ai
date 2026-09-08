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
