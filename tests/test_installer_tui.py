"""Menüs, Spinner und Logo des geführten Installers: Tastenfolgen ohne echtes Terminal, ein echtes PTY."""
from __future__ import annotations

import io
import os
import pty
import sys
import termios
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packaging'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from picam_installer import guided, tui  # noqa: E402
from test_installer_guided import env, fake_installer, fake_runner  # noqa: E402,F401

FORBIDDEN = set('✔⚙⏸⏹ℹ←…')


class Tty(io.StringIO):
    encoding = 'utf-8'

    def isatty(self):
        return True


@contextmanager
def no_terminal(_out):
    yield None


def scripted(*keys):
    queue = list(keys)

    def read(_fd):
        if not queue:
            raise AssertionError('keine Taste mehr')
        return queue.pop(0)
    return read


def menus(*keys, stream=None, input_=None, environ=None):
    out = tui.Out(stream or Tty(), stdin=io.StringIO(), env=environ or {'LANG': 'de_DE.UTF-8', 'TERM': 'xterm'})
    return tui.Menus(out, read=scripted(*keys), keymode=no_terminal, input_=input_), out


OPTIONS = [('system', 'Systemdienst – startet beim Booten'), ('user', 'Benutzerdienst – im Home'),
           ('portable', 'Portabel – ohne Dienst')]


def test_arrows_and_enter_choose():
    ui, out = menus('down', 'down', 'up', 'enter')
    assert ui.choose('Installationsart', OPTIONS) == 'user'
    text = out.stream.getvalue()
    assert 'Benutzerdienst' in text and '↑↓ wählen' in text and '1–3 direkt' in text


def test_vim_keys_wrap_and_digits_choose_directly():
    assert menus('k', 'enter')[0].choose('X', OPTIONS) == 'portable'
    assert menus('j', 'j', 'j', 'enter')[0].choose('X', OPTIONS) == 'system'
    assert menus('3')[0].choose('X', OPTIONS) == 'portable'


def test_escape_and_q_cancel():
    for key in ('esc', 'q'):
        with pytest.raises(KeyboardInterrupt):
            menus(key)[0].choose('X', OPTIONS)


def test_default_row_is_preselected():
    assert menus('enter')[0].choose('X', OPTIONS, default=2) == 'user'


def test_multi_select_toggles_with_space():
    items = [('a', 'eins', '', True), ('b', 'zwei', '', False)]
    assert menus('enter')[0].multi('K', items) == {'a'}
    assert menus('space', 'down', 'space', 'enter')[0].multi('K', items) == {'b'}
    assert menus('1', 'enter')[0].multi('K', items) == set()
    with pytest.raises(KeyboardInterrupt):
        menus('esc')[0].multi('K', items)


def test_confirm_keys():
    assert menus('enter')[0].confirm('Installieren?') is False
    assert menus('enter')[0].confirm('Starten?', default=True) is True
    assert menus('left', 'enter')[0].confirm('Installieren?') is True
    assert menus('j')[0].confirm('Installieren?') is True
    assert menus('n')[0].confirm('Installieren?', default=True) is False
    assert menus('esc')[0].confirm('Installieren?', default=True) is False


def test_text_prompt_revalidates_inline():
    answers = iter(['abc', '70000', ''])
    ui, out = menus(input_=lambda _prompt: next(answers))
    value = ui.text('Port', '8080', validate=lambda raw: None if raw.isdigit() and int(raw) < 65536 else 'Port ungültig')
    assert value == '8080'
    assert out.stream.getvalue().count('Port ungültig') == 2


def test_menu_lines_never_use_forbidden_glyphs():
    ui, out = menus('down', 'enter', 'space', 'enter', 'enter')
    ui.choose('Installationsart', OPTIONS)
    ui.multi('K', [('a', 'eins', 'x', True)])
    ui.confirm('Installieren?')
    assert not FORBIDDEN & set(out.stream.getvalue())


def test_ascii_fallback_without_utf8_or_with_no_color():
    for environ in ({'LANG': 'C', 'TERM': 'xterm'}, {'LANG': 'de_DE.UTF-8', 'NO_COLOR': '1', 'TERM': 'xterm'}):
        stream = Tty()
        stream.encoding = 'ascii'
        out = tui.Out(stream, stdin=io.StringIO(), env=environ)
        assert out.sym is tui.ASCII
        with out.progress(2) as progress:
            progress.step('eins')
            progress.step('zwei')
        assert all(ord(char) < 128 for char in stream.getvalue())


def test_progress_live_marks_steps_and_draws_bar():
    out = tui.Out(Tty(), stdin=io.StringIO(), env={'LANG': 'de_DE.UTF-8', 'TERM': 'xterm'})
    with out.progress(3) as progress:
        progress.step('Release entpacken')
        progress.step('Selbsttest')
    text = out.stream.getvalue()
    assert '✓ Release entpacken' in tui_plain(text) and '✓ Selbsttest' in tui_plain(text)
    assert '█' in text and '3/3' in tui_plain(text) and text.endswith('\033[?25h')


def test_progress_marks_failure():
    out = tui.Out(Tty(), stdin=io.StringIO(), env={'LANG': 'de_DE.UTF-8', 'TERM': 'xterm'})
    with pytest.raises(RuntimeError), out.progress(3) as progress:
        progress.step('Selbsttest')
        raise RuntimeError
    assert '✗ Selbsttest' in tui_plain(out.stream.getvalue())


