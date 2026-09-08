# Rezepte

Schnipsel zum Kopieren. Alle laufen ohne Hardware, außer Rezept 11.
Ablage für Wegwerfskripte: `var/` (nicht versioniert).

## 1 — Frames ansehen

```python
from dispread.frames import open_source

src = open_source("synthetic://seven-seg?digits=5&decimals=2&unit=N&count=5&glare=0.3")
src.open()
for frame in src.frames():
    print(frame.frame_sequence, frame.size, frame.timebase.value,
          frame.raw_metadata["ground_truth"]["text"])
src.close()
print(src.describe())
```

## 2 — Synthetische Frames als PNG-Ordner exportieren

Damit hast du Material für `folder://` ([Kapitel 3](03-erste-bildquelle-folder.md)).

```python
import cv2
from pathlib import Path
from dispread.frames import open_source

ziel = Path("var/beispielbilder"); ziel.mkdir(parents=True, exist_ok=True)
src = open_source("synthetic://seven-seg?digits=5&decimals=2&unit=N&count=12&noise=0.1")
src.open()
for frame in src.frames():
    cv2.imwrite(str(ziel / f"frame{frame.frame_sequence}.png"), frame.image)
src.close()
```

Bewusst `frame1.png … frame12.png` — damit fällt eine alphabetische Sortierung
auf (siehe Kapitel 3).

## 3 — ROI-Vorschau zeichnen

Der Weg, eine ROI auf einem Pi ohne Bildschirm zu bestätigen: zeichnen,
ansehen, Zahlen anpassen, wiederholen.

```python
import cv2
import numpy as np
from pathlib import Path
from dispread.frames import open_source
from dispread.detect.manual_roi import quad_from_box
from dispread.layout import DisplayLayout

src = open_source("synthetic://seven-seg?count=1")
src.open(); frame = next(iter(src.frames())); src.close()

quad = quad_from_box(*frame.raw_metadata["digit_area"])   # oder deine Zahlen
bild = frame.image.copy()
cv2.polylines(bild, [np.array(quad, np.int32)], True, (0, 255, 0), 2)

# Ziffernraster mitzeichnen - so sieht man, ob die Zellen sitzen.
x, y, w, h = frame.raw_metadata["digit_area"]
layout = DisplayLayout(digits=5, decimals=2, unit="N")
for zx, zy, zw, zh in layout.cell_boxes(w, h):
    cv2.rectangle(bild, (x + zx, y + zy), (x + zx + zw, y + zy + zh), (0, 180, 255), 1)

Path("var/diagnostics").mkdir(parents=True, exist_ok=True)
cv2.imwrite("var/diagnostics/roi_vorschau.png", bild)
```

## 4 — Einen Frame komplett durch die Kette

Steht vollständig in [Kapitel 1](01-kette-verstehen.md), Abschnitt „Ein Frame
zu Fuß". Das ist das Rezept, das man am häufigsten braucht.

## 5 — `values.jsonl` auswerten

```python
import json
from collections import Counter
from pathlib import Path
from dispread.records import ValueRecord, ValueStatus

pfad = Path("var/examples/16_end_to_end/values.jsonl")
records = [ValueRecord.from_dict(json.loads(z)) for z in pfad.read_text("utf-8").splitlines() if z]

print("Datensaetze:", len(records))
print("Status:     ", Counter(r.status.value for r in records))
print("Gruende:    ", Counter(g for r in records for g in r.reject_reasons))

# Invariante nachpruefen: kein Zahlenwert bei STALE/UNREADABLE
verletzt = [r for r in records
            if r.status in (ValueStatus.STALE, ValueStatus.UNREADABLE) and r.value is not None]
print("Invariante verletzt:", len(verletzt))

# Traegt der Lauf ueberhaupt Zeitaussagen?
print("Zeitbasis:", {r.capture_timestamp.base.value for r in records},
      "| verwertbar:", all(r.capture_timestamp.base.carries_time_information for r in records))
```

## 6 — Serielle Gegenstelle ohne Hardware

`socat` ist nicht installiert ([OQ-15](../open-questions.md)) — die stdlib
genügt:

```python
import os
from dispread.records import InvalidValuePolicy
from dispread.sink.protocol.ascii_csv import AsciiCsvFormatter
from dispread.sink.serial_out import SerialSink

master_fd, slave_fd = os.openpty()
sink = SerialSink(os.ttyname(slave_fd), AsciiCsvFormatter(invalid_policy=InvalidValuePolicy.STATUS_FLAG))
sink.open()
# ... sink.emit(record) ...
sink.close()

os.set_blocking(master_fd, False)
try:
    leitung = os.read(master_fd, 1 << 20)
except BlockingIOError:
    leitung = b""
print(leitung.decode("ascii", "replace"))
os.close(master_fd); os.close(slave_fd)
```

Das Format ist **provisorisch** und nicht das GSVmulti-Telegramm
([OQ-07](../open-questions.md)).

## 7 — Latenzen je Stufe auswerten

```python
durations = [r.trace.stage_durations_us() for r in records if r.trace]
for stufe in ("locate", "rectify", "read", "gate", "build", "total"):
    werte = sorted(d[stufe] for d in durations if stufe in d)
    if werte:
        print(f"{stufe:8s} p50={werte[len(werte)//2]:9.1f}  p95={werte[int(len(werte)*0.95)]:9.1f}  max={werte[-1]:9.1f}")
```

