#!/usr/bin/env bash
set -euo pipefail
trap 'printf "✗ Installation fehlgeschlagen (Zeile %s).\n" "$LINENO" >&2' ERR
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ok() { printf '✓ %s\n' "$*"; }
hint() { printf '✗ Hinweis: %s\n' "$*" >&2; }

# Nur fehlende Pakete installieren; ein zweiter Lauf startet apt nicht erneut.
missing=()
while IFS= read -r line || [[ -n "$line" ]]; do
    package="${line%%#*}"
    package="${package//[[:space:]]/}"
    [[ -n "$package" ]] || continue
    [[ "$package" =~ ^[a-z0-9][a-z0-9+.-]+$ ]] || { hint "Ungueltiges Paket: $package"; exit 1; }
    if [[ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" == 'install ok installed' ]]; then
        ok "$package bereits vorhanden"
    else
        missing+=("$package")
    fi
done < "$ROOT/packaging/apt-packages.txt"
if (( ${#missing[@]} )); then
    sudo apt-get install -y -- "${missing[@]}"
    ok "Fehlende Systempakete installiert"
fi

if [[ -e .venv && ! -x .venv/bin/python ]]; then
    hint '.venv existiert, ist aber keine nutzbare Python-Umgebung; bitte manuell pruefen.'
    exit 1
fi
if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv --system-site-packages .venv
    ok '.venv angelegt'
else
    ok '.venv bereits vorhanden'
fi
if ! grep -Eq '^include-system-site-packages = true$' .venv/pyvenv.cfg; then
    hint '.venv braucht --system-site-packages; vorhandene Umgebung nicht veraendert.'
    exit 1
fi
./.venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 13) else "Python >= 3.13 erforderlich")'
# Editable-Installation muss zu diesem Checkout und seiner Paketversion gehoeren.
if [[ -x .venv/bin/dispread ]] && ./.venv/bin/python - <<'PY'
import importlib.metadata
import json
import pathlib
import sys
import tomllib

root = pathlib.Path.cwd()
project = tomllib.loads((root / 'pyproject.toml').read_text())['project']
try:
    dist = importlib.metadata.distribution(project['name'])
    direct = json.loads(dist.read_text('direct_url.json') or '{}')
except (importlib.metadata.PackageNotFoundError, ValueError):
    sys.exit(1)
sys.exit(0 if dist.version == project['version']
         and direct.get('url') == root.as_uri()
         and direct.get('dir_info', {}).get('editable') else 1)
PY
then
    ok 'Projektinstallation bereits vorhanden'
else
    ./.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
    ok 'Projekt installiert'
fi

# Hardware-/Boot-Konfiguration nur lesen. Kein usermod, Boot-Edit oder Neustart.
account="$(id -un)"
groups=" $(id -nG) "
for group in dialout video; do
    if [[ "$groups" == *" $group "* ]]; then
        ok "Gruppenmitgliedschaft $group bereits vorhanden"
    else
        hint "Gruppe $group fehlt. Manuell: sudo usermod -aG $group $account ; danach neu anmelden."
    fi
done
boot=/boot/firmware
[[ -f "$boot/config.txt" ]] || boot=/boot
if grep -Eq '^[[:space:]]*dtparam=uart0=on([[:space:]]*(#.*)?)?$' "$boot/config.txt"; then
    ok 'dtparam=uart0=on als Boot-Eintrag vorhanden (Abschnitt/aktive Konfiguration manuell pruefen)'
else
    hint "UART0-Eintrag fehlt. Manuell: printf '\\n[all]\\ndtparam=uart0=on\\n' | sudo tee -a $boot/config.txt ; Neustart selbst planen."
fi
if [[ ! -r /proc/cmdline || ! -r "$boot/cmdline.txt" ]]; then
    hint "Serielle Konsole unbekannt: /proc/cmdline oder $boot/cmdline.txt nicht lesbar. Manuell: cat /proc/cmdline $boot/cmdline.txt"
elif grep -Eq '(^|[[:space:]])console=(serial[0-9]+|ttyAMA[0-9]+|ttyS[0-9]+)(,|[[:space:]]|$)' /proc/cmdline "$boot/cmdline.txt"; then
    hint 'Serielle Konsole konfiguriert. Manuell: sudo raspi-config nonint do_serial_cons 1 ; Neustart selbst planen.'
else
    code=$?
    if (( code == 1 )); then
        ok 'Keine serielle Konsole in Kernel-/Boot-Kommandozeile gefunden'
    else
        hint 'Serielle Konsole unbekannt: Kernel-/Boot-Kommandozeile konnte nicht geprueft werden.'
    fi
fi
for device in ttyAMA0 serial0; do
    if systemctl is-active --quiet "serial-getty@$device.service"; then
        hint "Serielles Getty aktiv. Manuell: sudo systemctl disable --now serial-getty@$device.service"
    fi
done

cat <<'NEXT'
✓ Software eingerichtet. Hardware-Hinweise oben vor dem Einsatz klaeren.
Naechste Schritte im Projektverzeichnis (<adresse> durch die von Windows erreichbare Adresse ersetzen):
  1. ./.venv/bin/dispread bridge identity --provision
  2. ./.venv/bin/dispread init-tls --host <adresse>
  3. scripts/werkbank-dienst.sh start --host <adresse> --port <port>
  4. ./.venv/bin/dispread bridge export-profile --name 'Dispread Pi' --endpoint https://<adresse>:<port>/bridge/v2 --output profil.json --pair
Die Bruecke verwendet ihr eigenes gepinntes Identitaetszertifikat; init-tls
richtet den separaten klassischen Browser-TLS-Weg ein (siehe Betriebsanleitung).
Vorlagen und Timing-Kalibrierung muessen vor einem Messlauf bereitgestellt sein.
NEXT
