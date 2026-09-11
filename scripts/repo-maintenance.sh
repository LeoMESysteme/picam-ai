#!/usr/bin/env bash
# Unbeaufsichtigte taegliche Doku-Pflege, per @reboot-Cron kurz nach dem
# morgendlichen Boot des Pi ausgefuehrt (der Pi ist nachts aus).
#
# Ruft `claude -p` mit einem festen Prompt (repo-maintenance-prompt.md) auf,
# beschraenkt auf Dateibearbeitung (kein Bash/Agent/WebFetch fuer die Claude-
# Session), pro lokalem Branch, und committet danach automatisch NUR wenn
# ausschliesslich docs/ und CHANGELOG.md geaendert wurden UND eine
# parsebare Commit-Message vorliegt. Ein Lauf, der mittendrin stirbt
# (gekillt, Absturz, Netzwerkriss) hinterlaesst entweder gar keine oder
# unparsebare Aenderungen und wird NIE committet — siehe ABORT_REASON
# unten, das ist die Faelle abdeckt, die der reine Exit-Code verpassen kann
# (ein gekillter und dann reaped `claude -p` kann trotzdem 0 liefern).
#
# Bricht sicher ab, wenn docs/ oder CHANGELOG.md auf dem jeweiligen Branch
# vor dem Zugriff schon schmutzig sind (mischt sonst manuelle und
# automatische Aenderungen). Unrelated Werkstattunordnung im Rest des Baums
# (z. B. nicht committete Tooling-Dateien) blockiert die Routine bewusst
# NICHT — nur docs/ und CHANGELOG.md zaehlen fuer diese Pruefung.
#
# Wenn ein Branch nicht sauber committet werden kann (Parse-Fehler,
# Fremdpfade, oder schon vor dem Checkout schmutzig), werden etwaige
# Aenderungen gestasht (nichts geht verloren) und GENAU DIESER Branch wird in
# einer Markerdatei ($STATE_DIR/needs-review) eingetragen — jeder weitere
# Lauf ueberspringt ihn, bis ein Mensch die Zeile entfernt (oder die Datei
# loescht), waehrend andere Branches im selben und in kuenftigen Laeufen
# weiter gepflegt werden. Ohne diese Markerdatei waere ein Stash sonst
# unsichtbar fuer `git status` und wuerde sich auf demselben Branch Nacht
# fuer Nacht unbemerkt wiederholen.
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
NEEDS_REVIEW_FILE="$STATE_DIR/needs-review"
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

# Scoped on purpose: unrelated workspace clutter elsewhere in the tree must
# never block this routine, and (with the branch loop) must never falsely
# look like "claude touched something outside docs/" either.
docs_dirty() {
    [ -n "$(git status --porcelain -- docs CHANGELOG.md)" ]
}

# A branch stays blocked (skipped, never retried) as long as its own
# "branch: <name>" line is still present in the needs-review marker file —
# removing that line (or the whole file) is the human's signal to retry it.
branch_needs_review() {
    [ -f "$NEEDS_REVIEW_FILE" ] && grep -qFx "branch: $1" "$NEEDS_REVIEW_FILE"
}

if [ -f "$NEEDS_REVIEW_FILE" ]; then
    echo "NOTE: $NEEDS_REVIEW_FILE exists — the branches listed in it will" \
         "be skipped this run until a human resolves them. Contents:"
    cat "$NEEDS_REVIEW_FILE"
fi

ORIGINAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

restore_branch() {
    local current
    current="$(git rev-parse --abbrev-ref HEAD)"
    if [ "$current" != "$ORIGINAL_BRANCH" ]; then
        if docs_dirty; then
            echo "WARNING: leaving $current dirty (docs/CHANGELOG.md)," \
                 "refusing to switch back to $ORIGINAL_BRANCH to avoid" \
                 "carrying changes across branches"
            return
        fi
        echo "restoring original branch $ORIGINAL_BRANCH"
        git checkout "$ORIGINAL_BRANCH"
    fi
}
trap restore_branch EXIT

if docs_dirty; then
    echo "docs/ or CHANGELOG.md already dirty on $ORIGINAL_BRANCH before" \
         "run — skipping entirely to avoid mixing manual and automated" \
         "changes"
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

mapfile -t BRANCHES < <(git for-each-ref --format='%(refname:short)' refs/heads/)
declare -A SEEN_TREE

