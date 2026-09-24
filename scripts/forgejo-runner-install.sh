#!/usr/bin/env bash
# Forgejo-Runner für die Doku-Seite auf dem Pi einrichten (einmalig, als root).
#
#   sudo ./scripts/forgejo-runner-install.sh --uuid <UUID> --token-file <DATEI>
#
# UUID und Token zeigt Forgejo beim Anlegen des Runners unter
#   https://ds1515.me-systeme.de/l.hentschke/picam-ai/settings/actions/runners
# Den Token vorher in eine Datei legen, nicht in die Kommandozeile tippen:
#   install -m 600 /dev/null ~/.forgejo-runner-token && nano ~/.forgejo-runner-token
# Das Skript kopiert ihn nach /etc/forgejo-runner/token (nur root lesbar) und
# löscht die Quelldatei danach.
#
# Was es tut (idempotent, erneutes Ausführen aktualisiert):
#   1. forgejo-runner in der gepinnten Version laden, SHA-256 prüfen,
#      nach /usr/local/bin installieren
#   2. Systemnutzer forgejo-runner anlegen - ohne Gruppen, also ohne Zugriff
#      auf Kamera (video), seriell (dialout) oder GPIO
#   3. /etc/forgejo-runner/{config.yml,token} schreiben
#   4. systemd/forgejo-runner.service installieren und starten
#
# Label: picam-docs (Host-Modus). Siehe .github/workflows/docs.yml.
set -euo pipefail

VERSION="13.2.0"
# SHA-256 von forgejo-runner-13.2.0-linux-arm64, am 2026-09-23 gegen die
# .sha256-Datei und die GPG-Signatur von Forgejo (Primärschlüssel
# EB11 4F5E 6C0D C2BC DD18 3550 A4B6 1A2D C592 3710) geprüft.
SHA256="9d3d462ee83e4e629f959faeacceb20eed2f25290bddea402e65ace46a31afd9"
URL="https://code.forgejo.org/forgejo/runner/releases/download/v${VERSION}/forgejo-runner-${VERSION}-linux-arm64"
INSTANCE="https://ds1515.me-systeme.de/"
LABEL="picam-docs"

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

[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausführen." >&2; exit 1; }
[[ "$(uname -m)" == "aarch64" ]] || { echo "Nur für arm64 (Pi 5) gebaut." >&2; exit 1; }
[[ "$UUID" =~ ^[0-9a-f-]{36}$ ]] || { echo "--uuid fehlt oder ist keine UUID." >&2; exit 2; }
"$ROOT/scripts/forgejo-runner-identity.sh" /etc/forgejo-runner/config.yml "$UUID" "$TOKEN_FILE"

# 1. Binary
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL -o "$tmp/forgejo-runner" "$URL"
echo "$SHA256  $tmp/forgejo-runner" | sha256sum -c --quiet
install -m 755 "$tmp/forgejo-runner" /usr/local/bin/forgejo-runner
/usr/local/bin/forgejo-runner --version

# 2. Systemnutzer ohne Zusatzgruppen
if ! id forgejo-runner >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/forgejo-runner --create-home \
        --shell /usr/sbin/nologin --user-group forgejo-runner
fi
install -d -m 750 -o forgejo-runner -g forgejo-runner /var/lib/forgejo-runner

# 3. Konfiguration und Token
install -d -m 755 /etc/forgejo-runner
if [[ -n "$TOKEN_FILE" ]]; then
    [[ -s "$TOKEN_FILE" ]] || { echo "Tokendatei leer oder nicht vorhanden: $TOKEN_FILE" >&2; exit 2; }
    tr -d ' \n\r\t' < "$TOKEN_FILE" > "$tmp/token"
    install -m 600 -o root -g root "$tmp/token" /etc/forgejo-runner/token
    shred -u "$TOKEN_FILE" 2>/dev/null || rm -f "$TOKEN_FILE"
fi
[[ -s /etc/forgejo-runner/token ]] || { echo "Kein Token: --token-file angeben." >&2; exit 2; }

cat > /etc/forgejo-runner/config.yml <<EOF
# Erzeugt von scripts/forgejo-runner-install.sh - Änderungen dort vornehmen.
log:
  level: info
runner:
  capacity: 1
  timeout: 1h
  shutdown_timeout: 10m
  fetch_interval: 10s
  labels:
    - ${LABEL}:host
cache:
  enabled: false
host:
  workdir_parent: /var/lib/forgejo-runner/work
server:
  connections:
    ds1515:
      url: ${INSTANCE}
      uuid: ${UUID}
      token_url: file:\$CREDENTIALS_DIRECTORY/token
EOF
chmod 644 /etc/forgejo-runner/config.yml

# 4. Dienst
install -m 644 "$ROOT/systemd/forgejo-runner.service" /etc/systemd/system/forgejo-runner.service
systemctl daemon-reload
systemctl enable forgejo-runner.service
systemctl restart forgejo-runner.service
sleep 5
systemctl --no-pager --lines=15 status forgejo-runner.service
systemctl is-active --quiet forgejo-runner.service
