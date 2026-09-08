# Status — Stand 2026-09-08

Wird **überschrieben**, nicht angehängt. Erste Datei, die eine neue Session
liest. Verlauf: [project_history.md](project_history.md),
[lab_journal.md](lab_journal.md).

## Sofort zu wissen

**1. Nichts ist committet.** Die gesamte Workbench, die Zahlenerkennung, die
Tests und alle Doku-Änderungen liegen als Arbeitsbaumstand vor, teils im Index.
In dieser Session lagen sie zwischenzeitlich in einem `git stash` und wurden mit
`git stash pop` zurückgeholt. Vor allem anderen: prüfen, ob der Stand vollständig
ist, und committen.

**2. Die Kamera kann jederzeit blockieren; dann hilft nur ein Reboot.** Der
Kernel benennt es selbst als Treiberfehler: `videobuf2_common: driver bug:
stop_streaming operation is leaving buffer 0 in active state` aus
`cfe_stop_streaming [rp1_cfe]`. Jeder Streamabbau kann die Pufferwarteschlange
defekt hinterlassen; danach scheitert jeder Start — als `stream on failed in
subdev`, als `Failed to queue buffer N: Invalid argument`, zuletzt hängt schon
`Picamera2(0)`. Widerlegt sind: PipeWire-Kamerakonkurrenz (libcamera-Monitor in
WirePlumber abgeschaltet, Fehler bleibt) und ein hängender Prozess (Töten gibt
die Kamera nicht frei). Die Hypothese „nur die großen Sensormodi lösen es aus"
ist zu eng: bei 960×720 liefen mehrere Sitzungen, dann trat es wieder auf. Es
ist ein Wettlauf beim Abbau, für den **keine sichere Konfiguration bekannt**
ist. `scripts/camera-commissioning.sh` meldet trotzdem „einsatzbereit", weil es
den Bilddurchlauf nicht prüft. Stand, Datenpunkte und was die Workbench dagegen
tun sollte: [OQ-22](open-questions.md).

**3. Der Fokus ist erledigt.** Die AI Camera hat **keine Fokus-Controls** (kein
`AfMode`, kein `LensPosition`) — es gibt keinen Autofokus und keine
Softwareverstellung, nur das mechanische Objektiv, Herstellerbereich etwa 20 cm
bis ∞. Die Unschärfe war belegbar Defokussierung und keine Bewegungsunschärfe:
Lichtreflexe im Bild waren runde Scheiben mit Achsverhältnis 1,20. Nach dem
Drehen am Objektiv mit `~/fokusmesser.py` steht die Schärfe bei **216,6**
(Ausgangslage 11,53), und die Anzeige eines BK Precision 5491B ist lesbar:
Ziffernhöhe **≈ 37 px**, Kontrast 0,749, **kein Glanz im Display** (0,0000).
Damit erreicht **960×720 die 30-px-Marke ohne `ScalerCrop`** — eine frühere
Schätzung von nur 24 px galt für 10 mm Ziffern bei 30 cm und trifft dieses Gerät
nicht. Zahlen: [VALIDATION.md](VALIDATION.md), Bild
`var/workbench/diagnostics/fokus-erreicht-960x720.jpg`.

Zwei mechanische Aufgaben bleiben, sonst ist die Einstellung beim nächsten
Anstoßen verloren: Objektiv gegen Verdrehen sichern und die Halterung starr
ausführen ([OPTICAL_SETUP.md](OPTICAL_SETUP.md)).

## Aktueller Stand

**P0 (Grundgerüst) erreicht, P1 (Kamera) teilweise.** Die Verarbeitungskette
aus Konzept §3 läuft Ende zu Ende ohne Hardware; die Kamera ist in Betrieb
genommen, vermessen und scharf gestellt. Was noch fehlt, steht unter P0 in
[ROADMAP.md](ROADMAP.md) — insbesondere fünf der sechs Bildquellen, das
Tesseract-Backend und die vollständige Messpipeline-CLI. Die Workbench trägt
Vorschau, Einrichtung im `setup`-Tab und seit dieser Session den Anschluss der
Zahlenerkennung an das Kamerabild.

## Angefangen und nicht fertig — Zahlenerkennung in der Workbench

**Fertig und geprüft:** Das Profil führt einen `layout`-Block (`digits`,
`decimals`, `has_sign`, `unit`, Rasterverhältnisse) mit eigener Prüfung in
`profiles.validate_layout`. Der Controller entzerrt bei bestätigter ROI jedes
Bild auf feste 400×160, liest es mit `SevenSegmentReader`, führt `ReleaseGate`
als **Anzeige** mit und legt Ergebnis, Evidenz je Stelle, Ablehnungsgründe und
Ausschnittqualität in `snapshot()["reading"]` ab. Die sieben Abtastpunkte je
Stelle werden ins Kamerabild zurückgezeichnet, hell wenn gemessen aktiv — so
sieht der Bediener, ob das Raster sitzt. Neuer Befehl `layout.set`. Gegen einen
synthetisch gerenderten Wert geprüft: gezeichnet `-12.34`, gelesen `-012.34`,
Wert −12,34, Freigabeprüfung `valid` ohne Ablehnungsgründe.

