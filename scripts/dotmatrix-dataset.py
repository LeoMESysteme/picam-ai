#!/usr/bin/env python3
r"""Datensatz-Lader fuer den Dot-Matrix-Leser - Task 6 aus
docs/superpowers/plans/2026-09-24-dotmatrix-reader.md.

Liest bestaetigte, automatisch geerntete Proben (`label_origin ==
"serial_ascii"`, `label_state == "readable"`) direkt aus einem
`DatasetStore`-Wurzelverzeichnis (`var/workbench/datasets`, nur lesen - siehe
AGENTS.md/global-constraints), entzerrt sie mit dem Sitzungsprofil, das die
Probe zur Import-Zeit belegte, und tastet die ersten `CELL_COUNT` Zeichenzellen
(der Zahlenblock, Regel `gsv2as_v1`) fuer den Zellen-Klassifikator ab.

## Herkunft des Profils

Seit Task 6 traegt jede von `scripts/import-harvest.py` importierte Probe
`profile_quad`/`profile_grid` (JSON-Strings) direkt in `label_origin_detail`
- das Profil, das zur Import-Zeit galt, ist damit an der Probe selbst
ablesbar, unabhaengig davon, ob die Profildatei spaeter geaendert oder
geloescht wird. Aeltere, vor Task 6 importierte Proben haben diese Felder
nicht (siehe `var/workbench/datasets/samples/*/sample.json`, `session_id`
allein reicht dort) - fuer sie liefert der Aufrufer eine `profile_map`
(Sitzungs-ID -> `{"path": ..., "sha256": ...}`), siehe
`write-map`/`read_profile_map` unten. Eine Probe, deren Profil auf keinem der
beiden Wege auflösbar ist, wird gezaehlt und uebersprungen, nie geraten
(AGENTS.md).

## Fix Runde 1 (Review): Pruefsumme der `profile_map`-Datei

`profile_map` traegt neben dem Pfad auch die `sha256`, die `write-map` beim
Schreiben der Zuordnung gemessen hat. Beim Aufloesen ueber `profile_map`
(nicht ueber `label_origin_detail`) wird die Datei am Pfad NEU gehasht und
gegen diese erwartete Pruefsumme geprueft - stimmt sie nicht (Profil wurde
nach `write-map` erneut bestaetigt/veraendert), wird die Probe NICHT mit dem
inzwischen anderen Quad/Raster entzerrt, sondern unter
`REASON_HASH_MISMATCH` gezaehlt und uebersprungen. Ein Map-Eintrag ohne
`sha256` gilt als nicht aufloesbar (`write-map` schreibt immer eine).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from dispread.charcells import CharGrid
from dispread.ocr.dotmatrix_font import CLASSES
from dispread.ocr.dotmatrix_sampling import normalized, sample_image
from dispread.rectify import rectify
from dispread.session_profile import SessionProfile

#: Einziges Geraet, das dieser Loader kennt (siehe Auftrag) - der Name, den
#: `import-harvest.py` als externe Geraete-ID im `DatasetStore` anlegt
#: (`_resolve_or_create_device`), nicht die interne UUID.
DEVICE_NAME = "gsv-sensor-161a"

#: Zellen 0-8 des Zahlenblocks (Vorzeichen + 6 Ziffern + Punkt + eine
#: Trennzelle, Formatregel `gsv2as_v1`, global-constraints.md) - Einheit und
#: Rest (Zellen 9-15) werden in diesem Schritt nicht klassifiziert.
CELL_COUNT = 9

#: Zaehlergruende in `stats` (Fix Runde 1): eine Probe ohne aufloesbares
#: Profil ueberhaupt, bzw. eine Probe, deren `profile_map`-Eintrag auf eine
#: inzwischen anders lautende Profildatei zeigt (Pruefsummen-Mismatch) - in
#: beiden Faellen wird NIE mit einem moeglicherweise falschen Quad/Raster
#: entzerrt.
REASON_NO_PROFILE = "ohne_profil"
REASON_HASH_MISMATCH = "profil_pruefsumme_abweichend"

#: Von `write-map` bekannte Sitzungsprofile (Ernte Phase 1). Relativ zur
#: Repo-Wurzel, wie in der Zuordnungsdatei abgelegt.
_REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_PROFILE_PATHS: dict[str, Path] = {
    "ernte1": _REPO_ROOT / "var" / "diagnostics" / "ernte1-profile" / "profile.json",
    "auf2": _REPO_ROOT / "var" / "diagnostics" / "auf2-profile" / "profile.json",
    "auf3": _REPO_ROOT / "var" / "diagnostics" / "auf3-profile" / "profile.json",
}


@dataclass
class CellSample:
    """Eine geerntete Probe, abgetastet auf die ersten `CELL_COUNT` Zellen."""

    sample_id: str
    group: str
    plateau: tuple[int, int]
    cell_text: str
    vectors: np.ndarray  # Form (CELL_COUNT, 9, 40), siehe dotmatrix_sampling.normalized


@dataclass
class ResolvedRecord:
    """Eine Probe mit dem entzerrten Graubild statt fertig abgetasteter
    Vektoren - fuer Task 7 (`dotmatrix-eval.py reader-check`), das den
    kompletten `DotMatrixReader.read()` (inklusive Kontrast-/
    Saettigungspruefung, die auf `CellSample.vectors` nicht mehr moeglich
    ist) gegen dieselbe Probe laufen lassen muss, die `evaluate()` sieht.
    Teilt sich die Profilaufloesung mit `load_cell_samples` ueber
    `_iter_resolved_records`, statt sie zu duplizieren."""

    sample_id: str
    group: str
    plateau: tuple[int, int]
    cell_text: str
    crop_gray: np.ndarray
    grid: CharGrid


def _profile_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _find_device_id(dataset_root: Path, device_name: str) -> str | None:
    devices_path = dataset_root / "devices.json"
    if not devices_path.is_file():
        return None
    data = json.loads(devices_path.read_text(encoding="utf-8"))
    for device_id, device in data.get("devices", {}).items():
        if device.get("name") == device_name:
            return device_id
    return None


def _grid_from_json(grid_json: str) -> tuple[CharGrid, tuple[int, int]] | None:
    """`profile_grid` (`CharGrid.to_dict()` plus `target_size`) zurueck in
    `CharGrid` und `target_size` - `None` bei unlesbarem/unvollstaendigem
    Text statt eines geratenen Rasters."""
    try:
        grid_dict = json.loads(grid_json)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(grid_dict, dict) or "target_size" not in grid_dict:
        return None
    target_size = tuple(grid_dict["target_size"])
    try:
        grid = CharGrid.from_dict({k: v for k, v in grid_dict.items() if k != "target_size"})
    except (KeyError, TypeError):
        return None
    return grid, target_size


def _quad_from_json(quad_json: str) -> list[list[float]] | None:
    try:
        quad = json.loads(quad_json)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(quad, list) or len(quad) != 4:
        return None
    return quad


def _resolve_profile(
    detail: dict, session_id: str | None, profile_map: dict[str, dict[str, str]]
) -> tuple[list[list[float]], CharGrid, tuple[int, int]] | str:
    """Profil einer Probe: bevorzugt aus `label_origin_detail` (Task 6,
    belegt genau, was zur Import-Zeit galt), sonst ueber `profile_map`
    (aeltere Proben, nur `session_id`).

    `profile_map[session_id]` ist `{"path": ..., "sha256": ...}` (das Format
    von `write-map`/`read_profile_map`). Beim Map-Weg wird die Datei am Pfad
    NEU gehasht und gegen die gespeicherte `sha256` geprueft, bevor sie
    geladen wird - eine seit `write-map` veraenderte Profildatei (z. B. eine
    neu bestaetigte Sitzung mit anderem Quad) darf nie unbemerkt fuer eine
    aeltere Probe verwendet werden (Fix Runde 1, Review-Befund). Ein
    Map-Eintrag ohne `sha256` gilt als nicht aufloesbar - `write-map`
    schreibt sie immer, ein fehlender Wert ist also ein Format-/Datenfehler,
    keine gueltige Zuordnung.

    Rueckgabe: das aufgeloeste Profil, oder ein Ablehnungsgrund-String
    (`REASON_NO_PROFILE`/`REASON_HASH_MISMATCH`) statt eines geratenen
    Profils.
    """
    quad_json = detail.get("profile_quad")
    grid_json = detail.get("profile_grid")
    if isinstance(quad_json, str) and isinstance(grid_json, str):
        quad = _quad_from_json(quad_json)
        grid_and_size = _grid_from_json(grid_json)
        if quad is not None and grid_and_size is not None:
            grid, target_size = grid_and_size
            return quad, grid, target_size

    if session_id:
        entry = profile_map.get(session_id)
        if entry:
            path_str = entry.get("path")
            expected_sha256 = entry.get("sha256")
            if path_str and expected_sha256:
                profile_path = Path(path_str)
                if profile_path.is_file():
                    if _profile_sha256(profile_path) != expected_sha256:
                        return REASON_HASH_MISMATCH
                    profile = SessionProfile.load(profile_path)
                    return profile.quad, profile.grid, profile.target_size
    return REASON_NO_PROFILE


def _init_stats(stats: dict[str, int] | None) -> dict[str, int]:
    if stats is None:
        stats = {}
    stats.setdefault(REASON_NO_PROFILE, 0)
    stats.setdefault(REASON_HASH_MISMATCH, 0)
    stats.setdefault("ungueltige_zeichen", 0)
    stats.setdefault("geladen", 0)
    return stats


def _iter_resolved_records(
    dataset_root: Path,
    profile_map: dict[str, dict[str, str]],
    *,
    stats: dict[str, int],
):
    """Gemeinsamer Kern von `load_cell_samples` und `load_resolved_records`:
    findet passende Proben, loest ihr Profil auf (`_resolve_profile`) und
    entzerrt das Bild - EINMAL, damit beide Aufrufer mit derselben
    Zuordnung und demselben entzerrten Bild arbeiten. Liefert
    `ResolvedRecord`s (entzerrtes Graubild, noch nicht abgetastet)."""
    dataset_root = Path(dataset_root)
    device_id = _find_device_id(dataset_root, DEVICE_NAME)
    if device_id is None:
        return

    samples_dir = dataset_root / "samples"
    if not samples_dir.is_dir():
        return

    for sample_dir in sorted(samples_dir.iterdir()):
        sample_path = sample_dir / "sample.json"
        if not sample_path.is_file():
            continue
        sample = json.loads(sample_path.read_text(encoding="utf-8"))
        if sample.get("label_origin") != "serial_ascii":
            continue
        if sample.get("label_state") != "readable":
            continue
        if sample.get("device_id") != device_id:
            continue

        detail = sample.get("label_origin_detail") or {}
        session_id = detail.get("session_id")
        resolved = _resolve_profile(detail, session_id, profile_map)
        if isinstance(resolved, str):
            stats[resolved] = stats.get(resolved, 0) + 1
            continue
        quad, grid, target_size = resolved

        cell_text = str(detail.get("cell_text", ""))[:CELL_COUNT]
        if any(ch not in CLASSES for ch in cell_text):
            stats["ungueltige_zeichen"] += 1
            continue

        image_path = sample_dir / "image.png"
        image = cv2.imread(str(image_path))
        if image is None:
            continue

        crop = rectify(image, tuple(tuple(p) for p in quad), target_size=target_size)
        gray = crop.image if crop.image.ndim == 2 else cv2.cvtColor(crop.image, cv2.COLOR_BGR2GRAY)

        plateau = (int(detail.get("plateau_start_ns", 0)), int(detail.get("plateau_end_ns", 0)))
        stats["geladen"] += 1
        yield ResolvedRecord(
            sample_id=sample.get("id", sample_dir.name),
            group=session_id or "",
            plateau=plateau,
            cell_text=cell_text,
            crop_gray=gray,
            grid=grid,
        )


def load_cell_samples(
    dataset_root: Path,
    profile_map: dict[str, dict[str, str]],
    *,
    stats: dict[str, int] | None = None,
) -> list[CellSample]:
    """Ladet alle passenden Proben aus `dataset_root` (nur lesen).

    Nur `label_origin == "serial_ascii"`, `label_state == "readable"` und
    Geraet `DEVICE_NAME`. Gruppe = `label_origin_detail["session_id"]`.
    `profile_map` ist `{session_id: {"path": ..., "sha256": ...}}` (siehe
    `read_profile_map`/`write-map`). Proben ohne auflösbares Profil, mit
    einer seit `write-map` veraenderten Profildatei (Pruefsummen-Mismatch,
    siehe `_resolve_profile`) oder mit einem `cell_text` ausserhalb der
    bekannten Zeichenklassen (`CLASSES`) werden gezaehlt (in `stats`, falls
    uebergeben) und uebersprungen, nie geraten.
    """
    stats = _init_stats(stats)
    out: list[CellSample] = []
    for rec in _iter_resolved_records(dataset_root, profile_map, stats=stats):
        vectors = normalized(sample_image(rec.crop_gray, rec.grid, range(CELL_COUNT)))
        out.append(
            CellSample(
                sample_id=rec.sample_id,
                group=rec.group,
                plateau=rec.plateau,
                cell_text=rec.cell_text,
                vectors=vectors,
            )
        )
    return out


def load_resolved_records(
    dataset_root: Path,
    profile_map: dict[str, dict[str, str]],
    *,
    stats: dict[str, int] | None = None,
    limit: int | None = None,
) -> list[ResolvedRecord]:
    """Wie `load_cell_samples`, aber mit dem entzerrten Graubild statt
    fertiger Vektoren (Task 7, `dotmatrix-eval.py reader-check`) - teilt
    sich die Profilaufloesung ueber `_iter_resolved_records`, damit reader-
    check und die Zellenmessung (`evaluate`) garantiert dieselbe Zuordnung
    und dasselbe entzerrte Bild sehen. `limit` bricht nach den ersten `N`
    geladenen Proben ab (nicht nach den ersten `N` Dateien - uebersprungene
    Proben zaehlen nicht mit)."""
    stats = _init_stats(stats)
    out: list[ResolvedRecord] = []
    for rec in _iter_resolved_records(dataset_root, profile_map, stats=stats):
        out.append(rec)
        if limit is not None and len(out) >= limit:
            break
    return out


def read_profile_map(path: Path) -> dict[str, dict[str, str]]:
    """Liest das von `write-map` geschriebene Format
    (`{"session_id": {"path": ..., "sha256": ...}}`) und liefert die
    `profile_map`-Form, die `load_cell_samples`/`_resolve_profile` erwarten -
    Pfade relativ zur Repo-Wurzel werden aufgeloest, die `sha256` bleibt
    erhalten (Fix Runde 1: sie wird beim Aufloesen gegen die dann aktuelle
    Datei geprueft, statt kommentarlos verworfen zu werden)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for session_id, entry in data.items():
        p = Path(entry["path"])
        if not p.is_absolute():
            p = _REPO_ROOT / p
        out[session_id] = {"path": str(p), "sha256": entry.get("sha256", "")}
    return out


def _cmd_write_map(args: argparse.Namespace) -> int:
    out: dict[str, dict[str, str]] = {}
    missing: list[str] = []
    for session_id, path in SESSION_PROFILE_PATHS.items():
        if not path.is_file():
            missing.append(session_id)
            continue
        try:
            rel = path.relative_to(_REPO_ROOT)
        except ValueError:
            rel = path
        out[session_id] = {
            "path": str(rel),
            "sha256": _profile_sha256(path),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    msg = f"Profil-Zuordnung geschrieben: {args.out} ({len(out)} Sitzungen)"
    if missing:
        msg += f" - fehlend, nicht in der Datei: {missing}"
    print(msg)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Datensatz-Lader fuer den Dot-Matrix-Leser (Task 6, Nachverfolgbarkeit)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    write_map = sub.add_parser(
        "write-map", help="Schreibt die Sitzungsprofil-Zuordnung fuer aeltere Proben ohne profile_quad/profile_grid."
    )
    write_map.add_argument("--out", type=Path, required=True, help="Zieldatei fuer die Zuordnung")
    write_map.set_defaults(func=_cmd_write_map)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
