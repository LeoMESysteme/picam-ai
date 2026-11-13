# Autonomer Arbeitsplan bis Mittwoch 2026-11-18 (Claude)

Leonhard ist bis Mittwoch weg. Erteilt am 2026-11-13 abends. Dieser Plan ist der
Wiedereinstieg für jede `/loop`-Runde: erst hier den Fortschritt lesen, dann den
nächsten offenen Punkt bearbeiten und den Fortschritt unten eintragen.

## Freigaben (wörtlich aus der Rückfrage)

- **Codex-Ergebnis reviewen:** Rahmen/Raster (`fix/rahmen-raster`). Bei grün nach
  `feat/integration` mergen.
- **Werkbank-Dienst neu starten:** „Ja, wenn reviewt“. Nur reviewte, grüne Stände,
  nur wenn kein Lauf aktiv ist (`bridge status` über den Socket prüfen).
- **Master:** „ja kannst du. beachte aber das gerade eine andere session das wiki
  erweitert und ein neues design/theme entwickelt“.
  - `feat/integration` → `master` erst nach grüner voller Suite.
  - Vorher den aktuellen `origin/master` und offene Wiki-Branches ansehen.
  - Wiki- und Theme-Dateien (Zensical, `sites/`, `docs/`-Theme, Wiki-Gerüst) nie
    überschreiben. Konflikte dort nicht selbst auflösen, sondern stehen lassen und
    notieren.
- **EXE-Runde 3 fertigstellen:** ohne Leonhards Sichtprüfung kein Merge nach
  `feat/integration`. Prüfanleitung für Mittwoch schreiben.
- **Kleine Backend-Punkte:** als Codex-Handoff oder selbst, mit Tests.
- **Specs vorbereiten:** Wiki-Seite Ausgabewege, UART-Prüfsumme mit Wiederholung,
  One-Line-Installer und TUI.
  - Leonhards Beschreibung: TUI/CLI führt visuell durch das Setup im Terminal. Von ihr
    aus sieht man Status und Logs und kann die Werkbank starten, stoppen,
    konfigurieren, Fehler suchen und aktualisieren.
  - Er wünscht einen ersten Entwurf, gern mit dem Skill `terminal:tui-design`.
  - Er wünscht eine aufgeräumte Codebase und ein Setup, das auf anderen Raspberries
    reibungslos läuft. So weit wie möglich vorantreiben; der Test auf einem anderen
    Pi folgt später.

## Regeln

- `AGENTS.md` und `CLAUDE.md` gelten.
- **Wer was macht:**
  - Codex nur für Backend.
  - UI an Claude-Subagenten, Sonnet als Standard.
  - Codex mit `< /dev/null` starten und kann nicht committen.
- **Keine Freigabe für:**
  - Kernel- oder Reboot-Arbeit
  - Eingriffe in andere Sessions
  - Löschen fremder Branches
- Commit und Push nur auf eigene Branches bzw. `feat/integration` und `master` wie oben.
  Attribution laut System.
- Jede Runde endet mit einem Eintrag unter „Fortschritt“ und einem Push.

## Reihenfolge

1. [x] Codex-Report `.worktrees/rahmen-raster/REPORT-codex.md` reviewen, korrigieren,
       volle Suite (`DISPREAD_DEV_DATA=/mnt/ssd/picam-dev ./.venv/bin/pytest -q -n 4`),
       committen, Merge nach `feat/integration`, Werkbank neu starten (Regeln oben).
2. [x] `feat/integration` → `master` (Regeln oben).
3. [x] Kleine Backend-Punkte:
       - App-Zähler 123/124 im Empfangstest
       - Port je Zeile in `details.jsonl`, nur der aktuelle Start, Leerlauf zusammenfassen
       - Adapterwechsel ins Journal
       - 3× `uart_timeout` beim UART-Verbinden
       - Anzeige „Erneut prüfen“ (UI, Runde 3)
4. [ ] EXE-Runde 3: `wip/bruecke-ux3` auf `feat/integration` rebasen bzw. mergen, R3-Test
       `test_value_field_ground_token[False]` reparieren, offene Punkte aus
       `TODO.md` („EXE, Gestaltung“) und dem Prüfbericht. Volle Windows-Suite, `ux_tour`
       hell und dunkel offscreen, `windows/bridge/PRUEFUNG-UX3.md` für Mittwoch. Branch
       pushen, nicht mergen.
5. [ ] Specs:
       - Wiki-Seite Ausgabewege (aus `docs/quellen/ausgabewege-vergleich-2026-11-13.md`;
         nur als Entwurf, die Wiki-Session nicht stören)
       - UART-Prüfsumme mit Wiederholung
       - One-Line-Installer und TUI (`terminal:tui-design`), dazu eine Bestandsaufnahme
         der Installationsschritte und Hardcodings, die ein frischer Pi braucht
         (Single Source of Truth, keine festen Pfade und IDs)

