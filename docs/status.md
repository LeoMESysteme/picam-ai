# Status — Stand 2026-09-28

Diese Datei wird zum Sessionende überschrieben. Historie: `CHANGELOG.md` und
`docs/project_history.md`. Arbeitsliste: [../TODO.md](../TODO.md).

## Aktueller Zweig und Zustand

Die Arbeit liegt im Worktree `/home/me-systeme/picam-ai-ernte` auf
`feat/task-b-versatz-normierung` (gepusht). Der Haupt-Checkout
`/home/me-systeme/picam-ai` steht auf `master`; dort arbeitet der Nutzer an
der Doku-Site. `var/` gibt es nur einmal, unter
`/home/me-systeme/picam-ai/var`; der Worktree verlinkt es per Symlink. Der
Zweig ist **noch nicht zur Integration freigegeben**.

**Kamera:** Seit 2026-09-25 ist die Logitech StreamCam (USB 3, UVC,
`046d:0893`) die aktive Kamera, die IMX500 ist außer Betrieb
([project_history.md](project_history.md), 2026-09-25). Die Umstellung
folgt [Spec](superpowers/specs/2026-09-25-streamcam-switch-design.md) und
[Plan](superpowers/plans/2026-09-25-streamcam-switch.md). Tasks 1–6 und die
Befunde des Abschlussreviews (Task 7) sind umgesetzt, reviewt und
committet. Ledger mit Rulings:
`.superpowers/sdd/2026-09-25-streamcam-switch/progress.md` (ignoriert).

## Letzter Befund

* **StreamCam an der Hardware geprüft (2026-09-28):**
  `camera-commissioning.sh` Exit 0 (6/6, USB3, Testbild 1920×1080 scharf),
  `pytest --mode=real tests/test_uvc_hardware.py` grün (30 Bilder, alle 11
  Regler zurückgelesen). 10-s-Probeaufnahme mit `--frame-rate 15`: 137
  Bilder, `frame_gaps.count = 0`, kein Drop, Versatz BOOTTIME − MONOTONIC
  −9/+10 ns ([VALIDATION.md](VALIDATION.md), 2026-09-28).
* **Messsitzung 2026-09-28:** Timing-Kalibrierung steht, M = 1225,8 ms
  aus drei Aufnahmen (Nutzerentscheidung: Maximum über alle, konservativ),
  `var/calibration/timing-streamcam.json`. Zwei neue scharfe Aufstellungen
  geerntet und importiert: `sc1` (schräg, Profil `sc1b`, 45 Proben), `sc2`
  (frontal, 58 Proben); Datensatz 492 Proben ([VALIDATION.md](VALIDATION.md),
  2026-09-28). Neu dafür: `display-offset.py --profile` (Task 8),
  `import-harvest.py` übersteht Drop-Zeilen (Task 9).
* **Dot-Matrix-Leser:** fertig und geprüft, nie ein falscher Wert. Die
  festgelegte Messung scheitert an zu weichen Aufstellungen im Training
  ([OQ-42](open-questions.md), [VALIDATION.md](VALIDATION.md) 2026-09-25).
  Es braucht scharf fokussierte Aufstellungen, jetzt mit der StreamCam.
* **`var/` nach versehentlicher Löschung (2026-09-25) wiederhergestellt:**
  alle 389 Proben laden, Profile, `devices.json` und der
  GSV-Rückstellpunkt sind zurück. Verloren sind die Einzelbilder der
  Ernte-Aufnahmen und die meisten Diagnosebilder. Details:
  `var/rescue-20260925/NOTES.md`. Eine Sicherung für `var/` fehlt noch.

## Nächste Schritte

1. OQ-42 entscheiden (Nutzer), dann `dotmatrix-eval.py loo` mit fünf Gruppen.
2. Befunde der Messsitzung abarbeiten (TODO.md): Fokus-Sweep liest nach
   großen Sprüngen ein veraltetes Pufferbild (M-9), Glasdetektor scheitert an
   der StreamCam, Raster-Prüfung auf 8 Zeilen in `propose`, JPEG-Warteschlange.
3. Sicherung für `var/` auf einem anderen Medium einrichten (lokale erste
   Sicherung: `/home/me-systeme/var-backups/var-20260928-vor-import.tar`).
4. Zweig nach `master` integrieren; die Gates der Doku-Site müssen auf dem
   zusammengeführten Stand laufen.

Mock-Suite am 2026-09-28: 690 bestanden, 3 übersprungen, 1 erwarteter
Fehlschlag; Ruff ohne Befund. Das GSVmulti-Telegramm bleibt OQ-07.
