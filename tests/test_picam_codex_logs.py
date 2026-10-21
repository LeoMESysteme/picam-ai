"""Checks for the root-run reader of the private Codex maintenance log."""

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "picam-codex-logs"
loader = importlib.machinery.SourceFileLoader("picam_codex_logs", str(SCRIPT))
spec = importlib.util.spec_from_loader("picam_codex_logs", loader)
logs = importlib.util.module_from_spec(spec)
loader.exec_module(logs)


def _jsonl(*events):
    return "\n".join(json.dumps(event) for event in events) + "\n"


def test_log_summary_shows_answer_usage_failures_and_file_changes():
    text = _jsonl(
        {"type": "thread.started"},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "git diff", "exit_code": 0, "aggregated_output": "ok"}},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "./scripts/docs-site.sh build -s", "exit_code": 1, "aggregated_output": "tour-facts: erkennung-zelle"}},
        {"type": "item.completed", "item": {"type": "file_change", "changes": [{"path": "docs/status.md", "kind": "update"}]}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "Keine Änderung nötig"}},
        {"type": "turn.completed", "usage": {"input_tokens": 1200, "cached_input_tokens": 800, "output_tokens": 90}},
    )
    out = "\n".join(logs.summarize_log(text))
    assert "1200 Eingabe, davon 800 Cache, 90 Ausgabe" in out
    assert "Kommandos: 2, davon 1 mit Exit != 0" in out
    assert "[exit 1] ./scripts/docs-site.sh build -s" in out
    assert "tour-facts: erkennung-zelle" in out
    assert "update docs/status.md" in out
    assert out.endswith("Keine Änderung nötig")


def test_log_summary_survives_aborted_run_and_garbage_lines():
    text = "kein json\n" + _jsonl({"type": "turn.failed", "error": {"message": "stream disconnected"}}, [1, 2])
    out = "\n".join(logs.summarize_log(text))
    assert "kein turn.completed" in out
    assert "stream disconnected" in out
    assert "(keine)" in out


def test_terminal_escapes_from_untrusted_log_are_removed():
    text = _jsonl({"type": "item.completed", "item": {"type": "agent_message", "text": "a\x1b]0;x\x07b\x1b[2Jc\nzeile"}})
    out = "\n".join(logs.summarize_log(text))
    assert "\x1b" not in out and "\x07" not in out
    assert "zeile" in out


def test_state_summary_shows_only_validated_fields():
    text = json.dumps({"last_audited": "a8376d7f", "last_week": "2026-W42", "guide_cursor": 15, "token": "geheim"})
    out = "\n".join(logs.summarize_state(text))
    assert "last_audited: a8376d7f" in out and "guide_cursor: 15" in out
    assert "geheim" not in out
    bad = "\n".join(logs.summarize_state(json.dumps({"last_audited": "$(rm -rf /)"})))
    assert "rm -rf" not in bad and "ungültig" in bad


def test_reader_refuses_symlinks(tmp_path):
    secret = tmp_path / "auth.json"
    secret.write_text('{"tokens": "geheim"}', encoding="utf-8")
    link = tmp_path / "last-codex-run.jsonl"
    os.symlink(secret, link)
    with pytest.raises(OSError):
        logs.read_regular(link)
    assert logs.read_regular(tmp_path / "fehlt.jsonl") is None


def test_arguments_are_rejected(capsys):
    assert logs.main(["picam-codex-logs", "/etc/shadow"]) == 2
    assert "keine Argumente" in capsys.readouterr().err


def test_log_summary_adds_up_repair_rounds():
    text = _jsonl(
        {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 5}},
        {"type": "turn.completed", "usage": {"input_tokens": 150, "cached_input_tokens": 120, "output_tokens": 3}},
    )
    out = "\n".join(logs.summarize_log(text))
    assert "Runden: 2" in out
    assert "250 Eingabe, davon 180 Cache, 8 Ausgabe" in out

