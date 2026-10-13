# Messpfad live — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Werkbank richtet die StreamCam im Browser auf den GSV-Sensor ein, liest danach live mit dem Dot-Matrix-Leser und schreibt jeden Wert als `ValueRecord` in ein JSONL-Audit.

**Architecture:** Neuer Kern `src/dispread/live/` ohne Web-Code: `CameraOwner` (einziger Kamerahalter), `setup.py` (assist-Logik aus `scripts/harvest-setup.py`, verlagert), `LiveSession` (Pipeline mit Nachführung, Dot-Matrix-Leser, Freigabe, JSONL, Zeitbasis), `LiveService` (Zustandsautomat für die Oberfläche). Der bestehende Server bekommt `/live/*`-Routen und eine schlanke Seite; der Picamera2-Worker der alten Werkbank wird durch einen Bilder-Feed von `CameraOwner` ersetzt.

**Tech Stack:** Python 3.13 (System-venv, `--system-site-packages`), OpenCV, numpy, aiohttp, pytest, ruff, node (nur für den Seitentest). Keine neuen Abhängigkeiten.

**Spec:** `docs/superpowers/specs/2026-10-12-messpfad-live-design.md`

## Global Constraints

* Tests laufen ohne Hardware: `./.venv/bin/pytest -q`; Lint: `./.venv/bin/ruff check src tests examples`. Echte Hardware nur in Task 12.
* **Kein Commit an `src/` oder `scripts/` ohne CHANGELOG-Eintrag** (AGENTS.md). Task 1 legt oben in `CHANGELOG.md` den Abschnitt `## 0.1.0.dev0 — 2026-10-12 (Messpfad live)` an; jede weitere Aufgabe ergänzt dort einen Punkt.
* Vorlagen: `var/dotmatrix/templates-stufe2c-2026-09-30.json`, sha256 `6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a` — immer mit Prüfsumme laden.
* Timing-Kalibrierung: `var/calibration/timing-streamcam.json` ist Pflicht beim Start einer Live-Sitzung; aufgezeichnet, **nicht** angewandt.
* Zeitstempel: `capture_timestamp` ist die Aufnahmezeit des gelesenen Bilds (`V4L2_MONOTONIC`); Umrechnung nur über `records.to_boottime_ns` mit `clock_offset_boottime_minus_monotonic_ns` aus `session.json`.
* Freigabe: `default_gate_config("dotmatrix", confirm_frames=2, expected_unit="mV/V")`.
* Zellentext der Einrichtung: `/dev/ttyUSB0`, 38400 Baud, oder Eingabe des Bedieners. `/dev/ttyAMA0` wird nicht angefasst.
* Freigabehinweis, wörtlich: `Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V — andere Lichtquellen und Geräte nicht geprüft.`
* Kein Erfinden von Kamera-Vorgabewerten: vor dem Fokus nur Format (`apply_controls=False`).
* Ablage der Live-Sitzungen: `var/live/<sitzung>/` (`setup/`, `profile.json`, `session.json`, `records.jsonl`).
* Code-Stil wie im Repo: deutsche Kommentare/Meldungen ohne Umlaute im Code (`ae`, `oe`, `ue`), Doku mit Umlauten.

## Review Focus

1. **Einrichtung startet, während ein Lauf läuft** — erwartet: Ablehnung „Lauf zuerst beenden", der Lauf bleibt unberührt. Test in Task 9.
2. **Bediener tippt einen Zellentext mit falscher Länge oder falschen Zeichen** — erwartet: klare Fehlermeldung vor dem Kamerastart, kein Absturz. Test in Task 9.
3. **Profil verweist auf ein fehlendes oder verändertes Referenzbild** (z. B. nach Aufräumen von `var/`) — erwartet: `StartRefused` mit Grund, keine Sitzung. Test in Task 8.
4. **Kamera fällt mitten im Lauf aus** (USB gezogen) — erwartet: Sitzung endet, Endversatz gemessen, Zusammenfassung mit Grund, Seite zeigt ihn. Test in Task 8 (Session) und Task 9 (Service).
5. **Doppelklick auf „Start" bzw. „Stopp" ohne Lauf** — erwartet: zweiter Start lehnt ab, Stopp ohne Lauf meldet klar „kein Lauf". Test in Task 9.

---

## Dateistruktur

| Datei | Verantwortung |
| --- | --- |
| `src/dispread/live/__init__.py` | Paket, Konstanten (Vorlagen, Kalibrierung, Freigabehinweis) |
| `src/dispread/live/benchmark.py` | Laufzeit der Lesekette messen |
| `src/dispread/live/tracking.py` | `TrackedQuadLocator` (QuadTracker als `DisplayLocator`) |
| `src/dispread/live/camera.py` | `CameraOwner` |
| `src/dispread/live/clock.py` | Versatz BOOTTIME−MONOTONIC, `ClockLog` |
| `src/dispread/live/setup.py` | Einrichtung: Fokus, Standbilder, Prüfungen, Vorschlag, Bestätigung |
| `src/dispread/live/session.py` | `LiveSession` |
| `src/dispread/live/service.py` | `LiveService`, `OwnerSetupCamera` |
| `src/dispread/workbench/live_api.py` | `/live/*`-Routen |
| `src/dispread/workbench/static/live.html`, `live.js` | Live-Seite |
| `src/dispread/pipeline.py` | `CharLayout`, Ablehnungsgrund des Locators, `dropped_frames` |
| `src/dispread/frames/uvc_source.py` | öffentliche Regler-Methoden, `apply_controls` |
| `src/dispread/camera_settings.py` | `preview_settings()` |
| `src/dispread/workbench/controller.py` | Picamera2-Worker raus, Feed von `CameraOwner` |
| `src/dispread/workbench/server.py` | `CameraOwner`/`LiveService` verdrahten |
| `scripts/harvest-setup.py` | ruft `dispread.live.setup` auf |
| `scripts/sync-record.py` | importiert `measure_clock_offset_ns` aus `dispread.live.clock` |
| `scripts/live-reader-benchmark.py` | Messskript Task 1 |

---

### Task 1: Testhelfer und Leserlaufzeit

**Files:**
- Modify: `tests/dotmatrix_helpers.py`
- Create: `src/dispread/live/__init__.py`, `src/dispread/live/benchmark.py`, `scripts/live-reader-benchmark.py`, `tests/test_live_benchmark.py`
- Modify: `CHANGELOG.md`, `docs/lab_journal.md`

**Interfaces:**
- Produces: `dispread.live.DEFAULT_TEMPLATES: Path`, `DEFAULT_TEMPLATES_SHA256: str`, `DEFAULT_CALIBRATION: Path`, `RELEASE_NOTICE: str`, `LIVE_DATA_DIR: Path`
- Produces: `time_read_chain(reader, image, quad, layout, *, repeats=50, clock=time.perf_counter_ns) -> dict` mit Schlüsseln `repeats, median_ms, p95_ms, max_ms, last_value, last_reject`
- Produces (Tests): `dotmatrix_helpers.synthetic_reader(seed=7) -> DotMatrixReader`, `embed(text_or_crop) -> np.ndarray` (BGR 800×400), `QUAD: list[list[float]]`, `LAYOUT: CharLayout`

- [ ] **Step 1: Testhelfer ergänzen** — an `tests/dotmatrix_helpers.py` anhängen:

```python
import cv2

from dispread.layout import CharLayout

TRAIN_TEXTS = ["+0.60972 ", "+ 1.2345 ", "+ 67.890 ", "+  988.5 ", "+ 3456.7 ", "+0.11111 "]
LAYOUT = CharLayout(grid=GRID, unit="mV/V")
FRAME_SIZE = (800, 400)
ORIGIN = (200, 120)
#: Bildet den in `embed` eingesetzten 400x160-Ausschnitt 1:1 zurueck.
QUAD = [[200.0, 120.0], [600.0, 120.0], [600.0, 280.0], [200.0, 280.0]]


def synthetic_reader(seed: int = 7):
    """DotMatrixReader mit synthetischen Vorlagen (wie test_dotmatrix_reader)."""
    from dispread.ocr.dotmatrix import DotMatrixReader
    from dispread.ocr.dotmatrix_font import CLASSES
    from dispread.ocr.dotmatrix_sampling import normalized, sample_image
    from dispread.ocr.dotmatrix_templates import build_templates

    rng = np.random.default_rng(seed)
    samples = {c: [] for c in CLASSES}
    for text in TRAIN_TEXTS * 6:
        img = render(text, blur=rng.uniform(0.3, 1.0))
        img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
        n = normalized(sample_image(img, GRID, range(9)))
        for i, ch in enumerate(text):
            samples[ch].append(n[i])
    return DotMatrixReader(build_templates(samples, ("synthetisch",)))


def embed(text_or_crop, frame_size=FRAME_SIZE, origin=ORIGIN):
    """400x160-Anzeige als BGR-Vollbild; `QUAD` bildet sie 1:1 zurueck."""
    crop = render(text_or_crop) if isinstance(text_or_crop, str) else text_or_crop
    frame = np.full((frame_size[1], frame_size[0]), 200, np.uint8)
    x, y = origin
    frame[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
```

- [ ] **Step 2: Fehlschlagenden Test schreiben** — `tests/test_live_benchmark.py`:

```python
from dotmatrix_helpers import LAYOUT, QUAD, embed, synthetic_reader

from dispread.live.benchmark import time_read_chain


def test_time_read_chain_reports_stats_and_reads_value():
    ticks = iter(range(0, 10_000_000_000, 2_000_000))  # jeder Aufruf +2 ms
    stats = time_read_chain(
        synthetic_reader(), embed("+ 1.2345 "), QUAD, LAYOUT, repeats=5, clock=lambda: next(ticks)
    )
    assert stats["repeats"] == 5
    assert stats["median_ms"] == 2.0 and stats["p95_ms"] == 2.0 and stats["max_ms"] == 2.0
    assert stats["last_value"] == 1.2345 and stats["last_reject"] is None
```

- [ ] **Step 3: Test laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_benchmark.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'dispread.live'`

- [ ] **Step 4: Paket und Messfunktion schreiben**

`src/dispread/live/__init__.py`:

```python
"""Live-Messpfad: Kamera, Einrichtung und Dot-Matrix-Lesen in der Werkbank.

Spec: docs/superpowers/specs/2026-10-12-messpfad-live-design.md. Dieses Paket
enthaelt keinen Web-Code; die Werkbank steuert es nur.
"""

from __future__ import annotations

from pathlib import Path

#: Eingefrorene Vorlagen Stufe 2c (Abnahme 3, 215/0/0).
DEFAULT_TEMPLATES = Path("var/dotmatrix/templates-stufe2c-2026-09-30.json")
DEFAULT_TEMPLATES_SHA256 = "6f20dec4f558e98be41203d0ab48eb4788d16e02c1350313a740c25cc03f693a"
#: Pflicht beim Start einer Live-Sitzung; wird aufgezeichnet, nicht angewandt.
DEFAULT_CALIBRATION = Path("var/calibration/timing-streamcam.json")
LIVE_DATA_DIR = Path("var/live")
RELEASE_NOTICE = (
    "Validiert nur: GSV-2AS/Displaytech 161A, Raumlicht, Einheit mV/V — "
    "andere Lichtquellen und Geräte nicht geprüft."
)
```

`src/dispread/live/benchmark.py`:

```python
"""Laufzeit der Lesekette (Entzerren + Dot-Matrix-Leser) messen.

Bestimmt, wie viele Bilder je Sekunde die Live-Sitzung lesen kann. Die
Sitzung liest immer das neueste Bild und ueberspringt aeltere (Spec §2) -
diese Messung sagt, wie viele das sind.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Sequence

import numpy as np

from dispread.layout import CharLayout
from dispread.ocr import ValueReader
from dispread.rectify import rectify


def time_read_chain(
    reader: ValueReader,
    image: np.ndarray,
    quad: Sequence[Sequence[float]],
    layout: CharLayout,
    *,
    repeats: int = 50,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> dict:
    durations: list[float] = []
    result = None
    for _ in range(repeats):
        t0 = clock()
        crop = rectify(image, quad, target_size=(400, 160))
        result = reader.read(crop.image, layout)
        durations.append((clock() - t0) / 1e6)
    durations.sort()
    p95_index = max(0, round(0.95 * len(durations)) - 1)
    return {
        "repeats": repeats,
        "median_ms": statistics.median(durations),
        "p95_ms": durations[p95_index],
        "max_ms": durations[-1],
        "last_value": None if result is None else result.value,
        "last_reject": None if result is None else result.diagnostics.get("reject_reason"),
    }
```

- [ ] **Step 5: Test laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_benchmark.py -v`
Expected: PASS

- [ ] **Step 6: Messskript schreiben** — `scripts/live-reader-benchmark.py`:

```python
#!/usr/bin/env python3
"""Leserlaufzeit auf dem Pi 5 messen (Plan Messpfad live, Task 1).

Liest ein gespeichertes Standbild mit Quad und Raster aus einem
`proposal.json` wiederholt durch Entzerren + Dot-Matrix-Leser und gibt
Median, p95 und Maximum in Millisekunden aus. Keine Kamera noetig.

    ./.venv/bin/python scripts/live-reader-benchmark.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

from dispread.charcells import CharGrid
from dispread.layout import CharLayout
from dispread.live import DEFAULT_TEMPLATES, DEFAULT_TEMPLATES_SHA256
from dispread.live.benchmark import time_read_chain
from dispread.ocr.dotmatrix import DotMatrixReader


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--still", type=Path, default=Path("var/diagnostics/sc7-assist/still.png"))
    parser.add_argument("--proposal", type=Path, default=Path("var/diagnostics/sc7-assist/proposal.json"))
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--templates-sha256", default=DEFAULT_TEMPLATES_SHA256)
    parser.add_argument("--repeats", type=int, default=200)
    args = parser.parse_args(argv)
    image = cv2.imread(str(args.still))
    if image is None:
        print(f"Bild nicht lesbar: {args.still}", file=sys.stderr)
        return 2
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    layout = CharLayout(grid=CharGrid.from_dict(proposal["grid"]), unit="mV/V")
    reader = DotMatrixReader.from_file(args.templates, args.templates_sha256)
    stats = time_read_chain(reader, image, proposal["quad"], layout, repeats=args.repeats)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Auf dem Pi messen**

Run: `./.venv/bin/python scripts/live-reader-benchmark.py`
Expected: JSON mit `last_value` ungleich `null` (sc7 wird gelesen) und Zeiten in ms. Kein laufender Ernteprozess daneben (`ls var/RECORDING_IN_PROGRESS` muss fehlen).

- [ ] **Step 8: Ergebnis festhalten**

In `docs/lab_journal.md` oben einen Eintrag `## 2026-10-12 — Leserlaufzeit Pi 5 (Messpfad live, Task 1)` mit Median, p95, Max, Anzahl Wiederholungen, Bildquelle und daraus abgeleiteter Leserate (`1000 / p95_ms` Bilder/s). In `CHANGELOG.md` oben den Abschnitt anlegen:

```markdown
## 0.1.0.dev0 — 2026-10-12 (Messpfad live)

**Problem:** Die Werkbank konnte mit der StreamCam weder einrichten noch
lesen; der validierte Dot-Matrix-Leser lief nur in Skripten.

**Änderung:** Neuer Kern `dispread.live` (Plan
`docs/superpowers/plans/2026-10-12-messpfad-live.md`):

* Laufzeitmessung der Lesekette (`live/benchmark.py`,
  `scripts/live-reader-benchmark.py`); Ergebnis im Laborjournal.

**Konsequenz:** wird mit den folgenden Aufgaben ergänzt.
```

- [ ] **Step 9: Lint und Commit**

```bash
./.venv/bin/ruff check src tests examples scripts/live-reader-benchmark.py
git add tests/dotmatrix_helpers.py tests/test_live_benchmark.py src/dispread/live scripts/live-reader-benchmark.py CHANGELOG.md docs/lab_journal.md
git commit -m "Messpfad live 1: Testhelfer und Leserlaufzeit"
```

---

### Task 2: Pipeline für `CharLayout` und nachgeführtes Quad

**Files:**
- Modify: `src/dispread/pipeline.py`
- Create: `src/dispread/live/tracking.py`, `tests/test_live_tracking.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `QuadTracker`, `TrackConfig`, `TrackResult` (`dispread.track`); `DisplayCandidate` (`dispread.detect`)
- Produces: `PipelineConfig.layout: DisplayLayout | CharLayout`; `Pipeline.process(frame, *, dropped_frames: int = 0) -> ValueRecord`. Liefert der Locator keinen Kandidaten, ist der Ablehnungsgrund `locator.last_reason` (falls gesetzt), sonst `display_not_located`.
- Produces: `TrackedQuadLocator(reference_image, quad, *, config=TrackConfig())` mit `locator_id == "tracked_confirmed_quad"`, `locate(frame) -> tuple[DisplayCandidate, ...]`, `last_reason: str | None` (`"tracking_lost:<grund>"`), `last_track: TrackResult | None`

- [ ] **Step 1: Fehlschlagende Tests schreiben** — `tests/test_live_tracking.py`:

```python
import numpy as np
from dotmatrix_helpers import LAYOUT, QUAD, embed, synthetic_reader

from dispread.frames import Frame
from dispread.live.tracking import TrackedQuadLocator
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.records import TimeBaseKind, Timestamp, ValueStatus
from dispread.validate import ReleaseGate, default_gate_config


class _Source:
    source_id = "test"


def _frame(seq, image):
    ts = Timestamp(value_ns=seq * 33_333_333, base=TimeBaseKind.V4L2_MONOTONIC)
    return Frame(frame_sequence=seq, image=image, capture_timestamp=ts, source_id="test")


def _pipeline(locator):
    gate = ReleaseGate(default_gate_config("dotmatrix", confirm_frames=1, expected_unit="mV/V"))
    config = PipelineConfig(profile_id="t", layout=LAYOUT, locate_every=0)
    return Pipeline(_Source(), locator, synthetic_reader(), gate, [], config)


