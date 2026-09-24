#!/usr/bin/env bash
# Refuse to combine a new Forgejo runner UUID with an existing runner token.
set -euo pipefail

CONFIG=${1:?configuration path missing}
REQUESTED_UUID=${2:?runner UUID missing}
TOKEN_FILE=${3-}

if [[ -f "$CONFIG" && -z "$TOKEN_FILE" ]]; then
    EXISTING_UUID=$(awk '$1 == "uuid:" {print $2; exit}' "$CONFIG")
    if [[ "$EXISTING_UUID" != "$REQUESTED_UUID" ]]; then
        echo "Vorhandene Runner-UUID ($EXISTING_UUID) weicht von --uuid ab. Neue UUID nur zusammen mit passendem --token-file verwenden." >&2
        echo "Fuer den Codex-Runner das separate Skript scripts/forgejo-codex-runner-install.sh verwenden." >&2
        exit 1
    fi
fi
