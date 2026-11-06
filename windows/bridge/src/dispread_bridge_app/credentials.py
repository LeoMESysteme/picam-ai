"""Atomic user-bound protected credentials. No plaintext or non-Windows fallback."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import sys
import tempfile
import threading
from pathlib import Path

from dispread.bridge.protocol import _identifier, _token, _transport


class CredentialError(OSError):
    pass


def _pin(value):
    if value is not None and (not isinstance(value, str) or re.fullmatch(r'[0-9a-f]{64}', value) is None):
        raise CredentialError('credential_unavailable')


class WindowsDPAPI:
    """Lazy ctypes CryptProtectData without CRYPTPROTECT_LOCAL_MACHINE."""

    def __init__(self):
        if sys.platform != 'win32':
            raise CredentialError('windows_protection_required')
        import ctypes
        from ctypes import wintypes as w
        self.c, self.w = ctypes, w
        self.crypt = ctypes.WinDLL('crypt32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.advapi = ctypes.WinDLL('advapi32', use_last_error=True)
        class Blob(ctypes.Structure):
            _fields_ = [('cbData', w.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
        self.Blob = Blob
        p = ctypes.POINTER(Blob)
        self.crypt.CryptProtectData.argtypes = [p, w.LPCWSTR, p, w.LPVOID, w.LPVOID, w.DWORD, p]
        self.crypt.CryptUnprotectData.argtypes = [p, w.LPVOID, p, w.LPVOID, w.LPVOID, w.DWORD, p]
        self.crypt.CryptProtectData.restype = self.crypt.CryptUnprotectData.restype = w.BOOL
        self.kernel.LocalFree.argtypes, self.kernel.LocalFree.restype = [w.HLOCAL], w.HLOCAL

    def _convert(self, raw, protect):
        c = self.c
        buffer = (c.c_ubyte * len(raw)).from_buffer_copy(raw)
        source, result = self.Blob(len(raw), buffer), self.Blob()
        function = self.crypt.CryptProtectData if protect else self.crypt.CryptUnprotectData
        # UI_FORBIDDEN=1; user scope is the default (LOCAL_MACHINE is absent).
        if not function(c.byref(source), None, None, None, None, 1, c.byref(result)):
            raise CredentialError('credential_unavailable')
        try:
            return c.string_at(result.pbData, result.cbData)
        finally:
            self.kernel.LocalFree(c.cast(result.pbData, self.w.HLOCAL))

    def protect(self, raw: bytes) -> bytes:
        return self._convert(raw, True)

    def unprotect(self, raw: bytes) -> bytes:
        return self._convert(raw, False)

    def secure_path(self, path):
        """Protected filesystem DACL granting only the actual token user's SID."""
        c, w, a, k = self.c, self.w, self.advapi, self.kernel
        signatures = [
            (k, 'GetCurrentProcess', [], w.HANDLE),
            (k, 'CloseHandle', [w.HANDLE], w.BOOL),
            (a, 'OpenProcessToken', [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)], w.BOOL),
            (a, 'GetTokenInformation', [w.HANDLE, c.c_int, w.LPVOID, w.DWORD, c.POINTER(w.DWORD)], w.BOOL),
            (a, 'ConvertSidToStringSidW', [w.LPVOID, c.POINTER(w.LPWSTR)], w.BOOL),
            (a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW',
             [w.LPCWSTR, w.DWORD, c.POINTER(w.LPVOID), c.POINTER(w.DWORD)], w.BOOL),
            (a, 'SetFileSecurityW', [w.LPCWSTR, w.DWORD, w.LPVOID], w.BOOL),
        ]
        for dll, name, args, result in signatures:
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result
        token, size, text, descriptor = w.HANDLE(), w.DWORD(), w.LPWSTR(), w.LPVOID()
        try:
            if not a.OpenProcessToken(k.GetCurrentProcess(), 8, c.byref(token)):
                raise CredentialError('credential_unavailable')
            a.GetTokenInformation(token, 1, None, 0, c.byref(size))
            if not 0 < size.value < 65536:
                raise CredentialError('credential_unavailable')
            buffer = c.create_string_buffer(size.value)
            if not a.GetTokenInformation(token, 1, buffer, size, c.byref(size)):
                raise CredentialError('credential_unavailable')
            sid = c.cast(buffer, c.POINTER(w.LPVOID))[0]
            if not a.ConvertSidToStringSidW(sid, c.byref(text)):
                raise CredentialError('credential_unavailable')
            if not a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                    f'D:P(A;OICI;FA;;;{text.value})', 1, c.byref(descriptor), None):
                raise CredentialError('credential_unavailable')
            if not a.SetFileSecurityW(str(path), 0x80000004, descriptor):
                raise CredentialError('credential_unavailable')
        finally:
            if descriptor:
                k.LocalFree(descriptor)
            if text:
                k.LocalFree(c.cast(text, w.HLOCAL))
            if token:
                k.CloseHandle(token)


