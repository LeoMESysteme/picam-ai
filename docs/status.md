# Status — Stand 2026-09-08

Wird **überschrieben**, nicht angehängt. Erste Datei, die eine neue Session
liest. Verlauf: [project_history.md](project_history.md),
[lab_journal.md](lab_journal.md).

## Aktueller Stand

**P0 (Grundgerüst) erreicht, P1 (Kamera) teilweise.** Die Verarbeitungskette
aus Konzept §3 läuft Ende zu Ende ohne Hardware; die Kamera ist in Betrieb
genommen und vermessen. Was noch fehlt, steht unter P0 in
[ROADMAP.md](ROADMAP.md) als offene Punkte — insbesondere fünf der sechs
Bildquellen, das Tesseract-Backend und die CLI.

## Neu am 2026-09-08 (zweite Session)

* **Projekt-venv war unbrauchbar** und ist repariert. Das Repo war von
  `picam_number-ingestion` nach `picam-ai` umbenannt worden; eine venv trägt
  absolute Pfade in den Shebangs von `.venv/bin/*`, in `pyvenv.cfg` und in der
  `.pth`-Datei des editierbaren Installs. Symptome waren
  `./.venv/bin/pytest: cannot execute: required file not found` und
  `ModuleNotFoundError: No module named 'dispread'`. Pfade ersetzt; zusätzlich
  zwei verwaiste Konsolenskripte (`dispread-doctor`, `dispread-replay`) aus
  `.venv/bin/` entfernt — ihre Module (`dispread.cli.*`) existieren nicht und
  waren in `pyproject.toml` absichtlich gestrichen. Dokumentiert als Falle in
  [anleitung/00-werkzeuge.md](anleitung/00-werkzeuge.md).
* **Anleitung für den menschlichen Entwickler** unter
  [anleitung/](anleitung/README.md): zehn Kapitel (0–9) entlang der offenen
  P0-Punkte (`folder://` → Profile → CLI → Kamera/Replay → Lokalisierung →
  OCR-Backends → Betrieb), jeweils mit Vertrag, Test-zuerst-Spezifikation,
  Gerüst, Fallenliste und „Fertig, wenn"-Checkliste. Dazu Vertragsreferenz,
  Rezepte und Glossar. Kein neuer Code unter `src/`.

## Verifiziert (heute erneut ausgeführt)

| Punkt | Nachweis |
| --- | --- |
| 36 Tests grün, `ruff` grün | `./.venv/bin/pytest -q`, `./.venv/bin/ruff check src tests examples` (nach venv-Reparatur) |
| Kette Ende zu Ende | `examples/16_end_to_end_headless.py`: 40/40 korrekt, 40 Telegramme auf der Leitung, 0 stille Fehlablesungen |
| Läuft ohne Kamera | Quelle `synthetic://`, serielle Gegenstelle `os.openpty()` — kein `socat` nötig |
| Alle Doku-Verweise lösen auf | geprüft über alle `docs/**/*.md` |
| Glanz reproduziert den Befund | `examples/16_end_to_end_headless.py --glare 0.9`: `{'unreadable': 35, 'valid': 5}`, davon **2 still falsch**, Exit 1 |
| Mehrbildbestätigung greift | `--confirm-frames 3`: `{'transition': 37, 'valid': 3}` |

## Dokumentierte Nachweise vom 2026-09-07 (nicht erneut reproduziert)

* Kamera erkannt, Sensorknoten `.../i2c@88000/imx500@1a`, Anschluss CAM/DISP0.
  `scripts/camera-commissioning.sh` → Exit 0.
* IMX500: **6,8 s** `.rpk`-Warmlauf, **15,0 Inferenzen/s** (Stock-SSD 320×320),
  `CnnKpiInfo` dnn 13,96 ms / dsp 12,36 ms.
* `SensorTimestamp` in **CLOCK_BOOTTIME**; Semantik weiter offen (Messung M2).
* `CnnInputTensor` fehlt in den Standardmetadaten.
* Stock-Modelle liefern COCO-Labels → für Displays unbrauchbar, daher ist die
  bestätigte manuelle ROI der Primärpfad.
* Bei starkem synthetischem Glanz **2 stille Fehlablesungen von 40**.

Quellen: [TIMING.md](TIMING.md), [VALIDATION.md](VALIDATION.md).

