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
fachlich korrigiert. Für den täglichen Push ist ein auf dieses Repo
begrenzter Forgejo-Schreib-Token vorgesehen. `DOCS_BOT_TOKEN` und
`DOCS_BOT_USERNAME` sind inzwischen gesetzt; der
Benutzername wurde auf `l.hentschke` korrigiert. Der manuell geprüfte Patch
ist auf `master`; der [Doku-Deploy 36](https://ds1515.me-systeme.de/l.hentschke/picam-ai/actions/runs/36)
einschließlich Cloudflare-Schutzprüfung war erfolgreich. Ein erster
automatischer Publish-Versuch ([Run 38](https://ds1515.me-systeme.de/l.hentschke/picam-ai/actions/runs/38))
wurde wegen eines falschen Abschnittsankers vom strengen Build gestoppt;
der Wartungsauftrag prüft solche Anker nun vor der Gate-Abnahme selbst.

## Verifikation

Für den geprüften Patch: OQ-Index-Prüfung und strenger Zensical-Build
erfolgreich; 24 Wartungs-Gate-Tests und 13 Dokubrowser-Tests bestanden.
Der öffentliche Zugriffsschutz der Live-Seite wurde nach dem Deploy
erneut erfolgreich geprüft. Hardware-Messungen fanden in diesem Pflegelauf
nicht statt.

## Nächster Schritt

Einen erneuten manuellen `mode=publish`-Lauf starten und bei einem
Doku-Commit den Bot-Push und den nachgelagerten Cloudflare-Deploy prüfen.
