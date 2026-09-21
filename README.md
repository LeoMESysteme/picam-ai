# picam-ai (dispread)

Ein Raspberry Pi 5 mit Raspberry Pi AI Camera (Sony IMX500) liest die Anzeigen
wechselnder Messverstärker (GSV-2ASD, GSV-2MSD-DI, GSV-2TSD-DI, AST-Geräte)
optisch aus und überträgt die Werte zeitgestempelt über eine serielle
Schnittstelle an **GSVmulti**. Einsatz im Kalibrierlabor; Prüfling und Referenz
müssen zeitlich zugeordnet werden können.

Ausführliche Projektdokumentation: [CLAUDE.md](CLAUDE.md) (Einstiegspunkt für
Entwickler und Agenten), [Konzept.md](Konzept.md) (autoritative Anforderungen)
und [docs/status.md](docs/status.md) (aktueller Stand).

## Installation

Voraussetzung: Python 3 mit systemweitem Zugriff auf `picamera2` (auf dem
Raspberry Pi bereits vorhanden). Die Flags unten sind nicht optional — siehe
[AGENTS.md](AGENTS.md) für die Begründung.

```bash
python3 -m venv --system-site-packages .venv
./.venv/bin/pip install --no-deps -e .
./.venv/bin/pip install pytest ruff
```

## Test

```bash
./.venv/bin/pytest -q                          # Mock-Tests, kein Hardwarebedarf
./.venv/bin/pytest -q --mode=real              # zusätzlich @hardware und @serial
./.venv/bin/ruff check src tests examples
```

## Run

```bash
./scripts/camera-commissioning.sh                       # Kamera-Diagnose, Exit 0 = einsatzbereit
./.venv/bin/python examples/16_end_to_end_headless.py    # ganze Kette ohne Hardware
```

## Usage

Der primäre Erkennungspfad ist eine bedienergeführt bestätigte ROI
(`detect/manual_roi`) — siehe [Konzept.md](Konzept.md) §3 für die vollständige
Verarbeitungskette (frames → detect → rectify → track → ocr → validate →
sink). Für einen schrittweisen Einstieg als Entwickler siehe den Lernpfad
unter [docs/anleitung/](docs/anleitung/README.md).
