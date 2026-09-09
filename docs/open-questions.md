# Offene Punkte

Jede Unbekannte hat eine Nummer `OQ-nn`. **Einträge werden nie gelöscht**, nur
auf `geklärt` oder `verworfen` gesetzt — mit Datum, Antwort und Verweis darauf,
wo die Antwort gelandet ist. So bleibt nachvollziehbar, warum etwas so ist.

Status: `offen` · `in Arbeit` · `geklärt` · `verworfen`

OQ-01 bis OQ-06 sind die sechs offenen Entscheidungen aus Konzept.md §11.

---

## OQ-01 — Welches serielle Format akzeptiert die eingesetzte GSVmulti-Version?

* **Status:** offen · **Zuständig:** ME-Systeme intern
* **Blockiert:** P4. **Nicht** P0–P3.
* **Vorabdefault:** `AsciiCsvFormatter`, als `provisional=True` gekennzeichnet.
* **Antwort landet in:** [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md)
* Siehe OQ-07 — praktisch dieselbe Frage aus der Beschaffungsperspektive.

## OQ-02 — Welche maximale Zeitabweichung zwischen DUT und Referenz ist zulässig?

* **Status:** offen · **Zuständig:** Labor / QM
* **Blockiert:** die **Abnahme**, nicht das Bauen. Das Messprogramm M1–M8
  läuft unabhängig davon; der Grenzwert wird am Ende gegen die Zahlen gelegt.
* **Antwort landet in:** [TIMING.md](TIMING.md), Abschnitt Unsicherheitsbudget

## OQ-03 — Kann die Referenz einen Trigger oder Zeitstempel bereitstellen?

* **Status:** offen · **Zuständig:** Labor
* **Blockiert:** Umfang von M6, nicht die Implementierung. `trigger_sequence`
  ist im Datensatz als `None`-fähiges Feld vorgesehen.
* **Günstigstes Experiment:** Handbuch der Kalibriermaschine prüfen, ob es
  einen Triggerausgang oder eine Netzwerk-Zeitquelle gibt. Etwa eine Stunde.
* **Antwort landet in:** [TIMING.md](TIMING.md)

## OQ-04 — Welche Gerätetypen bilden den ersten freizugebenden Umfang?

* **Status:** offen · **Zuständig:** Labor
* **Blockiert:** Umfang des Datensatzes (P2) und die Abnahmekriterien (P7).
* **Vorabdefault:** mit GSV-2ASD und einem AST-Gerät beginnen; die Architektur
  bleibt anzeigetyp-agnostisch.
* **Günstigstes Experiment:** zwei Wochen Zählstrich am Prüfplatz — welche
  Geräte kommen tatsächlich am häufigsten?
* **Antwort landet in:** [ROADMAP.md](ROADMAP.md), `datasets/README.md`

## OQ-05 — Ist eine einmalige Bestätigung durch den Laboranten im Ablauf vorgesehen?

* **Status:** offen · **Zuständig:** Labor
* **Blockiert:** das Bedienkonzept, nicht die Kette. Der `manual_roi`-Pfad ist
  bereits der Primärpfad und setzt die Bestätigung voraus.
