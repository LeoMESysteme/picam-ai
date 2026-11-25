---
name: docs-cleanup
description: Clean up, tidy, smooth, or update project documentation under docs/ and CHANGELOG.md — fixes stale or false claims (only when verifiable against the actual code), trims duplicated or bloated sections, repairs cross-references, and marks resolved open questions without ever deleting them. Use when asked to clean up the docs, tidy documentation, remove doc clutter, condense long docs, or update docs/open-questions.md.
---

Runs the same rule-set that powers the unattended nightly cron job
(`scripts/repo-maintenance.sh`, verified end-to-end below) directly in
the current session: read `scripts/repo-maintenance-prompt.md` for the
full task and hard boundaries, then apply it yourself against `docs/`
and `CHANGELOG.md` using `Read`/`Grep`/`Glob`/`Edit`. Unlike the cron
job, do **not** auto-commit — show the user the diff and the proposed
commit message, and let them decide whether to commit.

All paths below are relative to the repo root.

## Run (agent path — interactive, this is what you actually use)

1. Read `scripts/repo-maintenance-prompt.md` in full. It is the single
   source of truth for scope and hard boundaries: never touch
   `Konzept.md`, `AGENTS.md`, `CLAUDE.md`, `src/`, `tests/`, `examples/`,
   `scripts/`, `systemd/`, `udev/`, `.claude/`, `pyproject.toml`; never
   delete a `docs/open-questions.md` entry (mark it "geklärt" + date +
   evidence instead); `docs/status.md` and `docs/PLAN_*.md` are
   formatting-only; `docs/anleitung/` is typo/dead-link-only.
2. Follow it directly: read `docs/status.md` and
   `docs/open-questions.md` first, then the rest of `docs/*.md`. Only
   change what you can point at concrete evidence for — a `Grep`/`Read`
   hit in `src/`/`tests/`/`examples/`, or an obviously duplicated/dead
   section. When unsure, leave it and note it instead of guessing.
3. Do **not** run `git commit` yourself. When done, give the user:
   - a short summary of what changed and why
   - the commit message in the exact
     `===COMMIT-MESSAGE-START===` / `===COMMIT-MESSAGE-END===` format
     from the prompt file (see its "Commit-Message" section), so they
     can use it verbatim if they choose to commit

## Run (headless path — what the nightly cron job actually runs)

```bash
scripts/repo-maintenance.sh
```

Same prompt, same boundaries, but non-interactive (`claude -p
--permission-mode acceptEdits --disallowedTools
"Bash,Agent,WebFetch,WebSearch"`) and it *does* auto-commit — only if
the tree was clean before the run **and** only `docs/`/`CHANGELOG.md`
ended up changed; otherwise it aborts and leaves everything uncommitted
for manual review. Installed via `@reboot` cron (the Pi is off
overnight; fires ~20s after boot). Documented here for reference — the
interactive skill above doesn't invoke this script.

## Verification (this session, this container)

The script's actual logic (network check, `claude -p` invocation,
commit-message parsing) was run end-to-end against a disposable
synthetic git repo — not this project — with only the final `git
commit` line swapped for an `echo` so no commits were made anywhere
during testing. Fixture: a repo with an `docs/open-questions.md` entry
answerable by reading a two-line `src/fake_module.py`, a
`docs/lab_journal.md` with a verbatim-duplicated entry, and a
`docs/status.md` with a broken relative link.

Result — it fixed the dead link, answered the open question by reading
the source file and appending "**Geklärt am 2026-09-10:** ..." *without
deleting the question*, deduplicated the journal entry while preserving
every number and date, left `CHANGELOG.md` untouched (nothing there was
verifiably stale), and produced this commit message on its own:

```
Toten Link in status.md fixen, OQ-01 klaeren, Laborjournal-Duplikat kuerzen (automatisierte Doku-Pflege)

- docs/status.md: Link auf open-questions.md korrigiert
- docs/open-questions.md: OQ-01 anhand von src/fake_module.py als geklaert markiert
- docs/lab_journal.md: identischen 2026-01-02-Eintrag durch Kurzverweis ersetzt
```

## Gotchas

- **The network-readiness check must not use `curl -f`.**
  `https://api.anthropic.com` 404s on its root path, and `-f` treats
  any 4xx/5xx as failure — so the original check reported "no network"
  even when the network was completely fine:
  ```bash
  curl -fsS --max-time 5 -o /dev/null -w "%{http_code}\n" https://api.anthropic.com
  # -> 404, curl exit 22 (false "network down")

  curl -sS --max-time 5 -o /dev/null https://api.anthropic.com >/dev/null 2>&1; echo $?
  # -> 0 (correctly "network up", regardless of HTTP status)
  ```
  Fixed in `scripts/repo-maintenance.sh` to drop `-f` and just check
  curl's own exit code.
- **Never point the log/state dir inside the repo being cleaned.**
  `git status --porcelain` reports untracked directories too, so a log
  dir living inside the repo trips the script's own "tree was dirty
  before the run" safety check on the very next run. Production uses
  `~/.local/state/picam-ai-maintenance/`, outside the repo.
- **Don't use `--restricted` if you want plugins/skills available** —
  it explicitly ignores project settings files, and that's where
  `.claude/settings.json`'s `enabledPlugins` lives. Use
  `--disallowedTools "Bash,Agent,WebFetch,WebSearch"` instead: same
  "no shell, no subagents, no external fetches" safety property,
  without losing plugin loading.
- **The commit message is written by Claude per run, not templated.**
  It ends its response with a delimited block that the wrapper parses
  with `sed`; falls back to a generic, clearly-labeled message only if
  parsing ever fails, so a parsing hiccup never loses a day's edits.

## Troubleshooting

- **Script exits 0 immediately, log says "working tree already dirty
  before run"**: by design — it refuses to mix pre-existing
  uncommitted work with automated changes. Commit or stash first.
- **Log says "no network after 5 minutes, aborting"**: check the real
  cause with `curl -sS -o /dev/null -w '%{http_code}\n'
  https://api.anthropic.com` — a 4xx/5xx there means the host is
  reachable and fine; only a curl-level connection error is real.