def test_tracked_locator_reads_value_through_pipeline():
    reference = embed("+ 1.2345 ")
    record = _pipeline(TrackedQuadLocator(reference, QUAD)).process(_frame(1, embed("+ 1.2345 ")))
    assert record.status is ValueStatus.VALID
    assert record.value == 1.2345 and record.unit == "mV/V"


def test_lost_tracking_is_unreadable_with_reason():
    reference = embed("+ 1.2345 ")
    record = _pipeline(TrackedQuadLocator(reference, QUAD)).process(_frame(1, np.zeros_like(reference)))
    assert record.status is ValueStatus.UNREADABLE and record.value is None
    assert record.reject_reasons[0].startswith("tracking_lost:")


def test_dropped_frames_reach_the_trace():
    pipeline = _pipeline(TrackedQuadLocator(embed("+ 1.2345 "), QUAD))
    record = pipeline.process(_frame(1, embed("+ 1.2345 ")), dropped_frames=3)
    assert record.trace.dropped_frames == 3
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_tracking.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'dispread.live.tracking'`

- [ ] **Step 3: `TrackedQuadLocator` schreiben** — `src/dispread/live/tracking.py`:

```python
"""Bestaetigtes Quad als DisplayLocator, nachgefuehrt mit QuadTracker.

Registriert jedes Bild gegen das Referenzbild der Bestaetigung (nie gegen das
Vorbild, siehe dispread.track). Verletzt die Nachfuehrung ihre Grenzen, gibt
es keinen Kandidaten: der Wert wird UNREADABLE, der letzte laeuft nicht
weiter (Konzept.md §4).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from dispread.detect import DisplayCandidate
from dispread.frames import Frame
from dispread.track import QuadTracker, TrackConfig, TrackResult

LOCATOR_ID = "tracked_confirmed_quad"


class TrackedQuadLocator:
    def __init__(
        self, reference_image: np.ndarray, quad: Sequence[Sequence[float]], *, config: TrackConfig = TrackConfig()
    ) -> None:
        self._tracker = QuadTracker(reference_image, quad, config=config)
        self.last_reason: str | None = None
        self.last_track: TrackResult | None = None

    @property
    def locator_id(self) -> str:
        return LOCATOR_ID

    def locate(self, frame: Frame) -> tuple[DisplayCandidate, ...]:
        result = self._tracker.update(frame.image)
        self.last_track = result
        if result.quad is None:
            self.last_reason = f"tracking_lost:{result.reason}"
            return ()
        self.last_reason = None
        return (DisplayCandidate(quad=result.quad, score=result.score, locator_id=LOCATOR_ID, role_hint="main"),)
```

- [ ] **Step 4: Pipeline anpassen** — in `src/dispread/pipeline.py`:

Import ändern:

```python
from dispread.layout import CharLayout, DisplayLayout
```

`PipelineConfig.layout` ändern:

```python
    layout: DisplayLayout | CharLayout
```

`process` bekommt den Parameter und reicht ihn durch; der Ablehnungsgrund kommt vom Locator:

```python
    def process(self, frame: Frame, *, dropped_frames: int = 0) -> ValueRecord:
        """Einen Frame verarbeiten und den Datensatz erzeugen.

        `dropped_frames`: seit dem vorigen gelesenen Bild uebersprungene Bilder
        (Live-Sitzung liest immer das neueste Bild, Spec 2026-10-12 §2).
        """
```

Im Zweig `if self._candidate is None:` den Grund ersetzen:

```python
            reason = getattr(self.locator, "last_reason", None) or "display_not_located"
            return self._build_record(
                frame,
                value=None,
                unit=None,
                raw_text=None,
                status=ValueStatus.UNREADABLE,
                confidence=0.0,
                reasons=(reason,),
                frames_confirmed=0,
                confirmation_span_ns=0,
                trace=PipelineTrace(t_dequeue_ns=t_dequeue, t_locate_done_ns=t_locate, dropped_frames=dropped_frames),
            )
```

Im Erfolgszweig dem `PipelineTrace(...)` `dropped_frames=dropped_frames` hinzufügen. In `_build_record` die beiden Felder mitkopieren (bisher gingen sie verloren):

```python
        trace = PipelineTrace(
            t_dequeue_ns=trace.t_dequeue_ns,
            t_locate_done_ns=trace.t_locate_done_ns,
            t_rectify_done_ns=trace.t_rectify_done_ns,
            t_read_done_ns=trace.t_read_done_ns,
            t_gate_done_ns=trace.t_gate_done_ns,
            t_record_built_ns=built,
            queue_depth=trace.queue_depth,
            dropped_frames=trace.dropped_frames,
        )
```

- [ ] **Step 5: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_tracking.py tests/test_pipeline*.py -v` (falls keine `test_pipeline*.py` existiert: `./.venv/bin/pytest -q -k pipeline`)
Expected: PASS; bestehende Pipeline-Tests unverändert grün.

- [ ] **Step 6: CHANGELOG ergänzen, Lint, Commit** — Punkt im Abschnitt „Messpfad live": „`Pipeline` nimmt `CharLayout`, übernimmt den Ablehnungsgrund des Locators und führt `dropped_frames` im Trace; `TrackedQuadLocator` führt das bestätigte Quad mit `QuadTracker` nach."

```bash
./.venv/bin/ruff check src tests examples
./.venv/bin/pytest -q
git add src/dispread/pipeline.py src/dispread/live/tracking.py tests/test_live_tracking.py CHANGELOG.md
git commit -m "Messpfad live 2: Pipeline fuer CharLayout, nachgefuehrtes Quad"
```

---

### Task 3: Vorschau ohne Regler und `CameraOwner`

**Files:**
- Modify: `src/dispread/camera_settings.py`, `src/dispread/frames/uvc_source.py`, `tests/test_uvc_source.py`
- Create: `src/dispread/live/camera.py`, `tests/test_live_camera.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces: `camera_settings.preview_settings() -> CameraSettings` (Format ohne Regler, `controls={}`)
- Produces: `UvcSource(..., apply_controls: bool = True)`; `UvcSource.set_controls(controls: list[tuple[str, int]]) -> None`; `UvcSource.get_controls(names: list[str]) -> dict[str, int]`
- Produces: `CameraOwner(source_factory: Callable[[], FrameSource], *, max_fps: float | None = None, gap_factor: float = 1.5)` mit `start()`, `stop(timeout=3.0)`, `restart(source_factory=None)`, `latest() -> tuple[int, Frame] | None`, `wait_newer(after: int, timeout: float) -> tuple[int, Frame] | None`, `status() -> dict` (`running, error, frames, gaps, source`), `source_id: str`, `control_target() -> object | None`. Die Folgenummer im Tupel ist die des Owners (über Neustarts fortlaufend), nicht die der Quelle.

- [ ] **Step 1: Fehlschlagende Tests für `UvcSource` schreiben** — an `tests/test_uvc_source.py` anhängen:

```python
from dispread.camera_settings import preview_settings


def test_vorschau_setzt_keine_regler():
    calls = []
    src = UvcSource(preview_settings(), device="/dev/video8", capture_factory=lambda d: FakeCapture([1.0]),
                    set_controls=lambda dev, c: calls.append(c), get_controls=lambda dev, n: {},
                    sysfs_root=_DEFAULT_SYSFS_ROOT, apply_controls=False)
    src.open()
    assert calls == []
    assert [f.frame_sequence for f in src.frames()] == [1]


def test_regler_lassen_sich_im_betrieb_setzen_und_lesen():
    src, calls = make_source(FakeCapture([1.0]))
    src.open()
    calls.clear()
    src.set_controls([("focus_absolute", 40)])
    assert calls == [("focus_absolute", 40)]
    assert src.get_controls(["gain"]) == {"gain": 11}


def test_regler_vor_dem_oeffnen_abgelehnt():
    src, _ = make_source(FakeCapture([]))
    with pytest.raises(UvcError, match="nicht geoeffnet"):
        src.set_controls([("focus_absolute", 40)])
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_uvc_source.py -v -k "vorschau or regler"`
Expected: FAIL mit `ImportError: cannot import name 'preview_settings'`

- [ ] **Step 3: `preview_settings` und `UvcSource` erweitern**

In `src/dispread/camera_settings.py` nach `CameraSettings`:

```python
def preview_settings() -> CameraSettings:
    """Nur Format (1920x1080 YUYV, 30 fps), keine Reglerwerte.

    Fuer die Vorschau vor dem Fokus-Sweep, wenn es noch kein bestaetigtes
    Profil gibt. Nur zusammen mit `UvcSource(..., apply_controls=False)`
    verwenden: `ordered_controls()` waere hier ein KeyError. So wird kein
    Reglerwert erfunden (Modul-Docstring).
    """
    return CameraSettings(
        model=STREAMCAM_MODEL, usb_id=STREAMCAM_USB_ID, size=(1920, 1080), fourcc="YUYV", fps=30, controls={}
    )
```

In `src/dispread/frames/uvc_source.py`: `__init__` bekommt `apply_controls: bool = True` (als letzter Schlüsselwortparameter) und speichert `self._apply_controls = apply_controls`. In `open()` den Block ab `ordered_controls = self.settings.ordered_controls()` bis zum Ende der Readback-Schleife unter `if self._apply_controls:` einrücken. Danach zwei Methoden ergänzen:

```python
    def set_controls(self, controls: list[tuple[str, int]]) -> None:
        """Regler am geoeffneten Geraet setzen (Fokus-Sweep der Einrichtung)."""
        if self.device is None or self._capture is None:
            raise UvcError("Kamera nicht geoeffnet - Regler koennen nicht gesetzt werden")
        self._set_controls(self.device, list(controls))

    def get_controls(self, names: list[str]) -> dict[str, int]:
        if self.device is None or self._capture is None:
            raise UvcError("Kamera nicht geoeffnet - Regler koennen nicht gelesen werden")
        return dict(self._get_controls(self.device, list(names)))
```

- [ ] **Step 4: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_uvc_source.py -v`
Expected: PASS (alle, auch die bestehenden)

- [ ] **Step 5: Fehlschlagende Tests für `CameraOwner` schreiben** — `tests/test_live_camera.py`:

```python
import threading
import time

import numpy as np
import pytest

from dispread.frames import Frame
from dispread.live.camera import CameraOwner
from dispread.records import TimeBaseKind, Timestamp


def _frame(seq, ts_ns):
    ts = Timestamp(value_ns=ts_ns, base=TimeBaseKind.V4L2_MONOTONIC)
    return Frame(frame_sequence=seq, image=np.zeros((4, 4, 3), np.uint8), capture_timestamp=ts, source_id="fake")


class FakeSource:
    source_id = "fake"

    def __init__(self, stamps_ns, *, endless=False, fail_open=None):
        self.stamps = list(stamps_ns)
        self.endless = endless
        self.fail_open = fail_open
        self.read_error = None
        self.closed = False

    def open(self):
        if self.fail_open:
            raise RuntimeError(self.fail_open)

    def close(self):
        self.closed = True

    def frames(self):
        for i, ts in enumerate(self.stamps, start=1):
            yield _frame(i, ts)
        seq, ts = len(self.stamps), self.stamps[-1] if self.stamps else 0
        while self.endless:
            seq, ts = seq + 1, ts + 33_333_333
            time.sleep(0.005)
            yield _frame(seq, ts)
        self.read_error = "kein Bild innerhalb von READ_FAIL_TIMEOUT_S=2.0s"

    def describe(self):
        return {"fps": 30, "device": "/dev/fake"}

    capabilities = frozenset()


def _wait_stopped(owner, timeout=2.0):
    deadline = time.monotonic() + timeout
    while owner.status()["running"] and time.monotonic() < deadline:
        time.sleep(0.01)


def test_frames_and_gaps_are_counted_and_end_is_reported():
    source = FakeSource([33_333_333, 66_666_667, 166_666_667])
    owner = CameraOwner(lambda: source)
    owner.start()
    _wait_stopped(owner)
    status = owner.status()
    assert status["frames"] == 3 and status["gaps"] == 2
    assert status["running"] is False and "READ_FAIL_TIMEOUT_S" in status["error"]
    assert owner.latest()[0] == 3 and source.closed


def test_wait_newer_returns_newer_frames_and_stop_is_clean():
    owner = CameraOwner(lambda: FakeSource([33_333_333], endless=True))
    owner.start()
    first = owner.wait_newer(0, 1.0)
    second = owner.wait_newer(first[0], 1.0)
    assert second[0] > first[0]
    owner.stop()
    status = owner.status()
    assert status["running"] is False and status["error"] is None


def test_open_error_propagates_and_is_reported():
    owner = CameraOwner(lambda: FakeSource([], fail_open="Kamera nicht zu oeffnen (belegt?)"))
    with pytest.raises(RuntimeError, match="belegt"):
        owner.start()
    assert owner.status()["error"] == "Kamera nicht zu oeffnen (belegt?)"
    assert owner.wait_newer(0, 0.05) is None


def test_restart_swaps_source_and_keeps_owner_sequence_rising():
    owner = CameraOwner(lambda: FakeSource([33_333_333], endless=True))
    owner.start()
    before = owner.wait_newer(0, 1.0)[0]
    owner.restart(lambda: FakeSource([10], endless=True))
    after = owner.wait_newer(before, 1.0)
    assert after[0] > before
    owner.stop()


def test_control_target_only_for_sources_with_controls():
    owner = CameraOwner(lambda: FakeSource([1], endless=True))
    owner.start()
    assert owner.control_target() is None
    owner.stop()
    assert threading.active_count() >= 1
```

- [ ] **Step 6: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_camera.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'dispread.live.camera'`

- [ ] **Step 7: `CameraOwner` schreiben** — `src/dispread/live/camera.py`:

```python
"""Einziger Halter der Kamera im Werkbank-Prozess.

Eine UVC-Kamera laesst nur einen Oeffner zu. Einrichtung, Vorschau, alte
Werkbank und Live-Sitzung bekommen ihre Bilder deshalb alle von hier: ein
Lesethread, das jeweils neueste Bild, Warten auf ein neueres Bild. Es wird
nichts gepuffert - wer langsamer ist, ueberspringt Bilder (Spec 2026-10-12
§2).
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from typing import Any

from dispread.frames import Frame, FrameSource


class CameraOwner:
    def __init__(
        self,
        source_factory: Callable[[], FrameSource],
        *,
        max_fps: float | None = None,
        gap_factor: float = 1.5,
    ) -> None:
        self._factory = source_factory
        self._max_fps = max_fps
        self._gap_factor = gap_factor
        self._cond = threading.Condition()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._source: FrameSource | None = None
        self._describe: dict[str, Any] = {}
        self._latest: tuple[int, Frame] | None = None
        self._sequence = 0
        self._frames = 0
        self._gaps = 0
        self._last_ts: int | None = None
        self._period_ns: float | None = None
        self._running = False
        self._error: str | None = None

    # -- Steuerung ---------------------------------------------------------
    def start(self) -> None:
        with self._cond:
            if self._running:
                return
        source = self._factory()
        try:
            source.open()
        except Exception as exc:
            with self._cond:
                self._error = str(exc)
                self._cond.notify_all()
            raise
        describe = source.describe() if hasattr(source, "describe") else {}
        fps = describe.get("fps")
        with self._cond:
            self._source, self._describe = source, dict(describe)
            self._period_ns = 1e9 / float(fps) if fps else None
            self._last_ts = None
            self._running, self._error = True, None
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, args=(source,), name="camera-owner", daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
        with self._cond:
            self._thread = None
            self._running = False
            self._cond.notify_all()

    def restart(self, source_factory: Callable[[], FrameSource] | None = None) -> None:
        self.stop()
        if source_factory is not None:
            self._factory = source_factory
        self.start()

    # -- Bilder ------------------------------------------------------------
    def latest(self) -> tuple[int, Frame] | None:
        with self._cond:
            return self._latest

    def wait_newer(self, after: int, timeout: float) -> tuple[int, Frame] | None:
        """Neuestes Bild mit Owner-Folgenummer > `after`, sonst None.

        Kehrt sofort mit None zurueck, wenn die Kamera nicht laeuft und kein
        neueres Bild vorliegt."""
        with self._cond:
            self._cond.wait_for(
                lambda: (self._latest is not None and self._latest[0] > after) or not self._running, timeout
            )
            if self._latest is not None and self._latest[0] > after:
                return self._latest
            return None

    # -- Zustand -----------------------------------------------------------
    def status(self) -> dict[str, Any]:
        with self._cond:
            return {
                "running": self._running,
                "error": self._error,
                "frames": self._frames,
                "gaps": self._gaps,
                "source": dict(self._describe),
            }

    @property
    def source_id(self) -> str:
        source = self._source
        return source.source_id if source is not None else "camera-owner"

    def control_target(self) -> Any | None:
        """Die Quelle, wenn sie Regler setzen kann (UvcSource), sonst None."""
        source = self._source
        return source if source is not None and hasattr(source, "set_controls") else None

    # -- intern ------------------------------------------------------------
    def _run(self, source: FrameSource) -> None:
        error: str | None = None
        try:
            for frame in source.frames():
                if self._stop.is_set():
                    break
                self._note(frame)
                if self._max_fps:
                    self._stop.wait(1.0 / self._max_fps)
            else:
                error = getattr(source, "read_error", None) or "Bildquelle beendet"
        except Exception as exc:  # noqa: BLE001 - wird als Kamerastatus gemeldet
            error = str(exc)
        finally:
            with contextlib.suppress(Exception):
                source.close()
            with self._cond:
                self._running = False
                if error and not self._stop.is_set():
                    self._error = error
                self._cond.notify_all()

    def _note(self, frame: Frame) -> None:
        ts = frame.capture_timestamp.value_ns
        with self._cond:
            if self._last_ts is not None and self._period_ns:
                dt = ts - self._last_ts
                if dt > self._gap_factor * self._period_ns:
                    self._gaps += round(dt / self._period_ns) - 1
            self._last_ts = ts
            self._sequence += 1
            self._frames += 1
            self._latest = (self._sequence, frame)
            self._cond.notify_all()
