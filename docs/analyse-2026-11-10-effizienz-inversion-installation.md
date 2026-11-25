# Analyse 2026-11-10: Effizienz, invertierte Displays, Installation/TUI

Bestandsaufnahme aus einer Claude-Session vom 2026-11-10, ohne Code-Änderung.
Gemessen am laufenden Dienst `dispread-werkbank-bruecke` (Worktree
`.worktrees/bruecke-run`, Stand `c5cb924`), am Lauf
`var/live/live-20261106T175834Z/run-01` (6 785 Datensätze) und mit
Mikro-Benchmarks auf dem Pi 5 (`cv2.setNumThreads(2)` wie im Dienst).

Die drei Teile folgen der Reihenfolge in der Roadmap P9: Code polieren, TUI,
Installer, danach der nächste Sensor.

---

## 1. Effizienz: Latenz und Ressourcen

### 1.1 Leerlauf: ~52 % eines Kerns ohne Lauf und ohne Betrachter

Am 2026-11-10 lief kein Lauf, und kein Client war an Port 8082 verbunden.
Trotzdem hatte der Prozess nach 18,7 h etwa 9 CPU-Stunden verbraucht.

| Thread (top -H) | CPU | Ursache |
| --- | --- | --- |
| Kamera-Lesethread | ~27 % | `CameraOwner._run` liest dauerhaft 1080p YUYV mit 30 fps; OpenCV rechnet jedes Bild nach BGR um (2,8 ms), auch ohne Abnehmer |
| Alter Controller | ~14 % | `Controller._feed_from_owner` (`FEED_INTERVAL_S = 0.2`) rechnet 5× pro Sekunde `find_display_candidates` übers ganze Bild (12 ms), Overlay und JPEG in voller Auflösung (12 ms), auch ohne Betrachter |
| dritter Thread | ~11 % | nicht eindeutig zugeordnet (Kandidaten: asyncio-Schleife, Profil-Watcher alle 0,5 s) |

Mikro-Benchmarks (Pi 5, 1080p):

| Operation | Zeit |
| --- | --- |
| YUYV→BGR | 2,84 ms |
| YUYV→Grau (Y-Kanal) | 1,33 ms |
| JPEG q80, 1920×1080 | 12,2 ms |
| Verkleinern auf 960 + JPEG q80 | 5,3 ms |
| `rectify()` 400×160 inkl. Kennzahlen | 2,4 ms |
| nur `warpPerspective` 400×160 | 1,4 ms |
| `find_display_candidates` 1080p | 12,3 ms |

**Vorschläge (ohne Wirkung auf den Messpfad):**

1. Den alten Controller nur rechnen lassen, solange die alte Seite oder ihr
   Stream offen ist, oder ihn ganz entfernen (OP-2, nach Audit). Ersparnis ~14 %.
2. Leerlaufmodus im `CameraOwner`: ohne Lauf, Einrichtung und
   Vorschau-Betrachter nur `grab()`, `retrieve()` selten oder gar nicht. Der
   Stream läuft weiter (Zeitstempel, `frame_gaps`), ein Neuöffnen entfällt.
   Ersparnis ~20 % im Leerlauf, weniger Wärme.

### 1.2 Während eines Laufs

Stufenzeiten aus `PipelineTrace` (Median / 95 %):

| Stufe | Median | 95 % |
| --- | --- | --- |
| Lokalisieren (`rahmenbereiche_confirmed_quad`) | 7,1 ms | 14,8 ms |
| Entzerren | 2,5 ms | 4,0 ms |
| Lesen (dotmatrix) | 7,1 ms | 13,5 ms |
| Freigabe + Datensatz | < 0,05 ms | |
| **Pipeline gesamt** | **17,2 ms** | **29,4 ms** (max. 96 ms) |
| Abstand der Aufnahmen | 32,0 ms | 36,0 ms |
| Aufnahme → Verarbeitungsbeginn | 37,6 ms | 43,0 ms |

