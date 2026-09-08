# Laborjournal

Append-only. Pro Experiment: Datum, Ziel, Aufbau, Beobachtung, Messergebnis,
Schluss. Zahlen gehören zusätzlich nach [VALIDATION.md](VALIDATION.md) bzw.
[TIMING.md](TIMING.md), Entscheidungen nach
[project_history.md](project_history.md).

---

## 2026-09-07 — Inbetriebnahme der AI Camera

**Ziel:** Kamera erkennen und erste Aufnahme.

**Aufbau:** Raspberry Pi 5 (`raspi06`), AI Camera an CAM/DISP0. Kein
definierter optischer Aufbau — die Kamera hing frei und zeigte auf die
Unterseite eines Schreibtischs.

**Beobachtung:** Vor dem Reboot meldete `rpicam-hello --list-cameras`
`No cameras available!`. `dtoverlay -l` zeigte `No overlays loaded`, es gab
keinen Sensorknoten im Device-Tree, keine `rp1-cfe`-V4L2-Nodes und keine
CAM-I2C-Busse. Das Journal enthielt genau einen Boot um 12:03, während
`imx500-all` erst um 13:34 installiert worden war.

Nach dem Reboot um 15:08 war die Kamera erkannt: Sensorknoten
`/axi/pcie@1000120000/rp1/i2c@88000/imx500@1a`, neun `rp1-cfe`-V4L2-Nodes, drei
`v4l-subdev`, CAM-I2C-Busse 6 und 10.

**Messergebnis:** `rpicam-still` lieferte ein Bild (2028×1520, 315 kB). Die
Aufnahme ist **deutlich unscharf** — der manuelle Fokus der AI Camera ist auf
einen anderen Arbeitsabstand eingestellt.

**Schluss:** Ursache war der fehlende Reboot, nicht die Konfiguration.
`camera_auto_detect` prüft nur beim Booten. Merksatz für die Checkliste:
Kamera angesteckt ⇒ Reboot. Der Fokus muss vor der ersten sinnvollen Aufnahme
eingestellt werden.

---

## 2026-09-07 — IMX500-Warmlauf und Inferenzrate

**Ziel:** Die ohne Hardware nicht bestimmbaren Kenngrößen messen.

**Aufbau:** `imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk`,
Preview-Konfiguration, `buffer_count=8`.

**Messergebnis:** Siehe [TIMING.md](TIMING.md). Kernzahlen: 6,82 s bis zum
ersten Frame (das ist der `.rpk`-Upload auf den Sensor), danach Inferenz in
0,03 s, eingeschwungen 15,03 Inferenzen/s. `CnnKpiInfo` = (13962, 12362), also
dnn 13,96 ms und dsp 12,36 ms.

**Beobachtungen, die Erwartungen korrigieren:**

1. `network_intrinsics` behauptet `inference_rate: 26`, gemessen wurden
   **15,0/s**. Die deklarierte Rate ist keine Zusage.
2. **`CnnInputTensor` fehlt** in den Standardmetadaten. Vorhanden sind
   `CnnOutputTensor`, `CnnOutputTensorInfo` und `CnnKpiInfo`. Wer den
   Eingangstensor braucht — etwa um zu prüfen, was der Sensor wirklich sieht —
   muss ihn explizit aktivieren.
3. `SensorTimestamp` betrug 802 267 445 000 ns bei etwa 800 s Uptime. Die
   Domäne ist damit eindeutig **CLOCK_BOOTTIME**.
4. Die Labels aus `network_intrinsics` sind COCO: `person`, `bicycle`, `car`,
   `tv`, … Für Messverstärker-Displays ist das Modell damit nutzlos.

**Schluss:** Befund 4 hat die Architekturentscheidung ausgelöst, die bestätigte
manuelle ROI zum Primärpfad zu machen (siehe
[project_history.md](project_history.md)). Befund 3 belegt die Zeitbasis im
Code; die *Semantik* bleibt offen und ist Messung M2. Die 6,8 s Warmlauf kommen
bei jedem Anwendungsstart zur Einrichtungsdauer hinzu.

---

## 2026-09-07 — 7-Segment-Dekoder gegen synthetisches Material

