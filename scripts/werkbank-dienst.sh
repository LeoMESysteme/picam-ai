#!/usr/bin/env bash
# Bestehenden systemd-Benutzerdienst verwalten; kein Installieren/Provisionieren.
set -euo pipefail
trap 'printf "✗ Dienstbefehl fehlgeschlagen (Zeile %s).\n" "$LINENO" >&2' ERR
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
die() { printf '✗ %s\n' "$*" >&2; exit 1; }
usage() {
    cat <<'HELP'
werkbank-dienst.sh start|stop|restart|status|logs --host ADRESSE --port PORT [Optionen]
  --data PFAD              Werkbankdaten (sonst <repo>/var/workbench)
  --live-data PFAD         Live-Daten (sonst <repo>/var/live)
  --socket PFAD            Steuerung (sonst <repo>/var/run/werkbank/control.sock)
  --bridge-directory PFAD  Provisionierte Identitaet (sonst <repo>/var/workbench/bridge)
  --endpoint URL           Oeffentlicher Endpunkt (sonst https://HOST:PORT/bridge/v2)
  --unit NAME              Sonst dispread-werkbank-bruecke
  --wait-seconds N         HTTPS-Wartefrist bei restart (sonst 60 Sekunden)
  --force                 Stoppsperre ueberstimmen; kann einen Messlauf abbrechen
Relative Pfadoptionen beziehen sich auf die Repo-Wurzel. logs folgt dem Journal.
HELP
}
[[ $# -gt 0 ]] || { usage; exit 1; }
action=$1; shift
case "$action" in
    -h|--help) usage; exit 0 ;;
    start|stop|restart|status|logs) ;;
    *) die "Unbekannter Befehl: $action" ;;
esac
host= port= data= live_data= socket= bridge= endpoint=
unit=dispread-werkbank-bruecke
force=false
wait_seconds=60
while (( $# )); do
    case "$1" in
        --force) force=true; shift; continue ;;
        -h|--help) usage; exit 0 ;;
        --host|--port|--data|--live-data|--socket|--bridge-directory|--endpoint|--unit|--wait-seconds)
            [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || die "Wert fehlt fuer $1" ;;
        *) die "Unbekannte Option: $1" ;;
    esac
    case "$1" in
        --host) host=$2 ;; --port) port=$2 ;; --data) data=$2 ;;
        --live-data) live_data=$2 ;; --socket) socket=$2 ;;
        --bridge-directory) bridge=$2 ;; --endpoint) endpoint=$2 ;;
        --unit) unit=$2 ;; --wait-seconds) wait_seconds=$2 ;;
    esac
    shift 2
