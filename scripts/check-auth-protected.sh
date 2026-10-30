#!/usr/bin/env bash
# Prüft, dass eine Doku-Adresse ohne Anmeldung KEINEN Inhalt ausliefert.
#
#   ./scripts/check-auth-protected.sh https://verify.picam-docs.pages.dev
#
# Für jeden Probepfad muss die Antwort ein 302 auf die Forgejo-Anmeldung sein
# (FORGEJO_AUTHORIZE, Standard unten), mit leerem Rumpf. Alles andere - 200,
# 404, eine andere Weiterleitung, keine Antwort - zählt als nicht geschützt,
# Exit 1. Die Probepfade decken Seiten, statische Dateien, den Suchindex und
# nicht existierende Pfade ab, denn die Pages Function muss vor ALLEM liegen.
#
# Frisch deployte Adressen brauchen bei Cloudflare bis zu einigen Minuten,
# bis sie überall ankommen. Deshalb wird bis zu TIMEOUT_S (Standard 300)
# wiederholt, solange noch gar keine Antwort (000) oder 404 kommt. Geprüft
# wird am Ende immer das letzte Ergebnis.
set -euo pipefail

BASE="${1:?Aufruf: $0 https://host}"
AUTHORIZE="${FORGEJO_AUTHORIZE:-https://ds1515.me-systeme.de/login/oauth/authorize?}"
TIMEOUT_S="${TIMEOUT_S:-300}"
SITE_DIR="${SITE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/site}"
PATHS=(/ /index.html /docs/status.html /docs/status /api/geometrie.html /search.json
       /assets/javascripts/ /sitemap.xml /BUILD-INFO.txt /gibt-es-nicht-4711
       /docs/session-explorer.html /assets/sessions/catalog.json
       /assets/records-explorer/index.html)
# Ein echtes Manifest und ein echter Teil aus dem gebauten Archiv, falls die
# Seite Sessions enthält. Erfundene Pfade würden nur 404 hinter der Anmeldung
# prüfen, nicht die tatsächlich ausgelieferten Daten.
CATALOG="$SITE_DIR/assets/sessions/catalog.json"
if [[ -f "$CATALOG" ]] && command -v python3 >/dev/null; then
    while IFS= read -r extra; do
        [[ -n "$extra" ]] && PATHS+=("$extra")
    done < <(python3 -I - "$CATALOG" <<'PY' || true
import json, re, sys
from urllib.parse import quote
try:
    run = json.load(open(sys.argv[1], encoding="utf-8"))["runs"][0]
    part = next(p for f in run["files"] for p in f["parts"])
    for path in (run["manifest"], part["path"]):
        if isinstance(path, str) and re.fullmatch(r"[A-Za-z0-9._/-]+", path) and ".." not in path:
            print("/assets/sessions/" + quote(path, safe="/"))
except (OSError, ValueError, LookupError, TypeError, StopIteration):
    pass
PY
)
fi

probe() {
    # Ausgabe: "<code>|<location>|<bytes>" - "|" als Trenner, weil location leer sein kann
    curl -s -o /dev/null --max-time 20 -w '%{http_code}|%{redirect_url}|%{size_download}\n' "$BASE$1" || echo "000||0"
}

deadline=$(( $(date +%s) + TIMEOUT_S ))
failed=0
for p in "${PATHS[@]}"; do
    while :; do
        IFS="|" read -r code location bytes < <(probe "$p")
        [[ "$code" == "000" || "$code" == "404" ]] && (( $(date +%s) < deadline )) || break
        sleep 10
    done
    if [[ "$code" == "302" && "$location" == "$AUTHORIZE"* && "$bytes" == "0" ]]; then
        echo "geschützt:       $BASE$p"
    else
        echo "NICHT geschützt: $BASE$p (HTTP $code, Ziel: ${location:--}, $bytes Bytes)" >&2
        failed=1
    fi
done
exit $failed
