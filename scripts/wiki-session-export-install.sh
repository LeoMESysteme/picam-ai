#!/usr/bin/env bash
# Install only the new optional exporter. Existing runners and Workbench stay running.
# Run during a maintenance pause: sudo ./scripts/wiki-session-export-install.sh
# Idempotent: a second run updates code and units and migrates an older archive.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID -eq 0 ]] || { echo 'Bitte mit sudo in einer Messpause ausführen.' >&2; exit 1; }
id me-systeme >/dev/null
getent group forgejo-runner >/dev/null
[[ -d /var/lib/forgejo-runner ]] || { echo '/var/lib/forgejo-runner fehlt (Runner nicht eingerichtet).' >&2; exit 1; }
[[ -x "$ROOT/.venv/bin/python" ]] || { echo 'Projekt-.venv fehlt.' >&2; exit 1; }
[[ "$ROOT" != *'"'* && "$ROOT" != *$'\n'* ]] || { echo 'Ungültiger Projektpfad.' >&2; exit 1; }
EXPORT=/srv/picam-wiki-export
ARCHIVE=$EXPORT/archive
REQUEST=/var/lib/forgejo-runner/wiki-export-request

# Keine laufende Exportphase während Migration und Unit-Wechsel.
systemctl stop picam-wiki-export.path picam-wiki-export.service 2>/dev/null || true

# No runner can modify source code, configuration or snapshots. The request
# has a fixed meaning; its content is never read, executed or passed on.
install -d -m 755 -o root -g root "$EXPORT" /usr/local/lib/picam-wiki-export
install -d -m 2750 -o me-systeme -g forgejo-runner "$ARCHIVE"
# Der Runner darf wegen ProtectSystem=strict nur unter /var/lib/forgejo-runner
# schreiben; dort liegt die Anfrage. Die alte Datei unter /srv war für ihn
# nie beschreibbar und entfällt.
# Die Datei legt der Runner selbst an (PathChanged reagiert auch aufs
# Anlegen); root schreibt nichts in dieses für CI-Jobs beschreibbare Verzeichnis.
rm -f "$EXPORT/request"

# Migration eines älteren Archivs: Gruppe und setgid auf allen Verzeichnissen
# wiederherstellen (ein chmod durch me-systeme löscht setgid, weil der Dienst
# nicht in forgejo-runner ist), den gemeinsamen Blockspeicher auf 0640-Dateien
# in einem privaten 2700-Verzeichnis umstellen. Keine Symlinks verfolgen.
chgrp -hR forgejo-runner "$ARCHIVE"
find "$ARCHIVE" -type d -exec chmod g+s {} +
if [[ -d "$ARCHIVE/blocks" && ! -L "$ARCHIVE/blocks" ]]; then
    chmod 2700 "$ARCHIVE/blocks"
    find "$ARCHIVE/blocks" -maxdepth 1 -type f -name '*.gz.bin' -exec chmod 0640 {} +
fi
if [[ -d "$ARCHIVE/snapshots" && ! -L "$ARCHIVE/snapshots" ]]; then
    chmod 2750 "$ARCHIVE/snapshots"
fi

install -m 644 -o root -g root "$ROOT/scripts/wiki_sessions.py" /usr/local/lib/picam-wiki-export/wiki_sessions.py
install -m 644 -o root -g root "$ROOT/scripts/wiki_session_export_service.py" /usr/local/lib/picam-wiki-export/wiki_session_export_service.py
cat > /usr/local/lib/picam-wiki-export/run <<'SH'
#!/usr/bin/env bash
set -euo pipefail
exec "$PICAM_EXPORT_PYTHON" /usr/local/lib/picam-wiki-export/wiki_session_export_service.py
SH
chmod 755 /usr/local/lib/picam-wiki-export/run
cat > /etc/picam-wiki-export.conf <<EOF2
PICAM_EXPORT_PYTHON="$ROOT/.venv/bin/python"
PICAM_EXPORT_SOURCE="$ROOT/var/live"
EOF2
chmod 644 /etc/picam-wiki-export.conf
install -m 644 "$ROOT/systemd/picam-wiki-export.service" /etc/systemd/system/picam-wiki-export.service
install -m 644 "$ROOT/systemd/picam-wiki-export.path" /etc/systemd/system/picam-wiki-export.path
systemctl daemon-reload
# Only the path unit is (re)started so it watches the new request path.
# No restart of the runner, the Workbench or any other service.
systemctl enable picam-wiki-export.path
systemctl restart picam-wiki-export.path
echo "Exportanfrage: $REQUEST (legt der Runner beim nächsten Deploy an). Keine Workbench und kein bestehender Runner neu gestartet."
