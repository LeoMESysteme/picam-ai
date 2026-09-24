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

Der alte Claude-`@reboot`-Job ist deaktiviert. Der eigene
`picam-codex-docs`-Runner ist registriert; seine Codex-CLI hat eine
geschützte Kopie der vorhandenen ChatGPT-Anmeldung. Ein manueller
Forgejo-Vorschaulauf ([Run 35](https://ds1515.me-systeme.de/l.hentschke/picam-ai/actions/runs/35))
hat einen Doku-Patch erzeugt und den strengen Zensical-Build sowie die
Browsertests bestanden. Der Patch wurde vor Veröffentlichung geprüft und
fachlich korrigiert. Der tägliche Job kann erst nach Einrichtung eines
auf dieses Repo begrenzten Forgejo-Schreib-Tokens nach `master` pushen;
`DOCS_BOT_TOKEN` und `DOCS_BOT_USERNAME` sind noch nicht gesetzt. Ein
automatischer Veröffentlichungslauf und das anschließende
Cloudflare-Deployment sind noch nicht abgenommen.

## Verifikation

Für den geprüften Patch: OQ-Index-Prüfung und strenger Zensical-Build
erfolgreich; 13 Dokubrowser-Tests bestanden. Der Lauf prüfte außerdem
Quelltext, Anleitung und Navigation. Hardware-Messungen fanden in diesem
Pflegelauf nicht statt.

## Nächster Schritt

Forgejo-Token mit Schreibrecht nur auf dieses Repo einrichten. Token und
Benutzername als Forgejo-Secret beziehungsweise Variable hinterlegen. Einen
manuellen `mode=publish`-Lauf samt Cloudflare-Ergebnis prüfen.