done
[[ -n "$host" && -n "$port" ]] || die '--host und --port sind Pflichtangaben.'
[[ "$host" =~ ^[a-zA-Z0-9.:_-]+$ && "$host" != -* ]] || die 'Host ohne Schema, Pfad oder IPv6-Klammern angeben.'
[[ "$port" =~ ^[0-9]{1,5}$ ]] && (( 10#$port >= 1 && 10#$port <= 65535 )) || die 'Port muss zwischen 1 und 65535 liegen.'
[[ "$unit" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.@-]*$ ]] || die 'Ungueltiger Unitname.'
[[ "$wait_seconds" =~ ^[0-9]{1,4}$ ]] && (( 10#$wait_seconds > 0 )) || die 'Wartefrist muss positiv sein (Sekunden).'
port=$((10#$port))
wait_seconds=$((10#$wait_seconds))
[[ -x "$PYTHON" ]] || die "Projekt-Python fehlt: $PYTHON"
cd "$ROOT"
# Defaults aus derselben Python-Quelle wie dispread serve, keine zweite Pfadwelt.
defaults=$("$PYTHON" - <<'PY'
from dispread.defaults import BRIDGE_DIR, LIVE_DATA_DIR, WORKBENCH_DATA_DIR
print(WORKBENCH_DATA_DIR)
print(LIVE_DATA_DIR)
print(BRIDGE_DIR)
PY
)
mapfile -t default_paths <<< "$defaults"
absolute() { if [[ "$1" == /* ]]; then printf '%s' "$1"; else printf '%s/%s' "$ROOT" "$1"; fi; }
data=$(absolute "${data:-${default_paths[0]}}")
live_data=$(absolute "${live_data:-${default_paths[1]}}")
bridge=$(absolute "${bridge:-${default_paths[2]}}")
socket=$(absolute "${socket:-var/run/werkbank/control.sock}")
url_host=$host
[[ "$host" != *:* ]] || url_host="[$host]"
endpoint=${endpoint:-https://$url_host:$port/bridge/v2}

check_linger() {
    if [[ "$(loginctl show-user "$(id -un)" --property=Linger --value 2>/dev/null || true)" != yes ]]; then
        printf 'Hinweis: Linger fehlt/ist unbekannt. Fuer Betrieb nach Abmeldung manuell: loginctl enable-linger %s\n' "$(id -un)" >&2
    fi
}
start_service() {
    local socket_dir
    socket_dir=$(dirname "$socket")
    # Niemals einem fremden/symlinkten Socket-Verzeichnis Rechte umschreiben.
    [[ ! -L "$socket_dir" ]] || die "Socket-Verzeichnis ist ein Symlink: $socket_dir"
    mkdir -p -m 0700 -- "$socket_dir"
    [[ -O "$socket_dir" ]] || die "Socket-Verzeichnis gehoert einem anderen Benutzer: $socket_dir"
    chmod 0700 -- "$socket_dir"
    check_linger
    systemd-run --user "--unit=$unit" "--working-directory=$ROOT" \
        "--setenv=PYTHONPATH=$ROOT/src" --property=TimeoutStopSec=20s \
        -- "$PYTHON" -m dispread.workbench.cli serve \
        --host "$host" --port "$port" --data "$data" --live-data "$live_data" \
        --socket "$socket" --bridge-directory "$bridge" --bridge-endpoint "$endpoint"
    printf '✓ Startauftrag fuer %s uebergeben.\n' "$unit"
}
guard_stop() {
    if "$force"; then
        printf 'WARNUNG: --force ueberstimmt die Stoppsperre; ein aktiver Lauf kann abgebrochen werden.\n' >&2
        return
    fi
    local state status
    state=$(systemctl --user show "$unit" --property ActiveState --value) || die 'Dienstzustand unbekannt; Stop verweigert.'
    case "$state" in
        inactive|failed) return ;;
        active|activating|reloading) ;;
        *) die "Dienstzustand $state ist nicht sicher stoppbar; ggf. --force." ;;
    esac
    status=$(timeout 5s "$PYTHON" -m dispread.workbench.cli live status --socket "$socket") \
        || die 'Live-Status nicht erreichbar; Stop verweigert (ggf. --force).'
    if ! "$PYTHON" -c '
import json, sys
try:
    status = json.load(sys.stdin)
    safe = (isinstance(status, dict)
            and status.get("state") in {"idle", "setup_ready", "setup_failed", "confirmed", "stopped"}
            and status.get("diagnose_kopie") is False)
except (ValueError, TypeError):
    safe = False
sys.exit(0 if safe else 1)
' <<< "$status"; then
        die 'Lauf/Einrichtung/Diagnosekopie aktiv oder Status unbekannt; Stop verweigert (ggf. --force).'
    fi
}
stop_service() {
    guard_stop
    local code=0 result
    timeout 30s systemctl --user stop "$unit" || code=$?
    result=$(systemctl --user show "$unit" --property Result --value) || result=unknown
    if [[ "$result" == timeout || "$code" == 124 ]]; then
        systemctl --user reset-failed "$unit"
        die 'Stop-Zeitueberschreitung; reset-failed ausgefuehrt. Zustand vor erneutem Start pruefen.'
    fi
    (( code == 0 )) || die "Stop fehlgeschlagen (Exit $code)."
    printf '✓ %s gestoppt.\n' "$unit"
}
wait_ready() {
    local deadline=$((SECONDS + wait_seconds))
    # Selbstsigniertes Zertifikat: ausschliesslich Erreichbarkeit, keine
    # Zugangsdaten und kein Vertrauensnachweis. Auch Login-Redirect ist bereit.
    while (( SECONDS < deadline )); do
        if curl --insecure --silent --show-error --fail --max-time 2 --output /dev/null \
            "https://$url_host:$port/live" 2>/dev/null; then
            printf '✓ https://%s:%s/live antwortet.\n' "$url_host" "$port"
            return
        fi
        sleep 1
    done
    die "HTTPS antwortet nicht innerhalb von $wait_seconds Sekunden; Journal pruefen."
}
case "$action" in
    start) start_service ;;
    stop) stop_service ;;
    restart) stop_service; start_service; wait_ready ;;
    status) systemctl --user status --no-pager "$unit" ;;
    logs) journalctl --user -u "$unit" -f ;;
esac
