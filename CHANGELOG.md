# Changelog

Neueste Änderung oben. Je Abschnitt: was war das Problem, was wurde geändert,
was ist die Konsequenz.

## 0.1.0.dev0 — 2026-09-09 (noch später)

### Power-Zyklus-Budget überlebt jetzt einen dispread-Neustart korrekt (OQ-22)

**Problem:** `geometry_cycles` lebte nur im Prozessspeicher. Der RP2040
merkt sich Power-Zyklen aber pro **Boot**, nicht pro Prozess (belegt: ein
Test mit je einem frischen Python-Prozess pro Zyklus hing trotzdem nach
~24 Zyklen). Ein Neustart von `dispread` allein — ohne Host-Reboot — hätte
den Zähler faelschlich auf 0 gesetzt und so mehr echte Power-Zyklen erlaubt,
als das Sicherheitsbudget vorsieht. Das Sicherheitsversprechen aus der
vorigen Änderung war damit lückenhaft.

**Änderung:** `geometry_cycles` wird jetzt zusammen mit der aktuellen
Kernel-Boot-ID (`/proc/sys/kernel/random/boot_id`) in
`camera_cycles.json` persistiert (`_load_geometry_cycles`,
`_save_geometry_cycles`, `atomic_json`). Stimmt beim Start die gespeicherte
Boot-ID mit der aktuellen überein, wird der Zähler fortgeführt; bei einem
echten Reboot (andere oder fehlende Boot-ID) beginnt er korrekt bei 0.

**Konsequenz:** Das Sicherheitsbudget haelt jetzt auch ueber
`dispread`-Neustarts hinweg, ohne dass ein Host-Reboot noetig ist, um den
Zaehler zu "umgehen". Zwei neue Tests beweisen beide Faelle:
`test_geometry_cycles_survive_process_restart_same_boot` (gleiche Boot-ID
-> Zaehler bleibt) und `test_geometry_cycles_reset_on_new_boot`
(abweichende Boot-ID -> Zaehler auf 0). 67 Tests und `ruff check src tests
examples` grün.

## 0.1.0.dev0 — 2026-09-09 (spätabends)

### Hartes Power-Zyklus-Budget: RP2040-Sperre kann durch Workbench-Bedienung nicht mehr ausgeloest werden (OQ-22)

**Problem:** Bislang konnte eine Bedienperson im `setup`-Tab beliebig oft
Aufloesung oder Bildrate aendern. Jede echte Aenderung kostet einen
RP2040-Power-Zyklus (bestaetigt: unbind/rebind-Test hat den Regulator
tatsaechlich auf 0 Nutzer fallen lassen). Nach real gemessenen ~20-25
Zyklen antwortet der Chip nicht mehr auf I2C - bislang ohne Vorwarnung,
mitten in einer Sitzung.

**Änderung:** Neue Konstante `MAX_GEOMETRY_CYCLES = 15` (Sicherheitsabstand
unter dem beobachteten Bereich). `Controller.geometry_cycles` zaehlt jeden
tatsaechlichen Stream-Neuaufbau in `_worker`. `_check_geometry_budget()`
verweigert `camera.set`/`camera.set_many`, sobald eine **echte** Aenderung
(nicht das Wiederwaehlen des bereits aktiven Werts) das Budget
ueberschreiten wuerde, mit klarer Fehlermeldung statt eines spaeteren,
unvorhersehbaren Ausfalls. `geometry_cycles`/`geometry_cycles_max` stehen
jetzt in `snapshot()`.

