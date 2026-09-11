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
