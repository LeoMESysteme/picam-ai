# Roadmap

Kernaussage zur Reihenfolge: von den sechs offenen Entscheidungen aus Konzept
§11 blockiert **nur OQ-01 (und über OQ-01 auch OQ-06) echte
Implementierungsarbeit** — und zwar ausschließlich P4. OQ-02, OQ-03 und OQ-04
blockieren die **Abnahme**, nicht das Bauen. Es gibt also keinen Grund zu
warten. Jede offene Frage hat einen Vorabdefault, mit dem gearbeitet wird.

| Phase | Ziel | Kamera? | GSVmulti-Spec? | Hartes Exit-Kriterium | Stand |
| --- | --- | --- | --- | --- | --- |
| **P0** | Grundgerüst, Trennstellen, Diagnose, Doku, Beispiele | nein | nein | `pytest` + `ruff` grün; Beispiel 16 erzeugt `values.jsonl` + Telegramme auf der Leitung | ✅ **erreicht** 2026-09-07 |
| **P1** | Kamera in Betrieb, Zeitbasis vermessen, erste `replay://`-Session | ja | nein | `camera-commissioning.sh` Exit 0; `TIMING.md` mit echten Zahlen | 🔶 **teilweise** — Kamera läuft, Zeitbasis-Domäne geklärt; `replay://` und Messung M2 offen |
| **P2** | Optischer Aufbau + realer Datensatz mit automatischem Label | ja | nein | ≥ 6 Geräteinstanzen über ≥ 3 Displaytypen, davon **2 gesperrt**; Manifeste vollständig | offen |
| **P3** | Werterkennung an realen Anzeigen, Freigabeschwellen kalibrieren | ja | nein | Trefferquote **pro Fehlerklasse** aufgeschlüsselt | offen |
| **P4** | Echte GSVmulti-Anbindung | nein | **ja** | GSVmulti nimmt den Strom an, zeigt Wert und Einheit korrekt; Verhalten bei ungültig/veraltet/Abbruch belegt | blockiert durch OQ-01, OQ-06 |
| **P5** | Zeitbezug vollständig: §6 von Prosa in Zahlen | ja | teilw. | Unsicherheitsbudget mit **getrennten** Einzelbeiträgen ausgefüllt | offen |
| **P6** | Robustheit und Dauerbetrieb (§10 Ph. 3) | ja | teilw. | 72-h-Dauerlauf mit provozierten Störungen; **kein unmarkierter Altwert**; Speicher stabil | offen |
| **P7** | Validierung und Abnahme (§10 Ph. 4) | ja | ja | Abnahmeprotokoll auf den Sperrgeräten gegen vorab festgelegte Kriterien | offen |
| **P8** | *optional:* eigenes Modell, Lokalisierung auf den IMX500 | ja | nein | belegter Gewinn bei CPU-Last oder Latenz gegenüber der Pi-Variante | offen |

## P0 — was tatsächlich steht

- [x] Repo-Grundgerüst nach MEhub-Konventionen, Importpaket `dispread`
- [x] Projekt-venv mit `--system-site-packages`, Paket mit `--no-deps`
- [x] `ValueRecord` mit genau den neun Feldern aus Konzept §8, verlustfrei serialisierbar
- [x] Trennstellen als `Protocol`: `FrameSource`, `DisplayLocator`, `ValueReader`, `ReleaseGate`, `ValueSink`, `TelegramFormatter`
- [x] Bildquellen-Registry über URI, `synthetic://` lauffähig
- [x] 7-Segment-Dekoder mit Per-Segment-Evidenz
- [x] Freigabelogik mit Veralterung, Mehrbildbestätigung, eigenständigen Kriterien für Vorzeichen, Dezimalpunkt und Einheit
- [x] JSONL-Audit-Log mit Rotation, serielle Ausgabe, provisorisches ASCII-CSV
- [x] Ende-zu-Ende-Beispiel ohne Hardware, mit Latenzmessung und Sink-Gesundheit
- [x] Kamera-Diagnoseskript mit Eskalationsleiter
- [x] 36 Tests grün, `ruff` grün
- [x] Doku-Set inkl. `status.md`, `project_history.md`, `open-questions.md`
- [ ] `folder://`, `video://`, `replay://`, `picamera2://`, `imx500://` — Registry vorhanden, Implementierungen noch nicht. `open_source()` scheitert für diese Schemata mit `ImportError`
- [ ] Tesseract-Vergleichsbackend (braucht [OQ-15](open-questions.md))
- [ ] CLI (`dispread.cli.*`, geplant mit `dispread run --source … --profile …`,
  [anleitung/05-cli.md](anleitung/05-cli.md)) — nicht gebaut. Der
  `pyproject.toml`-Einsprungpunkt `dispread` zeigt inzwischen auf die separate,
  bereits implementierte Workbench-CLI (`dispread.workbench.cli:main`), nicht
  auf diese. Kamera-Diagnose: `scripts/camera-commissioning.sh`
