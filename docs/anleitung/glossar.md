---
weg: bedienen
hide:
  - toc
---
# Glossar

Jeder Begriff, der in diesem Projekt eine engere Bedeutung hat als im
Alltag. Alphabetisch.

## Projekt und Fachliches

### DUT

*Device under Test*, der Prüfling. Das Gerät, dessen Anzeige gelesen
wird. Sein Wert wird **nie** anhand der Referenz korrigiert.

*Weg:* Bedienen · *Auch:* Device under Test · *Quelle:* [Konzept §7](../../Konzept.md)

### GSVmulti

die Auswertesoftware von ME-Systeme, die die Werte
zeitgestempelt entgegennehmen soll. Das akzeptierte serielle Telegramm ist
unbekannt ([OQ-01](../open-questions.md), [OQ-07](../open-questions.md)).

*Weg:* Bedienen · *Quelle:* [GSVmulti-Protokoll](../GSVMULTI_PROTOCOL.md)

### Messverstärker

die Geräteklasse (GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI,
AST). Beispielgeräte, kein zugesicherter Umfang: welche Typen freigegeben
werden, ist [OQ-04](../open-questions.md).

*Weg:* Bedienen · *Quelle:* [Konzept](../../Konzept.md)

### OQ-nn

*Open Question*. Nummerierte Unbekannte in
[../open-questions.md](../open-questions.md). Jede hat einen Vorabdefault, eine
Zuständigkeit und einen Zielort für die Antwort. Einträge werden **nie
gelöscht**, nur auf `geklärt` gesetzt.

*Weg:* Entwickeln · *Auch:* Open Question · *Quelle:* [Offene Fragen](../open-questions.md)

### Referenz

die Kalibriermaschine bzw. das Normal. Zeitlich mit dem DUT
zuzuordnen, aber strikt getrennt vom Erkennungspfad (Konzept §7).

*Weg:* Bedienen · *Quelle:* [Konzept §7](../../Konzept.md)

### Sperrgerät

Geräteinstanz, die vor jeder Entwicklung zurückgehalten und
erst in der Abnahme einmalig ausgewertet wird. Mindestens zwei.

*Weg:* Bedienen · *Quelle:* [Validierung](../VALIDATION.md)

## Bildverarbeitung

### CLAHE

*Contrast Limited Adaptive Histogram Equalization*. Lokale
Kontrastanhebung. In `rectify.enhance()` verfügbar, standardmäßig **aus**:
sie verändert die Helligkeiten, aus denen die Segmentevidenz entsteht.

*Weg:* Konfigurieren · *Auch:* Contrast Limited Adaptive Histogram Equalization · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### Entzerren / Rectify

das Anzeigenviereck auf ein achsparalleles Rechteck
fester Größe abbilden (`rectify.rectify()`). Feste Zielgröße, weil der
Segmentleser gegen ein Raster abtastet.

*Weg:* Entwickeln · *Auch:* Entzerren, Rectify · *Quelle:* [Geometrie-API](../../api/geometrie.md)

### Homographie

die 3×3-Abbildung zwischen Bildviereck und entzerrtem
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

vier Eckpunkte einer Anzeige im Bildkoordinatensystem, im
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

(`saturated_fraction`)

### Schärfe

Varianz des Laplace-Operators. Nur innerhalb
**eines** Aufbaus vergleichbar, nie als absolute Güte.

*Weg:* Konfigurieren · *Auch:* sharpness · *Quelle:* [Geometrie-API](../../api/geometrie.md)

(`sharpness`)

### Segmentevidenz

die gemessene Helligkeit jedes der sieben Segmente je
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

*n* aufeinanderfolgende Frames müssen denselben Wert
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

monoton steigende Zeit ohne Sprünge. Domäne aller
Verarbeitungsmarken im `PipelineTrace`.

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### Latenz vs. Zeitunsicherheit

Latenz ist eine Verzögerung (korrigierbar,
wenn bekannt); Zeitunsicherheit ist die *Streuung* der Zuordnung. Eine kleine
Latenz garantiert keine kleine Unsicherheit. Grundsatz aus
[../TIMING.md](../TIMING.md).

*Weg:* Bedienen · *Auch:* Latenz, Zeitunsicherheit · *Quelle:* [Zeitbezug](../TIMING.md)

### M1 … M8

das Messprogramm zum Zeitbezug in
[../TIMING.md](../TIMING.md). Wichtigste: **M8** (nutzt GSVmulti den
gelieferten Aufnahmezeitstempel?) und **M5** (Displayaktualisierung und
Haltezeit, vermutlich der dominierende Term).

*Weg:* Entwickeln · *Quelle:* [Zeitbezug](../TIMING.md)

### `SensorTimestamp`

Zeitstempel aus den libcamera-Metadaten.

*Weg:* Entwickeln · *Quelle:* [Bildquellen-API](../../api/frames.md)

### Semantik

worauf sich ein Zeitstempel physikalisch
bezieht: Belichtungsbeginn, -mitte, Auslese-Ende, Host-Abholung. Steht auf
`UNKNOWN`, bis Messung M2 es belegt.

