# Dokumentationsübersicht

Die [Startseite](../index.md) führt zu den veröffentlichten Seiten.
Für Inbetriebnahme und Wartung siehe [Installation und Verwaltung](INSTALLER.md).
[Messpfad und Freigabe](uebersicht/messpfad.md),
[Zeitstempel richtig lesen](uebersicht/zeitstempel.md) und
[Daten und Abnahme](uebersicht/daten-und-abnahme.md) erklären den Messbetrieb.

Der [Wiki-Abgleich vom 2026-10-21](wiki-audit-2026-10-21.md) hält Prüfung,
Korrekturen und offene Befunde für alle 52 Navigationsseiten fest.

## Selbst programmieren

| Dokument | Inhalt |
| --- | --- |
| [anleitung/README.md](anleitung/README.md) | **Lernpfad in zwölf Kapiteln (0–11):** aktuelle Trennstellen, ausführbare Beispiele, geplante Erweiterungen und geführter Sammelmodus. Der jeweilige Kapitelstatus trennt Vorhandenes von Bauaufgaben |
| [anleitung/02-vertraege.md](anleitung/02-vertraege.md) | Alle Trennstellen und Datenklassen auf einer Seite |
| [anleitung/rezepte.md](anleitung/rezepte.md) | Codeschnipsel zum Kopieren |
| [anleitung/glossar.md](anleitung/glossar.md) | Fachbegriffe des Projekts |

## Immer zuerst

| Dokument | Inhalt |
| --- | --- |
| [status.md](status.md) | Veröffentlichte Versionen, Gerätebelege und Integrationsübergabe |
| [../TODO.md](../TODO.md) | Arbeitsreihenfolge und nächste Prüfungen |
| [open-questions.md](open-questions.md) | Offene Fragen und dokumentierte Antworten als `OQ-nn` |
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
| [FORTSCHRITT.md](FORTSCHRITT.md) | Interaktive Diagramme: Proben je Gruppe, Ernten, `loo`-Entwicklung, Abnahmen. Daten aus `docs-site/assets/data/fortschritt.json` |
| [VALIDATION.md](VALIDATION.md) | Fehlerklassen, Messreihen, Nachweise gegen die stillen Fehlermodi aus Konzept §7, Abnahmekriterien |

## Hardware und Aufbau

| Dokument | Inhalt |
| --- | --- |
| [HARDWARE_PROFILE.md](HARDWARE_PROFILE.md) | Rechner, Kamera, serielle Ports, Bootkonfiguration, Konfigurationsschlüssel |
| [CAMERA_COMMISSIONING.md](CAMERA_COMMISSIONING.md) | Checkliste und Fehlerbaum für die Inbetriebnahme |
| [OPTICAL_SETUP.md](OPTICAL_SETUP.md) | Halterung, Ziffernhöhe, Beleuchtung, Reflexionen (Konzept §9) |
| [DISPLAYBUS_TAP.md](DISPLAYBUS_TAP.md) | Konzeptskizze: passiver Mitleser am HD44780-Displaybus als Rückfallebene (nicht gebaut); aktives Auto-Labeling nutzt die serielle GSV-2AS-Schnittstelle ([OQ-38](open-questions.md#oq-38)) |

## Schnittstellen

| Dokument | Inhalt |
| --- | --- |
| [GSVMULTI_PROTOCOL.md](GSVMULTI_PROTOCOL.md) | Ausgabewege, UserDefined-Formate und Prüfbelege |
| [BRIDGE_PROTOCOL_V2.md](BRIDGE_PROTOCOL_V2.md) | Nachrichten und Transport zwischen Pi und Windows-Brücke |
| [HOSTING.md](HOSTING.md) | Geschütztes Doku-Hosting, Build, Runner und Pflege |
| [dependencies.md](dependencies.md) | Jede Abhängigkeit mit Begründung, inkl. der `--system-site-packages`/`--no-deps`-Regel |

## Außerhalb von docs/

| Dokument | Inhalt |
| --- | --- |
| [../Konzept.md](../Konzept.md) | **Autoritativ** für alle Anforderungen |
| [../AGENTS.md](../AGENTS.md) | Verbindliche Daueranweisungen, inkl. Doku-Pflicht |
| [../CLAUDE.md](../CLAUDE.md) | Einstieg für Claude Code |
