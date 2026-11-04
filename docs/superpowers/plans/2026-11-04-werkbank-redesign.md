# Werkbank `/live` neu gestaltet — Umsetzungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ziel:** Die Werkbank-Seite `/live` wird zur Machine-Vision-Oberfläche aus dem
freigegebenen Mock. Sie bekommt einen Einrichtungsfortschritt, eine live
gezeichnete Fokuskurve, Vorschau bis 15 fps mit deckungsgleichem HUD,
Zustandseffekte, Dialoge, einen interaktiven Viewer und eine Einarbeitung.

**Architektur:**
* Der Server erweitert `/live/status` um Fortschritts- und Laufdaten.
* Ein neuer MJPEG-Strom `/live/preview.mjpg` trägt je Bild ein
  `X-Hud`-JSON.
* Der Client besteht aus nativen ES-Modulen unter `static/live/`. Er
  zeichnet Bild, HUD und Effekte auf Canvas.
* Zustand kommt aus dem Statusabruf, Bild und HUD aus dem Strom.
* Der Übungslauf ersetzt beide Quellen clientseitig durch ein Szenario.

**Technik:** Python 3, aiohttp, OpenCV (vorhanden). Der Client ist
Vanilla-JS ohne Build, mit Canvas 2D und SVG. Tests laufen mit
`pytest`, `node --test` und Playwright (vorhanden).

**Spec:** [docs/superpowers/specs/2026-11-04-werkbank-redesign-design.md](../specs/2026-11-04-werkbank-redesign-design.md).
Gestaltungsreferenz ist der [Mock](../specs/2026-11-04-werkbank-redesign-mock/README.md).
Er wird mit `./build.sh` gebaut und unter `mock.html#t=…` angesehen.

## Global Constraints

* Die Spec-Abschnitte „Visuelle Welt“, „Wahrheitsregeln“ und
  „Backend-Vertrag“ gelten für jede Aufgabe, mit wörtlichen Werten.
* Keine neuen Python-Abhängigkeiten. Keine JS-Bibliothek, kein CDN, kein
  Build-Schritt. Schriften liegen lokal (Noto Sans und Noto Sans Mono,
  OFL, woff2).
* Die gesamte UI-Sprache ist Deutsch. Produkttexte aus `live.js`,
  `fields.py` und `tracking_advice.py` werden wörtlich übernommen.
* Die CSP bleibt unverändert: `connect-src 'self'; img-src 'self' blob:`.
* Bestehende Felder in `/live/status` und bestehende POST-Verträge
  bleiben unverändert. Es gibt nur Erweiterungen.
* **Doku-Pflicht (AGENTS.md):** Jeder Commit unter `src/` trägt einen
  `CHANGELOG.md`-Eintrag im selben Commit.
* Gearbeitet wird im Worktree `.claude/worktrees/feat-werkbank-redesign`
  auf dem Branch `feat/werkbank-redesign`.
* Die laufende Bank-Werkbank (`dispread-werkbank-*`, Export) wird nicht
  angefasst. Während einer Aufnahme (`var/RECORDING_IN_PROGRESS`) läuft
  keine volle Testsuite.
* **Arbeitsteilung (Nutzervorgabe 2026-11-04):**
  * **Codex** setzt nur Backend- und Testinfrastruktur-Aufgaben um,
    also die Aufgaben 1–5: Python, HTTP-Routen und Fake-Server.
    * Er fasst **nichts** unter `src/dispread/workbench/static/` an,
      keine CSS-, HTML- oder Client-JS-Datei und keine UI-Texte, auch
      nicht für kleine Korrekturen.
    * Er kann im Sandbox nicht committen und braucht `PYTHONPATH=src`;
      der Controller committet.
  * **Claude-Subagenten** setzen alles um, was Oberfläche, Gestaltung
    oder Bedienung betrifft: die Aufgaben 6–12 und jede spätere
    UI-Nacharbeit, auch Review-Funde an der Oberfläche.
  * Aufgabe 13 macht der Controller mit Leonhard.
* Schnelltests: `./.venv/bin/pytest -q tests/<datei>`,
  `node --test tests/<datei>.test.mjs` und
  `npx playwright test -c playwright.live.config.ts`. Die volle Suite
  läuft im Hintergrund.

## Review Focus

1. **Langsamer oder verdeckter Browser-Tab beim MJPEG-Strom.** Ein
   Schreibvorgang darf höchstens 2 s blockieren, danach endet der Strom.
   Leser-Thread und Kamera spüren nichts. Test in Aufgabe 4.
2. **Zwei Browser gleichzeitig offen.** Jede Bildsequenz wird höchstens
   einmal kodiert, und die Raten-Drossel gilt für beide. Test in
   Aufgabe 4.
3. **Neuladen mitten im Lauf.**
   * Die Zeitleiste füllt sich aus `run.recent`.
   * Der Dialog „Anzeige bewegt“ erscheint für denselben Hinweis (gleiches
     `since_s`) nach „Weiter beobachten“ nicht erneut, auch nicht nach
     dem Neuladen (`sessionStorage`).
   * Test in Aufgabe 10.
4. **Fenstergröße und Zoom.** Das HUD bleibt deckungsgleich, und
   `screenToImage(imageToScreen(p)) == p` gilt bei 0,25× bis 8× und bei
   devicePixelRatio 1 und 2. Test in Aufgabe 7.
5. **Vorschlag ändert sich, während das Bestätigungsformular ausgefüllt
   ist.**
   * Neue `proposal_revision` oder `session_id` setzt Name und Haken
     zurück.
   * Ein Klick zum Bearbeiten eines Rahmenbereichs sperrt Bestätigen und
     weitere Klicks bis zur Antwort.
   * Test in Aufgabe 8.

---

