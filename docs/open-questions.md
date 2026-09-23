# Offene Punkte

Jede Unbekannte hat eine Nummer `OQ-nn`. **Einträge werden nie gelöscht**, nur
auf `geklärt` oder `verworfen` gesetzt — mit Datum, Antwort und Verweis darauf,
wo die Antwort gelandet ist. So bleibt nachvollziehbar, warum etwas so ist.

Status: `offen` · `in Arbeit` · `geklärt` · `verworfen`

OQ-01 bis OQ-06 sind die sechs offenen Entscheidungen aus Konzept.md §11.

**Übersicht.** Die Tabelle erzeugt `scripts/oq-index.py` aus den Überschriften
und Statuszeilen. Nach einem neuen OQ oder einem Statuswechsel das Skript
laufen lassen. `tests/test_oq_index.py` fällt, wenn die Tabelle veraltet ist.
Einzelne Einträge gezielt öffnen: `grep -n '^## OQ-22' docs/open-questions.md`,
dann ab dieser Zeile lesen.

<!-- OQ-INDEX:START — erzeugt von scripts/oq-index.py, nicht von Hand bearbeiten -->

| OQ | Status | Titel |
| --- | --- | --- |
| OQ-01 | offen | Welches serielle Format akzeptiert die eingesetzte GSVmulti-Version? |
| OQ-02 | offen | Welche maximale Zeitabweichung zwischen DUT und Referenz ist zulässig? |
| OQ-03 | offen | Kann die Referenz einen Trigger oder Zeitstempel bereitstellen? |
| OQ-04 | teilweise geklärt | Welche Gerätetypen bilden den ersten freizugebenden Umfang? |
| OQ-05 | offen | Ist eine einmalige Bestätigung durch den Laboranten im Ablauf vorgesehen? |
| OQ-06 | offen | Wie werden ungültige Werte in GSVmulti und in der Kalibrierauswertung behandelt? |
| OQ-07 | offen | GSVmulti-Telegrammspezifikation beschaffen |
| OQ-08 | geklärt | An welchem CAM-Anschluss hängt die Kamera? |
| OQ-09 | offen | RS-232-/RS-485-Transceiver und galvanische Trennung |
| OQ-10 | offen | Spezialisierte 7-Segment-Traineddata für Tesseract |
| OQ-11 | offen | Workstation für die IMX500-Modellkonvertierung |
| OQ-12 | geklärt | Was ohne angeschlossene Kamera nicht verifizierbar war |
| OQ-13 | offen | Anzeigepolarität und der Fall „alle Stellen zeigen 8" |
| OQ-14 | offen | Freigabeschwellen an realen Geräten validieren |
| OQ-15 | geklärt | `tesseract-ocr`, `socat` und `chrony` installieren |
| OQ-16 | geklärt | Vollständigkeit des lokalen Planungsstands |
| OQ-17 | offen | Sichtbarer Dezimalpunkt und Profilannahme unterscheiden |
| OQ-18 | offen | Welches neuronale OCR-Modell trägt auf realen Displays? |
| OQ-19 | offen | Freigabeevidenz für weitere OCR-Backends |
| OQ-20 | offen | Auto-Setup gegen Multiplexing echter Anzeigen absichern |
| OQ-21 | offen | HTTPS-Browserabnahme der Workbench |
| OQ-22 | offen | Sensor setzt nach Streamwechsel keinen Stream mehr auf |
| OQ-23 | offen | Festes Segmentraster passt nicht zur realen BK-5491B-VFD-Schrift |
| OQ-24 | in Arbeit | Browserreaktion und Shutdown nach ROI-Bestätigung real abnehmen |
| OQ-25 | offen | Vorschlagsqualität von `fit_quad_in_region`/`fit_ocr_box` an realen Geräten |
| OQ-26 | offen | Grenzen der Nachführung an realen Geräten validieren |
| OQ-27 | offen | Rasterfeinschliff je Bild bewusst nicht gebaut |
| OQ-28 | offen | Eindeutigkeit der Autofit-Geometrie |
| OQ-29 | offen | Zeitpunkt von `calibrated_on`/`calibrated_on_frame_sequence` |
| OQ-30 | offen | `roi`-Op ist nicht atomar gegenüber einem fehlschlagenden `QuadTracker`-Aufbau |
| OQ-31 | geklärt | Stale-Vorschau-Zustand bei manueller Regler-Bearbeitung nach Autofit |
| OQ-32 | offen | `_row()`/`edit_row()` haben keinen sicheren Fallback für einen unbekannten `kind` |
| OQ-33 | offen | Ähnlichkeitsschwellwert des Datensatz-Sammelmodus ist unvalidiert |
| OQ-34 | offen | Realer interaktiver Browserdurchlauf des Datensatz-Sammelmodus steht aus |
| OQ-35 | offen | Automatisierte Testwerterzeugung für den Datensatz-Sammelmodus (GPIO/BK-5491B) |
| OQ-36 | offen | Sättigungsbasierte LCD-Quad-Findung nur an einem Gerät gemessen |
| OQ-37 | BEANTWORTET 2026-09-22 | Anzeigeformat des GSV-Sensors bei Werten ab 10 mV/V ungemessen |
| OQ-38 | weitgehend geklärt 2026-09-22 | Ground-Truth-Quelle für Auto-Labeling: Displaybus oder Geräteschnittstelle? |
| OQ-39 | offen | Ziffernabdeckung des GSV-Datensatzes ist durch den festen Stimulus begrenzt |
| OQ-40 | offen | Schwelle für „Telegrammlücke" im Gate-Labeler ist ungemessen |
| OQ-41 | teilweise geklärt 2026-09-23 | Telegramm und Anzeige unterscheiden sich in der führenden Null |

<!-- OQ-INDEX:END -->

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

* **Status:** teilweise geklärt (Technologie), Gerätezahl/-familie weiter offen
  · **Zuständig:** Labor
* **Blockiert:** Umfang des Datensatzes (P2) und die Abnahmekriterien (P7).
* **Vorabdefault:** mit GSV-2ASD und einem AST-Gerät beginnen; die Architektur
  bleibt anzeigetyp-agnostisch.
* **Günstigstes Experiment:** zwei Wochen Zählstrich am Prüfplatz — welche
  Geräte kommen tatsächlich am häufigsten?
* **Antwort landet in:** [ROADMAP.md](ROADMAP.md), `datasets/README.md`

