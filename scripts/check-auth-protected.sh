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
PATHS=(/ /index.html /docs/status.html /docs/status /api/geometrie.html /search.json
       /assets/javascripts/ /sitemap.xml /BUILD-INFO.txt /gibt-es-nicht-4711)

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
