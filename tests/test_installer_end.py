"""Ende der geführten Installation (Enter startet picam mit Einrichtung, q bleibt im Terminal, ohne
Terminal keine Frage) und Optik des Installers (Karten, Abzeichen, Farbrückfall, keine verbotenen Glyphen)."""
# ruff: noqa: F811
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packaging'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from picam_installer import engine, guided, tui  # noqa: E402
from test_installer_guided import env, fake_installer, fake_runner  # noqa: E402,F401,F811
from test_installer_tui import FORBIDDEN, Tty, menus, no_terminal, scripted, tui_plain  # noqa: E402

OWNER = SimpleNamespace(pw_name='labor', pw_dir='/home/labor', pw_uid=1000, pw_gid=1000)
VENV = Path('/opt/picam/current/.venv/bin/picam')
ENV_TTY = {'LANG': 'de_DE.UTF-8', 'TERM': 'xterm'}


def args_for(env, mode='user'):
    return engine.parser().parse_args(['--source', str(env.archive), '--mode', mode, '--user', 'labor',
                                       '--host', '192.168.10.42'])


def apply_with(env, monkeypatch, ui, execs, *, euid=1000, mode='user', out=None, input_=None):
    monkeypatch.setattr(os, 'geteuid', lambda: euid)
    monkeypatch.setattr(guided, 'wait_ready', lambda host, port: True)
    out = out or tui.Out(io.StringIO(), color=False)
    code = guided.apply(args_for(env, mode), out=out, input_=input_, ui=ui,
                        runner=lambda command, **_: SimpleNamespace(returncode=0, stdout='', stderr=''),
                        installer=fake_installer([]), execvp=lambda name, argv: execs.append((name, argv)))
    return code, out


# ---------------------------------------------------------------- Ende der Installation
def test_enter_starts_console_with_onboarding_as_operator(env, monkeypatch):
    ui, out = menus('j', 'enter')   # Dienst starten: ja, dann Enter
    execs = []
    code, _ = apply_with(env, monkeypatch, ui, execs, out=out)
    text = tui_plain(out.stream.getvalue())
    assert code == 0 and len(execs) == 1
    name, argv = execs[0]
    assert name == argv[0] and argv[-1] == '--onboarding' and argv[0].endswith('/current/.venv/bin/picam')
    assert 'Enter' in text and 'picam starten und Einrichtung abschließen' in text and 'q' in text
    assert 'im Terminal bleiben' in text


def test_q_stays_in_terminal(env, monkeypatch):
    for key in ('q', 'esc'):
        ui, out = menus('j', key)
        execs = []
        code, _ = apply_with(env, monkeypatch, ui, execs, out=out)
        assert code == 0 and execs == []
        assert '--onboarding' in tui_plain(out.stream.getvalue())      # Befehl wird genannt


def test_other_keys_are_ignored_until_enter_or_q(env, monkeypatch):
    ui, out = menus('j', 'x', 'space', 'enter')
    execs = []
    apply_with(env, monkeypatch, ui, execs, out=out)
    assert len(execs) == 1


def test_root_installer_hands_over_to_the_operator_via_sudo(env, monkeypatch):
    ui, out = menus('j', 'enter')
    execs = []
    monkeypatch.setattr(guided.shutil, 'which', lambda name: f'/usr/bin/{name}')
    apply_with(env, monkeypatch, ui, execs, euid=0, mode='system', out=out)
    argv = execs[0][1]
    assert argv[:5] == ['sudo', '-u', 'labor', '-H', argv[4]] and argv[-1] == '--onboarding'
    assert 'root' not in argv


def test_root_without_sudo_uses_runuser_and_home(monkeypatch):
    monkeypatch.setattr(guided.shutil, 'which', lambda name: '/usr/sbin/runuser' if name == 'runuser' else None)
    argv = guided.run_as_operator([str(VENV), '--onboarding'], OWNER, euid=0)
    assert argv[:4] == ['runuser', '-u', 'labor', '--'] and 'HOME=/home/labor' in argv


def test_other_account_without_root_is_not_switched():
    assert guided.run_as_operator(['x'], OWNER, euid=1001) is None
    assert guided.run_as_operator(['x'], OWNER, euid=1000) == ['x']


def test_portable_command_carries_config(env):
    args = args_for(env, 'portable')
    command = guided.start_command(args, OWNER, VENV, {'config': '/p/config.toml'})
    assert command == [str(VENV), '--onboarding', '--config', '/p/config.toml']


def test_no_terminal_means_no_question(env, monkeypatch):
    out = io.StringIO()
    execs = []
    code, _ = apply_with(env, monkeypatch, None, execs, out=tui.Out(out, color=False),
                         input_=lambda _p: 'n')
    text = out.getvalue()
    assert code == 0 and execs == [] and 'picam --onboarding' in text and 'Enter' not in text


def test_typed_ui_never_asks(env, monkeypatch):
    execs = []
    code, out = apply_with(env, monkeypatch, guided.Typed(tui.Out(io.StringIO(), color=False), lambda _p: 'n'),
                           execs)
    assert code == 0 and execs == []


