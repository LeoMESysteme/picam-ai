"""Bounded input probes; injected OS boundaries and fixed, credential-free results."""
import socket
import threading
import time
from contextlib import ExitStack, closing
from urllib.parse import urlsplit

from dispread.bridge.protocol import _token

from .session_export import GSVMULTI_BAUD
from .transports import resolve_endpoints, tls_context, verify_tls_peer
from .types import valid_port_name
from .ui.port import CheckResult

CHECK_BUDGET_S = 2.8  # margin for dispatch/return within the 3 s UI contract


def open_port(**kwargs):
    from serial import Serial
    return Serial(**kwargs)


def connect_socket(address, timeout):
    family, kind, proto, _, sockaddr = address
    stream = socket.socket(family, kind, proto)
    try:
        stream.settimeout(timeout)
        stream.connect(sockaddr)
        return stream
    except BaseException:
        stream.close()
        raise


def open_tls(stream, profile, hostname, timeout):
    stream.settimeout(timeout)
    return tls_context(profile).wrap_socket(stream, server_hostname=hostname)


class InputChecks:
    def __init__(self, ports, pairs, *, resolver=None, socket_factory=None, tls_factory=None, port_opener=None):
        self.ports, self.pairs = ports, pairs
        self.resolver = resolver or (lambda host, port: socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        self.socket_factory = socket_factory or connect_socket
        self.tls_factory = tls_factory or open_tls
        self.port_opener = port_opener or open_port
        # A hung driver/DNS call cannot accumulate unbounded probe threads.
        self._slot = threading.BoundedSemaphore(1)

    def run(self, operation):
        stage = ['Prüfung']
        done, result = threading.Event(), []
        deadline = time.monotonic() + CHECK_BUDGET_S
        if not self._slot.acquire(blocking=False):
            return CheckResult('err', 'Prüfung: Vorherige Prüfung läuft noch.', 'Prüfung später wiederholen.')

        def remaining():
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError
            return left

        def probe():
            try:
                value = operation(stage, remaining)
                remaining()  # late success is never accepted
                result.append(value)
            except Exception:
                result.append(CheckResult('err', f'{stage[0]}: Prüfung fehlgeschlagen.', 'Eingabe und Verbindung prüfen.'))
            finally:
                self._slot.release()
                done.set()
        threading.Thread(target=probe, daemon=True, name='bridge-input-check').start()
        if not done.wait(max(0, deadline - time.monotonic())):
            return CheckResult('err', f'{stage[0]}: Zeitgrenze überschritten.', 'Prüfung später wiederholen.')
        return result[0]

    def endpoint(self, text, profile):
        def probe(stage, remaining):
            stage[0] = 'Syntax'
            endpoint = text.strip()
            if '://' not in endpoint:
                endpoint = 'https://' + endpoint
            url = urlsplit(resolve_endpoints(endpoint)[0])
            if profile is None:
                return CheckResult('err', 'TLS: Profil fehlt.', 'Pi-Profil laden.')
            stage[0] = 'DNS'
            addresses = self.resolver(url.hostname, url.port or 443)
            remaining()
            stage[0] = 'TCP'
            stream = None
            for address in addresses:
                try:
                    stream = self.socket_factory(address, remaining())
                    break
                except OSError:
                    remaining()
            if stream is None:
                return CheckResult('err', 'TCP: Endpunkt nicht erreichbar.', 'Adresse und Port prüfen.')
            with closing(stream):
                remaining()
                stage[0] = 'TLS'
                with closing(self.tls_factory(stream, profile, url.hostname, remaining())) as peer:
                    verify_tls_peer(profile, peer.getpeercert(binary_form=True))
            return CheckResult('ok', 'Pi erreichbar, Zertifikat passt.')
        return self.run(probe)

    def port_pair(self, a, b):
        def probe(stage, remaining):
            stage[0] = 'Ports'
            if not valid_port_name(a) or not valid_port_name(b) or a == b:
                return CheckResult('err', 'Zwei verschiedene COM-Ports wählen.')
            present = {p.port for p in self.ports()}
            remaining()
            if not {a, b} <= present:
                return CheckResult('err', 'Port nicht vorhanden.', 'Portliste neu laden.')
            # Hold both handles concurrently to verify exclusive availability.
            with ExitStack() as stack:
                for port in (a, b):
                    handle = self.port_opener(port=port, baudrate=GSVMULTI_BAUD, exclusive=True,
                                              timeout=0, write_timeout=min(.2, remaining()))
                    stack.callback(handle.close)
                    remaining()
            try:
                known = any({p.bridge_port, p.gsv_port} == {a, b} for p in self.pairs())
            except Exception:
                known = False
            return (CheckResult('ok', 'Portpaar vorhanden und frei.') if known else
                    CheckResult('warn', 'Ports vorhanden und frei; Paarzuordnung unbestätigt.',
                                'com0com-Paarzuordnung prüfen.'))
        return self.run(probe)

    def adapter(self, port, baud):
        def probe(stage, remaining):
            stage[0] = 'Adapter'
            choices = self.ports()
            remaining()
            if not valid_port_name(port) or not any(p.port == port and p.kind == 'usb_serial' for p in choices):
                return CheckResult('err', 'USB-Seriell-Adapter nicht vorhanden.', 'Adapter anschließen und neu suchen.')
            with closing(self.port_opener(port=port, baudrate=baud, exclusive=True,
                                         timeout=0, write_timeout=min(.2, remaining()))):
                remaining()
            return CheckResult('ok', 'Adapter vorhanden und Port frei.')
        return self.run(probe)

    @staticmethod
    def pairing_code(code):
        try:
            _token(code)
            return CheckResult('ok', 'Codeformat gültig; Kopplung noch nicht geprüft.')
        except (ValueError, TypeError):
            return CheckResult('err', 'Codeformat ungültig.', 'Code vollständig aus der Werkbank übernehmen.')
