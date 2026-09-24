# Ernte Phase 1 — automatisch gelabelter GSV-Datensatz, Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aus einer Laborsitzung am GSV-2AS entsteht ohne Handarbeit pro Bild
ein Datensatz mit exakten Labels. Er besteht aus Bildern, Zellenausschnitten
und dem Sollwert aus dem seriellen Telegramm. Auf ihm wird in Phase 2 der
Zellen-Klassifikator (Richtung A) entwickelt und geprüft.

**Architecture:** Einmal je Sitzung bestätigt der Bediener Quad und
Zeichenzellenraster. Das ergibt ein Sitzungsprofil mit Auflösungs-Gate.
Danach läuft alles automatisch: `sync-record.py --norm-schedule` erzeugt
viele verschiedene Anzeigen, `gate-label.py` vergibt Labels nur in stabilen
Plateaus, ein Importer schneidet Zellen aus, prüft die Plausibilität und
legt Proben im `DatasetStore` an (`label_origin = serial_ascii`, Gruppe =
Sitzung).

**Tech Stack:** Python 3 (Projekt-.venv mit System-Paketen), OpenCV, numpy,
picamera2 (nur lazy im Kamerazweig), pytest, ruff.

**Spec:** Ein eigenes Design-Dokument gibt es nicht. Der vom Nutzer am
2026-09-23 bestätigte Ablauf steht unten unter „Entscheidungen". Er ersetzt
eine Spec. Mitzulesen sind
[2026-09-22-auto-labeling-seriell.md](2026-09-22-auto-labeling-seriell.md)
(Vorab-Festlegungen, Tasks E–H) und
[2026-09-22-dotmatrix-backend.md](2026-09-22-dotmatrix-backend.md)
(Zellenmodell, nicht bestandenes Verankerungs-Gate).

## Entscheidungen (2026-09-23, mit dem Nutzer)

1. **Leser-Richtung A:** ein Zellen-Klassifikator je Zeichenzelle
   (HD44780, 16 × 1, 5 × 8 Punkte), klassisch, mit Ablehnung. Das ist
   Phase 2 und nicht Teil dieses Plans.
2. **Das Zellenraster bestätigt der Bediener einmal je Sitzung** auf dem
   entzerrten Bild, genauso wie die manuelle ROI. Die automatische
   Verankerung (Gate nicht bestanden) wird damit umgangen und nicht
   aufgeweicht.
3. **Auflösungs-Gate:** Gemessen wird die Punktspaltenbreite im
   **Quellbild** (nicht im hochgerechneten entzerrten Bild). Liegt sie unter
   der Schwelle, wird die Sitzung abgelehnt. Die Schwelle legt Task 6 fest
   (erledigt: 2,6 px, Entscheidung 7). Das Argument behält trotzdem
   **keinen Vorgabewert**, der Wert wird beim Aufruf ausdrücklich gesetzt.
4. **Mehr Pixel je Punkt über `ScalerCrop`**, nie über einen grösseren
   Sensormodus (OQ-22).
