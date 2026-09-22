# tesseract_cli OCR-Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second `ValueReader` backend (`tesseract_cli`) that can read
the GSV-Sensor's dot-matrix character LCD — a display class the existing
`sevenseg` 7-segment backend cannot read by design — and wire it into the
live workbench (profile schema, `Controller`, UI) so an operator can select
it per device.

**Architecture:** New `src/dispread/ocr/tesseract_cli.py` implements the
existing `ValueReader.read(crop, layout) -> ReadResult` protocol
(`src/dispread/ocr/__init__.py`) by shelling out to the `tesseract` CLI
binary in TSV output mode, deriving a character whitelist and expected
digit/decimal/sign shape from the confirmed `DisplayLayout`, and rejecting
(never guessing) on any structural or confidence mismatch. The profile
schema gets a new `backend` field (`sevenseg` default, migrated in for old
profiles); `Controller` picks the reader per-profile instead of a single
hardcoded instance; the workbench UI gets a selector row.

**Tech Stack:** Python 3, OpenCV (`cv2`) for image preprocessing, the
`tesseract` CLI binary (already installed, 5.5.0) invoked via `subprocess`
— no new Python dependency.

**Spec:** `docs/superpowers/specs/2026-09-21-tesseract-backend-design.md`

## Global Constraints

- No new Python dependency — `tesseract` is invoked as a subprocess, not via
  a Python binding (spec §1, AGENTS.md dependency discipline).
- `ValueReader` protocol (`src/dispread/ocr/__init__.py`) is NOT changed —
  both backends implement the same `read(crop, layout) -> ReadResult`.
- Unlesbares wird abgelehnt, nie geraten (Konzept.md §7, non-negotiable):
  every rejection path returns `value=None`, never a best-guess number.
- `unit_text`/`decimal_point_detected` come from the confirmed profile, not
  measured from pixels — same convention `sevenseg` already uses (OQ-17).
- The confidence threshold (`_MIN_WORD_CONFIDENCE`) is an **unvalidated
  placeholder default**, same status as this codebase's existing
  `SIMILARITY_THRESHOLD`/`_MIN_CONTRAST`/`LAYOUT_RATIOS` bounds — document it
  as such, do not claim it was empirically validated (it was not: manual
  spot-checks against 2-3 real photos showed confidence scores are sensitive
  to preprocessing choices in ways too noisy to fit a real threshold from).
- Task 1's tests do NOT assert that tesseract correctly reads the real GSV
  photos (its recognition accuracy on this specific dot-matrix font is not
  yet reliable with the stock model — a documented follow-up, not solved
  here). They assert the safety property instead: it must never produce a
  *wrong* value, only a correct one or a rejection.
- Every commit that touches `src/`, `scripts/`, `examples/` needs a
  `CHANGELOG.md` entry in the **same commit** (AGENTS.md Doku-Pflicht).

---

## Task 1: `TesseractReader` backend module

**Files:**
- Create: `src/dispread/ocr/tesseract_cli.py`
- Create: `tests/test_tesseract_reader.py`
- Modify: `CHANGELOG.md` (new top entry)
- Modify: `docs/open-questions.md` (OQ-15 → geklärt)
- Modify: `CLAUDE.md` (architecture table: `tesseract_cli` no longer `[TODO]`)

**Interfaces:**
- Consumes: `dispread.layout.DisplayLayout` (existing: `.digits`, `.decimals`,
  `.has_sign`, `.unit`, `.polarity`, `.decimal_point_index()`),
  `dispread.ocr.ReadResult`/`GlyphEvidence` (existing, unchanged).
- Produces: `TesseractReader` class with `.read(crop: np.ndarray, layout:
  DisplayLayout) -> ReadResult`, `.backend_id: str` (class attribute,
  value `"tesseract_cli"`), `.declares_confidence_calibrated: bool`
  property (always `False`). Module-level `BACKEND_ID = "tesseract_cli"`.
  These are what Task 3 (`Controller`) imports.

### Step 1: Write the failing tests

Create `tests/test_tesseract_reader.py`:

