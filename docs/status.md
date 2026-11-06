# Status und Übergabe — 2026-11-06

Arbeitszweig `feat/werkbank-redesign`, Worktree
`.claude/worktrees/feat-werkbank-redesign`. T13 ist jetzt vorbereitet: echter Dienst `dispread-werkbank-t13.service`
auf `https://100.122.154.35:8082/live`, Sitzung `live-20261106T112527Z`.
Automatische Einrichtung nach 55,990 s fertig, Gesamturteil WARNUNG
(Raster/Displayfehler), Gegenlesen OK, keine Laufsperre. Leonhard hat
Rahmen und Format auf der Seite bestätigt; Serverzustand `confirmed`, keine
Laufsperre, Ausgabe `off`. Laufstart mit Referenz auf der Seite steht aus. Nutzer möchte zuvor auch
UART-Brücke testen. Neuer Windows-PC: Python/GSVmulti und virtuelles Portpaar inzwischen
vorhanden. Nutzer-Portliste: COM5=CNCA1 ↔ COM4=CNCB1, physischer FTDI-Adapter
COM6 (0403:6001, SER AB8556ZCA). Brücke soll COM6→COM5 verwenden, GSVmulti
COM4. Zusätzliche TXD-Leitung zum Pi-Pin 10 noch nicht bestätigt; kein
UART-Publisher gestartet. Frisches Brückenpaket unter
`var/diagnostics/werkbank-t13-20261106/download/` vorbereitet und isoliert
mit drei synthetischen Telegrammen geprüft. Download nur über Tailscale:
`http://100.122.154.35:8083/gsvmulti-bridge-20261106.zip`, begrenzter Dienst
`dispread-t13-download.service` (maximal zwei Stunden). README enthält
Windows-venv, Portliste, com0com-Anbieterlink, Verdrahtung und Demo-Befehle.
Noch keine neue UART-Verbindung und kein GSVmulti-Empfang nachgewiesen.
Beobachter `dispread-t13-observe` und `dispread-t13-top` sammeln bis zu
zwei Stunden unter `var/diagnostics/werkbank-t13-20261106/`; bei Abschluss
beenden. Kamera und Werkbank laufen für die gemeinsame Abnahme weiter.

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
Aktueller Windows-Test blockiert am Visual-Studio-Python 3.7; offizieller
Python-3.13-Installer und Befehle für separate `.venv313` ausgegeben,
Installation und erneuter Brückenstart noch nicht bestätigt. Der aktuelle UART-Demotest bleibt der nächste praktische Schritt.

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

1. Mit Leonhard T13 durchführen: echte Einrichtung, mindestens 30 Minuten
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
