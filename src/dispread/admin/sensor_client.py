"""Dünne Schnittstelle der Konsole zum Sensor-Backend (Registry, Werkzeug-CLI, Onboarding-Läufe).

Alle Funktionen der Oberfläche gehen hierüber, damit Tests sie ersetzen können und die Konsole nie selbst
Sensorpakete schreibt. Aufrufe der Werkzeug-CLI laufen über ``sys.executable -m dispread.admin.cli sensor …``;
fehlt ein Unterbefehl noch, kommt eine ehrliche Meldung statt eines Absturzes.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dispread.sensors import DEFAULT_SENSOR_ID
from dispread.sensors.onboarding import RunDir

ASSISTANTS = ('claude', 'codex')


def _cli_command(instance, args: list[str]) -> list[str]:
    command = [sys.executable, '-m', 'dispread.admin.cli']
    if instance is not None and getattr(instance, 'config', None):
        command += ['--config', instance.config]
    return [*command, 'sensor', *args]


def run_cli(args: list[str], instance=None, timeout: float = 30.0) -> tuple[int, str, str]:
    """(Exit, stdout, stderr); Start- und Zeitfehler als Exit 127 / 124 mit Meldung."""
    try:
        done = subprocess.run(_cli_command(instance, args), capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return 124, '', 'Zeitüberschreitung'
    except OSError as error:
        return 127, '', str(error)
    return done.returncode, done.stdout, done.stderr


def _failure(code: int, out: str, err: str, what: str) -> str:
    text = (err.strip() or out.strip()).splitlines()
    tail = text[-1] if text else f'Exit {code}'
    if 'invalid choice' in err or 'unrecognized' in err:
        return f'{what}: Unterbefehl im Backend noch nicht vorhanden ({tail})'
    return f'{what}: {tail}'


def _json(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None


# ----------------------------------------------------------------- Orte
def local_root_path(instance) -> Path:
    """Ordner der lokalen Sensorpakete der Instanz (Backend-Funktion, sonst neben den Daten)."""
    try:
        from dispread.sensors import local_root

        return Path(local_root(instance))
    except ImportError:
        pass
    data = getattr(instance, 'data', None)
    return (Path(data).parent if data else Path('var')) / 'sensors'


def onboarding_root(instance) -> Path:
    return local_root_path(instance).parent / 'sensor-onboarding'


# ----------------------------------------------------------------- Registry
def active_sensor_id(instance) -> str:
    return getattr(instance, 'sensor', None) or DEFAULT_SENSOR_ID


def list_sensors(instance=None) -> list[dict]:
    """Alle Sensoren (mitgeliefert und lokal) als Zeilen; Fehler einzelner Pakete werden nicht verschluckt."""
    from dispread import sensors

    root = local_root_path(instance)
    extra = [root] if root.is_dir() else []
    found, errors = sensors.registry_with_errors(extra)
    active = active_sensor_id(instance)
    rows = []
    for definition in found.values():
        local = definition.directory.parent == root
        rows.append({'id': definition.id, 'display_name': definition.display_name,
                     'manufacturer': definition.manufacturer, 'aliases': list(definition.aliases),
                     'status': definition.status, 'unit': definition.unit, 'active': definition.id == active,
                     'local': local, 'directory': str(definition.directory)})
    rows.sort(key=lambda row: (not row['active'], row['display_name'].lower()))
    if errors:
        rows.append({'id': '', 'error': '; '.join(errors)})
    return rows


# ----------------------------------------------------------------- Werkzeuge
def normalize_assistants(raw) -> dict[str, dict]:
    if isinstance(raw, dict):
        raw = raw.get('agents') or raw.get('assistants') or []
    found = {item.get('name'): item for item in raw or [] if isinstance(item, dict)}
    result = {}
    for name in ASSISTANTS:
        item = found.get(name, {})
        result[name] = {'name': name, 'installed': bool(item.get('installed')),
                        'logged_in': item.get('logged_in'), 'version': item.get('version')}
    return result


def detect_assistants(instance=None) -> dict[str, dict]:
    """KI-Assistenten (claude, codex): installiert / angemeldet. Unbekanntes gilt als nicht installiert."""
    raw = []
    try:
        from dispread.sensors import agent

        raw = agent.detect()
    except ImportError:
        code, out, _err = run_cli(['agents'], instance, timeout=20.0)
        raw = (_json(out) if code == 0 else None) or []
    except Exception:  # noqa: BLE001 - Erkennung darf die Konsole nie stören
        raw = []
    return normalize_assistants(raw)


def list_ports(instance=None) -> list[dict]:
    """Serielle Anschlüsse als [{'port', 'label'}]; ohne Backend oder ohne Anschlüsse leer."""
    code, out, _err = run_cli(['ports'], instance, timeout=20.0)
    data = _json(out) if code == 0 else None
    if isinstance(data, dict):
        data = data.get('ports') or []
    ports = []
    for item in data or []:
        if isinstance(item, str):
            ports.append({'port': item, 'label': item})
        elif isinstance(item, dict):
            path = item.get('port') or item.get('path') or item.get('device')
            if path:
                note = item.get('description') or item.get('label') or ''
                ports.append({'port': str(path), 'label': f'{path} ({note})' if note else str(path)})
    return ports


# ----------------------------------------------------------------- Onboarding
def create_run(request: dict, instance=None) -> RunDir:
    root = onboarding_root(instance)
    root.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    for attempt in range(5):
        try:
            return RunDir.create(root, request, now=now + timedelta(seconds=attempt))
        except FileExistsError:
            continue
    raise OSError(f'Laufmappe in {root} nicht anlegbar')


def start_onboard(run: RunDir, assistant: str, instance=None) -> subprocess.Popen:
    """Orchestrierung als eigener Prozess (eigene Prozessgruppe); Ausgabe nach run/onboard.log."""
    command = _cli_command(instance, ['onboard', '--run', str(run.path), '--assistant', assistant])
    with open(run.path / 'onboard.log', 'ab') as log:
        return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)


def stop_process(proc, *, kill: bool = False) -> None:
    sig = signal.SIGKILL if kill else signal.SIGTERM
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, AttributeError, TypeError, OSError):
        try:
            proc.kill() if kill else proc.terminate()
        except (ProcessLookupError, OSError, AttributeError):
            pass


def activate(sensor_id: str, instance=None) -> tuple[bool, str]:
    """Sensor als aktiv setzen (``picam sensor activate``). Rückgabe (ok, Meldung)."""
    code, out, err = run_cli(['activate', '--id', sensor_id, '--accept-provisional'], instance, timeout=60.0)
    if code != 0:
        return False, _failure(code, out, err, 'Aktivieren')
    data = _json(out)
    message = data.get('message') if isinstance(data, dict) else None
    return True, message or f'Sensor {sensor_id} ist aktiv.'