**Ziel:** Prüfen, ob der Dekoder trägt und ob er in die richtige Richtung
versagt.

**Aufbau:** Synthetischer Generator, 5 Stellen, 2 Nachkommastellen, Einheit N,
Ausschnitt 400×160, Wertfolge mit echten Sprüngen und Vorzeichenwechseln.

**Beobachtung in drei Schritten — zwei Fehlversuche, die dokumentiert bleiben:**

1. *Schwelle pro Ziffernzelle aus deren Min/Max.* Ergebnis: 10 von 12 korrekt,
   jede `8` verworfen. Ursache: bei sieben aktiven Segmenten ist der
   zellinterne Kontrast null.
2. *Otsu über alle Bildpunkte des Ausschnitts.* Ergebnis: `8` gelesen, aber der
   Überlauf nicht erkannt. Ursache: eine 7-Segment-Anzeige hat drei
   Helligkeitsstufen, und die inaktiven Segmente sind die häufigste. Gemessenes
   Histogramm: Panel 19 (34 477 px), inaktives Segment 34 (14 150 px), aktives
   Segment 115 (2 645 px). Otsu legte die Schwelle bei 34 und trennte damit
   Panel von Segmenten statt inaktiv von aktiv.
3. *Schwelle über die gepoolten Segmentmessungen aller Stellen.* Ergebnis:
   40/40 korrekt, Überlauf erkannt.

**Messergebnis:** Siehe [VALIDATION.md](VALIDATION.md). Rauschen und Unschärfe
degradieren gutartig — bis σ=10 fehlerfrei, ab σ=12 Ablehnung, ab σ=15
vollständige Ablehnung, in keiner Stufe eine stille Fehlablesung. **Starker
Glanz erzeugt dagegen 2 von 40 stillen Fehlablesungen.** Das `glare`-Flag über
den Anteil gesättigter Bildpunkte hat sie von 13 auf 2 gesenkt.

**Schluss:** Reflexionen sind der gefährliche Fall, nicht Unschärfe — das
deckt sich mit Konzept §9. Abschirmung und Beleuchtung sind damit Voraussetzung
und nicht Feinarbeit. Die verbleibenden 2 stillen Fehlablesungen sind **nicht**
gelöst und müssen an realem Material erneut bewertet werden. Bekannte Grenze
des Verfahrens: zeigt die Anzeige ausschließlich `8`, fehlt die inaktive Klasse
und der Ausschnitt wird abgelehnt ([OQ-13](open-questions.md)).

---

## 2026-09-07 — Kette Ende zu Ende ohne Hardware

**Ziel:** Nachweis, dass die Verarbeitungskette aus Konzept §3 vollständig ist.

**Aufbau:** `examples/16_end_to_end_headless.py`. Bildquelle synthetisch,
serielle Gegenstelle ein pty-Paar aus `os.openpty()`, zwei Ausgaben parallel
(JSONL-Audit-Log und serielles ASCII-CSV).

**Messergebnis:** 40 Frames, 40/40 korrekt, 0 stille Fehlablesungen, 40
Telegramme auf der Leitung. Verarbeitungsdauer p50 4,2 ms, p95 10,6 ms, max
30,3 ms — Details in [TIMING.md](TIMING.md).

**Beobachtung:** Ein Lauf meldete 40 Datensätze, aber nur 39 Telegramme. Das
war ein Leserace beim Auslesen des pty, nicht ein Übertragungsfehler — beide
Sinks meldeten 40 gesendet und 0 Fehler. Daraufhin wanderte die Sink-Gesundheit
in den Bericht, damit ein echter Schreibfehler nicht stillschweigend als
„übertragen" gilt.

**Schluss:** Die Kette steht. Auffällig ist die Streuung der
Verarbeitungsdauer: p95 ist das 2,5-Fache von p50, das Maximum das 7-Fache.
Genau diese Streuung — nicht der Mittelwert — geht in das Unsicherheitsbudget
ein. Ursache noch nicht untersucht; Verdacht auf Speicherallokation in
`warpPerspective` und Scheduling.

## 2026-09-08 — Kameravorschau über lokalen HTTP-Stream

