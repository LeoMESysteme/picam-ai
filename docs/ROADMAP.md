# Roadmap

Kernaussage zur Reihenfolge: von den sechs offenen Entscheidungen aus Konzept
§11 blockiert **nur OQ-01 (und über OQ-01 auch OQ-06) echte
Implementierungsarbeit** — und zwar ausschließlich P4. OQ-02, OQ-03 und OQ-04
blockieren die **Abnahme**, nicht das Bauen. Der Bau kann damit weitergehen;
Freigabe und Abnahme bleiben an ihre Nachweise und Entscheidungen gebunden. Stand des Abgleichs: 2026-10-21.

| Phase | Ziel | Kamera? | GSVmulti-Spec? | Hartes Exit-Kriterium | Stand |
| --- | --- | --- | --- | --- | --- |
| **P0** | Grundgerüst, Trennstellen, Diagnose, Doku, Beispiele | nein | nein | `pytest` + `ruff` grün; Beispiel 16 erzeugt `values.jsonl` + Telegramme auf der Leitung | ✅ **erreicht** 2026-09-07 |
| **P1** | Kamera in Betrieb, Zeitbasis vermessen, erste `replay://`-Session | ja | nein | `camera-commissioning.sh` Exit 0; `TIMING.md` mit echten Zahlen | 🔶 **teilweise** — seit 2026-09-25 StreamCam statt IMX500; `camera-commissioning.sh` Exit 0 (2026-09-28), Zeitbasis MONOTONIC → BOOTTIME über gemessenen Versatz, `replay://` implementiert; Zeitstempel-Semantik offen (OQ-43, für die Ernte durch die Timing-Kalibrierung abgedeckt) |
| **P2** | Optischer Aufbau + realer Datensatz mit automatischem Label | ja | nein | ≥ 6 Geräteinstanzen über ≥ 3 Displaytypen, davon **2 gesperrt**; Manifeste vollständig | **teilweise** — Sammelmodus, serielle Auto-Labels, Timing-Kalibrierung, Ernte und Import gebaut; reale Dot-Matrix-Daten und mehrere Aufstellungen vorhanden. Geräte-/Displayvielfalt und zwei gesperrte Geräteinstanzen fehlen; mehrere Aufstellungen desselben GSV-2AS sind keine weiteren Geräte |
| **P3** | Werterkennung an realen Anzeigen, Freigabeschwellen kalibrieren | ja | nein | Trefferquote **pro Fehlerklasse** aufgeschlüsselt; reale Freigabeschwellen für den vereinbarten Gerätekreis belegt | **teilweise** — Dot-Matrix-Abnahme 3: 215/215 richtig auf zwei neuen Aufstellungen desselben GSV-2AS (2026-09-30); Live-Bedienerläufe seit 2026-10-21. Andere Geräte, Vorzeichen, Einheiten und angepasste Toleranz nicht abgenommen |
| **P4** | Echte GSVmulti-Anbindung | nein | **ja** | GSVmulti nimmt den Strom an, zeigt Wert und Einheit korrekt; Verhalten bei ungültig/veraltet/Abbruch belegt | blockiert durch OQ-01, OQ-06 |
| **P5** | Zeitbezug vollständig: §6 von Prosa in Zahlen | ja | teilw. | Unsicherheitsbudget mit **getrennten** Einzelbeiträgen ausgefüllt | **teilweise** — StreamCam-Timing-Kalibrierung und Live-Referenzauswertung vorhanden; getrenntes Budget, Referenzsynchronität und M8 weiter offen |
| **P6** | Robustheit und Dauerbetrieb (§10 Ph. 3) | ja | teilw. | 72-h-Dauerlauf mit provozierten Störungen; **kein unmarkierter Altwert**; Speicher stabil | **teilweise** — Live-Pfad mit STALE und Audit gebaut, kurze Störversuche vorhanden; 72 h, Audit-Aufbewahrung und Nachführung bei großen Wertwechseln offen ([OQ-26](open-questions.md#oq-26)) |
| **P7** | Validierung und Abnahme (§10 Ph. 4) | ja | ja | Abnahmeprotokoll auf den Sperrgeräten gegen vorab festgelegte Kriterien | offen |
| **P8** | *optional:* eigenes Modell, Lokalisierung auf den IMX500 | ja | nein | belegter Gewinn bei CPU-Last oder Latenz gegenüber der Pi-Variante | offen — ruht, IMX500 außer Betrieb seit 2026-09-25 |

## P0 — was tatsächlich steht

- [x] Live-Messpfad mit `CameraOwner`, Browser-Einrichtung und namentlicher
  Bestätigung auf `/live`, Dot-Matrix-Leser und JSONL-Audit pro Lauf:
  **gebaut, Einrichtung und Bedienerläufe am Aufbau geprüft** (2026-10-21).
  Referenzaufzeichnung und nachträglicher Abgleich sind vorhanden; diese
  Läufe ersetzen keine formale Systemabnahme
  ([VALIDATION.md](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21)).
  Im inzwischen beendeten Werteplan-Versuch zeigte Faktor 2
  Nachführungsverlust, bei Faktor 0,5 kam VALID ohne Eingriff zurück.
  Die Rückstellung ist bestätigt; die Nachführung bleibt fehleranfällig
  ([OQ-26](open-questions.md#oq-26), [Status](status.md)).
  Abschlussauswertung des 13,4-min-Werteplan-Laufs: 0/11 137 Fehllesungen,
  aber kein VALID in stabilen Referenzfenstern bei Faktor 2 und 5;
  Rückstellung bestätigt. Die Nachführung bleibt damit offen
  ([Auswertung](VALIDATION.md#messpfad-live-werteplan-2026-10-21)).
  Keine serielle Ausgabe an GSVmulti; diese bleibt P4 / OQ-07.

- [x] Repo-Grundgerüst nach MEhub-Konventionen, Importpaket `dispread`
- [x] Projekt-venv mit `--system-site-packages`, Paket mit `--no-deps`
- [x] `ValueRecord` mit den neun Konzeptfeldern plus Auditfeldern, verlustfrei serialisierbar
- [x] Trennstellen: `FrameSource`, `DisplayLocator`, `ValueReader`,
  `ValueSink` und `TelegramFormatter` als `Protocol`; `ReleaseGate` als
  konkrete Klasse
- [x] Bildquellen-Registry über URI, `synthetic://` lauffähig
- [x] 7-Segment-Dekoder mit Per-Segment-Evidenz
- [x] Freigabelogik mit Veralterung, Mehrbildbestätigung, eigenständigen Kriterien für Vorzeichen, Dezimalpunkt und Einheit
- [x] JSONL-Audit-Log mit Rotation, serielle Ausgabe, provisorisches ASCII-CSV
- [x] Ende-zu-Ende-Beispiel ohne Hardware, mit Stufen-Rechenzeiten und Sink-Gesundheit; synthetische Aufnahmezeiten belegen keine reale Latenz
- [x] Kamera-Diagnoseskript mit Eskalationsleiter
- [x] Tests und `ruff` für den damaligen P0-Stand grün (die konkrete
  Testanzahl ist kein aktueller Projektstatus)
- [x] Doku-Set inkl. `status.md`, `project_history.md`, `open-questions.md`
- [x] `replay://` — implementiert (Clips mit einem Label je Clip)
- [x] `v4l2://` — `UvcSource` für die Logitech StreamCam (seit 2026-09-25 aktive Kamera): Regler setzen und zurücklesen, Zeitbasis `v4l2_monotonic` mit Umrechnung über `records.to_boottime_ns`, Hardwaretest `tests/test_uvc_hardware.py`
- [ ] `folder://`, `video://` — Registry vorhanden, Implementierungen noch nicht
- `picamera2://`, `imx500://` — **außer Betrieb** seit 2026-09-25 (IMX500 durch StreamCam ersetzt, `docs/project_history.md`); `open_source()` meldet das gezielt
- [ ] Tesseract-Vergleichsbackend — `dispread.ocr.tesseract_cli` ist gebaut
  und Ende-zu-Ende verdrahtet (Profil/Controller/UI); [OQ-15](open-questions.md)
  selbst ist geklärt (Binary installiert). Offen ist die Erkennungsgüte:
  0/11 echte GSV-Sensor-Fotos werden bisher erfolgreich gelesen (nie falsch,
  aber auch nicht richtig) — siehe [OQ-15](open-questions.md#oq-15)
- [ ] CLI (`dispread.cli.*`, geplant mit `dispread run --source … --profile …`,
  [anleitung/05-cli.md](anleitung/05-cli.md)) — nicht gebaut. Der
  `pyproject.toml`-Einsprungpunkt `dispread` zeigt inzwischen auf die separate,
  bereits implementierte Workbench-CLI (`dispread.workbench.cli:main`), nicht
  auf diese. Kamera-Diagnose: `scripts/camera-commissioning.sh`
- [x] Konturbasierte Vorschläge in `workbench.vision`, bestätigte ROI und
  `QuadTracker`-Nachführung; der Live-Pfad nutzt `TrackedQuadLocator`.
  Reale Grenzen bleiben [OQ-25](open-questions.md#oq-25) und
  [OQ-26](open-questions.md#oq-26); `imx500_detector` ruht mit der IMX500
- [x] Workbench-Profile und `SessionProfile` gebaut, mit bestätigter
  Geometrie und Kamerareglern; das frühere Ziel `config/profiles/` samt
  allgemeinem `ProfileStore` ist nicht umgesetzt
- [ ] Allgemeines `install.sh`, Messdienst, udev-Regel, pre-commit-Hook;
  `scripts/install-workbench.sh` und systemd-Units für die Doku-Runner
  existieren bereits
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
* [OQ-04](open-questions.md) — Gerätekreis festlegen, Sperrgeräte vereinbaren

## Top-Risiken mit Frühwarnsignal

| Risiko | Frühwarnsignal | Gegenmaßnahme |
| --- | --- | --- |
| Generische OCR ist für vorzeichenbehaftete Dezimalwerte nicht genau genug | Schon auf den ersten 200 gelabelten Frames Dezimalpunkt- und Vorzeichenfehler **getrennt** auswerten. Zusammen > 1 % bei gutem Bild ⇒ generische OCR ist erledigt | Der aktuelle GSV-2AS-Pfad nutzt den Dot-Matrix-Leser mit Zell-, Syntax- und Einheitsprüfung; 7-Segment und Tesseract bleiben getrennte Backends |
| GSVmulti akzeptiert keine Aufnahmezeitstempel | M8 negativ | JSONL-Audit-Log als führende Zeitquelle; konstante Sendeverzögerung als zu prüfende Integrationsoption |
| **Reflexionen erzeugen stille Fehlablesungen** | Synthetischer 7-Segment-Test: 2 von 40 bei starkem Glanz ([VALIDATION.md](VALIDATION.md)) | Abschirmung und Beleuchtung sind Voraussetzung, nicht Feinarbeit; `glare`-Flag blockiert die Freigabe |
| Displayverzögerung größer als die zulässige Abweichung | Erste M5-Messung an einem Gerät | Nur statische Kalibrierpunkte freigeben, dynamische Vergleiche ausschließen |
| Erwartung „funktioniert für beliebige unbekannte Geräte" | Geräte tauchen auf, die nicht im vereinbarten Umfang stehen | Konzept §2 sagt bereits, dass das nicht zusicherbar ist. Freigabe auf den benannten Gerätekreis beschränken, unbekannte Geräte **ablehnen** |
