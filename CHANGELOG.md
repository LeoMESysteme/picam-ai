# Changelog

Neueste Änderung oben. Je Abschnitt: was war das Problem, was wurde geändert,
was ist die Konsequenz.

## 0.1.0.dev0 — 2026-09-08

### Einstelltabelle in der Weboberfläche, Werte werden ausgewählt statt getippt

**Problem:** Die Einrichtung lag nur in `dispread tui`, das der Bediener erst in
der Web-Shell von Hand starten musste. Dort war jedes Feld ein Freitextdialog
mit `json.loads`: `true`/`false` für Belichtungsautomatik und Fokusassistenz,
Zahlen für die Belichtung, aber `mode` und `role` ohne Anführungszeichen. Typ,
Grenzen und Default lagen in den Kamera-Capabilities längst maschinenlesbar vor.

**Änderung:** Neues Modul `workbench/fields.py` beschreibt Zeilen und Aktionen
einmal als Daten (`rows()`, `actions()`, `run_blocked()`); `/status` liefert sie
mit, die Weboberfläche rendert daraus einen festen `setup`-Tab neben den Shells,
der nach der Anmeldung sofort aktiv ist. Auswahlfelder für Modus, Rolle,
Auflösung, Bildrate, Belichtungsautomatik, Fokusassistenz und Profil;
Zahlenfelder mit Kameragrenzen und Schnellwahl für Belichtungszeit, Verstärkung
und Kontrast; Anzeigebereich und Erkennungsfilter als reine Anzeigezeilen.
Gesperrte Zeilen und Aktionen nennen ihren Grund, statt erst am Kommando zu
scheitern. `dispread tui` bleibt für den Betrieb ohne Browser und rendert
dieselbe Quelle mit Auswahllisten statt Freitext. `snapshot()` führt die
vorhandenen Profilnamen mit; Freitext bleibt nur für einen neuen Profilnamen.

**Konsequenz:** Einrichtung ohne zusätzliches Kommando und ohne JSON-Kenntnis;
Web und Terminal können nicht mehr auseinanderlaufen, weil beide dieselben
Optionen lesen. Der Controller bleibt die durchsetzende Instanz — `fields.py`
ist Bedienhilfe, keine Regel. Keine OCR, Messwertfreigabe oder neue
Abhängigkeit. 63 Tests und Ruff grün, darunter der Nachweis, dass jede
angebotene Auswahl vom Controller angenommen wird. setup-Tab mit 21 Prüfpunkten
in Chromium über eine `file://`-Seite mit echter `/status`-Antwort geprüft;
Netzwerknavigation dieses Chromium bleibt defekt (OQ-21). Keine erneute
Hardwaremessung.

### Authentifizierte Kamera-Workbench mit Shell, TUI und Profilen

**Problem:** Der Ein-Datei-Prototyp bot weder echte Shells noch eine gemeinsame
Steuerung für Kameraeinstellungen, gespeicherte Profile und Boxkorrekturen.

**Änderung:** `dispread serve` startet eine HTTPS-Workbench mit Linux-PAM-
Anmeldung für `me-systeme`, echten PTY-Shell-Tabs und lokaler Unix-Socket-API.
`dispread tui` bietet eine tastaturbediente Einstelltabelle. Ein Kamerathread
verwaltet validierte Live-Controls, automatische Einstellvorschläge,
Fokusassistenz, Profilkonflikte und eingefrorene Bilder für ROI/Annotationen.
Der bisherige Beispielaufruf bleibt als Einstieg erhalten. Systemabhängigkeiten
und lokal ausgelieferte xterm-Assets sind dokumentiert.

**Konsequenz:** Einheitliche Steuerung ohne Sliderwand; Browsertrennung beendet
keine Shell. Noch keine OCR, Messwertfreigabe oder Modelltraining. 58 Tests
einschließlich TLS/WebSocket/Shell/TUI grün; realer Kameradienst geprüft.
Chromium-UI mit simuliertem Transport geprüft. Vollständige HTTPS-Browserabnahme
bleibt wegen lokaler Chromium-Navigationsprobleme offen (OQ-21); ebenso
gerätespezifische Auto-Setup-Validierung (OQ-20).

### Barebones-Terminalansicht für die Kameravorschau

**Problem:** Die Vorschauseite enthielt erklärenden Fließtext und kein
eigenes Logfenster.

**Änderung:** Dunkle Monospace-Oberfläche mit Kamera- und Logfenster,
kompaktem Live-Status, Bildnummer und Verarbeitungsrate. Auf schmalen
Bildschirmen stehen die Fenster untereinander. Erklärungen, Verbindungswechsel,
Kamerafehler und periodische Statusmeldungen erscheinen im Browserlog mit
UTC-Zeitangabe. Maximal 300 Zeilen, `clear`, automatisches Scrollen nur am Ende.

**Konsequenz:** Weniger Text außerhalb des Logs. Das Log enthält
Vorschaudiagnostik, keine Shell und keine vollständige Prozess-stdout-Umleitung.
Neun Vorschautests und Ruff grün; Terminalansicht mit simuliertem Feed in
Chromium geprüft. Keine erneute Hardwaremessung.

### Kameralivebild mit Display-Kandidaten über SSH

**Problem:** Für den ersten Versuch fehlte eine Livevorschau auf dem
Windows-Rechner und eine automatische Suche nach möglichen Anzeigebereichen.

**Änderung:** `examples/17_camera_display_preview.py` verbindet Picamera2,
OpenCV-Konturfilter, gelbe Kandidatenboxen und einen lokalen MJPEG-HTTP-Server.
Windows greift über SSH-Portweiterleitung im Browser zu. Nur das neueste Bild
wird vorgehalten; die Seite blendet bei ausbleibendem Bildfortschritt oder
Verbindungsabbruch das Bild aus. Filter sind per Argument einstellbar.

**Konsequenz:** Vorschau ohne zusätzliche Abhängigkeiten; keine OCR oder
Messwertfreigabe. Neun neue Tests prüfen Erkennung, HTTP und Fehlerbehandlung.
Realer Kamerastream lokal geprüft, Windows/SSH und Erkennungsqualität am
Gerät noch offen. Anleitung: `docs/anleitung/10-kamera-livevorschau.md`.

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
