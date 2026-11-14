"""Statische Installationsvertraege; fuehrt niemals apt oder den Installer aus."""

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PACKAGES = {
    'PAM': 'python3-pam',
    'aiohttp': 'python3-aiohttp',
    'cryptography': 'python3-cryptography',
    'cv2': 'python3-opencv',
    'numpy': 'python3-numpy',
    'serial': 'python3-serial',
    'textual': 'python3-textual',
    'zeroconf': 'python3-zeroconf',
}


def test_apt_manifest_covers_source_imports_and_install_tools():
    manifest = ROOT / 'packaging/apt-packages.txt'
    assert manifest.is_file(), 'Zentrale apt-Paketliste fehlt'
    packages = []
    for line in manifest.read_text().splitlines():
        package, _, comment = line.partition('#')
        package = package.strip()
        if not package:
            continue
        assert re.fullmatch(r'[a-z0-9][a-z0-9+.-]+', package), line
        assert comment.strip(), f'Paket ohne Begruendung: {package}'
        packages.append(package)
    assert len(packages) == len(set(packages))
    imports = set()
    for path in (ROOT / 'src').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split('.')[0])
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == 'import_module' and node.args
                  and isinstance(node.args[0], ast.Constant)):
                imports.add(node.args[0].value.split('.')[0])
    third_party = imports - sys.stdlib_module_names - {'dispread'}
    assert third_party <= MODULE_PACKAGES.keys(), f'Nicht zugeordnet: {third_party - MODULE_PACKAGES.keys()}'
    assert {MODULE_PACKAGES[name] for name in third_party} <= set(packages)
    assert {'v4l-utils', 'openssl', 'python3-venv', 'python3-setuptools', 'python3-wheel'} <= set(packages)


def test_installer_shell_syntax():
    subprocess.run(['bash', '-n', ROOT / 'scripts/install-workbench.sh'], check=True)