**Nur** deuten, wenn `capture_timestamp.base.carries_time_information` wahr
ist. Bei `synthetic://` und `folder://` sind das reine Rechenzeiten der
Software.

## 8 — Segmentmessungen eines Ausschnitts sichtbar machen

Das beste Werkzeug, wenn der Leser „Unsinn" liefert: nachsehen, was er
gemessen hat.

```python
from dispread.layout import SEGMENT_SAMPLE_POINTS, DisplayLayout
from dispread.ocr.sevenseg import _sample, _to_gray, segment_threshold

gray = _to_gray(crop.image)
h, w = gray.shape[:2]
layout = DisplayLayout(digits=5, decimals=2, unit="N")
zellen = [{s: _sample(gray, box, rel) for s, rel in SEGMENT_SAMPLE_POINTS.items()}
          for box in layout.cell_boxes(w, h)]
schwelle, kontrast = segment_threshold([v for z in zellen for v in z.values()])
print(f"Schwelle {schwelle:.3f}  Kontrast {kontrast:.3f}")
for i, z in enumerate(zellen):
    print(i, {s: round(v, 2) for s, v in sorted(z.items())})
```

Unterstrich-Namen sind projektinterne Helfer — für Diagnose in `var/` in
Ordnung, in `src/` nicht.

## 9 — Vorlage für ein neues Modul

```python
"""<Ein Satz: was das Modul tut.>

Warum so und nicht anders: <Entscheidung>. Bezug: Konzept.md §<n>
bzw. OQ-<nn>.

Grenzen: <was es ausdruecklich nicht kann>.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["MeinErgebnis", "MeineKomponente"]


@dataclass(frozen=True, slots=True)
class MeinErgebnis:
    """Ergebnisse sind Beweismittel - deshalb frozen."""

    wert: float | None
    gruende: tuple[str, ...] = ()


class MeineKomponente:
    def __init__(self, *, schwelle: float = 0.5) -> None:
        self.schwelle = schwelle

    def describe(self) -> dict[str, Any]:
        """Selbstbeschreibung fuers Runartefakt - inkl. eigener Grenzen."""
        return {"typ": type(self).__name__, "schwelle": self.schwelle}
```

## 10 — Vorlage für einen Test

```python
"""<Was hier geprueft wird - und warum es wichtig ist.>"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_lehnt_unlesbares_ab() -> None:
    """Die Richtung, die zaehlt: ablehnen statt raten."""
    ...


def test_schreibt_nur_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISPREAD_VAR_LIB", str(tmp_path))
    ...


@pytest.mark.hardware      # nur mit --mode=real
def test_mit_kamera() -> None:
    ...
```

## 11 — Ein Einzelbild von der Kamera (braucht Hardware)

```bash
./scripts/camera-commissioning.sh          # erst Diagnose, Exit 0 erwarten
rpicam-still -o var/diagnostics/probe.jpg --immediate
```

In Python, mit Metadaten aus derselben Aufnahme:

```python
from picamera2 import Picamera2

picam2 = Picamera2()
picam2.configure(picam2.create_still_configuration(main={"size": (2028, 1520)}))
picam2.start()
request = picam2.capture_request()
try:
    bild = request.make_array("main")
    md = request.get_metadata()
finally:
    request.release()          # PFLICHT
picam2.stop()
print(md["SensorTimestamp"], md.get("ExposureTime"), md.get("AnalogueGain"))
```

Ohne Kamera: `global_camera_info()` ist `[]` — erwarteter Zustand, kein Bug.
`camera_auto_detect` greift nur beim Booten.

## 12 — Wohin darf geschrieben werden

`src/dispread/paths.py` ist die einzige Quelle der Wahrheit, und jeder Pfad ist
per Umgebungsvariable überschreibbar:

| Konstante | Default | Variable |
| --- | --- | --- |
| `ROOT` | Repowurzel | `DISPREAD_ROOT` |
| `CONFIG` / `PROFILES` | `config/` · `config/profiles/` | `DISPREAD_CONFIG` / `DISPREAD_PROFILES` |
| `ETC` | `/etc/dispread` | `DISPREAD_ETC` |
| `VAR_LIB` | `/var/lib/dispread` | `DISPREAD_VAR_LIB` |
| `RUN` | `/run/dispread` | `DISPREAD_RUN` |
| `DATASETS` | `datasets/` | `DISPREAD_DATASETS` |
| `VAR`, `EXAMPLES_OUT`, `DIAGNOSTICS` | `var/`, `var/examples/`, `var/diagnostics/` | `DISPREAD_VAR` |

Tests schreiben **nur** nach `tmp_path` oder in umgebogene Pfade.

## 13 — Kurzbefehle

```bash
./.venv/bin/pytest -q -k roi              # nach Namen filtern
./.venv/bin/pytest -x -q                  # beim ersten Fehler stoppen
./.venv/bin/pytest --lf -q                # nur letzte Fehlschlaege
./.venv/bin/pytest -q --mode=real         # inkl. Hardware-Tests
./.venv/bin/ruff check --fix src tests examples
./.venv/bin/python -m dispread.cli --help          # ab Kapitel 5
git diff --stat && git status --short
```

## 14 — Vor dem Commit

```bash
./.venv/bin/pytest -q && ./.venv/bin/ruff check src tests examples
```

Dann: `CHANGELOG.md` (Pflicht bei `src/`-Änderungen), ggf. neuer `OQ-nn`,
ROADMAP-Häkchen, und vor Sessionende `docs/status.md` neu schreiben.
