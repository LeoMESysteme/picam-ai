#!/usr/bin/env bash
# Einmalig als root: Codex-Anmeldung des Doku-Runners an ~/.codex/auth.json
# des aufrufenden Nutzers koppeln (docs/HOSTING.md).
# sudo ./scripts/picam-codex-auth-sync-install.sh [--user <NAME>]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTH_USER="${SUDO_USER:-}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --user) AUTH_USER="$2"; shift 2 ;;
        *) echo "Unbekanntes Argument: $1" >&2; exit 2 ;;
    esac
done

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausfuehren." >&2; exit 1; }
[[ -n "$AUTH_USER" && "$AUTH_USER" != root ]] || { echo "--user fehlt." >&2; exit 2; }
id picam-codex-runner >/dev/null 2>&1 || { echo "Erst forgejo-codex-runner-install.sh ausfuehren." >&2; exit 1; }
AUTH_HOME="$(getent passwd "$AUTH_USER" | cut -d: -f6)"
[[ -f "$AUTH_HOME/.codex/auth.json" ]] || { echo "$AUTH_HOME/.codex/auth.json fehlt: erst lokal 'codex login'." >&2; exit 1; }

install -m 755 -o root -g root "$ROOT/scripts/picam-codex-auth-sync" /usr/local/bin/picam-codex-auth-sync
install -d -m 750 -o root -g picam-codex-runner /etc/picam-codex-runner
printf 'AUTH_USER=%s\n' "$AUTH_USER" > /etc/picam-codex-runner/auth-sync.env
chmod 644 /etc/picam-codex-runner/auth-sync.env
for unit in service path; do
    sed "s#AUTH_HOME#$AUTH_HOME#" "$ROOT/systemd/picam-codex-auth-sync.$unit" > "/etc/systemd/system/picam-codex-auth-sync.$unit"
    chmod 644 "/etc/systemd/system/picam-codex-auth-sync.$unit"
done
systemctl daemon-reload
systemctl enable picam-codex-auth-sync.service picam-codex-auth-sync.path
systemctl restart picam-codex-auth-sync.path
systemctl start picam-codex-auth-sync.service
journalctl -u picam-codex-auth-sync.service -n 3 --no-pager --output=cat
runuser -u picam-codex-runner -- env HOME=/var/lib/picam-codex-runner \
    CODEX_HOME=/var/lib/picam-codex-runner/.codex \
    /opt/picam-codex/node_modules/.bin/codex login status
