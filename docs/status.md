# Status und Übergabe — 2026-11-06

Werkzeugpflege 2026-11-06: Repowise auf Nutzerwunsch systemweit deinstalliert.
Agent-Anweisungen, Doku-Pflegeprompt und lokale Plugin-Einträge in diesem
Worktree bereinigt. Laufende Clients für geladene Hooks/Werkzeuglisten neu
starten. Der bisherige fachliche Arbeitsstand folgt unverändert.

Arbeitszweig `feat/werkbank-redesign`, Worktree
`.claude/worktrees/feat-werkbank-redesign`. Erster T13-Lauf beendet:
`live-20261106T112527Z/run-01`, 12:55:55–13:18:33 MEZ, 22:38 min.
Nutzer bewegte die Anzeige absichtlich mehrfach. 39.886 Datensätze,
75,79 % VALID; 0 Abweichungen unter 10.773 eindeutig vergleichbaren
Referenzfreigaben, 19.451 im Wechsel-Schutzfenster unentschieden, 5 ungedeckt.
Keine Audit-/Kamerafehler. Noch keine vollständige T13-Abnahme.

Dauerhafte Korrekturanzeige: letzte 8284 Bilder alle mit zweitem Fit,
6605 akzeptiert. Kein blockierter Lauf; letzter Datensatz VALID.
`correcting` bedeutet derzeit „zweiten Fit verwendet“. UI-Semantik und
physischer Grund der dauerhaften Erstfit-Ablehnung offen (OQ-63).
Diagnosebilder waren aus; Nachanalyse kann die Bildursache nicht beweisen.
[Auswertung](quellen/werkbank-t13-2026-11-06.md) enthält alle Befunde.

Status- und top-Beobachter beendet. Werkbank weiter zum Ansehen aktiv auf
`https://100.122.154.35:8082/live`, Dienst `dispread-werkbank-t13.service`.
Vor neuer Abnahme: HUD/Bilddiagnose planen, Korrekturhinweis klären;
anschließend >=30 Minuten und dokumentierten Vorschauvergleich durchführen.
X-Hud-fps und isolierter Controllerverbrauch fehlen weiterhin.

UART-Brücke bleibt zurückgestellt, Pi-Demosender beendet. Neuer Windows-PC:
Python 3.15 / `.venv315`, COM6 FTDI, Brücke COM6→COM5, GSVmulti COM4.
Letzter UART-Versuch ohne TXD-Rückkanal: 0 COM-Schreibbestätigungen.
Kabel-TXD→physischer Pi-Pin 10 vor Fortsetzung bestätigen lassen.

Die neue `/live`-Werkbank ist
softwareseitig umgesetzt, einschließlich GSVmulti-Ausgabewahl und der
abschließenden Backend- und UI-Korrekturen. Hardware-Abnahme T13 und Merge
nach `master` stehen aus und brauchen Leonhards ausdrückliches OK.

## Windows-EXE: technische Umsetzung, UI für Claude

Leonhard hat Spec und Plan zur Ausführung durch Codex/Subagents freigegeben.
EXE-GUI und sämtliche sichtbaren Workbench-Anpassungen (Anleitung je Weg,
Auswahl, Verbindung/Bereitschaft) bleiben ausdrücklich Claude vorbehalten;
am Ende wird eine konkrete Übergabe vorbereitet, noch keine Nachricht
an einen anderen Chat gesendet.

Arbeitsstand dieser Umsetzung: verwalteter Worktree
`/home/me-systeme/.codex/worktrees/windows-bridge-core/picam-ai`, Branch
`codex/windows-bridge-core`, Basis `ea29e44`. Der bisherige Redesign-Worktree
mit fremden Änderungen und laufender Werkbank bleibt unberührt.
P1-Kern und Codec: 70 relevante Tests bestanden, Review ohne wichtige
Befunde. N2-Geräte-/Portpaaradapter: 48 Tests bestanden, beide wichtigen
Reviewbefunde korrigiert und nachgeprüft. Der echte Treiberprovider bleibt
unverifiziert und verweigert Änderungen. N1-Buildvorbereitung: beide Reviewbefunde korrigiert und nachgeprüft;
79 Tests bestanden, ein echter Windows-Test hier übersprungen. P2-Identität
ist im Review, N3-Vorlagenbelege in Arbeit.
Windows-Paket-/Treiber-
Nachweise bleiben separat ausstehend, keine Qt-Pakete am Pi installiert.
Weitere technische Teile und Reviews folgen gemäß [Plan](superpowers/plans/2026-11-06-windows-bruecke.md).
[Claude-Übergabe](superpowers/handoffs/2026-11-06-windows-bruecke-claude.md)
wird mit tatsächlich vorhandenen Schnittstellen und offenen Gates fortgeführt.
DUT-Sperren und OQ-53/OQ-62/OQ-64 bleiben bestehen.

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
Bereitschaftsmeldung für später warten; T13-Leserabnahmelauf inzwischen beendet und ausgewertet. T13-Lauf 01 ist ausgewertet; UART-Demotest ist zurückgestellt.

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

1. Neue T13-Abnahme nach Klärung von OQ-63 mit Leonhard vorbereiten: echte Einrichtung, mindestens 30 Minuten
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
