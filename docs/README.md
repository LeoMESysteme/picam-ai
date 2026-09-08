# Dokumentationsübersicht

## Selbst programmieren

| Dokument | Inhalt |
| --- | --- |
| [anleitung/README.md](anleitung/README.md) | **Lernpfad in zehn Kapiteln (0–9):** was als Nächstes gebaut wird, mit Gerüst, Test und Fallenliste je Aufgabe. Einstieg für Menschen, die selbst implementieren |
| [anleitung/02-vertraege.md](anleitung/02-vertraege.md) | Alle Trennstellen und Datenklassen auf einer Seite |
| [anleitung/rezepte.md](anleitung/rezepte.md) | Codeschnipsel zum Kopieren |
| [anleitung/glossar.md](anleitung/glossar.md) | Fachbegriffe des Projekts |

## Immer zuerst

| Dokument | Inhalt |
| --- | --- |
| [status.md](status.md) | Aktueller Stand, Blocker, nächste drei Schritte. Wird überschrieben, nicht angehängt |
| [open-questions.md](open-questions.md) | Alle Unbekannten als `OQ-nn`, mit Vorabdefault und Zuständigkeit |
| [ROADMAP.md](ROADMAP.md) | Phasen P0–P8 mit Exit-Kriterien und Risiken |

## Verlauf und Entscheidungen

| Dokument | Inhalt |
| --- | --- |
| [project_history.md](project_history.md) | Entscheidungen, die nicht aus dem Code ersichtlich sind: Problem / Entscheidung / Begründung / Alternativen / Konsequenz |
| [lab_journal.md](lab_journal.md) | Append-only Laborjournal: Aufbau, Beobachtung, Deutung je Experiment — auch die Fehlversuche |
| [../CHANGELOG.md](../CHANGELOG.md) | Nach außen sichtbare Änderungen |

## Messwerte

| Dokument | Inhalt |
| --- | --- |
| [TIMING.md](TIMING.md) | Zeitbezug: Messprogramm M1–M8, gemessene Werte, Unsicherheitsbudget. Enthält den Grundsatz „Latenz ist nicht Zeitunsicherheit" |
| [VALIDATION.md](VALIDATION.md) | Fehlerklassen, Messreihen, Nachweise gegen die stillen Fehlermodi aus Konzept §7, Abnahmekriterien |

## Hardware und Aufbau

| Dokument | Inhalt |
| --- | --- |
| [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) | Rechner, Kamera, serielle Ports, Bootkonfiguration, Konfigurationsschlüssel |
| [CAMERA_COMMISSIONING.md](CAMERA_COMMISSIONING.md) | Checkliste und Fehlerbaum für die Inbetriebnahme |
| [OPTICAL_SETUP.md](OPTICAL_SETUP.md) | Halterung, Ziffernhöhe, Beleuchtung, Reflexionen (Konzept §9) |

## Schnittstellen

| Dokument | Inhalt |
| --- | --- |
| [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md) | Was bekannt ist, was nicht, die Adapter-Naht, das provisorische Platzhalterformat |
| [dependencies.md](dependencies.md) | Jede Abhängigkeit mit Begründung, inkl. der `--system-site-packages`/`--no-deps`-Regel |

## Außerhalb von docs/

| Dokument | Inhalt |
| --- | --- |
| [../Konzept.md](../Konzept.md) | **Autoritativ** für alle Anforderungen |
| [../AGENTS.md](../AGENTS.md) | Verbindliche Daueranweisungen, inkl. Doku-Pflicht |
| [../CLAUDE.md](../CLAUDE.md) | Einstieg für Claude Code |