```

- [ ] **Step 8: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_camera.py -v`
Expected: PASS

- [ ] **Step 9: CHANGELOG, Lint, Commit** — Punkt: „`UvcSource` kann ohne Regler öffnen (`apply_controls=False`, `preview_settings()`) und Regler im Betrieb setzen/lesen; `CameraOwner` ist der einzige Kamerahalter, zählt Lücken und meldet Ausfälle."

```bash
./.venv/bin/ruff check src tests examples
./.venv/bin/pytest -q
git add src/dispread/camera_settings.py src/dispread/frames/uvc_source.py src/dispread/live/camera.py tests/test_uvc_source.py tests/test_live_camera.py CHANGELOG.md
git commit -m "Messpfad live 3: Vorschau ohne Regler, CameraOwner"
```

---

### Task 4: Zeitbasis

**Files:**
- Create: `src/dispread/live/clock.py`, `tests/test_live_clock.py`
- Modify: `scripts/sync-record.py`, `CHANGELOG.md`

**Interfaces:**
- Produces: `CLOCK_OFFSET_SAMPLES = 5`; `measure_clock_offset_ns(samples=CLOCK_OFFSET_SAMPLES, clock=time.clock_gettime_ns) -> int` (aus `sync-record.py` verlagert)
- Produces: `ClockLog(measure=measure_clock_offset_ns, monotonic_ns=time.monotonic_ns)` mit `sample() -> int`, `last_sample_monotonic_ns: int | None`, `to_session(*, ended: bool) -> dict` (`{"start", "end", "samples": [[t_monotonic_ns, offset_ns], ...]}`; `end` ist `None`, solange nicht beendet)

- [ ] **Step 1: Fehlschlagende Tests schreiben** — `tests/test_live_clock.py`:

```python
from dispread.live.clock import ClockLog, measure_clock_offset_ns
from dispread.records import TimeBaseKind, Timestamp, to_boottime_ns


def test_measure_uses_median_of_bracketed_samples():
    values = iter([100, 1100, 102, 200, 1205, 202, 300, 1300, 302])  # je (MONO, BOOT, MONO)
    # Einzelversaetze: 1100-101=999, 1205-201=1004, 1300-301=999 -> Median 999
    assert measure_clock_offset_ns(samples=3, clock=lambda _clk: next(values)) == 999


def test_clock_log_session_dict_and_boottime_conversion():
    offsets, ticks = iter([5, 7]), iter([10, 20])
    log = ClockLog(measure=lambda: next(offsets), monotonic_ns=lambda: next(ticks))
    log.sample()
    assert log.to_session(ended=False) == {"start": 5, "end": None, "samples": [[10, 5]]}
    log.sample()
    session = {"clock_offset_boottime_minus_monotonic_ns": log.to_session(ended=True)}
    assert session["clock_offset_boottime_minus_monotonic_ns"]["end"] == 7
    stamp = Timestamp(value_ns=1_000, base=TimeBaseKind.V4L2_MONOTONIC).to_dict()
    assert to_boottime_ns(stamp, session) == 1_005
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_clock.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'dispread.live.clock'`

- [ ] **Step 3: `clock.py` schreiben** — die Funktion `measure_clock_offset_ns` samt Docstring und die Konstante `CLOCK_OFFSET_SAMPLES = 5` (mit ihrem Kommentar) aus `scripts/sync-record.py` hierher verschieben:

```python
"""Zeitbasis der Live-Sitzung (Konzept.md §6, Spec 2026-10-12 §2).

StreamCam-Bilder tragen CLOCK_MONOTONIC (V4L2), serielle Telegramme
CLOCK_BOOTTIME. Verglichen wird nur ueber `records.to_boottime_ns` mit dem
hier gemessenen Versatz; `ClockLog` misst ihn bei Start, periodisch und am
Ende und liefert die Form, die `session.json` braucht.
"""

from __future__ import annotations

import time
from collections.abc import Callable

#: Anzahl Einzelmessungen fuer `measure_clock_offset_ns` (Median).
CLOCK_OFFSET_SAMPLES = 5


def measure_clock_offset_ns(samples: int = CLOCK_OFFSET_SAMPLES, clock=time.clock_gettime_ns) -> int:
    # (Docstring und Rumpf unveraendert aus scripts/sync-record.py uebernehmen)
    offsets: list[int] = []
    for _ in range(samples):
        m1 = clock(time.CLOCK_MONOTONIC)
        b = clock(time.CLOCK_BOOTTIME)
        m2 = clock(time.CLOCK_MONOTONIC)
        offsets.append(b - (m1 + m2) // 2)
    offsets.sort()
    return offsets[len(offsets) // 2]


class ClockLog:
    def __init__(
        self,
        measure: Callable[[], int] = measure_clock_offset_ns,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> None:
        self._measure = measure
        self._monotonic_ns = monotonic_ns
        self.samples: list[tuple[int, int]] = []

    def sample(self) -> int:
        offset = int(self._measure())
        self.samples.append((int(self._monotonic_ns()), offset))
        return offset

    @property
    def last_sample_monotonic_ns(self) -> int | None:
        return self.samples[-1][0] if self.samples else None

    def to_session(self, *, ended: bool) -> dict:
        if not self.samples:
            return {"start": None, "end": None, "samples": []}
        return {
            "start": self.samples[0][1],
            "end": self.samples[-1][1] if ended else None,
            "samples": [[t, offset] for t, offset in self.samples],
        }
```

In `scripts/sync-record.py` die verschobene Definition und Konstante löschen und stattdessen importieren:

```python
from dispread.live.clock import CLOCK_OFFSET_SAMPLES, measure_clock_offset_ns
```

- [ ] **Step 4: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_clock.py tests/test_sync_record.py -v`
Expected: PASS

- [ ] **Step 5: CHANGELOG, Lint, Commit** — Punkt: „`measure_clock_offset_ns` liegt jetzt in `dispread.live.clock` (von `sync-record.py` importiert); `ClockLog` liefert den Versatz für `session.json`."

```bash
./.venv/bin/ruff check src tests examples
git add src/dispread/live/clock.py tests/test_live_clock.py scripts/sync-record.py CHANGELOG.md
git commit -m "Messpfad live 4: Zeitbasis (ClockLog)"
```

---

### Task 5: Einrichtung Teil 1 — Helfer und Fokus verlagern

**Files:**
- Create: `src/dispread/live/setup.py`, `tests/test_live_setup.py`
- Modify: `scripts/harvest-setup.py`, `tests/test_harvest_assist.py`, `tests/test_harvest_setup.py`, `CHANGELOG.md`

**Interfaces:**
- Produces in `dispread.live.setup`: `SetupError(ValueError)`; Konstanten `GSV2AS_EMPTY_CELLS = (8, 13, 14, 15)`, `N_CELLS = 16`, `DEFAULT_TARGET_SIZE = (400, 160)`, `LATTICE_GRID = CharGrid(n_cells=16, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0)`, `WHITE_BALANCE_SETTLE_S = 3.0`, `MIN_STABILITY_S = 30.0`, `SERIAL_PORT = "/dev/ttyUSB0"`, `SERIAL_BAUDRATE = 38400`
- Produces: `SetupCamera` (Protocol: `device: str`, `set_controls(controls)`, `get_controls(names) -> dict[str, int]`, `fresh_still(discard: int = 10) -> np.ndarray`)
- Produces: `CellTextSource = Callable[[Callable[[], np.ndarray]], tuple[np.ndarray, str]]`; `offline_text_source(text: str) -> CellTextSource`; `serial_text_source(port) -> CellTextSource`
- Produces: `measurement_roi(gray, hint_box)`, `serial_cell_text(port) -> str`, `mask_changed_cells(before, after) -> tuple[str, str]`, `capture_with_text(capture, port) -> tuple[np.ndarray, str]`, `heldout_improves(old_check, new_check) -> bool`
- Produces: `focus_camera(cam: SetupCamera, hint_box, *, settle_s: float = 1.0, sleep=None) -> tuple[CameraSettings, list[tuple[int, float]]]`

**Regel für Monkeypatches:** Funktionen in `live/setup.py` schlagen Abhängigkeiten zur Laufzeit im eigenen Modul nach (`fit_lattice`, `check_setup`, …) und lösen `sleep`/`monotonic` erst beim Aufruf auf (`sleep = sleep or time.sleep`), damit Tests, die `time.sleep` patchen, weiter greifen.

- [ ] **Step 1: Fehlschlagenden Test schreiben** — `tests/test_live_setup.py`:

```python
import numpy as np
import pytest

from dispread.live import setup as live_setup


class FakeSetupCamera:
    device = "/dev/fake"

    def __init__(self, image):
        self.image = image
        self.controls = []

    def set_controls(self, controls):
        self.controls.append(list(controls))

    def get_controls(self, names):
        values = {"exposure_time_absolute": 156, "white_balance_temperature": 4600, "gain": 10}
        return {n: values[n] for n in names}

    def fresh_still(self, discard=10):
        return self.image


def test_focus_camera_turns_autofocus_off_first_and_reads_back(monkeypatch):
    monkeypatch.setattr(live_setup, "sweep_focus", lambda measure: (48, [(48, measure(48))]))
    cam = FakeSetupCamera(np.full((1080, 1920, 3), 128, np.uint8))
    settings, sweep = live_setup.focus_camera(cam, None, settle_s=0, sleep=lambda _s: None)
    assert cam.controls[0] == [("focus_automatic_continuous", 0)]
    assert cam.controls[1] == [("focus_absolute", 48)]
    assert cam.controls[2] == [("auto_exposure", 3), ("white_balance_automatic", 1)]
    assert settings.controls == {
        "focus_absolute": 48, "exposure_time_absolute": 156, "white_balance_temperature": 4600, "gain": 10,
    }
    assert settings.device == "/dev/fake" and sweep[0][0] == 48


def test_offline_text_source_returns_capture_and_text():
    image = np.zeros((2, 2, 3), np.uint8)
    assert live_setup.offline_text_source("ABC")(lambda: image) == (image, "ABC")


