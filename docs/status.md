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
* **Noch nicht gemessen:** Zeitversatz Telegramm ↔ Glas und Schutzfenster M
  für die StreamCam. Ohne `var/calibration/timing-streamcam.json` startet
  `harvest.py` nicht. Das alte M = 695 ms gilt nur für die IMX500.
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

1. **Messsitzung mit dem Nutzer:** `harvest-setup.py focus` →
   `sync-record.py --source camera --camera-settings … --norm-schedule …` →
   `display-offset.py` → `timing-calibration.py`. Dabei prüfen, ob sich die
   „eingefrorenen" Belichtungswerte bei anderem Licht ändern (Befund M-10
   des Abschlussreviews).
2. Zwei scharf fokussierte Ernten mit der StreamCam, dann die
   Dot-Matrix-Messung erneut (OQ-42-Entscheidung vorher).
3. Sicherung für `var/` einrichten.
4. Zweig-Integration vorbereiten: Die Gates der Doku-Site (`master`) müssen
   auf dem zusammengeführten Stand laufen.

Mock-Suite am 2026-09-28: 682 bestanden, 3 übersprungen, 1 erwarteter
Fehlschlag; Ruff ohne Befund. Das GSVmulti-Telegramm bleibt OQ-07.
