#!/usr/bin/env bash
# Installiert die Security-Werkzeuge nutzerlokal und reproduzierbar:
#   - gitleaks (arm64/amd64-Release von GitHub, SHA256 gegen checksums.txt geprueft) nach ~/.local/bin
#   - bandit in ein eigenes venv (.venv-tools), NICHT in .venv
#     (.venv nutzt --system-site-packages und die ABI-Regel aus pyproject.toml)
# Aufruf: scripts/install-security-tools.sh   (idempotent)
set -euo pipefail

GITLEAKS_VERSION="${GITLEAKS_VERSION:-8.30.1}"
BANDIT_VERSION="${BANDIT_VERSION:-1.8.6}"
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_VENV="${TOOLS_VENV:-$REPO_ROOT/.venv-tools}"

case "$(uname -m)" in
  aarch64|arm64) ARCH="arm64" ;;
  x86_64|amd64)  ARCH="x64" ;;
  *) echo "FEHLER: Architektur $(uname -m) nicht unterstuetzt" >&2; exit 1 ;;
esac

install_gitleaks() {
  if [ -x "$BIN_DIR/gitleaks" ] && "$BIN_DIR/gitleaks" version 2>/dev/null | grep -q "$GITLEAKS_VERSION"; then
    echo "gitleaks $GITLEAKS_VERSION bereits installiert ($BIN_DIR/gitleaks)"
    return
  fi
  local base="https://github.com/gitleaks/gitleaks/releases/download/v$GITLEAKS_VERSION"
  local tarball="gitleaks_${GITLEAKS_VERSION}_linux_$ARCH.tar.gz"
  local tmp; tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  curl -fsSL -o "$tmp/$tarball" "$base/$tarball"
  curl -fsSL -o "$tmp/checksums.txt" "$base/gitleaks_${GITLEAKS_VERSION}_checksums.txt"
  # Nur die Zeile fuer unser Archiv pruefen; Abbruch bei Abweichung (set -e)
  (cd "$tmp" && grep " $tarball\$" checksums.txt | sha256sum -c -)
  mkdir -p "$BIN_DIR"
  tar -xzf "$tmp/$tarball" -C "$tmp" gitleaks
  install -m 0755 "$tmp/gitleaks" "$BIN_DIR/gitleaks"
  echo "gitleaks installiert: $("$BIN_DIR/gitleaks" version) -> $BIN_DIR/gitleaks"
}

install_bandit() {
  if [ ! -x "$TOOLS_VENV/bin/python" ]; then
    python3 -m venv "$TOOLS_VENV"
  fi
  "$TOOLS_VENV/bin/pip" install --quiet --upgrade "bandit==$BANDIT_VERSION"
  echo "bandit installiert: $("$TOOLS_VENV/bin/bandit" --version | head -1) -> $TOOLS_VENV/bin/bandit"
}

install_gitleaks
install_bandit
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "Hinweis: $BIN_DIR ist nicht im PATH." ;;
esac