**Konsequenz:** Solange nur ueber die Workbench bedient wird, kann die
RP2040-Sperre **nicht mehr unbeabsichtigt ausgeloest werden** - die
Bedienperson bekommt stattdessen rechtzeitig die Aufforderung, `dispread`
(und danach den Host) neu zu starten, statt dass die Kamera mitten in einer
Messreihe unvorhersehbar haengt. Das behebt den RP2040-Fehler selbst nicht,
verhindert aber zuverlaessig, ueber die eigene Bedienoberflaeche
hineinzulaufen. Neuer Test
`test_geometry_budget_blocks_change_but_allows_same_value` beweist beides:
echte Aenderung wird bei erschoepftem Budget verweigert, Wiederwaehlen des
aktiven Werts bleibt erlaubt. 65 Tests und `ruff check src tests examples`
grün.

## 0.1.0.dev0 — 2026-09-09 (später)

### Aufloesungswechsel kostet jetzt deterministisch einen statt zwei Power-Zyklen (OQ-22)

**Problem:** Der `resolution`-Auswahlzeile in `fields.py` sandte Breite und
Hoehe als zwei getrennte `camera.set`-Befehle. Der zuvor ergaenzte
250-ms-Entprellpfad in `_worker` buendelt das meistens zu einem
Stream-Neuaufbau, ist aber eine Zeitfensterheuristik - kein garantiertes
Verhalten, falls die beiden Befehle mit mehr Abstand ankommen.

**Änderung:** Neuer Controller-Befehl `camera.set_many` setzt mehrere
Kamerafelder in genau einer `_change()`-Revision; die per-Feld-Logik aus
`camera.set` ist dafuer in `_apply_camera_key()` ausgelagert (von beiden
Befehlen geteilt, keine Dopplung). Die Aufloesungszeile in `fields.py`
sendet jetzt einen einzigen `camera.set_many`-Befehl mit Breite und Hoehe
zusammen statt zwei `camera.set`-Befehlen.

**Konsequenz:** Ein Aufloesungswechsel kostet garantiert genau einen
RP2040-Power-Zyklus statt (zeitfensterabhaengig) bis zu zwei - unabhaengig
vom Timing zwischen den beiden Feldern. Neuer Test
`test_camera_set_many_is_one_atomic_revision` beweist das direkt: eine
Revision, beide Felder gesetzt. 64 Tests und `ruff check src tests
examples` grün.

## 0.1.0.dev0 — 2026-09-09

### Kamerathread: Geometrie-Aenderungen buendeln, haengende Kamera-Ioctls sichtbar machen (OQ-22)

**Problem:** Ein Diagnose-Reproducer ohne `dispread`-Code hat gezeigt, dass
der RP2040-Bridge-Chip auf der AI-Camera nach rund 20-25 Power-Zyklen
(`stop`/`configure`/`start`) innerhalb einer Bootsitzung nicht mehr auf I2C
antwortet — danach haengt jeder weitere Kamerazugriff, nur ein Reboot hilft
(Details: [OQ-22](docs/open-questions.md)). `Controller._worker` loeste
bislang bei **jeder** einzelnen Aenderung von Breite, Hoehe oder Bildrate
sofort einen Neuaufbau aus; da die Weboberflaeche Breite und Hoehe als zwei
getrennte Befehle sendet, kostete eine Aufloesungsaenderung im Betrieb zwei
Power-Zyklen statt einem. Zusaetzlich hing der Worker bei einer haengenden
Kamera-Ioctl (`configure`/`start`/`stop`/`capture_request`) fuer immer
schweigend, statt den Fehler als das zu melden, was er ist.

