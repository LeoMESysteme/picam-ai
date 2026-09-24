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

## Zensical-Doku

Roadmap und erste Anleitungskapitel wurden gegen den aktuellen Code geprüft.
Kapitel 0 nennt keine feste Testanzahl. Kapitel 1 verlinkt die API der sechs
Pipeline-Stufen mit kurzen Hover-Erklärungen. Kapitel 2 unterscheidet fünf
`Protocol`-Schnittstellen von der konkreten Klasse `ReleaseGate`.

Der Claude-`@reboot`-Job ist deaktiviert. Der separate
`picam-codex-docs`-Runner ist angemeldet und registriert;
`DOCS_BOT_TOKEN` und `DOCS_BOT_USERNAME` sind in Forgejo gesetzt. Der
manuell geprüfte Patch ist auf `master`, und [Doku-Deploy 36](https://ds1515.me-systeme.de/l.hentschke/picam-ai/actions/runs/36)
mit Cloudflare-Schutzprüfung war erfolgreich.

Der automatische Publish ist noch nicht end-to-end bestätigt. Der letzte
[Versuch 44](https://ds1515.me-systeme.de/l.hentschke/picam-ai/actions/runs/44)
bestand den strengen Build, stoppte aber im Mobiltest: Zensicals
`navigation.tracking` übernahm gelegentlich den Abschnittsanker der
Ausgangsseite. Die automatische URL-Nachführung ist nun deaktiviert;
Sofortnavigation und Kontextvorschauen bleiben aktiv. Der Gate sichert
einen bereits geprüften Patch bei einem späteren Publish-Fehler als Artefakt.

## Verifikation

OQ-Index-Prüfung und strenger Zensical-Build erfolgreich. Der mobile
Glossar-Test scheiterte mit URL-Nachführung 2 von 5 Mal und bestand ohne
sie 8 von 8 Mal; die gesamte Dokubrowser-Suite bestand mit 13 Tests.
24 Wartungs-Gate-Tests und Ruff sind grün. Der Zugriffsschutz der
Live-Seite wurde nach dem Deploy erneut geprüft. Keine Hardware-Messung
in diesem Doku-Pflegelauf.

## Nächster Schritt

Einen erneuten `mode=publish`-Lauf starten und Bot-Push sowie den
nachgelagerten Cloudflare-Deploy prüfen.