## Fortschritt

- 2026-11-13 abends: Plan angelegt. Codex arbeitet Handoff Rahmen/Raster ab.
- 2026-11-13 19:40: **Punkt 1 erledigt.** Codex-Ergebnis reviewt (Fokusband 0,95–1,05 mit
  Ablehnung, Raster A1+B1 63/65). Nacharbeit: `docs/status.md` zusammengeführt statt
  überschrieben, Szenen-Fixtures nachgezogen, Bericht nach
  `docs/quellen/rahmen-raster-2026-11-13/`, Overlays als JPEG (Originale auf der SSD), veralteter
  Playwright-Hinweistext (seit c322f40 rot) korrigiert. Pi-Suite 4228 grün plus 1 Fixture
  behoben, Node 289, Doku-Playwright 91, Live-Playwright 64/65 plus 1 Wackler (OQ-71, einzeln
  grün). Merge `95d0540`, Werkbank darauf neu gestartet (kein Lauf aktiv, Pi-ID unverändert).
  Für Mittwoch: Das Fokusband kann gute Starts sperren (ein guter Lauf lag bei 1,418).
- 2026-11-13 ~20:15: Punkt 2 läuft. Probe-Merge `origin/master` + `feat/integration` im
  Scratch-Worktree `mtest`, Konflikte nur CHANGELOG.md und docs/status.md (beide Seiten
  behalten). Volle Suite darauf läuft. Wiki-Session arbeitet uncommittiert auf
  `feat/wiki-lebendig` (Basis b22d64a = origin/master); berührt sich mit unserem Merge in
  CHANGELOG.md und tests/docs-site.spec.ts. Das ist beim Merge der Wiki-Session zu beachten.
  Parallel aus Punkt 5 erledigt: Spec-Entwürfe Wiki-Seite Ausgabewege, UART-Prüfsumme (mit
  Befund „stiller Wertfehler möglich“), Installer/TUI inklusive Bestandsaufnahme L1–L11.
- 2026-11-13 ~20:30: **Punkt 2 erledigt.** `master` = `d6d5ab5` (Merge von `feat/integration`,
  Konflikte nur CHANGELOG.md beidseitig und docs/status.md mit Hosting-Abschnitt aus master).
  Volle Suite auf dem Merge 4236 bestanden, strikter Doku-Build sauber. `feat/integration`
  per Fast-Forward auf denselben Stand. **Hinweis für die Wiki-Session:** `feat/wiki-lebendig`
  basiert auf b22d64a; beim Nachziehen von master berühren sich CHANGELOG.md und
  tests/docs-site.spec.ts (dort hat die Wiki-Session uncommittete Änderungen). Nicht selbst
  aufgelöst. Der Push auf master löst den Doku-Workflow aus (Deploy prüfen).
  Punkt 3 vorbereitet: Handoff auf `fix/kleine-backend` (Worktree `.worktrees/kleine-backend`).
  Punkt 4: Claude-Subagent arbeitet auf `wip/bruecke-ux3`.
- 2026-11-14 ~00:15: Rate-Limit 20:40–23:20 (Subagent EXE-Runde 3 brach ab, danach fortgesetzt).
  **Punkt 3 erledigt** (bis auf „Erneut prüfen“, das zur EXE-Runde 3 gehört): Codex-Ergebnis
  reviewt, `docs/status.md` erneut vor Überschreiben bewahrt, Windows-Suite 669 bestanden
  (auch die 13 Sandbox-Fälle), Pi-Brückentests 164, ruff sauber. Merge `0c26a43` in
  `feat/integration`. Die Textwünsche für die Journal-Ereignisse (`adapter_*`, `port_*`) und
  den Zähler stehen in `docs/quellen/kleine-backend-2026-11-13/REPORT-codex.md` (für Runde 3).
  Werkbank nicht neu gestartet: Die Pi-Seite ändert sich nur in `gsv_bridge.py`, und das läuft
  in der Windows-App, nicht im Dienst.
- 2026-11-14 ~00:45: CI auf master `d6d5ab5`: Build und Deploy der Doku-Seite erfolgreich,
  Workflow „Playwright Tests“ **fehlgeschlagen**. Schritt-Logs sind per Token nicht lesbar.
  Lokale Nachstellung auf `feat/integration` (= master + Punkt 3): Doku 91 bestanden,
  Werkbank 64 bestanden plus 1 flaky (bekannter Wackler „UART direkt ohne Haken sendet über
  Enter und runStart nichts“, Zeile 2186, Fehlertext bleibt leer). CI lief 19:59 parallel
  zur vollen Suite (Volllast); vermutlich derselbe Wackler zweimal. Nicht belegt. Nächster
  master-Push lässt den Workflow erneut laufen; Leonhard kann auf der Actions-Seite den Schritt
  nachsehen.
