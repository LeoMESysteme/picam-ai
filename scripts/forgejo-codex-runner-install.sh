#!/usr/bin/env bash
# Einmalig als root: separaten Codex-Runner auf dem Pi installieren.
# sudo ./scripts/forgejo-codex-runner-install.sh --uuid <UUID> --token-file <DATEI>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UUID=""
TOKEN_FILE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --uuid) UUID="$2"; shift 2 ;;
        --token-file) TOKEN_FILE="$2"; shift 2 ;;
        *) echo "Unbekanntes Argument: $1" >&2; exit 2 ;;
    esac
done

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausfuehren." >&2; exit 1; }
[[ "$(uname -m)" == aarch64 ]] || { echo "Nur fuer den Pi 5 (arm64)." >&2; exit 1; }
[[ "$UUID" =~ ^[0-9a-f-]{36}$ ]] || { echo "--uuid fehlt oder ist ungueltig." >&2; exit 2; }
"$ROOT/scripts/forgejo-runner-identity.sh" /etc/picam-codex-runner/config.yml "$UUID" "$TOKEN_FILE"
command -v /usr/local/bin/forgejo-runner >/dev/null
command -v npm >/dev/null

# Codex bewusst auf eine getestete Version pinnen; /opt ist nur Installation.
npm install --prefix /opt/picam-codex --no-audit --no-fund @openai/codex@0.156.1
/opt/picam-codex/node_modules/.bin/codex --version

if ! id picam-codex-runner >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/picam-codex-runner --create-home \
        --shell /usr/sbin/nologin --user-group picam-codex-runner
fi
install -d -m 700 -o picam-codex-runner -g picam-codex-runner /var/lib/picam-codex-runner
install -d -m 700 -o picam-codex-runner -g picam-codex-runner /var/lib/picam-codex-runner/.codex
install -d -m 700 -o picam-codex-runner -g picam-codex-runner /var/lib/picam-codex-runner/work
install -d -m 750 -o root -g picam-codex-runner /etc/picam-codex-runner

if [[ -n "$TOKEN_FILE" ]]; then
    [[ -s "$TOKEN_FILE" ]] || { echo "Tokendatei fehlt oder ist leer." >&2; exit 2; }
    install -m 600 -o root -g root "$TOKEN_FILE" /etc/picam-codex-runner/token
    shred -u "$TOKEN_FILE" 2>/dev/null || rm -f "$TOKEN_FILE"
fi
[[ -s /etc/picam-codex-runner/token ]] || { echo "Runner-Token fehlt." >&2; exit 2; }

cat > /etc/picam-codex-runner/config.yml <<EOF
# Erzeugt von scripts/forgejo-codex-runner-install.sh.
log:
  level: info
runner:
  capacity: 1
  timeout: 1h
  shutdown_timeout: 10m
  fetch_interval: 10s
  labels:
    - picam-codex-docs:host
cache:
  enabled: false
host:
  workdir_parent: /var/lib/picam-codex-runner/work
server:
  connections:
    ds1515:
      url: https://ds1515.me-systeme.de/
      uuid: ${UUID}
      token_url: file:\$CREDENTIALS_DIRECTORY/token
EOF
chmod 644 /etc/picam-codex-runner/config.yml
install -m 644 "$ROOT/systemd/forgejo-codex-runner.service" /etc/systemd/system/forgejo-codex-runner.service
systemctl daemon-reload
systemctl enable forgejo-codex-runner.service
systemctl restart forgejo-codex-runner.service
sleep 5
systemctl --no-pager --lines=12 status forgejo-codex-runner.service
systemctl is-active --quiet forgejo-codex-runner.service