### Aufgabe 1: Fokus-Proben und Belichtungsrunden live im Status (Codex)

**Dateien:**
- Ändern: `src/dispread/focus_sweep.py` (`climb_focus`, `sweep_focus`)
- Ändern: `src/dispread/live/setup.py` (`focus_camera`, `adjust_exposure`)
- Ändern: `src/dispread/live/service.py` (`_run_setup`, `status`)
- Test: `tests/test_focus_sweep.py`, `tests/test_live_setup.py`, `tests/test_live_service.py`

**Schnittstellen:**
- Erzeugt:
  - `climb_focus(..., on_sample: Callable[[int, float], None] | None = None)`
    ruft den Haken genau einmal je **neu** gemessenem Fokuswert auf, in
    Messreihenfolge. Das gilt auch im Rückfall auf `sweep_focus`.
  - `focus_camera(..., on_sample=None)` reicht den Haken durch.
  - `adjust_exposure(..., on_round: Callable[[dict], None] | None = None)`
    erhält je Runde `{"level": float, "controls": dict}`.
- Erzeugt für spätere Aufgaben:
  - `status()["setup"]["focus"] = {"method", "samples", "verify"}`.
    `verify` ist `{"score", "threshold"}` oder `None`, mit
    `threshold = 0.85 × bester Wert`.
  - `status()["setup"]["exposure"] = {"target": 130, "band": [115, 150], "rounds": [...]}`.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `test_climb_focus_reports_each_new_sample_in_order`: Die Aufrufliste
    des Hakens ist gleich `list(measurements)`. Kein Fokuswert kommt
    doppelt vor.
  - `test_climb_focus_reports_fallback_samples`: Bei flacher Kurve kommen
    auch die Sweep-Proben über den Haken.
  - `test_adjust_exposure_reports_each_round`: Mit einer Messattrappe
    Pegel 100 → 124 gibt es zwei Aufrufe, der letzte hat
    `level == 124.0`.
  - `test_status_exposes_focus_samples_while_focusing`: Eine
    Kameraattrappe blockiert nach der 3. Probe. Dann hat
    `status()["setup"]["focus"]["samples"]` die Länge 3 und
    `["verify"] is None`. Nach dem Schritt ist `verify["threshold"]`
    gleich `0.85 * max(score)`.
- [ ] **Schritt 2:** `./.venv/bin/pytest -q tests/test_focus_sweep.py tests/test_live_setup.py tests/test_live_service.py -k "sample or round or focus_samples"` muss mit FAIL enden.
- [ ] **Schritt 3: Haken umsetzen.**
  - Den Aufruf in `sample()` von `climb_focus` legen, nach dem Eintrag in
    `measured`.
  - Der Dienst hält `_setup_focus` und `_setup_exposure` unter
    `self._lock`.
  - Beide werden bei `start_setup` geleert und nach dem Fokus-Schritt mit
    `focus_verify` ergänzt.
- [ ] **Schritt 4:** Dieselben Tests müssen PASS ergeben; danach `ruff check src tests`.
- [ ] **Schritt 5:** Commit „Werkbank: Fokus-Proben und Belichtungsrunden live im Status“ mit CHANGELOG-Eintrag.

### Aufgabe 2: Einrichtungsfortschritt und Prüfungen vor dem Vorschlag (Codex)

**Dateien:**
- Ändern: `src/dispread/live/setup.py` (`assist_measure`)
- Ändern: `src/dispread/live/service.py`
- Test: `tests/test_live_setup.py`, `tests/test_live_service.py`

**Schnittstellen:**
- Verwendet: Aufgabe 1 (gleicher Lock und gleiches Rücksetzen bei `start_setup`).
- Erzeugt:
  - `assist_measure(..., on_phase: Callable[[str, int], None] = noop, on_wait: Callable[[float, float], None] = noop)`.
    Phasen: `mitteln|zelltext|raster|stabilitaet|zweites_standbild|gegenlesen`.
    Das zweite Argument ist der Versuch, ab 1 gezählt.
  - Die Stabilitätswartezeit ruft das injizierte `sleep` in Scheiben von
    höchstens 0,5 s auf und meldet `on_wait(elapsed, total)`.
  - Der Dienst übergibt `report=` und erzeugt daraus
    `status()["setup"]["checks_live"]`.
  - `status()["setup"]["progress"]` hat die Form wie in der Spec, mit
    `attempts_max = 3`. `wait` ist nur in Phase `stabilitaet` gesetzt.
    Bei `SetupError` wird der laufende Schritt `failed`.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `test_assist_measure_waits_in_slices_and_reports_wait`:
    - Das aufgezeichnete `sleep` ergibt in Summe 15,0 s, und jede Scheibe
      ist höchstens 0,5 s lang.
    - Der erste `on_wait` meldet `(0.5, 15.0)`, der letzte `(15.0, 15.0)`.
  - `test_assist_measure_reports_phases_in_order`: Die Phasen kommen in
    der Reihenfolge der Spec, mit Versuch 1.
  - `test_status_progress_marks_steps`:
    - Während `standbilder` gelten `steps[0..2].state == "done"`,
      `steps[3].state == "running"` und `steps[4].state == "pending"`.
    - Bei `setup_failed` ist der Schritt `"failed"`.
  - `test_status_checks_live_before_proposal`: Nach dem ersten
    `report(prechecks)` gilt
    `status()["setup"]["checks_live"]["kontrast"]["status"] == "OK"`,
    und `status()["setup"].get("checks")` ist `None`.
- [ ] **Schritt 2:** `./.venv/bin/pytest -q tests/test_live_setup.py tests/test_live_service.py -k "slices or phases or progress or checks_live"` muss mit FAIL enden.
- [ ] **Schritt 3: Umsetzen.**
  - Der Dienst führt `_step_times: dict[str, list[float | None]]` aus
    `report(step)`.
  - `elapsed_s` laufender Schritte kommt aus `self._monotonic()`.
