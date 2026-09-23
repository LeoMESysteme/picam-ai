# Status — Stand 2026-09-23

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Der Zensical-/Cloudflare-Stand aus `docs/zensical-prototyp` ist per Fast-forward
in `master` integriert und auf `origin/master` veröffentlicht. Jeder weitere
Push auf `master` startet automatisch `.github/workflows/docs.yml`.

Der produktive Cloudflare-Deploy ist zweifach auf einen echten Push nach
`master` begrenzt: durch den Workflow-Trigger und durch die Bedingung am
Produktionsschritt. Manuelle Läufe und Feature-Branches dürfen Build,
Zugriffsschutztests und den Prüfstand ausführen, aber Produktion nicht
überschreiben.

## Doku und Hosting

* Zensical baut über `./scripts/docs-site.sh build` nach `site/`.
* Forgejo Actions verwendet den eigenen Runner mit Label `picam-docs`.
* Der Lauf erzeugt das Artefakt `doku-seite`, testet die Cloudflare Function,
  deployt zunächst nach `verify`, prüft dort den Anmeldeschutz und aktualisiert
  erst danach `https://picam-docs.pages.dev`.
* Die Pages Function erlaubt Zugriff nur nach Forgejo-OAuth und bestätigtem
  Leserecht auf `l.hentschke/picam-ai`; Details in [HOSTING.md](HOSTING.md).
* Drei veraltete interne Anker im Dotmatrix-Plan sind an Zensicals erzeugte
  ASCII-IDs angepasst; der Doku-Build meldet keine Probleme mehr.
* Der produktive Forgejo-Lauf `docs.yml` für den Integrationsstand `39cad8f`
  endete erfolgreich. `https://picam-docs.pages.dev` leitete danach ohne
  Sitzung weiterhin mit HTTP 302 zur Forgejo-OAuth-Anmeldung um.

## Verifikation vor dem Merge

Ausgeführt im isolierten Zensical-Worktree mit eigener Projekt-`.venv`
(`--system-site-packages`, Paketinstallation `--no-deps`):

* `./.venv/bin/pytest`: **482 bestanden, 3 übersprungen, 1 xfailed**
* `./.venv/bin/ruff check .`: **ohne Befund**
* `npx --yes node@22 --test cloudflare/test/middleware.test.js`:
  **12 bestanden**
* `./scripts/docs-site.sh build`: **Build erfolgreich, keine Probleme**
* Workflow-YAML geladen; Trigger und Produktions-Gates statisch geprüft

Die seriellen Tests erzeugen ihren minimalen Rückstellpunkt jetzt selbst im
temporären Testverzeichnis. Sie benötigen keine ignorierte Labordatei mehr und
sind damit in frischen Worktrees reproduzierbar.

## Merge-Grenze

`docs/zensical-prototyp` und `feat/task-b-versatz-normierung` zweigen beide bei
`3136b18` ab. Dieser Merge enthält den Zensical-/Cloudflare-Zweig, **nicht** den
späteren Commit `465bcca` aus `feat/task-b-versatz-normierung`. Dessen
uncommittierte Dateien im Haupt-Worktree wurden nicht verändert.

## Weiterhin wichtig

* Die Kamera bleibt wegen OQ-22 auf höchstens 960×720 begrenzt; einen hängenden
  Kameraprozess nicht hart beenden.
* Für die Ernte gilt weiterhin der festgelegte Sicherheitsabstand **M = 695 ms**.
* Das GSVmulti-Telegramm bleibt unbekannt (OQ-07); `AsciiCsvFormatter` ist
  weiterhin nur provisorisch.

## Nächster Schritt

`feat/task-b-versatz-normierung` kann unabhängig weitergeführt oder separat
integriert werden. Vor einem späteren Merge die dortigen uncommittierten
Änderungen und den gemeinsamen Abzweig bei `3136b18` berücksichtigen.