Übersprungen wurden 12 von 6 785 Bildern. Der Takt reicht, die Pipeline belegt
im Lauf etwa einen halben Kern.

* **Aufnahme → Verarbeitungsbeginn** (~38 ms) liegt vor allem an der
  USB-Übertragung. UVC setzt den Zeitstempel üblicherweise beim ersten Paket,
  und ein YUYV-Bild wird über etwa ein Bildintervall übertragen (Semantik
  offen, OQ-43). MJPEG würde schneller übertragen, bringt aber
  Kompressionsartefakte in den Messpfad. Nicht empfohlen.
* `rectify()` berechnet Laplace-Varianz, Sättigung und Dunkelanteil, die im
  Live-Pfad niemand liest (~1 ms von 2,4 ms). Der Punktmatrix-Leser bestimmt
  seine Sättigung selbst. Ein abschaltbarer Schalter wäre gefahrlos.
* Lokalisieren und Lesen zuerst mit cProfile auf einem `replay://`-Clip
  vermessen. Kandidat: die Diagnose pro Zelle in `DotMatrixReader.read`
  (`dots` mit `round()` in Python), die in jedem Bild aufgebaut wird.
* Grau direkt aus dem Y-Kanal spart ~1,5 ms plus die mehrfachen `cvtColor`
  in Tracker, Entzerrung und Leser. **Aber:** Die Pixelwerte ändern sich
  gegenüber den eingefrorenen Vorlagen. Das ginge nur mit einer neuen
  Abnahme; derzeit nicht lohnend.

### 1.3 Speicher auf der SD-Karte

* `records.jsonl`: ~1 004 B pro Datensatz, bei 30 pro Sekunde **~100 MB/h**.
* `LiveSession` öffnet `JsonlSink(..., max_bytes=0)`, also ohne Rotation.
* `/` am 2026-11-10: 49 GB, 80 % belegt, 9,5 GB frei. Ein Dauerlauf füllt das
  in etwa 4 Tagen.
* `component_versions` ist in jedem Datensatz gleich (~170 B, ~17 %) und
  gehört einmal in `session.json`. Abgeschlossene Läufe ließen sich
  komprimieren (JSONL typisch etwa Faktor 10). Beides ändert das
  Audit-Format: Die neun Felder aus Konzept §8 bleiben unberührt, Leser und
  Session-Explorer müssen aber angepasst werden. Das gehört in die noch
  fehlende Speicher-/Export-Spec (Roadmap P9).
* Die Rohbilddiagnose (`live/diagnostics.py`) ist bereits begrenzt
  (300 Bilder, 600 MB) und braucht nichts.

### 1.4 Empfohlene Reihenfolge

1. Alten Controller nur auf Abruf rechnen lassen oder entfernen.
2. Leerlaufmodus im `CameraOwner`.
3. Wachstum von `records.jsonl` begrenzen (Speicher-Spec).
4. Lokalisieren und Lesen profilieren, Kennzahlen in `rectify` abschaltbar.

---

## 2. Invertierte, blau hinterleuchtete Displays (helle Ziffern)

Anlass: geplante nächste Erweiterung nach der Demo vom 11.11. (Pfad
GSV-2TSD-DI / Ziffernvielfalt). Bezug: OQ-13 (Anzeigepolarität), OQ-04
(Gerätetypen).

**Schätzung:** 2–3 Wochen, wenn das Display baugleich ist (Punktmatrix 5×8,
16×1, HD44780) und das Gerät dieselben RS232-Befehle wie das GSV-2AS
versteht. Bei anderer Geometrie oder anderem Protokoll 4–6 Wochen oder mehr.
Die Inversion selbst ist wenig Code; den Großteil kosten Daten,
Kalibrierung und Abnahme.

### 2.1 Wo „dunkle Punkte auf hellem Grund" im Code steckt