*Weg:* Entwickeln · *Auch:* TimestampSemantics · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

(`TimestampSemantics`)

### Zeitbasis

Herkunft und Belastbarkeit: `V4L2_MONOTONIC`, `SENSOR_BOOTTIME` und `REPLAY_RECORDED` tragen eine Zeitaussage, `SYNTHETIC` und `FILE_MTIME` nicht (`carries_time_information`).

*Weg:* Entwickeln · *Auch:* TimeBaseKind · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

(`TimeBaseKind`)

Für die nötige BOOTTIME-Umrechnung und die offene Stempelsemantik siehe [Zeitstempel richtig lesen](../uebersicht/zeitstempel.md).

### Unsicherheit

`None`, solange ungemessen. **Nie 0**;
das wäre eine Falschaussage.

*Weg:* Entwickeln · *Auch:* uncertainty_ns · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

(`uncertainty_ns`)

## Schnittstellen und Hardware

### IMX500

Sony-Sensor der Raspberry Pi AI Camera, mit
On-Sensor-Inferenz. Seit 2026-09-25 außer Betrieb. Historisch gemessen:
6,8 s Warmlauf beim ersten `.rpk`-Upload, 15,0 Inferenzen/s.

*Weg:* Bedienen · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

### `.rpk`

gepacktes Modell für den IMX500. Die 23 mitgelieferten sind
COCO-/ImageNet-Modelle und für Displays unbrauchbar. Der **Packager** ist auf
dem Pi vorhanden, der **Converter** für eigene Modelle nicht
([OQ-11](../open-questions.md)).

*Weg:* Entwickeln · *Quelle:* [Offene Fragen](../open-questions.md#oq-11)

### Telegramm

die Bytes eines Datensatzes auf der seriellen Leitung, erzeugt
von einem `TelegramFormatter`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### `provisional`

Flag in `FormatterCapabilities`: das Format wurde **nicht**
gegen eine echte Spezifikation geprüft. Gehört in jedes Runartefakt. Beim
`AsciiCsvFormatter` immer `True`.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### `pty`

Pseudoterminal-Paar (`os.openpty()`). Gegenstelle für die serielle
Ausgabe ohne Hardware.

*Weg:* Entwickeln · *Quelle:* [Ausgabe-API](../../api/sink.md)

### RS-232 / Transceiver

Pi-GPIO-Pegel dürfen **nicht** direkt an RS-232;
es braucht einen Pegelwandler, galvanische Trennung ist zu bewerten
([OQ-09](../open-questions.md)).

*Weg:* Bedienen · *Auch:* RS-232, Transceiver · *Quelle:* [Offene Fragen](../open-questions.md#oq-09)

### `/dev/ttyAMA0`

vorgesehener UART-Datenport für die noch offene GSVmulti-Ausgabe; die elektrische Anbindung ist nicht freigegeben (OQ-09).

*Weg:* Konfigurieren · *Quelle:* [Hardwareprofil](../HARDWARE_PROFILE.md)

Die serielle GSV-2AS-Referenz nutzt am aktuellen Aufbau `/dev/ttyUSB0`. **`/dev/serial0`** zeigt auf `ttyAMA10` und ist der 3-Pin-Debug-Header, **nicht** der Nutzdatenport.

## Python und Werkzeuge

### Editierbarer Install

das Paket wird aus `src/`
importiert statt kopiert. Trägt einen absoluten Pfad in der `.pth`-Datei; ein
umbenanntes Projektverzeichnis bricht ihn ([Kapitel 0](00-werkzeuge.md)).

*Weg:* Entwickeln · *Quelle:* [Werkzeuge](00-werkzeuge.md)

(`./.venv/bin/pip install --no-deps -e .`)

### `frozen` Datenklasse

nach dem Erzeugen unveränderlich. Alle
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

strukturelle Typisierung: passende Methoden genügen, kein
Erben nötig. Mit `@runtime_checkable` ist `isinstance()` möglich und wird in
Tests als Konformitätsprüfung benutzt.

*Weg:* Entwickeln · *Quelle:* [Verträge](02-vertraege.md)

### `slots=True`

feste Attributmenge, weniger Speicher, und ein Tippfehler
bei einer Zuweisung fliegt auf.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `StrEnum`

Enum, dessen Mitglieder Strings sind. Erlaubt direkte
JSON-Serialisierung über `.value`.

*Weg:* Entwickeln · *Quelle:* [Verträge und Datensätze](../../api/vertraege.md)

### `--system-site-packages` / `--no-deps`

die venv-Regel des Projekts:
Systempakete sichtbar lassen, keine PyPI-Kopien von `numpy`/`cv2`/`pyserial`
darüberlegen. Begründung in [../dependencies.md](../dependencies.md).

*Weg:* Entwickeln · *Auch:* --system-site-packages, --no-deps · *Quelle:* [Abhängigkeiten](../dependencies.md)