def test_progress_without_terminal_writes_plain_lines():
    stream = io.StringIO()
    out = tui.Out(stream, stdin=io.StringIO(), env={'LANG': 'de_DE.UTF-8'})
    with out.progress(2) as progress:
        progress.step('Zielverzeichnisse anlegen')
    with out.task('System prüfen', quiet=True):
        pass
    assert stream.getvalue() == '  › Zielverzeichnisse anlegen\n' and '\033' not in stream.getvalue()


def test_intro_needs_terminal_and_can_be_disabled(monkeypatch):
    out = tui.Out(io.StringIO(), stdin=io.StringIO())
    assert tui.play_intro(out) is False and out.stream.getvalue() == ''
    tty_out = tui.Out(Tty(), stdin=Tty(), env={'LANG': 'de_DE.UTF-8', 'TERM': 'xterm'})
    assert tui.intro_allowed(tty_out, env={'PICAM_INTRO': '0'}) is False
    assert tui.intro_allowed(tty_out, env={'NO_COLOR': '1'}) is False


def test_logo_frames_reveal_and_settle():
    first = tui.logo_cells(0.0)
    assert all(level in (0, 1, 3, 4) for row in first for _, level in row)
    final = tui.logo_cells(None)
    assert [''.join(char for char, _ in row).rstrip() for row in final] == list(tui.LOGO)
    assert tui.scramble(tui.CAPTION, 1.0) == tui.CAPTION != tui.scramble(tui.CAPTION, 0.3)


def test_read_key_parses_sequences():
    for raw, key in ((b'\x1b[A', 'up'), (b'\x1bOB', 'down'), (b'\x1b', 'esc'), (b'\r', 'enter'),
                     (b' ', 'space'), (b'j', 'j'), ('ä'.encode(), 'ä')):
        read, write = os.pipe()
        os.write(write, raw)
        try:
            assert tui.read_key(read) == key
        finally:
            os.close(read)
            os.close(write)
    read, write = os.pipe()
    os.write(write, b'\x03')
    with pytest.raises(KeyboardInterrupt):
        tui.read_key(read)
    os.close(read)
    os.close(write)


def test_key_mode_is_restored_on_interrupt(monkeypatch):
    master, slave = pty.openpty()
    stdin = os.fdopen(slave, 'r', closefd=False)
    monkeypatch.setattr(sys, 'stdin', stdin)
    before = termios.tcgetattr(slave)
    out = tui.Out(Tty(), stdin=stdin)
    with pytest.raises(KeyboardInterrupt), tui.keys(out):
        assert termios.tcgetattr(slave)[3] & termios.ICANON == 0
        raise KeyboardInterrupt
    assert termios.tcgetattr(slave) == before
    assert out.stream.getvalue().endswith('\033[?25h')
    os.close(master)
    os.close(slave)


def tui_plain(text):
    import re
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)


# ---------------------------------------------------------------- Geführter Ablauf mit Menüs
def test_make_ui_falls_back_to_typed_input():
    out = tui.Out(io.StringIO(), stdin=io.StringIO())
    assert isinstance(guided.make_ui(out, None), guided.Typed)
    tty = tui.Out(Tty(), stdin=Tty(), env={'TERM': 'xterm'})
    assert isinstance(guided.make_ui(tty, lambda _p: ''), guided.Typed)
    dumb = tui.Out(Tty(), stdin=Tty(), env={'TERM': 'dumb'})
    assert isinstance(guided.make_ui(dumb, None), guided.Typed)


def test_guided_menu_flow_with_fastfetch_deselected(env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(guided, 'operator_accounts', lambda: ['labor', 'gast'])
    (env.tmp / 'home').mkdir()
    texts = iter(['', str(env.tmp / 'p')])  # Port übernehmen, Ordner
    ui, out = menus('3', 'enter', 'enter', 'space', 'enter', 'j', input_=lambda _p: next(texts))
    calls = []
    code = guided.run([], ui=ui, out=out, runner=fake_runner(), installer=fake_installer(calls),
                      installer_root=env.tmp)
    text = tui_plain(out.stream.getvalue())
    assert code == 0, text
    plan_args = calls[0][0]
    assert (plan_args.mode, plan_args.user, plan_args.fastfetch) == ('portable', 'labor', False)
    assert 'Komponenten' in text and 'keine' in text and 'me-fastfetch' in text


def test_guided_menu_flow_plans_fastfetch_by_default(env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    monkeypatch.setattr(guided, 'operator_accounts', lambda: ['labor'])
    (env.tmp / 'home').mkdir()
    texts = iter(['', '8081', str(env.tmp / 'p')])  # Konto, Port, Ordner
    ui, out = menus('3', 'enter', 'enter', 'n', input_=lambda _p: next(texts))
    calls = []
    assert guided.run([], ui=ui, out=out, runner=fake_runner(), installer=fake_installer(calls),
                      installer_root=env.tmp) == 130
    text = tui_plain(out.stream.getvalue())
    assert calls[0][0].fastfetch is True and '~/.local/bin/me-fastfetch' in text and '~/.bashrc' in text
    assert 'nichts geändert' in text and not (env.tmp / 'home/.local').exists()


def test_sudo_handover_carries_fastfetch_choice(env, monkeypatch):  # noqa: F811
    execs = []
    monkeypatch.setattr(os, 'geteuid', lambda: 1000)
    (env.tmp / 'home').mkdir()
    answers = iter(['1', '', '1', '8080', 'j'])
    guided.run(['--without-fastfetch'], input_=lambda _prompt: next(answers),
               out=tui.Out(io.StringIO(), stdin=io.StringIO()), runner=fake_runner(),
               installer=fake_installer([]), installer_root=env.tmp, execvp=lambda name, argv: execs.append(argv))
    assert '--without-fastfetch' in execs[0] and '--with-fastfetch' not in execs[0]