def test_keyboard_interrupt_counts_as_q(env, monkeypatch):
    out = tui.Out(Tty(), stdin=io.StringIO(), env=ENV_TTY)
    keys = iter(['j'])

    def read(_fd):
        try:
            return next(keys)
        except StopIteration:
            raise KeyboardInterrupt from None
    execs = []
    apply_with(env, monkeypatch, tui.Menus(out, read=read, keymode=no_terminal), execs, out=out)
    assert execs == []


def test_summary_names_address_account_password_and_certificate(env, monkeypatch):
    monkeypatch.setattr(tui.shutil, 'get_terminal_size', lambda fallback=(80, 24): os.terminal_size((140, 40)))
    out = tui.Out(Tty(), stdin=io.StringIO(), env=ENV_TTY)
    ui = tui.Menus(out, read=scripted('j', 'q'), keymode=no_terminal)
    monkeypatch.setattr(guided, 'cert_fingerprint', lambda path: 'AB:CD:' * 16 + 'EF')
    apply_with(env, monkeypatch, ui, [], out=out)
    text = tui_plain(out.stream.getvalue())
    assert 'FERTIG' in text and 'https://192.168.10.42:8080/live' in text
    assert 'Benutzer „labor“ mit dem Linux-Passwort dieses Kontos' in text
    assert 'sudo passwd labor' in text and 'selbstsigniert' in text and 'SHA-256' in text
    assert 'picam --onboarding' in text


# ---------------------------------------------------------------- Optik
class AsciiTty(Tty):
    encoding = 'ascii'


def render(env_vars, *, color=True, stream=None):
    stream = stream or Tty()
    out = tui.Out(stream, stdin=io.StringIO(), env=env_vars) if color else tui.Out(stream, color=False,
                                                                                  env=env_vars)
    out.rule('System')
    out.card('System', [('Betriebssystem', 'Debian 13 - aarch64', 'ok'), ('Bruecke', 'fehlt', 'warn'),
                        ('Dienst', 'kaputt', 'fail'), ('Netz', 'aus', 'off'), ('Pfad', '/opt/picam')],
             badge='ok', hint='alles gut')
    out.status('fail', 'Fehler', 'x')
    return out, stream.getvalue()


def test_card_uses_palette_truecolor_with_stepped_background():
    out, text = render(ENV_TTY)
    assert '48;2;51;60;71' in text and '48;2;36;43;51' in text      # surface, band der Konsole
    assert '48;2;50;70;61' in text and '48;2;74;66;48' in text      # Abzeichen ok, warn
    plain = tui_plain(text)
    for word in ('OK', 'WARNUNG', 'FEHLER', 'AUS', 'SYSTEM'):
        assert word in plain
    assert not FORBIDDEN & set(plain)


def test_color_falls_back_to_256_and_16():
    _, text256 = render({**ENV_TTY, 'PICAM_COLORS': '256'})
    assert '48;5;' in text256 and ';2;' not in text256
    _, text16 = render({**ENV_TTY, 'TERM': 'linux'})
    assert ';2;' not in text16 and '48;' not in text16 and '38;5' not in text16
    assert re.search(r'\x1b\[[0-9;]*9?[0-7]m', text16)


def test_no_color_has_plain_badges_and_no_escapes():
    out, text = render({**ENV_TTY, 'NO_COLOR': '1'})
    assert '\033[' not in text and '[OK]' in text and '[WARNUNG]' in text and '[FEHLER]' in text
    assert all(ord(char) < 128 for char in text)


def test_ascii_without_utf8_locale():
    _, text = render({'LANG': 'C', 'TERM': 'xterm'}, stream=AsciiTty())
    assert all(ord(char) < 128 for char in tui_plain(text).replace('·', '.'))
    assert '|' in text and '#' in text


def test_card_without_terminal_is_plain_lines():
    stream = io.StringIO()
    out = tui.Out(stream, color=False)
    out.card('System', [('Betriebssystem', 'Debian', 'ok'), ('Pfad', '/x')], hint='h')
    text = stream.getvalue()
    assert '\033[' not in text and 'System' in text and 'Betriebssystem' in text and '/x' in text


def test_card_lines_have_equal_width_and_fit_the_terminal(monkeypatch):
    monkeypatch.setattr(tui.shutil, 'get_terminal_size', lambda fallback=(80, 24): os.terminal_size((80, 24)))
    _, text = render(ENV_TTY)
    widths = {tui.visible(line) for line in text.split('\n') if line.strip().startswith('\033[38;2;69;201;190;48;2;51')}
    assert len(widths) == 1 and widths.pop() <= 80


def test_selected_menu_row_uses_selection_colour():
    ui, out = menus('enter')
    ui.choose('Art', [('a', 'Alpha – eins'), ('b', 'Beta – zwei')])
    assert '48;2;34;90;87' in out.stream.getvalue()      # select_bg der Konsole


def test_whole_guided_output_has_no_forbidden_glyphs(env, monkeypatch):
    out = tui.Out(Tty(), stdin=io.StringIO(), env=ENV_TTY)
    ui = tui.Menus(out, read=scripted('j', 'q'), keymode=no_terminal)
    apply_with(env, monkeypatch, ui, [], out=out)
    assert not FORBIDDEN & set(tui_plain(out.stream.getvalue()))
