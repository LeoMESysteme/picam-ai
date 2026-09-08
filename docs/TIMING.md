# Zeitbezug — Messplan und Messwerte

Setzt Konzept.md §6 von Prosa in Zahlen um. Jede Zeitgröße hat eine Domäne, ein
Messverfahren und einen Messwert **oder** ein ausdrückliches „unbekannt".

## Grundsatz: Latenz ist nicht Zeitunsicherheit

Eine konstante Verzögerung von 200 ms verschiebt den Zeitbezug, verschlechtert
ihn aber nicht — sie ist korrigierbar. Eine Verzögerung von 50 ms ± 40 ms ist
trotz kleinerem Mittelwert **schlechter**, weil nur die Streuung und der
unbekannte systematische Rest in das Unsicherheitsbudget eingehen.

Konsequenz für jeden Bericht: **Mittelwert (korrigierbar) und Streuung (nicht
korrigierbar) werden getrennt ausgewiesen.** Ein einzelner Zahlenwert „Latenz"
ist als Ergebnis unzulässig.

Zweiter Grundsatz: Der Aufnahmezeitstempel entkoppelt den Zeitbezug von der
OCR-Laufzeit, aber **nicht** vom internen Messzeitpunkt des DUT. Der
Displaybeitrag (M5) ist mit hoher Wahrscheinlichkeit der dominierende Term und
wird von keiner Softwareoptimierung kleiner.

## Messprogramm

| ID | Messgröße | Verfahren | Status |
| --- | --- | --- | --- |
| **M1** | Zeitbasen-Offsets BOOTTIME/MONOTONIC/REALTIME, NTP-Qualität | `chrony` installieren, `chronyc tracking` über 24 h protokollieren | **offen** — chrony fehlt ([OQ-15](open-questions.md)); derzeit läuft `systemd-timesyncd`, das keine Offset-Historie liefert |
| **M2** | Semantik von `SensorTimestamp` (Belichtungsbeginn? Auslese-Ende?) | GPIO-getriggerte LED mit bekannten Monotonic-Zeitpunkten, Belichtungszeit systematisch variieren. Wandert der Zeitstempel mit steigender Belichtungszeit mit → Bezug auf Auslese-Ende; wenn nicht → Belichtungsbeginn | **teilweise** — Domäne geklärt (siehe unten), Semantik offen |
| **M3** | Rolling-Shutter-Zeilenversatz | dieselbe LED-Anordnung, Puls kürzer als ein Frame; Zeilenposition des Streifens gegen Pulszeitpunkt | offen |
| **M4** | Pipeline-Latenzverteilung je Stufe | eingebaute Instrumentierung (`PipelineTrace`), p50/p95/max je Stufe | **teilweise** — auf synthetischem Material gemessen (siehe unten) |
| **M5** | **Displayaktualisierung und Haltezeit je Gerätetyp** | Sprunganregung, gleichzeitig Highspeed-Aufnahme und elektrischer Sprungzeitpunkt über GPIO, ≥ 30 Wiederholungen je Typ | offen — braucht Kamera **und** reale Geräte |
| **M6** | Pi gegen Referenz: Offset und Drift | abhängig von [OQ-03](open-questions.md). Bester Fall gemeinsame Zeitquelle, schlechtester Fall gemeinsames Ereignis und Kreuzkorrelation | offen |
| **M7** | Serielle Strecke | Loopback bei Zielbaudrate, `write()` bis Empfang, Backpressure bei voller Leitung | **teilweise** — gegen pty geprüft, nicht elektrisch ([OQ-09](open-questions.md)) |
| **M8** | **Nutzt GSVmulti den gelieferten Aufnahmezeitstempel?** | Datenstrom mit absichtlich um z. B. 5 s vordatiertem Aufnahmezeitstempel einspeisen und prüfen, welche Zeit GSVmulti anzeigt bzw. speichert | offen — blockiert durch [OQ-07](open-questions.md) |

**M8 ist der wichtigste Einzelversuch des Projekts** und kostet nach Vorliegen
der Spezifikation eine halbe Stunde. Fällt er negativ aus, beseitigt ein
interner Pi-Zeitstempel die zeitliche Verschiebung in GSVmulti nicht (Konzept
§6) und die Integrationsstrategie muss anders aussehen — etwa nachträgliche
Zuordnung über das JSONL-Audit-Log oder eine konstant gehaltene
Sendeverzögerung mit dokumentiertem Korrekturwert.

## Messwerte

### Zeitbasis von `SensorTimestamp` — 2026-09-07

**Domäne: CLOCK_BOOTTIME.** Gemessen bei einer Uptime von ~800 s betrug
`SensorTimestamp` 802 267 445 000 ns ≈ 802,27 s. Die Übereinstimmung mit der
Systemlaufzeit ist eindeutig.

