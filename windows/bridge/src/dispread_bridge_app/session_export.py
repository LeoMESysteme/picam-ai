"""Byte-preserving export of the single approved COM8 source (not receiver acceptance)."""
import re
from hashlib import sha256
from importlib.resources import files

TEMPLATE_ID = 'bruecke-session-com8-20261106'
TEMPLATE_SHA256 = '6e553a1e34194266a9a753b621910c144fab95fd16a5219395e1d1d8c8085992'
ALLOWED_FIELDS = ('ch1.ComNr', 'ch1.Name', 'UserDevice.ComNo')


def _template() -> bytes:
    raw = files('dispread_bridge_app').joinpath('templates/Session-COM8.ucf').read_bytes()
    if sha256(raw).hexdigest() != TEMPLATE_SHA256:
        raise ValueError('session_template_invalid')
    return raw


# GSVmulti's rate belongs to the reviewed session, independently of the bridge UART.
GSVMULTI_BAUD = int(re.search(rb'^BaudRate = ([0-9]+)\r$', _template(), re.MULTILINE)[1])


def generate_session(port: str) -> bytes:
    if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]{0,2}', port) or int(port[3:]) > 256:
        raise ValueError('session_port_invalid')
    number = port[3:].encode('ascii')
    raw = _template()
    # The source hash fixes both the sections and the uniqueness of these lines.
    for before, after in ((b'ComNr = 8\r\n', b'ComNr = ' + number + b'\r\n'),
                          (b'Name = "Chan. 8_1"\r\n', b'Name = "Chan. ' + number + b'_1"\r\n'),
                          (b'ComNo = 8\r\n', b'ComNo = ' + number + b'\r\n')):
        raw = raw.replace(before, after, 1)
    return raw
