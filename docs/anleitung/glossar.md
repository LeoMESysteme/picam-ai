# Glossar

Jeder Begriff, der in diesem Projekt eine engere Bedeutung hat als im
Alltag. Alphabetisch.

## Projekt und Fachliches

**DUT** — *Device under Test*, der Prüfling. Das Gerät, dessen Anzeige gelesen
wird. Sein Wert wird **nie** anhand der Referenz korrigiert.

**GSVmulti** — die Auswertesoftware von ME-Systeme, die die Werte
zeitgestempelt entgegennehmen soll. Das akzeptierte serielle Telegramm ist
unbekannt ([OQ-01](../open-questions.md), [OQ-07](../open-questions.md)).

**Messverstärker** — die Geräteklasse (GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI,
AST). Beispielgeräte, kein zugesicherter Umfang: welche Typen freigegeben
werden, ist [OQ-04](../open-questions.md).

**OQ-nn** — *Open Question*. Nummerierte Unbekannte in
[../open-questions.md](../open-questions.md). Jede hat einen Vorabdefault, eine
Zuständigkeit und einen Zielort für die Antwort. Einträge werden **nie
gelöscht**, nur auf `geklärt` gesetzt.

**Referenz** — die Kalibriermaschine bzw. das Normal. Zeitlich mit dem DUT
zuzuordnen, aber strikt getrennt vom Erkennungspfad (Konzept §7).

**Sperrgerät** — Geräteinstanz, die vor jeder Entwicklung zurückgehalten und
erst in der Abnahme einmalig ausgewertet wird. Mindestens zwei.

## Bildverarbeitung

**CLAHE** — *Contrast Limited Adaptive Histogram Equalization*. Lokale
Kontrastanhebung. In `rectify.enhance()` verfügbar, standardmäßig **aus**:
sie verändert die Helligkeiten, aus denen die Segmentevidenz entsteht.

**Entzerren / Rectify** — das Anzeigenviereck auf ein achsparalleles Rechteck
fester Größe abbilden (`rectify.rectify()`). Feste Zielgröße, weil der
Segmentleser gegen ein Raster abtastet.

**Homographie** — die 3×3-Abbildung zwischen Bildviereck und entzerrtem
Ausschnitt. Wird im `DisplayCrop` mitgeführt, damit man einzelne Segmente für
Diagnosebilder zurückprojizieren kann.

**IoU** — *Intersection over Union*, Flächenüberlappung zweier Regionen. Maß
dafür, ob eine Lokalisierung getroffen hat.

**Otsu** — Schwellwertverfahren, das den Schnitt maximaler
Zwischenklassenvarianz sucht. Hier **nicht** über alle Bildpunkte, sondern über
die gepoolten Segmentmessungen — Begründung im Docstring von
`sevenseg.segment_threshold()`.

**Quad** — vier Eckpunkte einer Anzeige im Bildkoordinatensystem, im
Uhrzeigersinn ab oben links.

**ROI** — *Region of Interest*, der Anzeigebereich. Im Primärpfad **bestätigt**
(vom Bediener, Konzept §4), nicht gefunden.

**Sättigung** (`saturated_fraction`) — Anteil der Bildpunkte ≥ 250. Maß für
Überstrahlung; treibt das `glare`-Flag.

**Schärfe** (`sharpness`) — Varianz des Laplace-Operators. Nur innerhalb
**eines** Aufbaus vergleichbar, nie als absolute Güte.

**Segmentevidenz** — die gemessene Helligkeit jedes der sieben Segmente je
Stelle, plus `margin`. Der Grund, warum der klassische Leser Primärpfad ist:
das Gate kann daraus begründen, statt zu glauben.

## Kette und Verträge

**Freigabe / Gate** (`ReleaseGate`) — entscheidet aus Leseergebnis, Profil und
eigener Historie über `VALID | TRANSITION | UNREADABLE | STALE`. Bekommt
strukturell keinen Referenzwert.

**Konfidenz** — aggregiertes Qualitätsmaß, hier die Segmentmarge.
**Ausdrücklich keine Fehlerwahrscheinlichkeit** (Konzept §7).

**Marge** (`margin`) — Abstand der knappsten Segmentmessung zur
Entscheidungsschwelle, normiert 0..1. Klein = knapp entschieden.

**Mehrbildbestätigung** — *n* aufeinanderfolgende Frames müssen denselben Wert
zeigen (`GateConfig.confirm_frames`). Kostet Zeit, die als
`confirmation_span_ns` dokumentiert wird.

**Senke / Sink** — Ausgabe (`JsonlSink`, `SerialSink`). Zählt Fehler statt zu
werfen und liefert je Datensatz einen `TxReceipt`.

**STALE** — es gibt **keinen** aktuellen Wert mehr (nach
`stale_after_ns` ohne Freigabe). Trägt keinen Zahlenwert.

**TRANSITION** — die Anzeige wechselt bzw. die Bestätigung läuft noch. Aussage
über die Anzeige, kein Systemfehler.

**Trennstelle** — eine der sechs austauschbaren Nahtstellen aus Konzept §3, je
als `typing.Protocol`. Siehe [Kapitel 2](02-vertraege.md).

**UNREADABLE** — gerade nicht lesbar. Trägt keinen Zahlenwert.

**`ValueRecord`** — der interne Datensatz (Konzept §8): was das System erkannt
hat. Neun Pflichtfelder, `frozen`, verlustfrei serialisierbar.