* **Update 2026-09-21, Technologie vom Nutzer bestätigt:** Alle im
  Produktivbetrieb zu lesenden Anzeigen sind **LCD**
  (`layout.polarity = "dark_on_bright"`), nicht LED/VFD. Das betrifft die
  eigentlichen Messverstärker-Displays (GSV-/AST-Geräte), **nicht** den
  aktuellen Sammelmodus-Entwicklungsbestand: die beiden bisher registrierten
  Geräte "RND-Lab" und "BK Precision" (73 reale Proben, siehe
  [VALIDATION.md](VALIDATION.md) 2026-09-21) sind Laboraufbauten mit
  `technology=LED`, physisch aber teils VFD (BK-5491B, siehe OQ-23-Kopf) —
  keines davon ist LCD. Der bisherige reale Dataset-Benchmark-Lauf prüft
  damit die Pipeline-Mechanik korrekt, ist aber **nicht** repräsentativ für
  die tatsächliche Zielhardware. Konsequenz: Sobald ein LCD-Gerät verfügbar
  ist, gehört es vorrangig in den Sammelmodus aufgenommen - die
  LED/LCD-Vielfaltsvorgabe aus dem Exportziel
  (`docs/status.md`, „mindestens 6 verifizierte Geräte, 3 Familien, LED und
  LCD") ist jetzt weniger eine Vielfaltsvorgabe als eine **Zielhardware-
  Vorgabe**: LCD ist Pflicht, LED/VFD bleiben nur als zusätzliche
  Entwicklungsdaten wertvoll.

## OQ-05 — Ist eine einmalige Bestätigung durch den Laboranten im Ablauf vorgesehen?

* **Status:** offen · **Zuständig:** Labor
* **Blockiert:** das Bedienkonzept, nicht die Kette. Der `manual_roi`-Pfad ist
  bereits der Primärpfad und setzt die Bestätigung voraus.
* **Vorabdefault:** Bestätigung ist vorgesehen (Konzept §4 „bevorzugter
  Betrieb"), Vollautomatik ist spätere Option.
* **Update 2026-09-10, Implementierungsentscheidung (keine Antwort auf diese
  OQ):** Bedienerwunsch: Die Workbench verlangt jetzt technisch **pro
  Sitzung** eine erneute Bestätigung statt einer dauerhaft ohne weiteren
  Blick gültigen einmaligen Bestätigung — `Controller.__init__` setzt
  `confirmed` einer geladenen Geometrie auf `false` (nur die Laufzeitkopie,
  die gespeicherte Profildatei bleibt unverändert; `roi`/`roi_quad`/`ocr_box`
  bleiben als Startpunkt erhalten), der `run`-Modus ist bis zur erneuten
  Bestätigung gesperrt, und die volle Kandidatensuche läuft auf dem Livebild
  wieder mit. Das ist eine Softwareentscheidung für den Editor-Workflow,
  **keine** Antwort auf die eigentliche, weiterhin offene Labor-/QM-Frage
  dieser OQ (ob eine einmalige Bestätigung je Geräteinstanz betrieblich
  vorgesehen ist) — dafür bräuchte es weiterhin die Antwort aus dem Labor.

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
* **Befund:** Die Spezifikation liegt lokal nicht vor.
* **Korrektur der Abrufaussage (2026-09-22):** Die bisherige Formulierung
  „`me-systeme.de` blockt automatische Abrufe mit HTTP 403" ist **zu pauschal**.
  Gemessen am 2026-09-22:
  * **PDF-Anleitungen unter `/produkte/.../anleitungen/` liefern HTTP 200.**
    Heruntergeladen und lokal abgelegt sind jetzt
    `var/datenblaetter/gsv2-bedienungsanleitung.pdf` (GSV-2, enthält das
    RS232-Protokoll des **Geräts**) und `var/datenblaetter/ba-gsvmulti.pdf`
    (GSVmulti-Bedienungsanleitung, Stand 13.08.2011, 10 Seiten). **`var/` ist
    gitignored** — beide Dateien sind lokal, nicht im Repo; dauerhaft sind nur
    die oben genannten URLs.
  * **HTML-Produktseiten liefern weiterhin HTTP 403** (geprüft an
    `https://www.me-systeme.de/en/gsv-2as-05`).
* **Warum OQ-07 trotzdem offen bleibt:** Das beschaffte GSVmulti-Handbuch von
  2011 ist eine **Bedienungsanleitung der Oberfläche** (Kanal hinzufügen,
  Skalierung, Speichern), **keine Telegrammspezifikation**. Gesucht ist laut
  Konzept §12 ausserdem die Version 2.6, nicht die von 2011. Die
  GSV-2-Anleitung dokumentiert das Protokoll des **Messverstärkers** — was
  GSVmulti als Eingang **akzeptiert**, ist damit nicht belegt, sondern nur
  plausibel. Es wird nichts geraten ([AGENTS.md](../AGENTS.md), „Kein Erfinden
  von Protokollen").
* **Belastbarste Quelle ist nicht die Doku, sondern ein Mitschnitt:** ein
  vorhandenes GSV-2/GSV-3 im ASCII-Modus an GSVmulti hängen und den realen
  Datenstrom aufzeichnen. Das liefert das tatsächliche Telegramm. **Neu
  verfügbar dafür:** das Laborgerät ist als **GSV-2AS** identifiziert
  ([OQ-38](open-questions.md)) und beherrscht laut Anleitung genau diesen
  ASCII-Modus — das für dieses Experiment nötige Gerät ist also vorhanden.
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
     umgekehrter Polarität fehlt die Behandlung. — **geklärt (2026-09-18)**,
     siehe Update unten. Fall 1 bleibt offen.
* **Lösungsansatz:** Polarität ins Geräteprofil aufnehmen; als
  Off-Referenz zusätzlich eine Panelfläche außerhalb der Segmente abtasten.

* **Update 2026-09-18, Fall 2 (Polarität):** `DisplayLayout` hat jetzt ein
  Feld `polarity: "bright_on_dark" | "dark_on_bright"` (Default
  `bright_on_dark`, reproduziert das bisherige Verhalten unveränderten
  gespeicherten Profilen gegenüber). `SevenSegmentReader.read` invertiert das
  Graustufenbild einmalig am Anfang, wenn `polarity == "dark_on_bright"`
  (`src/dispread/ocr/sevenseg.py`) — danach gilt im ganzen Leser wieder
  "hell = an", keine zweite Fallunterscheidung. `profiles.validate_layout`
  lehnt unbekannte Polaritätswerte ab. Die Workbench hat dazu eine
  Auswahlzeile `layout.polarity` (`src/dispread/workbench/fields.py`).
  Getestet in `tests/test_sevenseg.py`
  (`test_lcd_polaritaet_wird_gelesen`,
  `test_falsche_polaritaet_wird_abgelehnt_nicht_falsch_gelesen`,
  `test_unbekannte_polaritaet_wird_abgelehnt`): eine falsch eingestellte
  Polarität lehnt ab, sie liest nicht stillschweigend falsch. Fall 1 (Anzeige
  zeigt ausschließlich "8", keine inaktive Klasse vorhanden) ist davon
  unberührt und bleibt offen.

## OQ-14 — Freigabeschwellen an realen Geräten validieren

* **Status:** offen
* **Befund:** Alle Schwellen in `GateConfig` sind Vorabdefaults, keine
  validierten Grenzen. Konzept §7 verlangt ausdrücklich, sie an realen, auch
  bisher unbekannten Gerätetypen zu validieren.
* **Blockiert:** die Abnahme. Aufgabe von P3/P7.
* **Antwort landet in:** [VALIDATION.md](VALIDATION.md)

## OQ-15 — `tesseract-ocr`, `socat` und `chrony` installieren

* **Status:** geklärt (2026-09-21)
* **Befund:** Seit dem Reboot am 2026-09-07 verlangt `sudo` ein Passwort, die
  Installation konnte nicht automatisch erfolgen. Benötigt:
  `sudo apt install -y tesseract-ocr tesseract-ocr-eng socat chrony`
* **Wirkung:** Ohne `tesseract` fehlt die OCR-Vergleichsbasis, ohne `chrony`
  ist Messung M1 (Offset und Drift) nicht protokollierbar. `socat` ist nur
  Komfort — die Tests nutzen `os.openpty()` aus der stdlib.
* **Antwort landet in:** [dependencies.md](dependencies.md)
* **Antwort (2026-09-21):** Alle drei sind auf dem Lab-Pi installiert
  (`tesseract 5.5.0`, `socat`, `chrony 4.6.1-3`) - per `which`/`dpkg -l`
  geprueft. Der Eintrag war nur nicht aktualisiert; kein offener Blocker
  mehr. `dispread.ocr.tesseract_cli` ist geschrieben und ruft die
  tesseract-Binary auf (siehe CHANGELOG 2026-09-21) — ein produktiver,
  erfolgreicher Read gegen echte GSV-Sensor-Fotos steht noch aus (0/11
  Proben liefern bisher einen Wert, siehe docs/status.md).

## OQ-16 — Vollständigkeit des lokalen Planungsstands

* **Status:** geklärt (2026-09-10)
* **Befund:** Unter anderem `ROADMAP.md`, `dependencies.md`,
  `HARDWARE_PROFILE.md` und `lab_journal.md` werden referenziert, fehlen aber
  im aktuellen Arbeitsbaum unter `docs/`. Auch mehrere im Status genannte
  CLI-/Replay-Komponenten sind lokal nicht vorhanden. Frühere Messangaben
  werden deshalb als dokumentierte Ergebnisse, nicht als neu verifiziert behandelt.
* **Klärung:** Fehlende Dateien wiederherstellen oder Verweise und Meilensteine
  mit dem tatsächlich vorhandenen Stand abgleichen.
* **Antwort (2026-09-10):** `docs/ROADMAP.md`, `docs/dependencies.md`,
  `docs/HARDWARE_PROFILE.md` und `docs/lab_journal.md` liegen inzwischen alle
  mit Inhalt im Arbeitsbaum vor (per `ls docs/` geprüft). Die im Status
  genannte CLI-Komponente existiert: `src/dispread/workbench/cli.py` hat ein
  funktionierendes `stop`-Subkommando (bildet `dispread stop` aus
  `docs/status.md` ab). Die Replay-Komponente ist weiterhin nur ein
  Registry-Eintrag ohne Implementierung (`src/dispread/frames/__init__.py`
  registriert `replay`, es gibt kein `replay_source.py`) — das deckt sich mit
  `CLAUDE.md`, wo `replay://` ausdrücklich als "nur Registry-Eintrag, TODO"
  geführt wird, war also keine Doku-Abweichung.
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

* **Update 2026-09-21, empirischer Datenpunkt aus dem Sammelmodus
  (`docs/PLAN_2026-09-21-dataset-benchmark.md`):** Die BK-Precision-Situation
  `26692830cde04118b69f5b2c60c40335` mischt innerhalb **einer** Sitzung zwei
  Punktpositionen bei gleicher Ziffernzahl: Werte wie `012.38` (2
  Nachkommastellen) stehen neben `-0.0009`/`-0.0010` (4 Nachkommastellen) -
  das Gerät hat den Messbereich mitten in der Aufnahmesitzung gewechselt.
  Das ist die konkrete Antwort auf die obige Frage „welche Geräte können
  Punkt/Messbereich während eines Laufs wechseln": mindestens das
  BK-5491B tut es, beobachtet, nicht nur befürchtet. Für den Dataset-
  Benchmark (Task 3, `target_layout`) folgt daraus: Nachkommastellen dürfen
  **nie** über eine ganze Faltung eingefroren werden, sondern müssen je
  Zielprobe aus deren eigenem `expected_text` kommen - ein eingefrorenes
  `decimals` hätte hier garantiert die Fehlerklasse `decimal` erzeugt, nicht
  von der Optik verursacht, sondern vom Prüfstand selbst fabriziert.

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
* **Siebter Datenpunkt, 2026-09-22 — die Regel wurde verletzt und der Fehler
  trat sofort wieder auf.** Nach einem Reboot (Kamera wurde erst danach
  überhaupt wieder enumeriert) startete `scripts/sync-record.py` mit seiner
  damaligen Vorgabe **2028×1520**. Ergebnis: kein einziges Bild, der Prozess
  hing in `capture_request`, wurde per Signal beendet — und ab da setzte der
  Sensor keinen Stream mehr auf. `rpicam-hello -t 3000` erzeugte danach
  **33 × `stream on failed in subdev` in 0,11 s**, mit
  `cfe_stop_streaming+0xd4/0x200 [rp1_cfe]` im Aufrufpfad. Enumeration blieb
  wie gehabt intakt (`rpicam-hello --list-cameras` meldet den Sensor
  vollständig) — die Diagnose prüft den Bilddurchlauf eben nicht.

  Der Datenpunkt fügt der Tabelle nichts Neues hinzu, er **bestätigt sie**:
  grosser Sensormodus → letzte Sitzung des Boots. Bemerkenswert ist nur, dass
  ein neu gebautes Werkzeug die dokumentierte Betriebsgrösse nicht übernommen
  hatte.

  **Konsequenz, umgesetzt:** `scripts/sync-record.py` hat jetzt die Vorgabe
  **960×720** und **weist grosse Sensormodi hart ab** (`--camera-size` über
  1 MPixel → Abbruch mit Verweis auf diesen Eintrag), aufhebbar nur über ein
  ausdrückliches `--allow-large-sensor-mode`. Eine Warnung auf stderr wäre zu
  wenig gewesen: die Folge ist ein Reboot des Labor-Pi.
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
  **Erneut aufgetreten 2026-09-23, 12:15:23:** 6 × `stream on failed in
  subdev`, dazu um 12:16:15 ein WARN-Trace in `cfe_stop_streaming`. Der Lauf
  war 960×720 mit `ScalerCrop` `1730,966,806,604`. Davor liefen im selben
  Boot mehr als 20 Aufnahmen sauber, auch mit `ScalerCrop`. Vorausgegangen
  war das Drehen am Fokusring. **Wahrscheinlichere Ursache, vom Nutzer
  vermutet und am Kernel-Log bestätigt:** In diesem Boot liefen **20
  erfolgreiche Streamstarts** (`Using a link rate`, 09:54 bis 12:10), der
  **21.** ist gescheitert. Direkt davor steht `imx500_power_on: failed to get
  led gpio`. Das passt zur Grenze vom 2026-09-09 (nach grob 20–25
  Power-Zyklen ist der RP2040 unerreichbar). Der Fokusring als Ursache ist
  damit unwahrscheinlich. **Folge:** Die Streamstarts brauchen ein Budget je
  Boot, und die Werkzeuge müssen mit wenigen, langen Kamerasitzungen
  auskommen. `sync-record.py` meldete den Lauf mit 0 Bildern als vollständig.
  Das ist ein Bug und wird behoben.
  **(d) erledigt 2026-09-23:** Das Skript prüft das Kernel-Log auf
  `stream on failed` und macht eine gebundene Testaufnahme (640×480). Bei
  belegtem Gerät weicht es aus, statt zu kollidieren. Gegen die Hardware
  bestanden.
  **Erneut aufgetreten 2026-09-23, 15:57:10, direkt nach Reboot und
  Commissioning:** Bootzeit 14:24:31; die erste Commissioning-Sitzung um
  15:55 lieferte ein echtes 640×480-Bild. Die unmittelbar folgende
  960×720-Fokussitzung lieferte dagegen 0 Bilder und sofort
  `imx500_power_on: failed to get led gpio` sowie 6 × `stream on failed in
  subdev`. Der Nutzer hatte den Fokusring noch nicht berührt. Zwei
  `Using a link rate`-Zeilen stehen bei der erfolgreichen Sitzung; ob diese
  intern mehr als einen Power-Zyklus verbrauchte oder der Warmstart den
  RP2040 nicht zuverlässig zurücksetzte, ist offen. **Folge:** Das Budget 15
  bleibt eine Sperre gegen bekannte Erschöpfung, darf aber nicht als Zusage
  von 15 erfolgreichen Starts verstanden werden. Diagnose:
  `var/diagnostics/focus-handoff-2026-09-23/` (nicht versioniert), Zahlen in
  `VALIDATION.md`, Aufbau im Laborjournal.
  **Nachtrag 2026-09-23, 16:17:35:** Nach einem weiteren verifizierten
  Warmreboot (Boot-ID `6c6abda2-d316-40da-b557-1124431ade30`) scheiterte
  sogar der **erste** 960×720-Streamstart dieses Boots, ohne vorherige
  Commissioning-Sitzung. Vor dem LED- und CFE-Fehler meldete die
  `rp2040-gpio-bridge` selbst `rp2040_gbdg_wait_until_free failed` und
  `rp2040_gbdg_gpio_dir_out(19, 0) could not ST_CL`. Das
  Streamstart-Budget erklärt den neuen Fehlschlag nicht. Ob ein
  vollständiger Stromzyklus des Pi die Bridge wiederherstellt, bleibt
  offen; wegen anderer Dienste wurde er nicht durchgeführt.
* **Warum das wichtig ist:** Der Kamerathread der Workbench setzt den Stream bei
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

## OQ-23 — Festes Segmentraster passt nicht zur realen BK-5491B-VFD-Schrift

* **Status:** offen · erkannt 2026-09-09 bei der ersten realen
  Workbench-OCR-Prüfung
* **Befund:** Im beschrifteten Realbild
  `var/workbench/diagnostics/fokus-erreicht-960x720.jpg` steht `-000.13 mV`.
  Mit manuell auf Vorzeichen und fünf Stellen gelegter ROI, Layout
  5 Stellen / 2 Nachkommastellen / `mV` und `sign_cell_ratio=0.6` liefert
  `sevenseg/2` jedoch `777?7`, keinen Zahlenwert und die Ablehnungsgründe
  `unreadable_cells:1`, `no_value`. Die Freigabe bleibt korrekt
  `unreadable`; es entstand keine stille gültige Fehlablesung. Das Overlay
  zeigt als Ursache eine nicht ausreichend passende feste Abtastgeometrie:
  insbesondere die schmale VFD-`1` liegt nicht auf denselben relativen
  Segmentpunkten wie der synthetische Generator.
* **Konsequenz:** Die Workbench-Bedienung und die sichere Ablehnung sind
  implementiert, aber eine reale Erkennungsquote ist damit nicht belegt.
  Dieser eine Aufbau darf weder zum Nachstimmen und anschließenden Bewerten
  desselben Bildes noch zur Konfidenzkalibrierung verwendet werden.
* **Klärung:** Einen bestätigten Replay-Datensatz mit getrenntem Entwicklungs-
  und Testsatz erfassen. Dann profilierbare Segmentgeometrie bzw. flächige
  Segmentmessung gegen Tesseract/weitere Backends vergleichen und pro
  Fehlerklasse auswerten. Referenzwerte bleiben außerhalb von
  `ValueReader.read` und `ReleaseGate.evaluate`.
* **Blockiert:** reale Abnahme des Segmentlesers in P3, nicht die
  Workbench-Einrichtung.
* **Antwort landet in:** `src/dispread/ocr/`, Geräteprofile und
  `docs/VALIDATION.md`; Rohbefund im Laborjournal vom 2026-09-09.

* **Update 2026-09-09:** Die Workbench kann jetzt vier Displayecken einzeln
  bestätigen und perspektivisch auf 400×160 entzerren. Das beseitigt einen
  Geometriefehler des bisherigen achsparallelen Ausschnitts, klärt OQ-23 aber
  nicht: Die abweichende VFD-Glyphenform braucht weiterhin mehrere bestätigte
  reale Entwicklungs- und Testbilder.

* **Update 2026-09-09, Rasterkalibrierung:** Ein eigener `ocr_box` kann jetzt
  innerhalb der entzerrten ROI an Vorzeichen und Ziffern ausgerichtet werden.
  Der eingefrorene Editor zeigt dabei Zellen und reale Segment-Abtastpunkte.
  Damit lässt sich die bekannte Rasterverschiebung manuell beseitigen; ob die
  VFD-Glyphen danach mit den festen relativen Segmentpunkten zuverlässig lesbar
  sind, bleibt am getrennten Real-Testset zu klären.

* **Update 2026-09-09, Ziffernabstand:** Bedienerbeobachtung im Browser zeigte
  zu weit auseinanderliegende Segment-Abtastpunkte, weil `cell_boxes` bislang
  keinen Zwischenraum zwischen den Stellen kannte. Neues Layoutfeld
  `digit_gap_ratio` (Default `0.0`, Bedienzeile „ziffernabstand") lässt den
  Abstand jetzt mitkalibrieren; siehe [CHANGELOG.md](../CHANGELOG.md) 2026-09-09
  (Zwischenraum zwischen Ziffernstellen). Das ist eine unabhängige
  Geometriekorrektur und klärt OQ-23 weiterhin nicht abschließend — die
  abweichende VFD-Glyphenform braucht weiterhin einen bestätigten
  Real-Testsatz.

* **Update 2026-09-09, Obergrenze nachgeschärft:** Bedienerrückmeldung: Die
  Obergrenze `digit_gap_ratio <= 1.0` reichte für die reale Anzeige nicht;
  das native Zahlenfeld klemmte dort ohne Rückmeldung. Auf `3.0` angehoben,
  siehe [CHANGELOG.md](../CHANGELOG.md) 2026-09-09. Weiterhin ein
  unvalidierter Vorabdefault wie die übrigen `LAYOUT_RATIOS`-Einträge.

* **Update 2026-09-09, Empfindlichkeit gegen Helligkeits- und
  Punktabweichung:** Bedienerrückmeldung am realen Gerät: Eine Ziffer, die
  etwas schwächer leuchtet als die übrigen, oder ein Abtastpunkt, der nicht
  exakt auf der Segmentmitte liegt, führt spürbar häufig zur Ablehnung
  ("funktioniert nicht mehr richtig"). Zwei mögliche, nicht gegeneinander
  abgegrenzte Ursachen im aktuellen `sevenseg.py`:
  1. `segment_threshold()` schwellt bewusst über die **gepoolten** Segmentmessungen
     aller Stellen (Begründung im Code: verhindert Fehlablehnung bei "8" und
     falsche Panel/Segment-Trennung, siehe OQ-13). Das macht die Schwelle aber
     unempfindlich für eine Stelle, die insgesamt dunkler ist als die
     übrigen - ihre eigenen aktiven Segmente können unter der von den
     helleren Stellen dominierten globalen Schwelle liegen.
  2. `_SAMPLE_HALFWIDTH = 0.06` (Fensterradius je Abtastpunkt, Anteil der
     Zellenbreite) ist klein genug, dass ein leicht daneben liegender Punkt
     bereits Panel- statt Segmentpixel mittelt - dieselbe Rasterungenauigkeit
     wie OQ-23, hier als Messempfindlichkeit statt als Positionsfehler
     sichtbar.
  * **Bewusst nicht angefasst:** `_MIN_CONTRAST`/`_SAMPLE_HALFWIDTH` ohne
    reale Testbilder zu lockern hätte nach Konzept.md §7 das falsche
    Vorzeichen - es senkt die Ablehnungsschwelle blind und kann aus einer
    sicheren Ablehnung eine unsichere, falsch "sichere" Ablesung machen.
    Genau das verbietet AGENTS.md ("keine Vermutung"). `GATE_CONFIRM_FRAMES`
    (siehe oben, [CHANGELOG.md](../CHANGELOG.md) 2026-09-09) mindert nur das
    Flackerbild, nicht diese Empfindlichkeit.
  * **Klärung:** Braucht denselben bestätigten Real-Testsatz wie OQ-23 -
    insbesondere Aufnahmen mit gezielt unterschiedlich hellen Stellen -, um
    zwischen (1) und (2) zu unterscheiden und eine Änderung tatsächlich zu
    validieren statt zu raten.

* **Update 2026-09-09, mit zwei echten Annotationen belegt - Ursache (1)
  bestätigt, (2) nicht die Hauptursache:** Bediener speicherte im neuen
  `annotate`-Modus zwei echte Aufnahmen einer roten LED-Anzeige, beide
  zeigen `11.00` (4 Stellen, 2 Nachkommastellen, `digit_gap_ratio=0.65`,
  Profile `var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd` und
  `.../8a18ee05e31241b9b6702c5bb904ec97`). Der aktuelle Leser liest sie als
  `11?0` bzw. `110?` - exakt die gemeldete Ablehnung.
  * **Direkt nachgemessen** (`_sample()` je Segment vor dem Schwellwert,
    reproduziert über `crop_box`+`SevenSegmentReader.read` wie im echten
    Pfad): Die "aus"-Segmente liegen in beiden Bildern eng gebündelt bei
    Helligkeit 0,20-0,28. Die tatsächlich **an**-Segmente einer echten `0`
    streuen dagegen breit von rund 0,38 bis 0,85 - je nach Aufnahme ist ein
    anderes Segment das dunkelste (Stelle `a` in Bild 1, Stelle `c`/`e` in
    Bild 2). Der eine gepoolte, globale Schwellwert aus
    `segment_threshold()` liegt zwangsläufig irgendwo in dieser breiten
    Spanne und reisst je nach Aufnahme ein anderes, tatsächlich leuchtendes
    Segment mit ab. Damit ist Ursache (1) oben an echten Daten bestätigt.
  * **Gegenprobe zu Ursache (2) (Punkt-/Rasterversatz) durchgeführt:** Ein
    Einzelschritt-Warp direkt vom Rohbild statt der doppelten
    Größenänderung `rectify()` (auf 400×160) gefolgt von `crop_box()`
    (nochmals auf 400×160 hochskaliert) wurde probeweise nachgebaut. Er
    behebt die Fehlablesung nicht zuverlässig - in Bild 1 wird dadurch sogar
    eine zweite Stelle unlesbar, in Bild 2 bleibt weiterhin eine Stelle
    unlesbar, nur eine andere. (2) ist damit nicht die Hauptursache dieses
    konkreten Befunds; die doppelte Größenänderung bleibt aber eine separat
    beobachtete, unnötige Auflösungs-/Schärfeverlustquelle im
    `rectify()`→`crop_box()`-Pfad, unabhängig bewertet.
  * **Vorgeschlagene, noch nicht umgesetzte Lösung (auf Bedienerwunsch
    zurückgestellt, "erstmal nur dokumentieren"):** Grenzfall-Auflösung im
    Decoder - wenn das binäre An/Aus-Muster einer Zelle in keiner Tabelle
    steht, aber genau einem Tabellen-Digit bis auf Segmente entspricht, die
    innerhalb einer kleinen Toleranzbreite um den Schwellwert liegen, dieses
    eine Digit mit entsprechend reduzierter Konfidenz übernehmen - sonst wie
    bisher ablehnen. Enger als `_MIN_CONTRAST`/`_SAMPLE_HALFWIDTH` pauschal
    zu lockern, aber weiterhin eine Änderung an "unlesbar ablehnen statt
    raten" (Konzept.md §7) und deshalb nicht ohne ausdrückliche Freigabe
    umzusetzen.
  * **Klärung:** Umsetzung und Validierung der Grenzfall-Auflösung gegen
    diese zwei Bilder plus die bestehende Testsuite, sobald gewünscht.
    Zusätzliche echte Annotationen (auch mit bewusst unterschiedlicher
    Displayhelligkeit) würden die Validierung deutlich verlässlicher machen
    als zwei Aufnahmen aus derselben Kalibriersitzung.

* **Update 2026-09-11, breitere Messung — Ursache (1) erneut bestätigt, und ein
  neuer, bisher unbekannter Befund.** Zahlen und Verfahren vollständig in
  [VALIDATION.md](VALIDATION.md), Abschnitt „2026-09-11 — Ausgangsmessung
  `sevenseg/2`"; Aufbau und Deutung in [lab_journal.md](lab_journal.md).
  * **Datenlage korrigiert:** Es liegen **neun** Annotationen vor, sechs davon
    mit getipptem Sollwert — dieser Eintrag und OQ-25 nannten bisher zwei.
    Alle sechs stammen weiterhin von **einer** Geräteinstanz; der Satz bleibt
    damit ein Entwicklungssatz, kein Testset.
  * **Ist-Stand:** 5 korrekt, **0 falsch angenommen**, 1 abgelehnt.
  * **Ursache (1) unabhängig erneut belegt, diesmal als Stelle-zu-Stelle-
    Differenz:** In `8a18ee05` misst das tatsächlich leuchtende `e` der letzten
    Stelle 0,38, während dieselben Segmente der Nachbarstelle bis 0,85
    erreichen. Die eine globale Schwelle liegt dazwischen.
  * **Neuer Befund — Segment `a` leuchtet, wo es nicht leuchten sollte:** In
    `6ffc561b` misst Segment `a` der Stelle 0 roh 0,38, während `b`/`c`
    derselben Stelle bei 0,76/0,84 liegen; die Stelle zeigt eine `1`, `a` muss
    also aus sein. Eine panelbezogene Entscheidungsregel dekodiert diese Stelle
    deshalb als `7`. Ursache ungeklärt — Übersprechen zur Nachbarstelle,
    Nachleuchten des VFD oder ein Abtastpunkt, der über die Zellgrenze reicht,
    sind nicht gegeneinander abgegrenzt.
  * **Daraus das Abnahmekriterium für jede künftige Decoder-Änderung:**
    `6ffc561b` Stelle 0 liefert `1` **oder** wird abgelehnt — niemals `7`. Und
    die Zahl der falschen Annahmen bleibt bei **0**; gegen diese Ausgangszahl
    blockiert bereits eine einzige falsche Annahme die Änderung, unabhängig
    davon, wieviele zusätzliche Treffer sie bringt.
  * **Verworfen, mit Grund:** Otsu *innerhalb* einer Zelle als
    Entscheidungsschwelle. Bei sechs aktiven und einem inaktiven Segment
    maximiert es die gewichtete Zwischenklassenvarianz mit einem ausgewogenen
    4:3-Schnitt statt des richtigen 6:1-Schnitts — gemessen wirkungslos.
  * **Flächige Segmentmessung ist mit den heutigen Profilwerten schlechter**
    (3 statt 5 korrekt), weil `thickness_ratio`/`inset_ratio` nie kalibriert
    wurden. Ein Sweep zeigt zwei weit auseinanderliegende Parametersätze mit
    identischer Punktzahl — die Geometrie ist durch sechs Bilder eines Geräts
    **unterbestimmt**. Deshalb kommt die Kalibrierung (Autofit) vor der
    Messänderung, siehe
    [PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md).

* **Update 2026-09-21, erstmals gezählt statt an einem Einzelbild vermutet
  (`scripts/dataset-benchmark.py`,
  [PLAN_2026-09-21-dataset-benchmark.md](PLAN_2026-09-21-dataset-benchmark.md)):**
  Gegen **alle 73 lesbaren Proben** des Sammelmodus-Bestands (2 Geräte,
  „RND-Lab" 40, „BK Precision" 33) passt eine grobe Rahmenvorsuche
  (~36 Geometrie-Kandidaten je Probe) **kein einziges Mal** — **0 von 73**,
  achsparallel wie entzerrt, in beiden Geräten. Das bestätigt die frühere
  Einzelbild-Vermutung als gemessenen Befund, nicht mehr als Verdacht: das
  feste relative Segment-Abtastraster passt bei diesem Bestand grundsätzlich
  nicht zur Kameraaufnahme, unabhängig von Geräteserie oder Technologie —
  RND-Lab ist LED, nicht VFD wie BK-5491B, betroffen sind also beide.
  Segmentdiagnose (`segment_report`) an Beispielen zeigt keinen einheitlichen
  Fehlertyp: teils liegt kein einziges Segment über der Schwelle (Stelle 1 in
  `0b5eaacf...`: alle Werte 0,12–0,16, Kontrast zu gering), teils liegt ein
  Muster nahe am Sollmuster, aber nicht identisch (Stelle 2 in
  `0282bca7...`: gemessen `a`/`b`/`f`/`g` aktiv statt `a`/`b`/`c`/`d`/`g` für
  die erwartete „3" — zwei von fünf Segmenten falsch). Das deutet eher auf
  eine grundsätzlich falsche
  Rasterposition/-skalierung als auf eine einzelne Schwellenverschiebung —
  siehe auch OQ-25-Update unten zur Geometrievorsuche selbst. Phase B
  (Leave-one-group-out-Übertragung) konnte dadurch in keiner der 6
  durchgeführten Faltungen (2 von 3 BK-Situationen + 4 RND-Lab-Situationen;
  die dritte BK-Situation „schräg links" hat noch keinen `selected`-Vertreter
  und wurde als Lücke gemeldet, nicht ersetzt) überhaupt eine Übertragungszahl
  liefern — der Vertreter jeder Faltung passte selbst nicht. Rohdaten:
  `docs/VALIDATION.md`, Abschnitt „2026-09-21".
* **Klärung, präzisiert:** Die nächste sinnvolle Stufe ist nicht mehr „mehr
  Bilder sammeln", sondern die Rastergeometrie selbst prüfen — vermutlich
  braucht es eine größere/andere Werte-Spanne in
  `dispread.ocr.autofit._CANDIDATES` als die für synthetische Bilder
  gewählte, oder eine grundsätzlich andere Zellaufteilung (`cell_boxes`)
  für reale Aufnahmen. Das ist jetzt eine Aussage über die Geometrie, keine
  über die Datenmenge mehr.

## OQ-24 — Browserreaktion und Shutdown nach ROI-Bestätigung real abnehmen

* **Status:** in Arbeit · erkannt 2026-09-09 durch Bedienerrückmeldung
* **Befund:** Der Browser wurde nach ROI-Bestätigung langsam bis unbedienbar;
  auch der gestartete Dienst ließ sich aus der Bedienumgebung nicht mehr
  zuverlässig stoppen. Im bisherigen Controller lief pro 15-fps-Bild die
  Vollbild-Kandidatensuche trotz bestätigter ROI weiter, und die gesamte
  OpenCV-/JPEG-Arbeit hielt den Controller-Lock. Der lokale Statussocket des
  beobachteten Prozesses antwortete noch, die UI-Symptomatik selbst ist in der
  Browserumgebung aber nicht reproduziert/profiliert.
* **Änderung:** Vollbildsuche endet nach Bestätigung, OCR-Vorschau ist auf 5 Hz
  begrenzt, OpenCV-/JPEG-Arbeit liegt außerhalb des Locks. Neuer lokaler Befehl
  `dispread stop`; Kameraabschluss mit Zeitgrenze. Ein isolierter simulierter
  Dienst wurde damit erfolgreich beendet.
* **Update 2026-09-10, präzisiert — „Vollbildsuche endet nach Bestätigung"
  galt zu unbedingt.** Bedienerrückmeldung: Nach einem Neustart mit bereits
  bestätigter ROI/OCR aus einer vorherigen Sitzung lief die Kandidatensuche
  (gelbe Boxen) dauerhaft **nie mehr** — kein visueller Hinweis mehr, ob die
  geladene Geometrie noch zur aktuellen Szene passt, obwohl sie nie gegen das
  aktuell laufende Bild geprüft wurde. Die ursprüngliche Änderung hier war
  richtig gegen die 15-fps-Dauerkosten, aber zu grob: „nach Bestätigung nie
  mehr" statt „nur nicht mehr bei jedem Bild". Jetzt läuft die Suche außerhalb
  des `run`-Modus gedrosselt weiter (`CANDIDATE_INTERVAL_S = 1,0 s`,
  `controller.py`); ein Ladevorgang mit bereits bestätigter Geometrie loggt
  zusätzlich einen Warnhinweis. Die Bestätigung selbst bleibt unangetastet —
  keine automatische Übernahme, kein Auto-Un-Confirm. Kostenmessung:
  [VALIDATION.md](VALIDATION.md), Abschnitt „Kosten der wieder aktivierten,
  gedrosselten Kandidatensuche".
* **Update 2026-09-10, spätabends, erneut präzisiert — die wiederhergestellte
  Suche lief noch über das ganze Bild.** Bedienerrückmeldung direkt auf das
  vorige Update: Am realen Prüfstand (Netzteil mit zwei Anzeigen, zwei
  Monitore im Hintergrund, weitere Messgeräte) schlug die Vergleichssuche
  regelmäßig andere Bildschirme im Bild statt der bestätigten Anzeige vor -
  die vorige Änderung ließ `find_display_candidates` (Vollbildsuche)
  unverändert weiterlaufen, nur gedrosselt statt bei jedem Bild. Jetzt nutzt
  `Controller.publish()` stattdessen `fit_quad_in_region` mit `config["roi"]`
  als Suchfenster-Hinweis - der Suchraum bleibt auf die Umgebung der
  bestätigten ROI beschränkt. Zusätzlich neuer Mindestüberdeckungsfilter
  `MIN_HINT_OVERLAP = 0,2` in `fit_quad_in_region` selbst (`vision.py`): ein
  Kandidat muss den ungepolsterten Hinweisbereich zu mindestens 20 %
  überdecken, sonst kann bei einer großzügig bestätigten ROI weiterhin ein
  zufällig rechteckigeres, aber unbeteiligtes Objekt am Rand des
  aufgeweiteten Suchfensters gewinnen - an einer nachgebauten Ablenker-Szene
  verifiziert (`test_fit_quad_in_region_ignores_unrelated_objects_outside_the_hint`).
  Kostenmessung und Realbild-Nachweis: [VALIDATION.md](VALIDATION.md).
* **Update 2026-09-09, Editorzustand:** Eine Bedienprüfung zeigte, dass das
  eingefrorene OCR-Raster Layoutänderungen nicht übernahm und die erhöhte
  Profilrevision danach `Enter` blockierte. Der Status liefert nun das aktuelle
  Raster; reine Layoutänderungen aktualisieren die offene Editierrevision und
  bleiben bestätigbar. Die reale Browserprüfung braucht einen Neustart des vor
  dieser Korrektur gestarteten Diensts und bleibt deshalb Teil der Klärung.
* **Klärung:** Den realen Dienst kontrolliert neu starten, ROI im Windows-
  Browser als Quad bestätigen, Status-/Bildrate beobachten und sowohl Ctrl-C
  als auch `dispread stop` abnehmen. Erst dann auf `geklärt` setzen. Keine
  Aussage über Kameralatenz aus synthetischen oder `FILE_MTIME`-Bildern.
* **Antwort landet in:** `docs/VALIDATION.md`, `docs/lab_journal.md` und dieser
  Eintrag; Browser-Grundproblem siehe auch OQ-21.

## OQ-25 — Vorschlagsqualität von `fit_quad_in_region`/`fit_ocr_box` an realen Geräten

* **Status:** offen · erkannt 2026-09-10 beim Bau der automatischen
  Workbench-Vorschläge ([PLAN_2026-09-10-workbench-editor.md](PLAN_2026-09-10-workbench-editor.md))
* **Befund:** Gegen die zwei realen Annotationen aus der Sitzung vom
  2026-09-09 (`var/workbench/annotations/6ffc561bb18f47f0aa14648b1f904dcd`,
  `.../8a18ee05e31241b9b6702c5bb904ec97`) trifft `fit_quad_in_region`
  (`roi.suggest`) die tatsächliche Displayposition zuverlässig (IoU ≈ 0,91
  gegen die bestätigte `roi_quad`, siehe [VALIDATION.md](VALIDATION.md)).
  `fit_ocr_box` (`ocr.suggest`) scheitert an denselben zwei Bildern
  vollständig (IoU 0,0): Die grosszügig bestätigte `roi_quad` umfasst zwei
  übereinanderliegende Anzeigen (`V` und `A`) desselben Netzteils, und die
  Funktion wählt konsequent die falsche (untere `A`-Zeile hat mehr
  Blob-Fläche als die gewünschte obere `V`-Zeile) - die aus Konzept.md §7
  bekannte Haupt-/Nebenanzeige-Verwechslung, hier erstmals an echten Daten
  belegt statt nur befürchtet. Ein Bild zeigt zusätzlich einen
  grossflächigen Glanzfleck als eigenen Blob. Mit einer probeweise enger
  vorgeschlagenen `roi_quad` liefert `fit_ocr_box` stattdessen `None` (sicherer
  Fehlschlag statt falschem Vorschlag), aber weiterhin keinen brauchbaren
  Vorschlag. Zusätzlich unvalidiert: die Filterwerte selbst (Blobhöhen-Spanne,
  Cluster-Lückenschwelle, Schliess-Kernel-Anteil, Flächen-/Seitenverhältnis-
  Grenzen in `fit_quad_in_region`/`fit_ocr_box`) sind Vorabdefaults wie bei
  `DetectionConfig` schon üblich, keine an mehreren realen Geräten
  validierten Grenzen - eine bekannte weitere Schwäche zeigte sich zudem an
  einem sehr schmalen synthetischen Layout (3 Stellen, keine Nachkommastelle),
  siehe Docstring von `fit_ocr_box`.
* **Blockiert:** nichts - `roi.suggest`/`ocr.suggest` bleiben reine,
  unbestätigte Vorschläge, `manual_roi` bleibt Primärpfad. Kein automatisch
  übernommener Wert kann davon betroffen sein.
* **Update 2026-09-10, weiterer Aufrufort (inzwischen wieder abgeloest,
  siehe naechstes Update):** `Controller.command("freeze")` rief `fit_ocr_box`
  zwischenzeitlich ebenfalls automatisch auf. Dieselbe Haupt-/Nebenanzeige-
  Grenze galt dort unveraendert - am oben genannten Netzteil-Beispiel schlug
  auch diese automatische Vermutung die `A`- statt der `V`-Anzeige vor.
* **Update 2026-09-10, spaet nachts:** Der zweistufige Bestaetigungsablauf
  (siehe `CHANGELOG.md`, "TUI-style zweistufiger Bestaetigungsablauf") loest
  den automatischen Aufruf in `freeze()` wieder ab - die OCR-Vermutung
  passiert jetzt explizit beim Uebergang von Stufe A (ROI bestaetigt) zu
  Stufe B (`ocr.suggest`, client-ausgeloest), nicht mehr beim blossen
  Oeffnen des Editors. Die beschriebene Grenze (Haupt-/Nebenanzeige-
  Verwechslung) betrifft weiterhin genau diesen `ocr.suggest`-Aufruf,
  unabhaengig davon, wodurch er ausgeloest wird.
* **Klärung:** Ohne weiteren Bedienerhinweis ist die Haupt-/Nebenanzeige-
  Verwechslung laut Konzept.md §7 strukturell nicht auflösbar - denkbare
  nächste Schritte sind ein zweiter, engerer Bedienerhinweis speziell für
  `ocr_box` oder ein Layout-Feld für "erwartete Zeilenzahl im ROI". Beides
  nicht Teil dieser Stufe. Weitere reale Annotationen (auch mit bewusst
  einzelner Anzeige im Ausschnitt) würden die Validierung deutlich
  verlässlicher machen als zwei Aufnahmen desselben Geräts.
* **Update 2026-09-11, Datenlage korrigiert:** Der Befund oben spricht von
  „den zwei realen Annotationen". Inzwischen liegen **neun** Annotationen vor,
  sechs davon mit getipptem Sollwert (Aufzählung und Messung in
  [VALIDATION.md](VALIDATION.md), Abschnitt „2026-09-11"). Alle stammen
  weiterhin von **einer** Geräteinstanz, die Aussage dieses Eintrags über die
  Vorschlagsqualität bleibt damit unverändert gültig — die Zahl war schlicht
  veraltet. Die IoU-Messung von `fit_quad_in_region`/`fit_ocr_box` wurde
  **nicht** auf die übrigen vier Bilder ausgeweitet; das steht weiterhin aus.
* **Antwort landet in:** `docs/VALIDATION.md`, `src/dispread/workbench/vision.py`.

* **Update 2026-09-21, `fit_quad_in_region` an 73 realen Proben - 0 von 73
  liefern ein Quad** (`scripts/dataset-benchmark.py`, Arm „deskewed" der
  Dataset-Benchmark-Geometrie, siehe OQ-23-Update oben): Für **jede einzelne**
  der 73 lesbaren Sammelmodus-Proben (beide Geräte) lehnt `fit_quad_in_region`
  die von Hand gezogene Zielbox als Hinweisbereich vollständig ab (`None`).
  Anders als bei den zwei Annotationen von 2026-09-10 (IoU ≈ 0,91) trifft die
  Funktion hier **nie**. Wahrscheinlichste Ursache, noch nicht einzeln
  nachgewiesen: die Sammelmodus-Zielboxen sind bewusst locker um die Anzeige
  gezogen (Plan 2026-09-21 misst eine ~5-fache Flächenstreuung allein
  innerhalb einer Situation) und dadurch systematisch zu großzügig für
  `fit_quad_in_region`s `MIN_HINT_OVERLAP=0,2`/Flächenfilter - eine andere
  Belastung als die bestätigten, engeren `roi_quad`-Hinweise aus dem
  Annotationspfad, für die die Funktion ursprünglich gemessen wurde. Betrifft
  ausschließlich den `deskewed`-Arm des Dataset-Benchmarks; `manual_roi`
  bleibt unberührt (reiner Vorschlag, nie automatisch übernommen).
* **Klärung, präzisiert:** Vor einer Änderung an `fit_quad_in_region` selbst
  erst klären, ob die Ursache tatsächlich die lockere Zielbox ist (z. B.
  testweise `MIN_HINT_OVERLAP` senken oder die Zielbox vor dem Aufruf enger
  fitten) statt die Funktion blind nachzuschärfen - siehe AGENTS.md, keine
  Vermutung ohne Messung.

## OQ-26 — Grenzen der Nachführung an realen Geräten validieren

* **Status:** offen · erkannt 2026-09-11 in
  [PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md)
  (Task 12, aus der Spezifikation übernommen)
* **Befund:** `TrackConfig` in `src/dispread/track.py` legt drei Schwellen für
  die begrenzte Nachführung eines bestätigten Quads fest —
  `max_shift=0.10`, `max_rotation_deg=3.0`, `min_score=0.60`. Wie alle Werte
  in `DetectionConfig` sind das Vorabdefaults, die nicht gegen echte
  Gerätebewegung (Vibration, thermische Drift, versehentlicher
  Bedienereingriff) validiert wurden — nur gegen synthetisches Material
  (`tests/test_track.py`) und die vier realen Clips unter
  `var/workbench/clips/`, die alle von einer einzigen Geräteinstanz
  (`device_id="RND Lab"`) stammen.
* **Klärung:** Braucht mehrere reale Geräteinstanzen mit provozierter
  Bewegung (siehe ROADMAP-P2-Sperrbedingungen), um zu prüfen, ob die drei
  Schwellen echte Fehlausrichtung zuverlässig fangen, ohne bei normaler
  Vibration `tracking_lost` fälschlich auszulösen oder umgekehrt eine echte
  Verschiebung durchzulassen.
* **Antwort landet in:** `docs/VALIDATION.md`.

## OQ-27 — Rasterfeinschliff je Bild bewusst nicht gebaut

* **Status:** offen (bewusste Nicht-Entscheidung, kein Fix ausstehend)
* **Befund:** Ein Rasterfeinschliff je Bild (Projektionsprofil zieht die
  Zellgrenzen pro Frame nach) wurde für
  [PLAN_2026-09-11-ocr-selbstkalibrierung.md](PLAN_2026-09-11-ocr-selbstkalibrierung.md)
  erwogen und verworfen — Begründung in
  [project_history.md](project_history.md), Eintrag „2026-09-11 — OCR-
  Selbstkalibrierung: verankerte Werkzeuge statt genereller OCR/
  Klassifikator". Phase C dieses Plans (`QuadTracker`) fängt starre Bewegung
  des ganzen Quads bereits ab; ein Feinschliff ohne Verankerung am
  bestätigten Raster würde die Haupt-/Nebenanzeige-Verwechslung aus
  [OQ-25](open-questions.md) in den Lesepfad erben.
* **Klärung:** Offen bleibt, ob ein verankerter (nicht frei laufender)
  Feinschliff für nicht-starre Änderungen im Ausschnitt (z. B. leichte
  Verzerrung durch Temperatur) je gebraucht wird — bislang keine reale
  Messung, die dafür spricht.
* **Antwort landet in:** `src/dispread/ocr/`.

## OQ-28 — Eindeutigkeit der Autofit-Geometrie

* **Status:** offen · erkannt 2026-09-11 (Task 4 dieses Plans)
* **Befund:** Der Koordinatenabstiegs-Sweep in `fit_layout`
  (`src/dispread/ocr/autofit.py`) fand auf dem realen Annotationssatz zwei
  strukturell unterschiedliche, aber gleich gut punktende Parametersätze
  (siehe [VALIDATION.md](VALIDATION.md), Abschnitt „2026-09-11 — Autofit
  (`fit_layout`) gegen dieselben sechs Annotationen (Task 4)"). `flat_optimum`
  soll genau diesen Fall anzeigen.
* **Klärung:** Ob `flat_optimum` diesen Fall an einem echten Gerät im
  laufenden Betrieb zuverlässig erkennt — statt z. B. knapp daneben zu liegen
  und einen der beiden Sätze unmarkiert zurückzugeben — ist mit einer
  einzigen Geräteinstanz nicht zu beantworten.
* **Antwort landet in:** `docs/VALIDATION.md`.

## OQ-29 — Zeitpunkt von `calibrated_on`/`calibrated_on_frame_sequence`

* **Status:** offen · erkannt 2026-09-18 in Task 5's Review
  (PLAN_2026-09-11-ocr-selbstkalibrierung.md)
* **Befund:** In `Controller._autofit`
  (`src/dispread/workbench/controller.py`) wird `self.calibrated_on` (und
  darüber `calibrated_on_frame_sequence`, das über die Clipaufnahme aus Task 2
  in `clip.json` landet) gesetzt, sobald `layout.autofit` irgendein passendes
  Ergebnis liefert — nicht erst, wenn der Bediener es über den `roi`-Op
  tatsächlich bestätigt. In Task 5's Review plan-mandated so belassen, nicht
  gefixt. Szenario: Bediener lässt Autofit laufen, sieht ein unüberzeugendes
  Ergebnis (z. B. `flat_optimum=True`), verwirft es, bestätigt stattdessen
  manuell eine unabhängige/handjustierte ROI — `calibrated_on_frame_sequence`
  behauptet in `clip.json` weiterhin irreführend, die bestätigte Geometrie
  stamme aus dem verworfenen Autofit-Versuch.
* **Blockiert:** nichts Sicherheitsrelevantes — das Feld erreicht nur die
  `clip.json`-Provenienz-/Audit-Metadaten, nie `ValueRecord`, die serielle
  Ausgabe oder das Freigabegate (gemäß den Nicht-Zielen dieses Plans).
* **Klärung:** Ob `calibrated_on` erst beim tatsächlichen `roi`-
  Bestätigungsschritt gesetzt werden soll statt beim bloßen Autofit-Treffer.
* **Antwort landet in:** `src/dispread/workbench/controller.py`
  (`_autofit`/`roi`-Op), ggf. `docs/VALIDATION.md` bei einer künftigen
  Messung.

## OQ-30 — `roi`-Op ist nicht atomar gegenüber einem fehlschlagenden `QuadTracker`-Aufbau

* **Status:** offen · erkannt 2026-09-18 in Task 7's Review
  (PLAN_2026-09-11-ocr-selbstkalibrierung.md)
* **Befund:** Im `roi`-Op-Bestätigungszweig
  (`src/dispread/workbench/controller.py`) wird `self._change(data)`
  (committet `confirmed=True`, erhöht die Revision, kann `run`→`setup`
  zurückschalten) **vor** dem Aufbau von
  `self.tracker = QuadTracker(frame["image"], roi_quad(frame["image"], data))`
  aufgerufen. Schlägt der Tracker-Aufbau fehl (Exception), ist die
  Bestätigung bereits committet, aber es existiert kein Tracker, und der
  auslösende Frame wird nicht aus `self.frames` entfernt. Gefunden in Task 7's
  Review; vom Controller als zutreffend bestätigt — korrigiert die
  ursprüngliche „pre-existing"-Einordnung des Implementierers.
* **Blockiert:** nichts Akutes — die Auswirkung ist selbstlimitierend:
  `self.frames` ist auf 4 Einträge mit FIFO-Verdrängung begrenzt, und der
  Fehler degradiert exakt auf den Vor-Task-7-Zustand (bestätigt, kein
  Tracker, schließt sicher ab, keine Fehlkorrektur).
* **Klärung:** Ein günstiger Fix existiert (Tracker vor `self._change(data)`
  konstruieren, danach erst zuweisen), war aber keine Bedingung für Task 7's
  Abnahme.
* **Antwort landet in:** `src/dispread/workbench/controller.py` (`roi`-Op).

## OQ-31 — Stale-Vorschau-Zustand bei manueller Regler-Bearbeitung nach Autofit

* **Status:** geklärt (2026-09-18) · erkannt 2026-09-18 in Task 5's Fix-Runde
  (PLAN_2026-09-11-ocr-selbstkalibrierung.md), vom Re-Reviewer bestätigt,
  im Abschlussreview desselben Plans als R8a behoben
* **Befund:** Task 5's Fix-Runde behob eine Bug-Klasse für den Canvas-/
  Geometrie-Editierfluss (ein stehengebliebenes `editing.autofit`-Ergebnis
  wurde beim Bestätigen stillschweigend angewendet, statt verworfen zu
  werden). Der Implementierer flaggte selbst, dass dieselbe Bug-Klasse
  vermutlich auch für die manuelle Layout-Regler-UI in der Einstelltabelle
  gilt: Läuft ein Autofit erfolgreich, editiert der Bediener danach **vor**
  dem Bestätigen ein Layout-Feld direkt über die Regler der Einstelltabelle,
  könnte das stehengebliebene Autofit-Ergebnis diese manuelle Bearbeitung
  beim Bestätigen trotzdem überschreiben. Vom Re-Reviewer als real bestätigt,
  aber als andere Bugoberfläche eingestuft als das in dieser Runde tatsächlich
  Gefixte.
* **Klärung (2026-09-18, Abschlussreview R8a):** Bestätigt und behoben. Jede
  Layout-Änderung aus der Einstelltabelle (`layout.set`/`layout.set_many` in
  `send()`) verwirft einen anstehenden Autofit-Vorschlag über den neuen
  gemeinsamen Pfad `invalidateAutofit()` — derselbe, den Task 5's Fix-Runde
  für den Canvas-Fluss benutzt. Eine noch laufende Autofit-Anfrage gilt dabei
  ebenfalls als überholt (`requestId` wird erhöht), sonst hätte eine spät
  eintreffende Antwort die zwischenzeitliche Handänderung überschrieben — das
  war ein echtes Rennen, nicht nur eine Reihenfolgefrage. Testabdeckung:
  `tests/workbench_client.test.mjs` (R8a, beide Fälle inkl. Polarität),
  angestoßen von `tests/test_workbench_client.py`.
* **Antwort landet in:** `src/dispread/workbench/static/workbench.js`.

## OQ-32 — `_row()`/`edit_row()` haben keinen sicheren Fallback für einen unbekannten `kind`

* **Status:** offen (Ursprungsbug behoben, zugrunde liegende Lücke nicht) ·
  erkannt 2026-09-18 in Task 8's Review (PLAN_2026-09-11-ocr-selbstkalibrierung.md)
* **Befund:** Task 8's Review fand und behob einen Critical-Bug: eine neue
  Zeile mit `kind="text"` (wörtlich aus dem damaligen — inzwischen
  korrigierten — Plantext kopiert) ließ `dispread tui`
  (`src/dispread/workbench/tui.py`, `edit_row()`) mit `KeyError: 'min'`
  abstürzen, weil nur die Zweige für `kind=="info"` und `kind=="choice"` eine
  sichere Behandlung haben — jeder andere Wert fällt durch zu Code, der
  numerische Editiermetadaten (`row["min"]`/`row["max"]`) voraussetzt. Der
  akute Bug wurde behoben (`kind="info"` statt `"text"`), aber `edit_row()`
  hat weiterhin keine Validierung oder einen sicheren Default für einen
  unbekannten/unbehandelten `kind` — die Gefahr würde beim nächsten neuen
  Zeilentyp lautlos wiederkehren.
* **Klärung:** `edit_row()` (und die zugehörige `_row()`-Zeilenerzeugung in
  `fields.py`) braucht einen expliziten `else`-Zweig, der einen unbekannten
  `kind` ablehnt statt anzunehmen, dass Zahlenmetadaten vorhanden sind.
* **Antwort landet in:** `src/dispread/workbench/tui.py`,
  `src/dispread/workbench/fields.py`.

## OQ-33 — Ähnlichkeitsschwellwert des Datensatz-Sammelmodus ist unvalidiert

* **Status:** offen · erkannt 2026-09-18 beim Bau des Datensatz-Sammelmodus
  (`src/dispread/workbench/datasets.py`)
* **Befund:** `DatasetStore._find_similar_in_group()` warnt vor einer
  Wiederholungsaufnahme, deren mittlere normierte Graustufendifferenz zu
  einer anderen Probe derselben Situation unter `SIMILARITY_THRESHOLD = 0.02`
  liegt. Der Wert ist ein Vorabdefault wie `LAYOUT_RATIOS` — an keinem realen
  Datensatz kalibriert. Zu niedrig gesetzt, warnt er nie; zu hoch gesetzt,
  nervt er bei echten unabhängigen Wiederholungen mit ähnlicher Beleuchtung.
* **Klärung:** Braucht echte, als unabhängig bestätigte Wiederholungsaufnahmen
  am selben Gerät, um den Schwellwert gegen tatsächlich beobachtete
  Bildähnlichkeit zu kalibrieren — dieselbe Art Realdatensatz, den dieser
  Sammelmodus überhaupt erst beschaffen soll.
* **Antwort landet in:** `src/dispread/workbench/datasets.py`,
  `docs/VALIDATION.md`.

## OQ-34 — Realer interaktiver Browserdurchlauf des Datensatz-Sammelmodus steht aus

* **Status:** offen · erkannt 2026-09-18 beim Bau des Datensatz-Sammelmodus
* **Befund:** `static/dataset.js` ist durch reine Geometrietests
  (`tests/dataset_client.test.mjs`) und aiohttp-Endpunkttests
  (`tests/test_dataset_api.py`) abgedeckt, aber ein echter interaktiver Klick-
  Durchlauf (Gerät anlegen → Aufnahme → Zielbox ziehen → speichern → Neustart
  → Export) hat in dieser Umgebung nicht stattgefunden — derselbe Grund wie
  OQ-21: der headless Chromium dieser Umgebung lädt laut dortigem Befund auch
  einfache lokale HTTP-Seiten nicht zuverlässig.
* **Klärung:** Abnahme mit einem echten Browser (siehe OQ-21) nachholen,
  inklusive der Szenarien mehrere Zeilen, `-.125`, führende Null, unlesbar,
  unsicher, ungültige Box, Gerätewechsel bei offenem Entwurf, doppelter Save,
  Schreibfehler, zwei Browsertabs, Tokenablauf, abgeschnittener Export.
* **Antwort landet in:** `docs/anleitung/11-datensatz-sammeln.md`,
  `docs/status.md`.

## OQ-35 — Automatisierte Testwerterzeugung für den Datensatz-Sammelmodus (GPIO/BK-5491B)

* **Status:** offen · erkannt 2026-09-21 auf Nutzeranfrage
  (`PLANNED_FEATURES.md`, Abschnitt „Other features", Zeile zu GPIO-Sensordaten)
* **Idee:** Das Bench-Multimeter BK Precision 5491B (Geräteeintrag im
  Sammelmodus: `identity_evidence="5491B"`, `model="Count Multimeter"`, siehe
  auch [OQ-23](open-questions.md) zur VFD-Anzeige desselben Geräts) über die
  GPIO-Pins des Pi automatisiert mit Testwerten versorgen, um viele reale
  Bilder mit bekanntem Sollwert ohne manuelles Eintippen zu erzeugen —
  optional auch über verschiedene Kamerawinkel hinweg.
* **Erste Einschätzung, ungeprüft an der realen Hardware:** Ein Multimeter
  *misst* ein anliegendes Signal, es *nimmt* über GPIO keinen Sollwert an —
  "GPIO an das Gerät anschließen" trifft die Richtung also nicht ganz. Zwei
  Bausteine, unabhängig kombinierbar:
  1. **Sollwert automatisch auslesen statt eintippen:** Modelle dieser Baureihe
     führen laut allgemeinem Datenblattwissen üblicherweise RS-232 und GPIB
     als Fernsteuerschnittstellen — **an diesem konkreten Gerät nicht
     nachgewiesen.** Falls vorhanden und verkabelt, ließe sich der intern
     gemessene Wert per Befehl abfragen und als Sollwert für die Probe
     verwenden — vertrauenswürdiger als ein selbst erzeugter Sollwert, weil
     es exakt das ist, was das Gerät selbst als seinen Messwert führt (bei
     dem auch die Anzeige gespeist wird). Braucht keine GPIO-Signalerzeugung,
     nur eine serielle/GPIB-Verbindung zum Pi.
  2. **Ein bekanntes Testsignal in den Messeingang einspeisen**, um gezielt
     verschiedene Anzeigewerte durchzufahren: reine Pi-GPIO-Pins liefern
     dafür keine geeignete, kalibrierte Analogspannung — nötig wäre ein
     DAC (z. B. I2C-Baustein) mit passender Pegelanpassung/Impedanz für den
     Messeingang, keine direkte Drahtverbindung GPIO→Messeingang. Dieselbe
     Vorsicht wie in [OQ-09](open-questions.md) (Pi-GPIO-Pegel nicht direkt
     mit einer externen Signalstrecke verbinden, galvanische Trennung
     prüfen) gilt hier analog, auch wenn es kein RS-232 ist.
* **Ungeklärt:** Hat dieses konkrete Gerät ein funktionierendes RS-232-
  oder GPIB-Interface, und liegt ein passendes Kabel/Adapter vor? Soll
  Baustein 1 (Auslesen) allein reichen, oder wird auch Baustein 2
  (Signaleinspeisung) gewünscht? Beides betrifft ausschließlich den
  Sammelmodus (`DatasetStore`/`dataset.capture`/`dataset.save`) - erreicht
  wie andere Zielbox-/Label-Daten nie `ValueReader`, `ReleaseGate` oder die
  Produktionskette.
* **Antwort landet in:** `docs/HARDWARE_PROFILE.md` (Schnittstellenbefund),
  `docs/anleitung/11-datensatz-sammeln.md` (falls umgesetzt).

## OQ-36 — Sättigungsbasierte LCD-Quad-Findung nur an einem Gerät gemessen

* **Status:** offen · erkannt 2026-09-22 (Spike zu `lcd_quad_in_region`,
  `src/dispread/workbench/vision.py`)
* **Befund:** `fit_quad_in_region` (Canny-Kantenzug) liefert auf den beiden
  LED-/VFD-Laborgeräten kein einziges Quad (0/36 und 0/41, gemessen
  2026-09-22) — das ist der in `docs/VALIDATION.md` (2026-09-21) als 0/73
  dokumentierte Befund, hier reproduziert; die 73 sind die lesbaren Proben
  genau dieser zwei Geräte. Auf dem GSV-Gerät, das zum Zeitpunkt jenes Laufs
  noch nicht existierte, liefert die Funktion 7 von 11.

  `lcd_quad_in_region` liefert dagegen bei 87 von 88 Proben ein Quad. Die
  reine Trefferzahl sagt aber nichts über die Brauchbarkeit; gemessen an der
  Fläche des gelieferten Quads relativ zur markierten Region:

  | Gerät | n | Quad gefunden | Median | innerhalb der Region |
  |---|---|---|---|---|
  | `87564e34…` (GSV, Farb-LCD) | 11 | 11 | 0.96 | alle |
  | `4237c46d…` | 36 | 35 | 1.00 | alle |
  | `91853b73…` | 41 | 41 | 0.75 (0.53–0.98) | 8 ragen hinaus |

  Nur der GSV-Fall ist brauchbar. Bei `4237c46d…` entartet das Quad zur
  markierten Box selbst (Median 1.00) und bringt keine Entkippung; bei
  `91853b73…` ragen 8 von 41 Quads über die markierte Region hinaus. Beide
  sind LED-/VFD-Laborersatzgeräte, laut Nutzer (2026-09-22) für den
  Produktionspfad nicht relevant, weil dort ausschliesslich LCD-Anzeigen
  eingesetzt werden — die Zahlen belegen aber, dass „findet ein Quad" dort
  nicht „findet die Anzeige" bedeutet.
* **Blockiert:** Ob die implementierte Schwelle `saturation_threshold=60`
  auch auf mehreren echten LCD-Geraeten (nicht nur dem einen gemessenen)
  haelt, ist ungeprueft. Die Methode ist bewusst nur als Vorschlag verdrahtet
  (`lcd_quad_in_region`), niemals als automatische Uebernahme - trotzdem
  bleibt unklar, ob sie bei weiteren LCD-Geraeten ebenso zuverlaessig einen
  ausreichend grossen, bezelfreien Bereich liefert.
* **Klärung:** Mit mehreren echten LCD-Geraeten (nicht nur `87564e34…`)
  messen, ob 60 ein brauchbarer Schwellenwert bleibt oder je Geraet/Beleuchtung
  nachjustiert werden muss.
* **Antwort landet in:** `docs/VALIDATION.md` (Messreihe je Geraet),
  `src/dispread/workbench/vision.py` (Docstring/Default von
  `lcd_quad_in_region`, falls sich der Wert aendert).

## OQ-37 — Anzeigeformat des GSV-Sensors bei Werten ab 10 mV/V ungemessen

* **Status:** **BEANTWORTET 2026-09-22.** Das Format wechselt **nicht**. Über
  14 Normierungsfaktoren von 1,0 bis 9000 — Anzeigewerte `+0.59696` bis
  `+05372.5`, also weit über 10 — zeigt die Anzeige **ausnahmslos 6 Ziffern**,
  der Dezimalpunkt wandert, führende Nullen bleiben stehen (**im Telegramm —
  auf dem Glas ist die führende Null unterdrückt, korrigiert 2026-09-23, siehe
  [OQ-41](open-questions.md)**). Der Zahlenblock
  belegt damit in **14 von 14** Fällen genau **8 Zellen**. Zahlen und Aufbau:
  [VALIDATION.md](VALIDATION.md), Eintrag „Anzeige über den
  Normierungsfaktor steuerbar".

  **Folge für die Rasterverankerung:** die Voraussetzung des Block-Ankers
  (Zahlenblock = 8 Zellen, unabhängig von der Punktposition) hält über den
  gesamten erreichbaren Bereich. Die hier befürchtete Formatänderung tritt
  nicht ein. Der Block-Anker selbst bleibt davon unberührt an seinem
  gemessenen Ergebnis (45,2 %, Gate nicht bestanden).

  **Wie es beantwortet wurde — ohne jeden Stimulus:** über `set norm` (16)
  und `set dpoint` (17), genau wie es die Präzisierung unten vorgeschlagen
  hatte. Der Eingriff war mit Freigabe des Nutzers, jeder Schritt mit
  Rücklesen, und der Ausgangszustand ist wiederhergestellt
  (Rückstellpunkt: `var/diagnostics/gsv-register-rueckstellpunkt-2026-09-22.json`).

  **Was dabei NICHT beantwortet wurde:** das Verhalten bei **negativen**
  Werten grossen Betrags. Negative Normierung erlaubt die Anleitung erst ab
  Firmware 1.5.06; dieses Gerät hat 1.3.07. Die Vorzeichenstelle bleibt
  unbelegt — siehe [OQ-39](open-questions.md).
* **Ursprünglicher Stand:** offen · erkannt 2026-09-22 (Rückfrage des Nutzers
  beim Entwurf des Block-Ankers für den Dot-Matrix-Leser)
* **Befund:** Alle 11 bestätigten GSV-Proben liegen zwischen `0.00042` und
  `1.05000`, also **unter 1,06**. Alle zeigen durchgängig 6 Ziffern und 5
  Nachkommastellen (`+X.XXXXX mV/V`). Über das Verhalten bei Werten **ab 10**
  sagt der Datensatz nichts.
* **Warum das zählt:** Der geplante Block-Anker der Rasterverankerung
  (`docs/superpowers/plans/2026-09-22-dotmatrix-backend.md`, Task 2) stützt
  sich darauf, dass der Zahlenblock **immer genau 8 Zellen** belegt —
  Vorzeichen + 6 Ziffern + Dezimalpunkt. Das gilt unabhängig davon, *wo* der
  Punkt steht: `+1.05000` und `+10.5000` enden beide bei Zelle 8, Zelle 9
  bleibt leer, die Einheit beginnt bei Zelle 10.

  Behält die Anzeige bei ≥ 10 die 6 Ziffern und verschiebt nur den Punkt,
  hält der Anker. Wechselt sie dagegen auf 7 Ziffern, verschiebt sich die
  Blockgrenze und der Anker bricht. Der Dezimalpunkt als Landmarke mit fester
  Zellposition ist aus demselben Grund bereits verworfen worden — er wandert
  mit der Grösse.
* **Blockiert:** nichts unmittelbar; der Anker lässt sich mit den vorhandenen
  Proben messen. Betrifft die Tragfähigkeit im Feld, sobald reale Messwerte
  den Bereich überschreiten.
* **Klärung:** Den Sensor einmal über 10 mV/V fahren und ein Foto aufnehmen.
  Eine einzige Probe genügt, um zwischen „Punkt wandert, 6 Ziffern bleiben"
  und „Format wechselt" zu unterscheiden. Gleiches gilt sinngemäss für
  negative Werte grosser Beträge.
* **Präzisierung 2026-09-22 — über den Messwert geht es nicht, über die
  Anzeige schon.** Der Vollausschlag des Laborgeräts ist **1,05 mV/V**
  (gemessen, [VALIDATION.md](VALIDATION.md)), und die höchste
  Eingangsempfindlichkeit des GSV-2 endet bei 3,5 mV/V (`Set Range`, Befehl
  50, nur 2 oder 3,5 zulässig; entspricht 3,675 Vollausschlag). **Ein
  Messwert ab 10 mV/V ist an diesem Gerät also physikalisch unerreichbar** —
  mit keinem Stimulus.

  Die Frage zielt aber auf das **Anzeigeformat**, nicht auf die Physik. Die
  Anleitung: „Die Displayanzeige ergibt sich aus Normierungsfaktor x
  Messwert", gesetzt über `set norm` (16), Einheit getrennt über `set unit`
  (15). Ein Normierungsfaktor, der die Anzeige bei unverändertem Sensorsignal
  über 10 bringt, beantwortet OQ-37 damit **ohne jeden Stimulus** — eine
  Konfigurationsänderung, eine Aufnahme, fertig. Da sie persistent ist
  (wie der Mode-Wechsel) und die Anzeige des Laborgeräts verändert, gehört
  sie abgesprochen und danach zurückgestellt.
* **Nebenbefund 2026-09-22:** Drei der 11 Proben (`1.05000`) sind sehr
  wahrscheinlich Bereichsübersteuerung statt Messwert, siehe
  [OQ-39](open-questions.md). Die nutzbare Probenzahl sinkt damit auf 8.
* **Antwort landet in:** `docs/VALIDATION.md`, dem Profilschema (falls die
  Ziffernzahl doch variabel ist) und der Verankerungslogik des
  Dot-Matrix-Lesers.

## OQ-38 — Ground-Truth-Quelle für Auto-Labeling: Displaybus oder Geräteschnittstelle?

* **Status:** **weitgehend geklärt 2026-09-22** — Gerät identifiziert,
  angeschlossen, auf ASCII umgeschaltet, Telegramm gemessen. **Verbliebene
  Sachfrage: die zeitliche Zuordnung** zwischen Telegramm und Anzeige
  (Punkt 4/5 unten). Das Herkunftsmerkmal im `DatasetStore` (Punkt 6) ist
  seit 2026-09-22 gebaut, mit zwei offenen Lücken (Migration der
  Bestandsproben, Export gibt die Herkunft noch nicht weiter — Details bei
  Punkt 6). · **Zuständig:** Labor
* **Nachtrag 2026-09-23:** Der Export gibt `label_origin` jetzt weiter
  (`EXPORT_SCHEMA_VERSION` 2). Die Lücke aus Punkt 6 ist damit in diesem Repo
  geschlossen. Der externe Loader in `picam-ai-auto-seven-segment` lehnt
  Version 2 noch ab (`evaluation.py:50`). **Optische Gegenprobe gelaufen:** Das
  Telegramm entspricht inhaltlich der Anzeige, **bis auf die führende Null**.
  Die unterdrückt das Glas, das Telegramm nicht, siehe [OQ-41](open-questions.md).
  Die zeitliche Zuordnung (Punkt 4/5) ist weiter offen.
* **Praktische Bestätigung 2026-09-22:** USB-RS232-Adapter (PL2303) an
  `/dev/ttyUSB0`, 38400 8N1 — der Strom kommt an, 5-Byte-Framing sitzt in
  19/19 Frames, ≈ 1,9 Frames/s, und die Werte folgen dem bewegten Stimulus.
  Zahlen in [VALIDATION.md](VALIDATION.md), Aufbau in
  [lab_journal.md](lab_journal.md). **Es wurde nur gelesen.**
* **Frage:** Woher kommt der Sollwert, wenn Proben des Sammelmodus nicht mehr
  von Hand, sondern automatisch gelabelt werden sollen — vom Displaybus des
  Geräts oder von einer seriellen Geräteschnittstelle?

### Ursprüngliche Einschätzung (2026-09-22 vormittags) — überholt

Aus der Fotoserie allein wurde geschlossen: kein Typenschild, kein erkennbarer
RS-232-Treiber, Schnittstelle nicht nachweisbar → **Displaybus empfohlen**,
mit dem Argument, ein intern geführter Messwert könne von der Anzeige
abweichen (Rundung, Stellenzahl, Formatierung). Dieses Argument ist durch die
Herstellerdokumentation widerlegt, siehe unten.

### Was den Befund gedreht hat

Der Nutzer hat am 2026-09-22 nachgereicht, dass das Gerät sich beim Hochfahren
meldet mit:

```
GSV-2AS (GSV21 V1.3.07)
```

Damit ist es ein **reguläres ME-Systeme GSV-2AS**, kein undokumentierter Bau.
Die Bedienungsanleitung „DMS Messverstärker GSV-2 (GSV-2LS, GSV-2AS,
GSV-2FSD)" ist öffentlich abrufbar und liegt lokal unter
`var/datenblaetter/gsv2-bedienungsanleitung.pdf` (+ `.txt`), Quelle:
`https://www.me-systeme.de/produkte/elektronik/gsv-2/anleitungen/gsv2-bedienungsanleitung.pdf`.
**`var/` ist gitignored** — die Datei überlebt keinen frischen Clone; die URL
ist die dauerhafte Quelle.

Aus ihr, wörtlich:

* Gerätefamilie: „GSV-2AS, GSV-2ASD: Aluminiumgehäuse mit **RS232**, RS422,
  CANbus, Display" — deckt sich mit dem Gehäuse auf den Fotos.
* **5-polige Schraubklemme für RS232 / RS422** (Tabelle S. 7):
  `A = GNDC` (Masse), `B = Rx`, `C = Tx`, `D = Rx+/CAN_GND`, `E = Tx+/CAN_L`.
  **Genau diese Klemme ist auf den Fotos vorhanden** — die kleine grüne
  Zusatzklemme neben der 15-poligen Leiste trägt einen Beschriftungsstreifen
  mit `A`/`B`/`C`. Der Abgriffpunkt ist also bereits im Gerät.
* **15-polige Klemme** (Tabelle 1): 1 = GNDB, 2…7 = Brücke (+US, +UF, +UD,
  -UD, -UF, -US), 8 = UE, 9 = UA (Analogausgang), 10 = GNDA, 11 = SW1,
  12 = Tara, 13 = SW2, **14 = UB, 15 = GNDB**. Die Nutzerauskunft
  „14/15 = Stromversorgung" ist damit unabhängig bestätigt.
* **Der GSV sendet von selbst:** „Der GSV schreibt seine Messwerte permanent
  auf die serielle Schnittstelle." Kein Polling nötig.
* Werkseinstellung: **38400 Baud, 8N1**. Umschaltbar (SetBaud); im
  Konfigurationsmodus über Steckbrücke JP2 fest 38400.
* Zwei Ausgabeformate, umschaltbar per `Set Mode` (Befehl 38d): Binär (5 Byte,
  24 bit) oder **ASCII**.
* **Der entscheidende Satz:** im ASCII-Modus „**entspricht** die ausgegebene
  Zeichenkette **der Anzeige im Display**". Format ab Werk: „Vorzeichen, 6
  Stellen mit Dezimalpunkt, Leerzeichen, Einheit, CR, LF", Beispiel
  `+1.2345 kg<CR><LF>`.
* Diese Kopplung ist auch im Befehlssatz verankert: `Set Digits` (61) „setzt
  die Anzahl der im LC-Display dargestellten Ziffern. Wenn die
  ASCII-Datenausgabe aktiviert ist, wird **auch die Anzahl der übertragenen
  Ziffern-Bytes** gesetzt."
* Maximale ASCII-Datenrate bei 38400 Baud: 200 Hz — weit über den 15 fps der
  Kamera.

Das beobachtete Anzeigeformat passt dazu exakt: `-0.00063 mV/V` ist Vorzeichen
+ 6 Stellen mit Dezimalpunkt + Leerzeichen + Einheit, und die 11 bestätigten
Proben zeigen durchgängig 6 Ziffern ([OQ-37](open-questions.md)).

### Geänderte Empfehlung

**RS232 im ASCII-Modus ist jetzt der Primärweg**, der Displaybus rückt auf den
Platz der Rückfallebene und Gegenprobe. Begründung:

* Das tragende Gegenargument ist weg. „Der Bus liefert das Glas, die
  Schnittstelle nur einen internen Wert" gilt für dieses Gerät **nicht** — der
  Hersteller koppelt ASCII-Ausgabe und Anzeige ausdrücklich.
* Der Abgriffpunkt existiert bereits (Klemme B/C/A), dokumentiert und
  spezifiziert. Kein Mitlesen an einem Flachband, kein Eingriff in das Gerät,
  kein Eigenbau.
* Es ist ein Standard-Seriellpfad, für den das Projekt ohnehin Infrastruktur
  hat.

Der Displaybus behält genau einen eigenen Nutzen, den die Serielle nicht
bietet: **Code-zu-Glyph-Paare** zur Klärung der Zeichensatz-ROM-Variante
(`°`/`Ω`/`µ`, siehe CLAUDE.md). Skizze bleibt in
[DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md).

### Was noch offen ist — und warum es nicht übersprungen werden darf

1. **Pegel: RS232, nicht TTL.** Klemme B/C führt RS-232-Pegel. Ein direkter
   Anschluss an Pi-GPIO ist unzulässig — das ist wörtlich
   [OQ-09](open-questions.md). Nötig ist ein USB-RS232-Adapter oder ein
   Transceiver.
2. ~~**Ist der ASCII-Modus an diesem Exemplar aktiv?**~~ **Geklärt und
   erledigt 2026-09-22.** Der Modus stand auf `0x00` (Binär); mit Freigabe des
   Nutzers auf `0x02` (Bit 1 = Text-Modus) gesetzt und zurückgelesen. Der
   Strom liefert seither `+0.46776 mV/V<CR><LF>`, **18/18 Zeilen** passen auf
   `^[+-]\d\.\d{5} mV/V$`. Zahlen in [VALIDATION.md](VALIDATION.md).
   **Die Änderung ist persistent** — Rückweg ist `Set Mode` mit gelöschtem
   Bit 1. Fallstrick für Nachahmer: `Get Mode` antwortet mit **zwei** Bytes
   `3B <wert>`; das `0x3B` ist das Semikolon-Präfix, nicht der Wert.
3. ~~**Sind B/C überhaupt nach draussen verdrahtet?**~~ **Geklärt 2026-09-22
   (Nutzerauskunft):** B und C sind angeschlossen und führen auf einen
   RS232-Steckverbinder. Der Abgriff ist damit ohne jeden Eingriff ins Gerät
   erreichbar. Anschlussbelegung und Adapterwahl stehen in
   [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md).
4. **Zeitliche Kopplung Anzeige ↔ Stream ist nicht dokumentiert.** Dass der
   *Inhalt* übereinstimmt, sagt die Anleitung. Dass er zum *selben Zeitpunkt*
   übereinstimmt, sagt sie nicht. **Verschärft durch die Messung:** der Strom
   läuft mit ≈ 2 Hz, die Kamera mit 15 fps — auf einen Messwert kommen rund
   sieben Bilder. Ohne bekannte Zeitkopplung ist nicht entscheidbar, welchem
   der sieben Bilder der Wert gehört. **Muss gemessen werden.**
5. **Die optische Einschwingzeit des LCD bleibt unverändert relevant.** Das
   Glas hinkt jeder Änderung nach; Bilder im Wechselfenster dürfen nicht
   automatisch gelabelt werden, sondern bekommen `label_state="uncertain"`.
   Siehe [DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md), Abschnitt „Der kritische
   Punkt".
6. ~~**`DatasetStore` hat kein Herkunftsmerkmal für Labels.**~~ **Merkmal
   selbst gebaut, 2026-09-22.** `save_sample` verlangt jetzt das
   Pflichtfeld `label_origin` (`"manual"` | `"serial_ascii"`, kein stiller
   `"manual"`-Default bei Fehlen) und bei `"serial_ascii"` ein typgeprüftes
   `label_origin_detail` (`source_port`, `guard_margin_ms`,
   `plateau_start_ns`, `plateau_end_ns`, `telegram_count`). Beide Felder
   gehen in die Unveränderlichkeitsprüfung ein (anderer `label_origin` auf
   denselben `capture_token` → `RevisionConflict`). `relabel_sample` setzt
   beim manuellen Korrigieren die Herkunft auf `"manual"` zurück und
   protokolliert die vorherige Herkunft in `label_history`
   (`previous_label_origin`/`previous_label_origin_detail`) — Details und
   Begründung: [CHANGELOG.md](../CHANGELOG.md) 2026-09-22 („Herkunftsmerkmal
   `label_origin`"), `src/dispread/workbench/datasets.py`
   (`_validate_label_origin`, `_relabel_sample_locked`),
   `tests/test_datasets.py`. **Automatisches Labeln selbst ist damit nicht
   gebaut** — nur die Voraussetzung dafür. Zwei Lücken bleiben offen:
   1. **Migration der Bestandsproben fehlt.** `SAMPLE_SCHEMA_VERSION` ist auf
      2 gestiegen; jede Probe mit `schema_version == 1` (kein
      `label_origin`, das betrifft alle 88 realen Proben unter
      `var/workbench/datasets/`) wird beim Laden jetzt hart abgelehnt
      (`_load_sample_json`, analog zu `_load_devices`). Ein Migrationsschritt,
      der den Bestandsproben nachträglich `label_origin="manual"` zuweist,
      ist nötig, **bevor** der Sammelmodus wieder auf sie zugreift — und ist
      absichtlich nicht Teil dieser Änderung.
   2. **Export gibt die Herkunft noch nicht weiter.** `_export_locked`/
      `manifest.json` (`EXPORT_SCHEMA_VERSION`) kennen `label_origin` noch
      nicht — die Herkunftsspur endet an der Probe und erreicht den
      Benchmark (noch) nicht. Bräuchte eine eigene Schemaversion und einen
      eigenen Test.
* **Abgrenzung:** Betrifft ausschliesslich den Sammelmodus
  (`DatasetStore`/`dataset.capture`/`dataset.save`). Ein so gewonnener Sollwert
  erreicht wie jedes andere Label **nie** `ValueReader`, `ReleaseGate` oder die
  Produktionskette.
* **Nicht in `hardware.conf`:** Der Abgriff ist ein **zweiter, eingehender**
  serieller Pfad (USB-RS232, 38400 8N1) und hat nichts mit `SERIAL_PORT`/
  `SERIAL_BAUD` zu tun — die beschreiben den **ausgehenden** Datenport nach
  GSVmulti (`/dev/ttyAMA0`, Baudrate offen über
  [OQ-01](open-questions.md)). Wer `SERIAL_BAUD=38400` aus der
  GSV-2AS-Anleitung übernimmt, konfiguriert den falschen Pfad. Die Parameter
  des Abgriffs gehören zum Sammelmodus, nicht nach
  `/etc/dispread/hardware.conf`.
* **Verwandt:** [OQ-35](open-questions.md) (dieselbe Frage am BK-5491B),
  [OQ-39](open-questions.md) (was ein Abgriff **nicht** löst),
  [OQ-09](open-questions.md) (Pegel), [OQ-07](open-questions.md) (die
  GSV-2-Anleitung ist zugleich die Quelle, die dort gesucht wurde).
* **Antwort landet in:** [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md)
  (Klemmenbelegung, Schnittstellenparameter),
  [DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md) (Rückfallebene),
  `docs/anleitung/11-datensatz-sammeln.md` (falls umgesetzt).

## OQ-39 — Ziffernabdeckung des GSV-Datensatzes ist durch den festen Stimulus begrenzt

* **Status:** offen · erkannt 2026-09-22 (bei der Machbarkeitsprüfung zu
  OQ-38) · **wesentlich relativiert am selben Tag**, siehe direkt unten
* **Wichtige Einschränkung dieses Eintrags (2026-09-22, Nutzerauskunft beim
  ersten seriellen Mitschnitt):** Der Nutzer hat mitgeteilt, dass er **die
  extern an den Sensor angeschlossenen Stimulatoren bewegt** — im Mitschnitt
  sichtbar als Wanderung der Rohwerte über `B8A95A`…`EF346B`
  ([VALIDATION.md](VALIDATION.md)). Der Stimulus ist also **nicht fest**. Die
  unten festgehaltene Grenze („neue Bilder zeigen nur noch denselben Wert")
  beruhte auf der früheren Angabe, die verklebte DIP-Platine solle nicht
  bewegt werden, und **gilt so nicht mehr**. Was offen bleibt: **welcher
  Anzeigebereich** mit den beweglichen Stimulatoren erreichbar ist —
  insbesondere negative Werte und Werte ab 10 mV/V
  ([OQ-37](open-questions.md)). Erst diese Antwort sagt, wie viel
  Ziffernabdeckung wirklich zu holen ist.
* **Befund:** Der Messgrössengeber am GSV ist eine **Lochrasterplatine mit
  DIP-Schalter** (Fotos `gsv_angeschlossene_platine1/2.jpg`,
  `…_unterseite.jpg`): ein Widerstandsnetz, handschriftlich beschriftet
  „4: 2 mV/V", „3: 1 mV/V". Sie erzeugt also eine Handvoll **diskreter**
  Brückenwerte. Der Nutzer hat am 2026-09-22 mitgeteilt, dass die Platine
  **verklebt** ist, damit sie nicht bewegt wird, und dass sie vorerst nicht
  benutzt werden soll.
* **Warum das zählt:** Auto-Labeling (OQ-38) vervielfacht die **Bilderzahl**,
  nicht die **Ziffernabdeckung**. Steht der Stimulus fest, zeigen alle künftig
  aufgenommenen Bilder denselben Anzeigewert — die Abdeckung bleibt genau die
  der bereits vorhandenen Proben, gleichgültig wie viele Bilder dazukommen.
  Ein Leser lernt keine Ziffer, die er nie an einer Stelle gesehen hat, an der
  sie vorkommen kann.
* **Was der Abgriff trotzdem bringt** — nicht kleinreden, es ist real:
  1. **Exakte Labels für die zappelnden letzten Stellen.** Im Bestand direkt
     sichtbar: der 0.948er-Cluster streut über `0.94801`…`0.94836`, also in
     den letzten beiden Stellen. Bei 15 fps ist das von Hand nicht zuverlässig
     zu labeln, von der Schnittstelle schon.
  2. **Pose-, Licht-, Fokus- und Glanzvielfalt** in beliebiger Menge, bei
     korrektem Label.
  Beides verbessert die Robustheit, keines die Ziffernabdeckung.
* **Was der Datensatz heute abdeckt** (ausgezählt 2026-09-22 über
  `var/workbench/datasets/samples/*/sample.json`, Gerät
  `87564e345aa047338f954c045bc9df02`, alle 11 `label_state="readable"`):

  | Sollwert | Anzahl |
  | --- | --- |
  | `0.00042` | 1 |
  | `0.00045` | 1 |
  | `0.94801` | 2 |
  | `0.94802` | 1 |
  | `0.94804` | 1 |
  | `0.94809` | 1 |
  | `0.94836` | 1 |
  | `1.05000` | 3 |

  Also **drei Cluster**, nicht ein einzelner Wert: Rauschbereich (~0.0004),
  ein Arbeitspunkt bei ~0.948 und `1.05000`. Führende Ziffern werden damit
  durchaus geübt (9, 4, 8 in vorderen Stellen). Durchgängig 6 Ziffern und 5
  Nachkommastellen ([OQ-37](open-questions.md)).

  **Zwei Lücken, die auffallen:**
  * **Kein einziger negativer Wert** — obwohl die Anzeige zum Zeitpunkt der
    Fotoserie auf `-0.00063 mV/V` stand. Die Vorzeichenstelle ist im Datensatz
    also unbelegt.
  * `1.05000` erscheint **dreimal exakt gleich**. **Rechnerisch belegt am
    2026-09-22:** der Vollausschlag dieses Exemplars ist 1,05 mV/V (der
    Binärwert `B8C62C` ergibt bipolar mit diesem Endwert `+0.46573`, und der
    ASCII-Strom zeigt bei gleicher Stimuluslage `+0.46776`). `FFFFFF` — laut
    Anleitung 105 % des Messbereichs — entspricht damit **exakt `+1.05000`**.
    Diese drei Proben sind also sehr wahrscheinlich **Übersteuerung**, nicht
    Messwerte. **Erstmals beobachtet am 2026-09-22:** im 599-s-Mitschnitt
    (Plateau-Statistik, [VALIDATION.md](VALIDATION.md)) erreicht der Wert
    während einer mechanischen Störung des Aufbaus zweimal genau `+1.05000`
    und kehrt danach zurück. Damit ist der Anschlag nicht mehr nur
    rechnerisch hergeleitet, sondern gesehen. Ein Anschlagwert ist kein Abdeckungsgewinn; die nutzbare
    Probenzahl sinkt damit faktisch von 11 auf 8. Endgültig bestätigen liesse
    sich das mit einem Versuch: Stimulus an den Anschlag fahren und prüfen, ob
    die Anzeige auf `1.05000` stehen bleibt.

  Ungemessen bleiben Werte ab 10 und negative Werte. **Negative Werte sind mit
  den vorhandenen Stimulatoren gar nicht erzeugbar** (Nutzerauskunft
  2026-09-22) — die Vorzeichenstelle bleibt unbelegt, solange kein anderer
  Stimulus dazukommt. Eine **Anzeige ab 10** ist mit stärkerem Stimulus
  ebenfalls nicht zu holen: der Vollausschlag dieses Exemplars ist 1,05 mV/V,
  und selbst die höchste Empfindlichkeit des GSV-2 (3,5 mV/V, `Set Range` 50)
  endet bei 3,675. Siehe dazu den Hinweis in [OQ-37](open-questions.md) — über
  den Normierungsfaktor ist es trotzdem erreichbar.

  Wie die drei Cluster zustande kamen, lässt sich aus den Fotos **nicht**
  ablesen: ob der DIP-Schalter vor dem Verkleben umgestellt wurde oder eine
  andere Quelle im Einsatz war, ist unbekannt und wird hier nicht behauptet.
* **Wesentliche Wendung 2026-09-22 (abends) — die Anzeige ist direkt
  steuerbar, der Stimulus muss gar nicht mitspielen.** Zwei Messungen
  desselben Tages zusammen:

  1. **Der bewegte Stimulus taugt nicht.** 1199 s Mitschnitt bei bewegtem
     Stimulus: 217 verschiedene Zeichenketten im Rohstrom, aber nach dem
     Schutzintervall bleiben bei M = 500 ms nur **25** davon übrig, und
     96,3 % der nutzbaren Zeit entfallen auf vier praktisch gleiche Werte.
     Das Gate kostet 44 % der Bilder, aber **88 % der Vielfalt** — die
     Vielfalt steckt in ein bis zwei Telegramme kurzen Ausschlägen, und
     genau die verwirft das Fenster. Das ist strukturell und wird durch
     längeres Aufzeichnen nicht besser.
  2. **Der Normierungsfaktor löst es.** `set norm` (16) plus `set dpoint`
     (17) verändern die Anzeige bei **festem** Stimulus, und der ASCII-Strom
     folgt nachweislich (Verhältnis 1,9963 bei einem Faktorwechsel auf 2,0).
     Jeder so eingestellte Wert steht **beliebig lange** still — Vielfalt und
     Plateaulänge stehen damit nicht mehr im Widerspruch. `EEnow = 0` am
     Gerät gemessen: die Schreibbefehle nutzen das EEPROM nicht ab.

  Damit ist der Kern dieses Eintrags entschärft: Ziffernabdeckung ist nicht
  mehr an den Stimulus gebunden, sondern planbar. Beide Messungen in
  [VALIDATION.md](VALIDATION.md).

  **Was offen bleibt — und es ist der härtere Rest:** **negative Werte.**
  Negative Normierung gibt es erst ab Firmware 1.5.06, dieses Gerät hat
  1.3.07, und die Stimulatoren erzeugen keine negativen Werte. Die
  **Vorzeichenstelle bleibt unbelegt.** Ein Leser, der ein `-` nie gesehen
  hat, ist an dieser Stelle unbelegt geprüft — das gehört an jede
  Benchmarkzahl geschrieben.

  Zweitens bleibt offen, ob eine über die Normierung erzeugte Ziffernfolge
  dieselbe **Bildstatistik** hat wie eine real gemessene. Für den Leser
  zählt, was auf dem Glas steht, und das ist identisch erzeugt — ein
  systematischer Unterschied ist nicht ersichtlich, aber auch nicht gemessen.
* **Wege zu mehr Vielfalt, die die verklebte Platine nicht anfassen**
  (gesammelt, nicht entschieden — die Auswahl ist eine Laborentscheidung):
  * ein **zweiter** Brückensimulator am selben Sensorkabel, steckbar statt
    verklebt;
  * eine echte Kraft-/Wägezelle mit variabler Last;
  * die Tara-/Nulltaste des Geräts (verschiebt die Anzeige, ändert die
    Ziffernfolge);
  * eine andere Verstärkungs-/Bereichseinstellung, falls zugänglich;
  * ein weiteres GSV-Exemplar mit anderem Anzeigezustand.
* **Blockiert:** nichts unmittelbar. Betrifft die Aussagekraft jeder
  Erkennungsgüte-Zahl, die auf dem so vergrösserten Datensatz gemessen wird —
  eine hohe Trefferquote auf 50 000 Bildern derselben drei Werte ist **keine**
  Aussage über die Erkennung im Feld.
* **Verwandt:** [OQ-37](open-questions.md) (Anzeigeformat ab 10 mV/V),
  [OQ-35](open-questions.md) (Baustein 2: Signaleinspeisung, gleiches Problem
  am BK-5491B), [OQ-38](open-questions.md).
* **Antwort landet in:** [VALIDATION.md](VALIDATION.md) (Abdeckungsangabe zu
  jeder Benchmarkzahl), `docs/anleitung/11-datensatz-sammeln.md`.

## OQ-40 — Schwelle für „Telegrammlücke" im Gate-Labeler ist ungemessen

* **Status:** offen · erkannt 2026-09-22 beim Bau von `scripts/gate-label.py`
  · **Zuständig:** Labor
* **Frage:** Ab welchem Telegrammabstand gilt ein Lauf gleicher Werte als
  nicht mehr vertrauenswürdig?
* **Warum das zählt:** Fällt ein Telegramm aus, sieht der Strom durchgehend
  aus, obwohl dazwischen ein **anderer** Wert gestanden haben kann, der nie
  ankam. Ein Bild aus dieser Lücke bekäme dann ein falsches Label, das wie
  Wahrheit aussieht — genau die Fehlerart, die dieses Projekt ausschliesst.
  Der Fall tritt auch **an einem echten Wertwechsel** auf: fehlt dort ein
  Telegramm, sieht ein A→B-Übergang harmlos aus, obwohl dazwischen ein
  drittes C gestanden haben kann.
* **Stand der Umsetzung:** `scripts/gate-label.py` prüft beides — Abstände
  innerhalb eines Laufs **und** den Abstand zum nächsten abweichenden
  Telegramm — gegen `--max-gap-ms`. Das Argument hat **bewusst keinen
  Vorgabewert**: eine erfundene Schwelle wäre eine unbelegte Zahl an der
  Stelle, an der es auf Belegbarkeit ankommt.
* **Datenlage:** Über 1125 Telegramme (599 s) gemessen: Abstand min 502 ms,
  p50 553 ms, p95 555 ms, max 562 ms — also sehr eng verteilt, kein einziger
  Ausfall. Das ist ein guter Ausgangspunkt, aber **eine Aufzeichnung ohne
  Ausfälle sagt nichts darüber, wie ein Ausfall aussieht**, wenn er auftritt.
* **Klärung:** Über eine längere Strecke (Stunden) mitschreiben und die
  Abstandsverteilung auf Ausreisser prüfen; zusätzlich unter Last (Kamera
  läuft parallel, USB ausgelastet) messen, weil dort Pufferüberläufe
  wahrscheinlicher sind. Die Schwelle dann aus der gemessenen Verteilung
  ableiten und **vor** der Ernte festschreiben — wie M, aus demselben Grund.
* **Nachtrag 2026-09-23 — gemessen unter Kameralast:** Die Fehlerart ist
  nicht nur der Ausfall, sondern auch der **Stau**. Einmal in 180 s stand der
  ganze Aufzeichnungsprozess 2,4 s still, und danach kamen fünf Telegramme
  mit fast gleichem `t_boot`. Die Werte sind vollständig, ihre Zeitstempel
  aber nicht. Eine reine `--max-gap-ms`-Prüfung fängt die Lücke, **nicht**
  die gestauchten Stempel danach. Nötig ist zusätzlich eine Untergrenze für
  den Abstand, oder alle Telegramme eines Staus werden verworfen. Ausserhalb
  des Staus: p50 533 ms, p95 534 ms (391 Abstände).
* **Nachtrag 2026-09-23, Ursache und Abhilfe:** Der Stau entstand durch
  blockierende Dateischreibvorgänge beim Rückschreiben auf die SD-Karte.
  Behoben durch getrennte Schreibthreads in `sync-record.py`. Unter
  erzwungener Last blieb der serielle Strom exakt (532–534 ms).
  `gate-label.py` lehnt Stösse jetzt über `--min-gap-ms` ab. **Weiter offen:**
  die Werte für `--min-gap-ms` und `--max-gap-ms`. Unter Kameralast liegen
  über 3 Läufe alle Abstände bei 529–536 ms. Eine Stundenmessung fehlt
  noch.
* **Verwandt:** [OQ-38](open-questions.md) (zeitliche Kopplung, M).
* **Antwort landet in:** [VALIDATION.md](VALIDATION.md) und der
  Vorab-Festlegung des Plans
  `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md`.

## OQ-41 — Telegramm und Anzeige unterscheiden sich in der führenden Null

* **Status:** **teilweise geklärt 2026-09-23.** Punkt (a) ist entschieden und
  umgesetzt: Die Null wird vor dem Vergleich aus dem Telegramm entfernt
  (`telegram_to_display_text` in `scripts/gate-label.py`, Plan Festlegung 1).
  (b) und (c) sind offen. · erkannt 2026-09-23 bei der optischen Gegenprobe
  (OQ-38) · **Zuständig:** Entwicklung
* **Befund (gemessen):** Über 15 Normierungsfaktoren (1,0 bis 9000) trägt das
  ASCII-Telegramm eine führende Null, die das Glas **nicht** zeigt. Zum
  Beispiel wird `+01.8290` auf dem Glas zu `+ 1.8290` und `+05487.0` zu
  `+ 5487.0`. Die Zelle bleibt belegt, als leere Zelle. Alle übrigen Zeichen
  und die Punktposition stimmen überein. Zahlen:
  [VALIDATION.md](VALIDATION.md), Eintrag 2026-09-23.
* **Warum das zählt:** Die Vorab-Festlegung 1 des Plans verlangt **exakte
  Zeichenkettengleichheit** zwischen Label und Anzeige. Übernimmt man das
  Telegramm unverändert als Label, trägt **jedes** Bild mit einem Wert ≥ 1
  ein Zeichen, das nicht auf dem Glas steht. Dieses falsche Label sähe aus
  wie Wahrheit.
* **Offen:** (a) Eine Abbildung Telegramm → Anzeige muss vor der Ernte als
  Vorschrift festgeschrieben werden, gegen die gemessenen Fälle. Beobachtet
  ist: eine `0` an Position 1, der eine Ziffer folgt, wird zur leeren Zelle.
  Das ist eine Abbildung und keine Toleranz, Festlegung 1 bleibt bestehen.
  (b) Welches Zeichen das Label für die leere Zelle trägt (Leerzeichen?),
  muss zum Zellenraster des Lesers passen. (c) Negative Werte sind hier
  ungeprüft, weil die Vorzeichenstelle unerreichbar ist (Firmware 1.3.07).
  Sie dürfen nicht stillschweigend mitgemeint sein.
* **Verwandt:** [OQ-37](open-questions.md), [OQ-38](open-questions.md).
* **Antwort landet in:** Plan `docs/superpowers/plans/2026-09-22-auto-labeling-seriell.md`
  (Vorab-Festlegungen) und `scripts/gate-label.py`.
