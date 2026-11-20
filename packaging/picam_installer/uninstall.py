"""Deinstallation einer mit diesem Installer angelegten Werkbank.

Vorgabe ist ein schreibfreier Plan. Erst ``--apply`` führt ihn aus:
Dienst stoppen und deaktivieren, Unit entfernen und systemd neu laden,
``picam``-Link entfernen, Code unter ``<prefix>`` (``releases/``,
``current``, ``previous``) löschen. Daten und Konfiguration bleiben
erhalten; nur ``--purge-data`` entfernt auch sie – genau die Pfade, die der
Plan nennt. Gelöscht wird nur, was als picam-Installation erkannt ist:
keine Symlinks im Pfad, Links nur, wenn sie in den Installationsort zeigen.

Die optionale Komponente me-fastfetch (Home des Bedienerkontos, ``home=``)
wird nur entfernt, soweit sie vom Installer stammt (Manifest): unveränderte
Dateien und der markierte Block in ``~/.bashrc`` (mit Sicherung). Das Paket
``fastfetch`` bleibt, außer ``--remove-fastfetch-package``.

``plan_uninstall`` ist rein lesend und liefert ein JSON-fähiges Dict;
``apply_uninstall`` plant aus denselben Angaben neu und führt nur aus, wenn
der Plan unverändert ist. Standardbibliothek, Python >= 3.9.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from . import fastfetch
from .engine import absolute, no_symlinks, quote_unit, target_paths
from .update import check_prefix

UNIT_NAME = 'picam-werkbank.service'
# Vom Installer/Update angelegte Einträge im Installationsort.
CODE_ENTRIES = ('current', 'previous', 'current.neu', 'previous.neu')
COMMAND_TIMEOUT_S = 60


class UninstallError(ValueError):
    pass


def link_target(mode, owner):
    """Gleicher Ort wie beim Verlinken in der geführten Installation."""
    if mode == 'system':
        return Path('/usr/local/bin/picam')
    if mode == 'user':
        return Path(owner.pw_dir) / '.local/bin/picam'
    return None


def default_paths(mode, owner, *, prefix=None, data=None, config=None, runtime=None, unit_dir=None):
    """Installationspfade wie ``engine.target_paths`` plus ``picam``-Link."""
    args = SimpleNamespace(mode=mode, prefix=prefix, data=data, config=config, runtime=runtime,
                           unit_dir=unit_dir, root=None)
    paths = target_paths(args, owner)
    paths['link'] = link_target(mode, owner)
    return paths


def _str(path):
    return str(path) if path is not None else None


def _plain_path(value, label):
    if value is None:
        return None
    path = absolute(value)
    if len(path.parts) < 3:
        raise UninstallError(f'{label} {path} liegt zu nah an der Wurzel; nichts geplant')
    no_symlinks(path)
    for entry in pwd.getpwall():
        home = Path(entry.pw_dir)
        if home.is_absolute() and len(home.parts) > 1 and home.is_relative_to(path):
            raise UninstallError(f'{label} {path} enthält das Benutzerverzeichnis {home}; nichts geplant')
    return path


def _config_data(config: Path):
    """``[workbench] data`` aus einer vom Installer geschriebenen Konfiguration."""
    try:
        text = config.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return None
    match = re.search(r'^data = (".*")\s*$', text, flags=re.MULTILINE)
    if not match:
        return None
    try:
        return Path(json.loads(match.group(1)))
    except ValueError:
        return None


def _config_user(config):
    """``pam_user`` aus der Konfiguration: Bedienerkonto einer Systeminstallation (für me-fastfetch)."""
    try:
        text = Path(config).read_text(encoding='utf-8')
    except (OSError, UnicodeError, TypeError):
        return None
    match = re.search(r'^pam_user = (".*")\s*$', text, flags=re.MULTILINE)
    try:
        return pwd.getpwnam(json.loads(match.group(1))) if match else None
    except (KeyError, ValueError, TypeError):
        return None


def _unit_owned(unit: Path, prefix: Path) -> bool:
    try:
        text = unit.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return False
    starts = [line for line in text.splitlines() if line.startswith('ExecStart=')]
    return (len(starts) == 1 and 'dispread.workbench.cli serve' in starts[0]
            and quote_unit(prefix / 'current')[1:-1] in starts[0])


def _config_dir_removable(directory: Path) -> bool:
    """Konfigurationsordner nur, wenn er außer config.toml (und Sicherungen/Temporärem) nichts enthält."""
    try:
        names = [entry.name for entry in directory.iterdir()]
    except OSError:
        return False
    return 'config.toml' in names and all(
        re.fullmatch(r'\.?config[A-Za-z0-9_.-]*', name) for name in names)


def plan_uninstall(*, mode, prefix, data=None, config=None, unit=None, link=None, runtime=None,
                   purge_data=False, home=None, remove_fastfetch_package=False):
    """Schreibfreien Deinstallationsplan erzeugen.

    ``mode``: ``system`` | ``user`` | ``portable``. ``unit`` ist die Unit-Datei
    (nicht bei portable). Wirft ``ValueError``, wenn ``prefix`` keine
    erkannte picam-Installation ist oder ein Pfad nicht passt.
    """
    if mode not in ('system', 'user', 'portable'):
        raise UninstallError(f'Unbekannte Installationsart: {mode!r}')
    request = {'mode': mode, 'prefix': _str(prefix), 'data': _str(data), 'config': _str(config),
               'unit': _str(unit), 'link': _str(link), 'runtime': _str(runtime), 'purge_data': bool(purge_data),
               'home': _str(home), 'remove_fastfetch_package': bool(remove_fastfetch_package)}
    prefix = _plain_path(prefix, 'Installationsort')
    check_prefix(prefix)
    releases = prefix / 'releases'
    if releases.is_symlink() or not releases.is_dir():
        raise UninstallError(f'{releases} ist kein echtes Verzeichnis')
    data = _plain_path(data, 'Datenordner')
    config = _plain_path(config, 'Konfiguration')
    runtime = _plain_path(runtime, 'Laufzeitordner') if mode == 'portable' else None
    link = Path(link) if link is not None else None
    if link is not None and not link.is_absolute():
        raise UninstallError('Linkpfad muss absolut sein')
    if mode == 'portable' and unit is not None:
        raise UninstallError('Portable Installation hat keinen Dienst')
    for label, path in (('Datenordner', data), ('Konfiguration', config), ('Laufzeitordner', runtime)):
        if path is not None and (path.is_relative_to(releases) or prefix.is_relative_to(path)
                                 or any(path.is_relative_to(prefix / name) for name in CODE_ENTRIES)):
            raise UninstallError(f'{label} {path} überschneidet sich mit dem Code unter {prefix}')

    actions, remove, keep, notes = [], [], [], []

    # 1. Dienst
    unit_info = None
    if mode != 'portable':
        if unit is None:
            raise UninstallError('Unit-Datei angeben (system/user)')
        unit = absolute(unit)
        if unit.name != UNIT_NAME:
            raise UninstallError(f'Unerwartete Unit {unit.name}; erwartet {UNIT_NAME}')
        no_symlinks(unit)
        scope = ['--user'] if mode == 'user' else []
        unit_info = {'name': UNIT_NAME, 'path': str(unit), 'scope': mode, 'present': unit.is_file()}
        if unit.is_file():
            if not _unit_owned(unit, prefix):
                raise UninstallError(f'{unit} startet nicht die Werkbank aus {prefix}; nichts geplant')
            actions += [{'kind': 'command', 'argv': ['systemctl', *scope, 'disable', '--now', UNIT_NAME],
                         'text': 'Dienst stoppen und Autostart abschalten'},
                        {'kind': 'unlink', 'path': str(unit), 'text': 'Unit-Datei entfernen'},
                        {'kind': 'command', 'argv': ['systemctl', *scope, 'daemon-reload'],
                         'text': 'systemd neu laden'}]
            remove.append(str(unit))
        else:
            notes.append(f'Unit {unit} fehlt; Dienst wird nicht angefasst.')
    else:
        notes.append('Portabel: ein laufender Werkbank-Prozess muss vorher von Hand beendet werden.')

    # 2. picam-Link
    if link is not None:
        if link.is_symlink():
            target = Path(os.readlink(link))
            if not target.is_absolute():
                target = link.parent / target
            if Path(os.path.normpath(target)).is_relative_to(prefix):
                actions.append({'kind': 'unlink', 'path': str(link), 'text': 'Befehl picam entfernen'})
                remove.append(str(link))
            else:
                keep.append({'path': str(link), 'reason': f'zeigt nicht in {prefix}'})
        elif link.exists():
            keep.append({'path': str(link), 'reason': 'kein Link dieser Installation'})

    # 3. Code
    for name in CODE_ENTRIES:
        entry = prefix / name
        if entry.is_symlink():
            actions.append({'kind': 'unlink', 'path': str(entry), 'text': f'Verweis {name} entfernen'})
            remove.append(str(entry))
        elif entry.exists():
            raise UninstallError(f'{entry} ist kein Verweis; keine automatische Löschung')
    actions.append({'kind': 'rmtree', 'path': str(releases), 'text': 'Alle Versionen löschen'})
    remove.append(str(releases))

    # 4. Daten und Konfiguration
    purge = []
    if data is not None and data.exists():
        if not data.is_dir() or not (data / 'workbench').is_dir():
            raise UninstallError(f'{data} ist kein picam-Datenordner (workbench/ fehlt)')
        purge.append(('rmtree', data, 'Daten löschen: Läufe, Kalibrierung, Zertifikat, Brückenidentität'))
    if config is not None:
        recorded = _config_data(config) if config.is_file() else None
        if recorded is not None and data is not None and recorded != data / 'workbench':
            message = f'Konfiguration nennt Daten unter {recorded}, geplant ist {data}'
            if purge_data:
                raise UninstallError(message + '; nichts geplant')
            notes.append(message + '.')
        if len(config.parent.parts) >= 3 and config.parent.is_dir() and _config_dir_removable(config.parent):
            purge.append(('rmtree', config.parent, 'Konfigurationsordner löschen'))
        elif config.is_file():
            purge.append(('unlink', config, 'Konfiguration löschen'))
    if runtime is not None and runtime.is_dir() and not runtime.is_symlink():
        purge.append(('rmtree', runtime, 'Laufzeitordner löschen'))
    for kind, path, text in purge:
        if purge_data:
            actions.append({'kind': kind, 'path': str(path), 'text': text})
            remove.append(str(path))
        else:
            keep.append({'path': str(path), 'reason': 'Daten/Konfiguration bleiben (--purge-data löscht sie)'})
    if purge_data and data is not None and data.exists():
        notes.append('Brückenidentität wird gelöscht: Windows-Brücken müssen nach einer Neuinstallation '
                     'neu gekoppelt werden.')

    # 5. Optionale Komponente me-fastfetch im Home des Bedienerkontos
    edit, needs_root = [], mode == 'system'
    if home is not None:
        component = fastfetch.removal(absolute(home), remove_package=remove_fastfetch_package and mode == 'system')
        if component is not None and remove_fastfetch_package and mode != 'system':
            component['notes'].append('Paket fastfetch nur mit sudo entfernen: sudo apt-get remove fastfetch')
        if component is not None:
            actions += component['actions']
            remove += component['remove']
            keep += component['keep']
            notes += component['notes']
            edit += component['edit']
            needs_root = needs_root or component['needs_root']

    # 6. Installationsort selbst nur, wenn danach leer
    actions.append({'kind': 'rmdir_if_empty', 'path': str(prefix), 'text': 'Installationsort entfernen, falls leer'})
    leftovers = sorted(entry.name for entry in prefix.iterdir()
                       if entry.name not in ('releases', *CODE_ENTRIES)
                       and not any(str(prefix / entry.name) == action['path'] for action in actions))
    if leftovers:
        keep.append({'path': str(prefix), 'reason': 'enthält weitere Einträge: ' + ', '.join(leftovers)})

    return {'applied': False, 'mode': mode, 'purge_data': bool(purge_data), 'request': request,
            'prefix': str(prefix), 'unit': unit_info, 'actions': actions, 'remove': remove, 'keep': keep,
            'edit': edit, 'needs_root': needs_root, 'notes': notes}


def apply_uninstall(plan, runner=subprocess.run, progress=None):
    """Plan ausführen. Plant vorher neu und bricht ab, wenn sich etwas geändert hat."""
    step = progress or (lambda _text: None)
    current = plan_uninstall(**plan['request'])
    if current['actions'] != plan['actions']:
        raise UninstallError('Installation hat sich seit dem Plan geändert; neu planen')
    if current['needs_root'] and os.geteuid() != 0:
        raise UninstallError('Systeminstallation entfernen braucht root (sudo)')
    allowed = set(current['remove']) | {current['prefix']} | set(current.get('edit', []))
    done = []
    for action in current['actions']:
        path = Path(action['path']) if 'path' in action else None
        if path is not None and str(path) not in allowed:
            raise UninstallError(f'{path} steht nicht im Plan')
        step(action['text'])
        try:
            if action['kind'] == 'command':
                runner(action['argv'], check=True, capture_output=True, text=True, timeout=COMMAND_TIMEOUT_S)
            elif action['kind'] == 'unlink':
                path.unlink(missing_ok=True)
            elif action['kind'] == 'rmtree':
                if path.is_symlink():
                    raise UninstallError(f'{path} wurde zum Symlink; abgebrochen')
                if path.exists():
                    shutil.rmtree(path)
            elif action['kind'] == 'bashrc_block':
                backup = fastfetch.remove_block(path)
                if backup:
                    action = dict(action, backup=str(backup))
            elif action['kind'] == 'rmdir_if_empty':
                try:
                    path.rmdir()
                except OSError:
                    action = dict(action, skipped='nicht leer')
            else:
                raise UninstallError(f'Unbekannter Schritt {action["kind"]!r}')
        except (OSError, subprocess.SubprocessError) as error:
            raise UninstallError(f'{action["text"]} fehlgeschlagen: {error}. Bereits erledigt: '
                                 + (', '.join(item['text'] for item in done) or 'nichts')) from error
        done.append(action)
    return dict(current, applied=True, done=done)


def parser():
    cli = argparse.ArgumentParser(prog='install.sh --uninstall',
                                  description='picam entfernen; Vorgabe ist ein schreibfreier Plan.')
    cli.add_argument('--uninstall', action='store_true', required=True)
    cli.add_argument('--mode', choices=('system', 'user', 'portable'), default='system')
    cli.add_argument('--user', help='Bedienerkonto der Installation (Vorgabe: aufrufendes Konto)')
    for option in ('prefix', 'data', 'config', 'runtime', 'unit-dir', 'link'):
        cli.add_argument('--' + option, help='Absoluter Pfad, sonst Vorgabe der Installationsart')
    cli.add_argument('--purge-data', action='store_true', help='Auch Daten und Konfiguration löschen')
    cli.add_argument('--remove-fastfetch-package', action='store_true',
                     help='Auch das Paket fastfetch entfernen, wenn der Installer es installiert hat')
    cli.add_argument('--apply', action='store_true', help='Plan tatsächlich ausführen')
    cli.add_argument('--json', action='store_true', help='Maschinenlesbarer Plan/Ergebnis auf stdout')
    return cli


def plan_from_args(args):
    if args.user:
        from .engine import account
        owner = account(args.user)
    else:
        owner = pwd.getpwuid(os.geteuid())
    if args.mode != 'system' and owner.pw_uid != os.geteuid():
        raise UninstallError('Benutzer-/portable Installation unter dem Bedienerkonto entfernen, ohne sudo')
    paths = default_paths(args.mode, owner, prefix=args.prefix, data=args.data, config=args.config,
                          runtime=args.runtime, unit_dir=args.unit_dir)
    link = absolute(args.link) if args.link else paths['link']
    operator = owner if args.user or args.mode != 'system' else (_config_user(paths['config']) or owner)
    return plan_uninstall(mode=args.mode, prefix=paths['prefix'], data=paths['data'], config=paths['config'],
                          unit=paths['unit'], link=link,
                          runtime=paths['runtime'] if args.mode == 'portable' else None,
                          purge_data=args.purge_data, home=operator.pw_dir,
                          remove_fastfetch_package=args.remove_fastfetch_package)


def main(argv):
    args = parser().parse_args(argv)
    try:
        plan = plan_from_args(args)
        result = apply_uninstall(plan, progress=None if args.json else lambda text: print('· ' + text)) \
            if args.apply else plan
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('picam installer: ' + str(error), file=sys.stderr)
        if isinstance(error.__cause__, subprocess.CalledProcessError) and error.__cause__.stderr:
            print(str(error.__cause__.stderr)[-2000:], file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print('Entfernt: ' + result['prefix'] if result['applied'] else 'Deinstallationsplan (nichts geändert):')
    if not result['applied']:
        for action in result['actions']:
            print(f'  · {action["text"]}: ' + (' '.join(action['argv']) if 'argv' in action else action['path']))
    for item in result['keep']:
        print(f'  bleibt: {item["path"]} ({item["reason"]})')
    for note in result['notes']:
        print('  ' + note)
    if not result['applied']:
        print('Ausführen mit --apply' + (' (als root)' if result['needs_root'] else '') + '.')
    return 0
