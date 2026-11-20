"""me-fastfetch (optionale Installerkomponente): echte Pseudo-Terminals und das installierte fastfetch.

Übernommen aus ~/.local/share/me-fastfetch/test_me_logo.py; das Skript liegt jetzt
unter packaging/me-fastfetch/, das Startskript entsteht aus der Vorlage wie beim
Installer. Ohne fastfetch werden die Tests übersprungen.
"""

import errno
import fcntl
import os
import pty
import select
import shlex
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'packaging/me-fastfetch/me-logo.py'
sys.path.insert(0, str(ROOT / 'packaging'))
from picam_installer import fastfetch  # noqa: E402

CHILD = """
import os, runpy, sys
namespace = runpy.run_path(sys.argv[1])
sys.argv = [sys.argv[1], '--fastfetch', '--duration', sys.argv[2]]
code = namespace['main']()
print('READY:' + str(code), flush=True)
line = b''
while not line.endswith(b'\\n'):
    line += os.read(0, 4096)
print('INPUT:' + line.hex(), flush=True)
"""

@pytest.mark.timing
@pytest.mark.skipif(shutil.which('fastfetch') is None, reason='fastfetch nicht installiert')
class AnimationInputTests(unittest.TestCase):
    def start_terminal(self, duration, command=None):
        pid, fd = pty.fork()
        if pid == 0:
            os.environ['TERM'] = 'xterm-256color'
            os.environ.pop('NO_COLOR', None)
            if command is not None:
                os.execv(command[0], command)
            os.execv(sys.executable, [sys.executable, '-c', CHILD, str(SCRIPT), str(duration)])
        self.pid, self.fd, self.output = pid, fd, b''
        self.addCleanup(self.close_terminal)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', 50, 120, 0, 0))
        self.original_settings = termios.tcgetattr(fd)
        self.wait_for(b'\x1b[?25l', 5)

    def close_terminal(self):
        try:
            os.kill(self.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.waitpid(self.pid, 0)
        os.close(self.fd)

    def wait_for(self, marker, timeout):
        deadline = time.monotonic() + timeout
        while marker not in self.output:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                self.fail(f'Terminal did not produce {marker!r} within {timeout}s')
            try:
                chunk = os.read(self.fd, 65536)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                chunk = b''
            self.assertTrue(chunk, 'Terminal closed unexpectedly')
            self.output += chunk

    def check_input(self, keys):
        self.start_terminal(3)
        began = time.monotonic()
        os.write(self.fd, keys)
        self.wait_for(b'READY:0', 0.6)
        self.assertLess(time.monotonic() - began, 0.6)
        self.assertEqual(termios.tcgetattr(self.fd), self.original_settings)
        self.assertIn(b'\x1b[?25h', self.output)
        # Finish the command only after the animation has already stopped.
        if not keys.endswith(b'\n'):
            os.write(self.fd, b'\n')
            keys += b'\n'
        self.wait_for(b'INPUT:' + keys.hex().encode(), 1)

    def test_typing_stops_animation_and_preserves_first_character(self):
        self.check_input(b'l')

    def test_enter_stops_animation_and_remains_available(self):
        self.check_input(b'\n')

    def test_pasted_unicode_command_is_preserved(self):
        self.check_input('echo größe'.encode())

    def test_normal_completion_restores_terminal(self):
        self.start_terminal(0.2)
        self.wait_for(b'READY:0', 1)
        self.assertEqual(termios.tcgetattr(self.fd), self.original_settings)
        self.assertIn(b'\x1b[?25h', self.output)

    def test_ctrl_c_restores_terminal(self):
        self.start_terminal(3)
        os.write(self.fd, b'\x03')
        self.wait_for(b'READY:130', 0.6)
        self.assertEqual(termios.tcgetattr(self.fd), self.original_settings)
        self.assertIn(b'\x1b[?25h', self.output)

    @unittest.skipUnless(os.access('/usr/bin/python3', os.X_OK), 'Startskript nutzt /usr/bin/python3')
    def test_bash_readline_keeps_typed_command(self):
        # Startskript wie vom Installer erzeugt, aber auf das Skript im Repo gerichtet.
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        template = (ROOT / 'packaging/me-fastfetch/me-fastfetch.in').read_bytes()
        rendered = fastfetch.render({name: template if name.endswith('.in') else b'' for name, _, _ in
                                     fastfetch.TARGETS}, directory)
        wrapper = directory / '.local/bin/me-fastfetch'
        content = rendered[wrapper][0].replace(shlex.quote(str(directory / fastfetch.SHARE / 'me-logo.py')).encode(),
                                               shlex.quote(str(SCRIPT)).encode())
        assert content.startswith(b'#!/bin/sh') and b'/usr/bin/python3 ' + shlex.quote(str(SCRIPT)).encode() in content
        wrapper.parent.mkdir(parents=True)
        wrapper.write_bytes(content)
        wrapper.chmod(0o755)
        shell_code = (
            f'{wrapper} --duration 3; '
            'read -e -r -p "READY> " command; printf "\\nCOMMAND:%s\\n" "$command"'
        )
        self.start_terminal(3, ['/bin/bash', '--noprofile', '--norc', '-ic', shell_code])
        os.write(self.fd, b'printf')
        self.wait_for(b'READY> ', 0.6)
        os.write(self.fd, b' hello\n')
        self.wait_for(b'COMMAND:printf hello', 1)

    def test_piped_output_remains_static(self):
        result = subprocess.run([sys.executable, str(SCRIPT), '--fastfetch'],
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'####', result.stdout)
        self.assertNotIn(b'\x1b', result.stdout)


def test_logo_shape_matches_fastfetch_logo_file():
    """Der Glanzlauf erkennt das Logo nur, wenn me-logo.txt und LOGO übereinstimmen."""
    text = (ROOT / 'packaging/me-fastfetch/me-logo.txt').read_text()
    rows = [line.removeprefix('$1') for line in text.splitlines() if line.startswith('$1')]
    source = SCRIPT.read_text()
    assert all(f'"{row}"' in source for row in rows) and len(rows) == 8
