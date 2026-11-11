"""Only reviewed COM lines may change; every other byte is evidence."""

import configparser
from hashlib import sha256
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "docs/quellen/bruecke-testlauf-2026-11-06/Session-COM8.ucf"


def test_com8_is_the_exact_reviewed_original():
    from dispread_bridge_app.session_export import GSVMULTI_BAUD, generate_session

    raw = generate_session("COM8")
    assert raw == SOURCE.read_bytes()
    assert sha256(raw).hexdigest() == "6e553a1e34194266a9a753b621910c144fab95fd16a5219395e1d1d8c8085992"
    assert GSVMULTI_BAUD == 115200


def test_com4_preserves_bytes_and_matches_independent_receiver_fixture():
    from dispread_bridge_app.session_export import generate_session

    raw = generate_session("COM4")
    original = SOURCE.read_bytes()
    assert raw == original.replace(b"ComNr = 8", b"ComNr = 4").replace(
        b'Name = "Chan. 8_1"', b'Name = "Chan. 4_1"'
    ).replace(b"ComNo = 8", b"ComNo = 4")
    generated, fixture = configparser.ConfigParser(), configparser.ConfigParser()
    generated.read_string(raw.decode("ascii"))
    fixture.read(ROOT / "tests/fixtures/gsvmulti/session-templates/uart-demo-11.ucf")
    generated.remove_section("CopyPaste")
    assert dict(generated) == dict(fixture)


@pytest.mark.parametrize("port", ["COM0", "COM257", "COM01", "com4", " COM4", "COM4\n", "COM4/../x", None, 4])
def test_rejects_noncanonical_com_names(port):
    from dispread_bridge_app.session_export import generate_session

    with pytest.raises(ValueError):
        generate_session(port)


@pytest.mark.parametrize("port", ["COM1", "COM256"])
def test_accepts_boundary_ports(port):
    from dispread_bridge_app.session_export import generate_session

    assert f"ComNr = {port[3:]}\r\n".encode() in generate_session(port)


def test_only_pinned_generator_evidence_allows_export():
    from dispread_bridge_app.session_templates import inspect_template

    evidence = inspect_template(SOURCE)
    evidence.require_automatic_export()
    assert not evidence.roundtrip_verified
    assert evidence.allowed_fields == ("ch1.ComNr", "ch1.Name", "UserDevice.ComNo")


def test_probe_recognizes_restricted_generator(tmp_path):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "inspect_session_probe", ROOT / "windows/bridge/probes/inspect_session.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from unittest.mock import patch

    with patch.object(sys, "argv", ["inspect_session.py", str(SOURCE)]):
        assert module.main() == 0


def test_prepared_com8_is_byte_identical_to_four_channel_evidence():
    from dispread_bridge_app.session_export import generate_template_session

    raw = generate_template_session('COM8', 'bruecke-session-4ch-hidden-20261111', allow_prepared=True)
    assert raw == (ROOT / 'docs/quellen/gsvmulti-versuche-2026-11-11/versuch2b-session-hidden.ucf').read_bytes()
    assert sha256(raw).hexdigest() == 'eabf06629857b455825f04d85b7c40155f9f9037f75722af4c36f2f801f2686c'


def test_four_channel_com4_changes_exactly_nine_reviewed_lines():
    from dispread_bridge_app.session_export import generate_template_session

    original = (ROOT / 'docs/quellen/gsvmulti-versuche-2026-11-11/versuch2b-session-hidden.ucf').read_bytes()
    generated = generate_template_session('COM4', 'bruecke-session-4ch-hidden-20261111', allow_prepared=True)
    before, after = original.splitlines(keepends=True), generated.splitlines(keepends=True)
    assert len(before) == len(after)
    changed = [(a, b) for a, b in zip(before, after, strict=True) if a != b]
    assert changed == [
        (b'ComNr = 8\r\n', b'ComNr = 4\r\n'),
        (b'Name = "Chan. 8_1"\r\n', b'Name = "Chan. 4_1"\r\n'),
        (b'ComNr = 8\r\n', b'ComNr = 4\r\n'),
        (b'Name = "Chan. 8_2"\r\n', b'Name = "Chan. 4_2"\r\n'),
        (b'ComNr = 8\r\n', b'ComNr = 4\r\n'),
        (b'Name = "Chan. 8_3"\r\n', b'Name = "Chan. 4_3"\r\n'),
        (b'ComNr = 8\r\n', b'ComNr = 4\r\n'),
        (b'Name = "Chan. 8_4"\r\n', b'Name = "Chan. 4_4"\r\n'),
        (b'ComNo = 8\r\n', b'ComNo = 4\r\n'),
    ]