**Änderung:** `_worker` puffert Geometrie-Aenderungen ueber ein kurzes
Zeitfenster (`GEOMETRY_DEBOUNCE_S`, 250 ms) und baut den Stream erst neu auf,
wenn Breite/Hoehe/Bildrate sich nicht mehr aendern — mehrere schnelle
Befehle buendeln sich so zu einem Neuaufbau statt mehrerer. Die riskanten
Kameraaufrufe (`stop`, `configure`, `start`, `capture_request`) laufen jetzt
ueber `_guarded()`: ein Wachhund-Thread mit `CAMERA_OP_TIMEOUT_S` (6 s).
Kehrt der Aufruf nicht zurueck, wird das als `CameraWedgedError` gemeldet
("Kamera reagiert nicht (...); vermutlich RP2040-Sperre (OQ-22), Reboot
noetig") statt als endloser Timeout; die anschliessende Aufraeumroutine
verzichtet dann bewusst auf einen weiteren `stop()`/`close()` auf demselben,
bereits blockierten Kameraobjekt.

**Konsequenz:** Reine Belichtungs-/Verstaerkungs-/Kontraständerungen waren
bereits vorher `set_controls()`-only und bleiben unveraendert kostenlos.
Aufloesungs-/Bildratenaenderungen kosten jetzt hoechstens einen Power-Zyklus
statt zwei. Eine echte RP2040-Sperre wird jetzt innerhalb von rund
`CAMERA_OP_TIMEOUT_S` als klarer Fehlerzustand sichtbar (`snapshot()["error"]`)
statt als unbestimmt haengender Kamerathread — behebt die Sperre selbst
nicht, macht sie aber sofort erkennbar. 63 Tests und `ruff check src tests
examples` weiterhin grün; die bestehenden Workbench-Tests laufen alle mit
`simulate=True` und durchlaufen den neuen Entprell-/Wachhundpfad nicht — ein
gezielter Test dafür fehlt noch.

## 0.1.0.dev0 — 2026-09-08

### Zahlenerkennung an der Kamera angeschlossen (Zwischenstand, Bedienung fehlt)

**Problem:** Die Verarbeitungskette aus Konzept §3 war fertig, lief aber nur
gegen synthetische Bilder. Die Workbench besaß Kamera und bestätigte ROI, hat
daraus aber nie einen Wert gelesen — und im Profil fehlte das Zahlenformat, das
der Segmentleser laut Konzept §4 braucht.

**Änderung:** Das Workbench-Profil führt einen `layout`-Block (`digits`,
`decimals`, `has_sign`, `unit` plus Rasterverhältnisse) mit eigener Prüfung in
`profiles.validate_layout` — unmögliche Formate wie „mehr Nachkommastellen als
Stellen" werden abgelehnt. Der Controller entzerrt bei bestätigter ROI jedes
Bild über `rectify` auf feste 400×160, liest es mit `SevenSegmentReader` und
führt die Freigabeprüfung `ReleaseGate` **als Anzeige** mit. Ergebnis, Evidenz
je Stelle, Ablehnungsgründe und Qualität des Ausschnitts stehen in `snapshot()["reading"]`.
Die Abtastpunkte der sieben Segmente werden ins Kamerabild zurückgezeichnet,
hell wenn gemessen aktiv — damit sieht der Bediener, ob das Raster sitzt. Neuer
Befehl `layout.set`.

**Konsequenz:** Aus einem scharfen Kamerabild entsteht ein gelesener Wert samt
Begründung, warum er freigegeben würde oder nicht. **Kein** `ValueRecord`, keine
Freigabe, keine serielle Ausgabe — `released` ist konstant `false`, und die
Zeitangabe der Vorschau-Veralterung ist CLOCK_MONOTONIC und ausdrücklich kein
Messwertzeitbezug. Die Einheit stammt weiter aus dem Profil
(`unit_source=profile`), sie wird nicht gelesen.

**Was noch fehlt:** Die Bedienzeilen in `fields.py` (Zahlenformat als
Auswahlfelder, Ablesung und Ablehnungsgründe als Anzeigezeilen) und die Tests
für den Lesepfad. Der Kern ist gegen einen synthetisch gerenderten Wert geprüft:
gezeichnet `-12.34`, gelesen `-012.34`, Wert −12,34, Freigabeprüfung `valid`
ohne Ablehnungsgründe. Bis das UI steht, ist das Zahlenformat nur über
`layout.set` oder die Profildatei erreichbar. 63 Tests und Ruff grün — die
Tests deckten diesen Pfad noch **nicht** ab.

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
