"""Welche Werkbank-Instanz verwaltet picam?

Reihenfolge: ausdrückliche Konfiguration (``--config``/``PICAM_CONFIG``),
installierter Systemdienst (``/etc/picam/config.toml``), Benutzerinstallation
(``~/.config/picam/config.toml``), sonst Entwicklungsbetrieb mit dem
``systemd-run``-Benutzerdienst aus ``scripts/werkbank-dienst.sh``.

Im Entwicklungsbetrieb liest picam die Startargumente aus der laufenden Unit
und merkt sie sich, damit ``picam start`` den Dienst später genauso startet.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dispread.gsv2as_serial import REFERENCE_PORT
from dispread.hardware_ports import GSV_UART_PORT
from dispread.sensors import DEFAULT_SENSOR_ID

SYSTEM_CONFIG = Path('/etc/picam/config.toml')
INSTALLED_UNIT = 'picam-werkbank.service'
DEV_UNIT = 'dispread-werkbank-bruecke'
SERVE_MODULE = 'dispread.workbench.cli'


def _home() -> Path:
    return Path(os.environ.get('HOME') or Path.home())


def user_config() -> Path:
    base = os.environ.get('XDG_CONFIG_HOME')
    return (Path(base) if base else _home() / '.config') / 'picam' / 'config.toml'


def dev_memory() -> Path:
    base = os.environ.get('XDG_CONFIG_HOME')
    return (Path(base) if base else _home() / '.config') / 'picam' / 'entwicklungsdienst.json'


def code_root() -> Path:
    """Release-Verzeichnis (venv liegt darin) oder Checkout."""
    release = Path(sys.prefix).resolve().parent
    if (release / 'release.json').is_file():
        return release
    return repo_root() or release


def repo_root() -> Path | None:
    """Checkout, aus dem dieses Paket geladen wurde (Entwicklungsbetrieb)."""
    root = Path(__file__).resolve().parents[3]
    return root if (root / 'pyproject.toml').is_file() and (root / 'src' / 'dispread').is_dir() else None


@dataclass
class Instance:
    kind: str                    # system | user | portable | dev | none
    unit: str | None             # systemd-Unit oder None (portabel)
    scope: str                   # system | user
    config: str | None = None    # config.toml, sonst None
    host: str | None = None
    port: int | None = None
    socket: str | None = None
    data: str | None = None
    live_data: str | None = None
    bridge_directory: str | None = None
    pam_user: str | None = None
    templates: str | None = None
    calibration: str | None = None
    bridge_name: str | None = None
    bridge_discovery: bool | None = None
    root: str | None = None      # Code: Release-Verzeichnis oder Checkout
    argv: list[str] = field(default_factory=list)   # Startbefehl (dev)
    workdir: str | None = None
    problem: str | None = None   # Konfiguration unlesbar o. ä.
    output_port: str = GSV_UART_PORT
    reference_port: str = REFERENCE_PORT
    sensor: str = DEFAULT_SENSOR_ID
    sensor_assistant: bool = False   # [features] sensor_assistant (experimentell, Vorgabe aus)

    @property
    def label(self) -> str:
        return {'system': 'Systemdienst', 'user': 'Benutzerdienst', 'portable': 'portabel',
                'dev': 'Entwicklungsbetrieb', 'none': 'nicht eingerichtet'}[self.kind]

    @property
    def url(self) -> str | None:
        if not self.host or not self.port:
            return None
        host = f'[{self.host}]' if ':' in self.host else self.host
        return f'https://{host}:{self.port}/live'

    def to_json(self) -> dict:
        data = asdict(self)
        data['label'] = self.label
        data['url'] = self.url
        return data


def _run(command, timeout=5.0):
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return done.returncode, done.stdout, done.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        return 127, '', str(error)


def _from_config(path: Path, kind: str) -> Instance:
    unit = None if kind == 'portable' else INSTALLED_UNIT
    scope = 'system' if kind == 'system' else 'user'
    instance = Instance(kind=kind, unit=unit, scope=scope, config=str(path))
    try:
        from dispread.workbench.config import load_config

        workbench, live, _ = load_config(path)
    except (OSError, ValueError) as error:
        instance.problem = f'Konfiguration {path} nicht lesbar: {error}'
        return instance
    for name in ('host', 'port', 'socket', 'data', 'live_data', 'bridge_directory', 'pam_user',
                 'bridge_name', 'bridge_discovery', 'output_port', 'reference_port'):
        if name in workbench:
            setattr(instance, name, workbench[name])
    instance.sensor = live.get('sensor', DEFAULT_SENSOR_ID)
    instance.sensor_assistant = _features_of(path)
    instance.templates = str(live['templates']) if 'templates' in live else None
    instance.calibration = str(live['calibration']) if 'calibration' in live else None
    root = code_root()
    current = root.parent.parent / 'current'
    if root.parent.name == 'releases' and current.is_symlink():
        root = current.resolve()  # nach einem Update zählt die aktive Version
    instance.root = str(root)
    return instance


def _features_of(path: Path) -> bool:
    try:
        from dispread.workbench.config import load_features

        return load_features(path)['sensor_assistant']
    except (OSError, ValueError):
        return False


def parse_exec_start(text: str) -> list[str]:
    """``argv[]=...`` aus ``systemctl show -p ExecStart`` (systemd-Format)."""
    marker = 'argv[]='
    start = text.find(marker)
    if start < 0:
        return []
    end = text.find(' ; ', start)
    return shlex.split(text[start + len(marker):end if end > 0 else None])


def _option(argv: list[str], name: str) -> str | None:
    for index, arg in enumerate(argv):
        if arg == name and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith(name + '='):
            return arg.split('=', 1)[1]
    return None


def _dev_from_argv(argv: list[str], workdir: str | None) -> Instance:
    base = Path(workdir) if workdir else (repo_root() or Path.cwd())

    def absolute(value):
        if value is None:
            return None
        path = Path(value)
        return str(path if path.is_absolute() else base / path)

    from dispread.live import DEFAULT_CALIBRATION, DEFAULT_TEMPLATES

    port = _option(argv, '--port')
    instance = Instance(kind='dev', unit=DEV_UNIT, scope='user', argv=argv, workdir=workdir,
                        host=_option(argv, '--host'), port=int(port) if port and port.isdigit() else None,
                        socket=_option(argv, '--socket'), data=absolute(_option(argv, '--data') or 'var/workbench'),
                        live_data=absolute(_option(argv, '--live-data') or 'var/live'),
                        bridge_directory=absolute(_option(argv, '--bridge-directory')),
                        templates=str(DEFAULT_TEMPLATES),
                        calibration=absolute(str(DEFAULT_CALIBRATION)),
                        root=str(base))
    instance.pam_user = os.environ.get('USER')
    from dispread.workbench.config import dev_sensor_config, load_config

    sensor_config = dev_sensor_config(instance.data)
    if sensor_config.is_file():
        try:
            _, live, _ = load_config(sensor_config)
            instance.sensor = live.get('sensor', DEFAULT_SENSOR_ID)
            instance.sensor_assistant = _features_of(sensor_config)
        except (OSError, ValueError) as error:
            instance.problem = f'Sensorkonfiguration {sensor_config}: {error}'
    return instance


def _remember(argv: list[str], workdir: str | None) -> None:
    path = dev_memory()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({'unit': DEV_UNIT, 'argv': argv, 'workdir': workdir}, indent=2)
        if not path.exists() or path.read_text() != payload:
            tmp = path.with_suffix('.tmp')
            tmp.write_text(payload)
            tmp.replace(path)
    except OSError:
        pass


def _recall() -> tuple[list[str], str | None] | None:
    try:
        data = json.loads(dev_memory().read_text())
        argv = data.get('argv')
        if isinstance(argv, list) and all(isinstance(a, str) for a in argv) and SERVE_MODULE in argv:
            return argv, data.get('workdir')
    except (OSError, ValueError, AttributeError):
        pass
    return None


def discover(config: str | None = None, run=_run) -> Instance:
    explicit = config or os.environ.get('PICAM_CONFIG')
    if explicit:
        path = Path(explicit).expanduser()
        kind = 'system' if path.resolve() == SYSTEM_CONFIG else (
            'user' if path.resolve() == user_config().resolve() else 'portable')
        return _from_config(path, kind)
    if SYSTEM_CONFIG.is_file():
        return _from_config(SYSTEM_CONFIG, 'system')
    if user_config().is_file():
        return _from_config(user_config(), 'user')
    code, out, _ = run(['systemctl', '--user', 'show', DEV_UNIT, '-p', 'ExecStart',
                        '-p', 'WorkingDirectory', '-p', 'LoadState', '--no-pager'])
    props = dict(line.split('=', 1) for line in out.splitlines() if '=' in line) if code == 0 else {}
    argv = parse_exec_start(props.get('ExecStart', ''))
    if argv and SERVE_MODULE in argv:
        workdir = props.get('WorkingDirectory') or None
        _remember(argv, workdir)
        return _dev_from_argv(argv, workdir)
    remembered = _recall()
    if remembered:
        return _dev_from_argv(*remembered)
    root = repo_root()
    if root is not None:
        instance = _dev_from_argv([], str(root))
        instance.problem = ('Noch kein Dienst bekannt: einmal mit scripts/werkbank-dienst.sh start '
                            '--host ADRESSE --port PORT starten, danach übernimmt picam die Angaben.')
        return instance
    return Instance(kind='none', unit=None, scope='user',
                    problem='Keine Installation gefunden (/etc/picam/config.toml fehlt).')
