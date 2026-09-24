# Status — Stand 2026-09-24

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Die [Roadmap](ROADMAP.md) zeigt den Phasenstand. `synthetic://` und
`replay://` sind implementiert; die Registry kennt weitere, noch nicht
implementierte Bildquellen. Die vorhandene `dispread`-CLI startet die
Workbench. Die geplante allgemeine `dispread run`-CLI fehlt. Das
GSVmulti-Telegramm bleibt [OQ-07](open-questions.md#oq-07); das
`AsciiCsvFormatter`-Format ist provisorisch.

## Zensical-Doku und Pflege

Roadmap und Anleitungskapitel 0–2 wurden gegen den aktuellen Code geprüft.
Der Einstieg trennt Orientierungs- und Baukapitel. Die sechs Stufen haben
anklickbare API-Verweise mit kurzen Hover-Erklärungen. Für eigene
Entwicklungsaufgaben nennt Kapitel 0 Test, Dokumentation und Commit als
zusammengehörige Schritte.

Der Claude-`@reboot`-Job ist deaktiviert. Der separate
`picam-codex-docs`-Runner ist registriert und angemeldet; die Forgejo-Variable
`DOCS_BOT_USERNAME` und das Secret `DOCS_BOT_TOKEN` sind gesetzt. Der tägliche
Workflow prüft Änderungen vor einem Push mit OQ-Index, strengem Zensical-Build,
Vorschau-Ankern und Browsertests. Beim ersten erfolgreichen manuellen
[Publish-Lauf 47](https://ds1515.me-systeme.de/l.hentschke/picam-ai/actions/runs/47)
hat er den Doku-Commit `b35f545` nach `master` gepusht. Der nachgelagerte
[Cloudflare-Deploy 48](https://ds1515.me-systeme.de/l.hentschke/picam-ai/actions/runs/48)
war erfolgreich; der Zugriffsschutz der Live-Seite wurde danach erneut
geprüft. Der erste zeitgesteuerte Lauf steht noch aus.

## Verifikation

Der strenge Build und 13 Dokubrowser-Tests bestanden im Publish-Lauf.
24 Wartungs-Gate-Tests und Ruff sind grün. Der mobile Glossar-Test bestand
nach Abschalten der automatischen URL-Nachführung 8 von 8 Wiederholungen.
Die Cloudflare-Schutzprüfung bestätigt Weiterleitungen ohne Anmeldung für
Startseite, Doku, API, Suchindex und Build-Info. Keine Hardware-Messung in
diesem Doku-Pflegelauf.

## Nächster Schritt

Den ersten planmäßigen 06:00-Uhr-Lauf prüfen; weitere Doku-Änderungen laufen
über denselben Gate- und Deploy-Pfad.
