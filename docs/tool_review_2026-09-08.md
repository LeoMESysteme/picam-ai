# Tool-Review zur Displayauslesung — 2026-09-08

Recherche und Empfehlung, **keine beschlossene Migration und kein Benchmark**.
Geprüft: Konzept, Projekt-Historie, Status, offene Fragen, Validierung,
Timing-Dokument, pyproject.toml und vorhandene Leser-/Pipeline-/Freigabemodule.

## Empfehlung

Picamera2/libcamera, OpenCV/NumPy, eine bestätigte ROI mit Positionsüberwachung,
den eigenen Segmentleser für freigegebene 7-Segment-Profile und einen kleinen
neuronalen Zeilenleser auf der Pi-CPU über ONNX Runtime kombinieren.
Tesseract bleibt Vergleichsbasis. Leserwahl pro Displayfamilie anhand realer
Fehlerdaten; automatische Lokalisierung auf dem IMX500 erst bei belegtem Bedarf.
Eine höhere Erkennungsqualität ist noch nicht nachgewiesen.

## Befund im Projekt

Die Projekt-Historie konkretisiert das ursprüngliche Konzept bereits sinnvoll:
manuelle ROI als Primärpfad, Segmentleser, Tesseract als Vergleich, ONNX Runtime
bei CPU-Bedarf, Training off-Pi. Die Begründung „Inferenzziel ist der IMX500“
sollte die Wahl des besten OCR-Lesers aber nicht vorwegnehmen.

* VALIDATION.md dokumentiert bei starkem synthetischem Glanz **2 stille
  Fehlablesungen unter 40 Frames**. Das ist kein Realgeräte-Benchmark.
* Der Segmentleser verlangt ein bekanntes Raster; LCD-Polarität und der Fall
  ausschließlich angezeigter Achten sind offen (OQ-13).
* Dezimalpunkt und Einheit stammen aus dem Profil. Der Punkt wird trotzdem
  als `decimal_point_detected` gemeldet (OQ-17). Wechselnde Punktpositionen
  brauchen Bildnachweise oder einen nachgewiesenen festen Gerätezustand.
* Das Gate verlangt Segment-Kontrast und Segmentabstand. Weitere Leser
  brauchen passende Freigabeevidenz (OQ-19), keine erfundenen Segmentdiagnosen.
* Mehrere referenzierte Dateien fehlen lokal (OQ-16). Frühere Hardware- und
  Testresultate wurden in dieser Session nicht erneut verifiziert.

## Werkzeugvergleich

