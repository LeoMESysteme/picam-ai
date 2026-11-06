"""Per-user Windows instance guard with a GUI-independent activation event.

The native adapter is imported lazily and uses SID-only DACLs on Global kernel
objects. Holding a mutex HANDLE (without thread ownership) is the process-life
claim; Windows closes it on process death. An auto-reset event carries only an
activation request, never a window handle, profile, credentials or commands.
"""
from __future__ import annotations

import math
import re
import sys
import threading


class SingleInstance:
    def __init__(self, *, native=None):
        self._native = native
        self._mutex = self._activation = None
        self._lock = threading.RLock()

    def activate_or_acquire(self) -> bool:
        with self._lock:
            if self._mutex is not None:
                return True
            if self._native is None:
                self._native = _WindowsKernel()
            native = self._native
            sid = native.user_sid()
            if re.fullmatch(r'S-1-(?:[0-9]+-)*[0-9]+', sid) is None:
                raise OSError('invalid Windows user SID')
            name = f'Global\\ME-Systeme.DispReadBridge.v1.{sid}'
            activation = native.event(name + '.activate', sid)
            mutex = None
            try:
                mutex, exists = native.mutex(name + '.instance', sid)
                if exists:
                    native.signal(activation)
                    return False
                self._mutex, self._activation = mutex, activation
                mutex = activation = None  # ownership transferred
                return True
            finally:
                if mutex is not None:
                    native.close(mutex)
                if activation is not None:
                    native.close(activation)

    def wait_for_activation(self, timeout_s=0) -> bool:
        """GUI/event dispatcher polls or waits; this never manipulates windows."""
        if not math.isfinite(timeout_s) or not 0 <= timeout_s <= 60:
            raise ValueError('activation timeout must be 0..60 seconds')
        with self._lock:
            if self._activation is None:
                raise RuntimeError('instance not acquired')
            return self._native.wait(self._activation, int(timeout_s * 1000))

    def close(self):
        with self._lock:
            for attr in ('_activation', '_mutex'):
                handle = getattr(self, attr)
                if handle is not None:
                    self._native.close(handle)
                    setattr(self, attr, None)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class _WindowsKernel:
    """ctypes signatures follow the linked Win32 references in the W2 report."""

    def __init__(self):
        if sys.platform != 'win32':
            raise OSError('single instance native adapter requires Windows')
        import ctypes
        from ctypes import wintypes as w
        self.c, self.w = ctypes, w
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.a = ctypes.WinDLL('advapi32', use_last_error=True)

        class SecurityAttributes(ctypes.Structure):
            _fields_ = [('nLength', w.DWORD), ('lpSecurityDescriptor', w.LPVOID),
                        ('bInheritHandle', w.BOOL)]
        self.SecurityAttributes = SecurityAttributes
        signatures = [
            (self.k, 'GetCurrentProcess', [], w.HANDLE),
            (self.k, 'CloseHandle', [w.HANDLE], w.BOOL),
            (self.k, 'LocalFree', [w.HLOCAL], w.HLOCAL),
            (self.k, 'CreateMutexW', [ctypes.POINTER(SecurityAttributes), w.BOOL, w.LPCWSTR], w.HANDLE),
            (self.k, 'CreateEventW', [ctypes.POINTER(SecurityAttributes), w.BOOL, w.BOOL, w.LPCWSTR], w.HANDLE),
            (self.k, 'SetEvent', [w.HANDLE], w.BOOL),
            (self.k, 'WaitForSingleObject', [w.HANDLE, w.DWORD], w.DWORD),
            (self.a, 'OpenProcessToken', [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL),
            (self.a, 'GetTokenInformation', [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD,
                                           ctypes.POINTER(w.DWORD)], w.BOOL),
            (self.a, 'ConvertSidToStringSidW', [w.LPVOID, ctypes.POINTER(w.LPWSTR)], w.BOOL),
            (self.a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW',
             [w.LPCWSTR, w.DWORD, ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.DWORD)], w.BOOL),
        ]
        for dll, name, args, result in signatures:
            function = getattr(dll, name)
            function.argtypes, function.restype = args, result

    def _error(self):
        return self.c.WinError(self.c.get_last_error())

    def user_sid(self):
        c, w = self.c, self.w
        token = w.HANDLE()
        if not self.a.OpenProcessToken(self.k.GetCurrentProcess(), 0x0008, c.byref(token)):
            raise self._error()
        try:
            size = w.DWORD()
            # TokenUser=1. First call obtains the required buffer length.
            if self.a.GetTokenInformation(token, 1, None, 0, c.byref(size)) or c.get_last_error() != 122:
                raise self._error()
            buffer = c.create_string_buffer(size.value)
            if not self.a.GetTokenInformation(token, 1, buffer, size, c.byref(size)):
                raise self._error()
            # TOKEN_USER starts with SID_AND_ATTRIBUTES; its first field is PSID.
            sid_pointer = c.cast(buffer, c.POINTER(w.LPVOID))[0]
            sid_text = w.LPWSTR()
            if not self.a.ConvertSidToStringSidW(sid_pointer, c.byref(sid_text)):
                raise self._error()
            try:
                return sid_text.value
            finally:
                self.k.LocalFree(c.cast(sid_text, w.HLOCAL))
        finally:
            self.close(token)

    def _create(self, name, sid, *, event):
        c, w = self.c, self.w
        descriptor = w.LPVOID()
        # Protected DACL: only this actual token user receives generic-all access.
        if not self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                f'D:P(A;;GA;;;{sid})', 1, c.byref(descriptor), None):
            raise self._error()
        try:
            attributes = self.SecurityAttributes(c.sizeof(self.SecurityAttributes), descriptor, False)
            c.set_last_error(0)
            handle = (self.k.CreateEventW(c.byref(attributes), False, False, name) if event
                      else self.k.CreateMutexW(c.byref(attributes), False, name))
            error = c.get_last_error()
            if not handle:
                raise c.WinError(error)
            return handle, error == 183  # ERROR_ALREADY_EXISTS
        finally:
            self.k.LocalFree(descriptor)

    def event(self, name, sid):
        return self._create(name, sid, event=True)[0]

    def mutex(self, name, sid):
        return self._create(name, sid, event=False)

    def signal(self, handle):
        if not self.k.SetEvent(handle):
            raise self._error()

    def wait(self, handle, timeout_ms):
        result = self.k.WaitForSingleObject(handle, timeout_ms)
        if result == 0:
            return True
        if result == 258:  # WAIT_TIMEOUT
            return False
        raise self._error()

    def close(self, handle):
        if not self.k.CloseHandle(handle):
            raise self._error()
