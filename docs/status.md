# Status — Stand 2026-09-29

Diese Datei wird zum Sessionende überschrieben. Historie: `CHANGELOG.md` und
`docs/project_history.md`. Arbeitsliste: [../TODO.md](../TODO.md).

## Zweig und Zustand

`feat/task-b-versatz-normierung` (Kamerawechsel, Dot-Matrix-Leser, Ernten)
ist am 2026-09-29 nach `master` gemergt. `var/` gibt es nur einmal, unter
`/home/me-systeme/picam-ai/var` (gitignored); der Worktree
`/home/me-systeme/picam-ai-ernte` verlinkt es per Symlink.

**Kamera:** Logitech StreamCam (USB 3, UVC, `046d:0893`) seit 2026-09-25,
die IMX500 ist außer Betrieb ([project_history.md](project_history.md),
2026-09-25). Umstellung nach
[Spec](superpowers/specs/2026-09-25-streamcam-switch-design.md) und
[Plan](superpowers/plans/2026-09-25-streamcam-switch.md), Tasks 1–10
umgesetzt und reviewt. Ledger:
`.superpowers/sdd/2026-09-25-streamcam-switch/progress.md` (ignoriert).

## Letzter Befund

* **StreamCam an der Hardware geprüft** (2026-09-28): Inbetriebnahme Exit 0,
  Hardwaretest grün, Aufnahmen ohne Bildlücke ([VALIDATION.md](VALIDATION.md)).
* **Kamera muss fest stehen.** Die ersten Aufstellungen `sc1`/`sc2` waren
  durch Bewegung der Kamera verschoben; ihre 103 Proben wurden wieder aus
  dem Datensatz genommen. Seit Task 10 prüft `import-harvest.py` jedes Bild
  gegen das Profilbild (`ausschnitt_verschoben`).
* **Aufstellung `sc3`** (Kamera fest auf dem Tisch, Reflexe durch Drehen des
  Displays vermieden): 46 Proben importiert, Ausrichtung max. 0,08 px,
  ROM-Gegenprobe je Zeichen 0 Abweichungen. Datensatz 435 Proben.
* **Timing-Kalibrierung neu** (2026-09-29, `sc3-cal-a/b/c`, Kamera fest):
  M = 325,9 ms, Anzeigeversatz 89,6 ms, σ_δ 2–26 ms. Ersetzt die vorläufige
  Datei aus den verschobenen Aufnahmen (M = 1225,8 ms).
* **Dot-Matrix-Leser:** fertig und geprüft, nie ein falscher Wert. Die
  festgelegte Messung (`loo`) wartet auf eine zweite scharfe Aufstellung und
  die Entscheidung zu [OQ-42](open-questions.md).
* **SD-Karte** lief am 2026-09-28 voll (Aufnahmen 1,3–1,8 GB); Einzelbilder
  der verworfenen Aufnahmen gelöscht, 7,6 GB frei. Lokale Sicherungen unter
  `/home/me-systeme/var-backups/`, keine auf einem anderen Medium.

## Zensical-Doku und Pflege

Aus `master` übernommen (Stand 2026-09-24): Doku-Site mit Zensical,
Hosting auf Cloudflare Pages mit Forgejo-Anmeldung, täglicher
Codex-Pflegelauf über den Runner `picam-codex-docs` mit OQ-Index, strengem
Build, Vorschau-Ankern und Browsertests vor jedem Push. Details:
[HOSTING.md](HOSTING.md), [project_history.md](project_history.md) 2026-09-23.

## Nächste Schritte

1. Zweite feste Aufstellung ernten, OQ-42 entscheiden, `dotmatrix-eval.py loo`.
2. Werkzeug für die Punktgitter-Anpassung in `harvest-setup`, Fix für den
   Fokus-Sweep (M-9), Speicherplatz vor Aufnahmen prüfen.
3. Sicherung von `var/` auf ein anderes Medium.

Das GSVmulti-Telegramm bleibt OQ-07.