**Ziel:** Den neuen SSH-Vorschauprototypen mit der echten Kamera prüfen.
**Zeit:** 2026-09-08T10:31:59.111530+00:00 (UTC, Beginn des Testharness).
**Aufbau:** Vorhandene IMX500, Picamera2, 960×720 RGB888, angefordert 15 Bilder/s,
Auto-Belichtung, kein Inferenzmodell. HTTP nur an 127.0.0.1:18080 für diesen
Kurztest. Kamera und Fokus physisch unverändert. Zunächst blockierte die
Sandbox lokale TCP-Sockets; erfolgreicher Versuch außerhalb der Sandbox.

**Beobachtung:** JPEG über HTTP gelesen, danach fortlaufende Bildnummern und
Live-Status geprüft. Schlussstatus: Bild 50, mittlere Software-Verarbeitungsrate
15,0 Bilder/s (CLOCK_MONOTONIC), JPEG 45.813 Bytes. SIGTERM beendet den Prozess
mit Exit 0. Das Diagnosebild zeigt eine teilweise unscharfe, kopfstehende
Arbeitsplatzszene ohne auswertbare Geräteanzeige; Overlay „Kein Display-Kandidat“.

**Schluss:** Aufnahme, Verarbeitung, JPEG-Übertragung und reguläres Beenden
funktionieren lokal. Keine Abnahme der Display-Erkennung an einem echten
7-Segment-Gerät, des Windows-Browsers oder des SSH-Tunnels. Keine Aussage über
Aufnahme-zu-Anzeige-Latenz. Nächster Versuch: Gerät frontal positionieren und
Fokus einstellen, dann Windows-Verbindung und Kandidaten visuell prüfen.

**Diagnose-Schnappschuss:** `var/examples/17_camera_display_preview/` mit
`diagnostic.json`, `camera.log`, `preview.jpg` (lokale, nicht versionierte
Artefakte). Zahlen zusätzlich in [VALIDATION.md](VALIDATION.md).

## 2026-09-08 — Neuer Workbench-Kameradienst

**Ziel:** Nach Modularisierung realen Kamera-Worker, Controls/Metadaten und
sauberes Beenden prüfen. **Zeit:** 2026-09-08T12:03:21.753165+00:00 (UTC,
Zeit der Ergebnisabfrage).

**Aufbau:** Bestehende IMX500 unverändert, 960×720 RGB888, angefordert 15 fps,
AeEnable=true und Contrast=1.0; keine physische Fokus-/Positionsänderung.
Controller direkt gestartet und nach mindestens 25 Bildern geschlossen.

**Ergebnis:** Bildnummer 25, Live-Status true, Verarbeitungsrate 14,8 Bilder/s
(CLOCK_MONOTONIC), Revision 0 gesetzt, kein Fehler, Thread beendet.
Istwerte: ExposureTime 24.631 µs, AnalogueGain 1,4992679, FrameDuration 66.657 µs.
SensorTimestamp 18.366.022.890.000 ns, SENSOR_BOOTTIME; Semantik unbekannt,
Unsicherheit None. Die übrigen rohen Metadaten sind im Diagnoseartefakt erhalten.

**Deutung:** Neuer Kameradienst funktioniert mit realer Hardware. Kein Nachweis
für Windows-Anmeldung, Erkennungsqualität, Multiplexvollständigkeit oder eine
reale Aufnahme-zu-Browser-Latenz. Auto-Setup wurde dabei nicht durchgeführt.

**Schnappschuss:** `var/workbench/diagnostics/camera-smoke.json` und
`camera-smoke.jpg`. Zahlen zusätzlich in VALIDATION.

## 2026-09-08 — Fokusdiagnose und blockierter Sensor

**Ziel:** Klären, warum das Bild unscharf ist und warum „Autofokus" und
„manueller Fokus" nicht wirken. **Zeit:** 2026-09-08T13:14:49.641331+00:00
(UTC, Beginn der Messung).

**Aufbau:** Bestehende IMX500 unverändert am Platz; die Kamera zeigte auf einen
LG-Monitor in kurzem Abstand, schräg von unten. Belichtung in Automatik,
Innenraumlicht. **Keine** physische Fokus- oder Positionsänderung, keine
Bootkonfiguration angefasst. Zwei Streamkonfigurationen nacheinander:
960×720 und 2028×1520 RGB888, je acht Bilder.

