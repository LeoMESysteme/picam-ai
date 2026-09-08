# 4 — Geräteprofile

**Ziel:** ROI, Zahlenformat und Einheit kommen aus einer bestätigten
JSON-Datei unter `config/profiles/`, nicht aus fest verdrahteten Zahlen im
Beispielskript. `ProfileStore().load("gsv-2asd-labor1")` liefert alles, was
Pipeline und Gate brauchen.

**Warum jetzt:** Konzept §4 sieht vor, dass der Bediener Anzeige, Einheit und
Zahlenformat **einmalig bestätigt** — das ist der Primärpfad des Projekts, und
bisher existiert er nur als Konstruktorargument in `examples/16`. Ohne Profile
gibt es keine CLI ([Kapitel 5](05-cli.md)), keine wiederholbare Messreihe und
keine sinnvolle `expected_unit` im Gate. Hakt die ROADMAP-Zeile „Geräteprofile:
`config/profiles/` samt JSON-Schema und `ProfileStore`" ab.

**Vorbedingungen:** [Kapitel 3](03-erste-bildquelle-folder.md) (du hast einmal
ein Modul mit Test gebaut). Bezug: [OQ-05](../open-questions.md),
[OQ-17](../open-questions.md).

## Was ins Profil gehört — und was nicht

Ein Profil ist die **bestätigte Annahme über ein Gerät an einem Platz**. Es ist
Beweismittel: es sagt, was ein Mensch wann bestätigt hat.

Hinein gehört:

| Feld | Warum |
| --- | --- |
| `profile_id` | stabiler Schlüssel, landet in jedem `ValueRecord` |
| `device_model` | z. B. `GSV-2ASD`; freier Text, aber gepflegt |
| `display_type` | `seven_seg` heute; Platzhalter für LCD/Dot-Matrix |
| `layout` | serialisiertes `DisplayLayout` (`digits`, `decimals`, `has_sign`, `unit`, …) |
| `roi_quad` | vier Punkte im **Bildkoordinatensystem** der Aufnahme |
| `role_hint` | `main` oder `secondary` — Verwechslung ist laut §7 kritisch |
| `capture_size` | `[Breite, Höhe]`, für die die ROI gilt |
| `confirmed_by`, `confirmed_at` | wer hat bestätigt, wann (ISO-8601, mit Zeitzone) |
| `unit_source` | `profile` oder `read` — heute immer `profile` |
| `decimal_point_source` | `profile` oder `detected` — heute immer `profile` ([OQ-17](../open-questions.md)) |
| `notes` | Aufbau, Beleuchtung, Auffälligkeiten |
| `schema_version` | damit ein altes Profil erkennbar bleibt |

Nicht hinein gehört:

* **Freigabeschwellen.** Die stehen in `GateConfig` und sind noch unvalidiert
  ([OQ-14](../open-questions.md)). Sie pro Gerät zu übersteuern, bevor sie
  überhaupt einmal gemessen wurden, verstetigt Zufallswerte.
* **Referenzwerte, Sollwerte, Kalibrierdaten.** Die haben in diesem Pfad nichts
  zu suchen (Konzept §7).
* **Kameraeinstellungen als Wahrheit.** Belichtung gehört in die
  Aufnahmesession ([Kapitel 6](06-kamera-aufnahme-replay.md)), nicht ins
  Geräteprofil — dasselbe Gerät kann bei anderem Licht stehen.

### Die wichtigste Designentscheidung: ROI und Auflösung

Eine ROI in Pixeln gilt nur für **eine** Aufnahmegröße. Läuft die Kamera
plötzlich mit 1332×990 statt 2028×1520, zeigt dieselbe ROI auf die falsche
Stelle. Zwei Auswege:

* **Stillschweigend skalieren** — verlockend und falsch. Der 7-Segment-Leser
  tastet gegen ein Raster ab; eine skalierte ROI verschiebt die Abtastpunkte,
  und das Ergebnis sind Fehlablesungen, die niemand als Konfigurationsproblem
  erkennt.
* **Ablehnen** — `capture_size` mitschreiben und beim Laden gegen die
  tatsächliche Framegröße prüfen. Passt es nicht: Fehler mit klarer Meldung.
  Die ROI wird dann neu bestätigt. Das ist die Richtung, die dieses Projekt
  wählt: eine Falschablehnung ist erlaubt, eine stille Fehlablesung nicht.

