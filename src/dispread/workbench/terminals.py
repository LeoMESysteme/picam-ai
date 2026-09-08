"""Echte PTYs; Shells leben unabhaengig von Browser-WebSockets."""

from __future__ import annotations

import asyncio
import errno
import fcntl
import os
import pty
import signal
import struct
import subprocess
import sys
import termios
import uuid
from pathlib import Path


class Terminal:
    def __init__(self, cwd, socket_path):
        self.id = uuid.uuid4().hex
        self.buffer = bytearray()
        self.offset = 0
        self.exit_code = None
        self.closed = False
        self.loop = asyncio.get_running_loop()
        descriptor, slave = pty.openpty()
        env = dict(
            os.environ,
            TERM="xterm-256color",
            COLORTERM="truecolor",
            DISPREAD_SOCKET=str(socket_path),
            VIRTUAL_ENV=str(Path(cwd) / ".venv"),
        )
        env["PATH"] = str(Path(cwd) / ".venv/bin") + os.pathsep + env.get("PATH", "")
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-m", "dispread.workbench.shell"],
                cwd=cwd,
                env=env,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,
            )
        except Exception:
            os.close(descriptor)
            raise
        finally:
            os.close(slave)
        self.pid, self.fd = self.process.pid, descriptor
        os.set_blocking(descriptor, False)
        self.resize(100, 24)
        self.loop.add_reader(descriptor, self.read)
        self.wait_task = self.loop.create_task(self.reap())

    def read(self):
        try:
            data = os.read(self.fd, 65536)
        except OSError as error:
            if error.errno == errno.EAGAIN:
                return
            data = b""
        if not data:
            self.loop.remove_reader(self.fd)
            return
        self.buffer.extend(data)
        if len(self.buffer) > 2 * 1024 * 1024:
            count = len(self.buffer) - 2 * 1024 * 1024
            del self.buffer[:count]
            self.offset += count

    async def reap(self):
        self.exit_code = await asyncio.to_thread(self.process.wait)

    async def write(self, data):
        if self.closed or self.exit_code is not None:
            return
        if len(data) > 16384:
            raise ValueError("Terminaleingabe zu gross")
        while data and not self.closed:
            try:
                written = os.write(self.fd, data)
                data = data[written:]
            except BlockingIOError:
                await asyncio.sleep(0.02)

    def resize(self, cols, rows):
        if not 2 <= cols <= 500 or not 2 <= rows <= 200:
            raise ValueError("Ungueltige Terminalgroesse")
        if not self.closed:
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    async def close(self):
        if self.closed:
            return
        self.closed = True
        self.loop.remove_reader(self.fd)
        # Capture normal shell descendants before hangup/reparenting.
        processes = []
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    if int(fields[3]) == self.pid:  # session ID
                        processes.append(int(entry.name))
                except (OSError, ValueError, IndexError):
                    pass
        os.close(self.fd)
        for pid in processes:
            try:
                os.kill(pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
        await asyncio.sleep(0.1)
        for pid in processes:
            try:
                if os.getsid(pid) == self.pid:
                    os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await self.wait_task


class Terminals:
    def __init__(self, cwd, socket_path):
        self.cwd, self.socket_path = cwd, socket_path
        self.items = {}

    def create(self):
        if len(self.items) >= 8:
            raise ValueError("Maximal acht Shell-Tabs; zuerst einen schliessen")
        terminal = Terminal(self.cwd, self.socket_path)
        self.items[terminal.id] = terminal
        return terminal

    def list(self):
        return [{"id": t.id, "exit_code": t.exit_code} for t in self.items.values()]

    async def close(self):
        await asyncio.gather(*(t.close() for t in self.items.values()))
        self.items.clear()
