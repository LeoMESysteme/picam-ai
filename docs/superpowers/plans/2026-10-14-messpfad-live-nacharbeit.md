# Messpfad live — Nacharbeit nach dem ersten echten Einrichtungsversuch

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Implementer: Codex (`codex exec`, Sandbox ohne Commits, `PYTHONPATH=src`); Reviews und Playwright-Läufe: Claude-Subagenten außerhalb der Sandbox.

**Goal:** Die Einrichtung auf `/live` soll an einer normalen frontalen Aufstellung zuverlässig durchlaufen, schneller fokussieren, kürzer warten und im Fehlerfall nachvollziehbar sein; die Oberfläche wird mit Playwright geprüft.

**Spec:** `docs/superpowers/specs/2026-10-12-messpfad-live-design.md` (bindend). Vorgängerplan: `docs/superpowers/plans/2026-10-12-messpfad-live.md`.

## Befund 2026-10-14 (erster echter Einrichtungsversuch, Werkbank auf Port 8081)

* Versuch 1: Kamera sehr nah (Glas ≈ 990 px breit) → `keine_startlage`.
* Versuch 2 (Glas ≈ 720 px (1920-px-Bild), frontal): Startsuche ok, aber „Rasterversatz 2j meldet FEHLER“. Offline mit dem angezeigten Text `+0.46801 ` ist 2j nach der Nachkorrektur **OK** (0,04/0,05) — der serielle Zellentext des Live-Laufs ist nicht gespeichert, Ursache dort ungeklärt (vermutlich maskierte Zellen durch wackelnde letzte Stelle).
* Versuch 3 (gleiche Aufstellung, Zellentext eingegeben): `keine_startlage`.
* **Ursache:** `fit_lattice` (Startsuche) ist rauschempfindlich. Auf derselben Aufstellung: heute 1 von 3 Einzelbildern ok; `sc7`-Ernte 5/6 Einzelbilder, **6/6 bei Mittel aus 8 Bildern**.
* Fokus-Sweep misst 38 Stellungen (32 grob + fein) mit je ~1 s Einschwingen ≈ 45 s; die Kurven sind eingipflig (Maximum heute bei 46–68).
* Stabilitätsmessung wartet fest ≥ 30 s (`STABILITY_MIN_ELAPSED_S`).
* Ungeschützt: `/live` ohne Anmeldung liefert ein nacktes 401 statt der Anmeldeseite.

## Global Constraints

* Freigabegrenzen bleiben unverändert scharf: 2j-Schwellen, Gegenlesen, FEHLER sperrt, WARNUNG nur mit Kenntnisnahme. Robustheit kommt aus besseren Eingangsbildern und Wiederholung der **Suche**, nie aus gelockerten Prüfungen.
* Die Kommandozeile `scripts/harvest-setup.py` behält ihr Verhalten (30-s-Stabilität für Ernten); neue Schnellwerte gelten nur für die Werkbank, soweit unten nicht anders gesagt.
* Kein Commit an `src/`/`scripts/` ohne Punkt im CHANGELOG-Abschnitt `## 0.1.0.dev0 — 2026-10-12 (Messpfad live)`.
* Tests ohne Hardware; Python mit `PYTHONPATH=src`; Codex committet nicht.

## Review Focus

1. Fokus-Suche auf flachem Kurvenstück (weit weg vom Gipfel) bleibt nicht am falschen Ort stehen.
2. Gemittelte Standbilder: Zellentext und Bild gehören zum selben Zeitfenster (serielle Klammer um die ganze Mittelung).
3. Wiederholte Startsuche verändert nicht, welches Bild Referenz und 2j-Grundlage ist (immer das erfolgreiche Mittelbild und sein Text).
4. Kürzere Stabilität nur auf der Werkbank; CLI bleibt bei 30 s.
5. Seite: Anmeldeweiterleitung führt nach dem Login zurück auf `/live`.

---

### Task N1: Fokus als Bergsteigen statt Vollsweep

**Files:** `src/dispread/focus_sweep.py`, `src/dispread/live/setup.py` (`focus_camera`), `src/dispread/live/service.py` (Startwert), Tests `tests/test_focus_sweep.py` (bestehende Datei erweitern oder neu), `tests/test_live_setup.py`.

Neue Funktion in `focus_sweep.py` (die alte `sweep_focus` bleibt als Rückfall):

