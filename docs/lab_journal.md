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