- [ ] **Schritt 4:** Die Tests müssen PASS ergeben, außerdem `tests/test_live_api.py` als Regressionsprüfung.
- [ ] **Schritt 5:** Commit „Werkbank: Einrichtungsfortschritt mit Phasen, Wartezeit und Prüfungen vor dem Vorschlag“ mit CHANGELOG-Eintrag.

### Aufgabe 3: Laufdaten je Bild (Codex)

**Dateien:**
- Ändern: `src/dispread/live/frame_tracking.py` (`FrameTracker.update`)
- Neu: `src/dispread/live/recent.py`
- Ändern: `src/dispread/live/session.py` (`step`, neue Methode `frame_info`)
- Ändern: `src/dispread/live/service.py` (`status`)
- Test: `tests/test_frame_tracking.py`, neu `tests/test_live_recent.py`, `tests/test_live_session.py`, `tests/test_live_service.py`

**Schnittstellen:**
- Erzeugt:
  - `FrameTracker.last_regions: list[dict] | None`. Je Rahmenbereich ein
    Eintrag `{"c": [x, y], "s": size, "peak": float, "ok": bool}` aus dem
    letzten `update`.
  - `class RecentStrip(window_s: float = 60.0, bucket_ms: int = 250)` mit
    `observe(now_s: float, status: str, value: float | None) -> None` und
    `to_list(now_s: float) -> list[list]`. Die Einträge haben die Form
    `[t_ms_relativ_zum_ältesten, "v|t|u|s", wert|None]`, mit dem
    schlechtesten Status je Eimer (s > u > t > v) und dem letzten
    freigegebenen Wert.
  - `LiveSession.frame_info() -> dict | None` mit den Schlüsseln `rec`,
    `track`, `cells` und `proc` exakt wie `X-Hud` in der Spec. `seq`,
    `cap_ns`, `w`, `h` und `preview` setzt erst Aufgabe 4.
    - Das Ergebnis ist ein unveränderliches Abbild, gebaut am Ende von
      `step()`.
    - `cells[i].uncertain` folgt `margin < 0`, dieselbe Regel wie bei
      `latest_guess`.
    - `track.correcting` ist `last_coarse.used`.
    - `proc.latency_ms` ist `(trace.t_record_built_ns - trace.t_dequeue_ns) / 1e6`.
    - `proc.fps` ist ein gleitendes Mittel über 2 s.
    - `proc.skipped_recent` ist der Anteil übersprungener
      Owner-Sequenzen in den letzten 2 s.
  - `status()["run"]["counts"] = dict(session._by_status)` mit allen vier
    Schlüsseln, fehlende als 0.
  - `status()["run"]["recent"] = session.recent.to_list(now)`.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `test_recent_strip_buckets_worst_status`: `v`, `u`, `v` im selben
    Eimer ergeben `"u"`, und der Wert ist der letzte freigegebene.
  - `test_recent_strip_drops_older_than_window`.
  - `test_frame_tracker_exposes_last_regions`: Ein Rahmenbereich ist
    verdeckt (Hilfen aus `tests/frame_tracking_helpers.py`); er hat
    `ok is False`, die übrigen `ok is True`.
  - `test_frame_info_has_quad_cells_regions_and_proc`:
    - Mit injizierter Pipeline: `len(track["quad"]) == 4`.
    - `cells` hat 16 Einträge, Zelle 8 mit `margin=-0.1` ergibt
      `uncertain is True`.
    - `proc["latency_ms"] >= 0`.
  - `test_frame_info_skipped_recent`: Owner-Sequenzen 1, 2, 5, 6 ergeben
    `skipped_recent == 2/6`.
  - `test_status_run_counts_are_per_frame`: Nach 3 Bildern gilt
    `counts["valid"] == 3`, ohne `_write_session`.
- [ ] **Schritt 2:** `./.venv/bin/pytest -q tests/test_live_recent.py tests/test_frame_tracking.py tests/test_live_session.py tests/test_live_service.py -k "recent or last_regions or frame_info or counts"` muss mit FAIL enden.
- [ ] **Schritt 3: Umsetzen.**
  - Bestehende Zähler und Abläufe in `step()` bleiben unverändert.
  - `frame_info` wird **nach** dem Audit-Schreiben gesetzt, wie
    `latest`.
- [ ] **Schritt 4:** Die Tests müssen PASS ergeben, ebenso `tests/test_live_tracking.py` und `tests/test_live_causes.py`.
- [ ] **Schritt 5:** Commit „Werkbank: Laufdaten je Bild (Quad, Zellen, Rahmenbereiche, Zähler, Verlauf)“ mit CHANGELOG-Eintrag.

### Aufgabe 4: Vorschau-Strom mit HUD-Kopf und adaptiver Rate (Codex)

**Dateien:**
- Neu: `src/dispread/live/preview.py`
- Ändern: `src/dispread/live/service.py` (`preview_jpeg` delegiert, neue Methode `preview_frame`)
- Ändern: `src/dispread/workbench/live_api.py` (Route `GET /live/preview.mjpg`)
- Test: neu `tests/test_live_preview.py`, `tests/test_live_api.py`