**Es entsteht ausdrücklich kein Messwert:** kein `ValueRecord`, keine Freigabe,
keine serielle Ausgabe, `released` konstant `false`. Die Veralterung der
Vorschau nutzt CLOCK_MONOTONIC und ist **kein** Messwertzeitbezug. Die Einheit
kommt aus dem Profil (`unit_source=profile`), sie wird nicht gelesen.

**Nächste Schritte, genau hier weitermachen:**

1. `src/dispread/workbench/fields.py`: Zeilen für das Zahlenformat als
   Auswahlfelder (`digits` 3–8, `decimals` 0–4 oder unbestimmt, Vorzeichenstelle
   ja/nein, Einheit aus einer kurzen Liste, `sign_cell_ratio` als Zahlenfeld)
   und Anzeigezeilen für Ablesung, Freigabeprüfung und Evidenz. Ohne diese
   Zeilen ist das Zahlenformat nur über die Profildatei oder `layout.set`
   erreichbar.
2. `tests/test_workbench.py`: Lesepfad testen — synthetisch gerenderte Anzeige
   über `render_display` durch `Controller.publish` schicken und den gelesenen
   Wert prüfen; dazu Layout-Validierung und die Ablehnung bei unmöglichem
   Format. Der bestehende Test „jede angebotene Auswahl wird akzeptiert" deckt
   die neuen Layoutzeilen automatisch mit ab, sobald sie existieren.
3. Am echten Gerät abnehmen: ROI auf die fünf Stellen des 5491B legen,
   Zahlenformat bestätigen und sehen, was der Leser aus `-000.13mV DC` macht.
   Das ist der erste echte Erkennungsdatenpunkt überhaupt
   ([OQ-04](open-questions.md)).

## In dieser Session ebenfalls — Einstelltabelle in der Weboberfläche

**Implementiert:** Die Einrichtung braucht kein zusätzliches Kommando mehr. Die
Shell-Leiste hat einen festen ersten Tab `setup`, der nach der Anmeldung sofort
aktiv ist und die Einstelltabelle im gleichen Terminalstil zeigt. Zeilen,
Optionen und Aktionen kommen aus dem neuen Modul
[`src/dispread/workbench/fields.py`](../src/dispread/workbench/fields.py)
(`rows()`, `actions()`, `run_blocked()`), das `/status` mitliefert; `dispread tui`
rendert dieselbe Quelle. Damit können Web und Terminal nicht auseinanderlaufen.

