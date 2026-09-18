# Kandidatenprüfung automatische Siebensegment-Erkennung

Stand: 2026-09-18. Die Prüfung lief auf **Raspberry Pi 5 Model B Rev 1.1**,
Debian 13 (trixie), aarch64, Python 3.13.5. OpenCV 4.10.0 und NumPy 2.2.4
kommen unverändert aus `/usr/lib/python3/dist-packages`. Die isolierte
Worktree-`.venv` nutzt `--system-site-packages`; das Projekt wurde mit
`--no-deps` installiert. Kein Torch, TensorFlow oder Paddle wurde installiert.

Die Tabelle bewertet Ausführbarkeit und Herkunft, nicht Erkennungsqualität.
Alle exakten Download-URLs, Revisionen, Dateigrößen und SHA-256 stehen im
[maschinenlesbaren Manifest](../experiments/automatic_seven_segment/candidates.json).
Die Modellbinärdateien liegen ausschließlich im ignorierten Verzeichnis
`experiments/automatic_seven_segment/models/`.

| Kandidat | Lizenz / Modellstand | Größe Gewichte | Ergebnis auf diesem Pi |
| --- | --- | ---: | --- |
| Tesseract `ssd_int` | Apache-2.0, `e493a10a4bf81632506cf24ba99d83854afff9f6` | 1 442 809 Byte | Lädt mit vorhandenem Tesseract 5.5.0 |
| Tesseract `ssd` | Apache-2.0, gleicher Commit | 11 314 684 Byte | Lädt mit Tesseract 5.5.0 |
| Tesseract `7seg` | Apache-2.0, gleicher Commit | 11 435 044 Byte | Lädt mit Tesseract 5.5.0 |
| PP-OCRv5 mobile ONNX Detektor | Apache-2.0, `e6f4fa85f00e168c862bc462aebca69eef9b3d3d` | 4 826 518 Byte | CPU-Inferenz mit ONNX Runtime 1.30.0 erfolgreich |
| PP-OCRv5 mobile ONNX Recognizer | Apache-2.0, `ed152b8b495f84de93cda5709d768548a9127622` | 16 534 782 Byte | CPU-Inferenz erfolgreich; gehört zum selben vollständigen Kandidaten |
| `renjithsasidharan/seven-segment-ocr` | Nicht nachgewiesen, `1e8a42e4f8bed8934220c312c9b682c77ba01d9b` | Nicht heruntergeladen | Ausgeschlossen: ungeklärte Code-/Gewichtelizenz; kein passendes tflite-runtime-Wheel für Python 3.13 |

## Tesseract

