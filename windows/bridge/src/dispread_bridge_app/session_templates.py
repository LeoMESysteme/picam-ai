"""Recognize reviewed archive originals without claiming a session format.

This is an evidence catalog, not a UCF parser or generator. No application/file
version or editable field has yet been established by a controlled roundtrip.
Only code-reviewed catalog changes can add evidence; external manifests cannot
promote a file into a supported session template.
"""
import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class SessionTemplateError(ValueError):
    """Unsupported evidence or a blocked automatic session export."""


@dataclass(frozen=True)
class TemplateEvidence:
    template_id: str
    gsv_version: str | None
    source_sha256: str
    allowed_fields: tuple[str, ...]
    roundtrip_verified: bool

    def require_automatic_export(self) -> None:
        """No exporter is supported by the current archive-only evidence."""
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
        # Both reviewed originals are shorter; an unknown large file is not parsed.
        digest = sha256(source.read(266)).hexdigest()
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