```python
def climb_focus(
    measure: Callable[[int], float],
    start: int = 48,
    step: int = 8,
    fine_step: int = 2,
    lo: int = 0,
    hi: int = 255,
    flat_tolerance: float = 0.05,
) -> tuple[int, list[tuple[int, float]]]:
    """Bergsteigen: ab `start` in Schritten `step` in die Richtung, in der die
    Schaerfe steigt; faellt sie nach einem Anstieg, ist der Gipfel ueberschritten.
    Dann dasselbe mit `fine_step` um den besten Wert. Ein Fokuswert wird nie
    zweimal gemessen. Kein Anstieg in beiden Richtungen (flach, Unterschied
    < `flat_tolerance` relativ) -> Rueckfall auf `sweep_focus` mit denselben
    Messungen als Startbestand (keine Wiederholung schon gemessener Werte).
    Rueckgabe wie `sweep_focus`: (bester Fokus, Messungen in Reihenfolge)."""
```

Algorithmus (verbindlich):
1. `s0 = measure(start)`. Nachbarn `start+step` und `start-step` (begrenzt auf `[lo, hi]`): erst `+step` messen; ist er relativ um mehr als `flat_tolerance` besser → Richtung `+1`; sonst `-step` messen; ist der besser → Richtung `-1`; sonst ist `start` Grob-Gipfel (beide Nachbarn schlechter) — außer beide sind innerhalb `flat_tolerance` gleich (flach) → Rückfall.
2. In Richtung weiter messen, solange der neue Wert besser als der bisher beste ist; der erste Wert, der um mehr als `flat_tolerance` schlechter ist als der beste, beendet den Grob-Lauf; Werte innerhalb der Toleranz (Plateau) gehen weiter. Grenze `lo`/`hi` beendet ebenfalls.
3. Fein: von bestem Grobwert aus in beide Richtungen mit `fine_step` bis höchstens `step - fine_step` Abstand, je Richtung abbrechen, sobald der Wert schlechter wird.
4. Rückfall auf `sweep_focus`, wenn nach Schritt 1 flach: dabei bereits gemessene Werte nicht erneut messen (gemeinsame `seen`-Menge).

Tests (synthetische Kurven, Zähler für Messungen): Gipfel bei 46 von Start 48 → ≤ 10 Messungen, Ergebnis 46±2; Gipfel bei 68 von Start 48; Gipfel bei 12; Gipfel bei 250 (Grenze); Plateau weit weg (Start 200 auf flachem Rand, Gipfel bei 50) → Rückfall findet 50±2; leichtes Rauschen (±2 %) ändert das Ergebnis höchstens um einen Fein-Schritt.

`focus_camera` nutzt `climb_focus(measure, start=start_focus)` mit neuem Parameter `start_focus: int = 48`; `LiveService._run_setup` übergibt den Fokus des zuletzt bestätigten Profils dieser Werkbank-Sitzung, sonst 48. `camera-settings.json` bekommt `"focus_method": "climb"` bzw. `"sweep"` (bei Rückfall).

### Task N2: Gemittelte Standbilder und wiederholte Startsuche

**Files:** `src/dispread/live/setup.py`, `tests/test_live_setup.py`.

* Neue Funktion `mean_still(cam: SetupCamera, frames: int = 8, discard: int = 10) -> np.ndarray`: einmal `cam.fresh_still(discard=discard)`, dann `frames - 1` mal `cam.fresh_still(discard=0)`, Mittel in float32, gerundet zu uint8. `frames == 1` → Einzelbild wie bisher.
* `assist_measure(..., stack_frames: int = 1, fit_attempts: int = 1)`: Standbilder werden mit `mean_still(cam, stack_frames)` aufgenommen; die serielle Klammer (`CellTextSource`) umschließt die **ganze** Mittelung. Scheitert `fit_lattice` mit einem `str`-Grund, wird bis zu `fit_attempts - 1` mal ein neues Mittelbild (mit neuem Zellentext) aufgenommen und erneut gesucht; erst nach dem letzten Versuch `SetupError` wie bisher. Referenz (`still.png`), Vorprüfung, Stabilitäts-Zeitstempel und 2j beziehen sich auf das erfolgreiche Mittelbild und seinen Text. Jeder Versuch wird über `info(...)` gemeldet.
* Defaults bleiben 1/1 (CLI unverändert); die Werkbank (N3) setzt `stack_frames=8, fit_attempts=3`.
* Tests: Fake-Kamera mit Bildfolge; `mean_still` mittelt korrekt; `fit_lattice` (gepatcht) scheitert beim ersten Versuch und gelingt beim zweiten → Ergebnis nutzt Bild und Text des zweiten; alle Versuche scheitern → `SetupError` mit dem letzten Grund; Klammer: `CellTextSource` wird genau einmal je Versuch aufgerufen.