Praktisch: `Pipeline.process()` prüft es nicht — also prüft es der Aufrufer
(CLI) oder ein `ManualRoiLocator`, dem du das erwartete `capture_size` mitgibst
und der bei Abweichung ein **leeres** Kandidatentupel liefert. Dann erzeugt die
Pipeline von selbst `display_not_located`. Überlege, welche der beiden Stellen
die richtige ist, und begründe die Wahl in `docs/project_history.md`.

## Beispielprofil

`config/profiles/gsv-2asd-labor1.json`:

```json
{
  "schema_version": 1,
  "profile_id": "gsv-2asd-labor1",
  "device_model": "GSV-2ASD",
  "display_type": "seven_seg",
  "layout": {
    "digits": 5,
    "decimals": 2,
    "has_sign": true,
    "unit": "N",
    "sign_cell_ratio": 0.6,
    "thickness_ratio": 0.16,
    "inset_ratio": 0.1
  },
  "roi_quad": [[412, 388], [1604, 392], [1600, 690], [408, 686]],
  "role_hint": "main",
  "capture_size": [2028, 1520],
  "confirmed_by": "l.hentschke",
  "confirmed_at": "2026-09-10T09:41:00+02:00",
  "unit_source": "profile",
  "decimal_point_source": "profile",
  "notes": "Kamera auf Stativ, 42 cm, Ringlicht seitlich, Streuscheibe."
}
```

## Schritt 1 — Test zuerst

`tests/test_profiles.py`. Was hier geprüft wird, ist wichtiger als die Menge:

```python
"""Geraeteprofile laden, pruefen und wieder schreiben."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dispread.layout import DisplayLayout


def _profil_dict(**overrides) -> dict:
    basis = {
        "schema_version": 1,
        "profile_id": "testgeraet",
        "device_model": "GSV-2ASD",
        "display_type": "seven_seg",
        "layout": DisplayLayout().to_dict(),
        "roi_quad": [[10, 10], [90, 10], [90, 50], [10, 50]],
        "role_hint": "main",
        "capture_size": [480, 200],
        "confirmed_by": "test",
        "confirmed_at": "2026-09-10T09:41:00+02:00",
        "unit_source": "profile",
        "decimal_point_source": "profile",
    }
    return basis | overrides


def test_rundlauf_ist_verlustfrei(tmp_path: Path) -> None:
    from dispread.profiles import DeviceProfile

    profil = DeviceProfile.from_dict(_profil_dict())
    assert DeviceProfile.from_dict(profil.to_dict()) == profil


def test_layout_wird_zum_objekt(tmp_path: Path) -> None:
    from dispread.profiles import DeviceProfile

    profil = DeviceProfile.from_dict(_profil_dict())
    assert isinstance(profil.layout, DisplayLayout)
    assert profil.layout.unit == "N"


def test_store_laedt_und_listet(tmp_path: Path) -> None:
    from dispread.profiles import ProfileStore

    (tmp_path / "testgeraet.json").write_text(json.dumps(_profil_dict()), encoding="utf-8")
    store = ProfileStore(tmp_path)
    assert store.list_ids() == ("testgeraet",)
    assert store.load("testgeraet").device_model == "GSV-2ASD"


def test_unbekanntes_profil_nennt_die_bekannten(tmp_path: Path) -> None:
    from dispread.profiles import ProfileStore

    with pytest.raises(KeyError) as exc:
        ProfileStore(tmp_path).load("gibtsnicht")
    assert "gibtsnicht" in str(exc.value)


@pytest.mark.parametrize(
    "kaputt",
    [
        {"roi_quad": [[0, 0], [1, 1]]},              # nur zwei Punkte
        {"role_hint": "irgendwas"},                   # nicht main/secondary
        {"unit_source": "geraten"},                   # unbekannte Herkunft
        {"capture_size": [0, 0]},                     # unsinnige Groesse
        {"confirmed_by": ""},                         # unbestaetigt
        {"confirmed_at": "10.09.2026"},               # kein ISO-8601
    ],
)
def test_kaputte_profile_werden_abgelehnt(kaputt: dict) -> None:
    from dispread.profiles import DeviceProfile, ProfileError

    with pytest.raises(ProfileError):
        DeviceProfile.from_dict(_profil_dict(**kaputt))


def test_id_muss_zum_dateinamen_passen(tmp_path: Path) -> None:
    from dispread.profiles import ProfileError, ProfileStore

    (tmp_path / "anders.json").write_text(json.dumps(_profil_dict()), encoding="utf-8")
    with pytest.raises(ProfileError):
        ProfileStore(tmp_path).load("anders")


def test_roi_passt_nicht_zur_bildgroesse(tmp_path: Path) -> None:
    from dispread.profiles import DeviceProfile

    profil = DeviceProfile.from_dict(_profil_dict())
    assert profil.matches_capture_size((480, 200)) is True
    assert profil.matches_capture_size((1332, 990)) is False


def test_speichern_erzeugt_lesbares_json(tmp_path: Path) -> None:
    from dispread.profiles import DeviceProfile, ProfileStore

    store = ProfileStore(tmp_path)
    profil = DeviceProfile.from_dict(_profil_dict())
    pfad = store.save(profil)
    assert json.loads(pfad.read_text(encoding="utf-8"))["profile_id"] == "testgeraet"
    assert store.load("testgeraet") == profil
```