| Baustein | Empfehlung | Begründung / Grenze |
| --- | --- | --- |
| Kamera | Picamera2/libcamera behalten | Vorhandener IMX500, Bild und Metadaten gemeinsam erfassen. |
| Bildverarbeitung | OpenCV/NumPy behalten | Entzerrung und Segmentanalyse bereits integriert. |
| 7-Segment | Eigenen Leser verbessern | Segment-Evidenz hilft bei Diagnose; Raster, Polarität und Glanz bleiben Grenzen. |
| Andere Segmentsoftware | ssocr optional vergleichen | Explizit für 7-Segment-Erkennung; kein belegter Genauigkeitsvorteil, Evidenzintegration müsste ergänzt werden. [Projekt](https://github.com/auerswal/ssocr) |
| Neuronale OCR | Kleines PP-OCR-Modell testen | Nur entzerrte Messwertzeile lesen; zusätzliche Textdetektion und Orientierung bei bestätigter Geometrie auslassen. |
| Integration | RapidOCR + ONNX Runtime für den Versuch | ONNX-basierte PaddleOCR-Modelle, getrennt schaltbare Detektion/Orientierung/Erkennung. [Projekt](https://github.com/RapidAI/RapidOCR), [Parameter](https://rapidai.github.io/RapidOCRDocs/v2.1.0/install_usage/rapidocr/parameters/) |
| Produktivadapter | RapidOCR behalten oder schmalen ONNX-Adapter wählen | Nach Abhängigkeitsprüfung entscheiden; eigener Adapter übernimmt Vorverarbeitung und Dekodierung. |
| Vergleichsbasis | Tesseract behalten | Einzeilenmodus `--psm 7`, eventuell `13`, passende Zeichenliste und deaktivierte Wortlexika testen. Zahlenfilter nur auf Messwert-ROI; Status/Einheit separat prüfen. [Dokumentation](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html) |
| EasyOCR | Keine erste Wahl | PyTorch-basierte Integration erweitert die Laufzeitabhängigkeiten; Mehrwert für diese Aufgabe unbelegt. [Projekt](https://github.com/JaidedAI/EasyOCR) |
| Ausgabe/Betrieb | pyserial, Adapter, JSON, JSONL, systemd behalten | Offener Punkt ist das GSVmulti-Protokoll einschließlich Zeit-/Fehlerbehandlung. |

RapidOCR ist Integrationsschicht, ONNX Runtime Inferenzlaufzeit und PP-OCR
das Modell; keine drei unabhängigen Erkenner. Zwei Leser desselben Bildes
können durch dieselbe Reflexion getäuscht werden. Widerspruch explizit
auswerten; ein Fallback darf eine Qualitätsablehnung nicht umgehen.

## Konkrete OCR-Kandidaten und Installation

**PP-OCRv5_mobile_rec** als Vergleichspunkt und **PP-OCRv6_tiny_rec** sowie
**PP-OCRv6_small_rec** als neuere Kandidaten aufnehmen. PaddleOCR dokumentiert
unterschiedliche Evaluationsdatensätze; die Genauigkeitswerte sind nicht direkt
vergleichbar und keine Displaygenauigkeit. ONNX-Export und Unterstützung in
der gewählten RapidOCR-Version konkret prüfen.
[Modellübersicht](https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html)

ONNX Runtime bietet inzwischen CPython-3.13-Wheels für Linux ARM64,
beispielsweise `onnxruntime-1.29.0-cp313-cp313-manylinux_2_28_aarch64.whl`.
Das belegt Verfügbarkeit, noch keine lokale ABI-Verträglichkeit.
[Paketdateien](https://pypi.org/project/onnxruntime/#files)

Projektregel beibehalten: `.venv` mit `--system-site-packages`, Installation
mit `--no-deps`; keine automatisch nachgezogenen PyPI-Versionen von NumPy
oder OpenCV. Benötigte Pakete, Modell, Zeichensatz, Vorverarbeitung, Lizenz
und Prüfsummen explizit dokumentieren. Training/Export bleiben off-Pi.

Scheitern Standardmodelle auf echten Segmentanzeigen, als nächste Option
einen kleinen Displayzeilen-Erkenner mit realen Trainingsdaten entwickeln.
Synthetische Daten allein belegen keine Übertragbarkeit.

## AI Camera und Lokalisierung

Vorhandene Kamera weiterverwenden. OCR auf dem Pi; ein späterer IMX500-
Detektor hilft beim Einrichten/Wiederfinden. Zuerst Einrichtungsdauer und
Positionsverluste messen. COCO-Stockmodelle sind keine Messdisplayfinder.

Als ersten Tracking-Versuch stabile Merkmale am Displayrahmen mit OpenCV
verfolgen, nicht wechselnde Ziffern. Trackingqualität muss die Freigabe
beeinflussen; bei Verlust erneut bestätigen.
[OpenCV Optical Flow](https://github.com/opencv/opencv/blob/4.x/doc/tutorials/others/optical_flow.markdown)

Die aktuelle Raspberry-Pi-Anleitung beschreibt **Edge-MDT** mit MCT und
Converter, danach RPK-Paketierung auf dem Pi. Optimierung/Konvertierung
üblicherweise auf Desktop oder Server.
[Deployment-Anleitung](https://www.raspberrypi.com/documentation/accessories/ai-camera.html)

Ultralytics dokumentiert IMX500-Export für YOLOv8n und YOLO11n; neuere
Familien werden nicht automatisch unterstützt. AGPL-3.0/Enterprise-Bedingungen
vor Festlegung prüfen; das ist keine pauschale Aussage über alle YOLO-
Implementierungen. [Export](https://docs.ultralytics.com/integrations/sony-imx500/),
[Lizenzmodell](https://www.ultralytics.com/license)

Zusatzbeschleuniger oder Kameratausch sind durch die bisherigen Daten nicht
begründet. Erst messen, ob Rechenleistung, Optik oder Displayaktualisierung
den Betrieb begrenzen.

## Nächster Vergleich

1. Fehlende Planungsdateien abgleichen, Optik einrichten und echte Aufnahmen
   mehrerer Geräte sammeln: Vorzeichen, Punktpositionen, LCD/LED, Menüs,
   Überlauf, Reflexion und Anzeigewechsel.
2. Profilannahmen von Bildbeobachtungen trennen; gemeinsame Bildqualitätsprüfung
   und leserspezifische Evidenzregeln definieren.
3. Segmentleser, Tesseract und neuronale Kandidaten auf denselben Aufnahmen
   offline vergleichen; ungeprüfte Ergebnisse nicht an GSVmulti freigeben.
4. Vollständige Messwertfehler, unerkannte Fehler, Falschablehnungen und
   Zustandsfehler getrennt zählen. Geräteinstanzen zwischen Entwicklung/Test
   trennen; für Übertragbarkeit ganze Modelle zurückhalten. Scores bleiben
   ohne Kalibriermessung unkalibriert.
5. Rechenzeit auf dem Pi mit expliziten CLOCK_MONOTONIC-Messmarken,
   Speicherbedarf und Durchsatz messen. Aufnahme-bis-Ausgabe-Latenz nur mit
   gültigen, abgeglichenen Zeitbasen; synthetische Frame-Zeitstempel und
   Datei-mtime sind dafür ungeeignet. Bildalter und Puffer begrenzen.
6. GSVmulti-Protokoll und Aufnahmezeit-Unterstützung organisatorisch klären.
   Leserwahl anhand Fehlerquoten und Zeitbudget; Lokalisierung danach ausbauen.

Keine Pakete installiert, Hardware verändert oder neue Messungen durchgeführt.
Keine Modellmigration umgesetzt.