def test_mask_changed_cells_rejects_length_mismatch():
    with pytest.raises(live_setup.SetupError, match="Laenge"):
        live_setup.mask_changed_cells("ab", "abc")
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_setup.py -v`
Expected: FAIL mit `ImportError: cannot import name 'setup'`

- [ ] **Step 3: `live/setup.py` anlegen** — Kopf, Konstanten, Protokoll und die verlagerten Helfer. Die Rümpfe von `measurement_roi`, `serial_cell_text`, `mask_changed_cells`, `capture_with_text`, `heldout_improves` sind **wörtlich** die von `_measurement_roi`, `_serial_cell_text`, `_mask_changed_cells`, `_capture_with_serial_text`, `_heldout_improves` aus `scripts/harvest-setup.py` (dort löschen); nur die Namen werden öffentlich und `capture_with_text` ruft `serial_cell_text`/`mask_changed_cells`:

```python
"""Einrichtung einer Punktraster-Anzeige (GSV-Sensor, Displaytech 161A).

Aus `scripts/harvest-setup.py` (assist/focus/propose/confirm) verlagert,
damit Kommandozeile und Werkbank dieselbe Implementierung nutzen
(Spec 2026-10-12 §1). Kein Kamerazugriff hier: alles laeuft ueber
`SetupCamera`, das die Kommandozeile mit einer direkten Aufnahme und die
Werkbank mit `CameraOwner` erfuellt.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

import cv2
import numpy as np

from dispread.camera_settings import STREAMCAM_MODEL, STREAMCAM_USB_ID, CameraSettings
from dispread.charcells import CharGrid
from dispread.focus_sweep import sharpness, sweep_focus
from dispread.frames.uvc_source import UvcError
from dispread.gsv2as_cell_text import cell_text_from_telegram

GSV2AS_EMPTY_CELLS = (8, 13, 14, 15)
N_CELLS = 16
DEFAULT_TARGET_SIZE = (400, 160)
LATTICE_GRID = CharGrid(n_cells=N_CELLS, left=0.0, pitch=25.0, top=160.0 / 9.0, bottom=160.0)
WHITE_BALANCE_SETTLE_S = 3.0
MIN_STABILITY_S = 30.0
SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUDRATE = 38400

HintBox = tuple[float, float, float, float]
CellTextSource = Callable[[Callable[[], np.ndarray]], tuple[np.ndarray, str]]


class SetupError(ValueError):
    """Einrichtung abgebrochen; die Meldung ist fuer den Bediener."""


class SetupCamera(Protocol):
    device: str

    def set_controls(self, controls: list[tuple[str, int]]) -> None: ...

    def get_controls(self, names: list[str]) -> dict[str, int]: ...

    def fresh_still(self, discard: int = 10) -> np.ndarray: ...


def offline_text_source(text: str) -> CellTextSource:
    """Zellentext vom Bediener: fuer jedes Standbild derselbe Text."""
    return lambda capture: (capture(), text)


def serial_text_source(port: Any) -> CellTextSource:
    """Zellentext vom GSV-2AS: jedes Standbild mit frischen Telegrammen geklammert."""
    return lambda capture: capture_with_text(capture, port)


# measurement_roi, serial_cell_text, mask_changed_cells, capture_with_text,
# heldout_improves: Rumpf woertlich aus scripts/harvest-setup.py (siehe Schritt 3).
```

Dann `focus_camera` — Rumpf von `run_focus` ohne Datei- und Kamerateil:

```python
def focus_camera(
    cam: SetupCamera,
    hint_box: HintBox | None,
    *,
    settle_s: float = 1.0,
    sleep: Callable[[float], None] | None = None,
) -> tuple[CameraSettings, list[tuple[int, float]]]:
    """Fokus-Sweep, danach Automatiken kurz einschwingen lassen und deren
    Werte als feste Regler uebernehmen (wie bisher `run_focus`)."""
    sleep = sleep or time.sleep

    def measure(focus: int) -> float:
        cam.set_controls([("focus_absolute", focus)])
        sleep(settle_s)
        try:
            frame = cam.fresh_still(discard=3)
        except UvcError as exc:
            raise UvcError(f"kein Bild von {cam.device} (Fokus-Sweep)") from exc
        gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return sharpness(measurement_roi(gray, hint_box))

    cam.set_controls([("focus_automatic_continuous", 0)])
    best_focus, sweep_log = sweep_focus(measure)
    cam.set_controls([("auto_exposure", 3), ("white_balance_automatic", 1)])
    sleep(WHITE_BALANCE_SETTLE_S)
    readback = cam.get_controls(["exposure_time_absolute", "white_balance_temperature", "gain"])
    settings = CameraSettings(
        model=STREAMCAM_MODEL,
        usb_id=STREAMCAM_USB_ID,
        size=(1920, 1080),
        fourcc="YUYV",
        fps=30,
        controls={
            "focus_absolute": best_focus,
            "exposure_time_absolute": readback["exposure_time_absolute"],
            "white_balance_temperature": readback["white_balance_temperature"],
            "gain": readback["gain"],
        },
        device=cam.device,
    )
    return settings, sweep_log
```

- [ ] **Step 4: Skript umstellen** — in `scripts/harvest-setup.py`:

Import ergänzen und die verlagerten Definitionen/Konstanten löschen (`SetupError`, `WHITE_BALANCE_SETTLE_S`, `N_CELLS`, `DEFAULT_TARGET_SIZE`, `GSV2AS_EMPTY_CELLS`, `_measurement_roi`, `_serial_cell_text`, `_mask_changed_cells`, `_capture_with_serial_text`, `_heldout_improves`):

```python
from dispread.live import setup as live_setup
from dispread.live.setup import (
    DEFAULT_TARGET_SIZE,
    GSV2AS_EMPTY_CELLS,
    N_CELLS,
    SetupError,
)
```

Adapter nach `_open_camera_io`:

```python
class _IoSetupCamera:
    """`SetupCamera` ueber die direkt geoeffnete Aufnahme der Kommandozeile."""

    def __init__(self, io: _CameraIO) -> None:
        self._io = io
        self.device = io.device

    def set_controls(self, controls):
        self._io.set_controls(self._io.device, list(controls))

    def get_controls(self, names):
        return self._io.get_controls(self._io.device, list(names))

    def fresh_still(self, discard: int = 10):
        return _capture_fresh_still(self._io, discard=discard)
```

In `run_focus` den Block von `def measure` bis zum Ende des `try/finally` und die `CameraSettings(...)`-Konstruktion ersetzen durch:

```python
    io = _open_camera_io(args.device)
    try:
        settings, sweep_log = live_setup.focus_camera(_IoSetupCamera(io), hint_box, settle_s=args.settle_s)
    finally:
        io.capture.release()
    best_focus = settings.controls["focus_absolute"]
```

(Der Rest von `run_focus` — `camera-settings.json`, Kontrollschritt mit `UvcSource`, Ausgaben — bleibt.) In `run_assist` die Aufrufe `_capture_with_serial_text` und `_mask_changed_cells` vorerst auf `live_setup.capture_with_text` und `live_setup.mask_changed_cells` umstellen (Task 6 ersetzt den Block ganz).

- [ ] **Step 5: Tests der Kommandozeile nachziehen**

In `tests/test_harvest_assist.py` und `tests/test_harvest_setup.py`:
* `monkeypatch.setattr(harvest_setup, "sweep_focus", …)` → `monkeypatch.setattr(live_setup, "sweep_focus", …)` mit `from dispread.live import setup as live_setup` oben in der Datei.
* `harvest_setup._capture_with_serial_text` → `live_setup.capture_with_text`, `harvest_setup._heldout_improves` → `live_setup.heldout_improves`, `harvest_setup._mask_changed_cells` → `live_setup.mask_changed_cells`, `harvest_setup._serial_cell_text` → `live_setup.serial_cell_text`.
* Patches auf `harvest_setup.time` bleiben (das `time`-Modul ist global).

- [ ] **Step 6: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_setup.py tests/test_harvest_assist.py tests/test_harvest_setup.py -v`
Expected: PASS

- [ ] **Step 7: CHANGELOG, Lint, Commit** — Punkt: „Einrichtung Teil 1: Fokus-Sweep und Zellentext-Helfer liegen in `dispread.live.setup`; `harvest-setup.py focus` nutzt sie unverändert."

```bash
./.venv/bin/ruff check src tests examples scripts/harvest-setup.py
./.venv/bin/pytest -q
git add src/dispread/live/setup.py tests/test_live_setup.py scripts/harvest-setup.py tests/test_harvest_assist.py tests/test_harvest_setup.py CHANGELOG.md
git commit -m "Messpfad live 5: Einrichtung Teil 1 (Fokus, Zellentext) verlagert"
```

---

### Task 6: Einrichtung Teil 2 — Standbilder und Prüfungen verlagern

**Files:**
- Modify: `src/dispread/live/setup.py`, `scripts/harvest-setup.py`, `tests/test_live_setup.py`, `tests/test_harvest_assist.py`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `SetupCamera`, `CellTextSource`, `mask_changed_cells`, `heldout_improves` (Task 5)
- Produces: `AssistResult` (dataclass: `first, second: np.ndarray; first_text, second_text: str; hint_box: HintBox; fit: Any; offset_check: Any; final_checks: Any; reader_check: Any | None; stability_elapsed_s: float`)
- Produces: `assist_measure(cam, *, cell_text: CellTextSource, expected_size: tuple[int, int], out_dir: Path, hint_box: HintBox | None = None, stability_s: float = MIN_STABILITY_S, templates: Path | None = None, templates_sha256: str | None = None, report: Callable[[dict], None] = ..., info: Callable[[str], None] = ..., sleep=None, monotonic=None) -> AssistResult` — schreibt `still.png` und `stability.png` nach `out_dir`.

- [ ] **Step 1: Fehlschlagende Tests schreiben** — an `tests/test_live_setup.py` anhängen:

```python
def test_assist_rejects_short_stability(tmp_path):
    cam = FakeSetupCamera(np.zeros((1080, 1920, 3), np.uint8))
    with pytest.raises(live_setup.SetupError, match="30"):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("x"), expected_size=(1920, 1080),
            out_dir=tmp_path, stability_s=5.0,
        )


def test_assist_rejects_wrong_still_size(tmp_path):
    cam = FakeSetupCamera(np.zeros((720, 1280, 3), np.uint8))
    with pytest.raises(live_setup.SetupError, match="Kameraaufloesung"):
        live_setup.assist_measure(
            cam, cell_text=live_setup.offline_text_source("x"), expected_size=(1920, 1080), out_dir=tmp_path,
        )
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_setup.py -v -k assist`
Expected: FAIL mit `AttributeError: module 'dispread.live.setup' has no attribute 'assist_measure'`

- [ ] **Step 3: `assist_measure` schreiben** — Imports in `live/setup.py` ergänzen:

```python
import math
from dataclasses import dataclass
from pathlib import Path

from dispread.dotlattice import evaluate_quad, fit_lattice
from dispread.lattice_offsets import refine_quad
from dispread.setup_checks import check_setup, diagnose_reader, raster_offset_check
from dispread.setup_hint import find_green_hint_box
```

Code (der Ablauf ist der bisherige Mittelteil von `run_assist`, Zeilen „first = …" bis „reader_check = diagnose_reader(…)"):

```python
@dataclass
class AssistResult:
    first: np.ndarray
    second: np.ndarray
    first_text: str
    second_text: str
    hint_box: HintBox
    fit: Any
    offset_check: Any
    final_checks: Any
    reader_check: Any | None
    stability_elapsed_s: float


def assist_measure(
    cam: SetupCamera,
    *,
    cell_text: CellTextSource,
    expected_size: tuple[int, int],
    out_dir: Path,
    hint_box: HintBox | None = None,
    stability_s: float = MIN_STABILITY_S,
    templates: Path | None = None,
    templates_sha256: str | None = None,
    report: Callable[[dict], None] = lambda _checks: None,
    info: Callable[[str], None] = lambda _message: None,
    sleep: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
) -> AssistResult:
    """Zwei Standbilder mit Zellentext, Punktraster, 2j und Setup-Pruefungen.

    Wirft `SetupError` mit Bedienertext, sobald ein Schritt FEHLER meldet."""
    sleep = sleep or time.sleep
    monotonic = monotonic or time.monotonic
    if not math.isfinite(stability_s) or stability_s < MIN_STABILITY_S:
        raise SetupError(f"Stabilitaetsmessung muss mindestens {MIN_STABILITY_S:.0f} Sekunden dauern")
    first, first_text = cell_text(cam.fresh_still)
    first_captured_at = monotonic()
    if first.shape[:2] != (expected_size[1], expected_size[0]):
        raise SetupError("Standbild passt nicht zur Kameraaufloesung")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(out_dir / "still.png"), first):
        raise SetupError("still.png konnte nicht geschrieben werden")
    if hint_box is None:
        hint_box = find_green_hint_box(first)
        if hint_box is None:
            raise SetupError("Kein gruener Bereich mit Punktstruktur gefunden; bitte --hint-box angeben")
    fit = fit_lattice(first, hint_box, empty_cells=GSV2AS_EMPTY_CELLS)
    if isinstance(fit, str):
        raise SetupError(f"Punktraster abgelehnt: {fit}; Hinweisbox pruefen oder --hint-box angeben")
    prechecks = check_setup(first, fit)
    report(prechecks.to_dict())
    precheck_failures = [
        name for name, result in prechecks.checks.items()
        if getattr(result, "status", None) == "FEHLER" and name != "raster"
    ]
    if precheck_failures:
        raise SetupError("Vorpruefung meldet FEHLER; Stabilitaetsmessung nicht gestartet")
    sleep(stability_s)
    second, second_text = cell_text(cam.fresh_still)
    stability_elapsed_s = monotonic() - first_captured_at
    first_text, second_text = mask_changed_cells(first_text, second_text)
    if second.shape != first.shape:
        raise SetupError("Zweites Standbild hat eine andere Bildgroesse")
    if not cv2.imwrite(str(out_dir / "stability.png"), second):
        raise SetupError("stability.png konnte nicht geschrieben werden")
    frame_texts = [(first, first_text), (second, second_text)]
    original_quad = fit.quad
    try:
        # refine_quad liest ROM-Glyphen direkt; maskierte Zellen haben keine
        # bekannte Glyphe und duerfen den Fit nicht beeinflussen.
        refinement_text = first_text.replace("?", " ")
        candidate_quad, _history = refine_quad(
            [(first, refinement_text)], original_quad, LATTICE_GRID, DEFAULT_TARGET_SIZE,
        )
        old_heldout = raster_offset_check([(second, second_text)], original_quad)
        new_heldout = raster_offset_check([(second, second_text)], candidate_quad)
        if heldout_improves(old_heldout, new_heldout):
            revised = evaluate_quad(first, hint_box, candidate_quad, empty_cells=GSV2AS_EMPTY_CELLS)
            if isinstance(revised, str):
                raise SetupError(f"Verbessertes Raster-Quad abgelehnt: {revised}; kein Vorschlag")
            fit = revised
            info("Raster-Quad nachgefuehrt: zurueckgehaltenes Standbild verbessert")
    except SetupError:
        raise
    except (ValueError, cv2.error) as exc:
        info(f"Raster-Quad nicht nachgefuehrt: {exc}")
    offset_check = raster_offset_check(frame_texts, fit.quad)
    report({"overall": offset_check.status, "checks": {"rasterversatz": offset_check.to_dict()}})
    if offset_check.status == "FEHLER":
        raise SetupError("Rasterversatz 2j meldet FEHLER; kein Vorschlag")
    final_checks = check_setup(
        first, fit, stability_image_bgr=second,
        stability_elapsed_s=stability_elapsed_s, offset_check=offset_check,
    )
    if final_checks.overall == "FEHLER":
        report(final_checks.to_dict())
        raise SetupError("Abschliessende Einrichtungspruefung meldet FEHLER; kein Vorschlag")
    reader_check = None
    if templates is not None:
        reader_check = diagnose_reader((first, second), fit.quad, templates, templates_sha256)
    return AssistResult(
        first=first, second=second, first_text=first_text, second_text=second_text, hint_box=hint_box,
        fit=fit, offset_check=offset_check, final_checks=final_checks, reader_check=reader_check,
        stability_elapsed_s=stability_elapsed_s,
    )
```

- [ ] **Step 4: `run_assist` umstellen** — in `scripts/harvest-setup.py` den Block innerhalb von `io = _open_camera_io(args.device); try:` ersetzen durch:

```python
        io = _open_camera_io(args.device)
        try:
            if hasattr(io.capture, "isOpened") and not io.capture.isOpened():
                raise UvcError(f"{io.device}: Kamera nicht zu oeffnen")
            io.set_controls(io.device, settings.ordered_controls())
            text_source = (
                live_setup.offline_text_source(offline_text)
                if serial_port is None
                else live_setup.serial_text_source(serial_port)
            )
            result = live_setup.assist_measure(
                _IoSetupCamera(io),
                cell_text=text_source,
                expected_size=settings.size,
                out_dir=args.out,
                hint_box=hint_box,
                stability_s=args.stability_s,
                templates=args.templates,
                templates_sha256=args.templates_sha256,
                report=_print_setup_checks,
                info=print,
                sleep=time.sleep,
                monotonic=time.monotonic,
            )
        finally:
            io.capture.release()
```

und im anschließenden `propose_args` die Werte aus `result` nehmen: `hint_box=",".join(f"{value:.8f}" for value in result.hint_box)`, `precomputed_fit=result.fit`, `stability_image_bgr=result.second`, `stability_elapsed_s=result.stability_elapsed_s`, `reader_check=result.reader_check`, `offset_check=result.offset_check`, `precomputed_checks=result.final_checks`. Nicht mehr benutzte Importe (`refine_quad`, `find_green_hint_box`, `diagnose_reader`, `evaluate_quad`, falls nur noch in `run_propose` gebraucht: stehen lassen) bereinigt ruff.

- [ ] **Step 5: Tests der Kommandozeile nachziehen** — in Tests, die `run_assist` fahren (`tests/test_harvest_assist.py`), die Patches auf `harvest_setup` für `fit_lattice`, `check_setup`, `raster_offset_check`, `evaluate_quad`, `refine_quad`, `diagnose_reader`, `find_green_hint_box` auf `live_setup` umstellen. Tests, die nur `run_propose` fahren, behalten `fit_lattice`/`evaluate_quad`/`glass_quad_in_region` auf `harvest_setup` (die bleiben in Task 7 im Skript). Patches auf `run_focus`, `_open_camera_io`, `run_propose` und `harvest_setup.time` bleiben.

- [ ] **Step 6: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_setup.py tests/test_harvest_assist.py tests/test_harvest_setup.py tests/test_dotlattice_start_sc7.py tests/test_dotlattice_cursor_shadow.py -v`
Expected: PASS (sc7-Tests überspringen ohne `var/`)

- [ ] **Step 7: CHANGELOG, Lint, Commit** — Punkt: „Einrichtung Teil 2: Standbilder, Punktraster, 2j und Setup-Prüfungen (`assist_measure`) liegen in `dispread.live.setup`; `harvest-setup.py assist` liefert unverändert dieselben Ergebnisse."

```bash
./.venv/bin/ruff check src tests examples scripts/harvest-setup.py
./.venv/bin/pytest -q
git add src/dispread/live/setup.py scripts/harvest-setup.py tests/test_live_setup.py tests/test_harvest_assist.py CHANGELOG.md
git commit -m "Messpfad live 6: Einrichtung Teil 2 (Standbilder, Pruefungen) verlagert"
```

---

### Task 7: Einrichtung Teil 3 — Vorschlag und Bestätigung verlagern

**Files:**
- Modify: `src/dispread/live/setup.py`, `scripts/harvest-setup.py`, `tests/test_live_setup.py`, `tests/test_harvest_setup.py`, `tests/test_harvest_assist.py`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `AssistResult`-Felder (Task 6)
- Produces: `write_overlays(image, quad, grid, out_dir, *, target_size=DEFAULT_TARGET_SIZE, fit=None, overall=None, edge_cells=None) -> list[Path]`
- Produces: `propose_with_fit(image, *, fit, frame_path: Path, camera_settings: CameraSettings, device_id: str, session_id: str, out_dir: Path, cell_text: str | None = None, offset_check=None, final_checks=None, stability_image_bgr=None, stability_elapsed_s=None, reader_check=None) -> dict` — schreibt `proposal.json` und Overlays, gibt den Vorschlag zurück
- Produces: `confirm_proposal(proposal: dict, *, confirmed_by: str, resolution_threshold_px: float, override_reason: str | None = None, accept_default_grid: bool = False, now=None) -> SessionProfile`

- [ ] **Step 1: Fehlschlagende Tests schreiben** — an `tests/test_live_setup.py` anhängen:

```python
from dispread.camera_settings import CameraSettings

_CAMERA = CameraSettings(model="logitech_streamcam", usb_id="046d:0893", size=(1920, 1080), fourcc="YUYV",
                         fps=30, controls={"focus_absolute": 48, "exposure_time_absolute": 156,
                                           "white_balance_temperature": 4600, "gain": 10})


def _proposal(tmp_path, overall="OK", raster="OK"):
    frame = tmp_path / "still.png"
    frame.write_bytes(b"png")
    return {
        "frame": str(frame), "device_id": "gsv-sensor-161a", "session_id": "live-test",
        "quad": [[0, 0], [400, 0], [400, 160], [0, 160]], "target_size": [400, 160],
        "grid": live_setup.LATTICE_GRID.to_dict(), "grid_source": "dot_lattice", "scaler_crop": None,
        "min_source_dot_column_px": 5.0, "native_scale": 1.0, "min_native_dot_column_px": 5.0,
        "camera": _CAMERA.to_dict(),
        "setup_checks": {"overall": overall, "checks": {"rasterversatz": {"status": raster}}},
    }


def test_confirm_builds_confirmed_profile(tmp_path):
    profile = live_setup.confirm_proposal(_proposal(tmp_path), confirmed_by="Leonhard Hentschke",
                                          resolution_threshold_px=2.6)
    assert profile.confirmed_by == "Leonhard Hentschke" and profile.resolution_ok
    assert profile.camera == _CAMERA and profile.reference_frame["path"].endswith("still.png")


def test_confirm_refuses_fehler_without_override(tmp_path):
    with pytest.raises(live_setup.SetupError, match="FEHLER"):
        live_setup.confirm_proposal(_proposal(tmp_path, overall="FEHLER"), confirmed_by="x",
                                    resolution_threshold_px=2.6)


def test_confirm_refuses_empty_name(tmp_path):
    with pytest.raises(live_setup.SetupError, match="Name"):
        live_setup.confirm_proposal(_proposal(tmp_path), confirmed_by="  ", resolution_threshold_px=2.6)
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_setup.py -v -k confirm`
Expected: FAIL mit `AttributeError: … no attribute 'confirm_proposal'`

- [ ] **Step 3: `write_overlays`, `propose_with_fit`, `confirm_proposal` schreiben** — Imports ergänzen:

```python
import hashlib
import json
from datetime import UTC, datetime

from dispread.charcells import source_dot_column_px
from dispread.rectify import rectify
from dispread.session_profile import PROFILE_SCHEMA_VERSION, SessionProfile
from dispread.setup_overlays import draw_sampling_overlay, draw_source_overlay
```

```python
def write_overlays(
    image: np.ndarray,
    quad,
    grid: CharGrid,
    out_dir: Path,
    *,
    target_size: tuple[int, int] = DEFAULT_TARGET_SIZE,
    fit: Any = None,
    overall: str | None = None,
    edge_cells: tuple[int, ...] | None = None,
) -> list[Path]:
    """overlay_source.png, overlay_rectified.png und (mit Fit) overlay_sampling.png."""
    written: list[Path] = []
    if fit is not None:
        overlay_source = draw_source_overlay(image, fit, overall)
    else:
        overlay_source = image.copy()
        points = np.array(quad, dtype=np.int32).reshape(-1, 1, 2)
        cv2.polylines(overlay_source, [points], isClosed=True, color=(0, 0, 255), thickness=2)
    cv2.imwrite(str(out_dir / "overlay_source.png"), overlay_source)
    written.append(out_dir / "overlay_source.png")
    crop = rectify(image, quad, target_size=target_size)
    if fit is not None and edge_cells is not None:
        cv2.imwrite(str(out_dir / "overlay_sampling.png"), draw_sampling_overlay(crop.image, edge_cells=edge_cells))
        written.append(out_dir / "overlay_sampling.png")
    rectified = crop.image
    rectified = cv2.cvtColor(rectified, cv2.COLOR_GRAY2BGR) if rectified.ndim == 2 else rectified.copy()
    for i, (x, y, w, h) in enumerate(grid.cell_boxes()):
        cv2.rectangle(rectified, (x, y), (x + w, y + h), (0, 255, 0), 1)
        cv2.putText(rectified, str(i), (x + 1, max(y + 10, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
    cv2.imwrite(str(out_dir / "overlay_rectified.png"), rectified)
    written.append(out_dir / "overlay_rectified.png")
    return written


def propose_with_fit(
    image: np.ndarray,
    *,
    fit: Any,
    frame_path: Path,
    camera_settings: CameraSettings,
    device_id: str,
    session_id: str,
    out_dir: Path,
    cell_text: str | None = None,
    offset_check: Any = None,
    final_checks: Any = None,
    stability_image_bgr: np.ndarray | None = None,
    stability_elapsed_s: float | None = None,
    reader_check: Any = None,
) -> dict:
    """Vorschlag aus einem Punktraster-Fit (bisher `run_propose` mit Fit)."""
    height, width = image.shape[:2]
    if (width, height) != tuple(camera_settings.size):
        sw, sh = camera_settings.size
        raise SetupError(
            f"Bild ist {width}x{height}, camera-settings.json verlangt aber {sw}x{sh} - "
            "Bild passt nicht zu den Kameraeinstellungen dieser Sitzung."
        )
    if offset_check is None and cell_text is None:
        raise SetupError("Rasterversatz 2j verlangt einen Zellentext")
    quad = fit.quad
    grid = LATTICE_GRID
    min_px = source_dot_column_px(grid, quad, DEFAULT_TARGET_SIZE)
    if offset_check is None:
        offset_check = raster_offset_check([(image, cell_text)], quad)
    if offset_check.status == "FEHLER":
        raise SetupError(f"Rasterversatz 2j: FEHLER — {offset_check.reason or offset_check.metrics}")
    checks = final_checks
    if checks is None:
        checks = check_setup(
            image, fit, stability_image_bgr=stability_image_bgr,
            stability_elapsed_s=stability_elapsed_s, offset_check=offset_check,
        )
    if checks.overall == "FEHLER":
        raise SetupError("Einrichtungspruefung meldet FEHLER; kein Vorschlag")
    checks_dict = checks.to_dict()
    raster_result = checks_dict.get("checks", {}).get("rasterversatz")
    if not isinstance(raster_result, dict) or raster_result.get("status") not in {"OK", "WARNUNG"}:
        raise SetupError("Einrichtungspruefung ohne gueltigen rasterversatz; kein Vorschlag")
    if reader_check is not None:
        checks_dict["checks"]["gegenlesen"] = reader_check.to_dict()
        if reader_check.status == "WARNUNG" and checks_dict["overall"] == "OK":
            checks_dict["overall"] = "WARNUNG"
    proposal = {
        "frame": str(frame_path),
        "device_id": device_id,
        "session_id": session_id,
        "quad": quad,
        "target_size": list(DEFAULT_TARGET_SIZE),
        "grid": grid.to_dict(),
        "grid_source": "dot_lattice",
        "scaler_crop": None,
        "min_source_dot_column_px": min_px,
        "native_scale": 1.0,
        "min_native_dot_column_px": min_px,
        "camera": camera_settings.to_dict(),
        "setup_checks": checks_dict,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "proposal.json").write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
    write_overlays(
        image, quad, grid, out_dir, fit=fit, overall=checks_dict["overall"],
        edge_cells=tuple(checks.checks["kanten"].cells),
    )
    return proposal
```

`confirm_proposal`: Rumpf von `run_confirm` ab `override_reason = args.override_reason` bis zur Konstruktion von `SessionProfile`, mit diesen Änderungen: jedes `print(…, file=sys.stderr); return 2` wird `raise SetupError(<derselbe Text>)`; `args.x` wird zum gleichnamigen Parameter; am Anfang zusätzlich

```python
    if not confirmed_by or not confirmed_by.strip():
        raise SetupError("Name des Bestaetigenden fehlt")
    now = now or (lambda: datetime.now(UTC))
```

und `confirmed_at_utc=now().isoformat()`. Rückgabe ist das `SessionProfile` (Speichern und `resolution_ok`-Warnung bleiben beim Aufrufer).

- [ ] **Step 4: Skript umstellen**

`run_confirm` wird:

```python
def run_confirm(args: argparse.Namespace) -> int:
    proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
    try:
        profile = live_setup.confirm_proposal(
            proposal,
            confirmed_by=args.confirmed_by,
            resolution_threshold_px=args.resolution_threshold_px,
            override_reason=args.override_reason,
            accept_default_grid=args.accept_default_grid,
        )
    except SetupError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    profile.save(args.out)
    # Ausgaben und resolution_ok-Warnung (return 3) wie bisher, Werte aus `profile`.
```

In `run_propose`: hat der Ablauf einen Fit (`args.auto_quad`, oder `--quad`/Detektor **mit** Zellentext → `evaluate_quad`), wird nach dem Fit-Schritt `live_setup.propose_with_fit(image, fit=fit, frame_path=args.frame, camera_settings=camera_settings, device_id=args.device_id, session_id=args.session_id, out_dir=args.out, cell_text=cell_text, offset_check=getattr(args, "offset_check", None), final_checks=getattr(args, "precomputed_checks", None), stability_image_bgr=getattr(args, "stability_image_bgr", None), stability_elapsed_s=getattr(args, "stability_elapsed_s", None), reader_check=getattr(args, "reader_check", None))` aufgerufen (`SetupError` → Meldung, `return 2`) und die bisherigen Ausgaben aus dem zurückgegebenen Vorschlag gedruckt. Der Zweig **ohne** Fit (kein Zellentext, Raster aus `--grid` oder Default-Split) baut wie bisher den Vorschlag ohne `setup_checks` und schreibt die Overlays mit `live_setup.write_overlays(image, quad, grid, out_dir, target_size=target_size)`.

- [ ] **Step 5: Tests der Kommandozeile nachziehen** — in Tests, die `run_propose` oder `run_assist` fahren, Patches auf `harvest_setup` für `check_setup`, `raster_offset_check`, `draw_source_overlay` auf `live_setup` umstellen. `fit_lattice`, `evaluate_quad`, `glass_quad_in_region` bleiben für `run_propose`-Tests auf `harvest_setup`. Fehlermeldungen sind wortgleich, Assertions auf Texte bleiben.

- [ ] **Step 6: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_setup.py tests/test_harvest_setup.py tests/test_harvest_assist.py tests/test_session_profile.py -v`
Expected: PASS

- [ ] **Step 7: CHANGELOG, Lint, Commit** — Punkt: „Einrichtung Teil 3: Vorschlag (`propose_with_fit`, `write_overlays`) und Bestätigung (`confirm_proposal`, verlangt jetzt einen nichtleeren Namen) liegen in `dispread.live.setup`."

```bash
./.venv/bin/ruff check src tests examples scripts/harvest-setup.py
./.venv/bin/pytest -q
git add src/dispread/live/setup.py scripts/harvest-setup.py tests/test_live_setup.py tests/test_harvest_setup.py tests/test_harvest_assist.py CHANGELOG.md
git commit -m "Messpfad live 7: Einrichtung Teil 3 (Vorschlag, Bestaetigung) verlagert"
```

---

### Task 8: `LiveSession`

**Files:**
- Create: `src/dispread/live/session.py`, `tests/test_live_session.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `CameraOwner.wait_newer/status/source_id` (Task 3), `TrackedQuadLocator` (Task 2), `ClockLog` (Task 4), `Pipeline.process(frame, dropped_frames=)` (Task 2), `JsonlSink`, `load_calibration`, `DotMatrixReader.from_file`, `SessionProfile.load`, `CharLayout.from_profile`
- Produces: `LiveConfig` (frozen dataclass: `templates=DEFAULT_TEMPLATES, templates_sha256=DEFAULT_TEMPLATES_SHA256, calibration=DEFAULT_CALIBRATION, unit="mV/V", confirm_frames=2, clock_interval_s=60.0`)
- Produces: `StartRefused(ValueError)`, `CameraLost(RuntimeError)`
- Produces: `LiveSession(owner, profile_path: Path, config: LiveConfig, out_dir: Path, *, reader_factory=DotMatrixReader.from_file, locator_factory=TrackedQuadLocator, clock: ClockLog | None = None, monotonic=time.monotonic, wall=None)` mit `start()`, `step(timeout: float = 0.5) -> ValueRecord | None` (wirft `CameraLost`), `run(stop: threading.Event) -> None`, `stop(reason: str = "bediener") -> dict`, Attributen `latest: ValueRecord | None`, `summary: dict`, `end_reason: str | None`, `session_path: Path`, `records_path: Path`

- [ ] **Step 1: Fehlschlagende Tests schreiben** — `tests/test_live_session.py`:

```python
import hashlib
import json

import cv2
import pytest
from dotmatrix_helpers import GRID, QUAD, embed, synthetic_reader

from dispread.camera_settings import CameraSettings
from dispread.detect.manual_roi import ManualRoiLocator
from dispread.frames import Frame
from dispread.live.clock import ClockLog
from dispread.live.session import CameraLost, LiveConfig, LiveSession, StartRefused
from dispread.records import TimeBaseKind, Timestamp, ValueStatus
from dispread.session_profile import SessionProfile

_CAMERA = CameraSettings(model="logitech_streamcam", usb_id="046d:0893", size=(800, 400), fourcc="YUYV", fps=30,
                         controls={"focus_absolute": 48, "exposure_time_absolute": 156,
                                   "white_balance_temperature": 4600, "gain": 10})


class FakeOwner:
    source_id = "fake"

    def __init__(self, images):
        self.items = [(i, img) for i, img in enumerate(images, start=1)]
        self.running = True

    def wait_newer(self, after, timeout):
        newer = [item for item in self.items if item[0] > after]
        if not newer:
            return None
        seq, image = newer[0]
        ts = Timestamp(value_ns=seq * 33_333_333, base=TimeBaseKind.V4L2_MONOTONIC)
        return seq, Frame(frame_sequence=seq, image=image, capture_timestamp=ts, source_id="fake")

    def status(self):
        return {"running": self.running, "error": None if self.running else "kein Bild", "frames": len(self.items),
                "gaps": 0, "source": {"device": "/dev/fake"}}


def _files(tmp_path, *, reference_ok=True):
    still = tmp_path / "still.png"
    cv2.imwrite(str(still), embed("+ 1.2345 "))
    digest = hashlib.sha256(still.read_bytes()).hexdigest() if reference_ok else "0" * 64
    profile = SessionProfile(
        schema_version=3, device_id="gsv-sensor-161a", session_id="live-test", quad=QUAD, target_size=(400, 160),
        grid=GRID, scaler_crop=None, min_source_dot_column_px=5.0, native_scale=1.0,
        min_native_dot_column_px=5.0, resolution_threshold_px=2.6, resolution_ok=True,
        confirmed_by="tester", confirmed_at_utc="2026-10-12T12:00:00+00:00", camera=_CAMERA,
        reference_frame={"path": str(still), "sha256": digest},
    )
    profile.save(tmp_path / "profile.json")
    calibration = tmp_path / "timing.json"
    calibration.write_text(json.dumps({
        "schema_version": 1, "camera_usb_id": "046d:0893", "guard_margin_ms": 325.9,
        "display_offset_ms": 89.6, "measured_at_utc": "2026-09-29T00:00:00+00:00", "sources": [],
    }))
    templates = tmp_path / "templates.json"
    templates.write_text("{}")
    return tmp_path / "profile.json", LiveConfig(templates=templates, templates_sha256="x", calibration=calibration)


def _session(tmp_path, images, **kw):
    profile_path, config = _files(tmp_path, **kw)
    offsets = iter(range(1000, 2000))
    return LiveSession(
        FakeOwner(images), profile_path, config, tmp_path / "run",
        reader_factory=lambda _p, _s: synthetic_reader(),
        locator_factory=lambda _ref, quad: ManualRoiLocator(tuple(tuple(p) for p in quad)),
        clock=ClockLog(measure=lambda: next(offsets), monotonic_ns=lambda: 0),
    )


def test_new_value_is_transition_then_valid_and_audited(tmp_path):
    session = _session(tmp_path, [embed("+ 1.2345 "), embed("+ 1.2345 ")])
    session.start()
    first, second = session.step(), session.step()
    assert first.status is ValueStatus.TRANSITION and first.value is None
    assert second.status is ValueStatus.VALID and second.value == 1.2345
    assert second.capture_timestamp.base is TimeBaseKind.V4L2_MONOTONIC
    summary = session.stop()
    lines = session.records_path.read_text().splitlines()
    assert len(lines) == 2 and summary["by_status"] == {"transition": 1, "valid": 1}
    data = json.loads(session.session_path.read_text())
    assert data["clock_offset_boottime_minus_monotonic_ns"]["end"] is not None
    assert data["timing_calibration"]["applied"] is False
    assert data["release_notice"].startswith("Validiert nur:")


def test_unreadable_frame_is_rejected_not_guessed(tmp_path):
    blank = embed("+ 1.2345 ") * 0 + 200
    session = _session(tmp_path, [blank])
    session.start()
    record = session.step()
    assert record.status is ValueStatus.UNREADABLE and record.value is None and record.reject_reasons


def test_start_refused_when_reference_still_changed(tmp_path):
    session = _session(tmp_path, [], reference_ok=False)
    with pytest.raises(StartRefused, match="Referenzbild"):
        session.start()


def test_start_refused_without_calibration(tmp_path):
    session = _session(tmp_path, [])
    (tmp_path / "timing.json").unlink()
    with pytest.raises(StartRefused, match="Timing-Kalibrierung"):
        session.start()


def test_camera_loss_ends_session_with_reason(tmp_path):
    session = _session(tmp_path, [])
    session.start()
    session._owner.running = False
    with pytest.raises(CameraLost, match="kein Bild"):
        session.step(timeout=0.01)
```

Hinweis zum Test der Lücke: `FakeOwner.wait_newer` liefert bei übersprungenen Bildern das neueste; die Anzahl übersprungener Bilder prüft Task 9 indirekt über `summary["frames_skipped"]`. Den Test so belassen.

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_session.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'dispread.live.session'`

- [ ] **Step 3: `session.py` schreiben**

```python
"""Live-Sitzung: bestaetigtes Profil -> Pipeline -> ValueRecord -> JSONL.

