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

## 2026-09-09 — Kamerasperre auch nach frischem Reboot; neue Spur GPIO-Kontention

**Ziel:** `./.venv/bin/dispread serve` scheiterte beim Start mit
`Failed to queue buffer N: Invalid argument` auf `/dev/video4`. Ursache
gesucht, mit dem Anspruch, diesmal einen echten Reboot von einem bloßen
Wiederauftreten des alten Fehlers zu unterscheiden.

**Aufbau:** Kein physischer Eingriff. Auswertung von `dmesg -T`,
`journalctl` (alle Boots), `/proc/uptime`, `/proc/stat` (`btime`), `chronyd`-
Log, `apt`-Historie, `lsmod`, Device-Tree-Overlay (`imx500-pi5.dtbo`,
dekompiliert mit `dtc`), und dem entpackten `imx500.ko` (Strings, kein
Kernel-Quellcode vorhanden).

**Beobachtung 1 — es war ein echter Reboot, keine Fortsetzung der alten
Sperre:** `dmesg -T` zeigt „Booting Linux on physical CPU 0x0” um 09:35:40,
`btime` in `/proc/stat` bestätigt denselben Zeitpunkt, `/proc/uptime` lag beim
ersten Fehlschlag bei ca. 370 s. `who -b` und `journalctl --list-boots` hatten
fälschlich noch den 2026-09-07 15:26 als Bootzeit eingetragen — das ist ein
reiner Anzeigefehler: Dieser Pi hat keine batteriegepufferte RTC, startet mit
der beim letzten Herunterfahren gespeicherten Zeit, und `chronyd` korrigiert
sie erst **nach** dem Booten (`System clock was stepped by 151759.56
seconds` um 09:36:19). Dienste, deren Startzeit-Bookkeeping vor diesem Schritt
lief (u. a. `wireplumber.service`), zeigen deshalb ebenfalls das falsche
Datum. Für die Kette selbst folgenlos, aber beim nächsten Debugging dieser Art
zuerst `chronyd`-Log statt `who -b`/`uptime` prüfen.

**Beobachtung 2 — der Fehler trat trotzdem sechs Minuten nach dem Reboot beim
allerersten Streamversuch auf:** Erster Fehlschlag 09:41:51, zweiter 09:44:06.
Beide Male dieselbe Abfolge: `imx500 10-001a: setup of GPIO led failed: -121`
→ `imx500_power_on: failed to get led gpio` → `rp1-cfe: stream on failed in
subdev` → beim Abbau `videobuf2_common: driver bug: stop_streaming operation
is leaving buffer 0 in active state` aus `cfe_stop_streaming`. Damit widerlegt
diese Session die bisherige OQ-22-Annahme „nur ein Reboot hilft" — hier half
er nicht, jedenfalls nicht sofort.

**Beobachtung 3 — kein Software-Regressions-Kandidat:** Der große
Kamera-Stack-Umbau (`libcamera` 0.7.1→0.7.2+rpt20260817, `libpisp`
1.6.0→1.7.0, `rpicam-apps`/`picamera2` 1.12.0/0.3.36→1.13.0/0.3.37) lief laut
`apt`-Historie bereits am 2026-09-07 um 13:31:59 — vor allen dokumentierten
erfolgreichen Sitzungen am 2026-09-08. Der tägliche `apt-daily-upgrade.timer`
hatte heute vor dem Fehlschlag noch nicht gefeuert. Der Fehler ist also nicht
durch ein neues Paket entstanden. Nebenbefund: `linux-headers-6.18.34…` und
passende `imx500.ko` liegen bereits unter `/usr/lib/modules/6.18.34+rpt-rpi-2712/`,
gebootet wird aber weiter `6.12.34+rpt-rpi-2712` — ein separater, hier nicht
verfolgter Punkt (kein Rollback nötig, nur nicht der aktive Kernel).

**Beobachtung 4 — neue Spur, GPIO-Kontention über den gemeinsamen RP1-Chip:**
`imx500-pi5.dtbo` (dekompiliert) zeigt `led-gpios` und `reset-gpios` am selben
GPIO-Controller-Phandle. Die entpackten Strings aus `imx500.ko` zeigen, dass
beide über `devm_gpiod_get_optional()` geholt werden — die Fehlermeldung
erscheint bei diesem Aufruf nur bei einem echten Fehler vom GPIO-Subsystem,
nicht bei einer fehlenden, optionalen Eigenschaft. Auf demselben Pi laufen
minütlich `x1201-monitor.service` (Geekworm-x120x-USV-Fuel-Gauge, Skript
`/usr/local/bin/x1200_once.py`) und `rm520n-signal-cache`/`-watchdog`
(MEhub, 5G-Modem). `x1200_once.py` fasst direkt `/dev/gpiochip0` an
(`python3-gpiod`, `PLD_PIN` als Input) — auf dem Pi 5 ist das der RP1-Chip,
derselbe Chip, der auch CSI/CFE und die Kamera-GPIOs bedient. Beide
Fehlschläge heute (09:41:51, 09:44:06) lagen in derselben Minute wie ein
`x1201-monitor.service`-Tick (09:41:00 bzw. 09:44:00) — bei minütlichem
Tick statistisch nicht beweisend, aber mechanistisch plausibel: ein
Firmware-/Kontroller-seitiger Konflikt zwischen zwei gleichzeitigen
RP1-GPIO-Anfragen (Kamera-Power-on vs. USV-Pegelabfrage) würde exakt so ein
`-EREMOTEIO` an einer Seite erzeugen.

**Schluss:** Kein Codefehler in `dispread`, keine Paket-Regression. Neue,
bislang nicht dokumentierte Hypothese: Die Kamerasperre kann durch
RP1-GPIO-Kontention mit anderen, auf demselben Pi laufenden Diensten
(`x1201-monitor`, ggf. `rm520n-*`) ausgelöst werden, nicht nur durch den
bereits bekannten Streamabbau-Wettlauf. Nicht geprüft und offen: ob ein
echter Stromzyklus (statt `sudo reboot`) den Zustand zuverlässiger auflöst als
der bisher übliche Warmstart — dazu wurde nichts unternommen, das hätte
andere MEhub-Dienste auf demselben Gerät unterbrochen. Details und
vorgeschlagene Prüfschritte: [OQ-22](open-questions.md).

**Nachtrag 10:05 — reiner Picamera2-Minimalreproducer bestätigt, Sperre
inzwischen dauerhaft:** Ein isolierter Test ohne `dispread`
(`Picamera2().configure(create_preview_configuration(960x720)).start()`,
kein Projektcode) scheiterte identisch — damit ist die Ursache beim
Plattform-/Treiberstack angesiedelt, nicht bei `dispread`. Der Prozess hing
bis zum 30-s-Timeout und löste beim Beenden erneut denselben
vb2-Treiberfehler aus; kein Zombie-Prozess blieb zurück, das Gerät ist danach
wieder unbelegt, aber weiterhin defekt. Die Kamera ist damit seit 09:41 Uhr
durchgehend gesperrt — ein gezielter Kontentionstest (Timer pausieren, dann in
der Minutenmitte erneut versuchen) liefert jetzt keine neue Information mehr,
weil jeder Versuch ohnehin scheitert; er müsste unmittelbar nach dem nächsten
Reboot laufen, bevor die Sperre wieder eintritt. Blockiert an zwei Stellen ohne
`sudo`-Passwort: `systemctl stop x1201-monitor.timer`/`rm520n-*.timer` (nicht
in der NOPASSWD-Liste) und `dynamic_debug` (kein `debugfs` gemountet,
verlangt root). `sudo poweroff` ist zwar NOPASSWD hinterlegt, wurde aber
bewusst nicht ausgeführt: ohne Fernsteuerung der Stromversorgung wäre die
Maschine danach nicht selbst wieder hochzubringen.

## 2026-09-09, Nachmittag — Kamerasperre reproduzierbar nach ~24 Power-Zyklen; Ursache beim RP2040 der AI-Camera, nicht bei RP1/x1201

**Ziel:** Die Vormittags-Spur (GPIO-Kontention mit `x1201-monitor` über
RP1/`/dev/gpiochip0`) gezielt prüfen. Nutzer hat vor einem erneuten Reboot die
Timer gestoppt; nach dem Reboot liefen sie aber automatisch wieder an
(`systemctl stop` überlebt keinen Neustart aktivierter Timer) — die geplante
saubere Trennung war so nicht möglich, stattdessen ergab sich ein aussagekräftiger
Dauertest mit aktiven Timern.

**Aufbau:** Reboot um 10:09:16 verifiziert (`Booting Linux on physical CPU`).
Minimalreproducer ohne `dispread`: `Picamera2().configure(
create_preview_configuration(960x720)).start().capture_array().stop().close()`
im Loop, alle ca. 12 s, `timeout 20s` je Versuch.

**Messergebnis:** Zyklen 1–24 (uptime 0 bis 442 s) liefen **alle** sauber
durch (`closed. OK`, exit 0) — über drei Minutengrenzen der `x1201`/`rm520n`-
Timer hinweg, ohne einen einzigen Fehlschlag. Zyklus 25 (uptime 472 s)
scheiterte und blieb ab da dauerhaft gesperrt (Zyklen 25–30 alle
Timeout/Fehler). Kernel-Log exakt zum Fehlschlagzeitpunkt (10:16:48, kein
Zusammenhang zu einem Timer-Tick, die lagen bei :00/:20):

```
rp2040-gpio-bridge 10-0040: rp2040_gbdg_i2c_send() rp2040_gbdg_wait_until_free failed
rp2040-gpio-bridge 10-0040: rp2040_gbdg_gpio_dir_out(19, 0) could not ST_CL
rp2040-gpio-bridge 10-0040: rp2040_gbdg_i2c_send() rp2040_gbdg_wait_until_free failed
imx500 10-001a: setup of GPIO led failed: -121
imx500 10-001a: imx500_power_on: failed to get led gpio
rp1-cfe 1f00110000.csi: stream on failed in subdev
```

**Deutung:** `led-gpios`/`reset-gpios` aus `imx500-pi5.dtbo` hängen nicht am
RP1, sondern an einem **eigenen RP2040-Mikrocontroller auf dem AI-Camera-
Modul**, der Power-Sequencing/Reset/LED über I2C-Bus 10 Adresse 0x40 steuert
(`rp2040-gpio-bridge`). Nach genug Power-Zyklen antwortet dieser RP2040 nicht
mehr auf I2C — die Vormittags-Hypothese „Kontention mit `x1201-monitor` über
RP1" ist damit widerlegt (falscher Chip, und der Wedge-Zeitpunkt lag nicht
bei einem Tick). Ob RP2040-Firmwarefehler, I2C-Timing-Grenzfall bei
Wiederholung oder Ressourcenleck ist offen. Der Reboot um 10:09 hat den
RP2040 zuverlässig zurückgesetzt (24 saubere Zyklen danach) — die Sperre
entsteht **innerhalb** einer Bootsitzung, reproduzierbar nach grob 20–25
Power-Zyklen, unabhängig von Sensorauflösung oder Fremdprozessen.

**Praktische Konsequenz für `dispread`:** `workbench/Controller._worker`
konfiguriert den Stream bei jeder Auflösungs-/Bildraten-Änderung neu — jede
Einstelländerung im laufenden Betrieb nähert das System diesem Limit, nicht
nur der Wechsel zu großen Sensormodi. Ein Zähler laufender Power-Zyklen mit
Warnung/Blockade vor dem gemessenen Limit wäre eine mögliche Absicherung;
nicht umgesetzt, da eine Entscheidung über die Workbench-Architektur nötig
ist. Vollständige Log-Ausschnitte: Sitzungsverlauf, nicht separat abgelegt.
Stand und offene Fragen: [OQ-22](open-questions.md).

## 2026-09-09 — Workbench-OCR: synthetischer Rundlauf und erster VFD-Befund

**Ziel:** Die neue Bedienoberfläche der bereits vorhandenen
7-Segment-Erkennung prüfen und erstmals feststellen, ob der Leser auf dem
realen BK-5491B-Bild einen Wert liefert. Keine Freigabe und keine
Konfidenzkalibrierung.

**Automatischer Aufbau:** `render_display(-12.34)` mit fünf Stellen, zwei
Nachkommastellen, Vorzeichen und Einheit `mV` wurde über die echte
`Controller.publish()`-Strecke geschickt. Ergebnis: Rohtext `-012.34`, Wert
−12,34, fünf Segmentbelege, Gate-Vorschau `valid`, keine Ablehnungsgründe,
`released=false`, `confidence_calibrated=false`. Die unbekannte
Dezimalposition wurde separat geprüft und mit `decimal_point_unknown` plus
`no_value` abgelehnt.

**Realer Offline-Aufbau:** Vorhandenes, am 2026-09-08 aufgenommenes Bild
`fokus-erreicht-960x720.jpg` des BK Precision 5491B; sichtbare Anzeige
`-000.13 mV DC`. Manuell bestätigte ROI in Bildpixeln `[322,325,180,40]`, nur
Vorzeichen und fünf Ziffern, Zielausschnitt 400×160. Layout: fünf Stellen,
zwei profilfeste Nachkommastellen, Vorzeichen, Einheit `mV`,
`sign_cell_ratio=0.6`. Die manuelle Wahrheit wurde dem Leser und dem Gate
nicht übergeben. Zeitbasis des Quellbilds `FILE_MTIME`, Unsicherheit `None`;
keine Latenzaussage zulässig.

**Ergebnis Offline:** Rohtext `777?7`, kein Wert, Gate `unreadable`, Gründe
`unreadable_cells:1` und `no_value`. Crop-Schärfe 88,37,
Segmentkontrast 0,4602, kleinste Marge 0,6495, Sättigung 0,0000. Das Overlay
zeigt, dass die festen relativen Segmentpunkte aus dem synthetischen Layout
nicht zur realen VFD-Glyphengeometrie passen; die schmale `1` ist besonders
deutlich. Wichtig: keine stille gültige Fehlablesung, aber auch keine reale
Lesefähigkeit. Als [OQ-23](open-questions.md) festgehalten.

**Laufender Kamerastream:** Ein bereits laufender Workbench-Prozess bei
960×720 und 15 fps wurde ohne Neustart, Auflösungswechsel oder zusätzlichen
RP2040-Power-Zyklus benutzt. Die alte ROI wurde reversibel gesetzt und 30
verschiedene Frames (Sequenzen 34329–34358) gelesen: 30× `?????`, 30×
`unreadable`, kein Wert; Gründe `unreadable_cells:5`, `no_value`.
Crop-Schärfe 1,57. Weil die aktuelle Szene nicht visuell bestätigt werden
konnte, ist das **kein** Gerätedatenpunkt und fließt in keine Quote ein. Das
Profil wurde danach auf den vorherigen unbestätigten Defaultzustand
zurückgesetzt. Keine physische Einstellung und keine dauerhafte
Hardwarekonfiguration geändert; deshalb kein Update am Hardwareprofil.

**Artefakte:**
`var/workbench/diagnostics/ocr-bk5491b-offline.jpg` (Original mit ROI,
Zellen und Abtastpunkten) und `ocr-bk5491b-offline.json` (Layout, Evidenz,
Zeitbasis, manuelle Wahrheit, `reference_was_reader_input=false`,
`formatter_provisional=true`).

## 2026-09-09 — ROI-Lag eingegrenzt und Shutdown isoliert geprüft

**Auslöser:** Bedienerrückmeldung: Nach Bestätigung der ROI wird die Web-UI
langsam/unbedienbar, der Dienst lässt sich nicht zuverlässig stoppen, und die
Zahlenerkennung passt nicht auf die Anzeige. Der laufende reale Prozess blieb
über den privaten Statussocket erreichbar. Beobachtet wurden 15,0 verarbeitete
Bilder/s und rund 50 % CPU über den Python-/OpenCV-Threadverbund; diese
Momentaufnahme ist keine normierte Lastmessung.

**Codebefund:** `Controller.publish()` hielt den gemeinsamen `RLock` über
Qualitätsberechnung, Vollbild-Kandidatensuche, OCR, Overlay und
JPEG-Kompression. Die Kandidatensuche lief auch nach Bestätigung der ROI weiter.
Damit konkurrierten Status, ROI-Befehl und Shutdown 15-mal pro Sekunde mit dem
gesamten Bildpfad. Die ROI war ausschließlich ein achsparalleles Rechteck; eine
geneigte Anzeige konnte nicht passend auf das feste 400×160-Raster entzerrt
werden. Der Shutdown rief im `finally` Kamera-`stop()`/`close()` ohne Wachhund
auf.

**Änderung und Offline-Messung:** Vollbildsuche nur noch vor Bestätigung;
Bildarbeit außerhalb des Controller-Locks; OCR-Vorschau 5 Hz; vier editierbare
Ecken mit Perspektivtransformation; bewachte Kameraabschlussaufrufe. Je 100
Aufrufe auf dem gespeicherten 960×720-Bild, Dauerbasis CLOCK_MONOTONIC:
30,837 ms/Bild unbestätigt mit Kandidatensuche, 5,801 ms/Bild bestätigt und
gedrosselt, 9,515 ms/Bild bei künstlich in jedem Bild erzwungener OCR. Diese
Zahlen sind reine Verarbeitungslaufzeiten, keine Aussage zur Aufnahmezeit oder
End-to-End-Latenz.

**Shutdown-Test:** Separater `serve --simulate` auf Loopback, eigener privater
Unix-Socket und temporäres Datenverzeichnis. `dispread stop` antwortete
`{"stopping": true}`; der Prozess endete anschließend mit Exit 0. Keine echte
Kamera und keine Hardwarekonfiguration berührt. Der bereits laufende reale
Dienst wurde nicht gestoppt oder neu gestartet, weil darin ein ungespeicherter
Bediener-ROI aktiv war.

**Bewertung:** Die statischen Ursachen sind beseitigt und synthetisch geprüft;
die konkrete Windows-Browserreaktion sowie Shutdown mit echter Kamera sind erst
nach einem kontrollierten Neustart des realen Dienstes belastbar. Daher OQ-24
`in Arbeit`, nicht `geklärt`. Perspektivkorrektur verbessert die Geometrie,
löst aber nicht ohne reale Bildsammlung die VFD-Glyphenfrage OQ-23.

## 2026-09-11 — Warum drei Kandidatenänderungen am Decoder verworfen wurden

**Anlass:** Bedienerauftrag, das OCR-Problem zu lösen — die Einrichtung kostet
zu viel Zeit, weil die Segmentpunkte exakt sitzen müssen, und eine im Lauf
verrutschende Kamera bricht die Erkennung ab. Eigene Annotation hunderter
Fotos ist ausdrücklich nicht praktikabel, weil das System universell
7-Segment-Anzeigen lesen soll.

**Aufbau:** Kein Hardwarezugriff. Ausgewertet wurden ausschließlich die bereits
vorhandenen Aufnahmen unter `var/workbench/annotations/`, mit dem jeweils
gespeicherten `roi_quad`, `ocr_box` und `layout` — also mit genau der
Geometrie, die der Bediener seinerzeit selbst bestätigt hatte. Gelesen wurde
über denselben Weg wie im Betrieb (`rectify` auf 400×160, dann `crop_box`).
Der Vergleichscode lag im Sitzungs-Scratchpad und wurde bewusst nicht ins Repo
übernommen: er war Entscheidungsgrundlage, kein Baustein.

**Zahlen:** vollständig in [VALIDATION.md](VALIDATION.md), Abschnitt
„2026-09-11 — Ausgangsmessung `sevenseg/2`".

**Deutung — und warum die ursprüngliche Reihenfolge falsch war.** Der Plan
dieser Sitzung sollte zuerst die Segmentmessung robuster machen: Segmente über
ihre Fläche statt an einem Punkt messen, und je Stelle gegen eine
Panel-Referenz normieren statt gegen eine globale Schwelle. Beides war gut
begründet — OQ-13 schlägt die Panel-Referenz selbst vor, und OQ-23 führt die
Punktempfindlichkeit seit dem 2026-09-09.

Gegen echte Bilder gehalten trägt keine der beiden Änderungen:

* Die Panel-Referenz mit einer Otsu-Schwelle *innerhalb* der Zelle punktet
  exakt wie der Ist-Stand. Der Grund ist elementar und hätte vorher auffallen
  können: eine Ziffer wie `0` hat sechs aktive und ein inaktives Segment, und
  Otsu maximiert eine **gewichtete** Zwischenklassenvarianz. Der ausgewogene
  4:3-Schnitt schlägt den richtigen 6:1-Schnitt.
* Mit einer spannenrelativen Schwelle statt Otsu wird das bisher abgelehnte
  Bild korrekt gelesen — dafür wird in einem anderen Bild aus einer `1` eine
  `7`. Dass das überhaupt auffiel, war Glück: eine weitere Stelle desselben
  Bildes wurde `?`, sonst wäre es als stille Fehlablesung durchgelaufen. Der
  Rohwert von Segment `a` liegt dort bei 0,38, obwohl die Stelle eine `1`
  zeigt und `a` aus sein muss. Ob das Übersprechen, Nachleuchten oder ein zu
  weit reichender Abtastpunkt ist, ist offen (OQ-23).
* Die Flächenmessung ist mit den heutigen Profilwerten deutlich **schlechter**
  als die Punktmessung. `thickness_ratio=0,16` und `inset_ratio=0,10` sind
  Defaults, die nie an einem realen Gerät kalibriert wurden; die Segmentmasken
  liegen damit systematisch neben den echten Leuchtflächen.

Der eigentlich lehrreiche Befund steckt im Sweep über diese beiden Parameter:
`0,12/0,10` und `0,20/0,05` erreichen dieselbe Punktzahl. Das sind keine zwei
guten Antworten, sondern ein unterbestimmtes Problem. Sechs Bilder **eines**
Geräts können zwischen konkurrierenden Decodern nicht entscheiden — zwei
Kandidaten punkteten identisch mit dem Ist-Stand und versagen trotzdem auf
verschiedenen Bildern.

**Konsequenz für die Planung:** Die Reihenfolge wurde umgedreht. Erst die
Messvorrichtung (Clipaufnahme mit einem getippten Label je Clip, `replay://`,
Benchmark mit getrennter Zählung von korrekt / **falsch angenommen** /
abgelehnt), dann die Kalibrierung der Geometrie aus dem getippten Wert, dann
die Nachführung — und die Decoder-Änderung zuletzt und datengesperrt. Details
in [PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md).

Dass der Ist-Stand auf diesen sechs Bildern **null** falsche Annahmen hat, ist
dabei die wichtigste Zahl: sie ist ab jetzt die Nichtregressionsbedingung, und
gegen null blockiert schon eine einzige falsche Annahme jede Änderung.

## 2026-09-21 — Dataset-Benchmark: erster echter Lauf, OQ-23 erstmals gezählt

Aufbau: `scripts/dataset-benchmark.py` (neu diese Sitzung, siehe
[PLAN_2026-09-21-dataset-benchmark.md](PLAN_2026-09-21-dataset-benchmark.md))
gegen den vollständigen realen Sammelmodus-Bestand gefahren, `--split
development --deskew both`. Vorher eine Vorab-Messung (read-only Spike, im
Plan dokumentiert) an fünf markierten Vertretern, danach die vier Bausteine
(`search_ocr_box`, `fit_dataset_sample`, `target_layout`,
`evaluate_dataset_sample`, `segment_report`, `aggregate`) gebaut, jeweils an
einer `render_display`-Pflichtprüfung verifiziert, bevor überhaupt reale
Bilder angefasst wurden — die Reihenfolge war bewusst so, um bei einem
Fehlschlag zwischen „Skript kaputt" und „OQ-23 bestätigt" unterscheiden zu
können (Konsequenz aus der Messreihe 2026-09-11 oben).

**Erster Lauf brach sofort ab** — nicht wegen eines Bugs, sondern weil die
BK-Precision-Situation „schräg links" noch keine als `selected` markierte
Probe hat (Datensatz ist seit dem Plan von 52 auf 77 Proben gewachsen). Die
ursprüngliche CLI-Fassung beendete beim ersten fehlenden `selected` den
kompletten Lauf; das wurde noch in derselben Sitzung korrigiert (nur die
betroffene Faltung wird übersprungen, der Rest läuft weiter, `exit_code`
bleibt 1) — sonst hätte eine einzelne Bedienlücke bei einem Gerät den
gesamten Befund für das andere Gerät verschluckt.

**Befund (Zahlen in [VALIDATION.md](VALIDATION.md), 2026-09-21):** Von 73
lesbaren Proben (beide Geräte) passt achsparallel **kein einziges** Raster
(0/73) — die Vorab-Messung an fünf Bildern war also keine Anomalie, sondern
der tatsächliche Zustand über den ganzen Bestand. Überraschender zweiter
Fund, nicht Teil der ursprünglichen Fragestellung: der `deskewed`-Arm
(`fit_quad_in_region`) findet für **keine einzige** der 73 Proben überhaupt
ein Quad — bei den zwei Annotationen von 2026-09-10 lag die IoU noch bei
0,91. Vermutung (nicht nachgewiesen): die Sammelmodus-Zielboxen sind absichtlich
locker gezogen (Plan misst ~5-fache Flächenstreuung selbst innerhalb einer
Situation) und reißen damit `fit_quad_in_region`s Flächen-/Überdeckungsfilter,
die gegen engere, bereits bestätigte `roi_quad`-Hinweise gemessen wurden.
Das ist jetzt [OQ-25](open-questions.md) zugeordnet, nicht neu erfunden.

**Deutung:** Phase B (die eigentliche Übertragungszahl) kam über keine
einzige der sechs durchgeführten Faltungen hinaus, weil schon der Vertreter
jeder Faltung in Phase A nicht passte — kein „0 % korrekt", sondern
„nicht messbar", und das Skript sagt das auch genau so, nicht beschönigt.
Die nächste sinnvolle Handlung ist **nicht** mehr Proben sammeln, sondern die
Rastergeometrie selbst untersuchen (OQ-23-Update): entweder der
Kandidatenraum in `dispread.ocr.autofit._CANDIDATES` ist für reale Displays
zu eng, oder `cell_boxes` braucht grundsätzlich eine andere Aufteilung als
die für synthetisches Material entworfene.

---

## 2026-09-22 — Zwei fehlerhafte GSV-Beschriftungen gefunden und korrigiert

**Ziel:** Vor dem Festlegen eines Abnahmekriteriums für einen neuen
Dot-Matrix-Leser prüfen, ob die 11 bestätigten GSV-Beschriftungen überhaupt
als Wahrheit taugen.

**Aufbau:** Rein rechnerisch auf dem vorhandenen Datensatz
(`var/workbench/datasets/samples/`, Gerät `87564e345aa047338f954c045bc9df02`),
plus visuelle Kontrolle der beiden auffälligen Bilder nach Entzerrung über
eine Sättigungsmaske. Kein Hardwarezugriff, die laufende Produktions-Workbench
auf Port 7777 wurde nicht angefasst.

**Beobachtung:** Neun der elf Beschriftungen haben exakt 6 Ziffern und 5
Nachkommastellen — das Anzeigeformat des GSV-Sensors ist fest
(`+X.XXXXX mV/V`). Genau zwei wichen ab, und beide erwiesen sich in den
Bildern als Tippfehler bei der Erfassung:

| Probe | Beschriftung war | Anzeige zeigt | Fehler |
|---|---|---|---|
| `663591e6…` | `0.904801` | `+0.94801` | eine `0` zu viel |
| `e96bd68c…` | `0.9801` | `+0.94801` | die `4` fehlt |

**Messergebnis:** Nach der Korrektur weichen **0 von 11** Beschriftungen vom
Festformat ab. Die Bilder blieben unberührt (`sha256` unverändert, gegen die
Sicherungskopien geprüft), `benchmark.load_dataset_samples` lädt weiterhin
alle 88 Proben ohne Übersprungene.

Ein Korrekturweg existierte vorher nicht: `save_sample` lehnt ein abweichendes
Label für denselben `capture_token` bewusst ab. Dafür wurde
`DatasetStore.relabel_sample` gebaut (siehe CHANGELOG). Da `var/` nicht unter
Versionskontrolle steht, hält das neue Feld `label_history` den vorherigen
Wert samt Begründung fest — sonst gäbe es **keinerlei** Spur, dass hier
Grundwahrheit verändert wurde.

