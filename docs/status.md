# Status — Stand 2026-09-24

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Die interaktiven OQ- und Roadmap-Ansichten wurden mit Commit `9462a2e` nach
`master` gepusht. `origin/master` zeigte bei der Prüfung auf diesen Commit.
Ob der anschließende Cloudflare-Deploy erfolgreich abgeschlossen wurde, ist
ohne Forgejo-Jobstatus nicht bestätigt; ein anonymer Aufruf der Pages-Adresse
führte zur Forgejo-Anmeldung. Die Kamera- und OQ-22-Branches sind separat
gepusht und noch nicht in `master` integriert.

Zur Pflege der Zensical-Ansichten wurden Anweisungen für TODO-, OQ- und
Roadmap-Änderungen ergänzt. Die Browserprüfungen hängen nicht mehr an einer
festen OQ-Zahl oder OQ-Nummer und prüfen die sichtbaren Filter- und
Suchergebnisse auf ihren Inhalt.

## Doku und Hosting

* `scripts/oq-index.py` erzeugt OQ-Tabelle und stabile `#oq-nn`-Anker aus
  `docs/open-questions.md` und den aktiven Aufgaben in `TODO.md`. Der Docs-Build
  prüft den Index vor dem Bauen. Auf dem Stand von `master` ist OQ-40 der
  einzige „Jetzt“-Eintrag.
* Die Roadmap-Ansicht nutzt die erste Tabelle in `docs/ROADMAP.md`. Bei einer
  Änderung der Phasen- oder Spaltenstruktur müssen JavaScript und Browsertest
  gemeinsam angepasst werden. Die Pflegeregeln stehen in `AGENTS.md` und
  `docs/HOSTING.md`.
* Die Seite liegt unter `https://picam-docs.pages.dev`; das Offline-ZIP
  entfällt. Die Pages Function verlangt Forgejo-Anmeldung und Repo-Leserecht.

## Verifikation dieser Sitzung

* Ausgangsstand: `./.venv/bin/pytest -q`: 490 bestanden, 3 übersprungen,
  1 xfailed; `./scripts/docs-site.sh build -s`: erfolgreich.
* Regressionsprobe: Eine temporäre 42. OQ ließ den alten Browsertest an der
  festen Erwartung 41 scheitern. Nach Anpassung bestanden alle sechs
  Browsertests auch mit 42 OQs. Die Prüffrage wurde danach entfernt.
* Abschlussprüfung nach Entfernen der Prüffrage:
  `./.venv/bin/pytest -q`: 490 bestanden, 3 übersprungen, 1 xfailed;
  `./.venv/bin/ruff check .`: ohne Befund;
  `./scripts/docs-site.sh build -s`: erfolgreich;
  `npx playwright test -c playwright.docs.config.ts`: 6 bestanden;
  `./.venv/bin/python scripts/oq-index.py --check`: aktuell.

## Nächster Schritt

Den Forgejo-Jobstatus des nächsten `master`-Pushs prüfen. Wenn die neueren
Kamera-/OQ-22-Branches später folgen, den OQ-Index erneut erzeugen und die
Roadmap auf neue Belege prüfen. Die Kamera bleibt wegen OQ-22 auf höchstens
960×720 begrenzt; einen hängenden Kameraprozess nicht hart beenden. Für die
Ernte gilt M = 695 ms. Das
GSVmulti-Telegramm ist unbekannt (OQ-07); `AsciiCsvFormatter` bleibt
provisorisch.
