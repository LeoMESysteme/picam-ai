# picam-ai · dispread

Optische Auslesung von Messverstärkeranzeigen im Kalibrierlabor. Die aktive
Kamera ist seit 2026-09-25 eine **Logitech StreamCam (UVC)**. Die zuvor
verwendete IMX500 ist außer Betrieb. Erkannte Werte werden mit Zeitbasis,
Freigabestatus und Begründung dokumentiert. Die echte GSVmulti-Anbindung ist
wegen der fehlenden Telegrammspezifikation offen
([OQ-07](docs/open-questions.md#oq-07)).

**Neu hier?** [Aktueller Stand](docs/status.md) →
[Verarbeitungskette](docs/anleitung/01-kette-verstehen.md) →
[Messpfad und Freigabe](docs/uebersicht/messpfad.md).
[Konzept.md](Konzept.md) ist für Anforderungen maßgeblich. Die
[Roadmap](docs/ROADMAP.md) zeigt den Umsetzungsstand; die
[API-Referenz](api/index.md) beschreibt den aktuellen Code.

## Nach Aufgabe einsteigen

| Aufgabe | Einstieg | Vertiefung |
| --- | --- | --- |
| Projektstand verstehen | [Status](docs/status.md) | [Roadmap](docs/ROADMAP.md), [Arbeitsliste](TODO.md) |
| Messpfad verstehen oder erweitern | [Lernpfad](docs/anleitung/README.md) | [Messpfad](docs/uebersicht/messpfad.md), [Verträge](docs/anleitung/02-vertraege.md) |
| Kamera und Anzeige einrichten | [Livevorschau](docs/anleitung/10-kamera-livevorschau.md) | [Kamera-Inbetriebnahme](docs/CAMERA_COMMISSIONING.md), [Optik](docs/OPTICAL_SETUP.md) |
| Daten sammeln und Ergebnisse bewerten | [Sammelmodus](docs/anleitung/11-datensatz-sammeln.md) | [Daten und Abnahme](docs/uebersicht/daten-und-abnahme.md), [Validierung](docs/VALIDATION.md) |
| Zeitstempel und Latenz einordnen | [Zeitstempel](docs/uebersicht/zeitstempel.md) | [Zeitmessungen](docs/TIMING.md) |
| Eine unbekannte Frage klären | [Offene Punkte](docs/open-questions.md) | [Laborjournal](docs/lab_journal.md), [Projektgeschichte](docs/project_history.md) |

## Alle Seiten

Die Tabellen sind zugleich ein vollständiges Verzeichnis der linken
Seitennavigation. Jede Seite ist von dieser Startseite direkt verlinkt.
Die [Dokumentationsübersicht](docs/README.md) erklärt die Rolle der Quellen.

### Projekt und Entscheidungen

| Seite | Inhalt |
| --- | --- |
| [Konzept](Konzept.md) | Anforderungen und Sicherheitsregeln |
| [Aktueller Stand](docs/status.md) | aktueller Arbeitsstand |
| [Arbeitsliste](TODO.md) | aktive Aufgaben |
| [Roadmap](docs/ROADMAP.md) | Phasen und Exit-Kriterien |
| [Geplante Features](PLANNED_FEATURES.md) | vorgesehene Funktionen |
| [Changelog](CHANGELOG.md) | Änderungshistorie |
| [Offene Punkte](docs/open-questions.md) | Fragen mit Zuständigkeit und Zielort |
| [Projektgeschichte](docs/project_history.md) | Entscheidungen und Alternativen |
| [Werkzeugrecherche](docs/tool_review_2026-09-08.md) | technische Abwägungen |

### Lernpfad und Nachschlagen

| Seite | Inhalt |
| --- | --- |
| [Anleitung](docs/anleitung/README.md) | Lernreihenfolge und Kapitelstatus |
| [0 · Werkzeuge](docs/anleitung/00-werkzeuge.md) | venv, Tests, Arbeitsrhythmus |
| [1 · Kette verstehen](docs/anleitung/01-kette-verstehen.md) | ein Frame durch alle Stufen |
| [2 · Verträge](docs/anleitung/02-vertraege.md) | Schnittstellen und Datenklassen |
| [3 · Bildquelle](docs/anleitung/03-erste-bildquelle-folder.md) | eigene Bildquelle bauen |
| [4 · Geräteprofile](docs/anleitung/04-geraeteprofile.md) | Layout und ROI |
| [5 · CLI](docs/anleitung/05-cli.md) | geplanter Pipeline-Aufruf |
| [6 · Aufnahme und Replay](docs/anleitung/06-kamera-aufnahme-replay.md) | Frames aufzeichnen und wiedergeben |
| [7 · Lokalisierung](docs/anleitung/07-lokalisierung.md) | Anzeige finden und verfolgen |
| [8 · OCR-Backends](docs/anleitung/08-ocr-backends.md) | Leser vergleichen |
| [9 · Betrieb](docs/anleitung/09-betrieb.md) | geplanter Dienst und Dauerlauf |
| [Kamera-Livevorschau](docs/anleitung/10-kamera-livevorschau.md) | Workbench bedienen |
| [Datensatz sammeln](docs/anleitung/11-datensatz-sammeln.md) | geführter Sammelmodus |
| [Rezepte](docs/anleitung/rezepte.md) | kurze ausführbare Beispiele |
| [Glossar](docs/anleitung/glossar.md) | Fachbegriffe |
| [Messpfad und Freigabe](docs/uebersicht/messpfad.md) | Entscheidungen je Frame |
| [Zeitstempel lesen](docs/uebersicht/zeitstempel.md) | Zeitbasen und zulässige Schlüsse |
| [Daten und Abnahme](docs/uebersicht/daten-und-abnahme.md) | Splits, Evidenz und Kennzahlen |

### Betrieb und Hardware

| Seite | Inhalt |
| --- | --- |
| [Kamera-Inbetriebnahme](docs/CAMERA_COMMISSIONING.md) | Diagnose und Fehlerbaum |
| [Hardwareprofil](docs/HARDWARE_PROFILE.md) | Rechner, Ports, Konfiguration |
| [Optischer Aufbau](docs/OPTICAL_SETUP.md) | Halterung, Licht, Reflexionen |
| [Displaybus-Abgriff](docs/DISPLAYBUS_TAP.md) | Konzept einer Sollwertquelle |
| [GSVmulti-Protokoll](docs/GSVMULTI_PROTOCOL.md) | bekannte und offene Formatfragen |
| [Abhängigkeiten](docs/dependencies.md) | Systempakete und Projekt-venv |
| [Doku-Hosting](docs/HOSTING.md) | Build, Runner und Veröffentlichung |

### Messungen

| Seite | Inhalt |
| --- | --- |
| [Fortschritt Ernten/Training](docs/FORTSCHRITT.md) | interaktive Diagramme |
| [Validierung](docs/VALIDATION.md) | Zahlen und Fehlerklassen |
| [Zeitverhalten](docs/TIMING.md) | M1–M8 und Unsicherheitsbudget |
| [Laborjournal](docs/lab_journal.md) | Aufbau, Beobachtung und Deutung |

### API und Projektregeln

| Seite | Inhalt |
| --- | --- |
| [API-Überblick](api/index.md) | Einstieg in die Docstrings |
| [Verträge und Datensätze](api/vertraege.md) | Record, Zeitstempel, Profile |
| [Bildquellen](api/frames.md) | Quellen und Frames |
| [Anzeige finden](api/detect.md) | Lokalisierung |
| [Geometrie](api/geometrie.md) | Nachführung und Entzerrung |
| [OCR](api/ocr.md) | Leser und Leseergebnisse |
| [Freigabe](api/validate.md) | Gate-Entscheidungen |
| [Ausgabe](api/sink.md) | JSONL, seriell, Formatter |
| [Pipeline](api/pipeline.md) | Verdrahtung und Trace |
| [Workbench](api/workbench.md) | Bedienoberfläche |
| [AGENTS.md](AGENTS.md) | verbindliche Projektregeln |
| [CLAUDE.md](CLAUDE.md) | ergänzender Entwicklerkontext |

## Lokal arbeiten

Die Projekt-venv nutzt Debian-Pakete mit system-site-packages; das Paket
wird mit no-deps installiert. Einzelheiten stehen in
[Abhängigkeiten](docs/dependencies.md). Das End-to-End-Beispiel läuft ohne
Hardware und liefert **keine** reale Latenzaussage
([Zeitstempel](docs/uebersicht/zeitstempel.md)).

    python3 -m venv --system-site-packages .venv
    ./.venv/bin/pip install --no-deps -e .
    ./.venv/bin/pytest -q
    ./.venv/bin/ruff check src tests examples
    ./.venv/bin/python examples/16_end_to_end_headless.py
