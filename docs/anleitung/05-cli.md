# 5 — Die CLI

Die im Kapitel geplante Messpfad-CLI ist noch nicht vorhanden: Es gibt kein
`dispread run`, keinen Profil-Unterbefehl und kein `dispread inspect` für
`ValueRecord`-Läufe. Der Eintrag in der Roadmap ist entsprechend offen.
`pyproject.toml` verweist mit dem Einsprungpunkt `dispread` auf die separate
Workbench-CLI (`dispread.workbench.cli:main`); sie ist kein Ersatz für die
Pipeline-CLI.

## Vorhandene Werkzeuge

Die Workbench hat eigene Abläufe für Kamera-Vorschau und Datensammlung. Lies
für einen direkten Einstieg [Kapitel 10 — Kamera-Livevorschau](10-kamera-livevorschau.md)
und [Kapitel 11 — Datensatz sammeln](11-datensatz-sammeln.md). Für
Kameradiagnose existiert außerdem `scripts/camera-commissioning.sh` samt
[Checkliste](../CAMERA_COMMISSIONING.md). Diese Befehle konfigurieren keinen
Messlauf über Pipeline, Geräteprofil und Senken.

## Bauaufgabe

Bevor du Unterbefehle planst, kläre in [Kapitel 2](02-vertraege.md), welche
Verträge ein Lauf verbinden muss, und in [Kapitel 4](04-geraeteprofile.md),
welche Profilfunktion noch fehlt. Die spätere CLI soll Quelle, Profil,
Ausgabeziele und Laufgrenzen explizit annehmen. Sie darf die Prüfungen der
Pipeline oder des Freigabe-Gates nicht umgehen.

Entwirf `main(argv)` so, dass Tests Argumente direkt übergeben können.
Prüfe mindestens Hilfe ohne Kamera, unbekannte Quell-URIs, ungültige Profile,
Laufzeitfehler und Ausgabepfade. Ein erfolgreicher Lauf muss seine Artefakte
und Grenzen nachvollziehbar ausweisen. Zeitangaben aus `SYNTHETIC` oder
`FILE_MTIME` sind keine Latenzmessung; das Runartefakt muss außerdem den
provisorischen Status eines Formatters kenntlich machen.

## Fertig

Erst wenn die Pipeline-CLI implementiert und durch Tests belegt ist, kann die
Roadmap-Zeile geschlossen werden. Ergänze dann CHANGELOG und
`docs/status.md` gemäß den Projektregeln. Bis dahin sind die Workbench-
Kommandos der vorhandene Einstieg, aber kein `dispread run`.
