# Status — Stand 2026-09-24

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Die Zensical-Doku ist auf `master` mit interaktiver OQ- und Roadmap-Ansicht
sowie ersten Kontextvorschauen vorhanden. OQ-Titel, Status und aktive
TODO-Verweise erfordern `./.venv/bin/python scripts/oq-index.py`; der strenge
Docs-Build prüft die erzeugte Übersicht. Die Vorschau-Ziele in
`zensical.toml` brauchen kurze Texte und stabile Abschnittsanker.

## Doku-Pflege in dieser Sitzung

Der bisherige Claude-`@reboot`-Eintrag wurde aus der Benutzer-Crontab auf dem
Pi entfernt; ein Claude-Wartungsprozess läuft nicht. Ein eigener Forgejo-
Workflow mit getrenntem Pi-Runner, Codex-CLI-Anmeldung, Prüf-Gate und Bot-
Push auf `master` ist implementiert. Der Audit prüft vollständige
Änderungslisten; der Runner-Token bleibt vom Dienstbenutzer abgeschirmt.
Die Implementierung ist auf `master` in Forgejo veröffentlicht.
Das persönliche `master`-Worktree enthält eine nicht committete Änderung an
`PLANNED_FEATURES.md`, die unangetastet bleibt.

Ein Installationsversuch mit der neuen Runner-UUID und dem Skript des
bestehenden `picam-docs`-Runners führte zu `unregistered runner`, weil sein
alter Token erhalten blieb. Die ursprüngliche UUID wurde wiederhergestellt;
der Dienst ist aktiv und meldet `declared successfully`. Beide Installer
schützen jetzt gegen diesen UUID/Token-Mismatch. Für den **neuen** Codex-
Runner fehlen noch seine Token-Datei, ein Bot-PAT und die Geräteanmeldung.
Ein produktiver Codex-Lauf und der nachgelagerte Cloudflare-Deploy sind noch
nicht geprüft.

## Verifikation

* Ausgangsstand im isolierten Worktree: 490 Python-Tests bestanden,
  3 übersprungen, 1 xfailed.
* Neuer Wartungs-Gate: 22 gezielte Tests bestanden, darunter ein Audit mit
  70 geänderten Dateien und ein erfolgreicher Test-Push; Ruff ohne Befund.
* Vollständige Python-Suite vor dem Runner-Fix: 512 bestanden,
  3 übersprungen, 1 erwarteter Fehlschlag.
* Strenger Zensical-Build: erfolgreich; bestehende Vorschau-Ziele gültig.
* Bestehende Dokubrowser-Tests: 12 bestanden.
* Workflow-YAML, eingebettete Bash-Blöcke, Installationsskript und systemd-
  Service wurden statisch geprüft.
* 24 gezielte Tests nach dem Runner-Fix bestanden. Darunter prüfen zwei Tests
  den UUID-Wechsel mit und ohne Token-Datei. Der bestehende Runner wurde nach
  Wiederherstellung erfolgreich bei Forgejo deklariert.

## Nächster Schritt

Runner und Bot in Forgejo einrichten, Codex unter dem Runner-Benutzer
einmalig anmelden und zuerst einen manuellen Vorschaulauf, dann einen
kontrollierten Veröffentlichungsdurchlauf mit Cloudflare-Abnahme ausführen.