for BRANCH in "${BRANCHES[@]}"; do
    echo "--- branch: $BRANCH ---"

    # Skip branches whose docs/ + CHANGELOG.md are byte-identical to one
    # already processed this run, without even checking them out — avoids
    # claude making the same edit three times and manufacturing merge
    # conflicts between otherwise-unrelated branches.
    if branch_needs_review "$BRANCH"; then
        echo "skipping $BRANCH: still has an unresolved needs-review entry"
        continue
    fi

    TREE_KEY="$(git rev-parse "$BRANCH:docs" 2>/dev/null)-$(git rev-parse "$BRANCH:CHANGELOG.md" 2>/dev/null)"
    if [ -n "${SEEN_TREE[$TREE_KEY]:-}" ]; then
        echo "docs/ + CHANGELOG.md identical to already-processed branch" \
             "${SEEN_TREE[$TREE_KEY]}, skipping"
        continue
    fi

    if docs_dirty; then
        # Shouldn't happen: every iteration below leaves the branch it
        # touched either committed, stashed-clean, or untouched. If this
        # still trips, something violated that invariant — stop everything
        # rather than guess, same as the top-of-script guard would.
        echo "UNEXPECTED: docs/CHANGELOG.md dirty on current branch before" \
             "checking out $BRANCH, aborting entire run for manual review"
        break
    fi

    if ! git checkout "$BRANCH"; then
        echo "cannot check out $BRANCH (in use elsewhere?), skipping"
        continue
    fi

    if docs_dirty; then
        echo "$BRANCH already has uncommitted docs/CHANGELOG.md changes" \
             "of its own, skipping (not ours to touch)"
        continue
    fi

    BEFORE_STATUS="$(git status --porcelain)"

    CLAUDE_OUTPUT="$("$CLAUDE_BIN" -p "$(cat "$PROMPT_FILE")" \
        --permission-mode acceptEdits \
        --disallowedTools "Bash,Agent,WebFetch,WebSearch" \
        --model claude-sonnet-5 2>&1)"
    CLAUDE_STATUS=$?
    printf '%s\n' "$CLAUDE_OUTPUT"
    echo "claude exit status: $CLAUDE_STATUS"

    CHANGED="$(git status --porcelain -- docs CHANGELOG.md)"
    if [ -z "$CHANGED" ]; then
        echo "no docs/CHANGELOG.md changes on $BRANCH" \
             "$([ "$CLAUDE_STATUS" -ne 0 ] && echo "(claude also exited non-zero: $CLAUDE_STATUS)")"
        SEEN_TREE[$TREE_KEY]="$BRANCH"
        continue
    fi

    # Only newly-changed paths count here — comparing against BEFORE_STATUS
    # (not assuming a clean tree) means pre-existing, unrelated dirty files
    # elsewhere in the tree can never be mistaken for claude having touched
    # something out of scope.
    AFTER_STATUS="$(git status --porcelain)"
    NEW_STATUS="$(comm -13 <(printf '%s\n' "$BEFORE_STATUS" | sort) <(printf '%s\n' "$AFTER_STATUS" | sort))"
    OUTSIDE_SCOPE=""
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        path="${line:3}"
        if ! printf '%s\n' "$path" | grep -Eq "$ALLOWED_PATH_RE"; then
            OUTSIDE_SCOPE="$OUTSIDE_SCOPE$line
"
        fi
    done <<<"$NEW_STATUS"

    # Claude writes its own commit message (see repo-maintenance-prompt.md),
    # delimited so it survives being embedded in a wider response.
    CLAUDE_SUBJECT_BODY="$(printf '%s\n' "$CLAUDE_OUTPUT" \
        | sed -n '/^===COMMIT-MESSAGE-START===$/,/^===COMMIT-MESSAGE-END===$/p' \
        | sed '1d;$d')"

    ABORT_REASON=""
    if [ "$CLAUDE_STATUS" -ne 0 ]; then
        ABORT_REASON="claude exited non-zero ($CLAUDE_STATUS) but left docs/CHANGELOG.md changes behind — signature of a run that died mid-flight"
    elif [ -n "$OUTSIDE_SCOPE" ]; then
        ABORT_REASON="claude touched files outside docs/ or CHANGELOG.md:
$OUTSIDE_SCOPE"
    elif [ -z "$CLAUDE_SUBJECT_BODY" ]; then
        ABORT_REASON="no parseable commit-message block in claude's output — the prompt only omits that block when nothing changed, so files changed + no block is itself the signature of a truncated/killed run"
    fi

    if [ -n "$ABORT_REASON" ]; then
        STASH_MSG="repo-maintenance: unparseable/failed run on $BRANCH at $(date -Is)"
        # scoped to docs/CHANGELOG.md: a whole-tree stash would also sweep
        # up unrelated untracked clutter elsewhere in the working tree
        git stash push -u -m "$STASH_MSG" -- docs CHANGELOG.md
        {
            echo "branch: $BRANCH"
            echo "reason: $ABORT_REASON"
            echo "stash: \"$STASH_MSG\" (see: git stash list / git stash show -p)"
            echo "log: $LOG_FILE"
            echo
        } >>"$NEEDS_REVIEW_FILE"
        echo "ABORTED and stashed on $BRANCH, moving on to other branches:" \
             "$ABORT_REASON"
        continue
    fi

    FULL_MSG="$CLAUDE_SUBJECT_BODY

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"

    git add -- docs CHANGELOG.md
    git commit -m "$FULL_MSG"
    echo "committed on $BRANCH: $(git rev-parse --short HEAD)"
    SEEN_TREE[$TREE_KEY]="$BRANCH"
done

echo "=== run finished: $(date -Is) ==="
