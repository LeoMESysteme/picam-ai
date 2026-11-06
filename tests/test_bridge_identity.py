"""Persistent Pi identity and pinned certificate consumer contracts."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from dispread.bridge.identity import DeviceIdentity, IdentityConflict, verify_certificate, verify_hello
from dispread.bridge.protocol import canonical_uart_hello


@pytest.fixture(scope="module")
def identity(tmp_path_factory):
    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp("pi") / "identity", "hardware-a")


def test_identity_survives_ip_hostname_and_process_change(tmp_path):
    first = DeviceIdentity.load_or_create(tmp_path / "identity", "hardware-a")
    other = DeviceIdentity.load_or_create(tmp_path / "identity", "hardware-a")
    assert first.pi_id == other.pi_id
    assert first.fingerprint == other.fingerprint
    assert first.certificate_pem == other.certificate_pem
    assert (tmp_path / "identity").stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in (tmp_path / "identity").iterdir())


def test_hardware_change_requires_explicit_reprovision(identity):
    before = identity.directory.joinpath("identity.json").read_bytes()
    with pytest.raises(IdentityConflict, match="hardware"):
        DeviceIdentity.load_or_create(identity.directory, "hardware-b")
    assert identity.directory.joinpath("identity.json").read_bytes() == before


def test_no_identity_in_distributable_image():
    root = Path(__file__).resolve().parents[1]
    assert not list((root / "src").rglob("identity.json"))
    assert not list((root / "src").rglob("key.pem"))


def test_uart_signature_uses_rsa3072_pss_sha256_salt32(identity):
    payload = canonical_uart_hello(identity.pi_id, "client-a", "a" * 43)
    signature = identity.sign_hello(payload)
    cert = verify_certificate(identity.certificate_pem, identity.fingerprint, identity.pi_id)
    assert isinstance(cert.public_key(), rsa.RSAPublicKey)
    assert cert.public_key().key_size == 3072
    cert.public_key().verify(signature, payload, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32), hashes.SHA256())
    verify_hello(identity.certificate_pem, payload, signature)
    with pytest.raises(InvalidSignature):
        verify_hello(identity.certificate_pem, payload + b"x", signature)


def test_certificate_checks_fingerprint_pi_and_validity(identity):
    cert = x509.load_pem_x509_certificate(identity.certificate_pem.encode())
    for fingerprint, pi_id in (("0" * 64, identity.pi_id), (identity.fingerprint, "different-pi")):
        with pytest.raises(ValueError):
            verify_certificate(identity.certificate_pem, fingerprint, pi_id)
    for now in (cert.not_valid_before_utc - timedelta(seconds=1), cert.not_valid_after_utc):
        with pytest.raises(ValueError, match="valid"):
            verify_certificate(identity.certificate_pem, identity.fingerprint, identity.pi_id, now=now)
    with pytest.raises(ValueError):
        verify_certificate(identity.certificate_pem + identity.certificate_pem, identity.fingerprint, identity.pi_id)
    with pytest.raises(ValueError):
        verify_certificate(identity.certificate_pem, identity.fingerprint, identity.pi_id, now=datetime.now())
    verify_certificate(identity.certificate_pem, identity.fingerprint, identity.pi_id, now=datetime.now(UTC))


def test_corrupt_identity_is_never_replaced(tmp_path):
    directory = tmp_path / "identity"
    directory.mkdir(mode=0o700)
    path = directory / "identity.json"
    path.write_text(json.dumps({"broken": True}))
    path.chmod(0o600)
    with pytest.raises(ValueError):
        DeviceIdentity.load_or_create(directory, "hardware-a")
    assert json.loads(path.read_text()) == {"broken": True}


def test_identity_rejects_symlink_and_public_private_state(tmp_path, identity):
    symlink = tmp_path / "link"
    symlink.symlink_to(identity.directory, target_is_directory=True)
    with pytest.raises(ValueError):
        DeviceIdentity.load_or_create(symlink, "hardware-a")
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(ValueError):
        DeviceIdentity.load_or_create(public, "hardware-a")


def test_local_cli_requires_explicit_provision_and_exports_public_profile(tmp_path, monkeypatch, capsys):
    from dispread.bridge import identity as identity_module
    from dispread.bridge.pairing import PairingStore
    from dispread.bridge.protocol import parse_profile
    from dispread.workbench.cli import main

    monkeypatch.setattr(identity_module, "local_hardware_id", lambda: "test-pi-hardware")
    directory = tmp_path / "identity"
    assert main(["bridge", "identity", "--directory", str(directory)]) == 1
    assert not (directory / "identity.json").exists()
    assert main(["bridge", "identity", "--directory", str(directory), "--provision"]) == 0
    assert "PRIVATE KEY" not in capsys.readouterr().out
    exported = tmp_path / "pi.dispread"
    assert main([
        "bridge", "export-profile", "--directory", str(directory), "--output", str(exported),
        "--name", "Pi Test", "--endpoint", "https://pi.example:8080", "--transport", "uart", "--pair",
    ]) == 0
    profile = parse_profile(exported.read_bytes())
    assert "PRIVATE KEY" not in exported.read_text()
    assert profile.endpoints == ("https://pi.example:8080",)
    assert profile.pairing_offer not in capsys.readouterr().out
    store = PairingStore(directory / "pairing")
    token = store.redeem_offer(profile.pairing_offer, "client-a", "uart")
    assert main(["bridge", "revoke", "--directory", str(directory), "client-a"]) == 0
    with pytest.raises(ValueError):
        store.authorize(token, "uart")
    assert exported.stat().st_mode & 0o777 == 0o600
    before = exported.read_bytes()
    assert main([
        "bridge", "export-profile", "--directory", str(directory), "--output", str(exported), "--name", "Pi Test",
    ]) == 1
    assert exported.read_bytes() == before


def test_pam_user_is_configurable_and_defaults_to_effective_os_user(monkeypatch):
    import os
    import pwd
    import sys
    from types import SimpleNamespace

    from dispread.workbench.auth import authenticate, pam_username

    monkeypatch.delenv("DISPREAD_PAM_USER", raising=False)
    assert pam_username() == pwd.getpwuid(os.geteuid()).pw_name
    monkeypatch.setenv("DISPREAD_PAM_USER", "operator-a")
    assert pam_username() == "operator-a"
    assert pam_username("operator-b") == "operator-b"
    observed = []

    class Handle:
        def start(self, service, username, conversation):
            observed.extend([service, username, conversation(None, [("User", 2), ("Password", 1)], None)])

        def authenticate(self):
            pass

        def acct_mgmt(self):
            pass

    monkeypatch.setitem(sys.modules, "PAM", SimpleNamespace(
        pam=Handle, PAM_PROMPT_ECHO_OFF=1, PAM_PROMPT_ECHO_ON=2, PAM_ERROR_MSG=3, PAM_TEXT_INFO=4, error=RuntimeError,
    ))
    assert authenticate("test-password", username="operator-b")
    assert observed == ["login", "operator-b", [("operator-b", 0), ("test-password", 0)]]
    from dispread.workbench.cli import parser

    args = parser().parse_args(["serve", "--pam-user", "operator-c"])
    assert args.pam_user == "operator-c"


def test_tls_context_serves_exact_identity_certificate_without_leaving_key_files(identity):
    import ssl

    before = set(identity.directory.iterdir())
    server_context = identity.tls_context()
    assert server_context.minimum_version >= ssl.TLSVersion.TLSv1_2
    client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client_context.check_hostname = False  # Identity is the pinned Pi URI SAN, not an IP/hostname.
    client_context.load_verify_locations(cadata=identity.certificate_pem)
    server_in, server_out, client_in, client_out = [ssl.MemoryBIO() for _ in range(4)]
    server = server_context.wrap_bio(server_in, server_out, server_side=True)
    client = client_context.wrap_bio(client_in, client_out, server_side=False)
    done = set()
    for _ in range(20):
        for name, endpoint in (("client", client), ("server", server)):
            if name not in done:
                try:
                    endpoint.do_handshake()
                    done.add(name)
                except ssl.SSLWantReadError:
                    pass
        server_in.write(client_out.read())
        client_in.write(server_out.read())
        if len(done) == 2:
            break
    assert len(done) == 2
    certificate = x509.load_der_x509_certificate(client.getpeercert(binary_form=True))
    assert certificate.fingerprint(hashes.SHA256()).hex() == identity.fingerprint
    assert set(identity.directory.iterdir()) == before


def test_verification_helpers_import_without_posix_fcntl(identity, monkeypatch):
    import builtins
    import importlib.util
    import sys

    from dispread.bridge import identity as identity_module

    payload = canonical_uart_hello(identity.pi_id, "windows-client", "b" * 43)
    signature = identity.sign_hello(payload)
    original_import = builtins.__import__

    def import_without_fcntl(name, *args, **kwargs):
        if name == "fcntl":
            raise ModuleNotFoundError("No module named 'fcntl'", name=name)
        return original_import(name, *args, **kwargs)

    name = "dispread.bridge._identity_without_fcntl"
    spec = importlib.util.spec_from_file_location(name, identity_module.__file__)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(builtins, "__import__", import_without_fcntl)
    spec.loader.exec_module(module)
    cert = module.verify_certificate(identity.certificate_pem, identity.fingerprint, identity.pi_id)
    assert cert.fingerprint(hashes.SHA256()).hex() == identity.fingerprint
    module.verify_hello(identity.certificate_pem, payload, signature)
