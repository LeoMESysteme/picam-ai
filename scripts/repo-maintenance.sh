#!/usr/bin/env bash
# Unbeaufsichtigte taegliche Doku-Pflege, per @reboot-Cron kurz nach dem
# morgendlichen Boot des Pi ausgefuehrt (der Pi ist nachts aus).
#
# Ruft `claude -p` mit einem festen Prompt (repo-maintenance-prompt.md) auf,
# beschraenkt auf Dateibearbeitung (kein Bash/Agent/WebFetch fuer die Claude-
# Session), committet danach automatisch NUR wenn ausschliesslich docs/ und
# CHANGELOG.md geaendert wurden. Bricht kommentarlos-sicher ab, wenn der
# Arbeitsbaum vor dem Lauf schon schmutzig ist (mischt sonst manuelle und
# automatische Aenderungen in einem Commit).
#
# Installation (einmalig):
#   (crontab -l 2>/dev/null; echo "@reboot sleep 20 && /home/me-systeme/picam-ai/scripts/repo-maintenance.sh") | crontab -
#
# Bezug: CLAUDE.md (Einstiegsreihenfolge, Doku-Pflicht), AGENTS.md
# (Dokumentationspflicht-Tabelle: OQ-Eintraege nie loeschen).

set -uo pipefail

REPO="/home/me-systeme/picam-ai"
CLAUDE_BIN="/home/me-systeme/.local/bin/claude"
STATE_DIR="/home/me-systeme/.local/state/picam-ai-maintenance"
LOG_FILE="$STATE_DIR/$(date -u +%Y-%m-%d).log"
LOCK_FILE="$STATE_DIR/run.lock"
ALLOWED_PATH_RE='^(docs/|CHANGELOG\.md$)'

mkdir -p "$STATE_DIR"
exec >>"$LOG_FILE" 2>&1
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "$(date -Is) already running, exiting"; exit 0; }

echo "=== repo-maintenance run: $(date -Is) ==="
cd "$REPO" || { echo "cannot cd to $REPO"; exit 1; }

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "not a git repo, aborting"
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "working tree already dirty before run — skipping entirely to avoid" \
         "mixing manual and automated changes"
    exit 0
fi

echo "waiting for network..."
NETWORK_UP=0
for _ in $(seq 1 30); do
    if curl -sS --max-time 5 -o /dev/null https://api.anthropic.com >/dev/null 2>&1; then
        NETWORK_UP=1
        break
    fi
    sleep 10
done
if [ "$NETWORK_UP" -ne 1 ]; then
    echo "no network after 5 minutes, aborting"
    exit 1
fi

PROMPT_FILE="$REPO/scripts/repo-maintenance-prompt.md"

CLAUDE_OUTPUT="$("$CLAUDE_BIN" -p "$(cat "$PROMPT_FILE")" \
    --permission-mode acceptEdits \
    --disallowedTools "Bash,Agent,WebFetch,WebSearch" \
    --model claude-sonnet-5 2>&1)"
CLAUDE_STATUS=$?
printf '%s\n' "$CLAUDE_OUTPUT"
echo "claude exit status: $CLAUDE_STATUS"

CHANGED="$(git status --porcelain | cut -c4-)"
if [ -z "$CHANGED" ]; then
    echo "no changes to commit"
    echo "=== run finished: $(date -Is) ==="
    exit 0
fi

DISALLOWED="$(echo "$CHANGED" | grep -Ev "$ALLOWED_PATH_RE" || true)"
if [ -n "$DISALLOWED" ]; then
    echo "ABORT: touched files outside docs/ or CHANGELOG.md, leaving" \
         "uncommitted for manual review:"
    echo "$DISALLOWED"
    exit 1
fi

# Claude writes its own commit message (see repo-maintenance-prompt.md),
# delimited so it survives being embedded in a wider response. Fall back to
# a generic, clearly-labeled message if parsing fails rather than losing
# the day's changes.
CLAUDE_SUBJECT_BODY="$(printf '%s\n' "$CLAUDE_OUTPUT" \
    | sed -n '/^===COMMIT-MESSAGE-START===$/,/^===COMMIT-MESSAGE-END===$/p' \
    | sed '1d;$d')"

if [ -n "$CLAUDE_SUBJECT_BODY" ]; then
    FULL_MSG="$CLAUDE_SUBJECT_BODY

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
else
    echo "WARNING: could not parse a commit message from claude's output," \
         "falling back to a generic one"
    FULL_MSG="Automatisierte Doku-Pflege (geplante Routine, Commit-Message-Parsing fehlgeschlagen)

Details zu den vorgenommenen Aenderungen im Log unter
~/.local/state/picam-ai-maintenance/$(date -u +%Y-%m-%d).log.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
fi

git add -- docs CHANGELOG.md
git commit -m "$FULL_MSG"
echo "committed: $(git rev-parse --short HEAD)"
echo "=== run finished: $(date -Is) ==="