Das [Originalrepository](https://github.com/Shreeshrii/tessdata_ssd/tree/e493a10a4bf81632506cf24ba99d83854afff9f6)
bezeichnet die Modelle als Proof of Concept. Synthetische Schriftbeispiele und
Trainingsfehler belegen keine Übertragbarkeit auf reale Geräte. Die
[Apache-2.0-Lizenz](https://github.com/Shreeshrii/tessdata_ssd/blob/e493a10a4bf81632506cf24ba99d83854afff9f6/LICENSE)
liegt im Repository. Der vorhandene Systemprozess verwendet Leptonica 1.84.1
und NEON. Es werden keine zusätzlichen Python-OCR-Pakete benötigt.

Ein weißes Bild (320 × 80 Pixel, PSM 7) lieferte bei `ssd_int` und `ssd` den
Text `1`, bei `7seg` leeren Text; alle Prozesse endeten mit Code 0. Das ist
ein synthetischer Negativtest, kein Genauigkeitsdatensatz. Der Adapter weist
daher nahezu strukturlose Bilder vor der OCR zurück. Unbekannte Zeichen
werden nicht durch eine Ziffern-Whitelist unterdrückt. Die Modelle liefern
keinen nachgewiesenen Segmentplan; automatische Detektion und Geometrie
müssen separat bewertet werden.

## PP-OCRv5 ohne Paddle-Installation

Die [offizielle Deployment-Dokumentation](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/docs/version3.x/inference_deployment/cross_platform/android_deployment.en.md)
verlinkt bereits konvertierte ONNX-Dateien. Deren offizielle Modellkarten
deklarieren Apache-2.0: [Detektor](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_det_onnx),
[Recognizer](https://huggingface.co/PaddlePaddle/PP-OCRv5_mobile_rec_onnx).
Damit ist keine lokale Paddle-/Paddle2ONNX-Installation nötig. Android-
Beispielzeiten sind keine Pi-Messung.

[ONNX Runtime unterstützt Linux ARM64](https://onnxruntime.ai/docs/get-started/with-python.html).
Verifiziert wurde das Wheel
`onnxruntime-1.30.0-cp313-cp313-manylinux_2_28_aarch64.whl`, SHA-256
`5327cf6aa15a02bad805fac8bd6882a62571e8b72f6f2938a8f37e6bd1966ce9`.
Es wurde ausschließlich in der Worktree-`.venv` mit `--no-deps` installiert.
Der Runtime-Code steht unter [MIT](https://github.com/microsoft/onnxruntime/blob/main/LICENSE).
Die Modellkonfiguration liest das bereits vorhandene Debian-PyYAML 6.0.2.
Die deklarierten kleinen Runtime-Abhängigkeiten FlatBuffers 25.12.19 und
Protobuf 6.33.2 wurden ebenfalls mit `--no-deps` ausschließlich dort
installiert; Packaging 25.0 ist bereits systemseitig vorhanden. Paket- und
Wheel-Hashes stehen im Manifest. Reproduktion im isolierten Worktree:

```bash
./.venv/bin/python -m pip install --no-deps onnxruntime==1.30.0 flatbuffers==25.12.19 protobuf==6.33.2
./.venv/bin/python -m pip check
```

`pip check` meldet auf diesem Host bereits sichtbare Debian-/Stub-Pakete
(`apt-listchanges`/`debconf`, `types-seaborn`, `types-flask-*`) mit fehlenden
PyPI-Metadaten beziehungsweise optionalen Paketen. Es meldet nach Installation
keine fehlende ONNX-Runtime-Abhängigkeit. Diese fremden Systempakete wurden
nicht verändert; ein global erfolgreiches `pip check` wird nicht behauptet.

Der experimentelle [Adapter](../src/dispread/experimental/ppocr_adapter.py)
verwendet zwei CPU-Sitzungen mit zwei Intra-Op-Threads und einem Inter-Op-Thread.
Die Modellkonfiguration und die offiziellen Referenzalgorithmen bestimmen:

* Detektor: BGR, lange Seite 960, auf Vielfache von 128 aufrunden, Mittelwerte
  `(0.485, 0.456, 0.406)`, Standardabweichungen `(0.229, 0.224, 0.225)`.
* DB-Postprocessing: Schwellwerte 0.3/0.6, höchstens 1000 Konturen,
  Unclip-Verhältnis 1.5. Rechtecke werden geometrisch um
  `Fläche × 1.5 / Umfang` erweitert. Das entspricht der äußeren Begrenzung
  des offiziellen Rechteck-Offsets, verzichtet aber bewusst auf dessen
  ganzzahlige Clipper-Quantisierung; kein Shapely/Pyclipper erforderlich.
* Recognizer: BGR, Höhe 48, Seitenverhältnis erhalten, mindestens 320 Spalten
  mit Null-Padding; über 3200 Spalten wird zurückgewiesen. Normalisierung
  nach `[-1, 1]`; Wörterbuch aus dem gepinnten YAML plus CTC-Blank und Space.
* CTC entfernt nur Wiederholungen und Blank. Vorzeichen und Dezimalzeichen
  bleiben erhalten. Text mit Einheiten oder sonstigen Zeichen wird abgelehnt.
  Jeder ausgegebene Zeichenscore muss mindestens 0.90 erreichen. Diese feste
  Entwicklungsvorgabe ist **keine kalibrierte Fehlerwahrscheinlichkeit**.

Referenzen unter Apache-2.0, Commit `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`:
[DetResizeForTest](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/ppocr/data/imaug/operators.py),
[DBPostProcess](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/ppocr/postprocess/db_postprocess.py),
[Recognition input](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/tools/infer/predict_rec.py),
[CTC decoder](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/ppocr/postprocess/rec_postprocess.py).
Die lokale Umsetzung importiert oder führt diesen Fremdcode nicht aus.

Ein reproduzierbarer synthetischer Rauchtest zeichnet `-12.3` mit OpenCV,
detektiert mindestens eine Textzeile und liest exakt `-12.3`; das unmittelbar
folgende weiße Bild wird zurückgewiesen. Das belegt den ausführbaren
Vor-/Nachverarbeitungspfad, **keine** Eignung für Siebensegmentanzeigen.
Die Regressionen prüfen zusätzlich Originalkoordinaten, getrennte Zeilen,
Rotation, CTC-Wiederholungen, Dezimalposition und schwache Vorzeichen.

```bash
./.venv/bin/pytest -q tests/test_ppocr_adapter.py
```

## Ausgeschlossener TFLite-Kandidat

Die rekursive Baumprüfung des
[gepinnten Repositories](https://github.com/renjithsasidharan/seven-segment-ocr/tree/1e8a42e4f8bed8934220c312c9b682c77ba01d9b)
fand keine LICENSE-, COPYING- oder NOTICE-Datei. Öffentliche Lesbarkeit ersetzt
keine explizite Nutzungslizenz. Gewichte und Code wurden deshalb nicht
ausgeführt oder integriert. Der veröffentlichte `predict.py`-Pfad importiert
TensorFlow; sein Alphabet enthält Ziffern, Kleinbuchstaben und Punkt, kein
Minuszeichen. Die [PyPI-Metadaten zu tflite-runtime 2.14.0](https://pypi.org/pypi/tflite-runtime/2.14.0/json)
listen ARM64-Wheels für CPython 3.8 bis 3.11, keines für 3.13. Ein Austausch
der Kamera-Pythonumgebung wäre keine zulässige Lösung dieser Einschränkung.
Der Kandidat bietet außerdem nur Erkennung eines Ausschnitts, keinen
vollständigen Detektions- und Overlay-Pfad.
