# Plan: OCR-Selbstkalibrierung — Messbarkeit, Autofit aus getipptem Wert, verankerte Nachführung

> **Für agentische Bearbeiter:** PFLICHT-SUBSKILL: `superpowers:subagent-driven-development`
> (empfohlen) oder `superpowers:executing-plans`, um diesen Plan Aufgabe für Aufgabe
> umzusetzen. Die Schritte nutzen Checkbox-Syntax (`- [ ]`) zur Fortschrittsverfolgung.

**Ziel:** Die OCR-Einrichtung von „Regler pixelgenau justieren" auf „einmal den
angezeigten Wert eintippen" umstellen, und eine im Lauf verrutschende Kamera
nachführen, statt die Erkennung abbrechen zu lassen.

**Architektur:** Vier Phasen, jede für sich lieferbar. Phase A baut die
Messvorrichtung (Clipaufnahme mit **einem** getippten Label je Clip,
`replay://`, Benchmark mit dreigeteilter Metrik) — ohne sie ist keine
Erkennungsänderung belegbar. Phase B leitet Zahlenformat und Rastergeometrie
aus dem getippten Wert ab, statt sie vom Bediener einstellen zu lassen. Phase C
führt die bestätigte Geometrie gegen ein bei der Bestätigung gemerktes
Referenzbild nach, hart begrenzt. Phase D ist die eigentliche Decoder-Änderung
und ist bewusst **datengesperrt**.

**Technik:** Python 3.13, System-OpenCV 4.10, NumPy — alles bereits vorhanden.
Keine neue Abhängigkeit, kein Training, kein neuronales Modell.

