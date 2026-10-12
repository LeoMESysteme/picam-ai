# Messpfad live: StreamCam, Einrichtung und Dot-Matrix-Lesen in der Werkbank — Entwurf

**Stand:** 2026-10-12, mit dem Nutzer abschnittsweise abgestimmt.
**Bezug:** Nutzerentscheidung 2026-10-01 (Variante B: Leser gilt für den
GSV-Sensor als ausreichend validiert, als Nächstes Anbindung an den
Messpfad); Abnahme 3 (`stufe2c`, 215/0/0) und Lesetest `sc7` (111/111),
VALIDATION.md; Spec Dot-Matrix-Leser 2026-09-24 und Spec StreamCam
2026-09-25 (beide schlossen die Werkbank-Anbindung aus); Plan
Einrichtungsassistent 2026-09-29 inkl. Nacharbeit 5; Konzept.md §3, §4,
§6, §7, §8.

## Ziel und Erfolgskriterium

Ein Bediener richtet in der Werkbank (`dispread serve`) die StreamCam auf
die Anzeige des GSV-Sensors (Displaytech 161A) ein, bestätigt das Profil
und sieht danach live den freigegebenen Wert mit Status. Jeder Wert wird
als `ValueRecord` (Konzept §8) mit Aufnahmezeitstempel in ein JSONL-Audit
geschrieben.

**Erfolg (Meilenstein 1):**

1. Einrichtung vollständig im Browser: Kameraprüfung, Fokus, zwei
   Standbilder mit Zellentext, Punktraster mit Prüfung 2j und
   Gegenlesen, Bestätigung durch eine namentlich genannte Person.
2. Live-Lesen mit `VALID | TRANSITION | UNREADABLE | STALE`; ein alter Wert
   läuft nie unmarkiert weiter, Unlesbares wird abgelehnt.
3. Jeder Datensatz trägt den Aufnahmezeitstempel des gelesenen Bilds; der
   Versatz `BOOTTIME − MONOTONIC` ist in `session.json` der Live-Sitzung
   gemessen, sonst wird abgelehnt.
4. Ein echter Lauf am Aufbau (StreamCam + GSV-2AS) ist in VALIDATION.md
   dokumentiert — als Nachweis der Kette, **nicht** als formaler
   Abnahme-Lauf.
5. Die Kamera hat genau einen Besitzer im Prozess; Einrichtung, Vorschau
   und Lesen teilen sich die Bilder.

## Nicht Teil dieses Schritts

* Serielle Ausgabe an GSVmulti (eigener späterer Schritt; das GSV-Telegramm
  ist offen, OQ-07; `ascii_csv` ist nur vorläufig).
* Einrichtung schräger Aufstellungen per Eckenklick im Browser; dafür
  bleibt `profile-regrid.py still` in der Kommandozeile.
* Weitere Geräte, Einheiten und Lichtquellen; Ablesen der Einheit aus der
  Anzeige (sie kommt aus dem bestätigten Profil, OQ-17).
* Negative Werte (Firmware 1.3.07 kann sie nicht anzeigen).
* Kamerabildaufnahme für Datensätze aus der Werkbank, falls sie sich nicht
  sauber an den neuen Kamerabesitzer hängen lässt (siehe §5); die
  Ernte-Skripte decken das ab.

## Ausgangslage (Bestandsaufnahme 2026-10-12)

* Die Werkbank nutzt weder `pipeline.py` noch `ValueRecord` noch eine
  Senke. `workbench/controller.py` (1739 Zeilen) bündelt Profile,
  Kamera-Worker, Clips, Datensatzaufnahme, Lesen, Freigabe und Overlays.
* Kamera-Worker (`_worker`, `_capture`, `_settle`, `_automatic`) und
  Regler (`profiles.py`, `fields.py`: `AeEnable`, `ExposureTime`) sind für
  Picamera2/libcamera geschrieben; mit der StreamCam meldet der Worker
  „Kamera der Werkbank ausser Betrieb".
* `_read` kennt nur `sevenseg` und `tesseract_cli`, nutzt den
  7-Segment-`GateConfig` (0,15/0,10) und erzeugt keinen Datensatz.
