# Status — Stand 2026-09-08

Wird **überschrieben**, nicht angehängt. Erste Datei, die eine neue Session
liest. Verlauf: [project_history.md](project_history.md),
[lab_journal.md](lab_journal.md).

## Sofort zu wissen — Kamera streamt nicht, Reboot nötig

Seit 2026-09-08 15:20:32 Ortszeit setzt der Sensor **keinen Stream mehr auf**.
Jeder Startversuch endet im Kernel mit `rp1-cfe 1f00110000.csi: stream on failed
in subdev`; auch `rpicam-still` liefert kein Bild. Die Enumeration bleibt
intakt, `scripts/camera-commissioning.sh` meldet trotzdem „einsatzbereit" —
diese Diagnose prüft den Bilddurchlauf nicht. **Erst rebooten, dann messen.**
**Es ist ein Treiberfehler**, vom Kernel wörtlich so benannt:
`videobuf2_common: driver bug: stop_streaming operation is leaving buffer 0 in
active state` aus `cfe_stop_streaming [rp1_cfe]`. Jeder Streamabbau kann die
Warteschlange defekt hinterlassen; danach scheitert jeder Start, zuletzt hängt
schon `Picamera2(0)`. Zwei Verdächtige sind widerlegt: PipeWire-Kamerakonkurrenz
(Monitor abgeschaltet, Fehler bleibt) und ein hängender Prozess (Töten gibt die
Kamera nicht frei). **Beste offene Hypothese: die Streamgröße** — drei Sitzungen
bei 960×720 überlebten, jede Sitzung mit 2028×1520 oder 4056×3040 war die letzte
des Boots. Sechs Datenpunkte, nächster Test und die Konsequenz `ScalerCrop`
statt größerer Stream: [OQ-22](open-questions.md). Belege im
[Laborjournal](lab_journal.md).

**Der Fokus ist geklärt (2026-09-08):** Die Lichtreflexe im Vollbild sind runde
Scheiben von 29–50 px Durchmesser bei einem Achsverhältnis von 1,20 — rund, nicht
gestreckt. Damit ist es **Defokussierung**, nicht Bewegungsunschärfe; die
Belichtungszeit ist unschuldig. Es muss mechanisch am Objektiv gedreht werden.
Der Fokusmesser `~/fokusmesser.py` hat das bestätigt: **Bestwert 75,0 gegenüber
11,53 in der Ausgangslage** — das Objektiv dreht und wirkt. Ob 75 das Maximum
ist, ist offen; der Lauf endete an der Kamerasperre und speicherte damals noch
kein Bild.

Ebenfalls belegt (2026-09-08): die AI Camera hat **keine Fokus-Controls** — kein
`AfMode`, kein `LensPosition`. Fokussiert wird ausschließlich mechanisch am
Objektiv, Herstellerbereich etwa 20 cm bis ∞. Das Bild ist mit Laplace-Varianz
11,53 (960×720) messbar unscharf. Zahlen: [VALIDATION.md](VALIDATION.md).

Nebenbefund für die Bildqualität: bei 30 cm Abstand und 10 mm Ziffernhöhe
liefert 2028×1520 rund 51 px Ziffernhöhe, 960×720 nur rund 24 px — unter der
30-px-Marke aus [OPTICAL_SETUP.md](OPTICAL_SETUP.md). Zum Lesen der Anzeige
gehört der höher auflösende Modus, nicht die 960×720-Vorschau.

## Aktueller Stand

**P0 (Grundgerüst) erreicht, P1 (Kamera) teilweise.** Die Verarbeitungskette
aus Konzept §3 läuft Ende zu Ende ohne Hardware; die Kamera ist in Betrieb
genommen und vermessen. Was noch fehlt, steht unter P0 in
[ROADMAP.md](ROADMAP.md) als offene Punkte — insbesondere fünf der sechs
Bildquellen, das Tesseract-Backend und die vollständige Messpipeline-CLI.
Die Workbench für Vorschau und Einrichtung ist vorhanden; die Einrichtung
läuft seit dieser Session direkt in der Weboberfläche.

## Letzte Session am 2026-09-08 — Einstelltabelle in der Weboberfläche

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