5. **Labels werden voll automatisch importiert.** Das ist eine Abweichung
   von Task F des Auto-Labeling-Plans („mit Menschenbeteiligung"). An die
   Stelle der Durchsicht von Hand treten automatische Plausibilitäts-
   prüfungen und eine optionale Stichprobenliste je Sitzung.
6. **OQ-40 wird übersprungen. Die Gap-Schwellen sind vorläufig:**
   `--min-gap-ms 300`, `--max-gap-ms 800`. Begründung: Unter Kameralast
   lagen alle gemessenen Abstände bei 529–536 ms, auch unter erzwungener
   Schreiblast (VALIDATION.md, 2026-09-23). Die beobachteten Fehlerbilder
   (0 ms, 2384 ms) liegen weit ausserhalb. Jedes Ergebnis, das mit diesen
   Werten entsteht, trägt `gap_thresholds_provisional: true`. Die
   Stundenmessung aus OQ-40 bleibt offen.
7. **`resolution_threshold_px = 2.6`** (native Sensorpixel je Punktspalte),
   vom Nutzer am 2026-09-24 festgelegt, **vor** der ersten Ernte. Grundlage
   ist Task 6: frontal 3,36, „30°" 3,34, „45°" 2,68 native px; entzerrt waren
   die Punkte in allen drei Stellungen noch einzeln erkennbar, bei 2,68 px
   eher am klarsten. 2,6 liegt knapp unter dem kleinsten Messwert, darunter
   gibt es keine Messung. **Grenzen:** Die Schwelle prüft keine Schärfe
   (frontal war mit mehr Pixeln weicher als „45°"), und die Stellungen waren
   flacher als benannt, grob ≈ 20° und ≈ 23° aus dem Seitenverhältnis des
   Glases, Neigung nicht herausgerechnet. Zahlen: VALIDATION.md, 2026-09-24.

## Global Constraints

- Python nur über `./.venv/bin/python`, `./.venv/bin/pytest`, `./.venv/bin/ruff` (AGENTS.md).
- Kommentare und Meldungen deutsch, im Stil der umgebenden Datei.
- `picamera2` wird nur lazy im Kamerazweig importiert. Alle Tests laufen ohne Kamera und ohne seriellen Port.
- Kamera-Ausgabegrösse **≤ 960×720**, nie `--allow-large-sensor-mode` (OQ-22).
- Kein Erfinden von Protokollen. Registerbefehle nur so, wie `scripts/gsv-registers.py` und `sync-record.py` sie schon kodieren.
- Label = **exakte** Zeichenkette nach `telegram_to_display_text()` (OQ-41). Keine Toleranz, kein Runden.
- `M = 695 ms` (`--guard-margin-ms 695`), festgelegt im Auto-Labeling-Plan unter Festlegung 3.
- Unabhängigkeitsgruppe = Aufnahmesitzung, nie ein einzelnes Bild.
- Serielle Labels sind Datensatzmaterial und erreichen `ValueReader`, `ReleaseGate` und `sink/` **nie**.
- Unlesbar oder unplausibel heisst ablehnen und den Grund zählen, nie raten.
- Die Vorzeichenstelle ist ungeprüft (Firmware 1.3.07). Jeder Bericht sagt das.
- Subagenten öffnen weder Kamera noch Port, committen nicht und bearbeiten weder `CHANGELOG.md` noch `docs/*.md` noch `TODO.md`. Den CHANGELOG-Text liefern sie im Bericht, Commit und Doku übernimmt der Orchestrator.

---

## Dateistruktur

| Datei | Verantwortung | Task |
| --- | --- | --- |
| `src/dispread/charcells.py` (neu) | `CharGrid`: Zellenraster im entzerrten Bild, Zellenboxen, Punktspaltenbreite im Quellbild | 1 |
| `src/dispread/session_profile.py` (neu) | `SessionProfile`: Quad, Raster, ScalerCrop, Auflösungsbefund; JSON laden/speichern (Schema 1) | 1 |
| `scripts/sync-record.py` | neu `--scaler-crop`, tatsächlicher ScalerCrop in `session.json` | 2 |
| `scripts/harvest-setup.py` (neu) | Sitzung einrichten: Quad-Vorschlag, Raster, Overlay-PNG, Gate, `profile.json` | 3 |
| `scripts/harvest.py` (neu) | Faktorplan erzeugen, `sync-record` und danach `gate-label` fahren, Ernte-Protokoll | 4 |
| `scripts/import-harvest.py` (neu) | Vorschläge auswählen, Zellen ausschneiden, Plausibilität prüfen, `DatasetStore.save_sample`, Stichprobenliste | 5 |
| `tests/test_charcells.py`, `tests/test_session_profile.py`, `tests/test_harvest_setup.py`, `tests/test_harvest.py`, `tests/test_import_harvest.py` (neu) | Tests | 1–5 |

Die Reihenfolge ist: Task 1 und Task 2 parallel, danach 3 und 4 parallel,
dann 5, dann 6 (Labor) und 7 (Ende-zu-Ende).

---

### Task 1: Zellenraster und Sitzungsprofil

**Files:**
- Create: `src/dispread/charcells.py`, `src/dispread/session_profile.py`
- Test: `tests/test_charcells.py`, `tests/test_session_profile.py`

**Interfaces:**
- Produces:
  - `CharGrid(n_cells: int, left: float, pitch: float, top: float, bottom: float, dot_columns: int = 5, gap_columns: int = 1)`, ein frozen dataclass. Alle Längen sind in Pixeln des **entzerrten** Bildes. Zelle i überdeckt `[left + i*pitch, left + (i+1)*pitch)` horizontal und `[top, bottom)` vertikal.
  - `CharGrid.cell_boxes() -> list[tuple[int, int, int, int]]` liefert `(x, y, w, h)` gerundet.
  - `CharGrid.to_dict() -> dict` / `CharGrid.from_dict(d) -> CharGrid`.
  - `CharGrid.validate(width: int, height: int) -> None` wirft `ValueError`, wenn das Raster über das Bild hinausragt, wenn `pitch <= 0`, wenn `top >= bottom` oder wenn `n_cells < 1`.
  - `source_dot_column_px(grid: CharGrid, quad, target_size: tuple[int, int]) -> float`. Die Zellecken werden über die inverse Homographie (dieselbe Eckordnung wie `dispread.rectify._order_quad`) ins Quellbild abgebildet. Zurück kommt das **Minimum** über alle Zellen von `(Zellbreite im Quellbild entlang der Zeilenmitte) / (dot_columns + gap_columns)`.
  - `SessionProfile(schema_version: int, device_id: str, session_id: str, quad: list[list[float]], target_size: tuple[int, int], grid: CharGrid, scaler_crop: tuple[int, int, int, int] | None, min_source_dot_column_px: float, resolution_threshold_px: float, resolution_ok: bool, confirmed_by: str, confirmed_at_utc: str)`
  - `SessionProfile.save(path: Path) -> None` schreibt atomar (tmp + `os.replace`). `SessionProfile.load(path: Path) -> SessionProfile` wirft `ValueError` bei unbekannter `schema_version` oder fehlendem Feld. `PROFILE_SCHEMA_VERSION = 1`.

- [ ] **Step 1: Failing tests schreiben**

```python
# tests/test_charcells.py
import numpy as np
import pytest
from dispread.charcells import CharGrid, source_dot_column_px

def test_cell_boxes_regular():
    g = CharGrid(n_cells=4, left=10.0, pitch=20.0, top=5.0, bottom=45.0)
    assert g.cell_boxes() == [(10, 5, 20, 40), (30, 5, 20, 40), (50, 5, 20, 40), (70, 5, 20, 40)]

def test_validate_rejects_overflow():
    g = CharGrid(n_cells=16, left=0.0, pitch=30.0, top=0.0, bottom=10.0)
    with pytest.raises(ValueError):
        g.validate(width=400, height=160)  # 16*30 = 480 > 400

def test_roundtrip_dict():
    g = CharGrid(n_cells=16, left=3.5, pitch=24.0, top=10.0, bottom=150.0)
    assert CharGrid.from_dict(g.to_dict()) == g

def test_source_dot_column_px_frontal_identity_scale():
    # Quad = achsparalleles Rechteck 400x160 im Quellbild, Ziel 400x160: Massstab 1
    quad = [[0, 0], [400, 0], [400, 160], [0, 160]]
    g = CharGrid(n_cells=16, left=0.0, pitch=24.0, top=0.0, bottom=160.0)
    assert source_dot_column_px(g, quad, (400, 160)) == pytest.approx(4.0, rel=1e-3)

def test_source_dot_column_px_oblique_takes_minimum():
    # rechte Seite im Quellbild halb so hoch/weit -> ferne Zellen schmaler
    quad = [[0, 0], [300, 40], [300, 120], [0, 160]]
    g = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=0.0, bottom=160.0)
    frontal = source_dot_column_px(g, [[0, 0], [300, 0], [300, 160], [0, 160]], (400, 160))
    assert source_dot_column_px(g, quad, (400, 160)) < frontal
```

```python
# tests/test_session_profile.py
import json
import pytest
from dispread.charcells import CharGrid
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile

def _profile():
    return SessionProfile(
        schema_version=PROFILE_SCHEMA_VERSION, device_id="gsv2as-01", session_id="s1",
        quad=[[1, 2], [3, 4], [5, 6], [7, 8]], target_size=(400, 160),
        grid=CharGrid(n_cells=16, left=2.0, pitch=24.0, top=8.0, bottom=150.0),
        scaler_crop=None, min_source_dot_column_px=2.2, resolution_threshold_px=2.0,
        resolution_ok=True, confirmed_by="bediener", confirmed_at_utc="2026-09-23T12:00:00+00:00")

def test_save_load_roundtrip(tmp_path):
    p = tmp_path / "profile.json"
    _profile().save(p)
    assert SessionProfile.load(p) == _profile()

def test_load_rejects_unknown_schema(tmp_path):
    p = tmp_path / "profile.json"
    _profile().save(p)
    d = json.loads(p.read_text()); d["schema_version"] = 99; p.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        SessionProfile.load(p)
```

- [ ] **Step 2:** `./.venv/bin/pytest -q tests/test_charcells.py tests/test_session_profile.py`, erwartet: FAIL (ImportError).
- [ ] **Step 3:** Implementieren. Die inverse Homographie entsteht mit `cv2.getPerspectiveTransform(dst, src)`, wobei `dst` die Zielrechteckecken in der Reihenfolge von `_order_quad` sind. Die Zellbreite im Quellbild misst die euklidische Distanz der abgebildeten Punkte `(x_links, y_mitte)` und `(x_rechts, y_mitte)`.
- [ ] **Step 4:** Die Tests laufen grün, `ruff check src tests` ist sauber.
- [ ] **Step 5:** Im Bericht stehen der CHANGELOG-Vorschlag und die geänderten Dateien.

---

### Task 2: `ScalerCrop` in `sync-record.py`

**Files:**
- Modify: `scripts/sync-record.py` (Kamerakonfiguration im Kamerazweig, CLI, `session.json`)
- Test: `tests/test_sync_record.py`

**Interfaces:**
- Produces: `--scaler-crop X,Y,W,H` in Sensorkoordinaten (ganzzahlig), Vorgabe: keins. `session.json["scaler_crop_requested"]` ist die Liste oder `null`, `session.json["scaler_crop_actual"]` ist der Wert aus den Metadaten des ersten Bildes (`ScalerCrop`) oder `null`.

- [ ] **Step 1: Failing tests** mit der vorhandenen Fake-Kamera aus `tests/test_sync_record.py`. (a) Mit `--scaler-crop 1000,800,1600,1200` bekommt die Fake-Kamera `set_controls({"ScalerCrop": (1000, 800, 1600, 1200)})` bzw. das Äquivalent in den `controls` der Konfiguration. Welcher Weg in picamera2 der richtige ist, wird in `/usr/lib/python3/dist-packages/picamera2` nachgelesen, der Bericht nennt Datei und Zeile. (b) `session.json` enthält beide Felder. (c) `--scaler-crop 1,2,3` (falsche Anzahl) und negative oder Nullwerte brechen mit einer klaren Meldung ab. (d) Ohne das Argument wird kein `ScalerCrop` gesetzt.
- [ ] **Step 2:** Die Tests schlagen fehl.
- [ ] **Step 3:** Implementieren. Die Ausgabegrösse bleibt die von `--camera-size`, die Sperre über 1 MPixel bleibt unverändert.
- [ ] **Step 4:** Die volle Suite läuft grün, ruff ist sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

Den Hardware-Nachweis übernimmt der Orchestrator in Task 6.

---

### Task 3: `scripts/harvest-setup.py`, Sitzung einrichten

**Files:**
- Create: `scripts/harvest-setup.py`
- Test: `tests/test_harvest_setup.py`

**Interfaces:**
- Consumes: `CharGrid`, `source_dot_column_px`, `SessionProfile` (Task 1); `lcd_quad_in_region(image, hint_box)` aus `src/dispread/workbench/vision.py`; `rectify(image, quad, target_size=...)` aus `src/dispread/rectify.py`.
- Produces: zwei Unterbefehle.
  - `propose --frame BILD --hint-box x,y,w,h --device-id ID --session-id ID --out DIR [--quad ...] [--grid left,pitch,top,bottom] [--target-size 400x160] [--scaler-crop ...]` schreibt `DIR/proposal.json` (Quad, Raster, gemessene `min_source_dot_column_px`), `DIR/overlay_source.png` (Quad auf dem Quellbild) und `DIR/overlay_rectified.png` (16 Zellen auf dem entzerrten Bild, nummeriert).
    - Ohne `--quad` kommt das Quad aus `lcd_quad_in_region`. Findet es nichts, ist das ein Fehler mit Exit 2, geraten wird nicht.
    - Ohne `--grid` gilt der Vorschlag `left=0, pitch=width/16, top=0, bottom=height`, ausdrücklich als Startpunkt markiert (`grid_source: "default_even_split"`).
  - `confirm --proposal DIR/proposal.json --resolution-threshold-px F --confirmed-by NAME --out DIR/profile.json` erzeugt das `SessionProfile`.
    - `--resolution-threshold-px` ist **Pflicht, ohne Vorgabewert** (Entscheidung 3).
    - Liegt `min_source_dot_column_px` unter der Schwelle, wird trotzdem ein Profil geschrieben, aber mit `resolution_ok=False` und Exit 3. `import-harvest.py` lehnt solche Profile ab.
    - `confirm` weigert sich bei `grid_source == "default_even_split"`, es sei denn, `--accept-default-grid` ist gesetzt. Grund: ein ungeprüfter Vorschlag soll nicht stillschweigend bestätigt werden.

- [ ] **Step 1: Failing tests** mit synthetischem Bild. Ein grünes Rechteck mit 16 dunklen 5×8-Punktmustern wird auf grauen Grund gezeichnet und per Homographie leicht geneigt. Geprüft wird:
  - `propose` findet das Quad (Ecken bis auf ±3 px) und schreibt beide PNGs sowie `proposal.json`.
  - `confirm` mit Schwelle unter dem Messwert gibt Exit 0 und `resolution_ok=True`. Mit Schwelle darüber gibt es Exit 3 und `resolution_ok=False`.
  - `confirm` ohne `--resolution-threshold-px` scheitert an argparse.
  - `confirm` auf den Default-Split ohne `--accept-default-grid` gibt Exit 2.
- [ ] **Step 2:** Die Tests schlagen fehl.
- [ ] **Step 3:** Implementieren, das Laden des Skripts in den Tests läuft über `importlib` wie in `tests/test_gate_label.py`.
- [ ] **Step 4:** Die volle Suite läuft grün, ruff ist sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 4: `scripts/harvest.py`, Faktorplan und Ernte-Lauf

**Files:**
- Create: `scripts/harvest.py`
- Test: `tests/test_harvest.py`

**Interfaces:**
- Consumes: `scripts/sync-record.py` (CLI, `--norm-schedule`, `--scaler-crop`) und `scripts/gate-label.py` (CLI), beide als Subprozess. `profile.json` (Task 1) liefert die `scaler_crop`.
- Produces:
  - `plan_factors(n_steps: int, seed: int, lo: float = 0.5, hi: float = 9000.0) -> list[float]` erzeugt log-uniform verteilte Faktoren, gerundet auf 4 signifikante Stellen und auf den Gerätebereich 0,15…1 580 000 geprüft. Zwei aufeinanderfolgende Faktoren liegen mindestens einen Faktor 1,3 auseinander, damit jeder Schritt ein **grosser** Wechsel ist. Die Folge ist deterministisch je `seed`.
  - `build_schedule(factors, hold_s: float) -> str` erzeugt `"f1:hold,f2:hold,..."` im Format von `--norm-schedule`.
  - `run(profile_path, out_dir, n_steps, hold_s, seed, port, guard_margin_ms=695, min_gap_ms=300, max_gap_ms=800)`:
    1. `sync-record.py --source camera --frame-rate 15 --image-format jpg --norm-schedule ... [--scaler-crop aus dem Profil] --duration (n_steps*(hold_s+2.0)+10)` nach `out_dir/recording`.
    2. `gate-label.py --recording ... --guard-margin-ms 695 --min-gap-ms 300 --max-gap-ms 800 --output out_dir/proposal.json`.
    3. `out_dir/harvest.json` enthält die Parameter, den Seed, die Faktoren, `gap_thresholds_provisional: true`, die Exitcodes und die Zusammenfassung aus `proposal.json` (Anzahl gelabelt und abgelehnt je Grund, Zahl verschiedener Zeichenketten).
  - Die Vorgabe `hold_s = 4.0` ist begründet: Ein Plateau von 4 s abzüglich 2 × M = 1,39 s lässt ≈ 2,6 s, also ≈ 39 labelbare Bilder je Schritt. Kürzer als `2*M/1000 + 1.0` wird mit Fehler abgelehnt.
- [ ] **Step 1: Failing tests:**
  - `plan_factors` ist deterministisch, liegt im Bereich und hält den Mindestabstand.
  - `build_schedule` hat das richtige Format.
  - `run` mit gemockten Subprozessen (`subprocess.run` gepatcht) setzt die Argumente exakt, gibt `--scaler-crop` nur weiter, wenn das Profil eine hat, bricht ab, wenn sync-record einen Exitcode ≠ 0 liefert, und schreibt `harvest.json` mit `gap_thresholds_provisional: true`.
  - Ein Profil mit `resolution_ok=False` führt zum Abbruch vor dem Start.
- [ ] **Step 2:** Die Tests schlagen fehl.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** Die volle Suite läuft grün, ruff ist sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag.

---

### Task 5: `scripts/import-harvest.py`, automatischer Import mit Plausibilitätsprüfung

**Files:**
- Create: `scripts/import-harvest.py`
- Test: `tests/test_import_harvest.py`

**Interfaces:**
- Consumes: `proposal.json` (gate-label: je Bild `image_path`, `telegram_text`, `label_text`, `label_normalization`, Plateaugrenzen, `label_origin_detail`; die Feldnamen gegen `scripts/gate-label.py` prüfen); `SessionProfile`; `CharGrid.cell_boxes`; `rectify`; `DatasetStore` (`src/dispread/workbench/datasets.py`: `create_device`, `begin_group`, `save_sample`, `_SERIAL_ASCII_DETAIL_REQUIRED`).
- Produces: `import-harvest.py --harvest DIR --profile profile.json --dataset-root PFAD [--per-plateau 3] [--audit 20] [--dry-run]`. Das Ergebnis ist `DIR/import.json` mit Zählern je Ablehnungsgrund und den angelegten Proben-IDs, dazu `DIR/audit.json` mit der Stichprobenliste.

Regeln, in dieser Reihenfolge:
1. Profil mit `resolution_ok=False` → Abbruch (Exit 3).
2. **Auswahl:** je Plateau höchstens `--per-plateau` Bilder, gleichmässig über das Plateau verteilt. Mehr Bilder desselben Plateaus bringen keine unabhängige Information und blähen die Ähnlichkeitsprüfung des Stores auf.
3. **Bildgüte:** Helligkeitsmittel und Laplace-Varianz des entzerrten Ausschnitts werden gegen den robusten Median der Sitzung geprüft (MAD, Schwelle `k=6`). Ausreisser werden als `bildguete` abgelehnt.
4. **Zellenkonsistenz**, zweistufig über die ganze Sitzung:
   - Jede Zelle wird ausgeschnitten, auf 10×16 skaliert und normiert (Mittel 0, Norm 1).
   - Je Zeichen entsteht der Medoid seiner Zellen.
   - Liegt eine Zelle eines Bildes weiter als `median + 6·MAD` der Distanzen zum Medoid ihres Zeichens, wird das Bild als `zellen_inkonsistent` abgelehnt.
   - Zeichen mit weniger als 5 Zellen in der Sitzung werden nicht geprüft, aber gezählt (`zeichen_zu_selten_fuer_pruefung`). Ungeprüft übernommen werden sie **nicht**, das Bild wird als `nicht_pruefbar` abgelehnt.
5. Die Zeichenzahl von `label_text` (ohne Einheit, siehe gate-label `numeric_text`/`label_text`) muss zur Rasterbelegung passen, sonst `laenge_passt_nicht`. Die Abbildung Zeichen → Zelle wird nachgelesen und im Code dokumentiert: Das GSV-2AS belegt 16 Zellen, rechtsbündig oder linksbündig? Das steht an den Bildern von `var/diagnostics/offset-norm-101440`. Unklarheit wird **im Bericht gemeldet und nicht angenommen**.
6. **Anlegen:** Gerät und Gruppe werden bei Bedarf angelegt, eine Gruppe je `session_id` (`begin_group`, `change_note` = Sitzung und Faktorplan). Dann folgt `save_sample` mit:
   - `label_origin="serial_ascii"`, `label_origin_detail` mit allen Pflichtschlüsseln sowie `session_id`, `telegram_text`, `label_normalization`, `gap_thresholds_provisional`,
   - `expected_text=label_text`,
   - `bbox` = achsparalleles Rechteck um das Quad.
   - Meldet der Store Ähnlichkeit, wird **genau dann** `similarity_confirmed=True` gesetzt, mit der Begründung „automatische serielle Ernte: Plateau <start_ns>–<end_ns>, <k> Bilder je Plateau (Plan 2026-09-23-ernte-phase1, Entscheidung 5)". Andere `DatasetError` werden gezählt und nicht verschluckt.
7. `--audit N` zieht N Proben zufällig (seed = Hash der `session_id`) und schreibt `audit.json` mit Bildpfad, Label und Overlay-Pfad.

- [ ] **Step 1: Failing tests** mit einer synthetischen Sitzung in `tmp_path`: Bilder aus Punktmustern bekannter Zeichen, `proposal.json`, `profile.json` und ein `DatasetStore` in `tmp_path`. Geprüft wird:
  - Auswahl ≤ k je Plateau.
  - Ein absichtlich falsch gelabeltes Bild (Label „7", Zelle zeigt „1") wird als `zellen_inkonsistent` abgelehnt.
  - Ein schwarzes Bild wird als `bildguete` abgelehnt.
  - Ein Profil mit `resolution_ok=False` ergibt Exit 3.
  - Die angelegten Proben tragen `label_origin == "serial_ascii"` und alle Pflichtschlüssel, und alle liegen in **einer** Gruppe.
  - `--dry-run` legt nichts an.
- [ ] **Step 2:** Die Tests schlagen fehl.
- [ ] **Step 3:** Implementieren.
- [ ] **Step 4:** Die volle Suite läuft grün, ruff ist sauber.
- [ ] **Step 5:** Bericht mit CHANGELOG-Vorschlag und der Antwort zu Regel 5 (Zeichen → Zelle).

---

### Task 6 (Labor, Orchestrator mit Nutzer): ScalerCrop und Winkelversuch, Schwelle festlegen

- [x] Den Sensorausschnitt um die Anzeige wählen (`ScalerCrop`, Seitenverhältnis 4:3 wie 960×720). Kurz aufzeichnen und prüfen, dass `scaler_crop_actual` gesetzt ist, kein `stream on failed` auftritt und 15 fps ohne `sensor_sequence`-Lücken laufen.
- [x] Frontal, bei ≈ 30° und bei ≈ 45° (der Nutzer dreht die Kamera): je `harvest-setup.py propose` mit bestätigtem Raster. Gemessen werden `min_source_dot_column_px` und, per Augenschein am Overlay, ob die Punkte getrennt bleiben.
- [x] Die Schwelle `resolution_threshold_px` legt der **kleinste Messwert fest, bei dem die Punkte noch sicher getrennt sind**. Sie wird in diesem Plan unter „Entscheidungen" eingetragen, **vor** der ersten Ernte. Dazu kommen ein VALIDATION-Eintrag und ein lab_journal-Eintrag.

### Task 7 (Orchestrator): Ende-zu-Ende an der echten Anzeige

- [ ] Einrichten: `harvest-setup.py propose` und `confirm`. Das Overlay wird dem Nutzer gezeigt, bestätigt wird erst nach seinem OK.
- [ ] `harvest.py` mit 30 Schritten à 4 s (≈ 3,5 min).
- [ ] `import-harvest.py --dry-run`, dann echt. Die Stichprobe aus `audit.json` wird dem Nutzer gezeigt.
- [ ] Berichtet werden: Bilder gesamt, gelabelt, importiert, abgelehnt je Grund, die Zahl verschiedener Zeichenketten und die Ziffernabdeckung je Stelle (OQ-39). Dazu gehören `gap_thresholds_provisional` und der Hinweis „Vorzeichen ungeprüft".
- [ ] Doku: VALIDATION, lab_journal, CHANGELOG, OQ-39-Nachtrag, Status des Auto-Labeling-Plans (Tasks E/F/G), `status.md`, `TODO.md`. Danach Commit.
