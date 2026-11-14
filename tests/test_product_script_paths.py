"""Produktskripte duerfen weder Entwickler-Home noch festen Login voraussetzen."""

import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Ausschliesslich CI/Wiki/Wartung und ein historisches Offline-Experiment.
# Neue Produktskripte werden automatisch geprueft, keine Positivliste.
SCRIPT_EXCEPTIONS = {
    'forgejo-*': 'CI-Runner des Entwicklungsservers',
    'wiki-*': 'Wiki-Wartung und Export',
    'wiki_*': 'Wiki-Server und Session-Export',
    'repo-maintenance*': 'Entwicklungs-Repository-Wartung',
    'picam-codex-*': 'Codex-Runner und Auth-Synchronisierung',
    'docs-maintenance*': 'Dokumentations-Wartung auf Forgejo',
    'check-auth-protected.sh': 'OAuth-Pruefung des Entwicklungsservers',
    'dotmatrix-grid-probe.py': 'Historisches Offline-Rasterexperiment mit Agenten-Artefaktpfad',
}
SOURCE_EXCEPTIONS = {'dispread/workbench/static/login.html': 'UI/Firmenname; im Handoff vom Editieren ausgenommen'}
# Hersteller-Domain me-systeme.de ist kein Benutzerkonto.
FORBIDDEN = re.compile(r'/home/me-systeme|(?<![\w.-])me-systeme(?![\w-]|\.de)')


def test_no_developer_paths_or_accounts_in_product():
    paths = [path for path in (ROOT / 'scripts').rglob('*')
             if path.is_file() and '__pycache__' not in path.parts
             and not any(fnmatch.fnmatch(path.name, pattern) for pattern in SCRIPT_EXCEPTIONS)]
    paths += [path for path in (ROOT / 'src').rglob('*')
              if path.is_file() and '__pycache__' not in path.parts
              and str(path.relative_to(ROOT / 'src')) not in SOURCE_EXCEPTIONS]
    violations = [str(path.relative_to(ROOT)) for path in paths
                  if FORBIDDEN.search(path.read_text(errors='replace'))]
    assert not violations, f'Entwicklerpfade/-konten im Produkt: {violations}'
