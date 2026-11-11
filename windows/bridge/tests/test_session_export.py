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


def test_four_channel_com8_is_byte_identical_to_evidence():
    from dispread_bridge_app.session_export import generate_session

    raw = generate_session('COM8', fmt='4ch')
    assert raw == (ROOT / 'docs/quellen/gsvmulti-versuche-2026-11-11/vorlage-4kanal-mvv.ucf').read_bytes()
    assert sha256(raw).hexdigest() == '6bc26b61323e054bfea2dd32c375617ec46725e8eb56f455daf45454b3d8ec43'


def test_four_channel_com4_changes_exactly_nine_reviewed_lines():
    from dispread_bridge_app.session_export import generate_session

    original = (ROOT / 'docs/quellen/gsvmulti-versuche-2026-11-11/vorlage-4kanal-mvv.ucf').read_bytes()
    generated = generate_session('COM4', fmt='4ch')
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


@pytest.mark.parametrize('fmt', ['', 'single', 'bogus', 4, [], {}])
def test_unknown_format_is_rejected_before_writing(tmp_path, fmt):
    from dispread_bridge_app.app_controller import AppError
    from dispread_bridge_app.session_export import generate_session
    from dispread_bridge_app.session_templates import SessionTemplateError
    from test_app_controller import make

    with pytest.raises(SessionTemplateError, match='session_format_invalid'):
        generate_session('COM8', fmt=fmt)
    destination = tmp_path / 'invalid.ucf'
    with pytest.raises(AppError, match='session_format_invalid'):
        make(tmp_path).export_session_file(destination, 'COM8', fmt=fmt)
    assert not destination.exists()


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


def test_single_default_switch_updates_export_and_unexported_context(tmp_path, monkeypatch):
    from dispread_bridge_app import session_templates as templates
    from dispread_bridge_app.session_export import generate_session
    from test_app_controller import make

    assert templates.DEFAULT_SESSION_FORMAT == '1ch'
    assert not hasattr(templates, 'ACTIVE_SESSION_TEMPLATE')
    controller = make(tmp_path)
    assert controller.context().default_session_format == '1ch'
    assert controller.context().session_format is None
    monkeypatch.setattr(templates, 'DEFAULT_SESSION_FORMAT', '4ch')
    ctx = controller.context()
    assert (ctx.default_session_format, ctx.session_channels, ctx.session_format) == ('4ch', 4, None)
    exported = controller.export_session_file(tmp_path / 'four.ucf', 'COM8')
    assert exported.fmt == '4ch'
    assert (exported.channels, exported.hidden_channels, exported.record_hidden_required) == (4, 3, True)
    original = (ROOT / 'docs/quellen/gsvmulti-versuche-2026-11-11/vorlage-4kanal-mvv.ucf').read_bytes()
    assert exported.path.read_bytes() == generate_session('COM8') == original
    assert generate_session('COM8', fmt='1ch') == SOURCE.read_bytes()


def test_context_uses_cached_template_metadata_without_package_io(tmp_path, monkeypatch):
    from dispread_bridge_app import session_templates as templates
    from dispread_bridge_app.ui.port import PortChoice
    from test_app_controller import make

    controller = make(tmp_path, list_ports=lambda: [PortChoice('COM9', 'USB serial', 'usb_serial', device_id='usb9')])
    controller.select_mode('uart_direct')
    controller.select_adapter('usb9')
    controller.export_session_file(tmp_path / 'direct.ucf', fmt='4ch')

    def unexpected_io(*args):
        pytest.fail('context must not read packaged files')

    monkeypatch.setattr(templates, 'files', unexpected_io)
    assert controller.context().session_channels == 4
