# Status und Übergabe — 2026-11-06

Werkzeugpflege 2026-11-06: Repowise auf Nutzerwunsch systemweit deinstalliert.
Agent-Anweisungen, Doku-Pflegeprompt und lokale Plugin-Einträge in diesem
Worktree bereinigt. Laufende Clients für geladene Hooks/Werkzeuglisten neu
starten. Der bisherige fachliche Arbeitsstand folgt unverändert.

Arbeitszweig `feat/werkbank-redesign`, Worktree
`.claude/worktrees/feat-werkbank-redesign`. T13 läuft jetzt auf dem echten
Dienst `dispread-werkbank-t13.service`, Oberfläche
`https://100.122.154.35:8082/live`. Nutzer hat selbst bestätigt und gestartet:
`live-20261106T112527Z/run-01`, Start 12:55:55 MEZ (11:55:55 UTC).
Referenz aktiv, GSVmulti-Ausgabe aus, kein Test-Override. Zwischenstand bei
82,677 s: 1434 VALID, 113 TRANSITION, 233 übersprungen; keine Auditfehler,
Trackingverluste oder Referenz-Parserfehler. Noch keine Abnahme; spätere
Statusproben enthalten auch UNREADABLE und sind vollständig auszuwerten.

Zuerst etwa 15 Minuten mit geöffneter Seite, dann 15 Minuten ohne Seite.
Nutzer soll gegen 13:11 MEZ die Seite schließen und Rückmeldung geben;
wirkliche Phasengrenze erst dann markieren. Frühester 30-Minuten-Zeitpunkt
13:25:55 MEZ. Lauf nicht automatisch beendet. Status- und top-Beobachter
`dispread-t13-observe` / `dispread-t13-top` aktiv, maximal zwei Stunden;
Rohdaten unter `var/diagnostics/werkbank-t13-20261106/`. Bei Abschluss beenden.
X-Hud-Vorschau-fps und alter Controller-Verbrauch noch offen; keine Builds
oder Tests während der Lastvergleichsphasen starten.

UART-Brücke auf ausdrücklichen Nutzerwunsch zurückgestellt. Pi-Demosender
beendet, ttyAMA0 frei. Letzter Versuch ohne TXD-Rückleitung: 0 bestätigte
COM-Schreibvorgänge. Neuer Windows-PC: Python 3.15 / `.venv315`, COM6 FTDI
(0403:6001, SER AB8556ZCA), Brücke COM6→COM5, GSVmulti COM4. Zusätzliche
Leitung Kabel-TXD→physischer Pi-Pin 10 laut letzter Rückmeldung nicht
angeschlossen. Vor Fortsetzung prüfen. Details im Laborjournal.

Die neue `/live`-Werkbank ist
softwareseitig umgesetzt, einschließlich GSVmulti-Ausgabewahl und der
abschließenden Backend- und UI-Korrekturen. Hardware-Abnahme T13 und Merge
nach `master` stehen aus und brauchen Leonhards ausdrückliches OK.

## Neue Produktanforderung für später

Leonhard verlangt eine wesentlich einfachere Windows-Einrichtung der
GSVmulti-Brücke: Anleitung aus der Ausgabewahl der Werkbank, bevorzugt
Windows-EXE mit Installation/Konfiguration und GUI, Wahl UART/Netzwerk,
konkrete Bereitschaftshinweise sowie möglichst automatisch erzeugte
GSVmulti-Sessiondatei. Ein Ein-Befehl-Skript ist eine mögliche Alternative.
In TODO, PLANNED_FEATURES und OQ-62 erfasst; noch keine neue Funktion
implementiert. Ergänzt: unabhängig von fehlendem/altem System-Python;
Skriptalternative mit vorab geprüfter, automatisch eingerichteter isolierter
Laufzeit. Abnahme auch ohne Python und mit ausschließlich Python 3.7.
Windows hat inzwischen Python 3.15; Brücke mit `.venv315`, COM6→COM5
startet und wartet auf Pi-Antwort. Erster Pi-Demoversuch `uart-demo-01`
kontrolliert unterbrochen: 0 COM-Schreibbestätigungen. Nutzer bestätigt
weiterhin nur GND/RXD verdrahtet, Rückkanal TXD→Pi-Pin 10 fehlt. Pi-Sender
ist beendet und ttyAMA0 frei. Auf zusätzliche Leitung und erneute
Bereitschaftsmeldung für später warten; T13-Leserabnahmelauf inzwischen aktiv. Der aktuelle praktische Schritt ist T13; UART-Demotest ist zurückgestellt.

## Übernahme und Abschluss

