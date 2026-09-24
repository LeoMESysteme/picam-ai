# Status — Stand 2026-09-24

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Die Zensical-Seite zeigt jetzt eine OQ-Übersicht mit Fokus aus den aktiven
Aufgaben in `TODO.md` sowie eine aufklappbare Roadmap. Die Änderung liegt im
isolierten Branch `docs/zensical-prototyp`; sie ist noch nicht nach `master`
integriert oder auf Cloudflare veröffentlicht. Der vorhandene Produktions-Gate
deployed weiterhin nur nach einem Push auf `master` und prüft zuvor den
Anmeldeschutz.

## Doku und Hosting

* `scripts/oq-index.py` erzeugt die OQ-Tabelle und stabile `#oq-nn`-Anker.
  `./scripts/docs-site.sh build` prüft den Index vor jedem Build. Auf dem
  Stand dieses Branches ist **OQ-40** der einzige OQ-Fokus aus `TODO.md`.
* OQ-Filter, Suche, Statusfarben und Roadmap-Phasen laufen als lokale
  JavaScript/CSS-Assets. Ohne JavaScript bleiben die Quelltabellen lesbar.
* Die Doku wird nur noch auf `https://picam-docs.pages.dev` bereitgestellt.
  Das Offline-ZIP entfällt; bestehende `.html`-Links bleiben gültig.
* Die Pages Function verlangt weiter Forgejo-Anmeldung und Leserecht am Repo.
  Details und Wartung: [HOSTING.md](HOSTING.md).

## Verifikation

Im isolierten Doku-Worktree am 2026-09-24 ausgeführt:

* `./.venv/bin/pytest -q`: **490 bestanden, 3 übersprungen, 1 xfailed**
* `./.venv/bin/ruff check .`: **ohne Befund**
* `node --test cloudflare/test/middleware.test.js`: **12 bestanden**
* `./scripts/docs-site.sh build`: **Build erfolgreich, keine Probleme**
* Playwright: **6 Browserprüfungen** zu OQ-Filter und Suche, Phasen und Links, Sofortnavigation,
  Mobilbreite, dunkles Design und Ansicht ohne JavaScript geprüft

## Stand anderer Arbeiten

Dieser Branch enthält noch nicht die neuere Kamerabrücken-Dokumentation und
die TODO-Priorisierung aus `feat/task-b-versatz-normierung`. Bei deren späterer
Integration muss `./.venv/bin/python scripts/oq-index.py` erneut laufen;
sonst stoppt der Doku-Build. Die Kamera bleibt wegen OQ-22 auf höchstens
960×720 begrenzt; einen hängenden Kameraprozess nicht hart beenden. Für die
Ernte gilt weiterhin **M = 695 ms**. Das GSVmulti-Telegramm ist unbekannt
(OQ-07); `AsciiCsvFormatter` bleibt provisorisch.

## Nächster Schritt

Den Doku-Branch reviewen und getrennt von den Kameraänderungen nach `master`
integrieren. Der bestehende Workflow prüft den Schutz auf `verify`, bevor er
Produktion aktualisiert. Der Commit-Graph ist eine spätere Ausbaustufe.
