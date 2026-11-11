"""Pinned session catalog and archive provenance, without receiver acceptance.

Only the selected active session permits automatic export. Prepared sessions
require explicit developer opt-in; archive originals remain evidence only.
Only code-reviewed catalog changes can add evidence; external manifests cannot
promote a file into a supported session template.
"""
import configparser
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from pathlib import Path
from typing import Literal


class SessionTemplateError(ValueError):
    """Unsupported evidence or a blocked automatic session export."""


@dataclass(frozen=True)
class SessionTemplateSpec:
    template_id: str
    package_file: str
    source_sha256: str
    source_path: str
    telegram_format: str
    status: Literal['active', 'prepared']


# The only selection point. A prepared format must be deliberately activated
# in reviewed code once the sender supports it; no UI/profile setting selects it.
ACTIVE_SESSION_TEMPLATE = 'bruecke-session-com8-20261106'
SESSION_TEMPLATES = (
    SessionTemplateSpec(
        template_id='bruecke-session-com8-20261106',
        package_file='templates/Session-COM8.ucf',
        source_sha256='6e553a1e34194266a9a753b621910c144fab95fd16a5219395e1d1d8c8085992',
        source_path='docs/quellen/bruecke-testlauf-2026-11-06/Session-COM8.ucf',
        telegram_format='single_value', status='active',
    ),
    SessionTemplateSpec(
        template_id='bruecke-session-4ch-hidden-20261111',
        package_file='templates/versuch2b-session-hidden.ucf',
        source_sha256='eabf06629857b455825f04d85b7c40155f9f9037f75722af4c36f2f801f2686c',
        source_path='docs/quellen/gsvmulti-versuche-2026-11-11/versuch2b-session-hidden.ucf',
        telegram_format='gsvmulti_userdefined_4ch_v1', status='prepared',
    ),
)


@dataclass(frozen=True)
class SessionTemplate:
    spec: SessionTemplateSpec
    raw: bytes
    channels: int
    hidden_channels: int
    baud_rate: int
    # (section, Input): Input is the receiver's channel index, not the chN suffix.
    channel_inputs: tuple[tuple[str, int], ...]

    @property
    def record_hidden_required(self) -> bool:
        return self.hidden_channels > 0

    @property
    def allowed_fields(self) -> tuple[str, ...]:
        return tuple(f'{section}.{field}' for section, _ in self.channel_inputs
                     for field in ('ComNr', 'Name')) + ('UserDevice.ComNo',)


def load_session_catalog() -> dict[str, SessionTemplate]:
    """Validate all package hashes and derive receiver settings from their bytes."""
    catalog = {}
    rates = set()
    for spec in SESSION_TEMPLATES:
        raw = files('dispread_bridge_app').joinpath(spec.package_file).read_bytes()
        if sha256(raw).hexdigest() != spec.source_sha256:
            raise SessionTemplateError(f'source_hash_mismatch: {spec.template_id}')
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(raw.decode('cp1252'))
            sections = [section for section in parser.sections() if re.fullmatch(r'ch[1-9][0-9]*', section)]
            channels = parser.getint('UserDevice', 'NumChan')
            inputs = tuple((section, parser.getint(section, 'Input')) for section in sections)
            hidden = sum(parser.getboolean(section, 'IsHidden') for section in sections)
            channel_rates = {parser.getint(section, 'BaudRate') for section in sections}
            if (channels < 1 or len(sections) != channels or
                    len({index for _, index in inputs}) != channels or
                    any(index < 1 for _, index in inputs)):
                raise ValueError('invalid channel definitions')
        except (configparser.Error, ValueError) as error:
            raise SessionTemplateError(f'session_template_invalid: {spec.template_id}') from error
        if len(channel_rates) != 1 or min(channel_rates) < 1:
            raise SessionTemplateError(f'baud_rate_mismatch: {spec.template_id}')
        rate = channel_rates.pop()
        rates.add(rate)
        if spec.template_id in catalog or spec.status not in ('active', 'prepared'):
            raise SessionTemplateError('session_catalog_invalid')
        catalog[spec.template_id] = SessionTemplate(spec, raw, channels, hidden, rate, inputs)
    if len(rates) != 1:
        raise SessionTemplateError('baud_rate_mismatch: session catalog')
    if ACTIVE_SESSION_TEMPLATE not in catalog or catalog[ACTIVE_SESSION_TEMPLATE].spec.status != 'active':
        raise SessionTemplateError('automatic_export_blocked: selected template is not active')
    return catalog


def active_session_template() -> SessionTemplate:
    return load_session_catalog()[ACTIVE_SESSION_TEMPLATE]