**`TxReceipt`** — was tatsächlich über die Leitung ging: Sendezeit, Bytes,
Format, Retries. Bewusst getrennt vom `ValueRecord`.

## Zeit

**CLOCK_BOOTTIME** — Zeit seit dem Booten, inklusive Suspend. Domäne des
`SensorTimestamp` auf diesem Pi (gemessen 2026-09-07). Vergleiche über
Reboot-Grenzen hinweg sind sinnlos — deshalb `boot_id` ins Session-Manifest.

**CLOCK_MONOTONIC** — monoton steigende Zeit ohne Sprünge. Domäne aller
Verarbeitungsmarken im `PipelineTrace`.

**Latenz vs. Zeitunsicherheit** — Latenz ist eine Verzögerung (korrigierbar,
wenn bekannt); Zeitunsicherheit ist die *Streuung* der Zuordnung. Eine kleine
Latenz garantiert keine kleine Unsicherheit. Grundsatz aus
[../TIMING.md](../TIMING.md).

**M1 … M8** — das Messprogramm zum Zeitbezug in
[../TIMING.md](../TIMING.md). Wichtigste: **M8** (nutzt GSVmulti den
gelieferten Aufnahmezeitstempel?) und **M5** (Displayaktualisierung und
Haltezeit, vermutlich der dominierende Term).

**`SensorTimestamp`** — Zeitstempel aus den libcamera-Metadaten.

**Semantik** (`TimestampSemantics`) — worauf sich ein Zeitstempel physikalisch
bezieht: Belichtungsbeginn, -mitte, Auslese-Ende, Host-Abholung. Steht auf
`UNKNOWN`, bis Messung M2 es belegt.

**Zeitbasis** (`TimeBaseKind`) — Herkunft und Belastbarkeit:
`SENSOR_BOOTTIME` und `REPLAY_RECORDED` tragen eine Zeitaussage,
`SYNTHETIC` und `FILE_MTIME` nicht (`carries_time_information`).

**Unsicherheit** (`uncertainty_ns`) — `None`, solange ungemessen. **Nie 0**;
das wäre eine Falschaussage.

## Schnittstellen und Hardware

**IMX500** — Sony-Sensor der Raspberry Pi AI Camera, mit
On-Sensor-Inferenz. Gemessen: 6,8 s Warmlauf beim ersten `.rpk`-Upload, 15,0
Inferenzen/s.

**`.rpk`** — gepacktes Modell für den IMX500. Die 23 mitgelieferten sind
COCO-/ImageNet-Modelle und für Displays unbrauchbar. Der **Packager** ist auf
dem Pi vorhanden, der **Converter** für eigene Modelle nicht
([OQ-11](../open-questions.md)).

**Telegramm** — die Bytes eines Datensatzes auf der seriellen Leitung, erzeugt
von einem `TelegramFormatter`.

**`provisional`** — Flag in `FormatterCapabilities`: das Format wurde **nicht**
gegen eine echte Spezifikation geprüft. Gehört in jedes Runartefakt. Beim
`AsciiCsvFormatter` immer `True`.

**pty** — Pseudoterminal-Paar (`os.openpty()`). Gegenstelle für die serielle
Ausgabe ohne Hardware.

**RS-232 / Transceiver** — Pi-GPIO-Pegel dürfen **nicht** direkt an RS-232;
es braucht einen Pegelwandler, galvanische Trennung ist zu bewerten
([OQ-09](../open-questions.md)).

**`/dev/ttyAMA0`** — der Datenport für GSVmulti. **`/dev/serial0`** zeigt auf
`ttyAMA10` und ist der 3-Pin-Debug-Header, **nicht** der Nutzdatenport.

## Python und Werkzeuge

**Editierbarer Install** (`pip install -e .`) — das Paket wird aus `src/`
importiert statt kopiert. Trägt einen absoluten Pfad in der `.pth`-Datei; ein
umbenanntes Projektverzeichnis bricht ihn ([Kapitel 0](00-werkzeuge.md)).

**`frozen` Datenklasse** — nach dem Erzeugen unveränderlich. Alle
Ergebnisobjekte hier. Änderung nur als neues Objekt
(`dataclasses.replace`).

**Generator** — Funktion mit `yield`. Alle `frames()`-Methoden sind Generatoren,
damit nicht der ganze Datensatz im Speicher liegt.

**Lazy Import** — Import erst innerhalb der Funktion. In `frames/__init__.py`
die Voraussetzung dafür, dass ein fehlendes `picamera2` die anderen Quellen
nicht unbenutzbar macht.

**`Protocol`** — strukturelle Typisierung: passende Methoden genügen, kein
Erben nötig. Mit `@runtime_checkable` ist `isinstance()` möglich und wird in
Tests als Konformitätsprüfung benutzt.

**`slots=True`** — feste Attributmenge, weniger Speicher, und ein Tippfehler
bei einer Zuweisung fliegt auf.

**`StrEnum`** — Enum, dessen Mitglieder Strings sind. Erlaubt direkte
JSON-Serialisierung über `.value`.

**`--system-site-packages` / `--no-deps`** — die venv-Regel des Projekts:
Systempakete sichtbar lassen, keine PyPI-Kopien von `numpy`/`cv2`/`pyserial`
darüberlegen. Begründung in [../dependencies.md](../dependencies.md).