### Task N3: Werkbank-Einrichtung schneller und nachvollziehbar

**Files:** `src/dispread/setup_checks.py` (Parameter), `src/dispread/live/setup.py`, `src/dispread/live/service.py`, Tests.

* `check_setup(..., stability_min_elapsed_s: float = STABILITY_MIN_ELAPSED_S)` und `assist_measure(..., min_stability_s: float = MIN_STABILITY_S)` reichen die Grenze durch; Default 30 s (CLI unverändert).
* `LiveService._run_setup` ruft `assist_measure(..., stability_s=15.0, min_stability_s=15.0, stack_frames=8, fit_attempts=3)`.
* Diagnose: `_run_setup` schreibt `setup/cell-text.json` (Texte je Standbild, maskiert/unmaskiert, Quelle `seriell`/`eingabe`, Versuchsnummer) und bei Abbruch `setup/failure.json` (`step`, `reason`, Zeit). `status()["setup"]` bekommt `step` und `elapsed_s` seit Start.
* Tests in `tests/test_live_service.py`, `tests/test_setup_checks*.py`/`test_live_setup.py`.

### Task N4: Anmeldung und Live-Seite, Playwright-Prüfung

**Files:** `src/dispread/workbench/server.py` (guard/login), `src/dispread/workbench/static/live.js`, `live.html`, `tests/live_ui_server.py` (neu), `tests/live-ui.spec.ts` (neu), `playwright.live.config.ts` (neu), `tests/test_live_api.py`.

* Unangemeldeter `GET /live` → Weiterleitung auf `/login?next=/live`; nach erfolgreicher Anmeldung Weiterleitung auf `next`, nur wenn `next` ein lokaler Pfad ist (beginnt mit `/`, nicht `//`), sonst `/`. API-Routen (`/live/status` usw.) bleiben bei 401.
* Seite: während `setup_running` Schritt und vergangene Sekunden anzeigen; Fehlermeldung bleibt sichtbar bis zum nächsten Start.
* `tests/live_ui_server.py`: startet `make_app` mit Test-Verifier (`passwort == "test-only"`), einem Fake-`Controller`/`Terminals` wie in `tests/test_workbench.py` und einem skriptbaren Fake-`LiveService` (Zustände über eine kleine Test-Route `POST /__test__/state` setzbar, nur in diesem Testserver).
* `tests/live-ui.spec.ts` (Playwright, `playwright.live.config.ts` mit `webServer` auf diesen Testserver): Weiterleitung `/live` → Login → zurück auf `/live`; Zustände idle → setup_running (Schritt sichtbar) → setup_failed (Fehler + Hinweis sichtbar) → setup_ready (Overlays, Bestätigen-Box) → running mit frischem gültigem Wert (Ziffern grün) → Wert 0,9 s alt (STALE, keine Ziffern) → Verbindungsabbruch (STALE „Verbindung … verloren“).
* Playwright läuft außerhalb der Codex-Sandbox (Sockets) — Codex schreibt Spec und Server, der Controller lässt sie von einem Claude-Subagenten laufen und Fehler zurückspielen.

### Task N5: Echter Durchlauf am Aufbau (mit dem Nutzer)

Werkbank mit dem neuen Stand neu starten (Port 8081), Einrichtung über `/live` an derselben frontalen Aufstellung **dreimal hintereinander**; erwartet: jedes Mal Vorschlag (OK/WARNUNG), Fokus < 15 s, gesamte Einrichtung < 60 s. Danach Plan-Task 12 des Vorgängerplans (Lauf, Werte über `set norm`, Auswertung, Doku).

### Task N6: Lokale Steuerung der Live-Einrichtung (für Tests am Aufbau ohne Browser)

**Warum:** Die Einrichtung braucht keinen Handgriff am Aufbau. Über den vorhandenen lokalen Steuer-Socket (`server.py` `control`, Unix-Socket mit Modus 0600) soll sie sich ohne Browser-Anmeldung auslösen und beobachten lassen, damit Robustheit und Dauer an der echten Kamera wiederholt gemessen werden können.

