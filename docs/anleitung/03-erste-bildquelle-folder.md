# 3 — Erste eigene Bildquelle: `folder://`

**Ziel:** `open_source("folder:///pfad?rate=5&glob=*.png")` liefert Frames aus
einem Bildverzeichnis, und die vollständige Kette läuft gegen echtes
Bildmaterial statt gegen den Generator.

**Warum jetzt:** Es ist der kleinste Vertrag im Projekt (sechs Methoden, davon
zwei trivial), braucht keine Hardware, und es ist die Voraussetzung für alles
Weitere: sobald du in [Kapitel 6](06-kamera-aufnahme-replay.md) echte
Aufnahmen machst, ist `folder://` der Weg, sie durch die Kette zu schicken.
Hakt die ROADMAP-Zeile „`folder://` … Implementierungen noch nicht" unter P0
ein Stück weiter ab.

**Vorbedingungen:** [Kapitel 0](00-werkzeuge.md), [Kapitel 1](01-kette-verstehen.md).
Nachschlagen in [Kapitel 2](02-vertraege.md).

## Ausgangslage

Die Registry kennt das Schema schon. In `src/dispread/frames/__init__.py`:

```python
def _open_folder(uri: str) -> FrameSource:
    from dispread.frames.folder_source import FolderSource     # existiert noch nicht

    parsed = urlparse(uri)
    q = _query_scalars(uri)
    return FolderSource(
        directory=parsed.path,
        pattern=q.get("glob", "*.png"),
        rate_hz=float(q.get("rate", 10.0)),
    )
```

Heute:

```bash
./.venv/bin/python -c "from dispread.frames import open_source; open_source('folder:///tmp')"
# ModuleNotFoundError: No module named 'dispread.frames.folder_source'
```

Deine Aufgabe ist genau diese eine Datei:
`src/dispread/frames/folder_source.py` mit einer Klasse `FolderSource`, deren
Konstruktor `directory`, `pattern` und `rate_hz` annimmt. **Die Registry rührst
du nicht an** — sie gibt die Signatur vor.

## Entscheide zuerst, dann tippe

Diese sechs Fragen entscheiden das Design. Sie sind hier schon beantwortet,
aber lies die Begründung — dieselben Fragen kommen bei jeder weiteren Quelle
wieder.

| Frage | Entscheidung | Begründung |
| --- | --- | --- |
| Welche Zeitbasis? | `TimeBaseKind.FILE_MTIME` | Die Dateizeit sagt nichts über den Aufnahmezeitpunkt. `is_time_bearing` wird damit `False`, und niemand kann aus diesen Frames eine Latenz berechnen. Eine `SENSOR_BOOTTIME` zu behaupten wäre eine Falschaussage. |
| `uncertainty_ns`? | `None` | Ungemessen ist nicht 0. |
| Sortierung? | **natürlich**, nicht alphabetisch | Alphabetisch kommt `frame10.png` vor `frame2.png`. Bei einer Aufnahmereihe verdreht das die Reihenfolge und damit jede Bestätigungslogik. |
| Was macht `rate_hz`? | nur den Abspieltakt | Es ist eine Bequemlichkeit fürs Zuschauen, **keine** Aussage über die Aufnahmerate. `rate_hz <= 0` heißt „so schnell wie möglich". |
| Unlesbare Datei? | überspringen, **zählen** | Werfen würde einen ganzen Datensatz wegen eines kaputten PNG unbrauchbar machen. Stillschweigend ignorieren verbietet das Projekt — also zählen und in `describe()` ausweisen. |
| Verzeichnis fehlt? | `FileNotFoundError` in `open()` | Der Konstruktor macht kein I/O; ein Objekt zu bauen darf nicht scheitern, weil eine Platte gerade nicht da ist. Fehler beim Öffnen, nicht beim Konfigurieren. |

Ein leeres Verzeichnis ist **erlaubt** (`frames()` liefert nichts), muss aber
in `describe()` als `count: 0` sichtbar sein. Ein Lauf, der null Frames
verarbeitet, darf nicht wie ein erfolgreicher Lauf aussehen.

## Schritt 1 — Test zuerst

Lege `tests/test_folder_source.py` an. Das ist die Spezifikation; sie muss rot
sein, bevor du das Modul schreibst.

