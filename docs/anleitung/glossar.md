---
weg: bedienen
hide:
  - toc
---
# Glossar

Jeder Begriff, der in diesem Projekt eine engere Bedeutung hat als im
Alltag. Alphabetisch.

## Projekt und Fachliches

### Anzeigeart

Art der Geräteanzeige, für die ein passender Erkenner gewählt werden soll. Sie kann nach Bestätigung im Geräteprofil festgehalten werden; welche Anzeigearten freigegeben werden, ist noch zu prüfen.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

### ASCII-Streaming

Fortlaufende Übertragung von Werten als ASCII-Datenstrom. Einer der zu unterscheidenden GSVmulti-Schnittstellenfälle; weder CSV-Dateiimport noch Geräteemulation belegen seine Unterstützung.

*Weg:* Entwickeln · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### CSV-Dateiimport

Übernahme von Werten aus einer CSV-Datei. Im Konzept ein eigener Schnittstellenfall neben ASCII-Streaming und Geräteemulation; daraus folgt keine Unterstützung beliebiger serieller CSV-Datenströme durch GSVmulti.

*Weg:* Entwickeln · *Quelle:* [Konzept](../../Konzept.md)

### Dezimalpunkt

Zur Messwertinterpretation gehörendes Zeichen für die Dezimalstelle. Ein übersehener Punkt ist ein kritischer Lesefehler; seine sichere Erkennung gehört zu den geforderten Freigabekriterien.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### DUT

*Device under Test*, der Prüfling. Das Gerät, dessen Anzeige gelesen
wird. Sein Wert wird **nie** anhand der Referenz korrigiert.

*Weg:* Bedienen · *Auch:* Device under Test · *Quelle:* [Konzept §7](../../Konzept.md)

### Dynamische Vergleiche

Vergleiche zeitlich veränderlicher DUT- und Referenzwerte. Dabei sind die Displayverzögerung und ihre Schwankung besonders kritisch; ein Aufnahmezeitstempel allein bezeichnet noch nicht den internen DUT-Messzeitpunkt.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Einheit

Zum Zahlenwert gehörende Maßeinheit, deren richtige Zuordnung der Bediener bestätigen soll. Eine falsche Einheit zählt zu den kritischen Fehlern; der interne Datensatz sieht eine erkannte oder bestätigte Einheit vor.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

### Emulation eines GSV-Geräts

Nachbildung einer GSV-Geräteanbindung als möglicher GSVmulti-Schnittstellenfall. Der Adapter muss dafür gegebenenfalls auch Gerätekommandos beantworten; die nötige Spezifikation liegt noch nicht vor.

*Weg:* Entwickeln · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### Geräteidentifikation

Identifikation des angebundenen Geräts, die für die GSVmulti-Anbindung zusammen mit Initialisierungskommandos zu klären ist. Automatisch erkannte Geräteidentitäten müssen außerdem zuverlässig geprüft werden.

*Weg:* Entwickeln · *Quelle:* [Konzept](../../Konzept.md)

### GSVmulti

Die Auswertesoftware von ME-Systeme, die die Werte
zeitgestempelt entgegennehmen soll. Das akzeptierte serielle Telegramm ist
unbekannt ([OQ-01](../open-questions.md), [OQ-07](../open-questions.md)).

*Weg:* Bedienen · *Quelle:* [GSVmulti-Protokoll](../GSVMULTI_PROTOCOL.md)

### Hauptanzeige

Die im Aufbau auszulesende Anzeige, die eindeutig und formatfüllend im Bild erscheinen soll. Der Live-Pfad kennzeichnet die bestätigte Anzeige mit `main`; diese Kennzeichnung allein verhindert keine Verwechslung.

*Weg:* Bedienen · *Quelle:* [Optischer Aufbau](../OPTICAL_SETUP.md)

### Messbereich

Zum Gerät gehörende Bereichsangabe, die der Bediener bei der Einrichtung gegebenenfalls bestätigen soll. Zusammen mit Einheit und Dezimalformat gehört sie zur eindeutigen Interpretation der ausgewählten Anzeige.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

### Messverstärker

Die Geräteklasse (GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI,
AST). Beispielgeräte, kein zugesicherter Umfang: welche Typen freigegeben
werden, ist [OQ-04](../open-questions.md).

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Nebenanzeige

Zusätzliche Anzeige, die nicht mit der auszulesenden Hauptanzeige verwechselt werden darf. Lokalisierungskandidaten können dafür den Hinweis `secondary` tragen; der Hinweis allein erkennt keine Verwechslung.

