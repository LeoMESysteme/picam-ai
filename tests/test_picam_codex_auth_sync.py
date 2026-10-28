"""Checks for the root-run sync between ~/.codex/auth.json and the docs runner."""

import importlib.machinery
import importlib.util
import json
import os
import pwd
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "picam-codex-auth-sync"
loader = importlib.machinery.SourceFileLoader("picam_codex_auth_sync", str(SCRIPT))
spec = importlib.util.spec_from_loader("picam_codex_auth_sync", loader)
auth_sync = importlib.util.module_from_spec(spec)
loader.exec_module(auth_sync)

ME = pwd.getpwuid(os.getuid())


def _auth(refresh: str, account: str = "acct-1", token: str = "a") -> str:
    return json.dumps({
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": None,
        "tokens": {"access_token": token, "refresh_token": "r-" + token, "id_token": "i", "account_id": account},
        "last_refresh": refresh,
    })


@pytest.fixture
def paths(tmp_path):
    local = tmp_path / "home" / ".codex" / "auth.json"
    runner = tmp_path / "runner" / ".codex" / "auth.json"
    local.parent.mkdir(parents=True)
    runner.parent.mkdir(parents=True)
    return local, runner


def _sync(local, runner):
    return auth_sync.sync(local, ME, runner, ME)


def _leftovers(*dirs):
    return [p.name for d in dirs for p in d.iterdir() if p.name.startswith(".auth.json.sync-")]


def test_missing_runner_copy_takes_local_login(paths):
    local, runner = paths
    local.write_text(_auth("2026-10-28T09:00:00Z"))
    assert _sync(local, runner) == "to-runner"
    assert runner.read_text() == local.read_text()
    assert runner.stat().st_mode & 0o777 == 0o600
    assert _leftovers(local.parent, runner.parent) == []


def test_newer_local_login_replaces_runner_copy(paths):
    local, runner = paths
    local.write_text(_auth("2026-10-28T09:00:00Z", token="new"))
    runner.write_text(_auth("2026-10-20T09:00:00Z", token="old"))
    assert _sync(local, runner) == "to-runner"
    assert json.loads(runner.read_text())["tokens"]["access_token"] == "new"


def test_newer_runner_refresh_goes_back_to_local(paths):
    local, runner = paths
    local.write_text(_auth("2026-10-20T09:00:00Z", token="old"))
    runner.write_text(_auth("2026-10-28T09:00:00.123456Z", token="new"))
    assert _sync(local, runner) == "to-local"
    assert json.loads(local.read_text())["tokens"]["access_token"] == "new"
    assert _sync(local, runner) == "none"


def test_runner_with_other_account_never_replaces_local(paths):
    local, runner = paths
    local.write_text(_auth("2026-10-20T09:00:00Z", account="acct-1", token="mine"))
    runner.write_text(_auth("2026-10-28T09:00:00Z", account="acct-2", token="foreign"))
    assert _sync(local, runner) == "to-runner"
    assert json.loads(local.read_text())["tokens"]["access_token"] == "mine"
    assert json.loads(runner.read_text())["tokens"]["access_token"] == "mine"


def test_runner_symlink_is_replaced_without_touching_its_target(paths, tmp_path):
    local, runner = paths
    local.write_text(_auth("2026-10-28T09:00:00Z"))
    victim = tmp_path / "victim.txt"
    victim.write_text("unverändert")
    runner.symlink_to(victim)
    assert _sync(local, runner) == "to-runner"
    assert not runner.is_symlink()
    assert victim.read_text() == "unverändert"
    assert runner.read_text() == local.read_text()


def test_broken_runner_file_is_replaced(paths):
    local, runner = paths
    local.write_text(_auth("2026-10-28T09:00:00Z"))
    runner.write_text("{kein json")
    assert _sync(local, runner) == "to-runner"
    assert runner.read_text() == local.read_text()


def test_unusable_local_login_stops_without_writing(paths):
    local, runner = paths
    local.write_text(json.dumps({"tokens": {"access_token": "a"}}))
    runner.write_text(_auth("2026-10-28T09:00:00Z"))
    before = runner.read_text()
    with pytest.raises(auth_sync.Refused):
        _sync(local, runner)
    assert runner.read_text() == before


def test_missing_local_login_changes_nothing(paths):
    local, runner = paths
    runner.write_text(_auth("2026-10-28T09:00:00Z"))
    assert _sync(local, runner) == "none"
    assert not local.exists()


def test_installed_units_are_templated_for_the_developer_home():
    root = SCRIPT.parents[1]
    path_unit = (root / "systemd" / "picam-codex-auth-sync.path").read_text()
    service = (root / "systemd" / "picam-codex-auth-sync.service").read_text()
    assert "PathChanged=AUTH_HOME/.codex/auth.json" in path_unit
    assert "PathChanged=/var/lib/picam-codex-runner/.codex/auth.json" in path_unit
    assert "ReadWritePaths=AUTH_HOME/.codex" in service
    assert 'sed "s#AUTH_HOME#$AUTH_HOME#"' in (root / "scripts" / "picam-codex-auth-sync-install.sh").read_text()