* **Vorabdefault:** Bestätigung ist vorgesehen (Konzept §4 „bevorzugter
  Betrieb"), Vollautomatik ist spätere Option.

## OQ-06 — Wie werden ungültige Werte in GSVmulti und in der Kalibrierauswertung behandelt?

* **Status:** offen · **Zuständig:** ME-Systeme intern + QM
* **Blockiert:** P4, zusammen mit OQ-01.
* **Vorabdefault:** `InvalidValuePolicy` als austauschbarer Adapterparameter
  mit den drei Varianten `omit_record`, `send_nan`, `status_flag`. Alle drei
  sind implementiert und getestet, die Wahl ist eine Konfiguration.
* **Antwort landet in:** [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md)

---

## OQ-07 — GSVmulti-Telegrammspezifikation beschaffen

* **Status:** offen · **Zuständig:** Mensch bei ME-Systeme
* **Befund:** Die Spezifikation liegt lokal nicht vor. `me-systeme.de` blockt
  automatische Abrufe mit **HTTP 403** — die im Konzept §12 verlinkte
  Datenformat-Seite und das GSVmulti-Handbuch sind so nicht erreichbar. Ein
  Mensch muss sie intern beschaffen.
* **Belastbarste Quelle ist nicht die Doku, sondern ein Mitschnitt:** ein
  vorhandenes GSV-2/GSV-3 im ASCII-Modus an GSVmulti hängen und den realen
  Datenstrom aufzeichnen. Das liefert das tatsächliche Telegramm.
* **Antwort landet in:** [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md),
  Implementierung in `src/dispread/sink/protocol/gsv_ascii.py`

## OQ-08 — An welchem CAM-Anschluss hängt die Kamera?

* **Status:** geklärt (2026-09-07)
* **Antwort:** CAM/DISP0. Der Sensorknoten erscheint als
  `/axi/pcie@1000120000/rp1/i2c@88000/imx500@1a`, die CAM-I2C-Busse sind 6
  und 10. Erkannt über `camera_auto_detect=1`, ohne explizites Overlay.
* **Gelandet in:** [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)

## OQ-09 — RS-232-/RS-485-Transceiver und galvanische Trennung

* **Status:** offen · **Zuständig:** Hardware / Beschaffung
* **Befund:** Kein USB-Seriell-Adapter angeschlossen. Verfügbar sind nur
  `/dev/ttyAMA0` (Datenport, durch `dtparam=uart0=on` aktiv) und
  `/dev/ttyAMA10` alias `/dev/serial0` — letzteres ist der **3-Pin-Debug-Header**
  und nicht der Nutzdatenport.
* **Konzept §8:** Pi-GPIO-Pegel dürfen **nicht** direkt mit RS-232 verbunden
  werden. Galvanische Trennung ist für den Laboraufbau zu bewerten.
* **Blockiert:** die elektrische Strecke, nicht die Software. Getestet wird bis
  dahin gegen pty.
* **Antwort landet in:** [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)

## OQ-10 — Spezialisierte 7-Segment-Traineddata für Tesseract

* **Status:** offen
* **Befund:** Debian liefert nur prosa-trainierte Traineddata (`eng`).
  Spezialisierte Sätze wie `ssd` oder `letsgodigital` sind **nicht** in Debian.
  Download müsste off-Pi erfolgen, mit Lizenzprüfung.
* **Relevanz:** gering, solange der klassische Segment-Dekoder trägt. Tesseract
  ist die Vergleichsbasis, nicht der Primärpfad.

## OQ-11 — Workstation für die IMX500-Modellkonvertierung

* **Status:** offen
* **Befund:** Auf dem Pi ist nur der *Packager* vorhanden (`imx500-package`,
  `fpk2rpk`, `PostConverter.jar` unter `/usr/lib/imx500-tools/`). Der
  *Converter* und `model_compression_toolkit` fehlen; `torch`/`tensorflow`/`onnx`
  sind bewusst nicht installiert.
* **Konsequenz:** Training, Quantisierung und Konvertierung laufen off-Pi. Auf
  dem Pi bleibt nur Paketierung und Deployment.
* **Relevanz:** erst für P8 (optional).

## OQ-12 — Was ohne angeschlossene Kamera nicht verifizierbar war

* **Status:** geklärt (2026-09-07) — durch die Inbetriebnahme abgearbeitet.
* **Ergebnisse:** siehe [TIMING.md](TIMING.md). Insbesondere: `.rpk`-Warmlauf
  6,8 s, 15,0 Inferenzen/s, `SensorTimestamp` in CLOCK_BOOTTIME,
  `CnnInputTensor` **fehlt** in den Standardmetadaten, Stock-Modelle liefern
  COCO-Labels.

## OQ-13 — Anzeigepolarität und der Fall „alle Stellen zeigen 8"

* **Status:** offen
* **Befund:** Der Segment-Dekoder schwellt über die gepoolten Segmentmessungen
  aller Stellen. Zwei bekannte Grenzen:
  1. Zeigt die Anzeige ausschließlich `8`, gibt es keine inaktive Klasse, der
     Kontrast ist klein und der Ausschnitt wird **abgelehnt**. Eine
     Falschablehnung ist nach Konzept §7 die zulässige Richtung — geraten wird
     nicht —, aber es ist eine Einschränkung.
  2. Vorausgesetzt ist helle Anzeige auf dunklem Grund (LED). Für LCD mit
     umgekehrter Polarität fehlt die Behandlung.
* **Lösungsansatz:** Polarität ins Geräteprofil aufnehmen; als
  Off-Referenz zusätzlich eine Panelfläche außerhalb der Segmente abtasten.

## OQ-14 — Freigabeschwellen an realen Geräten validieren

* **Status:** offen
* **Befund:** Alle Schwellen in `GateConfig` sind Vorabdefaults, keine
  validierten Grenzen. Konzept §7 verlangt ausdrücklich, sie an realen, auch
  bisher unbekannten Gerätetypen zu validieren.
* **Blockiert:** die Abnahme. Aufgabe von P3/P7.
* **Antwort landet in:** [VALIDATION.md](VALIDATION.md)

## OQ-15 — `tesseract-ocr`, `socat` und `chrony` installieren

* **Status:** offen · **Zuständig:** Mensch mit `sudo`-Passwort
* **Befund:** Seit dem Reboot am 2026-09-07 verlangt `sudo` ein Passwort, die
  Installation konnte nicht automatisch erfolgen. Benötigt:
  `sudo apt install -y tesseract-ocr tesseract-ocr-eng socat chrony`
* **Wirkung:** Ohne `tesseract` fehlt die OCR-Vergleichsbasis, ohne `chrony`
  ist Messung M1 (Offset und Drift) nicht protokollierbar. `socat` ist nur
  Komfort — die Tests nutzen `os.openpty()` aus der stdlib.
* **Antwort landet in:** [dependencies.md](dependencies.md)

## OQ-16 — Vollständigkeit des lokalen Planungsstands

* **Status:** offen · erkannt 2026-09-08 bei der Tool-Recherche
* **Befund:** Unter anderem `ROADMAP.md`, `dependencies.md`,
  `HARDWARE_PROFILE.md` und `lab_journal.md` werden referenziert, fehlen aber
  im aktuellen Arbeitsbaum unter `docs/`. Auch mehrere im Status genannte
  CLI-/Replay-Komponenten sind lokal nicht vorhanden. Frühere Messangaben
  werden deshalb als dokumentierte Ergebnisse, nicht als neu verifiziert behandelt.
* **Klärung:** Fehlende Dateien wiederherstellen oder Verweise und Meilensteine
  mit dem tatsächlich vorhandenen Stand abgleichen.
* **Antwort landet in:** `docs/status.md` und den betroffenen Dokumenten.

## OQ-17 — Sichtbarer Dezimalpunkt und Profilannahme unterscheiden

* **Status:** offen · erkannt 2026-09-08 bei der Tool-Recherche
* **Befund:** `SevenSegmentReader.read` setzt `decimal_point_detected` anhand
  des Profils; der Punkt wird nicht im Bild gemessen. Die Einheit kommt
  ebenfalls aus dem Profil, dort bereits mit `unit_source=profile` markiert.
* **Klärung:** Welche Geräte können Punkt, Einheit oder Messbereich während
  eines Laufs wechseln? Bildprüfung und explizite Herkunft der Punktposition
  vorsehen; Profilannahmen dürfen keine optische Erkennung vortäuschen.
* **Antwort landet in:** `docs/tool_review_2026-09-08.md`, später Leser,
  Profile und `docs/VALIDATION.md`.

## OQ-18 — Welches neuronale OCR-Modell trägt auf realen Displays?

* **Status:** offen · erkannt 2026-09-08 bei der Tool-Recherche
* **Befund:** ONNX Runtime bietet inzwischen Linux-ARM64-Wheels für CPython
  3.13. Das belegt noch keine Verträglichkeit mit der konkreten System-NumPy-
  Installation und keine Erkennungsqualität oder Laufzeit auf diesem Pi.
* **Klärung:** PP-OCRv5 mobile und PP-OCRv6 tiny/small gegen Tesseract und den
  Segmentleser auf denselben realen Aufnahmen prüfen; Modell, Zeichensatz,
  Vorverarbeitung, Runtime, Lizenz und Prüfsummen festhalten. Keine automatische
  Installation von PyPI-NumPy/OpenCV in die Projekt-venv.
* **Antwort landet in:** `docs/tool_review_2026-09-08.md`, später
  `docs/dependencies.md` und `docs/VALIDATION.md`.

## OQ-19 — Freigabeevidenz für weitere OCR-Backends

* **Status:** offen · erkannt 2026-09-08 bei der Tool-Recherche
* **Befund:** `ReleaseGate.evaluate` verlangt `contrast` und `min_margin`
  aus der Segmentanalyse. Ein neuer OCR-Leser ohne diese Diagnosen wird
  abgelehnt. Ein neuronaler Score ist kein Ersatz für einen Segmentabstand.
* **Klärung:** Gemeinsame optische Qualitätsprüfung und je Backend validierte
  Evidenzregeln definieren, ohne fehlende Diagnosen mit erfundenen Werten zu füllen.
* **Antwort landet in:** `docs/tool_review_2026-09-08.md`, später
  Freigabelogik und `docs/VALIDATION.md`.

## OQ-20 — Auto-Setup gegen Multiplexing echter Anzeigen absichern

* **Status:** offen · erkannt 2026-09-08 beim Workbench-Ausbau
* **Befund:** Die neue begrenzte Belichtungs-/Gain-Suche bewertet Kontrast,
  Überstrahlung und zeitliche Helligkeitsschwankungen im bestätigten Bereich.
  Diese Kriterien beweisen nicht, dass alle multiplexenden Segmente vollständig
  aufgenommen wurden; eine stabile Phasenlage kann fehlende Segmente verbergen.
* **Klärung:** Je realem Gerät geeignete Belichtungsbereiche und Multiplexperiode
  messen; automatische Vorschläge mit optisch bestätigten vollständigen Anzeigen
  vergleichen. Bis dahin bleibt Auto-Setup eine Einstellhilfe mit menschlicher
  Bestätigung, keine automatische Freigabe.
* **Antwort landet in:** `docs/OPTICAL_SETUP.md`, Geräteprofile und
  `docs/VALIDATION.md`; Aufbau in `docs/lab_journal.md`.

## OQ-21 — HTTPS-Browserabnahme der Workbench

* **Status:** offen · erkannt 2026-09-08 beim Workbench-Ausbau
* **Befund:** Der lokale Chromium-152-Headless-Test lädt HTTPS-Seiten trotz
  erfolgreicher TLS-Handshakes auf Serverseite nicht fertig; Navigation und
  anschließende CDP-Auswertung laufen in Timeouts. Direkte Python-/curl-
  HTTPS-Abfragen laden die Loginseite vollständig. Die konkrete Ursache in
  dieser Browserumgebung ist nicht geklärt.
* **Eingegrenzt am 2026-09-08:** Es ist kein TLS- und kein Zertifikatsproblem.
  Dasselbe Chromium lädt auch eine reine HTTP-Seite eines lokalen
  `python -m http.server` nicht (leerer Body, `net_error -101`, „Page load timed
  out"), während `file://`-Seiten samt JavaScript einwandfrei laufen. Zusätzlich
  feuern Timer im Headless-Modus nur mit `--virtual-time-budget`, nicht mit
  `--timeout`. Browserprüfungen dieser Umgebung laufen deshalb über eine
  `file://`-Seite mit eingespielter echter `/status`-Antwort; das prüft das
  Frontend, aber weder TLS noch Anmeldung noch WebSocket.
* **Klärung:** Mit vertrautem Zertifikat im Windows-Browser anmelden und
  Kamera, echte Shell, TUI sowie Wiederverbindung gemeinsam abnehmen. Falls
  reproduzierbar: Browser-/TLS-Netzwerkdiagnose ergänzen. Keine Sicherheits-
  umgehung oder passwortfreie Produktionsanmeldung als Ersatz einbauen.
* **Antwort landet in:** `docs/anleitung/10-kamera-livevorschau.md`,
  `docs/status.md`; technische Befunde gegebenenfalls `docs/lab_journal.md`.

## OQ-22 — Sensor setzt nach Streamwechsel keinen Stream mehr auf

* **Status:** offen · erkannt 2026-09-08 bei der Fokusdiagnose
* **Befund:** Nach einer Messreihe, die im selben Prozess erst 960×720 und dann
  2028×1520 streamte (`configure` → `start` → `stop` → `configure` → `start`),
  liefert der Sensor **überhaupt keine Bilder mehr**. Jeder weitere Startversuch
  — auch aus einem frischen Prozess und auch mit `rpicam-still` — endet im
  Kernel mit `rp1-cfe 1f00110000.csi: stream on failed in subdev`, begleitet von
  `WARNING ... call_s_stream+0x100/0x118 [videodev]` und
  `videobuf2_common: driver bug: stop_streaming operation is leaving buffer 0 in
  active state`. 8.429 solche Zeilen zwischen 15:20:32 und 15:22:12 Ortszeit.
  Enumeration bleibt intakt: `global_camera_info()` und
  `scripts/camera-commissioning.sh` melden weiter „einsatzbereit" — die
  Diagnose prüft den Bilddurchlauf also **nicht**. Letzte erfolgreiche Aufnahme
  vor dem Reboot 15:14, erster Fehlschlag 15:20:32.
* **Zwischenstand 1 (verworfen): PipeWire/WirePlumber.** Beide hielten
  `/dev/v4l-subdev2`, den imx500-Sensorknoten, und WirePlumber 0.5.8 hatte den
  libcamera-Monitor aktiv — zwei libcamera-Klienten am selben Sensor. Der
  Monitor wurde benutzerseitig abgeschaltet
  (`~/.config/wireplumber/wireplumber.conf.d/50-kein-kameramonitor.conf`,
  `monitor.libcamera = disabled`); danach hält PipeWire den Sensorknoten
  nachweislich **nicht** mehr. **Der Fehler tritt trotzdem weiter auf.** Damit
  ist Kamerakonkurrenz als Ursache widerlegt. Die Abschaltung darf bleiben, sie
  entfernt einen Störfaktor.
* **Zwischenstand 2 (verworfen): hängender Prozess.** Ein beendeter
  Fokusmesser-Lauf blieb nach Strg+C 1:57 min als PID 4681 in
  `futex_wait_queue` stehen und hielt den Sensor. Das ist aber **Folge, nicht
  Ursache**: `Picamera2.stop()` wartet auf Puffer, die der Treiber nie
  zurückgibt. Den Prozess zu töten gibt die Kamera **nicht** frei — der
  anschließende Startversuch scheiterte weiter, und der Kill selbst löste
  erneut `cfe_stop_streaming ... leaving buffer 0 in active state` aus.
* **Stand: es ist ein Treiberfehler, und der Kernel sagt es selbst.**
  `videobuf2_common: driver bug: stop_streaming operation is leaving buffer 0
  in active state`, aufgerufen aus `cfe_stop_streaming+0xd4/0x200 [rp1_cfe]`.
  Jeder Streamabbau — sauber beendet oder per Signal — kann die vb2-Warteschlange
  in diesem Zustand hinterlassen. Danach scheitert jeder weitere Start, in zwei
  Varianten: `stream on failed in subdev` oder
  `/dev/video4[15:cap]: Failed to queue buffer N: Invalid argument`. Zuletzt
  hängt sogar `Picamera2(0)` beim Öffnen. **Nur ein Reboot hilft**; ein
  Modul-Reload wäre die Alternative und verlangt `sudo`.
* **Beste offene Hypothese: die Streamgröße entscheidet.** Sechs Datenpunkte,
  lückenlos konsistent:

  | Zeit | Sitzung | Modus | Ergebnis |
  | --- | --- | --- | --- |
  | 10:31 | Vorschaubeispiel | 960×720 | lief, Folge-Sitzungen weiter möglich |
  | 12:03 | Workbench-Kameradienst | 960×720 | lief, Folge-Sitzungen weiter möglich |
  | 14:03 | Kamera-Smoke-Test | 960×720 | lief, Folge-Sitzungen weiter möglich |
  | 15:14 | Fokusdiagnose | 960×720, dann **2028×1520** | lief; **danach alles blockiert** (15:20:32) |
  | 15:31 | `rpicam-still` | **4056×3040** | lief; **10 s später blockiert** |
  | 15:47 | Fokusmesser | **2028×1520** | lief (Bestwert 75); **danach blockiert** |

  Drei Sitzungen bei 960×720 hintereinander überlebten den Abbau, jede Sitzung
  mit einem der großen Sensormodi war die letzte des Boots.
* **Hypothese am 2026-09-08 abgeschwächt:** In der nächsten Runde liefen bei
  960×720 **mehrere** Sitzungen hintereinander (Fokussieren in mehreren Läufen,
  Bestwert 216,6), dann trat derselbe Fehler wieder auf. Die Streamgröße ist
  also nicht der Schalter, sondern höchstens ein Einflussfaktor: 960×720
  verzögert das Problem, hebt es nicht auf. Es bleibt ein Wettlauf beim
  Streamabbau, der nicht bei jedem Abbau zuschlägt. Damit ist keine
  Konfiguration bekannt, die dauerhaft sicher ist.
* **Konsequenz für die Bildkette, unabhängig von der Ursache:** Der Messbetrieb
  bleibt bei 960×720. Ziffernhöhe wird, falls nötig, über **`ScalerCrop`** geholt
  — digitaler Ausschnitt auf die Anzeige bei gleichbleibender Ausgabegröße; der
  Sensormodus ist ohnehin in beiden Fällen 2028×1520. Am 2026-09-08 gemessen
  wurde das nicht gebraucht: 960×720 erreichte am Testgerät 37 px Ziffernhöhe
  ([VALIDATION.md](VALIDATION.md)).
* **Was die Workbench tun muss, solange der Treiber so ist:** (a) den Stream
  nicht ohne Not neu aufsetzen, (b) beim Beenden nach begrenzter Wartezeit hart
  aussteigen, damit ein hängendes `Picamera2.stop()` das Gerät nicht zusätzlich
  belegt, (c) den blockierten Sensor als solchen melden („Reboot nötig") statt
  als anonymen Timeout, (d) `scripts/camera-commissioning.sh` um eine echte
  Aufnahmeprüfung ergänzen, damit „einsatzbereit" Bilddurchlauf bedeutet.
* **Warum das wichtig ist:*** **Warum das wichtig ist:** Der Kamerathread der Workbench setzt den Stream bei
  jeder Änderung von Breite, Höhe oder Bildrate genau so neu auf
  (`Controller._worker`). Trifft das denselben Treiberzustand, fällt die Kamera
  mitten im Betrieb aus und ist ohne Reboot nicht zurückzuholen. Im Labor wäre
  das ein Ausfall während einer Kalibrierung.
* **Klärung:** (1) Den Größentest oben fahren. (2) Unabhängig davon gehört der
  Befund upstream gemeldet — der Kernel bezeichnet ihn selbst als `driver bug`,
  mit Aufrufpfad `cfe_stop_streaming` im `rp1_cfe`-Treiber, libcamera
  v0.7.2+rpt20260817, libpisp v1.7.0. (3) Solange es unklar ist:
  Auflösung und Bildrate nur bei stehender Kamera ändern, nicht im laufenden
  Messbetrieb — und die Auflösungszeile im setup-Tab entsprechend
  kennzeichnen. (4) `camera-commissioning.sh` um eine echte Aufnahmeprüfung
  ergänzen, damit „einsatzbereit" auch Bilddurchlauf bedeutet.
* **Nicht tun:** Den Fehlschlag im Kamerathread stillschweigend wegfangen und
  weiterlaufen. Ein Sensor, der keinen Stream aufsetzt, ist ein harter Ausfall
  und muss als Fehler sichtbar bleiben.

* **Update 2026-09-09, Nachmittag — korrigiert: nicht RP1/x1201-Kontention,
  sondern der Onboard-RP2040 der AI-Camera hängt sich nach genau
  reproduzierbar ~24 Power-Zyklen auf.** Mit einem minimalen Reproducer ohne
  `dispread` (`Picamera2().configure().start().capture_array().stop().close()`
  im Loop, alle 12 s) liefen **24 Zyklen sauber durch** (uptime 0 bis 442 s,
  über drei Minutengrenzen hinweg), dann scheiterte Zyklus 25 (uptime 472 s)
  und blieb ab da dauerhaft gesperrt. Im Kernel-Log genau zu diesem Zeitpunkt:
  `rp2040-gpio-bridge 10-0040: rp2040_gbdg_i2c_send() rp2040_gbdg_wait_until_free
  failed`, `rp2040_gbdg_gpio_dir_out(19, 0) could not ST_CL`, danach erst
  `imx500 10-001a: setup of GPIO led failed: -121` und `stream on failed in
  subdev`. Das ordnet die Vormittags-Spur ein: `led-gpios`/`reset-gpios`
  hängen nicht an RP1, sondern an einem **eigenen RP2040-Mikrocontroller auf
  dem AI-Camera-Modul selbst**, der Reset/LED/Power-Sequencing über I2C-Bus 10
  (Adresse 0x40) steuert (`rp2040-gpio-bridge`, Modul
  `spi_rp2040_gpio_bridge`). Die Kontentionshypothese mit
  `x1201-monitor`/`/dev/gpiochip0` (RP1) ist damit hinfällig — die Timer waren
  während des gesamten Tests aktiv und liefen erkennbar unabhängig vom
  Wedge-Zeitpunkt (Ticks um :00/:20, Wedge um :48). Stattdessen: der
  RP2040 selbst wird nach genügend Power-Sequencing-Zyklen für den
  I2C-Bridge-Verkehr unerreichbar — ob Firmware-Bug im RP2040, ein
  I2C-Timing-Grenzfall bei schneller Wiederholung oder ein Ressourcenleck,
  ist offen und braucht das RP2040-Firmware-Log (nicht zugänglich) oder einen
  I2C-Bus-Trace. **Das bestätigt und quantifiziert die viel ältere Vermutung
  aus diesem Dokument** („Streamabbau bleibt der Verdächtige, ein Wettlauf,
  der nicht bei jedem Abbau zuschlägt") — nur dass der Auslöser nicht die
  Streamgröße ist, sondern die **Anzahl** der Power-Zyklen, grob 20–25.
  Praktisch bedeutet das: Der Workbench-Kamerathread (`Controller._worker`),
  der bei jeder Auflösungs-/Bildraten-Änderung neu konfiguriert, nähert sich
  diesem Limit mit jeder Einstelländerung im laufenden Betrieb — nicht nur bei
  großen Sensormodi. Ein frischer Reboot setzt den RP2040 zuverlässig zurück
  (dieser Test lief direkt nach einem verifiziert echten Reboot und begann
  sauber); ob auch ein Modul-Reload ohne Reboot reicht, ist nicht getestet.

* **Update 2026-09-09 vormittags (überholt, siehe oben) — Reboot allein hat
  diesmal nicht geholfen; erste Spur GPIO-Kontention über RP1.** Nach einem verifiziert echten, frischen Reboot
  (Kernel-Meldung „Booting Linux on physical CPU”, `btime`/`uptime` bestätigt —
  `who -b`/`journalctl --list-boots` zeigten wegen fehlender batteriegepufferter
  RTC und nachträglichem `chronyd`-Zeitsprung fälschlich noch den alten
  Boot-Zeitpunkt) scheiterte der **erste** Streamversuch bereits sechs Minuten
  nach dem Hochfahren, mit zusätzlichem, bisher nie beobachtetem Symptom davor:
  `imx500 10-001a: setup of GPIO led failed: -121` /
  `imx500_power_on: failed to get led gpio`, dann erst `stream on failed in
  subdev` und der bekannte vb2-Treiberfehler beim Abbau. Diese Zeile fehlt in
  der gesamten bisherigen Journal-Historie (alle vorherigen erfolgreichen
  Sitzungen) komplett — sie ist neu, nicht ein wiederkehrendes Rauschen.
  Ausgeschlossen: eine Paket-Regression (der Kamera-Stack-Umbau `libcamera`
  0.7.2/`libpisp` 1.7.0/`rpicam-apps` 1.13.0 lief bereits am 2026-09-07 vor
  allen erfolgreichen Sitzungen vom 2026-09-08; `apt-daily-upgrade.timer`
  hatte heute noch nicht gefeuert).
  `led-gpios` und `reset-gpios` hängen im Overlay (`imx500-pi5.dtbo`) am
  selben GPIO-Controller-Phandle und werden laut den Strings in `imx500.ko`
  über `devm_gpiod_get_optional()` geholt — diese Fehlermeldung erscheint nur
  bei einem echten Fehler des GPIO-Subsystems, nicht bei einer fehlenden
  optionalen Eigenschaft. Auf demselben Pi läuft minütlich
  `x1201-monitor.service` (Geekworm-x120x-USV, `/usr/local/bin/x1200_once.py`),
  das direkt `/dev/gpiochip0` anfasst — auf dem Pi 5 derselbe RP1-Chip, der
  auch CSI/CFE und die Kamera-GPIOs bedient. Beide heutigen Fehlschläge lagen
  in derselben Minute wie ein `x1201-monitor`-Tick; bei minütlichem Tick für
  sich genommen nicht beweisend, aber mechanistisch naheliegend: zwei
  gleichzeitige RP1-GPIO-Anfragen (Kamera-Power-on vs. USV-Pegelabfrage)
  könnten sich das `-EREMOTEIO` liefern. **Nicht geprüft:** ob ein echter
  Stromzyklus (Netzteil ziehen, nicht `sudo reboot`) zuverlässiger hilft als
  der bisher übliche Warmstart — dazu hätte dieser Pi andere produktive
  MEhub-Dienste unterbrochen, das braucht eine bewusste Freigabe.
  Vorgeschlagene nächste Schritte, aufsteigend im Aufwand:
  1. `x1201-monitor.timer` und `rm520n-*.timer` für einen Testlauf stoppen und
     gezielt in der Minutengrenze mehrfach `dispread serve` starten — bestätigt
     oder widerlegt die Kontentionshypothese ohne Risiko für den Kamerapfad.
  2. Prüfen, ob `imx500_power_on` beim Fehlschlag von `devm_gpiod_get_optional`
     für die LED wirklich früh abbricht (Reset/Regulator/Takt also nie gesetzt
     werden) — würde erklären, warum danach kein Stream zustande kommt; dazu
     reicht ein erneuter Fehlschlag mit `dynamic_debug` auf `imx500.c`, kein
     Kernel-Rebuild nötig.
  3. Erst danach, falls (1) nichts zeigt: ein echter Stromzyklus als
     Gegenprobe zum reinen `reboot` — mit Ansage, da er MEhub mit betrifft.
  Aufbau, vollständige Zeitleiste und Befehle: `docs/lab_journal.md`,
  Eintrag 2026-09-09.

* **Update 2026-09-09, Nachmittag spät — zwei Abmilderungen in
  `workbench/Controller._worker` umgesetzt (beheben die RP2040-Sperre
  nicht, verringern/entschärfen sie nur):** (1) Geometrie-Änderungen
  (Breite/Höhe/Bildrate) werden jetzt über ein 250-ms-Fenster gebündelt,
  bevor der Stream neu aufgebaut wird — eine Auflösungsänderung (bisher zwei
  Befehle, zwei Power-Zyklen) kostet jetzt höchstens einen. (2) Die
  riskanten Kameraaufrufe laufen über einen Wachhund
  (`CAMERA_OP_TIMEOUT_S = 6 s`); hängt einer davon, wird das sofort als
  `CameraWedgedError` mit Verweis auf diese OQ gemeldet, statt den
  Kamerathread endlos schweigend hängen zu lassen — deckt damit den unter
  „Was die Workbench tun muss" Punkt (c) ab. Details:
  [CHANGELOG.md](../CHANGELOG.md) 2026-09-09. Noch offen: ein gezielter Test
  für den neuen Entprell-/Wachhundpfad (bestehende Tests laufen alle mit
  `simulate=True`), und ob (2) auch bei einem hängenden `Picamera2()`-
  Konstruktoraufruf selbst greift — der liegt außerhalb von `_worker`s
  Guard.

* **Update 2026-09-09, spät — bei Raspberry Pi gemeldet, kein Fix ohne Reboot
  bislang verifiziert.** Vollständige Commit-Historie von
  `drivers/spi/spi-rp2040-gpio-bridge.c` geprüft (`gh api`): seit Einführung
  2024-05-21 nur zwei Commits, keiner adressiert diesen Fehler; keine
  offenen oder geschlossenen Issues im `raspberrypi/linux`-Tracker erwähnen
  ihn. Damit ist der Fehler **nirgends dokumentiert** — gemeldet als
  [raspberrypi/linux#7613](https://github.com/raspberrypi/linux/issues/7613)
  mit Reproducer, Kernel-Log-Signatur und allem, was ausgeschlossen wurde
  (RP1-GPIO-Kontention, veraltete RP2040-Firmware, Kernel-6.18.34-Diff).
  Ein möglicher Wiederherstellungsweg ohne vollen Reboot — Unbind/Rebind von
  `10-0040` (RP2040-Bridge) am I2C-Bus, wodurch `cam0_reg` (der von Sensor
  **und** Bridge gemeinsam genutzte, GPIO-rückende Regulator, live per
  `gpiod` als von `cam0_reg` exklusiv gehalten bestätigt) auf `num_users: 0`
  fallen und danach real neu einschalten sollte — liegt vorbereitet als
  Skript vor (`/tmp/rp2040_recover_test.sh` dieser Sitzung, nicht
  versioniert), aber **noch nicht ausgeführt**: das Unbind/Bind
  braucht Root, kein Nicht-Root-Weg existiert nachweislich (kein
  gecachtes `sudo`, kein Setuid-/Polkit-Helfer, alle relevanten
  Sysfs-Pfade `root:root`, die GPIO-Leitung selbst vom Kernel exklusiv
  gehalten). Nächster Schritt bei Gelegenheit: das Skript mit `sudo`
  ausführen und das Ergebnis hier sowie im GitHub-Issue nachtragen —
  unabhängig vom Ausgang, da auch ein Fehlschlag für die Meldung relevant
  ist.

* **Update 2026-09-09, 11:15 — Test durchgeführt, Ergebnis negativ, Zustand
  danach schlechter als vorher.** `sudo`-Zugriff kurz verfügbar (Cache),
  Skript ausgeführt. `echo 10-0040 > .../rp2040-gpio-bridge/unbind` senkte
  `cam0_reg` erwartungsgemäß auf `num_users: 0 / disabled` — die
  Power-Gating-Analyse stimmt. Der anschließende Rebind scheiterte jedoch:
  `i2c_designware 1f00088000.i2c: controller timed out`, dann **`SDA stuck
  at low`** — ein echter I2C-Bus-Lockup, kein reines Treiberproblem. Danach
  wurde die Kamera **nicht mehr erkannt** (`No camera number 0 found`),
  vorher war sie zumindest noch enumeriert, nur blockiert beim Streamen.
  **Schluss: Unbind/Rebind ist keine funktionierende Wiederherstellung ohne
  Reboot — im Test hat es den Zustand verschlechtert.** Vermutung: der
  RP2040 braucht entweder eine längere Aus-Phase als die getesteten ~2 s,
  oder eine bestimmte Reihenfolge/Timing beim I2C-Wiederanlauf, die ein
  simples Unbind/Bind nicht liefert. Nachtrag im Issue:
  [Kommentar](https://github.com/raspberrypi/linux/issues/7613#issuecomment-5599453376).
  Reboot war danach nötig. `/tmp/rp2040_recover_test.sh` nicht ohne
  Weiteres wiederverwenden.

* **Update 2026-09-09, spätabends — hartes Power-Zyklus-Budget in der
  Workbench, verhindert das Auslösen über die eigene Bedienoberfläche.**
  Da keine funktionierende Wiederherstellung existiert und der Fehler
  hardwareseitig ungeloest bleibt, verweigert `Controller` jetzt eine
  echte Aufloesungs-/Bildratenaenderung, sobald `geometry_cycles` das
  Sicherheitsbudget (`MAX_GEOMETRY_CYCLES = 15`, unter dem beobachteten
  ~20-25er-Bereich) erreicht - mit klarer Fehlermeldung statt eines
  spaeteren, unvorhersehbaren Ausfalls. Behebt den RP2040-Fehler nicht,
  verhindert aber zuverlaessig, ihn ueber `dispread` selbst auszuloesen.
  Details: [CHANGELOG.md](../CHANGELOG.md) 2026-09-09 spätabends, Test
  `test_geometry_budget_blocks_change_but_allows_same_value`.

* **Update 2026-09-09, noch später — Lücke im Budget geschlossen: Zähler
  überlebt jetzt einen dispread-Neustart korrekt.** Der Zähler lag nur im
  Prozessspeicher; ein reiner `dispread`-Neustart (ohne Host-Reboot) hätte
  ihn faelschlich auf 0 gesetzt, obwohl der RP2040 die Zyklen laengst
  verbraucht hatte (belegt: Fehlschlag trat in einem frueheren Test auch
  ueber mehrere frische Prozesse hinweg auf derselben Bootsitzung ein).
  Jetzt an die Kernel-Boot-ID gebunden persistiert
  (`camera_cycles.json`) — haelt ueber Prozessneustarts, setzt sich nur bei
  echtem Reboot zurueck. Details:
  [CHANGELOG.md](../CHANGELOG.md) 2026-09-09 noch später.

* **Update 2026-09-09, noch später — mögliche echte Abhilfe auf
  Devicetree-Ebene gefunden, nicht selbst umsetzbar (kein Root, Reboot zum
  Testen nötig).** Der beim Rebind-Test aufgetretene I2C-Bus-Lockup
  (`SDA stuck at low`) betrifft `i2c@88000` (RP1) — dessen Devicetree-Knoten
  hat **keine** `scl-gpios`/`sda-gpios`-Eigenschaften. Linux' eingebaute
  generische GPIO-Bus-Recovery (`i2c_generic_gpio_recovery`, Standardmechanismus
  genau für einen haengenden SDA-Zustand) ist fuer diesen Bus also gar nicht
  verdrahtet — ein Stuck-Zustand kann sich derzeit nicht von selbst
  erholen. Waere dieses Feature per Overlay/Basis-Devicetree ergaenzt
  (setzt voraus, dass RP1s Pinmux SCL/SDA waehrend der Recovery als
  reine GPIOs freigeben kann), koennte der Kernel einen solchen Lockup
  selbststaendig ohne jeden Host-Reboot beheben — unabhaengig davon, was
  die eigentliche RP2040-Ursache ist. Im Issue nachgetragen:
  [Kommentar](https://github.com/raspberrypi/linux/issues/7613#issuecomment-5599575083).
  Nicht selbst umgesetzt: braucht Root zum Bauen/Installieren eines
  Overlays und einen Reboot zum Testen.

* **Antwort landet in:** `docs/lab_journal.md`, `docs/HARDWARE_PROFILE.md`,
  gegebenenfalls `scripts/camera-commissioning.sh` und `docs/ROADMAP.md`.