**Spec:** dieses Dokument, Abschnitt [Spezifikation](#spezifikation).

---

## Globale Randbedingungen

Aus `AGENTS.md`, `Konzept.md` §7 und `CLAUDE.md`. Sie gelten implizit für
**jede** Aufgabe in diesem Plan.

- Python ausschließlich über `./.venv/bin/python`, `./.venv/bin/pytest`,
  `./.venv/bin/ruff`. Keine PyPI-Installation von NumPy/OpenCV in die venv.
- **Kein Commit an `src/` ohne CHANGELOG-Eintrag** im obersten Abschnitt, im
  selben Commit, im Schema Problem / Änderung / Konsequenz.
- Unlesbare oder unbekannte Eingaben werden **abgelehnt, nicht geraten**. Eine
  Falschablehnung ist die zulässige Richtung; eine stille Fehlablesung nicht.
- Modell-/Backendkonfidenz ist **keine** Fehlerwahrscheinlichkeit.
  `declares_confidence_calibrated` bleibt `False`.
- Der Referenzwert der Kalibriermaschine erreicht `ValueReader.read` und
  `ReleaseGate.evaluate` **strukturell nicht**. Ein Label darf ausschließlich
  offline im Benchmark verwendet werden.
- Jede Zeitangabe trägt ihre `TimeBaseKind`. Aus `SYNTHETIC` und `FILE_MTIME`
  wird keine Zeitaussage abgeleitet. Unbekannte Unsicherheit ist `None`, nicht `0`.
- Jede neue Schwelle ist ein **Vorabdefault** und wird als solcher im Code
  benannt, bis eine Messung in `docs/VALIDATION.md` steht.
- Neue Funktionalität muss ohne Kamera testbar sein (`synthetic://`,
  `folder://`, `replay://`). `picamera2` wird nirgends neu importiert.
- Zielgröße des entzerrten Ausschnitts bleibt `CROP_SIZE = (400, 160)`.

---

## Spezifikation

### Problem, wie der Bediener es beschreibt

> „OCR ist besonders zeitaufwendig für den User, da die einzelnen
> Segmentpunkte exakt positioniert sein müssen, da sonst die Auslesung nicht
> funktioniert. Bei längeren Lesungen kann die Kamera etwas verrutschen und
> dann bricht die Erkennung ab. Selber hunderte Fotos zu annotieren ist nicht
> praktikabel, auch da dieses Projekt universell 7-Segment-Displays auslesen
> soll."

Das sind drei getrennte Probleme, die getrennte Lösungen brauchen:

| # | Problem | Phase |
| --- | --- | --- |
| 1 | Einrichtung dauert, Raster muss von Hand sitzen | B |
| 2 | Kamera verrutscht im Lauf, Erkennung bricht ab | C |
| 3 | Messung ist punkt- und schwellenempfindlich | D, datengesperrt |
| 0 | Keine dieser Änderungen ist heute belegbar | A |

### Messbefund vom 2026-09-11 (diese Sitzung, an echten Daten)

Unter `var/workbench/annotations/` liegen inzwischen **neun** Annotationen,
nicht die in `docs/status.md` und OQ-25 genannten zwei. Sechs davon tragen
einen getippten Sollwert. Alle stammen von **einem** Gerät (4 Stellen, 2
Nachkommastellen, ohne Vorzeichenstelle, `digit_gap_ratio=0.65`, Einheit `V`),
mit drei verschiedenen angezeigten Werten.

**Ist-Stand `sevenseg/2` auf diesen sechs Bildern:**

```
korrekt = 5     falsch angenommen = 0     abgelehnt = 1
```

Das abgelehnte Bild ist `8a18ee05` (`110?`, Sollwert `11,00`). Die
Segmentmessungen der letzten Stelle (soll `0`, also sechs aktive Segmente):

```
Stelle 3   a:AN 0.42  b:AN 0.60  c:AN 0.44  d:AN 0.53  e:AN 0.38  f:AN 0.54  g:aus 0.28
Stelle 2   a:AN 0.59  b:AN 0.85  c:AN 0.69  d:AN 0.81  e:AN 0.58  f:AN 0.77  g:aus 0.26
```

Stelle 3 leuchtet als Ganzes schwächer als Stelle 2. Die eine globale Schwelle
aus `segment_threshold()` liegt zwangsläufig zwischen beiden Niveaus und reißt
das tatsächlich leuchtende `e` (0.38) mit ab. **Das bestätigt Ursache (1) aus
OQ-23 erneut und unabhängig.**

### Drei Lösungsansätze wurden prototypisch gegen genau diese Bilder gemessen

Der Prototyp lag im Scratchpad und ist bewusst **nicht** ins Repo übernommen
worden — er war eine Entscheidungsgrundlage, kein Baustein.

| Variante | korrekt | falsch | abgelehnt |
| --- | --- | --- | --- |
| A — heute: Punktabtastung, eine globale Schwelle | 5 | **0** | 1 |
| B — Panelbezug je Stelle, Otsu innerhalb der Zelle | 5 | **0** | 1 |
| D — Panelbezug je Stelle, Schwelle = Anteil der Zellspanne | 5 | **0** | 1 |
| C/E — Segmentflächen statt Punkte, Profil-Defaults | 3 | **0** | 3 |
| C — erste Fassung der Flächenmessung | 0 | **1** | 5 |

Drei Befunde, die den Plan umgestellt haben:

1. **Die Entscheidungsregel allein bringt nichts.** Variante B liefert exakt
   dasselbe Ergebnis wie heute. Otsu *innerhalb* einer Zelle wählt bei sechs
   aktiven und einem inaktiven Segment die falsche Trennung — es maximiert die
   gewichtete Zwischenklassenvarianz und bevorzugt deshalb einen ausgewogenen
   4:3-Schnitt gegenüber dem richtigen 6:1-Schnitt.
2. **Variante D repariert ein Bild und zerbricht ein anderes.** Sie liest
   `8a18ee05` korrekt, dekodiert dafür in `6ffc561b` Stelle 0 als `7` statt
   `1` — gerettet nur dadurch, dass eine andere Stelle in demselben Bild
   `?` wurde. Der Rohwert von Segment `a` liegt dort bei 0.38, während `b`/`c`
   derselben Stelle bei 0.76/0.84 liegen; irgendetwas beleuchtet diese
   Segmentposition (Übersprechen, Nachleuchten, oder der Abtastpunkt trifft
   den Nachbarn). **Das gehört als Messbefund in OQ-23**, siehe Task 12.
3. **Flächige Segmentmessung ist mit den heutigen Profilwerten schlechter, nicht
   besser.** `thickness_ratio=0.16` und `inset_ratio=0.10` sind nie kalibriert
   worden. Ein Sweep zeigt, dass sie real Treffer kosten:

   ```
   thickness=0.12 inset=0.10   korrekt=5   falsch=0   abgelehnt=1
   thickness=0.20 inset=0.05   korrekt=5   falsch=0   abgelehnt=1
   thickness=0.16 inset=0.10   korrekt=3   falsch=0   abgelehnt=3   <- heutiger Default
   ```

Der Sweep ist zugleich die Warnung: **zwei weit auseinanderliegende
Parametersätze erreichen dieselbe Punktzahl.** Sechs Bilder eines Geräts
unterbestimmen das Problem. Genau deshalb steht Phase A vorn und Phase D
hinten, und genau deshalb optimiert der Autofit in Phase B nicht auf
„Treffer", sondern auf **Trennschärfe** (siehe Task 5).

### Bedienerentscheidungen dieser Sitzung

1. **Nachführung ohne neue Bestätigung ist erlaubt, hart begrenzt.** Verschieben
   und Drehen derselben bereits bestätigten Anzeige gilt nicht als neuer
   Bestätigungsakt; eine andere Anzeige zu wählen schon. Außerhalb der Grenze
   wird der Wert `UNREADABLE` und der Bediener muss neu bestätigen.
   Begründung: `Konzept.md` §4 macht die Bestätigung zum menschlichen Akt über
   die **semantische Identität** (welche Anzeige, welche Einheit, welches
   Format); die Liste „nicht verhandelbar" in `AGENTS.md` enthält kein Verbot
   geometrischer Nachregistrierung.
2. **Einrichtung per getipptem Wert statt per Regler.** Der Bediener bestätigt
   die ROI und tippt einmal, was auf der Anzeige steht. Die Regler bleiben als
   Handkorrektur erhalten, sind aber nicht mehr der Normalweg.
3. **Testdaten als Kurzclips.** Wert am Gerät einstellen, **einmal** eintippen,
   3–5 s aufnehmen. Jeder Frame des Clips trägt dasselbe Label. Damit erfüllt
   dieselbe Laborstunde auch ROADMAP-P2.

### Verworfene Alternativen

Gehört nach `docs/project_history.md` (Task 12).

- **ssocr** (`https://www.unix-ag.uni-kl.de/~auerswal/ssocr/`, GPLv3, C, nur
  CLI) — vom Bediener vorgeschlagen. Verworfen als Primärpfad: es liefert nur
  die Ziffernfolge, keine Per-Segment-Evidenz, und `ReleaseGate.evaluate`
  verlangt `contrast` und `min_margin` aus der Segmentanalyse (OQ-19). Dazu
  Subprozessgrenze je Bild und eigene Ziffernsegmentierung, die den bereits
  bestätigten Rasterhinweis nicht nutzt. Als späteres, unabhängig
  implementiertes Vergleichsbackend neben Tesseract (OQ-15) weiterhin denkbar.
- **Gitterfreier Per-Ziffer-Decoder** (ssocr-Logik in-process, Raster je Bild
  neu herleiten). Verworfen, weil er OQ-25 in den **Lesepfad** erbt:
  `fit_ocr_box` wählt an dem realen Netzteil konsequent die falsche Zeile
  (untere `A`-Anzeige statt oberer `V`-Anzeige, IoU 0,0 an beiden Bildern).
  Als Vorschlag ist das folgenlos, im Lesepfad wäre es eine stille Ablesung
  der falschen Messgröße — die Haupt-/Nebenanzeige-Verwechslung aus
  `Konzept.md` §7. Die brauchbare Hälfte (Selbstskalierung je Ziffer) ist in
  Phase D **verankert** aufgenommen: nur innerhalb einer Umgebung des
  bestätigten Rasters.
- **Kleiner Ziffernklassifikator, rein synthetisch trainiert.** Umgeht das
  Annotationsproblem, nicht das Datenproblem — `Konzept.md` §9 und der
  Docstring von `layout.py` sagen beide, dass synthetische Daten ein reales
  Testset ergänzen und nie ersetzen. Dazu: Softmax ist keine
  Fehlerwahrscheinlichkeit (`AGENTS.md`), die Freigabe bräuchte einen neuen
  Evidenzvertrag (OQ-19), und der IMX500-*Converter* fehlt auf dem Pi (OQ-11).
  Gehört nach ROADMAP-P8.
- **Rasterfeinschliff je Bild** (Projektionsprofil zieht die Zellgrenzen
  nach). Aus diesem Plan gestrichen: Phase C fängt die Bewegung bereits ab,
  und der Feinschliff bringt nur bei nicht-starren Änderungen im Ausschnitt
  etwas. Wird als eigener OQ-Eintrag festgehalten (Task 12), nicht gebaut.

### Nicht-Ziele

- Keine Freigabe von Messwerten in der Workbench. `released` bleibt `False`.
- Kein automatisches Übernehmen einer **semantischen** Auswahl: welche
  Anzeige, welche Einheit, welches Zahlenformat bleibt der ✓-Klick.
- Keine Änderung an `ValueRecord`, am Telegrammformat oder an der seriellen
  Ausgabe.
- Keine Lockerung von `_MIN_CONTRAST`/`_SAMPLE_HALFWIDTH` ohne die Daten aus
  Phase A. Das ist ausdrücklich die in OQ-23 benannte falsche Richtung.

---

## Dateistruktur

**Neu:**

| Datei | Verantwortung |
| --- | --- |
| `src/dispread/frames/replay_source.py` | `replay://` — aufgezeichnete Clips zurücklesen, Zeitbasis ehrlich abbilden |
| `src/dispread/benchmark.py` | Erkennungsqualität messen: dreigeteilte Metrik, Fehlerklassen, Gruppensplit-Prüfung |
| `src/dispread/ocr/autofit.py` | Rastergeometrie aus einem getippten Sollwert bestimmen. Reine Funktion, kein Zustand |
| `src/dispread/track.py` | `QuadTracker` — begrenzte Nachregistrierung eines bestätigten Quads |
| `scripts/ocr-benchmark.py` | Dünne CLI über `dispread.benchmark` |
| `tests/test_replay_source.py`, `tests/test_benchmark.py`, `tests/test_autofit.py`, `tests/test_track.py` | je Modul |

**Geändert:**

| Datei | Änderung |
| --- | --- |
| `src/dispread/workbench/controller.py` | Ops `clip.start`/`clip.stop`/`layout.autofit`/`layout.set_many`; Schreib-Thread; Tracker-Einbindung in `publish()` |
| `src/dispread/workbench/static/workbench.js` | Clip-Bedienung, Kalibrierschritt mit Werteingabe im `setup`-Modus |
| `src/dispread/workbench/static/index.html` | Bedienelemente dazu |
| `src/dispread/workbench/fields.py` | Anzeigezeilen für Nachführgüte und Polarität |
| `src/dispread/layout.py` | Feld `polarity` (Phase D) |
| `src/dispread/workbench/profiles.py` | `polarity` validieren |
| `src/dispread/ocr/sevenseg.py` | Polaritätsumkehr (Phase D, Task 10); Messänderung nur gesperrt (Task 11) |
| `src/dispread/validate.py` | `tracking_lost` in `GateConfig.blocking_flags` |

`controller.py` hat 1067 Zeilen und wächst hier weiter. Der Plan schiebt
deshalb jede rechnende Logik in eigene Module (`track.py`, `ocr/autofit.py`,
`benchmark.py`) und lässt im Controller nur Verdrahtung. Ein Aufteilen von
`controller.py` selbst ist nicht Teil dieses Plans.

---

# Phase A — Messbarkeit

Ohne diese Phase ist keine Erkennungsänderung belegbar. Das ist kein
Vorsichtssatz, sondern in dieser Sitzung gemessen: zwei Kandidatenänderungen
punkteten auf den vorhandenen Bildern identisch mit dem Ist-Stand, obwohl sie
auf verschiedenen Bildern versagen.

## Task 1: `ReplaySource` für `replay://`

**Dateien:**
- Neu: `src/dispread/frames/replay_source.py`
- Neu: `tests/test_replay_source.py`
- Ändern: `docs/ROADMAP.md` (P0-Zeile), `CHANGELOG.md`

**Schnittstellen:**
- Nutzt: `dispread.frames.types.Frame`, `dispread.records.Timestamp`,
  `TimeBaseKind`, `TimestampSemantics` — alle vorhanden. `_open_replay()` in
  `src/dispread/frames/__init__.py:108` importiert bereits
  `dispread.frames.replay_source.ReplaySource` mit dem Argument
  `session_dir` — diese Signatur ist vorgegeben und darf sich nicht ändern.
- Liefert: `ReplaySource`, `CLIP_SCHEMA_VERSION = 1` und das
  **Clip-Verzeichnisformat**, das Task 2 schreibt und Task 3 auswertet:

```
<clip>/clip.json
<clip>/frame_000001.png
<clip>/frame_000002.png   ...
```

```jsonc
{
  "schema_version": 1,
  "clip_id": "8f2c…",              // = Verzeichnisname
  "device_id": "gsv-2asd-0007",    // Splitgrenze (ROADMAP: nie der Frame)
  "ground_truth_text": "28,80",    // EINMAL getippt, gilt fuer alle Frames
  "profile": { … },                // vollstaendiges Profil zur Aufnahmezeit
  "profile_name": "netzteil-v",
  "calibrated_on_frame_sequence": 4711,  // oder null
  "dropped_frames": 0,
  "created_at": "2026-09-11T13:02:11+00:00",
  "created_timebase": "UTC",
  "frames": [
    {
      "file": "frame_000001.png",
      "frame_sequence": 4712,
      "capture_timestamp": {"value_ns": 123, "base": "sensor_boottime",
                            "semantics": "unknown", "uncertainty_ns": null},
      "metadata": { … }
    }
  ]
}
```

**Regel zur Zeitbasis:** Trug der aufgezeichnete Zeitstempel eine Zeitaussage
(`carries_time_information`), wird er beim Zurücklesen zu
`REPLAY_RECORDED` — genau dafür existiert dieser Enum-Wert. Trug er keine
(`SYNTHETIC`, `FILE_MTIME`), bleibt er unverändert. Ein Replay darf aus einer
synthetischen Aufnahme **keine** Zeitaussage machen.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Neue Datei `tests/test_replay_source.py`:

```python
"""replay:// — aufgezeichnete Clips zuruecklesen, ohne Zeitaussagen zu erfinden."""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from dispread.frames import open_source
from dispread.records import TimeBaseKind


def _write_clip(directory, *, base="sensor_boottime", frames=2, label="28,80"):
    directory.mkdir(parents=True, exist_ok=True)
    entries = []
    for index in range(frames):
        name = f"frame_{index + 1:06d}.png"
        image = np.full((8, 12, 3), index * 10, np.uint8)
        assert cv2.imwrite(str(directory / name), image)
        entries.append(
            {
                "file": name,
                "frame_sequence": 100 + index,
                "capture_timestamp": {
                    "value_ns": 1_000 + index,
                    "base": base,
                    "semantics": "unknown",
                    "uncertainty_ns": None,
                },
                "metadata": {"ExposureTime": 5000},
            }
        )
    (directory / "clip.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "clip_id": directory.name,
                "device_id": "geraet-1",
                "ground_truth_text": label,
                "profile": {},
                "profile_name": "test",
                "calibrated_on_frame_sequence": None,
                "dropped_frames": 0,
                "created_at": "2026-09-11T00:00:00+00:00",
                "created_timebase": "UTC",
                "frames": entries,
            }
        )
    )
    return directory


def test_clip_wird_mit_label_und_sequenz_zurueckgelesen(tmp_path):
    clip = _write_clip(tmp_path / "clip-a")
    source = open_source(f"replay://{clip}")
    source.open()
    try:
        frames = list(source.frames())
    finally:
        source.close()
    assert [f.frame_sequence for f in frames] == [100, 101]
    assert frames[0].raw_metadata["ground_truth"]["text"] == "28,80"
    assert frames[0].raw_metadata["device_id"] == "geraet-1"
    assert frames[0].image.shape == (8, 12, 3)


def test_aufgezeichneter_sensorzeitstempel_wird_als_replay_gefuehrt(tmp_path):
    """REPLAY_RECORDED traegt die Zeitaussage der Aufnahme, nicht die des Abspielens."""
    clip = _write_clip(tmp_path / "clip-b", base="sensor_boottime")
    source = open_source(f"replay://{clip}")
    source.open()
    frame = next(iter(source.frames()))
    source.close()
    assert frame.timebase is TimeBaseKind.REPLAY_RECORDED
    assert frame.is_time_bearing
    assert frame.capture_timestamp.value_ns == 1_000


def test_synthetische_aufnahme_wird_durch_replay_nicht_zeittragend(tmp_path):
    """Ein Replay darf aus SYNTHETIC keine Zeitaussage machen (AGENTS.md)."""
    clip = _write_clip(tmp_path / "clip-c", base="synthetic")
    source = open_source(f"replay://{clip}")
    source.open()
    frame = next(iter(source.frames()))
    source.close()
    assert frame.timebase is TimeBaseKind.SYNTHETIC
    assert not frame.is_time_bearing


def test_fehlende_clipdatei_wird_klar_gemeldet(tmp_path):
    (tmp_path / "leer").mkdir()
    source = open_source(f"replay://{tmp_path / 'leer'}")
    with pytest.raises(FileNotFoundError, match="clip.json"):
        source.open()


def test_unbekannte_schemaversion_wird_abgelehnt(tmp_path):
    clip = _write_clip(tmp_path / "clip-d")
    data = json.loads((clip / "clip.json").read_text())
    data["schema_version"] = 99
    (clip / "clip.json").write_text(json.dumps(data))
    source = open_source(f"replay://{clip}")
    with pytest.raises(ValueError, match="Clipschema"):
        source.open()
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_replay_source.py -q
```
Erwartet: `ModuleNotFoundError: No module named 'dispread.frames.replay_source'`.

- [ ] **Schritt 3: Implementierung schreiben**

Neue Datei `src/dispread/frames/replay_source.py`:

```python
"""Aufgezeichnete Clips zurueckspielen.

Ein Clip ist die kleinste Einheit belastbarer Validierung: der Bediener stellt
am Geraet einen Wert ein, tippt ihn *einmal* ein und nimmt ein paar Sekunden
auf. Jeder Frame traegt damit dasselbe Label, ohne Einzelbildannotation.

Der Sollwert steht in `raw_metadata["ground_truth"]` - wie bei
`SyntheticSource`. Die Pipeline sieht ihn nie; nur der Benchmark liest ihn.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2

from dispread.frames.types import Capability, Frame
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics

CLIP_SCHEMA_VERSION = 1


class ReplaySource:
    """Bildquelle aus einem aufgezeichneten Clipverzeichnis."""

    def __init__(self, session_dir: str) -> None:
        self.directory = Path(session_dir)
        self.clip: dict[str, Any] = {}

    # -- FrameSource ------------------------------------------------------
    def open(self) -> None:
        manifest = self.directory / "clip.json"
        if not manifest.exists():
            raise FileNotFoundError(f"Kein clip.json in {self.directory}")
        clip = json.loads(manifest.read_text())
        if clip.get("schema_version") != CLIP_SCHEMA_VERSION:
            raise ValueError(
                f"Clipschema {clip.get('schema_version')!r} unbekannt, erwartet {CLIP_SCHEMA_VERSION}"
            )
        self.clip = clip

    def close(self) -> None:
        self.clip = {}

    @property
    def source_id(self) -> str:
        return f"replay:{self.directory.name}"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.SEEK})

    def describe(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "clip_id": self.clip.get("clip_id"),
            "device_id": self.clip.get("device_id"),
            "ground_truth_text": self.clip.get("ground_truth_text"),
            "frame_count": len(self.clip.get("frames", ())),
            "dropped_frames": self.clip.get("dropped_frames", 0),
            "profile_name": self.clip.get("profile_name"),
            "calibrated_on_frame_sequence": self.clip.get("calibrated_on_frame_sequence"),
        }

    def frames(self) -> Iterator[Frame]:
        if not self.clip:
            raise RuntimeError("ReplaySource.open() fehlt")
        ground_truth = {"text": self.clip.get("ground_truth_text")}
        for entry in self.clip["frames"]:
            path = self.directory / entry["file"]
            image = cv2.imread(str(path))
            if image is None:
                raise FileNotFoundError(f"Clipbild nicht lesbar: {path}")
            yield Frame(
                frame_sequence=int(entry["frame_sequence"]),
                image=image,
                capture_timestamp=_replayed(entry["capture_timestamp"]),
                source_id=self.source_id,
                raw_metadata={
                    **entry.get("metadata", {}),
                    "ground_truth": ground_truth,
                    "device_id": self.clip.get("device_id"),
                    "clip_id": self.clip.get("clip_id"),
                },
            )


def _replayed(raw: dict[str, Any]) -> Timestamp:
    """Aufgezeichneten Zeitstempel ehrlich zurueckgeben.

    Trug er eine Zeitaussage, wird er REPLAY_RECORDED - der Enum-Wert existiert
    genau dafuer. Trug er keine (SYNTHETIC, FILE_MTIME), bleibt er, was er war:
    ein Replay darf aus einer synthetischen Aufnahme keine Zeitaussage machen.
    """
    base = TimeBaseKind(raw["base"])
    if base.carries_time_information:
        base = TimeBaseKind.REPLAY_RECORDED
    return Timestamp(
        value_ns=int(raw["value_ns"]),
        base=base,
        semantics=TimestampSemantics(raw.get("semantics", "unknown")),
        uncertainty_ns=raw.get("uncertainty_ns"),
    )
```

- [ ] **Schritt 4: Tests laufen lassen, grün bestätigen**

```bash
./.venv/bin/pytest tests/test_replay_source.py -q && ./.venv/bin/ruff check src tests
```
Erwartet: 5 passed, ruff sauber.

- [ ] **Schritt 5: ROADMAP und CHANGELOG nachziehen**

In `docs/ROADMAP.md` die P0-Zeile
`- [ ] folder://, video://, replay://, picamera2://, imx500:// — Registry vorhanden, Implementierungen noch nicht`
so ändern, dass `replay://` als vorhanden geführt wird und die übrigen offen bleiben.

In `CHANGELOG.md` oben einen Abschnitt nach dem Hausschema (Problem / Änderung /
Konsequenz) einfügen: Problem = Erkennungsänderungen sind mangels Datensatz
nicht belegbar; Änderung = `replay://` liest Clips mit **einem** Label je Clip
zurück; Konsequenz = Labelkosten sinken von „pro Bild" auf „pro Clip", P2 wird
mit derselben Laborstunde erfüllt.

- [ ] **Schritt 6: Committen**

```bash
git add src/dispread/frames/replay_source.py tests/test_replay_source.py docs/ROADMAP.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
replay:// implementiert: Clips mit einem Label je Clip zurueckspielen

Ohne realen, gelabelten Datensatz ist keine Decoder-Aenderung belegbar. Ein
Clip traegt genau ein getipptes Label fuer alle seine Frames; aufgezeichnete
Sensorzeitstempel werden als REPLAY_RECORDED gefuehrt, synthetische bleiben
ohne Zeitaussage.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Clipaufnahme in der Workbench

**Dateien:**
- Ändern: `src/dispread/workbench/controller.py` (Ops `clip.start`/`clip.stop`,
  Schreib-Thread, Zustand im `snapshot()`)
- Ändern: `src/dispread/workbench/static/index.html`,
  `src/dispread/workbench/static/workbench.js`
- Ändern: `tests/test_workbench.py`
- Ändern: `CHANGELOG.md`

**Schnittstellen:**
- Nutzt: das Clipformat aus Task 1 (`CLIP_SCHEMA_VERSION`), `atomic_json` aus
  `dispread.workbench.profiles`.
- Liefert: Ops `clip.start` (Args `{device_id, ground_truth_text, seconds}`) und
  `clip.stop` (keine Args); `snapshot()["clip"]` mit
  `{"state": "idle"|"recording", "frames": int, "dropped": int, "path": str|None, "seconds_left": float|None}`.

**Entwurfsentscheidung:** Das PNG-Schreiben läuft in einem eigenen Thread über
eine begrenzte Queue. Ein PNG von 960×720 kostet 20–30 ms; im `publish()`-Pfad
würde das die Vorschau bei 15 fps stehenbleiben lassen. Läuft die Queue voll,
wird **gezählt**, nicht stillschweigend verworfen — `dropped_frames` steht im
`clip.json` und im Status.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

An `tests/test_workbench.py` anhängen (die vorhandenen Fixtures dieser Datei
weiterverwenden — nicht neu erfinden):

```python
def test_clip_schreibt_manifest_mit_einem_label_fuer_alle_frames(tmp_path):
    controller = _confirmed_controller(tmp_path)      # vorhandener Helfer
    controller.command("mode", {"value": "annotate"})
    controller.command(
        "clip.start",
        {"device_id": "geraet-1", "ground_truth_text": "28,80", "seconds": 60},
    )
    for _ in range(3):
        controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})
    controller.command("clip.stop")
    controller.drain_clip_writer()                    # deterministisch statt sleep

    clips = sorted((tmp_path / "clips").iterdir())
    assert len(clips) == 1
    manifest = json.loads((clips[0] / "clip.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["ground_truth_text"] == "28,80"
    assert manifest["device_id"] == "geraet-1"
    assert len(manifest["frames"]) == 3
    assert manifest["dropped_frames"] == 0
    for entry in manifest["frames"]:
        assert (clips[0] / entry["file"]).exists()


def test_clip_braucht_bestaetigte_geometrie_und_geraeteangabe(tmp_path):
    controller = _controller(tmp_path)                # unbestaetigt
    with pytest.raises(ValueError, match="bestaetigt"):
        controller.command("clip.start", {"device_id": "g", "ground_truth_text": "1", "seconds": 5})

    controller = _confirmed_controller(tmp_path)
    controller.command("mode", {"value": "annotate"})
    with pytest.raises(ValueError, match="Geraetekennung"):
        controller.command("clip.start", {"device_id": "", "ground_truth_text": "1", "seconds": 5})
    with pytest.raises(ValueError, match="Sollwert"):
        controller.command("clip.start", {"device_id": "g", "ground_truth_text": "  ", "seconds": 5})


def test_clip_ist_ueber_replay_wieder_lesbar(tmp_path):
    """Aufnahme und Wiedergabe muessen dasselbe Format meinen."""
    controller = _confirmed_controller(tmp_path)
    controller.command("mode", {"value": "annotate"})
    controller.command(
        "clip.start", {"device_id": "geraet-1", "ground_truth_text": "11,00", "seconds": 60}
    )
    controller.publish(_frame(), {"timebase": "synthetic", "uncertainty_ns": None})
    controller.command("clip.stop")
    controller.drain_clip_writer()

    clip = next(iter(sorted((tmp_path / "clips").iterdir())))
    source = open_source(f"replay://{clip}")
    source.open()
    frames = list(source.frames())
    source.close()
    assert len(frames) == 1
    assert frames[0].raw_metadata["ground_truth"]["text"] == "11,00"
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_workbench.py -q -k clip
```
Erwartet: `ValueError: Unbekannter Befehl: clip.start`.

- [ ] **Schritt 3: Implementierung schreiben**

In `src/dispread/workbench/controller.py`:

```python
#: Wieviele Bilder hoechstens auf das Schreiben warten duerfen. Ein PNG von
#: 960x720 kostet 20-30 ms; im publish()-Pfad wuerde das die Vorschau bei
#: 15 fps anhalten. Laeuft die Queue voll, wird gezaehlt statt still verworfen.
CLIP_QUEUE_DEPTH = 24

#: Obergrenze je Clip. Ein Kalibrierpunkt braucht Sekunden, nicht Minuten;
#: ohne Grenze laeuft eine vergessene Aufnahme die Platte voll.
CLIP_MAX_SECONDS = 120
```

Im `__init__`:

```python
self.clip = None              # laufende Aufnahme oder None
self.clip_queue = None        # queue.Queue der zu schreibenden Bilder
self.clip_thread = None
```

Neue Ops in `command()` (innerhalb `self.lock`, im `elif`-Block vor `else`):

```python
elif op == "clip.start":
    if not self.config["confirmed"] or not self.snapshot()["live"]:
        raise ValueError("Clipaufnahme braucht bestaetigte Geometrie und Livebild")
    if self.mode not in ("setup", "annotate"):
        raise ValueError("Clipaufnahme laeuft in setup oder annotate")
    if self.clip is not None:
        raise ValueError("Clipaufnahme laeuft bereits")
    device_id = str(args.get("device_id", "")).strip()
    text = str(args.get("ground_truth_text", "")).strip()
    if not device_id:
        # Splitgrenze ist die Geraeteinstanz, nie der Frame (ROADMAP).
        # Ohne Kennung ist der Datensatz fuer einen Gruppensplit wertlos.
        raise ValueError("Geraetekennung fehlt")
    if not text:
        raise ValueError("Sollwert fehlt - ein Clip ohne Label ist kein Testdatum")
    seconds = float(args.get("seconds", 5.0))
    if not 0.5 <= seconds <= CLIP_MAX_SECONDS:
        raise ValueError(f"Clipdauer 0.5..{CLIP_MAX_SECONDS} s")
    self._clip_start(device_id, text, seconds)
elif op == "clip.stop":
    self._clip_stop()
```

Neue Methoden:

```python
def _clip_start(self, device_id, text, seconds):
    target = self.root / "clips" / uuid.uuid4().hex
    target.mkdir(parents=True)
    self.clip_queue = queue.Queue(maxsize=CLIP_QUEUE_DEPTH)
    self.clip = {
        "path": target,
        "device_id": device_id,
        "ground_truth_text": text,
        "deadline": time.monotonic() + seconds,
        "profile": copy.deepcopy(self.config),
        "profile_name": self.name,
        "calibrated_on_frame_sequence": self.calibrated_on,
        "entries": [],
        "dropped": 0,
    }
    self.clip_thread = threading.Thread(target=self._clip_writer, name="clip", daemon=True)
    self.clip_thread.start()
    self.log("info", f"Clipaufnahme {target.name} gestartet: {device_id}, Sollwert {text!r}")

def _clip_writer(self):
    """Bilder schreiben, ohne den Bildpfad aufzuhalten."""
    while True:
        item = self.clip_queue.get()
        if item is None:
            return
        path, image = item
        if not cv2.imwrite(str(path), image):
            self.log("error", f"Clipbild nicht geschrieben: {path}")

def _clip_stop(self):
    if self.clip is None:
        return
    clip, self.clip = self.clip, None
    if self.clip_queue is not None:
        self.clip_queue.put(None)
    atomic_json(
        clip["path"] / "clip.json",
        {
            "schema_version": CLIP_SCHEMA_VERSION,
            "clip_id": clip["path"].name,
            "device_id": clip["device_id"],
            "ground_truth_text": clip["ground_truth_text"],
            "profile": clip["profile"],
            "profile_name": clip["profile_name"],
            "calibrated_on_frame_sequence": clip["calibrated_on_frame_sequence"],
            "dropped_frames": clip["dropped"],
            "created_at": datetime.now(UTC).isoformat(),
            "created_timebase": "UTC",
            "frames": clip["entries"],
        },
    )
    self.log(
        "info",
        f"Clip {clip['path'].name}: {len(clip['entries'])} Bilder, {clip['dropped']} verworfen",
    )

def drain_clip_writer(self):
    """Auf den Schreib-Thread warten. Fuer Tests - kein Bedienbefehl."""
    if self.clip_thread is not None:
        self.clip_thread.join(timeout=10)
        self.clip_thread = None
```

In `publish()`, im gesperrten Abschnitt am Ende (dort, wo `self.raw` gesetzt
wird), nach `self.sequence += 1`:

```python
if self.clip is not None:
    if time.monotonic() >= self.clip["deadline"]:
        self._clip_stop()
    else:
        name = f"frame_{len(self.clip['entries']) + 1:06d}.png"
        try:
            self.clip_queue.put_nowait((self.clip["path"] / name, image))
        except queue.Full:
            # Gezaehlt, nicht stillschweigend verworfen - die Zahl steht im
            # clip.json und macht einen luecken haften Clip erkennbar.
            self.clip["dropped"] += 1
        else:
            self.clip["entries"].append(
                {
                    "file": name,
                    "frame_sequence": self.sequence,
                    "capture_timestamp": {
                        "value_ns": int(metadata.get("SensorTimestamp", 0)),
                        "base": metadata.get("timebase", TimeBaseKind.FILE_MTIME.value),
                        "semantics": metadata.get("timestamp_semantics", "unknown"),
                        "uncertainty_ns": metadata.get("uncertainty_ns"),
                    },
                    "metadata": copy.deepcopy(metadata),
                }
            )
```

`snapshot()` um das Feld ergänzen:

```python
"clip": {
    "state": "idle" if self.clip is None else "recording",
    "frames": 0 if self.clip is None else len(self.clip["entries"]),
    "dropped": 0 if self.clip is None else self.clip["dropped"],
    "path": None if self.clip is None else str(self.clip["path"]),
    "seconds_left": None if self.clip is None else max(0.0, self.clip["deadline"] - time.monotonic()),
},
```

`close()` muss eine laufende Aufnahme sauber abschließen — vor `self.stop.set()`:

```python
with self.lock:
    self._clip_stop()
```

Neue Importe oben in `controller.py`: `queue`, und
`from dispread.frames.replay_source import CLIP_SCHEMA_VERSION`.
`self.calibrated_on = None` im `__init__` ergänzen (Task 5 setzt es).

- [ ] **Schritt 4: Tests laufen lassen, grün bestätigen**

```bash
./.venv/bin/pytest tests/test_workbench.py -q && ./.venv/bin/ruff check src tests
```

- [ ] **Schritt 5: Bedienoberfläche ergänzen**

In `index.html` einen Block analog zum vorhandenen `ground-truth`-Overlay
anlegen (`clip-panel` mit Feldern Gerätekennung, Sollwert, Dauer und zwei
Knöpfen). In `workbench.js` zwei Handler ergänzen, die `clip.start`/`clip.stop`
aufrufen, und im Statusbereich `state.clip.frames`/`state.clip.seconds_left`
anzeigen. Kein neuer Bestätigungsmechanismus — die Aufnahme ändert nichts an
`confirmed`.

```bash
node --check src/dispread/workbench/static/workbench.js
```

- [ ] **Schritt 6: CHANGELOG und Committen**

CHANGELOG: Problem = Labelkosten pro Bild; Änderung = Clipaufnahme mit einem
Label je Clip, Schreiben im eigenen Thread, verworfene Bilder werden gezählt;
Konsequenz = ein Kalibrierpunkt kostet einen Tippvorgang statt N Annotationen.

```bash
git add src/dispread/workbench/controller.py src/dispread/workbench/static/ tests/test_workbench.py CHANGELOG.md
git commit -m "$(cat <<'EOF'
Clipaufnahme in der Workbench: ein getipptes Label je Clip

Der Bediener stellt einen Wert ein, tippt ihn einmal und nimmt wenige Sekunden
auf; jeder Frame traegt dasselbe Label. Bilder werden in einem eigenen Thread
geschrieben, damit die 15-fps-Vorschau nicht auf PNG-Kodierung wartet;
verworfene Bilder werden gezaehlt und im Manifest gefuehrt statt still zu
verschwinden.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Benchmark mit dreigeteilter Metrik

**Dateien:**
- Neu: `src/dispread/benchmark.py`
- Neu: `scripts/ocr-benchmark.py`
- Neu: `tests/test_benchmark.py`
- Ändern: `docs/VALIDATION.md`, `CHANGELOG.md`

**Schnittstellen:**
- Nutzt: `ReplaySource` (Task 1), `SevenSegmentReader`, `rectify`, `crop_box`.
- Liefert:

```python
@dataclass(frozen=True, slots=True)
class Outcome:
    source_id: str
    device_id: str
    expected: str
    correct: int
    wrong: int
    rejected: int
    #: Fehlerklasse -> Anzahl. Schluessel: sign, decimal, digit, count
    wrong_classes: dict[str, int]
    #: Ablehnungsgrund -> Anzahl, aus den Reader-Diagnosen
    reject_classes: dict[str, int]
    #: Bis zu fuenf Beispiele "soll -> ist" fuer die Fehleranalyse
    examples: tuple[str, ...]

def normalise(text: str) -> str
def classify(expected: str, got: str) -> str
def read_frame(image, profile, reader) -> ReadResult
def evaluate_clip(directory: Path, reader: ValueReader) -> Outcome
def evaluate_annotation(directory: Path, reader: ValueReader) -> Outcome
def evaluate_set(directories: Sequence[Path], reader: ValueReader) -> dict[str, Any]
def assert_disjoint_devices(development: Sequence[Path], test: Sequence[Path]) -> None
```

**Wichtig — die Metrik wird auf Leserebene gemessen, nicht auf Gate-Ebene.**
Die Freigabe kann nur zusätzlich ablehnen, nie zusätzlich annehmen. Die
Leserzahl ist damit die konservative Obergrenze der falschen Annahmen. Das
gehört in den Docstring.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Neue Datei `tests/test_benchmark.py`:

```python
"""Benchmark: die gefaehrliche Zahl ist die falsche Annahme, nicht die Ablehnung."""

from __future__ import annotations

import pytest

from dispread.benchmark import assert_disjoint_devices, classify, normalise


def test_normalise_akzeptiert_komma_und_punkt():
    """Bediener tippen '28,80'; der Leser liefert '28.80'."""
    assert normalise("28,80") == normalise("28.80") == "2880"
    assert normalise("-000.13") == "-00013"


@pytest.mark.parametrize(
    ("expected", "got", "klasse"),
    [
        ("-1234", "1234", "sign"),
        ("1234", "-1234", "sign"),
        ("1234", "1235", "digit"),
        ("1234", "123", "count"),
        ("1234", "1234", "correct"),
    ],
)
def test_fehlerklassen_werden_getrennt_gefuehrt(expected, got, klasse):
    """Konzept.md §7 nennt fehlendes Minuszeichen als eigenstaendigen Fehler."""
    assert classify(expected, got) == klasse


def test_gruppensplit_wird_erzwungen(tmp_path):
    """Splitgrenze ist die Geraeteinstanz, nie der Frame (ROADMAP)."""
    development = _clip(tmp_path / "a", device="geraet-1")
    test = _clip(tmp_path / "b", device="geraet-1")
    with pytest.raises(ValueError, match="geraet-1"):
        assert_disjoint_devices([development], [test])

    other = _clip(tmp_path / "c", device="geraet-2")
    assert_disjoint_devices([development], [other])  # wirft nicht
```

(`_clip` ist derselbe Helfer wie in `tests/test_replay_source.py`; per
`from tests.test_replay_source import _write_clip` wiederverwenden oder in
`tests/conftest.py` als Fixture hochziehen — nicht duplizieren.)

Dazu ein Test, der die ganze Kette gegen einen synthetisch erzeugten Clip
fährt und die dreigeteilte Metrik prüft:

```python
def test_synthetischer_clip_wird_vollstaendig_korrekt_gelesen(tmp_path):
    from dispread.benchmark import evaluate_clip
    from dispread.ocr.sevenseg import SevenSegmentReader

    clip = _synthetic_clip(tmp_path / "syn", value=12.34, frames=5)
    outcome = evaluate_clip(clip, SevenSegmentReader())
    assert (outcome.correct, outcome.wrong, outcome.rejected) == (5, 0, 0)
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_benchmark.py -q
```
Erwartet: `ModuleNotFoundError: No module named 'dispread.benchmark'`.

- [ ] **Schritt 3: Implementierung schreiben**

Neue Datei `src/dispread/benchmark.py`. Kernstücke:

```python
def normalise(text: str) -> str:
    """Getippten oder gelesenen Wert auf vergleichbare Ziffernfolge bringen.

    Bediener tippen mit Komma ("28,80"), der Leser liefert einen Punkt. Der
    Dezimaltrenner selbst wird entfernt - seine *Position* prueft die
    Layoutstufe, nicht der Zeichenvergleich.
    """
    text = text.strip().replace(",", "").replace(".", "").replace(" ", "")
    return text


def classify(expected: str, got: str) -> str:
    """Fehlerklasse einer Abweichung. Konzept.md §7 verlangt getrennte Klassen."""
    if expected == got:
        return "correct"
    if expected.lstrip("-") == got.lstrip("-"):
        return "sign"
    if len(expected.lstrip("-")) != len(got.lstrip("-")):
        return "count"
    return "digit"
```

Das Lesen eines Einzelbildes muss **exakt** den Weg des echten Pfades gehen —
`rectify` auf `CROP_SIZE`, dann `crop_box` mit der `ocr_box`. Ein abweichender
Weg würde etwas anderes messen als der Betrieb:

```python
def read_frame(image, profile, reader):
    """Ein Bild genau so lesen wie Controller._read() es im Betrieb tut."""
    layout = DisplayLayout.from_dict(profile["layout"])
    height, width = image.shape[:2]
    quad = tuple((float(x * width), float(y * height)) for x, y in profile["roi_quad"])
    crop = rectify(image, quad, target_size=CROP_SIZE)
    return reader.read(crop_box(crop.image, profile["ocr_box"]), layout)


def _tally(expected, read, examples, wrong_classes, reject_classes):
    """Ein Leseergebnis einsortieren; liefert 'correct', 'wrong' oder 'rejected'.

    Die gefaehrliche Spalte ist 'wrong': eine Ablehnung kostet einen Messwert,
    eine falsche Annahme verfaelscht eine Kalibrierung.
    """
    if read.value is None:
        for reason in _reject_reasons(read):
            reject_classes[reason] = reject_classes.get(reason, 0) + 1
        return "rejected"
    got = normalise(read.raw_text)
    klasse = classify(expected, got)
    if klasse == "correct":
        return "correct"
    wrong_classes[klasse] = wrong_classes.get(klasse, 0) + 1
    if len(examples) < 5:
        examples.append(f"{expected} -> {got}")
    return "wrong"


def _reject_reasons(read):
    """Warum wurde abgelehnt? Aus den Diagnosen des Lesers, nicht geraten."""
    reasons = [f"state:{flag}" for flag in sorted(read.status_flags)]
    if int(read.diagnostics.get("unreadable_cells", 0)):
        reasons.append("unreadable_cells")
    if not read.sign_region_readable:
        reasons.append("sign_region_unreadable")
    if not read.decimal_point_detected:
        reasons.append("decimal_point_unknown")
    return reasons or ["no_value"]


def evaluate_clip(directory, reader):
    source = open_source(f"replay://{directory}")
    source.open()
    clip = source.describe()
    expected = normalise(clip["ground_truth_text"])
    profile = json.loads((directory / "clip.json").read_text())["profile"]
    counts = {"correct": 0, "wrong": 0, "rejected": 0}
    wrong_classes: dict[str, int] = {}
    reject_classes: dict[str, int] = {}
    examples: list[str] = []
    try:
        for frame in source.frames():
            read = read_frame(frame.image, profile, reader)
            counts[_tally(expected, read, examples, wrong_classes, reject_classes)] += 1
    finally:
        source.close()
    return Outcome(
        source_id=source.source_id,
        device_id=clip["device_id"],
        expected=expected,
        correct=counts["correct"],
        wrong=counts["wrong"],
        rejected=counts["rejected"],
        wrong_classes=wrong_classes,
        reject_classes=reject_classes,
        examples=tuple(examples),
    )
```

`evaluate_annotation` macht dasselbe für ein einzelnes
`var/workbench/annotations/<id>/` und überspringt Verzeichnisse ohne
`ground_truth_text` oder ohne `profile.layout` — eine Altannotation nach
Schema 1 hat kein `layout` (im Datenbestand ist das genau
`0dd690423ad04ee2…`). Das Profil steht dort unter `annotation["profile"]`,
`roi_quad`/`ocr_box` liegen zusätzlich auf oberster Ebene; letztere gelten,
weil sie die bestätigte Geometrie dieser Aufnahme sind.

```python
def assert_disjoint_devices(development, test):
    """Splitgrenze ist die Geraeteinstanz, nie der Frame (ROADMAP, Konzept §9).

    Benachbarte Frames derselben Aufnahme in Entwicklung und Test wuerden das
    Ergebnis zu optimistisch aussehen lassen. Das hier ist der Test, der bei
    Verletzung fehlschlaegt - nicht nur eine Regel in der Doku.
    """
    left = {_device_of(path) for path in development}
    right = {_device_of(path) for path in test}
    shared = sorted(left & right)
    if shared:
        raise ValueError(
            "Dieselbe Geraeteinstanz steht in Entwicklungs- und Testsatz: " + ", ".join(shared)
        )
```

`scripts/ocr-benchmark.py` ist eine dünne CLI:

```python
#!/usr/bin/env python3
"""Erkennungsqualitaet messen. Schreibt nichts in die Doku - das macht ein Mensch."""
# Aufruf:
#   ./.venv/bin/python scripts/ocr-benchmark.py --annotations var/workbench/annotations
#   ./.venv/bin/python scripts/ocr-benchmark.py --dev 'var/workbench/clips/a*' --test 'var/workbench/clips/b*'
```

- [ ] **Schritt 4: Tests laufen lassen, grün bestätigen**

```bash
./.venv/bin/pytest tests/test_benchmark.py -q && ./.venv/bin/ruff check src tests
```

- [ ] **Schritt 5: Ausgangsmessung erzeugen und in VALIDATION.md festhalten**

```bash
./.venv/bin/python scripts/ocr-benchmark.py --annotations var/workbench/annotations
```

Erwartet (in dieser Sitzung bereits gemessen, muss reproduziert werden):
`korrekt=5  falsch angenommen=0  abgelehnt=1`, abgelehnt ist `8a18ee05`.

Neuer Abschnitt in `docs/VALIDATION.md`: „Ausgangsmessung `sevenseg/2` auf den
realen Annotationen (2026-09-11)" mit diesen Zahlen, der Zahl der
auswertbaren Annotationen (6 von 9), dem Hinweis auf **eine** Geräteinstanz
und dem ausdrücklichen Satz, dass dieser Satz damit ein **Entwicklungs-**, kein
Testsatz ist.

- [ ] **Schritt 6: CHANGELOG und Committen**

```bash
git add src/dispread/benchmark.py scripts/ocr-benchmark.py tests/test_benchmark.py docs/VALIDATION.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
Benchmark mit dreigeteilter Metrik und erzwungenem Geraete-Gruppensplit

Eine hoehere Trefferquote allein sagt nichts; gefaehrlich ist die falsche
Annahme. Der Benchmark fuehrt korrekt/falsch/abgelehnt getrennt, schluesselt
nach Fehlerklasse auf (Vorzeichen, Stellenzahl, Ziffer) und verweigert die
Auswertung, wenn dieselbe Geraeteinstanz in Entwicklungs- und Testsatz steht.
Ausgangsmessung: 5 korrekt, 0 falsch, 1 abgelehnt auf sechs realen
Annotationen eines Geraets.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase B — Einrichtung: Geometrie aus dem getippten Wert

## Task 4: `fit_layout` als reine Funktion

**Dateien:**
- Neu: `src/dispread/ocr/autofit.py`
- Neu: `tests/test_autofit.py`
- Ändern: `CHANGELOG.md`

**Schnittstellen:**
- Nutzt: `DisplayLayout`, `SevenSegmentReader`, `ReadResult`, `crop_box`-Logik
  (nachgebaut als reine Funktion, damit `autofit` nicht von der Workbench abhängt).
- Liefert:

```python
@dataclass(frozen=True, slots=True)
class AutofitResult:
    matched: bool
    layout: DisplayLayout
    ocr_box: tuple[float, float, float, float]
    #: Kleinster Segmentabstand zur Entscheidungsschwelle im besten Treffer.
    #: KEINE Fehlerwahrscheinlichkeit - nur ein Trennschaerfemass.
    separation: float
    #: Derselbe Wert fuer den zweitbesten, deutlich anderen Parametersatz.
    runner_up: float
    #: True, wenn bester und zweitbester Satz sich kaum unterscheiden - das
    #: Optimum ist dann flach und die Geometrie unterbestimmt.
    flat_optimum: bool
    evaluated: int
    reason: str | None

def parse_expected(text: str) -> tuple[str, bool, int, int]
def fit_layout(crop, text, layout, ocr_box, *, reader=None) -> AutofitResult
```

`parse_expected` liefert immer eine ganze Zahl Nachkommastellen — `0`, wenn
kein Trennzeichen getippt wurde. Nicht `None`: `DisplayLayout.decimals = None`
bedeutet „Dezimalpunkt frei, muss erkannt werden" und wird von der Freigabe
abgelehnt (`decimal_point_unknown`). Ein getipptes `1234` heißt aber, dass die
Anzeige eine ganze Zahl zeigt — das ist eine Aussage, keine Unbekannte.

**Zielfunktion — das ist der Kern dieser Aufgabe.** Nicht „stimmt die
Ziffernfolge", sondern: *unter allen Parametersätzen, die exakt richtig
dekodieren, den mit der größten Trennschärfe wählen.* Begründung aus der
Messung dieser Sitzung: `thickness=0.20/inset=0.05` und
`thickness=0.12/inset=0.10` erreichen auf sechs Bildern dieselbe Punktzahl.
Ein Autofit, der auf „stimmt" optimiert, nimmt den, den er zuerst erreicht,
und der Bediener bestätigt eine zufällig gewählte Geometrie. Als Trennschärfe
wird `read.diagnostics["min_margin"]` verwendet — das vorhandene, genau dafür
gedachte Maß (Abstand der knappsten Segmentmessung zur Schwelle, normiert).

**Suchverfahren:** Koordinatenabstieg, zwei Durchläufe über acht Parameter mit
je fest aufgezählten Kandidaten. Rund 100 Auswertungen, deterministisch, ohne
Zufall. Ein Koordinatenabstieg kann in einem lokalen Optimum landen; ein
erfolgloser Autofit meldet deshalb `matched=False` und liefert das
**unveränderte** Eingabelayout zurück — nie eine Teilvermutung.

**Ableitung aus dem Text:** `digits` und `decimals` kommen direkt aus dem
getippten Wert und werden nicht gesucht. `has_sign` wird **nur** auf `True`
gesetzt, wenn der Text ein Minuszeichen enthält — ein positiv angezeigter Wert
beweist nicht, dass die Anzeige keine Vorzeichenstelle hat. Sonst bleibt die
Einstellung des Bedieners stehen.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Neue Datei `tests/test_autofit.py`:

```python
"""Rastergeometrie aus einem einmal getippten Sollwert bestimmen."""

from __future__ import annotations

import pytest

from dispread.frames.synthetic_source import render_display
from dispread.layout import DisplayLayout
from dispread.ocr.autofit import fit_layout, parse_expected


@pytest.mark.parametrize(
    ("text", "digits_text", "minus", "digits", "decimals"),
    [
        ("28,80", "2880", False, 4, 2),
        ("28.80", "2880", False, 4, 2),
        ("-000.13", "00013", True, 5, 2),
        ("1234", "1234", False, 4, 0),
    ],
)
def test_getippter_wert_wird_zerlegt(text, digits_text, minus, digits, decimals):
    assert parse_expected(text) == (digits_text, minus, digits, decimals)


def test_positiver_wert_beweist_keine_fehlende_vorzeichenstelle():
    """Nur ein Minuszeichen beweist eine Vorzeichenstelle - seine Abwesenheit nicht."""
    layout = DisplayLayout(digits=4, decimals=2, has_sign=True, unit="V")
    image, _, area = render_display(28.80, layout)
    x, y, w, h = area
    result = fit_layout(image[y : y + h, x : x + w], "28,80", layout, (0.0, 0.0, 1.0, 1.0))
    assert result.layout.has_sign is True  # unveraendert uebernommen


def test_autofit_findet_ein_abweichendes_raster(recwarn):
    """Start mit den Defaults, Anzeige mit deutlichem Ziffernabstand."""
    real = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V", digit_gap_ratio=0.65)
    image, _, area = render_display(12.34, real)
    x, y, w, h = area
    crop = image[y : y + h, x : x + w]

    start = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")  # gap 0.0
    assert start.digit_gap_ratio == 0.0

    result = fit_layout(crop, "12,34", start, (0.0, 0.0, 1.0, 1.0))
    assert result.matched, result.reason
    assert result.layout.digit_gap_ratio == pytest.approx(0.65, abs=0.2)
    assert result.separation > 0.0


def test_autofit_ist_deterministisch():
    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V", digit_gap_ratio=0.65)
    image, _, area = render_display(12.34, layout)
    x, y, w, h = area
    crop = image[y : y + h, x : x + w]
    start = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")
    first = fit_layout(crop, "12,34", start, (0.0, 0.0, 1.0, 1.0))
    second = fit_layout(crop, "12,34", start, (0.0, 0.0, 1.0, 1.0))
    assert first == second


def test_erfolgloser_autofit_liefert_das_eingabelayout_unveraendert():
    """Kein Teilraten: was nicht passt, wird als nicht passend gemeldet."""
    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")
    image, _, area = render_display(12.34, layout)
    x, y, w, h = area
    result = fit_layout(image[y : y + h, x : x + w], "99,99", layout, (0.0, 0.0, 1.0, 1.0))
    assert not result.matched
    assert result.layout == layout
    assert result.reason
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_autofit.py -q
```
Erwartet: `ModuleNotFoundError: No module named 'dispread.ocr.autofit'`.

- [ ] **Schritt 3: Implementierung schreiben**

Neue Datei `src/dispread/ocr/autofit.py`:

```python
"""Rastergeometrie aus einem einmal getippten Sollwert bestimmen.

Der Bediener bestaetigt die Anzeige und tippt einmal, was darauf steht. Statt
`ziffernabstand`, `vorzeichenbreite` und die uebrigen Verhaeltnisse von Hand zu
justieren, sucht diese Funktion den Parametersatz, der genau diesen Text
dekodiert - und unter mehreren passenden den mit der groessten Trennschaerfe.

Warum Trennschaerfe und nicht blosse Uebereinstimmung: an sechs realen
Aufnahmen eines Geraets erreichen `thickness=0.20/inset=0.05` und
`thickness=0.12/inset=0.10` dieselbe Trefferzahl (Messung 2026-09-11,
docs/VALIDATION.md). Ein Autofit auf "stimmt" wuerde davon einen beliebigen
nehmen. Passt keiner, wird das gemeldet - nichts wird teilweise geraten.

Angepasst wird auf dem Bestaetigungsbild. Bewertet wird spaeter auf
Clipframes, die diese Anpassung nie gesehen haben (OQ-23 verbietet
Nachstimmen und Bewerten am selben Bild).
"""
```

Kernstücke:

```python
#: Kandidaten je Parameter. Bewusst fest aufgezaehlt statt kontinuierlich
#: optimiert: die Suche bleibt deterministisch und nachvollziehbar.
_CANDIDATES: dict[str, tuple[float, ...]] = {
    "digit_gap_ratio": (0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0, 1.4),
    "sign_cell_ratio": (0.3, 0.4, 0.5, 0.6, 0.8, 1.0),
    "thickness_ratio": (0.08, 0.10, 0.12, 0.14, 0.16, 0.20, 0.25),
    "inset_ratio": (0.0, 0.05, 0.10, 0.15, 0.20),
}
#: Verschiebung und Skalierung des OCR-Rahmens, relativ zu seiner eigenen
#: Groesse. Eng begrenzt: der Rahmen ist vom Bediener bestaetigt, der Autofit
#: zieht ihn nur nach, er sucht ihn nicht neu (sonst erbt er die
#: Haupt-/Nebenanzeige-Verwechslung aus OQ-25).
_BOX_SHIFTS = (-0.06, -0.03, 0.0, 0.03, 0.06)
_BOX_SCALES = (0.90, 0.95, 1.0, 1.05, 1.10)
_PASSES = 2
#: Unterschied in der Trennschaerfe, unterhalb dessen das Optimum als flach
#: gilt. Vorabdefault.
_FLAT_DELTA = 0.05


def parse_expected(text: str) -> tuple[str, bool, int, int]:
    """'-000,13' -> ('00013', True, 5, 2).

    Komma und Punkt gelten beide als Dezimaltrenner - Bediener tippen im
    deutschen Layout mit Komma, der Leser liefert einen Punkt.
    """
    cleaned = text.strip().replace(",", ".").replace(" ", "")
    minus = cleaned.startswith("-")
    body = cleaned.lstrip("+-")
    if not body or not all(c.isdigit() or c == "." for c in body) or body.count(".") > 1:
        raise ValueError(f"Unlesbarer Sollwert: {text!r}")
    whole, _, fraction = body.partition(".")
    digits = whole + fraction
    if not digits.isdigit():
        raise ValueError(f"Unlesbarer Sollwert: {text!r}")
    return digits, minus, len(digits), len(fraction) if "." in body else 0
```

Die Suche selbst:

```python
def fit_layout(crop, text, layout, ocr_box, *, reader=None):
    reader = reader or SevenSegmentReader()
    expected, minus, digits, decimals = parse_expected(text)

    base = replace(
        layout,
        digits=digits,
        decimals=decimals,
        # Nur ein Minuszeichen beweist eine Vorzeichenstelle. Seine Abwesenheit
        # beweist nichts - die Einstellung des Bedieners bleibt stehen.
        has_sign=True if minus else layout.has_sign,
    )

    state = {name: getattr(base, name) for name in _CANDIDATES}
    box = tuple(float(v) for v in ocr_box)
    best = _evaluate(crop, reader, base, state, box, expected, minus)
    runner_up = -1.0
    evaluated = 1

    for _ in range(_PASSES):
        for name, values in _CANDIDATES.items():
            for value in values:
                trial = dict(state, **{name: value})
                score = _evaluate(crop, reader, base, trial, box, expected, minus)
                evaluated += 1
                if score > best:
                    runner_up, best, state = best, score, trial
                elif score > runner_up:
                    runner_up = score
        for box_candidate in _box_candidates(ocr_box):
            score = _evaluate(crop, reader, base, state, box_candidate, expected, minus)
            evaluated += 1
            if score > best:
                runner_up, best, box = best, score, box_candidate
            elif score > runner_up:
                runner_up = score
    ...
```

`_evaluate` liefert ein sortierbares Mass: `(-1.0)` wenn die Ziffernfolge nicht
exakt stimmt oder das Vorzeichen nicht passt, sonst `min_margin` aus den
Diagnosen. So dominiert exakte Übereinstimmung, und innerhalb der passenden
Sätze gewinnt die Trennschärfe.

`flat_optimum = matched and (best - runner_up) < _FLAT_DELTA`.

- [ ] **Schritt 4: Tests laufen lassen, grün bestätigen**

```bash
./.venv/bin/pytest tests/test_autofit.py tests/test_sevenseg.py -q && ./.venv/bin/ruff check src tests
```

- [ ] **Schritt 5: Gegen die realen Annotationen messen**

```bash
./.venv/bin/python - <<'PY'
"""Autofit gegen die vom Bediener von Hand eingestellte Geometrie halten."""
import json
from pathlib import Path

import cv2

from dispread.layout import DisplayLayout
from dispread.ocr.autofit import fit_layout
from dispread.rectify import rectify
from dispread.workbench.controller import CROP_SIZE, crop_box

for directory in sorted(Path("var/workbench/annotations").iterdir()):
    annotation = json.loads((directory / "annotation.json").read_text())
    truth = annotation.get("ground_truth_text")
    if not truth or "layout" not in annotation.get("profile", {}):
        continue
    image = cv2.imread(str(directory / annotation["image"]))
    handset = DisplayLayout.from_dict(annotation["profile"]["layout"])
    height, width = image.shape[:2]
    quad = tuple((x * width, y * height) for x, y in annotation["roi_quad"])
    crop = rectify(image, quad, target_size=CROP_SIZE)
    reader_crop = crop_box(crop.image, annotation["ocr_box"])

    # Vom Default aus starten, nicht von der bereits justierten Geometrie -
    # sonst misst der Versuch, wie gut der Bediener war, nicht den Autofit.
    start = DisplayLayout(
        digits=handset.digits, decimals=handset.decimals,
        has_sign=handset.has_sign, unit=handset.unit,
    )
    result = fit_layout(reader_crop, truth, start, tuple(annotation["ocr_box"]))
    print(
        f"{directory.name[:8]}  soll={truth:>8s}  matched={result.matched}  "
        f"trennschaerfe={result.separation:.3f} (zweitbester {result.runner_up:.3f})  "
        f"flach={result.flat_optimum}  gap={result.layout.digit_gap_ratio:.2f} "
        f"dicke={result.layout.thickness_ratio:.2f} rand={result.layout.inset_ratio:.2f}  "
        f"vs. Hand: gap={handset.digit_gap_ratio:.2f} dicke={handset.thickness_ratio:.2f}"
    )
PY
```

Zu prüfen sind drei Dinge, und **alle drei Ausgänge sind verwertbar**:

1. Findet der Autofit für `8a18ee05` (heute abgelehnt) ein Raster, das den
   Sollwert dekodiert? Wenn ja, löst Phase B einen Teil des Problems, das
   bisher der Decoder-Änderung zugeschrieben wurde.
2. Meldet er sonst ehrlich `matched=False`? Still eine falsche Geometrie zu
   liefern wäre das einzige nicht verwertbare Ergebnis.
3. Wie oft steht `flach=True`? Der Sweep dieser Sitzung lässt es erwarten; die
   Zahl entscheidet, wie prominent der Hinweis in der Bedienung sein muss.

Zahlen nach `docs/VALIDATION.md`, mit dem Hinweis, dass sie von **einer**
Geräteinstanz stammen und deshalb keine Trefferquote belegen.

- [ ] **Schritt 6: CHANGELOG und Committen**

```bash
git add src/dispread/ocr/autofit.py tests/test_autofit.py docs/VALIDATION.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
Autofit: Rastergeometrie aus einem einmal getippten Sollwert

Ersetzt das manuelle Justieren von ziffernabstand, vorzeichenbreite, Dicke und
Rand. Optimiert nicht auf blosse Uebereinstimmung, sondern unter allen exakt
passenden Parametersaetzen auf die groesste Trennschaerfe - an sechs realen
Aufnahmen erreichen zwei weit auseinanderliegende Saetze dieselbe Trefferzahl,
das Problem ist unterbestimmt. Flache Optima werden als solche gemeldet.
Findet die Suche nichts, bleibt das Eingabelayout unveraendert.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `layout.autofit` im Controller und in der Bedienung

**Dateien:**
- Ändern: `src/dispread/workbench/controller.py` (Ops `layout.autofit`,
  `layout.set_many`; `self.calibrated_on`)
- Ändern: `src/dispread/workbench/static/workbench.js`,
  `src/dispread/workbench/static/index.html`
- Ändern: `tests/test_workbench.py`, `CHANGELOG.md`
- Ändern: `docs/anleitung/10-kamera-livevorschau.md`

**Schnittstellen:**
- Nutzt: `fit_layout`, `AutofitResult` (Task 4).
- Liefert: Op `layout.autofit` mit Args `{id, quad, ocr_box, text}` →
  `{"matched": bool, "layout": {...}, "ocr_box": [...], "separation": float,
    "runner_up": float, "flat_optimum": bool, "reason": str|None,
    "preview": {"raw_text": str, "value": float|None}}`;
  Op `layout.set_many` mit Args `{values: {feld: wert}}`.

**Wie bei `ocr.suggest`: der Op wird bewusst VOR dem Controller-Lock behandelt.**
Die Suche kostet rund hundert Leseraufrufe; sie darf das Lock nicht halten —
das war die Ursache des am 2026-09-10 gemeldeten Bugs (siehe
`controller.py:408` und OQ-24).

**Bedienfluss:** Stufe B des bestehenden zweistufigen Ablaufs bekommt einen
dritten Knopf „kalibrieren". Er öffnet dasselbe Werteingabefeld, das heute nur
im `annotate`-Modus erscheint (`$('ground-truth')` in `workbench.js:377`), jetzt
auch im `setup`-Modus. Nach der Eingabe ruft der Client `layout.autofit`, zeigt
das Ergebnisraster und den damit gelesenen Wert, und erst der ✓-Klick schickt
`layout.set_many` gefolgt vom unveränderten `roi`-Op. **Der ✓-Klick bleibt die
einzige Stelle, an der `confirmed` wahr wird.**

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

```python
def test_autofit_liefert_einen_vorschlag_ohne_etwas_zu_bestaetigen(tmp_path):
    controller = _confirmed_controller(tmp_path)
    frozen = controller.command("freeze")
    before = copy.deepcopy(controller.config)

    result = controller.command(
        "layout.autofit",
        {"id": frozen["id"], "quad": frozen["quad"], "ocr_box": frozen["ocr_box"], "text": "12,34"},
    )
    assert set(result) >= {"matched", "layout", "ocr_box", "separation", "flat_optimum"}
    assert controller.config == before, "Autofit darf nichts uebernehmen"


def test_autofit_rechnet_ausserhalb_des_locks(tmp_path):
    """Wie ocr.suggest: eine lange Suche darf keine Bedieneingabe blockieren."""
    controller = _confirmed_controller(tmp_path)
    frozen = controller.command("freeze")
    released = threading.Event()

    def probe():
        with controller.lock:
            released.set()

    with _patched_slow_autofit(released):        # Suche wartet auf released
        thread = threading.Thread(target=probe)
        thread.start()
        controller.command("layout.autofit", {...})
        thread.join(timeout=5)
    assert released.is_set()


def test_layout_set_many_setzt_alle_felder_in_einer_revision(tmp_path):
    controller = _confirmed_controller(tmp_path)
    before = controller.revision
    controller.command(
        "layout.set_many",
        {"values": {"digit_gap_ratio": 0.65, "thickness_ratio": 0.12, "digits": 4}},
    )
    assert controller.revision == before + 1
    assert controller.config["layout"]["digit_gap_ratio"] == 0.65
    assert controller.config["layout"]["thickness_ratio"] == 0.12


def test_layout_set_many_lehnt_unbekannte_felder_ab(tmp_path):
    controller = _confirmed_controller(tmp_path)
    with pytest.raises(ValueError, match="Unbekanntes Layoutfeld"):
        controller.command("layout.set_many", {"values": {"gibtsnicht": 1}})
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_workbench.py -q -k "autofit or set_many"
```
Erwartet: `ValueError: Unbekannter Befehl: layout.autofit`.

- [ ] **Schritt 3: Implementierung schreiben**

In `command()`, direkt neben dem bestehenden `ocr.suggest`-Sonderfall
(`controller.py:408`):

```python
if op == "layout.autofit":
    # Wie ocr.suggest absichtlich VOR dem Lock: die Suche kostet rund hundert
    # Leseraufrufe und darf waehrenddessen keine Bedieneingabe blockieren.
    return self._autofit(args)
```

```python
def _autofit(self, args):
    """Rastervorschlag aus dem getippten Wert. Bestaetigt nichts."""
    with self.lock:
        frame = self.frames[args["id"]]
        layout = DisplayLayout.from_dict(copy.deepcopy(self.config["layout"]))
    height, width = frame["image"].shape[:2]
    quad_px = tuple((float(x * width), float(y * height)) for x, y in args["quad"])
    crop = rectify(frame["image"], quad_px, target_size=CROP_SIZE)
    reader_crop = crop_box(crop.image, args["ocr_box"])
    try:
        result = fit_layout(reader_crop, args["text"], layout, tuple(args["ocr_box"]))
    except ValueError as error:
        self.log("warn", f"Autofit: {error}")
        return {"matched": False, "reason": str(error)}

    preview = self.reader.read(crop_box(crop.image, result.ocr_box), result.layout)
    if result.matched and result.flat_optimum:
        self.log(
            "warn",
            "Autofit: mehrere deutlich verschiedene Raster lesen diesen Wert gleich gut - "
            "Geometrie ist durch ein Bild nicht eindeutig bestimmt, Raster im Bild pruefen",
        )
    with self.lock:
        self.calibrated_on = frame["sequence"] if result.matched else None
    return {
        "matched": result.matched,
        "layout": result.layout.to_dict(),
        "ocr_box": list(result.ocr_box),
        "separation": round(result.separation, 4),
        "runner_up": round(result.runner_up, 4),
        "flat_optimum": result.flat_optimum,
        "evaluated": result.evaluated,
        "reason": result.reason,
        "preview": {"raw_text": preview.raw_text, "value": preview.value},
    }
```

`layout.set_many` im gesperrten Block, nach dem Muster von `camera.set_many`:

```python
elif op == "layout.set_many":
    data = copy.deepcopy(self.config)
    for key, value in args["values"].items():
        if key not in DEFAULT["layout"]:
            raise ValueError(f"Unbekanntes Layoutfeld: {key}")
        data["layout"][key] = value
    self._change(data)
    for frame in self.frames.values():
        frame["revision"] = self.revision
        frame["profile"]["layout"] = copy.deepcopy(self.config["layout"])
```

- [ ] **Schritt 4: Tests laufen lassen, grün bestätigen**

```bash
./.venv/bin/pytest -q && ./.venv/bin/ruff check src tests examples
```

- [ ] **Schritt 5: Bedienoberfläche und Anleitung**

`index.html`: Knopf `ocr-calibrate` („kalibrieren") neben den vorhandenen
`ocr-confirm`/`ocr-toggle`; Ergebniszeile `autofit-result` mit gelesenem Wert,
Trennschärfe und — falls `flat_optimum` — einem sichtbaren Hinweis.

`workbench.js`, im Stil der vorhandenen `confirmRoi()`/`confirmOcr()`
(gleiches `editing.pending`-Muster gegen die am 2026-09-10 behobene
Race-Condition, gleiches `requestId`-Überholverfahren):

```js
async function calibrate(){
 if(editing.pending)return;
 $('ground-truth').hidden=false;$('ground-truth-input').value='';$('ground-truth-input').focus();
 editing.awaiting='autofit';
}
async function runAutofit(text){
 editing.pending='layout.autofit';const requestId=++editing.requestId;draw();
 try{
  const r=await command('layout.autofit',{id:editing.id,quad:editing.quad,ocr_box:editing.ocr_box,text});
  if(!editing||editing.requestId!==requestId)return;              // ueberholt
  if(!r.matched){log('warn','Autofit: '+(r.reason||'kein passendes Raster gefunden'));return;}
  editing.autofit=r;editing.ocr_box=r.ocr_box;                    // nur Vorschau
  if(r.flat_optimum)log('warn','Autofit: mehrere verschiedene Raster lesen diesen Wert gleich gut - Raster im Bild pruefen.');
  log('info',`Autofit: liest ${r.preview.raw_text}, Trennschaerfe ${r.separation}`);
 }catch(e){log('error',e.message);}
 finally{if(editing)editing.pending=null;draw();}
}
```

Der ✓-Knopf schickt erst das gefundene Layout, dann die unveränderte
Bestätigung — in dieser Reihenfolge, damit `roi` gegen die bereits gesetzte
Layoutrevision läuft:

```js
async function confirmOcr(){
 if(editing.pending)return;
 if(editing.autofit)await command('layout.set_many',{values:editing.autofit.layout});
 editing.pending='roi';draw();
 if(state.mode==='annotate'){$('ground-truth').hidden=false;$('ground-truth-input').value='';$('ground-truth-input').focus();return;}
 await sendRoiConfirm({});
}
```

**Achtung:** `layout.set_many` ruft `_change()` und erhöht damit
`self.revision`. Der `roi`-Op prüft `frame["revision"] != self.revision` und
würde sonst „Modus/Profil geaendert" werfen. `layout.set_many` zieht deshalb —
wie `layout.set` es schon tut (`controller.py:460`) — die Revision der
eingefrorenen Bilder mit. Das ist in Schritt 3 bereits so implementiert und
gehört mit einem Test abgesichert:

```python
def test_autofit_uebernahme_macht_das_eingefrorene_bild_nicht_ungueltig(tmp_path):
    controller = _confirmed_controller(tmp_path)
    frozen = controller.command("freeze")
    controller.command("layout.set_many", {"values": {"digit_gap_ratio": 0.65}})
    controller.command("roi", {"id": frozen["id"], "quad": frozen["quad"],
                               "ocr_box": frozen["ocr_box"]})   # darf nicht werfen
    assert controller.config["confirmed"] is True
```

```bash
node --check src/dispread/workbench/static/workbench.js
```

`docs/anleitung/10-kamera-livevorschau.md`: den neuen dritten Schritt
aufnehmen und die „Fertig, wenn"-Liste des Kapitels nachziehen.

- [ ] **Schritt 6: CHANGELOG und Committen**

```bash
git add src/dispread/workbench/ tests/test_workbench.py docs/anleitung/ CHANGELOG.md
git commit -m "$(cat <<'EOF'
Einrichtung per getipptem Wert statt per Regler

Bedienerbefund: die Segmentpunkte muessen exakt sitzen, sonst liest das System
nicht - das Justieren kostet die meiste Einrichtzeit. Jetzt tippt der Bediener
einmal den angezeigten Wert; layout.autofit schlaegt daraus das Raster vor und
zeigt, was damit gelesen wird. Die Regler bleiben als Handkorrektur. Der
Vorschlag bestaetigt nichts - erst der bestehende ✓-Klick setzt confirmed.
Mehrdeutige (flache) Optima werden dem Bediener gemeldet statt still
aufgeloest.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

# Phase C — Nachführung der bestätigten Geometrie

Diese Phase darf vor der Decoder-Änderung ausgeliefert werden, weil sie ändert,
**welche Bildpunkte** gelesen werden, nicht **wie** sie dekodiert werden. Die
Ablehnungslogik bleibt unangetastet, und das Fehlerverhalten ist durch die mit
dem Bediener vereinbarte Regel begrenzt: außerhalb der Grenze wird nicht
korrigiert, sondern abgelehnt.

## Task 6: `QuadTracker`

**Dateien:**
- Neu: `src/dispread/track.py`
- Neu: `tests/test_track.py`
- Ändern: `CHANGELOG.md`

**Schnittstellen:**
- Nutzt: `cv2.findTransformECC` (in System-OpenCV 4.10 vorhanden, geprüft),
  `cv2.invertAffineTransform`, `dispread.rectify.rectify`, `dispread.detect.Quad`.
- Liefert:

```python
@dataclass(frozen=True, slots=True)
class TrackConfig:
    #: Zulaessige Verschiebung, als Anteil der Arbeitsbreite. Vorabdefault.
    max_shift: float = 0.10
    max_rotation_deg: float = 3.0
    min_score: float = 0.60
    work_size: tuple[int, int] = (200, 80)
    iterations: int = 30
    epsilon: float = 1e-4

@dataclass(frozen=True, slots=True)
class TrackResult:
    quad: Quad | None          # None = Grenze verletzt, nicht korrigieren
    shift: float
    rotation_deg: float
    score: float
    reason: str | None

class QuadTracker:
    def __init__(self, image, quad, *, config=TrackConfig()) -> None
    def update(self, image) -> TrackResult
```

**Zwei Konstruktionsregeln, die in den Docstring gehören:**

1. **Immer gegen das Referenzbild der Bestätigung registrieren, nie gegen das
   vorige Bild.** Eine Kette von Bild-zu-Bild-Schätzungen akkumuliert Drift;
   nach einer Stunde wäre die Geometrie weit von der bestätigten entfernt,
   ohne dass eine einzelne Schätzung je die Grenze verletzt hätte.
2. **Das Arbeitsbild wird in einem Schritt aus dem Rohbild entzerrt**, mit
   `target_size=work_size` — nicht aus dem bereits auf `CROP_SIZE` entzerrten
   Ausschnitt. Sonst registriert ECC auf einem zweifach neu abgetasteten Bild
   und misst Abtastartefakte als Bewegung mit (OQ-23 führt die doppelte
   Größenänderung in `rectify()`→`crop_box()` bereits als eigene Schärfeverlust-
   quelle).

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Neue Datei `tests/test_track.py`:

```python
"""Verankerte Nachfuehrung: derselben Anzeige folgen, nie eine andere waehlen."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from dispread.frames.synthetic_source import render_display
from dispread.layout import DisplayLayout
from dispread.track import QuadTracker, TrackConfig


def _scene(shift_x=0, shift_y=0, angle=0.0):
    """Anzeige auf grosser Flaeche, optional verschoben und gedreht."""
    layout = DisplayLayout(digits=4, decimals=2, has_sign=False, unit="V")
    display, _, _ = render_display(12.34, layout, size=(240, 100))
    scene = np.full((400, 640, 3), 30, np.uint8)
    scene[150:250, 200:440] = display
    if shift_x or shift_y or angle:
        matrix = cv2.getRotationMatrix2D((320.0, 200.0), angle, 1.0)
        matrix[0, 2] += shift_x
        matrix[1, 2] += shift_y
        scene = cv2.warpAffine(scene, matrix, (640, 400), borderValue=(30, 30, 30))
    return scene


_QUAD = ((200.0, 150.0), (440.0, 150.0), (440.0, 250.0), (200.0, 250.0))


def test_unbewegte_szene_wird_nicht_verschoben():
    tracker = QuadTracker(_scene(), _QUAD)
    result = tracker.update(_scene())
    assert result.quad is not None
    assert result.shift < 0.01
    assert result.score > 0.9


def test_kleine_verschiebung_wird_nachgefuehrt():
    """Der korrigierte Ausschnitt muss der Anzeige folgen, nicht stehenbleiben."""
    tracker = QuadTracker(_scene(), _QUAD)
    result = tracker.update(_scene(shift_x=8, shift_y=-4))
    assert result.quad is not None, result.reason
    moved_x = result.quad[0][0] - _QUAD[0][0]
    moved_y = result.quad[0][1] - _QUAD[0][1]
    assert moved_x == pytest.approx(8, abs=2.0)
    assert moved_y == pytest.approx(-4, abs=2.0)


def test_zu_grosse_verschiebung_wird_abgelehnt_nicht_korrigiert():
    """Ausserhalb der Grenze: nicht korrigieren. Die Ablehnung ist die sichere Richtung."""
    tracker = QuadTracker(_scene(), _QUAD, config=TrackConfig(max_shift=0.05))
    result = tracker.update(_scene(shift_x=90))
    assert result.quad is None
    assert result.reason == "shift_out_of_bounds"


def test_zu_grosse_drehung_wird_abgelehnt():
    tracker = QuadTracker(_scene(), _QUAD, config=TrackConfig(max_rotation_deg=2.0))
    result = tracker.update(_scene(angle=8.0))
    assert result.quad is None
    assert result.reason in ("rotation_out_of_bounds", "low_score", "ecc_diverged")


def test_voellig_anderes_bild_wird_abgelehnt():
    """Wird die Anzeige verdeckt, darf keine Geometrie 'gefunden' werden."""
    tracker = QuadTracker(_scene(), _QUAD)
    result = tracker.update(np.full((400, 640, 3), 200, np.uint8))
    assert result.quad is None


def test_nachfuehrung_haeuft_keine_drift_an():
    """Immer gegen die Referenz der Bestaetigung, nie gegen das vorige Bild."""
    tracker = QuadTracker(_scene(), _QUAD)
    for _ in range(20):
        tracker.update(_scene(shift_x=5))
    result = tracker.update(_scene())          # zurueck an den Ausgangsort
    assert result.quad is not None
    assert abs(result.quad[0][0] - _QUAD[0][0]) < 2.0
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_track.py -q
```
Erwartet: `ModuleNotFoundError: No module named 'dispread.track'`.

- [ ] **Schritt 3: Implementierung schreiben**

Neue Datei `src/dispread/track.py`. Die Vorzeichenkonvention von
`findTransformECC` (welche Richtung die gefundene Abbildung meint) wird **von
den Tests festgelegt** — `test_kleine_verschiebung_wird_nachgefuehrt` prüft,
dass der korrigierte Ausschnitt der Anzeige folgt. Gerüst:

```python
class QuadTracker:
    def __init__(self, image, quad, *, config=TrackConfig()):
        self.config = config
        self.quad = tuple((float(x), float(y)) for x, y in quad)
        self.reference = self._patch(image)

    def _patch(self, image):
        # Einschrittige Entzerrung direkt aus dem Rohbild auf work_size -
        # nicht ueber den bereits auf CROP_SIZE entzerrten Ausschnitt, sonst
        # misst ECC Abtastartefakte als Bewegung mit.
        crop = rectify(image, self.quad, target_size=self.config.work_size)
        gray = crop.image if crop.image.ndim == 2 else cv2.cvtColor(crop.image, cv2.COLOR_BGR2GRAY)
        return gray.astype(np.float32) / 255.0

    def update(self, image):
        current = self._patch(image)
        warp = np.eye(2, 3, dtype=np.float32)
        try:
            score, warp = cv2.findTransformECC(
                self.reference, current, warp, cv2.MOTION_EUCLIDEAN,
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                 self.config.iterations, self.config.epsilon),
                None, 5,
            )
        except cv2.error:
            # ECC konvergiert nicht, wenn das Bild strukturell nicht mehr passt
            # (Anzeige verdeckt, Licht aus). Das ist kein Fehler, sondern der
            # Befund "nicht wiedergefunden" - und fuehrt zur Ablehnung.
            return TrackResult(None, 0.0, 0.0, 0.0, "ecc_diverged")

        rotation_deg = float(np.degrees(np.arctan2(warp[1, 0], warp[0, 0])))
        shift = float(np.hypot(warp[0, 2], warp[1, 2])) / self.config.work_size[0]

        # Erst pruefen, dann rechnen: eine verletzte Grenze wird nicht
        # korrigiert, sondern gemeldet. Die Ablehnung ist die sichere Richtung
        # (Konzept.md §7), und der Bediener bekommt den Grund im Klartext.
        if score < self.config.min_score:
            return TrackResult(None, shift, rotation_deg, float(score), "low_score")
        if shift > self.config.max_shift:
            return TrackResult(None, shift, rotation_deg, float(score), "shift_out_of_bounds")
        if abs(rotation_deg) > self.config.max_rotation_deg:
            return TrackResult(None, shift, rotation_deg, float(score), "rotation_out_of_bounds")

        return TrackResult(self._moved_quad(warp), shift, rotation_deg, float(score), None)

    def _moved_quad(self, warp):
        """Die Bewegung aus dem Arbeitsbild zurueck in Bildkoordinaten legen.

        `findTransformECC(referenz, aktuell, ...)` liefert die Abbildung, die
        das aktuelle Bild auf die Referenz legt. Gesucht ist die Gegenrichtung:
        wo die Anzeige jetzt *ist*. Deshalb die inverse Affine.
        Welche Richtung tatsaechlich welche ist, pinnt
        `test_kleine_verschiebung_wird_nachgefuehrt` - stimmt das Vorzeichen
        nicht, folgt der Ausschnitt in die falsche Richtung und der Test faellt.
        """
        width, height = self.config.work_size
        corners = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
        inverse = cv2.invertAffineTransform(warp)
        moved = cv2.transform(corners.reshape(-1, 1, 2), inverse).reshape(-1, 2)
        to_image = cv2.getPerspectiveTransform(corners, np.float32(self.quad))
        points = cv2.perspectiveTransform(moved.reshape(-1, 1, 2).astype(np.float32), to_image)
        return tuple((float(x), float(y)) for x, y in points.reshape(-1, 2))
```

- [ ] **Schritt 4: Tests laufen lassen, grün bestätigen**

```bash
./.venv/bin/pytest tests/test_track.py -q && ./.venv/bin/ruff check src tests
```

- [ ] **Schritt 5: Laufzeit messen**

```bash
./.venv/bin/python - <<'PY'
"""Kosten eines update() auf einem realen 960x720-Bild."""
import json
import statistics
import time
from pathlib import Path

import cv2

from dispread.track import QuadTracker

directory = next(Path("var/workbench/annotations").glob("8a18ee05*"))
annotation = json.loads((directory / "annotation.json").read_text())
image = cv2.imread(str(directory / annotation["image"]))
height, width = image.shape[:2]
quad = tuple((x * width, y * height) for x, y in annotation["roi_quad"])

tracker = QuadTracker(image, quad)
tracker.update(image)                       # einmal warmlaufen
samples = []
for _ in range(200):
    start = time.perf_counter()
    tracker.update(image)
    samples.append((time.perf_counter() - start) * 1000.0)
print(f"update(): median {statistics.median(samples):.2f} ms, "
      f"p95 {statistics.quantiles(samples, n=20)[-1]:.2f} ms, max {max(samples):.2f} ms")
PY
```

Die Zahl gehört nach `docs/VALIDATION.md`, neben die dort schon geführten
Kosten der gedrosselten Kandidatensuche (8,0 ms Leerlauf / 12,5 ms Suchfall).

**Entscheidungsregel für Task 7:** Liegt der Median über 10 ms, wird die
Nachführung gedrosselt wie die Kandidatensuche (`TRACK_INTERVAL_S`, analog zu
`CANDIDATE_INTERVAL_S = 1.0`) statt bei jedem Bild zu laufen — dann gilt die
zuletzt gültige Korrektur weiter, bis die nächste Schätzung vorliegt. Liegt er
darunter, läuft sie bei jedem gelesenen Bild. Die Entscheidung wird im
CHANGELOG mit der gemessenen Zahl begründet, nicht geraten.

- [ ] **Schritt 6: CHANGELOG und Committen**

```bash
git add src/dispread/track.py tests/test_track.py docs/VALIDATION.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
QuadTracker: begrenzte Nachregistrierung einer bestaetigten Anzeige

Bedienerbefund: bei laengeren Lesungen verrutscht die Kamera und die Erkennung
bricht ab. Der Tracker registriert das aktuelle Bild gegen das bei der
Bestaetigung gemerkte Referenzbild - immer gegen die Referenz, nie gegen das
vorige Bild, sonst akkumuliert Drift. Verschiebung, Drehung und Registrier-
guete sind hart begrenzt; ausserhalb der Grenze wird nicht korrigiert.
Entzerrt einschrittig aus dem Rohbild, damit ECC keine Abtastartefakte als
Bewegung misst.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Nachführung in den Lesepfad einhängen

**Dateien:**
- Ändern: `src/dispread/workbench/controller.py`
- Ändern: `src/dispread/validate.py` (`tracking_lost` in `blocking_flags`)
- Ändern: `tests/test_workbench.py`, `tests/test_gate_und_referenz.py`
- Ändern: `CHANGELOG.md`

**Schnittstellen:**
- Nutzt: `QuadTracker`, `TrackResult`, `TrackConfig` (Task 6).
- Liefert: `reading["track"] = {"score", "shift", "rotation_deg", "corrected", "reason"}`;
  Statusflag `tracking_lost` im Freigabepfad.

**Wo der Tracker entsteht und vergeht:**
- Er wird im `roi`-Op angelegt, unmittelbar nachdem `confirmed=True` gesetzt
  wurde — das eingefrorene Bild dieser Bestätigung ist die Referenz.
- **Nur im `else`-Zweig, nicht im `annotate`-Zweig.** Im `annotate`-Modus
  schreibt der `roi`-Op eine `annotation.json` und ruft `_change()` gar nicht
  auf (`controller.py:571`); dort wird aufgenommen, nicht gemessen, und es
  gibt keine laufende Ablesung, die nachzuführen wäre. Der Tracker gehört
  deshalb **ausdrücklich nicht** in beide Zweige — sonst hielte der
  Aufnahmepfad eine Referenz, die zu keiner bestätigten Geometrie gehört.
- `_change()` verwirft ihn (`self.tracker = None`), wie es dort schon mit
  `self.gate` geschieht: eine geänderte Konfiguration darf keine Referenz aus
  der alten mitschleppen.
- Er lebt **nur zur Laufzeit**. Nach einem Neustart gibt es keine Referenz, bis
  erneut bestätigt wurde — das deckt sich mit der bereits erzwungenen erneuten
  Bestätigung beim Sitzungsstart (`controller.py:201`).

**Was die Korrektur NICHT tut:** Sie schreibt nichts nach `config["roi_quad"]`.
Die bestätigte Geometrie bleibt die Referenz; die Korrektur lebt in
`self.track_quad` und geht nur in das Lesen dieses Bildes ein. Damit bleibt
jederzeit sichtbar, was der Mensch bestätigt hat und was die Maschine
nachgeführt hat.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

```python
def test_verrutschte_anzeige_wird_weiter_gelesen(tmp_path):
    """Der eigentliche Bedienerwunsch: ein leichter Versatz bricht den Lauf nicht ab."""
    controller = _confirmed_controller_mit_anzeige(tmp_path)
    controller.publish(_szene(), _metadaten())
    assert controller.reading["value"] == 12.34

    controller.publish(_szene(shift_x=6), _metadaten())
    assert controller.reading["value"] == 12.34, "Nachfuehrung haette folgen muessen"
    assert controller.reading["track"]["corrected"] is True
    assert controller.config["roi_quad"] == _bestaetigtes_quad, "bestaetigte Geometrie bleibt"


def test_zu_grosser_versatz_fuehrt_zur_ablehnung_nicht_zur_korrektur(tmp_path):
    controller = _confirmed_controller_mit_anzeige(tmp_path)
    controller.publish(_szene(), _metadaten())
    controller.publish(_szene(shift_x=200), _metadaten())
    assert "tracking_lost" in controller.reading["status_flags"]
    assert controller.reading["gate_status"] == "unreadable"
    assert "state:tracking_lost" in controller.reading["gate_reasons"]


def test_tracker_wird_bei_konfigurationsaenderung_verworfen(tmp_path):
    controller = _confirmed_controller_mit_anzeige(tmp_path)
    controller.publish(_szene(), _metadaten())
    assert controller.tracker is not None
    controller.command("layout.set", {"key": "digits", "value": 5})
    assert controller.tracker is None
```

Und in `tests/test_gate_und_referenz.py`:

```python
def test_verlorene_nachfuehrung_blockiert_die_freigabe():
    """Konzept.md §4: bei Verlust der Anzeige wird der Messwert ungueltig."""
    gate = ReleaseGate(GateConfig())
    read = _lesbares_ergebnis(status_flags=frozenset({"tracking_lost"}))
    decision = gate.evaluate(read, capture_ns=0)
    assert decision.status is ValueStatus.UNREADABLE
    assert "state:tracking_lost" in decision.reject_reasons
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_workbench.py tests/test_gate_und_referenz.py -q -k "track or nachfuehr"
```

- [ ] **Schritt 3: Implementierung schreiben**

In `src/dispread/validate.py`, `GateConfig.blocking_flags`:

```python
blocking_flags: frozenset[str] = field(
    default_factory=lambda: frozenset({"overflow", "menu", "hold", "glare", "tracking_lost"})
)
```

In `controller.py`: `self.tracker = None`, `self.track_quad = None` im
`__init__`; in `_change()` neben `self.gate = None` auch
`self.tracker, self.track_quad = None, None`; im `roi`-Op nach `self._change(data)`:

```python
self.tracker = QuadTracker(frame["image"], roi_quad(frame["image"], data))
```

In `publish()`, unmittelbar bevor gelesen wird (`quad = roi_quad(image, config)`):

```python
track = None
if self.tracker is not None:
    track = self.tracker.update(image)
    if track.quad is not None:
        quad = track.quad
```

`_read()` bekommt den `TrackResult` als zusätzlichen Parameter
(`def _read(self, image, config, quad, track=None)`) und der Aufruf in
`publish()` wird zu `reading = self._read(image, config, quad, track)`.

Der Statusflag kommt **nicht** aus dem Leser — der weiß von Nachführung nichts
und soll es auch nicht. Der Controller ergänzt ihn in `_read()` an dem
`ReadResult`, das er der Freigabe übergibt, zwischen `read = self.reader.read(...)`
und `decision = self.gate.evaluate(...)`:

```python
read = self.reader.read(reader_crop, layout)
if track is not None and track.quad is None:
    # ReadResult ist frozen - ersetzen statt mutieren. Die Nachfuehrung ist
    # ein Befund ueber das Bild, kein Befund des Lesers; sie darf deshalb
    # nicht in sevenseg.py wandern.
    read = replace(read, status_flags=read.status_flags | {"tracking_lost"})
```

(`from dataclasses import replace` oben in `controller.py` ergänzen.)
Das Rückgabedict von `_read()` bekommt zusätzlich:

```python
"track": None if track is None else {
    "score": round(track.score, 3),
    "shift": round(track.shift, 4),
    "rotation_deg": round(track.rotation_deg, 2),
    "corrected": track.quad is not None,
    "reason": track.reason,
},
```

- [ ] **Schritt 4: Tests laufen lassen, grün bestätigen**

```bash
./.venv/bin/pytest -q && ./.venv/bin/ruff check src tests examples
```

- [ ] **Schritt 5: Committen**

```bash
git add src/dispread/workbench/controller.py src/dispread/validate.py tests/ CHANGELOG.md
git commit -m "$(cat <<'EOF'
Bestaetigte Geometrie wird im Lauf begrenzt nachgefuehrt

Vom Bediener so entschieden: dieselbe bereits bestaetigte Anzeige zu verfolgen
ist kein neuer Bestaetigungsakt, eine andere Anzeige zu waehlen waere einer.
Innerhalb harter Grenzen folgt die Lesegeometrie still und die Korrektur steht
im Leseergebnis; ausserhalb wird nicht korrigiert, sondern das Flag
tracking_lost gesetzt, das die Freigabe blockiert (Konzept.md §4: bei Verlust
der Anzeige wird der Messwert ungueltig). config["roi_quad"] bleibt
unveraendert - was der Mensch bestaetigt hat, bleibt unterscheidbar von dem,
was die Maschine nachgefuehrt hat.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Nachführgüte sichtbar machen

**Dateien:**
- Ändern: `src/dispread/workbench/fields.py` (`_reading_rows`)
- Ändern: `src/dispread/workbench/static/workbench.js` (Überlagerung)
- Ändern: `tests/test_workbench.py`, `CHANGELOG.md`

- [ ] **Schritt 1: Test schreiben**

```python
def test_nachfuehrzeile_erscheint_im_bedienbild(tmp_path):
    state = _status_mit_reading({"track": {"score": 0.82, "shift": 0.013,
                                           "rotation_deg": 0.4, "corrected": True, "reason": None}})
    ids = [row["id"] for row in _reading_rows(state)]
    assert "reading.track" in ids


def test_nachfuehrzeile_fehlt_ohne_nachfuehrung(tmp_path):
    state = _status_mit_reading({"track": None})
    assert "reading.track" not in [row["id"] for row in _reading_rows(state)]
```

- [ ] **Schritt 2: Fehlschlag bestätigen**

```bash
./.venv/bin/pytest tests/test_workbench.py -q -k nachfuehr
```

- [ ] **Schritt 3: Implementierung**

In `fields.py`, `_reading_rows`, nach dem vorhandenen Block für Kontrast und
Segmentabstand:

```python
REASONS = {
    "low_score": "Bild passt nicht mehr zur Referenz",
    "shift_out_of_bounds": "zu weit verschoben",
    "rotation_out_of_bounds": "zu stark gedreht",
    "ecc_diverged": "Anzeige nicht wiedergefunden",
}

track = (reading or {}).get("track")
if track:
    if track["corrected"]:
        value = f"folgt, {track['shift'] * 100:.1f} % versetzt, {track['rotation_deg']:+.1f}°"
    else:
        value = "AUS DEM RAHMEN: " + REASONS.get(track["reason"], track["reason"] or "unbekannt")
    rows.append(
        _row(
            "reading.track",
            "nachfuehrung",
            "text",
            value,
            value,
            "verfolgt dieselbe bestaetigte Anzeige; ausserhalb der Grenze wird "
            f"abgelehnt statt korrigiert. Guete {track['score']:.2f}",
        )
    )
```

Die Zeile erscheint nur, wenn `reading["track"]` gesetzt ist — ohne bestätigte
Geometrie gibt es keine Nachführung und damit auch nichts anzuzeigen.

In `workbench.js`, in `draw()` bzw. beim Zeichnen der Überlagerung: das
nachgeführte Quad in einer von der bestätigten Geometrie **unterscheidbaren**
Farbe zeichnen (die bestätigte ROI ist heute grün `(130,220,130)`, die
Vorschlagsboxen gelb `(0,220,220)` — für die Nachführung eine dritte Farbe).
Der Bediener muss sehen können, dass nachgeführt wurde und wie weit; eine
stille Korrektur, die aussieht wie die bestätigte Geometrie, wäre genau die
Vermischung, die der Rest dieses Projekts vermeidet.

- [ ] **Schritt 4: Grün bestätigen**

```bash
./.venv/bin/pytest -q && node --check src/dispread/workbench/static/workbench.js
```

- [ ] **Schritt 5: Committen** (CHANGELOG nicht vergessen)

---

# Phase D — Decoder, datengesperrt

## Task 9: Anzeigepolarität ins Profil (unabhängig, klärt OQ-13 Fall 2)

**Dateien:**
- Ändern: `src/dispread/layout.py`, `src/dispread/workbench/profiles.py`,
  `src/dispread/ocr/sevenseg.py`, `src/dispread/workbench/fields.py`
- Ändern: `tests/test_sevenseg.py`, `tests/test_workbench.py`
- Ändern: `docs/open-questions.md` (OQ-13), `CHANGELOG.md`

**Schnittstellen:**
- Liefert: `DisplayLayout.polarity: str = "bright_on_dark"`, zulässig auch
  `"dark_on_bright"`; wandert automatisch über `to_dict`/`from_dict` ins Profil.

**Keine Schemaversion nötig:** `profiles.validate()` füllt fehlende
Layout-Felder innerhalb von Schema 3 bereits mit dem Default
(`profiles.py:79`). Gespeicherte Profile bleiben gültig und bekommen
`bright_on_dark` — das reproduziert exakt das heutige Verhalten, keine
Vermutung über die tatsächliche Anzeige.

- [ ] **Schritt 1: Test schreiben**

```python
def test_lcd_polaritaet_wird_gelesen(reader):
    """OQ-13 Fall 2: dunkle Ziffern auf hellem Grund."""
    layout = DisplayLayout(digits=5, decimals=2, unit="N", polarity="dark_on_bright")
    hell = DisplayLayout(digits=5, decimals=2, unit="N")
    image, _, area = render_display(12.34, hell)
    x, y, w, h = area
    inverted = 255 - image[y : y + h, x : x + w]
    assert reader.read(inverted, layout).value == 12.34


def test_falsche_polaritaet_wird_abgelehnt_nicht_falsch_gelesen(reader):
    layout = DisplayLayout(digits=5, decimals=2, unit="N")   # bright_on_dark
    hell = DisplayLayout(digits=5, decimals=2, unit="N")
    image, _, area = render_display(12.34, hell)
    x, y, w, h = area
    result = reader.read(255 - image[y : y + h, x : x + w], layout)
    assert result.value != 12.34
    assert result.value is None, "falsche Polaritaet muss ablehnen, nicht raten"


def test_unbekannte_polaritaet_wird_abgelehnt():
    with pytest.raises(ValueError, match="polarity"):
        validate_layout({**DEFAULT["layout"], "polarity": "irgendwas"})
```

- [ ] **Schritt 2: Fehlschlag bestätigen**
- [ ] **Schritt 3: Implementierung**

In `layout.py`: Feld, `to_dict`-Eintrag, Docstring mit dem Verweis auf OQ-13.
In `profiles.py`: `validate_layout` prüft
`layout["polarity"] in ("bright_on_dark", "dark_on_bright")`.
In `sevenseg.py`, in `_to_gray` bzw. direkt danach:

```python
if layout.polarity == "dark_on_bright":
    # LCD: dunkle Segmente auf hellem Grund. Einmal umkehren, danach gilt im
    # ganzen Leser wieder "hell = an" - keine zweite Fallunterscheidung.
    gray = 255 - gray
```

In `fields.py`: Auswahlzeile `layout.polarity`.

- [ ] **Schritt 4: Grün bestätigen**

```bash
./.venv/bin/pytest -q && ./.venv/bin/ruff check src tests examples
```

- [ ] **Schritt 5: OQ-13 nachziehen**

OQ-13 Fall 2 auf `geklärt (Datum)` setzen, mit Antwort und Verweis. **Fall 1
bleibt offen** — der wird erst von Task 11 berührt. Eintrag nicht löschen.

- [ ] **Schritt 6: Committen**

---

## Task 10: Messbefund in der Doku — bereits erledigt

**Status: am 2026-09-11 umgesetzt, im selben Commit wie dieser Plan.**
Die Doku-Pflicht aus `AGENTS.md` („Neue Unbekannte erkannt → OQ-Eintrag,
**sofort, auch ohne Code-Änderung**"; „Messung gelaufen → `VALIDATION.md` und
`lab_journal.md`, **am selben Tag**") lässt sich nicht in eine Aufgabe
verschieben, die vielleicht erst in Tagen läuft.

Erledigt und nachlesbar:

| Inhalt | Ort |
| --- | --- |
| Ausgangsmessung 5 / 0 / 1, Tabelle je Annotation, Segmentdump, Prototyp-Vergleich, `thickness`/`inset`-Sweep | `docs/VALIDATION.md`, Abschnitt „2026-09-11 — Ausgangsmessung `sevenseg/2`" |
| Ursache (1) erneut belegt; **neuer Befund** `a`-Segment in `6ffc561b`; Abnahmekriterium; Otsu-je-Zelle verworfen | `docs/open-questions.md`, OQ-23, Update 2026-09-11 |
| Korrigierte Datenlage (neun statt zwei Annotationen) | OQ-23 und OQ-25, je Update 2026-09-11 |
| Aufbau, Deutung, warum die Reihenfolge umgedreht wurde | `docs/lab_journal.md`, Eintrag 2026-09-11 |

**Für Task 11 maßgeblich:** `6ffc561b` Stelle 0 liefert `1` oder wird
abgelehnt — niemals `7`. Und falsche Annahmen bleiben bei **0**.

---

## Task 11: Decoder-Messänderung — GESPERRT

**Diese Aufgabe darf nicht begonnen werden, bevor alle Sperrbedingungen erfüllt
sind.** Sie steht hier, damit die Bedingungen schriftlich sind, nicht damit sie
umgangen werden.

### Sperrbedingungen

Die Schwelle ist **wörtlich das P2-Exit-Kriterium aus `docs/ROADMAP.md`** —
nicht eine eigene, niedrigere Zahl. Ein Decoder darf nicht an einem Datensatz
abgenommen werden, der schwächer ist als der, den dieselbe ROADMAP für die
Phase davor verlangt.

| # | Bedingung | Quelle | Heute |
| --- | --- | --- | --- |
| 1 | Clipsatz mit ≥ **6 Geräteinstanzen** über ≥ **3 Displaytypen** | ROADMAP P2 | 1 Instanz, 1 Typ |
| 2 | davon **2 Instanzen gesperrt**, vor jeder Entwicklung vereinbart, einmalig ausgewertet | ROADMAP P2 | nicht vereinbart |
| 3 | ≥ **8 verschiedene angezeigte Werte** je Instanz, inkl. Werten mit Vorzeichen und mit `0` und `8` an jeder Stelle | dieser Plan | 3 Werte |
| 4 | Entwicklungs- und Testsatz **geräteweise disjunkt**, maschinell geprüft (`assert_disjoint_devices`) | ROADMAP, Konzept §9 | nicht vorhanden |
| 5 | Ausgangsmessung nach Task 3 in `docs/VALIDATION.md` | dieser Plan | offen |

Bedingung 3 ist die einzige, die dieser Plan zusätzlich stellt: die ROADMAP
zählt Geräte, nicht Werte, aber ein Decoder, der nie eine `8` an einer
bestimmten Stelle gesehen hat, ist an dieser Stelle unbelegt (OQ-13 Fall 1).

### Abnahmekriterium

**Falsche Annahmen: ≤ 0.** Die heutige Ausgangszahl auf den sechs realen
Annotationen ist **null**. „Keine neuen stillen Fehlablesungen" heißt gegen
eine Ausgangszahl von null damit: *eine einzige* falsche Annahme im Testsatz
blockiert die Änderung, unabhängig davon, wie viele zusätzliche Treffer sie
bringt. Dazu:

- `tests/test_sevenseg.py::test_starke_unschaerfe_erzeugt_keine_stillen_fehlablesungen`
  bleibt grün. Schlägt er fehl, wird der **Decoder** korrigiert, nie der Test
  abgeschwächt.
- `6ffc561b` Stelle 0 liest `1` oder wird abgelehnt, nie `7` (Task 10).
- Die Trefferquote wird **pro Fehlerklasse** berichtet, nicht als eine Zahl
  (ROADMAP-P3-Exit-Kriterium).

### Kandidatenänderung (nicht entschieden, nur festgehalten)

Aus dem Prototyp dieser Sitzung, in der Reihenfolge absteigender Evidenz:

1. **Panelbezug je Stelle.** Zwei Panelfenster je Zelle (die Innenflächen der
   oberen und unteren Segmentschleife — sie leuchten bei keiner Ziffer)
   liefern eine Off-Referenz je Stelle. Das ist der in OQ-13 bereits
   vorgeschlagene Mechanismus und adressiert die gemessene Ursache (1).
2. **Entscheidung als Anteil der Zellspanne** statt gegen eine globale
   Schwelle — mit Trennungsprüfung (`min(an) − max(aus) ≥ Anteil der Spanne`,
   sonst ablehnen) und einer höheren absoluten Schwelle, bevor „alle sieben an"
   als `8` akzeptiert wird. Ohne diese beiden Prüfungen entstand im Prototyp
   genau die `1`→`7`-Fehlablesung.
3. **Flächige Segmentmessung** erst, wenn Phase B `thickness_ratio`/
   `inset_ratio` tatsächlich kalibriert — mit den heutigen Defaults ist sie
   nachweislich schlechter.

Otsu *innerhalb* der Zelle ist **verworfen**: bei sechs aktiven und einem
inaktiven Segment wählt es nachweislich den falschen Schnitt.

- [ ] **Schritt 1:** Sperrbedingungen prüfen und das Ergebnis im Task
      dokumentieren. Sind sie nicht erfüllt: hier abbrechen, nichts ändern.
- [ ] **Schritt 2–n:** Erst nach erfüllter Sperre ausformulieren — TDD gegen
      den dann vorhandenen Testsatz, `BACKEND_VERSION` auf `"3"`,
      `docs/VALIDATION.md` mit Vorher/Nachher je Fehlerklasse.

---

## Task 12: Doku-Abschluss

**Dateien:** `docs/status.md`, `docs/project_history.md`,
`docs/open-questions.md`, `docs/ROADMAP.md`, `CLAUDE.md`

- [ ] **Schritt 1: `docs/project_history.md`** — die verworfenen Alternativen
      aus der [Spezifikation](#verworfene-alternativen) übernehmen (ssocr,
      gitterfreier Decoder, synthetisch trainierter Klassifikator,
      Rasterfeinschliff je Bild), jeweils mit Begründung.

- [ ] **Schritt 2: Neue OQ-Einträge anlegen** (Nummern lückenlos fortsetzen):
  - **OQ-26 — Grenzen der Nachführung an realen Geräten validieren.**
    `max_shift=0.10`, `max_rotation_deg=3.0`, `min_score=0.60` sind
    Vorabdefaults wie alle Werte in `DetectionConfig`. Antwort landet in
    `docs/VALIDATION.md`.
  - **OQ-27 — Rasterfeinschliff je Bild.** Bewusst nicht gebaut; Begründung
    (Phase C fängt starre Bewegung ab, ein Feinschliff ohne Verankerung erbt
    OQ-25). Antwort landet in `src/dispread/ocr/`.
  - **OQ-28 — Eindeutigkeit der Autofit-Geometrie.** Der Sweep zeigt zwei
    gleich gut punktende, weit auseinanderliegende Parametersätze. Ob
    `flat_optimum` diesen Fall am realen Gerät zuverlässig anzeigt, ist offen.

- [ ] **Schritt 3: entfällt** — OQ-23, OQ-25 und `docs/status.md` sind am
      2026-09-11 bereits korrigiert (neun Annotationen, sechs mit Sollwert),
      siehe Task 10.

- [ ] **Schritt 4: `docs/ROADMAP.md`** — P1 (`replay://`-Session) und P2
      (realer Datensatz) nachziehen, sobald die Clips aufgenommen sind.

- [ ] **Schritt 5: `CLAUDE.md`** — in der Aufbau-Tabelle `replay://` von
      „nur Registry-Eintrag, TODO" auf fertig ziehen und `track` als neue
      Stufe aufnehmen.

- [ ] **Schritt 6: `docs/status.md` neu schreiben** (überschreiben, nicht
      anhängen) — Pflicht vor dem letzten Commit jeder Session.

---

## Verifikation (gilt für jede Aufgabe)

```bash
./.venv/bin/pytest -q
./.venv/bin/ruff check src tests examples
node --check src/dispread/workbench/static/workbench.js     # bei JS-Aenderungen
./.venv/bin/python examples/16_end_to_end_headless.py       # Kette ohne Hardware
```

Nicht aus Tests ableitbar und deshalb gesondert abzunehmen (OQ-21/OQ-24):
der Kalibrierschritt im echten Browser, die Clipaufnahme am echten Gerät und
das Verhalten der Nachführung, wenn die Kamera während eines Laufs wirklich
angestoßen wird.