**Schluss:** Die Formatkonsistenz-Prüfung ist als Routine für künftige
Sammelläufe brauchbar — sie hat beide Fehler ohne Bildbetrachtung gefunden,
und zwar in Sekunden. Sie trägt aber **nur bei Geräten mit festem
Anzeigeformat**. Dasselbe Verfahren auf die beiden anderen Datensatzgeräte
angewandt liefert bei `91853b73…` (41 Proben) ein völlig einheitliches Bild,
bei `4237c46d…` (36 Proben) sieben Ausreißer — von denen vier einen in sich
stimmigen Nahe-Null-Cluster (`-0.0002` … `-0.0010`) bilden und damit eher nach
legitimer Bereichsumschaltung als nach Tippfehlern aussehen. Dort wurde
**nichts geändert**; ohne Bildprüfung ist „Tippfehler" von „anderer Messwert"
nicht unterscheidbar. Beide Geräte sind ohnehin LED-/VFD-Laborvertreter und
für den späteren Produktionspfad (durchgehend GSV-LCD) nicht maßgeblich.

---

## 2026-09-22 — Task-2-Gate: Rasterverankerung nicht erreicht

**Ziel:** Entscheiden, ob der Dot-Matrix-Zellenleser tragfähig ist — konkret:
lässt sich das 16-Zellen-Raster pro Bild zuverlässig anlegen?

**Aufbau:** Rein rechnerisch auf den 11 GSV-Proben. Entzerrung über
`lcd_quad_in_region`, adaptive Binarisierung, drei verschiedene
Verankerungsverfahren. Zahlen in [VALIDATION.md](VALIDATION.md), 2026-09-22.
Die laufende Produktions-Workbench wurde nicht angefasst.

**Beobachtung — die Messung war dreimal selbst der Fehler.** Die Zahl stieg
19,3 % → 37,5 % → 67,9 %, und **jede** Steigerung kam von einem behobenen
Werkzeugfehler, keiner von einer Änderung am Verfahren:

1. Die Score-Suche über Kante *und* Teilung entartet: Eine halb so grosse
   Teilung packt alle 16 Zellen in den dichten Textbereich und maximiert
   „Tinte in der Mitte, wenig am Rand" besser als das richtige Raster.
2. Die globale Otsu-Schwelle kippt an einem Helligkeitsverlauf über das
   Display und macht das rechte Drittel zu einem schwarzen Klumpen. Eine
   adaptive Schwelle (Gauss, 51, 15) löst das vollständig.
3. Eine 5×7-Zellreduktion mit Schwelle 0,4 löscht tintenarme Glyphen: Der
   Punkt `.` wird zum Nullvektor und damit ununterscheidbar von einer leeren
   Zelle. Das erklärte die zunächst unsinnigen 0/44 bei `blank`.