Spec 2026-10-12 §2/§4. Liest immer das neueste Bild des CameraOwner,
ueberspringt aeltere und zaehlt sie. Jeder Datensatz traegt die Aufnahmezeit
des gelesenen Bilds. Die Timing-Kalibrierung ist Pflicht und wird in
session.json aufgezeichnet, aber nicht angewandt.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from dispread.layout import CharLayout
from dispread.live import (
    DEFAULT_CALIBRATION,
    DEFAULT_TEMPLATES,
    DEFAULT_TEMPLATES_SHA256,
    RELEASE_NOTICE,
)
from dispread.live.clock import ClockLog
from dispread.live.tracking import TrackedQuadLocator
from dispread.ocr.dotmatrix import DotMatrixReader
from dispread.pipeline import Pipeline, PipelineConfig
from dispread.records import ValueRecord
from dispread.session_profile import SessionProfile
from dispread.sink.jsonl import JsonlSink
from dispread.timing_calibration import load_calibration
from dispread.validate import ReleaseGate, default_gate_config

SCHEMA = "live-session/1"


class StartRefused(ValueError):
    """Sitzung startet nicht; die Meldung nennt den Grund."""


class CameraLost(RuntimeError):
    """Die Kamera liefert keine Bilder mehr."""


@dataclass(frozen=True)
class LiveConfig:
    templates: Path = DEFAULT_TEMPLATES
    templates_sha256: str = DEFAULT_TEMPLATES_SHA256
    calibration: Path = DEFAULT_CALIBRATION
    unit: str = "mV/V"
    confirm_frames: int = 2
    clock_interval_s: float = 60.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LiveSession:
    def __init__(
        self,
        owner: Any,
        profile_path: Path,
        config: LiveConfig,
        out_dir: Path,
        *,
        reader_factory: Callable[[Path, str], Any] = DotMatrixReader.from_file,
        locator_factory: Callable[[Any, list], Any] = TrackedQuadLocator,
        clock: ClockLog | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] | None = None,
    ) -> None:
        self._owner = owner
        self._profile_path = Path(profile_path)
        self._config = config
        self._out_dir = Path(out_dir)
        self._reader_factory = reader_factory
        self._locator_factory = locator_factory
        self._clock = clock or ClockLog()
        self._monotonic = monotonic
        self._wall = wall or (lambda: datetime.now(UTC))
        self.session_path = self._out_dir / "session.json"
        self.records_path = self._out_dir / "records.jsonl"
        self.latest: ValueRecord | None = None
        self.end_reason: str | None = None
        self.summary: dict = {}
        self._pipeline: Pipeline | None = None
        self._sink: JsonlSink | None = None
        self._meta: dict = {}
        self._seen = 0
        self._by_status: dict[str, int] = {}
        self._frames_read = 0
        self._frames_skipped = 0
        self._last_clock = 0.0

    # -- Start ---------------------------------------------------------------
    def start(self) -> None:
        cfg = self._config
        try:
            profile = SessionProfile.load(self._profile_path)
            layout = CharLayout.from_profile(profile, cfg.unit)
        except (OSError, ValueError, KeyError) as exc:
            raise StartRefused(f"Profil {self._profile_path}: {exc}") from exc
        try:
            reader = self._reader_factory(cfg.templates, cfg.templates_sha256)
        except (OSError, ValueError) as exc:
            raise StartRefused(f"Vorlagen {cfg.templates}: {exc}") from exc
        try:
            calibration = load_calibration(cfg.calibration)
        except ValueError as exc:
            raise StartRefused(f"Timing-Kalibrierung fehlt oder ist ungueltig: {exc}") from exc
        if profile.camera is not None and calibration.camera_usb_id != profile.camera.usb_id:
            raise StartRefused(
                f"Timing-Kalibrierung gilt fuer {calibration.camera_usb_id}, Profil nutzt {profile.camera.usb_id}"
            )
        reference = profile.reference_frame or {}
        ref_path = Path(reference.get("path", ""))
        if not ref_path.is_file() or _sha256(ref_path) != reference.get("sha256"):
            raise StartRefused(f"Referenzbild {ref_path} fehlt oder wurde veraendert - neu einrichten")
        image = cv2.imread(str(ref_path))
        if image is None:
            raise StartRefused(f"Referenzbild {ref_path} nicht lesbar - neu einrichten")
        gate = ReleaseGate(
            default_gate_config("dotmatrix", confirm_frames=cfg.confirm_frames, expected_unit=cfg.unit)
        )
        self._pipeline = Pipeline(
            source=self._owner,
            locator=self._locator_factory(image, profile.quad),
            reader=reader,
            gate=gate,
            sinks=[],
            config=PipelineConfig(
                profile_id=f"{profile.device_id}/{profile.session_id}", layout=layout, locate_every=0
            ),
        )
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._sink = JsonlSink(self.records_path)
        self._sink.open()
        self._meta = {
            "schema": SCHEMA,
            "session_id": profile.session_id,
            "device_id": profile.device_id,
            "profile": {"path": str(self._profile_path), "sha256": _sha256(self._profile_path)},
            "templates": {"path": str(cfg.templates), "sha256": cfg.templates_sha256},
            "timing_calibration": {
                "path": str(cfg.calibration),
                "sha256": _sha256(Path(cfg.calibration)),
                "display_offset_ms": calibration.display_offset_ms,
                "guard_margin_ms": calibration.guard_margin_ms,
                "applied": False,
            },
            "gate": {"backend": "dotmatrix", "confirm_frames": cfg.confirm_frames, "expected_unit": cfg.unit},
            "camera": self._owner.status().get("source", {}),
            "release_notice": RELEASE_NOTICE,
            "started_at_utc": self._wall().isoformat(),
        }
        latest = self._owner.latest() if hasattr(self._owner, "latest") else None
        self._seen = latest[0] if latest else 0
        self._clock.sample()
        self._last_clock = self._monotonic()
        self._write_session(ended=False)

    # -- Lesen ---------------------------------------------------------------
    def step(self, timeout: float = 0.5) -> ValueRecord | None:
        assert self._pipeline is not None and self._sink is not None, "start() zuerst"
        got = self._owner.wait_newer(self._seen, timeout)
        if got is None:
            status = self._owner.status()
            if not status["running"]:
                raise CameraLost(status.get("error") or "Kamera gestoppt")
            return None
        sequence, frame = got
        skipped = max(0, sequence - self._seen - 1) if self._seen else 0
        self._seen = sequence
        self._frames_skipped += skipped
        record = self._pipeline.process(frame, dropped_frames=skipped)
        self._sink.emit(record)
        self._frames_read += 1
        self._by_status[record.status.value] = self._by_status.get(record.status.value, 0) + 1
        self.latest = record
        if self._monotonic() - self._last_clock >= self._config.clock_interval_s:
            self._clock.sample()
            self._last_clock = self._monotonic()
            self._write_session(ended=False)
        return record

    def run(self, stop: threading.Event) -> None:
        """Lesen, bis `stop` gesetzt ist oder die Kamera ausfaellt."""
        try:
            while not stop.is_set():
                self.step()
        except CameraLost as exc:
            self.end_reason = f"kamera: {exc}"

    # -- Ende ----------------------------------------------------------------
    def stop(self, reason: str = "bediener") -> dict:
        if self.end_reason is None:
            self.end_reason = reason
        self._clock.sample()
        if self._sink is not None:
            self._sink.close()
        self._write_session(ended=True)
        return self.summary

    def _write_session(self, *, ended: bool) -> None:
        owner_status = self._owner.status()
        self.summary = {
            "by_status": dict(self._by_status),
            "frames_read": self._frames_read,
            "frames_skipped": self._frames_skipped,
            "frame_gaps": owner_status.get("gaps", 0),
            "camera_error": owner_status.get("error"),
            "end_reason": self.end_reason if ended else None,
        }
        data = dict(self._meta)
        data["clock_offset_boottime_minus_monotonic_ns"] = self._clock.to_session(ended=ended)
        data["summary"] = self.summary
        if ended:
            data["ended_at_utc"] = self._wall().isoformat()
        tmp = self.session_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.session_path)
