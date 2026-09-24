#!/usr/bin/env python3
"""Gate an unattended Codex documentation edit before it reaches master."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BOT_NAME = "picam docs bot"
BOT_EMAIL = "picam-docs-bot@users.noreply.local"
EXPECTED_REMOTE = "https://ds1515.me-systeme.de/l.hentschke/picam-ai.git"


def git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, env=env, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise ValueError(f"git {' '.join(args[:2])} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def week_key() -> str:
    today = datetime.now(ZoneInfo("Europe/Berlin"))
    year, week, _ = today.isocalendar()
    return f"{year}-W{week:02d}"


def needs_audit(state: dict, head: str, week: str) -> bool:
    return state.get("last_audited") != head or state.get("last_week") != week


def allowed_path(path: str) -> bool:
    if path in {"zensical.toml", "README.md", "docs/status.md", "docs/open-questions.md", "docs/ROADMAP.md"}:
        return True
    if path.startswith("docs/anleitung/") or path.startswith("docs/uebersicht/"):
        return path.endswith(".md")
    return False


def _oq_entries(document: str) -> dict[str, str]:
    # The generated table may change; only the actual OQ entry bodies are locked.
    entries: dict[str, str] = {}
    matches = list(re.finditer(r'(?m)^(?:<span id="oq-\d{2,}"></span>\n\n)?## OQ-(\d{2,})\b.*$', document))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(document)
        entries[match.group(1)] = document[match.start() : end].rstrip()
    return entries


def ensure_existing_oq_unchanged(original: str, updated: str) -> None:
    def intro(document: str) -> str:
        without_index = re.sub(r"<!-- OQ-INDEX:START.*?<!-- OQ-INDEX:END -->", "", document, flags=re.S)
        first = re.search(r'(?m)^(?:<span id="oq-\d{2,}"></span>\n\n)?## OQ-\d{2,}\b', without_index)
        return without_index[:first.start()].rstrip() if first else without_index.rstrip()

    if intro(original) != intro(updated):
        raise ValueError("OQ intro changed outside the generated index")
    before, after = _oq_entries(original), _oq_entries(updated)
    for number, body in before.items():
        if after.get(number) != body:
            raise ValueError(f"existing OQ-{number} was changed or removed")


def codex_environment(source: dict[str, str]) -> dict[str, str]:
    sensitive = re.compile(r"TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY", re.I)
    return {key: value for key, value in source.items() if not sensitive.search(key)}


def validate_publish_remote(remote: str) -> None:
    if remote != EXPECTED_REMOTE:
        raise ValueError("origin is not the expected Forgejo repository")


def ensure_master_unchanged(repo: Path, base: str) -> None:
    remote_url = git(repo, "remote", "get-url", "origin")
    token = os.environ.get("FORGEJO_TOKEN", "")
    if remote_url.startswith("https://") and token:
        with tempfile.TemporaryDirectory() as directory:
            askpass = Path(directory) / "askpass.sh"
            askpass.write_text(
                '#!/bin/sh\ncase "$1" in *Username*) printf "oauth2\\n" ;; '
                '*Password*) printf "%s\\n" "$FORGEJO_TOKEN" ;; esac\n', encoding="utf-8"
            )
            askpass.chmod(0o700)
            env = dict(os.environ, GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT="0")
            git(repo, "fetch", "--quiet", "origin", "master", env=env)
    else:
        git(repo, "fetch", "--quiet", "origin", "master")
    remote = git(repo, "rev-parse", "refs/remotes/origin/master")
    if remote != base:
        raise ValueError("origin/master changed after checkout; refusing to publish")


def metadata_path(repo: Path) -> Path:
    path = Path(git(repo, "rev-parse", "--git-path", "docs-maintenance.json"))
    return (path if path.is_absolute() else repo / path).resolve()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        json.dump(data, temp, ensure_ascii=False, indent=2)
        temp.write("\n")
        temp_path = Path(temp.name)
    temp_path.chmod(0o600)
    temp_path.replace(path)


def github_output(**values: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as file:
            for key, value in values.items():
                file.write(f"{key}={value}\n")


def changed_paths(repo: Path) -> list[str]:
    tracked = git(repo, "diff", "--name-only", "HEAD").splitlines()
    untracked = git(repo, "ls-files", "--others", "--exclude-standard").splitlines()
    return sorted(set(tracked + untracked))


def validate_paths(repo: Path, paths: list[str]) -> None:
    for path in paths:
        if not allowed_path(path):
            raise ValueError(f"file outside documentation edit scope: {path}")
        target = repo / path
        if target.is_symlink() or not target.parent.resolve().is_relative_to(repo.resolve()):
            raise ValueError(f"unsafe documentation path: {path}")


class _SiteLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.previews: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a" and "data-preview" in values and values.get("href"):
            self.previews.append(values["href"])


def validate_preview_targets(site: Path) -> None:
    parsed: dict[Path, _SiteLinks] = {}

    def page(path: Path) -> _SiteLinks:
        if path not in parsed:
            result = _SiteLinks()
            result.feed(path.read_text(encoding="utf-8"))
            parsed[path] = result
        return parsed[path]

    for source in site.rglob("*.html"):
        for href in page(source).previews:
            resolved = urlsplit(urljoin(f"https://site.local/{source.relative_to(site).as_posix()}", href))
            target = site / unquote(resolved.path).lstrip("/")
            if resolved.netloc != "site.local" or not target.is_file():
                raise ValueError(f"preview target missing: {source.relative_to(site)} -> {href}")
            if resolved.fragment and unquote(resolved.fragment) not in page(target).ids:
                raise ValueError(f"preview anchor missing: {source.relative_to(site)} -> {href}")


def token_usage(log_file: Path) -> tuple[int, int, int]:
    usage = (0, 0, 0)
    with log_file.open(encoding="utf-8") as log:
        for line in log:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "turn.completed":
                details = event.get("usage", {})
                usage = tuple(int(details.get(key, 0)) for key in ("input_tokens", "cached_input_tokens", "output_tokens"))
    return usage


def guide_batch(pages: list[str], cursor: int, week: str) -> tuple[list[str], int]:
    if not pages:
        raise ValueError("guide pages are missing")
    if cursor < len(pages):
        next_cursor = min(cursor + 3, len(pages))
        return pages[cursor:next_cursor], next_cursor
    week_number = int(week.split("W", 1)[1])
    return [pages[week_number % len(pages)]], cursor


def probe(repo: Path, state_file: Path) -> None:
    if git(repo, "status", "--porcelain"):
        raise ValueError("checkout must be clean before documentation maintenance")
    base = git(repo, "rev-parse", "HEAD")
    ensure_master_unchanged(repo, base)
    state = load_json(state_file)
    week = week_key()
    pages = [path.relative_to(repo).as_posix() for path in sorted((repo / "docs" / "anleitung").glob("*.md"))]
    cursor = min(int(state.get("guide_cursor", 0)), len(pages))
    initial = cursor < len(pages)
    weekly = state.get("last_week") != week
    guide_pages, next_cursor = guide_batch(pages, cursor, week)
    run = needs_audit(state, base, week) or initial
    previous = state.get("last_audited")
    previous_is_ancestor = bool(previous) and subprocess.run(
        ["git", "merge-base", "--is-ancestor", previous, base], cwd=repo, check=False,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    if previous_is_ancestor:
        files = git(repo, "diff", "--name-only", f"{previous}..{base}").splitlines()
    else:
        files = []
    info = {
        "base": base,
        "week": week,
        "weekly": weekly,
        "initial": initial,
        "guide_pages": guide_pages if initial or weekly else [],
        "next_guide_cursor": next_cursor,
        "changed_files": files[:60],
        "truncated_files": len(files) > 60,
        "run": run,
    }
    save_json(metadata_path(repo), info)
    github_output(run=str(run).lower())
    print("Codex-Audit erforderlich" if run else "Keine Änderungen seit dem letzten Audit")


def _run_checked(command: list[str], repo: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=repo, env=env, check=True)


def audit(repo: Path, state_file: Path, codex_bin: str, publish_requested: bool) -> None:
    info_file = metadata_path(repo)
    info = load_json(info_file)
    if not info.get("run") or not info.get("base"):
        raise ValueError("missing probe result or audit was not requested")
    base = info["base"]
    if git(repo, "rev-parse", "HEAD") != base or git(repo, "status", "--porcelain"):
        raise ValueError("checkout changed since probe")
    ensure_master_unchanged(repo, base)
    prompt = (repo / "scripts" / "docs-maintenance-prompt.md").read_text(encoding="utf-8")
    prompt += "\n\n## Auftrag für diesen Lauf\n"
    prompt += json.dumps(
        {key: info[key] for key in ("base", "weekly", "initial", "guide_pages", "changed_files", "truncated_files")},
        ensure_ascii=False,
        indent=2,
    )
    command = [
        codex_bin, "exec", "--ignore-user-config", "--ephemeral", "--json", "--sandbox", "workspace-write",
        "-m", "gpt-6-luna", "-c", 'approval_policy="never"',
        "-c", "agents.max_concurrent_threads_per_session=2",
        "-c", 'agents.default_subagent_model="gpt-6-luna"',
        "-c", 'agents.default_subagent_reasoning_effort="low"', "-",
    ]
    state_file.parent.mkdir(parents=True, exist_ok=True)
    log_file = state_file.parent / "last-codex-run.jsonl"
    with log_file.open("w", encoding="utf-8") as output:
        try:
            result = subprocess.run(
                command, cwd=repo, env=codex_environment(dict(os.environ)), input=prompt,
                stdout=output, stderr=subprocess.DEVNULL, text=True, timeout=20 * 60, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Codex exceeded the 20 minute limit") from exc
    log_file.chmod(0o600)
    if result.returncode:
        raise ValueError(f"Codex failed with exit code {result.returncode}; private log: {log_file}")
    input_tokens, cached_tokens, output_tokens = token_usage(log_file)
    print(f"Codex-Nutzung: {input_tokens} Eingabe, {cached_tokens} davon Cache, {output_tokens} Ausgabe")
    if git(repo, "rev-parse", "HEAD") != base:
        raise ValueError("Codex created a commit; only the gate may commit")
    paths = changed_paths(repo)
    validate_paths(repo, paths)
    if "docs/open-questions.md" in paths:
        original = git(repo, "show", f"{base}:docs/open-questions.md")
        _run_checked([str(repo / ".venv" / "bin" / "python"), "scripts/oq-index.py"], repo)
        ensure_existing_oq_unchanged(original, (repo / "docs/open-questions.md").read_text(encoding="utf-8"))
    _run_checked([str(repo / ".venv" / "bin" / "python"), "scripts/oq-index.py", "--check"], repo)
    paths = changed_paths(repo)
    validate_paths(repo, paths)
    if not paths:
        _run_checked(["./scripts/docs-site.sh", "build", "-s"], repo)
        validate_preview_targets(repo / "site")
        if publish_requested:
            save_json(state_file, {"last_audited": base, "last_week": info["week"], "guide_cursor": info["next_guide_cursor"]})
        info.update(ready=False, changed=False)
        save_json(info_file, info)
        github_output(changed="false")
        print("Keine belegte Doku-Änderung erforderlich")
        return
    if "docs/status.md" not in paths:
        raise ValueError("docs/status.md must be rewritten before an automated commit")
    _run_checked(["git", "diff", "--check"], repo)
    _run_checked(["./scripts/docs-site.sh", "build", "-s"], repo)
    validate_preview_targets(repo / "site")
    _run_checked(["npx", "playwright", "test", "-c", "playwright.docs.config.ts"], repo)
    paths = changed_paths(repo)
    validate_paths(repo, paths)
    git(repo, "add", "--", *paths)
    git(repo, "-c", "core.hooksPath=/dev/null", "-c", f"user.name={BOT_NAME}", "-c", f"user.email={BOT_EMAIL}", "commit", "-m", "docs: aktualisiere Zensical-Erklärungen und Vorschauen")
    candidate = git(repo, "rev-parse", "HEAD")
    info.update(ready=True, changed=True, candidate=candidate)
    save_json(info_file, info)
    github_output(changed="true")
    print(f"Doku-Commit geprüft: {candidate[:12]}")
    print(git(repo, "show", "--stat", "--oneline", "HEAD"))


def publish(repo: Path, state_file: Path) -> None:
    info = load_json(metadata_path(repo))
    if not info.get("ready") or not info.get("candidate"):
        raise ValueError("no validated documentation commit to publish")
    if git(repo, "rev-parse", "HEAD") != info["candidate"]:
        raise ValueError("validated commit changed before publish")
    if git(repo, "rev-parse", "HEAD^") != info["base"]:
        raise ValueError("validated commit does not build directly on master")
    if git(repo, "status", "--porcelain"):
        raise ValueError("checkout is dirty before publish")
    remote = git(repo, "remote", "get-url", "origin")
    validate_publish_remote(remote)
    ensure_master_unchanged(repo, info["base"])
    env = dict(os.environ)
    if not env.get("DOCS_BOT_TOKEN") or not env.get("DOCS_BOT_USERNAME"):
        raise ValueError("bot credentials are missing")
    with tempfile.TemporaryDirectory() as directory:
        askpass = Path(directory) / "askpass.sh"
        askpass.write_text(
            '#!/bin/sh\ncase "$1" in *Username*) printf "%s\\n" "$DOCS_BOT_USERNAME" ;; '
            '*Password*) printf "%s\\n" "$DOCS_BOT_TOKEN" ;; esac\n', encoding="utf-8"
        )
        askpass.chmod(0o700)
        env.update(GIT_ASKPASS=str(askpass), GIT_TERMINAL_PROMPT="0")
        git(repo, "-c", "core.hooksPath=/dev/null", "push", "origin", "HEAD:refs/heads/master", env=env)
    save_json(state_file, {"last_audited": info["candidate"], "last_week": info["week"], "guide_cursor": info["next_guide_cursor"]})
    print(f"master aktualisiert: {info['candidate'][:12]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("probe", "audit", "publish"))
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--state-file", type=Path, default=Path(os.environ.get("CODEX_HOME", ".")) / "maintenance-state.json")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--publish-requested", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "probe":
            probe(args.repo, args.state_file)
        elif args.command == "audit":
            audit(args.repo, args.state_file, args.codex_bin, args.publish_requested)
        else:
            publish(args.repo, args.state_file)
    except (ValueError, subprocess.CalledProcessError, OSError) as exc:
        print(f"Doku-Pflege abgebrochen: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
