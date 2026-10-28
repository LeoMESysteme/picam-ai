"""Lokale Entwicklungsaufnahmen auf SD oder optionalem Entwicklungsmedium.

Nur fuer Skripte und Tests. Eingaben bevorzugen stets den vorhandenen
Produktpfad; explizite Ausgaben werden nicht umgeleitet.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_LEGACY = {"rescue-20260925", "removed-20260928-sc", "removed-20260929-sc3a"}
_RESTORE_POINT = "gsv-register-rueckstellpunkt-2026-09-22.json"


def _relative(path: Path, repo_root: Path) -> Path | None:
    if path.is_absolute():
        # var ist in Worktrees oft ein Link auf den gemeinsamen Datenbestand.
        for root in (repo_root / "var", (repo_root / "var").resolve()):
            try:
                return path.relative_to(root)
            except ValueError:
                pass
        return None
    return Path(*path.parts[1:]) if path.parts and path.parts[0] == "var" else path


def _development_relative(relative: Path) -> Path | None:
    parts = relative.parts
    if not parts or ".." in parts:
        return None
    if parts[0] in _LEGACY:
        return Path("altlasten") / relative
    if parts[0] == "diagnostics":
        return None if len(parts) > 1 and parts[1] == _RESTORE_POINT else relative
    if parts[0] == "live":
        if len(parts) == 1 or parts[1] < "live-20261023":
            return relative
    return None


def input_path(path: str | Path, *, repo_root: Path = REPO_ROOT) -> Path:
    """Vorhandene Eingabe: var/<rel>, danach DISPREAD_DEV_DATA/<rel>.

    Akzeptiert auch alte var/-Pfade und beliebige explizite Eingabepfade.
    Existiert der Pfad so, wie er uebergeben wurde, kommt er unveraendert
    zurueck (gespeicherte Pfade und daraus gebildete Kennungen bleiben
    gleich). Fehlt die Aufnahme ueberall, bleibt der lokale Pfad fuer die
    bisherige Fehlerbehandlung des Aufrufers erhalten. Legt nichts an.
    """
    path = Path(path)
    if path.exists():
        return path
    relative = _relative(path, repo_root)
    if relative is None or not relative.parts or relative.parts[0] not in {"diagnostics", "live", *_LEGACY}:
        return path
    local = repo_root / "var" / relative
    development = _development_relative(relative)
    if development is None or local.exists():
        return local
    root = os.environ.get("DISPREAD_DEV_DATA")
    if root:
        candidate = Path(root) / development
        if candidate.exists():
            return candidate
    return local


def logical_path(path: str | Path) -> Path:
    """Pfad auf dem Entwicklungsmedium zurueck in das alte var/-Schema.

    Fuer alles, was gespeichert oder gehasht wird (Profile, Datensatz,
    Kennungen): dort darf kein Pfad auf das Entwicklungsmedium stehen.
    Andere Pfade kommen unveraendert zurueck.
    """
    path = Path(path)
    root = os.environ.get("DISPREAD_DEV_DATA")
    if not root:
        return path
    try:
        relative = path.relative_to(Path(root))
    except ValueError:
        return path
    if relative.parts and relative.parts[0] == "altlasten":
        relative = Path(*relative.parts[1:])
    return Path("var") / relative


def diagnostic_output(relative: str | Path = "") -> Path:
    """Standard fuer NEUE Diagnoseaufnahmen; legt keine Verzeichnisse an."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Diagnose-Ausgabe muss relativ sein")
    root = os.environ.get("DISPREAD_DEV_DATA")
    return (Path(root) if root else Path("var")) / "diagnostics" / relative


def recording_glob(pattern: str, *, repo_root: Path = REPO_ROOT) -> list[Path]:
    """Aufnahmen beider Ablagen, gleiche relative Pfade nur einmal (SD zuerst)."""
    matches = {path.relative_to(repo_root / "var"): path
               for path in (repo_root / "var").glob(pattern)}
    root = os.environ.get("DISPREAD_DEV_DATA")
    if root:
        for path in Path(root).glob(pattern):
            relative = path.relative_to(root)
            if _development_relative(relative) == relative:
                matches.setdefault(relative, path)
    return [matches[key] for key in sorted(matches)]
