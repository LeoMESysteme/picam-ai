# Session-Explorer: freigegebener Umsetzungsplan

Stand: 2026-10-28. Freigabe im Chat; umgesetzt auf `codex/session-explorer`.

## Verbindliche Grenzen

Alle abgeschlossenen Messpfad-Läufe, Daten und Metadaten ohne Diagnosebilder.
Bestehender Explorer eingebettet plus Vollansicht. Gesamtübersicht,
Entwicklung und Dateiliste; beide Gewichtungen, vergleichbare Läufe als
Vorgabe. Kein Eingriff in `src/dispread/`, Workbench, Geräte oder laufende
Messungen. Echte Importe nur ohne Workbench; keine neuen Zeitpläne.
Normale Builds brauchen keine Sessions. Veröffentlichungen nehmen bei
Importproblemen den letzten geprüften Snapshot, sonst einen Leerzustand.
Auth-Prüfungen bleiben hart. Builds und Browserabnahme erst nach bestätigter
Messpause. Vollständiger Auftrag und Entscheidungen stehen im Chat.

## Aufgaben

1. Export und Statistik: resumierbare Blöcke, SQLite für exakte Quantile,
   Gruppen, atomare Generationen, unveränderliches Archiv und Exportlock.
   Tests für Fortsetzung, Konsistenz, Gewichtungen und Fehlzustände.
2. Wiki: Gesamtwerte, Kalenderverläufe, Dateiliste, No-JS-Fassung;
   vorhandene HTML-Anwendung samt sicherem Manifestladen und Zeitregeln.
3. Veröffentlichung: optionalen Snapshot nach normalem Build einbinden;
   feste Exportanfrage und höchstens 15 s warten. Eigener Exportdienst,
   Installationsskript ohne Neustart bestehender Dienste. Kleine
   Integrationsfixtures anstelle echter Sessions für die Abnahme.
4. Dokumentation, unabhängiger Review und gezielte Tests; strenger Build
   und vollständige Doku-Browsertests in bestätigter Messpause.

## Präzisierungen

* Blockweise SHA-256-Prüfsummen plus Reihenfolge und Längen sichern die
  Originaldateien. Ein zusammengesetzter Hash wird nicht als SHA-256 der
  vollständigen Originaldatei bezeichnet. So bleibt auch Hashing innerhalb
  großer Dateien fortsetzbar.
* Die beiden Ansichten heißen „Jeder Lauf zählt gleich“ und „Alle Frames
  gemeinsam“. p95 der ersten Ansicht ist der Median der Session-p95;
  gepoolte Quantile stammen aus Einzelbeobachtungen.
* Der Exportdienst prüft vor jedem begrenzten Verarbeitungsschritt den
  Workbench-Prozessbestand. Das ist keine harte Echtzeit-Isolation; auf dem
  gemeinsamen Pi laufen Build und Abnahme weiterhin nur in Messpausen.
* Daten und erzeugte Seitenteile werden ausschließlich in Buildausgaben
  geschrieben; die vorhandenen Markdown-Symlinks werden nicht beschrieben.