**Files:** `src/dispread/workbench/server.py` (`control`), `src/dispread/workbench/cli.py`, Tests in `tests/test_live_api.py` oder `tests/test_workbench.py`.

* Neue Operationen am lokalen Socket: `live.status` (→ `LiveService.status()`), `live.setup` (Argument `cell_text` optional → `start_setup`), `live.stop` (→ `stop_run`), `live.camera` (→ `start_camera`). **Keine** Bestätigung und **kein** Laufstart über den Socket: Konzept §4 verlangt eine namentlich bestätigende Person in der Oberfläche.
* `LiveError` → Antwort `{"error": ...}` mit Status 409 wie bei HTTP.
* CLI: `dispread live status|setup [--cell-text TEXT]|stop|camera` (über `request(op, args)`), Ausgabe als JSON.
* Tests ohne Sockets wo möglich (Handler direkt mit Fake-Service aufrufen); der Socket-Weg selbst wird vom Controller außerhalb der Sandbox geprüft.

### Task N7: Punkterkennung in Punktgröße, engere Zeilengrenze, gestufte Startsuche

**Befund (Ursachenanalyse 2026-10-14, echte Standbilder):** Alle Punktdetektoren in `src/dispread/dotlattice.py` suchen lokale 3×3-Minima nach fester Glättung von 0,7 px. Scharfe LCD-Punkte (≈ 6,7×8,4 px, flacher dunkler Boden) liefern je Punkt 1–4 zufällig liegende Minima; der Zeilen-Restfehler ist dann Rauschen (rms_rows 0,22 bei Grenze 0,25), die Startsuche kippt bei kleinsten Bildunterschieden, und ein um eine Zeile verkipptes Raster wurde angenommen (nur 2j fing es ab). Mit Glättung in Punktgröße: richtige Raster rms_rows 0,05–0,09, falsche 0,19–0,23.

**Files:** `src/dispread/dotlattice.py`, `tests/test_dotlattice.py`, `tests/test_dotlattice_start_sc7.py` (bzw. neue Datei `tests/test_dotlattice_start_bench.py`), `tests/test_setup_checks.py` oder wo die betroffenen ab4/ab6-Tests liegen.

* Grundlage ist der gemessene Patch `.superpowers/sdd/2026-10-14-messpfad-live-nacharbeit/N7-fix.diff` (75 Zeilen): `_lattice_candidates` glättet je Achse mit σ = max(0,7, 0,2 × Punktabstand aus dem Quad) und gibt bei fehlenden Minima ein leeres Array zurück; `_MAX_RMS_ROWS` 0,25 → 0,15; `fit_lattice` mit bis zu drei Startdurchläufen (`_START_SIGMA_FRACTIONS = (None, 0.15, 0.18)`), ein weiterer Durchlauf **nur** nach `keine_startlage`; `startlage_mehrdeutig` und `vorzeichen_kein_plus` bleiben endgültig.
* Tests anpassen: `test_evaluate_quad_reports_validated_profile_despite_proxy_limit` (ab4, ab6) → „validiertes Profil liegt innerhalb der Grenzen“; `test_uncertain_real_still_start_is_rejected[ab6]` akzeptiert `keine_startlage` oder `startlage_mehrdeutig` (abgelehnt bleibt Pflicht).
* Neue Tests (überspringen ohne `var/`): die vier Standbilder vom 2026-10-14 (`var/live/live-20261014T123033Z/setup/still.png`, `…/stability.png`, `var/live/live-20261014T123533Z/setup/still.png`, `var/live/live-20261014T154211Z/setup/still.png`) liefern ein Raster, und 2j mit dem bekannten Text (`+0.46801 ` bzw. `+0.46797 ` für 154211Z) ist OK; das alte falsche Quad `[[643.6,516.9],[1290.7,530.8],[1287.0,601.7],[645.2,588.3]]` auf 123033Z/still ergibt 2j FEHLER und rms_rows > 0,15; `sc7-assist/stability.png` bleibt abgelehnt; eine gestörte Variante (Rauschen σ 4 oder Helligkeit ×0,85) liefert entweder Ablehnung oder ein 2j-OK-Raster, nie ein falsches; `_lattice_candidates` auf leerem Bild → leeres Ergebnis, kein Absturz.
