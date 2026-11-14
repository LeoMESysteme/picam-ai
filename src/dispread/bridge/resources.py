"""Pi output-port ownership. Importable on Windows; POSIX is used only on acquire."""
from __future__ import annotations

import hashlib
import os
import stat
import threading
from pathlib import Path


class SerialPortLease:
    def __init__(self, directory: Path | None = None):
        self.directory = directory
        self._lock = threading.Lock()
        self._held = {}

    def acquire(self, path: str, owner_id: str, role: str):
        import fcntl

        canonical = Path(path).resolve()
        reference = Path('/dev/ttyUSB0').resolve()
        if canonical == reference or canonical.name == 'ttyUSB0':
            raise ValueError('reference port may never be opened as output')
        try:
            device = canonical.stat()
            ref = reference.stat() if reference.exists() else None
            if ref is not None and stat.S_ISCHR(device.st_mode) and device.st_rdev == ref.st_rdev:
                raise ValueError('reference port may never be opened as output')
            key = f'device-{device.st_rdev}' if stat.S_ISCHR(device.st_mode) else str(canonical)
        except FileNotFoundError:
            key = str(canonical)
        directory = self.directory or Path(f'/tmp/dispread-serial-{os.getuid()}')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError('unsafe serial lease directory')
        with self._lock:
            if owner_id in self._held:
                raise ValueError('owner already has a serial port')
            fd = os.open(directory / (hashlib.sha256(key.encode()).hexdigest() + '.lock'),
                         os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(fd)
                raise ValueError('serial port occupied; stop its owner explicitly') from None
            except BaseException:
                os.close(fd)
                raise
            self._held[owner_id] = fd
        return str(canonical)

    def release(self, owner_id: str):
        with self._lock:
            fd = self._held.pop(owner_id, None)
            if fd is not None:
                os.close(fd)
