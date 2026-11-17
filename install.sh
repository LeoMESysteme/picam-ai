#!/usr/bin/env bash
# Read-only by default. No curl|bash assumptions or machine-specific paths.
set -euo pipefail
installer_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
installer_python="${PICAM_INSTALLER_PYTHON:-python3}"
if ! command -v "$installer_python" >/dev/null 2>&1; then
    printf 'Python fehlt. PICAM_INSTALLER_PYTHON=/pfad/zu/python3 setzen.\n' >&2
    exit 1
fi
exec "$installer_python" "$installer_root/scripts/install.py" "$@"