* `DotMatrixReader` (`ocr/dotmatrix.py`) wird nur von Skripten und
  `setup_checks.py` benutzt. Die Einrichtung (`assist`) liegt großteils in
  `scripts/harvest-setup.py` (1029 Zeilen).
* Wiederverwendbar und getestet: `datasets.py` (`DatasetStore`, auch von
  `import-harvest.py` genutzt), `vision.py`, `server.py`, `auth.py`,
  Datensatz-Oberfläche.

**Entscheidung:** kein Umbau des Controllers an Ort und Stelle und keine
getrennte neue Web-App, sondern ein neuer Kern `dispread/live/` ohne
Web-Code und eine neue schlanke Live-Seite im bestehenden Server. Der alte
Kamera- und Lesepfad der Werkbank wird stillgelegt, die Datensatzfunktionen
bleiben.

## 1. Architektur

```
dispread/live/                       (ohne Web-Code, mit replay:// testbar)
  camera.py    CameraOwner   einziger Halter von UvcSource; verteilt Bilder
                             (neuestes Bild + Abonnenten), setzt Regler,
                             Start/Stopp, meldet „belegt" klar weiter
  setup.py     SetupSession  assist-Ablauf aus harvest-setup.py, verlagert:
                             Fokus-Sweep → 2 Standbilder (+ Zellentext von
                             ttyUSB0 oder Eingabe) → Punktraster → 2j und
                             Setup-Prüfungen → Bericht + Overlays →
                             confirm(by=…) → SessionProfile
  session.py   LiveSession   bestätigtes Profil + Vorlagen (sha256) →
                             Pipeline: Quad nachführen → entzerren 400×160
                             → DotMatrixReader → ReleaseGate("dotmatrix")
                             → ValueRecord → Senken (jsonl)
  clock.py     Zeitbasis     Versatz BOOTTIME−MONOTONIC (Start, alle 60 s,
                             Ende), Timing-Kalibrierung lesen, Lücken
workbench/
  live_api.py  Routen /live/*: Status, Einrichtungsschritte, Bestätigen,
                             Start/Stopp
  static/live.html, live.js  neue schlanke Seite
  controller.py              Kamera-Worker und _read entfernt,
                             Datensätze bleiben
```

Regeln:

* **Nur `CameraOwner` öffnet die Kamera.** Einrichtung, Vorschau und Lesen
  abonnieren seine Bilder. Ein zweiter Prozess (z. B. ein Ernte-Skript)
  bekommt wie bisher „belegt"; die Seite nennt das.
* **Eine Implementierung der Einrichtung.** `scripts/harvest-setup.py
  assist` ruft danach `live/setup.py` auf und liefert dieselben Ergebnisse
  wie heute.
* **`LiveSession` nutzt die vorhandene `Pipeline`.** Deren
  7-Segment-Annahme (`config.layout: DisplayLayout`) wird auf
  `CharLayout` verallgemeinert; der 7-Segment-Pfad bleibt lauffähig.
* **Die Seite steuert und zeigt nur an.** Freigabe und Ablehnung
  entscheidet `live/`.

## 2. Datenfluss und Zeitbasis

1. **Aufnahme:** `CameraOwner` holt jedes Bild aus `UvcSource` mit
   V4L2-Zeitstempel (`TimeBaseKind.V4L2_MONOTONIC`) und eigener
   Folgenummer. Die StreamCam hat keine Treiber-Bildnummer; Aussetzer
   gehen nach `frame_gaps`.
2. **Lesen:** `LiveSession` nimmt immer das **neueste** Bild. Ist der Leser
   langsamer als die Kamera, werden ältere Bilder übersprungen und
   gezählt, nicht gepuffert. Die Leserlaufzeit auf dem Pi 5 ist
   ungemessen; ihre Messung ist die erste Aufgabe des Plans und bestimmt
   die erreichbare Leserate.
