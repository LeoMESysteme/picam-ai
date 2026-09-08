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
* **Antwort landet in:** `docs/lab_journal.md`, `docs/HARDWARE_PROFILE.md`,
  gegebenenfalls `scripts/camera-commissioning.sh` und `docs/ROADMAP.md`.