**Schnittstellen:**
- Verwendet: `LiveSession.frame_info()` aus Aufgabe 3, `CameraOwner.latest()`.
- Erzeugt:
  - `@dataclass(frozen=True) class PreviewFrame: seq: int; cap_ns: int; jpeg: bytes; hud: dict`
  - `class RateGovernor(clock: Callable[[], float])` mit
    `update(skipped_recent: float | None, encode_ms: float) -> None`,
    `interval_s -> float` (1/15 oder 1/5) und
    `reason -> Literal["messung", "kodierung"] | None`.
    - Drosselt bei `skipped_recent > 0.10` oder bei einem Kodiermittel
      > 25 ms über die letzten 10 Kodierungen.
    - Entdrosselt erst nach 5 s ohne Auslöser.
  - `class PreviewEncoder(latest, hud_of, *, width=960, quality=80, governor)`
    mit `frame() -> PreviewFrame | None`. Je `seq` wird genau einmal
    kodiert, unter einem eigenen Lock. Das Quad wird **nicht** ins Bild
    gezeichnet.
  - `LiveService.preview_frame() -> PreviewFrame | None`. `hud` enthält
    `seq`, `cap_ns`, `w`, `h`, `rec`, `track`, `cells`, `proc` und
    `preview: {"fps", "throttled"}`.
  - `GET /live/preview.mjpg`, Typ `multipart/x-mixed-replace; boundary=frame`.
    - Je Teil die Kopfzeilen `Content-Type: image/jpeg`,
      `Content-Length`, `X-Frame-Sequence`, `X-Capture-Ns` und
      `X-Hud: <json ensure_ascii=True>`.
    - Ein Teil wird nur geschrieben, wenn `seq` neu ist und
      `interval_s` seit dem letzten Teil verstrichen ist.
    - Jeder Schreibvorgang hat `asyncio.wait_for(..., 2)`. Der Strom endet
      nach 600 s, und der Client verbindet neu.
  - `GET /live/preview.jpg` bleibt bestehen und kommt aus dem Encoder.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `test_encoder_encodes_each_sequence_once`: Zwei Aufrufe von `frame()`
    bei gleicher `seq` kodieren einmal (der Kodierer ist ein Spion).
  - `test_rate_governor_throttles_on_skips_and_recovers_after_5s`: Mit
    einer Uhrattrappe ergibt `skipped_recent=0.2` ein Intervall von 0,2
    und `reason == "messung"`. 4,9 s ohne Auslöser ergeben weiter 0,2,
    5,1 s ergeben 1/15.
  - `test_rate_governor_throttles_on_slow_encode`.
  - `test_preview_mjpg_parts_carry_hud_headers`: aiohttp-Testclient. Der
    erste Teil hat `X-Hud` mit `seq`, das zur Kopfzeile
    `X-Frame-Sequence` passt, und der Körper beginnt mit `b"\xff\xd8"`.
  - `test_preview_mjpg_slow_client_ends_stream`: Ein Schreibvorgang, der
    nie fertig wird, beendet den Handler nach ≤ 2,5 s, und die Kamera
    läuft weiter.
  - `test_two_streams_share_encoding`: Zwei gleichzeitige Ströme ergeben
    eine Kodierung je `seq`.
- [ ] **Schritt 2:** `./.venv/bin/pytest -q tests/test_live_preview.py tests/test_live_api.py -k "encoder or governor or mjpg or streams"` muss mit FAIL enden.
- [ ] **Schritt 3: Umsetzen.** Das Muster folgt `workbench/server.py:154-184`, die Kodierung läuft über `asyncio.to_thread`.
- [ ] **Schritt 4:** Die Tests müssen PASS ergeben, ebenso der bestehende Test von `preview.jpg` in `tests/test_live_api.py`. Ein Test, der das eingezeichnete Quad prüft, wird auf „kein Quad“ umgestellt; das wird im Commit-Text begründet.
- [ ] **Schritt 5:** Commit „Werkbank: MJPEG-Vorschau bis 15 fps mit HUD-Kopf und Messvorrang“ mit CHANGELOG-Eintrag.

### Aufgabe 5: Fake-Server und Vertragsprüfung für die neuen Felder (Codex)

**Dateien:**
- Ändern: `tests/live_ui_server.py`
- Neu: `tests/live_status_shape.mjs` (Formprüfung, von Node-Tests und Playwright genutzt)
- Ändern: `tests/test_live_api.py` (Vertragsvergleich Fake ↔ echt, `:182`, `:214`)
- Neu: `tests/fixtures/live/still.jpg` (Kopie aus dem Mock-Ordner)

**Schnittstellen:**
- Verwendet: alle Felder aus den Aufgaben 1–4.
- Erzeugt:
  - Szenen des Fake-Servers über `POST /test/scene {"name": …}`:
    `idle`, `setup_focus`, `setup_standbilder`, `setup_ready_warnung`,
    `running_valid`, `running_transition`, `running_rahmen_verdeckt`,
    `running_stalled`, `running_anzeige_bewegt`, `stopped`.
  - `/live/preview.mjpg` liefert `still.jpg` mit 15 fps und passendem
    `X-Hud` je Szene.
  - `assertStatusShape(status): void` in `tests/live_status_shape.mjs`
    wirft bei fehlenden oder falsch typisierten Feldern.

- [ ] **Schritt 1:** Fehlschlagender Test `test_fake_status_has_all_real_keys_for_every_scene`: Für jede Szene ist die Schlüsselmenge des Fakes eine Obermenge der echten Statusschlüssel.
- [ ] **Schritt 2:** `./.venv/bin/pytest -q tests/test_live_api.py -k fake` muss mit FAIL enden.
- [ ] **Schritt 3:** Szenen und MJPEG-Attrappe umsetzen. Die Werte stammen aus `live-20261030T133635Z` und sind im Spec-Brief genannt.
- [ ] **Schritt 4:** Der Test muss PASS ergeben. Dazu prüft `node --test tests/live_status_shape.test.mjs` alle Szenen, die der Fake nach `tests/fixtures/live/scene-*.json` schreibt (`python tests/live_ui_server.py --dump-scenes`), mit `assertStatusShape`, und der Test ergibt PASS.
- [ ] **Schritt 5:** Commit „Test: Fake-Server der Live-Seite mit Szenen und MJPEG“ (Tests ohne `src/`, also kein CHANGELOG nötig).

