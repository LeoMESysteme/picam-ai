# Umstellung IMX500 → Logitech StreamCam — Entwurf

**Stand:** 2026-09-25, mit dem Nutzer abschnittsweise abgestimmt.
**Bezug:** Nutzerentscheidung 2026-09-25 („wir wechseln offiziell von der
imx500 auf die logitech kamera"; IMX500-Code entfernen/deaktivieren, Doku und
Verweise für eine Rückumstellung erhalten, aber klar kennzeichnen, dass die
Logitech aktiv ist); OQ-22 (RP2040-Wedge) und Ausfall mitten im Stream
2026-09-25 (I2C -121, „Camera frontend has timed out"); StreamCam-Test
2026-09-25 (`var/diagnostics/streamcam-spike/`); Plan Ernte Phase 1;
Spec Dot-Matrix-Leser 2026-09-24.

## Ziel und Erfolgskriterium

Ernten laufen mit der Logitech StreamCam (USB 046d:0893, UVC, `/dev/video8`)
genauso wie bisher (`harvest-setup` → `harvest` → `import-harvest` →
Training), aber ohne Streamstart-Budget, ohne Wedge-Neustarts und mit
Fokus per Software.

**Erfolg:**

1. Eine Ernte läuft über mehrere Aufzeichnungen hintereinander durch, ohne
   Kamerahänger und mit korrektem Bildzähler in `session.json`.
2. Zeitversatz Telegramm↔Glas und Schutzfenster M sind für die StreamCam
   neu gemessen und hinterlegt; ohne diese Messung startet keine
   StreamCam-Ernte.
3. Bestehende IMX500-Sessions, -Profile und der Datensatz bleiben für
   Import, Datensatz und Training unverändert nutzbar (Regressionstests).

**Messwerte aus dem Test (2026-09-25, Grundlage, keine Zusage):**
1920×1080 YUYV liefert ~25–30 fps; bester `focus_absolute` = 48 bei
AF aus; Glas ~346 px breit ≈ 3,6 px je Punktspalte (Schwelle 2,6);
Punkte klar getrennt; OpenCV liefert je Bild den V4L2-Pufferzeitstempel
in CLOCK_MONOTONIC (µs), ~35–40 ms vor Ankunft im Programm; keine
Treiber-Bildnummer (`CAP_PROP_POS_FRAMES` = -1); `BOOTTIME − MONOTONIC`
≈ 0 (wenige µs Abtastrauschen); uvcvideo `clock=CLOCK_MONOTONIC`.

## Nicht Teil dieses Schritts

Werkbank-Anbindung der StreamCam (nur Deaktivierung des Picamera2-Pfads),
Kameradienst (vorgemerkte Idee, bleibt ungeplant), Treiber-Bildnummer über
eine V4L2-Bibliothek, Hardware-Zeitstempel (`uvcvideo hwtimestamps`),
Umbau des Dot-Matrix-Lesers.

## 1. Architektur

### Neu

**`src/dispread/frames/uvc_source.py` — `UvcSource`**, Schema
`v4l2:///dev/video8?size=1920x1080&fourcc=YUYV&fps=30`. `cv2` wird wie
bisher erst in der Factory importiert.

* Öffnet das Gerät über `cv2.VideoCapture(device, cv2.CAP_V4L2)`, setzt
  FourCC, Größe, fps und liest sie zurück; weicht die tatsächliche Größe ab
  (z. B. USB2-Rückfall), **Abbruch**.
* Setzt die Kamerasteuerung aus einem festen Satz über `v4l2-ctl`
  (Subprozess, `--set-ctrl`, danach `--get-ctrl` zum Zurücklesen):

  | Control | Wert |
  | --- | --- |
  | `focus_automatic_continuous` | 0 |
  | `focus_absolute` | aus Profil |
  | `auto_exposure` | 1 (manuell) |
  | `exposure_time_absolute` | aus Profil |
  | `white_balance_automatic` | 0 |
  | `white_balance_temperature` | aus Profil |
  | `gain` | aus Profil |
  | `power_line_frequency` | 1 (50 Hz) |
  | `zoom_absolute` | 100 (fest) |
  | `pan_absolute`, `tilt_absolute` | 0 (fest) |

  Weicht ein zurückgelesener Wert ab, **Abbruch** mit Name, Soll und Ist.
  Die Reihenfolge ist wichtig: Automatik zuerst aus, dann Absolutwert.
* Hinter einer schmalen Fassade (Capture-Objekt und Control-Funktionen
  injizierbar), damit Tests ohne Kamera laufen.
* Jedes Bild: `Timestamp(value_ns=round(CAP_PROP_POS_MSEC·1e6),
  base=TimeBaseKind.V4L2_MONOTONIC, semantics=UNKNOWN, uncertainty_ns=None)`.
  Liefert `CAP_PROP_POS_MSEC` 0 oder einen nicht monoton steigenden Wert,
  wird das Bild als Fehler gezählt, nicht mit erfundenem Zeitstempel
  weitergegeben.

**`TimeBaseKind.V4L2_MONOTONIC`** in `records.py`: V4L2-Pufferzeitstempel
(uvcvideo, CLOCK_MONOTONIC). Zählt wie `SENSOR_BOOTTIME` als echte
Kamerazeit.

### Fällt weg bzw. wird deaktiviert

* `scripts/sync-record.py`: Picamera2-Kamerazweig (`_camera_frames`),
  Streamstart-Budget (Exit 5, Zählerdatei, `--stream-budget`,
  `--override-stream-budget`, Kernel-Log-Zählung), `--scaler-crop`,
  960×720-Sperre, `--allow-large-sensor-mode`.
* `scripts/harvest-setup.py`: ScalerCrop-/Binning-Rechnung
  (`native_scale` aus Sensorgeometrie).
* `src/dispread/frames/__init__.py`: `picamera2://` und `imx500://` aus der
  Registry; ein Aufruf wirft `ValueError` mit „IMX500 außer Betrieb seit
  2026-09-25, siehe docs/project_history.md (StreamCam statt IMX500)".
* Werkbank (`workbench/controller.py`): Picamera2-Kamerapfad deaktiviert,
  Kamerastart meldet klar „Kamera der Werkbank außer Betrieb (IMX500
  abgelöst), StreamCam-Anbindung folgt"; Simulationsmodus bleibt.
* `scripts/camera-commissioning.sh`: neu für die StreamCam (Gerät mit
  USB-ID vorhanden, USB3-Verbindung, Formate/Größen, Steuerung
  rücklesbar, ein Testbild). Exit 0 = einsatzbereit, wie bisher.
* Die IMX500-Tests (Budget, ScalerCrop, Sensorgeometrie) fallen mit dem
  Code weg.

### Bleibt

* Mit der IMX500 aufgenommene Sessions und v2-Profile bleiben für
  `import-harvest`, `dotmatrix-dataset`, Training und Auswertung lesbar.
* Die IMX500-Doku (OQ-22, TIMING, Lab-Journal) bleibt, markiert als
  „historisch, außer Betrieb".

## 2. Datenfluss und Zeitbezug

Die seriellen Telegramme tragen `t_boot` (CLOCK_BOOTTIME). Die Auswerter
(`gate-label.py`, `display-offset.py`, `import-harvest.py`) nehmen bisher
an, dass `capture_timestamp.value_ns` in derselben Domäne liegt.

* **Rohwert bleibt roh:** `frames.jsonl` speichert den V4L2-Zeitstempel
  unverändert mit `base: "v4l2_monotonic"`.
* **Versatz wird gemessen:** `sync-record` misst beim Start und am Ende
  `BOOTTIME − MONOTONIC` (je Median aus 5 eng geklammerten Abfragen) und
  schreibt `clock_offset_boottime_minus_monotonic_ns: {start, end}` in
  `session.json`.
* **Eine Umrechnungsstelle:** `to_boottime_ns(timestamp: dict, session: dict)
  -> int` in `records.py`:
  * `sensor_boottime` → unverändert (alte IMX500-Sessions),
  * `v4l2_monotonic` → `value_ns + offset`, wobei `offset` = Start-Wert;
    weichen Start und Ende um mehr als 1 ms ab (Suspend dazwischen) oder
    fehlt der Versatz → `ValueError` (ablehnen, nicht raten),
  * jede andere Basis → `ValueError`.

  `gate-label`, `display-offset` und `import-harvest` nutzen nur noch diese
  Funktion.
* **Verpasste Bilder:** `sensor_sequence` ist bei der StreamCam `null`.
  `sync-record` zählt Zeitstempellücken > 1,5 × erwarteter Bildabstand der
  Kamera als `frame_gaps` (Anzahl, größte Lücke, Liste mit Zeitpunkten) in
  `session.json`.
* **Aufnahmerate:** Kamera läuft mit 30 fps; `--frame-rate` drosselt
  weiterhin die geschriebenen Bilder, Vorgabe 15 fps.
* **Timing-Kalibrierung:** Vor der ersten StreamCam-Ernte eine
  `sync-record`-Aufnahme mit Normsprüngen, dann `display-offset.py`.
  Ergebnis in `var/calibration/timing-streamcam.json`:
  `camera_usb_id`, `guard_margin_ms` (M), `display_offset_ms`,
  `measured_at_utc`, `session_dir`, `display_offset_report_sha256`.
  `harvest.py` liest M daraus und **verweigert den Start**, wenn die Datei
  fehlt, unlesbar ist oder die USB-ID nicht zum Profil passt. Das alte
  M = 695 ms gilt nur für die IMX500 und ist kein Vorgabewert mehr.

## 3. Ernte-Ablauf, Profil, Fehlerbehandlung

### Profil v3

`SessionProfile` bekommt `PROFILE_SCHEMA_VERSION = 3` und einen Block
`camera`:

```json
"camera": {
  "model": "logitech_streamcam",
  "usb_id": "046d:0893",
  "device": "/dev/video8",
  "size": [1920, 1080],
  "fourcc": "YUYV",
  "fps": 30,
  "controls": {"focus_absolute": 48, "exposure_time_absolute": …,
               "white_balance_temperature": …, "gain": …}
}
```

Bei v3 gilt `scaler_crop = null`, `native_scale = 1.0` und
`min_native_dot_column_px = min_source_dot_column_px` (Bildpixel = native
Pixel, Zoom fest 100). `load` liest v2 und v3; v2 hat kein `camera`.

`harvest.py` gibt die Kameraeinstellungen des Profils an `sync-record`
weiter (`--camera-controls` als JSON oder Profilpfad) und lehnt
v2-Profile ab: „IMX500-Profil, Kamera außer Betrieb — neues Profil mit
harvest-setup anlegen".

`/dev/video8` ist nicht stabil über Neustarts: die Quelle sucht das Gerät
über die USB-ID (`/dev/v4l/by-id/…` bzw. sysfs) und prüft, dass der
gefundene Knoten zur Profil-USB-ID passt; `device` im Profil ist nur
Information.

### Ablauf für den Bediener

1. **`harvest-setup.py focus`** (neu): Fokus-Sweep über `focus_absolute`
   (grob, dann fein) mit Schärfemaß (Laplace-Varianz) im Bereich der
   Anzeige (`--hint-box` oder Bildmitte); Belichtung/Weißabgleich einmal
   auf Automatik einschwingen lassen, Werte zurücklesen, dann auf manuell
   mit genau diesen Werten einfrieren. Schreibt ein Einstellungs-JSON und
   ein Kontrollbild. Ersetzt den bisherigen Schärfemesser.
2. **`propose` / `confirm`** wie bisher; `propose` nimmt ein Kontrollbild mit
   den eingefrorenen Einstellungen auf, `confirm` übernimmt die
   Einstellungen ins Profil. Auflösungsschwelle 2,6 px je Punktspalte im
   Bild.
3. **`harvest.py`** wie bisher (sync-record + gate-label), ohne Budget.

### Fehlerbehandlung (ablehnen statt raten)

| Fall | Verhalten |
| --- | --- |
| Kamera fehlt / falsche USB-ID | Abbruch vor dem Start, Hinweis auf Gerätesuche |
| zurückgelesener Steuerwert weicht ab | Abbruch mit Name, Soll, Ist |
| tatsächliche Größe/FourCC weicht ab | Abbruch |
| USB2 statt USB3 | Warnung in `session.json`; `camera-commissioning.sh` meldet es |
| 2 s kein Bild mitten in der Aufnahme | sauberer Abschluss mit `acquisition_error`, korrekter Bildzähler |
| Zeitstempel 0 / nicht monoton | Bild verworfen, gezählt in `session.json` |

Der bekannte Fehler „`frames_recorded` = 0 nach Ausfall trotz
geschriebener Bilder" wird dabei behoben und mit einem Test festgehalten.

## 4. Tests

Alle ohne Kamera (Attrappe hinter der Fassade), außer einem
`@hardware`-Test.

* `UvcSource`: Steuerwerte setzen und zurücklesen, Abweichung → Abbruch;
  Reihenfolge Automatik-aus vor Absolutwert; Zeitbasis `v4l2_monotonic`;
  falsche Größe → Abbruch; Zeitstempel 0 / rückläufig → verworfen und
  gezählt.
* `to_boottime_ns`: Umrechnung; Suspend-Fall → Ablehnung; fehlender Versatz
  → Ablehnung; unbekannte Basis → Ablehnung; `sensor_boottime` unverändert.
* `gate-label`, `display-offset`, `import-harvest` mit einer synthetischen
  StreamCam-Session; bestehende IMX500-Session-Tests liefern unverändert
  dasselbe (Regression).
* `sync-record`: `frame_gaps`, Versatzmessung in `session.json`,
  `frames_recorded` nach Ausfall mitten in der Aufnahme.
* `SessionProfile`: v3 speichern/laden; v2 lesbar; v1 abgewiesen.
* `harvest.py`: verweigert v2-Profil; verweigert Start ohne bzw. mit
  unpassender Timing-Datei; gibt Kameraeinstellungen an `sync-record`
  weiter.
* `frames`: `picamera2://`/`imx500://` → klare Außer-Betrieb-Meldung;
  `v4l2://`-Parsing.
* `@hardware`: StreamCam öffnen, 30 Bilder, Steuerung zurücklesen,
  Zeitstempel monoton.

## 5. Doku (Controller, nicht Subagenten)

* Entscheidung „StreamCam statt IMX500" in `docs/project_history.md`
  (Problem / Entscheidung / verworfene Alternativen, AGENTS.md), in
  Konzept.md als Abweichung vermerkt (Kamera im Hardwareteil). Begründung: OQ-22-Wedge beim
  Streamstart, Ausfall mitten im Stream nach mechanischer Handhabung,
  Fokus per Software, AI-Funktionen der IMX500 werden nicht genutzt.
* CLAUDE.md: „Was dieses Projekt ist", „Aufbau" (`v4l2://` fertig,
  `picamera2://`/`imx500://` außer Betrieb), „Erwartete Zustände" und
  „Hardware-Fakten" mit StreamCam-Teil; IMX500-Fakten als „historisch,
  außer Betrieb" gekennzeichnet.
* OQ-22: Nachtrag „für den Betrieb gegenstandslos" inkl. Ausfall mitten im
  Stream. Neue OQ: Zeitstempel-Semantik der UVC-Kamera (Belichtung vs.
  Pufferempfang), durch die Timing-Kalibrierung empirisch abgedeckt.
* TODO, status, CHANGELOG, VALIDATION (StreamCam-Test und
  Timing-Kalibrierung), ROADMAP, Memory (`camera_service_idea`,
  `oq22_hardware_risk` als historisch).

## 6. Reihenfolge

1. `TimeBaseKind.V4L2_MONOTONIC`, `to_boottime_ns`, Umstellung der drei
   Auswerter.
2. `UvcSource`, Registry; `picamera2://`/`imx500://` raus.
3. `sync-record`: StreamCam-Zweig, IMX500-Zweig und Budget raus,
   `frame_gaps`, Versatzmessung, Bildzähler-Fehler.
4. Profil v3, `harvest-setup focus`, `propose`/`confirm` ohne Crop.
5. `harvest.py`: Timing-Datei, Kameraeinstellungen aus dem Profil.
6. Werkbank-Kamera deaktivieren, `camera-commissioning.sh` neu.
7. Messsitzung mit dem Nutzer (Timing-Kalibrierung), danach Ernten.
