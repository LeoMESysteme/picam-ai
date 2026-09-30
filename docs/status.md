# Status — Stand 2026-09-30

Diese Datei ist der aktuelle Snapshot; Historie steht in `CHANGELOG.md` und
`docs/project_history.md`. Die Arbeitsliste steht in [TODO.md](../TODO.md).

## Anleitung

Die ersten Baukapitel beschreiben geplante, teils noch nicht implementierte
Komponenten. `folder://` ist in der Registry, aber die `FolderSource` fehlt.
Geräteprofile und die Pipeline-CLI (`dispread run`) fehlen ebenfalls. Der
`dispread`-Einsprungpunkt führt zur separaten Workbench-CLI.

## Kamera und Datensammlung

Aktive Kamera: Logitech StreamCam über UVC (`046d:0893`); die IMX500 ist seit
2026-09-25 außer Betrieb. Die Quelle `v4l2://` setzt eine `camera.json` voraus.
Workbench-Livevorschau und Datensammlung sind in den Kapiteln 10 und 11 der
[Anleitung](anleitung/README.md) beschrieben.

## Mess- und Forschungsstand

Der Stand der Ernte-/Trainingsarbeit und der Abnahmen ist in
[Fortschritt Ernten/Training](FORTSCHRITT.md) dokumentiert. Zahlen und
Messbedingungen stehen in [VALIDATION.md](VALIDATION.md); Zeitmessungen mit
ihren Grenzen stehen in [TIMING.md](TIMING.md). Das GSVmulti-Telegramm bleibt
offen ([OQ-07](open-questions.md)).

## Dokumentationspflege

Die Zensical-Navigation enthält den Lernpfad, Workbench-Anleitungen,
Projektstatus, Roadmap sowie Mess- und Hardwaredokumente. Der vorgeschriebene
Site-Build wird vom Gate ausgeführt.