### Aufgabe 6: Gerüst, Hülle und Modell (Claude)

**Dateien:**
- Neu: `src/dispread/workbench/static/live/index.html`
- Neu unter `src/dispread/workbench/static/live/`: `app.js`, `model.js`,
  `api.js`, `shell.js`, `live.css`
- Neu: `src/dispread/workbench/static/vendor/fonts/*.woff2` plus Lizenz
- Ändern: `src/dispread/workbench/live_api.py`: `/live` liefert
  `static/live/index.html`. Statische Auslieferung von `/static/live/`
  prüfen, `server.py` nur bei Bedarf ändern.
- Verschieben: `tests/live_client.test.mjs` importiert aus `static/live/model.js`
- Neu: `src/dispread/workbench/PRODUCT.md` (Werkbank-Produktkontext)
- Neu: Surface-Brief per `impeccable surface-brief write src/dispread/workbench/static/live/index.html …`
- Test: `tests/live_client.test.mjs`, `tests/live-ui.spec.ts`

**Schnittstellen:**
- Erzeugt:
  - In `model.js`:
    - `statusView(status)` und `connectionView(status, lastOkMs, nowMs, httpStatus)`,
      **inhaltsgleich** aus `live.js` übernommen.
    - `effectState(status, conn) -> {kind: "offline"|"stalled"|"error"|"correcting"|"transition"|null, corners: number[], regions: number[]}`,
      Vorrang wie in der Spec.
    - `stepRows(status) -> [{key, label, state, elapsed_s, detail, sub: [...]}]`.
  - In `api.js`: `createClient({fetchImpl = fetch, now = () => performance.now()})`
    gibt zurück:
    - `start(onStatus, onConnection)` (500-ms-Abruf, `?full=1` beim
      ersten Mal)
    - `post(path, body) -> Promise<{ok: boolean, error: string | null}>`
      mit CSRF aus dem letzten Status
    - `stop()`
  - In `shell.js`:
    - `mountShell(root) -> {titleActions, leftDock, viewerHost, resultHost, inspector, timeline, statusbar}`
      (DOM-Knoten)
    - `renderTitle(status, view, handlers)` und `renderStatusbar(status, hudProc)`.
  - `live.css` enthält die Tokens aus der Spec wörtlich, Grundgröße
    13 px, Radius ≤ 2 px und keine Schatten außer `.popover`, `.menu`
    und `.modal`.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `effectState: offline wins over everything`.
  - `effectState: stalled beats unreadable`.
  - `effectState: rahmen_verdeckt marks right corners`: `track.regions`
    5–8 mit `ok=false` ergeben `regions == [4, 5, 6, 7]` und
    `corners ⊇ [1, 2]`.
  - `stepRows: running standbilder shows wait 9/15`.
  - Der bestehende Testsatz läuft unverändert gegen `model.js`.
- [ ] **Schritt 2:** `node --test tests/live_client.test.mjs` muss mit FAIL enden.
- [ ] **Schritt 3: `model.js`, `api.js` und `shell.js` umsetzen.**
  - Die Hülle folgt Mock-Kapitel 1 (`#t=1`).
  - Dazu PRODUCT.md der Werkbank: Nutzer, Szene und Wahrheitsregeln
    aus der Spec.
  - Brand Commitment: „Kategorie-Standard Machine-Vision-HMI auf dem
    Niveau von Cognex In-Sight und MVTec MERLIC“.
- [ ] **Schritt 4:**
  - `node --test tests/live_client.test.mjs` muss PASS ergeben.
  - `npx playwright test -c playwright.live.config.ts -g "Hülle"`: Die
    neue Prüfung „Hülle zeigt Titel, Docks und Statusleiste in Szene
    idle“ ergibt PASS.
- [ ] **Schritt 5:** Commit „Werkbank: neues Seitengerüst (Hülle, Modell, Abruf) im Machine-Vision-Stil“ mit CHANGELOG-Eintrag.

### Aufgabe 7: Viewer mit Strom, Zoom, HUD und Markierungs-Info (Claude)

**Dateien:**
- Neu unter `src/dispread/workbench/static/live/`:
  `mjpeg.js`, `viewer/view.js`, `viewer/hud.js`, `viewer/legend.js`
- Test: neu `tests/live_mjpeg.test.mjs`, neu `tests/live_viewer.test.mjs`, `tests/live-ui.spec.ts`

**Schnittstellen:**
- Verwendet: das `X-Hud`-Format (Spec), `mountShell().viewerHost`.
- Erzeugt:
  - `async function* parseParts(chunks: AsyncIterable<Uint8Array>, boundary: string)`
    liefert `{headers: Map<string, string>, body: Uint8Array}`.
  - `openPreview(url, onFrame: ({bitmap, hud}) => void, signal)`
    verbindet nach Abbruch mit Backoff von 0,5 bis 5 s neu.
  - `createViewer(canvas, {onMarker})` gibt zurück: `setFrame(bitmap, hud)`,
    `setStill(url)`, `setSource("live"|"still"|"abtast"|"entz")`,
    `setLayers(Set)`, `zoomBy(f, atScreenXY)`, `fit()`, `oneToOne()`,
    `imageToScreen([x, y])` und `screenToImage([x, y])`.
  - `drawHud(ctx, hud, view, layers)` und
    `hitTest(hud, [x, y]) -> {kind, index, info: string} | null`. Der
    Info-Text kommt nur aus HUD- oder Statuszahlen.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `parseParts splits parts across chunk boundaries`: Zwei Teile, an 7
    Stellen zerschnitten, ergeben 2 Teile mit korrekten
    `X-Frame-Sequence` und Byte-Längen.
  - `screenToImage∘imageToScreen is identity for zoom 0.25…8 and dpr 1,2`,
    auf ±0,01 px genau (Review Focus 4).
  - `hitTest finds region 3 and cell 8`: Die Info zu Zelle 8 enthält
    `"Abstand 0,41"` und nicht `"%"`.
  - Playwright „Viewer zoomt um den Zeiger und Popover erklärt
    Rahmenbereich“ (Szene `running_valid`).
