"""Erkennt installierte Assistenten und startet sie in einer eigenen Prozessgruppe."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .onboarding import RunDir
from .tools import DEFAULT_TIMEOUT, check_cancel

ASSISTANTS = ('claude', 'codex')
RPC_ENV = 'PICAM_SENSOR_AGENT_RPC'


def _probe(*command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=4, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None


def detect() -> list[dict]:
    result = []
    for name in ASSISTANTS:
        executable = shutil.which(name)
        version = logged_in = None
        if executable:
            found = _probe(executable, '--version')
            if found is not None and found.returncode == 0:
                version = found.stdout.strip() or None
            if name == 'codex':
                login = _probe(executable, 'login', 'status')
                if login is not None and login.returncode in (0, 1):
                    logged_in = login.returncode == 0
            else:
                login = _probe(executable, 'auth', 'status')
                if login is not None:
                    try:
                        value = json.loads(login.stdout).get('loggedIn')
                        logged_in = value if isinstance(value, bool) else None
                    except (ValueError, AttributeError):
                        pass  # Aeltere Claude-Versionen kennen auth status nicht.
        result.append({'name': name, 'installed': executable is not None, 'version': version,
                       'logged_in': logged_in})
    return result


def _agent_environment(run: RunDir, name: str) -> dict[str, str]:
    root = run.path.resolve()
    writable = root / '.agent'
    writable.mkdir(mode=0o700, exist_ok=True)
    for sub in ('home', 'tmp', 'rpc'):
        (writable / sub).mkdir(mode=0o700, exist_ok=True)
    env = os.environ.copy()
    config_name, legacy, credential = (
        ('CODEX_HOME', '.codex', 'auth.json') if name == 'codex'
        else ('CLAUDE_CONFIG_DIR', '.claude', '.credentials.json')
    )
    original = Path(env.get(config_name) or Path.home() / legacy) / credential
    # Nur lesender Zugriff auf die bestehende Anmeldung; kein Token im Prompt
    # und keine Kopie in Laufartefakten. Erneutes Login erfolgt ausserhalb.
    link = writable / 'home' / credential
    if original.is_file() and not link.exists() and not link.is_symlink():
        link.symlink_to(original.resolve())
    bin_dir = root / 'bin'
    bin_dir.mkdir(exist_ok=True)
    wrapper = bin_dir / 'picam'
    wrapper.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} -m dispread.admin.cli "$@"\n')
    wrapper.chmod(0o755)
    source = str(Path(__file__).resolve().parents[2])
    env.update({config_name: str(writable / 'home'), 'TMPDIR': str(writable / 'tmp'),
                'XDG_CACHE_HOME': str(writable / 'home'), 'XDG_STATE_HOME': str(writable / 'home'),
                'PATH': os.pathsep.join([str(bin_dir), str(Path(sys.executable).parent), env.get('PATH', '')]),
                'PYTHONPATH': source, 'PYTHONDONTWRITEBYTECODE': '1', RPC_ENV: str(writable / 'rpc'),
                'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'})
    return env


def start(run: RunDir, which: str) -> subprocess.Popen:
    if which not in ASSISTANTS:
        raise ValueError(f'Unbekannter KI-Assistent {which!r}')
    executable = shutil.which(which)
    if executable is None:
        raise ValueError(f'KI-Assistent {which} fehlt')
    root = run.path.resolve()
    env = _agent_environment(run, which)
    if which == 'claude':
        command = [executable, '-p', '--output-format', 'stream-json', '--verbose', '--permission-mode', 'dontAsk',
                   '--setting-sources', '', '--strict-mcp-config', '--allowedTools', 'Bash(picam sensor:*)',
                   f'Bash({sys.executable} -m dispread.admin.cli sensor:*)', 'Read']
    else:
        command = [executable, 'exec', '--json', '-m', 'gpt-6.2-sol', '-s', 'workspace-write',
                   '-C', str(root), '--skip-git-repo-check', '--ephemeral', '--ignore-user-config',
                   '-c', 'approval_policy="never"', '-', ]
    prompt = Path(__file__).with_name('agent_prompt.md').read_text(encoding='utf-8')
    prompt += '\n\nLaufmappe: ' + str(root) + '\n\nrequest.json (Bedienereingaben):\n'
    prompt += json.dumps(run.request(), ensure_ascii=False)
    prompt_path = root / 'agent-prompt.txt'
    prompt_path.write_text(prompt, encoding='utf-8')
    with prompt_path.open('rb') as stream, (root / 'agent.log').open('wb') as log:
        commands = [sys.executable, '-m', 'dispread.sensors._agent_sandbox', str(root / '.agent'), *command]
        return subprocess.Popen(commands, stdin=stream, stdout=log, stderr=subprocess.STDOUT,
                                cwd=root, env=env, start_new_session=True)


def _messages(line: str) -> list[str]:
    try:
        obj = json.loads(line)
    except ValueError:
        return [line.strip()] if line.strip() else []
    if not isinstance(obj, dict):
        return []
    message = obj.get('message')
    item = obj.get('item')
    if obj.get('type') == 'assistant' and isinstance(message, dict):
        content = message.get('content')
        if isinstance(content, list):
            return [block['text'] for block in content if isinstance(block, dict)
                    and block.get('type') == 'text' and isinstance(block.get('text'), str)]
    if (obj.get('type') == 'item.completed' and isinstance(item, dict)
            and item.get('type') == 'agent_message' and isinstance(item.get('text'), str)):
        return [item['text']]
    if obj.get('type') in {'error', 'turn.failed'} or obj.get('is_error'):
        return [str(obj.get('error') or obj.get('message') or obj.get('result') or obj.get('type'))]
    return []


def _stop(proc: subprocess.Popen) -> None:
    # Auch nach Ende des Leitprozesses koennen Kindprozesse noch laufen.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=2)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=2)


def run_agent(run: RunDir, name: str, serve_tools, *, timeout: float = DEFAULT_TIMEOUT) -> int:
    proc = start(run, name)
    deadline = time.monotonic() + timeout
    try:
        with (run.path / 'agent.log').open('rb') as log:
            while True:
                check_cancel(run)
                if time.monotonic() >= deadline:
                    raise TimeoutError('Zeitlimit des KI-Assistenten erreicht')
                returncode = proc.poll()
                while line := log.readline():
                    if returncode is None and not line.endswith(b'\n'):
                        log.seek(-len(line), os.SEEK_CUR)
                        break
                    for message in _messages(line.decode('utf-8', 'replace')):
                        run.log(message, 'agent')
                if returncode is not None:
                    return returncode
                serve_tools(deadline)
                time.sleep(0.1)
    finally:
        _stop(proc)


def request_tool(argv: list[str], directory: Path) -> int:
    """Bittet den Elternprozess um einen auf diesen Lauf beschraenkten CLI-Aufruf."""
    key = uuid.uuid4().hex
    pending = directory / f'{key}.request'
    temporary = directory / f'{key}.tmp'
    temporary.write_text(json.dumps(argv), encoding='utf-8')
    temporary.replace(pending)
    response = directory / f'{key}.response'
    deadline = time.monotonic() + DEFAULT_TIMEOUT
    while not response.is_file():
        if time.monotonic() >= deadline:
            print('Zeitlimit fuer Sensor-Werkzeug erreicht', file=sys.stderr)
            return 2
        time.sleep(0.1)
    result = json.loads(response.read_text(encoding='utf-8'))
    if 'error' in result:
        print(result['error'], file=sys.stderr)
    else:
        print(json.dumps(result['value'], ensure_ascii=False, allow_nan=False))
    return result['code']
