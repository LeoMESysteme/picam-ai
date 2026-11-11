"""Byte-preserving COM substitution of pinned sessions (not receiver acceptance)."""
import re

from .session_templates import (
    SessionTemplate,
    SessionTemplateError,
    active_session_template,
    load_session_catalog,
)

# Compatibility names are derived, never a second catalog or selection point.
_ACTIVE_TEMPLATE = active_session_template()
TEMPLATE_ID = _ACTIVE_TEMPLATE.spec.template_id
TEMPLATE_SHA256 = _ACTIVE_TEMPLATE.spec.source_sha256
TEMPLATE_CHANNELS = _ACTIVE_TEMPLATE.channels
ALLOWED_FIELDS = _ACTIVE_TEMPLATE.allowed_fields
# GSVmulti's rate belongs to the active session, independently of the bridge UART.
GSVMULTI_BAUD = _ACTIVE_TEMPLATE.baud_rate


def _generate(port: str, template: SessionTemplate) -> bytes:
    if not isinstance(port, str) or not re.fullmatch(r'COM[1-9][0-9]{0,2}', port) or int(port[3:]) > 256:
        raise ValueError('session_port_invalid')
    number = port[3:].encode('ascii')
    inputs = dict(template.channel_inputs)
    section = ''
    seen = set()
    result = []
    for line in template.raw.splitlines(keepends=True):
        content = line.rstrip(b'\r\n')
        ending = line[len(content):]
        if content.startswith(b'[') and content.endswith(b']'):
            section = content[1:-1].decode('ascii')
        replacement = content
        field = content.split(b' = ', 1)[0]
        if section in inputs and field == b'ComNr':
            replacement = b'ComNr = ' + number
        elif section in inputs and field == b'Name':
            replacement = b'Name = "Chan. ' + number + b'_' + str(inputs[section]).encode('ascii') + b'"'
        elif section == 'UserDevice' and field == b'ComNo':
            replacement = b'ComNo = ' + number
        else:
            result.append(line)
            continue
        key = f'{section}.{field.decode("ascii")}'
        if key in seen:
            raise SessionTemplateError('session_template_invalid: duplicate COM field')
        seen.add(key)
        result.append(replacement + ending)
    if seen != set(template.allowed_fields):
        raise SessionTemplateError('session_template_invalid: missing COM field')
    return b''.join(result)


def generate_session(port: str) -> bytes:
    """Public generator: always the selected active template, with no override."""
    return _generate(port, active_session_template())


def generate_template_session(port: str, template_id: str, *, allow_prepared: bool = False) -> bytes:
    """Developer/test entry; prepared templates need an explicit opt-in."""
    try:
        template = load_session_catalog()[template_id]
    except KeyError:
        raise SessionTemplateError('unknown_template') from None
    if template.spec.status == 'prepared' and not allow_prepared:
        raise SessionTemplateError('automatic_export_blocked: prepared template')
    return _generate(port, template)