- [ ] **Schritt 2:** `node --test tests/live_mjpeg.test.mjs tests/live_viewer.test.mjs` muss mit FAIL enden.
- [ ] **Schritt 3: Umsetzen.**
  - Die Zeichenweise folgt dem Mock (`mock.src.html`, Funktionen zu HUD
    und Overlay), mit 1-px-Linien bei jedem Zoom.
  - Bildquellen: `/live/setup/{overlay_source|overlay_sampling|overlay_rectified}.png`.
- [ ] **Schritt 4:** Node- und Playwright-Tests müssen PASS ergeben, dazu ein Screenshot bei 1440×900, Szene `running_valid`, Augenschein gegen `mock.html#t=58`.
- [ ] **Schritt 5:** Commit „Werkbank: Viewer mit MJPEG-Strom, Zoom und HUD“ mit CHANGELOG-Eintrag.

### Aufgabe 8: Einrichtungsansicht (Claude)

**Dateien:**
- Neu unter `src/dispread/workbench/static/live/`:
  `setup/steps.js`, `setup/focus-chart.js`, `setup/exposure.js`,
  `setup/checks.js`, `setup/confirm.js`, `viewer/regions-edit.js`
- Test: `tests/live-ui.spec.ts`, `tests/live_client.test.mjs`

**Schnittstellen:**
- Verwendet:
  - `stepRows`, `createClient().post` und `createViewer` (Aufgaben 6–7)
  - die Statusfelder `setup.progress`, `focus`, `exposure`, `checks_live`,
    `checks`, `check_reasons`, `regions`, `centre_results`,
    `proposal_revision` und `gegenlesen.metrics.tolerance`
- Erzeugt:
  - `renderSteps(dock, rows)`
  - `renderFocusChart(svg, focus)`: Punkte in Messreihenfolge, Bestwert
    markiert, Linie bei `verify.threshold`, sonst bei 85 % des Maximums
  - `renderChecks(table, status)`
  - `mountConfirm(host, client)`: setzt sich bei neuer
    `proposal_revision` oder `session_id` zurück
  - `enableRegionEditing(viewer, client, status)`

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - Playwright „Einrichtung zeigt Fokuskurve live“: Szene `setup_focus`
    mit 3 Proben ergibt 3 Punkte. Mit 9 Proben steht die Linie bei 536.
  - Playwright „Stabilität zählt 9/15“ (Szene `setup_standbilder`).
  - Playwright „Bestätigen setzt sich bei neuer Revision zurück“ (Review
    Focus 5):
    - Name tippen.
    - Der Fake erhöht `proposal_revision`.
    - Danach ist das Namensfeld leer, und alle Haken sind aus.
  - Playwright „Rahmenbereich-Klick sperrt bis zur Antwort“: Der Fake
    hält POST 1 s fest. Solange sind Bestätigen und der zweite Klick
    wirkungslos.
  - Playwright „Klick im Zeichenbereich zeigt Grund“: Der Text
    „im Zeichenbereich“ steht am Klickpunkt.
- [ ] **Schritt 2:** `npx playwright test -c playwright.live.config.ts -g "Einrichtung|Stabilität|Bestätigen|Rahmenbereich"` muss mit FAIL enden.
- [ ] **Schritt 3: Umsetzen** nach Mock-Kapiteln 2–7 (`#t=10`, `#t=21`, `#t=30`, `#t=46`, `#t=50`). Die Bestätigungsfelder und Texte kommen wörtlich aus `live.js`.
- [ ] **Schritt 4:** Die Tests müssen PASS ergeben, dazu Screenshots von `setup_focus` und `setup_ready_warnung` bei 1280×800 ohne Überlauf.
- [ ] **Schritt 5:** Commit „Werkbank: Einrichtungsansicht mit Fortschritt, Fokuskurve, Prüfungen und Bereichsbearbeitung“ mit CHANGELOG-Eintrag.

### Aufgabe 9: Laufansicht (Claude)

**Dateien:**
- Neu unter `src/dispread/workbench/static/live/`:
  `run/result.js`, `run/dock.js`, `run/inspector.js`, `run/timeline.js`,
  `run/start-popover.js`
- Test: `tests/live-ui.spec.ts`, neu `tests/live_timeline.test.mjs`

**Schnittstellen:**
- Verwendet:
  - `statusView` (Aufgabe 6) und `X-Hud.rec` (Aufgabe 7)
  - die Statusfelder `run.counts`, `run.recent`, `rejection_causes`,
    `tracking`, `reference`, `diagnostics`, `test_run` und `last_mark`
