# Status — Stand 2026-09-29 (Sessionende)

Diese Datei wird zum Sessionende überschrieben. Historie: `CHANGELOG.md` und
`docs/project_history.md`. Arbeitsliste: [../TODO.md](../TODO.md).

## Zweig und Zustand

Alles liegt auf `master` und ist gepusht. `var/` gibt es nur einmal, unter
`/home/me-systeme/picam-ai/var` (gitignored). Der Worktree
`/home/me-systeme/picam-ai-ernte` verlinkt es per Symlink. Codex arbeitet im
Worktree `/home/me-systeme/picam-ai-assist` (Branch
`feat/einrichtungsassistent`) am Einrichtungsassistenten. Der Branch ist
**nicht gemergt**, siehe unten.

**Kamera:** Logitech StreamCam (USB 3, UVC, `046d:0893`) seit 2026-09-25.
Die IMX500 ist außer Betrieb ([project_history.md](project_history.md),
2026-09-25).

## Wo wir stehen: Abnahme 2 des Dot-Matrix-Lesers läuft

* **Abnahme 1** (Stufe 2, `ink_per_cell_v1`): nicht bestanden, 0 falsch.
  `ab2` wurde an einer Spiegelkante in der Leerzelle 8 zu 100 % abgelehnt.
* **Entwicklungsrunde erledigt:** Normierung `bg_closing_v1`, also
  Hintergrund je Punkt per Grauwert-Schließung (Commit `50d68d6`, Spec §2
  Punkt 3 mit vorab festgelegtem Kriterium). `loo` mit 942 Proben:
  * 0 falsch,
  * `ab2` 83/83,
  * alle scharfen Gruppen vollständig richtig,
  * die unscharfe Gruppe `auf2` wird jetzt vollständig abgelehnt (vorher
    63/76). VALIDATION.md.
* **Stufe 2 erneut eingefroren:** Vorlagen
  `var/dotmatrix/templates-stufe2b-2026-09-29.json`, sha256
  `fc3b44bdc880372a600168218560a3926fa307fe533b2592f7c4c244a89aa75e`, Code
  `ef5cedf`.
* **Abnahme 2:**
  * `ab3` (frontal, nah, 10,9 px je Punktspalte) ist geerntet und
    importiert.
  * `ab4` (schräg von rechts, anderes Licht) fehlt noch.
  * Danach **ein einziger** `abnahme`-Lauf über `ab3,ab4`.
  * Den Leser beim Einrichten von Abnahme-Aufstellungen nicht gegenlesen
    (Auswahlverzerrung).

## Weitere Befunde des Tages

* **Bildverluste behoben:** Die SD-Karte blieb sekundenlang stehen, bis
  34 % Verlust. Seit `dc8af22` nimmt `harvest.py` über
  `sync-record.py --staging-root /dev/shm` zuerst in den RAM auf. Die
  Probeernte `sc6b` und `ab3` hatten 0 Verluste und keine langen
  Telegrammlücken mehr. Eine Ernte braucht bis etwa 3,6 GB `MemAvailable`,
  sonst lehnt sie vor dem Start ab.
* **SD-Karte:** No-Name `SD16G`, meldet 50 GiB, echte Kapazität unklar.
  Aufgeräumt (Codex-Plugin-Kopien, Caches), `fstrim` gelaufen. `var/` ist
  **nicht** auf einem anderen Medium gesichert, nur lokal unter
  `/home/me-systeme/var-backups/`.
* **Einrichtungsassistent (Codex):** Das Review ergab: zurück an Codex.
  Es gibt zwei Fälle, in denen er ein falsches Raster annimmt, und `sc6`
  scheitert ganz (feste Pixelkonstanten). Der Auftrag steht als
  „Nacharbeit 1“ im
  [Plan](superpowers/plans/2026-09-29-einrichtungsassistent.md).

## Zensical-Doku und Pflege

Doku-Site mit Zensical, Hosting auf Cloudflare Pages mit Forgejo-Anmeldung,
täglicher Codex-Pflegelauf über den Runner `picam-codex-docs`. Die
Job-Bedingung, die geplante Läufe übersprang, ist entfernt. Die manuelle
Vorschau 72 lief am 2026-09-29 durch. Der nächste geplante Publish-Lauf
steht noch aus. Details: [HOSTING.md](HOSTING.md).

## Nächste Schritte

1. `ab4` aufbauen und ernten, dann `dotmatrix-eval.py abnahme` über
   `ab3,ab4` (Befehl in TODO.md).
2. Codex' Nacharbeit am Einrichtungsassistenten reviewen und mergen.
3. `var/` auf ein anderes Medium sichern, die Kapazität der Karte prüfen.

Das GSVmulti-Telegramm bleibt OQ-07.
