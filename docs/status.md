# Status und Übergabe — 2026-11-06

Arbeitszweig `feat/werkbank-redesign`, Worktree
`.claude/worktrees/feat-werkbank-redesign`. Die neue `/live`-Werkbank ist
softwareseitig umgesetzt, einschließlich GSVmulti-Ausgabewahl und der
abschließenden Backend- und UI-Korrekturen. Hardware-Abnahme T13 und Merge
nach `master` stehen aus und brauchen Leonhards ausdrückliches OK.

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
[Validierungsbericht](VALIDATION.md). Keine neue Hardwaremessung in dieser
Übernahme; Kamera, serielle Ports und Werkbank-Dienste wurden nicht benutzt.

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