- Erzeugt:
  - `renderResult(host, view, status, hudRec)`.
    - Statuswort, Codewort und Wert, Veraltet durchgestrichen,
      Unlesbar als „Kein Wert“.
    - Im Testlauf nie ein Wert.
  - `createTimeline(canvas)` gibt zurück: `seed(recent)`,
    `push(tMs, status, value)` und `mark(tMs, label)`.
    - Die Wertspur zeichnet nur `v`-Werte als Stufen.
  - `mountStartPopover(host, client)` mit Referenz, Diagnosebilder,
    Werteplan und Testmodus.
    - Testmodus und Werteplan bestätigen über `openModal` (Aufgabe 10)
      mit den Texten aus `live.js`.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `timeline value trace ignores non-valid and never interpolates`: Die
    Folge `v1`, `t`, `u`, `v2` ergibt genau eine Stufe von `v1` zu `v2`
    und keine Zwischenpunkte.
  - Playwright „Ergebnis zeigt Veraltet durchgestrichen“ (Szene
    `running_stalled`).
  - Playwright „Testlauf zeigt nie einen Wert“ (Szene `running_valid`
    mit `test_run`).
  - Playwright „Neuladen füllt die Zeitleiste aus run.recent“: nach
    `page.reload()` mindestens 100 gefärbte Pixel-Spalten (Review
    Focus 3).
- [ ] **Schritt 2:** `node --test tests/live_timeline.test.mjs` und `npx playwright test -c playwright.live.config.ts -g "Ergebnis|Testlauf|Zeitleiste"` müssen mit FAIL enden.
- [ ] **Schritt 3: Umsetzen** nach Mock-Kapitel 8 (`#t=58`, `#t=63`). Die Fehllesungen erscheinen erst bei `stopped` (Spec OP-1), vorher steht dort „Abgleich nach Laufende“.
- [ ] **Schritt 4:** Die Tests müssen PASS ergeben.
- [ ] **Schritt 5:** Commit „Werkbank: Laufansicht mit Ergebnis, Zeitleiste und Inspektor“ mit CHANGELOG-Eintrag.

### Aufgabe 10: Zustandseffekte, Hinweise und Dialoge (Claude)

**Dateien:**
- Neu unter `src/dispread/workbench/static/live/`:
  `viewer/effects.js`, `ui/toasts.js`, `ui/modal.js`, `run/alerts.js`
- Test: neu `tests/live_effects.test.mjs`, `tests/live-ui.spec.ts`

**Schnittstellen:**
- Verwendet: `effectState` (Aufgabe 6), `createViewer().imageToScreen` (Aufgabe 7).
- Erzeugt:
  - `createEffects(canvas, {reducedMotion})` gibt zurück:
    `set(effectState, geometry)`, `frame(dtMs)` und
    `stats() -> {particles, lastDrawMs}`.
    - Bei einer Client-Bildrate unter 20 fps wird die Partikelzahl
      halbiert.
  - `toast({level, title, text, sticky = false, key})`.
    - Gleicher `key` ersetzt den Hinweis, statt ihn zu stapeln.
    - Höchstens 3 sichtbar.
  - `openModal({title, text, actions: [{label, value, primary, escape}]}) -> Promise<value>`
    mit Fokusfalle.
  - `watchAlerts(status, {client, viewer})`. Sie erzeugt Hinweise und
    den Dialog „Anzeige bewegt“ einmal je `tracking_hint.since_s`.
    - Ein Weglegen wird in `sessionStorage` gemerkt, mit try/catch.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `effects priority follows spec`: Effekte werden gemeinsam gesetzt,
    und nur der höchste Vorrang wird gezeichnet.
  - `effects reducedMotion draws no particles`.
  - `effects halves particles under 20 fps`.
  - Playwright „Rahmen verdeckt: Leuchten, Hinweis, Ecken rechts“ (Szene
    `running_rahmen_verdeckt`). Bildpunkt-Stichprobe am rechten Rand:
    Rotanteil höher als bei `running_valid`.
  - Playwright „Anzeige bewegt: Dialog, Esc = Weiter beobachten, kein
    Wiederauftauchen nach Neuladen“ (Review Focus 3).
  - Playwright „Streamstillstand: Feld mit Alter“.
  - Playwright „Verbindung verloren: Band nach 1,5 s“ (der Fake
    antwortet nicht mehr).
- [ ] **Schritt 2:** `node --test tests/live_effects.test.mjs` und `npx playwright test -c playwright.live.config.ts -g "verdeckt|bewegt|Streamstillstand|Verbindung"` müssen mit FAIL enden.
- [ ] **Schritt 3: Umsetzen** nach Mock-Kapitel 8a–8e (`#t=69`, `#t=72`, `#t=78`, `#t=84`, `#t=92`). Die Partikellogik darf aus `mock.src.html` übernommen werden.
- [ ] **Schritt 4:** Die Tests müssen PASS ergeben. `stats().lastDrawMs` liegt im Playwright-Lauf bei 1440×900 unter 4 ms (Median über 60 Bilder).
- [ ] **Schritt 5:** Commit „Werkbank: Zustandseffekte, Hinweise und Dialoge“ mit CHANGELOG-Eintrag.

### Aufgabe 11: Einarbeitung — Rundgang, Übungslauf, Hilfe (Claude)

**Dateien:**
- Neu unter `src/dispread/workbench/static/live/`:
  `help/tour.js`, `help/dock.js`, `help/glossar-de.json`,
  `practice/scenario.js`, `practice/still.jpg` (aus dem Mock)
- Ändern: `api.js` (eine Quelle für Status, Bild und Aktionen, umschaltbar)
- Test: neu `tests/live_scenario.test.mjs`, `tests/live-ui.spec.ts`

**Schnittstellen:**
- Verwendet: `assertStatusShape` (Aufgabe 5), `toast` und `openModal` (Aufgabe 10).
- Erzeugt:
  - `createScenario({clock})` gibt zurück: `status()`,
    `frame() -> {bitmapSource, hud}`, `act(path, body) -> {ok, error}`
    und `chapter -> string`.
    - Zeitachse und Kapitel wie `CH` in `mock.src.html`.
    - Das Szenario wartet an den Bedienstellen auf `act`: Einrichtung
      starten, Bestätigen (Name Pflicht), Lauf starten, Dialog, Lauf
      stoppen.
  - `api.js`: `useSource("server" | scenario)`. Im Szenario-Modus darf
    `fetch` für POST **nicht** aufgerufen werden.
  - `startTour(stops, {storage})`: Stationen wie in der Spec, Angebot
    beim ersten Besuch.
  - `mountHelp(dock, status)`: Glossar aus JSON plus `tracking_reasons`
    und `LIVE_CAUSE_TEXT`-Erklärungen aus dem Status, mit Suche.

