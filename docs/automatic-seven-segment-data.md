# Datengrundlage für den automatischen Siebensegment-Versuch

Stand: 2026-09-18, Zeitbasis UTC. Manifest:
[`experiments/automatic_seven_segment/manifest.json`](../experiments/automatic_seven_segment/manifest.json).

Der eingefrorene Datensatz ist **für eine Eignungsfreigabe unzureichend**:
elf echte Fotografien, acht öffentlich dokumentierte Geräteinstanzen und drei
RND-Aufnahmen aus demselben konservativ zusammengefassten Altbestand. Vier
physisch getrennte Geräte wurden für den Test reserviert; davon sind nur zwei
Anzeigen lesbar, zwei sind ausgeschaltet. Es gibt **vier unabhängige Testbilder
statt der angestrebten 30**. Ein hoher Anteil korrekt abgelehnter leerer Anzeigen
ist kein Ersatz für richtige vollständige Messwerte.

| Teilmenge | Bilder | Unabhängigkeitsgruppen | Lesbare Zielanzeigen |
| --- | ---: | ---: | ---: |
| Entwicklung | 7 | 5 | 4 |
| Reservierter Test | 4 | 4 | 2 |

Die acht öffentlichen Geräte umfassen Multimeter, Thermometer, eine Waage,
eine Uhr mit Temperaturanzeige und ein LED-Einbaumessgerät. Der RND-Bestand
ergänzt leuchtende LED-Anzeigen eines Labornetzteils. Die Zahl acht beinhaltet
unbeleuchtete Geräte und belegt ausdrücklich keine Erkennungsqualität auf acht
Geräten. Im Test fehlen LED-Anzeigen vollständig. Vorzeichen, wechselnde
Dezimalposition am selben Gerät, verdeckte Segmente, Verfolgungsverlust und
Wiederaufnahme sind nicht mit echten unabhängigen Testbildern abgedeckt.

## Herkunft und Lizenzen

Öffentliche JPEGs liegen als unveränderte Originalbytes unter `data/`; nur ihre
lokalen Dateinamen wurden gekürzt. SHA-256, Original-Downloadlink, Autor,
Quellseite und Lizenz stehen je Bild im Manifest. Bei Weitergabe von Bildern
oder daraus abgeleiteten Overlays müssen diese Attributionen mitgeliefert
werden. Overlays sind als Bearbeitung zu kennzeichnen; CC-BY-SA-Bearbeitungen
bleiben unter der jeweiligen oder einer kompatiblen Share-Alike-Lizenz.

