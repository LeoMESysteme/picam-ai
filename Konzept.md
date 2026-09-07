# KI-gestützte Displayauslesung im Kalibrierlabor

## 1. Ziel und Ausgangslage

An einem Raspberry Pi 5 ist eine Raspberry Pi AI Camera angeschlossen. Das System soll die Anzeigen wechselnder Messverstärker optisch erfassen und die erkannten Werte kontinuierlich über eine serielle Schnittstelle an GSVmulti übertragen.

Beispielgeräte sind GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI sowie Messverstärker von AST aus Dresden. Die konkreten Anzeigearten und Schnittstellen der jeweiligen Gerätevarianten sind noch zu prüfen.

Der Einsatz erfolgt im Kalibrierlabor. Prüfling (Device under Test, DUT) und Referenz der Kalibriermaschine sollen zeitlich möglichst gut zugeordnet werden können. Geräte, Anzeigetypen, Kamerapositionen und Bildausschnitte wechseln regelmäßig.

**Empfehlung:** Ein KI-gestütztes, bedienergeführtes System mit automatischer Displaylokalisierung, spezialisierter Zeichenerkennung, Qualitätsprüfung und zeitgestempeltem Datenstrom entwickeln.

Dieses Dokument fasst die bisherige Konzeptdiskussion zusammen. Leistungswerte und Kompatibilität sind noch nicht durch einen Prototyp nachgewiesen.

## 2. Warum KI sinnvoll ist

Für eine fest positionierte 7-Segment-Anzeige kann klassische Segmentauswertung ausreichen. Bei ständig wechselnden Geräten werden feste Zeichenmasken und manuell gepflegte Bildkoordinaten jedoch aufwendig.

KI ist besonders hilfreich beim Finden des Displays und beim Lesen unterschiedlicher Schrift- und Anzeigeformen. Geometrische Bildverarbeitung und feste Prüfregeln ergänzen die KI.

| Aufgabe | Geeigneter Ansatz | Zweck |
| --- | --- | --- |
| Display finden | Kleiner Objektdetektor | Wechselnde Positionen und Gehäuse unterstützen |
| Display entzerren | Eckpunkterkennung oder Segmentierung, anschließend OpenCV | Perspektive und Rotation korrigieren |
| Anzeigeart erkennen | Optionaler Klassifikator | Passenden Erkenner auswählen |
| Ziffern und Symbole lesen | Spezialisierte OCR oder kleines Zeichenmodell | Variable Schriftarten und Zeichenpositionen verarbeiten |
| 7-Segment-Anzeigen prüfen | Klassische Segmentauswertung | Ergänzende Kontrolle ermöglichen |
| Messwert freigeben | Syntax-, Qualitäts- und Zustandsregeln | Unsichere Ergebnisse erkennen |
| Position verfolgen | Tracking und erneute Lokalisierung | Verschiebungen während der Messung erkennen |

Große Sprachmodelle oder generative KI sind für den laufenden Messpfad nicht erforderlich. Ein universell zuverlässiges System für beliebige unbekannte Geräte kann aus dem Konzept allein nicht zugesichert werden.

## 3. Vorgeschlagene Verarbeitungskette

1. Kamerabild zusammen mit den zugehörigen Metadaten erfassen.
2. Relevante Anzeige automatisch lokalisieren.
3. Displayausschnitt geometrisch entzerren und Kontrast aufbereiten.
4. Ziffern, Vorzeichen, Dezimalpunkt, Einheit und relevante Statusanzeigen erkennen.
5. Ergebnis auf Lesbarkeit, Syntax und zulässige Betriebszustände prüfen.
6. Wert mit Aufnahmezeit, Sequenznummer und Qualitätsstatus verknüpfen.
7. Über einen getrennten Protokolladapter in das von GSVmulti akzeptierte Format umsetzen.
8. Kontinuierlich seriell ausgeben und Diagnoseinformationen lokal protokollieren.