@dataclass(frozen=True)
class TemplateEvidence:
    template_id: str
    gsv_version: str | None
    source_sha256: str
    allowed_fields: tuple[str, ...]
    roundtrip_verified: bool

    def require_automatic_export(self) -> None:
        """Only the pinned active source permits its port-only generator."""
        active = active_session_template()
        if (self.template_id == active.spec.template_id and self.source_sha256 == active.spec.source_sha256
                and self.allowed_fields == active.allowed_fields and not self.roundtrip_verified):
            return
        raise SessionTemplateError(
            'automatic_export_blocked: exact GSVmulti/file versions and a '
            'controlled reopen/receiver check for port, unit, scale, rate, '
            'prefix and number filter are missing'
        )


# Pin provenance in reviewed code, never in an imported Pi profile/manifest.
_EXPECTED_MANIFEST = {
    'schema_version': 1,
    'source_archive': 'docs/quellen/gsvmulti-validation-2026-11-04.zip',
    'source_archive_sha256':
        'e7e6742acee9203ed0f1da251006e9c9bb9a8eb4c10f2ce06992512daf1ae5e3',
    'templates': [
        {
            'template_id': 'uart-direct-demo-20261104-11',
            'file': 'uart-demo-11.ucf',
            'archive_member': 'var/diagnostics/gsvmulti/uart-direct-demo-20261104-11/'
                              'receiver/svmulti-uart-mvv-test.ucf',
            'source_sha256':
                '0880ab1c2406e4761624de904407060579d85ca8126ce411bdf31455734f2b4e',
            'gsv_version': None,
            'allowed_fields': [],
            'roundtrip_verified': False,
        },
        {
            'template_id': 'uart-direct-demo-20261104-14',
            'file': 'uart-demo-14.ucf',
            'archive_member': 'var/diagnostics/gsvmulti/uart-direct-demo-20261104-14/'
                              'receiver-profile.ucf',
            'source_sha256':
                'f7ee09ad481d6d38612d54fda049f0d2d9be7d4d9d4f6a9e3b50a9dbb44c844c',
            'gsv_version': None,
            'allowed_fields': [],
            'roundtrip_verified': False,
        },
    ],
    'recordings': [
        {
            'file': 'uart-demo-11-receiver.txt',
            'archive_member': 'var/diagnostics/gsvmulti/uart-direct-demo-20261104-11/'
                              'receiver/04_11_26-14_00_02.txt',
            'source_sha256':
                '24617dc71f18f14ca4d261f00a00d66ce197f21a622ce44e4ebf95c07db3f7ba',
        },
    ],
}


def inspect_template(path: Path) -> TemplateEvidence:
    """Return provenance for exact known bytes; do not infer fields or versions."""
    with path.open('rb') as source:
        # Bound unknown input; hash the complete reviewed sources.
        digest = sha256(source.read(65537)).hexdigest()
    for template in load_session_catalog().values():
        if digest == template.spec.source_sha256:
            return TemplateEvidence(template.spec.template_id, None, digest, template.allowed_fields, False)
    for entry in _EXPECTED_MANIFEST['templates']:
        if digest == entry['source_sha256']:
            return TemplateEvidence(entry['template_id'], None, digest, (), False)
    raise SessionTemplateError('unknown_template: no reviewed original matches these bytes')


def validate_manifest(path: Path) -> tuple[TemplateEvidence, ...]:
    """Check the reviewed archive catalog and exact local fixture bytes.

    A caller-supplied manifest is only checked, never treated as authority for
    versions, roundtrips, allowed fields, paths or hashes. This function does not
    load a GSVmulti session or open any port.
    """
    try:
        manifest = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError) as error:
        raise SessionTemplateError('unsupported_manifest: invalid JSON') from error
    # Canonical JSON comparison also distinguishes false/0 and schema 1/1.0.
    if json.dumps(manifest, sort_keys=True) != json.dumps(_EXPECTED_MANIFEST, sort_keys=True):
        raise SessionTemplateError('unsupported_manifest: catalog requires code review')
    entries = _EXPECTED_MANIFEST['templates'] + _EXPECTED_MANIFEST['recordings']
    for entry in entries:
        source = path.parent / entry['file']
        if source.is_symlink():
            raise SessionTemplateError('unsupported_manifest: fixture must be a local regular file')
        if sha256(source.read_bytes()).hexdigest() != entry['source_sha256']:
            raise SessionTemplateError('source_hash_mismatch: fixture differs from archive original')
    return tuple(inspect_template(path.parent / entry['file'])
                 for entry in _EXPECTED_MANIFEST['templates'])