| Bereich | Annahme heute | Aufwand |
| --- | --- | --- |
| Leser (`ocr/dotmatrix_sampling.py`) | Hintergrund = hellste Punkte, Punktpegel = zweitdunkelster Punkt, `background_opening` entfernt helle Defekte | klein: Polaritäts-Flag im Profil, `255 − gray` vor dem Abtasten |
| Vorlagen und Schwellen (`ocr/dotmatrix_templates.py`) | aus echten Proben dieses Displays gelernt (`d_max` = 1,25 × 99,5. Perzentil, `margin_min`) | **groß:** neue Vorlagen aus echten Proben, eigene Abnahme (bisher 215 Proben, Abnahme 3) |
| Belichtung im Assistenten (`live/setup.py`, `adjust_exposure`, `hint_glass_level`) | regelt auf den Pegel des hellen Glases | mittel: leuchtende Punkte dürfen nicht sättigen; andere Logik, nicht bloß invertiert |
| Prüfungen beim Einrichten (`setup_checks.py`) | `_glare_check` sucht helle Flecken; `_glass_defects`, `_edge_check`, `_lighting_finding` | mittel: die Blendungsprüfung schlüge bei hellen Ziffern immer an; jede Prüfung muss die Polarität kennen |
| Gitteranpassung (`dotlattice.py`) | Kandidaten sind dunkle Punkte | klein bis mittel |
| Nachführung (Rahmenbereiche, `live/tracking.py`) | Merkmale am Gehäuserahmen | vermutlich unabhängig von der Polarität, testen |
| Werkbank-UI | – | klein: Polarität/Geräteprofil beim Einrichten wählen, Overlay-Farben |

`detect/vision.py` (Otsu in beiden Polaritäten) und `benchmark.py`
(`polarity`, `255 - gray`) kennen die Polarität bereits. Das sind aber Pfade
für den Altpfad bzw. Benchmark, nicht der Live-Leser.

### 2.2 Was physikalisch anders ist (nur am echten Display messbar)

* **Überstrahlung:** Leuchtende Punkte laufen bei Fokus und Abstand der
  Kamera ineinander; das Punktraster wird unschärfer.
* **Spiegelungen:** Ein dunkler Hintergrund spiegelt den Raum deutlich
  stärker. Mit Raumlicht vermutlich das größere Risiko als die Inversion.
* **Farbkanal:** Weiße Ziffern sind in allen Kanälen hell, blaues Licht fast
  nur im Blau-Kanal. Rot oder Grün statt Grau dürfte deutlich mehr Kontrast
  geben. Chance, aber messen.
* **Nicht angesteuerte Punkte** sind bei hinterleuchteten LCDs oft schwach
  sichtbar und könnten die Leerzellenprüfung stören.

### 2.3 Was außer der Inversion auf GSV-2AS festgelegt ist

* `parse_gsv2as` erwartet 6 Ziffern, Einheit fest `mV/V`, Raster fest 16 Zellen,
  `DEVICE_ID = "gsv-sensor-161a"`, Standardvorlagen in `live/__init__.py`.
* Gegenlesen und Ziffernvielfalt beim Einrichten laufen über GSV-2-RS232
  (`set norm`/`dpoint`). Fehlt das am neuen Gerät, wird das Sammeln von
  Proben deutlich teurer.
* Ein Minuszeichen wurde live nie gelesen (Firmware 1.3.07 ohne negative
  Normierung). Kommt es am neuen Gerät vor, ist das ungeprüft.

### 2.4 Vorgeschlagener erster Schritt (1–2 Tage)

1. Ein invertiertes Gerät vor die StreamCam stellen, mit dem
   Datensatz-Sammelmodus 30–50 Bilder bzw. Clips aufnehmen.
2. Die vorhandene Kette offline darüber laufen lassen: invertiert, Kanäle
   R/G/Grau. Messen: Rasterpassung, Abstand der Vorlagen, Spiegelungen.