```python
"""FolderSource: Bildverzeichnis als Bildquelle."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from dispread.frames import Capability, FrameSource, open_source
from dispread.records import TimeBaseKind


def _write_bild(path: Path, helligkeit: int = 120) -> None:
    img = np.full((40, 80, 3), helligkeit, np.uint8)
    assert cv2.imwrite(str(path), img)


@pytest.fixture
def bildordner(tmp_path: Path) -> Path:
    # Absichtlich so benannt, dass alphabetische Sortierung falsch waere.
    for name in ("frame1.png", "frame2.png", "frame10.png"):
        _write_bild(tmp_path / name)
    return tmp_path


def test_erfuellt_das_protokoll(bildordner: Path) -> None:
    from dispread.frames.folder_source import FolderSource

    assert isinstance(FolderSource(directory=str(bildordner)), FrameSource)


def test_registry_erzeugt_die_quelle(bildordner: Path) -> None:
    src = open_source(f"folder://{bildordner}?rate=0&glob=*.png")
    assert src.describe()["pattern"] == "*.png"


def test_reihenfolge_ist_natuerlich(bildordner: Path) -> None:
    src = open_source(f"folder://{bildordner}?rate=0")
    src.open()
    namen = [f.raw_metadata["path"] for f in src.frames()]
    src.close()
    assert [Path(n).name for n in namen] == ["frame1.png", "frame2.png", "frame10.png"]


def test_sequenz_beginnt_bei_eins_und_ist_lueckenlos(bildordner: Path) -> None:
    src = open_source(f"folder://{bildordner}?rate=0")
    src.open()
    assert [f.frame_sequence for f in src.frames()] == [1, 2, 3]
    src.close()


def test_zeitbasis_traegt_keine_zeitaussage(bildordner: Path) -> None:
    src = open_source(f"folder://{bildordner}?rate=0")
    src.open()
    frame = next(iter(src.frames()))
    src.close()
    assert frame.timebase is TimeBaseKind.FILE_MTIME
    assert frame.is_time_bearing is False
    assert frame.capture_timestamp.uncertainty_ns is None


def test_capabilities_ohne_live(bildordner: Path) -> None:
    src = open_source(f"folder://{bildordner}?rate=0")
    assert Capability.SEEK in src.capabilities
    assert Capability.LIVE not in src.capabilities


def test_kaputte_datei_wird_gezaehlt_nicht_geworfen(tmp_path: Path) -> None:
    _write_bild(tmp_path / "gut.png")
    (tmp_path / "kaputt.png").write_bytes(b"kein PNG")
    src = open_source(f"folder://{tmp_path}?rate=0")
    src.open()
    frames = list(src.frames())
    beschreibung = src.describe()
    src.close()
    assert len(frames) == 1
    assert beschreibung["unreadable_files"] == 1


def test_leerer_ordner_ist_erlaubt_aber_sichtbar(tmp_path: Path) -> None:
    src = open_source(f"folder://{tmp_path}?rate=0")
    src.open()
    assert list(src.frames()) == []
    assert src.describe()["count"] == 0
    src.close()


def test_fehlendes_verzeichnis_scheitert_erst_beim_oeffnen(tmp_path: Path) -> None:
    src = open_source(f"folder://{tmp_path / 'gibtsnicht'}?rate=0")   # kein Fehler
    with pytest.raises(FileNotFoundError):
        src.open()


def test_describe_nennt_die_grenzen_der_quelle(bildordner: Path) -> None:
    src = open_source(f"folder://{bildordner}?rate=0")
    src.open()
    d = src.describe()
    src.close()
    assert d["timebase"] == TimeBaseKind.FILE_MTIME.value
    assert d["carries_time_information"] is False
    assert d["count"] == 3
```

Lauf:

```bash
./.venv/bin/pytest -q tests/test_folder_source.py
# erwartet: Fehler (ModuleNotFoundError) - gut so
```

## Schritt 2 — Gerüst

`src/dispread/frames/folder_source.py`. Docstring erst, Code danach:

```python
"""Bildverzeichnis als Bildquelle.

Zweck: aufgenommenes oder exportiertes Bildmaterial ohne Kamera durch die
Kette schicken. Die Zeitbasis ist FILE_MTIME und traegt damit ausdruecklich
keine Zeitaussage - aus diesen Frames darf keine Latenzangabe abgeleitet
werden (Konzept.md §6).

Fuer eine Aufnahmesession mit originalen Sensorzeitstempeln ist nicht diese
Quelle zustaendig, sondern replay:// (siehe docs/anleitung/06-...).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2

from dispread.frames.types import Capability, Frame
from dispread.records import TimeBaseKind, Timestamp, TimestampSemantics


def natuerlicher_schluessel(name: str) -> tuple[object, ...]:
    """Sortierschluessel, in dem Zahlen als Zahlen zaehlen.

    "frame10.png" gehoert hinter "frame2.png".
    """
    # TODO: Name in Ziffern- und Textstuecke zerlegen (re.split auf (\d+))
    #       und Ziffernstuecke als int zurueckgeben.
    raise NotImplementedError


class FolderSource:
    """Frames aus einem Verzeichnis, in natuerlicher Sortierung."""

    def __init__(self, *, directory: str, pattern: str = "*.png", rate_hz: float = 10.0) -> None:
        self.directory = Path(directory)
        self.pattern = pattern
        self.rate_hz = rate_hz
        self._paths: list[Path] = []
        self._seq = 0
        self._unreadable = 0

    # -- FrameSource ---------------------------------------------------
    def open(self) -> None:
        # TODO: Verzeichnis pruefen (FileNotFoundError), Dateien sammeln,
        #       sortieren, Zaehler zuruecksetzen.
        raise NotImplementedError

    def close(self) -> None:
        # Nichts offen - aber die Methode gehoert zum Vertrag.
        ...

    @property
    def source_id(self) -> str:
        # Stabil und aussagekraeftig; landet in jedem ValueRecord.
        return f"folder:{self.directory}"

    @property
    def capabilities(self) -> frozenset[Capability]:
        return frozenset({Capability.SEEK})

    def describe(self) -> dict[str, Any]:
        # TODO: source_id, timebase, carries_time_information, directory,
        #       pattern, count, rate_hz, unreadable_files
        raise NotImplementedError

    def frames(self) -> Iterator[Frame]:
        # TODO: je Datei einlesen (cv2.imread), unlesbare zaehlen und
        #       ueberspringen, Frame bauen, Takt einhalten.
        raise NotImplementedError
```

## Schritt 3 — In welcher Reihenfolge implementieren

1. `natuerlicher_schluessel` — reine Funktion, sofort testbar. Tipp:
   `re.split(r"(\d+)", name)` und die Ziffernstücke nach `int` wandeln.
2. `open()` — `if not self.directory.is_dir(): raise FileNotFoundError(...)`,
   dann `sorted(self.directory.glob(self.pattern), key=…)`. Die Fehlermeldung
   soll den Pfad **und** das Muster nennen; du liest sie später selbst.
3. `describe()` — nur ein Dict. Danach ist der Registry-Test grün.
4. `frames()` — der eigentliche Teil. Gerüst:

```python
def frames(self) -> Iterator[Frame]:
    intervall = 1.0 / self.rate_hz if self.rate_hz > 0 else 0.0
    for path in self._paths:
        t_start = time.monotonic()
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)   # BGR, uint8
        if image is None:                                  # cv2 wirft nicht, es gibt None
            self._unreadable += 1
            continue
        self._seq += 1
        yield Frame(
            frame_sequence=self._seq,
            image=image,
            capture_timestamp=Timestamp(
                value_ns=int(path.stat().st_mtime_ns),
                base=TimeBaseKind.FILE_MTIME,
                semantics=TimestampSemantics.UNKNOWN,
                uncertainty_ns=None,          # ungemessen ist nicht 0
            ),
            source_id=self.source_id,
            raw_metadata={"path": str(path)},
        )
        if intervall:
            # Verarbeitungszeit abziehen, sonst wird der Takt langsamer als bestellt.
            time.sleep(max(0.0, intervall - (time.monotonic() - t_start)))
    # TODO: ueberlegen, ob der Zaehler self._unreadable hier noch irgendwo
    #       auffallen muss - describe() allein liest niemand automatisch.
```

Der letzte `TODO` ist keine Fleißaufgabe: überlege wirklich, wie eine
übersprungene Datei im Betrieb sichtbar wird. Die CLI aus
[Kapitel 5](05-cli.md) schreibt `describe()` in ihr Runartefakt — bis dahin ist
`describe()` der richtige Ort.

## Schritt 4 — Gegen die ganze Kette prüfen