| Datei / Gerät | Fotograf | Lizenz / Primärquelle |
| --- | --- | --- |
| `m832.jpg`, Mastech M-832 | Chabrez | [Public domain](https://commons.wikimedia.org/wiki/File:Multimeter_DT-830.jpg) |
| `tes1302.jpg`, TES-1302 | Andy116 | [CC BY-SA 4.0](https://commons.wikimedia.org/wiki/File:Digital_Thermometer_TES-1302.jpg) |
| `casio.jpg`, Casio DQ-750F | Adhish Bhargava (Adhishb) | [CC BY-SA 3.0](https://commons.wikimedia.org/wiki/File:Casiodq750f.jpg) |
| `fluke23.jpg`, Fluke 23 | Alex P. Kok | [CC BY-SA 4.0](https://commons.wikimedia.org/wiki/File:Fluke_23_multimeter.jpg) |
| `dt830b.jpg`, tatsächlich HAOYUE DT830D laut Gehäuse | K.Venkataramana | [CC0](https://commons.wikimedia.org/wiki/File:Digital_Multimeter_(To_measure_Voltage,_Current_and_Resistance).jpg) |
| `scale.jpg`, SilverCrest-Waage | Sarang | [Public domain](https://commons.wikimedia.org/wiki/File:K%C3%BCchenwaage_digital.jpg) |
| `irthermometer.jpg`, CURAmed-Stirnthermometer | Sarang | [Public domain](https://commons.wikimedia.org/wiki/File:Digital_IR-Thermometer.jpg) |
| `digem.jpg`, Gossen DIGEM ff1B | Mister rf | [CC BY-SA 4.0](https://commons.wikimedia.org/wiki/File:DIGEM_ff1B.jpg) |

Lizenztexte: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/),
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) und
[CC0](https://creativecommons.org/publicdomain/zero/1.0/).

Die drei RND-Dateien stammen aus lokalen `var/workbench/annotations`-Artefakten
des bestehenden Checkouts, ohne neue Kameraaufnahme. Dafür liegt keine
öffentliche Weitergabelizenz vor: `LicenseRef-Project-Local-Evaluation` bedeutet
nur den autorisierten lokalen Versuch, **keine** Open-Data-Lizenz. Sie dürfen
nicht zusammen mit öffentlichen Daten hochgeladen oder als frei lizenzierter
Datensatz veröffentlicht werden.

## Label- und Identitätsprüfung

Die Transkriptionen wurden anhand der Originalbilder visuell geprüft, nicht
aus OCR-Vorhersagen übernommen. Bei RND wurden bestehende `ground_truth_text`
verwendet und nachgesehen: `11.00`, `12.76`, `28.80`. Das Fluke-Display zeigt
`.000` ohne gedruckte führende Null; die Casio-Temperatur ist `22.0`, die
Waagentemperatur `22.5`. `null` bezeichnet hier ausschließlich eine visuell
bestätigte Anzeige ohne ablesbaren aktuellen Zahlenwert. Beim ausgeschalteten
DIGEM sichtbare Segmentumrisse sind keine gültigen Ziffern.

Alle Zielboxen umfassen die jeweilige Zahlenzeile, nicht das gesamte Gerät;
bei leeren Anzeigen das Fenster. Sie sind manuelle Entwicklungslabels in
Pixel-`xywh`, bezogen auf OpenCVs standardmäßig EXIF-orientiertes Dekodieren.
Dies ist insbesondere bei TES-1302 zu beachten. `target_displays` beschreibt
zusätzliche erkannte Zeilen für die Auswertung. Mehrzeilige Bilder haben
vorsichtshalber `all_displays_annotated=false`; unbeschriftete Nachbaranzeigen
oder Datum/Uhrzeit dürfen nicht pauschal als Fehlalarm gezählt werden.

Für öffentliche Einzelbilder wird die abgebildete Geräteinstanz anhand
Quellaufnahme, Autor und sichtbar anderem Modell/Gehäuse von den übrigen
Instanzen abgegrenzt. Das ist ein Nachweis der Trennung **innerhalb dieses
kleinen Korpus**, keine verifizierte Seriennummer und kein Beleg einer neuen
Instanz für jede weitere Aufnahme desselben Modells. Neue Ansichten aus
denselben Quellen müssen zuerst auf mögliche Identitätsgleichheit geprüft
werden. RND-Altdaten enthalten keine explizite Instanz-ID und bleiben deshalb
mit `identity_verified=false`, `device_id=null` außerhalb zertifizierter
Gerätetrennung. Alle drei RND-Bilder teilen dieselbe Unabhängigkeitsgruppe,
obwohl zwei Aufnahmetage und verschiedene Zahlen vertreten sind.

Zunächst wurden M-832 und TES-1302 reserviert; die Bildsichtung stellte fest,
dass beide ausgeschaltet sind. Vor jedem Kandidatenlauf wurden deshalb Casio
und Fluke als weitere Testgeräte reserviert. Diese vier Identitäten bleiben
fest. Keine Testvorhersage floss in Labels, Datenauswahl oder Schwellwerte ein.
Die eingefrorenen IDs stehen im Manifest. Es wurden keine synthetischen
Varianten oder benachbarten Clipframes als neue Testbeispiele erzeugt.

## Gesuchte, nicht verwendete Daten und verbleibende Lücke

Neun lokale Annotationen und fünf Clip-Verzeichnisse wurden gefunden. Drei
unterschiedliche, bereits beschriftete RND-Zustände wurden übernommen; weitere
nahe Aufnahmen hätten keine neue Geräteabdeckung geschaffen. Bestehende Clips
werden weder neu aufgenommen noch nachträglich zu unabhängigen Bildern erklärt.

[SSOCR-Beispielbilder](https://github.com/jiweibo/SSOCR) besitzen zwar eine
Repository-Lizenz, belegen aber keine eindeutig getrennten physischen Geräte.
Sie wurden nicht in den zertifizierten Test aufgenommen. Synthetische Fonts,
SVG-Ziffern und Trainingsbilder der untersuchten Modelle wurden ebenfalls
nicht als unabhängige Testdaten eingesetzt.

Eine öffentliche beleuchtete LED-Netzteilaufnahme wurde gezielt gesucht:
[LodeStar LP3005D von Derrick Parker, CC0](https://commons.wikimedia.org/wiki/File:Bench_power_supply.jpg).
Der Originaldownload antwortete wiederholt mit HTTP 429; auch die alternative
Commons-Netzteilaufnahme und eine LED-Uhr waren beim Download nicht verfügbar.
Sie wurden nicht mit erfundenen Labels oder fehlenden Dateien in das Manifest
aufgenommen. Der heruntergeladene DIGEM zeigt nur unbeleuchtete Segmente und
ersetzt keinen LED-Positivfall. Mehr öffentliche Quellen zu suchen ist möglich;
der vorliegende eingefrorene Versuch behauptet keine vollständige Datensuche.

Nächster notwendiger Datenschritt ist ein neues, vor der nächsten Abstimmung
festgelegtes Geräte-Testset mit mindestens 30 unabhängigen, überwiegend
lesbaren Aufnahmen, LED und LCD, negativen Zahlen und wechselnden
Dezimalpositionen. Bilder derselben unbekannten Instanz bleiben gruppiert.
Der aktuelle Korpus eignet sich zum reproduzierbaren Auffinden konkreter
Fehler und zur Demonstration der Datengrenzen, nicht zur Freigabe der UI-Demo.