Der Parametrisierungs-Test ist der wichtigste: **ein Profil, das nicht
vollständig bestätigt ist, darf nicht laden.** Ein leeres `confirmed_by`
bedeutet, dass niemand hingeschaut hat — und dann ist der ganze Primärpfad
eine Behauptung.

## Schritt 2 — Gerüst

`src/dispread/profiles.py`:

```python
"""Bestaetigte Geraeteprofile (Konzept.md §4).

Ein Profil ist die einmalig vom Bediener bestaetigte Annahme ueber ein Geraet
an einem Platz: Ausschnitt, Zahlenformat, Einheit. Es ist Beweismittel - wer
hat wann was bestaetigt - und deshalb laedt ein unvollstaendig bestaetigtes
Profil nicht.

Herkunft von Einheit und Dezimalpunkt wird explizit gefuehrt
(unit_source, decimal_point_source), damit eine Profilannahme nicht als
optische Messung durchgeht (OQ-17).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dispread import paths
from dispread.detect import Quad
from dispread.layout import DisplayLayout

PROFILE_SCHEMA_VERSION = 1
_ROLLEN = ("main", "secondary")
_HERKUNFT = ("profile", "read", "detected")


class ProfileError(ValueError):
    """Profil ist unvollstaendig, widerspruechlich oder nicht bestaetigt."""


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    profile_id: str
    device_model: str
    display_type: str
    layout: DisplayLayout
    roi_quad: Quad
    role_hint: str
    capture_size: tuple[int, int]
    confirmed_by: str
    confirmed_at: str
    unit_source: str = "profile"
    decimal_point_source: str = "profile"
    notes: str = ""
    schema_version: int = PROFILE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        # TODO: alle Regeln pruefen und ProfileError mit sprechender Meldung
        #       werfen. Reihenfolge: Pflichtfelder, dann Wertebereiche.
        raise NotImplementedError

    def matches_capture_size(self, size: tuple[int, int]) -> bool:
        ...

    def to_dict(self) -> dict[str, Any]:
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceProfile:
        ...


class ProfileStore:
    """Profile aus einem Verzeichnis. Default: paths.PROFILES."""

    def __init__(self, directory: Path | str | None = None) -> None:
        self.directory = Path(directory) if directory else paths.PROFILES

    def list_ids(self) -> tuple[str, ...]: ...
    def load(self, profile_id: str) -> DeviceProfile: ...
    def save(self, profile: DeviceProfile) -> Path: ...
```

Hinweise zur Umsetzung:

* `__post_init__` ist bei `frozen=True` der richtige Ort für Prüfungen —
  dasselbe Muster wie `ValueRecord`. Schau dir dort an, wie die Meldungen
  formuliert sind: sie nennen den Wert **und** die Regel.
* `confirmed_at` prüfst du mit `datetime.fromisoformat()`; verlange eine
  Zeitzone (`dt.tzinfo is not None`). Eine Laborzeit ohne Zeitzone ist im
  Zeitbezug dieses Projekts wertlos.
* `roi_quad` aus JSON ist eine Liste von Listen — in ein Tupel von Tupeln
  wandeln, sonst schlägt der Rundlauf-Vergleich fehl und `frozen` ist nur
  Dekoration.
* `load()` soll bei unbekannter ID die bekannten IDs mit auflisten. Du bist der
  erste Nutzer dieser Fehlermeldung.

## Schritt 3 — JSON-Schema dazu

`config/profiles/schema.json` als JSON-Schema (Draft 2020-12): `required` für
alle Pflichtfelder, `enum` für `role_hint`, `unit_source`,
`decimal_point_source`, `minItems`/`maxItems` 4 für `roi_quad`.

`jsonschema` liegt als Systempaket vor (`/usr/lib/python3/dist-packages`,
Version 4.19.2) und darf deshalb benutzt werden — aber **nicht** über
`pip install`, sondern nur als Systempaket, wie in
[../dependencies.md](../dependencies.md) beschrieben. Neue Abhängigkeit heißt:
Eintrag in `docs/dependencies.md` **im selben Commit**.