Lokalisierung und OCR müssen nicht zwingend mit derselben Frequenz arbeiten. Nach der Einrichtung kann der bestätigte Bereich verfolgt werden; bei Lageänderungen wird erneut lokalisiert. Erkennungs- und Ausgaberate sind anhand der realen Anzeigen und Zeitvorgaben festzulegen.

## 4. Bedienkonzept für wechselnde Geräte

### Bevorzugter Betrieb: einmaliges Bestätigen

- Der Laborant positioniert Gerät und Kamera.
- Das System markiert erkannte Anzeigen und schlägt Messwertbereich und Einheit vor.
- Der Laborant bestätigt die richtige Anzeige, Einheit und gegebenenfalls Messbereich oder Dezimalformat.
- Während der Kalibrierung überwacht das System Position und Bildqualität.
- Bei Verlust der Anzeige oder unsicherer Interpretation wird der Messwert ungültig.

Die Einrichtungsdauer ist im Prototyp zu messen. Eine kurze Einrichtung wird angestrebt, ist aber noch nicht belegt.

### Wiederkehrende Geräte

Bestätigte Profile können Anzeigeart, Einheit, Zahlenformat, relevante Statussymbole, Belichtungsparameter und beobachtete Aktualisierungsrate speichern. Der aktuelle Bildausschnitt wird trotzdem neu bestimmt. Automatisch erkannte Geräteidentitäten müssen zuverlässig geprüft werden.

Ein vollautomatischer Betrieb ist eine spätere Option, wenn die Validierung seine Zuverlässigkeit für die freigegebenen Gerätegruppen belegt.

## 5. Tools und Rolle der AI Camera

| Baustein | Kandidaten bzw. Ansatz |
| --- | --- |
| Kamerazugriff | Picamera2, libcamera; rpicam-apps zur Inbetriebnahme |
| Bildaufbereitung und Segmentanalyse | OpenCV, NumPy |
| Displaylokalisierung | Kleines Detektions- oder Eckpunktmodell, beispielsweise aus der YOLO-/SSD-Modellfamilie |
| OCR-Vergleich im Prototyp | Tesseract, PaddleOCR oder spezialisierter Ziffernerkenner |
| Eigene Modelle | PyTorch oder TensorFlow; Laufzeit nach Modell und Zielhardware auswählen |
| Serielle Ausgabe | Python mit pyserial |
| Dauerbetrieb | systemd, Watchdog, begrenzte Puffer und Diagnoseprotokolle |
| Gerätekonfiguration | JSON-Profile |

Die Werkzeuge sind Kandidaten. ARM-Kompatibilität, Laufzeit, Lizenzbedingungen und gegebenenfalls IMX500-Konvertierbarkeit sind vor der Festlegung zu prüfen.

Die AI Camera mit Sony IMX500 kann kompatible neuronale Netze im Sensor ausführen und Bild- sowie Inferenzdaten bereitstellen. Eigene Modelle benötigen eine passende Quantisierung, Konvertierung und Paketierung. Ein allgemeines OCR-Modell lässt sich nicht automatisch unverändert auf den Sensor übertragen.

**Entwicklungsweg:** Zunächst die Verarbeitung auf dem Pi 5 aufbauen und messen. Danach prüfen, ob die Displaylokalisierung oder ein anderer passender Teil auf den IMX500 verlagert wird. OCR und Qualitätslogik können auf dem Pi bleiben. Eine bestimmte OCR-Rate oder Latenz ist ohne Benchmark nicht zugesichert.

## 6. Synchronität und zeitliche Grenzen

Ein gleichmäßiger serieller Datenstrom allein stellt keine Synchronität zur Referenz her. Zu unterscheiden sind:

| Zeitpunkt bzw. Einfluss | Bedeutung |
| --- | --- |
| Interne Messung und Filterung des DUT | Physikalischer Zeitbezug des angezeigten Werts |
| Aktualisierung und Haltezeit des Displays | Anzeige kann einen älteren oder gemittelten Wert darstellen |
| Belichtung und Sensorauslesung | Zeitlicher Bezug des aufgenommenen Bilds |
| OCR-Verarbeitung | Verzögerung bis zum erkannten Ergebnis |
| Serielle Übertragung und Empfang | Weitere Verzögerung bis GSVmulti |

Aufnahmezeitstempel reduzieren die Abhängigkeit von schwankender OCR-Laufzeit. Sie geben jedoch nicht automatisch den internen Messzeitpunkt des DUT an. Auch die Laufzeit der Verarbeitung ist nicht zwangsläufig konstant.

Für die zeitliche Zuordnung sind erforderlich:

- Bild und Metadaten aus derselben Aufnahme verwenden.
- Bedeutung, Zeitbasis und Genauigkeit des Kamerazeitstempels prüfen; Belichtungsdauer und zeilenweise Auslesung berücksichtigen.
- Pi-Zeit und Referenzzeit auf eine gemeinsame Zeitbasis beziehen oder deren Versatz und Drift bestimmen.
- Optional einen gemeinsamen Trigger erfassen. Ein GPIO-Ereignis synchronisiert allein weder die Belichtung noch die interne DUT-Messung.
- Displayaktualisierung und Verzögerungsverhalten der Gerätetypen experimentell bestimmen.
- Prüfen, ob GSVmulti übermittelte Aufnahmezeiten verwendet oder nur Empfangszeiten zuordnet.

Wenn GSVmulti keine Aufnahmezeitstempel berücksichtigt, beseitigt ein interner Pi-Zeitstempel die zeitliche Verschiebung in GSVmulti nicht. Dann muss die Integration oder das Auswerteverfahren angepasst werden.

Ein höherer Sendetakt liefert keine zusätzlichen unabhängigen Messwerte, wenn die Anzeige langsamer aktualisiert. Wiederholte Beobachtungen desselben Werts sind außerdem nicht automatisch neue interne DUT-Messungen.

Für statische Kalibrierpunkte kann ein gemeinsames stabiles Zeitfenster geeignet sein. Für dynamische Vergleiche sind die Displayverzögerung und ihre Schwankung besonders kritisch. Ein Unsicherheitsbudget ist erst nach Messung der Einzelbeiträge sinnvoll; Latenz und Zeitunsicherheit dürfen nicht gleichgesetzt werden.

## 7. Erkennungssicherheit und Fehlerbehandlung

Kritische Fehler sind unter anderem falsche Ziffern, fehlendes Minuszeichen, übersehener Dezimalpunkt, falsche Einheit sowie Verwechslungen von Haupt- und Nebenanzeige.

Freigabekriterien sollten umfassen:

- ausreichende Schärfe, Belichtung und Sichtbarkeit;
- eindeutig identifizierter Messwertbereich;
- sicher erkannte Vorzeichen und Dezimalpunkte;
- erlaubtes Zahlenformat und bestätigte Einheit;
- Erkennung von Überlauf, Menüs und anderen ungültigen Betriebszuständen;
- nachvollziehbares Verhalten während eines Anzeigewechsels.

Konfidenzwerte eines Modells sind keine nachgewiesenen Fehlerwahrscheinlichkeiten. Die Freigabeschwellen müssen mit realen, auch bisher unbekannten Gerätetypen validiert werden. Eine explizite Ablehnung unlesbarer oder unbekannter Eingaben ist erforderlich.

KI-OCR und klassische Segmentprüfung können sich ergänzen. Ihre Übereinstimmung ist hilfreich, aber kein Beweis unabhängiger Fehlerfreiheit: Beide können durch dieselbe Spiegelung oder ein fehlendes Segment getäuscht werden.