*Weg:* Bedienen · *Quelle:* [Optischer Aufbau](../OPTICAL_SETUP.md)

### OQ-nn

*Open Question*. Nummerierte Unbekannte in
[../open-questions.md](../open-questions.md). Jede hat einen Vorabdefault, eine
Zuständigkeit und einen Zielort für die Antwort. Einträge werden **nie
gelöscht**, nur auf `geklärt` gesetzt.

*Weg:* Entwickeln · *Auch:* Open Question · *Quelle:* [Offene Fragen](../open-questions.md)

### Referenz

Die Kalibriermaschine bzw. das Normal. Zeitlich mit dem DUT
zuzuordnen, aber strikt getrennt vom Erkennungspfad (Konzept §7).

*Weg:* Bedienen · *Quelle:* [Konzept §7](../../Konzept.md)

### Sperrgerät

Geräteinstanz, die vor jeder Entwicklung zurückgehalten und
erst in der Abnahme einmalig ausgewertet wird. Mindestens zwei.

*Weg:* Bedienen · *Quelle:* [Validierung](../VALIDATION.md)

### Statische Kalibrierpunkte

Kalibrierpunkte mit stabilem Zustand, für die ein gemeinsames stabiles Zeitfenster zur Zuordnung von DUT und Referenz geeignet sein kann. Ob statische Punkte oder dynamische Verläufe erfasst werden sollen, ist vorab festzulegen.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Überlauf

Ungültiger Betriebszustand der Anzeige, der erkannt und von der Zahlenfreigabe ausgeschlossen werden muss. Im Messpfad gehört er neben Menü und Hold zu den blockierenden Statusflags.

*Weg:* Bedienen · *Quelle:* [Messpfad und Freigabe](../uebersicht/messpfad.md)

### Vorzeichen

Zur Zahl gehörendes Plus- oder Minuszeichen. Ein fehlendes Minuszeichen ist ein kritischer Fehler; sichere Vorzeichenerkennung ist deshalb ein gefordertes Freigabekriterium.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### Zahlenformat

Bestätigte Regel zur Darstellung der angezeigten Zahl, die ein wiederverwendbares Geräteprofil festhalten kann. Nur ein erlaubtes Zahlenformat zusammen mit bestätigter Einheit erfüllt die entsprechenden Freigabeanforderungen.

*Weg:* Konfigurieren · *Quelle:* [Konzept](../../Konzept.md)

## Bildverarbeitung

### CLAHE

*Contrast Limited Adaptive Histogram Equalization*. Lokale
Kontrastanhebung. In `rectify.enhance()` verfügbar, standardmäßig **aus**:
sie verändert die Helligkeiten, aus denen die Segmentevidenz entsteht.

*Weg:* Konfigurieren · *Auch:* Contrast Limited Adaptive Histogram Equalization · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### Entzerren / Rectify

Das Anzeigenviereck auf ein achsparalleles Rechteck
fester Größe abbilden (`rectify.rectify()`). Feste Zielgröße, weil der
Segmentleser gegen ein Raster abtastet.

*Weg:* Entwickeln · *Auch:* Entzerren, Rectify · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### Homographie

Die 3×3-Abbildung zwischen Bildviereck und entzerrtem
Ausschnitt. Wird im `DisplayCrop` mitgeführt, damit man einzelne Segmente für
Diagnosebilder zurückprojizieren kann.

*Weg:* Entwickeln · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### IoU

*Intersection over Union*, Flächenüberlappung zweier Regionen. Maß
dafür, ob eine Lokalisierung getroffen hat.

*Weg:* Entwickeln · *Auch:* Intersection over Union · *Quelle:* [Lokalisierungs-API](../../api/detect.md)

### Otsu

Schwellwertverfahren, das den Schnitt maximaler
Zwischenklassenvarianz sucht. Hier **nicht** über alle Bildpunkte, sondern über
die gepoolten Segmentmessungen — Begründung im Docstring von
`sevenseg.segment_threshold()`.

*Weg:* Entwickeln · *Quelle:* [OCR-API](../../api/ocr.md)

### Quad

Vier Eckpunkte einer Anzeige im Bildkoordinatensystem, im
Uhrzeigersinn ab oben links.

*Weg:* Entwickeln · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### ROI

*Region of Interest*, der Anzeigebereich. Im Primärpfad **bestätigt**
(vom Bediener, Konzept §4), nicht gefunden.