3. Erst danach die Schätzung festlegen.

Vom Nutzer noch zu klären: Gerät bzw. Displaymodul (Punktmatrix oder
7-Segment, Zeichen × Zeilen), RS232-Befehlssatz, Exemplar im Labor.

---

## 3. Aufräumen, Installation, TUI/CLI

**Schätzung gesamt:** 4–7 Wochen.

### 3.1 Ausgangslage: Ein frischer Pi könnte heute keinen Lauf starten

* **Vorlagen und Timing-Kalibrierung liegen in `var/`, nicht im Git**, und der
  Pfad ist relativ zum Arbeitsverzeichnis
  (`DEFAULT_TEMPLATES = Path("var/dotmatrix/templates-stufe2c-2026-09-30.json")`,
  `DEFAULT_CALIBRATION = Path("var/calibration/timing-streamcam.json")`,
  `LIVE_DATA_DIR = Path("var/live")` in `src/dispread/live/__init__.py`).
  Ohne sie lehnt `LiveSession.start()` ab.
* **Die Timing-Kalibrierung ist Pflicht und hängt von Kamera und Aufbau ab.**
  Sie entsteht aus `scripts/display-offset.py` → `scripts/timing-calibration.py`.
  Für neue Pis ist offen: im Labor neu messen (geführter Schritt in der TUI)
  oder ein Wert pro Kameramodell? **Fachliche Entscheidung.**
* **Der produktive Dienst läuft als vorübergehende `systemd-run`-User-Unit**
  (`dispread-werkbank-bruecke`) aus `.worktrees/bruecke-run`. Nach einem
  Neustart ist er weg. Die Tailscale-IP `100.122.154.35`, `/home/me-systeme/...`
  und `/tmp/.../control.sock` stehen in der Befehlszeile.
* **`scripts/install-workbench.sh` hat 9 Zeilen** (apt + pip). Es fehlen:
  UART für `/dev/ttyAMA0` in `config.txt` (Neustart nötig), Gruppen `video`
  und `dialout`, Dienst beim Booten, TLS (`dispread init-tls` nur als Hinweis),
  Prüfung auf USB3-Port, festes Datenverzeichnis, Konfigurationsdatei statt
  Befehlszeile.
* **Voraussetzung Raspberry Pi OS Trixie** (`requires-python >= 3.13`;
  dieser Pi: Python 3.13.5, trixie). Bookworm (3.11) fällt durch; der
  Installer muss das zuerst prüfen.
* Paketabhängigkeiten nur als Debian-Pakete (`--system-site-packages`,
  `--no-deps`, siehe `docs/dependencies.md`); die Liste steht verstreut im
  Installskript.

### 3.2 Schätzung pro Teil

| Teil | Aufwand | Inhalt |
| --- | --- | --- |
| Aufräumen | 1–2 Wochen | alten Controller und alte Seite entfernen (`workbench/controller.py` 1 544 Zeilen, `fields.py`, alte Statics; OP-2: erst nach Audit). Reste von IMX500, 7-Segment und Tesseract prüfen. 51 Skripte in Produkt- und Laborwerkzeuge trennen. Tests anpassen (~69 000 Zeilen Tests gegenüber ~35 000 Zeilen `src`). Datensatz-Sammelmodus bleibt (invertierte Sensoren, OQ-61). |
| Installation | 1–2 Wochen | Vorlagen als versionierte Paketdaten mit SHA-256, feste Datenorte, dauerhafte systemd-Unit, Konfigurationsdatei, Systemeinrichtung (UART, Gruppen, Pakete), Bootstrap ohne geklontes Repo, Test auf frischem Pi (P7, `p7-frischinstallation`). Offen: OQ-49 (Veröffentlichung, Integritätsprüfung). |
| TUI/CLI | 1,5–3 Wochen | Textual läuft bereits; `workbench/tui.py` gehört aber zum alten Controller. Die lokale Socket-Steuerung existiert (`dispread live status/setup/stop/aufraeumen`, `bridge …`). Neu: Systemprüfung (`camera-commissioning.sh`, `setup_checks`), Konfiguration (Ausgabeweg, Ports, Netz/TLS, Benutzer, Speicherort), Verwaltung (Dienst, Läufe, Export, Aufbewahrung), Fehlersuche (Logs, Kamera, UART), nicht interaktiver Modus. |

