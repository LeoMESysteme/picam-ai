"""Capability checks, independent of distro names and product imports."""
from __future__ import annotations

import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MODULES = ('numpy', 'cv2', 'serial', 'aiohttp', 'PAM', 'cryptography', 'setuptools', 'wheel')


@dataclass(frozen=True)
class SystemInfo:
    system: str
    machine: str
    os_id: str
    os_version: str
    python: str
    version: tuple
    missing_modules: tuple
    apt: bool
    systemd: bool
    user_bus: bool


def os_release(path=Path('/etc/os-release')):
    values = {}
    try:
        for line in path.read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep and key in {'ID', 'VERSION_ID', 'ID_LIKE'}:
                parts = shlex.split(value)
                if len(parts) == 1:
                    values[key] = parts[0]
    except (OSError, ValueError):
        pass
    return values


def probe_system(python, runner=subprocess.run):
    if platform.system() != 'Linux':
        return SystemInfo(platform.system(), platform.machine(), 'unbekannt', 'unbekannt',
                          str(python), tuple(sys.version_info[:3]), (), False, False, False)
    executable = shutil.which(python) if not Path(python).is_absolute() else python
    if not executable:
        raise ValueError('Python nicht gefunden; --python /pfad/zu/python3 angeben')
    code = f'''import importlib,json,sys
missing=[]
for name in {MODULES!r}:
    try: importlib.import_module(name)
    except Exception as e: missing.append(name + ": " + type(e).__name__)
print(json.dumps({{"version":list(sys.version_info[:3]),"missing":missing,"python":sys.executable}}))
'''
    try:
        result = runner([str(executable), '-I', '-c', code], check=True, capture_output=True, text=True, timeout=45)
        info = json.loads(result.stdout)
        if (not isinstance(info, dict) or not isinstance(info.get('version'), list)
                or len(info['version']) != 3 or not all(type(v) is int and v >= 0 for v in info['version'])
                or not isinstance(info.get('missing'), list) or not all(isinstance(v, str) for v in info['missing'])
                or not isinstance(info.get('python'), str) or not Path(info['python']).is_absolute()):
            raise ValueError('Unvollstaendige Python-Pruefantwort')
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise ValueError('Python-/Systembibliothekspruefung fehlgeschlagen; --python kontrollieren') from error
    release = os_release()
    runtime = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    return SystemInfo(platform.system(), platform.machine(), release.get('ID', 'unbekannt'),
                      release.get('VERSION_ID', 'unbekannt'), info['python'], tuple(info['version']),
                      tuple(info['missing']), bool(shutil.which('apt-get')),
                      bool(shutil.which('systemctl') and Path('/run/systemd/system').is_dir()),
                      (runtime / 'bus').exists())
