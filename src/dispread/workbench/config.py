"""Strict, opt-in TOML configuration for installed workbench instances.

The namespace is updated only after the complete file has been validated.
Legacy invocations keep their existing defaults and CWD-relative paths.
"""

from __future__ import annotations

import ipaddress
import re
import sys
import tomllib
from pathlib import Path

from dispread.gsv2as_serial import REFERENCE_PORT
from dispread.hardware_ports import GSV_UART_PORT, validate_port_pair

_PATHS = {
    'data': 'directory', 'live_data': 'directory', 'socket': 'socket',
    'cert': 'file', 'key': 'file', 'bridge_directory': 'directory',
}
_FIELDS = frozenset(_PATHS) | {
    'host', 'port', 'pam_user', 'bridge_endpoint', 'bridge_name',
    'bridge_discovery', 'camera', 'simulate', 'output_port', 'reference_port',
}
# Include non-configurable serve options so argparse abbreviations stay unambiguous.
_SERVE_OPTIONS = _FIELDS | {
    'config', 'help', 'width', 'height', 'fps', 'min_area', 'max_area',
    'min_aspect', 'max_aspect', 'min_rectangularity',
}


def _text(value, name):
    if (not isinstance(value, str) or not value.strip()
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError(f'{name}: nichtleere Zeichenfolge ohne Steuerzeichen erforderlich')
    return value


def _host(value):
    _text(value, 'host')
    if any(char.isspace() for char in value):
        raise ValueError('host: Leerzeichen sind nicht erlaubt')
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        pass
    labels = value.removesuffix('.').split('.')
    if (len(value) > 253 or all(part.isdigit() for part in labels)
            or any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', part)
                   for part in labels)):
        raise ValueError('host: gueltige IP-Adresse oder Hostname erforderlich')
    return value


def _path(value, name, base, kind):
    _text(value, name)
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    for parent in path.parents:
        if parent.exists() and not parent.is_dir():
            raise ValueError(f'{name}: Elternpfad ist kein Verzeichnis: {parent}')
    if path.exists():
        valid = path.is_dir() if kind == 'directory' else path.is_file()
        if kind == 'socket':
            valid = path.is_socket() or path.is_file()
        if not valid:
            raise ValueError(f'{name}: Pfad hat einen ungueltigen Dateityp: {path}')
    # Missing templates/calibration are handled by setup/run readiness checks.
    return path


def validate_serial_setting(value: str, name: str) -> str:
    _text(value, name)
    pattern = (r'(?:uart[0-4]|/dev/ttyAMA[0-9]+)' if name == 'output_port'
               else r'/dev/(?:tty(?:USB|ACM)[0-9]+|serial/by-id/(?!\.{1,2}$)[^/]+)')
    if not re.fullmatch(pattern, value):
        raise ValueError(f'{name}: ungültige serielle Schnittstelle')
    return value


def _workbench(values, base):
    result = {}
    for name, value in values.items():
        if name in _PATHS:
            value = str(_path(value, name, base, _PATHS[name]))
        elif name == 'host':
            value = _host(value)
        elif name in {'port', 'camera'}:
            if type(value) is not int or not (1 <= value <= 65535 if name == 'port' else value >= 0):
                raise ValueError(f'{name}: ungueltiger Ganzzahlwert')
        elif name in {'simulate', 'bridge_discovery'}:
            if type(value) is not bool:
                raise ValueError(f'{name}: TOML true/false erforderlich')
        elif name in {'output_port', 'reference_port'}:
            value = validate_serial_setting(value, name)
        elif name == 'bridge_endpoint':
            from dispread.bridge.protocol import MAX_ENDPOINTS, _endpoint

            if not isinstance(value, list) or len(value) > MAX_ENDPOINTS:
                raise ValueError('bridge_endpoint: Liste von HTTPS-/WSS-Endpunkten erforderlich')
            for endpoint in value:
                _text(endpoint, name)
                try:
                    _endpoint(endpoint)
                except ValueError as error:
                    raise ValueError(f'bridge_endpoint: {error}') from error
            if len(set(value)) != len(value):
                raise ValueError('bridge_endpoint: doppelte Endpunkte')
        else:
            value = _text(value, name)
        result[name] = value
    if 'output_port' in result or 'reference_port' in result:
        validate_port_pair(result.get('output_port', GSV_UART_PORT),
                           result.get('reference_port', REFERENCE_PORT))
    return result


def _explicit_options(argv):
    explicit = set()
    for arg in argv:
        if not arg.startswith('--'):
            continue
        option = arg[2:].split('=', 1)[0].replace('-', '_')
        matches = [name for name in _SERVE_OPTIONS if name.startswith(option)]
        if option in _SERVE_OPTIONS:
            explicit.add(option)
        elif len(matches) == 1:
            explicit.add(matches[0])
    return explicit


def load_config(path):
    """Validated ``(workbench, live)`` values of a serve TOML file (absolute paths)."""
    source = Path(path).resolve()
    with source.open('rb') as stream:
        config = tomllib.load(stream)
    return parse_config(config, source.parent)


def parse_config(config, base):
    if unknown := config.keys() - {'workbench', 'live'}:
        raise ValueError(f'unbekannte Abschnitte: {", ".join(sorted(unknown))}')
    for section, allowed in (('workbench', _FIELDS), ('live', {'templates', 'calibration'})):
        values = config.get(section, {})
        if not isinstance(values, dict):
            raise ValueError(f'{section}: TOML-Tabelle erforderlich')
        if unknown := values.keys() - allowed:
            raise ValueError(f'{section}: unbekannte Schluessel: {", ".join(sorted(unknown))}')
    workbench = _workbench(config.get('workbench', {}), base)
    live = {name: _path(value, f'live.{name}', base, 'file')
            for name, value in config.get('live', {}).items()}
    return workbench, live, 'live' in config


def apply_config(args, argv=None):
    """Apply a serve TOML file, preserving options explicitly passed on the CLI."""
    if getattr(args, 'command', None) != 'serve' or getattr(args, 'config', None) is None:
        return args
    source = Path(args.config)
    try:
        source = source.resolve()
        values, live, has_live = load_config(source)
        if has_live:
            from dispread.live.session import LiveConfig

            values['live_config'] = LiveConfig(**live)
    except (OSError, ValueError, RuntimeError) as error:
        raise ValueError(f'Konfiguration {source}: {error}') from error
    explicit = _explicit_options(sys.argv[1:] if argv is None else argv)
    for name, value in values.items():
        if name not in explicit:
            setattr(args, name, value)
    return args

