# Status — Stand 2026-09-24

Wird **überschrieben**, nicht angehängt. Historie in `CHANGELOG.md` und
`docs/project_history.md`.

## Sofort zu wissen

Die Zensical-Doku hat interaktive OQ- und Roadmap-Ansichten. Die OQ-Übersicht
wird aus `docs/open-questions.md` und den aktiven Aufgaben in `TODO.md`
erzeugt. Nach Änderungen an diesen Quellen
`./.venv/bin/python scripts/oq-index.py` ausführen. Der strenge Docs-Build
prüft den Index.

Für die Anleitung gibt es einen ersten Satz Kontextvorschauen: kurze
Glossarbegriffe und der Timing-Grundsatz öffnen sich beim Überfahren oder
Fokussieren eines Links. Zwei Codezeilen haben Erklärungen. API-Links zeigen
kurze Titel statt ganzer generierter Klassen. Die Pflegehinweise stehen in
`AGENTS.md` und `docs/HOSTING.md`.

Die Arbeit liegt auf dem Branch `docs/hover-previews` im Worktree
`/home/me-systeme/picam-ai-docs-zensical`. Eine Veröffentlichung erfordert
einen Merge nach `master` und den erfolgreichen Forgejo-Deploy. Der aktuelle
Cloudflare-Stand wurde in dieser Sitzung nicht geprüft.

## Verifikation dieser Sitzung

* `./scripts/docs-site.sh build -s`: erfolgreich.
* `npx playwright test -c playwright.docs.config.ts`: 12 bestanden.
* `./.venv/bin/pytest -q`: 490 bestanden, 3 übersprungen, 1 xfailed.
* `./.venv/bin/ruff check .`: ohne Befund.
* `./.venv/bin/python scripts/oq-index.py --check`: aktuell.
* `git diff --check`: ohne Befund.

## Nächster Schritt

Den Branch prüfen und in `master` integrieren. Nach dem Push den
Forgejo-Docs-Job und den Cloudflare-Deploy kontrollieren. Für das Produkt
bleiben OQ-22 (Kamera auf höchstens 960×720) und OQ-07 (unbekanntes
GSVmulti-Telegramm) zu beachten; `AsciiCsvFormatter` ist provisorisch.