*Weg:* Bedienen · *Auch:* Region of Interest, Anzeigebereich · *Quelle:* [Konzept §4](../../Konzept.md)

### Sättigung

Anteil der Bildpunkte ≥ 250. Maß für
Überstrahlung; treibt das `glare`-Flag.

*Weg:* Konfigurieren · *Auch:* saturated_fraction · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### Schärfe

Varianz des Laplace-Operators. Nur innerhalb
**eines** Aufbaus vergleichbar, nie als absolute Güte.

*Weg:* Konfigurieren · *Auch:* sharpness · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### Segmentevidenz

Die gemessene Helligkeit jedes der sieben Segmente je
Stelle, plus `margin`. Sie erklärt Entscheidungen des Siebensegment-Lesers.
Der Live-Pfad am GSV-2AS verwendet stattdessen Punktraster und Vorlagenabstände
des `DotMatrixReader`.

*Weg:* Entwickeln · *Quelle:* [OCR-API](../../api/ocr.md)

## Kette und Verträge

### Freigabe / Gate {#freigabe-gate}

`ReleaseGate` entscheidet aus Leseergebnis, Profil und
eigener Historie über `VALID | TRANSITION | UNREADABLE | STALE`. Bekommt
strukturell keinen Referenzwert.

*Weg:* Konfigurieren · *Auch:* Freigabe, Gate, ReleaseGate · *Quelle:* [Freigabe-API](../../api/validate.md)

### Konfidenz {#konfidenz}

Qualitätsmaß des jeweiligen Lesers; das Gate begrenzt `min_margin` nach oben auf 1.

*Weg:* Konfigurieren · *Quelle:* [Freigabe-API](../../api/validate.md)

Beim Segmentleser ist die Marge normiert, beim Dot-Matrix-Leser stammt sie aus der Vorlagenskala. Werte verschiedener Leser sind deshalb nicht unmittelbar vergleichbar. **Keine Fehlerwahrscheinlichkeit** (Konzept §7).

### Marge {#marge}

Beim Segmentleser ist `margin` der Abstand der knappsten Segmentmessung zur Entscheidungsschwelle, normiert 0..1.

*Weg:* Konfigurieren · *Auch:* margin · *Quelle:* [OCR-API](../../api/ocr.md)

Beim Dot-Matrix-Leser ist sie der kleinere verbleibende Abstand zur erlaubten Vorlagendistanz und zur geforderten Klassentrennung; diese Skala ist nicht normiert. Klein = knapp entschieden.

### Mehrbildbestätigung {#mehrbildbestaetigung}

*N* aufeinanderfolgende Frames müssen denselben Wert
zeigen (`GateConfig.confirm_frames`). Kostet Zeit, die als
`confirmation_span_ns` dokumentiert wird.

*Weg:* Konfigurieren · *Quelle:* [Freigabe-API](../../api/validate.md)

### Senke / Sink {#senke-sink}

Ausgabe (`JsonlSink`, `SerialSink`). Zählt Fehler statt zu
werfen und liefert je Datensatz einen `TxReceipt`.

*Weg:* Entwickeln · *Auch:* Senke, Sink · *Quelle:* [Ausgabe-API](../../api/sink.md)

### `STALE` {#stale}

