# Neue Aufstellung: Einrichtung 162902Z vom 2026-11-11

[Belegarchiv](setup-new-position-2026-11-11-162902.zip),
[SHA-256](setup-new-position-2026-11-11-162902.sha256),
[Übergabe an Claude](../superpowers/handoffs/2026-11-11-einrichtungsfehler-an-claude.md).
Auf Nutzerwunsch für spätere autonome Korrekturen ohne erhaltene
Kameraaufstellung gesichert. Kein neuer Setup- oder Messlauf ausgelöst.

## Beobachtung und Eingaben

Sitzung `live-20261111T162902Z`, laufender Dienst aus `bruecke-run` auf
`08ac9b9cc818c013de10e6cee6579d372607d59e`. Beim ersten lesenden Statusabruf
lief die Rastersuche noch; beim eigentlichen Dateischnappschuss war die
Einrichtung mit `keine_startlage` beendet. Alle drei Versuche tragen diesen
Fit-Grund. Über die serielle Auditquelle protokollierte Zellentexte:
`+0.69551 `, `+0.69550 `, `+0.69551 `. Der Rasterfinder erhält diese Texte
nicht als Korrekturvorgabe. Der zweite Textversuch wurde wegen einer Änderung
während der Aufnahme wiederholt.

Fokusziel 46, beste gemessene Schärfe 174,9093, Endprüfung 173,1235.
Belichtung zunächst 200, danach 300; Verstärkung 14, Weißabgleich 4730.
Dies sind gespeicherte Kamera-Reglerwerte, keine aus Dateizeitstempeln
abgeleiteten physikalischen Belichtungszeiten.

## Zusätzlicher Fokusbefund

Das erhaltene Bild ist 1920 × 1080 groß. Die automatisch gefundene grüne
Hinweisbox liegt ungefähr bei x=538,3, y=144,6, Breite=800,4, Höhe=110,0 px.
Das berichtete Fokusfenster liegt bei x=640, y=360, Breite=640, Höhe=360 px.
Die beiden Rechtecke überschneiden sich nicht. Auch die Bildsichtung zeigt
die LCD-Anzeige oberhalb dieses Fokusfensters. Die erfolgreiche Fokusprüfung
belegt damit hier nicht unmittelbar die Schärfe der LCD-Zeichen. Ein Bild
aus dem Zeitpunkt der Fokusmessung fehlt; die unveränderte Anordnung über
diese Zeitspanne ist dadurch nicht unabhängig belegt.

Die Grünkontur ist keine unabhängig annotierte Ground Truth. Ob dieser
Befund die Rasterablehnung verursacht, ist nicht bewiesen. Für eine
Korrektur sowohl Rasterstart [OQ-69](../open-questions.md#oq-69) als auch
Fokusführung [OQ-74](../open-questions.md#oq-74) berücksichtigen, statt
unbelegt eine einzige Ursache festzuschreiben.

## Gesicherte Dateien

Das ZIP enthält `setup-new-position-live-20261111T162902Z/`:

* `setup/`: unveränderte Originale `still.png`, `camera-settings.json`,
  `cell-text.json` und `failure.json`.
* `versions/`, `observations.json`, `status-latest.json`: die bei der Sicherung
  beobachteten Dateiversionen und der Status einschließlich Kamera-Rückmeldung,
  Fokusproben, Belichtungsrunden und Einrichtungsfortschritt. Hier entstand
  nur ein abgeschlossener Dateischnappschuss; frühere Bilder werden nicht
  als gesichert behauptet.
* `image-analysis.json`: Bildhash, Hinweisbox, Fokusfenster, Schnittfläche 0
  und Grenzen der daraus möglichen Aussagen.
* `source-08ac9b9.tar.gz`, `environment.json`, `runtime-module-resolution.json`:
  eingefrorene Quellen/Tests/Skripte, Laufzeitumgebung und geprüfte Importpfade.
  Der relevante Betriebsquellbaum war unverändert. Der Prozess arbeitet
  tatsächlich mit `PYTHONPATH=src` im genannten Worktree. Die Importprüfung
  stammt aus der vorangegangenen Diagnose desselben Dienstprozesses.
* `reference-assets/`: eingefrorene Leser-Vorlagen und historische
  Timing-Datei. Keine Kalibrierung für einen anderen Host oder Aufbau ableiten.
* `replay.py`, `replay-results.jsonl`: Offline-Rezept und tatsächlich
  ausgeführte Wiederholung mit den eingefrorenen Quellen.
* `CLAUDE-HANDOFF.md`, `MANIFEST.json`: Fortsetzungsauftrag und Dateiintegrität.

## Wiederholung ohne Kamera

Im Repositorywurzelverzeichnis mit Projekt-venv und Debian-OpenCV/NumPy:

```bash
sha256sum -c docs/quellen/setup-new-position-2026-11-11-162902.sha256
./.venv/bin/python -m zipfile -e docs/quellen/setup-new-position-2026-11-11-162902.zip var/replay-new-position
./.venv/bin/python var/replay-new-position/setup-new-position-live-20261111T162902Z/replay.py --verify-only
./.venv/bin/python var/replay-new-position/setup-new-position-live-20261111T162902Z/replay.py
```

In einen neuen Zielordner entpacken. Erwarteter historischer Fit:
`keine_startlage`. Das Rezept entpackt den archivierten Code temporär und
öffnet nur Dateien. Für den Vergleich einer neueren oder korrigierten
Version `--source /pfad/zum/checkout` ergänzen. Eine geänderte Rückgabe ist
noch keine belegte korrekte Geometrie oder Messfreigabe.

## Nicht vorhandene Daten und Zeitbasis

Die Anwendung überschreibt `still.png` bei neuen Suchversuchen. Deshalb
ist nur das letzte Mittelbild vorhanden. Die ersten beiden Mittelbilder
und die jeweils acht Rohbilder wurden nicht gespeichert. Die serialisierten
Texte/Fehlergründe bleiben erhalten; daraus sind fehlende Pixel nicht
rekonstruierbar. Eine Stabilitätsmessung wurde nicht erreicht. Bilder vor
und nach dem Kameraneustart im Fokusschritt fehlen ebenfalls.

Status-Erfassungszeiten sind ausdrücklich Host-Wanduhr UTC, Unsicherheit
unbekannt. Datei-Mtime ist ausschließlich Herkunftsmetadatum (`FILE_MTIME`).
Es gibt keine unabhängigen Aufnahmezeitstempel für die gesicherten
Mittelbilder; daraus keine Framealter-, Latenz- oder Zeitfreigabe ableiten.

Vorherige Fälle bleiben im [ersten Paket](setup-failures-2026-11-11.md) und
im [Zusatzpaket nach Neustart](setup-followup-2026-11-11.md) erhalten.