Wichtig: das Schema ist die Prüfung für **fremde** Dateien und für Werkzeuge
außerhalb von Python. Die Prüfungen in `__post_init__` bleiben trotzdem — sie
gelten auch für Profile, die im Code entstehen, etwa im ROI-Werkzeug.

## Schritt 4 — Profil benutzen

Ziel ist, dass `examples/16` und dein Skript aus [Kapitel 1](01-kette-verstehen.md)
das Profil verwenden können:

```python
from dispread.profiles import ProfileStore
from dispread.detect.manual_roi import ManualRoiLocator
from dispread.validate import GateConfig, ReleaseGate
from dispread.pipeline import PipelineConfig

profil = ProfileStore().load("gsv-2asd-labor1")
locator = ManualRoiLocator(profil.roi_quad, role_hint=profil.role_hint,
                           confirmed_by=profil.confirmed_by)
gate = ReleaseGate(GateConfig(expected_unit=profil.layout.unit))
config = PipelineConfig(profile_id=profil.profile_id, layout=profil.layout)
```

Genau diese vier Zeilen wandern in [Kapitel 5](05-cli.md) in die CLI. Schreibe
zusätzlich ein kleines Beispiel (`examples/05_profil_anwenden.py`) im Stil von
`examples/16` — mit Docstring-Kopf (*Zweck / Hardware / Ausgabe / Referenz*).

## Ein ROI-Werkzeug (Kür, aber nützlich)

Der Bediener soll die ROI bestätigen, nicht Zahlen in JSON tippen. Auf einem
Pi ohne Bildschirm bleibt der Weg über eine Datei:

1. Frame aufnehmen bzw. aus `folder://` nehmen, als PNG speichern.
2. ROI-Vorschlag zeichnen (`cv2.polylines`) und als
   `var/diagnostics/roi_vorschau.png` schreiben.
3. Ansehen, Zahlen im JSON anpassen, Schritt 2 wiederholen — bis das Raster
   sitzt.
4. Erst dann `confirmed_by`/`confirmed_at` setzen. **Die Bestätigung ist der
   Akt eines Menschen**, kein Automatismus.

Rezept 3 in den [Rezepten](rezepte.md) hat den Zeichencode. Später wird daraus
`dispread roi` ([Kapitel 5](05-cli.md)).

## Fallen

* **Profil-ID nachträglich ändern.** Sie steht in jedem `ValueRecord` einer
  alten Messreihe. Neue ID = neues Profil, altes bleibt liegen.
* **`decimals: null` bedeutet nicht „egal".** Es heißt: der Dezimalpunkt muss
  **erkannt** werden — und das kann der heutige Leser nicht, er meldet dann
  ehrlich `decimal_point_detected=False`, und das Gate lehnt ab. Setze `null`
  also nur, wenn du in [Kapitel 8](08-ocr-backends.md) die Erkennung baust.
* **Einheit im Layout ist die *erwartete* Einheit.** Der Leser liest sie nicht;
  `unit_source: "profile"` sagt das. Wer das Feld später zur gemessenen Einheit
  macht, muss `unit_source` mit ändern — sonst behauptet ein Datensatz eine
  Messung, die nicht stattgefunden hat.
* **`config/` existiert noch nicht.** `paths.PROFILES` zeigt auf
  `ROOT/config/profiles`. Verzeichnis anlegen und mindestens ein Beispielprofil
  einchecken, damit Tests und CLI etwas zum Laden haben. Echte Laborprofile mit
  Gerätebezug gehören perspektivisch nach `/etc/dispread` (`paths.ETC`).
* **Kein `dict`-Durchreichen.** Wenn irgendwo `profil["layout"]["digits"]`
  steht, ist die Typisierung umgangen und die Prüfung übersprungen.

## Fertig, wenn

* [ ] Tests grün, `ruff` grün
* [ ] `config/profiles/` enthält Schema und mindestens ein Beispielprofil
* [ ] Ein unvollständig bestätigtes Profil lädt **nicht**
* [ ] ROI-Größenprüfung existiert und lehnt bei Abweichung ab
* [ ] `CHANGELOG.md`, `docs/dependencies.md` (falls `jsonschema` benutzt),
      ROADMAP-Häkchen
* [ ] Entscheidung „ablehnen statt skalieren" in
      `docs/project_history.md` festgehalten (Problem / Entscheidung /
      Begründung / Alternativen / Konsequenz)

Weiter mit [Kapitel 5 — Die CLI](05-cli.md).
