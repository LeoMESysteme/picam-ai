"""Only three reviewed fields may change; every other byte is evidence."""

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