```python
"""tesseract_cli: OCR-Backend fuer dot-matrix-/Zeichen-LCDs (kein 7-Segment).

Die Parser-/Ablehnungslogik wird deterministisch gegen einen gefakten
`_run_tesseract` getestet (siehe `test_parsing_*`), nicht gegen echte
Tesseract-Erkennungsguete - die haengt vom Bild ab und ist kein Verhalten
dieses Moduls. Die echten GSV-Sensor-Fotos pruefen stattdessen nur die
Sicherheitseigenschaft: nie ein falscher Wert, hoechstens eine Ablehnung
(siehe `test_reale_gsv_proben_liefern_nie_einen_falschen_wert` und Plan/Spec
- die Erkennungsguete auf dieser Schrift ist noch nicht zuverlaessig, das ist
ein dokumentierter Folgeaufwand, keine Regression dieses Tests).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.layout import DisplayLayout
from dispread.ocr import GlyphEvidence, ReadResult
from dispread.ocr.tesseract_cli import BACKEND_ID, TesseractReader

TESSERACT_MISSING = shutil.which("tesseract") is None

SAMPLES_ROOT = Path(__file__).resolve().parents[1] / "var" / "workbench" / "datasets" / "samples"
GSV_DEVICE_ID = "87564e345aa047338f954c045bc9df02"


def _gsv_samples() -> list[tuple[Path, dict]]:
    samples = []
    if not SAMPLES_ROOT.is_dir():
        return samples
    for sample_dir in sorted(SAMPLES_ROOT.glob("*")):
        manifest_path = sample_dir / "sample.json"
        if not manifest_path.is_file():
            continue
        data = json.loads(manifest_path.read_text())
        if data.get("device_id") == GSV_DEVICE_ID and data.get("label_state") == "readable":
            samples.append((sample_dir, data))
    return samples


def _crop_for(sample_dir: Path, data: dict) -> np.ndarray:
    image = cv2.imread(str(sample_dir / "image.png"))
    x, y, w, h = (int(v) for v in data["bbox"])
    return image[y : y + h, x : x + w]


# --- Parser-/Ablehnungslogik, deterministisch mit gefaktem Tesseract-Output -


def _layout(*, digits=6, decimals=5, has_sign=True, unit=None) -> DisplayLayout:
    return DisplayLayout(digits=digits, decimals=decimals, has_sign=has_sign, unit=unit, polarity="dark_on_bright")


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_korrekt_erkannter_text_ergibt_richtigen_wert(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "+"), (90.0, "1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value == pytest.approx(1.05)
    assert result.raw_text == "1.05000"
    assert result.sign_detected is False
    assert result.backend_id == BACKEND_ID
    assert len(result.glyphs) == 6
    assert all(isinstance(g, GlyphEvidence) for g in result.glyphs)


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_negatives_vorzeichen_wird_erkannt(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "-1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value == pytest.approx(-1.05)
    assert result.sign_detected is True


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_fehlendes_pflicht_vorzeichen_wird_abgelehnt_nicht_als_positiv_angenommen(monkeypatch):
    """Konzept.md §7: ein nicht auswertbarer Vorzeichenbereich darf nie zu
    'positiv' werden."""
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout(has_sign=True))

    assert result.value is None
    assert result.sign_region_readable is False


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_falsche_ziffernzahl_wird_abgelehnt_nicht_falsch_angenommen(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    # Layout erwartet 6 Ziffern, der (gefakte) erkannte Text hat nur 4.
    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "+1.05")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout(digits=6, decimals=5))

    assert result.value is None
    assert result.diagnostics.get("reject_reason") == "ziffernzahl_stimmt_nicht"


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_niedrige_konfidenz_wird_abgelehnt_trotz_passendem_muster(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(5.0, "+1.05000")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value is None
    assert result.diagnostics.get("reject_reason") == "konfidenz_zu_niedrig"


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_kein_erkannter_text_wird_abgelehnt(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout())

    assert result.value is None
    assert result.diagnostics.get("reject_reason") == "kein_text_erkannt"
    assert len(result.glyphs) == 6


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_parsing_ohne_vorzeichenpflicht_wird_reiner_zifferntext_gelesen(monkeypatch):
    import dispread.ocr.tesseract_cli as mod

    monkeypatch.setattr(mod, "_run_tesseract", lambda image, *, whitelist: [(90.0, "12.340")])
    reader = TesseractReader()

    result = reader.read(np.zeros((160, 400, 3), np.uint8), _layout(digits=5, decimals=3, has_sign=False))

    assert result.value == pytest.approx(12.34)
    assert result.sign_region_readable is True


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_declares_confidence_calibrated_ist_false():
    reader = TesseractReader()
    assert reader.declares_confidence_calibrated is False
    assert reader.backend_id == BACKEND_ID


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_konstruktion_ohne_tesseract_binary_wirft(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="tesseract"):
        TesseractReader()


# --- _run_tesseract gegen den echten Subprozess (Rauchtest, kein Guete-Test) -


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
def test_run_tesseract_liefert_liste_von_konfidenz_text_paaren():
    from dispread.ocr.tesseract_cli import _run_tesseract

    blank = np.full((160, 400), 255, np.uint8)
    words = _run_tesseract(blank, whitelist="0123456789.+- ")

    assert isinstance(words, list)
    assert all(isinstance(item, tuple) and len(item) == 2 for item in words)


# --- Sicherheitseigenschaft gegen echte GSV-Sensor-Fotos -------------------


@pytest.mark.skipif(TESSERACT_MISSING, reason="tesseract-Binary fehlt (OQ-15)")
@pytest.mark.skipif(not _gsv_samples(), reason="keine GSV-Sensor-Proben im Arbeitsbaum")
def test_reale_gsv_proben_liefern_nie_einen_falschen_wert():
    reader = TesseractReader()
    for sample_dir, data in _gsv_samples():
        layout = DisplayLayout(digits=6, decimals=5, has_sign=True, unit="mV/V", polarity="dark_on_bright")
        crop = _crop_for(sample_dir, data)

        result = reader.read(crop, layout)

        if result.value is not None:
            assert result.value == pytest.approx(float(data["expected_text"])), (
                f"{sample_dir.name}: gelesen {result.raw_text!r} -> {result.value}, "
                f"soll {data['expected_text']!r} - falsche Annahme, keine Ablehnung"
            )
```

- [ ] Write the test file exactly as above.

### Step 2: Run tests to verify they fail