Eine Zustandslogik sollte mindestens gültig, Übergang, unlesbar und veraltet unterscheiden. Mehrbildbestätigung erzeugt Verzögerung; diese muss dokumentiert und beim Zeitbezug berücksichtigt werden. Reale Messwertsprünge dürfen nicht durch Plausibilitätsregeln stillschweigend geglättet oder korrigiert werden.

Alte Werte dürfen bei Erkennungsverlust nicht unmarkiert als aktuelle gültige Werte weiterlaufen. Fehlerstatus, NaN, Auslassen eines Datensatzes oder ein anderer Mechanismus müssen zum tatsächlich unterstützten GSVmulti-Protokoll passen. Die Erkennung darf den Referenzwert nicht benutzen, um den DUT-Wert passend zu korrigieren.

## 8. Serielle Schnittstelle und GSVmulti

Das Ziel ist ein kontinuierlicher Datenstrom in einem von GSVmulti akzeptierten Format. CSV-Dateiimport, ASCII-Streaming und Emulation eines GSV-Geräts sind unterschiedliche Schnittstellenfälle.

Vor der Implementierung sind zu klären:

- konkrete GSVmulti-Version und unterstützte Geräteanbindung;
- Beispieltelegramm oder verbindliche Protokollspezifikation;
- Baudrate, Zeichenformat, Trennzeichen und Zeilenende;
- Dezimaltrennzeichen, Vorzeichen, Einheit und Kanalzahl;
- Geräteidentifikation und Initialisierungskommandos;
- Behandlung von Aufnahmezeit, ungültigen und veralteten Werten;
- Streaming-, Abfrage- und Wiederverbindungsverhalten.

Die Herstellerinformation zu ASCII-Betriebsarten von GSV-2/GSV-3 belegt noch keine Unterstützung beliebiger CSV-Datenströme. Falls erforderlich, muss der Adapter auch Gerätekommandos beantworten.

Als physische Verbindung kommen ein geeigneter USB-Seriell-Adapter oder ein UART mit passendem RS-232-/RS-485-Transceiver infrage. Für einen virtuellen USB-COM-Port ist eine geeignete USB-Device-/Bridge-Lösung zu wählen; diese Funktion am Pi 5 darf nicht pauschal vorausgesetzt werden. Pi-GPIO-Pegel dürfen nicht direkt mit RS-232 verbunden werden. Eine galvanische Trennung ist für den Laboraufbau zu prüfen.

### Interner Datensatz

Unabhängig vom späteren Ausgabeformat sollte intern mindestens Folgendes verfügbar sein:

| Feld | Inhalt |
| --- | --- |
| frame_sequence | Laufende Bildnummer |
| capture_timestamp | Aufnahmezeit mit dokumentierter Zeitbasis |
| value | Erkannter Zahlenwert |
| unit | Erkannte oder bestätigte Einheit |
| status | Gültig, Übergang, unlesbar oder veraltet |
| confidence | Qualitätskennzahl der Erkennung |
| profile_id | Verwendetes Geräte-/Anzeigeprofil |
| trigger_sequence | Optional zugeordnetes Triggerereignis |
| result_timestamp | Optionaler Zeitpunkt der Ergebnisfertigstellung |

Diese Felder sind ein interner Entwurf und kein bestätigtes GSVmulti-Telegramm.

## 9. Optischer Aufbau und Trainingsdaten

Auch KI benötigt lesbare Bilder. Sinnvoll sind eine verstellbare, stabile Halterung, ausreichend große Ziffern im Bild und reproduzierbare Beleuchtung. Reflexionen lassen sich gegebenenfalls durch Abschirmung und passend ausgerichtete Polarisationsfilter reduzieren; deren Einfluss auf LCD-Kontrast ist zu prüfen.

Nach der Einrichtung sollten Belichtung und Verstärkung möglichst konstant bleiben. Multiplexing, Flimmern und Ziffernwechsel können unvollständige oder überlagerte Zeichen erzeugen. Die passende Belichtung ist experimentell zu bestimmen.