```

Hinweis: `FakeOwner` im Test hat kein `latest()`; `start()` prüft das mit `hasattr`. `CameraOwner` hat es.

- [ ] **Step 4: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_session.py -v`
Expected: PASS. Falls `load_calibration` andere Pflichtfelder verlangt als im Test geschrieben: `src/dispread/timing_calibration.py:79` (`load_calibration_from_bytes`) lesen und das Test-JSON genau daran anpassen — nicht den Lader ändern.

- [ ] **Step 5: CHANGELOG, Lint, Commit** — Punkt: „`LiveSession`: bestätigtes Profil → nachgeführtes Quad → Dot-Matrix-Leser → Freigabe (`confirm_frames=2`) → `records.jsonl`; `session.json` mit Versatz BOOTTIME−MONOTONIC, aufgezeichneter (nicht angewandter) Timing-Kalibrierung und Freigabehinweis. Start wird abgelehnt ohne Kalibrierung, bei falscher Vorlagenprüfsumme oder verändertem Referenzbild."

```bash
./.venv/bin/ruff check src tests examples
./.venv/bin/pytest -q
git add src/dispread/live/session.py tests/test_live_session.py CHANGELOG.md
git commit -m "Messpfad live 8: LiveSession mit JSONL-Audit und Zeitbasis"
```

---

### Task 9: `LiveService` (Zustandsautomat für die Oberfläche)

**Files:**
- Create: `src/dispread/live/service.py`, `tests/test_live_service.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `CameraOwner` (Task 3), `focus_camera`, `assist_measure`, `propose_with_fit`, `confirm_proposal`, `offline_text_source`, `serial_text_source`, `SERIAL_PORT`, `SERIAL_BAUDRATE` (Tasks 5–7), `LiveSession`, `LiveConfig`, `StartRefused` (Task 8), `validate_offline_cell_text` (`dispread.gsv2as_cell_text`), `RESOLUTION_ERROR_PX` (`dispread.setup_checks`)
- Produces: `LiveError(ValueError)`; `OwnerSetupCamera(owner)` (erfüllt `SetupCamera`)
- Produces: `LiveService(owner, data_dir: Path, *, config: LiveConfig = LiveConfig(), simulate: bool = False, source_for: Callable[[CameraSettings], FrameSource] | None = None, serial_opener: Callable[[], Any] | None = None, setup_runner: Callable[..., None] | None = None, wall=None)` mit `status() -> dict`, `start_setup(*, cell_text: str | None = None) -> None`, `confirm(*, confirmed_by: str, format_checked: bool, acknowledge_warning: bool = False) -> None`, `start_run() -> None`, `stop_run() -> None`, `start_camera() -> None`, `setup_file(name: str) -> Path | None`, `close() -> None`
- Zustände (`status()["state"]`): `idle`, `setup_running`, `setup_ready`, `setup_failed`, `confirmed`, `running`, `stopped`

- [ ] **Step 1: Fehlschlagende Tests schreiben** — `tests/test_live_service.py`:

```python
import json
import threading
import time

import pytest

from dispread.live.service import LiveError, LiveService


class FakeOwner:
    source_id = "fake"

    def __init__(self):
        self.restarts = 0

    def status(self):
        return {"running": True, "error": None, "frames": 1, "gaps": 0, "source": {"device": "/dev/fake"}}

    def latest(self):
        return None

    def wait_newer(self, after, timeout):
        time.sleep(min(timeout, 0.01))
        return None

    def restart(self, factory=None):
        self.restarts += 1

    def start(self):
        pass


def _wait_state(service, states, timeout=2.0):
    deadline = time.monotonic() + timeout
    while service.status()["state"] not in states and time.monotonic() < deadline:
        time.sleep(0.01)
    return service.status()["state"]


def test_simulate_refuses_setup_with_clear_reason(tmp_path):
    service = LiveService(FakeOwner(), tmp_path, simulate=True)
    with pytest.raises(LiveError, match="StreamCam"):
        service.start_setup()


def test_bad_operator_cell_text_is_refused_before_camera(tmp_path):
    called = []
    service = LiveService(FakeOwner(), tmp_path, setup_runner=lambda **kw: called.append(kw))
    with pytest.raises(LiveError, match="Zellentext"):
        service.start_setup(cell_text="zu kurz")
    assert called == [] and service.status()["state"] == "idle"


def test_setup_runner_result_leads_to_ready_then_confirm_rules(tmp_path):
    def runner(*, session_dir, cell_text, report):
        report("vorschlag")
        (session_dir / "setup").mkdir(parents=True, exist_ok=True)
        return {"setup_checks": {"overall": "WARNUNG", "checks": {}}, "frame": "x"}

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup()
    assert _wait_state(service, {"setup_ready"}) == "setup_ready"
    with pytest.raises(LiveError, match="Format"):
        service.confirm(confirmed_by="Leonhard Hentschke", format_checked=False)
    with pytest.raises(LiveError, match="WARNUNG"):
        service.confirm(confirmed_by="Leonhard Hentschke", format_checked=True)


def test_setup_failure_is_reported(tmp_path):
    def runner(**_kw):
        raise ValueError("Punktraster abgelehnt: keine_startlage")

    service = LiveService(FakeOwner(), tmp_path, setup_runner=runner)
    service.start_setup()
    assert _wait_state(service, {"setup_failed"}) == "setup_failed"
    assert "keine_startlage" in service.status()["error"]


def test_run_rules_double_start_stop_without_run_and_setup_while_running(tmp_path, monkeypatch):
    service = LiveService(FakeOwner(), tmp_path)
    with pytest.raises(LiveError, match="kein Lauf"):
        service.stop_run()
    with pytest.raises(LiveError, match="bestaetigt"):
        service.start_run()

    class FakeSession:
        def __init__(self, *a, **kw):
            self.latest, self.summary, self.end_reason = None, {}, None
            self.session_path = tmp_path / "s.json"

        def start(self):
            pass

        def run(self, stop):
            stop.wait()

        def stop(self, reason="bediener"):
            self.end_reason = reason
            return {"end_reason": reason}

    monkeypatch.setattr("dispread.live.service.LiveSession", FakeSession)
    service._state, service._profile_path = "confirmed", tmp_path / "profile.json"
    service._profile_camera = None
    service.start_run()
    assert service.status()["state"] == "running"
    with pytest.raises(LiveError, match="laeuft bereits"):
        service.start_run()
    with pytest.raises(LiveError, match="Lauf zuerst beenden"):
        service.start_setup()
    service.stop_run()
    assert service.status()["state"] == "stopped"


def test_camera_loss_during_run_is_shown(tmp_path, monkeypatch):
    class LosingSession:
        def __init__(self, *a, **kw):
            self.latest, self.summary, self.end_reason = None, {}, None
            self.session_path = tmp_path / "s.json"

        def start(self):
            pass

        def run(self, stop):
            self.end_reason = "kamera: kein Bild"

        def stop(self, reason="bediener"):
            return {"end_reason": self.end_reason}

    monkeypatch.setattr("dispread.live.service.LiveSession", LosingSession)
    service = LiveService(FakeOwner(), tmp_path)
    service._state, service._profile_path, service._profile_camera = "confirmed", tmp_path / "p.json", None
    service.start_run()
    assert _wait_state(service, {"stopped"}) == "stopped"
    assert "kein Bild" in service.status()["error"]
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_service.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'dispread.live.service'`

- [ ] **Step 3: `service.py` schreiben**

```python
"""Zustandsautomat der Live-Seite: Einrichtung, Bestaetigung, Lauf.

Kein Web-Code. Die Werkbank ruft diese Methoden auf und zeigt `status()` an;
alle Entscheidungen (Freigabe, Ablehnung, Bestaetigungsregeln) fallen hier
oder tiefer (Spec 2026-10-12 §1/§3).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from dispread.camera_settings import CameraSettings
from dispread.frames import FrameSource
from dispread.frames.uvc_source import UvcError, UvcSource
from dispread.gsv2as_cell_text import validate_offline_cell_text
from dispread.live import RELEASE_NOTICE
from dispread.live import setup as live_setup
from dispread.live.session import LiveConfig, LiveSession, StartRefused
from dispread.session_profile import SessionProfile
from dispread.setup_checks import RESOLUTION_ERROR_PX

OVERLAYS = ("still", "stability", "overlay_source", "overlay_sampling", "overlay_rectified")
DEVICE_ID = "gsv-sensor-161a"


class LiveError(ValueError):
    """Bedienfehler oder abgelehnter Schritt; Meldung fuer die Seite."""


class OwnerSetupCamera:
    """`SetupCamera` ueber den CameraOwner (Bilder aus dem laufenden Strom)."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner
        self.device = owner.status().get("source", {}).get("device") or "?"

    def _target(self) -> Any:
        target = self._owner.control_target()
        if target is None:
            raise live_setup.SetupError("Kamera kann keine Regler setzen (Simulation?)")
        return target

    def set_controls(self, controls: list[tuple[str, int]]) -> None:
        self._target().set_controls(list(controls))

    def get_controls(self, names: list[str]) -> dict[str, int]:
        return self._target().get_controls(list(names))

    def fresh_still(self, discard: int = 10) -> np.ndarray:
        latest = self._owner.latest()
        seen = latest[0] if latest else 0
        got = None
        for _ in range(discard + 1):
            got = self._owner.wait_newer(seen, 2.0)
            if got is None:
                raise UvcError(f"kein frisches Bild von {self.device}")
            seen = got[0]
        return got[1].image.copy()