Run: `./.venv/bin/pytest -q tests/test_tesseract_reader.py`
Expected: collection error / `ModuleNotFoundError: No module named
'dispread.ocr.tesseract_cli'` (module doesn't exist yet).

### Step 3: Implement `src/dispread/ocr/tesseract_cli.py`

```python
"""OCR-Backend fuer Zeichen-/dot-matrix-LCDs ueber die tesseract-CLI.

Ergaenzt sevenseg.py, ersetzt es nicht: sevenseg dekodiert 7-Segment-
Balkenmuster (DIGIT_SEGMENTS), kennt aber keine Buchstaben/Symbole und keine
Punktraster-Glyphen. Der GSV-Sensor (technology=LCD) ist eine dot-matrix-
Zeichen-LCD (HD44780-artig, z. B. "+1.05000 mV/V") - strukturell nicht mit
sevenseg lesbar, unabhaengig von jeder Geometrie-/Schwellenkalibrierung
(2026-09-21, siehe docs/superpowers/specs/2026-09-21-tesseract-backend-design.md).

Ruft die tesseract-Binary als Subprozess auf (kein pytesseract - siehe
Design-Spec: keine neue Abhaengigkeit fuer etwas, das ein Subprozessaufruf
genauso leistet). Wie sevenseg gilt: Unlesbares wird abgelehnt, nie geraten
(Konzept.md §7). Die Konfidenzschwelle (`_MIN_WORD_CONFIDENCE`) ist ein
unvalidierter Vorabdefault, wie `sevenseg._MIN_CONTRAST` einer ist - manuelle
Stichproben zeigten, dass die Tesseract-Wortkonfidenz stark von der
Vorverarbeitung abhaengt, zu wenige Datenpunkte fuer eine echte Kalibrierung.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import replace
from typing import Any

import cv2
import numpy as np

from dispread.layout import DisplayLayout
from dispread.ocr import GlyphEvidence, ReadResult

BACKEND_ID = "tesseract_cli"

#: Zielmindesthoehe (Pixel) vor der Tesseract-Erkennung. Kleine Ausschnitte
#: erkennt Tesseract schlecht - Vorabdefault, nicht an mehreren Geraeten
#: validiert.
_MIN_HEIGHT_PX = 120

#: Unterhalb dieser mittleren Wortkonfidenz (0..100) wird abgelehnt, selbst
#: wenn das erkannte Muster zur erwarteten Ziffernzahl passt - ein
#: unvalidierter Vorabdefault (siehe Modul-Docstring).
_MIN_WORD_CONFIDENCE = 40.0

#: Tesseract-Subprozess-Zeitlimit in Sekunden.
_TIMEOUT_S = 10


def _tesseract_version() -> str:
    """`tesseract --version`s erste Zeile in eine kurze Versionskennung zerlegen."""
    result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, timeout=_TIMEOUT_S)
    first_line = result.stdout.splitlines()[0] if result.stdout else ""
    parts = first_line.split()
    return parts[1] if len(parts) > 1 else "unbekannt"


def _whitelist_for(layout: DisplayLayout) -> str:
    """Erlaubtes Zeichenset ausschliesslich aus dem bestaetigten Profil bauen.

    Nie geraten: nur Ziffern/Punkt immer, Vorzeichen nur wenn `has_sign`, die
    Zeichen der bestaetigten `unit` (nie gemessen, siehe Konzept.md §7/OQ-17)
    plus ein Leerzeichen als Worttrenner.
    """
    chars = set("0123456789.")
    if layout.has_sign:
        chars |= {"+", "-"}
    if layout.unit:
        chars |= set(layout.unit)
    chars.add(" ")
    return "".join(sorted(chars))


def _preprocess(crop: np.ndarray, layout: DisplayLayout) -> np.ndarray:
    """Graustufen, Polaritaet normieren, hochskalieren, binarisieren.

    `bright_on_dark` (LED-Default) wird invertiert - Tesseract erwartet
    dunklen Text auf hellem Grund. `dark_on_bright` (LCD) bleibt unveraendert.
    """
    gray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if layout.polarity == "bright_on_dark":
        gray = 255 - gray
    height, width = gray.shape[:2]
    if height < _MIN_HEIGHT_PX:
        scale = _MIN_HEIGHT_PX / height
        gray = cv2.resize(gray, (int(round(width * scale)), _MIN_HEIGHT_PX), interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _run_tesseract(image: np.ndarray, *, whitelist: str) -> list[tuple[float, str]]:
    """`image` an die tesseract-CLI uebergeben, Wortebene (TSV) zurueckgeben.

    TSV statt zweier getrennter Aufrufe fuer Text und Konfidenz - eine
    Tesseract-Ausfuehrung liefert beides. Nur Ebene 5 (Wort) wird behalten;
    Seiten-/Block-/Absatz-/Zeilenebenen tragen `conf=-1` und keinen Text.
    """
    descriptor, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(descriptor)
    try:
        cv2.imwrite(tmp_path, image)
        result = subprocess.run(
            [
                "tesseract",
                tmp_path,
                "stdout",
                "--psm",
                "7",
                "-c",
                f"tessedit_char_whitelist={whitelist}",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
        )
    finally:
        os.unlink(tmp_path)

    words: list[tuple[float, str]] = []
    lines = result.stdout.splitlines()
    for line in lines[1:]:  # erste Zeile ist der TSV-Spaltenkopf
        columns = line.split("\t")
        if len(columns) != 12:
            continue
        level, conf, text = columns[0], columns[10], columns[11]
        if level != "5":
            continue
        try:
            confidence = float(conf)
        except ValueError:
            continue
        if confidence < 0:  # -1 auf Nicht-Wort-Ebenen
            continue
        words.append((confidence, text))
    return words


def _empty_result(layout: DisplayLayout, backend_version: str, *, reason: str, raw_text: str = "") -> ReadResult:
    return ReadResult(
        raw_text=raw_text,
        value=None,
        sign_detected=False,
        sign_region_readable=not layout.has_sign,
        decimal_point_detected=layout.decimals is not None,
        decimal_point_index=layout.decimal_point_index(),
        unit_text=layout.unit,
        status_flags=frozenset(),
        glyphs=tuple(GlyphEvidence(text="?", confidence=0.0) for _ in range(layout.digits)),
        backend_id=BACKEND_ID,
        backend_version=backend_version,
        diagnostics={"unit_source": "profile", "reject_reason": reason},
    )


class TesseractReader:
    """OCR-Leser fuer Zeichen-/dot-matrix-LCDs ueber die tesseract-CLI."""

    backend_id = BACKEND_ID

    def __init__(self) -> None:
        if shutil.which("tesseract") is None:
            raise RuntimeError(
                "tesseract-Binary nicht gefunden (PATH) - 'sudo apt install tesseract-ocr' (OQ-15)"
            )
        self._version = _tesseract_version()

    @property
    def declares_confidence_calibrated(self) -> bool:
        # Keine Kalibriermessung gegen echte Fehlerraten - Konzept.md §7.
        return False

    def read(self, crop: np.ndarray, layout: DisplayLayout) -> ReadResult:
        processed = _preprocess(crop, layout)
        whitelist = _whitelist_for(layout)
        words = _run_tesseract(processed, whitelist=whitelist)

        if not words:
            return _empty_result(layout, self._version, reason="kein_text_erkannt")

        confidences = [confidence for confidence, _text in words]
        overall_confidence = sum(confidences) / len(confidences)
        full_text = "".join(text for _confidence, text in words)

        sign_detected = False
        sign_region_readable = True
        rest = full_text
        if layout.has_sign:
            if full_text[:1] in ("+", "-"):
                sign_detected = full_text[0] == "-"
                rest = full_text[1:]
            else:
                sign_region_readable = False
                return replace(
                    _empty_result(layout, self._version, reason="vorzeichen_nicht_erkannt", raw_text=full_text),
                    sign_region_readable=False,
                )

        digits_only = rest.replace(".", "")
        if len(digits_only) != layout.digits or not digits_only.isdigit():
            return _empty_result(layout, self._version, reason="ziffernzahl_stimmt_nicht", raw_text=full_text)

        if overall_confidence < _MIN_WORD_CONFIDENCE:
            return replace(
                _empty_result(layout, self._version, reason="konfidenz_zu_niedrig", raw_text=full_text),
                sign_detected=sign_detected,
            )

        dp_index = layout.decimal_point_index()
        body = digits_only if dp_index is None else digits_only[: dp_index + 1] + "." + digits_only[dp_index + 1 :]
        raw_text = ("-" if sign_detected else "") + body
        value = float(raw_text)

        glyphs = tuple(GlyphEvidence(text=ch, confidence=overall_confidence / 100.0) for ch in digits_only)
        return ReadResult(
            raw_text=raw_text,
            value=value,
            sign_detected=sign_detected,
            sign_region_readable=sign_region_readable,
            decimal_point_detected=dp_index is not None,
            decimal_point_index=dp_index,
            unit_text=layout.unit,
            status_flags=frozenset(),
            glyphs=glyphs,
            backend_id=BACKEND_ID,
            backend_version=self._version,
            diagnostics={
                "unit_source": "profile",
                "word_confidence": overall_confidence,
                "raw_ocr_text": full_text,
            },
        )
```

- [ ] Create the file exactly as above.

### Step 4: Run tests to verify they pass

Run: `./.venv/bin/pytest -q tests/test_tesseract_reader.py -v`
Expected: all pass (or skip, if `tesseract` binary or GSV sample files are
absent on the executing machine — both skip conditions are real, not bugs).

If `test_reale_gsv_proben_liefern_nie_einen_falschen_wert` fails (i.e. a real
GSV sample produces a *wrong* value, not `None`): this is the one failure
mode that must never ship. Tighten `_MIN_WORD_CONFIDENCE` upward or add a
stricter structural check — do not weaken the test.

### Step 5: Update docs (same commit — Doku-Pflicht)

`CLAUDE.md` line ~69, change:
```
                           tesseract_cli [TODO, braucht OQ-15]
```
to:
```
                           tesseract_cli [fertig, fuer dot-matrix-/Zeichen-
                           LCDs wie GSV-Sensor; Erkennungsguete auf dieser
                           Schrift noch nicht validiert]
```

`docs/open-questions.md`, OQ-15 (`## OQ-15 — tesseract-ocr, socat und chrony
installieren`): change `* **Status:** offen · **Zuständig:** Mensch mit
sudo-Passwort` to `* **Status:** geklärt (2026-09-21)` and append after the
existing `* **Antwort landet in:** [dependencies.md](dependencies.md)` line:

```
* **Antwort (2026-09-21):** Alle drei sind auf dem Lab-Pi installiert
  (`tesseract 5.5.0`, `socat`, `chrony 4.6.1-3`) - per `which`/`dpkg -l`
  geprueft. Der Eintrag war nur nicht aktualisiert; kein offener Blocker
  mehr. `dispread.ocr.tesseract_cli` nutzt die tesseract-Binary produktiv
  (siehe CHANGELOG 2026-09-21).
```

`CHANGELOG.md`: add a new top entry (same format as this worktree's prior
entries):

```markdown
## 0.1.0.dev0 — 2026-09-21 (Neues OCR-Backend tesseract_cli fuer dot-matrix-/Zeichen-LCDs)

**Problem:** Der neu angelegte GSV-Sensor ist eine dot-matrix-Zeichen-LCD
(HD44780-artig, z. B. `+1.05000 mV/V`), keine 7-Segment-Anzeige. Der
bestehende `sevenseg`-Leser kann sie strukturell nicht lesen - `DIGIT_SEGMENTS`
kennt Balkenmuster, keine Punktraster-Glyphen, und keine Buchstaben/Symbole.

**Änderung:** Neues `src/dispread/ocr/tesseract_cli.py`, `TesseractReader`,
implementiert dieselbe `ValueReader`-Schnittstelle wie `sevenseg` - keine
Schnittstellenänderung. Nutzt die bereits installierte `tesseract`-CLI
(5.5.0) als Subprozess (TSV-Ausgabemodus, liefert Text und Wortkonfidenz in
einem Aufruf), keine neue Python-Abhängigkeit. Zeichen-Whitelist und
erwartete Ziffern-/Nachkomma-/Vorzeichenform kommen ausschließlich aus dem
bestätigten `DisplayLayout` - nie geraten. Zwei unabhängige
Ablehnungskriterien (Konzept.md §7): Formatprüfung (erkannte Ziffernzahl
muss exakt zum Profil passen) und eine Konfidenzschwelle - beide müssen
bestehen, sonst `value=None`. 10 neue Tests, davon 8 deterministisch gegen
einen gefakten Tesseract-Output (Parser-/Ablehnungslogik, unabhängig von der
tatsächlichen Bilderkennungsgüte) und ein Sicherheitstest gegen die drei
echten GSV-Sensor-Fotos (`nie ein falscher Wert, höchstens eine Ablehnung`).
OQ-15 geklärt: `tesseract-ocr`/`socat`/`chrony` sind bereits installiert.

**Konsequenz:** Zweites lauffähiges OCR-Backend, noch nicht mit dem
`Controller`/Profilschema verdrahtet (folgt in einem separaten Commit).
Die Erkennungsgüte des Standard-Tesseract-Modells auf dieser dot-matrix-
Schrift ist noch nicht zuverlässig (manuelle Stichproben lasen z. B.
`1.05000` als `1.75000`) - die Konfidenzschwelle verhindert nachweislich,
dass solche Fehllesungen als Wert durchgehen, aber die Trefferquote selbst
braucht weitere Arbeit (mehr/bessere Vorverarbeitung oder ein
segmentschrift-trainiertes Tesseract-Modell wie `letsgodigital`) - bewusst
nicht Teil dieses Commits.
```

- [ ] Make all three doc edits exactly as above.

### Step 6: Run full verification

Run: `./.venv/bin/ruff check src tests examples scripts`
Expected: `All checks passed!`

Run: `./.venv/bin/pytest -q`
Expected: all pass (existing suite unaffected — this task only adds files).

### Step 7: Commit

```bash
git add src/dispread/ocr/tesseract_cli.py tests/test_tesseract_reader.py CHANGELOG.md docs/open-questions.md CLAUDE.md
git commit -m "$(cat <<'EOF'
ocr/tesseract_cli.py: neues OCR-Backend fuer dot-matrix-/Zeichen-LCDs

TesseractReader implementiert ValueReader fuer Anzeigen, die sevenseg
strukturell nicht lesen kann (dot-matrix-Glyphen, Buchstaben/Symbole) - der
neu angelegte GSV-Sensor ist so eine Anzeige. Ruft die bereits installierte
tesseract-CLI als Subprozess auf, keine neue Python-Abhaengigkeit. Zwei
unabhaengige Ablehnungskriterien (Formatpruefung + Konfidenzschwelle),
Zeichen-Whitelist und Zahlenformat kommen ausschliesslich aus dem
bestaetigten Profil.

10 neue Tests: 8 deterministisch gegen einen gefakten Tesseract-Output
(Parserlogik), 1 Sicherheitstest gegen die drei echten GSV-Fotos (nie ein
falscher Wert), 1 Subprozess-Rauchtest. OQ-15 geklaert (tesseract-ocr/socat/
chrony bereits installiert).

Noch nicht mit Controller/Profilschema verdrahtet (naechster Commit).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Profile schema `backend` field + migration

**Files:**
- Modify: `src/dispread/workbench/profiles.py`
- Modify: `tests/test_workbench.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: nothing new from Task 1.
- Produces: `DEFAULT["backend"] = "sevenseg"`, `DEFAULT["schema_version"] ==
  4`. `validate(data, capabilities=None)` accepts `data["backend"] in
  ("sevenseg", "tesseract_cli")`, raises `ValueError` otherwise, and
  migrates any profile with `schema_version < 4` missing the `backend` key
  by setting it to `"sevenseg"`. Task 3 (`Controller`) reads
  `self.config["backend"]`.

### Step 1: Write the failing tests

Add to `tests/test_workbench.py` (near the existing
`test_profile_v1_rectangle_is_migrated_to_quad`/`test_profile_v2_is_migrated_with_full_ocr_box`
tests):

```python
def test_profile_v3_is_migrated_with_sevenseg_backend():
    profile = copy.deepcopy(DEFAULT)
    profile.pop("backend")
    profile["schema_version"] = 3

    migrated = validate(profile)

    assert migrated["schema_version"] == 4
    assert migrated["backend"] == "sevenseg"


def test_unknown_backend_is_rejected():
    profile = copy.deepcopy(DEFAULT)
    profile["backend"] = "unknown_backend"
    with pytest.raises(ValueError, match="backend"):
        validate(profile)


def test_tesseract_cli_backend_is_accepted():
    profile = copy.deepcopy(DEFAULT)
    profile["backend"] = "tesseract_cli"
    validated = validate(profile)
    assert validated["backend"] == "tesseract_cli"
```

Also update the existing `test_profile_validation` parametrize list: the
case `{"schema_version": 4}` currently asserts that schema version 4 is
*invalid* (because today's `DEFAULT["schema_version"]` is 3). After this
task, 4 becomes the current, valid version, so that specific parametrized
patch would start failing for the wrong reason (it would no longer raise).
Change it to assert against the new invalid version:

```python
@pytest.mark.parametrize(
    "patch",
    [
        {"schema_version": 5},
        {"roi": [-0.1, 0, 0.5, 0.5]},
        {"roi": [0, 0, 2, 1]},
        {"ocr_box": [0.2, 0.2, 0.9, 0.5]},
        {"confirmed": True},
        {"role": "unknown"},
        {"version": -1},
    ],
)
def test_profile_validation(patch):
    profile = copy.deepcopy(DEFAULT)
    profile.update(patch)
    with pytest.raises(ValueError):
        validate(profile)
```

- [ ] Make both edits to `tests/test_workbench.py`.

### Step 2: Run tests to verify they fail

Run: `./.venv/bin/pytest -q tests/test_workbench.py -k "backend or profile_validation"`
Expected: `test_profile_v3_is_migrated_with_sevenseg_backend` fails with
`KeyError: 'backend'` (doesn't exist in `DEFAULT` yet);
`test_unknown_backend_is_rejected` and `test_tesseract_cli_backend_is_accepted`
fail similarly; `test_profile_validation[patch6]` (the new `schema_version:
5` case) currently passes already (5 is invalid either way) — that's fine,
it's the *old* `schema_version: 4` case removal that matters, verify no
other test currently depends on `DEFAULT["schema_version"] == 3` (search
first: `grep -rn 'schema_version.*3\b' tests/test_workbench.py`).

### Step 3: Implement the schema change

In `src/dispread/workbench/profiles.py`, change:

```python
DEFAULT = {
    "schema_version": 3,
```

to:

```python
DEFAULT = {
    "schema_version": 4,
```

and add `"backend": "sevenseg",` as a new key in the `DEFAULT` dict, right
after `"layout": DisplayLayout().to_dict(),` (end of the dict, before the
closing `}`):

```python
    "layout": DisplayLayout().to_dict(),
    # Welcher ValueReader diesen Ausschnitt liest. "sevenseg" fuer 7-Segment-
    # Anzeigen (Default, unveraendertes Verhalten), "tesseract_cli" fuer
    # Zeichen-/dot-matrix-LCDs, die sevenseg strukturell nicht lesen kann
    # (siehe docs/superpowers/specs/2026-09-21-tesseract-backend-design.md).
    "backend": "sevenseg",
}
```

Add the migration in `validate()`, right after the existing schema-3
digit_gap_ratio backfill block and before the `if set(data) != set(DEFAULT)`
check:

```python
    if isinstance(data.get("layout"), dict):
        for key, default in DEFAULT["layout"].items():
            data["layout"].setdefault(key, default)
    # Schema 3 -> 4: neues backend-Feld. Unbedingt auf schema_version == 3
    # geprueft (nicht zusaetzlich auf "backend" not in data) - sonst wuerde
    # ein Testfixture, das DEFAULT komplett kopiert und nur roi_quad/ocr_box
    # entfernt (wie die bestehenden v1/v2-Migrationstests es tun), "backend"
    # bereits enthalten und schema_version bliebe faelschlich bei 3 haengen.
    # setdefault reproduziert exakt das bisherige Verhalten fuer ein
    # echtes altes Profil ohne dieses Feld, ohne ein bereits vorhandenes
    # backend zu ueberschreiben.
    if data.get("schema_version") == 3:
        data.setdefault("backend", "sevenseg")
        data["schema_version"] = 4
    if set(data) != set(DEFAULT) or data["schema_version"] != 4:
        raise ValueError("Unbekanntes Profilschema oder unbekannte Felder")
```

Add the backend value check right after the existing `role`/`confirmed`
check:

```python
    if data["role"] not in ("main", "secondary") or type(data["confirmed"]) is not bool:
        raise ValueError("Ungueltige Anzeigenrolle/Bestaetigung")
    if data["backend"] not in ("sevenseg", "tesseract_cli"):
        raise ValueError("backend muss sevenseg oder tesseract_cli sein")
```

- [ ] Make all three edits to `src/dispread/workbench/profiles.py`.

### Step 4: Update the two pre-existing migration tests

Because schema 3 now always advances to schema 4 (Step 3 above), the two
pre-existing tests that migrate an old profile through schema 3 now end up
at schema 4 instead. In `tests/test_workbench.py`, change:

```python
def test_profile_v1_rectangle_is_migrated_to_quad():
    profile = copy.deepcopy(DEFAULT)
    profile.pop("roi_quad")
    profile.pop("ocr_box")
    profile["schema_version"] = 1
    profile["roi"] = [0.1, 0.2, 0.5, 0.4]
    profile["confirmed"] = True

    migrated = validate(profile)
    assert migrated["schema_version"] == 3
```

to end with:

```python
    migrated = validate(profile)
    assert migrated["schema_version"] == 4
```

and change:

```python
def test_profile_v2_is_migrated_with_full_ocr_box():
    profile = copy.deepcopy(DEFAULT)
    profile.pop("ocr_box")
    profile["schema_version"] = 2

    migrated = validate(profile)

    assert migrated["schema_version"] == 3
```

to end with:

```python
    migrated = validate(profile)

    assert migrated["schema_version"] == 4
```

(only the `schema_version` assertion changes in both — every other
assertion in these two tests, e.g. the `roi_quad`/`ocr_box` value checks,
stays exactly as it is today.)

- [ ] Make both one-line assertion edits.

### Step 5: Run tests to verify they pass

Run: `./.venv/bin/pytest -q tests/test_workbench.py -v`
Expected: all pass, including the two updated migration tests and the three
new backend tests from Step 1.

### Step 6: Update CHANGELOG (same commit)

Add a new top entry to `CHANGELOG.md`:

```markdown
## 0.1.0.dev0 — 2026-09-21 (Profilschema: backend-Feld fuer tesseract_cli)

**Problem:** `src/dispread/ocr/tesseract_cli.py` (voriger Commit) existiert,
aber kein Profil kann es auswaehlen - `DisplayLayout`/das Profilschema
kannten nur `sevenseg`.

**Änderung:** `DEFAULT["backend"] = "sevenseg"`, Schema 3 -> 4. Migration:
ein Profil mit Schema 3 ohne `backend`-Feld bekommt `"sevenseg"` - exakt das
bisherige Verhalten, keine Vermutung; die Umstellung erfolgt unbedingt bei
`schema_version == 3` (nicht zusaetzlich an der Feldabwesenheit geprueft),
sonst haetten die bestehenden v1/v2-Migrationstests (die DEFAULT komplett
kopieren) das neue Feld bereits mitgebracht und waeren faelschlich bei
Schema 3 haengen geblieben. `validate()` lehnt unbekannte `backend`-Werte
ab. 3 neue Tests (Migration, unbekannter Wert abgelehnt, `tesseract_cli`
akzeptiert); zwei bestehende Migrationstests
(`test_profile_v1_rectangle_is_migrated_to_quad`,
`test_profile_v2_is_migrated_with_full_ocr_box`) erwarten jetzt
`schema_version == 4` statt `3`; ein bestehender Parametrisierungsfall in
`test_profile_validation` von `schema_version: 4` auf `5` verschoben (4 ist
jetzt die gueltige aktuelle Version).

**Konsequenz:** Das Feld existiert und wird validiert, aber `Controller`
liest es noch nicht (naechster Commit) - ein gesetztes `backend` hat bisher
keine Wirkung.
```

- [ ] Add the CHANGELOG entry.

### Step 7: Run full verification

Run: `./.venv/bin/ruff check src tests examples scripts && ./.venv/bin/pytest -q`
Expected: `All checks passed!`, all tests pass.

### Step 8: Commit

```bash
git add src/dispread/workbench/profiles.py tests/test_workbench.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
profiles.py: backend-Feld fuers Profilschema (sevenseg/tesseract_cli)

DEFAULT["backend"] = "sevenseg", Schema 3 -> 4. Migration reproduziert das
bisherige Verhalten fuer alte Profile (kein backend-Feld -> sevenseg),
validate() lehnt unbekannte Werte ab. Controller liest das Feld noch nicht
(naechster Commit).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `Controller` wiring — backend selection

**Files:**
- Modify: `src/dispread/workbench/controller.py`
- Modify: `tests/test_workbench.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `TesseractReader` (Task 1, `dispread.ocr.tesseract_cli`),
  `DEFAULT["backend"]` / `validate()`'s backend check (Task 2).
- Produces: `Controller._reader_for(backend: str) -> ValueReader` (used
  internally); `Controller.command("backend.set", {"value": "sevenseg" |
  "tesseract_cli"})`; `Controller.command("layout.autofit", ...)` now
  returns `{"matched": False, "reason": "..."}` immediately (no search) when
  `self.config["backend"] == "tesseract_cli"`.

### Step 1: Write the failing tests

First add `import shutil` to the existing top-of-file import block in
`tests/test_workbench.py` (it isn't imported yet — needed for the
`skipif` guard below), next to the existing `import os`/`import threading`
lines.

Then add to `tests/test_workbench.py`, near the existing `_autofit_scene`
helper and its tests (`test_autofit_liefert_einen_vorschlag_ohne_etwas_zu_bestaetigen`):

```python
@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract-Binary fehlt (OQ-15)")
def test_backend_set_switches_which_reader_answers_reads(tmp_path):
    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit=None)
    image, _shown, area = render_display(12.34, layout)
    x, y, width, height = area
    image_height, image_width = image.shape[:2]

    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.config["roi"] = [x / image_width, y / image_height, width / image_width, height / image_height]
    c.config["ocr_box"] = [0.0, 0.0, 1.0, 1.0]
    c.config["confirmed"] = True
    c.publish(image, {"timebase": "synthetic"})

    assert c.config["backend"] == "sevenseg"
    reading_sevenseg = c.snapshot()["reading"]
    assert reading_sevenseg["backend"].startswith("sevenseg/")

    c.command("backend.set", {"value": "tesseract_cli"})
    assert c.config["backend"] == "tesseract_cli"
    c.publish(image, {"timebase": "synthetic"})
    reading_tesseract = c.snapshot()["reading"]
    assert reading_tesseract["backend"].startswith("tesseract_cli/")


def test_backend_set_rejects_unknown_value(tmp_path):
    c = Controller(tmp_path)
    with pytest.raises(ValueError, match="backend"):
        c.command("backend.set", {"value": "not_a_backend"})


def test_layout_autofit_rejects_immediately_for_tesseract_backend(tmp_path):
    """Kein tesseract-Binary noetig: der Backend-Check in `_autofit` gibt
    zurueck, bevor irgendein Reader instanziiert wird."""
    layout, image, text, quad, ocr_box = _autofit_scene()
    c = Controller(tmp_path)
    c.config["layout"] = layout.to_dict()
    c.command("backend.set", {"value": "tesseract_cli"})
    c.publish(image, {"timebase": "synthetic"})
    frozen = c.command("freeze")

    result = c.command("layout.autofit", {"id": frozen["id"], "quad": quad, "ocr_box": ocr_box, "text": text})

    assert result == {
        "matched": False,
        "reason": (
            "layout.autofit ist fuer backend=tesseract_cli nicht anwendbar - "
            "die gesuchten Glyphenverhaeltnisse gelten nur fuer sevenseg"
        ),
    }
```

- [ ] Add `import shutil` and the three tests to `tests/test_workbench.py`
      exactly as above.

### Step 2: Run tests to verify they fail

Run: `./.venv/bin/pytest -q tests/test_workbench.py -k backend`
Expected: `test_backend_set_switches_which_reader_answers_reads` and
`test_backend_set_rejects_unknown_value` fail with `ValueError: Unbekannter
Befehl: backend.set` (op doesn't exist yet);
`test_layout_autofit_rejects_immediately_for_tesseract_backend` fails
because `_autofit` still runs the real (slow, sevenseg-shaped) search
instead of returning the expected rejection dict.

### Step 3: Implement the `Controller` changes

In `src/dispread/workbench/controller.py`:

1. Add the import (near the existing `from dispread.ocr.sevenseg import
   SevenSegmentReader` line):

```python
from dispread.ocr.sevenseg import SevenSegmentReader
from dispread.ocr.tesseract_cli import TesseractReader
```

2. In `__init__`, replace:

```python
        self.reader = SevenSegmentReader()
```

with:

```python
        self.reader = SevenSegmentReader()
        # tesseract_cli ist teurer zu instanzieren (prueft die Binary,
        # fragt die Version ab) - nur bei Bedarf erzeugen, dann fuer die
        # Laufzeit dieser Controller-Instanz wiederverwenden.
        self._tesseract_reader = None
```

3. Add a new method, right after `__init__` completes (any point before its
   first use is fine — place it near the other small private helpers, e.g.
   just above `_read`):

```python
    def _reader_for(self, backend):
        """`ValueReader` fuer das aktuell konfigurierte `backend`-Feld.

        `sevenseg` ist die bereits bei `__init__` erzeugte Standardinstanz.
        `tesseract_cli` wird erst bei Bedarf erzeugt (prueft dabei, ob die
        Binary vorhanden ist) und danach wiederverwendet, nicht bei jedem
        Read neu instanziiert.
        """
        if backend == "tesseract_cli":
            if self._tesseract_reader is None:
                self._tesseract_reader = TesseractReader()
            return self._tesseract_reader
        return self.reader
```

4. In `_read` (around line 1319), replace:

```python
            read = self.reader.read(reader_crop, layout)
```

with:

```python
            reader = self._reader_for(config["backend"])
            read = reader.read(reader_crop, layout)
```

and a few lines below, replace:

```python
                "confidence_calibrated": self.reader.declares_confidence_calibrated,
```

with:

```python
                "confidence_calibrated": reader.declares_confidence_calibrated,
```

5. In `_autofit` (around line 826), add the backend check right after the
   existing `with self.lock:` block that reads `self.config["layout"]`:

```python
        with self.lock:
            frame = self.frames[args["id"]]
            layout = DisplayLayout.from_dict(copy.deepcopy(self.config["layout"]))
            backend = self.config["backend"]
        if backend == "tesseract_cli":
            return {
                "matched": False,
                "reason": (
                    "layout.autofit ist fuer backend=tesseract_cli nicht anwendbar - "
                    "die gesuchten Glyphenverhaeltnisse gelten nur fuer sevenseg"
                ),
            }
        height, width = frame["image"].shape[:2]
```

   (this replaces the existing `height, width = frame["image"].shape[:2]`
   line that currently follows the `with self.lock:` block directly — the
   new `if backend == "tesseract_cli": return ...` block is inserted
   between the lock block and that line, and the lock block itself gains
   `backend = self.config["backend"]`).

6. Also in `_autofit`, the `preview = self.reader.read(...)` line further
   down needs to use the same per-backend lookup for consistency (even
   though it's unreachable for `tesseract_cli` after the step-5 change, this
   keeps the method internally consistent rather than leaving a
   backend-blind call in code that otherwise checks it):

```python
        preview = self._reader_for(backend).read(crop_box(crop.image, result.ocr_box), result.layout)
```

7. In `command()`'s locked dispatch table, add a new `elif` branch right
   after the existing `layout.set_many` branch and before `elif op ==
   "focus":`:

```python
            elif op == "backend.set":
                data = copy.deepcopy(self.config)
                data["backend"] = args["value"]
                self._change(data)
```

- [ ] Make all seven edits to `src/dispread/workbench/controller.py`.

### Step 4: Run tests to verify they pass

Run: `./.venv/bin/pytest -q tests/test_workbench.py -v`
Expected: all pass, including the three new backend tests and the full
pre-existing suite in this file (the `_reader_for`/`reader` renaming inside
`_read`/`_autofit` must not change behavior for `backend="sevenseg"`, which
is every existing test's default).

If `test_backend_set_switches_which_reader_answers_reads` fails because
`TesseractReader()` raises (no `tesseract` binary on the test machine): add
`@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract-Binary fehlt (OQ-15)")`
above it and import `shutil` at the top of `tests/test_workbench.py` if not
already imported.

### Step 5: Update CHANGELOG (same commit)

Add a new top entry to `CHANGELOG.md`:

```markdown
## 0.1.0.dev0 — 2026-09-21 (Controller: backend-Feld waehlt den Leser)

**Problem:** `backend` existierte im Profilschema (voriger Commit), aber
`Controller` benutzte immer die fest instanzierte `SevenSegmentReader` -
das Feld hatte keine Wirkung.

**Änderung:** `Controller._reader_for(backend)` waehlt zwischen der
bestehenden `SevenSegmentReader`-Instanz und einer bei Bedarf erzeugten,
wiederverwendeten `TesseractReader`-Instanz. `_read`/`_autofit` nutzen das
statt des fest verdrahteten `self.reader`. Neuer Befehl `backend.set`
(analog `profile.role`). `layout.autofit` (die sevenseg-Glyphenverhaeltnis-
Suche) lehnt bei `backend=tesseract_cli` sofort mit einer erklaerenden
Meldung ab, statt eine fuer dieses Backend bedeutungslose Suche laufen zu
lassen. 3 neue Tests: Backend-Wechsel aendert tatsaechlich, welcher Leser
antwortet; unbekannter Wert abgelehnt; `layout.autofit` lehnt sofort ab.

**Konsequenz:** Ein Profil kann jetzt tatsaechlich `tesseract_cli` als
Leser nutzen. Noch offen: eine UI-Auswahl dafuer (naechster Commit) - bisher
nur ueber den `backend.set`-Befehl direkt erreichbar.
```

- [ ] Add the CHANGELOG entry.

### Step 6: Run full verification

Run: `./.venv/bin/ruff check src tests examples scripts && ./.venv/bin/pytest -q`
Expected: `All checks passed!`, all tests pass.

### Step 7: Commit

```bash
git add src/dispread/workbench/controller.py tests/test_workbench.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
controller.py: backend-Feld waehlt tatsaechlich den Leser (sevenseg/tesseract_cli)

_reader_for(backend) ersetzt das fest verdrahtete self.reader an den drei
Lesestellen (_read, _autofit). Neuer backend.set-Befehl. layout.autofit
lehnt bei backend=tesseract_cli sofort ab (die gesuchten Glyphenverhaeltnisse
gelten nur fuer sevenseg) statt eine bedeutungslose Suche zu starten.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: UI backend selector

**Files:**
- Modify: `src/dispread/workbench/fields.py`
- Modify: `tests/test_workbench.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `Controller.command("backend.set", ...)` (Task 3).
- Produces: nothing new consumed elsewhere — this is the leaf UI task.

### Step 1: Write the failing test

Add to `tests/test_workbench.py`, next to the other `fields.rows(c.snapshot())`-based
tests (e.g. `test_inner_ocr_box_calibrates_grid_inside_padded_roi`'s
neighbors — search `fields.rows(c.snapshot())` for the established pattern):

```python
def test_backend_row_is_present_and_reflects_current_value(tmp_path):
    c = Controller(tmp_path)

    backend_rows = [row for row in fields.rows(c.snapshot()) if row["key"] == "backend"]

    assert len(backend_rows) == 1
    row = backend_rows[0]
    assert row["value"] == "sevenseg"
    option_values = {option["value"] for option in row["options"]}
    assert option_values == {"sevenseg", "tesseract_cli"}
    tesseract_option = next(o for o in row["options"] if o["value"] == "tesseract_cli")
    assert tesseract_option["ops"] == [["backend.set", {"value": "tesseract_cli"}]]
```

This relies on `_row`'s and `_option`'s existing, already-verified return
shapes (`src/dispread/workbench/fields.py:65-74`): `_row(...)` returns a
dict with a `"key"`/`"value"`/`"options"` entry, `_option(...)` returns a
dict with `"value"`/`"ops"` — the same shape every other field-row test in
this file already asserts against (e.g. `table["reading.value"]["display"]`
two tests above).

- [ ] Add the test to `tests/test_workbench.py` exactly as above.

- [ ] Add the test, with field names verified against `_row`'s actual
      return shape.

### Step 2: Run test to verify it fails

Run: `./.venv/bin/pytest -q tests/test_workbench.py -k backend_row`
Expected: FAIL — no row with `key == "backend"` exists yet.

### Step 3: Implement the UI row

In `src/dispread/workbench/fields.py`, in `rows(state)`, add a new row
right before `result.extend(_layout_rows(config["layout"]))`:

```python
    result.append(
        _row(
            "backend",
            "leser-backend",
            "choice",
            config["backend"],
            "7-Segment (sevenseg)" if config["backend"] == "sevenseg" else "Zeichen-OCR (tesseract)",
            "sevenseg fuer 7-Segment-Anzeigen; tesseract_cli fuer Zeichen-/dot-matrix-LCDs (z. B. GSV-Sensor)",
            options=[
                _option("sevenseg", "7-Segment (sevenseg)", [["backend.set", {"value": "sevenseg"}]]),
                _option(
                    "tesseract_cli",
                    "Zeichen-OCR (tesseract)",
                    [["backend.set", {"value": "tesseract_cli"}]],
                ),
            ],
        )
    )
    result.extend(_layout_rows(config["layout"]))
```

- [ ] Make the edit to `src/dispread/workbench/fields.py`.

### Step 4: Run test to verify it passes

Run: `./.venv/bin/pytest -q tests/test_workbench.py -k backend_row -v`
Expected: PASS.

### Step 5: Update CHANGELOG (same commit)

Add a new top entry to `CHANGELOG.md`:

```markdown
## 0.1.0.dev0 — 2026-09-21 (Workbench-UI: Leser-Backend waehlbar)

**Problem:** `backend.set` (voriger Commit) war nur ueber einen direkten
Befehl erreichbar, keine Bedienoberflaeche dafuer.

**Änderung:** Neue Zeile "leser-backend" in `fields.rows()`, direkt vor den
Layout-Feldern - Auswahl zwischen `sevenseg` (7-Segment) und `tesseract_cli`
(Zeichen-/dot-matrix-LCDs wie GSV-Sensor), demselben deklarativen
`_row`/`_option`-Muster wie die bestehende `polaritaet`-Zeile. Die
bestehende `reading.evidence`-Zeile zeigt das aktive Backend bereits generisch
(`reading.get('backend')`) - keine Aenderung dort noetig.

**Konsequenz:** Ein Bediener kann jetzt ueber die Werkbank-Oberflaeche
zwischen den beiden Lesern wechseln. Kein echter Browser-Klick-Durchlauf
verifiziert (dieselbe Einschraenkung wie OQ-21/OQ-34 fuer den ganzen
Prototyp) - `fields.rows()` ist unit-getestet, nicht die DOM-Interaktion.
```

- [ ] Add the CHANGELOG entry.

### Step 6: Run full verification

Run: `./.venv/bin/ruff check src tests examples scripts && ./.venv/bin/pytest -q`
Expected: `All checks passed!`, all tests pass.

### Step 7: Commit

```bash
git add src/dispread/workbench/fields.py tests/test_workbench.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
fields.py: Leser-Backend (sevenseg/tesseract_cli) in der Workbench-UI waehlbar

Neue Zeile "leser-backend" vor den Layout-Feldern, gleiches _row/_option-
Muster wie die bestehende polaritaet-Zeile. reading.evidence zeigt das
aktive Backend bereits generisch, keine Aenderung dort noetig.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## After Task 4: update `docs/status.md`

Not a numbered task (no code), but required before ending the session
(AGENTS.md: "Vor Sessionende docs/status.md aktualisieren"). Prepend a note
to the top of the "Sofort zu wissen" section summarizing: `tesseract_cli`
backend built and wired end-to-end (profile schema, `Controller`, UI);
recognition accuracy on the GSV-Sensor's dot-matrix font is not yet
reliable with the stock Tesseract model (documented follow-up: more
preprocessing iteration, or a segment-font-trained model); the confidence
threshold is an unvalidated placeholder. Link to
`docs/superpowers/specs/2026-09-21-tesseract-backend-design.md` and this
plan file.