class CredentialStore:
    def __init__(self, directory, *, protector=None):
        self.directory = Path(directory)
        self._protector = protector
        self._lock = threading.Lock()

    def _ready(self):
        if self._protector is None:
            self._protector = WindowsDPAPI()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or self.directory.is_symlink():
            raise CredentialError('credential_unavailable')
        if sys.platform == 'win32':
            self._protector.secure_path(self.directory)
        elif info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise CredentialError('credential_unavailable')

    def _path(self, pi_id, transport):
        _identifier(pi_id)
        _transport(transport)
        return self.directory / (hashlib.sha256(f'{pi_id}\0{transport}'.encode()).hexdigest() + '.dpapi')

    def save(self, pi_id, transport, token, *, expected_pin=None):
        _pin(expected_pin)
        _token(token)
        path = self._path(pi_id, transport)
        with self._lock:
            temporary = None
            try:
                self._ready()
                value = dict(pi_id=pi_id, transport=transport, token=token)
                if expected_pin is not None:
                    value['certificate_sha256'] = expected_pin
                raw = json.dumps(value).encode()
                encrypted = self._protector.protect(raw)
                fd, temporary = tempfile.mkstemp(prefix='.credential-', dir=self.directory)
                with os.fdopen(fd, 'wb') as stream:
                    if sys.platform == 'win32':
                        self._protector.secure_path(temporary)
                    stream.write(encrypted)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
                if sys.platform != 'win32':
                    directory_fd = os.open(self.directory, os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
            except Exception:
                raise CredentialError('credential_unavailable') from None
            finally:
                if temporary:
                    Path(temporary).unlink(missing_ok=True)

    def load(self, pi_id, transport, *, expected_pin=None):
        _pin(expected_pin)
        path = self._path(pi_id, transport)
        with self._lock:
            try:
                self._ready()
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    return None
                if not stat.S_ISREG(info.st_mode) or path.is_symlink() or info.st_size > 16384:
                    raise CredentialError('credential_unavailable')
                if sys.platform != 'win32' and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
                    raise CredentialError('credential_unavailable')
                value = json.loads(self._protector.unprotect(path.read_bytes()))
                fields = {'pi_id', 'transport', 'token'}
                if (set(value) not in (fields, fields | {'certificate_sha256'})
                        or (value['pi_id'], value['transport']) != (pi_id, transport)):
                    raise CredentialError('credential_unavailable')
                _token(value['token'])
                stored_pin = value.get('certificate_sha256')
                if 'certificate_sha256' in value and stored_pin is None:
                    raise CredentialError('credential_unavailable')
                _pin(stored_pin)
                if expected_pin is not None and (stored_pin is None or not hmac.compare_digest(stored_pin, expected_pin)):
                    return None  # Legacy/changed identity needs a fresh scoped pairing.
                return value['token']
            except Exception:
                raise CredentialError('credential_unavailable') from None

    def remove(self, pi_id, transport):
        with self._lock:
            try:
                self._ready()
                self._path(pi_id, transport).unlink(missing_ok=True)
            except Exception:
                raise CredentialError('credential_unavailable') from None