Werte mit endlicher Auswahl sind Auswahlfelder — Modus, Rolle, Auflösung,
Bildrate, Belichtungsautomatik, Fokusassistenz, Profil. Belichtungszeit,
Verstärkung und Kontrast sind Zahlenfelder mit den Grenzen der laufenden Kamera
und einer Schnellwahl aus Minimum, Kameradefault, Istwert und Maximum.
`true`/`false` oder JSON tippt niemand mehr; Freitext bleibt nur für einen neuen
Profilnamen. Gesperrte Zeilen und Aktionen nennen ihren Grund (etwa „feste
Belichtung noetig: AeEnable auf false" an der Option `run`), statt erst am
Kommando zu scheitern. Der Controller bleibt die durchsetzende Instanz;
`fields.py` ist Bedienhilfe und ersetzt keine Regel. `snapshot()` führt jetzt die
vorhandenen Profilnamen mit. Keine OCR, keine Messwertfreigabe, keine neue
Abhängigkeit.

**Verifiziert:** 63 Tests und `ruff check src tests examples` grün. Neu darunter:
jede angebotene Auswahl und jede Schnellwahl wird vom Controller angenommen,
Sperrlogik der manuellen Belichtung, Aktionsfreigaben, Profilliste ohne
ungültige Dateinamen, `setup` in der `/status`-Antwort über TLS und die
Auswahllisten der TUI. Die TUI wurde zusätzlich headless gegen den echten
Unix-Socket eines laufenden `serve --simulate` bedient (Auflösung 960×720 →
1280×960, Belichtungsautomatik aus, Schnellwahl übernommen).

**Browserprüfung:** Der setup-Tab wurde in Chromium mit 21 Prüfpunkten geprüft —
Rendering aller zwölf Zeilen, gesperrte `run`-Option mit Grund, Auswahl sendet
das Kommando, Auflösung sendet zwei Kommandos, Grenzverletzung wird abgelehnt,
Aktionsleiste, Tastenkürzel, Zeilennavigation, Namensabfrage und die Zusicherung,
dass der 500-ms-Poll ein offenes Auswahlfeld nicht überschreibt. Weil dieses
Chromium keine Netzwerkseite lädt, lief die Prüfung über eine `file://`-Seite mit
eingespielter echter `/status`-Antwort; TLS, Anmeldung und WebSocket sind damit
**nicht** abgenommen. OQ-21 ist dazu präzisiert: der Fehler betrifft auch reines
HTTP, ist also kein TLS-Problem.

**Nächster Schritt:** Zertifikat auf Windows vertrauen,
`./.venv/bin/dispread serve` starten, `https://100.122.154.35:8080` öffnen, mit
dem normalen SSH-/Linux-Passwort anmelden — der setup-Tab steht direkt bereit.
Danach ROI im Kamerabild bestätigen, Belichtung fest einstellen und Profil
speichern. Details: [Workbench-Anleitung](anleitung/10-kamera-livevorschau.md).
Kein dauerhafter Workbench-Prozess aus dieser Session läuft weiter.

## Vorherige Session am 2026-09-08 — Kamera-Workbench

**Implementiert:** Modulare Workbench unter `src/dispread/workbench` statt
weiter wachsendem Beispielskript. `dispread serve` startet HTTPS und Kamera;
`dispread tui` eine tastaturbediente Einstelltabelle innerhalb einer echten
Shell (inzwischen zusätzlich als `setup`-Tab in der Weboberfläche). Ganze Weboberfläche mit Linux-PAM für `me-systeme` geschützt. Bis zu
acht PTY-Shell-Tabs, Browsertrennung/Logout beendet keine Shell, explizites
Schließen und Serverende räumen auf. xterm.js wird lokal ausgeliefert.

Ein Kamerabesitzer verwaltet Controls, Ist-Metadaten, Fokusassistenz,
bestätigte ROI, begrenzte automatische Belichtungs-/Gain-Vorschläge und
JSON-Profile. Externe Änderungen werden validiert und bei lokalen Änderungen
als Konflikt angezeigt. Boxkorrekturen beziehen sich auf eingefrorene Bilder;
`annotate` speichert Originalbild und zugehörige Daten. Keine OCR,
Messwertfreigabe oder Modelltraining ergänzt. Der Modus `run` bedeutet in
dieser Workbench feste Vorschaukonfiguration.

**Installation erledigt:** Debian-Pakete aiohttp 3.11.16, Textual 2.1.2 und
python3-pam verfügbar; Projekt mit `--no-deps --no-build-isolation -e .`
installiert. `dispread`-Einstieg verfügbar. Lokales Zertifikat und privater
Schlüssel unter `var/workbench/tls/` erzeugt; nicht versioniert. Fingerabdruck:
`AE:A1:3D:84:9E:0F:9C:91:97:44:1A:DA:DA:EC:AA:E4:58:91:AD:5E:22:D1:76:4E:5E:18:5A:07:9B:24:3D:B7`.

**Verifiziert:** 58 Tests grün, Ruff und Diff-Whitespace-Prüfung grün.
Tests umfassen TLS-Login mit Testauthentifizierung, CSRF/Origin-Schutz,
WSS-Shell, Wiederverbindung/Logout, TUI-Tastaturbedienung, Profile/Dateikonflikte,
Annotation-Bildzuordnung, Request-Freigabe und Abbruch der Einstellhilfe.
Echter Kamera-Worker: Bild 25, 14,8 verarbeitete Bilder/s, kein Fehler,
Thread beendet (2026-09-08T12:03:21.753165+00:00 UTC). Artefakte:
`var/workbench/diagnostics/camera-smoke.json` und `camera-smoke.jpg`.
Aufbau und Messzahlen in Laborjournal/VALIDATION. Keine physischen Einstellungen
oder Bootkonfiguration verändert.

**Browserprüfung:** Separater Chromium-Test mit lokal simuliertem Transport
bestätigt Bildanzeige, Terminaldarstellung und Einfrieren; Screenshot
`/tmp/workbench-ui.png`, DOM-Prüfung `terminal/live/freeze = true`.
Vollständiger lokaler HTTPS-Chromium-Test hängt dagegen schon beim Laden der
Loginseite; Python/curl und TLS/WSS-Integrationstests laden korrekt. Ursache
und Windows-Gesamtabnahme stehen als OQ-21 offen. Keine erfolgreiche Anmeldung
mit dem echten Benutzerpasswort behauptet; kein Testpasswort-Modus im Produkt.
Gerätespezifische Auto-Setup-Validierung bleibt OQ-20.

## Frühere Session am 2026-09-08 — Kameraprototyp

**Kameralivevorschau mit automatischen Display-Vorschlägen implementiert.**
`examples/17_camera_display_preview.py` öffnet Picamera2 (960×720, 15 Bilder/s
angefordert), sucht rechteckige Kandidaten mit OpenCV und liefert gelbe Boxen
als MJPEG über einen HTTP-Server ausschließlich auf Loopback. Windows-Zugriff
über SSH-Portweiterleitung. Keine neue Abhängigkeit, keine OCR oder
Messwertfreigabe, keine Änderung der bestehenden Messwertpipeline.

Die Browserseite blendet bei fehlendem Bildfortschritt/Verbindungsabbruch das
Bild aus. Neuester JPEG-Puffer statt wachsender Warteschlange; Capture-Timeouts
brechen ausstehende Kamerajobs vor dem Schließen ab. Filter sind per Argument
konfigurierbar. Startanleitung:
[anleitung/10-kamera-livevorschau.md](anleitung/10-kamera-livevorschau.md).

**Verifiziert:** 45 Tests grün (davon neun neue Vorschautests), `ruff check src
tests examples` und `git diff --check` grün. HTTP-Tests benötigen außerhalb
der Sandbox Zugriff auf lokale TCP-Sockets.

**Reale Kamera kurz geprüft:** Start des Harness
2026-09-08T10:31:59.111530+00:00 (UTC), JPEG über lokalen HTTP-Port 18080,
Schlussstatus Bild 50 und 15,0 verarbeitete Bilder/s (CLOCK_MONOTONIC),
SIGTERM beendet mit Exit 0. Diagnoseartefakte unter
`var/examples/17_camera_display_preview/`: `diagnostic.json`, `camera.log`,
`preview.jpg`. Zahlen und Aufbau in VALIDATION und Laborjournal ergänzt.
Keine Bootkonfiguration oder physische Kameraeinstellung verändert.

**Noch offen:** Das Diagnosebild zeigt eine teilweise unscharfe,
kopfstehende Arbeitsplatzszene ohne geeignete Geräteanzeige. Ein echtes
7-Segment-Gerät muss frontal positioniert und fokussiert werden. Kandidaten
am Gerät und Windows-Browser/SSH sind noch nicht manuell abgenommen. Keine
Aussage über Erkennungsquote oder Kamera-zu-Browser-Latenz.

Zuvor in dieser Unterhaltung: Projekt und Runablauf erklärt; bestehende
AGENTS.md gemäß vorherigem Auftrag nicht verändert. Die bereits vorhandenen
lokalen Nutzerskripte `takepic.py` und `test_run.py` wurden nicht verändert.

## Vorherige Arbeiten am 2026-09-08 (zweite Session)

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

## Verifiziert in der vorherigen Session am 2026-09-08

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
* **Kein definierter optischer Aufbau.** Der Fokus ist am 2026-09-08 eingestellt
  (Schärfe 216,6, Ziffernhöhe ≈ 37 px), aber Objektiv und Halterung sind nicht
  gesichert — ein Anstoßen macht die Einstellung zunichte
  ([OPTICAL_SETUP.md](OPTICAL_SETUP.md)).
* **Kamera blockiert sporadisch bis zum Reboot** — Treiberfehler in `rp1_cfe`
  beim Streamabbau, keine sichere Konfiguration bekannt
  ([OQ-22](open-questions.md)). Für ein Kalibrierlabor ein Ausfallrisiko
  mitten in der Messung.
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

1. **Den Arbeitsstand committen.** Nichts von der Workbench, der
   Zahlenerkennung oder der Doku ist in einem Commit; in dieser Session lag
   alles zwischenzeitlich in einem `git stash`.
2. **Zahlenerkennung fertigstellen** — die drei Punkte unter „Angefangen und
   nicht fertig", dann am 5491B abnehmen. Das liefert den ersten echten
   Erkennungsdatenpunkt und damit den Einstieg in
   [OQ-04](open-questions.md).
3. **Optik mechanisch sichern und erste echte Aufnahmen sammeln**, dann
   `replay://` implementieren — ab da ist die Kette gegen reales Material
   regressionsfähig. Ablauf und Fallen:
   [anleitung/06-kamera-aufnahme-replay.md](anleitung/06-kamera-aufnahme-replay.md).
   Weiter offen und ohne Vorlauf anstoßbar: fehlende Pakete per `sudo apt
   install -y tesseract-ocr tesseract-ocr-eng socat chrony`
   ([OQ-15](open-questions.md)) sowie OQ-07 und OQ-09 organisatorisch.

## Wichtigster offener Messpunkt

**M8** ([TIMING.md](TIMING.md)): Verwendet GSVmulti einen übermittelten
Aufnahmezeitstempel, oder nur die Empfangszeit? Kostet nach Vorliegen der
Spezifikation eine halbe Stunde und entscheidet die Integrationsstrategie.
Ein schnellerer Leser behebt weder die unbekannte Displayverzögerung (M5) noch
eine fehlende Zeitzuordnung.