Erst Bildmaterial erzeugen (Rezept 2 in den [Rezepten](rezepte.md) schreibt
synthetische Frames als PNG), dann:

```bash
./.venv/bin/pytest -q                                    # alles, nicht nur dein Test
./.venv/bin/ruff check src tests examples
./.venv/bin/python var/scratch.py                        # dein Skript aus Kapitel 1,
                                                         # Quelle auf folder:// umgestellt
```

Fällt dir dabei auf, dass du für `folder://` kein `src.layout` hast? Richtig —
das ist eine Eigenheit der synthetischen Quelle. Ein Verzeichnis weiß nicht,
welches Zahlenformat die Anzeige hat. Genau diese Lücke füllt
[Kapitel 4](04-geraeteprofile.md); bis dahin gibst du das `DisplayLayout` im
Skript von Hand an.

## Fallen

* **`cv2.imread` wirft nicht.** Es gibt `None` zurück. Wer das nicht prüft,
  bekommt den Fehler erst tief in `rectify()` als kryptischen NumPy-Fehler.
* **`cv2.imread` liest Graustufen-PNG standardmäßig als 3 Kanäle.** Das ist
  hier in Ordnung (`Frame.image` erlaubt beides), aber gib es bewusst an:
  `IMREAD_COLOR` oder `IMREAD_UNCHANGED`, nicht den Default „irgendwie".
* **Nicht die gesamte Liste in den Speicher laden.** `frames()` ist ein
  Generator; bei 10 000 Bildern ist das der Unterschied zwischen läuft und
  läuft nicht (der Pi hat begrenzt Speicher, Konzept §5 verlangt begrenzte
  Puffer).
* **mtime hat auf manchen Dateisystemen 1-s-Auflösung.** Deshalb ist die
  Reihenfolge die Dateisortierung, nicht die mtime-Sortierung.
* **`glob` ist nicht rekursiv.** `*.png` findet keine Unterordner. Wenn du das
  willst: `rglob` und Muster dokumentieren — aber dann ändert sich die
  Sortierung, weil der Pfad mitzählt.
* **Nicht heimlich Metadaten erfinden.** Kein `exposure_time_us`, kein
  `analogue_gain`, wenn die Datei sie nicht hergibt. `None` ist die richtige
  Antwort.
* **Kein Cache über `open()` hinaus.** Zweimal `open()` heißt: Liste neu
  einlesen und Zähler zurücksetzen, wie es die synthetische Quelle vormacht.

## Fertig, wenn

* [ ] `./.venv/bin/pytest -q` grün, inklusive der neuen Tests
* [ ] `./.venv/bin/ruff check src tests examples` grün
* [ ] `open_source("folder:///…")` liefert Frames, die durch `Pipeline.process()`
      laufen und einen `ValueRecord` mit `frame_sequence` 1..n ergeben
* [ ] `describe()` weist `carries_time_information: False` und
      `unreadable_files` aus
* [ ] `CHANGELOG.md`: Problem / Änderung / Konsequenz — **Pflicht** bei
      Änderungen unter `src/`
* [ ] `docs/ROADMAP.md`: `folder://` in der P0-Liste vermerkt
* [ ] Neu entdeckte Unbekannte als `OQ-nn` in
      [../open-questions.md](../open-questions.md)

## Wenn du mehr willst

Dieselbe Struktur, steigende Schwierigkeit — jeweils mit eigenem Test:

* **`video://`** — `cv2.VideoCapture`, `frames()` liest bis `ret == False`.
  Zeitbasis bleibt `FILE_MTIME`, denn ein Containerzeitstempel ist keine
  Sensorzeit. Achte auf `release()` in `close()`.
* **Sortierung wählbar** — `?sort=name|mtime`, Default `name`. In `describe()`
  ausweisen, welche gewählt war.
* **Sidecar-Metadaten** — liegt neben `frame000123.png` eine
  `frame000123.json`, könnten Belichtung und Verstärkung daraus kommen. Genau
  das macht `replay://` in [Kapitel 6](06-kamera-aufnahme-replay.md) — dort mit
  originalem Sensorzeitstempel und Zeitbasis `REPLAY_RECORDED`. Baue es hier
  **nicht** ein: eine Quelle, die manchmal Zeitaussagen trägt und manchmal
  nicht, ist die gefährlichere Variante.

Weiter mit [Kapitel 4 — Geräteprofile](04-geraeteprofile.md).