def test_prepared_generation_requires_explicit_developer_opt_in():
    from dispread_bridge_app.session_export import generate_session, generate_template_session
    from dispread_bridge_app.session_templates import SessionTemplateError

    with pytest.raises(SessionTemplateError, match='automatic_export_blocked'):
        generate_template_session('COM8', 'bruecke-session-4ch-hidden-20261111')
    with pytest.raises(TypeError):
        generate_session('COM8', template_id='bruecke-session-4ch-hidden-20261111')
    with pytest.raises(SessionTemplateError, match='unknown_template'):
        generate_template_session('COM8', 'unknown', allow_prepared=True)


def test_public_export_reports_active_metadata_and_refuses_template_selection(tmp_path):
    from dispread_bridge_app.app_controller import AppError
    from test_app_controller import make

    controller = make(tmp_path)
    exported = controller.export_session_file(tmp_path / 'active.ucf', 'COM8')
    assert exported.template_id == 'bruecke-session-com8-20261106'
    assert exported.path.read_bytes() == SOURCE.read_bytes()
    assert (exported.channels, exported.hidden_channels, exported.record_hidden_required) == (1, 0, False)
    assert controller.context().session_template == exported.template_id
    blocked = tmp_path / 'prepared.ucf'
    with pytest.raises(TypeError):
        controller.export_session_file(blocked, 'COM8', template_id='bruecke-session-4ch-hidden-20261111')
    with pytest.raises(AppError, match='automatic_export_blocked'):
        controller.export_session({'gsv_port': 'COM8', 'template_id': 'bruecke-session-4ch-hidden-20261111'}, blocked)
    assert not blocked.exists()


def test_catalog_activation_updates_public_export_metadata_and_context(tmp_path):
    """Simulate a reviewed catalog activation before application startup."""
    import os
    import subprocess
    import sys

    code = '''
import sys
from dataclasses import replace
from pathlib import Path
from dispread_bridge_app import session_templates as templates
templates.ACTIVE_SESSION_TEMPLATE = 'bruecke-session-4ch-hidden-20261111'
templates.SESSION_TEMPLATES = tuple(
    replace(spec, status='active' if spec.template_id == templates.ACTIVE_SESSION_TEMPLATE else 'prepared')
    for spec in templates.SESSION_TEMPLATES)
from test_app_controller import make
controller = make(Path(sys.argv[1]))
exported = controller.export_session_file(Path(sys.argv[1]) / 'four.ucf', 'COM8')
assert (exported.channels, exported.hidden_channels, exported.record_hidden_required) == (4, 3, True)
assert exported.template_id == controller.context().session_template == templates.ACTIVE_SESSION_TEMPLATE
assert exported.path.read_bytes() == Path(sys.argv[2]).read_bytes()
'''
    result = subprocess.run(
        [sys.executable, '-c', code, str(tmp_path),
         str(ROOT / 'docs/quellen/gsvmulti-versuche-2026-11-11/versuch2b-session-hidden.ucf')],
        capture_output=True, text=True, check=False,
        env={**os.environ, 'PYTHONPATH': os.pathsep.join([
            str(ROOT / 'src'), str(ROOT / 'windows/bridge/src'), str(ROOT / 'windows/bridge/tests')])},
    )
    assert result.returncode == 0, result.stderr