- [ ] **Schritt 1: Fehlschlagende Tests schreiben**
  - `scenario statuses pass assertStatusShape at every chapter`.
  - `scenario waits for confirm with name`: `act('/live/confirm', {confirmed_by: ''})`
    gibt `ok:false` mit dem Servertext für fehlenden Namen zurück.
  - Playwright „Übungslauf sendet keine POSTs“: Der Netzwerkmitschnitt
    enthält während des ganzen Übungslaufs keinen POST an `/live/*`.
    Das Band „Übungslauf – keine Messung“ ist sichtbar.
  - Playwright „Übungslauf gesperrt während eines Laufs“ (Szene
    `running_valid`): Der Menüpunkt ist deaktiviert und hat einen Grund.
  - Playwright „Rundgang: 8 Stationen, Überspringen merkt sich“.
  - Playwright „Hilfe findet ‚Gegenlesen‘“.
- [ ] **Schritt 2:** `node --test tests/live_scenario.test.mjs` und `npx playwright test -c playwright.live.config.ts -g "Übungslauf|Rundgang|Hilfe"` müssen mit FAIL enden.
- [ ] **Schritt 3: Umsetzen.**
  - Die Glossartexte sind kurz und in Bedienersprache.
  - Gründe werden nicht doppelt gepflegt, sondern aus dem Status
    ergänzt.
- [ ] **Schritt 4:** Die Tests müssen PASS ergeben.
- [ ] **Schritt 5:** Commit „Werkbank: Rundgang, Übungslauf ohne Hardware und Hilfe-Dock“ mit CHANGELOG-Eintrag.

### Aufgabe 12: Ablösung der alten Seite und Gesamtprüfung im Browser (Claude)

**Dateien:**
- Entfernen: `src/dispread/workbench/static/live.html`, `live.js`
- Ändern: `tests/live-ui.spec.ts`. Die beiden alten Abläufe werden auf
  die neue Seite umgeschrieben; die Prüfinhalte bleiben gleich
  (Verbindungsverlust, Bereichsbearbeitung).
- Ändern: `tests/test_live_client.py`, falls ein Pfad sich ändert.
- Ändern: `.github/workflows/playwright.yml`. `playwright.live.config.ts`
  läuft in CI mit.

- [ ] **Schritt 1:** Neuer Playwright-Gesamtablauf „Einrichtung → Bestätigen → Lauf → Stopp“: Er läuft gegen den Fake bei 1280×800, 1440×900 und 1920×1080 ohne Konsolenfehler und ohne horizontales Scrollen.
- [ ] **Schritt 2:** `npx playwright test -c playwright.live.config.ts` muss mit FAIL enden, weil noch Altverweise bestehen.
- [ ] **Schritt 3:** Altdateien entfernen und Verweise bereinigen (`grep -rn "live.js\|live.html" src tests`).
- [ ] **Schritt 4:** Alle Live-Tests müssen PASS ergeben: `node --test tests/live_*.test.mjs`, die Playwright-Suite und `./.venv/bin/pytest -q tests/test_live_*.py`. Die volle Suite läuft im Hintergrund. Danach `impeccable detect src/dispread/workbench/static/live` mit null Befunden oder begründeten Ausnahmen, und ein Review gegen den Mock mit dem Agenten `impeccable-finish-reviewer`.
- [ ] **Schritt 5:** Commit „Werkbank: alte Live-Seite abgelöst, Playwright-Ablauf in CI“ mit CHANGELOG-Eintrag.

### Aufgabe 13: Hardware-Abnahme, Messung und Doku (Controller mit Leonhard)

**Dateien:**
- Ändern: `docs/VALIDATION.md`, `docs/status.md`, `TODO.md`, `CHANGELOG.md`
- Ändern: die Bedienen-Seiten im Wiki unter `docs/`, mit neuen Screenshots
- Neu: `src/dispread/workbench/DESIGN.md` über den Agenten `impeccable-documenter`, abgeleitet aus dem gebauten Stand

- [ ] **Schritt 1:** Mit Leonhards Freigabe im Chat wird eine echte Einrichtung und ein Lauf von mindestens 30 min mit Referenz am Aufbau gefahren. Raumlicht nötig, vorher und nachher Bescheid an die Wiki-Sitzung.
- [ ] **Schritt 2: Messen.**
  - Vorschau-fps aus dem `X-Hud`, Median ≥ 12.
  - `skipped_recent` und `frames_skipped` mit und ohne geöffnete Seite,
    verglichen mit `live-20261030T082502Z`.
  - CPU-Last nach `top -b -d 5`.
  - Den alten Controller-Verbrauch messen (OP-2).
  - **Die Abnahme scheitert**, wenn der Leser mit Vorschau mehr als
    2 Prozentpunkte mehr Bilder überspringt als ohne.
- [ ] **Schritt 3:** Die Zahlen kommen in VALIDATION.md. OP-2 wird nur bei Bedarf als eigene Aufgabe nachgezogen.
- [ ] **Schritt 4:** Wiki, `status.md`, TODO und DESIGN.md der Werkbank aktualisieren. `./scripts/docs-site.sh build -s` muss fehlerfrei laufen.
- [ ] **Schritt 5:** Commit „Doku: Werkbank-Neugestaltung abgenommen“. Danach Merge nach `master`, nur mit Leonhards ausdrücklichem OK.