## Blocker und Grenzen

* **Kein echter Gerätedatensatz.** Alle Zahlen stammen von synthetischem
  Material — Konzept §9 ist eindeutig, dass das kein Nachweis ist
  ([OQ-04](open-questions.md), [OQ-14](open-questions.md)).
* **GSVmulti-Protokoll unbekannt** ([OQ-01](open-questions.md),
  [OQ-06](open-questions.md), [OQ-07](open-questions.md)). ASCII-CSV bleibt
  ausdrücklich provisorisch, `gsv_ascii.py` wirft absichtlich.
* **Elektrische serielle Strecke offen** ([OQ-09](open-questions.md)) — kein
  Transceiver, nur gegen pty geprüft.
* **`tesseract-ocr`, `socat`, `chrony` nicht installiert**
  ([OQ-15](open-questions.md)): `sudo` verlangt seit dem Reboot ein Passwort.
* **Fokus der Kamera verstellt**, kein definierter optischer Aufbau. Nach dem
  Glanz-Befund ist das der wichtigste physische Hebel
  ([OPTICAL_SETUP.md](OPTICAL_SETUP.md)).
* **Dezimalpunkt wird nicht optisch gemessen**, sondern aus dem Profil
  übernommen ([OQ-17](open-questions.md)). Dasselbe gilt für die Einheit, dort
  bereits als `unit_source=profile` markiert.

## Ergebnis der Tool-Recherche vom 2026-09-08

[tool_review_2026-09-08.md](tool_review_2026-09-08.md): Empfohlen ist die
bestehende Basis plus ein kleiner neuronaler Zeilenleser auf dem Pi über ONNX
Runtime; RapidOCR ist Integrationskandidat. PP-OCRv5 mobile und PP-OCRv6
tiny/small sind mit **realen** Displaydaten gegen Segmentleser und Tesseract zu
vergleichen. Das ist eine Empfehlung, keine beschlossene Migration.

Dabei neu erfasst: [OQ-16](open-questions.md) bis
[OQ-19](open-questions.md).

## Zu OQ-16 (Vollständigkeit) — inzwischen weitgehend erledigt

Die damals fehlenden Dokumente `ROADMAP.md`, `dependencies.md`,
`HARDWARE_PROFILE.md` und `lab_journal.md` existieren jetzt, ebenso
`OPTICAL_SETUP.md`. Zusätzlich bereinigt: `pyproject.toml` deklarierte zwei
Konsolenskripte auf nicht vorhandene Module — entfernt. `CLAUDE.md` markiert
jetzt je Komponente, was fertig ist und was nur als Registry-Eintrag existiert.
Offen bleibt der Teil von OQ-16, der die fehlenden CLI- und Replay-Komponenten
betrifft; sie stehen als offene Punkte unter P0 in [ROADMAP.md](ROADMAP.md).

## Nächste drei Schritte

1. **Fehlende Pakete installieren** (braucht einen Menschen mit `sudo`):
   `sudo apt install -y tesseract-ocr tesseract-ocr-eng socat chrony`
2. **Optischen Aufbau herstellen**, Fokus einstellen, erste echte Aufnahmen
   sammeln — dann `replay://` implementieren. Ab da ist die Kette gegen reales
   Material regressionsfähig. Ablauf und Fallen:
   [anleitung/06-kamera-aufnahme-replay.md](anleitung/06-kamera-aufnahme-replay.md).
   Ohne Hardware parallel möglich: `folder://` und die Geräteprofile
   ([anleitung/03](anleitung/03-erste-bildquelle-folder.md),
   [anleitung/04](anleitung/04-geraeteprofile.md)).
3. **OQ-07 und OQ-09 organisatorisch anstoßen.** Beide haben Vorlaufzeit und
   blockieren nichts, solange sie laufen.

## Wichtigster offener Messpunkt

**M8** ([TIMING.md](TIMING.md)): Verwendet GSVmulti einen übermittelten
Aufnahmezeitstempel, oder nur die Empfangszeit? Kostet nach Vorliegen der
Spezifikation eine halbe Stunde und entscheidet die Integrationsstrategie.
Ein schnellerer Leser behebt weder die unbekannte Displayverzögerung (M5) noch
eine fehlende Zeitzuordnung.