class LiveService:
    def __init__(
        self,
        owner: Any,
        data_dir: Path,
        *,
        config: LiveConfig = LiveConfig(),
        simulate: bool = False,
        source_for: Callable[[CameraSettings], FrameSource] | None = None,
        serial_opener: Callable[[], Any] | None = None,
        setup_runner: Callable[..., dict] | None = None,
        wall: Callable[[], datetime] | None = None,
    ) -> None:
        self._owner = owner
        self._data_dir = Path(data_dir)
        self._config = config
        self._simulate = simulate
        self._source_for = source_for or (lambda settings: UvcSource(settings))
        self._serial_opener = serial_opener or self._open_serial
        self._setup_runner = setup_runner or self._run_setup
        self._wall = wall or (lambda: datetime.now(UTC))
        self._lock = threading.Lock()
        self._state = "idle"
        self._step: str | None = None
        self._error: str | None = None
        self._session_dir: Path | None = None
        self._proposal: dict | None = None
        self._profile_path: Path | None = None
        self._profile_camera: CameraSettings | None = None
        self._profile_info: dict | None = None
        self._session: LiveSession | None = None
        self._run_stop: threading.Event | None = None
        self._run_thread: threading.Thread | None = None
        self._setup_thread: threading.Thread | None = None

    # -- Anzeige -------------------------------------------------------------
    def status(self) -> dict:
        with self._lock:
            setup = None
            if self._proposal is not None:
                checks = self._proposal.get("setup_checks", {})
                setup = {
                    "overall": checks.get("overall"),
                    "checks": {n: c.get("status") for n, c in checks.get("checks", {}).items()},
                    "overlays": [n for n in OVERLAYS if self.setup_file(n) is not None],
                }
            run = None
            if self._session is not None:
                latest = self._session.latest
                run = {
                    "latest": None if latest is None else {
                        "frame_sequence": latest.frame_sequence,
                        "status": latest.status.value,
                        "value": latest.value,
                        "unit": latest.unit,
                        "raw_text": latest.raw_text,
                        "reject_reasons": list(latest.reject_reasons),
                        "frames_confirmed": latest.frames_confirmed,
                        "confirmation_span_ns": latest.confirmation_span_ns,
                        "capture_timestamp": latest.capture_timestamp.to_dict(),
                    },
                    "summary": dict(self._session.summary),
                }
            return {
                "state": self._state,
                "step": self._step,
                "error": self._error,
                "simulate": self._simulate,
                "camera": self._owner.status(),
                "release_notice": RELEASE_NOTICE,
                "session_id": None if self._session_dir is None else self._session_dir.name,
                "setup": setup,
                "profile": self._profile_info,
                "run": run,
            }

    def setup_file(self, name: str) -> Path | None:
        if name not in OVERLAYS or self._session_dir is None:
            return None
        path = self._session_dir / "setup" / f"{name}.png"
        return path if path.is_file() else None

    # -- Kamera --------------------------------------------------------------
    def start_camera(self) -> None:
        try:
            self._owner.start()
        except Exception as exc:  # noqa: BLE001 - Meldung fuer die Seite
            raise LiveError(f"Kamera nicht gestartet: {exc}") from exc

    # -- Einrichtung ---------------------------------------------------------
    def start_setup(self, *, cell_text: str | None = None) -> None:
        if self._simulate:
            raise LiveError("Einrichtung braucht die StreamCam (Simulation zeigt nur die Vorschau)")
        with self._lock:
            if self._state == "running":
                raise LiveError("Lauf zuerst beenden")
            if self._state == "setup_running":
                raise LiveError("Einrichtung laeuft bereits")
        text = None
        if cell_text is not None and cell_text != "":
            try:
                text = validate_offline_cell_text(cell_text)
            except ValueError as exc:
                raise LiveError(f"Zellentext: {exc}") from exc
        session_dir = self._data_dir / ("live-" + self._wall().strftime("%Y%m%dT%H%M%SZ"))
        with self._lock:
            self._state, self._step, self._error = "setup_running", "start", None
            self._session_dir, self._proposal = session_dir, None
            self._profile_path = self._profile_camera = self._profile_info = None
            self._session = None
        self._setup_thread = threading.Thread(
            target=self._setup_worker, args=(session_dir, text), name="live-setup", daemon=True
        )
        self._setup_thread.start()

    def _report(self, step: str) -> None:
        with self._lock:
            self._step = step

    def _setup_worker(self, session_dir: Path, text: str | None) -> None:
        try:
            proposal = self._setup_runner(session_dir=session_dir, cell_text=text, report=self._report)
        except Exception as exc:  # noqa: BLE001 - jeder Abbruch geht als Meldung an die Seite
            with self._lock:
                self._state, self._error = "setup_failed", str(exc)
            return
        with self._lock:
            self._proposal, self._state, self._step = proposal, "setup_ready", "vorschlag"

    def _open_serial(self) -> Any:
        import serial

        return serial.Serial(live_setup.SERIAL_PORT, live_setup.SERIAL_BAUDRATE, timeout=2.0)

    def _run_setup(self, *, session_dir: Path, cell_text: str | None, report: Callable[[str], None]) -> dict:
        """Echter Ablauf: Fokus -> Kamera mit festen Reglern -> Standbilder -> Vorschlag."""
        setup_dir = session_dir / "setup"
        setup_dir.mkdir(parents=True, exist_ok=True)
        report("fokus")
        settings, sweep = live_setup.focus_camera(OwnerSetupCamera(self._owner), None)
        (setup_dir / "camera-settings.json").write_text(
            json.dumps({"camera": settings.to_dict(), "focus_sweep": [[f, s] for f, s in sweep],
                        "created_at_utc": self._wall().isoformat()}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        report("kamera")
        self._owner.restart(lambda: self._source_for(settings))
        port = None
        try:
            if cell_text is None:
                try:
                    port = self._serial_opener()
                except Exception as exc:  # noqa: BLE001
                    raise live_setup.SetupError(
                        f"kein GSV-2AS an {live_setup.SERIAL_PORT} ({exc}) - Zellentext eingeben"
                    ) from exc
                text_source = live_setup.serial_text_source(port)
            else:
                text_source = live_setup.offline_text_source(cell_text)
            report("standbilder")
            result = live_setup.assist_measure(
                OwnerSetupCamera(self._owner),
                cell_text=text_source,
                expected_size=settings.size,
                out_dir=setup_dir,
                templates=self._config.templates,
                templates_sha256=self._config.templates_sha256,
                info=lambda message: report(message),
            )
        finally:
            if port is not None:
                port.close()
        report("vorschlag")
        return live_setup.propose_with_fit(
            result.first,
            fit=result.fit,
            frame_path=setup_dir / "still.png",
            camera_settings=settings,
            device_id=DEVICE_ID,
            session_id=session_dir.name,
            out_dir=setup_dir,
            offset_check=result.offset_check,
            final_checks=result.final_checks,
            stability_image_bgr=result.second,
            stability_elapsed_s=result.stability_elapsed_s,
            reader_check=result.reader_check,
        )

    def confirm(self, *, confirmed_by: str, format_checked: bool, acknowledge_warning: bool = False) -> None:
        with self._lock:
            if self._state != "setup_ready" or self._proposal is None or self._session_dir is None:
                raise LiveError("Kein Vorschlag zum Bestaetigen")
            proposal, session_dir = self._proposal, self._session_dir
        if not format_checked:
            raise LiveError("Einheit mV/V und Format gsv2as_v1 muessen geprueft sein")
        overall = proposal.get("setup_checks", {}).get("overall")
        if overall == "FEHLER":
            raise LiveError("Einrichtung meldet FEHLER - nicht bestaetigbar")
        if overall == "WARNUNG" and not acknowledge_warning:
            raise LiveError("Einrichtung meldet WARNUNG - ausdruecklich zur Kenntnis nehmen")
        try:
            profile: SessionProfile = live_setup.confirm_proposal(
                proposal, confirmed_by=confirmed_by, resolution_threshold_px=RESOLUTION_ERROR_PX,
            )
        except live_setup.SetupError as exc:
            raise LiveError(str(exc)) from exc
        if not profile.resolution_ok:
            raise LiveError("Aufloesung unter der Schwelle - Kamera naeher stellen und neu einrichten")
        path = session_dir / "profile.json"
        profile.save(path)
        with self._lock:
            self._profile_path, self._profile_camera = path, profile.camera
            self._profile_info = {"confirmed_by": profile.confirmed_by,
                                  "confirmed_at_utc": profile.confirmed_at_utc,
                                  "warning_acknowledged": overall == "WARNUNG"}
            self._state = "confirmed"

    # -- Lauf ----------------------------------------------------------------
    def start_run(self) -> None:
        with self._lock:
            if self._state == "running":
                raise LiveError("Lauf laeuft bereits")
            if self._state not in ("confirmed", "stopped") or self._profile_path is None:
                raise LiveError("Erst einrichten und bestaetigen")
            profile_path, camera = self._profile_path, self._profile_camera
            out_dir = profile_path.parent
        if camera is not None:
            self._owner.restart(lambda: self._source_for(camera))
        session = LiveSession(self._owner, profile_path, self._config, out_dir)
        try:
            session.start()
        except StartRefused as exc:
            raise LiveError(str(exc)) from exc
        stop = threading.Event()
        with self._lock:
            self._session, self._run_stop, self._state, self._error = session, stop, "running", None
        self._run_thread = threading.Thread(target=self._run_worker, args=(session, stop), name="live-run",
                                            daemon=True)
        self._run_thread.start()

    def _run_worker(self, session: LiveSession, stop: threading.Event) -> None:
        session.run(stop)
        if not stop.is_set():  # Kamera ausgefallen, nicht vom Bediener beendet
            session.stop(session.end_reason or "kamera")
            with self._lock:
                self._state, self._error = "stopped", session.end_reason

    def stop_run(self) -> None:
        with self._lock:
            if self._state != "running" or self._run_stop is None or self._session is None:
                raise LiveError("kein Lauf aktiv")
            stop, session, thread = self._run_stop, self._session, self._run_thread
        stop.set()
        if thread is not None:
            thread.join(3.0)
        session.stop("bediener")
        with self._lock:
            self._state = "stopped"

    def close(self) -> None:
        if self._state == "running":
            self.stop_run()
```

Hinweis: In `test_setup_runner_result_leads_to_ready_then_confirm_rules` heißt der Fehler bei fehlender Formatprüfung „…Format gsv2as_v1 muessen geprueft sein" — der Test sucht `"Format"`. In `test_run_rules_…` sucht der Test bei `start_run` ohne Bestätigung `"bestaetigt"`: die Meldung „Erst einrichten und bestaetigen" enthält das.

- [ ] **Step 4: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_service.py -v`
Expected: PASS

- [ ] **Step 5: CHANGELOG, Lint, Commit** — Punkt: „`LiveService`: Zustandsautomat der Live-Seite (Einrichtung im Hintergrund mit Fortschritt, Bestätigung nur ohne FEHLER und mit Kenntnisnahme bei WARNUNG, Lauf starten/stoppen, Kameraausfall wird angezeigt)."

```bash
./.venv/bin/ruff check src tests examples
./.venv/bin/pytest -q
git add src/dispread/live/service.py tests/test_live_service.py CHANGELOG.md
git commit -m "Messpfad live 9: LiveService"
```

---

### Task 10: `/live`-API, Live-Seite und Verdrahtung in `dispread serve`

**Files:**
- Create: `src/dispread/workbench/live_api.py`, `src/dispread/workbench/static/live.html`, `src/dispread/workbench/static/live.js`, `tests/test_live_api.py`, `tests/live_client.test.mjs`, `tests/test_live_client.py`
- Modify: `src/dispread/workbench/server.py`, `src/dispread/workbench/cli.py`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `LiveService` (Task 9), `CameraOwner` (Task 3), `preview_settings`, `UvcSource(apply_controls=False)` (Task 3)
- Produces: `add_live_routes(app: web.Application, service, csrf_of: Callable[[web.Request], str]) -> None`; `make_app(controller, terminals, verifier=authenticate, live=None)`
- Routen: `GET /live` (Seite), `GET /live/status`, `POST /live/setup` (`{"cell_text": str|null}`), `POST /live/confirm` (`{"confirmed_by", "format_checked", "acknowledge_warning"}`), `POST /live/run/start`, `POST /live/run/stop`, `POST /live/camera/start`, `GET /live/setup/{name}.png`, `GET /live/preview.jpg`
- Produces (JS): `statusView(status) -> {headline: string, cls: string, detail: string}` in `live.js`, exportiert

- [ ] **Step 1: Fehlschlagende API-Tests schreiben** — `tests/test_live_api.py`:

```python
import asyncio

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from dispread.live.service import LiveError
from dispread.workbench.live_api import add_live_routes


class FakeService:
    def __init__(self):
        self.calls = []

    def status(self):
        return {"state": "idle", "release_notice": "Validiert nur: …"}

    def start_setup(self, *, cell_text=None):
        self.calls.append(("setup", cell_text))

    def confirm(self, **kw):
        raise LiveError("Kein Vorschlag zum Bestaetigen")

    def start_run(self):
        self.calls.append(("run",))

    def stop_run(self):
        raise LiveError("kein Lauf aktiv")

    def start_camera(self):
        self.calls.append(("camera",))

    def setup_file(self, name):
        return None

    def preview_jpeg(self):
        return None


def _run(check):
    async def main():
        app = web.Application()
        service = FakeService()
        add_live_routes(app, service, csrf_of=lambda _r: "tok")
        async with TestClient(TestServer(app)) as client:
            await check(client, service)

    asyncio.run(main())


def test_status_carries_csrf_and_notice():
    async def check(client, _service):
        data = await (await client.get("/live/status")).json()
        assert data["csrf"] == "tok" and data["release_notice"].startswith("Validiert nur")

    _run(check)


def test_setup_passes_cell_text_and_errors_become_409():
    async def check(client, service):
        assert (await client.post("/live/setup", json={"cell_text": "+0.60972 "})).status == 200
        assert service.calls == [("setup", "+0.60972 ")]
        response = await client.post("/live/run/stop")
        assert response.status == 409 and "kein Lauf" in (await response.json())["error"]

    _run(check)


def test_unknown_overlay_is_404():
    async def check(client, _service):
        assert (await client.get("/live/setup/etc-passwd.png")).status == 404

    _run(check)
```

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_live_api.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'dispread.workbench.live_api'`

- [ ] **Step 3: `LiveService.preview_jpeg` ergänzen** — in `src/dispread/live/service.py`:

```python
    def preview_jpeg(self, width: int = 960) -> bytes | None:
        """Neuestes Bild verkleinert als JPEG; mit Lauf das nachgefuehrte Quad."""
        import cv2

        latest = self._owner.latest()
        if latest is None:
            return None
        image = latest[1].image
        scale = width / image.shape[1]
        small = cv2.resize(image, (width, round(image.shape[0] * scale)))
        session = self._session
        locator = getattr(getattr(session, "_pipeline", None), "locator", None)
        track = getattr(locator, "last_track", None)
        if track is not None and track.quad is not None:
            points = np.array([[x * scale, y * scale] for x, y in track.quad], dtype=np.int32)
            cv2.polylines(small, [points], True, (0, 220, 0), 2)
        ok, encoded = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return encoded.tobytes() if ok else None
```

- [ ] **Step 4: `live_api.py` schreiben**

```python
"""HTTP-Routen der Live-Seite. Nur Weiterreichen an LiveService."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from aiohttp import web

from dispread.live.service import LiveError

STATIC = Path(__file__).parent / "static"


def add_live_routes(app: web.Application, service, csrf_of: Callable[[web.Request], str]) -> None:
    async def page(_request):
        return web.FileResponse(STATIC / "live.html")

    async def status(request):
        data = await asyncio.to_thread(service.status)
        data["csrf"] = csrf_of(request)
        return web.json_response(data)

    async def _call(fn, **kwargs):
        try:
            await asyncio.to_thread(fn, **kwargs)
        except LiveError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        return web.json_response({"ok": True})

    async def setup(request):
        data = await request.json() if request.can_read_body else {}
        return await _call(service.start_setup, cell_text=data.get("cell_text"))

    async def confirm(request):
        data = await request.json()
        return await _call(
            service.confirm,
            confirmed_by=str(data.get("confirmed_by", "")),
            format_checked=bool(data.get("format_checked")),
            acknowledge_warning=bool(data.get("acknowledge_warning")),
        )

    async def run_start(_request):
        return await _call(service.start_run)

    async def run_stop(_request):
        return await _call(service.stop_run)

    async def camera_start(_request):
        return await _call(service.start_camera)

    async def setup_image(request):
        path = service.setup_file(request.match_info["name"])
        if path is None:
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def preview(_request):
        jpeg = await asyncio.to_thread(service.preview_jpeg)
        if jpeg is None:
            raise web.HTTPServiceUnavailable()
        return web.Response(body=jpeg, content_type="image/jpeg")

    app.router.add_get("/live", page)
    app.router.add_get("/live/status", status)
    app.router.add_post("/live/setup", setup)
    app.router.add_post("/live/confirm", confirm)
    app.router.add_post("/live/run/start", run_start)
    app.router.add_post("/live/run/stop", run_stop)
    app.router.add_post("/live/camera/start", camera_start)
    app.router.add_get("/live/setup/{name}.png", setup_image)
    app.router.add_get("/live/preview.jpg", preview)
```

- [ ] **Step 5: API-Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_live_api.py -v`
Expected: PASS

- [ ] **Step 6: Seite schreiben**

`src/dispread/workbench/static/live.html`:

```html
<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>picam / live</title>
<style>
body{font:15px system-ui,sans-serif;margin:0;background:#111;color:#eee}
main{max-width:1100px;margin:0 auto;padding:16px;display:grid;gap:16px}
.notice{background:#4a3b00;color:#ffe9a6;padding:8px 12px;border-radius:6px}
.value{font:600 56px ui-monospace,monospace}
.valid{color:#7ee787}.transition{color:#ffd33d}.unreadable,.stale,.error{color:#ff7b72}
section{background:#1c1c1c;border-radius:8px;padding:12px}
img{max-width:100%;border-radius:6px}
button{font:inherit;padding:6px 12px;margin:4px 4px 0 0}
input[type=text]{font:inherit;width:22ch}
#overlays img{max-width:48%}
</style>
</head>
<body>
<main>
  <div class="notice" id="notice"></div>
  <section>
    <div class="value" id="headline">—</div>
    <div id="detail"></div>
  </section>
  <section>
    <img id="preview" alt="Kameravorschau">
    <div id="camera"></div>
    <button id="camera-start">Kamera neu verbinden</button>
  </section>
  <section>
    <h2>Einrichtung</h2>
    <label>Zellentext Zellen 0–8, z. B. „+0.60972 " (leer = vom GSV-2AS lesen): <input type="text" id="cell-text" maxlength="9"></label>
    <button id="setup">Einrichtung starten</button>
    <div id="setup-state"></div>
    <div id="overlays"></div>
    <div id="confirm-box" hidden>
      <label>Name: <input type="text" id="confirmed-by"></label>
      <label><input type="checkbox" id="format-checked"> Einheit mV/V und Format geprüft</label>
      <label id="ack-label" hidden><input type="checkbox" id="ack"> WARNUNG zur Kenntnis genommen</label>
      <button id="confirm">Bestätigen</button>
    </div>
  </section>
  <section>
    <button id="run-start">Lauf starten</button>
    <button id="run-stop">Lauf stoppen</button>
    <div id="error" class="error"></div>
  </section>
</main>
<script type="module" src="/static/live.js"></script>
</body>
</html>
```

`src/dispread/workbench/static/live.js`:

```javascript
// Live-Seite: zeigt LiveService.status() an und reicht Bedienschritte weiter.
// Entscheidungen fallen im Server (dispread.live), nie hier.

export function statusView(status) {
  const run = status.run && status.run.latest;
  if (status.state === 'running' && run) {
    const reasons = run.reject_reasons.join(', ');
    if (run.status === 'valid') {
      return {headline: `${run.raw_text} ${run.unit}`, cls: 'valid', detail: `Bild ${run.frame_sequence}`};
    }
    return {headline: run.status.toUpperCase(), cls: run.status, detail: reasons};
  }
  const labels = {
    idle: 'Bereit zur Einrichtung', setup_running: `Einrichtung läuft: ${status.step || ''}`,
    setup_ready: 'Vorschlag prüfen und bestätigen', setup_failed: 'Einrichtung abgebrochen',
    confirmed: 'Bestätigt – Lauf starten', running: 'Lauf startet …', stopped: 'Lauf beendet',
  };
  return {headline: labels[status.state] || status.state, cls: status.error ? 'error' : '', detail: status.error || ''};
}

if (typeof document !== 'undefined') {
  let csrf = '';
  const $ = (id) => document.getElementById(id);
  const post = async (path, body) => {
    const response = await fetch(path, {method: 'POST', headers: {'Content-Type': 'application/json',
      'X-CSRF-Token': csrf}, body: JSON.stringify(body || {})});
    const data = await response.json().catch(() => ({}));
    $('error').textContent = response.ok ? '' : (data.error || response.statusText);
  };
  const render = (s) => {
    csrf = s.csrf;
    $('notice').textContent = s.release_notice;
    const view = statusView(s);
    $('headline').textContent = view.headline;
    $('headline').className = `value ${view.cls}`;
    $('detail').textContent = view.detail;
    const cam = s.camera || {};
    $('camera').textContent = cam.running ? `Kamera läuft, ${cam.frames} Bilder, ${cam.gaps} Lücken`
      : `Kamera aus: ${cam.error || '—'}`;
    $('setup-state').textContent = s.setup ? `Gesamturteil: ${s.setup.overall}` : '';
    $('overlays').replaceChildren(...(s.setup ? s.setup.overlays : []).map((name) => {
      const img = document.createElement('img');
      img.src = `/live/setup/${name}.png?${s.session_id}`;
      img.alt = name;
      return img;
    }));
    $('confirm-box').hidden = s.state !== 'setup_ready';
    $('ack-label').hidden = !(s.setup && s.setup.overall === 'WARNUNG');
  };
  const tick = async () => {
    try {
      const response = await fetch('/live/status');
      if (response.ok) render(await response.json());
    } finally {
      $('preview').src = `/live/preview.jpg?${Date.now()}`;
      setTimeout(tick, 500);
    }
  };
  $('setup').onclick = () => post('/live/setup', {cell_text: $('cell-text').value || null});
  $('confirm').onclick = () => post('/live/confirm', {confirmed_by: $('confirmed-by').value,
    format_checked: $('format-checked').checked, acknowledge_warning: $('ack').checked});
  $('run-start').onclick = () => post('/live/run/start');
  $('run-stop').onclick = () => post('/live/run/stop');
  $('camera-start').onclick = () => post('/live/camera/start');
  tick();
}
```

- [ ] **Step 7: node-Test für `statusView`** — `tests/live_client.test.mjs`:

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import {statusView} from '../src/dispread/workbench/static/live.js';

const latest = (over) => ({frame_sequence: 7, status: 'valid', raw_text: '+1.2345', unit: 'mV/V',
  reject_reasons: [], ...over});

test('valid value shows text, unit and green class', () => {
  const view = statusView({state: 'running', run: {latest: latest()}});
  assert.equal(view.headline, '+1.2345 mV/V');
  assert.equal(view.cls, 'valid');
});

test('stale never shows the old number', () => {
  const view = statusView({state: 'running', run: {latest: latest({status: 'stale', raw_text: '',
    reject_reasons: ['no_value']})}});
  assert.equal(view.headline, 'STALE');
  assert.ok(!view.headline.includes('1.2345'));
});

test('setup failure shows the error', () => {
  const view = statusView({state: 'setup_failed', error: 'Punktraster abgelehnt: keine_startlage'});
  assert.equal(view.cls, 'error');
  assert.match(view.detail, /keine_startlage/);
});
```

`tests/test_live_client.py`:

```python
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).with_name("live_client.test.mjs")


def test_live_page_status_view():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node fehlt")
    result = subprocess.run([node, "--test", str(HARNESS)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
```

Run: `./.venv/bin/pytest tests/test_live_client.py -v`
Expected: PASS (oder SKIP ohne node)

- [ ] **Step 8: In `make_app` und `serve` verdrahten** — in `src/dispread/workbench/server.py`:

```python
from dispread.camera_settings import preview_settings
from dispread.frames import open_source
from dispread.frames.uvc_source import UvcSource
from dispread.live import LIVE_DATA_DIR
from dispread.live.camera import CameraOwner
from dispread.live.service import LiveService

from .live_api import add_live_routes
```

`make_app(controller, terminals, verifier=authenticate, live=None)`; vor `return app` (nach den bestehenden `add_route`-Zeilen):

```python
    if live is not None:
        add_live_routes(app, live, csrf_of=lambda request: sessions.get(request.cookies.get(COOKIE))["csrf"])
```

In `serve()` vor `controller = Controller(...)`:

```python
    if args.simulate:
        owner = CameraOwner(lambda: open_source("synthetic://seven-seg"), max_fps=10)
    else:
        owner = CameraOwner(lambda: UvcSource(preview_settings(), apply_controls=False))
    live = LiveService(owner, Path(getattr(args, "live_data", LIVE_DATA_DIR)), simulate=args.simulate)
```

`runner = web.AppRunner(make_app(controller, terminals, live=live), access_log=None)`. Nach `controller.start()`:

```python
        try:
            owner.start()
        except Exception as error:  # noqa: BLE001 - Server laeuft weiter, Seite zeigt den Fehler
            controller.log("error", f"Kamera: {error}")
```

Im `finally` nach `await asyncio.to_thread(controller.close)`:

```python
        await asyncio.to_thread(live.close)
        await asyncio.to_thread(owner.stop)
```

In `src/dispread/workbench/cli.py` beim `serve`-Parser: `serve.add_argument("--live-data", default="var/live")`.

Die Übergabe von `owner` an den `Controller` folgt in Task 11.

- [ ] **Step 9: Alle Tests, Lint, CHANGELOG, Commit** — Punkt: „Live-Seite `/live` in `dispread serve`: Vorschau, Einrichtung mit Overlays, Bestätigung, Lauf mit Wert und Status, dauerhafter Freigabehinweis; `CameraOwner` öffnet die StreamCam ohne Regler bis zur Einrichtung."

```bash
./.venv/bin/ruff check src tests examples
./.venv/bin/pytest -q
git add src/dispread/workbench/live_api.py src/dispread/workbench/static/live.html src/dispread/workbench/static/live.js src/dispread/workbench/server.py src/dispread/workbench/cli.py src/dispread/live/service.py tests/test_live_api.py tests/live_client.test.mjs tests/test_live_client.py CHANGELOG.md
git commit -m "Messpfad live 10: /live-API, Live-Seite, Verdrahtung in serve"
```

---

### Task 11: Alte Werkbank vom Picamera2-Worker lösen

**Files:**
- Modify: `src/dispread/workbench/controller.py`, `src/dispread/workbench/server.py`, `tests/test_workbench.py`, `CHANGELOG.md`

**Interfaces:**
- Consumes: `CameraOwner.wait_newer/status` (Task 3)
- Produces: `Controller(data, camera=0, simulate=False, owner=None)`; mit `owner` bekommt der Controller Bilder gedrosselt (`FEED_INTERVAL_S = 0.2`) und lehnt `camera.set`, `camera.set_many`, `focus`, `auto.start` mit `ValueError("Kameraregler der StreamCam stehen auf der Live-Seite (/live)")` ab.

- [ ] **Step 1: Fehlschlagende Tests schreiben** — an `tests/test_workbench.py` anhängen:

```python
def test_controller_is_fed_by_camera_owner_and_refuses_camera_ops(tmp_path):
    import numpy as np

    from dispread.frames import Frame
    from dispread.records import TimeBaseKind, Timestamp

    class FakeOwner:
        def __init__(self):
            self.seq = 0

        def wait_newer(self, after, timeout):
            time.sleep(0.01)
            self.seq += 1
            ts = Timestamp(value_ns=self.seq * 33_333_333, base=TimeBaseKind.V4L2_MONOTONIC)
            image = np.zeros((480, 640, 3), np.uint8)
            return self.seq, Frame(frame_sequence=self.seq, image=image, capture_timestamp=ts, source_id="fake")

        def status(self):
            return {"running": True, "error": None, "frames": self.seq, "gaps": 0, "source": {}}

    c = Controller(tmp_path / "data", simulate=False, owner=FakeOwner())
    c.start()
    try:
        deadline = time.monotonic() + 3
        while c.snapshot()["live"] is False and time.monotonic() < deadline:
            time.sleep(0.05)
        assert c.snapshot()["live"] is True and c.snapshot()["error"] is None
        with pytest.raises(ValueError, match="/live"):
            c.command("camera.set", {"key": "ExposureTime", "value": 1000})
    finally:
        c.close()


def test_controller_without_owner_and_without_simulation_reports_missing_camera(tmp_path):
    c = Controller(tmp_path / "data", simulate=False)
    c.start()
    try:
        deadline = time.monotonic() + 2
        while not c.snapshot()["error"] and time.monotonic() < deadline:
            time.sleep(0.05)
        assert "Live-Seite" in c.snapshot()["error"]
    finally:
        c.close()
```

(Falls `time`/`pytest` in der Datei noch nicht importiert sind, oben ergänzen. Die genauen Schlüssel von `snapshot()` vor dem Schreiben in `controller.py:366` nachlesen; `live` und `error` sind dort Felder.)

- [ ] **Step 2: Tests laufen lassen, Fehlschlag prüfen**

Run: `./.venv/bin/pytest tests/test_workbench.py -v -k "owner or missing_camera"`
Expected: FAIL mit `TypeError: … unexpected keyword argument 'owner'`

- [ ] **Step 3: Controller umbauen** — in `src/dispread/workbench/controller.py`:

* `__init__` bekommt `owner=None` als letzten Parameter und speichert `self.owner = owner`.
* Konstanten: `FEED_INTERVAL_S = 0.2`; `CAMERA_AUSSER_BETRIEB_MSG` ersetzen durch
  `KEINE_KAMERA_MSG = "Die Kamera der Werkbank laeuft ueber die Live-Seite (/live); dieser Controller hat keinen Bilder-Feed bekommen."`
* Am Anfang von `command()`:

```python
        if self.owner is not None and op in ("camera.set", "camera.set_many", "focus", "auto.start"):
            raise ValueError("Kameraregler der StreamCam stehen auf der Live-Seite (/live)")
```

* `_worker` vollständig ersetzen:

```python
    def _worker(self):
        try:
            if self.owner is not None:
                self._feed_from_owner()
            elif self.simulate:
                self._simulate_frames()
            else:
                with self.lock:
                    self.error = KEINE_KAMERA_MSG
                self.log("error", KEINE_KAMERA_MSG)
                while not self.stop.is_set():
                    self.stop.wait(0.2)
        except Exception as error:
            with self.lock:
                self.error, self.jpeg = str(error), None
            self.log("error", f"Kamera gestoppt: {error}")

    def _feed_from_owner(self):
        """Bilder vom CameraOwner, gedrosselt: die 7-Segment-Vorschau ist teuer
        und darf das Live-Lesen nicht ausbremsen (Spec 2026-10-12 §5)."""
        seen = 0
        while not self.stop.is_set():
            got = self.owner.wait_newer(seen, 0.5)
            if got is None:
                status = self.owner.status()
                if not status["running"]:
                    with self.lock:
                        self.error = status["error"] or "Kamera aus"
                    self.stop.wait(0.2)
                continue
            seen, frame = got
            with self.lock:
                self.error = None
            stamp = frame.capture_timestamp
            self.publish(frame.image, {"timebase": stamp.base.value, "uncertainty_ns": stamp.uncertainty_ns})
            self.stop.wait(FEED_INTERVAL_S)

    def _simulate_frames(self):
        self.capabilities = {
            "AeEnable": [False, True, True],
            "ExposureTime": [100, 100000, 10000],
            "AnalogueGain": [1.0, 16.0, 1.0],
            "Contrast": [0.1, 4.0, 1.0],
        }
        while not self.stop.is_set():
            with self.lock:
                data, revision = copy.deepcopy(self.config), self.revision
            cam = data["camera"]
            if revision != self.applied:
                validate(data, self.capabilities)
                with self.lock:
                    self.applied = revision
                self.log("info", f"Controls r{revision} gesetzt; Ist-Belichtung separat in Metadaten")
            if self.auto_requested:
                self.auto_requested = False
                self.auto = {"state": "failed", "reason": "Auto-Setup braucht echte Kamera"}
            image = np.zeros((cam["height"], cam["width"], 3), np.uint8)
            cv2.rectangle(
                image,
                (int(cam["width"] * 0.2), int(cam["height"] * 0.3)),
                (int(cam["width"] * 0.8), int(cam["height"] * 0.6)),
                (160, 160, 160),
                -1,
            )
            cv2.putText(
                image, "012.50", (int(cam["width"] * 0.25), int(cam["height"] * 0.52)),
                cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3,
            )
            self.publish(image, {"timebase": TimeBaseKind.SYNTHETIC.value, "uncertainty_ns": None})
            self.stop.wait(1 / cam["fps"])
```

* Löschen: `_capture`, `_settle`, `_automatic`, `_guarded`, `CameraWedgedError` und alles, was danach nur noch von ihnen benutzt wurde (ruff meldet unbenutzte Importe/Konstanten; zusätzlich `grep -n "GEOMETRY_DEBOUNCE_S\|geometry_cycles\|CameraWedged\|ausser Betrieb" src/dispread/workbench/` und nur Unbenutztes entfernen).
* In `server.py`: `controller = Controller(args.data, args.camera, args.simulate, owner=owner)`.

- [ ] **Step 4: Veraltete Tests entfernen** — in `tests/test_workbench.py` die drei Tests der gelöschten Picamera2-Helfer löschen: `test_capture_request_release_on_failure`, `test_auto_cancel_restores_original_controls`, `test_control_settle_requires_real_metadata`. Danach `grep -rn "CAMERA_AUSSER_BETRIEB_MSG\|ausser Betrieb" tests/` — Tests, die die alte Meldung erwarten, auf `KEINE_KAMERA_MSG` bzw. „Live-Seite" umstellen.

- [ ] **Step 5: Tests laufen lassen**

Run: `./.venv/bin/pytest tests/test_workbench.py tests/test_workbench_client.py -v`
Expected: PASS

- [ ] **Step 6: Alle Tests, Lint, CHANGELOG, Commit** — Punkt: „Alte Werkbank: Picamera2-Worker und seine Helfer entfernt; der Controller bekommt Bilder gedrosselt vom `CameraOwner` und verweist Kameraregler auf `/live`. Der 7-Segment-Lesepfad der alten Seite bleibt vorerst (eigener Aufräumschritt)."

```bash
./.venv/bin/ruff check src tests examples
./.venv/bin/pytest -q
git add src/dispread/workbench/controller.py src/dispread/workbench/server.py tests/test_workbench.py CHANGELOG.md
git commit -m "Messpfad live 11: alte Werkbank vom Picamera2-Worker geloest"
```

---

### Task 12: Echter Lauf am Aufbau und Doku

**Files:**
- Modify: `docs/VALIDATION.md`, `docs/lab_journal.md`, `docs/status.md`, `TODO.md`, `CHANGELOG.md`, `docs/ROADMAP.md`, `docs/anleitung/10-kamera-livevorschau.md`, `CLAUDE.md` (Abschnitt „Erwartete Zustände": die Werkbank-Kamera ist nicht mehr außer Betrieb)

**Interfaces:**
- Consumes: alles Vorherige. Braucht den Nutzer am Aufbau (StreamCam an USB3, GSV-2AS an `/dev/ttyUSB0`, Kamera senkrecht auf Displaymitte).

- [ ] **Step 1: Vorbedingungen prüfen**

Run:

```bash
ls var/RECORDING_IN_PROGRESS 2>/dev/null && echo "ERNTE LAEUFT - abbrechen"
./scripts/camera-commissioning.sh
ls -l var/calibration/timing-streamcam.json
sha256sum var/dotmatrix/templates-stufe2c-2026-09-30.json
```

Expected: keine laufende Ernte; Kamera-Diagnose Exit 0; Kalibrierdatei vorhanden; sha256 `6f20dec4…f693a`.

- [ ] **Step 2: Werkbank starten und einrichten** — `./.venv/bin/dispread serve` (als `me-systeme`), im Browser `https://<host>:8080/live` öffnen. Einrichtung ohne Zellentext starten (GSV-2AS seriell). Erwartet: Schritte fokus → kamera → standbilder → vorschlag, Overlays erscheinen, Gesamturteil OK oder WARNUNG.

- [ ] **Step 3: Bestätigen und laufen lassen** — Overlays prüfen, Name eintragen, Format abhaken, ggf. WARNUNG zur Kenntnis nehmen, bestätigen. Lauf starten, mindestens 10 Minuten. Am GSV-2AS dabei 5 verschiedene Werte über `set norm` einstellen (`scripts/gsv-registers.py`), damit `TRANSITION` → `VALID` sichtbar wird. Einmal die Anzeige 2 s abdecken (erwartet `UNREADABLE`, danach wieder `VALID`). Lauf stoppen.

- [ ] **Step 4: Auswerten**

Run (Sitzungsordner aus der Seite oder `ls -t var/live | head -1`):

```bash
S=var/live/$(ls -t var/live | head -1)
python3 - "$S" <<'EOF'
import json, sys, collections
from pathlib import Path
from dispread.records import to_boottime_ns
d = Path(sys.argv[1]); session = json.loads((d / "session.json").read_text())
recs = [json.loads(l) for l in (d / "records.jsonl").read_text().splitlines()]
print("Status:", collections.Counter(r["status"] for r in recs))
print("Werte:", sorted({r["value"] for r in recs if r["status"] == "valid"}))
print("Zusammenfassung:", session["summary"])
print("BOOTTIME erstes Bild:", to_boottime_ns(recs[0]["capture_timestamp"], session))
EOF
```

Expected: jeder am Gerät eingestellte Wert erscheint als `valid`; kein `valid`-Wert, der nicht eingestellt war; `to_boottime_ns` rechnet ohne Fehler um; `frames_skipped` und `frame_gaps` stehen da.

- [ ] **Step 5: Doku nachziehen**

* `docs/VALIDATION.md`: Eintrag „2026-10-xx — Messpfad live, erster echter Lauf" mit Dauer, Status-Zählung, eingestellten vs. gelesenen Werten, übersprungenen Bildern, Leserate; ausdrücklich „kein formaler Abnahme-Lauf" und der Freigabehinweis.
* `docs/lab_journal.md`: Ablauf und Auffälligkeiten.
* `docs/status.md`: Messpfad live in Betrieb, Grenzen (nur Raumlicht, ein Gerät, eine Einheit; keine serielle Ausgabe).
* `TODO.md`: Punkt 2 als erledigt markieren; neuer nächster Schritt „serielle Ausgabe an GSVmulti (OQ-07)"; Aufräumschritt „7-Segment-Lesepfad der alten Werkbank entfernen" eintragen.
* `docs/ROADMAP.md`: Live-Messpfad unter P0/P1 eintragen.
* `docs/anleitung/10-kamera-livevorschau.md`: Abschnitt „Live-Seite `/live`" (Ablauf, Fehlermeldungen); „Fertig, wenn"-Checkliste ergänzen.
* `CLAUDE.md`: „Die Kamera der Werkbank (`dispread serve`) ist außer Betrieb …" ersetzen durch den neuen Zustand (Kamera über `/live`, alte Seite bekommt gedrosselte Bilder, Kameraregler nur auf `/live`).
* `CHANGELOG.md`: im Abschnitt „Messpfad live" die **Konsequenz** ausformulieren.

- [ ] **Step 6: Commit**

```bash
git add docs/VALIDATION.md docs/lab_journal.md docs/status.md TODO.md docs/ROADMAP.md docs/anleitung/10-kamera-livevorschau.md CLAUDE.md CHANGELOG.md
git commit -m "Messpfad live 12: erster echter Lauf, Doku"
```

---

## Offene Punkte

* Leserlaufzeit auf dem Pi 5 — Task 1 misst sie; liegt p95 über 100 ms, liest die Sitzung weniger als 10 Bilder/s (kein Codeumbau, steht im Laborjournal).
* Ob GSVmulti Aufnahmezeitstempel nutzt (Konzept §6, OQ-07) — erst für den seriellen Schritt.
* Ein früheres Profil als Startwert der Einrichtung (Spec §3, „darf") baut dieser Plan nicht: die Einrichtung läuft immer vollständig neu, was die Spec ohnehin verlangt.
* Der Zellentext des Bedieners umfasst die Zellen 0–8 (9 Zeichen, `validate_offline_cell_text`), nicht alle 16 Zellen.
* `confirm_frames = 2` ist eine Vorgabe dieses Plans (Spec §2), keine gemessene Grenze; der echte Lauf (Task 12) zeigt die Bestätigungsverzögerung in `confirmation_span_ns`.
