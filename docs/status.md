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
  ROM-Gegenprobe je Zeichen 0 Abweichungen.
* **Aufstellung `sc4`** (2026-09-29, flacher und schräg von links): 79
  Proben, 0 Abweichungen vom ROM. Datensatz 514 Proben (Dot-Matrix 426).
* **Timing-Kalibrierung neu** (2026-09-29, `sc3-cal-a/b/c`, Kamera fest):
  M = 325,9 ms, Anzeigeversatz 89,6 ms, σ_δ 2–26 ms. Ersetzt die vorläufige
  Datei aus den verschobenen Aufnahmen (M = 1225,8 ms).
* **Aufstellung `sc5`** (2026-09-29, leicht von oben, schräg von rechts,
  Punktkontrast 41): 114 Proben, ROM 0. `sc3` mit korrigiertem Profil `sc3b`
  neu importiert (47). Datensatz 629 Proben, davon 541 aus dem Dot-Matrix-Gerät.
* **Dot-Matrix-Leser, festgelegte Messung** (`loo`, Regel `rom_per_group`,
  OQ-42): nie ein falscher Wert. `sc4` 79/79, `sc5` 114/114, `ernte1` 133/152
  richtig. `sc3` 0/47: Die Punktschwärze fällt dort über das Glas von links
  nach rechts ab (Blickwinkel), und `normalized()` misst den Tintenpegel nur
  global. `auf2`/`auf3` abgelehnt.
* **SD-Karte** lief am 2026-09-28 voll (Aufnahmen 1,3–1,8 GB); Einzelbilder
  der verworfenen Aufnahmen gelöscht, nach dem Löschen der Einzelbilder 2026-09-29 9,1 GB frei. Lokale Sicherungen unter
  `/home/me-systeme/var-backups/`, keine auf einem anderen Medium.

## Zensical-Doku und Pflege

Aus `master` übernommen (Stand 2026-09-24): Doku-Site mit Zensical,
Hosting auf Cloudflare Pages mit Forgejo-Anmeldung, täglicher
Codex-Pflegelauf über den Runner `picam-codex-docs` mit OQ-Index, strengem
Build, Vorschau-Ankern und Browsertests vor jedem Push. Details:
[HOSTING.md](HOSTING.md), [project_history.md](project_history.md) 2026-09-23.

Prüfung am 2026-09-29: Der Pflegeworkflow startet täglich um 06:00 Uhr
(Europe/Berlin) oder manuell, aber nicht bei Pushes auf `master`. Der
Codex-Runner nahm den geplanten Lauf um 06:00:41 Uhr an. Die späteren
Commits auf `master` lösen daher keinen eigenen Pflegelauf aus; der nächste
geplante Lauf prüft den dann aktuellen Stand.

## Nächste Schritte

1. Entscheidung: Tintenpegel je Zelle als Spezifikationsänderung (wegen `sc3`) oder weitere Aufstellungen; danach `loo` erneut.
2. Werkzeug für die Punktgitter-Anpassung in `harvest-setup`, Fix für den
   Fokus-Sweep (M-9), Speicherplatz vor Aufnahmen prüfen.
3. Sicherung von `var/` auf ein anderes Medium.

Das GSVmulti-Telegramm bleibt OQ-07.
