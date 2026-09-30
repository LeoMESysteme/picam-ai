# Status — Stand 2026-09-30 (Sessionende)

Dieser Snapshot wird zum Sessionende überschrieben. Verlauf:
[Changelog](../CHANGELOG.md) und
[Projektgeschichte](project_history.md); Aufgaben:
[TODO.md](../TODO.md).

## Betrieb und Messstand

Die aktive Kamera ist die Logitech StreamCam über UVC (046d:0893).
Die IMX500 ist seit 2026-09-25 außer Betrieb
([Hardwareprofil](HARDWARE_PROFILE.md)). Die echte Anbindung an GSVmulti
bleibt wegen der fehlenden Telegrammspezifikation offen
([OQ-07](open-questions.md#oq-07)).

Die Dot-Matrix-Abnahme 1 mit der früheren Normierung ist nicht bestanden:
Die Gruppe ab2 wurde an einer Spiegelkante in der Leerzelle abgelehnt.
Danach wurde bg_closing_v1 eingefroren; die Entwicklungsmessung mit
942 Proben meldete 0 falsche Lesungen, ab2 83/83 richtig und die unscharfe
Gruppe auf2 vollständig abgelehnt. Die erste neue Abnahme-Aufstellung ab3
ist geerntet und importiert; ab4 fehlt. Zahlen und Versuchsbedingungen:
[VALIDATION.md](VALIDATION.md), [Fortschritt](FORTSCHRITT.md) und
[Laborjournal](lab_journal.md).

Die Aufnahme nutzt für Ernten eine RAM-Zwischenablage, nachdem
SD-Schreibhänger Bildverluste verursacht hatten. Die Probeläufe sc6b
und ab3 hatten keine Bildverluste. Das ist ein Befund dieser Läufe,
keine Zusage für alle künftigen Aufnahmen.

## Software und Anleitung

Die ersten Baukapitel beschreiben teils noch geplante Komponenten:
folder:// ist registriert, aber FolderSource fehlt; Geräteprofile und
die Pipeline-CLI für dispread run fehlen ebenfalls. Der bestehende
dispread-Einsprungpunkt führt zur separaten Workbench-CLI
([Lernpfad](anleitung/README.md), [Roadmap](ROADMAP.md)).
Livevorschau und Datensatz-Sammelmodus haben eigene
[Bedienseiten](anleitung/10-kamera-livevorschau.md) und
[Dokumentation zum Sammeln](anleitung/11-datensatz-sammeln.md).

## Zensical-Dokumentation und Runner

Die [Startseite](../index.md) nennt jetzt die StreamCam und verlinkt
alle Navigationsziele direkt. Die Vertiefungen zu
[Messpfad](uebersicht/messpfad.md),
[Zeitstempeln](uebersicht/zeitstempel.md) und
[Daten/Abnahme](uebersicht/daten-und-abnahme.md) verbinden Anforderungen,
API und Nachweise. Frühere IMX500-Baukapitel und Kameramesswerte sind als
historisch gekennzeichnet; das [Kamerarezept](anleitung/rezepte.md)
verwendet `v4l2://`, die aktiven UVC-Profile stehen in der
[Bildquellen-API](../api/frames.md).

Der Forgejo-Runner nahm am 2026-09-30 um 06:00 einen Auftrag an und
veröffentlichte um 06:04 einen Doku-Commit. Sein rotierender Audit hatte
die Startseite nicht als festen Prüfschritt. Der Audit-Auftrag enthält sie
nun bei jedem Lauf. Ein lokaler Codex-Probelauf mit der installierten CLI
zeigte: Mit --ephemeral scheiterte der Spawn an „no thread with id“;
ohne diesen Schalter wurde ein Kind-Thread angelegt. Das aktualisierte
Startkommando enthält die explizite `docs_reader`-Rollenangabe, nachdem die CLI sie
mit `--ignore-user-config` nicht automatisch geladen hatte. Der lokale
Rollen-Probelauf war erfolgreich. Der Dienst-Runner selbst war bei der
Prüfung aktiv; seine geschützte Anmeldung und
Sessionlogs waren für diese Sitzung nicht lesbar
([Hosting und Pflege](HOSTING.md)).

## Nächste Schritte

1. ab4 aufbauen und ernten, danach genau einen Abnahmelauf über ab3 und ab4
   auswerten ([TODO.md](../TODO.md)).
2. Nacharbeit am Einrichtungsassistenten gegen den
   [Plan](superpowers/plans/2026-09-29-einrichtungsassistent.md) prüfen.
3. Den nächsten geplanten Doku-Pflegelauf und einen tatsächlichen
   docs_reader-Einsatz im geschützten Runner-Log kontrollieren.
