# Changelog

Neueste Änderung oben. Je Abschnitt: was war das Problem, was wurde geändert,
was ist die Konsequenz.

## 0.1.0.dev0 — 2026-09-08

### Kamera in Betrieb genommen und vermessen

**Problem:** Die AI Camera war an CAM/DISP0 angeschlossen, wurde aber nicht
erkannt. `rpicam-hello --list-cameras` meldete `No cameras available!`.

**Änderung:** `scripts/camera-commissioning.sh` prüft die gesamte Kette rein
lesend durch und nennt am Ende die nächste Maßnahme. Ursache war der fehlende
Reboot — `camera_auto_detect` prüft die Anschlüsse ausschließlich beim Booten,
und die Kamera war nach dem letzten Boot angesteckt worden.

**Konsequenz:** Kamera läuft. Zwei Falschmeldungen im Skript beseitigt:
`dtoverlay -l` ist kein Kriterium (firmwareseitig angewandte Overlays
erscheinen dort nicht), und die CAM-I2C-Busnummern sind nicht stabil (hier 6
und 10). Nachweis ist der Sensorknoten im Device-Tree plus die
libcamera-Enumeration. Gemessen: 6,8 s `.rpk`-Warmlauf, 15,0 Inferenzen/s,
`SensorTimestamp` in CLOCK_BOOTTIME — siehe `docs/TIMING.md`.

### Verarbeitungskette aus Konzept §3 aufgebaut

**Problem:** Das Repo enthielt nur das Konzept, keinen Code. Zugleich sind
zentrale Anforderungen offen — das GSVmulti-Telegramm ist unbekannt, es gibt
keinen Datensatz echter Geräte.

**Änderung:** Alle Trennstellen als `Protocol` definiert, mit `frozen`
Datenklassen als Vertrag: `FrameSource`, `DisplayLocator`, `ValueReader`,
`ReleaseGate`, `ValueSink`, `TelegramFormatter`. Implementiert sind
`synthetic://` als Bildquelle, `manual_roi` als Lokalisierung, die
Vierpunkt-Entzerrung, der 7-Segment-Leser mit Per-Segment-Evidenz, die
Freigabelogik, das JSONL-Audit-Log und die serielle Ausgabe mit provisorischem
ASCII-CSV.

**Konsequenz:** Die Kette läuft Ende zu Ende ohne Hardware
(`examples/16_end_to_end_headless.py`, 40/40 korrekt, 40 Telegramme auf der
Leitung). Das echte GSVmulti-Format ist später ein neuer Formatter, keine
Änderung an der Pipeline.

### Bestätigte manuelle ROI als Primärpfad statt IMX500-Detektion

**Problem:** Naheliegend wäre, die Anzeige mit einem der 23 mitgelieferten
IMX500-Modelle zu finden.

**Änderung:** Priorität umgekehrt. Gemessen liefert `network_intrinsics`
COCO-Labels (`person`, `bicycle`, `tv`) — für Messverstärker-Displays
unbrauchbar. Eigene Modelle sind auf diesem Pi nicht konvertierbar, nur der
Packager ist vorhanden.

**Konsequenz:** Werterkennung, Freigabelogik und Ausgabekette konnten sofort
gebaut und gemessen werden. Konzept §10 Ph. 2 nennt den manuellen Ausschnitt
selbst als Rückfalloption. Die Detektion bleibt austauschbar.

### Segmentschwelle aus den Segmentmessungen statt aus dem Bild

**Problem:** Zwei Fehlversuche. Eine Schwelle pro Ziffernzelle verwarf jede
`8` (bei sieben aktiven Segmenten ist der zellinterne Kontrast null). Otsu über
alle Bildpunkte erkannte den Überlauf nicht — eine 7-Segment-Anzeige hat drei
Helligkeitsstufen, und die inaktiven Segmente sind die häufigste.

**Änderung:** Die Schwelle kommt aus den gepoolten Segmentmessungen aller
Stellen.

**Konsequenz:** `8` wird gelesen, Überlauf erkannt, starke Unschärfe führt
nicht mehr zur Ablehnung aller Frames. Bekannte Grenze: zeigt die Anzeige
ausschließlich `8`, wird abgelehnt (OQ-13) — nach Konzept §7 die zulässige
Richtung.

### Invarianten aus Konzept §7 im Code verankert

**Änderung:** Der `ValueRecord`-Konstruktor verweigert einen `STALE`- oder
`UNREADABLE`-Datensatz mit Zahlenwert und eine Ablehnung ohne Begründung.
`ValueReader.read` und `ReleaseGate.evaluate` bekommen den Referenzwert
strukturell nicht als Parameter. Vorzeichen, Dezimalpunkt und Einheit sind
eigenständige Ablehnungskriterien; `sign_region_readable` ist getrennt von
`sign_detected`.

**Konsequenz:** Alle drei „stillen" Fehlermodi aus §7 haben einen Test, der
fehlschlägt, wenn das System sie zeigt — inklusive des Nachweises, dass ein um
20 % verfälschter Referenzwert identische Datensätze erzeugt.

### Zeitbasis als Pflichtfeld

**Problem:** Beim Entwickeln ohne Kamera entstehen Zeitstempel, die keine
Zeitaussage tragen. Der naheliegende Fehler wäre, sie später als reale
Latenzen zu berichten.

**Änderung:** `TimeBaseKind` ist Pflichtfeld in `Frame` und `ValueRecord`, mit
`carries_time_information`. Adapterzustand liegt in einem separaten
`TxReceipt`; der Adapter darf `capture_timestamp` nie verändern.

**Konsequenz:** `report.json` weist `timing_is_meaningful` maschinenlesbar aus.

### Dokumentation als Projektbestandteil

**Änderung:** `docs/status.md` (Momentaufnahme), `project_history.md`
(Entscheidungen), `open-questions.md` (OQ-01 bis OQ-19), `lab_journal.md`
(Experimente inklusive Fehlversuche), `TIMING.md`, `VALIDATION.md`,
`ROADMAP.md`, `HARDWARE_PROFILE.md`, `CAMERA_COMMISSIONING.md`,
`OPTICAL_SETUP.md`, `GSVMULTI_PROTOCOL.md`, `dependencies.md`. Die
Aktualisierungspflicht steht in `AGENTS.md`.

**Konsequenz:** `pyproject.toml` deklarierte zwei Konsolenskripte auf nicht
vorhandene Module — entfernt, weil ein Einsprungpunkt auf ein fehlendes Modul
erst zur Laufzeit scheitert. `CLAUDE.md` markiert je Komponente, was fertig ist.
