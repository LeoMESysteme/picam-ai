# Status und Übergabe — 2026-11-11

## Kritischer Auftrag: Workbench vor Bridge/EXE stabilisieren

[Blocker, Prioritäten und Abschlusskriterien](WORKBENCH_BLOCKER.md),
[ausführliche Claude-Übergabe](superpowers/handoffs/2026-11-11-einrichtungsfehler-an-claude.md).
Nach Limit-Reset zuerst bearbeiten. Wiederholte Setupfehler, Fokus- und
Bedienprobleme sowie kurzer Verbindungs-/Bildausfall blockieren Bridge-/EXE-
Weiterentwicklung, Systemtests und Kaulitz-Teilabnahme. Nutzerrückkehr und
Zieltermin: Freitag, 2026-11-13. Kein Beleg einer bereits erfolgten Behebung.

OQ-71 kritisch: Abbruch/Neustart bei `setup_ready + FEHLER` fehlen;
Bestätigen wird korrekt abgelehnt. Zusätzlich fehlt nach erfolgreicher
Bestätigung ein direkter Einstieg in neue Einrichtung. Nutzer musste dafür
`165234Z/run-01` starten und stoppen. Die vorläufige Deutung dieses kurzen
Laufs als eigenständiger Trackingfehler ist zurückgenommen, OQ-76 geklärt.
OQ-69/70/72/73/74/75 bleiben offen und kritisch. Versehentlicher Zellentext
mit „hatte“ war laut Nutzer Fehleingabe, kein neuer belegter Softwarebug.

## Gesicherte Referenzen und Zahlen

Neueste bestätigte Einrichtung: `live-20261111T165754Z`, WARNUNG bestätigt,
bei Sicherung kein Lauf. Zusammen mit `164508Z` und `165234Z` drei positive
Setup-Gegenproben, je zehn Originaldateien mit Bildern, Vorschlag, Profil,
Bestätigung; sechs historische Geometriekontrollen zusätzlich erhalten.
[Regressionspaket mit ausführbarem Rezept](quellen/workbench-positive-regression-2026-11-11.md).
Alle drei statischen Setup-Replays einschließlich echter Quad-Verfeinerung,
Gegenlesen und Bereichsreserve bestanden; Endquads jeweils 0,0 px Unterschied
zum gespeicherten Vorschlag. Sechs historische Originaltests bestanden.

`164508Z/run-01`: 2.920 VALID / 3.843 Auditdatensätze = 75,9823 %,
757 TRANSITION, 166 UNREADABLE; 26 weitere Frames übersprungen.
0 Trackingverluste, 0 Auditfehler, kein Kameralesefehler. 129,940458 s
Host-Wanduhrspanne UTC, Unsicherheit unbekannt, keine Latenzmessung.
Referenzvergleich: 0 Abweichungen unter 556 vergleichbaren VALID,
2.352 unentschieden, 12 ungedeckt. UART direkt, kein Windows-/GSVmulti-
Empfangsnachweis. 75-%-Minimum auf verarbeiteten Datensätzen erreicht,
keine vollständige Hardware-/Langlaufabnahme daraus ableiten.

## Neuester fehlgeschlagener Versuch

`live-20261111T170836Z`: Nutzer sieht erneut geringere optische Schärfe als
möglich; Raster erster Versuch OK, danach Kanten-FEHLER in Leerzellen 14/15,
keine Stabilitätsmessung. Vier Setup-Originale und Fokus-/Statusdaten erhalten.
Ziel/Rückmeldung 56, beste Schärfe 522,219448, Endprüfung 517,933823;
kein numerischer Rücksprung belegt. [Eigenes Paket und Rezept](quellen/setup-focus-failure-2026-11-11-170836.md).
Weitere zufällige Aufstellungen vorerst nicht erforderlich; gezielte
Fokus-Bildfolge wäre bei späterer Hardwareprüfung die relevante Ergänzung.

## Fehlerbelege und Logs

* [Erste Fehlerfälle und reproduzierte Bedien-Sackgasse](quellen/setup-failures-2026-11-11.md):
  Rasterstart, manuell bearbeitete Nachführverteilung, echte UI-/Backend-Funktionen.
* [Kantenabbrüche und Worktree-/Fokusprüfung](quellen/setup-followup-2026-11-11.md):
  `161702Z`/`161955Z`, Raster 145/145, Kanten-FEHLER Zelle 7 jeweils offline.
