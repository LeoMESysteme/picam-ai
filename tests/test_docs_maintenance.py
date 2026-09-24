"""Behavioral checks for the unattended Zensical maintenance gate."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "docs-maintenance.py"
spec = importlib.util.spec_from_file_location("docs_maintenance", SCRIPT)
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


def test_unchanged_revision_uses_no_model_until_weekly_review():
    state = {"last_audited": "abc123", "last_week": "2026-W39"}
    assert maintenance.needs_audit(state, "abc123", "2026-W39") is False
    assert maintenance.needs_audit(state, "def456", "2026-W39") is True
    assert maintenance.needs_audit(state, "abc123", "2026-W40") is True


def test_initial_guide_audit_advances_in_small_daily_batches():
    pages = [f"docs/anleitung/{number:02d}.md" for number in range(8)]
    assert maintenance.guide_batch(pages, 0, "2026-W39") == (pages[:3], 3)
    assert maintenance.guide_batch(pages, 3, "2026-W39") == (pages[3:6], 6)
    assert maintenance.guide_batch(pages, 6, "2026-W39") == (pages[6:], 8)
    assert maintenance.guide_batch(pages, 8, "2026-W39") == ([pages[39 % 8]], 8)


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("docs/anleitung/glossar.md", True),
        ("docs/anleitung/neues-thema.md", True),
        ("docs/status.md", True),
        ("docs/open-questions.md", True),
        ("zensical.toml", True),
        ("src/dispread/pipeline.py", False),
        ("docs/VALIDATION.md", False),
        ("docs/lab_journal.md", False),
        ("docs/TIMING.md", False),
        (".github/workflows/docs.yml", False),
    ],
)
def test_only_reviewable_documentation_can_be_published(path, allowed):
    assert maintenance.allowed_path(path) is allowed


def test_existing_oq_answers_cannot_be_rewritten():
    original = '<!-- OQ-INDEX:START -->old index<!-- OQ-INDEX:END -->\n<span id="oq-07"></span>\n\n## OQ-07: Protokoll\nAntwort unbekannt\n'
    new = '<!-- OQ-INDEX:START -->new index<!-- OQ-INDEX:END -->\n<span id="oq-07"></span>\n\n## OQ-07: Protokoll\nAntwort unbekannt\n<span id="oq-99"></span>\n\n## OQ-99: Neu\nOffen\n'
    maintenance.ensure_existing_oq_unchanged(original, new)
    with pytest.raises(ValueError, match="OQ-07"):
        maintenance.ensure_existing_oq_unchanged(original, new.replace("Antwort unbekannt", "Antwort geraten"))
    with pytest.raises(ValueError, match="intro"):
        maintenance.ensure_existing_oq_unchanged("Einleitung\n" + original, "Andere Einleitung\n" + new)


def test_bot_token_is_not_available_to_codex_process():
    env = maintenance.codex_environment({"PATH": "/usr/bin", "DOCS_BOT_TOKEN": "secret", "FORGEJO_TOKEN": "token"})
    assert env["PATH"] == "/usr/bin"
    assert "DOCS_BOT_TOKEN" not in env
    assert "FORGEJO_TOKEN" not in env


def test_publish_token_is_limited_to_expected_forgejo_remote():
    maintenance.validate_publish_remote("https://ds1515.me-systeme.de/l.hentschke/picam-ai.git")
    with pytest.raises(ValueError, match="origin"):
        maintenance.validate_publish_remote("https://elsewhere.invalid/l.hentschke/picam-ai.git")


def test_preview_gate_rejects_missing_target_anchor(tmp_path: Path):
    (tmp_path / "guide.html").write_text(
        '<a data-preview="" href="glossar.html#value-record">ValueRecord</a>', encoding="utf-8"
    )
    (tmp_path / "glossar.html").write_text('<h2 id="other">Other</h2>', encoding="utf-8")
    with pytest.raises(ValueError, match="value-record"):
        maintenance.validate_preview_targets(tmp_path)
    (tmp_path / "glossar.html").write_text('<h2 id="value-record">ValueRecord</h2>', encoding="utf-8")
    maintenance.validate_preview_targets(tmp_path)


def test_documentation_links_in_code_blocks_are_rejected():
    diagram = "```text\n1 [frames](../../api/frames.md)   Bildquelle\n```\n"
    with pytest.raises(ValueError, match="code fence"):
        maintenance.validate_markdown_links(diagram, "docs/anleitung/01-kette-verstehen.md")
    maintenance.validate_markdown_links(
        "[frames](../../api/frames.md)\n```markdown\n[example](example.md)\n```\n",
        "docs/anleitung/01-kette-verstehen.md",
    )


def test_codex_usage_is_summarized_without_logging_agent_text(tmp_path: Path):
    log = tmp_path / "codex.jsonl"
    log.write_text(
        '{"type":"item.completed","item":{"text":"private source text"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":50,"cached_input_tokens":20,"output_tokens":7}}\n',
        encoding="utf-8",
    )
    assert maintenance.token_usage(log) == (50, 20, 7)


def test_codex_audit_rejects_sandbox_failure_even_if_turn_completed(tmp_path: Path):
    log = tmp_path / "codex.jsonl"
    log.write_text(
        '{"type":"item.completed","item":{"type":"command_execution","status":"failed",'
        '"exit_code":1,"aggregated_output":"bwrap: loopback: Failed to create NETLINK_ROUTE socket"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":100}}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inspect"):  # a failed tool is not a completed audit
        maintenance.ensure_codex_inspected_repo(log)
    log.write_text(
        '{"type":"item.completed","item":{"type":"command_execution","status":"completed",'
        '"exit_code":0,"aggregated_output":"docs reviewed"}}\n'
        '{"type":"turn.completed","usage":{"input_tokens":100}}\n',
        encoding="utf-8",
    )
    maintenance.ensure_codex_inspected_repo(log)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def test_master_race_rejects_unrelated_remote_commit(tmp_path: Path):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare", "--initial-branch=master")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=master")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("initial\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "origin", "master")
    base = _git(repo, "rev-parse", "HEAD")

    other = tmp_path / "other"
    _git(tmp_path, "clone", str(remote), str(other))
    _git(other, "config", "user.name", "Other")
    _git(other, "config", "user.email", "other@example.invalid")
    (other / "docs" / "a.md").write_text("human change\n")
    _git(other, "add", ".")
    _git(other, "commit", "-m", "human change")
    _git(other, "push", "origin", "master")

    with pytest.raises(ValueError, match="master"):
        maintenance.ensure_master_unchanged(repo, base)


def test_probe_recovers_when_saved_revision_is_not_in_checkout(tmp_path: Path):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare", "--initial-branch=master")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=master")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "docs" / "anleitung").mkdir(parents=True)
    (repo / "docs" / "anleitung" / "README.md").write_text("guide\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "origin", "master")
    state_file = tmp_path / "state.json"
    state_file.write_text('{"last_audited":"missing-commit","last_week":"2026-W01"}')

    maintenance.probe(repo, state_file)

    info = maintenance.load_json(maintenance.metadata_path(repo))
    assert info["run"] is True
    assert info["diff_base"] is None
    assert "docs/anleitung/README.md" in info["changed_files"]


def test_probe_keeps_all_changed_files_and_diff_boundaries(tmp_path: Path):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare", "--initial-branch=master")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=master")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    guide = repo / "docs" / "anleitung"
    guide.mkdir(parents=True)
    (guide / "README.md").write_text("guide\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    old = _git(repo, "rev-parse", "HEAD")
    _git(repo, "remote", "add", "origin", str(remote))
    for number in range(70):
        (guide / f"page-{number:02d}.md").write_text(f"Page {number}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "many pages")
    new = _git(repo, "rev-parse", "HEAD")
    _git(repo, "push", "origin", "master")
    state = tmp_path / "state.json"
    maintenance.save_json(state, {"last_audited": old, "last_week": "2026-W01"})

    maintenance.probe(repo, state)

    info = maintenance.load_json(maintenance.metadata_path(repo))
    assert info["diff_base"] == old
    assert info["base"] == new
    assert len(info["changed_files"]) == 70
    assert "docs/anleitung/page-69.md" in info["changed_files"]


def test_no_edit_audit_does_not_mark_broken_site_as_current(tmp_path: Path):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare", "--initial-branch=master")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=master")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "docs" / "anleitung").mkdir(parents=True)
    (repo / "docs" / "anleitung" / "README.md").write_text("guide\n")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "docs-maintenance-prompt.md").write_text("Check the guide.\n")
    (repo / "scripts" / "oq-index.py").write_text("pass\n")
    build = repo / "scripts" / "docs-site.sh"
    build.write_text("#!/bin/sh\nexit 2\n")
    build.chmod(0o755)
    (repo / ".venv" / "bin").mkdir(parents=True)
    (repo / ".venv" / "bin" / "python").symlink_to(Path(__import__("sys").executable))
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "origin", "master")
    codex = tmp_path / "fake-codex"
    codex.write_text(
        '#!/bin/sh\n'
        'printf "%s\\n" \'{"type":"item.completed","item":{"type":"command_execution",'
        '"status":"completed","exit_code":0}}\'\n'
        'printf "%s\\n" \'{"type":"turn.completed","usage":{}}\'\n'
    )
    codex.chmod(0o755)
    state = tmp_path / "state.json"
    maintenance.probe(repo, state)

    with pytest.raises(subprocess.CalledProcessError):
        maintenance.audit(repo, state, str(codex), publish_requested=True)
    assert not state.exists()


def test_successful_audit_and_publish_advances_state_only_after_push(tmp_path: Path, monkeypatch):
    remote = tmp_path / "remote.git"
    remote.mkdir()
    _git(remote, "init", "--bare", "--initial-branch=master")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=master")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "docs" / "anleitung").mkdir(parents=True)
    (repo / "docs" / "anleitung" / "README.md").write_text("guide\n")
    (repo / "docs" / "status.md").write_text("before\n")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "docs-maintenance-prompt.md").write_text("Review the docs.\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "origin", "master")
    base = _git(repo, "rev-parse", "HEAD")
    codex = tmp_path / "fake-codex"
    codex.write_text(
        '#!/bin/sh\nprintf "after\\n" > docs/status.md\n'
        'printf "%s\\n" \'{"type":"item.completed","item":{"type":"command_execution",'
        '"status":"completed","exit_code":0}}\'\n'
        'printf "%s\\n" \'{"type":"turn.completed","usage":{"input_tokens":2}}\'\n'
    )
    codex.chmod(0o755)
    monkeypatch.setattr(maintenance, "_run_checked", lambda *args, **kwargs: None)
    monkeypatch.setattr(maintenance, "validate_publish_remote", lambda remote: None)
    monkeypatch.setenv("DOCS_BOT_USERNAME", "bot")
    monkeypatch.setenv("DOCS_BOT_TOKEN", "local-test-token")
    state = tmp_path / "state.json"

    maintenance.probe(repo, state)
    maintenance.audit(repo, state, str(codex), publish_requested=True)

    candidate = _git(repo, "rev-parse", "HEAD")
    assert candidate != base
    assert not state.exists()
    assert _git(remote, "rev-parse", "refs/heads/master") == base

    maintenance.publish(repo, state)

    assert _git(remote, "rev-parse", "refs/heads/master") == candidate
    assert maintenance.load_json(state)["last_audited"] == candidate
