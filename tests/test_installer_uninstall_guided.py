"""Geführte Deinstallation im Terminal (``uninstall.guided_main``): Plan, Rückfrage, Fortschritt, Fazit.

Nur temporäre Layouts und ein Runner, der Befehle aufzeichnet (wie ``test_installer_uninstall``)."""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from picam_installer import tui, uninstall  # noqa: E402
from test_installer_uninstall import layout, recorder  # noqa: E402

FORBIDDEN = set('✔⚙⏸⏹ℹ')
ANSI = re.compile(r'\x1b\[[0-9;]*m')
SGR = ANSI


class Tty(io.StringIO):
    encoding = 'utf-8'

    def isatty(self):
        return True


@pytest.fixture
def as_root(monkeypatch):
    monkeypatch.setattr(os, 'geteuid', lambda: 0)


@pytest.fixture
def paths(tmp_path, monkeypatch):
    layout_paths = layout(tmp_path)
    monkeypatch.setattr(uninstall, 'plan_from_args', lambda args: uninstall.plan_uninstall(
        **layout_paths, purge_data=bool(args.purge_data)))
    return layout_paths


def run(paths, answer, *, env=None, tty=True, purge=False, calls=None):
    stream = Tty() if tty else io.StringIO()
    out = tui.Out(stream, stdin=io.StringIO(), env=env or {'TERM': 'xterm', 'LANG': 'de_DE.UTF-8'})
    asked = []

    def ask(prompt):
        asked.append(prompt)
        if isinstance(answer, Exception):
            raise answer
        return answer

    calls = calls if calls is not None else []
    argv = ['--uninstall', '--guided'] + (['--purge-data'] if purge else [])
    code = uninstall.guided_main(
        uninstall.parser().parse_args(argv), out=out, ask=ask,
        apply=lambda planned, progress: uninstall.apply_uninstall(planned, runner=recorder(calls), progress=progress))
    return code, stream.getvalue(), asked, calls


def test_describe_groups_plan_in_operator_words(paths):
    view = uninstall.describe(uninstall.plan_uninstall(**paths))
    labels = [label for label, _ in view['remove']]
    assert labels[:3] == ['Dienst', 'Dienst', 'Befehl picam'] and 'Programmversionen' in labels
    assert 'Verweise' in labels and 'Installationsort' in labels
    assert {label for label, _ in view['keep']} >= {'Daten', 'Einstellungen'}
    assert view['service'] and view['needs_root']


def test_wrong_answer_changes_nothing(paths, as_root):
    for answer in ('', 'ja', 'Deinstallieren', EOFError()):
        code, text, asked, calls = run(paths, answer)
        assert code == 130 and calls == []
        assert 'Nichts deinstalliert' in text and 'deinstallieren' in asked[0]
        assert (paths['prefix'] / 'releases').is_dir()


def test_right_answer_applies_and_summarizes(paths, as_root):
    code, text, asked, calls = run(paths, 'deinstallieren')
    plain = ANSI.sub('', text)
    assert code == 0 and calls                       # systemctl wurde (aufgezeichnet) aufgerufen
    assert not (paths['prefix'] / 'releases').exists() and paths['data'].exists()
    for word in ('WIRD ENTFERNT', 'BLEIBT ERHALTEN', 'FERTIG', 'Programmversionen', 'Befehl picam', 'Daten',
                 'Einstellungen', '--purge-data'):
        assert word in plain
    assert plain.index('WIRD ENTFERNT') < plain.index('BLEIBT ERHALTEN') < plain.index('FERTIG')
    assert not FORBIDDEN & set(plain)


def test_ansi_output_uses_cards_and_badges(paths, as_root):
    code, text, *_ = run(paths, 'deinstallieren')
    assert '\x1b[' in text and '38;2;' in text and 'WARNUNG' in text and ' OK ' in text
    assert max(len(ANSI.sub('', line)) for line in text.splitlines()) <= 110


def test_no_color_prints_plain_ascii_without_escapes(paths, as_root):
    code, text, *_ = run(paths, 'deinstallieren', env={'TERM': 'xterm', 'NO_COLOR': '1', 'LANG': 'de_DE.UTF-8'})
    assert code == 0 and not SGR.search(text) and '[WARNUNG]' in text and '[OK]' in text
    assert not FORBIDDEN & set(text)


def test_without_terminal_plain_lines(paths, as_root):
    code, text, *_ = run(paths, 'deinstallieren', tty=False)
    assert code == 0 and '\x1b' not in text and 'Wird entfernt' in text


def test_purge_plan_says_data_goes_too(paths, as_root):
    code, text, asked, calls = run(paths, 'deinstallieren', purge=True)
    assert code == 0 and not paths['data'].exists()
    assert 'Brückenidentität' in ANSI.sub('', text)


def test_failure_names_what_is_done(paths):
    def failing(planned, progress):
        raise uninstall.UninstallError('x fehlgeschlagen: kaputt. Bereits erledigt: nichts')

    stream = Tty()
    out = tui.Out(stream, stdin=io.StringIO(), env={'TERM': 'xterm', 'LANG': 'de_DE.UTF-8'})
    code = uninstall.guided_main(uninstall.parser().parse_args(['--uninstall']), out=out,
                                 ask=lambda _p: 'deinstallieren', apply=failing)
    text = ANSI.sub('', stream.getvalue())
    assert code == 1 and 'FEHLGESCHLAGEN' in text and 'Bereits erledigt' in text and paths['prefix'].exists()
