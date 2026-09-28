# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Einstiegsreihenfolge (verbindlich)

0. [TODO.md](TODO.md) — **die Arbeitsliste**: was als nächstes ansteht, mit
   genug Kontext zum Wiedereinstieg ohne Recherche. Wenn dort ein Blocker
   ganz oben steht (z. B. „Pi braucht einen Reboot"), gilt der zuerst.
1. [docs/status.md](docs/status.md) — aktueller Stand, Blocker, nächste Schritte
2. [docs/open-questions.md](docs/open-questions.md) — **nur die Übersichtstabelle
   oben** (zwischen `OQ-INDEX`-Markern, ≈ 3,5 KB; die ganze Datei hat > 100 KB).
   Einzelne Einträge gezielt öffnen: `grep -n '^## OQ-22' docs/open-questions.md`
   und ab dieser Zeile lesen
3. [AGENTS.md](AGENTS.md) — verbindliche Daueranweisungen, inkl. Doku-Pflicht
4. [Konzept.md](Konzept.md) — **autoritativ** für alle Anforderungen (deutsch).
   Vor jeder Änderung am Messpfad oder an Verhalten lesen, für reine Doku- und
   Werkzeugaufgaben nicht nötig
5. [CHANGELOG.md](CHANGELOG.md) — nur der oberste Eintrag (mit Zeilenlimit
   lesen, die Datei hat > 150 KB). Ältere Einträge über `grep -n '^## ' CHANGELOG.md`

Die Doku-Pflicht steht in `AGENTS.md` und wird hier absichtlich **nicht**
dupliziert, damit sie nicht auseinanderläuft.

## Arbeitsweise für Agents

* **Prozess-Skills** (Brainstorming, Pläne, subagentengetriebene Umsetzung mit
  Reviews) nur für mehrstufige Features. Kleine Fixes, Doku-Nachträge,
  Diagnosen und Fragen werden direkt erledigt, ohne diesen Ablauf.
* **Suchen:** gezielt mit `grep` und `Read`. Breite Suchen über viele Dateien
  gehen an einen Explore-Subagenten, damit die Dateiinhalte nicht im
  Hauptkontext landen.
* **Repowise:** Bash-Ausgaben von Tests, Lint und `git log` werden automatisch
  gekürzt. Ein Marker `[repowise#<ref>: …]` lässt sich **im Repo-Verzeichnis**
  mit `repowise expand <ref>` zurückholen. `grep`, `git diff` und `ls` bleiben
  absichtlich ungekürzt. Die MCP-Tools (`get_risk`, `get_health`, `get_why`)
  nur bei ausdrücklichem Bedarf; `get_answer` ist abgeschaltet, weil es ein
  LLM-Umweg ist.

Für den menschlichen Entwickler liegt unter
[docs/anleitung/](docs/anleitung/README.md) ein Lernpfad, der die offenen
P0-Punkte als Schritt-für-Schritt-Aufgaben führt (Gerüst, Test, Fallen).
Wird Code aus einem dieser Kapitel gebaut, gehört das Kapitel mit
aktualisiert — insbesondere seine „Fertig, wenn"-Checkliste.

## Befehle

```bash
./.venv/bin/pytest -q                          # Mock-Tests, kein Hardwarebedarf
./.venv/bin/pytest -q --mode=real              # zusätzlich @hardware und @serial
./.venv/bin/ruff check src tests examples
./scripts/camera-commissioning.sh              # StreamCam-Diagnose, Exit 0 = einsatzbereit
./.venv/bin/python examples/16_end_to_end_headless.py   # ganze Kette ohne Hardware
```

Einrichtung von Null (die Flags sind nicht optional, siehe `AGENTS.md`):

```bash
python3 -m venv --system-site-packages .venv
./.venv/bin/pip install --no-deps -e .
./.venv/bin/pip install pytest ruff
```

## Was dieses Projekt ist

Ein Raspberry Pi 5 mit einer **Logitech StreamCam** (USB 3, UVC, `046d:0893`;
seit 2026-09-25, vorher Raspberry Pi AI Camera / Sony IMX500, siehe
[docs/project_history.md](docs/project_history.md)) liest die Anzeigen
wechselnder Messverstärker (GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI, AST-Geräte)
optisch aus und überträgt die Werte zeitgestempelt über eine serielle
Schnittstelle an **GSVmulti**. Einsatz im Kalibrierlabor; Prüfling und Referenz
müssen zeitlich zugeordnet werden können.

Große Sprachmodelle oder generative KI sind für den laufenden Messpfad
ausdrücklich **nicht** vorgesehen — es ist eine CV-/OCR-Kette mit klassischer
Regelprüfung, bedienergeführt.

## Aufbau

Die Verarbeitungskette aus Konzept.md §3, jede Stufe eine austauschbare
Trennstelle:

```
frames/    Bildquelle      v4l2:// [fertig, StreamCam, UvcSource] ·
                           synthetic:// [fertig] · replay:// [fertig, Clips mit
                           einem Label je Clip] · folder:// video://
                           [Registry-Eintrag] · picamera2:// imx500://
                           [außer Betrieb seit 2026-09-25, gezielte Fehlermeldung]
detect/    Anzeige finden  manual_roi [fertig, PRIMÄRPFAD]
                           contour_heuristic [TODO] · imx500_detector
                           [außer Betrieb mit der IMX500]
track      Nachführen      QuadTracker, begrenzte ECC-Nachregistrierung eines
                           bestätigten Quads gegen die Bestätigungsreferenz —
                           korrigiert das Quad, bevor damit entzerrt wird
                           [fertig]
rectify    Entzerren       OpenCV-Vierpunkt + optional CLAHE [fertig]
ocr/       Wert lesen      sevenseg mit Per-Segment-Evidenz [fertig]
                           tesseract_cli [gebaut, fuer dot-matrix-/Zeichen-
                           LCDs wie GSV-Sensor; lehnt bisher alle 11 echten
                           GSV-Proben ab (0/11 liefern einen Wert) — nie
                           falsch, aber Erkennungsguete noch nicht erreicht]
validate   Freigabe        Syntax-, Qualitäts- und Zustandsregeln (§7) [fertig]
sink/      Ausgabe         jsonl (Audit) · serial_out · protocol/ascii_csv [fertig]
                           protocol/gsv_ascii [wirft absichtlich, OQ-07]
pipeline   verdrahtet alles und führt den PipelineTrace mit [fertig]
records    ValueRecord (§8), Timestamp, TxReceipt — der stabile Vertrag [fertig]
layout     Ziffernraster, kommt im Betrieb aus dem bestätigten Profil (§4) [fertig]
```

`open_source()` kennt `v4l2`, `synthetic`, `replay`, `folder` und `video`;
`picamera2://` und `imx500://` enden mit einer gezielten `ValueError`
(„IMX500 außer Betrieb"). Was fertig ist und was nicht, führt
[docs/ROADMAP.md](docs/ROADMAP.md) unter P0.

**Zeitbasis der Kamera:** StreamCam-Bilder tragen den V4L2-Pufferzeitstempel
in CLOCK_MONOTONIC (`TimeBaseKind.V4L2_MONOTONIC`, Semantik offen, OQ-43).
Serielle Telegramme liegen in BOOTTIME. Verglichen wird nur über
`records.to_boottime_ns` mit dem in `session.json` gemessenen Versatz; fehlt
er, wird abgelehnt. Vor einer StreamCam-Ernte ist die Timing-Kalibrierung
Pflicht (`scripts/timing-calibration.py` →
`var/calibration/timing-streamcam.json`).

Zentrale Verträge in [src/dispread/records.py](src/dispread/records.py):
`ValueRecord` mit genau den neun Feldern aus Konzept §8, `status` als
`VALID | TRANSITION | UNREADABLE | STALE`.

## Erwartete Zustände, die keine Bugs sind

* **Die StreamCam hat zwei Knoten** (`index` 0 = Bilder, 1 = Metadaten), und
  die Nummer (`/dev/video0`, früher `/dev/video8`) wechselt je nach
  Steckreihenfolge. `find_uvc_device()` sucht über USB-ID und `index == 0`;
  keine Knotennummer fest eintragen.
* **Die Kamera der Werkbank (`dispread serve`) ist außer Betrieb**, bis die
  StreamCam dort angebunden ist; sie meldet „Kamera der Werkbank ausser
  Betrieb …". `--simulate` läuft.
* **Nur ein Prozess kann die StreamCam halten.** Ein zweiter bekommt
  „nicht zu öffnen (belegt?)".
* **Die StreamCam übernimmt Regler auch ohne laufenden Stream**, und
  `UvcSource` setzt sie bei jedem Öffnen neu. Nach einer Aufnahme stehen
  Autofokus und Automatiken deshalb aus.

*Historisch (IMX500, außer Betrieb):* Ohne angeschlossene Kamera liefert
`Picamera2.global_camera_info()` `[]`; `dtoverlay -l` meldet `No overlays
loaded`, obwohl die Kamera läuft; `camera_auto_detect` greift nur beim Booten.

Neue Funktionalität muss über `folder://`, `synthetic://` oder `replay://`
testbar sein. `cv2` wird für `v4l2://` erst in der Factory importiert, und
`UvcSource` nimmt Capture-Objekt und Regler-Funktionen injiziert entgegen.
`picamera2` wird nirgends mehr importiert. Das ist die Voraussetzung dafür,
dass Tests ohne Kamera laufen.

## Hardware-Fakten, die man leicht falsch annimmt

* Datenport für GSVmulti ist **`/dev/ttyAMA0`**. `/dev/serial0` zeigt auf
  `ttyAMA10` und ist der **3-Pin-Debug-Header**, nicht der Nutzdatenport.
* Pi-GPIO-Pegel dürfen **nicht** direkt mit RS-232 verbunden werden
  ([OQ-09](docs/open-questions.md)).
* **StreamCam:** 1920×1080 nur in YUYV an einem **USB3-Port** (blau); an USB2
  fällt sie auf kleinere Größen zurück, und `UvcSource` bricht ab. Fokus per
  Software, `focus_absolute` = 48 am GSV-Aufbau am besten; Regler werden
  über `v4l2-ctl` gesetzt, **Automatik zuerst aus, dann Absolutwert**. In
  einem gemeinsamen Aufruf schlägt `focus_absolute` bei noch aktivem
  Autofokus mit EIO fehl. Keine Treiber-Bildnummer (`CAP_PROP_POS_FRAMES` =
  -1), Aussetzer zeigt `frame_gaps` in `session.json`. `BOOTTIME −
  MONOTONIC` liegt ohne Suspend bei wenigen ns.
* *Historisch (IMX500):* Die 23 `.rpk` unter `/usr/share/imx500-models/` sind
  COCO-/ImageNet-Modelle, für Messverstärker-Displays untauglich; Warmlauf
  beim ersten `.rpk`-Upload 6,8 s; `SensorTimestamp` in CLOCK_BOOTTIME
  (gemessen, Semantik offen, M2 in [docs/TIMING.md](docs/TIMING.md));
  Streamstart-Wedge der RP2040-Brücke (OQ-22).
* **Die Anzeige des GSV-2AS ist über RS232 direkt steuerbar** — und das ist
  der Weg zu Ziffernvielfalt, nicht der Stimulus. `set norm` (16) skaliert
  die Anzeige (`Anzeige = Normierungsfaktor × Messwert`, Bereich
  0,15…1 580 000), `set dpoint` (17) setzt den Dezimalpunkt. Gemessen: der
  ASCII-Strom folgt der Normierung, und über 14 Faktoren von 1,0 bis 9000
  zeigt die Anzeige **ausnahmslos 6 Ziffern** — der Zahlenblock belegt immer
  genau 8 Zellen, der Punkt wandert. `EEnow = 0` an diesem Gerät: Schreib-
  befehle nutzen das EEPROM nicht ab. **Negative Normierung gibt es erst ab
  Firmware 1.5.06; dieses Gerät hat 1.3.07** — die Vorzeichenstelle bleibt
  damit unerreichbar.
* Registerantworten des GSV-2 tragen ein **Semikolon-Präfix `0x3B`**. Die
  Spalte „Länge der Befehlsantwort" der Anleitung zählt nur die Datenbytes —
  wer genau so viele Bytes liest, hält `0x3B` für den Registerwert.
  `scripts/gsv-registers.py` macht es richtig.
* Die Anzeige des GSV-Sensors ist ein **Displaytech 161A** (von der Platine
  abgelesen): Punktraster-Zeichen-LCD mit **16 Zeichen × 1 Zeile**. Die
  Zellenzahl ist damit bekannt und keine Messgröße. Der Modultyp legt aber
  **nur die Geometrie** fest, nicht den Zeichensatz — der Controller
  (HD44780-kompatibel) kommt in ROM-Varianten mit unterschiedlichen
  Sonderzeichen. Bei Ziffern fällt eine falsch angenommene Variante nicht auf,
  erst bei `°`/`Ω`/`µ`.

## Nicht verhandelbar

Siehe [AGENTS.md](AGENTS.md). Kurz: veraltete Werte nie unmarkiert
weiterführen, den Referenzwert nie zur Korrektur des DUT-Werts benutzen, echte
Sprünge nicht glätten, Konfidenz ist keine Fehlerwahrscheinlichkeit, Unlesbares
ablehnen statt raten — und **kein Erfinden von Protokollen**.