* [Weitere Aufstellung 162902Z](quellen/setup-new-position-2026-11-11-162902.md):
  drei Mal `keine_startlage`, letztes Bild, Fokusdaten und Standalone-Rezept.
  Im letzten Bild LCD-Hinweisbox vollständig außerhalb fester Fokus-ROI;
  Bild vom Fokuszeitpunkt fehlt, daher keine alleinige Ursache bewiesen.
* [Ausfalllogs](quellen/workbench-outage-2026-11-11.md):
  ungefähr sieben Sekunden laut Nutzer. Dienst PID 3321848 blieb aktiv,
  NRestarts=0, kein zugeordnetes Neustartereignis. App-/Kernel-/Netzwerklogs
  samt Fehlerausgaben erhalten. Ursache offen, Dauer nicht gemessen.
* [Kandidatenstände und passive Dateiversionen](quellen/workbench-recovery-context-2026-11-11.md):
  Quell-HEADs, relevante binärfähige Patches und neue Dateien aus ui/ux;
  ungeprüfte Kandidaten, keine heimlich ausgerollten Fixes.

ZIPs unter `docs/quellen/` mit äußerem SHA-256 und innerem Manifest;
Arbeitskopien `var/diagnostics/`. Zahlen in [VALIDATION](VALIDATION.md),
Aufbau und Bedienerklärungen im [Laborjournal](lab_journal.md).
Sicherungsbranch: `docs/workbench-critical-2026-11-11`; tatsächlichen
Commit-/Remote-Stand über Git prüfen. Fremde lokale Änderungen erhalten.

## Prüfung dieser Sicherung

Sieben ZIPs: äußere SHA-256, ZIP-CRC und alle inneren Manifestdateien geprüft.
Frisch entpacktes positives Paket bestätigt Integrität; drei statische
Setup-Replays und sechs historische Geometrietests erfolgreich. Neuester
Kantenfehler offline reproduziert. Code-Patches beider Arbeitskandidaten
gegen frisch entpackte HEAD-Quellen anwendbar. Strenger Doku-Build bestanden.
Der vollständige 90-Test-Doku-Browserlauf wurde beendet: 5 bestanden,
1 Diagrammtest mit 30-s-Timeout fehlgeschlagen, 1 unterbrochen, 83 nicht
ausgeführt. Gezielte Wiederholung des Diagrammtests und des unterbrochenen
JS-Fallback-Tests ohne parallele Archivarbeit: 2 bestanden (17,6 s,
60-s-Testbudget). Ursache des ersten Timeouts nicht bewiesen. Das ist keine
bestandene Gesamtsuite; vollständiger Lauf vor Merge erforderlich.
Es gab keine Produktcodeänderung und keinen Merge.

## Betriebsstand und Grenzen

Dienst `dispread-werkbank-bruecke.service`, PID 3321848 seit 17:16:36 MEZ,
`.worktrees/bruecke-run`, Commit `08ac9b9`, `PYTHONPATH=src`,
`https://100.122.154.35:8082/live`. Importpfade mit passendem Interpreter und
Prozessumgebung geprüft. Der ausdrücklich gewünschte Neustart lud denselben
alten Stand, kein Update. Neuere Arbeit in `feat/bruecke-ui` (`8335abf`)
und `feat/bruecke-ux` (`2c5be9b`) plus uncommittete Änderungen sind gesichert.
Vor Korrekturen aktuellen Zielstand gegen archivierte Fälle vergleichen.
Fokusmodule run/ui/takt/ux identisch; Branchwechsel allein belegt keinen Fix.

Rohstapel, verlorene Stabilitätsproben und Fokusbilder vor/nach Kameraneustart
fehlen. Keine künstlichen Kopien als unabhängige Nachweise ausgeben.
FILE_MTIME und Sicherungs-Wanduhr sind keine Sensor-Latenzbelege.
Statische Regressionen und große Teile der Zustands-/Steuersequenz sind
auch ohne Aufbau bearbeitbar; physische/Windows-Abnahme getrennt halten.
Keine weiteren Kameraaktionen oder Dienstumstellung für die Sicherung.
Keine Claude-Sitzung gestartet oder angeschrieben; lokale Einstiegsverweise
auch in ui/ux gesetzt, ausführlicher Auftrag für Wiederaufnahme vorhanden.
