# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Einstiegsreihenfolge (verbindlich)

1. [docs/status.md](docs/status.md) — aktueller Stand, Blocker, nächste Schritte
2. [docs/open-questions.md](docs/open-questions.md) — was offen ist und warum
3. [AGENTS.md](AGENTS.md) — verbindliche Daueranweisungen, inkl. Doku-Pflicht
4. [Konzept.md](Konzept.md) — **autoritativ** für alle Anforderungen (deutsch)
5. [CHANGELOG.md](CHANGELOG.md) — die letzten drei Einträge

Die Doku-Pflicht steht in `AGENTS.md` und wird hier absichtlich **nicht**
dupliziert, damit sie nicht auseinanderläuft.

## Befehle

```bash
./.venv/bin/pytest -q                          # Mock-Tests, kein Hardwarebedarf
./.venv/bin/pytest -q --mode=real              # zusätzlich @hardware und @serial
./.venv/bin/ruff check src tests examples
./scripts/camera-commissioning.sh              # Kamera-Diagnose, Exit 0 = einsatzbereit
./.venv/bin/python examples/16_end_to_end_headless.py   # ganze Kette ohne Hardware
```

Einrichtung von Null (die Flags sind nicht optional, siehe `AGENTS.md`):

```bash
python3 -m venv --system-site-packages .venv
./.venv/bin/pip install --no-deps -e .
./.venv/bin/pip install pytest ruff
```

## Was dieses Projekt ist

Ein Raspberry Pi 5 mit Raspberry Pi AI Camera (Sony IMX500) liest die Anzeigen
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
frames/    Bildquelle      synthetic:// [fertig] · picamera2:// imx500:// folder://
                           video:// replay:// [nur Registry-Eintrag, TODO]
detect/    Anzeige finden  manual_roi [fertig, PRIMÄRPFAD]
                           contour_heuristic · imx500_detector [TODO]
rectify    Entzerren       OpenCV-Vierpunkt + optional CLAHE [fertig]
ocr/       Wert lesen      sevenseg mit Per-Segment-Evidenz [fertig]
                           tesseract_cli [TODO, braucht OQ-15]
validate   Freigabe        Syntax-, Qualitäts- und Zustandsregeln (§7) [fertig]
sink/      Ausgabe         jsonl (Audit) · serial_out · protocol/ascii_csv [fertig]
                           protocol/gsv_ascii [wirft absichtlich, OQ-07]
pipeline   verdrahtet alles und führt den PipelineTrace mit [fertig]
records    ValueRecord (§8), Timestamp, TxReceipt — der stabile Vertrag [fertig]
layout     Ziffernraster, kommt im Betrieb aus dem bestätigten Profil (§4) [fertig]
```

`open_source()` kennt alle sechs URI-Schemata, aber nur `synthetic://` hat eine
Implementierung — die übrigen scheitern mit `ImportError`. Was fertig ist und
was nicht, führt [docs/ROADMAP.md](docs/ROADMAP.md) unter P0.

Zentrale Verträge in [src/dispread/records.py](src/dispread/records.py):
`ValueRecord` mit genau den neun Feldern aus Konzept §8, `status` als
`VALID | TRANSITION | UNREADABLE | STALE`.

## Erwartete Zustände, die keine Bugs sind

* **Ohne angeschlossene Kamera:** `Picamera2.global_camera_info()` liefert `[]`
  und `IMX500(...)` wirft `RuntimeError: IMX500: Requested camera dev-node not
  found`. Der reine Import von `picamera2`/`IMX500` funktioniert trotzdem.
* **`dtoverlay -l` meldet `No overlays loaded`, obwohl die Kamera läuft.**
  `camera_auto_detect` wird von der Firmware beim Booten angewandt und
  erscheint dort nicht. Nachweis ist der Sensorknoten im Device-Tree plus die
  libcamera-Enumeration.
* **`camera_auto_detect` greift nur beim Booten.** Nach dem Anstecken der
  Kamera ist ein Reboot nötig.

Neue Funktionalität muss über `folder://`, `synthetic://` oder `replay://`
testbar sein — `picamera2` wird nur in den beiden Kameramodulen importiert, und
zwar lazy in der Factory. Das ist die Voraussetzung dafür, dass Tests ohne
Kamera laufen.

## Hardware-Fakten, die man leicht falsch annimmt

* Datenport für GSVmulti ist **`/dev/ttyAMA0`**. `/dev/serial0` zeigt auf
  `ttyAMA10` und ist der **3-Pin-Debug-Header**, nicht der Nutzdatenport.
* Pi-GPIO-Pegel dürfen **nicht** direkt mit RS-232 verbunden werden
  ([OQ-09](docs/open-questions.md)).
* Die 23 `.rpk` unter `/usr/share/imx500-models/` sind **COCO-/ImageNet-Modelle**
  (`person`, `bicycle`, `tv`). Für Messverstärker-Displays taugen sie nicht —
  deshalb ist die bestätigte manuelle ROI der Primärpfad.
* IMX500-Warmlauf beim ersten `.rpk`-Upload: **6,8 s** gemessen. Der
  *Converter* für eigene Modelle fehlt auf dem Pi, nur der *Packager* ist da.
* `SensorTimestamp` liegt in der **CLOCK_BOOTTIME**-Domäne (gemessen). Die
  *Semantik* — Belichtungsbeginn oder Auslese-Ende — ist noch offen (Messung M2
  in [docs/TIMING.md](docs/TIMING.md)).

## Nicht verhandelbar

Siehe [AGENTS.md](AGENTS.md). Kurz: veraltete Werte nie unmarkiert
weiterführen, den Referenzwert nie zur Korrektur des DUT-Werts benutzen, echte
Sprünge nicht glätten, Konfidenz ist keine Fehlerwahrscheinlichkeit, Unlesbares
ablehnen statt raten — und **kein Erfinden von Protokollen**.
