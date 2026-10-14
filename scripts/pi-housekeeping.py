#!/usr/bin/env python3
"""Pi-Hauswart: Bericht und ausschließlich freigegebene Cache-Bereinigung.

Keine Hardwarezugriffe, keine externen Programme oder zusätzlichen Pakete.
Symlinks werden beim Vermessen nicht verfolgt und als Löschkandidaten abgelehnt.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import stat
import time
from pathlib import Path

GB = 1_000_000_000
MAX_AGE = 3600


def tree_info(path: Path) -> tuple[int, float, bool]:
    """Allokierte Bytes, jüngste mtime, vollständig; ohne Symlink-/Mount-Abstieg."""
    size, newest, complete = 0, 0.0, True
    try:
        device = path.lstat().st_dev
        pending = [path]
        while pending:
            item = pending.pop()
            info = item.lstat()
            newest = max(newest, info.st_mtime)
            size += info.st_blocks * 512
            if stat.S_ISDIR(info.st_mode):
                if info.st_dev != device or item.is_mount():
                    complete = False
                    continue
                pending.extend(item.iterdir())
    except OSError:
        complete = False
    return size, newest, complete


def children(path: Path, pattern: str = '*') -> list[Path]:
    if not path.is_dir() or has_symlink(path):
        return []
    return sorted(path.glob(pattern))


def has_symlink(path: Path) -> bool:
    return any(part.is_symlink() for part in (path, *path.parents))


def process_uid(process: Path) -> int:
    """Besitzer aus /proc/<pid>; separat für künstliche proc-Bäume testbar."""
    return process.stat().st_uid


def process_snapshot(proc: Path) -> dict:
    """Prozessreferenzen prüfen; bei verweigerten Links bleibt cmdline."""
    references, pytest_running, complete = [], False, True
    try:
        processes = list(proc.iterdir())
    except OSError:
        return {'references': [], 'pytest_running': False, 'complete': False}
    for process in processes:
        if not process.name.isdigit():
            continue
        try:
            process_uid(process)  # Nicht lesbares stat macht die Prüfung unvollständig.
            args = process.joinpath('cmdline').read_bytes().decode(errors='replace').split('\0')
            if not any(args):  # Kernel-Threads haben keine Benutzerraum-Exe.
                continue
            references.extend(args)
            pytest_running |= any(re.search(r'(^|/)pytest(?:$|[-.])', arg) is not None for arg in args)
            try:
                links = [os.readlink(process / name).removesuffix(' (deleted)')
                         for name in ('exe', 'cwd')]
            except PermissionError:
                # Auch eigene, nicht dumpable Prozesse verweigern diese Links.
                # Ihre lesbare cmdline bleibt als Schutzreferenz erhalten.
                continue
            references.extend(links)
            cwd = Path(links[-1])
            for arg in args:
                value = arg.split('=', 1)[-1]
                if '/' in value and not any(char.isspace() for char in value):
                    argument_path = Path(value)
                    references.append(str((cwd / argument_path).resolve()))
        except FileNotFoundError:
            if process.exists():
                complete = False
        except OSError:
            complete = False
    return {'references': references, 'pytest_running': pytest_running, 'complete': complete}


def used(path: Path, snapshot: dict) -> bool:
    expression = re.compile(re.escape(str(path)) + r'''(?=$|[/\s'":])''')
    return any(expression.search(reference) for reference in snapshot['references'])


def contains_paperclip(path: Path) -> bool:
    """Auch npm-Verzeichnisse mit Hash-Namen und verschachteltem Paket schützen."""
    pending = [path]
    while pending:
        item = pending.pop()
        if 'paperclipai' in item.name.lower():
            return True
        if item.is_symlink() and 'paperclipai' in os.readlink(item).lower():
            return True
        if item.name == 'package.json' and not item.is_symlink():
            if 'paperclipai' in item.read_text(errors='replace').lower():
                return True
        if item.is_dir() and not item.is_symlink():
            pending.extend(item.iterdir())
    return False


def protected_paths(home: Path, repo: Path, tmp: Path) -> list[Path]:
    return [repo / 'var', home / 'var-backups', home / '.codex/sessions',
            home / '.cache/ms-playwright',
            *(home / '.codex/.tmp' / name for name in ('marketplaces', 'plugins', 'bundled-marketplaces')),
            *children(tmp, 'claude-*'), *children(tmp, 'picam-ai-n5-*')]


def candidates(home: Path, repo: Path, tmp: Path, user: str) -> list[tuple[Path, str]]:
    result = [(path, 'pytest') for path in children(tmp / f'pytest-of-{user}', 'pytest-*')
              if path.name != 'pytest-current']
    result += [(home / '.npm/_cacache', 'cache')]
    result += [(path, 'npx') for path in children(home / '.npm/_npx')]
    result += [(path, 'version') for path in children(home / '.vscode-server/cli/servers', 'Stable-*')]
    for package in ('standalone', 'app-server-daemon'):
        result += [(path, 'release') for path in children(home / '.codex/packages' / package / 'releases')]
    result += [(path, 'aged') for path in children(home / '.codex/.tmp', 'git-*')]
    result += [(repo / 'playwright-report', 'cache')]
    return result


def recording(repo: Path) -> bool:
    # Auch ein defekter Symlink ist ein Sperrmarker.
    return os.path.lexists(repo / 'var/RECORDING_IN_PROGRESS')


def skip_reason(path: Path, kind: str, home: Path, repo: Path, tmp: Path,
                user: str, snapshot: dict, now: float) -> str | None:
    if recording(repo):
        return 'RECORDING_IN_PROGRESS: Löschen gesperrt'
    if has_symlink(path):
        return 'Symlink im Pfad: keine Bereinigung'
    resolved = path.resolve()
    for protected in protected_paths(home, repo, tmp):
        target = protected.resolve()
        if resolved == target or resolved in target.parents or target in resolved.parents:
            return 'Geschützter Datenpfad'
    if kind in ('pytest', 'npx', 'version', 'release'):
        if not snapshot['complete']:
            return 'Prozessprüfung unvollständig'
        if used(path, snapshot):
            return 'Von laufendem Prozess benutzt'
    if kind == 'pytest':
        if snapshot['pytest_running']:
            return 'pytest läuft'
        current = tmp / f'pytest-of-{user}' / 'pytest-current'
        if current.resolve() == resolved:
            return 'Ziel von pytest-current'
    if kind == 'release':
        # Installationen können current neben releases oder darin ablegen.
        for current in (path.parent / 'current', path.parent.parent / 'current'):
            if current.resolve() == resolved:
                return 'Ziel von current'
        if path.name == 'current':
            return 'current bleibt erhalten'
    if kind == 'npx' and contains_paperclip(path):
        return 'Enthält paperclipai'
    _, newest, complete = tree_info(path)
    if not complete:
        return 'Baum unvollständig lesbar oder enthält Mountpoint'
    if kind in ('pytest', 'aged') and now - newest <= MAX_AGE:
        return 'Jüngste mtime höchstens 1 h alt'
    return None


def cleanup(home: Path, repo: Path, tmp: Path, user: str, proc: Path,
            *, clean: bool, dry_run: bool, now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    snapshot = process_snapshot(proc)
    result = []
    for path, kind in candidates(home, repo, tmp, user):
        if not os.path.lexists(path):
            continue
        entry = {'path': str(path), 'bytes': tree_info(path)[0], 'action': 'eligible', 'reason': None}
        try:
            reason = skip_reason(path, kind, home, repo, tmp, user, snapshot, now)
            if reason:
                entry.update(action='skipped', reason=reason)
            elif dry_run:
                entry['action'] = 'would_delete'
            elif clean:
                # Kurz vor jeder Mutation Sperren, Prozesse und Altersregel erneut prüfen.
                reason = skip_reason(path, kind, home, repo, tmp, user, process_snapshot(proc), time.time())
                if reason:
                    entry.update(action='skipped', reason=reason)
                else:
                    if path.is_dir():
                        if not shutil.rmtree.avoids_symlink_attacks:
                            raise OSError('rmtree ohne Symlink-Schutz: Löschen verweigert')
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    entry['action'] = 'deleted'
        except (OSError, RuntimeError) as error:
            entry.update(action='error', reason=str(error))
        result.append(entry)
    return result


def disk(path: Path) -> dict:
    usage = shutil.disk_usage(path)
    return {'total_bytes': usage.total, 'used_bytes': usage.used, 'free_bytes': usage.free,
            'used_percent': 100 * usage.used / usage.total if usage.total else 0}


def largest(path: Path) -> list[dict]:
    result = []
    for child in children(path):
        size, _, complete = tree_info(child)
        result.append({'path': str(child), 'bytes': size, 'complete': complete})
    return sorted(result, key=lambda item: item['bytes'], reverse=True)[:10]


def protected_report(home: Path, repo: Path, tmp: Path) -> list[dict]:
    result = []
    for path in protected_paths(home, repo, tmp):
        size, _, complete = tree_info(path)
        result.append({'path': str(path), 'bytes': size, 'complete': complete})
    return result


def report(home: Path, repo: Path, tmp: Path, proc: Path) -> dict:
    memory = {}
    for line in (proc / 'meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        memory[key] = int(value.strip().split()[0]) * 1024
    card, temporary = disk(Path('/')), disk(tmp)
    warnings = []
    if card['free_bytes'] < 5 * GB:
        warnings.append('Karte (/): weniger als 5 GB frei')
    if temporary['used_percent'] > 50:
        warnings.append('/tmp: mehr als 50 % belegt')
    mounts = (proc / 'mounts').read_text().splitlines()
    temporary['filesystem'] = next((line.split()[2] for line in mounts
                                    if line.split()[1] == str(tmp)), 'kein eigener Mountpoint')
    return {'home': str(home), 'repo': str(repo), 'card': card, 'tmp': temporary,
            'ram': {'total_bytes': memory['MemTotal'], 'available_bytes': memory['MemAvailable'],
                    'used_bytes': memory['MemTotal'] - memory['MemAvailable']},
            'swap': {'total_bytes': memory['SwapTotal'], 'free_bytes': memory['SwapFree'],
                     'used_bytes': memory['SwapTotal'] - memory['SwapFree']},
            'largest_home': largest(home), 'largest_var': largest(repo / 'var'),
            'protected': protected_report(home, repo, tmp),
            'recording_in_progress': recording(repo), 'warnings': warnings}


def render_text(data: dict) -> str:
    lines = [f"Pi-Hauswart: {data['repo']}"]
    for key, label in (('card', 'Karte (/)'), ('tmp', '/tmp')):
        info = data[key]
        lines.append(f"{label}: {info['free_bytes'] / GB:.2f} GB frei, {info['used_percent']:.1f} % belegt")
    lines += [f"RAM: {data['ram']['available_bytes'] / GB:.2f} GB verfügbar",
              f"Swap: {data['swap']['used_bytes'] / GB:.2f} GB belegt / {data['swap']['total_bytes'] / GB:.2f} GB"]
    lines.append(f"/tmp-Dateisystem: {data['tmp']['filesystem']}")
    for key, label in (('largest_home', 'Größte Posten im Home'), ('largest_var', 'Größte Posten in var'),
                       ('protected', 'Geschützt, nur gemeldet')):
        lines.append(label + ':')
        for item in data[key]:
            lines.append(f"  {item['bytes'] / GB:.3f} GB {item['path']}" +
                         ('' if item['complete'] else ' (unvollständig)'))
    lines += ['WARNUNG: ' + warning for warning in data['warnings']]
    if data['recording_in_progress']:
        lines.append('RECORDING_IN_PROGRESS: Bericht erstellt; Löschen gesperrt.')
    for item in data['cleanup']:
        lines.append(f"{item['action']}: {item['path']} ({item['bytes']} Bytes)" +
                     (f" — {item['reason']}" if item['reason'] else ''))
    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path('/home/me-systeme'))
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--json', action='store_true', help='Maschinenlesbarer Bericht mit warnings-Feld')
    parser.add_argument('--clean', action='store_true', help='Freigegebene Liste bereinigen')
    parser.add_argument('--dry-run', action='store_true', help='Löschplan mit Größen, ohne Änderungen')
    args = parser.parse_args(argv)
    home, repo = args.home.absolute(), args.repo.absolute()
    try:
        data = report(home, repo, Path('/tmp'), Path('/proc'))
        data['cleanup'] = cleanup(home, repo, Path('/tmp'), getpass.getuser(), Path('/proc'),
                                  clean=args.clean, dry_run=args.dry_run)
    except (OSError, ValueError, KeyError) as error:
        data = {'error': str(error), 'warnings': []}
        print(json.dumps(data) if args.json else f"Fehler: {error}")
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else render_text(data))
    return int(any(item['action'] == 'error' for item in data['cleanup']))


if __name__ == '__main__':
    raise SystemExit(main())
