"""Pfadkonstanten als einzige Quelle der Wahrheit.

Muster uebernommen von /opt/mehub/current/src/mehub/paths.py: alles ist per
Umgebungsvariable ueberschreibbar, damit Tests und Beispiele nicht in die
echten Laufzeitverzeichnisse schreiben.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


#: Projektwurzel (enthaelt Konzept.md, pyproject.toml, docs/).
ROOT = _env_path("DISPREAD_ROOT", Path(__file__).resolve().parents[2])

#: Projekt-venv. Python-Befehle laufen immer hierueber (siehe AGENTS.md).
VENV = _env_path("DISPREAD_VENV", ROOT / ".venv")

#: Konfiguration und Geraeteprofile im Repo.
CONFIG = _env_path("DISPREAD_CONFIG", ROOT / "config")
PROFILES = _env_path("DISPREAD_PROFILES", CONFIG / "profiles")

#: Betriebliche Konfiguration ausserhalb des Repos (hardware.conf).
ETC = _env_path("DISPREAD_ETC", Path("/etc/dispread"))

#: Laufzeitdaten: Sessions, Diagnosebilder, Wertelogs.
VAR_LIB = _env_path("DISPREAD_VAR_LIB", Path("/var/lib/dispread"))

#: Fluechtiger Laufzeitzustand: Heartbeat, pty-Symlinks.
RUN = _env_path("DISPREAD_RUN", Path("/run/dispread"))

#: Datensaetze (Aufnahmesessions, synthetische Saetze). Gross - gehoert
#: langfristig auf externen Speicher, siehe docs/HARDWARE_PROFILE.md.
DATASETS = _env_path("DISPREAD_DATASETS", ROOT / "datasets")

#: Ausgaben von Beispielen und Diagnoselaeufen. Nicht versioniert.
VAR = _env_path("DISPREAD_VAR", ROOT / "var")
EXAMPLES_OUT = VAR / "examples"
DIAGNOSTICS = VAR / "diagnostics"


def ensure(path: Path) -> Path:
    """Verzeichnis anlegen, falls noetig, und zurueckgeben."""
    path.mkdir(parents=True, exist_ok=True)
    return path