**Beobachtung 1 — es gibt keine Fokusmechanik.** `Picamera2.camera_controls`
enthält **kein** `AfMode`, `LensPosition`, `AfState` oder sonstiges Feld mit
`Af`/`Lens`/`Focus` im Namen. Vorhanden sind 29 Controls, darunter `Sharpness`
— das ist ISP-Nachschärfung, keine Fokusverstellung. Damit ist belegt, was
[HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) als „Fokus: manuell" führt: das
Objektiv ist ausschließlich mechanisch verstellbar. Ein Autofokus kann nicht
„nicht funktionieren" — er existiert nicht.

**Beobachtung 2 — das Bild ist echt unscharf.** Laplace-Varianz im ganzen Bild:
Median 11,53 bei 960×720 und 8,24 bei 2028×1520 (Zahlen in
[VALIDATION.md](VALIDATION.md)). Die Unschärfe ist über das gesamte Bild
gleichmäßig; kein Bereich ist scharf, auch nicht bei anderer Entfernung im
selben Bild. Gleichzeitig wählte die Automatik ExposureTime 33.044 µs bei
AnalogueGain 2,03 — bei 33 ms Belichtung ist **Bewegungsunschärfe eines nicht
starr montierten Moduls von Defokussierung nicht zu unterscheiden**. Der
gesättigte Anteil lag bei 5,8 %, also deutlich über der 2-%-Glanzschwelle.

