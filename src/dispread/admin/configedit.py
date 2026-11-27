"""Erlaubte Änderungen an ``config.toml`` einer installierten Werkbank.

Nur wenige Felder sind änderbar, alles andere legt der Installer fest:
Port, Brückenname und Discovery. Die Adresse (``host``) steckt im Zertifikat
und in den Kopplungen und bleibt hier nur lesbar. Jede Änderung wird vor dem
Schreiben mit demselben Prüfer validiert, den ``dispread serve --config``
benutzt, und atomar ersetzt. Wirksam wird sie erst nach einem Dienstneustart.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

EDITABLE = {
    'port': 'Port der Werkbank (1–65535)',
    'bridge_name': 'Name des Pi in der Windows-Brücke',
    'bridge_discovery': 'Pi im Netzwerk ankündigen (true/false)',
}
READ_ONLY = ('host', 'pam_user', 'data', 'live_data', 'socket', 'bridge_directory', 'bridge_endpoint')


@dataclass
class Change:
    key: str
    old: object
    new: object
    text: str


def parse_value(key: str, raw: str):
    if key not in EDITABLE:
        allowed = ', '.join(EDITABLE)
        raise ValueError(f'{key} ist nicht änderbar (änderbar: {allowed})')
    if key == 'port':
        if not raw.strip().isdigit() or not 1 <= int(raw) <= 65535:
            raise ValueError('Port muss eine ganze Zahl von 1 bis 65535 sein')
        return int(raw)
    if key == 'bridge_discovery':
        lowered = raw.strip().lower()
        if lowered in ('true', 'ja', 'an', '1', 'yes', 'on'):
            return True
        if lowered in ('false', 'nein', 'aus', '0', 'no', 'off'):
            return False
        raise ValueError('bridge_discovery: true oder false')
    text = raw.strip()
    if not text or any(ord(c) < 32 for c in text) or len(text) > 64:
        raise ValueError('Name: 1–64 Zeichen ohne Steuerzeichen')
    return text


_HEADER = re.compile(r'^\s*\[([A-Za-z0-9_.-]+)\]\s*(#.*)?$')


def _section_bounds(lines: list[str], name: str) -> tuple[int, int]:
    start = None
    for index, line in enumerate(lines):
        match = _HEADER.match(line)
        if match:
            if start is not None:
                return start, index
            if match.group(1) == name:
                start = index + 1
    if start is None:
        raise ValueError(f'Abschnitt [{name}] fehlt')
    return start, len(lines)


def _replace_key(lines: list[str], key: str, value, *, section: str = 'workbench') -> object:
    start, end = _section_bounds(lines, section)
    pattern = re.compile(rf'^\s*{re.escape(key)}\s*=\s*(.*?)\s*$')
    encoded = json.dumps(value, ensure_ascii=False) if not isinstance(value, bool) else str(value).lower()
    for index in range(start, end):
        match = pattern.match(lines[index])
        if match:
            try:
                old = tomllib.loads(f'v = {match.group(1)}')['v']
            except tomllib.TOMLDecodeError as error:
                raise ValueError(f'{key} ist mehrzeilig oder ungewöhnlich formatiert; '
                                 'bitte von Hand in einer Zeile schreiben') from error
            lines[index] = f'{key} = {encoded}'
            return old
    insert = end
    while insert > start and not lines[insert - 1].strip():
        insert -= 1
    lines.insert(insert, f'{key} = {encoded}')
    return None


def _with_port(endpoint: str, port: int) -> str:
    return re.sub(r'^(https://(?:\[[^\]]+\]|[^/:]+)):\d+', rf'\g<1>:{port}', endpoint)


def propose(path: str | Path, key: str, raw: str) -> tuple[str, list[Change]]:
    """Neuer Dateitext und Änderungsliste, ohne zu schreiben."""
    from dispread.workbench.config import load_config

    source = Path(path)
    text = source.read_text()
    lines = text.splitlines()
    value = parse_value(key, raw)
    changes = []
    old = _replace_key(lines, key, value)
    if old == value:
        return text, []
    changes.append(Change(key, old, value, f'{key}: {old!r} → {value!r}'))
    if key == 'port':
        current, _, _ = load_config(source)
        endpoints = current.get('bridge_endpoint')
        if endpoints:
            updated = [_with_port(e, value) for e in endpoints]
            if updated != endpoints:
                _replace_key(lines, 'bridge_endpoint', updated)
                changes.append(Change('bridge_endpoint', endpoints, updated,
                                      'bridge_endpoint folgt dem Port'))
    new_text = '\n'.join(lines) + '\n'
    from dispread.workbench.config import parse_config

    parse_config(tomllib.loads(new_text), source.resolve().parent)
    return new_text, changes


def propose_sensor(path: Path, sensor_id: str, *, dev_data: str | None = None) -> str:
    """Aendert die Sensorauswahl ueber denselben validierten TOML-Schreibweg."""
    from dispread.workbench.config import parse_config

    if path.exists():
        text = path.read_text(encoding='utf-8')
    elif dev_data is not None:
        text = '[workbench]\ndata = ' + json.dumps(dev_data, ensure_ascii=False) + '\n'
    else:
        raise FileNotFoundError(f'Konfiguration fehlt: {path}')
    lines = text.splitlines()
    if 'live' not in tomllib.loads(text):
        lines.extend(('', '[live]'))
    old = _replace_key(lines, 'sensor', sensor_id, section='live')
    updated = text if old == sensor_id else '\n'.join(lines) + '\n'
    parse_config(tomllib.loads(updated), path.resolve().parent)
    return updated


def apply(path: str | Path, new_text: str, *, create: bool = False) -> None:
    source = Path(path).resolve()
    existing = source.exists()
    if not existing and not create:
        raise FileNotFoundError(source)
    if not os.access(source.parent, os.W_OK) or (existing and not os.access(source, os.W_OK)):
        raise PermissionError(f'{source} ist nicht schreibbar – mit sudo ausführen')
    stat = source.stat() if existing else None
    fd, tmp = tempfile.mkstemp(dir=source.parent, prefix='.config.', suffix='.toml')
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(new_text)
        if stat is not None:
            os.chmod(tmp, stat.st_mode & 0o777)
            if os.geteuid() == 0:
                os.chown(tmp, stat.st_uid, stat.st_gid)
            os.replace(tmp, source)
        else:
            os.link(tmp, source)
            os.unlink(tmp)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
