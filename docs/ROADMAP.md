# Roadmap

Stand des Abgleichs: **2026-10-28**. Die UserDefined-Schnittstelle ist durch
die Herstelleranleitung belegt; ein GSVmulti-Prototyp kann jetzt gebaut
werden ([Bewertung](GSVMULTI_PROTOCOL.md)). P4 ist noch nicht umgesetzt
oder abgenommen: Empfang in 2.01 Pro (OQ-01), Ungültigbehandlung (OQ-06),
Transport/Wiederanlauf (OQ-47) und Zeitachse (M8/P5) brauchen Nachweise.
OQ-02, OQ-03 und OQ-04 betreffen weiterhin die Abnahme.

| Phase | Ziel | Kamera? | GSVmulti-Spec? | Hartes Exit-Kriterium | Stand |
| --- | --- | --- | --- | --- | --- |
| **P0** | Grundgerüst, Trennstellen, Diagnose, Doku, Beispiele | nein | nein | `pytest` + `ruff` grün; Beispiel 16 erzeugt `values.jsonl` + Telegramme auf der Leitung | ✅ **erreicht** 2026-09-07 |
| **P1** | Kamera in Betrieb, Zeitbasis vermessen, erste `replay://`-Session | ja | nein | `camera-commissioning.sh` Exit 0; `TIMING.md` mit echten Zahlen | 🔶 **teilweise** — seit 2026-09-25 StreamCam statt IMX500; `camera-commissioning.sh` Exit 0 (2026-09-28), Zeitbasis MONOTONIC → BOOTTIME über gemessenen Versatz, `replay://` implementiert; Zeitstempel-Semantik offen (OQ-43, für die Ernte durch die Timing-Kalibrierung abgedeckt) |
| **P2** | Optischer Aufbau + realer Datensatz mit automatischem Label | ja | nein | ≥ 6 Geräteinstanzen über ≥ 3 Displaytypen, davon **2 gesperrt**; Manifeste vollständig | **teilweise** — Sammelmodus, serielle Auto-Labels, Timing-Kalibrierung, Ernte und Import gebaut; reale Dot-Matrix-Daten und mehrere Aufstellungen vorhanden. Geräte-/Displayvielfalt und zwei gesperrte Geräteinstanzen fehlen; mehrere Aufstellungen desselben GSV-2AS sind keine weiteren Geräte |
| **P3** | Werterkennung an realen Anzeigen, Freigabeschwellen kalibrieren | ja | nein | Trefferquote **pro Fehlerklasse** aufgeschlüsselt; reale Freigabeschwellen für den vereinbarten Gerätekreis belegt | **teilweise** — Dot-Matrix-Abnahme 3: 215/215 richtig auf zwei neuen Aufstellungen desselben GSV-2AS (2026-09-30); Live-Bedienerläufe seit 2026-10-21. Andere Geräte, Vorzeichen, Einheiten und angepasste Toleranz nicht abgenommen |
| **P4** | Echte GSVmulti-Anbindung | nein | **ja** | GSVmulti nimmt den Strom an, zeigt Wert und Einheit korrekt; Verhalten bei ungültig/veraltet/Abbruch belegt | **offen** — UserDefined-Spezifikation vorhanden (2026-10-28), Prototyp baubar; Adapter und Abnahme fehlen (OQ-01, OQ-06, OQ-47) |
| **P5** | Zeitbezug vollständig: §6 von Prosa in Zahlen | ja | teilw. | Unsicherheitsbudget mit **getrennten** Einzelbeiträgen ausgefüllt | **teilweise** — StreamCam-Timing-Kalibrierung und Live-Referenzauswertung vorhanden; getrenntes Budget, Referenzsynchronität und M8 weiter offen |
| **P6** | Robustheit und Dauerbetrieb (§10 Ph. 3) | ja | teilw. | 72-h-Dauerlauf mit provozierten Störungen; **kein unmarkierter Altwert**; Speicher stabil | **teilweise** — Live-Pfad mit STALE und Audit gebaut, kurze Störversuche vorhanden; 72 h, Audit-Aufbewahrung und Nachführung bei großen Wertwechseln offen ([OQ-26](open-questions.md#oq-26)) |
| **P7** | Validierung und Abnahme (§10 Ph. 4) | ja | ja | Abnahmeprotokoll auf den Sperrgeräten gegen vorab festgelegte Kriterien | offen |
| **P8** | *optional:* eigenes Modell, Lokalisierung auf den IMX500 | ja | nein | belegter Gewinn bei CPU-Last oder Latenz gegenüber der Pi-Variante | offen — ruht, IMX500 außer Betrieb seit 2026-09-25 |

## Arbeitsschritte und Checkpoints {#roadmap-schritte}

Die Karte liest diese Schritte zusammen mit der Phasentabelle. Die Reihenfolge
der offenen Schritte ist die Priorität innerhalb des jeweiligen Meilensteins;
die projektweite Arbeitsreihenfolge bleibt in [TODO](../TODO.md).
„Gebaut“ bezeichnet die Umsetzung, „belegt“ einen ausdrücklich verlinkten
Nachweis. Beides ersetzt keine vollständige Systemabnahme. Ein leeres Datum
bedeutet, dass kein einzelner Aktualisierungszeitpunkt dokumentiert ist.

<div class="roadmap-steps-source" markdown="1">

| Phase | ID | Schritt | Stand | Aktualisiert | Beleg |
| --- | --- | --- | --- | --- | --- |
| P0 | p0-geruest | Repo-Grundgerüst | gebaut | — | [P0-Nachweis](#p0-was-tatsachlich-steht) |
| P0 | p0-vertraege | `ValueRecord` und Trennstellen | gebaut | — | [P0-Nachweis](#p0-was-tatsachlich-steht) |
| P0 | p0-freigabe | Freigabe mit Veralterung und eigenständigen Qualitätskriterien | gebaut | — | [P0-Nachweis](#p0-was-tatsachlich-steht) |
| P0 | p0-audit | JSONL-Audit und ausdrücklich provisorische Ausgabe | gebaut | — | [P0-Nachweis](#p0-was-tatsachlich-steht) |
| P0 | p0-beispiel | Ende-zu-Ende-Beispiel ohne Hardware | gebaut | — | [P0-Nachweis](#p0-was-tatsachlich-steht) |
| P0 | p0-diagnose | Kamera-Diagnose und Projektdokumentation | gebaut | — | [P0-Nachweis](#p0-was-tatsachlich-steht) |
| P1 | p1-kamera | StreamCam: Kamera-Commissioning mit Exit 0 | belegt | 2026-09-28 | [Inbetriebnahme](VALIDATION.md#2026-09-28-streamcam-inbetriebnahme-hardwaretest-probeaufnahme) |
| P1 | p1-replay | `replay://` implementiert | gebaut | — | [Bildquellenstand](#p0-was-tatsachlich-steht) |
| P1 | p1-zeitbasis | MONOTONIC nach BOOTTIME über gemessenen Versatz | vorhanden | — | [Zeitbezug](TIMING.md) |
| P1 | p1-semantik | Zeitstempel-Semantik der Kamera klären | offen | — | [OQ-43](open-questions.md#oq-43) |
| P2 | p2-sammeln | Sammelmodus und serielle Auto-Labels | gebaut | — | [Datensatz und Trennung](VALIDATION.md#datensatzaufbau) |
| P2 | p2-ernte | Timing-Kalibrierung, Ernte und Import | gebaut | — | [StreamCam-Kalibrierung und Ernten](VALIDATION.md#2026-09-28-streamcam-timing-kalibrierung-und-erste-zwei-ernten-sc1-sc2) |
| P2 | p2-sperren | Zwei Geräteinstanzen sperren | offen | — | [Gerätekreis und Sperrgeräte](open-questions.md#oq-04) |
| P2 | p2-vielfalt | Mindestens sechs Geräteinstanzen über drei Displaytypen | offen | — | [Datensatzregeln](VALIDATION.md#datensatzaufbau) |
| P3 | p3-leser | Dot-Matrix-Abnahme 3: 215/215 richtige Proben | belegt | 2026-09-30 | [Leser-Abnahme 3](VALIDATION.md#2026-09-30-abnahme-3-ab5ab6-bestanden-215215-0-falsch-0-abgelehnt) |
| P3 | p3-live | Live-Bedienerläufe am begrenzten GSV-2AS-Aufbau | belegt | 2026-10-21 | [Bedienerläufe](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21) |
| P3 | p3-geraete | Weitere Geräte, Vorzeichen und Einheiten prüfen | offen | — | [Gerätekreis](open-questions.md#oq-04) |
| P3 | p3-schwellen | Freigabeschwellen und angepasste Toleranz real belegen | offen | — | [Freigabeevidenz](open-questions.md#oq-14) |
| P3 | p3-fehlerklassen | Trefferquote nach Fehlerklassen aufschlüsseln | offen | — | [Fehlerklassen](VALIDATION.md#fehlerklassen-getrennt-zu-zahlen) |
| P4 | p4-format | UserDefined-Spezifikation für den Prototyp beschaffen | belegt | 2026-10-28 | [Primärquelle und Nachweisgrenzen](GSVMULTI_PROTOCOL.md#quellen), [OQ-01](open-questions.md#oq-01), [OQ-07](open-questions.md#oq-07) |
| P4 | p4-ungueltig | Behandlung ungültiger und veralteter Werte vereinbaren | offen | — | [OQ-06](open-questions.md#oq-06) |
| P4 | p4-anbindung | UserDefined-Formatter, Transport und Live-Lebenszyklus anbinden | offen | — | [Anbindungsnaht](GSVMULTI_PROTOCOL.md#die-naht-im-code), [OQ-47](open-questions.md#oq-47) |
| P4 | p4-nachweis | Annahme, Wert, Einheit und Abbruchverhalten in GSVmulti nachweisen | offen | — | [Abnahmeplan](GSVMULTI_PROTOCOL.md#abnahme) |
| P5 | p5-kalibrierung | StreamCam-Timing-Kalibrierung | vorhanden | — | [Zeitbezug](TIMING.md) |
| P5 | p5-referenz | Live-Referenzauswertung | vorhanden | 2026-10-21 | [Werteplan-Auswertung](VALIDATION.md#messpfad-live-werteplan-2026-10-21) |
| P5 | p5-budget | Unsicherheitsbudget mit getrennten Einzelbeiträgen ausfüllen | offen | — | [Zeitbezug und Messprogramm](TIMING.md) |
| P5 | p5-synchron | Referenzsynchronität klären und belegen | offen | — | [Referenzzeitbasis](open-questions.md#oq-03) |
| P5 | p5-m8 | M8: Zeitachse des UserDefined-Imports prüfen | offen | — | [M8](GSVMULTI_PROTOCOL.md#die-wichtigste-einzelfrage-m8) |
| P6 | p6-live | Live-Pfad mit STALE und Audit | gebaut | 2026-10-21 | [Live-Bedienerläufe](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21) |
| P6 | p6-stoerung | Kurze Störversuche am Aufbau | belegt | 2026-10-21 | [Bedienerläufe und Grenzen](VALIDATION.md#messpfad-live-bedienerlaeufe-2026-10-21) |
| P6 | p6-tracking | Nachführung bei großen Wertwechseln absichern | offen | — | [OQ-26](open-questions.md#oq-26) |
| P6 | p6-audit | Audit-Belege dauerhaft aufbewahren | offen | — | [Aktive Arbeitsliste](../TODO.md) |
| P6 | p6-dauerlauf | 72-h-Dauerlauf mit provozierten Störungen durchführen | offen | — | [Abnahmekriterien](VALIDATION.md#abnahmekriterien) |
| P7 | p7-kriterien | Abnahmekriterien und Gerätekreis vorab festlegen | offen | — | [Abnahmekriterien](VALIDATION.md#abnahmekriterien), [OQ-04](open-questions.md#oq-04) |
| P7 | p7-abnahme | Formale Abnahme auf den Sperrgeräten durchführen | offen | — | [Abnahmekriterien](VALIDATION.md#abnahmekriterien) |
| P7 | p7-protokoll | Abnahmeprotokoll gegen die vereinbarten Kriterien erstellen | offen | — | [Abnahmekriterien](VALIDATION.md#abnahmekriterien) |
| P8 | p8-imx500 | Eigenes Modell und IMX500-Lokalisierung | ruht | 2026-09-25 | [Aktives Hardwareprofil](HARDWARE_PROFILE.md) |
| P8 | p8-vergleich | Gewinn bei CPU-Last oder Latenz gegenüber der Pi-Variante belegen | ruht | — | [Optionaler Meilenstein](#roadmap) |

</div>

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

* **M8 klärt die tatsächlich verwendete GSVmulti-Zeitachse.** Das
  UserDefined-Zahlenprofil hat kein definiertes Aufnahmezeitfeld. Zuerst
  bekannte Sendefolgen, Pausen und gebündelten Empfang gegen gespeicherte
  Werte und Zeitachse prüfen; ein weiteres Zahlenfeld wird nicht automatisch
  zum Zeitstempel. [Versuchsgrenzen](GSVMULTI_PROTOCOL.md#die-wichtigste-einzelfrage-m8).
* **M5 ist mit hoher Wahrscheinlichkeit der dominierende Term**
  (Displayaktualisierung und Haltezeit) und wird von keiner
  Softwareoptimierung kleiner. Früh messen, bevor Aufwand in
  Pipeline-Optimierung fließt.

## Sofort anstoßen, weil rein organisatorisch mit Vorlaufzeit

* [OQ-07](open-questions.md#oq-07) — UserDefined-Empfang in 2.01 Pro bestätigen;
  Spezifikationsbeschaffung seit 2026-10-28 nicht mehr der Blocker
* [OQ-47](open-questions.md#oq-47) — Windows-COM-Transport und Wiederanlauf festlegen
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
