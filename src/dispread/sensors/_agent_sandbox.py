"""Datei- und Unix-Socket-Grenze fuer Agent und Kindprozesse."""

from __future__ import annotations

import ctypes
import errno
import os
import shutil
import socket
import sys
from pathlib import Path

_CREATE, _ADD, _RESTRICT = 444, 445, 446
_WRITE = 1 << 1
# Schreiben, Entfernen, Anlegen, Umhaengen und Kuerzen. Lesezugriff fuer
# ausfuehrbare Dateien/Libs bleibt erhalten. TRUNCATE braucht ABI 3.
_WRITES = _WRITE | sum(1 << bit for bit in range(4, 15))


class _Ruleset(ctypes.Structure):
    _fields_ = [('access', ctypes.c_uint64), ('network', ctypes.c_uint64), ('scope', ctypes.c_uint64)]


class _PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('access', ctypes.c_uint64), ('fd', ctypes.c_int32)]



class _ArgComparison(ctypes.Structure):
    _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_int),
                ('first', ctypes.c_uint64), ('second', ctypes.c_uint64)]


def _block_unix_socket_creation() -> None:
    """Der Agent erreicht die private Werkbank-Steuerung nur ueber den Broker."""
    seccomp = ctypes.CDLL('libseccomp.so.2')
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
                                               ctypes.POINTER(_ArgComparison)]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    policy = seccomp.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not policy:
        raise RuntimeError('seccomp-Filter konnte nicht angelegt werden')
    try:
        socket_call = seccomp.seccomp_syscall_resolve_name(b'socket')
        io_uring_call = seccomp.seccomp_syscall_resolve_name(b'io_uring_setup')
        unix_family = _ArgComparison(0, 4, int(socket.AF_UNIX), 0)  # SCMP_CMP_EQ fuer Argument 0
        error_action = 0x00050000  # SCMP_ACT_ERRNO
        if socket_call < 0 or seccomp.seccomp_rule_add_array(
            policy, error_action | errno.EACCES, socket_call, 1, ctypes.byref(unix_family)
        ) != 0:
            raise RuntimeError('seccomp-Regel fuer Unix-Sockets konnte nicht angelegt werden')
        if io_uring_call >= 0 and seccomp.seccomp_rule_add_array(
            policy, error_action | errno.ENOSYS, io_uring_call, 0, None
        ) != 0:
            raise RuntimeError('seccomp-Regel fuer io_uring konnte nicht angelegt werden')
        if seccomp.seccomp_load(policy) != 0:
            raise RuntimeError('seccomp-Filter konnte nicht aktiviert werden')
    finally:
        seccomp.seccomp_release(policy)

def restrict(directory: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)

    def check(value):
        if value < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))
        return value

    abi = check(libc.syscall(_CREATE, None, 0, 1))
    if abi < 6:
        raise RuntimeError('Agent braucht Linux Landlock ab ABI 6')
    # Schreibende Geraete-ioctls bleiben beim Werkzeugprozess. Die
    # Signalgrenze schuetzt andere Prozesse derselben Bedienerkennung.
    rights = _WRITES | (1 << 15)
    rules = _Ruleset(rights, 0, 1 << 1)  # LANDLOCK_SCOPE_SIGNAL
    fd = check(libc.syscall(_CREATE, ctypes.byref(rules), ctypes.sizeof(rules), 0))
    try:
        writable = [(directory / name, rights) for name in ('home', 'tmp', 'rpc')]
        for path, access in [*writable, (Path('/dev/null'), _WRITE)]:
            path_fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = _PathRule(access, path_fd)
                check(libc.syscall(_ADD, fd, 1, ctypes.byref(rule), 0))
            finally:
                os.close(path_fd)
        check(libc.prctl(38, 1, 0, 0, 0))  # PR_SET_NO_NEW_PRIVS
        check(libc.syscall(_RESTRICT, fd, 0))
    finally:
        os.close(fd)


def _bubblewrap(directory: Path, executable: str, args: list[str]) -> None:
    sandbox = shutil.which('bwrap')
    if sandbox is None:
        raise RuntimeError('Kein Landlock verfügbar. Für KI-Onboarding wird bubblewrap benötigt.')
    command = [sandbox, '--ro-bind', '/', '/', '--dev', '/dev', '--proc', '/proc',
               '--unshare-user', '--unshare-pid', '--unshare-ipc', '--die-with-parent']
    for name in ('home', 'tmp', 'rpc'):
        path = str(directory / name)
        command.extend(('--bind', path, path))
    command.extend(('--', executable, *args))
    os.execv(sandbox, command)


def main() -> None:
    directory, executable, *args = sys.argv[1:]
    try:
        _block_unix_socket_creation()
        try:
            restrict(Path(directory))
        except OSError as error:
            if error.errno not in {errno.ENOSYS, errno.EOPNOTSUPP}:
                raise
            _bubblewrap(Path(directory), executable, args)
        except RuntimeError:
            _bubblewrap(Path(directory), executable, args)
        os.execv(executable, [executable, *args])
    except (OSError, RuntimeError) as error:
        raise SystemExit(f'Agent-Schreibgrenze konnte nicht eingerichtet werden: {error}') from error


if __name__ == '__main__':
    main()