3. **Kette:** Quad nachführen (Verlust → `UNREADABLE`, Hinweis „neu
   einrichten") → entzerren auf 400×160 → `DotMatrixReader` →
   `ReleaseGate(default_gate_config("dotmatrix"))`. Es gelten die
   eingefrorenen Schwellen des Lesers, nicht die 7-Segment-Werte.
4. **Datensatz:** `ValueRecord` mit allen neun Pflichtfeldern.
   `capture_timestamp` ist die Aufnahmezeit des gelesenen Bilds, nicht die
   Verarbeitungszeit; `result_timestamp` aus derselben Uhr;
   `frames_confirmed` und `confirmation_span_ns` dokumentieren die
   Bestätigungsverzögerung; `raw_text` enthält die 16 Zellen; `unit` kommt
   aus dem bestätigten Profil.
5. **Senken:** in Meilenstein 1 nur `JsonlSink` (Audit); der jeweils
   neueste Datensatz geht zusätzlich an die Seite.

**Zeitbasis (Konzept §6):**

* `BOOTTIME − MONOTONIC` wird bei Sitzungsstart, alle 60 s und am Ende
  gemessen und in `var/live/<sitzung>/session.json` geschrieben.
  Umgerechnet wird nur über `records.to_boottime_ns`; fehlt der Versatz,
  wird abgelehnt.
* `var/calibration/timing-streamcam.json` (Anzeigeversatz 89,6 ms,
  M = 326 ms) ist **Pflicht beim Start** (fehlt sie, startet die Sitzung
  nicht); ihr sha256 steht in `session.json`. Sie wird **nicht** auf die
  Zeitstempel angewandt: Datensätze tragen die rohe Aufnahmezeit, die
  Auswertung korrigiert. Ein still eingerechneter Versatz würde die
  Zeitbasis verschleiern.
* Kein Nachsenden: Ein wiederholter Anzeigewert ist keine neue Messung.
  Jeder Datensatz gehört zu genau einem gelesenen Bild.

**Sitzungsende:** Kamera stoppen, letzten Versatz messen, Zusammenfassung
in `session.json` (Anzahl je Status, übersprungene Bilder, Lücken).

## 3. Einrichtung im Browser

Konzept §4: Eine Person bestätigt Anzeige, Einheit und Dezimalformat.

1. **Kameraprüfung:** USB3, 1920×1080 YUYV, Regler gesetzt und
   zurückgelesen. Sonst Abbruch mit Grund („USB2-Port", „Kamera belegt").
2. **Fokus:** Sweep über `focus_absolute` mit Vorschlag und Live-Vorschau;
   der Bediener kann nachstellen.
3. **Zwei Standbilder mit Zellentext:** der Text kommt vom GSV-2AS über
   `/dev/ttyUSB0` (38400 Baud, wie `assist`). Ohne GSV-2AS tippt der
   Bediener den angezeigten Text ein. `/dev/ttyAMA0` bleibt für die
   spätere Ausgabe an GSVmulti frei.
4. **Anpassung und Prüfungen:** Punktraster, Prüfung 2j, Rand, Spiegelung,
   Stabilität, Gegenlesen gegen den Zellentext. Bericht mit Overlays und
   Gesamturteil. **FEHLER** sperrt die Bestätigung, **WARNUNG** verlangt
   eine ausdrückliche Kenntnisnahme.
5. **Bestätigen:** Name, Einheit (mV/V) und Format (`gsv2as_v1`, Punkt
   wandert innerhalb von 6 Ziffern) prüfen. Ergebnis ist ein
   `SessionProfile` unter `var/live/<sitzung>/profile.json`.

**Wiederverwenden:** Ein früheres Profil darf als Startwert dienen; Quad und
alle Prüfungen laufen trotzdem **neu** (Konzept §4).

**Schräge Aufstellungen:** Wo `assist` heute mit `startlage_mehrdeutig`
oder `keine_startlage` scheitert, zeigt die Seite den Grund und den Hinweis
„Kamera senkrecht auf Displaymitte". Die Einrichtung von Hand bleibt in der
Kommandozeile.

## 4. Fehlerbehandlung im Lauf

Jeder Fall ist auf der Seite sichtbar und im Datensatz bzw. in
`session.json` festgehalten.

| Fall | Verhalten |
| --- | --- |
| Leser lehnt ab | `UNREADABLE` + `reject_reasons` |
| Wert ändert sich | `TRANSITION` bis zur Bestätigung |
| > 500 ms kein bestätigter neuer Wert | `STALE`, alter Wert nie unmarkiert |
| Quad driftet, Nachführung verloren | `UNREADABLE`, Hinweis „neu einrichten" |
| 2 s keine Bilder von der Kamera | Sitzung endet, Hinweis, Endversatz gemessen |
| Vorlagen-sha256 oder Kalibrierdatei falsch/fehlt | Start abgelehnt |
| Kamera von anderem Prozess belegt | klare Meldung, keine Wiederholschleife |

**Freigabehinweis**, dauerhaft auf der Seite und in `session.json`:
„Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V —
andere Lichtquellen und Geräte nicht geprüft."

## 5. Stilllegung in der Werkbank

* Aus `workbench/controller.py` entfallen der Picamera2-Worker (`_worker`,
  `_capture`, `_settle`, `_automatic`), der Lesepfad (`_read`,
  `_reader_for`, `_draw_cells`) und die Meldung „außer Betrieb"; dazu die
  libcamera-Regler in `profiles.py` und `fields.py`.
* Es bleiben Datensätze (`datasets.py`, `dataset.js`), `vision.py`,
  Server, Anmeldung und Terminals.
* Datensatzaufnahme und Clips aus der Kamera bekommen ihre Bilder von
  `CameraOwner`. Hängt das zu eng am Controller, wird die Kameraaufnahme
  für Datensätze in Meilenstein 1 abgeschaltet und später nachgezogen.
* `dispread serve --simulate` bleibt: `CameraOwner` bekommt dann
  `synthetic://` oder `replay://` statt der StreamCam.

## 6. Tests

Alle ohne Hardware (CLAUDE.md):

* **Kern `live/`:** `replay://`-Clips und injizierte `UvcSource`-Attrappen
  für übersprungene Bilder, Lücken, Kameraverlust und „belegt";
  Statusübergänge `VALID → TRANSITION → STALE → UNREADABLE`;
  Startablehnung bei falschem Vorlagen-sha256 oder fehlender Kalibrierung;
  Versatz in `session.json` und Ablehnung ohne Versatz.
* **Einrichtung:** die verlagerte `assist`-Logik gegen die bestehenden
  Tests (`test_harvest_assist.py`, `test_dotlattice_*`); die
  Kommandozeile liefert unverändert dieselben Ergebnisse.
* **Echte Standbilder:** `sc7`/`sc7a` aus `var/diagnostics` (Tests
  überspringen, wenn `var/` fehlt, wie bisher).
* **API und Seite:** Servertests für `/live/*`, ein Playwright-Test für
  Einrichtung → Bestätigen → Live-Anzeige mit `--simulate`.
* **Hardware (`--mode=real`):** ein echter Lauf mit StreamCam und GSV-2AS,
  dokumentiert in VALIDATION.md, kein formaler Abnahme-Lauf.

## 7. Phasen

Jede Phase endet mit grünen Tests und einem Commit.

1. Leserlaufzeit auf dem Pi 5 messen; `CameraOwner`; `Pipeline` auf
   `CharLayout` verallgemeinern.
2. `assist`-Logik nach `live/setup.py`; `harvest-setup.py` ruft sie auf.
3. `LiveSession` mit Zeitbasis und JSONL, kopflos mit `replay://`.
4. `/live/*`-API und neue Seite; alten Kamera- und Lesepfad entfernen.
5. Echter Lauf am Aufbau; Doku (status, TODO, CHANGELOG,
   Anleitung Kapitel 10, ROADMAP).

## Offene Punkte

* Leserlaufzeit auf dem Pi 5 (Phase 1) — bestimmt die Leserate.
* Ob GSVmulti Aufnahmezeitstempel überhaupt nutzt (Konzept §6, OQ-07) —
  betrifft erst den seriellen Schritt.
