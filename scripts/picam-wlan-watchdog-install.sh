#!/usr/bin/env bash
# Einmalig als root: WLAN-Waechter installieren (docs/HOST_NETZWERK.md).
# sudo ./scripts/picam-wlan-watchdog-install.sh
# Rueckbau: sudo systemctl disable --now picam-wlan-watchdog.timer
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID -eq 0 ]] || { echo "Bitte mit sudo ausfuehren." >&2; exit 1; }

install -d -m 755 -o root -g root /usr/local/lib/picam-wlan-watchdog
install -m 755 -o root -g root "$ROOT/scripts/picam-wlan-watchdog" /usr/local/lib/picam-wlan-watchdog/run
for unit in service timer; do
    install -m 644 -o root -g root "$ROOT/systemd/picam-wlan-watchdog.$unit" "/etc/systemd/system/picam-wlan-watchdog.$unit"
done
systemctl daemon-reload
systemctl enable --now picam-wlan-watchdog.timer
systemctl start picam-wlan-watchdog.service
systemctl list-timers picam-wlan-watchdog.timer --no-pager
