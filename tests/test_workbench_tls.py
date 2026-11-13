"""TLS-CLI verlangt einen expliziten Host und zeigt vorhandene Zertifikate lesend."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from dispread.workbench import cli


@pytest.mark.parametrize('extra', [[], ['--host', ''], ['--host', 'https://pi.example/live']])
def test_init_tls_requires_valid_explicit_host_before_any_write(tmp_path, capsys, extra):
    directory = tmp_path / 'tls'
    assert cli.main(['init-tls', '--directory', str(directory), *extra]) != 0
    assert not directory.exists()
    if not extra or not extra[-1]:
        assert 'Adresse angeben, unter der Windows den Pi erreicht' in capsys.readouterr().out


@pytest.fixture
def certificate(tmp_path):
    import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'test')])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(1)
            .not_valid_before(datetime(2026, 1, 1, tzinfo=UTC))
            .not_valid_after(datetime(2027, 1, 1, tzinfo=UTC))
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName('pi.example'), x509.IPAddress(ipaddress.ip_address('192.0.2.5')),
                x509.IPAddress(ipaddress.ip_address('2001:db8::5'))]), critical=False)
            .sign(key, hashes.SHA256()))
    path = tmp_path / 'tls/cert.pem'
    path.parent.mkdir()
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return path


def test_show_certificate_reports_sans_and_utc_expiry_without_private_key(certificate, capsys):
    before = certificate.read_bytes(), certificate.stat().st_mtime_ns
    assert cli.main(['init-tls', '--directory', str(certificate.parent), '--show']) == 0
    info = json.loads(capsys.readouterr().out)
    assert info['san'] == ['DNS:pi.example', 'IP:192.0.2.5', 'IP:2001:db8::5']
    assert info['not_after_utc'] == '2027-01-01T00:00:00+00:00'
    assert info['time_basis'] == 'UTC'
    assert before == (certificate.read_bytes(), certificate.stat().st_mtime_ns)
    assert list(certificate.parent.iterdir()) == [certificate]


def test_show_missing_or_invalid_certificate_fails_without_creating(tmp_path, capsys):
    directory = tmp_path / 'tls'
    assert cli.main(['init-tls', '--directory', str(directory), '--show']) != 0
    assert not directory.exists()
    directory.mkdir()
    (directory / 'cert.pem').write_text('invalid certificate')
    assert cli.main(['init-tls', '--directory', str(directory), '--show']) != 0


def test_init_tls_preserves_existing_certificate(certificate):
    before = certificate.read_bytes()
    assert cli.main(['init-tls', '--directory', str(certificate.parent), '--host', 'pi.example']) != 0
    assert certificate.read_bytes() == before
    assert not (certificate.parent / 'key.pem').exists()


def test_generated_certificate_contains_explicit_host_and_local_sans(tmp_path, capsys):
    directory = tmp_path / 'tls'
    assert cli.main(['init-tls', '--directory', str(directory), '--host', 'pi.example']) == 0
    capsys.readouterr()
    assert cli.main(['init-tls', '--directory', str(directory), '--show']) == 0
    info = json.loads(capsys.readouterr().out)
    assert info['san'] == ['DNS:pi.example', 'DNS:localhost', 'IP:127.0.0.1']
    expiry = datetime.fromisoformat(info['not_after_utc'])
    assert timedelta(days=364) < expiry - datetime.now(UTC) <= timedelta(days=365)
    assert (directory / 'key.pem').stat().st_mode & 0o777 == 0o600


def test_live_status_uses_selected_socket(monkeypatch, capsys):
    calls = []

    async def request(op, args=None, socket_path=None):
        calls.append((op, args, socket_path))
        return {'state': 'idle'}

    monkeypatch.setattr(cli, 'request', request)
    assert cli.main(['live', 'status', '--socket', '/tmp/example/control.sock']) == 0
    assert calls == [('live.status', {}, '/tmp/example/control.sock')]
    assert json.loads(capsys.readouterr().out) == {'state': 'idle'}