Grenze der TUI: Ausrichten und Bestätigen der Anzeige braucht Bilder und
bleibt auf `/live`. Die TUI kann den Assistenten starten und seinen Stand
zeigen.

### 3.3 Was die Schätzung kippen kann

1. Timing-Kalibrierung pro Gerät messen → geführte Prozedur mit Aufbau, allein
   bis zu einer Woche.
2. Die Speicher-/Export-Spec (Roadmap P9) fehlt; die TUI-Verwaltung baut
   darauf auf. Sie sollte **vor** der TUI stehen.
3. Die Windows-Brücke hat einen eigenen Installer und ist nicht enthalten.

### 3.4 Empfohlene Reihenfolge

Aufräumen → Installation und Datenorte (zuerst Pfade, Vorlagen, Unit) → TUI.
Den Test auf einem frischen Pi früh als Rohfassung laufen lassen, nicht erst
am Ende.

### 3.5 Checkliste frischer Pi (Entwurf für P7)

- [ ] OS-Prüfung: Raspberry Pi OS Trixie, Python ≥ 3.13, Pi 5
- [ ] Debian-Pakete: `python3-opencv`, `python3-numpy`, `python3-serial`,
      `python3-aiohttp`, `python3-textual`, `python3-pam`,
      `python3-cryptography`, `python3-zeroconf`, `openssl`, `v4l-utils`
      (Liste gegen `docs/dependencies.md` abgleichen)
- [ ] venv `--system-site-packages`, `pip install --no-deps`
- [ ] Benutzer in `video` und `dialout`
- [ ] UART `/dev/ttyAMA0` in `config.txt` freischalten, Neustart, prüfen
      (nicht `/dev/serial0`, das ist der Debug-Header)
- [ ] StreamCam am USB3-Port (`usb_speed_mbps == 5000`), `find_uvc_device`
- [ ] Vorlagen mit SHA-256 an festem Ort (nicht relativ zu CWD)
- [ ] Timing-Kalibrierung: messen oder Modellwert (Entscheidung offen)
- [ ] TLS-Zertifikat (`dispread init-tls`), Login (PAM-Benutzer)
- [ ] Bindadresse konfigurierbar statt fester Tailscale-IP
- [ ] Datenverzeichnis, Aufbewahrung, freier Platz
- [ ] systemd-Unit, die beim Booten startet; Socket nicht unter `/tmp`
- [ ] `scripts/camera-commissioning.sh` Exit 0
- [ ] Ende-zu-Ende: Einrichtung auf `/live`, Testlauf, Audit geschrieben

---

## Kandidaten für neue offene Fragen

Nicht in `docs/open-questions.md` eingetragen, weil die OQ-Nummern zwischen
den Zweigen auseinanderlaufen (master bis OQ-64, `feat/gsvmulti-bridge` bis
OQ-59, mit uncommitteten Änderungen). Beim nächsten Merge mit freier Nummer
anlegen:

1. **Timing-Kalibrierung auf neuen Pis:** pro Gerät messen oder pro
   Kameramodell übernehmen? Antwort landet in TIMING.md und im
   Installationsplan.
2. **Hinterleuchtete invertierte Displays:** Modul, Zeichensatz, RS232-Gegenlesen,
   Einfluss von Spiegelungen und Überstrahlung; Bezug OQ-13, OQ-04.
3. **Wachstum des Audits in Dauerläufen:** ~100 MB/h ohne Rotation;
   Bezug Speicher-/Export-Spec (Roadmap P9).
