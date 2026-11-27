# Dokumentationsübersicht

## Direkt zur passenden Anleitung

| Was möchtest du tun? | Einstieg |
| --- | --- |
| **Einen Pi erstmals einrichten** | [Installation in einer Zeile](INSTALLER.md#installation-in-einer-zeile) · [Timing kalibrieren](INSTALLER.md#timing-kalibrieren) |
| **Anzeige bestätigen und ersten Lauf starten** | [Anzeige einrichten](anleitung/10-kamera-livevorschau.md#anzeige-einrichten) · [Lauf und Wertstatus](anleitung/10-kamera-livevorschau.md#lauf-und-wertstatus) |
| **Einen neuen Sensor hinzufügen** | [Assistent in der Konsole](SENSOR_PACKAGES.md#neuen-sensor-hinzufuegen) · [Paketformat und Grenzen](SENSOR_PACKAGES.md) |
| **Eine Meldung einordnen** | [Typische Werkbank-Fehler](anleitung/10-kamera-livevorschau.md#typische-fehler) · [Kamera-Inbetriebnahme](CAMERA_COMMISSIONING.md) |
| **Messwerte in GSVmulti übertragen** | [Ausgabewege](GSVMULTI_PROTOCOL.md#ausgabewege) · [Windows-Brücke einrichten](GSVMULTI_PROTOCOL.md#gsvmulti-start) |
| **Ergebnisse prüfen** | [Laufdateien](anleitung/10-kamera-livevorschau.md#dateien-und-lokale-bedienung) · [Session-Explorer](session-explorer.md) · [Zeitstempel](uebersicht/zeitstempel.md) |
| **Einen vorhandenen Pi verwalten** | [Dienst und Diagnose](anleitung/09-betrieb.md) · [Update und Rückweg](INSTALLER.md#update-auf-die-neueste-version) |

[Glossar](anleitung/glossar.md) · [Aktueller Stand](status.md) · [Offene Fragen](open-questions.md)

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
| [Wiki-Abgleich vom 21.10.2026](wiki-audit-2026-10-21.md) | Prüfung und Korrekturen der damaligen Navigationsseiten |

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