- [ ] `contour_heuristic`- und `imx500_detector`-Lokalisierung, `RegionTracker`
- [ ] Geräteprofile: `config/profiles/` samt JSON-Schema und `ProfileStore`
- [ ] `install.sh`, systemd-Units, udev-Regel, pre-commit-Hook
- [ ] `docs`-Konsistenztest (`tests/test_docs.py`): OQ-Nummern lückenlos, keine toten Verweise, `status.md` mit Datum

## Fehlerklassen und Datensatzregeln

Siehe [VALIDATION.md](VALIDATION.md). Zwei Punkte, die die Roadmap prägen:

* **Splitgrenze ist die Geräteinstanz, nie der Frame.** Konzept §9 warnt vor
  Nachbarframes derselben Aufnahme in Training und Test. Durchzusetzen als
  Gruppensplit mit einem Test, der bei Verletzung fehlschlägt.
* **Sperrgeräte früh vereinbaren.** Mindestens zwei Instanzen, bevorzugt ein
  ganzer Hersteller, werden vor jeder Entwicklung gesperrt und einmalig in der
  Abnahme ausgewertet.

## Messprogramm Zeitbezug

M1–M8, siehe [TIMING.md](TIMING.md). Zwei Punkte prägen die Priorisierung:

* **M8 ist der wichtigste Einzelversuch des Projekts** (nutzt GSVmulti den
  gelieferten Aufnahmezeitstempel?) und kostet eine halbe Stunde. So früh wie
  möglich, notfalls mit handgeschriebenem Telegramm.
* **M5 ist mit hoher Wahrscheinlichkeit der dominierende Term**
  (Displayaktualisierung und Haltezeit) und wird von keiner
  Softwareoptimierung kleiner. Früh messen, bevor Aufwand in
  Pipeline-Optimierung fließt.

## Sofort anstoßen, weil rein organisatorisch mit Vorlaufzeit

* [OQ-07](open-questions.md) — GSVmulti-Telegrammspezifikation intern beschaffen
* [OQ-09](open-questions.md) — Transceiver und galvanische Trennung
* [OQ-15](open-questions.md) — `tesseract-ocr`, `socat`, `chrony` installieren
* [OQ-04](open-questions.md) — Gerätekreis festlegen, Sperrgeräte vereinbaren

## Top-Risiken mit Frühwarnsignal

| Risiko | Frühwarnsignal | Gegenmaßnahme |
| --- | --- | --- |
| Generische OCR ist für vorzeichenbehaftete Dezimalwerte nicht genau genug | Schon auf den ersten 200 gelabelten Frames Dezimalpunkt- und Vorzeichenfehler **getrennt** auswerten. Zusammen > 1 % bei gutem Bild ⇒ generische OCR ist erledigt | Der klassische Segment-Dekoder ist bereits der Primärpfad, mit eigenständiger Prüfung von Vorzeichen und Dezimalpunkt |
| GSVmulti akzeptiert keine Aufnahmezeitstempel | M8 negativ | JSONL-Audit-Log als führende Zeitquelle; konstante Sendeverzögerung mit Korrekturwert |
| **Reflexionen erzeugen stille Fehlablesungen** | Gemessen: 2 von 40 bei starkem Glanz ([VALIDATION.md](VALIDATION.md)) | Abschirmung und Beleuchtung sind Voraussetzung, nicht Feinarbeit; `glare`-Flag blockiert die Freigabe |
| Displayverzögerung größer als die zulässige Abweichung | Erste M5-Messung an einem Gerät | Nur statische Kalibrierpunkte freigeben, dynamische Vergleiche ausschließen |
| Erwartung „funktioniert für beliebige unbekannte Geräte" | Geräte tauchen auf, die nicht im vereinbarten Umfang stehen | Konzept §2 sagt bereits, dass das nicht zusicherbar ist. Freigabe auf den benannten Gerätekreis beschränken, unbekannte Geräte **ablehnen** |
