"""Explizite Aufbewahrung beendeter Live-Laeufe; niemals automatisch loeschen."""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _tree_info(path: Path) -> tuple[int, float] | None:
    """Bytes/neuste Datei-mtime; Links/Sonderdateien sperren den Kandidaten.

    Verzeichniszeiten ignorieren: Diagnose-Loeschung verjuengt kein Audit.
    """
    size = 0
    newest = float('-inf')
    for item in path.rglob('*'):
        if item.is_symlink():
            return None
        stat = item.stat()
        if item.is_file():
            size += stat.st_size
            newest = max(newest, stat.st_mtime)
        elif not item.is_dir():
            return None
    return size, newest


def cleanup_runs(root: Path, *, days: int, diagnostics_only: bool = False, execute: bool = False,
                 protected=(), now: datetime | None = None) -> dict:
    """Nur alte run-NN mit bekanntem UTC-Ende listen/loeschen, Setup nie anfassen.

    Der aufrufende Dienst serialisiert Start/Stop und schuetzt aktive Laeufe
    sowie asynchrone Diagnosekopien. Fehlendes Ende (auch nach Absturz), neue
    Dateien oder Links lassen einen Lauf vorsichtshalber stehen.
    """
    if type(days) is not int or days <= 0:
        raise ValueError('Tage muessen eine positive ganze Zahl sein')
    if type(diagnostics_only) is not bool or type(execute) is not bool:
        raise ValueError('Aufraeumoptionen muessen boolesch sein')
    # Die konfigurierte Wurzel darf ueber Links erreichbar sein (Worktree-var).
    # Ab hier nur dieser reale Baum; Links innerhalb bleiben ausgeschlossen.
    root = Path(root).resolve()
    protected = {Path(p).resolve() for p in protected}
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    result = {'dry_run': not execute, 'entries': [], 'total_bytes': 0, 'total_mb': 0.0, 'failed': False}
    if not root.exists():
        return result
    for session in sorted(root.iterdir()):
        if (not re.fullmatch(r'live-\d{8}T\d{6}Z', session.name)
                or session.is_symlink() or not session.is_dir()):
            continue
        for run in sorted(session.iterdir()):
            if (not re.fullmatch(r'run-\d{2,}', run.name) or run.is_symlink()
                    or not run.is_dir() or run in protected):
                continue
            try:
                info = _tree_info(run)
                if info is None or info[1] >= cutoff.timestamp():
                    continue
                metadata = json.loads((run / 'session.json').read_text(encoding='utf-8'))
                ended = datetime.fromisoformat(metadata['ended_at_utc'])
                if ended.tzinfo is None or ended >= cutoff:
                    continue
                target = run / 'diagnose' if diagnostics_only else run
                if target.is_symlink() or not target.is_dir():
                    continue
                target_info = _tree_info(target)
                if target_info is None:
                    continue
            except (OSError, ValueError, KeyError, TypeError):
                continue
            entry = {'path': str(target), 'bytes': target_info[0], 'mb': target_info[0] / 1e6,
                     'status': 'planned'}
            if execute:
                # Unterhalb des geprueften Live-Baums; rmtree folgt keinen Links.
                try:
                    shutil.rmtree(target)
                    entry['status'] = 'deleted'
                except OSError as error:
                    entry.update(status='failed', error=str(error))
                    result['failed'] = True
            result['entries'].append(entry)
            result['total_bytes'] += entry['bytes']
    result['total_mb'] = result['total_bytes'] / 1e6
    return result
