"""run_hint_command führt Hinweisbefehle ohne Shell aus (bandit B602)."""
from __future__ import annotations

import sys
from types import SimpleNamespace

from dispread.admin import cli


def _instance(tmp_path):
    return SimpleNamespace(root=str(tmp_path), config=None)


def test_befehl_ohne_shell_und_im_instanzverzeichnis(tmp_path):
    out = tmp_path / 'ausgabe.txt'
    code = cli.run_hint_command(
        f'{sys.executable} -c "import os, pathlib; pathlib.Path(\'ausgabe.txt\').write_text(os.getcwd())"',
        _instance(tmp_path))
    assert code == 0
    assert out.read_text() == str(tmp_path)


def test_shell_metazeichen_werden_nicht_ausgewertet(tmp_path):
    marker = tmp_path / 'darf-nicht-entstehen'
    code = cli.run_hint_command(f'{sys.executable} -c pass; touch {marker}', _instance(tmp_path))
    assert not marker.exists()
    assert code != 0 or not marker.exists()


def test_unbalancierte_anfuehrungszeichen_geben_fehlercode(tmp_path, capsys):
    assert cli.run_hint_command('echo "offen', _instance(tmp_path)) == 2
    assert 'nicht ausführbar' in capsys.readouterr().err