Damit ist im Code `TimeBaseKind.SENSOR_BOOTTIME` belegt. **Noch offen** ist die
*Semantik* (`TimestampSemantics`): ob sich der Wert auf Belichtungsbeginn,
Belichtungsmitte oder Auslese-Ende bezieht, ist Messung M2. Bis dahin steht im
Datensatz `unknown` — nicht ein geratener Wert.

### IMX500-Warmlauf und Inferenzrate — 2026-09-07

Modell `imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk`, Auflösung
2028×1520.

| Größe | Messwert |
| --- | --- |
| Import `picamera2` + `IMX500` | 0,33 s |
| `IMX500(rpk)` Konstruktor | 0,09 s |
| `Picamera2.start()` | 0,05 s |
| **bis zum ersten Frame** (`.rpk`-Upload auf den Sensor) | **6,82 s** |
| erste Inferenz danach | 0,03 s |
| Frames bis zur ersten Inferenz | 2 |
| **eingeschwungene Rate** | **15,03 Inferenzen/s** |
| `CnnKpiInfo` dnn_runtime | 13,96 ms |
| `CnnKpiInfo` dsp_runtime | 12,36 ms |
| `ExposureTime` | 21,06 ms |
| `FrameDuration` | 33,31 ms (≈ 30 fps) |
| `ScalerCrop` | (2, 0, 4052, 3040) — voller Sensor |

Zwei Befunde, die Erwartungen korrigieren:

* `network_intrinsics` behauptet `inference_rate: 26`, gemessen wurden **15,0/s**.
  Die deklarierte Rate ist also keine Zusage.
* **`CnnInputTensor` fehlt** in den Standardmetadaten. Vorhanden sind
  `CnnOutputTensor`, `CnnOutputTensorInfo` und `CnnKpiInfo`. Wer den
  Eingangstensor braucht, muss ihn explizit aktivieren.

Die 6,8 s Warmlauf sind für den Betrieb relevant: nach jedem Start der
Anwendung liefert die Kamera in dieser Zeit keine Inferenz. Bei einem
Gerätewechsel im Labor kommt das zur Einrichtungsdauer hinzu.

### Verarbeitungslatenz je Stufe — 2026-09-07

⚠️ **Auf synthetischem Material gemessen.** Die Bildquelle war
`synthetic://seven-seg`, die Zeitbasis also `SYNTHETIC`. Diese Zahlen
beschreiben die Rechenzeit der Stufen, sie sind **keine** Aussage über reale
Latenzen im Messpfad. `report.json` weist das als
`"timing_is_meaningful": false` aus.

Ausschnitt 400×160, 5 Stellen, 40 Frames:

| Stufe | p50 | p95 | max |
| --- | --- | --- | --- |
| locate (bestätigte ROI) | 1,3 µs | 11,6 µs | 12,5 µs |
| rectify | 2 795 µs | 3 249 µs | 26 465 µs |
| read (7-Segment) | 1 383 µs | 3 783 µs | 7 403 µs |
| gate | 16,5 µs | 32,0 µs | 43,7 µs |
| build | 8,9 µs | 11,9 µs | 12,1 µs |
| **total** | **4 229 µs** | **10 604 µs** | **30 304 µs** |

Auffällig ist die Streuung: p95 ist das 2,5-Fache von p50, das Maximum das
7-Fache. Genau diese Streuung — nicht der Mittelwert — geht in das
Unsicherheitsbudget ein. Ursache ist noch nicht untersucht (Verdacht:
Speicherallokation in `warpPerspective`, Scheduling).

## Unsicherheitsbudget (Vorlage)

Wird von M1–M7 gefüllt. Erst wenn diese Tabelle ausgefüllt ist, ist
[OQ-02](open-questions.md) („welche Abweichung ist zulässig?") überhaupt
sinnvoll beantwortbar — und genau deshalb blockiert OQ-02 den Baubeginn nicht.

| Beitrag | Quelle | systematisch (korrigierbar) | Streuung (1σ) |
| --- | --- | --- | --- |
| Interne DUT-Messung und Filterung | Datenblatt / M5 | ? | ? |
| Displayaktualisierung und Haltezeit | **M5** | ? | ? |
| Belichtung (Mitte der Belichtung) | M2 | Belichtungszeit / 2 ≈ 10,5 ms | ? |
| Zeilenweise Auslesung | M3 | Zeilenposition × µs/Zeile | ? |
| Kamerazeitstempel-Unsicherheit | M2 | ? | ? |
| Pi-Uhr gegen Referenz | M1, M6 | Offset | Drift-Rest |
| Mehrbildbestätigung | `confirmation_span_ns` im Datensatz | Spanne / 2 | Spannbreite |
| Verarbeitung und serielle Übertragung | M4, M7 | nur relevant falls M8 negativ | siehe oben |
