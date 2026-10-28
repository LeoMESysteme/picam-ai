#!/usr/bin/env bash
# Install only the new optional exporter. Existing runners and Workbench stay running.
# Run during a maintenance pause: sudo ./scripts/wiki-session-export-install.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID -eq 0 ]] || { echo 'Bitte mit sudo in einer Messpause ausführen.' >&2; exit 1; }
id me-systeme >/dev/null
getent group forgejo-runner >/dev/null
[[ -x "$ROOT/.venv/bin/python" ]] || { echo 'Projekt-.venv fehlt.' >&2; exit 1; }
# No runner can modify source code, configuration or snapshots. The request
# has a fixed meaning; its content is never executed or passed as arguments.
install -d -m 755 -o root -g root /srv/picam-wiki-export /usr/local/lib/picam-wiki-export
install -d -m 2750 -o me-systeme -g forgejo-runner /srv/picam-wiki-export/archive
if [[ ! -e /srv/picam-wiki-export/request ]]; then
    install -m 600 -o forgejo-runner -g forgejo-runner /dev/null /srv/picam-wiki-export/request
fi
install -m 644 -o root -g root "$ROOT/scripts/wiki_sessions.py" /usr/local/lib/picam-wiki-export/wiki_sessions.py
install -m 644 -o root -g root "$ROOT/scripts/wiki_session_export_service.py" /usr/local/lib/picam-wiki-export/wiki_session_export_service.py
cat > /usr/local/lib/picam-wiki-export/run <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec "$PICAM_EXPORT_PYTHON" /usr/local/lib/picam-wiki-export/wiki_session_export_service.py
SH
chmod 755 /usr/local/lib/picam-wiki-export/run
[[ "$ROOT" != *'"'* && "$ROOT" != *$'\n'* ]] || { echo 'Ungültiger Projektpfad.' >&2; exit 1; }
cat > /etc/picam-wiki-export.conf <<EOF
PICAM_EXPORT_PYTHON="$ROOT/.venv/bin/python"
PICAM_EXPORT_SOURCE="$ROOT/var/live"
EOF
chmod 644 /etc/picam-wiki-export.conf
install -m 644 "$ROOT/systemd/picam-wiki-export.service" /etc/systemd/system/picam-wiki-export.service
install -m 644 "$ROOT/systemd/picam-wiki-export.path" /etc/systemd/system/picam-wiki-export.path
systemctl daemon-reload
# Only the new path unit is enabled. No restart of an existing service.
systemctl enable --now picam-wiki-export.path
echo 'Exportanfrage eingerichtet. Keine Workbench und kein bestehender Runner neu gestartet.'
