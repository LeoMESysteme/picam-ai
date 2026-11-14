"""Portable protected-store tests; native DPAPI gate is separate."""
import sys

import pytest
from dispread_bridge_app.credentials import CredentialError, CredentialStore, WindowsDPAPI


class UserProtector:
    def __init__(self, user=b'user-a:'):
        self.user = user

    def secure_path(self, path):
        pass  # Portable fake does not prove native Windows ACLs.

    def protect(self, raw):
        return self.user + bytes(x ^ 127 for x in raw)

    def unprotect(self, raw):
        if not raw.startswith(self.user):
            raise OSError('secret-exception')
        return bytes(x ^ 127 for x in raw[len(self.user):])


def test_atomic_protected_store_scopes_transport_and_removes(tmp_path):
    store = CredentialStore(tmp_path / 'secrets', protector=UserProtector())
    token = 'a' * 43
    store.save('pi-a', 'network', token)
    assert store.load('pi-a', 'network') == token
    assert store.load('pi-a', 'uart') is None
    assert token.encode() not in b''.join(p.read_bytes() for p in (tmp_path / 'secrets').iterdir())
    if sys.platform != 'win32':
        assert all(p.stat().st_mode & 0o077 == 0 for p in (tmp_path / 'secrets').iterdir())
    store.remove('pi-a', 'network')
    assert store.load('pi-a', 'network') is None


def test_other_windows_user_cannot_reuse_credentials(tmp_path):
    path = tmp_path / 'secrets'
    CredentialStore(path, protector=UserProtector()).save('pi-a', 'uart', 'a' * 43)
    other = CredentialStore(path, protector=UserProtector(b'user-b:'))
    with pytest.raises(CredentialError) as error:
        other.load('pi-a', 'uart')
    assert str(error.value) == 'credential_unavailable'
    assert len(list(path.iterdir())) == 1


@pytest.mark.skipif(sys.platform != 'win32', reason='requires real Windows user-bound DPAPI')
def test_native_windows_dpapi_roundtrip():
    protector = WindowsDPAPI()
    ciphertext = protector.protect(b'secret')
    assert b'secret' not in ciphertext
    assert protector.unprotect(ciphertext) == b'secret'


def test_failed_atomic_replace_preserves_previous_ciphertext(tmp_path, monkeypatch):
    from dispread_bridge_app import credentials
    store = CredentialStore(tmp_path / 'secrets', protector=UserProtector())
    store.save('pi-a', 'network', 'a' * 43)
    def full_disk(*args):
        raise OSError('token=' + 'b' * 43)
    monkeypatch.setattr(credentials.os, 'replace', full_disk)
    with pytest.raises(CredentialError, match='credential_unavailable'):
        store.save('pi-a', 'network', 'b' * 43)
    assert store.load('pi-a', 'network') == 'a' * 43
    assert len(list((tmp_path / 'secrets').iterdir())) == 1


def test_protected_blob_cannot_be_moved_to_another_pi_or_transport(tmp_path):
    store = CredentialStore(tmp_path / 'secrets', protector=UserProtector())
    store.save('pi-a', 'network', 'a' * 43)
    source = next((tmp_path / 'secrets').iterdir())
    store.save('pi-b', 'uart', 'b' * 43)
    target = next(p for p in (tmp_path / 'secrets').iterdir() if p != source)
    target.write_bytes(source.read_bytes())
    with pytest.raises(CredentialError):
        store.load('pi-b', 'uart')


def test_default_protector_never_falls_back_to_plaintext_on_linux(tmp_path):
    if sys.platform == 'win32':
        pytest.skip('non-Windows refusal test')
    with pytest.raises(CredentialError):
        CredentialStore(tmp_path / 'secrets').save('pi-a', 'network', 'a' * 43)
    assert not (tmp_path / 'secrets').exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='requires real Windows DPAPI and SID-only file DACLs')
def test_native_windows_protected_store_roundtrip(tmp_path):
    store = CredentialStore(tmp_path / 'native-credentials')
    store.save('pi-native', 'network', 'a' * 43, expected_pin='1' * 64)
    assert store.load('pi-native', 'network', expected_pin='1' * 64) == 'a' * 43
    paths = list((tmp_path / 'native-credentials').iterdir())
    assert len(paths) == 1
    assert b'a' * 43 not in paths[0].read_bytes()
    store.remove('pi-native', 'network')
    assert store.load('pi-native', 'network') is None


def test_bound_credential_matches_only_its_certificate_pin(tmp_path):
    store = CredentialStore(tmp_path / 'secrets', protector=UserProtector())
    store.save('pi-a', 'network', 'a' * 43, expected_pin='1' * 64)
    assert store.load('pi-a', 'network', expected_pin='1' * 64) == 'a' * 43
    assert store.load('pi-a', 'network', expected_pin='2' * 64) is None
    assert store.load('pi-a', 'uart', expected_pin='1' * 64) is None
    # The unchanged explicit compatibility path remains available to old callers.
    assert store.load('pi-a', 'network') == 'a' * 43


def test_legacy_unbound_credential_requires_fresh_pairing_on_bound_path(tmp_path):
    store = CredentialStore(tmp_path / 'secrets', protector=UserProtector())
    store.save('pi-a', 'network', 'a' * 43)
    before = next((tmp_path / 'secrets').iterdir()).read_bytes()
    assert store.load('pi-a', 'network', expected_pin='1' * 64) is None
    assert next((tmp_path / 'secrets').iterdir()).read_bytes() == before
    store.save('pi-a', 'network', 'b' * 43, expected_pin='1' * 64)
    assert store.load('pi-a', 'network', expected_pin='1' * 64) == 'b' * 43


@pytest.mark.parametrize('pin', ['', 'a' * 63, 'A' * 64, 'not-a-pin'])
def test_invalid_expected_pin_cannot_select_or_replace_credential(tmp_path, pin):
    store = CredentialStore(tmp_path / 'secrets', protector=UserProtector())
    store.save('pi-a', 'network', 'a' * 43)
    with pytest.raises(CredentialError):
        store.load('pi-a', 'network', expected_pin=pin)
    with pytest.raises(CredentialError):
        store.save('pi-a', 'network', 'b' * 43, expected_pin=pin)
    assert store.load('pi-a', 'network') == 'a' * 43