**Beobachtung 3 — der Sensor streamt seitdem nicht mehr.** Die anschließende
Messung, die genau diese Unterscheidung treffen sollte (kurze Belichtung mit
hoher Verstärkung), bekam kein Bild mehr. Seit 15:20:32 Ortszeit meldet der
Kernel bei jedem Startversuch `rp1-cfe 1f00110000.csi: stream on failed in
subdev` — 8.429 Einträge zwischen 15:20:32 und 15:22:12, dazu
`WARNING ... call_s_stream+0x100/0x118 [videodev]` und
`videobuf2_common: driver bug: stop_streaming operation is leaving buffer 0 in
active state`. Betroffen ist nicht nur dieses Projekt: auch `rpicam-still`
liefert kein Bild mehr und bleibt ohne Ausgabe hängen. Enumeration funktioniert
weiter (`camera-commissioning.sh` endet mit Exit 0, „Kamera einsatzbereit"), das
prüft aber nur Device-Tree und `global_camera_info()`, nicht den Bilddurchlauf.
Kein Prozess hält Kameraknoten außer PipeWire/WirePlumber, die das schon vorher
taten. Auslöser war offenbar die Folge Konfigurieren → Streamen → `stop()` →
neue Konfiguration → `start()` innerhalb eines Prozesses beziehungsweise das
erneute Öffnen danach; die letzte erfolgreiche Aufnahme lag um 15:14.

**Schluss:** Für die Schärfe sind zwei Ursachen offen — mechanischer Fokus und
33-ms-Belichtung. Die trennende Messung ist erst nach einem **Reboot** möglich,
weil der Sensor jetzt keinen Stream mehr aufsetzt; ein Modul-Reload würde
`sudo` verlangen, das seit dem letzten Reboot ein Passwort braucht. Der
Stream-Neuaufsetzer im Kamerathread ist damit ein Risiko im Betrieb und steht
als [OQ-22](open-questions.md).

**Schnappschuss:** `var/workbench/diagnostics/focus-probe.json`,
`focus-960x720.jpg`, `focus-2028x1520.jpg` (nicht versioniert).

## 2026-09-08 — Unschärfeform gemessen: Defokussierung, nicht Bewegung

**Ziel:** Entscheiden, ob die Unschärfe vom Objektiv oder von 33 ms
Belichtungszeit kommt. **Zeit:** 2026-09-08, Vollbild von 15:31:41 Ortszeit
(`rpicam-still --immediate`, 4056×3040, 2.122.979 Bytes, nach dem Reboot um
15:30:18 aufgenommen).

**Aufbau:** Kamera unverändert am Platz, sehr dunkles Motiv in Nahdistanz, im
Bildteil unten rechts punktförmige Lichtreflexe. Keine physische Änderung.

**Methode:** Ein defokussierter Lichtpunkt bildet sich als **Scheibe** ab, ein
verwackelter als **Strich**. Die hellen Flecken (Schwelle 255) wurden über
Zusammenhangskomponenten isoliert und über die zweiten Momente in Haupt- und
Nebenachse zerlegt. Das ist unabhängig von Belichtungszeit und Motivkontrast.

**Messergebnis:** Fünf Reflexe, Durchmesser 29,4 bis 50,1 px, Median
35,0 × 29,2 px, Achsverhältnis **1,20**. Bewegungsunschärfe würde die Flecken
in eine gemeinsame Richtung strecken; ab etwa 1,8 wäre das erkennbar. Laplace-
Varianz des Vollbilds 22,26, in der Bildmitte 12,39.

**Schluss:** **Defokussierung, eindeutig.** Die Belichtungszeit ist als Ursache
ausgeschlossen, die geplante Belichtungsreihe entfällt. Rechnerische Größenordnung
zur Einordnung: 35 px entsprechen bei 1,55 µm Pixelabstand etwa 54 µm
Zerstreuungskreis; mit D = f/N = 4,74 mm / 1,79 = 2,65 mm passt das zu einem
Fokusfehler in der Größenordnung „Objektiv auf unendlich, Motiv bei etwa 23 cm".
Die absolute Zahl hängt am unbekannten echten Abstand und ist nur eine
Plausibilitätsprobe, kein Messwert. Konsequenz für den Handgriff: Objektiv mit
dem Fokuswerkzeug drehen, Abstand mindestens 20 cm einhalten und dabei einen
Schärfewert mitlaufen lassen (`~/fokusmesser.py`).

**Nebenbefund zur Kamerasperre:** Der erste Streamfehler nach dem Reboot lag um
15:31:51, zehn Sekunden nach der erfolgreichen Aufnahme und **vor** jedem
Projektcode. Damit ist der Streamwechsel im Kamerathread als Auslöser
widerlegt. PipeWire und WirePlumber halten `/dev/v4l-subdev2` — den
imx500-Sensorknoten — dauerhaft offen, WirePlumber 0.5.8 mit aktivem
libcamera-Monitor. Zwei libcamera-Klienten am selben Sensor sind die beste
Erklärung für `stream on failed in subdev`. Test und Abschaltzeilen in
[OQ-22](open-questions.md).

**Schnappschuss:** `/tmp/first-light.jpg` (nicht versioniert, Vollbild),
Messskript `~/fokusmesser.py`.

## 2026-09-08 — Fokus gedreht, Bestwert 75; Kamerasperre als Treiberfehler belegt

**Ziel:** Objektiv mit Rückmeldung scharf stellen und die Kamerasperre
einordnen. **Zeit:** Boots um 15:30:18 und 15:42:37, Läufe 15:31 bis 15:52.

**Aufbau:** Kamera unverändert am Platz, `~/fokusmesser.py` bei 2028×1520 mit
Belichtungsautomatik, eine Sitzung, Ende mit Strg+C. Der Bediener drehte
währenddessen am Objektiv.

**Messergebnis Fokus:** Bester Schärfewert **75,0** gegenüber 11,53 bei der
Ausgangslage am selben Motiv (Laplace-Varianz, relativ). Das Objektiv **dreht
also und wirkt** — der frühere Verdacht „manueller Fokus ohne Wirkung" ist
damit erledigt. Ob 75 das erreichbare Maximum ist, ist offen: der Lauf hat kein
Bild gespeichert, und die Sitzung endete durch die Kamerasperre. Der
Fokusmesser speichert seit dieser Session das schärfste Bild mit.

**Messergebnis Kamerasperre — zwei Hypothesen widerlegt, eine belegt:**

1. *PipeWire-Kamerakonkurrenz:* widerlegt. Der libcamera-Monitor von
   WirePlumber wurde benutzerseitig abgeschaltet, PipeWire hält
   `/dev/v4l-subdev2` danach nicht mehr — der Fehler bleibt.
2. *Hängender Prozess:* widerlegt als Ursache. Ein Fokusmesser-Lauf stand nach
   Strg+C noch 1:57 min in `futex_wait_queue` und hielt den Sensor; das ist
   aber die Folge davon, dass `Picamera2.stop()` auf Puffer wartet, die der
   Treiber nicht zurückgibt. Das Töten des Prozesses gab die Kamera **nicht**
   frei, und der Kill löste selbst wieder
   `cfe_stop_streaming ... leaving buffer 0 in active state` aus.
3. *Treiberfehler:* belegt, vom Kernel wörtlich so benannt —
   `videobuf2_common: driver bug: stop_streaming operation is leaving buffer 0
   in active state` aus `cfe_stop_streaming+0xd4/0x200 [rp1_cfe]`. Zwei
   Folgesymptome beobachtet: `stream on failed in subdev` und
   `/dev/video4[15:cap]: Failed to queue buffer N: Invalid argument`. Am Ende
   hängt bereits `Picamera2(0)`. Nur ein Reboot stellt den Zustand her.

**Deutung:** Der Streamabbau hinterlässt die vb2-Warteschlange defekt. Sechs
Datenpunkte legen nahe, dass es die Streamgröße entscheidet: drei Sitzungen bei
960×720 überlebten den Abbau, jede Sitzung mit 2028×1520 oder 4056×3040 war die
letzte des Boots. Tabelle und der nächste Test in
[OQ-22](open-questions.md). Ist das bestätigt, holt der Messbetrieb die
Ziffernhöhe über `ScalerCrop` statt über einen größeren Stream — der
Sensormodus bleibt in beiden Fällen 2028×1520.

**Was ich falsch gesagt hatte:** zuerst den Streamwechsel im Kamerathread, dann
den hängenden Prozess. Beides widerlegt, beides oben festgehalten, damit es
niemand erneut verfolgt.

**Schnappschuss:** Kernelmeldungen im Journal des jeweiligen Boots;
Messskript `~/fokusmesser.py`.

## 2026-09-08 — Fokus eingestellt: Anzeige lesbar

**Ziel:** Objektiv mit Rückmeldung auf die Anzeige scharf stellen.

**Aufbau:** BK Precision 5491B Tischmultimeter als Testobjekt, Anzeige
„-000.13mV DC". Kamera am Platz, `~/fokusmesser.py` bei 960×720 mit
Belichtungsautomatik. Der Bediener drehte in mehreren Sitzungen am Objektiv und
beobachtete den Schärfewert.

**Messergebnis:** Bestwert **216,6** (Ausgangslage 11,53, Zwischenstand 75,0).
Im Anzeigebereich Laplace-Varianz 480,2, Kontrast 0,749, gesättigter Anteil
0,0000, Ziffernhöhe etwa 37 px. Zahlen in [VALIDATION.md](VALIDATION.md),
Bild `var/workbench/diagnostics/fokus-erreicht-960x720.jpg`.

**Deutung:** Der mechanische Fokus ist damit eingestellt und die Bildkette
liefert an diesem Gerät lesbare Ziffern über der 30-px-Marke — ohne
`ScalerCrop`. Kein Glanz **im** Display; die Sättigung im Gesamtbild kommt von
weißem Papier in der Umgebung. Offen bleibt alles zur Erkennung selbst: das
Testobjekt ist kein GSV-Messverstärker, und ein echter Gerätedatensatz fehlt
weiter. Zwei mechanische Aufgaben folgen: Objektiv gegen Verdrehen sichern und
die Halterung starr ausführen, sonst ist die Einstellung beim nächsten Anstoßen
verloren ([OPTICAL_SETUP.md](OPTICAL_SETUP.md)).

**Zur Kamerasperre:** In dieser Runde liefen bei 960×720 **mehrere** Sitzungen
hintereinander, bevor der Fehler erneut auftrat. Die Hypothese „nur die großen
Sensormodi lösen es aus" ist damit zu eng: 960×720 verzögert das Problem, hebt
es aber nicht auf. Der Streamabbau bleibt der Verdächtige, offenbar mit einem
Wettlauf, der nicht bei jedem Abbau zuschlägt. Stand in
[OQ-22](open-questions.md).