Ein vierter Fehler in meiner Vorgabe an die Autokorrelation („kleinster Lag,
der ein lokales Maximum ist") drückte die Teilungswahl systematisch an die
Bereichsuntergrenze — die Autokorrelation hatte bei der Referenzprobe ein
lokales Maximum bei Lag 25 (0,328) und ein **stärkeres** bei Lag 36 (0,396),
und 36 ist der richtige Wert.

**Messergebnis:** Bestes Verfahren ist die Tintenausdehnung als Anker mit
**67,9 %** Median über sechs Parameterkombinationen. Die vorab festgelegte
Abbruchgrenze lag bei 70 %. Gate **nicht bestanden**.

**Schluss.** Die Vorab-Festlegung wird eingehalten, statt weiter zu iterieren,
bis eine Zahl gefällt — genau dafür war sie da. Wichtiger als die Zahl ist
aber der Hinweis auf die Ursache: Die drei `1.05000`-Proben, alle aus
derselben Aufnahmeposition, verhalten sich durchgehend gutartig (16 Zellen
belegen 0,94 der Crop-Breite, Autokorrelation trifft den Referenzwert), die
übrigen acht liegen bei 0,73–0,78. Der Sättigungs-Quad erfasst also je nach
Aufnahmesituation unterschiedlich viel physischen Ausschnitt. Damit ist der
nächste sinnvolle Schritt **nicht** ein weiteres Verankerungsverfahren,
sondern eine stabilere Bezugsgrösse für den Ausschnitt — oder eine
Aufnahmeprozedur, die den markierten Bereich reproduzierbar macht.

---

## 2026-09-22 — GSV-Aufbau aus Fotos aufgenommen (keine Hardware angefasst)

**Ziel:** Klären, ob und wo sich am GSV Sensordaten mitlesen lassen, um Proben
des Sammelmodus automatisch statt von Hand zu labeln.

**Aufbau:** Keine Messung, keine Berührung des Geräts. Ausgewertet wurden acht
Fotos unter `var/beispielbilder/gsv_aufbau/` (OnePlus GM1901, 4000×3000,
2026-09-22 11:42–11:44), teils in Vollauflösung ausgeschnitten. Ergänzt durch
zwei Auskünfte des Nutzers am selben Tag.

**Beobachtung:**

* **Gehäuse/Verkabelung.** Alu-Gussgehäuse, Displayfenster in der Front. Zwei
  Verschraubungen links (graues Sensorkabel, dazu rot/schwarz), eine rechts.
  Die Anzeige stand während der Aufnahme auf `-0.00063 mV/V`.
* **Hauptplatine.** Lesbar bestückt mit **ADS1256** (24-bit-ADC, SPI),
  **ADG733** (Analogmux), **REF02C** (Spannungsreferenz), einem 10-MHz-Quarz,
  einem Schaltregler (Speicherdrossel „151") und einem mehrreihigen
  Stiftleistenblock. **Kein Bestückungsdruck mit Teilenummer sichtbar** — der
  Platinenrand liegt oben unter dem Flachband, rechts unter dem
  Stiftleistenblock.
* **Kein RS-232-Treiber erkennbar.** Weder ein SOIC-16 mit der typischen
  Vierergruppe Ladungspumpen-Kondensatoren noch ein eindeutig als Transceiver
  lesbarer Baustein. Das ist ein Negativbefund aus Fotos, **kein Beweis der
  Abwesenheit**: Teile der Platine liegen unter der Klemmenadapterplatine und
  dem Flachband.
* **Klemmleiste.** 15-polige Schraubklemme (1–15) auf einer aufgesteckten
  Adapterplatine, dazu ein Taster (vermutlich Tara/Null) und eine kleine
  Zusatzklemme mit den Aufklebern „B" und „C". **Die Mehrzahl der 15 Schrauben
  ist unbelegt.** Belegt sind ein mehradriges Bündel (gelb/braun/weiss/grün/
  rot/violett) im Bereich 1–6 — der Brückenanschluss — sowie 14/15.
* **Anzeige.** 16-poliges Flachband von der Hauptplatine zur Displayplatine;
  auf dieser steht **DISPLAYTECH 161A**. Das ist der HD44780-übliche
  Parallelbus. Deckt sich mit dem, was CLAUDE.md bereits festhält.
* **Messgrössengeber.** Die extern angeschlossene Lochrasterplatine
  (`gsv_angeschlossene_platine1/2.jpg`, `…_unterseite.jpg`, Rademacher Nr. 915)
  ist **kein Datenausgang, sondern der Stimulus**: ein Widerstandsnetz mit
  vierfachem DIP-Schalter und handschriftlicher Beschriftung „4: 2 mV/V",
  „3: 1 mV/V" — also eine Handvoll diskreter Brückenwerte.

**Auskünfte des Nutzers (2026-09-22):**

1. Es gibt **kein Typenschild**; das Gerät ist kein offizieller Bau.
   → **Später am selben Tag widerrufen**, siehe Nachtragseintrag unten
   („GSV als GSV-2AS identifiziert"). Das Gerät meldet sich beim Hochfahren
   als `GSV-2AS (GSV21 V1.3.07)`. Alle Schlüsse dieses Eintrags, die auf
   „undokumentiertes Gerät" beruhen, sind damit hinfällig.
2. Das schwarze zweiadrige Kabel aus der rechten Verschraubung auf Klemme
   14/15 ist die **Stromversorgung**.
3. Die Stimulus-Platine ist **verklebt**, damit sie nicht verstellt wird, und
   soll vorerst nicht bewegt oder benutzt werden.

**Messergebnis:** Keines — es wurde nicht gemessen. Die Fotoauswertung liefert
Indizien, keine Zahlen.

**Schluss:** Der Weg „Typbezeichnung → Datenblatt → Schnittstellenpin" ist
mangels Typenschild versperrt; ob dieses Exemplar eine digitale Schnittstelle
besitzt, kann nur jemand beantworten, der die verbaute OEM-Platine kennt.
Unabhängig davon ist der **Displaybus** der tragfähigere Abgriff für
OCR-Sollwerte, weil er den Zeichenstring liefert, den die Kette lesen soll,
statt eines intern geführten Messwerts — festgehalten als
[OQ-38](open-questions.md), Skizze in [DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md).
Zweiter, davon unabhängiger Schluss: der verklebte Stimulus begrenzt die
erreichbare **Ziffernabdeckung**, egal wie viele Bilder automatisch gelabelt
werden — [OQ-39](open-questions.md).

---

## 2026-09-22 — Nachtrag: GSV als GSV-2AS identifiziert, serieller Weg dokumentiert

**Ziel:** Den Befund des vorigen Eintrags korrigieren, nachdem der Nutzer eine
Gerätekennung nachgereicht hat.

**Aufbau:** Keine Hardware angefasst. Nutzerauskunft plus öffentlich
abrufbare Herstellerdokumentation.

**Beobachtung:**

* Der Sensor zeigt beim Hochfahren `GSV-2AS (GSV21 V1.3.07)`. Es ist also ein
  reguläres ME-Systeme GSV-2AS; die Annahme „kein offizieller Bau, kein
  Datenblatt" aus dem vorigen Eintrag war falsch.
* Die Bedienungsanleitung „DMS Messverstärker GSV-2 (GSV-2LS, GSV-2AS,
  GSV-2FSD)" liess sich **ohne Hürde herunterladen** (HTTP 200) und liegt
  lokal unter `var/datenblaetter/gsv2-bedienungsanleitung.pdf` (+ `.txt`).
* Aus ihr bestätigt bzw. neu:
  * GSV-2AS = „Aluminiumgehäuse mit RS232, RS422, CANbus, Display".
  * **5-polige Klemme:** `A = GNDC`, `B = Rx`, `C = Tx`, `D = Rx+/CAN_GND`,
    `E = Tx+/CAN_L`. Diese Klemme ist auf den Fotos vorhanden — die kleine
    grüne Zusatzklemme trägt einen Beschriftungsstreifen `A`/`B`/`C`. Die im
    vorigen Eintrag als unklar notierten Aufkleber „B" und „C" sind also die
    RS232-Datenleitungen.
  * **15-polige Klemme:** 14 = UB, 15 = GNDB. Die Nutzerauskunft
    „14/15 = Stromversorgung" ist damit unabhängig bestätigt. Ebenso passt
    2…7 = Brücke zum beobachteten mehradrigen Bündel, und 9/10 = Analogausgang
    zu den dickeren rot/schwarzen Adern.
  * Der GSV „schreibt seine Messwerte **permanent** auf die serielle
    Schnittstelle"; Werkseinstellung 38400 Baud, 8N1.
  * Im umschaltbaren **ASCII-Modus** „entspricht die ausgegebene Zeichenkette
    der Anzeige im Display", Format ab Werk „Vorzeichen, 6 Stellen mit
    Dezimalpunkt, Leerzeichen, Einheit, CR, LF".
  * Das beobachtete `-0.00063 mV/V` passt exakt auf dieses Format, ebenso die
    durchgängig 6 Ziffern der 11 bestätigten Proben ([OQ-37](open-questions.md)).

**Messergebnis:** Keines — weiterhin nichts gemessen. Alles Dokumentenbefund.

**Schluss:** Die Empfehlung des vorigen Eintrags dreht sich. Das Argument
„Displaybus, weil ein interner Wert von der Anzeige abweichen kann" trägt für
dieses Gerät nicht, weil der Hersteller ASCII-Ausgabe und Anzeige ausdrücklich
koppelt. **Primärweg ist RS232 im ASCII-Modus** über die vorhandene Klemme
A/B/C; der Displaybus bleibt Gegenprobe und einziger Weg zu den
Code-zu-Glyph-Paaren. Ungeprüft bleiben: ob der ASCII-Modus an diesem Exemplar
aktiv ist, ob B/C nach draussen verdrahtet sind, und vor allem die **zeitliche**
Kopplung zwischen Stream und Anzeige — die Anleitung sagt nur etwas über den
Inhalt, nicht über den Zeitpunkt. Details: [OQ-38](open-questions.md).

**Warnung, unverändert:** Klemme B/C führt **RS-232-Pegel**. Direkter
Anschluss an Pi-GPIO ist unzulässig ([OQ-09](open-questions.md)) — es braucht
einen USB-RS232-Adapter oder einen Transceiver.

---

## 2026-09-22 — Serieller Abgriff am GSV-2AS angeschlossen und mitgelesen

**Ziel:** Prüfen, ob über die RS232-Klemme A/B/C tatsächlich ein Messwertstrom
am Pi ankommt.

**Aufbau:** Der Nutzer hat den RS232-Steckverbinder des GSV-2AS mit einem
USB-RS232-Adapter verbunden und diesen am Pi angesteckt. Der Adapter meldet
sich als `067b:2303` (Prolific PL2303), Kernel legt `/dev/ttyUSB0` an. Port
per `stty` auf 38400 8N1 raw ohne Handshake gesetzt. Kein `dispread`-Prozess
lief; die Kamera war nicht beteiligt.

**Nur gelesen.** An das Gerät wurde **kein Byte gesendet** — keine
Konfiguration verändert, kein Befehl abgesetzt.

**Beobachtung:**

* Es kommen Daten. 3-s-Mitschnitt: 30 Bytes = 6 Frames. 10-s-Mitschnitt:
  95 Bytes = 19 Frames, also **≈ 1,9 Frames/s**.
* Das dokumentierte 5-Byte-Framing sitzt exakt: Synchronbyte `0x2C` bei
  Offset 0 in **19/19** Frames. Baudrate, Verdrahtung und Adapter stimmen
  damit alle drei.
* **Binärformat, nicht ASCII** — wie ab Werk erwartet.
* Status-Byte durchgehend `0x18` im 10-s-Lauf (Schwellwertschalter SW1 und
  SW2 gesetzt); im 3-s-Lauf zuerst `0x00`, dann `0x18`.
* Rohwerte wandern über `B8A95A` … `EF346B`. **Während des Mitschnitts hat der
  Nutzer die extern an den Sensor angeschlossenen Stimulatoren bewegt** — die
  Streuung ist also die erwünschte Reaktion, kein Rauschen.

**Messergebnis:** Zahlen in [VALIDATION.md](VALIDATION.md), Eintrag
2026-09-22 „GSV-2AS: serieller Abgriff verifiziert". Rohmitschnitte unter
`var/diagnostics/gsv-serial-2026-09-22/`.

**Schluss:** Der in [OQ-38](open-questions.md) empfohlene Weg ist **praktisch
bestätigt**, nicht mehr nur aus der Anleitung abgeleitet: der Abgriff liefert
einen lebenden, dem Sensoreingang folgenden Messwertstrom, ohne Eingriff ins
Gerät. Zwei Dinge fehlen noch:

1. **ASCII-Modus.** Im Binärformat ist der Anzeigewert nicht berechenbar — die
   Anleitung überträgt binär „normiert auf ±1", die Anzeige ergibt sich aus
   „Normierungsfaktor x Messwert", und dieser Faktor ist für dieses Exemplar
   unbekannt. Erst der ASCII-Modus liefert die Zeichenkette, die der Anzeige
   entspricht. Die Umschaltung ist ein **schreibender** Eingriff (`Set Mode`,
   Befehl 38) und bleibt laut Anleitung **auch nach dem Abschalten erhalten** —
   deshalb nicht eigenmächtig ausgeführt.
2. **Zeitliche Kopplung.** Bei ≈ 2 Hz Messwertrate und 15 fps Kamera kommen
   rund sieben Bilder auf einen Messwert. Wie Stream und Anzeige zeitlich
   zueinander stehen, ist ungemessen.

**Nebenbefund mit Folgen für [OQ-39](open-questions.md):** Die Stimulatoren
sind offenbar **doch beweglich** — der Nutzer hat sie während des Mitschnitts
bedient. Damit ist die dort festgehaltene Grenze („fester Wert, keine
zusätzliche Ziffernabdeckung") möglicherweise weitgehend hinfällig. Welcher
Wertebereich so erreichbar ist, ist offen.

---

## 2026-09-22 — GSV-2AS auf ASCII umgeschaltet, Telegramm steht

**Ziel:** Den Messwertstrom von Binär auf das Textformat umstellen, damit der
Sollwert der Anzeige entspricht und als Label taugt.

**Aufbau:** unverändert — GSV-2AS über Klemme A/B/C und USB-RS232-Adapter
(PL2303) an `/dev/ttyUSB0`, 38400 8N1.

**Eingriff, mit Freigabe des Nutzers:** Mode-Register von `0x00` auf `0x02`
gesetzt (Bit 1 = Text-Modus), in der von der Anleitung vorgeschriebenen
Reihenfolge und mit Kontroll-Rücklesen. Sonst wurde nichts verändert. Die
Änderung ist **persistent**; Rückweg ist dasselbe mit gelöschtem Bit 1.

**Beobachtung:**

* **Fallstrick, der fast zu einer Fehlkonfiguration geführt hätte:** `get mode`
  antwortet mit **zwei** Bytes, `3B 00`. Das `0x3B` ist das Semikolon-Präfix
  für Registerwerte; die Anleitung zählt in der Spalte „Länge der
  Befehlsantwort" nur das Datenbyte. Der erste Versuch las nur ein Byte, hielt
  `0x3B` für den Modus und schloss daraus „Text-Modus ist bereits aktiv" —
  falsch, aber folgenlos, weil das Skript genau deshalb ohne Schreibzugriff
  abbrach. Der tatsächliche Modus war `0x00`, passend zum beobachteten
  Binärstrom.
* Nach der Umschaltung kommt sofort Text. Rohbytes einer Zeile:
  `2b 30 2e 34 36 37 37 36 20 6d 56 2f 56 0d 0a` = `+0.46776 mV/V<CR><LF>`.
* 10-s-Mitschnitt: 18 vollständige Zeilen, **18/18** passen auf
  `^[+-]\d\.\d{5} mV/V$`, alle 13 Zeichen lang. 1,8 Zeilen/s — dieselbe Rate
  wie vorher im Binärmodus.
* Einmal war der Strom nach dem Umschalten still: `start transmission` war
  offenbar nicht durchgekommen, weil die Portsitzung unmittelbar danach
  geschlossen wurde. Ein erneutes `0x24` in derselben Sitzung hat ihn sofort
  wieder gestartet. **Merke:** `start transmission` in derselben offenen
  Sitzung absetzen und die Wirkung dort prüfen.

**Messergebnis:** [VALIDATION.md](VALIDATION.md), Eintrag 2026-09-22 „GSV-2AS
auf ASCII-Modus umgeschaltet". Rohmitschnitt
`var/diagnostics/gsv-serial-2026-09-22/capture_ascii_10s.bin`.

**Schluss:** Der Sollwertkanal steht. Das Telegramm ist gemessen statt
angenommen, und sein Format deckt sich mit den 11 bestätigten Datensatzproben.
Damit ist der Hauptteil von [OQ-38](open-questions.md) erledigt; offen bleibt
die **zeitliche** Zuordnung zwischen Telegramm und Anzeige.

**Zweiter Schluss, der eine Datensatzfrage klärt:** Der Vollausschlag dieses
Exemplars ist 1,05 mV/V — der früher gemessene Binärwert `B8C62C` ergibt
bipolar mit diesem Endwert `+0.46573`, und der ASCII-Strom zeigt bei
praktisch gleicher Stimuluslage `+0.46776`. `FFFFFF` (laut Anleitung 105 % des
Messbereichs) entspricht damit rechnerisch exakt `+1.05000`. Die drei
identischen `1.05000`-Proben im Datensatz sind also sehr wahrscheinlich
**Übersteuerung**, nicht Messwerte — siehe [OQ-39](open-questions.md).

**Ungeprüft geblieben:** ob die Anzeige in diesem Moment wirklich `+0.46776`
zeigt. Niemand hat währenddessen aufs Display gesehen; das ist der letzte
fehlende Beleg für „ASCII-String = Anzeige".

---

## 2026-09-22 — Plateau-Statistik des ASCII-Stroms und Vorbereitung des Auto-Labelings

**Ziel:** Vor dem Bau eines Synchronaufzeichners klären, ob der serielle
Strom überhaupt lange genug still steht, um Bilder daraus labeln zu können.
Die Regel dafür ist ein Schutzintervall um jeden Wertwechsel; sie trägt nur,
wenn es zwischen den Wechseln ruhige Strecken gibt.

**Aufbau:** unverändert — GSV-2AS über Klemme A/B/C, USB-RS232-Adapter
(PL2303) an `/dev/ttyUSB0`, 38400 8N1. **Rein passiv, es wurde kein Byte
gesendet.** Kamera nicht beteiligt, kein `dispread`-Prozess lief. Jede Zeile
mit Ankunftszeit in CLOCK_BOOTTIME, also derselben Domäne wie der
`SensorTimestamp` der Kamera — das ist die Voraussetzung dafür, beide Ströme
später überhaupt zusammenbringen zu können.

**Messergebnis:** [VALIDATION.md](VALIDATION.md), Eintrag „Plateau-Statistik
des ASCII-Stroms". Rohmitschnitt und Auswertskript unter
`var/diagnostics/gsv-serial-2026-09-22/`.

**Schluss:** Die Sperre ist gelöst. 1125 Telegramme über 599 s, keine einzige
Formatabweichung, Plateaus der exakten Zeichenkette bis 30 s. Selbst bei einem
sehr grosszügigen Schutzintervall von 1 s bleibt rund die Hälfte der
Wanduhrzeit nutzbar.

**Der Schluss, der beim Hinsehen wichtiger wurde.** Die Zahl zählt *Bilder*,
nicht *Information*. Im Ruhezustand trägt der Strom praktisch **eine**
Zeichenkette — `+0.46776 mV/V` in 379 von 660 Telegrammen der ersten sechs
Minuten, die nächsthäufigen unterscheiden sich in einem Zeichen der fünften
Nachkommastelle. Eine zehnminütige Ruheaufzeichnung liefert also rund 4700
Bilder derselben Anzeige, und das ist nach der Split-Regel des Plans
(`independence_group` je Sitzung) **eine** unabhängige Beobachtung. Damit wäre
nichts gewonnen: es ist dieselbe Grenze, an der die Verankerungsarbeit schon
bei 11 Proben stehengeblieben ist.

Die erste Kameraaufzeichnung darf deshalb **kein passiver Dauerlauf** sein,
sondern muss eine Sitzung mit bewusst gefahrenem Stimulus werden — langsam
über den erreichbaren Bereich, mit einigen grossen Sprüngen und Ruhepausen
dazwischen. Dieselbe Sitzung beantwortet dann drei Dinge auf einmal: den
Versatz zwischen Telegramm und Anzeige (aus den Sprüngen), die erreichbare
Ziffernabdeckung ([OQ-39](open-questions.md), aus dem Durchlauf) und die
reale Ausbeute (aus den Pausen).

**Nebenbefund:** In den Sekunden 20–35 wandert der Wert bis `+1.05000` — eine
mechanische Störung am Aufbau, nicht bedient. Das sind die **ersten
beobachteten** Anschläge an den Vollausschlag; bisher war die
Übersteuerungsvermutung zu den drei gleichlautenden Datensatzproben nur
rechnerisch hergeleitet.

**Was dabei gebaut wurde:** das Herkunftsmerkmal `label_origin` im
`DatasetStore` (OQ-38 Punkt 6), das Migrationsskript für die 88
Bestandsproben und der Synchronaufzeichner. Einzelheiten im
[CHANGELOG](../CHANGELOG.md) und im
[Plan](superpowers/plans/2026-09-22-auto-labeling-seriell.md).

**Zwei Dinge sind ausdrücklich NICHT ausgeführt worden.** Die Migration
schreibt in `var/` und gehört dem Nutzer; solange sie nicht gelaufen ist,
**lehnt der Sammelmodus die 88 Bestandsproben ab**. Und der Kamerazweig des
Aufzeichners ist nie gelaufen — sein erster realer Einsatz ist selbst ein
Prüfschritt und gehört kurz gehalten, bevor eine lange Sitzung entsteht.

---

## 2026-09-22 — Der Stimulus ist die falsche Stellschraube; die Anzeige ist direkt steuerbar

**Ausgangspunkt:** Der Nutzer hat gemeldet, dass er den Stimulus dauerhaft
bewegen muss, damit die Werte fluktuieren, und gefragt, ob sich Werte nicht
über GPIO einspeisen liessen, um über längere Zeit ohne Handbetrieb zu
sammeln.

**Erste Messung — warum der bewegte Stimulus nicht trägt.** 1199 s passiver
Mitschnitt bei bewegtem Stimulus. Im Rohstrom stehen 217 verschiedene
Zeichenketten; das sieht nach reichlich Vielfalt aus. Nach dem
Schutzintervall bleibt davon fast nichts: bei M = 500 ms noch 25
Zeichenketten, und 96,3 % der nutzbaren Zeit entfallen auf vier praktisch
gleiche Werte.

Der Mechanismus ist strukturell, nicht statistisch: die Vielfalt steckt in
Ausschlägen von ein bis zwei Telegrammen Länge, und das Fenster verwirft
jedes Plateau kürzer als 2·M. Zwischen M = 200 ms und M = 300 ms bricht die
Vielfalt schlagartig ein — dort unterschreitet der Telegrammabstand von
553 ms die Schwelle. **Das Gate kostet 44 % der Bilder, aber 88 % der
Information.** Länger aufzeichnen ändert daran nichts.

**Zur GPIO-Frage.** Technisch ginge es, aber es wäre der aufwendige Weg: ein
Bridge-Signal von 1 mV/V bei 5 V Speisung sind 5 mV, ein 12-bit-DAC über
3,3 V hat 0,8 mV Schritte — gröber als der gesamte interessante Bereich. Dazu
ist mV/V ratiometrisch, das eingespeiste Signal müsste der Speisespannung
folgen, und es ginge in den Messeingang des Laborverstärkers. Für den Zweck —
Glyphen auf dem Glas erzeugen — gibt es einen direkteren Weg.

**Zweite Messung — der direkte Weg.** Die Anleitung: „Die Displayanzeige
ergibt sich aus Normierungsfaktor × Messwert", `set norm` (16), dazu
`set dpoint` (17). Vor jedem Eingriff wurde der komplette Registerstand
ausgelesen und als Rückstellpunkt gesichert
(`scripts/gsv-registers.py`, neu).

Drei Dinge, die dabei von „abgeleitet" auf „gemessen" gewechselt sind:

1. **Die Umrechnungsvorschrift stimmt.** Der ausgelesene Normierungs-Rohwert
   ist exakt 5250020 — genau die Konstante aus der Rechenvorschrift der
   Anleitung, passend zu Faktor 1,0. Die Rückrechnung war damit gegen das
   Gerät bestätigt, bevor irgendetwas geschrieben wurde.
2. **`EEnow = 0`.** Das Special-Mode-Register sagt: Schreibbefehle landen
   „erst nach dem Ausschalten" im EEPROM. Die Abnutzungssorge bei hunderten
   Normierungswechseln ist damit gegenstandslos — gemessen, nicht gehofft.
3. **Der ASCII-Strom folgt der Normierung.** Das war die eine ungeprüfte
   Verkettung zweier Anleitungssätze. Wechsel auf Faktor 2,0: Median vorher
   `0.60661`, nachher `1.21095`, Verhältnis **1,9963**.

**Der Befund, der eine offene Frage schliesst.** Durchlauf über 14
Normierungsfaktoren von 1,0 bis 9000, Anzeigen von `+0.59696` bis
`+05372.5`. In **14 von 14** Fällen: genau 6 Ziffern, genau 8 Zellen für den
Zahlenblock. Der Dezimalpunkt wandert, führende Nullen bleiben stehen, das
Format wechselt nicht. Damit ist [OQ-37](open-questions.md) beantwortet, und
zwar ohne jeden Stimulus — die Voraussetzung des Block-Ankers hält über den
ganzen Bereich.

**Messergebnis:** [VALIDATION.md](VALIDATION.md), zwei Einträge vom
2026-09-22 („Schutzintervall verwirft bevorzugt die Vielfalt" und „Anzeige
über den Normierungsfaktor steuerbar"). Rohdaten und Skripte unter
`var/diagnostics/gsv-serial-2026-09-22/`.

**Schluss.** Die Ziffernabdeckung ist nicht mehr an den Stimulus gebunden,
sondern planbar: für jede gewünschte Anzeige lässt sich der Normierungsfaktor
ausrechnen, und der Wert steht dann beliebig lange still. Damit lösen sich
Vielfalt und Plateaulänge, die sich bisher widersprochen haben, gleichzeitig.
Der Nutzer muss den Stimulus nicht mehr bewegen.

**Was ausdrücklich offen bleibt:**

* **Negative Werte.** Negative Normierung gibt es laut Anleitung erst ab
  Firmware 1.5.06; dieses Gerät meldet 1.3.07. Die Stimulatoren erzeugen
  ebenfalls keine negativen Werte. Die **Vorzeichenstelle bleibt unbelegt**,
  und das gehört an jede Benchmarkzahl geschrieben.
* **Die Kamera.** Sie wird nicht erkannt — kein Knoten im Device-Tree, keine
  dmesg-Einträge. Ohne sie ist der zeitliche Versatz zwischen Telegramm und
  Anzeige nicht messbar, und ohne den gibt es kein M. Der Nutzer prüft das
  Kabel.
* **Ob eine über die Normierung erzeugte Ziffernfolge dieselbe Bildstatistik
  hat wie eine real gemessene.** Für den Leser zählt, was auf dem Glas steht,
  und das entsteht auf demselben Weg — ein Unterschied ist nicht ersichtlich,
  aber auch nicht gemessen.

**Nicht angefasst:** `set zero` (Nullpunktabgleich) — das wäre ein Eingriff
in die Messkette des Laborgeräts und der einzige Weg zu negativen Werten,
aber keiner, den man nebenbei geht.

---

## 2026-09-22 — Kamera nach Reboot da, sofort wieder blockiert (OQ-22)

**Ausgangspunkt:** Der Nutzer hat den Pi neu gestartet, damit die AI Camera
erkannt wird. Sie wurde erkannt: `rpicam-hello --list-cameras` meldet den
IMX500 mit beiden Modi.

**Was ich getan habe — und was daran falsch war.** Ich habe den Kamerazweig
von `scripts/sync-record.py` das erste Mal gegen echte Hardware gestartet. Das
Skript hatte als Vorgabe **2028×1520**. Ich habe diese Vorgabe nicht gegen
[OQ-22](open-questions.md) geprüft, obwohl dort seit dem 2026-09-08 steht:
„Der Messbetrieb bleibt bei 960×720", und die Tabelle sechs Datenpunkte führt,
in denen **jede** Sitzung mit einem grossen Sensormodus die letzte des Boots
war.

**Verlauf:** Kein einziges Bild; der Prozess hing in `capture_request`. Ich
habe ihn per Signal beendet — auch das beschreibt OQ-22 bereits als Auslöser
des Pufferfehlers. Ab da setzte der Sensor keinen Stream mehr auf.
`rpicam-hello -t 3000` erzeugte **33 × `stream on failed in subdev` in
0,11 s**, mit `cfe_stop_streaming+0xd4/0x200 [rp1_cfe]` im Aufrufpfad.

**Eine Fehldeutung, die ich unterwegs hatte und korrigieren musste.** Aus
„alle Kernel-Fehler liegen im Zeitfenster meines *letzten* Tests" hatte ich
geschlossen, meine früheren Versuche hätten nichts kaputtgemacht. Das war
falsch gefolgert: die picamera2-Versuche laufen still in den Timeout und
schreiben gar nichts ins Kernel-Log, erst `rpicam-hello` meldet sich laut.
Und der allererste Streamversuch nach dem Boot **war** mein 2028×1520-Lauf —
es gab keine erfolgreiche Sitzung davor, mit der sich vergleichen liesse. Der
Nutzer hatte den Verdacht zuerst geäussert und lag richtig.

**Zweiter Befund, unabhängig davon:** Das Skript nutzte
`create_still_configuration`. Der erprobte Pfad im Repo ist
`create_video_configuration` mit `format="RGB888"`, gesetzter `FrameRate` und
`queue=False` — so nimmt der Workbench-Kamerathread auf, und so sind die 88
Bestandsproben entstanden. `queue=False` ist für eine Versatzmessung nicht
optional: ein gepuffertes altes Bild würde den gesuchten Zeitversatz
verfälschen. Beides ist korrigiert.

**Ausserdem gelernt:** `capture_request(wait=2.0)` ist ein **Timeout in
Sekunden**, kein Flag — der Aufruf endet mit `TimeoutError` aus
`job.get_result(timeout=...)`. Bei einem blockierten Sensor sieht das aus wie
ein Konfigurationsfehler, ist aber der Sensorzustand.

**Konsequenz, umgesetzt:** `sync-record.py` hat jetzt die Vorgabe 960×720 und
**weist grosse Sensormodi hart ab** statt zu warnen, aufhebbar nur über
`--allow-large-sensor-mode`. Eine Warnzeile auf stderr wäre zu wenig: die
Folge ist ein Reboot des Labor-Pi.

**Offen:** Die Kamera braucht erneut einen Reboot. `camera-commissioning.sh`
prüft weiterhin nur die Enumeration, nicht den Bilddurchlauf — genau deshalb
meldet es „einsatzbereit", während der Sensor blockiert ist. Das steht als
Punkt (d) in OQ-22 und ist weiterhin offen.

## 2026-09-23 — Kamera läuft, Normierung aus der Aufzeichnung heraus, das Glas zeigt keine führende Null

**Ausgangspunkt:** Pi-Uptime 17 h 39 min, der letzte Boot war also am
2026-09-22 gegen 16:15. Im Kernel-Log dieses Boots steht kein `stream on
failed`. Die Enumeration ist normal. Den vorgeschriebenen Smoke-Test habe ich
zuerst mit 5 fps gefahren, dann mit 15 fps. Beide liefen sauber. Damit ist der
Kamerazweig von `sync-record.py` zum ersten Mal erfolgreich gegen Hardware
gelaufen. Die Kamera zeigt auf das GSV-2AS, `+0.60397 mV/V` ist gut lesbar.

**Aufzeichnungen:**
* `offset-stim-100209`: Der Nutzer hat den Stimulator von Hand bewegt. Das
  ergab eher eine Rampe als einzelne Sprünge, der Wert ändert sich in fast
  jedem Telegramm. Laut Nutzer hat er die Kamera dabei eventuell kurz
  verdeckt. In der Auswertung war das weder in der Gesamthelligkeit noch in
  der des Anzeigebereichs zu finden.
* `normtest-101403`, `offset-norm-101440`, `leadzero-102347`: Normierungs-
  sprünge über `--norm-schedule`, geschrieben aus der offenen Portsitzung von
  `sync-record.py`, Stimulus unberührt. Nach jedem Lauf wurde auf norm = 1,0
  und dpoint = 1 zurückgestellt und das per Rücklesen bestätigt.

**Deutung 1 — die Plan-Abweichung.** Die grossen Sprünge für Task B kommen
aus der Normierung und nicht vom Bediener. Das habe ich vor der Messung im
Plan festgeschrieben, mit dem Stimulator als dritter Population. Der
Schreibzyklus hält den Strom ≈ 1,8 s an. Das erste Telegramm nach einem
Normierungssprung kommt deshalb zu einem Zeitpunkt, den der Wiederanlauf
bestimmt und nicht der Takt des Geräts. Die Normierungspopulation misst also
**Befehl → Glas**, nicht **Telegramm → Glas**. Für M zählt sie nicht.

**Deutung 2 — die führende Null.** Dass die Zeichenkette der Anzeige
entspricht, war bisher nur Herstelleraussage. In der Bildfolge der
Normierungssprünge fiel sofort auf: Das Glas zeigt `+ 1.8290`, das Telegramm
`+01.8290`. Das gilt über alle 15 Faktoren. Die Aussage vom Vortag „führende
Nullen bleiben stehen" stammte aus dem ASCII-Strom. Ich habe sie korrigiert,
nicht gelöscht. Die Folge ist neu erfasst als [OQ-41](open-questions.md): Ohne
eine festgeschriebene Abbildung trüge jedes serielle Label ≥ 1 ein falsches
Zeichen.

**Deutung 3 — der Stillstand.** Einmal standen beide Kanäle ≈ 2,5 s
gleichzeitig still. Danach kamen fünf Telegramme mit gleichem Zeitstempel.
Die Ursache ist nicht geklärt. Es kommen SD-Schreibstau oder ein
blockierender Hauptprozess in Frage. Das `frame_sequence` des Skripts zählt
geschriebene Bilder, nicht Sensorbilder, und hat den Stillstand deshalb
nicht gezeigt. Die Folge für den Labeler steht in OQ-40.

**Irrweg bei der Auswertung.** Der erste Auswerteansatz lieferte für alle
Populationen „nicht über der Null-Basislinie", auch für die Normierungs-
sprünge, bei denen sich alle sechs Ziffern ändern. Der Ansatz war die
Bild-zu-Bild-Differenz über einen grossen Ausschnitt. Das ist ein Fehler des
Verfahrens, kein Befund: Das LCD schaltet träge, die Änderung verteilt sich
über mehrere Bilder, und die geänderten Pixel machen nur einen kleinen Teil
des Ausschnitts aus. Die grösste mittlere Differenz der ganzen Aufzeichnung
lag bei 4,9 Graustufen, der Median bei 0,66. Die Bildfolge zeigt den Wechsel
dagegen eindeutig. Neuer Ansatz: Projektion auf die Differenz zweier
Plateau-Vorlagen.

## 2026-09-23 — Der Stillstand kommt vom Zurückschreiben auf die SD-Karte

Ich hatte vermutet, dass `dirty_expire` von 30 s dahintersteckt, weil der
erste Stillstand ≈ 34 s nach dem Start auftrat. Die gemessene Korrelation
fällt deutlicher aus: Jede Bildlücke liegt in einer Rückschreibphase, und ein
danebenlaufender Prozess ohne Dateizugriffe hatte nie einen Aussetzer. Beide
Kanäle standen still, weil **beide** Threads schrieben: der Hauptthread die
JPEGs, der Lesethread `serial.jsonl`. `cv2.imwrite` gibt den GIL weitgehend
frei (≈ 85 % Spinner-Rate). Der GIL war also nicht die Ursache, es war die
blockierte Dateiarbeit selbst.

Ein Lauf ohne nennenswertes Rückschreiben beweist die Abhilfe nicht. Die
Last habe ich deshalb mit `dd … conv=fsync` erzwungen. Erst dieser Lauf
zeigt, dass der Fix trägt: Der serielle Strom bleibt exakt, verlorene Bilder
sind gezählt. Die Systemeinstellungen (`vm.dirty_*`) habe ich bewusst nicht
angefasst. Das wäre ein Eingriff ins System des Labor-Pi gewesen, und der
Fix im Skript macht ihn unnötig.

## 2026-09-23 — Winkelversuch unterbrochen: Kamera wieder blockiert

Ernte Phase 1, Task 6.

**Frontal**, `ScalerCrop` `1972,731,1195,896`:
* 7,3 px je Punktspalte im Ausgabebild, Schärfe (Laplace-Varianz) 9,0.
* Das Raster `4,24.4,40,115` sitzt. Die Zeichen stehen linksbündig ab
  Zelle 0.
* Die Zeichen wirken trotz 7 px weich. Das deutet auf Unschärfe hin, nicht
  auf fehlende Auflösung.
* Nachtrag: Die 7,3 px sind hochgerechnet. Der Sensormodus ist 2×2-gebinnt,
  echt sind es × (1195/2)/960 ≈ 0,62, also ≈ 4,5 px. Das Gate wird darauf
  umgestellt.

**30°:** Der Nutzer hat die Kamera neu aufgestellt und **gleichzeitig** den
Fokusring 1/4 im Uhrzeigersinn gedreht. Ergebnis:
* Schärfe 3,5, damit deutlich schlechter.
* Das Glas ist im Vollbild nur noch ≈ 140 px breit, weil die Kamera weiter
  weg steht.

Den Beitrag von Winkel und Fokus kann ich nicht trennen. Der Faktor 2,5
spricht dafür, dass im Uhrzeigersinn die falsche Richtung war.

**Blockade:** Danach hat der Nutzer 1/4 zurückgedreht. Die nächste Aufnahme
lieferte 0 Bilder, dazu `stream on failed` (OQ-22). Einzige Einwirkung
dazwischen war das Drehen am Fokusring. Weitere Streamversuche habe ich nicht
gemacht, der Reboot ist beim Nutzer angefragt.

**Lehre für den Aufbau:** Fokus und Aufstellung nie gleichzeitig ändern.
Beim Drehen am Fokusring die Kamera und das Kabel festhalten.

**Korrektur, gleicher Tag:** Der Nutzer hat an die Grenze von 20–25
Power-Zyklen aus OQ-22 erinnert. Im Kernel-Log stehen 20 erfolgreiche
Streamstarts in diesem Boot, der 21. ist gescheitert. Das ist die
wahrscheinlichere Erklärung, der Fokusring ist es kaum. Meine Werkzeuge haben
das Budget verschwendet: Der Winkelversuch kostete 3–4 Starts je Winkel,
jede Schärfemessung einen weiteren.

## 2026-09-23 — Fokusübergabe: zweiter Kameralauf des Boots blockiert

**Ziel:** Den Fokus in der 30°-Stellung in einer einzigen 90-s-Kamerasitzung
einstellen. Vorher sollte `camera-commissioning.sh` einmal den echten
Bilddurchlauf bestätigen. Der Nutzer sollte erst nach dem Signal
`READY_TO_TURN` drehen.

**Ablauf:** Der Pi war seit 14:24:31 neu gebootet. Um 15:55 bestand die
Commissioning-Aufnahme bei 640×480 (86 606 Byte, kein `stream on failed`).
Der anschliessende Fokuslauf öffnete 960×720, 15 fps, `queue=False`. Noch vor
dem ersten Bild meldete der Kernel um 15:57:10
`imx500_power_on: failed to get led gpio` und sechsmal
`stream on failed in subdev`; libcamera konnte keinen der sechs CFE-Puffer
einreihen. `READY_TO_TURN` wurde nie ausgegeben. Der Nutzer hat weder Fokus
noch Kameraposition verändert.

**Abbruch:** Der Python-Prozess hing in `futex_wait_queue`. Ein einmaliges
Ctrl+C als weicher Abbruch erreichte das Terminal, führte aber innerhalb von
10 s nicht durch den Aufräumpfad. Kein SIGKILL und kein weiterer
Streamversuch; der Prozess bleibt bis zum Reboot belegt.

**Deutung:** Die bisherige Sicherheitsannahme „frischer Boot + Budget 15"
reicht nicht aus. In diesem Boot scheiterte bereits die Kamerasitzung direkt
nach einer erfolgreichen Commissioning-Sitzung. Ob `rpicam-still` intern zwei
Power-Zyklen verursachte (zwei `Using a link rate`-Zeilen) oder der RP2040
nicht zuverlässig durch den Warmstart zurückgesetzt wurde, ist offen. Die
Fokusmessung selbst hat **keinen Messwert** geliefert.

**Artefakte:**
`var/diagnostics/focus-handoff-2026-09-23/commissioning.txt` und
`focus-failure.txt` (nicht versioniert).

## 2026-09-23 — Auch der erste Start nach Warmreboot scheitert (OQ-22)

Der Nutzer hat erneut rebootet. Boot-ID
`6c6abda2-d316-40da-b557-1124431ade30` und Bootzeit 16:13:22
(Europe/Berlin) bestätigen den neuen Boot. Davor gab es darin keinen
Kamerastart. Um 16:17:35 öffnete der Fokushelfer 960×720, 15 fps,
`queue=False`. Bereits beim ersten Start war die RP2040-GPIO-Bridge über
I²C nicht bereit: `rp2040_gbdg_wait_until_free failed`, darauf
`rp2040_gbdg_gpio_dir_out(19, 0) could not ST_CL`, LED-GPIO `-121` und
sechsmal `stream on failed in subdev`. libcamera meldete beim ersten
CFE-Puffer `Remote I/O error`. Es kam kein Bild und kein Signal zum Drehen;
die Kamera wurde vom Nutzer nicht angefasst.

Der Python-Prozess blieb in `futex_wait_queue`. Ein weiterer Streamversuch
wurde nicht gemacht. Das bisherige 20–25-Starts-Budget erklärt diesen
Fehlschlag nicht. Warum die Bridge nach dem Warmreboot beim ersten Start
nicht antwortet, bleibt offen. Ein vollständiger Stromzyklus des Pi wäre
eine trennende Gegenprobe; er unterbricht auch andere Dienste auf diesem
Pi und wurde hier nicht durchgeführt.

**Artefakt:** `var/diagnostics/focus-handoff-2026-09-23/focus-first-start-failure.txt`
(nicht versioniert). Der Fokushelfer liegt unter
`/home/me-systeme/fokus-live-2026-09-23.py`.

## 2026-09-24 — Kamera wieder da, Task 6 in einer Vormittagssitzung

Nach der nächtlichen Abschaltung meldeten sich IMX500 und RP2040-Brücke
beim Boot sauber, und der erste Kamerastart lieferte sofort Bilder. Damit
bleibt offen, ob der Warmreboot-Fehlschlag von gestern nur durch einen
Kaltstart behebbar ist; ein Gegenbeweis ist ein einzelner guter Kaltstart
nicht.

Ablauf: eine 20-min-Sitzung im vollen Bildfeld zum groben Fokussieren
(Schärfemesser `var/diagnostics/task6-tools/focus_meter.py`, liest nur die
geschriebenen JPEGs), dann 15 min mit ScalerCrop 1920×1440 für den Feinfokus.
Im vollen Bildfeld ist die Anzeige nur ≈ 175 px breit, die Punkte laufen
zusammen; erst der Ausschnitt macht sie sichtbar. Der Fokuswert wurde beim
Drehen mehrfach durch Verschieben der Kamera verfälscht — beim nächsten Mal
Kamera fixieren, bevor fokussiert wird.

Die Kamera stand von Anfang an auf der „30°"-Stellung; die zuerst als
frontal bezeichneten Bilder sind umbenannt (`task6-30deg*`). Frontal und
„45°" kamen je als 10-s-Vollbild (Anzeige suchen) plus 30-s-Ausschnitt dazu.

Irrweg: Das Gitter-Overlay `overlay_rectified.png` las ich bei 400 px Breite
als gespiegelt. Ein Subagent fand keinen Fehler in der Eckenreihenfolge;
ohne Gitter vergrössert liest der Text richtig. Geblieben ist ein
Regressionstest mit asymmetrischem Muster.

Befund für die Ernte: Eine Lichtspiegelung links oben auf dem Glas
schneidet bei frontal und „45°" die automatische Glaserkennung ab und
überstrahlt bei „45°" `+` und `0`. Vor der Ernte Licht oder Winkel ändern
oder das Quad von Hand setzen.

Schwelle `resolution_threshold_px = 2,6`, vom Nutzer festgelegt. Zahlen in
VALIDATION.md (2026-09-24).

## 2026-09-24 — Ernte 1 läuft durch, 81 Proben importiert

Der Nutzer hat nach der Blockade um 11:11 neu gestartet und die
Lichtspiegelung beseitigt. Mit zwei Streamstarts ging es: 20 s Ausschnitt
zum Einrichten, dann die Ernte selbst. Die Kamera war zwischen dem Vollbild
vor der Blockade und dem Neustart leicht verrutscht; die Anzeige lag danach
am oberen Bildrand, aber vollständig im Ausschnitt und grösser als vorher
(3,46 native px je Punktspalte, Punkte klar getrennt). Ohne Spiegelung fand
der Glas-Detektor das Quad allein.

Kurzer Fehlalarm: In der Stichprobe zeigt das Glas `+ 28.681` mit Leerzelle,
das Label heisst `+28.681 mV/V`. `import-harvest.py` legt die Zellen aber
nach dem Rohtelegramm mit Leerzelle an (`cell_text`), die Zuordnung stimmt.
Zahlen: VALIDATION.md, 2026-09-24, „Ernte 1".

Nachmittags: Ernte 2 in derselben Aufstellung (1 Start), dann Aufstellung 2
schräg von links und näher (3 Starts), danach Neustart vorsorglich vor dem
8. Start. Für Aufstellung 3 wird der Seed so gewählt, dass der Faktorplan
Werte mit führender 6 enthält (Seed 20261160, 7 von 30) — nur Stimulus-
auswahl, keine Auswertungsentscheidung. Zahlen: VALIDATION.md, „Ernte 2
und Aufstellung 2".

## 2026-09-24 — Erster Dot-Matrix-Trainingslauf und Übergabe

**Aufbau:** Offline-Auswertung der 301 bereits importierten GSV-2AS-Bilder
(152 `ernte1`, 76 `auf2`, 73 `auf3`). Es gab in dieser Korrektursitzung
keinen zusätzlichen Hardwareeingriff. Profilzuordnung:
`var/diagnostics/dotmatrix-profile-map.json`; geplanter Bericht:
`var/diagnostics/dotmatrix-stufe1/report.json`. Zeitangaben werden aus
dieser Offline-Auswertung nicht abgeleitet.

**Ablauf:** `dotmatrix-eval.py loo` stoppte im ersten Fold durch die
vorab festgelegte ROM-Gegenprobe (Exit 3, acht abweichende Zeichen,
kein Bericht). Ein separater Vergleich zeigte: `ernte1` passt zum ROM;
`auf3` weicht systematisch ab. Am Bild gemessen lag die Kamera beim
`auf3`-Erntelauf gegenüber dem Profil um ungefähr `dx=0,3`, `dy=4,6`
Quellpixel versetzt. Das ist größer als die ±1-Pixel-Suche im
entzerrten Bild. Die Kamera war beim Fokussieren bewegt worden; das
zunächst bestätigte Raster darf für diese Bilder nicht mehr gelten.
Ohne `auf3` scheitert der Fold mit nur `auf2` als Trainingsgruppe noch
bei vier Zeichen um je einen Punkt. `auf2` war bewusst weich geerntet;
ob allein die Unschärfe diese Abweichungen erklärt, bleibt offen
([OQ-42](open-questions.md#oq-42)).

**Deutung:** Die Gegenprobe hat eine Auswertung mit unpassendem Raster
verhindert. Weder ROM-Tabelle noch Schwellen wurden angepasst. Für echte
Daten gibt es noch keine Fehler- oder Ablehnungsrate; die synthetische
Störprobe aus der Abschlussprüfung ist nur eine Entwicklungsdiagnose
(Zahlen in [VALIDATION.md](VALIDATION.md)). Vor einer Wiederholung muss
`auf3` ein belegtes Raster erhalten; über eine mögliche ROM-Toleranz bei
weichen Bildern ist anhand der Glasbilder zu entscheiden.

**Artefakte:** Task-7-Bericht und `final-fix-brief.md` unter
`.superpowers/sdd/2026-09-24-dotmatrix-reader/` (lokal ignoriert),
Chat-Exporte `codex_main.txt`/`codex_subagent.txt` im Haupt-Checkout.
Der letzte Claude-Subagent endete wegen API-Limit während einer
uncommitteten Korrekturrunde. Diese Änderungen sind keine abgeschlossene
Messung und kein freigegebener Codezustand.

## 2026-09-25 — Dot-Matrix-Leser fertig gebaut, Entwicklungsmessung hängt an Schärfe

Nach dem Sessionlimit übernommen: Korrekturwelle der Abschlussprüfung
abgeschlossen (u. a. `NaN`-Schwellen in `templates.json` hätten jede Zelle
durchgelassen), geseedeter Sicherheitstest mit 300 gestörten Werten: 0
falsch. Nutzerentscheidung zu OQ-42: `auf3` auf einem Erntebild neu
bestätigt, Gegenprobe mit 1 Punkt Toleranz (`rom_check_v2`). Bei der
Umsetzung zeigte sich, dass meine Spec-Angabe „erkennt ≥ 40 % falsche Labels"
nicht stimmte — die Gegenprobe vergleicht Mittelwerte und schlägt erst bei
einer Mehrheit an (≈ 60 %); korrigiert.

Die vorab festgelegte Messung bricht trotzdem ab: die zwei weichen
Aufstellungen zusammen lassen die Diagonale der `4` zulaufen (3 Punkte). Die
Diagnose über alle Kombinationen zeigt nie einen falschen Wert; eine
Kombination erfüllt das Ziel schon (`ernte1`+`auf2` → `auf3`: 67 richtig, 6
abgelehnt), die anderen lehnen alles ab. Schluss: Das Training braucht mehr
Aufstellungen mit ähnlicher, guter Schärfe; weiche Aufstellungen eignen sich
als Testmaterial für Ablehnung, nicht als alleinige Vorlagenquelle. Zahlen:
VALIDATION.md, 2026-09-25.

## 2026-09-29 — Bildverluste behoben, Spiegelkante im Leser behoben

**Bildverluste:** Ein Subagent hat die steigenden Verluste (bis 34 % in
`sc6`) untersucht. Die SD-Karte, ein No-Name-Modell `SD16G` mit gemeldeten
50 GiB, blieb bei der Aufnahme sekundenlang stehen. Selbst kleine
Protokollzeilen hingen bis 23 s. Die Kodierung war nie der Engpass.
Nebenbei fanden sich 31 liegengebliebene Kopien eines Codex-Plugins
(5,5 GB) in `~/.codex/.tmp`. Sie sind gelöscht, ebenso Caches, danach lief
`fstrim`. Jetzt sind 14 GB frei.

Die Aufnahme läuft jetzt zuerst in `/dev/shm` und wird danach kopiert
(`--staging-root`). Die Probeernte `sc6b` an unveränderter Kamera hatte
keinen Verlust und keine langen Telegrammlücken mehr. Sie brachte 67 % mehr
beschriftete Bilder. Das Kopieren von 1,5 GB dauerte 77 s. Offen bleibt,
ob die Karte ihre Kapazität tatsächlich hat, und eine Sicherung von `var/`
auf ein anderes Medium.

**Spiegelkante:** Die Analyse von `ab2` Zelle 8 zeigte einen weichen
dunklen Keil von oben rechts (76 statt 98 Grauwerte), den auch die
Spaltenlücken zeigen. Eine Schätzung aus den Lücken schied aus, weil
leuchtende Nachbarpunkte die Lücken um 0,10–0,49 der Punkttiefe abdunkeln.
Eine Grauwert-Schließung mit ±1,5 Punkten entfernt die Zeichen und behält
den Verlauf. Umgesetzt als `bg_closing_v1`, das Kriterium stand vorab in der
Spec. `loo`: `ab2` jetzt 83/83, alle scharfen Gruppen unverändert, 0
falsch. Die Kehrseite: `auf2` (unscharf) wird ohne eigenes Training
vollständig abgelehnt. Zahlen in VALIDATION.md.

## 2026-09-30 — Abnahme 2 an falschen Rastern gescheitert, Abnahme 3 bestanden

**`ab4` und Abnahme 2:**
* Die Kamera stand schräg von rechts. Die ersten beiden Stände waren zu
  nah: Die geringe Schärfentiefe machte links alles weich (Kontrast 6–9).
  Erst der etwa 1,5-fache Abstand brachte 32,7.
* Abnahme 2 über `ab3`/`ab4` ergab 0 falsch, aber 85,8 % abgelehnt.
* Meine erste Deutung war „Punktschatten“: Aus-Punkte waren einseitig
  dunkel neben An-Punkten. Der daraus gebaute Schattenabzug verfehlte das
  vorab festgelegte Kriterium und wurde zurückgenommen.
* Den entscheidenden Hinweis gab der Nutzer: Im entzerrten Bild von `ab4`
  standen die Zeichen schräg und ragten aus ihren Zellen. Das Raster war
  geschert.
* Die Messung gegen das ROM-Muster zeigte: Auch `ab3`, `ernte1`, `auf2` und
  `auf3` lagen 0,4–0,9 Punktspalten daneben.
* Ursache: Die Rasteranpassung mit `latfit.py` findet oft die dunklen
  Punktränder statt der Mitten. Ihr Restmaß bleibt dabei klein.

**Korrektur:**
* `profile-regrid.py` korrigierte die Raster. Die korrigierten Profile hat
  der Nutzer nach Sichtprüfung bestätigt, `auf3` bleibt offen.
* `loo` danach: `ab4` 119/119, `ab3` 152/162, 0 falsch. Die Schwelle
  `d_max` sank von 2,6 auf 1,9.
* Neu gelernt und eingefroren als `stufe2c`.
* Auffällig: Die verschobenen `ernte1`-Proben hatten zuvor die Streuung
  künstlich verbreitert. Davon profitierte die weiche Gruppe `auf2`; mit
  korrektem Raster liest sie 49/76 statt 70/76.

**Abnahme 3 mit `ab5` und `ab6`:**
* `ab5` steht frontal und gedreht. Der erste Stand zeigte ein Spiegelbild
  der Kamera über den Zellen 5–11 und wurde verworfen.
* `ab6` steht schräg von links.
* Bei beiden lag `latfit.py` wieder 0,22 bzw. 0,36 daneben.
  `profile-regrid.py still` fing das vor der Ernte ab.
* Der erste Start der `ab6`-Ernte scheiterte an der Speicherprüfung, weil
  parallel ein Import und Codex-Tests liefen. Dabei ging nichts verloren.
* Die Abnahme ergab 215/215 richtig, 0 falsch, 0 abgelehnt.
* Einschränkung: Beim Import von `ab6` verwarf `zellen_inkonsistent` 42 %.
  Die Prüfung vergleicht Zellen über alle Positionen, und bei schrägem Blick
  unterscheiden die sich stärker.

**Betrieb:**
* Die SD-Karte lief zweimal fast voll. Ursache war ein Leck von Codex:
  Kopien des repowise-Plugin-Marktplatzes in
  `~/.codex/.tmp/marketplaces/.staging`, etwa 1 GB pro Stunde.
* Dazu kamen alte VS-Code-Server und Codex-Versionen sowie volle
  tar-Sicherungen je Aufstellung.
* Das Kopieren aus dem RAM auf die Karte dauert inzwischen etwa 435 s statt
  77–200 s. Die Karte wird also langsamer.

**Einrichtungsassistent (Codex):** Es gab drei Reviews.
* Die Prüfung des Rasterversatzes 2j ist jetzt eingebaut und nicht mehr
  umgehbar.
* Im echten Offline-Ablauf liefert er auf `sc6` und `ab5` Vorschläge nahe
  am Profil. Bei schrägen Aufstellungen findet er noch keine Startlage.
* Vor dem Merge fehlt noch Nacharbeit 4 (Plan).


## 2026-09-30 — Einrichtungsassistent: Nacharbeit 1 offline geprüft

**Aufbau:** Nur gespeicherte Standbilder und bestätigte Profile wurden
gelesen: Frame 17 von `sc3`, `sc4`, `sc5`, `ab1`, `ab2` und Frame 15 von
`sc6`; für `sc3` gilt `sc3b-profile`. Die Profil-Bounding-Box plus 10 %
Rand diente als grobe Hinweisbox, die grünen Hinweisboxen wurden separat
aus dem Bild erkannt. Beide Wege nutzten `fit_lattice` ohne Stützpunkte
mit den Format-Leerzellen 8 und 13–15. `check_setup` wertete die
angepassten Quads aus. Es wurde keine Kamera geöffnet und unter `var/`
nichts geschrieben. Einzelzahlen stehen in [VALIDATION.md](VALIDATION.md).

**Beobachtung:** Alle sechs Profil-Hinweisboxen treffen die bestätigten
Quads mit höchstens 0,48 px Eckabweichung; alle sechs automatisch aus dem
grünen Punktbereich gewonnenen Boxen mit höchstens 0,57 px. `sc6` mit
etwa 7 px je Punktspalte wird nun ebenfalls erkannt. Die Quellminima
seines Pluszeichens enthalten nicht jeden äußeren Punkt; deshalb muss
die Plusprüfung den inneren rechten Arm zulassen. Breite grüne Boxen
verschieben die Schätzung des Punktabstands und die Rangfolge der
Startquads; eine zweite, nur bei Bedarf genutzte Suchrunde und ein
skalierter Pitch-Versuch beheben die beobachteten Ablehnungen von `sc5`
und `sc6`. Getrennte Plusanker werden auf konkurrierende ganze Raster
geprüft, damit zwei Anzeigen in einer Hinweisbox nicht geraten werden.

**Prüfungen:** Zellinterne Hintergrundpaare ergeben in der Leerzelle 8
von `ab2` den Wert 8,5 und FEHLER; die anderen fünf Aufstellungen liegen
bei 1–3 und bleiben OK. Float-Punktkontrast ist `sc5=19,101` und
`sc6=19,726`, mit der vorläufigen WARNUNG-Schwelle 17 beide OK. Der
Leserkontrast aus `sample_image` vor der Normierung liegt für diese
beiden bei 0,283 und 0,339. Rahmen und Glanz melden auf allen
bestätigten Aufstellungen OK.
Die synthetische Gegenprobe verdunkelt äußere Punktspalten und erkennt
auch die linke Spalte eines echten Plus. Die im Plan genannten 44 gegen
94 Grauwerte für `sc6` gehören zu einem verworfenen Zwischenstand;
dessen Bild liegt nicht mehr vor und kann hier nicht nachgerechnet werden.

**Deutung:** Die Kantenampel von `ab2` bleibt ein konservativer Vorabwert
für die Spiegelkante, auch wenn die eingefrorene Stufe-2-Normierung
`bg_closing_v1` die gespeicherten `ab2`-Proben inzwischen liest. Weder
die Stabilitätsampel noch der reale Kameraablauf oder die tatsächlich
benötigte Einrichtungszeit sind durch diese Offline-Auswertung belegt.

**Gegenprobe nach dem neuen Rasterversatz-Befund auf `master`:** Die
Profil-Referenzframes `ab3` Frame 15 und `ab4` Frame 16 wurden
schreibgeschützt gelesen; ihre SHA-256 stimmen mit den Profilen überein.
Die automatische grüne Hinweisbox führt bei `ab3` zu 504/1047
zugeordneten Punkten (48,1 %), bei `ab4` zu 327/482 (67,8 %).
Beides liegt unter der Vorabgrenze 80 % und ergibt Raster-FEHLER.
Mit der Profil-Bounding-Box plus 10 % scheitert `ab3` bereits an
`vorzeichen_kein_plus`; `ab4` ergibt 353/482 (73,2 %) und FEHLER.
Die alten Profilquads sind durch den neuen Befund selbst als falsch
erkannt. Deshalb wird hier keine Eckabweichung als Qualitätsnachweis
verwendet. Die Nacharbeit lehnt diese beiden gespeicherten Fälle ab.
Die danach mit `profile-regrid.py` bestätigten Profile korrigieren den
Versatz getrennt; eine automatische Prüfung und Nachführung im
Assistenten gehört zu Nacharbeit 2.

## 2026-09-30 — Einrichtungsassistent: Rasterversatz 2j offline geprüft

**Aufbau:** Das gespeicherte `ab4`-Standbild `frame_000016.png` wurde mit
dem gleichzeitigen Text `+0.46780 mV/V` aus `serial.jsonl` ausgewertet.
Die beiden Profilquads (`ab4-profile`, `ab4-profile-regrid1.json`)
wurden nur gelesen. Der Check korrelierte die bekannten ROM-Zeichen
waagerecht in Halbzellen und senkrecht in ganzen Zellen; maßgeblich war
jeweils der größte Betrag des Medianversatzes. Keine Kamera, kein
serieller Port und keine Änderung unter `var/`.

**Beobachtung:** Das alte Quad meldete horizontal 0,935 Punktspalten und
vertikal 0,105 Punktzeilen, also FEHLER. Das korrigierte Quad meldete
0,047 bzw. 0,046 und OK. Die synthetischen Tests enthalten ein
geschertes, ein zu enges und ein korrektes Punktraster. Ein injizierter
Kameralauf verifiziert, dass der Assistent bei 2j-FEHLER kein
`proposal.json` schreibt.

**Deutung:** Die 2j-Messung unterscheidet im belegten Fall die alte von
der korrigierten Geometrie, obwohl die alte Raster-RMS allein den Fehler
nicht sicher gezeigt hatte. Die Schwellen sind vorläufig und ein echter
zweiter Kameraframe im Mindestabstand von 30 Sekunden wurde nicht
gemessen. Die automatische Nachführung wird im Code an einem
zurückgehaltenen zweiten Standbild gegengeprüft; die Hardwarewirkung
bleibt für den nächsten gemeinsamen Kameratermin offen.

**Räumliche Grenze (Review Nacharbeit 3):** Der 2j-Abgleich kann mangels
ROM-Mustern für `m`, `V` und `/` die belegten Zellen 0–7 messen, nicht die
Einheit in Zellen 9–12. Für `sc6` meldete die lesende Gegenprobe dort
zwischen Profil- und nachgeführtem Quad bis zu 0,40 Punktspalten
Geometrieunterschied, mit `?`-maskiertem Text bis zu 0,49 (Review
Nacharbeit 4, 2026-09-30). Die Nachführung extrapoliert den rechten Bereich;
ein direkter Nachweis der dortigen Punktmitten steht damit aus.

## 2026-09-30 — Einrichtungsassistent: Nacharbeit 3 offline gegengeprüft

**Aufbau:** Die gespeicherten, voneinander verschiedenen Frames
`sc6` 15/30 und `ab5` 7/30 wurden mit dem finalen Fit, der
Nachführung auf dem ersten und der 2j-Gegenprobe auf dem zweiten Bild
gelesen. `ab4` 16/30 und `ab6` 22/30 dienten als sichere
Startlagen-Gegenproben. Die Texte `+0.46786 `, `+0.46788 `,
`+0.46780 ` und `+0.46789 ` stammen aus der Offline-Review; kein
serieller Port wurde geöffnet. Die CLI-Tests injizierten Kameraobjekte
und schrieben nur in temporäre Testverzeichnisse. Die gespeicherten
Frames belegen keinen 30-s-Abstand; die im Softwaretest eingesetzten
31 s sind ein Testparameter, keine Messung der Aufstellung.

**Beobachtung:** `sc6` lieferte 196/208 Startpunkte; das nachgeführte
Quad bestand 2j mit 0,043/0,070 Punktspalten/-zeilen und die
Schlussprüfung mit WARNUNG. Bei `ab5` fiel der waagerechte 2j-Versatz
von 0,324 auf 0,033, der senkrechte betrug zuletzt 0,061. Trotz nur
314/456 zugeordneten Kandidaten blieb 2j OK und die Schlussprüfung
WARNUNG. Beide echten Offline-Abläufe schrieben einen Vorschlag.
`ab4` blieb als `startlage_mehrdeutig`, `ab6` als `keine_startlage`
abgelehnt. Eine versuchsweise lockerere Ankerwahl bei `ab4` lieferte
eine um 9,14 px falsche Lage und wurde verworfen.

**Deutung:** Die gemeinsame entzerrte Punktsuche beseitigt den
Kandidatenbruch zwischen Fit und Schlussbewertung. Die von 2j
unabhängige Zuordnungsquote ist bei scharfen Punkträndern kein
hinreichender Grund mehr für FEHLER; sie bleibt als WARNUNG sichtbar.
Für `ab4` und `ab6` braucht die Startsuche weitere belegte Anker oder
eine gesonderte sichere Bedienerführung, bevor sie automatische
Vorschläge liefern kann. Ein echter Lauf an der Kamera steht weiter aus.

## 2026-09-30 — Einrichtungsassistent: Nacharbeit 4, feste Quads

**Aufbau:** Vier bereits bestätigte Profil-Quads wurden über den
vollständigen Offline-`propose`-Befehl mit bekanntem Zellentext geprüft.
Verwendet wurden `ab4` Frame 16, `ab5` Frame 7, `ab6` Frame 20 und
`sc6` Frame 15. Die zugehörigen Profile und Diagnosebilder wurden unter
`var/` nur gelesen; Vorschläge und Overlays gingen nach `tmp_path`.
Kamera und serieller Port blieben geschlossen. Die genauen 2j-, RMS-
und Bias-Werte sowie die Ampeln stehen in [VALIDATION.md](VALIDATION.md).

**Beobachtung:** Alle vier textgestützten Vorschläge bestanden 2j und
die Gesamtprüfung mit OK oder WARNUNG. `ab6` Frame 22 wurde nicht als
Regression für den manuellen Vorschlag gewählt, weil die gesonderte
Kantenprüfung dort FEHLER meldet; Frame 20 ist hierfür geeignet.
Ein eigener synthetischer Test reproduzierte den früheren stillen
Rückfall auf das schlechtere Start-Quad bei abgelehnter Nachführung.
Nach der Änderung bricht dieser Pfad mit dem Ablehnungsgrund ab.

**Deutung:** RMS, Bias und Zuordnungsquote sind bei festem Quad
Hilfswerte für die Rasterlage; die unabhängige 2j-Messung entscheidet
über den bekannten Textbereich. Die automatische Startsuche behält ihre
strengeren Grenzen. Die rechte Einheit bleibt geometrisch extrapoliert,
und für `ab4`/`ab6` existiert weiterhin keine automatische Startlage.
Es gab weder einen neuen Hardwarelauf noch eine Messung der
Einrichtungsdauer oder eines realen 30-s-Stabilitätsintervalls.

## 2026-10-01 — Aufstellung `sc7`: erster echter Lauf des Einrichtungsassistenten

**Aufbau:** Die StreamCam stand frontal und nah vor dem GSV-Sensor, das Glas
war etwa 900 px breit. Der Text kam seriell vom GSV-2AS über
`/dev/ttyUSB0`. Der erste Versuch `sc7a` lief mit etwa 820 px Glasbreite
und leicht von oben.

**Beobachtung `sc7a`:**
* `assist` brach mit `keine_startlage` ab. Die Plus-Anker kamen mit
  schräger Punktperiode heraus.
* Von Hand mit Saatpunkten: `latfit.py` lag 0,88 Punktspalten daneben,
  `profile-regrid.py still` korrigierte auf 0,04 / 0,05.
* `propose` mit dieser richtigen Lage lehnte trotzdem ab, mit
  `cursorzeile_belegt`. Unter jedem Punkt der untersten Zeile lag etwa
  eine Zeile tiefer ein schwacher Schatten.

**Beobachtung `sc7`:** Die Kamera stand tiefer, senkrecht auf Höhe der
Displaymitte. Die Schatten waren kaum noch zu sehen.
* `assist` lief ohne Hilfe durch: Fokus 68, 2j 0,04 / 0,07, Stabilität
  0,03 px über 33 s, Gegenlesen 2/2, Gesamturteil WARNUNG (Bias 0,135).
* `profile-regrid.py still` an 16 eigenen Standbildern: 0,04 / 0,07.
* Ernte mit 25 Schritten, da der Arbeitsspeicher für 30 nicht reichte:
  2926 Bilder, 0 verworfen, 1507 gelabelt.
* Import: 111 Proben, 9 abgelehnt wegen `zellen_inkonsistent`.
* Lesetest `stufe2c`: 111/111 richtig, 0 falsch, 0 abgelehnt.

**Deutung:** Bei frontalem Blick funktioniert der Assistent auch in einer
neuen Größe. Bei Blick von oben entstehen aus der Nähe Punktschatten. Diese
und die Startsuche sind Nacharbeit 5. Der Leser verkraftet die größere
Abbildung ohne Fehler. Zahlen: [VALIDATION.md](VALIDATION.md) 2026-10-01.

## 2026-10-01 — Einrichtungsassistent: Nacharbeit 5 an `sc7a`-Standbildern

**Ziel:** Die falsche Ablehnung bei leichtem Blick von oben beheben,
ohne echte Cursorpunkte durchzulassen.

**Aufbau:** Nur gespeicherte Bilder `sc7a-assist/still.png`,
`sc7a-still/frames/frame_000016.png`, `sc7-assist/still.png` und das
gespeicherte `sc7a-quad.json`. Diagnosebilder unter `var/` blieben
unverändert. Tests und `propose` schrieben ausschließlich temporäre
Artefakte. Kamera und serielle Schnittstelle wurden nicht geöffnet.

**Beobachtung:** Die schwachen Schatten unter Zeile 6 überschritten die
absolute Kandidatengrenze von 8. Ihre Tiefen waren 8,1–13,8 und 8,4–12,0,
während echte zugeordnete Punkte im selben Bild Medianwerte von 28,7 und
27,4 hatten. Ohne die falsche Cursorablehnung fand die bestehende
Startsuche für `sc7a` bereits eine Lage; die vermutete Änderung der
Quellbild-Minima war nicht erforderlich. Mit dem relativen Grenzwert
bestanden alle 32 gespeicherten `sc7a`-Frames die Cursorprüfung; drei
Grenzfälle wurden als Regressionen aufgenommen. Der feste Referenzquad bestand
den vollständigen Offline-Vorschlag mit 2j OK (0,041/0,057) und
Gesamt-WARNUNG. Zahlen und Pfade stehen in [VALIDATION.md](VALIDATION.md).

**Deutung:** Eine relative Tiefengrenze unterscheidet in diesen Bildern
schwache optische Schatten von echten LCD-Punkten. Ein synthetischer
belegter Cursor bleibt eine Ablehnung. Für neue Blickwinkel und
Lichtverhältnisse braucht es weiterhin Bild- und Bedienerprüfung; hier
fand kein weiterer echter Kameralauf statt.

## 2026-10-12 — Leserlaufzeit Pi 5 (Messpfad live, Task 1)

**Messdatum:** 2026-10-13; Abschnittsdatum gemäß Task-Brief.

**Ziel:** Laufzeit von Entzerren (400×160) und Dot-Matrix-Lesen bestimmen.

**Aufbau:** Raspberry Pi 5, gespeichertes Standbild
`var/diagnostics/sc7-assist/still.png`, Quad und Raster aus
`var/diagnostics/sc7-assist/proposal.json`, Einheit mV/V. Eingefrorene
Vorlagen `var/dotmatrix/templates-stufe2c-2026-09-30.json`, SHA-256
`6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a`.
Keine Kamera geöffnet, `var/RECORDING_IN_PROGRESS` fehlte; Daten nur gelesen.
Aufruf: `./.venv/bin/python scripts/live-reader-benchmark.py` mit Defaults
und `PYTHONPATH="$PWD/src"` für den Worktree statt des Hauptcheckouts.

**Messergebnis:** 200 Wiederholungen, Median **44,27291 ms**, p95
**68,504584 ms**, Maximum **118,582498 ms**. Letzter Wert **0,46792 mV/V**,
`last_reject: null`. Laufzeit mit `time.perf_counter_ns` gemessen
(monotone Verarbeitungsuhr); keine Zeitangabe aus dem Standbild abgeleitet.

**Schluss:** `1000 / p95_ms` ergibt **14,59756 Bilder/s** für diese
Lesekette. Dies ist eine Laufzeitschätzung am wiederholten Standbild,
keine gemessene Live-Rate und keine Aufnahme- oder DUT-Latenz. Nachführung,
Freigabe und Audit-Ausgabe sind hier nicht enthalten. Zahlen zusätzlich
in [VALIDATION.md](VALIDATION.md#leserlaufzeit-2026-10-13-messpfad-live-task-1).

---

## 2026-10-14 — Werkbank-Startsuche in Punktgröße (Task N7)

**Aufbau und Befund:** Ursachenanalyse an gespeicherten, scharfen und frontalen
Werkbank-Standbildern vom 2026-10-14; keine Hardwareänderung in dieser Task.
Die flachen Böden der etwa 6,7 × 8,4 px großen LCD-Punkte erzeugten bei fester
0,7-px-Glättung je Punkt 1–4 zufällige Minima. Ein um eine Punktzeile verkipptes
Raster wurde angenommen und erst durch 2j abgelehnt.

**Gemessene Vorher/Nachher-Zahlen aus dem Task-Brief und Controller-Befund:**
Vier aktuelle Standbilder: **0/4 → 4/4 korrekt**; gestörte Varianten:
**18/18 korrekt, 0 falsch**, zuvor **9 falsch**. Ältere Aufstellungen bleiben
innerhalb **1 px**. Korrekte Raster liegen mit punktgroßer Glättung bei
rms_rows **0,05–0,09**, falsche bei **0,19–0,23**; zuvor lag der verrauschte
Zeilenrestfehler bei **0,22** mit Grenze **0,25**. Diese Angaben stammen aus
der vorausgehenden Ursachenanalyse, nicht aus einer neuen Live-Messung.

**Deutung und Umsetzung:** Glättung je Achse mit max(0,7 px, 0,2 × Punktabstand)
und rms_rows-Grenze **0,15** trennen die beobachteten richtigen und falschen
Raster. Startdurchläufe mit fester 0,7-px-Glättung, danach den gemessenen
Anteilen 0,15 und 0,18 folgen ausschließlich auf `keine_startlage`.
Mehrdeutigkeit und Minus bleiben endgültig; 2j und Gegenlesen bleiben scharf.
Regressionen lesen die Standbilder nur und überspringen fehlende Dateien.
Aus den Standbildern wird keine Aufnahmezeit oder Latenz abgeleitet.

## 2026-10-14 — Messpfad live: Einrichtung an der StreamCam nach N7 { #messpfad-live-einrichtung-nach-n7-2026-10-14 }

**Ziel:** Einrichtung am echten Aufbau nach der N7-Korrektur erneut prüfen.

**Aufbau:** StreamCam frontal auf GSV-2AS / Displaytech 161A, Glas etwa
720 px breit, Raumlicht, Zellentext seriell gelesen. Werkbank auf Port 8081,
Einrichtung über `dispread live setup` ausgelöst. Der vierte Versuch lief
am Abend nach Werkbank-Neustart mit Code-Stand `2303cdf`. Die Befunde
stammen vom Controller; diese Dokumentationskorrektur öffnete keine Hardware.

**Beobachtung:** Vor N7 **0/4** Einrichtungen, darunter ein falsches Raster,
das erst 2j abfing. Nach N7 **4/4** Vorschläge in **47/55/49/45 s**
(45–55 s), jeweils Gesamt-WARNUNG wegen einer Proxy-Prüfung: zuerst
`raster` WARNUNG, beim vierten Versuch `kanten` WARNUNG und `raster` OK.
Rasterversatz und Gegenlesen waren jeweils OK. Einrichtungsdateien liegen
unter `var/live/<sitzung>/setup/` (lokale Daten, nicht in Git); die Zahlen
stehen auch in [VALIDATION](VALIDATION.md#messpfad-live-einrichtung-2026-10-14).

**Deutung und offen:** Die Einrichtung gelingt am geprüften Aufbau; dies
ist kein formaler Abnahme-Lauf. Bestätigung durch die bedienende Person,
Messlauf, Wertwechsel über `set norm` und Trackingmessung bei diesen
Wertwechseln stehen weiterhin aus. Daraus folgt noch keine Aussage zur
Live-Trefferquote oder Trackingqualität.

## 2026-10-21 — Messpfad live: Bedienerläufe am Aufbau { #messpfad-live-bedienerlaeufe-2026-10-21 }

**Ziel:** Den Live-Messpfad mit der bedienenden Person am echten Aufbau
benutzen: Einrichtung, Bestätigung, Läufe. Dabei auf Licht, Schräglage und
Wertwechsel achten.

**Aufbau:** StreamCam auf GSV-2AS / Displaytech 161A, Raumlicht und
Tageslicht, serieller Zellentext als Referenz. `dispread serve --port 8081`,
Läufe über `/live`. Diese Dokumentation öffnete keine Hardware; Befunde
stammen vom Controller und der bedienenden Person. Zahlen:
[VALIDATION](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21).

**Beobachtungen:**

* **Schatten und Schräglage (Morgen).** Die Kamera stand schräg, ihr Schatten
  lag auf der Anzeige. Die Punkttiefe war außerhalb des Schattens 0,39–0,41,
  im Schatten 0,67–0,69. Zellen an der Schattenkante überschritten `d_max`
  (`d_best` bis 2,30 × `d_max`). Die beste Vermutung stimmte dennoch in allen
  28 Standbildern mit Vorschlag mit der Referenz überein, mit Abstand
  ≥ 1,27 zur zweitbesten Klasse. Folge: Licht-Hinweis (Kontrastsprung
  zwischen Zellen) und angepasste Toleranz (L3).
* **Schwankende letzte Ziffer.** Mit manuellem Zellentext und einer
  wechselnden letzten Ziffer meldete die Einrichtung ein irreführendes
  2j FEHLER. Folge: Maskierung, Neuaufnahme bis zu fünfmal, 8 Zeichen und `?`
  im Zellentext (L2).
* **Lesesperre.** Nach Bestätigung eines Vorschlags mit Gegenlesen WARNUNG
  waren am Prüfstand 1202/1202 Datensätze UNREADABLE. Folge: Lesesperre und
  ausdrücklicher Testlauf (L1).
* **Testlauf** `live-20261021T100128Z`: Die Vermutungen stimmten nach
  Angabe der Person mit der Anzeige überein; `tracking_lost` 0,
  `track_score` mindestens 0,86 bei Wertwechseln.
* **Toleranzlauf ×1,41** (25 s): 304 von 318 VALID, Nachführung ohne Verlust.
* **Strenger Lauf** (79 s, viele Wertwechsel, kurz eine Hand davor): 911 von
  1168 VALID, 188 UNREADABLE. Alle 67 Wertwechsel erfasst. Je Wechsel
  270–340 ms ohne VALID; das passt zur LCD-Umschaltung (etwa 200–300 ms) plus
  einem Bestätigungsbild. Die Hand ergab 1,4 s UNREADABLE und
  `tracking_lost` 33, wie gewollt.
* **Bildrate.** Verarbeitet wurden 14,7 Bilder/s von 30; der Leser braucht
  median 53 ms/Bild, die Kette 64 ms. Jedes zweite Bild entfällt.

**Deutung und offen:** Der Messpfad liest am Aufbau brauchbar, aber das ist
kein formaler Abnahme-Lauf, und die angepasste Toleranz ist nicht
validiert. Offen: Leser auf 30 Bilder/s mit Pi-Schutz, TRANSITION statt
UNREADABLE bei Wertwechseln, Referenzaufzeichnung zur Toleranzvalidierung,
Referenzlauf, Ausgabe an GSVmulti (OQ-07, Protokoll fehlt), später
UI/UX-Überarbeitung der Werkbank.


## 2026-10-21 — Leser-Vektorisierung in der Sandbox

**Aufbau:** Softwaremessung, keine Hardwareänderung. Synthetischer
400 × 160 Crop `+0.60972 ` mit synthetischen Vorlagen und gespeichertes
Standbild `var/live/live-20261021T114122Z/setup/still.png` mit Quad/Raster
aus `proposal.json`, Stufe-2c-Vorlagen. Fünf Aufwärmlesungen und 50
Zeitdifferenzen je Variante mit monotonem `time.perf_counter_ns`; Entzerren
vor der Zeitmessung. CPU währenddessen geteilt und begrenzt.

**Beobachtung:** Median synthetisch 46,81 → 4,42 ms, echtes Standbild
45,50 → 5,15 ms. Zahlen und p90 stehen in [VALIDATION](VALIDATION.md#leser-vektorisierung-sandbox-2026-10-21).
Klassen und Verschiebungen werden gemeinsam verglichen, Punktmitten und
Abtastung für alle Zellen gemeinsam berechnet. Division in Float32 bleibt
erhalten, damit Rundung an Freigabegrenzen keine Entscheidung ändert.

**Deutung:** Die Schleifen waren der wesentliche Engpass; die Indikation
liegt unter 15 ms. Das belegt weder Dauerlast noch Live-Durchsatz auf dem
ruhigen Pi. Der Controller misst 60 s am Aufbau mit CPU, Temperatur und
Drosselbits; diese Sandbox-Messung ersetzt keine Abnahme. `var/` blieb
unverändert, kein Kamera- oder serieller Zugriff.


## 2026-10-21 — Erster Live-Lauf mit Referenzaufzeichnung { #messpfad-live-referenzlauf-2026-10-21 }

**Ziel:** Tempo und Übergangsstatus am Aufbau prüfen und erstmals gegen den
seriellen GSV-2AS-Strom abgleichen.

**Aufbau:** StreamCam am GSV-2AS, Raumlicht, strenger Leser, Referenz
mitgeschrieben, Werte von Hand geändert, kurz die Hand vor der Anzeige.

**Beobachtung:** 27,2 gelesene Bilder/s statt 14,7; 0 Fehllesungen bei 715
entschiedenen VALID; 26 Wechsel, Verzögerung Median 277 ms; Wechsel jetzt
überwiegend als „Wert wechselt“ (TRANSITION). Die Seite wirkte nicht schneller,
weil Vorschau und Status nur alle 0,5 s abgeholt werden. SSH-Abbrüche und
kurze Hänger: Codex-App-Server (per SSH von der Desktop-App gestartet) legte
wegen `[marketplaces.repowise]` alle ~15 min eine ~200-MB-Kopie an; der
Wächter zeigte 56 s Stillstand genau beim Anlegen einer Kopie. Eintrag mit
Nutzerfreigabe entfernt, Kopien gelöscht. Der Absturz um 14:08 hatte sehr
wahrscheinlich dieselbe Ursache (nicht belegbar, kein persistentes Journal).

**Offen:** längerer Referenzlauf (≥ 10 min, mit Werteplan), Toleranzlauf mit
Referenz, Vorschau schneller (UI-Überarbeitung).


## 2026-10-21 — Toleranzlauf ×1,8 mit Referenzaufzeichnung { #messpfad-live-toleranzlauf-2026-10-21 }

**Ziel:** Die angepasste Lesetoleranz erstmals gegen den seriellen
GSV-2AS-Strom prüfen.

**Aufbau:** StreamCam am GSV-2AS, Raumlicht, Gegenlesen WARNUNG, Toleranz
×1,8 bestätigt, Referenz mitgeschrieben, kein Werteplan, Werte von Hand
geändert; 5,6 min.

**Beobachtung:** 0 Fehllesungen bei 6630 entschiedenen VALID; die 2762 VALID
kurz nach einem Wechsel zeigen alle den alten oder neuen Wert. 8978 Bilder
liefen unter der Toleranz. 29,7 gelesene Bilder/s, Verzögerung nach Wechsel
Median 193 ms. Ruhige Anzeige durchgehend VALID; UNREADABLE nur mitten im
Umschalten. Serieller Strom ohne Fehler (635 Telegramme, alle 533 ms). Der Pi
blieb ohne Aussetzer, CI und Codex-Kopien liefen nicht mit.

**Offen:** Lauf ≥ 10 min mit Werteplan, zweite Aufstellung, Name statt
„test“ bei der Bestätigung.


## 2026-10-21 — Langer strenger Lauf mit Referenz (12 min) { #messpfad-live-langlauf-2026-10-21 }

**Ziel:** Dauerbetrieb über 10 min gegen den seriellen GSV-2AS-Strom.

**Aufbau:** StreamCam am GSV-2AS, Raumlicht, streng ohne Toleranz,
bestätigt mit Namen, Referenz mitgeschrieben, kein Werteplan.

**Beobachtung:** 0 Fehllesungen bei 8979 entschiedenen VALID, die 9064 VALID
kurz nach Wechseln alle mit altem oder neuem Wert. 716 Wechsel, 715 mit VALID
erreicht, Median 232 ms. 29,8 Bilder/s über 12 min, keine Kameralücke, keine
verlorene Nachführung. 7 STALE-Bilder, als die letzte Ziffer schnell zwischen
zwei Werten zitterte und eine Zelle 0,65 s im Umschalten hing; das ist die
gewollte Markierung, keine Störung der Verbindung. Pi ohne Aussetzer.

**Offen:** Toleranzlauf über 10 min, Lauf mit Werteplan (große Sprünge über
den ganzen Bereich), zweite Aufstellung oder anderes Licht.

## 2026-10-21 — Vorbereitung eines strengen Laufs mit Werteplan

**Ziel:** Bedienergeführten Messlauf mit fünf Normierungsfaktoren und
serieller Referenz vorbereiten. Noch kein Messlauf und keine Abnahme.

**Aufbau und Eingriff:** Vorhandene StreamCam am GSV-2AS; keine mechanische
Änderung durch den Agenten. Werkbank aus dem Haupt-Checkout in tmux
`picam-messlauf-20261021` auf Port 8081 gestartet. Register über das vorhandene
Leseskript gesichert; Normierung, Dezimalpunkt, Einheit, Modus, Stellenzahl,
Messbereich, Gerätetyp und Firmware stimmen mit dem Rückstellpunkt vom
2026-09-22 überein. Der serielle Messwertstrom wurde wieder gestartet.
Die automatische Einrichtung setzt Fokus 42, Belichtung 300, Gain 14 und
Weißabgleich 4717 K, Automatiken danach aus; Werte zurückgelesen.
Sitzungsbezogene Einstellungen stehen in `setup/camera-settings.json`.

**Beobachtung:** Sitzung `live-20261021T151835Z`, alle neun Prüfungen OK,
Gegenlesen 2/2 ohne Widerspruch oder erhöhte Toleranz. Der Agent hat das
Sampling-Overlay angesehen; die namentliche Prüfung und Bestätigung durch
die Person stehen aus. Zahlen: [VALIDATION](VALIDATION.md#messlauf-vorbereitung-2026-10-21).

**Schluss und Ablauf:** Die Person hat ausdrücklich den strengen Lauf am
aktuellen Aufbau gewählt. Vorbereitet ist
`1:140,2:140,0.5:140,5:140,10:160` (Faktor:Sekunden), insgesamt 720 s
Haltezeit zuzüglich Befehlspausen. Referenz mitschreiben, einmal etwa 2 s
Displayabdeckung mit notiertem Zeitpunkt, nach etwa 13 min stoppen und
Rückstellung abwarten. Der Plan stoppt den Lauf nicht automatisch. Während
des Laufs keine Pushes, Builds oder Tests auf dem Pi; Runner unverändert.
Bestätigung und Laufstart bleiben auf `/live`. Kein Toleranznachweis.

**Belege:** Diagnose, Registerstand, Werteplan und Bedienablauf unter
`var/diagnostics/messlauf-vorbereitung-20261021/`; Einrichtungsbilder und
Prüfbericht unter `var/live/live-20261021T151835Z/setup/` (lokale Daten).

**Nachtrag 17:21 MESZ:** Leonhard Hentschke hat die Einrichtung auf `/live`
bestätigt, Einheit und Format geprüft; `confirmation.json` gespeichert.
Laufstart und Bestätigung des Werteplans stehen noch aus.

**Laufende Diagnose nach Start um 17:22 MESZ:** Beim Wechsel des Werteplans
von Faktor 1 auf 2 meldet die Person dauerhaft UNREADABLE. Das Audit nennt
`tracking_lost:low_score`, die Referenz etwa 1,2115 mV/V. Beide Schreibbefehle
(`set norm`, `set dpoint`) wurden mit `[59, 160]` bestätigt. Bild 4317 ist
noch VALID mit 1,2115; ab Bild 4318 scheitert die Nachführung. Kamera ohne
Bildlücken. Der Tracker registriert das gesamte entzerrte Display gegen
das Einrichtungsbild, einschließlich der wechselnden Ziffern; dies ist
ein konkreter Befund zum bisher zurückgestellten R13. Eine Ziffernänderung
als Ursache ist plausibel, mechanische Einflüsse sind damit nicht unabhängig
ausgeschlossen. Keine Einstellungsänderung während des Laufs.
Diagnoseschnappschuss: `run-01/tracking-diagnose.json`. Zahlen stehen in
[VALIDATION](VALIDATION.md#messlauf-vorbereitung-2026-10-21).

**Erholung ohne Eingriff:** Nach dem nächsten Planschritt auf Faktor 0,5
liefert der Lauf wieder VALID mit etwa 0,30287 mV/V. Das stärkt die Hypothese
der wertabhängigen Nachführung; ein unabhängiger Bewegungsnachweis fehlt
weiter. Kamera und Tracking-Schwellen wurden nicht verändert.

**Abschlussstatus beim Wiki-Abgleich:** Der bereits laufende Versuch wurde
durch die Bedienung beendet; der Doku-Agent hat nur den lokalen Status und
die gespeicherte `session.json` gelesen. Ende laut Artefakt am 2026-10-21
um 17:36 MESZ (`2026-10-21T15:36:01.987480+00:00`), Grund `bediener`.
Die Rückstellprüfung des Referenzrecorders meldet erfolgreiches Schreiben
und Übereinstimmung mit dem Rückstellpunkt. Kamera bleibt für die Vorschau
an. Keine Hardwareänderung durch den Wiki-Abgleich. Die anschließende
Referenzauswertung folgt unten; eine vom Zifferninhalt unabhängige
Nachführung bleibt offen. Abschlusszahlen auch in
[VALIDATION](VALIDATION.md#messpfad-live-werteplan-2026-10-21).


## 2026-10-21 — Abschluss des strengen Werteplan-Laufs

**Ziel und Aufbau:** Sitzung `live-20261021T151835Z/run-01`, fünf Faktoren
1, 2, 0,5, 5 und 10, 17:22:35 bis 17:36:01 MESZ (806 s einschließlich
Rückstellung). Leonhard Hentschke bestätigt Einrichtung, Format und Einheit,
ca. 2 s Displayabdeckung ungefähr nach 6 min und sonst unveränderten Aufbau.
Strenger Leser ohne erhöhte Toleranz; keine Einstellung im Lauf geändert.
Die Kamera läuft nach dem Lauf für die Vorschau weiter.

**Ergebnis:** Normierung und Dezimalpunkt durch Schreiben und Rücklesen
zurückgestellt. Referenzabgleich Exit 0: 0/11 137 Fehllesungen; 2563 VALID
im Schutzintervall und 232 ohne Referenzdeckung sind dadurch nicht als
korrekt nachgewiesen. 28,59 gelesene Bilder/s, keine Kameralücke, kein
Auditfehler und kein Referenz-Queue-Verlust. Aber 8074 Trackingverluste:
bei Faktor 2 und 5 sämtliche stabilen Referenzfenster UNREADABLE, bei
1, 0,5 und 10 nahezu durchgehend VALID. Die fünf Referenzlücken an
Befehlspausen verhindern belastbare Verzögerungszahlen für die großen
Normierungssprünge. [Vollständige Zahlen](VALIDATION.md#messpfad-live-werteplan-2026-10-21).

**Deutung:** R13 ist ausgelöst; Nachführung bei wechselndem Zifferninhalt
vor weiteren Freigabeläufen bearbeiten ([OQ-26](open-questions.md#oq-26)).
Ein unabhängiger Bildnachweis der Ursache fehlt mangels gespeicherter
Live-Bilder. Die berichtete Abdeckung lässt sich zeitlich nicht eindeutig
isolieren; keine separate Aussage zur Abdeckreaktion. Kein bestandener
Robustheits- oder Toleranznachweis.

**Belege:** `reference-eval.json` und `werteplan-auswertung.json` neben den
unveränderten Lauf-Audits. Keine Änderung am Messpfad, kein Push und kein
Serverneustart für die Auswertung.

---

## 2026-11-04 — Windows-Vorbereitung der GSVmulti-Anbindung

**Ziel:** Einen ersten UserDefined-Demodatenempfang vorbereiten.

**Aufbau laut Nutzerrückmeldung:** Windows 11, GSVmulti 2.03, Python 3.15
x64. PRO-Lizenz aktiviert; UserDefined danach verfügbar. Letzte PowerShell-
Portabfrage nennt COM3. Kein Pi-UART-Kabel neu angeschlossen oder geprüft.

**Beobachtung:** com0com-GUI meldet fehlendes .NET trotz laut Nutzer
vorhandener Runtime/Developer-Pack. Versionen unbekannt; CLI öffnet sich.
Dessen `list` meldet:

```text
CNCA0 PortName=-
CNCB0 PortName=-
CNCA1 PortName=COM#
CNCB1 PortName=COM#
```

**Beleg:** Nutzerrückmeldung, lokal gesichert unter
`var/diagnostics/gsvmulti/windows-com0com-list-20261104-01.txt`.
Dies ist kein direkt vom Agenten abgefragter Windows-Diagnoselauf.

**Stand:** Keine COM-Nummernzuordnung des virtuellen Paars, geladene
Treiberfunktion oder GSVmulti-Empfang bestätigt. Der nächste Versuch weist
dem zweiten Paar reale COM-Namen zu und prüft die Windows-Portliste.
Kein Messlauf und keine Latenz-/Durchsatzmessung; OQ-47 bleibt offen.

**Weitere Rückmeldung im selben Einrichtungsvorgang:** Die erneute
com0com-Liste ist unverändert, die PowerShell-Portabfrage nennt weiter
nur COM3. Ausgaben der vorgeschlagenen Namensänderungen wurden nicht
übermittelt; deren Ausführung/Erfolg wird deshalb nicht angenommen.
Beleg: `var/diagnostics/gsvmulti/windows-com0com-list-20261104-02.txt`.
Nächste lesende Diagnose: `Win32_PnPEntity` für com0com mit
`ConfigManagerErrorCode`. Eine Signatur-/Treiberblockade ist noch keine
bestätigte Diagnose. Keine Messwertübertragung durchgeführt.

**Konkreter PnP-Befund:** Nutzer meldet für beide Busgeräte Error und
`ConfigManagerErrorCode: 52` (`ROOT\COM0COM\0000`, `0001`) und bestätigt
die Installation der signierten Ausgabe. Windows weist die Treibersignatur
zurück; die .NET-GUI-Meldung erklärt diesen Treiberstartfehler nicht.
Diagnoseschnappschuss:
`var/diagnostics/gsvmulti/windows-com0com-pnp-20261104-03.txt`.
Exakte Paketversion/Zertifikat sind nicht unabhängig geprüft. Kein
Windows-Sicherheitsparameter wurde vom Agenten verändert. Noch kein
Ersatztreiber ausgewählt oder Empfangstest durchgeführt; OQ-47 bleibt offen.

**Fortsetzung: Nutzer wählt UART direkt.** Der erste Empfangstest soll
Pi-TX über das vorhandene USB-TTL-Kabel an den realen Windows-COM-Port
führen, ohne virtuellen Treiber und ohne Windows-Brücke. Auf dem Pi wurde
nur lesend geprüft: `/dev/ttyAMA0` vorhanden, `dtparam=uart0=on`, Getty für
diesen Port inaktiv, `pinctrl` zeigt GPIO14=TXD0/GPIO15=RXD0, `fuser` nennt
keinen Prozess. Schnappschuss:
`var/diagnostics/gsvmulti/pi-uart-preflight-20261104.txt`.
Kabel-RX/GND-Belegung und Windows-Adapterport noch offen. Keine Verdrahtung
angeleitet oder bestätigt und kein UART-Telegramm gesendet.

**Windows-Adapteridentifikation:** Die vom Nutzer übermittelte
`Win32_SerialPort`-Abfrage zeigt ausschließlich COM3, Name Intel Active
Management Technology SOL, PCI-Kennung `VEN_8086&DEV_7F6B`. COM3 gehört
somit nicht zum USB-TTL-Kabel. Beleg:
`var/diagnostics/gsvmulti/windows-serialports-20261104-04.txt`.
Ein fehlender Adapter in dieser Abfrage allein beweist noch keine bestimmte
Fehlerursache. Nächster Schritt ist der Vergleich vorhandener PnP-Geräte
bei abgezogenem und eingestecktem USB-Kabel. GPIO-Enden bleiben bis zur
Bestätigung der Belegung frei; keine UART-Telegramme gesendet.

**USB-Gerät jetzt identifiziert:** Der PnP-Vergleich nach Einstecken zeigt
`USB Serial Port (COM4)` (Ports) und `USB Serial Converter` (USB), beide
Status OK, VID_0403/PID_6001 mit FTDIBUS-Kennung. Beleg:
`var/diagnostics/gsvmulti/windows-usb-ttl-20261104-05.txt`. COM4 ist damit
für den direkten Demoempfang vorgesehen; COM3 bleibt Intel AMT.
Nächster Schritt: UserDefined-Kanal auf COM4 vorbereiten und Kabel-RXD/GND
zuordnen. Noch keine GPIO-Verbindung oder serielle Übertragung bestätigt.

**Kabelbeschriftung:** Nutzer bestätigt, dass gelbe und schwarze Adern
unbeschriftet sind. Die RXD/GND-Zuordnung bleibt offen; COM4/FTDI-Kennung
ist dafür kein Beleg. Vor Verdrahtung wird die Zuordnung über Artikelnummer,
Produktquelle oder aussagekräftige Produktbilder gesucht. Noch keine
GPIO-Verbindung oder Messwertübertragung bestätigt.

**Nutzerrecherche zur Aderbelegung:** Nutzer meldet Gelb=RXD, Schwarz=GND,
Orange=TXD aus einer Internetquelle. Exaktes Modell/Quelle sind nicht
unabhängig identifiziert; die Angabe entspricht dem üblichen FTDI-Schema.
Für den einseitigen Test wird Pin 8 (GPIO14/TXD0) → Gelb und Pin 6 (GND) →
Schwarz angeleitet; sämtliche anderen Adern frei. Pi-Pinpositionen nach
Raspberry-Pi-Dokumentation, Pinmux erneut GPIO14=TXD0/GPIO15=RXD0; fuser
zeigt keinen Portnutzer. Durchführung der Verdrahtung und Empfangsbereitschaft
von GSVmulti sind noch nicht bestätigt. Kein Telegramm gesendet.

**Mechanischer Anschluss korrigiert:** Nutzer beschreibt einen gemeinsamen
schwarzen 6-poligen Buchsenblock mit Beschriftung GND/CTS/VCC/TXD/RXD/RTS.
Die vorherige Annahme einzeln steckbarer Female-Kontakte wird korrigiert.
Keine Direktmontage des ganzen Blocks am Pi. Zwei Male–Female-Jumper
werden für GND → physischer Pin 6 und RXD → physischer Pin 8 angeleitet;
übrige Kontakte frei. Kontakte jetzt über die Nutzerbeschriftung zuordenbar.
Noch keine tatsächlich ausgeführte Verdrahtung oder Übertragung bestätigt.

**Verdrahtung laut Nutzer hergestellt:** Nutzer meldet „pins sind
angeschlossen“ nach der Anweisung GND → physischer Pi-Pin 6 und RXD →
physischer Pi-Pin 8. Keine unabhängige Sichtprüfung. Pi erneut lesend
geprüft: GPIO14=TXD0/GPIO15=RXD0, fuser nennt keinen UART-Nutzer,
serial-getty@ttyAMA0 inaktiv. Der vorhandene Formatter erzeugt 600
synthetische Telegramme von `%-000.300` bis `%+000.299`, jeweils CRLF.
Empfangsbereitschaft von GSVmulti wird noch abgefragt; keine serielle
Übertragung begonnen. Vorbereitung:
`var/diagnostics/gsvmulti/uart-direct-test-preparation.json`.

---

## 2026-11-04 — Direkter UART-Demolauf 01 und Startreihenfolge

**Aufbau:** Nutzer meldet Zwei-Jumper-Verbindung Pi-Pin 8/TXD0 → Kabel-RXD
und Pi-Pin 6/GND → Kabel-GND. USB-TTL-Adapter COM4 unter Windows 11,
GSVmulti 2.03 PRO mit UserDefined. Keine unabhängige Sichtprüfung der
Verdrahtung. Pi-Pinmux zeigt GPIO14=TXD0, kein Portnutzer vor Sendebeginn.
Pi sendet auf ttyAMA0 mit 115200, 8N1, ohne Handshake.

**Lauf 01:** 600 synthetische Werte, Zielrate 10/s. Der Pi-Treiber nahm
600 vollständige Telegramme (6600 Bytes) an; Hostlaufzeit des Programms
60,316465131 s. Zahlen und Grenzen stehen in
[VALIDATION](VALIDATION.md#uart-demo-20261104-01). Artefakte im Verzeichnis
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-01/`.

**Nutzerbeobachtung:** GSVmulti meldet wenige Sekunden nach Connect Timeout,
keine Werte beobachtet. Übermittelte Add-Channel-/DEFINE-Screenshots zeigen
COM4, 115200, UserDefined, Präfix %, einen Wert, Position 1, Filter aus.
Der Timeout-Screenshot zeigt Datenfrequenz 1 Hz. Die Konfiguration passt
syntaktisch zum Sender; die tatsächliche Rohdatenannahme bleibt offen.

**Deutung und kontrollierter Folgeschritt:** GSVmulti verband sich vor dem
Senderstart. Die Startreihenfolge ist deshalb eine plausible, noch
unbestätigte Ursache. Lauf 02 startet zuerst den Sender: endliches Fenster
mit 1200 Demowerten bei Zielrate 10/s, danach soll der Nutzer während
des aktiven Senders Connect klicken. Artefakte:
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-02/`. Dieser zweite
Lauf läuft noch; keine fertigen Ergebnisse angenommen. Falls weiterhin
Timeout erscheint, direkt auf Windows Rohdaten lesen, um elektrische
Strecke/Windows-Empfang von GSVmulti-Parsing zu trennen. Keine Freigabe
oder Latenzaussage aus dem synthetischen Versuch.

**Lauf 02 beendet:** Nutzer meldet erneut keine Zahlen und Timeout.
Pi-Sender nach 1044/1200 vollständigen Schreibvorgängen (11484 Bytes)
kontrolliert per SIGINT beendet, Hostprogrammlaufzeit 105,522084465 s.
Das Abbruchsignal dient der Diagnose und ist kein beobachteter UART-
Schreibfehler. `session.json` kennzeichnet dies als
`sender_stopped_for_diagnosis`. Zahlen in
[VALIDATION](VALIDATION.md#uart-demo-20261104-02).

Die Startreihenfolge allein ist als Problemlösung nicht bestätigt.
Als nächstes GSVmulti vollständig schließen (COM4 freigeben) und den
Windows-Port ohne Zahlenparser über PowerShell lesen. Ein begrenztes
Empfangsfenster wird vor dem nächsten Pi-Sender geöffnet. Kein weiterer
Sendeversuch, solange diese Empfangsbereitschaft fehlt.

---

## 2026-11-04 — UART-Demo 03: Rohdaten isolieren

**Vorbereitung:** Der erste Versuch, COM4 in PowerShell zu öffnen, scheiterte
mit UnauthorizedAccessException. Die vom finally-Block ausgegebenen
0 Bytes sind deshalb kein Null-Empfangs-Messresultat. Nach Schließen von
GSVmulti meldet der Nutzer den Port als offen.

**Aufbau:** GSVmulti geschlossen, Windows PowerShell liest COM4 als Bytes,
115200/8N1/Handshake aus. Nutzer bestätigt weiterhin die Zwei-Jumper-
Verbindung. Pi sendet erst nach gemeldetem geöffneten Windows-Empfänger.

**Ergebnis:** 600 vom Pi-Treiber angenommene Telegramme, 6600 Bytes,
Hostprogrammlaufzeit 63,891135362 s. Nutzer kopiert die ersten Hex-Lese-
häppchen. Deren Zusammenfügen ergibt exakt sechs erwartete Telegramme
`%-000.300` bis `%-000.295`, jeweils CRLF, und ein weiteres Präfix %.
Gesamtmenge des Windows-Empfangs unbekannt. Zahlen und Beleggrenzen:
[VALIDATION](VALIDATION.md#uart-demo-20261104-03).

**Deutung:** Der physische/serielle Pfad liefert für diese Proben die richtigen
Bytes nach Windows. Separat ausgegebene Präfix-/Zeilenendbytes sind normale
Read-Chunks und kein Beleg für falsches Framing. Warum GSVmulti weiterhin
Timeout zeigte, ist noch offen. Nächster kontrollierter Vergleich: Nach
Beenden des PowerShell-Empfangs im UserDefined-Dialog nur Filter Out
Non-Numeric einschalten, %/ein Wert/COM4/115200 unverändert lassen.
Noch kein Filter-Test ausgeführt und keine erfolgreiche GSVmulti-Übernahme
angenommen.


---

## 2026-11-04 — UART-Demo 04: Erster sichtbarer GSVmulti-Zahlenempfang

**Aufbau:** Gleiche gemeldete Zwei-Jumper-Strecke Pi ttyAMA0 TX/GND zum
FTDI-Adapter COM4. GSVmulti 2.03 Pro, UserDefined, 115200/8N1, Präfix %,
ein Wert/Position 1. PowerShell gibt den Port frei. Als Einzelvariable wird
Filter Out Non-Numeric eingeschaltet; Nutzer meldet Bereitschaft, dann
startet der Pi-Sender vor dem angeforderten Connect.

**Ergebnis:** Endlicher synthetischer Lauf mit 600 Pi-Treiberschreibvorgängen,
6600 Bytes und 60,519593368 s Hostlaufzeit (HOST_MONOTONIC). Nutzer meldet
„ja jetzt kommt was an“; Screenshot zeigt −0,134500. Gezeigte Datenfrequenz
weiter 1 Hz, Einheit leer. Screenshot, Setup und Sendelog im Laufverzeichnis
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-04/` gesichert.
Zahlen und Beleggrenzen: [VALIDATION](VALIDATION.md#uart-demo-20261104-04).

**Deutung:** Sichtbarer Empfang ist bestätigt. −0,134500 ist kein gesendeter
Einzelwert der 0,001-Rampe. Laut Herstelleranleitung S. 34 werden schnelle
Werte für numerische Anzeigen auf vier Anzeigen/s gemittelt; dies ist eine
passende Erklärung, noch kein Nachweis des konkreten Fensters. Keine
zusätzliche Glättung im Sender einführen. Unveränderte gespeicherte Werte
und Rate müssen durch eine Aufzeichnung ohne Datenreduktion geklärt werden
(OQ-50); aus dem Screenshot weder Empfangsanzahl noch Verluste ableiten.
Der Sender ist nach den 600 Telegrammen beendet. Ein späterer Timeout ist
bei beendetem Datenstrom erwartbar, sein tatsächliches Auftreten wurde
nicht beobachtet. Keine reale DUT-Messung oder Freigabe.


---

## 2026-11-04 — UART-Demo 05: Aufzeichnung zum Einzelwertvergleich

**Vorbereitung:** Nutzer-Screenshots zeigen Start/Ende der Aufnahme manuell
und Data Reduction = Record every value. Auto Export war im Screenshot noch
ausgeschaltet. Danach wurde Enable Auto-Export, Text file (tab separator)
und ein Zielordner angeleitet; Nutzer meldet „bereit“. Die resultierende
Exportkonfiguration ist nicht unabhängig gezeigt. Kein Hardwareumbau.

**Durchführung:** Gleiche endliche synthetische Rampe wie Lauf 04, 600 Werte
mit Zielrate 10/s über ttyAMA0, 115200/8N1, kein Handshake. Empfänger wird
zum Verbinden und Start Measuring / Start Recording aufgefordert. Sende-
und Empfangsaufzeichnung beginnen daher nicht nachgewiesen gleichzeitig;
ein fehlender Anfang ist getrennt von Verlusten während der Aufnahme zu
bewerten. Kein Nachliefern von Messwerten als vermeintlich aktuelle Daten.
Artefakte und Setup-Screenshots unter
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-05/`.
**Senderabschluss:** 600/600 Telegramme und 6600 Bytes Pi-seitig angenommen,
Hostlaufzeit 60,398420834 s (HOST_MONOTONIC), regulär beendet. Nutzer zum
Stop Recording, danach Stop Measuring und Übermitteln der exportierten
TXT-Datei aufgefordert. Aufnahmestart und Export noch unbestätigt.
[Zahlen](VALIDATION.md#uart-demo-20261104-05). Kein Einzelwert-, Zeitachsen-
oder Latenznachweis allein aus dem Senderlauf.


**Auswertung der Nutzerdateien, 2026-11-04:** TDMS, Index und TXT aus Lauf 05
sind eingegangen und im Laufverzeichnis mit Hashes gesichert. Einmaliges
Analysewerkzeug npTDMS 1.13.0 als Wheel geladen und über sys.path importiert;
keine Änderung der Projektumgebung oder Debian-NumPy. Reproduzierbares
Rezept `var/diagnostics/gsvmulti/analyze-recording-05.py` mit Assertions
und maschinenlesbarem Ergebnis `recording-comparison.json`.

TXT und TDMS enthalten identische 420 Werte, −0,120 bis +0,299. Diese
entsprechen exakt den Senderindizes 180–599, ohne Lücken, Duplikate oder
Zahlenänderung. Negative Werte, Null und positive Werte sind enthalten.
Der spätere manuelle Aufnahmestart passt zum fehlenden Anfang; die genaue
Startgrenze ist unbestätigt. Die Metadaten bestätigen GSVmulti 2.03 Pro,
keine Aufnahmedezimierung, Skalierung 1 und noch keine Einheit.

Die Aufnahme bewahrt diese Rampenwerte trotz gemittelter Zahlenanzeige.
Abrupte Sprünge sind damit noch nicht geprüft. Zeitachse separat:
Wellenformintervall 0,10240713017714835 s, Frequency-Metadatum weiterhin
1 Hz. Exportspanne 42,908590 s, Pi-Schreibereignisspanne gleicher Werte
42,160910364 s (HOST_MONOTONIC). Differenz ist kein Transportlatenzmaß;
GSVmulti-Zeitrekonstruktion und Synchronisierung sind nicht nachgewiesen.
OQ-50 auf teilweise geklärt gesetzt; DUT-Ausgabe bleibt gesperrt.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-05).


---

## 2026-11-04 — UART-Demo 06: GSVmulti-Datenfrequenz als Einzelvariable

**Konfiguration:** Change Data Rate-Screenshot zeigte 1 Wert/s. Nutzer
stellt nach Anleitung auf 10 und bestätigt „ja jetzt ist 10hz eingetragen“.
Die resultierende Einstellung ist als Nutzerrückmeldung gesichert, noch
nicht im neuen Export unabhängig bestätigt. Kein Hardwareumbau. Konfig-
Snapshot und ursprünglicher Dialog im Laufverzeichnis von Demo 06.

**Versuch:** Gleiche 600-Werte-Rampe wie Demo 05 bei Pi-Zielrate 10/s,
115200/8N1 auf ttyAMA0. Nur GSVmulti-Datenfrequenz soll sich ändern;
Filter, Record every value und Text-Auto-Export unverändert angeleitet.
Sender vor Connect / Start Measuring / Start Recording gestartet.
Genaue Aufnahmegrenze weiterhin unbestätigt. Die zuvor angekündigte
Sprungfolge folgt separat, damit der Zeitvergleich nur eine Variable ändert.
Lauf unter `var/diagnostics/gsvmulti/uart-direct-demo-20261104-06/`.
**Senderabschluss:** 600/600 Telegramme, 6600 Bytes, 60,575376702 s
Hostlaufzeit (HOST_MONOTONIC), regulär beendet. Bytefolgen aller 600 Werte
per Assertion identisch zu Lauf 05. Nutzer zum Stop Recording, danach
Stop Measuring und Übermitteln neuer TXT-/TDMS-Dateien aufgefordert.
[Zahlen](VALIDATION.md#uart-demo-20261104-06). Export noch nicht vorhanden;
keine Zeitachsenkorrektur oder Latenz behauptet.


**Nutzerexport aus Lauf 06 ausgewertet:** TXT und TDMS enthalten 467 Werte
von −0,167 bis +0,299, exakt die Senderindizes 133–599. Keine Lücken,
Duplikate oder Zahlenänderungen; Frequenzmetadatum 10 Hz bestätigt.
Dateien und Hashes gesichert, Rezept `analyze-recording-06.py` und Berichte
`recording-comparison.json`/`rate-comparison.json` im Diagnoseverzeichnis.
[Zahlen](VALIDATION.md#uart-demo-20261104-06).

Zeitachse weiter abweichend: GSVmulti-Spanne 48,198790 s gegenüber
47,088755820 s Pi-Schreibereignisspanne gleicher Werte (HOST_MONOTONIC),
Differenz 1,110034180 s. Metadaten weiterhin dt mode=tf. Herstelleranleitung
S. 73–74/155 erklärt dt aus Start, Ende und Werteanzahl; Formel gegen TDMS
innerhalb 1e-8 s bestätigt. Damit ist verständlich, weshalb Frequency=10
nicht automatisch dt=0,1 s bewirkt. Konkrete Ursache der Spannenabweichung
und echte Einzelwertzeitpunkte sind weiter ungemessen. Keine zusätzliche
Mittelung, Rateänderung oder Zeitkorrektur vorgenommen. Nächster Schritt:
Advanced-Reiter der Aufnahmekonfiguration zeigen lassen, Zeitmodus prüfen.
Sprungtest separat; DUT-Ausgabe bleibt gesperrt.


---

## 2026-11-04 — UART-Demo 07: Abrupte Sprünge und nominelles Zeitraster

**Vorbereitung:** Advanced-Screenshot bestätigt Auto-Select aktiv,
Calculate dt from Final time gewählt, Replace Missing Values aus. Danach
Auto-Select aus, Use device data rate, Resulting dt=0,1 s und OK angeleitet.
Nutzer meldet „bereit“; resultierende Einstellung noch nicht unabhängig
gezeigt. GSVmulti-Frequenz 10 Hz aus Lauf 06 bestätigt. Kein Hardwareumbau.

**Versuchsaufbau:** Lokales, als Wegwerf-Messrezept abgelegtes
`var/diagnostics/gsvmulti/send-uart-step-demo.py`; keine Produktcodeänderung.
Vorab In-Memory-Prüfung: 600 Telegramme/6600 Bytes, acht direkte Übergänge,
alle Formatter-Bytefolgen korrekt. Echter UART-Lauf 07 danach gestartet:
200 Werte 0 als Vorlauf, anschließend acht Blöcke zu je 50 Werten:
−0,250 → +0,750 → 0 → −0,125 → +0,500 → −0,500 → 0 → +0,250.
Zielrate 10/s; tatsächliche Pi-Schreibereignisse mit HOST_MONOTONIC
protokolliert, Ausgangszeitbasis SYNTHETIC. Gleicher ttyAMA0/115200/8N1-Pfad.

**Prüfziel:** Gespeicherte Sprünge ohne Zwischenwerte und Blocklängen gegen
Sendelog vergleichen; neues nominelles Zeitschema getrennt prüfen. Ein
festes 0,1-s-Raster gilt ausdrücklich nicht als gemessene Aufnahmezeit oder
Latenz. Sender vor Start Measuring / Start Recording; genaue Aufnahmegrenze
unbekannt. Setup-Screenshot, Fixture-Smoke und Metadaten unter
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-07/`.
**Senderabschluss:** 600/600 angenommene Telegramme, 6600 Bytes,
60,345691839 s Hostlaufzeit (HOST_MONOTONIC). Blockwerte und -längen
sowie alle acht direkten Übergänge im Sendelog per Assertion bestätigt.
Nutzer zum Stop Recording, danach Stop Measuring und Übermitteln neuer
TXT-/TDMS-Dateien aufgefordert. Empfang und Sprungtreue noch offen.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-07).
Reale DUT-Ausgabe bleibt gesperrt.


**Auswertung Lauf 07, 2026-11-04:** Nutzer übermittelt TXT, TDMS und Index.
Originale mit Hashes gesichert; `analyze-recording-07.py` prüft den ganzen
Werteabschnitt und die Übergänge. Eine zunächst fehlgeschlagene Assertion
im lokalen Analyserezept verglich Dezimal-Textdarstellungen statt Zahlen
(z.B. −0,250 gegenüber −0,2500000). Auf numerischen Decimal-Vergleich
korrigiert; die vollständige Auswertung besteht danach. Kein neuer
Sendeversuch und keine Änderung an Messdateien oder Produktcode.

446 Werte entsprechen exakt den Senderindizes 154–599: 46 Nullwerte aus
dem Vorlauf, dann alle acht Blöcke zu genau 50 Werten. Alle acht Sprünge
direkt erhalten, keine zusätzlichen Zwischenwerte; TXT und TDMS stimmen
mit dem Sender überein. Nominales dt=0,1 s, Frequency=10 Hz und dt mode=1/f0
sind im Export bestätigt. Quellzeit-/Latenznachweis bleibt ausgeschlossen.
Nominelle Exportspanne 44,5 s gegenüber 44,765583329 s der entsprechenden
Pi-Schreibereignisse (HOST_MONOTONIC). Konstante Plateaus erlauben keinen
Nachweis gegen kompensierende Verlust-/Wiederholungsereignisse.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-07).

**Weiteres Vorgehen:** Direkter UserDefined-Import und gespeicherte
Sprungtreue sind für diese synthetischen Tests belegt. Als nächstes
Ungültig-/Altwertverhalten beobachten und testen, danach Puffernachlauf
und Wiederanlauf; Einheit und gemeinsame Windows-Brücke weiter offen.
Kein Sender aktiv, reale DUT-Ausgabe unverändert gesperrt.


---

## 2026-11-04 — UART-Demo 08: Datenpause und Wiederanlauf

**Aufbau:** Nutzer meldet Bereitschaft zum Ausfalltest. Gleiche gemeldete
UART-Strecke ttyAMA0 → COM4, 115200/8N1; GSVmulti 2.03 Pro, 10 Hz und
nominelles dt=0,1 s aus Lauf 07. Aufzeichnung jeder Zahl und Text-Auto-Export
unverändert angeleitet. Kein Kabel abziehen, keine manuelle Neuverbindung;
Messung/Aufzeichnung während der Pause weiterlaufen lassen.

**Stimulus:** Wegwerf-Rezept `var/diagnostics/gsvmulti/send-uart-outage-demo.py`:
300 frische synthetische Werte +0,250, dann 30 s absichtlich keinerlei
UART-Bytes bei offenem Pi-Port, danach 200 neue Werte −0,750. Keine
NaN-/Ersatzwerte, keine nachgelieferte Historie. Dieses isoliert ausgelassene
Senden ist kein Test eines echten DUT-Invalidierungspfads oder der gemeinsamen
Windows-Brücke. Zielrate bei aktivem Senden 10/s. Quelle SYNTHETIC;
Pi-Schreib-/Pausenmarken HOST_MONOTONIC mit unbekannter Quellzeitunsicherheit.

**Vorprüfung:** In-Memory-Bytefolge 500 Telegramme/5500 Bytes, Wartefolge
300×0,1 s, 30 s, 200×0,1 s und fünf Phasenmarker korrekt. Echte Wartezeiten
nicht in dieser Vorprüfung gemessen. Danach echter UART-Lauf 08 gestartet,
Sender vor Start Measuring / Start Recording. Phasen separat in
`phase-events.jsonl`, Zahlen in `tx.jsonl` unter
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-08/`.
Nutzer soll Timeout/Meldungen während der Pause sichern und Einstellungen
unverändert lassen. Empfang und Altwertmarkierung noch offen. Ein verdichtetes
nominelles Raster wäre kein gültiger Zeitbeleg für die Datenpause. Reale
DUT-Ausgabe bleibt gesperrt.


**Senderabschluss Lauf 08:** Regulär 500/500 Telegramme, 5500 Bytes,
80,823739876 s Hostlaufzeit. Phasenmarker belegen 30,000983790 s Pause
ohne Pi-Schreibereignis; Abstand letztes vorheriges/erstes folgendes
Schreibereignis 30,102895564 s (je HOST_MONOTONIC). Keine Zahl während der
Pause gesendet, weder letzte gültige Zahl noch Ersatz- oder NaN-Wert.

**Nutzerbelege:** TXT, TDMS, Index und Screenshot archiviert. Screenshot
zeigt timeout! bei Recording started. Nutzer bestätigt die Fortsetzung
auf −0,750 ohne manuellen Eingriff. Beide Dateien enthalten die gesamte
Zahlenfolge: 300× +0,250, danach 200× −0,750; kein zusätzlicher Zahlenwert.
Auswerterezept `var/diagnostics/gsvmulti/analyze-recording-08.py` besteht.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-08).

**Befund zur Zeitachse:** Der Übergang von +0,250 auf −0,750 liegt im TXT
nur 0,1 s auseinander. Alle 500 Werte liegen auf 49,9 s nominellem Raster,
während die Pi-Schreibereignisspanne 80,721821120 s (HOST_MONOTONIC) umfasst.
Die Datenpause hat im hochgeladenen Messkanal weder einen Zeitabstand noch
eine Ungültigmarkierung. Sichtbarer Timeout und automatisches Weiterlaufen
reichen somit nicht für korrekte Kalibrierdaten. Das ist beobachtetes
Verhalten, kein nachgewiesener Fehler der serialen Byteübertragung.

**Entscheidung für weitere Diagnose:** Keine reale DUT-Ausgabe freigeben.
Omit/Senderpause allein erfüllt die Anforderung an die gespeicherten Daten
in dieser Konfiguration nicht. Explizite Ungültigmarkierung als getrennten
synthetischen Versuch prüfen; Annahme von NaN noch unbekannt. Kein Ersatzwert
0 und kein Wiederholen des letzten gültigen Werts. Timeout-Verzögerung,
Altwertanzeige vor Timeout, Kabel-/Prozessausfall und gemeinsame Brücke bleiben
offen. Kein Sender aktiv und keine neue Hardwareänderung.


---

## 2026-11-04 — UART-Demo 09: Explizite NaN-Probe

**Vorbereitung:** Nach Befund der verdichteten Datenpause meldet Nutzer
Bereitschaft zur NaN-Probe. GSVmulti 2.03 Pro, COM4/115200/8N1, Filter Out
Non-Numeric ein, Record every value, 10 Hz und nomineller Zeitmodus 1/f0
unverändert angeleitet. Kein Hardwareumbau oder Produktcode geändert.

**Stimulus:** Wegwerf-Rezept `var/diagnostics/gsvmulti/send-uart-nan-demo.py`:
300 gültige synthetische Werte +0,125, 200 synthetische UNREADABLE-Datensätze
mit value=None, Ablehnungsgrund und Konfidenz 0, danach 200 neue gültige
Werte −0,625. Bestehender UserDefinedFormatter mit demo=True und SEND_NAN
formatiert die ungültigen Datensätze zu %NaN\r\n. Kein Ersatzwert und keine
Wiederholung des letzten gültigen Werts; NaN-Annahme nicht vorausgesetzt.
Alle Abschnitte mit Zielrate 10/s. Quelle SYNTHETIC; Sende-/Phasenereignisse
HOST_MONOTONIC. Kein Test einer echten DUT-Invalidierung.

**Vorprüfung:** In-Memory exakt 700 Telegramme/6700 Bytes, davon 200
UNREADABLE-NaN-Telegramme. Phasenfolge und Wartefolge geprüft, reale
Wartezeiten nicht in dieser Vorprüfung gemessen. Echter UART-Lauf 09
anschließend gestartet; Nutzer zum Start Measuring / Start Recording und
zu Screenshots während NaN aufgefordert, keine manuelle Neuverbindung.
Artefakte unter `var/diagnostics/gsvmulti/uart-direct-demo-20261104-09/`.
Empfang, Darstellung, exportierte Markierung und Fortsetzung noch offen;
reale DUT-Ausgabe bleibt gesperrt.


**Senderabschluss Lauf 09:** Regulär 700/700 Telegramme, 6700 Bytes,
70,865717076 s Hostlaufzeit (HOST_MONOTONIC). 200 NaN-Telegramme während
20,326734103 s NaN-Phase; Abstand letzter/erster gültiger Zahl 20,427649216 s
(HOST_MONOTONIC). Alle ungültigen Quelldatensätze haben value=None und
Ablehnungsgrund; bestehende Demo-Policy erzeugt den Telegrammtext.

**Nutzerbelege und Auswertung:** TXT/TDMS/Index und Screenshot gesichert;
Nutzer meldet Timeout während NaN, anschließend Weiterlesen ohne Lücke.
Beide Dateien enthalten nur 408 gültige Zahlen: 208× +0,125, 200× −0,625.
Kein NaN, unendlicher Wert oder großer Fehlwertmarker. Die 92 fehlenden
gültigen Anfangswerte passen zur späteren Aufnahme; genaue Grenze unbekannt.
Zwischen den Blöcken im Export 0,1 s, der ungültige Zeitraum fehlt vollständig.
Rezept `var/diagnostics/gsvmulti/analyze-recording-09.py` besteht.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-09).

**Deutung:** NaN funktioniert in dieser getesteten Zahlenfilter-Konfiguration
nicht als gespeicherte Ungültigmarkierung. Daraus keinen universellen
NaN-Ausschluss ableiten; Parser-/Filterursache nicht isoliert. Reale DUT-
Ausgabe bleibt gesperrt. Keine echten Quellzeiten aus dem nominellen Raster.

**Weitere Diagnose:** Herstelleroption Replace Missing values laut Anleitung
S. 74 prüfen, bei der GSVmulti selbst per Timeout-Zählung 1E+300 als Marker
in die Aufnahme einfügen soll. Neue offene Frage OQ-51 angelegt. Wirkung bei
UserDefined und rechtzeitige Abgrenzung der Ungültigkeit unbewiesen. Nur diese
Empfängeroption ändern, dieselbe NaN-Sendefolge beibehalten. Vergleichsrezept
`send-uart-replace-missing-demo.py` vorbereitet, noch nicht gestartet.
Keine neue Formatkonvention im Sender erfunden, keine Markerzahl als echten
Wert freigegeben. Kein Sender aktiv, keine neue Hardwareänderung.


---

## 2026-11-04 — UART-Demo 10: Replace Missing Values als Einzelvariable

**Vorbereitung:** Nutzer meldet Bereitschaft nach Anleitung, ausschließlich
Replace Missing Values unter Configure Recording → Advanced zu aktivieren.
Resultierender Checkbox-Zustand nicht unabhängig gezeigt. Filter, 10 Hz,
nomineller Zeitmodus 1/f0, Record every value und Text-Auto-Export sollen
unverändert bleiben. Keine Hardwareänderung; reale DUT-Ausgabe gesperrt.

**Versuch:** Gleiches Sendeschema wie Lauf 09: 300 gültige +0,125,
200 synthetische UNREADABLE-Datensätze über bestehenden demo-only Formatter
als %NaN\r\n, danach 200 gültige −0,625. Aktive Zielrate 10/s. Quelle
SYNTHETIC; Sender-/Phasenereignisse HOST_MONOTONIC. Keine vom Pi gesendeten
1E+300-Marker und keine erfundene Telegrammänderung. AST der Fixture-
Konstante und Sendefunktion ist identisch zum Rezept von Lauf 09, geprüft.

Echter UART-Lauf 10 gestartet, Nutzer zu Start Measuring / Start Recording,
Screenshot während NaN und unverändertem Weiteraufzeichnen aufgefordert.
Rezept `var/diagnostics/gsvmulti/send-uart-replace-missing-demo.py`;
Artefakte unter `var/diagnostics/gsvmulti/uart-direct-demo-20261104-10/`.
Marker, Anzahl, Lage, Zeitraster und Fortsetzung erst nach Export beurteilen.
Keine Gültigkeits-/Latenzbehauptung aus einem Marker oder nominellem Raster.


**Senderabschluss Lauf 10:** Regulär 700/700 Telegramme, 6700 Bytes,
70,501553623 s Hostlaufzeit. NaN-Phase 20,086055080 s, Abstand letzter/
erster gültiger Zahl 20,186442122 s (HOST_MONOTONIC). Vollständige 700er-
Payloadfolge bytegleich zu Lauf 09 geprüft; keine neue Markerzahl gesendet.

**Nutzerbelege:** TXT/TDMS/Index und Screenshot archiviert. Nutzer meldet
Timeout während NaN und stehenden Recorder-Graphen. Nach gezielter Nachfrage
prüft er die Checkbox und bestätigt „Ja, der Haken ist gesetzt“. Somit ist
Replace Missing Values für diesen Versuch als aktiv zurückgemeldet, nicht
mehr nur angeleitet. Es gibt kein neues Bild der Checkbox; die Bestätigung
ist als Nutzerrückmeldung im Setup und Auswertebericht gespeichert.

**Auswertung:** 428 identische gültige Werte in TXT/TDMS: 228× +0,125,
200× −0,625. Keine NaN-, Inf- oder großen Fehlwertmarker. Abstand beider
Blöcke weiterhin 0,1 s, die NaN-Phase fehlt. Nominalspanne 42,7 s gegenüber
63,095700362 s Pi-Schreibereignisspanne gleicher gültiger Zahlen
(HOST_MONOTONIC). Nicht als Latenz interpretieren. Lokales Auswerterezept
`analyze-recording-10.py` besteht. [Zahlen](VALIDATION.md#uart-demo-20261104-10).

**Einordnung:** Die dokumentierte Empfängeroption erzielt in diesem
UserDefined-Test keinen beobachtbaren Effekt zur Erhaltung der Ungültigkeit.
Kein allgemeines Urteil über andere Geräte oder GSVmulti-Konfigurationen.
Nach Senderpause, NaN-Probe und gezieltem Optionenvergleich liegt ein
reproduzierbarer Grenzfall vor. Als nächstes technische Klärung mit GSVmulti-
Entwicklung anhand dieses Falls; kein weiterer Live-Test gestartet.
OQ-51 teilweise geklärt (negativer Versuch, Ursache/unterstützter Weg offen).
Reale DUT-Ausgabe bleibt gesperrt, kein Sender aktiv. Kein Kontakt versandt.

Lokales Belegpaket erstellt: `var/exports/gsvmulti-userdefined-invalid-2026-11-04.zip`, 183457 Bytes,
SHA256 `673ea914325b65226ab4da9a9365644a210bdbd46844daf8c6980a7b718d8453`. Enthält Läufe 08/09/10,
Originale, Screenshots, Logs, Rezepte und kurze technische Beschreibung.
ZIP-CRC und alle Manifest-SHA256 geprüft. Kein Kontakt und kein Upload.


---

## 2026-11-04 — Fortsetzung: Einheit als unabhängiger Abnahmepunkt

Nutzer möchte an der Anbindung weiterarbeiten. Arbeitsplan und aktive
TODO-Notiz an die zehn direkten UART-Versuche angepasst; offene Freigabeschranke
bleibt bestehen. Als nächster unabhängiger Punkt wird die bislang leere
Empfängereinheit geprüft. Nutzer bestätigt Unit bei gestoppter Messung/Aufnahme
als bedienbar. Anleitung: mV/V wählen, User Scaling=1 belassen und Session
unter neuem Namen sichern. Auswahl und Speicherung noch nicht zurückgemeldet.

Gültiges endliches Senderrezept `var/diagnostics/gsvmulti/send-uart-unit-demo.py`
vorbereitet (gleiche 600-Werte-Rampe wie Läufe 05/06), Syntax geprüft,
noch nicht gestartet. Danach Nutzer-TXT/TDMS gegen Zahlenfolge und Einheit
prüfen. Kein neuer Messlauf, kein Hardwareumbau, keine GSVmulti-Entwicklung
kontaktiert; reale DUT-Ausgabe weiterhin gesperrt.


---

## 2026-11-04 — UART-Demo 11: Einheit mV/V prüfen

**Vorbereitung:** Nutzer meldet Bereitschaft nach Anleitung Unit=mV/V,
User Scaling=1 und Save Session unter neuem Namen. Gewählte Einheit und
Sessiondatei noch nicht unabhängig gezeigt. Letzte bekannte Einstellungen:
10 Hz, 1/f0 nominell, Zahlenfilter ein, Record every value, Replace Missing
Values ein. Kein Hardwareumbau; reale DUT-Ausgabe bleibt gesperrt.

**Versuch:** Gleiche gültige 600-Werte-Rampe wie Lauf 05/06, −0,300 bis
+0,299, vorhandener send_demo und UserDefinedFormatter. Keine neuen
Formatregeln oder ungültigen Werte. Zielrate 10/s, ttyAMA0/115200/8N1,
Quelle SYNTHETIC; Sendeereignisse HOST_MONOTONIC. Sender vor angefordertem
Connect / Start Measuring / Start Recording gestartet. Genaue Aufnahmegrenze
unbekannt. Rezept `var/diagnostics/gsvmulti/send-uart-unit-demo.py`, Daten
unter `var/diagnostics/gsvmulti/uart-direct-demo-20261104-11/`.
Einheit, Skalierung und Zahlen erst anhand des Nutzerexports nachweisen;
kein Zeitaussage- oder Ungültigwertnachweis aus dieser gültigen Rampe.


**Senderabschluss Lauf 11:** Regulär 600/600 angenommene Telegramme,
6600 Bytes, 61,473499440 s Hostlaufzeit (HOST_MONOTONIC). Alle 600 Payloads
bytegleich zu Lauf 06 geprüft. Nutzer zum Stop Recording / Stop Measuring
und Übermitteln neuer TXT-/TDMS-Dateien sowie ggf. gespeicherter Session
aufgefordert. Einheit noch nicht im Export bestätigt.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-11).
Kein Sender aktiv; echte DUT-Ausgabe bleibt gesperrt.


**Empfängerauswertung Lauf 11:** Nutzer liefert TXT, TDMS und gespeicherte
Session `svmulti-uart-mvv-test.ucf`. Originale/Hashes gesichert. Beide
Messdateien enthalten 510 exakt passende Werte −0,210 bis +0,299
(Senderindizes 90–599), ohne Lücken oder Duplikate im Ausschnitt. TDMS:
Scaling=1, unit_string und NI_UnitDescription jeweils mV/V. UCF ch1.Unit=mV/V,
COM4/115200 und Frequency=10 Hz. Unit ist damit in der Session persistiert;
ein Neuladeversuch ist nicht erfolgt. TXT enthält keine eigene Einheit.
[Zahlen](VALIDATION.md#uart-demo-20261104-11).

Auswerterezept `var/diagnostics/gsvmulti/analyze-recording-11.py` besteht.
Nominelle Exportspanne 50,9 s, zugeordnete Pi-Schreibereignisspanne
52,314450467 s (HOST_MONOTONIC); keine Aussage über Sensorzeit/Latenz.
Einheiten-Abnahmepunkt für gültige direkte UART-Demodaten belegt. OQ-01
für das akzeptierte gültige Einkanal-Zahlenprofil dieser Version geklärt;
Format bleibt provisorisch, native GSV-Spezifikation/NaN-/Zeitsemantik nicht
verallgemeinern. Reale DUT-Ausgabe wegen OQ-06/OQ-51 weiterhin gesperrt.
Kein Sender aktiv und keine neue Hardwareänderung.


---

## 2026-11-04 — UART-Demo 12: COM-Kanal schließen und öffnen

**Vorbereitung:** Nutzer bereit für Puffernachlauf-/Wiederanlaufprüfung.
Gleicher physischer ttyAMA0→COM4-Pfad; Kabel bleibt angeschlossen.
GSVmulti 2.03 Pro, mV/V/Skalierung1/10 Hz, nominell 1/f0, Zahlenfilter,
Record every value, Replace Missing Values zuletzt bestätigt. Keine neue
Hardwareverdrahtung. Reale DUT-Ausgabe bleibt gesperrt.

**Stimulus:** 900 eindeutige gültige synthetische Zahlen in drei Blöcken
zu 300 Werten bei Zielrate 10/s: +0,100..+0,399 vor Schließen,
−0,100..−0,399 während angefordertem geschlossenem Windows-Kanal,
+0,600..+0,899 ab Signal zum Öffnen. Pi sendet kontinuierlich, keine Pause,
keine Wiederholung und keine Rekonstruktion historischer Messungen.
Anleitung zum Kanalwechsel: Stop Recording → Stop Measuring → Device Close;
später Device Open → Start Measuring → Start Recording. Phasenmarker steuern
die Aufforderungen, tatsächliche Windows-Aktionsgrenzen bleiben ungemessen.

**Vorprüfung:** In-Memory 900 eindeutige Telegramme/9900 Bytes und vier
Phasenmarker korrekt. Anschließend echten UART-Lauf 12 gestartet.
Rezept `var/diagnostics/gsvmulti/send-uart-reopen-demo.py`; Artefakte unter
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-12/`.
Quelle SYNTHETIC, Pi-Schreib-/Phasenereignisse HOST_MONOTONIC. Alter wird
nicht aus künstlichen Quellzeitstempeln abgeleitet. Export nach Wiederöffnen
kann Altphasenwerte zeigen; ein leerer Befund schließt vor Aufnahmestart
bereits verarbeitete Altwerte nicht aus. Kein allgemeiner Frische-/Latenznachweis.


**Abschluss Lauf 12:** 900/900 eindeutige Telegramme, 9900 Bytes,
91,232970889 s Hostlaufzeit (HOST_MONOTONIC), regulärer Senderabschluss.
Nutzer bestätigt zunächst Kanal geschlossen, meldet danach, Öffnen bzw.
Aufnahmestart sei nicht möglich. Screenshot zeigt beim Öffnen Error
805306614/0x300000F6, MEGSV.DLL: Comport requested for opening is already open.
Aufrufkette Error Converter → GS Vactivate Extended → OpenDevice2.vi.
Nutzer meldet dies nach Device Close wie Channel Close; vollständiges
Beenden/Neustarten von GSVmulti ermögliche wieder die Verbindung.

**Bewertung:** Wiederanlauf ist fehlgeschlagen, Puffernachlaufversuch nicht
bewertbar. Tatsächliche Windows-Aktionszeiten ungemessen; insbesondere ist
das root-seitige Erfassen der Schließbestätigung kein Schließzeitpunkt.
Screenshot, Nutzerbericht und root-seitige Rückmeldemarker gesichert.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-12).

**Weitere Diagnose:** Neue OQ-52 für COM-/DLL-Lebenszyklus angelegt und
Index erzeugt. Hersteller-DLL-Dokumentation kennt denselben Fehlercode;
noch kein Beweis, ob der Windows-Port gehalten oder nur intern als offen
geführt wird. Externe PowerShell-Open/Dispose-Probe auf COM4 im Fehlerzustand
und nach vollständigem GSVmulti-Ende vorbereitet. Kein neuer Sender dafür
notwendig; keine Bytes schreiben, Probe schließt ihren eigenen Handle stets.
Bisher keine Windows-Probe ausgeführt, kein Sender aktiv, keine neue
Hardwareverdrahtung und keine reale DUT-Freigabe.


**Externe Portprobe im Fehlerzustand:** Nutzer meldet bei GSVmulti weiter
offen SerialPort.Open auf COM4 verweigert. finally wurde im interaktiven
PowerShell-Prompt separat als Befehl eingegeben und daher nicht erkannt;
Dispose im gelieferten Transkript nicht ausgeführt. Bestehendes Probeobjekt
explizit aufräumen lassen, GSVmulti vollständig beenden und dieselbe Probe
in einem &-Block wiederholen. Kein Eigentümerprozess oder Handle-Leak als
bewiesen behaupten; Vergleich nach Prozessende steht noch aus.
Diagnoseschnappschuss im Verzeichnis von Lauf 12 gesichert.
Kein Sender aktiv, keine weitere Hardwareänderung und keine reale Freigabe.


**Portprobe nach vollständigem Prozessende:** Nutzer meldet COM4 öffnen
erfolgreich. Dieselbe Open-Probe war zuvor bei weiter laufendem GSVmulti
nach Device/Channel Close verweigert. Vorher-/Nachher-Belege im Diagnose-
verzeichnis von Lauf 12 gesichert. Der Vergleich spricht für GSVmulti-/
Bibliotheks-assoziierte Port-Ressourcenverwaltung; genauer Handle-Besitzer
und interne Ursache noch unbewiesen. Kein neuer Senderlauf und keine neue
DUT-Freigabe. Probe schließt ihren eigenen Handle im finally-Block.

**Praktischer Stand:** Für weitere synthetische Versuche GSVmulti vollständig
beenden und mit gespeicherter Session neu starten, wenn nach Close der
Fehler auftritt. Das ist ein manueller Workaround, kein abgenommener
Wiederanlauf im selben Prozess. Der laufende GSVmulti-Prozess darf nicht
als von der eigenen Brücke automatisch reparierbar angenommen werden.

Port-Lebenszyklusbeleg separat gebuendelt: `var/exports/gsvmulti-userdefined-reopen-2026-11-04.zip`, 69379 Bytes,
SHA256 `096208994bc68d3a760b76861431ecf50466bb5876a7c198914b14bad8225ecf`. ZIP-CRC und Dateihashes geprueft;
inklusive Screenshot und externer Vorher-/Nachher-Portproben. Kein Versand.


---

## 2026-11-04 — Nutzerhypothese: NaN ohne Zahlenfilter prüfen

Nutzer schlägt vor, Filter Out Non-Numeric in der UserDefined-Definition
zu deaktivieren. Screenshot zeigt zunächst aktivierten Filter bei Präfix %,
einem Wert und unbenutztem Separator. Hypothese: Filter könnte NaN vor dem
Zahlenparser entfernen. Das ist nicht belegt; die Anleitung beschreibt
Textfilterung, aber keine zugesicherte NaN-Semantik. Erste Versuche ohne Filter
lieferten auch für gültige Zahlen Timeout; deshalb beide Annahmen trennen.

Vorbereitetes lokales Rezept `var/diagnostics/gsvmulti/send-uart-no-filter-nan-demo.py`
sendet dieselbe 700er-Folge wie Läufe 09/10. AST von Fixture und Sendefunktion
identisch geprüft. Nur Zahlenfilter soll sich ändern; Präfix %, ein Wert,
115200/8N1, 10 Hz, nominell 1/f0, mV/V/Skalierung1 und zuletzt bestätigtes
Replace Missing Values bleiben unverändert. Kein Sender gestartet.
Vorbereitungs-Snapshot `no-filter-nan-preparation.json` und ursprünglicher
Screenshot im Diagnose-Basisverzeichnis. Wegen OQ-52 vor erforderlicher
Neuverbindung GSVmulti vollständig neu starten und erst danach Definition
ändern, nicht versehentlich alte gespeicherte Definition wieder laden.

Prüfkriterien: Gültige Zahlen vor NaN empfangen; NaN explizit in TDMS/TXT
erhalten; nachfolgende gültige Zahlen fortgesetzt. Erfolg nicht allein aus
Anzeige oder Timeoutfreiheit ableiten. Reale DUT-Ausgabe weiter gesperrt.


---

## 2026-11-04 — UART-Demo 13: NaN ohne Zahlenfilter

**Vorbereitung:** Nutzer meldet Bereitschaft nach Anleitung, nur Filter Out
Non-Numeric auszuschalten. Der gelieferte Ausgangsscreenshot zeigte den
Filter noch aktiv; resultierender Zustand nicht unabhängig abgebildet.
Präfix %, ein Wert, 115200/8N1, 10 Hz, 1/f0, mV/V/Skalierung1, Record every
value und zuletzt bestätigtes Replace Missing Values unverändert angeleitet.
Kein Hardwareumbau und keine neue Formatkonvention.

**Durchführung:** Echter UART-Lauf 13 mit derselben 700er-Fixture wie 09/10
startet: 300 gültige +0,125, 200 demo-only %NaN aus synthetischen UNREADABLE-
Datensätzen, 200 gültige −0,625. Pi-Phasen-/Sendeereignisse HOST_MONOTONIC,
Quelle SYNTHETIC, keine Quellzeit-/Latenzbehauptung. Nutzer zu Start Measuring /
Start Recording aufgefordert; gültige Zahlenannahme im ersten Abschnitt
separat abgefragt, weil frühe Filter-aus-Versuche schon darauf Timeout zeigten.
Rezept `var/diagnostics/gsvmulti/send-uart-no-filter-nan-demo.py`, Daten unter
`var/diagnostics/gsvmulti/uart-direct-demo-20261104-13/`.
Senderabschluss und Empfangsbeobachtung folgen. Reale DUT-Ausgabe gesperrt.


**Abschluss Lauf 13:** Regulär 700/700 Telegramme, 6700 Bytes,
70,340202721 s Hostlaufzeit (HOST_MONOTONIC), NaN-Phase 20,078144215 s.
Alle 700 Payloads bytegleich zu Lauf 10 geprüft. Nutzer meldet zunächst
Timeout/keine Zahl bei gültigen +0,125 und bestätigt anschließend durchgehenden
Timeout über NaN und die abschließenden gültigen −0,625. Keine erfolgreiche
Empfängeraufzeichnung belegt. [Zahlen](VALIDATION.md#uart-demo-20261104-13).

**Einordnung:** Filter aus ergibt kein funktionierendes Zahlenprofil; Ursache
und NaN-Semantik sind dadurch nicht getrennt. Vor weiterem Senden aktuelle
geänderte UCF gegen erfolgreiche mV/V-UCF aus Lauf 11 vergleichen. Hypothese,
dass Filter NaN entfernt, bleibt unbewiesen. Ein weiterer UI-Vergleich
Binärpräfix 25 hex wurde als Möglichkeit genannt und als identisches Sender-
Rezept vorbereitet, nicht gestartet. % und 25 hex sind dasselbe Byte, ein
anderer interner Parserweg muss erst belegt werden; keine Wirkung behaupten.
Kein Sender aktiv und keine reale DUT-Freigabe.


**UCF-Vergleich zu Lauf 13:** Nutzerdatei `svmulti-uart-mvv-test2.ucf`
gegen erfolgreiche Session aus Lauf 11 verglichen. Exakt drei Unterschiede:
Unit mV/V → leer, Frequency 10 → 1, Separator 256 → 0. COM4/115200,
Input1, ein Kanal, Prefix37 und OpenFlags1073741824 unverändert. Originale,
Hashes und Vergleich unter `uart-direct-demo-20261104-13/` gesichert.
[Beleg](VALIDATION.md#uart-demo-20261104-13).

**Bewertung:** Neben der beabsichtigten Filteränderung wurden Rate und Einheit
zurückgesetzt; nur Filter als Variable ist daher nicht belegt. Das beweist
keine Timeout-Ursache. Separator kann eine zusammengesetzte Kodierung sein;
Bedeutung nicht gesichert und kein zusätzlich geändertes UI-Trennzeichen
daraus ableiten. Neue OQ-53 angelegt, Index erzeugt. Hersteller-DLL-Handbuch
und Produktseiten recherchiert, keine belastbare Zuordnung dieses UCF-Felds
gefunden. Zuerst aktuelle Filter-aus-Konfiguration auf 10 Hz/mV/V zurücksetzen,
neu speichern und UI/Datei vergleichen. Noch kein weiterer Senderlauf.


**Korrigierter UI-Stand nach Lauf 13:** Nutzer liefert drei Screenshots:
Filter Out Non-Numeric aus, Character Prefix %, ein Wert, Separator unused;
Add Channel COM4/115200, Position1; Datenfrequenz10 Hz. Bilder mit Hashes
unter `uart-direct-demo-20261104-13/receiver/`, Zusammenfassung
`corrected-ui-configuration.json`. Unit und Skalierung nicht sichtbar;
neue korrigierte UCF noch nicht geliefert. Kein weiterer Sender gestartet.
Vor Vergleich aktuellen Stand über Save Session sichern lassen.


---

## 2026-11-04 — Korrigierte Session und UART-Demo 14

Nutzer korrigiert erst Frequency auf10, dann Unit auf mV/V. Gleichnamige UCF-
Zwischenstände unter getrennten Namen archiviert. Jüngste UCF stimmt bis auf
Separator0 statt256 in allen Feldern mit der funktionierenden Lauf-11-UCF
überein; UI bestätigt Filter aus. OQ-53 für diese gepaarten Beobachtungen
teilweise geklärt, keine allgemeine Bitkodierung abgeleitet.

**Versuch 14:** Derselbe NaN-Sender wie Lauf 13; 700/700 Telegramme,
6700 Bytes, 70,365982680 s Hostlaufzeit, NaN-Phase 20,067549642 s
(HOST_MONOTONIC). Alle 700 Payloads identisch zu Lauf 10 geprüft. Nutzer
meldet zunächst keine gültigen +0,125 und bestätigt am Ende durchgehend
Timeout auch bei NaN und −0,625. Keine neue erfolgreiche Aufnahme belegt.
[Zahlen und Grenzen](VALIDATION.md#uart-demo-20261104-14).

**Einordnung:** Ohne Filter auch mit10Hz/mV/V kein brauchbarer Zahlenempfang.
Die NaN-Hypothese ist damit nicht isoliert bewiesen/widerlegt. Als positive
Gegenprobe bekannte funktionierende Session aus Lauf 11 nach vollständigem
GSVmulti-Neustart laden und identische 700er-Folge senden. So bleibt die
gespeicherte Konfiguration bis auf das Filter-assoziierte Rohfeld gleich.
Rezept `var/diagnostics/gsvmulti/send-uart-filter-on-control-demo.py` vorbereitet,
AST der Fixture identisch, kein neuer Sender gestartet. Keine reale DUT-Freigabe.


---

## 2026-11-04 — UART-Demo 15: Positive Kontrolle mit Filter ein

Nach Anleitung vollständiger GSVmulti-Neustart und ursprüngliche funktionierende
UCF laden meldet Nutzer bereit. Gleiche 700er-NaN-Fixture wie Lauf14 gesendet,
alle 700 Payloads bytegleich geprüft. 700/700 Telegramme, 6700 Bytes,
70,668683281 s Hostlaufzeit; NaN-Phase 20,336218894 s (HOST_MONOTONIC).
Nutzer bestätigt +0,125 im ersten Abschnitt. Danach liefert er TXT und TDMS.

**Auswertung:** Beide Dateien enthalten 440 identische gültige Zahlen:
240× +0,125 und 200× −0,625, exakt der gültige Senderrest ab Index60.
Kein NaN-/Inf-/großer Fehlwertmarker. TDMS bestätigt mV/V, Scaling1 und10Hz.
Zwischen den gültigen Blöcken erneut0,1 s, NaN-Intervall nicht erhalten.
Nominelle Spanne43,9 s gegenüber64,547879613 s der entsprechenden gültigen
Pi-Schreibereignisse (HOST_MONOTONIC). Keine Latenzaussage daraus ableiten.
Originale/Hashes, erwartete geladene UCF und Auswerterezept
`analyze-recording-15.py` gesichert. [Zahlen](VALIDATION.md#uart-demo-20261104-15).
Replace Missing Values ist diesmal nicht erneut unabhängig bestätigt;
keine aktuelle Checkbox-/Timeout-Abbildung geliefert. Bisherige explizite
Bestätigung bleibt auf Lauf10 begrenzt.

**Schluss für diese Profile:** Filter-ein-Kontrolle stellt gültigen Empfang
wieder her, Filter-aus-Profil14 hatte keine Zahlen geliefert. NaN-Hypothese
bleibt hinsichtlich interner Parserstufe offen, keine ausreichende
Ungültigbehandlung nachgewiesen. Reale DUT-Ausgabe bleibt gesperrt.

**Nächste gezielte Probe:** Dokumentiertes Zeichenpräfix A bei Filter aus,
sonstige Parameter wie Lauf14. Dadurch ändert sich erstmals das Präfixbyte
(37→65); möglicher Binär25-Vergleich hätte dagegen dasselbe %-Byte geliefert.
Eigener synthetischer Demo-Formatter im lokalen Rezept
`send-uart-A-prefix-nan-demo.py` delegiert Zahlenvalidierung an vorhandenen
UserDefinedFormatter und setzt nur das Präfix um. Formatänderung bleibt im
Formatter, keine Pipelineänderung und kein erfundenes natives GSV-Protokoll.
In-Memory 700 Telegramme/6700 Bytes korrekt, nichtsynthetische Eingaben
abgelehnt, provisional markiert. Vorbereitet, nicht gestartet. Zuerst neue
UCF prüfen, dann GSVmulti vollständig neu starten und neue Definition laden.


**A-Präfix-Session vor Sendetest geprüft:** Nutzer liefert
`svmulti-uart-mvv-test5.ucf`. Gegen die korrigierte Filter-aus-UCF aus Lauf14
verglichen: exakt ein Unterschied, UserDevice.Prefix37→65 (%→A).
Alle übrigen gespeicherten Felder gleich, insbesondere Separator0, 10Hz,
mV/V, COM4/115200 und ein Wert. Original mit Hash unter
`var/diagnostics/gsvmulti/A-prefix-verified-profile.ucf`, Vergleich im
`A-prefix-nan-preparation.json`. Kein A-Sender gestartet. Vor dem Versuch
vollständiges GSVmulti-Ende, Neustart und Laden genau dieser UCF anleiten;
so aktive Port-/Parserkonfiguration nicht aus bloßem Speichern voraussetzen.
Reale DUT-Ausgabe gesperrt.

---

## 2026-11-04 — UART-Demo 16 und Bibliotheksprovenienz

Unveränderter direkter Aufbau Pi-TX→FTDI-RX→Windows COM4. Geprüfte
A-Präfix-UCF nach angeleitetem vollständigem GSVmulti-Neustart laden lassen;
Nutzer meldet bereit. Filter aus, 10 Hz, mV/V. Eigenständiger synthetischer
Demo-Formatter ändert ausschließlich das Präfixbyte gegenüber Lauf14.
700/700 Telegramme, 6700 Bytes, 71,213798174 s Hostlaufzeit;
NaN-Phase 20,079974009 s (HOST_MONOTONIC). Alle 700 Payloads bis auf
0x25→0x41 bytegleich zu14 geprüft. Nutzer bestätigt Timeout sowohl bei
anfänglichen gültigen +0,125 als auch im gesamten Durchlauf. Kein Export
und kein erfolgreicher NaN-Empfang belegt. [Zahlen](VALIDATION.md#uart-demo-20261104-16).
Keine neue Hardwareänderung, kein Sender mehr aktiv, reale DUT-Ausgabe gesperrt.

**Herstellerquellen:** Öffentlich verlinktes MEGSV-x64-SDK ausschließlich
heruntergeladen und statisch gelesen, keine DLL ausgeführt oder installiert.
90989 Bytes, SHA256
`0eb6fae009525435c886a4a0cf7a693a0b833506661e45fae987b2d1ce31b389`.
Quelle: [Herstellerarchiv](https://setup.me-systeme.de/megsv/megsv_x64.zip).
Header Megsv.h nennt Version1.50 und Copyright1999–2009; darin keine
UserDefined-/Separator-/NaN-Spezifikation gefunden. Statische Exportliste
liefert ebenfalls keine belegte Erklärung des aktuellen Filterverhaltens.
Das Archiv ist nicht als die tatsächlich geladene GSVmulti-Bibliothek
identifiziert. Original/Index und statische Exportliste unter
`var/diagnostics/gsvmulti/manufacturer-megsv-x64/` gesichert.

**Nächster Schritt:** Neue OQ-54 zur Provenienz der tatsächlich geladenen
Bibliotheken. Lesender PowerShell-Befehl `Get-Process -Module -FileVersionInfo`
vorbereitet, noch nicht auf Windows ausgeführt. Die
[Microsoft-Dokumentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/get-process?view=powershell-5.1)
beschreibt beide Parameter. Versionsinventar allein beweist weder Parser-
Implementierung noch Port-Handle-Besitzer. Weitere UI-Varianten zunächst
zurückstellen, stattdessen belastbare Build-/Bibliotheksangaben erfassen.

---

## 2026-11-04 — Windows-Laufzeitversionen bestätigt, Logging recherchiert

Nutzer liefert fünf geladene GSV-Module mit Pfad, Datei- und Produktversion.
GSVmultichannel.exe2.3.4, MEGSV.dll1.62.0.64 (Produkt1.62.0.0),
MEGSV4w32.dll1.20.0.64, MEGSV86w32.dll1.48.1.64,
GSV86CAN.dll1.17.7.64. Basis C:\Program Files\GSV-Multichannel_v2.03,
DLLs unter data. Snapshot in
`var/diagnostics/gsvmulti/windows-loaded-modules-20261104/modules.json`.
[Inventar](GSVMULTI_PROTOCOL.md#geladene-gsv-bibliotheken), OQ-54 geklärt.
Versionsstrings allein identifizieren weder Parserzuständigkeit noch den
Port-Handle-Besitzer; keine DLL ersetzt/ausgeführt. Kein neuer Senderlauf.

Hersteller-Versionshistorie per Webquelle geprüft: ab2.02 dokumentiertes
LogLevel in ProgramData-Konfiguration, Stufe2 zusätzlich Treiberfehler;
Logausgabe C:\GSVmultiLog. Kein ausdrücklicher UserDefined-/NaN-Fix gefunden.
Direkter Archivdownload der Historie mit HTTP403 abgewiesen, daher keine
lokal archivierte Historie oder deren Hash behaupten. Webquelle und
Auswertungsgrenzen im Protokolldokument verlinkt. Nächste Windows-Abfrage
liest nur bisherigen LogLevel und vorhandene Logdateinamen; noch keine
Loggingänderung oder erfolgreiche Fehleraufzeichnung belegt.

---

## 2026-11-04 — Logging-Istzustand und Aktivierung vorbereitet

Nutzerabfrage der ProgramData-config.ini findet `[Config]`, aber keinen
aktiven LogLevel-Eintrag. Damit kein expliziter LogLevel belegt; tatsächliche
Defaultwirkung nicht separat gemessen. Logverzeichnis noch nicht abgefragt.
Snapshot `windows-loaded-modules-20261104/logging-state.json` unter Diagnosebasis.

Lokales Rezept `var/diagnostics/gsvmulti/enable-gsv-logging.ps1` vorbereitet,
noch nicht auf Windows ausgeführt: verlangt vollständig beendetes GSVmulti,
verweigert bei vorhandenem LogLevel oder uneindeutigem Config-Header, sichert
Original per eindeutiger Backup-Datei und fügt LogLevel2 unter Config ein.
Latin1 wird als reversible Byteabbildung verwendet, bestehende Datei-Bytes
bleiben bis auf ASCII-Einfügung erhalten; nicht erkannter Header (z.B. UTF16)
führt zum Abbruch ohne Änderung. Keine Projektabhängigkeit, kein Produktskript.
Danach bekannten funktionierenden Filter-ein-Stand laden und Close-/Reopen-
Fehler einmal protokollieren. Noch keine Aktivierung/Logdatei/Fehlerursache
bestätigt, kein Sender aktiv und echte DUT-Ausgabe weiter gesperrt.

**Logging-Konfigurationsänderung vom Nutzer bestätigt (2026-11-04):**
PowerShell meldet Gesetzt: [Config] LogLevel = 2 und Sicherung unter
`C:\ProgramData\MEsystemeGSVmulti\config.ini.bak-b150608fe39f457daf43f641c23bf967`.
Befehlserfolg als Nutzerbeleg gespeichert; keine unabhängige Dateirücklesung.
Neustart, Laden der bekannten %-Präfix-/Filter-ein-Session und tatsächliche
Logausgabe noch nicht bestätigt. Vor gezieltem Close-/Reopen-Versuch auf
Empfangsbereitschaft warten. Kein Sender aktiv, keine reale DUT-Ausgabe.

**Bereitschaft für Logging-Gegenprobe:** Nutzer meldet nach Anweisung zum
Neustart und Laden der bekannten %-Präfix-/Filter-ein-Session bereit.
Kein unabhängiger UI-/Konfigurationsrücklesebeleg. Einmaliges Device Close
und Wiederöffnen desselben Profils angeleitet, danach neueste Logdatei unter
C:\GSVmultiLog lesen, GSVmulti zunächst weiterlaufen lassen. Kein Sender
nötig; ohne Sendestrom ist Timeout allein kein Wiederöffnungsfehlerbeleg.
Ergebnis/Logausgabe stehen aus, Laufzeit-Logging noch nicht bewiesen.

---

## 2026-11-04 — Logging-Gegenprobe: Initialer Bufferfehler und gesperrte Wiederöffnung

User meldet Logdatei unter C:\GSVmultiLog und liefert deren letzte Zeilen
sowie Screenshot. LogLevel2 ist damit zur Laufzeit wirksam. Direkt nach
Open Session UserDevice COM4/Input1/Fdata10,000 wird0xFFFFFFFF in
GS Vclear Buffer.vi protokolliert. Später zweimal0x300000F6 in
GS Vactivate Extended.vi über OpenDevice2.vi/OpenSession.vi. Screenshot
bestätigt COM4 already open. Kein Sender aktiv, keine neue Hardwareänderung.
Die Aufzeichnung enthält keine explizite Close-/Deactivate-Zeile; fehlende
Zeile beweist keinen ausgebliebenen internen Aufruf. Zeittexte nur externes
Logformat ohne zugeordneten TimeBaseKind, keine gemessenen Intervalle.
[Zahlen und Grenzen](VALIDATION.md#userdefined-logging-20261104).

Herstellerreferenz für GSVclearBuffer geprüft (ältere GSV2/3-API). −1 ist
kein spezifischer Ursachenbeleg, Verbindung der Fehler nicht bewiesen.
Neue OQ-55, OQ-52 mit Loggingbeleg ergänzt. Nutzer bestätigt: Programm
startet ohne Kanal, Session wird von ihm geladen. Dies ermöglicht eine
Gegenprobe ohne Sessionladen: frisch starten, identisches UserDefined-Profil
über Add Channel anlegen, einmal Close und über Add Channel erneut anlegen,
Log vergleichen. Noch nicht ausgeführt. Kein Sender nötig und keine neue
Präfix-/Filtervariante. Reale DUT-Ausgabe weiter gesperrt.

Belege lokal zusammengestellt, Original-Logdatei nicht empfangen:
`var/exports/gsvmulti-userdefined-reopen-logging-2026-11-04.zip`,19198 Bytes,
SHA256 `55af774313dc71d3a0f0e8b50127a7e78076ce169b673bace07676886994b6d6`.
ZIP-CRC und alle Manifest-SHA256 geprüft. Enthält Logausschnitt, Screenshot,
Versionsinventar und Vergleichsanleitung; keine DLLs, kein Versand.

---

## 2026-11-04 — Add-Channel-Gegenprobe und Vergleichspaket für die Entwicklung

Nutzer liefert nach leerem Neustart ohne Sessionladen neuen Logausschnitt
und Screenshot: Einmal0xFFFFFFFF in GS Vclear Buffer.vi bei initialem Aufbau,
zweimal0x300000F6 beim Wiederöffnen über AddChannel_v5.vi/OpenDevice2.vi.
Damit treten beide Fehler auch direkt über Add Channel auf. Neues Log meldet
Fdata1,000, vorherige Session10,000; kein reiner Ein-Variablen-Vergleich und
keine Gleichheit aller aktiven Profile behauptet. Neue UCF nicht geliefert.
Keine explizite Deaktivierung im Ausschnitt, Ursache und Zusammenhang offen.
Kein Senderlauf, keine Hardwareänderung, keine neue DUT-Messung.
[Zahlen/Grenzen](VALIDATION.md#userdefined-addchannel-logging-20261104).

OQ-55-Titel auf allgemeinen UserDefined-Initialisierungspfad erweitert,
Status teilweise geklärt: Sessionladen als notwendige Bedingung widerlegt,
Fehlerursache weiter offen. OQ-52 ebenfalls mit Gegenprobe ergänzt.
Nutzer hat direkten Kontakt zur Entwicklung. Statt weiterer gleichartiger
Close-/Open-Versuche Vergleichspaket lokal erstellt, ohne Nachricht/Versand:
`var/exports/gsvmulti-userdefined-reopen-comparison-2026-11-04.zip`,39844 Bytes,
SHA256 `7b2dc934d014b2ebf938e7ff8b5a311af09e9cc1b6d9072e47c932af77176e6c`.
ZIP-CRC und12 Manifestdateien geprüft. Enthält beide Ausschnitte/Screenshots,
Versionen und bekannte alte UCF mit klarer Herkunftsgrenze. README fragt nach
Unterstützung von ClearBuffer für UserDevice, tatsächlichem Freigeben von
COM-Handle/interner Registrierung auf jedem Schließ-/Fehlerpfad und korrigiertem
Build/unterstütztem Wiederöffnen. Keine interne Ursache oder Reparatur behauptet.

---

## 2026-11-04 — Nutzer akzeptiert GSVmulti-Neustart als vorläufigen Workaround

Die GSVmulti-/MEGSV-Fehler können laut Nutzer aktuell nicht sofort behoben
werden und werden vorerst hingenommen. Vollständiger Prozessneustart vor
neuen Verbindungen bleibt Workaround; keine weiteren gleichartigen Close-/
Open-Reproduktionen. OQ-52/OQ-55 bleiben teilweise geklärt. Keine Änderung
an Hardware, Treibern oder Software und kein neuer Mess-/Senderlauf.

Nächste vorhandene Arbeitsplan-Etappe: gemeinsame Windows-Brücke, die beim
bisherigen direkten UART-Demopfad umgangen wurde. Voraussetzung ist ein
funktionierendes virtuelles COM-Portpaar; com0com meldet weiterhin Code52.
Dieses Hindernis zuerst gezielt diagnostizieren, danach gültige synthetische
Werte über TCP und separat UART durch die gemeinsame Brücke prüfen.
Ungültig-/Zeitsemantik und echte DUT-Ausgabesperre bleiben bestehen. Der
spätere extern abrufbare SSH-Bootstrap bleibt Ausbau nach funktionierendem
Grundaufbau (OQ-49). Noch kein neuer Treiber oder Ersatz empfohlen/installiert.

---

## 2026-11-04 — Nutzerfrage USB statt UART: Machbarkeit lesend geprüft

Lokales Modell Pi5 ModelB Rev1.1 bestätigt; Debian13/Kernel6.12.34,
kein Controller unter /sys/class/udc sichtbar. Bootkonfiguration nur gelesen
und als Snapshot mit Hash gesichert. dwc2-host-Zeile gehört zum cm5-Abschnitt,
nicht als aktive Pi5-Konfiguration interpretieren. Keine Hardware angefasst,
kein Modul geladen, keine Boot-/Strom-/Treiberänderung und kein Senderlauf.

Hersteller-OTG-Anleitung belegt Pi5-USB-C-Peripheral und CDC-ACM-Funktion,
Microsoft Usbser für geeignete CDC-Deskriptoren. Daraus ergibt sich als Option
Pi USB-C→Windows COM→GSVmulti, lokal ohne com0com und ohne GPIO-UART.
Windows-Enumeration und stabiler Betrieb mit Kamera/Peripherie ungetestet;
Stromversorgung des Pi über denselben USB-C-Anschluss ist vor Umbau zu klären.
Neue OQ-56 angelegt. [Quellen](GSVMULTI_PROTOCOL.md#usb-cdc-option).
Bisheriger Transportplan noch nicht geändert; GSVmulti-Fehler und fehlende
Ungültig-/Zeitsemantik werden durch einen USB-Wechsel nicht behoben.

---

## 2026-11-04 — USB-Umsetzung untersucht, X1201 schränkt Stromführung ein

Nutzer beauftragt Untersuchung, keine Installation. Nur lesend geprüft:
dwc2 builtin; libcomposite/usb_f_acm/g_serial vorhanden, configfs gemountet,
kein Gadget und kein UDC; ttyGS0-Getty disabled. CLI-Hilfe bestätigt vorhandene
endliche Demo über frei angegebenen com-port, ttyGS0 nicht geöffnet/getestet.
Firmwareabfragen get_throttled und usb_max_current_enable scheitern mit
fehlendem Zugriff auf vcio_gencmd; kein Strom-/Unterspannungsbefund behauptet.
Snapshots und ausführliche technische Einschätzung im Diagnoseverzeichnis.

Nutzer nennt SupTronics X1201 V1.1, Laden über UPS-eigenen USB-C, Produktion
eventuell ohne UPS. Exakter Hersteller untersagt zusätzliche Pi-USB-C-
Versorgung. Vorherige allgemeine Aussage UPS sei gute Ausgangslage dadurch
konkret eingeschränkt: keine normale PC-USB-Verbindung parallel zur UPS
freigegeben. USB2-VBUS-Blocker existieren, gewährleisten aber keine Gadget-
Erkennung; Hersteller nennt Einschränkung ausdrücklich. Kandidat erst prüfen,
kein Kauf oder Aufbau durchgeführt. Produktionsversorgung separat entscheiden.
OQ-56 teilweise geklärt; [Quellen/Details](GSVMULTI_PROTOCOL.md#usb-cdc-umsetzung).

Vorschlag: ein CDC-ACM-Gerät über ConfigFS, geprüfte Deskriptoren/Identität,
Windows-COM-Erkennung, vorhandene synthetische Demo und TXT/TDMS-Abgleich.
Legacy g_serial als Alternative, USB-Ethernet löst keinen direkten COM-Port.
Kein Produktcode, Bootparameter, Dienst oder Kernelmodul verändert, kein Reboot,
kein Sender aktiv. Laufende Referenz/Kamera unangetastet, echte DUT-Ausgabe
bleibt gesperrt. Eigene USB-Live-Konfiguration wäre spätere Änderung; bestehende
UART-Portbegrenzung nicht aufweichen. Versorgung vor Hardwaretest klären.

---

## 2026-11-04 — com0com wieder priorisiert, USB-Untersuchung zurückgestellt

Nutzer möchte zunächst com0com weiterverfolgen. Direkte USB-Option bleibt
ungeändert dokumentiert, kein Gadget aktiviert und keine Hardwareänderung.
Vor weiterem Installer-/Portnamenversuch zuerst Windows-PnP-Status und
zugeordnetes Treiberpaket (Version/Provider/INF/IsSigned/Signer) lesend erfassen.
Rezept `var/diagnostics/gsvmulti/com0com-driver-diagnosis-20261104/inspect-driver.ps1`
vorbereitet, Windows-Ausgabe noch offen. Danach konkrete CodeIntegrity-
Ereignisse korrelieren; Microsoft dokumentiert dort Signatur-Ladefehler.
IsSigned allein ist kein Beleg einer gültigen Windows-Kernel-Ladefreigabe.
Kein Treiber installiert oder entfernt, kein Neustart und keine Messung.

---

## 2026-11-04 — Aktives com0com-Paket als nicht signiert gemeldet

Nutzer liefert aktuelles Windows-Inventar: beide ROOT\COM0COM-Geräte0000/0001
melden CM_PROB_UNSIGNED_DRIVER, Service com0com. Zugeordnet ist jeweils
Version3.0.0.0, Provider Vyacheslav Frolov, INF oem234.inf, IsSigned=False,
Signer leer. Rohdaten als Nutzersnapshot unter
`var/diagnostics/gsvmulti/com0com-driver-diagnosis-20261104/user-driver-inventory.json`.
Das belegt aktuelle Metadaten, nicht Dateiintegrität oder konkreten
Zertifikat-/Katalogfehler. Nutzer nennt signiertes ZIP gleichen Versionsnamens;
welche enthaltene Installer-EXE ausgeführt wurde ist noch offen.

Originalarchiv vom offiziellen Projekt lesend heruntergeladen:475063 Bytes,
SHA256 `6e5d4359865277430d4ae88c73fb7e648a0ed8e81aea5002478179cfcb0bb0e1`.
Enthält Setup_com0com_v3.0.0.0_W7_x86_signed.exe und entsprechende x64-EXE.
Keine EXE ausgeführt/installiert, keine lokale Windows-Paketidentität daraus
behauptet. Öffentliche Signiert-Bezeichnung beweist keine Akzeptanz des
konkreten Windows11-Systems. Source-/Dateiliste gesichert.

Nächste lesende Abfrage vorbereitet: CatalogFile/DriverVer/Provider aus
aktiver oem234.inf sowie com0com-Treffer der letzten maximal2000 CodeIntegrity-
Ereignisse in7 Tagen, davon höchstens8 ausgeben. Leerer Ausschnitt ist kein
Beleg fehlender Ablehnung. Katalog- und eingebettete Dateisignaturen getrennt
bewerten; keine einzelne NotSigned-Angabe als vollständigen Katalognachweis
interpretieren. Noch keine Ereignisse oder INF-Datei gelesen, kein Treiber-
wechsel, keine Messung und kein Sender aktiv.

---

## 2026-11-04 — x86-Installer bestätigt, INF-Abfrage bricht ab

Nutzer bestätigt Setup_com0com_v3.0.0.0_W7_x86_signed.exe. Danach gelieferter
PowerShell-Fehler: C:\windows\INF\oem234.inf nicht gefunden. ErrorActionStop
bricht den kombinierten Block bereits dort ab; kein CodeIntegrity-Ergebnis
empfangen. Korrigierte unabhängige Logabfrage separat abgelegt. Das fehlende
INF beweist weder Deinstallation noch konkreten Treiber-/Signaturdefekt;
vorheriger CIM-Verweis bleibt als historischer Snapshot erhalten.

Beide Installer aus bereits gesichertem Originalarchiv mit7z nur als Daten
entpackt. PE-Header der enthaltenen com0com.sys gelesen: x86-Paket Machine014c,
x64-Paket8664. Beide enthalten com0com.cat; Vorhandensein ist kein Nachweis
aktueller Windows-Signaturakzeptanz. Kein EXE-/Treiber-Code ausgeführt und
keine neue Abhängigkeit installiert. Ergebnis/Hashes unter
`official-installer-architectures.json` im Diagnoseverzeichnis.

Der vom Nutzer gewählte Installer enthält somit einen32-Bit-Kerneltreiber,
der für Intel-Windows11 nicht passt. Microsoft dokumentiert, dass32-Bit-
Treiber auf64-Bit-Windows nicht unterstützt sind. Das beweist nicht die
Architektur der aktuell gebundenen Windows-Datei oder die vollständige
Ursache des Code52; auch IsSigned=False/fehlender INF-Pfad bleiben getrennte
Befunde. Nächster begründeter Korrekturschritt: x64-Signed-Installer desselben
Archivs normal ausführen, danach Geräte-/Paketstatus neu lesen. Keine
Zwangsentfernung anhand des alten oem234-Namens. Bei erneutem Fehler aktuelle
Paketzuordnung und unabhängige CodeIntegrity-Abfrage prüfen. Noch keine
korrekte Windows-Installation oder erfolgreiche virtuelle COM-Ports belegt.

---

## 2026-11-04 — Nach x64-Anleitung unverändertes Inventar und GUI-Warnung

Nutzer liefert erneut zwei Geräte mit CM_PROB_UNSIGNED_DRIVER sowie
Version3.0.0.0/oem234.inf/IsSigned=False/Signer leer. Auf Rückfrage berichtet
er wieder den Hinweis zur benötigten .NET2.0-GUI-Laufzeit. Das bestätigt
keinen laufenden Treiber und keine geänderte Paketzuordnung; expliziter
Treiberinstallations-Erfolg noch nicht gemeldet. Neuer Nutzersnapshot
`post-x64-inventory.json`, ältere Evidenz unverändert erhalten.

Öffentliches3.0.0.0-Quellarchiv nur lesend geladen und NSIS/install.nsi geprüft:
218810 Bytes, SHA256
`6751e911f73980b23cc878a456eb99d1dc6d0603c11c1d3ced109abe1c556380`.
AdviseDotNETVersion erzeugt den GUI-Hinweis und wird im öffentlichen Skript
von .onInstSuccess aufgerufen; LaunchSetup wählt bei fehlender Laufzeit
setupc.exe statt setupg.exe. Treiber-preinstall/update/infclean sind eigene
setupc-Aufrufe. Das stützt die Trennung von GUI-Laufzeit und Treiberstart;
NSIS-Erfolg ist kein Beleg für erfolgreiche Kernel-Ladefreigabe. Exakte
Übereinstimmung dieses Quellskripts mit2017-Signed-Binaries nicht bewiesen.
Nichts ausgeführt/installiert, keine zusätzliche Abhängigkeit.

Nächster Schritt sind unabhängige lesende Geräte-/Treiberdetails per PnPUtil,
registrierter Win32_SystemDriver-Pfad und CodeIntegrity-Ereignisse. Keine
weitere Neuinstallation oder .NET-Installation aus dem GUI-Hinweis ableiten.
INF-Dateilesen bleibt aus dem Protokollpfad entfernt. Hersteller-/Windows-
Signaturursache weiterhin offen; kein brauchbares virtuelles COM-Paar belegt.

---

## 2026-11-04 — CyberCircuits erkannt, aktive Datei scheitert an Integritätsprüfung

Nutzerdatei vollständig erhalten und mit SHA256 archiviert. PnPUtil erkennt
CyberCircuits als Signierer des bestbewerteten/installierten oem234.inf;
Gerät0000 meldet Code52/Problemstatus0xC0000428. Dienst Stopped, Dateipfad
C:\windows\system32\drivers\com0com.sys. Zweimal Ereignis3004 zum fehlenden
Dateihash im System; älteres3076 ausdrücklich nur Audit mit erlaubtem Laden.
[Beleg/Grenzen](VALIDATION.md#com0com-ci-20261104). Keine Latenz-/Intervallangabe
und kein Transporttest; externe Datumsstrings bleiben ohne Zeitbasenzuordnung.

Die zuvor statisch extrahierten Originaltreiber enthalten eingebettete
Signaturtabellen und öffentliche CyberCircuits-Zertifikate; nur Zertifikats-
subjekte/-aussteller per OpenSSL gelesen, kein Windows-Trust geprüft und
kein Treiber ausgeführt. Dies ist kein Beleg aktiver Windows-Dateiidentität.
SHA256 des offiziellen x64-Treibers liegt für Vergleich bereit. Nächste
Windows-Abfrage liest tatsächlichen64-Bit-Systempfad (bei32-Bit-PowerShell
über Sysnative), SHA256 und Authenticode-Status. Keine manuelle CatRoot-/
Zertifikats-/Registry-Reparatur aus der Hashfehlermeldung ableiten. Ursache
zwischen Dateibestand, Katalogzuordnung und Kernel-Vertrauen weiter offen.

---

## 2026-11-04 — Original-x64-Datei und gültige Authenticode-Signatur bestätigt

Nutzerhash der aktiven com0com.sys ist per Assertion exakt gleich dem
Original-x64-SHA256; Windows Authenticode meldet Valid/CyberCircuits.
Dateiidentität/Architektur damit geklärt, Code52 und tatsächliche Kernel-
Ladefreigabe nicht. [Beleg](VALIDATION.md#com0com-ci-20261104).
Original-Signerzertifikat statisch gelesen: gültig ab4.1.2016 bis26.1.2018;
Ablaufdatum allein ist wegen Signaturzeitstempel kein Ablehnungsnachweis.
Microsoft unterscheidet Authenticode und Kernel-Treibersignierungsrichtlinien.
Nächste reine Statusabfrage: Windows-Build, Secure Boot, DeviceGuard/HVCI.
Keine Schutzfunktion geändert, keine neue Installation oder Treiberladeprobe.

---

## 2026-11-04 — Schutzstatus bestätigt, anders signierter com0com-Kandidat vorbereitet

Nutzer liefert Windows11 Pro Build26200, SecureBoot=True, laufende VBS und
Speicherintegrität, CI-StatusEnforced. Kein Schutz geändert. Zusammen mit
Original-x64-Dateihash und AuthenticodeValid ist der Unterschied zur Kernel-
Zulassung belegt, nicht eine einzelne konkrete Ablehnungsregel. Microsofts
Treibersignierungsregeln als Ursachekandidat, Katalog-/Policyanteil nicht isoliert.

Recherche: Originalprojekt bietet weiterhin3.0.0.0, GitHub-Spiegel
sthomas69 liefert laut Release-Digest bytegleiches475063-Byte-Archiv. Kein
neuer Microsoft-zugelassener Build dort nachgewiesen. Vovsoft verlinkt auf
eigener Webseite eine andere com0com-Ausgabe im eigenen Repository. Nur
heruntergeladen und statisch entpackt. Kandidaten-x64-Treiber trägt
Christos-Nikolaou-Zertifikat ab13.6.2012, endet1.8.2014; Zeitstempel-/Windows-
Trust nicht geprüft. Mehrere PE-Sektionen anders, daher kein isolierter
Signaturtausch. Keine Aussage über HVCI-Funktion oder Windows11-Zulassung.
[Belege](VALIDATION.md#com0com-ci-20261104).

Ein vorbereiteter Abruf/Hash-Prüf-/Setup-Ablauf verwendet eindeutig neues
Tempverzeichnis und exakt geprüften Installer-SHA256, anschließend normalen
Administrator-Installer und erneutes PnP-Inventar. Bisheriges com0com zuvor
über normalen Uninstaller entfernen; Baseline-Installer und Diagnosesnapshots
bleiben erhalten. .NET-GUI-Warnung bleibt getrennt. Keine Zwangsentfernung
anhand alter INF-Dateien und keine Änderung an Windows-Schutzfunktionen.
Noch nicht auf Windows ausgeführt, kein Sender aktiv. Nach diesem gezielten
Buildvergleich nicht ohne neue Evidenz weitere Installer durchprobieren.

---

## 2026-11-04 — com0com meldet nach Buildvergleich Code0, COM5/COM6 vorhanden

Nach den Anweisungen zur normalen Entfernung des alten com0com und Installation
der Vovsoft-verlinkten Ausgabe liefert Nutzer sechs PnP-Geräte mit Code0.
Paar1: CNCA1=COM5, CNCB1=COM6. Code52 im aktuellen Snapshot überwunden;
welche genaue Richtlinie den alten Build blockierte, nicht isoliert.
[Beleg](VALIDATION.md#com0com-pnp-ok-20261104). Kein Agent hat auf Windows
Software ausgeführt. Aktueller Binärhash und Schutzstatus nach Installation
noch nicht erneut erfasst; keine unabhängige HVCI-Abnahme behaupten.

Nächster Windows-Test: GSVmulti geschlossen lassen, COM5/COM6 mit SerialPort
öffnen, Puffer leeren, bekannte ASCII-Demozeilen in beide Richtungen exakt
prüfen, beide Ports auch bei Fehlern in finally freigeben. Danach Dateihash
und aktuellen Schutzstatus lesen. Nur Porttest, kein GSVmulti-/Brücken-/
TCP-Nachweis und keine echte DUT-Ausgabe. COM5 vorläufig als spätere
Brückenseite, COM6 als GSVmulti-Seite vorgesehen; noch nicht in GSVmulti benutzt.

---

## 2026-11-04 — Portpaar funktional, Sicherheitszustand weiterhin aktiv

Nutzerprobe bestätigt je eine exakte ASCII-Zeile COM5→COM6 und COM6→COM5.
Port-Cleanup im vorbereiteten Script, kein GSVmulti beteiligt. SecureBoot=True,
Speicherintegrität läuft weiter, CIEnforced. Aktueller Treiberhash stimmt mit
Vovsoft-x64-Kandidat überein. [Beleg/Grenzen](VALIDATION.md#com0com-pair-ok-20261104).
Code52-Blocker somit für dieses Setup überwunden; keine allgemeine Windows-
Kompatibilität, kein Wiederanlauf-/Latenznachweis. Pi-Hardware unverändert.

Nutzer hat Windows-Brückenpaket noch nicht auf dem PC. Neues Diagnosepaket
mit COM5/COM6-README vorbereitet, Produkt-Pythondateien bytegleich zu aktuellen
Quellen, ZIP-CRC/Manifest geprüft. Bestehende SSH-Verbindung läuft über die
Tailscale-Adresse des Pi; dafür SCP-Transfer und Python3.15-venv mit
--system-site-packages/pyserial3.5 --no-deps vorbereitet, zunächst nur --help.
Keine öffentliche Veröffentlichung oder fertiger extern gehosteter Bootstrap
(OQ-49). Noch nichts auf Windows übertragen/installiert/ausgeführt bestätigt.
Danach lokale synthetische Brückendemo COM5→COM6/GSVmulti, erst dann TCP.

---

## 2026-11-04 — Windows-Paket übertragen und Python-Brücke startfähig

Nutzer bestätigt SCP-Erfolg, isolierte Python3.15-Umgebung, Installation von
pyserial3.5 und erfolgreiche --help-Ausgabe der portablen Brücke. Ausgabe
enthält den vollständigen Windows-Brückenordner, im Diagnose-Snapshot gesichert.
Keine Pip-/Python-Aktualisierung nötig; Pi-Python/Kameraumgebung unverändert.
[Beleg](VALIDATION.md#windows-bridge-help-20261104).

Lokale Windows-Demo vorbereitet: GSVmulti vollständig neu starten, UserDefined
COM6/115200,Präfix%,Zahlenfilter ein,ein Wert,10Hz,mV/V/Scaling1; manuelle
Aufnahme mit allen Werten und TXT-Export. Danach vorhandener Demoteil der
Brücke auf COM5 mit600 eindeutigen synthetischen Werten−0,300…+0,299 und
Zielrate10Hz. Eigener neuer GUID-Runordner/Log für jeden Versuch; Exitcode
und Senderlog sowie TXT/TDMS zur Auswertung anfordern. Noch nicht gestartet,
kein Pi-Sender nötig und keine reale DUT-Ausgabe. Dieser lokale Demoaufruf
prüft nicht den internen Pi-JSONL-/ACK-Pfad; TCP folgt nach gültigem Empfang.

---

## 2026-11-04 — Lokaler Windows-Weg vollständig aufgezeichnet, Zeitraster bleibt nominell

Nutzer liefert TXT/TDMS/Index und bridge.jsonl. Originale mit SHA256 gesichert.
Auswertung bestätigt600/600 eindeutige Werte, exakt −0,300…+0,299 in Sender-
reihenfolge, keine Lücken/Doppelungen/Änderungen. TDMS bestätigt mV/V, Scaling1,
Frequency10 und COM6. Windows3.15/pySerial→COM5→COM6/GSVmulti damit für gültige
Demowerte belegt. [Zahlen/Grenzen](VALIDATION.md#windows-local-demo-20261104-01).

Windows-Schreibereignisse dauern zwischen erstem/letztem66,1322657 s
(HOST_MONOTONIC), mittlere Rate9,0576059Hz statt Ziel10Hz. GSVmulti speichert
alle600 auf nominellem0,1-s-Raster über59,9 s. Keine Datenlücke und kein
Latenzmaß. Sender wartet nach Schreib-/Logarbeit jeweils1/rate; genaue
Anteile von IO und Windows-Scheduling sind nicht getrennt gemessen. Neue
OQ-57, keine Änderung an Messwerten oder Demosendercode. Analyse-Rezept
normalisiert Decimal-Schritte nur für eindeutige Berichtsdarstellung;
Originalwerte unverändert. Wiederholte Auswertung nach dieser Berichtskorrektur
und zusätzlichen COM6-/Schrittassertionen bestanden.

Nächste Probe vorbereitet: gemeinsamer TCP-Pfad vom Pi, Source600/Ziel10Hz,
Windows-Polling100Hz (Abfragefrequenz, keine Messrate). Sender an Tailscale-
Adresse binden, bestehender Schutzweg SSH/VPN bleibt. Windows-Bridge darf vor
Publisherstart wiederholt verbinden; Publisher erst nach Nutzer-bereit starten.
GSVmulti-Kanal COM6 kann offen bleiben, nur neue Aufnahme starten. Kein neuer
Pi-Sender aktiv, keine Aufnahme des TCP-Versuchs und keine echte DUT-Ausgabe.
---

## 2026-11-04 — Gemeinsamer TCP-Pfad sendet vollständig, Anzeige bestätigt

Nach Nutzer-bereit den vorhandenen Pi-Demopublisher gestartet: ausschließlich
Bind an Tailscale100.122.154.35:5000,600 synthetische Werte/Ziel10Hz. Windows-
Brücke bereits im TCP-Modus, Abfrageziel100Hz, COM5; GSVmulti-Kanal COM6 bleibt
offen, nur neue Aufnahme. Keine Hardware-, Treiber- oder Sicherheitsänderung.
Nutzer bestätigt während des Laufs wechselnde Zahlen in GSVmulti.

Publisher regulär mit Exitcode0 beendet; Quellaudit, Angebot und erfolgreiche
COM-Schreibbestätigungen umfassen jeweils alle600 Frames0…599. Requests und
Run-ID stimmen vollständig. [Zahlen/Grenzen](VALIDATION.md#tcp-demo-20261104-01).
Damit erster gemeinsamer Pi-JSONL-/ACK-Transport durchlaufen; ACK ist weiterhin
nur COM-Treiberbestätigung. Pi-Hostereignisse erlauben keine Latenzaussage zur
synthetischen Quelle oder zur ungepaarten Windows-Uhr. Keine ungültigen Werte,
keine Wiederanlaufprobe und keine DUT-Freigabe. TCP-Listener nach Ende frei.

Nutzer zum Stoppen der GSVmulti-Aufnahme und anschließend Strg+C in der
Windows-Brücke angeleitet. Neue TXT/TDMS und bridge.jsonl aus tcp-demo-Runordner
stehen noch aus; erst deren Vergleich prüft vollständige Empfängerspeicherung.
Originale, Setup und reproduzierbarer Quellvergleich unter
var/diagnostics/gsvmulti/tcp-demo-20261104-01 gesichert.
---

## 2026-11-04 — TCP-Empfängerdateien bestätigen alle600 Quellwerte

Nutzer liefert neue TXT/TDMS/Index und Windows-bridge.jsonl. Alle Originale
unverändert gesichert, SHA256 und Analyse-Rezept im TCP-Diagnoseverzeichnis.
Vollständiger Vergleich von Pi-Audit, Angebot, Pi-ACK, Windows-ACK/Payload,
TXT und TDMS bestanden:600/600 Werte−0,300…+0,299 exakt und in Reihenfolge,
keine Lücken/Doppelungen/Änderungen. Beide TDMS-Einheiten mV/V, Scaling1,
Frequency10 und COM6 bestätigt. [Zahlen/Grenzen](VALIDATION.md#tcp-demo-20261104-01).

Damit erstmals gemeinsamer Pi→TCP→Windows-Brücke→COM5/com0com/COM6→GSVmulti-
Dateipfad für gültige Demowerte belegt. Zahlenfolge enthält im Windows-Log
keine Verbindungsfehler;5 Timeout-Verbindungsversuche davor und19 nach dem
ended-Ereignis liegen außerhalb der Zahlenübertragung. Dies passt zum
angeleiteten Windows-Start vor Pi-Publisher und Retry nach Senderende,
ersetzt aber keinen Abbruch-/Wiederanlaufversuch während eines laufenden
Quellstroms. Ende des Windows-Prozesses/Cleanup nicht separat nachgewiesen.

Windows-Schreibereignisspanne60,1336699 s, Mittel9,96114Hz bei Quellziel10Hz;
GSVmulti weiterhin nominell59,9 s/0,1-s-Raster. Getrennte Host-Uhren und
synthetische Aufnahmezeit, keine Latenzableitung. Keine Hardware-/Konfig-
oder Produktcodeänderung, keine reale DUT-Freigabe. Nächster bestehender
Prüfpunkt: kontrollierter Abbruch/Wiederanlauf und Altwertnachlauf, danach
separater UART-Nachweis über dieselbe Brücke. Kein neuer Sender gestartet.

---

## 2026-11-04 — Wiederanlauf-Diagnose vorbereitet, Quelle unabhängig vom Empfang

Nutzer stimmt dem nächsten kontrollierten Brücken-Abbruch/Wiederanlauf zu.
Codeprüfung: bisheriger600er-Publisher wartet nach jedem Wert auf dessen ACK;
bei unterbrochener Brücke steht daher auch die Demoquelle. Für einen Test
weiterlaufender lokaler Eingaben ungeeignet. Separates, als Throwaway markiertes
Diagnoseprogramm nutzt denselben OutputPublisher und denselben Formatter,
Audit vor Publish, ohne ACK-Warten während der Werteerzeugung. Kein Produktcode
geändert und kein struktureller Freigabebypass. Bestehender Abnahmeplan gilt.

Lokale TCP-/Memory-COM-Vorprobe mit100 Quellwerten bestanden: Quelle lief
während Disconnect weiter; erster Wiederanlaufwert69 nach letztem19, danach
bis99, keine Zwischenhistorie nachgesendet.50 Veröffentlichungen in der
Unterbrechung dokumentiert. [Zahlen/Grenzen](VALIDATION.md#tcp-reconnect-precheck-20261104-01).
Das ist keine Windows-Abnahme und keine Framealter-/Latenzmessung.

Windows-Controller vorbereitet: neuer GUID-Runordner, eigene before/after-
Brückenlogs, PID-bezogene Beendigung ausschließlich seiner eigenen Kindprozesse,
10s Pause nach100 Schreibbestätigungen, anschließend Neustart. Lokales
COM6/GSVmulti bleibt offen, bestehender Close/Open-Fehler wird nicht erneut
provoziert. Controller-/Quellskript syntaxgeprüft; Windows-Ausführung noch
nicht erfolgt. Export gsvmulti-reconnect-controller-2026-11-04.py mit festem
SHA256 für SCP über bestehendes SSH, kein öffentlicher Installer (OQ-49).
Auf Windows neue GSVmulti-Aufnahme/Controller vorzubereiten, erst danach
Pi-Quelle starten. Kein Sender auf Tailscale-Port5000 aktiv, keine Hardware-
oder Sicherheitsänderung, echte DUT-Ausgabe weiter gesperrt.

---

## 2026-11-04 — Wiederanlauf abgeschlossen und Dateiauswertung für Übergabe gesichert

Nutzer-bereit nach laufender GSVmulti-Aufnahme und Windows-Controller. Quelle
nur an Tailscale100.122.154.35:5000 gestartet,600 synthetische Werte unabhängig
von ACK erzeugt. Controller beendete nach100 written seinen eigenen Windows-
Brückenprozess, wartete10s und startete zweite Instanz auf COM5. GSVmulti COM6
und Aufnahme durchgehend offen. Pi zeichnet Abbruch und neue Verbindung auf,
Publikationen laufen weiter. Nutzer bestätigt Fortsetzung ohne Eingriff.

Pi regulär Exit0, letzte Frame599/COM-written bestätigt. Nutzer liefert sofort
TXT/TDMS/Index sowie vollständige before/after-/Steuerlogs, Controllerkopie und
summary. Alle Originale bytegetreu gesichert, Controllerkopie identisch zum
bereitgestellten Skript.510/510 COM-geschriebene Werte exakt in TXT/TDMS,
mV/V/Scaling1/COM6.89 Frames100…188 bei Unterbrechung nicht nachgesendet;
Zusatzframe356 schon in der Quell-Latest-Auswahl ersetzt, nicht nach COM-
Schreiben verloren. OQ-58 zur isolierten Zeit-/Schedulingursache eröffnet.
[Zahlen und Grenzen](VALIDATION.md#tcp-reconnect-20261104-01).

Wiederanlauf99→189 entspricht dem neuesten Angebot, kein historischer Puffer.
Windows-Steuerpause10,0001885s, Schreibereignislücke10,1779168s, im Export
weiterhin nur0,1s. Damit numerischer Wiederanlauf belegt, Ungültig-/Zeitlücke
bleibt offen. Keine Frische-/Latenzableitung aus SYNTHETIC und keine echte
DUT-Freigabe. Beide Kindprozesse durch Controller beendet (Exit1 absichtlich),
Controller completed=true. Pi-TCP-Listener nach Ende frei, kein Sender aktiv.

Nutzer beendet die Arbeit für einige Tage und beauftragt Dokumentation,
Commit und Push des GSVmulti-Stands. Übergabe in docs/status.md, tatsächliche
Workbench-Nähte/Tests und offene Abnahme getrennt dokumentieren. Kein Merge
nach master und keine neue Messung; unabhängige lokale Redesign-/Benutzernotizen
nicht mit GSVmulti vermischen. Diagnosebelege mit Manifest im Repo archivieren,
damit die Fortsetzung nicht von ignoriertem var/ oder Chat-Anhängen abhängt.