Claude stoppte nach Backend-Commit `92f00b7` in der letzten UI-Welle W2.
Sonnet hatte die sieben Korrekturpunkte und den Changelog geschrieben,
aber noch nicht committet. Sein Node-Lauf hatte 229 bestandene Tests;
Playwright meldete 45 bestanden und einen Fehler beim Zugriff auf das
noch fehlende Viewer-Raster. Der zweite Start scheiterte am belegten Port.

W2 schließt den UART-Start ohne Bestätigung auch über Enter und den direkten
Start-Handler, bindet die Freigabezeit an den angezeigten Wert und korrigiert
Hinweistexte, Zeitbeschriftungen, Werteplan-Verlauf, Menüsemantik und unnötige
Zoom-Beschriftungsupdates. Codex ergänzt die Prüfung beider Startwege und
synchronisiert den Viewer-Test mit dem getrennt eintreffenden Statusraster.
Die Gestaltung folgt weiterhin dem freigegebenen Mock.

## Prüfstand

Neu ausgeführt: 229/229 Node-Tests, 46/46 Workbench-Playwright-Tests.
Die danach ergänzten Viewer- und UART-Handler-Prüfungen bestanden jeweils
3/3 Wiederholungen. Strenger Doku-Build erfolgreich, OQ-Index aktuell,
`git diff --check` sauber. Laufansicht bei 1280 × 800 px mit dem Fake-Server
visuell geprüft (lokale Aufnahme `/tmp/werkbank-finish-1280.png`).
Unabhängiges W2-Review: keine wichtigen Korrektheits-/Sicherheitsbefunde.
Wiki-Playwright: 90 bestanden, 1 Fehler im bestehenden Roadmap-Mausradtest
(Ebenenwechsel blieb auf `inside`). Isolierte Wiederholung danach 3/3
bestanden. Damit kein vollständig grüner Wiki-Gesamtlauf; vor einem Merge
erneut prüfen. Keine Änderung am Roadmap-Code oder dessen Tests.
Historische Belege aus Claudes Protokoll: 3517 bestanden, 10 übersprungen,
2 xfailed im vollständigen Python-Lauf auf `64adb7d`; nach W1 625 bestandene
gezielte Python-Tests und Ruff sauber. Diese Läufe wurden in der Übernahme
nicht als neue Vollprüfung wiederholt.

## Ausgabe und Freigabegrenzen

Pro Lauf genau ein Weg: `off` = Aus, `serial` = UART direkt (P4-3),
`uart` = UART über Windows-Brücke, `tcp` = Netzwerk über Windows-Brücke.
UART direkt gibt gemäß Nutzerentscheidung echte Werte aus, trägt dauerhaft
„Prototyp – nicht am Windows-PC abgenommen, keine Messfreigabe“ und verlangt
vor jedem Start die ausdrückliche Bestätigung. Brückenwege bleiben für echte
DUT-Werte strukturell gesperrt; Testläufe erlauben keine externe Ausgabe.
Der Übungslauf simuliert die Wege und sendet nichts.

Die Windows-Demobelege vom 04.11. bleiben gültig: 600/600 exakte TCP-Werte,
510/510 geschriebene Werte nach Brückenprozessabbruch. GSVmulti verdichtet
Ausfallzeiten; Ungültig-/Altwert- und Zeitsemantik sind weiter offen.
Details und Wiederaufbau stehen im [Protokoll](GSVMULTI_PROTOCOL.md),
[Belegarchiv](quellen/gsvmulti-validation-2026-11-04.md) und
[Validierungsbericht](VALIDATION.md). Die W2-Übernahme griff nicht auf Hardware zu; die danach gestartete
T13-Einrichtung steht im Laborjournal und in VALIDATION.md.

## Nächster Schritt

1. Laufenden T13 mit Leonhard abschließen: echte Einrichtung, mindestens 30 Minuten
   Lauf mit Referenz, Vorschau-/Lastvergleich mit und ohne geöffnete Seite,
   übersprungene Bilder und Ressourcenverbrauch des alten Controllers.
2. Erst danach Integration nach ausdrücklicher Merge-Freigabe.
3. Anschließend Laufablage/Export/Aufbewahrung (OQ-60), Nachberechnung
   (OQ-59) und Bestandsaufnahme des alten Controllers (OQ-61) gemäß
   [TODO](../TODO.md). Das sind spätere Erweiterungen, keine offenen W2-Fixes.

Kleine zuvor zurückgestellte Reviewpunkte (Rundgang-Ziel bei geöffnetem
Hilfe-Dock, späte Hinweise nach Übungsende, Kürzungen bei 1280 px) bleiben
im lokalen Ablaufprotokoll `.superpowers/sdd/2026-11-04-werkbank-redesign/progress.md`
nachvollziehbar und sind bei T13 zu beobachten. Die Implementierung ist
keine Produktions- oder Messfreigabe.