Es gibt **keinen** aktuellen Wert mehr (nach
`stale_after_ns` ohne Freigabe). Trägt keinen Zahlenwert.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `TRANSITION` {#transition}

Die Anzeige wechselt bzw. die Bestätigung läuft noch. Aussage
über die Anzeige, kein Systemfehler.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Trennstelle {#trennstelle}

Eine der sechs Nahtstellen aus Konzept §3. Fünf sind `typing.Protocol`;
die Freigabe setzt die konkrete Klasse `ReleaseGate` um. Siehe
[Kapitel 2](02-vertraege.md).

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `UNREADABLE` {#unreadable}

Gerade nicht lesbar. Trägt keinen Zahlenwert.

*Weg:* Bedienen · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `ValueRecord` {#value-record}

Der interne Datensatz (Konzept §8): was das System erkannt
hat. Neun Pflichtfelder, `frozen`, verlustfrei serialisierbar.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `TxReceipt` {#tx-receipt}

Was tatsächlich über die Leitung ging: Sendezeit, Bytes,
Format, Retries. Bewusst getrennt vom `ValueRecord`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

## Zeit

### `CLOCK_BOOTTIME`

Zeit seit dem Booten, inklusive Suspend.

*Weg:* Entwickeln · *Quelle:* [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md)

Das war die Zeitbasis des `SensorTimestamp` der inzwischen außer Betrieb genommenen IMX500 (Messung 2026-09-07). Vergleiche über Reboot-Grenzen hinweg sind sinnlos — deshalb `boot_id` ins Session-Manifest. Für die aktive StreamCam siehe [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md).

### `CLOCK_MONOTONIC`

Monoton steigende Zeit ohne Sprünge. Domäne aller
Verarbeitungsmarken im `PipelineTrace`.

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### Latenz vs. Zeitunsicherheit

Latenz ist eine Verzögerung (korrigierbar,
wenn bekannt); Zeitunsicherheit ist die *Streuung* der Zuordnung. Eine kleine
Latenz garantiert keine kleine Unsicherheit. Grundsatz aus
[../TIMING.md](../TIMING.md).

*Weg:* Bedienen · *Auch:* Latenz, Zeitunsicherheit · *Quelle:* [Zeitbezug](../TIMING.md)

### M1 … M8

Das Messprogramm zum Zeitbezug in
[../TIMING.md](../TIMING.md). Wichtigste: **M8** (nutzt GSVmulti den
gelieferten Aufnahmezeitstempel?) und **M5** (Displayaktualisierung und
Haltezeit, vermutlich der dominierende Term).

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### `SensorTimestamp`

Zeitstempel aus den libcamera-Metadaten.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Semantik

Worauf sich ein Zeitstempel physikalisch
bezieht: Belichtungsbeginn, -mitte, Auslese-Ende, Host-Abholung. Steht auf
`UNKNOWN`, bis Messung M2 es belegt.

*Weg:* Entwickeln · *Auch:* TimestampSemantics · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Zeitbasis

Herkunft und Belastbarkeit: `V4L2_MONOTONIC`, `SENSOR_BOOTTIME` und `REPLAY_RECORDED` tragen eine Zeitaussage, `SYNTHETIC` und `FILE_MTIME` nicht (`carries_time_information`).

*Weg:* Entwickeln · *Auch:* TimeBaseKind · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

Für die nötige BOOTTIME-Umrechnung und die offene Stempelsemantik siehe [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md).

### Unsicherheit

`None`, solange ungemessen. **Nie 0**;
das wäre eine Falschaussage.

*Weg:* Entwickeln · *Auch:* uncertainty_ns · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

## Schnittstellen und Hardware

### `.rpk`

Gepacktes Modell für den IMX500. Die 23 mitgelieferten sind
COCO-/ImageNet-Modelle und für Displays unbrauchbar. Der **Packager** ist auf
dem Pi vorhanden, der **Converter** für eigene Modelle nicht
([OQ-11](../open-questions.md)).

*Weg:* Entwickeln · *Quelle:* [Offene Fragen](../open-questions.md#oq-11)

### `/dev/ttyAMA0`

Vorgesehener UART-Datenport für die noch offene GSVmulti-Ausgabe; die elektrische Anbindung ist nicht freigegeben (OQ-09).

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

Die serielle GSV-2AS-Referenz nutzt am aktuellen Aufbau `/dev/ttyUSB0`. **`/dev/serial0`** zeigt auf `ttyAMA10` und ist der 3-Pin-Debug-Header, **nicht** der Nutzdatenport.

### `/dev/ttyAMA10`

Serieller Port am 3-Pin-Debug-Header des Pi, auf den `/dev/serial0` zeigt. Er ist ausdrücklich nicht der vorgesehene Nutzdatenport für die GSVmulti-Ausgabe.

*Weg:* Konfigurieren · *Auch:* /dev/serial0 · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### `/dev/ttyUSB0`

Port des dokumentierten PL2303-USB-RS232-Adapters für den eingehenden GSV-2AS-Referenzstrom. Er wird für Datenernte und optionale Live-Referenzaufzeichnung genutzt und ist kein GSVmulti-Ausgang.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### 8N1

Serielles Zeichenformat der dokumentierten GSV-2AS-Verbindung: Das Referenzgerät wird mit 38400 Baud und 8N1 gelesen. Diese Geräteeinstellung legt das noch unbekannte GSVmulti-Ausgabeformat nicht fest.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### ASCII

Textausgabeformat des GSV-2AS als Alternative zur Binärausgabe. Laut Geräteanleitung entspricht die ausgegebene Zeichenkette der Displayanzeige; damit ist die Annahme durch GSVmulti noch nicht belegt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Baudrate

Geschwindigkeitsparameter der seriellen Verbindung. Für den GSV-2AS-Referenzeingang sind 38400 Baud dokumentiert; die passende Einstellung des geplanten GSVmulti-Ausgangs ist weiterhin offen.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Binärformat

Alternative zur ASCII-Ausgabe des GSV-2AS: fünf Byte je Messwert mit 24 Bit. Das Ausgabeformat wird am Gerät per `Set Mode` umgeschaltet; die dokumentierte Laborreferenz wurde auf ASCII umgestellt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### CAM/DISP0

Historischer Kameraanschluss der inzwischen außer Betrieb genommenen Raspberry Pi AI Camera am Pi 5. Die aktuelle Logitech StreamCam wird über USB angebunden.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Galvanische Trennung

Elektrische Isolation der seriellen Verbindung, deren Eignung für den Laboraufbau noch zu bewerten ist. Sie ist nicht bereits durch einen Pegelwandler oder die funktionierende Referenzaufzeichnung nachgewiesen.

*Weg:* Bedienen · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### GNDC

Bezeichnung der Masse für RS232 und RS422 an Klemme A der fünfpoligen GSV-2AS-Schraubklemme. Sie gehört zum dokumentierten seriellen Geräteanschluss.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### GPIO

Pi-Anschlüsse mit 3,3-V-Pegeln. Sie dürfen nicht direkt an RS-232 angeschlossen werden: Der nötige Transceiver muss sowohl die Pegelwandlung als auch die Invertierung erledigen.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### GSV-2AS

Messverstärker des dokumentierten Laboraufbaus. Sein serieller ASCII-Strom dient über einen USB-RS232-Adapter als getrennte Referenz für Datenernte und optionale Live-Aufzeichnung; er belegt keine GSVmulti-Kompatibilität.

*Weg:* Bedienen · *Quelle:* [GSVmulti-Anbindung](../GSVMULTI_PROTOCOL.md)

### IMX500

Sony-Sensor der Raspberry Pi AI Camera, mit
On-Sensor-Inferenz. Seit 2026-09-25 außer Betrieb. Historisch gemessen:
6,8 s Warmlauf beim ersten `.rpk`-Upload, 15,0 Inferenzen/s.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Logitech StreamCam

Seit 2026-09-25 aktive USB-3-Kamera des Projekts mit USB-ID `046d:0893`. Sie ersetzt die Raspberry Pi AI Camera und wird über UVC/V4L2 angebunden.

*Weg:* Bedienen · *Auch:* StreamCam · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### PL2303

Chipsatz des dokumentierten USB-RS232-Adapters am GSV-2AS-Referenzeingang. Die Verbindung erscheint als `/dev/ttyUSB0` und wird mit 38400 Baud, 8N1 gelesen.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Polarisationsfilter

Optischer Filter, der Spiegelungen reduzieren kann. Sein Einfluss auf den LCD-Kontrast muss am Aufbau geprüft werden; eine falsche Orientierung kann die Anzeige unlesbar machen.

*Weg:* Bedienen · *Quelle:* [Optischer Aufbau](../OPTICAL_SETUP.md)

### `provisional`

Flag in `FormatterCapabilities`: das Format wurde **nicht**
gegen eine echte Spezifikation geprüft. Gehört in jedes Runartefakt. Beim
`AsciiCsvFormatter` immer `True`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### `pty`

Pseudoterminal-Paar (`os.openpty()`). Gegenstelle für die serielle
Ausgabe ohne Hardware.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### Raspberry Pi 5

Rechnerplattform des Projekts. Am dokumentierten Laborgerät sind die aktive StreamCam und die serielle Referenz angebunden; der vorgesehene GSVmulti-Ausgang benötigt weiterhin eine geklärte elektrische Anbindung.

*Weg:* Bedienen · *Auch:* Pi 5 · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Raspberry Pi AI Camera

Historisches Kameramodul mit Sony IMX500 und Inferenz im Sensor. Seit 2026-09-25 außer Betrieb und durch die Logitech StreamCam ersetzt; seine Fokus- und Anschlussangaben gelten nicht für die aktive USB-Kamera.

*Weg:* Bedienen · *Auch:* AI Camera · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### RS-232 / Transceiver

Pi-GPIO-Pegel dürfen **nicht** direkt an RS-232;
es braucht einen Pegelwandler, galvanische Trennung ist zu bewerten
([OQ-09](../open-questions.md)).

*Weg:* Bedienen · *Auch:* RS-232, Transceiver · *Quelle:* [Offene Fragen](../open-questions.md#oq-09)

### RS-485

Im Konzept neben RS-232 genannte mögliche elektrische Schnittstelle für eine UART-Anbindung mit passendem Transceiver. Eine solche GSVmulti-Ausgangsstrecke ist damit noch nicht freigegeben.

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### RS422

Neben RS232 dokumentierte Schnittstelle an der fünfpoligen GSV-2AS-Schraubklemme. Die Belegung unterscheidet Rx−, Tx−, Rx+ und Tx+; der aktuelle Referenzaufbau verwendet den USB-RS232-Adapter.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Rx

Empfangsleitung der seriellen Verbindung. Am GSV-2AS liegt Rx auf Klemme B; beim Anschluss an den PC wird sie mit dessen TX-Leitung gekreuzt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Set Mode

GSV-2-Gerätebefehl 38 zum Umschalten des Ausgabeformats zwischen Binär und ASCII. Die dokumentierte Änderung des Laborgeräts auf ASCII ist persistent und überlebt das Ausschalten.

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### Telegramm

Die Bytes eines Datensatzes auf der seriellen Leitung, erzeugt
von einem `TelegramFormatter`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### Tx

Sendeleitung der seriellen Verbindung. Am GSV-2AS liegt Tx auf Klemme C; beim Anschluss an den PC wird sie mit dessen RX-Leitung gekreuzt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### UART

Serielle Anschlussmöglichkeit des Pi. Für die geplante Ausgabe nach GSVmulti ist `/dev/ttyAMA0` vorgesehen; für RS-232 oder RS-485 ist ein passender Transceiver nötig.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### USB-RS232-Adapter

Adapter zwischen USB am Pi und der RS232-Schnittstelle des Messverstärkers. Im aktuellen Referenzpfad wird ein PL2303 an `/dev/ttyUSB0` verwendet; der vorgesehene UART-Ausgang bleibt davon getrennt.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### UVC

USB-Kameraanbindung der aktiven Logitech StreamCam. Die Bildquelle `v4l2://` verlangt bestätigte Geräteeinstellungen einschließlich USB-ID, Bildformat, Bildrate und Kamerareglern.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### V4L2

Kamerazugriff für die aktive StreamCam über `v4l2://`. Der Live-Pfad nutzt bestätigte Kameraeinstellungen; die historischen Picamera2- und IMX500-Schemata werden gezielt abgelehnt.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Virtueller USB-COM-Port

Mögliche USB-Geräteschnittstelle zum Empfänger. Dafür verlangt das Konzept eine geeignete USB-Device- oder Bridge-Lösung; diese Funktion darf am Pi 5 nicht pauschal vorausgesetzt werden.

*Weg:* Entwickeln · *Quelle:* [Konzept](../../Konzept.md)

## Python und Werkzeuge

### Editierbarer Install

Das Paket wird aus `src/`
importiert statt kopiert. Trägt einen absoluten Pfad in der `.pth`-Datei; ein
umbenanntes Projektverzeichnis bricht ihn ([Kapitel 0](00-werkzeuge.md)).

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

Installation mit: `./.venv/bin/pip install --no-deps -e .`.

### `frozen` Datenklasse

Nach dem Erzeugen unveränderlich. Alle
Ergebnisobjekte hier. Änderung nur als neues Objekt
(`dataclasses.replace`).

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### Generator

Funktion mit `yield`. Alle `frames()`-Methoden sind Generatoren,
damit nicht der ganze Datensatz im Speicher liegt.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Lazy Import

Import erst innerhalb der Funktion. In `frames/__init__.py`
die Voraussetzung dafür, dass ein fehlendes `picamera2` die anderen Quellen
nicht unbenutzbar macht.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### `Protocol`

Strukturelle Typisierung: passende Methoden genügen, kein
Erben nötig. Mit `@runtime_checkable` ist `isinstance()` möglich und wird in
Tests als Konformitätsprüfung benutzt.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `slots=True`

Feste Attributmenge, weniger Speicher, und ein Tippfehler
bei einer Zuweisung fliegt auf.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `StrEnum`

Enum, dessen Mitglieder Strings sind. Erlaubt direkte
JSON-Serialisierung über `.value`.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `--system-site-packages` / `--no-deps`

Die venv-Regel des Projekts:
Systempakete sichtbar lassen, keine PyPI-Kopien von `numpy`/`cv2`/`pyserial`
darüberlegen. Begründung in [../dependencies.md](../dependencies.md).

*Weg:* Entwickeln · *Auch:* --system-site-packages, --no-deps · *Quelle:* [Abhängigkeiten](../dependencies.md)
