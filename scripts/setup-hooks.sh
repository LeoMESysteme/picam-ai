#!/usr/bin/env bash
# Aktiviert die Git-Hooks aus .githooks/ nur fuer dieses Repository (lokale
# Konfiguration, kein --global). Rueckgaengig: git config --unset core.hooksPath
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
chmod +x .githooks/pre-commit .githooks/pre-push scripts/ci.py scripts/test-select.py
git config --local core.hooksPath .githooks
echo "core.hooksPath = $(git config --local core.hooksPath)"
echo "pre-commit: ci.py t0 --staged | pre-push: ci.py t1"
echo "Dev-Werkzeuge: siehe docs/dependencies.md (Abschnitt Dev-Werkzeuge); fehlende Tools: scripts/install-security-tools.sh"
