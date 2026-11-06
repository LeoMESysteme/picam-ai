"""Selbsttest der gebauten App (interner Testbuild). Kein Fenster, keine Verbindung.

Die EXE hat keine Konsole (console=False); das Ergebnis geht deshalb als JSON in
die mit --self-test-out angegebene Datei (und zusätzlich nach stdout, falls
vorhanden). Das ist ein Importtest, keine Windows-Qualifikation.
"""
from __future__ import annotations

import importlib
import json
import platform
import sys
from pathlib import Path

REQUIRED_MODULES = (
    'dispread.gsv_bridge', 'dispread.bridge', 'serial', 'serial.tools.list_ports',
    'cryptography', 'aiohttp', 'zeroconf',
    'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
    'dispread_bridge_app.main', 'dispread_bridge_app.ui.window',
)
FORBIDDEN_ROOTS = ('cv2', 'numpy', 'picamera2', 'libcamera')
FORBIDDEN_PREFIXES = ('dispread.workbench',)


def run_self_test(*, require_frozen: bool = False, create_app: bool = True) -> dict:
    frozen = bool(getattr(sys, 'frozen', False))
    report = {
        'schema': 1, 'kind': 'interner_testbuild_selbsttest', 'frozen': frozen,
        'python': platform.python_version(), 'platform': sys.platform,
        'machine': platform.machine(), 'imports': {}, 'qt_platform': None,
        'qt_platform_plugin_found': None, 'build_info': None,
        'forbidden_loaded': [], 'errors': [], 'ok': False,
        'note': 'Importtest ohne Fenster; keine Windows-Qualifikation.',
    }
    errors = report['errors']
    if require_frozen and not frozen:
        errors.append('nicht eingefroren')
    for name in REQUIRED_MODULES:
        try:
            importlib.import_module(name)
            report['imports'][name] = True
        except Exception as exc:  # noqa: BLE001 - jeder Importfehler ist ein Befund
            report['imports'][name] = False
            errors.append(f'Import {name}: {type(exc).__name__}: {exc}')
    try:
        from dispread_bridge_app import build_info
        report['build_info'] = {k: getattr(build_info, k, None)
                                for k in ('version', 'commit', 'build_time_utc', 'channel')}
    except Exception as exc:  # noqa: BLE001
        report['build_info'] = None
        if frozen:
            errors.append(f'build_info fehlt: {type(exc).__name__}')
    if create_app and report['imports'].get('PySide6.QtWidgets'):
        try:
            from PySide6.QtCore import QLibraryInfo
            from PySide6.QtWidgets import QApplication
            plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
            if sys.platform == 'win32':
                found = (plugins / 'platforms' / 'qwindows.dll').is_file()
                report['qt_platform_plugin_found'] = found
                if not found:
                    errors.append('Qt-Plattform-Plugin qwindows.dll fehlt')
            app = QApplication.instance() or QApplication([sys.argv[0]])
            report['qt_platform'] = app.platformName()
            app.processEvents()           # nie ein Widget anlegen oder anzeigen
        except Exception as exc:  # noqa: BLE001
            errors.append(f'Qt: {type(exc).__name__}: {exc}')
    loaded = sorted(
        n for n in sys.modules
        if n.split('.')[0] in FORBIDDEN_ROOTS or n.startswith(FORBIDDEN_PREFIXES))
    report['forbidden_loaded'] = loaded
    if loaded:
        errors.append('ausgeschlossene Module geladen: ' + ', '.join(loaded[:5]))
    report['ok'] = not errors
    return report


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = None
    if '--self-test-out' in argv:
        i = argv.index('--self-test-out')
        out = argv[i + 1] if i + 1 < len(argv) else None
    report = run_self_test(require_frozen=True)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(text + '\n', encoding='utf-8')
    if sys.stdout is not None:
        try:
            print(text)
        except Exception:  # noqa: BLE001 - ohne Konsole kein Ausgabekanal
            pass
    return 0 if report['ok'] else 1