Für Training und Validierung werden reale Bilder bzw. Videos benötigt, die Folgendes abdecken:

- verschiedene Hersteller, Displaytechniken und Segmentformen;
- alle Ziffern, Vorzeichen, Dezimalpunkte und relevanten Einheiten;
- wechselnde Entfernung, Perspektive und Beleuchtung;
- Unschärfe, Reflexionen, Verdeckung und abgeschnittene Anzeigen;
- Anzeigewechsel, Überlauf und Menüs.

Synthetische Daten können ergänzen. Die erforderliche Datenmenge ist noch offen. Die Validierung sollte ganze Geräte bzw. Modelle vom Training ausschließen, damit die Übertragbarkeit auf neu eintreffende Geräte geprüft wird. Benachbarte Frames derselben Aufnahme in Training und Test würden die Ergebnisse zu optimistisch erscheinen lassen.

## 10. Umsetzung und Abnahme

### Phase 1: Anforderungen und Material

Beispielgeräte und Aufnahmen sammeln, gewünschte zeitliche Zuordnung spezifizieren und das GSVmulti-Protokoll klären. Festlegen, ob überwiegend statische Kalibrierpunkte oder dynamische Verläufe erfasst werden sollen.

### Phase 2: Durchgängiger Prototyp

Displayfinder, bedienergeführte Auswahl, OCR, Zeitstempel und serielle Ausgabe auf dem Pi 5 verbinden. Mit mehreren unterschiedlichen Anzeigen prüfen. Ein manueller Displayausschnitt kann als Rückfalloption dienen.

### Phase 3: Robustheit

Tracking, Fehlerzustände, Profile, Diagnosebilder, Wiederverbindung und Dauerbetrieb ergänzen. Anhand realer Fehlablesungen entscheiden, ob spezialisierte Modelle oder IMX500-Ausführung benötigt werden.

### Phase 4: Validierung

Vollständig korrekte Datensätze, unerkannte Fehlablesungen, verworfene Werte, Latenzverteilung und zeitliche Zuordnung messen. Zusätzlich Gerätewechsel, Anzeigewechsel, Kameraverschiebung, Kommunikationsabbruch und Neustart testen.

Akzeptanzkriterien sind vor der Abnahme festzulegen. Eine hohe Zeichenquote allein genügt nicht; maßgeblich ist der gesamte Messwert einschließlich Vorzeichen, Dezimalpunkt, Einheit und Zeitbezug.

## 11. Offene Entscheidungen

1. Welches konkrete serielle Format akzeptiert die eingesetzte GSVmulti-Version?
2. Welche maximale Zeitabweichung zwischen DUT und Referenz ist zulässig?
3. Kann die Referenz einen Trigger oder Zeitstempel bereitstellen?
4. Welche Gerätetypen und Anzeigearten bilden den ersten freizugebenden Umfang?
5. Ist eine einmalige Bestätigung durch den Laboranten im Ablauf vorgesehen?
6. Wie werden ungültige Werte in GSVmulti und in der Kalibrierauswertung behandelt?

## 12. Quellen aus der bisherigen Diskussion

- [Raspberry Pi: AI Camera – Integration und eigene Modelle](https://www.raspberrypi.com/documentation/accessories/ai-camera.html)
- [ME-Systeme: Einstellung des Datenformats](https://www.me-systeme.de/en/software/gsvmulti/data-format)
- [ME-Systeme: GSVmulti-Handbuch, Version 2.6, Englisch](https://www.me-systeme.de/produkte/software/gsvmulti/anleitungen/ba-gsvmulti-v2.6_en.pdf)

Die Links dienen als Ausgangspunkte für die technische Umsetzung. Dieses Dokument fasst die Diskussion zusammen und ersetzt keine Prüfung der konkreten Hardware-, Software- und Protokollversionen.

