"""UX2 contract without real network, serial or PnP access."""

import json
import socket
import ssl
import threading
import time
from types import SimpleNamespace

import pytest
from dispread_bridge_app.app_controller import AppError
from dispread_bridge_app.ui.port import MODES, PortChoice
from test_app_controller import make, profile_bytes


@pytest.fixture
def single_channel_default(monkeypatch):
    """Diese Tests prüfen die Einkanal-Vorlage; die Vorgabe ist seit 2026-11-12 Vierkanal."""
    from dispread_bridge_app import session_templates
    monkeypatch.setattr(session_templates, 'DEFAULT_SESSION_FORMAT', '1ch')


@pytest.fixture(scope="module")

def identity(tmp_path_factory):
    from dispread.bridge.identity import DeviceIdentity

    return DeviceIdentity.load_or_create(tmp_path_factory.mktemp("ux2-id"), "ux2-pi")


def usb(port="COM9"):
    return PortChoice(port, "FTDI USB Serial", "usb_serial", device_id="usb-9")


class Stream:
    def __init__(self, der=None):
        self.der, self.closed = der, False

    def close(self):
        self.closed = True

    def getpeercert(self, binary_form=False):
        return self.der


def test_direct_setup_export_restart_and_no_worker(tmp_path):
    opened = []

    def opener(**kw):
        assert kw["baudrate"] == 115200
        assert kw["exclusive"] is True
        opened.append(Stream())
        return opened[-1]

    c = make(tmp_path, list_ports=lambda: [usb()], port_opener=opener)
    assert tuple(m.mode for m in c.modes()) == MODES
    c.select_mode("uart_direct")
    assert c.context().setup.variant == "D1"
    c.select_adapter("usb-9")
    c.setup_step("next")
    assert c.context().setup.variant == "D2"
    assert all(s.closed for s in opened)
    c.setup_step("next")
    assert c.context().setup.variant == "D3"
    with pytest.raises(AppError, match="session_required"):
        c.setup_step("next")
    exported = c.export_session_file(tmp_path / "direct.ucf")
    assert exported.port == "COM9" and exported.path.is_file()
    c.setup_step("next")
    assert c.context().setup.variant == "D4"
    c.setup_step("finish")
    assert c.context().mode == "operate" and c._worker is None and c._manager is None
    assert not c.auto_connect_at_start()
    c2 = make(tmp_path, list_ports=lambda: [usb()])
    assert c2.context().route_mode == "uart_direct" and c2.context().mode == "operate"
    assert next(m for m in c2.modes() if m.mode == "uart_direct").configured
    assert c2.context().gsv_baud == 115200 and c2.context().uart_baud == 460800


def test_leave_setup_keeps_incomplete_state_and_legacy_route(tmp_path):
    c = make(tmp_path)
    assert c.context().setup_leavable
    c.leave_setup()
    assert c.context().mode == "operate" and not any(m.configured for m in c.modes())
    c.select_route("uart")
    assert c.context().route_mode == "uart_bridge"
    c.select_mode("network")
    assert c.context().mode == "setup"
    c.select_route("uart")
    state = json.loads(c._state_path.read_text())
    state.pop("route_mode")
    c._state_path.write_text(json.dumps(state))
    assert make(tmp_path).context().route_mode == "uart_bridge"


def test_finish_without_selected_route_configures_network(tmp_path, identity):
    c = make(tmp_path)
    try:
        c.set_port_pair("COM4", "COM5")
        c.load_profile(profile_bytes(identity))
        c.setup_step("finish")
        assert c.context().route_mode == "network"
        assert next(m for m in c.modes() if m.mode == "network").configured
        c2 = make(tmp_path)
        try:
            assert c2.context().mode == "operate"
            assert c2.context().route_mode == "network"
        finally:
            c2.request_exit(True)
    finally:
        c.request_exit(True)


@pytest.mark.parametrize("route", [None, "network", "uart"])
def test_legacy_finished_setup_restores_implicit_or_explicit_route(tmp_path, identity, route):
    c = make(tmp_path)
    c.set_port_pair("COM4", "COM5")
    c.load_profile(profile_bytes(identity))
    c.request_exit(True)
    state = json.loads(c._state_path.read_text())
    state.pop("route_mode")
    state.pop("configured_modes")
    state.update(setup_done=True, route=route)
    c._state_path.write_text(json.dumps(state))
    c2 = make(tmp_path)
    try:
        expected = "uart_bridge" if route == "uart" else "network"
        assert c2.context().route_mode == expected
        assert c2.context().mode == "operate"
        assert next(m for m in c2.modes() if m.mode == expected).configured
    finally:
        c2.request_exit(True)


def test_active_worker_locks_mode_endpoint_and_adapter(tmp_path):
    c = make(tmp_path)
    c._worker = SimpleNamespace(is_active=lambda: True, status=SimpleNamespace(active=True))
    for call in (
        lambda: c.select_mode("uart_direct"),
        lambda: c.select_adapter("usb-9"),
        lambda: c.select_endpoint("https://pi.local"),
    ):
        with pytest.raises(AppError, match="mode_locked"):
            call()
    assert all(not m.available for m in c.modes())


def test_port_checks_close_handles_and_never_claim_unproved_pair(tmp_path):
    opened, calls = [], []

    def opener(**kw):
        calls.append(kw)
        opened.append(Stream())
        return opened[-1]

    c = make(
        tmp_path,
        list_ports=lambda: [usb(), PortChoice("COM4", "virtual", "com0com"), PortChoice("COM5", "virtual", "com0com")],
        port_opener=opener,
    )
    assert c.check_port_pair("COM4", "COM4").state == "err"
    assert c.check_port_pair("COM4", "COM6").state == "err"
    assert c.check_port_pair("COM4", "COM5").state == "warn"
    assert c.check_adapter("COM4").state == "err"
    assert c.check_adapter("COM9").state == "ok"
    assert all(p.closed for p in opened) and all(k["exclusive"] for k in calls)
    assert calls[-1]["baudrate"] == 460800
    assert c.list_adapters() == (usb(),)


def test_checks_suppress_exception_text_and_bound_hung_dependencies(tmp_path):
    gate = threading.Event()
    c = make(tmp_path, list_ports=lambda: [usb()], port_opener=lambda **kw: (_ for _ in ()).throw(OSError("SECRET")))
    result = c.check_adapter("COM9")
    assert result.state == "err" and "SECRET" not in repr(result)
    c = make(tmp_path / "slow", resolver=lambda *a: gate.wait(8))
    c._profile = SimpleNamespace()
    start = time.monotonic()
    try:
        result = c.check_endpoint("https://pi.local")
        assert result.state == "err" and time.monotonic() - start < 3
        start = time.monotonic()
        c.check_endpoint("https://pi.local")
        assert time.monotonic() - start < 0.3
    finally:
        gate.set()


@pytest.mark.parametrize("stage", ["dns", "tcp", "tls", "pin", "ok"])
def test_endpoint_checks_real_pinned_certificate_and_failure_stage(tmp_path, identity, stage):
    der, streams = ssl.PEM_cert_to_DER_cert(identity.certificate_pem), []

    def resolver(*a):
        if stage == "dns":
            raise socket.gaierror("SECRET")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    def connect(addr, timeout):
        assert 0 < timeout <= 3
        if stage == "tcp":
            raise OSError("SECRET")
        streams.append(Stream())
        return streams[-1]

    def tls(stream, profile, hostname, timeout):
        if stage == "tls":
            raise ssl.SSLError("SECRET")
        streams.append(Stream(b"other" if stage == "pin" else der))
        return streams[-1]

    c = make(tmp_path, resolver=resolver, socket_factory=connect, tls_factory=tls)
    c.load_profile(profile_bytes(identity))
    result = c.check_endpoint("https://pi.local:443")
    assert result.state == ("ok" if stage == "ok" else "err")
    if stage != "ok":
        assert ("TLS" if stage == "pin" else stage.upper()) in result.message
    assert "SECRET" not in repr(result) and all(s.closed for s in streams)


def test_pairing_format_does_not_need_profile_or_reveal_code(tmp_path):
    c = make(tmp_path)
    for code, expected in [("Q" * 43, "ok"), ("invalid", "err"), ("Q" * 43 + "\n", "err")]:
        result = c.check_pairing_code(code)
        assert result.state == expected and code not in result.message


def test_context_never_enumerates_ports_and_cache_expires_after_two_seconds(tmp_path):
    now, queries = [0.0], []

    def ports():
        queries.append(now[0])
        return [usb()]

    c = make(tmp_path, list_ports=ports, clock=lambda: now[0])
    c.select_mode("uart_direct")
    c.list_adapters()
    c.select_adapter("usb-9")
    count = len(queries)
    for _ in range(20):
        assert c.context().adapter_present is True
        c.list_adapters()
    assert len(queries) == count
    now[0] = 2.01
    c.list_adapters()
    assert len(queries) == count + 1
    c.request_exit(True)


def test_export_allows_only_exact_three_field_settings(tmp_path):
    c = make(tmp_path)
    result = c.export_session({"gsv_port": "COM4"}, tmp_path / "valid.ucf")
    assert result.port == "COM4"
    for settings in ({"gsv_port": "COM4", "scale": 2}, {"gsv_port": "COM257"}, {}, {"template": "other"}):
        path = tmp_path / "blocked.ucf"
        with pytest.raises(AppError):
            c.export_session(settings, path)
        assert not path.exists()


def test_activity_seq_counts_only_validated_pi_exchanges(tmp_path):
    from dispread.bridge.types import BridgeEvent

    c = make(tmp_path)
    for kind, code in [
        ("connection", "connecting"),
        ("activity", "poll"),
        ("activity", "ack"),
        ("activity", "heartbeat"),
        ("exchange", "failed"),
    ]:
        c._emit(BridgeEvent(kind, code, None, None, {}))
    assert c.context().activity_seq == 3
    assert all(e.title for e in c.context().journal)


def test_mode_completion_is_per_route_and_reconfiguration_invalidates_it(tmp_path, identity):
    c = make(tmp_path)
    c.load_profile(profile_bytes(identity))
    c.set_port_pair("COM4", "COM5")
    c.select_route("network")
    c._step = 5
    c.setup_step("finish")
    c.select_route("uart")
    assert c.context().mode == "setup"
    assert not next(m for m in c.modes() if m.mode == "uart_bridge").configured
    c.select_mode("network")
    assert c.context().mode == "operate"
    c.set_port_pair("COM3", "COM5")
    assert c.context().mode == "setup"
    c.load_profile(profile_bytes(identity))
    assert not next(m for m in c.modes() if m.mode == "network").configured


def test_own_active_pair_is_not_reopened(tmp_path):
    c = make(tmp_path, port_opener=lambda **kw: pytest.fail("own ports must not be reopened"))
    c.set_port_pair("COM4", "COM5")
    c._worker = SimpleNamespace(is_active=lambda: True)
    assert c.check_port_pair("COM4", "COM5").state == "ok"
    assert c.check_port_pair("COM3", "COM5").state == "err"


def test_port_check_timeout_always_releases_late_handle(tmp_path, monkeypatch):
    from dispread_bridge_app import input_checks

    monkeypatch.setattr(input_checks, "CHECK_BUDGET_S", 0.05)
    gate, released = threading.Event(), threading.Event()

    class Late(Stream):
        def close(self):
            super().close()
            released.set()

    def opener(**kw):
        gate.wait(2)
        return Late()

    c = make(tmp_path, list_ports=lambda: [usb()], port_opener=opener)
    try:
        assert c.check_adapter("COM9").state == "err"
    finally:
        gate.set()
    assert released.wait(1)


def test_known_com0com_pair_mapping_can_be_confirmed(tmp_path):
    from dispread_bridge_app.types import PortPair

    c = make(
        tmp_path,
        vcom=SimpleNamespace(inventory=lambda: [PortPair("p", "COM4", "COM5", False)]),
        port_opener=lambda **kw: Stream(),
    )
    assert c.check_port_pair("COM4", "COM5").state == "ok"


def _finish_direct(c, path):
    c.select_mode("uart_direct")
    c.select_adapter("usb-9")
    c.setup_step("next")
    c.setup_step("next")
    c.export_session_file(path)
    c.setup_step("next")
    c.setup_step("finish")


def test_review_adapter_change_requires_rechecking_and_new_session(tmp_path):
    ports = [usb(), PortChoice("COM10", "second USB", "usb_serial", device_id="usb-10")]
    c = make(tmp_path, list_ports=lambda: ports, port_opener=lambda **kw: Stream())
    _finish_direct(c, tmp_path / "direct9.ucf")
    c.select_adapter("usb-10")
    assert c.context().mode == "setup"
    assert c.context().setup.variant == "D1"
    assert c.context().session_name is None
    with pytest.raises(AppError, match="session_required"):
        c.setup_step("finish")


def test_review_endpoint_selection_cannot_carry_direct_completion(tmp_path):
    c = make(tmp_path, list_ports=lambda: [usb()], port_opener=lambda **kw: Stream())
    _finish_direct(c, tmp_path / "direct9.ucf")
    c.select_endpoint("https://example.test:443")
    assert c.context().route_mode == "network" and c.context().mode == "setup"
    assert not next(m for m in c.modes() if m.mode == "network").configured


def test_review_session_metadata_is_per_mode_and_port(tmp_path):
    c = make(tmp_path, list_ports=lambda: [usb()], port_opener=lambda **kw: Stream())
    _finish_direct(c, tmp_path / "direct9.ucf")
    c.select_mode("network")
    c.export_session_file(tmp_path / "network5.ucf", "COM5")
    c.select_mode("uart_direct")
    assert c.context().mode == "operate"
    assert c.context().session_name == "direct9.ucf"
    assert c.context().setup.data["session_path"] == str(tmp_path / "direct9.ucf")
    c2 = make(tmp_path, list_ports=lambda: [usb()])
    assert c2.context().session_name == "direct9.ucf"


def test_review_stale_adapter_probe_cannot_advance_new_mode(tmp_path):
    entered, release = threading.Event(), threading.Event()
    errors = []

    def opener(**kwargs):
        entered.set()
        release.wait(2)
        return Stream()

    c = make(tmp_path, list_ports=lambda: [usb()], port_opener=opener)
    c.select_mode("uart_direct")
    c.select_adapter("usb-9")

    def advance():
        try:
            c.setup_step("next")
        except AppError as error:
            errors.append(error.code)

    thread = threading.Thread(target=advance)
    thread.start()
    assert entered.wait(1)
    c.select_mode("network")
    release.set()
    thread.join(2)
    assert not thread.is_alive()
    assert c.context().setup.step == 1 and c.context().setup.variant == "E1"
    assert errors == ["setup_changed"]


def test_context_uses_cached_pairing_without_credential_io(tmp_path, identity, monkeypatch):
    c = make(tmp_path)
    c.set_port_pair("COM4", "COM5")
    c.load_profile(profile_bytes(identity))
    monkeypatch.setattr(c._credentials, "load", lambda *a, **kw: pytest.fail("context must not read credentials"))
    c.context()


def test_inactive_direct_completion_survives_restart(tmp_path):
    c = make(tmp_path, list_ports=lambda: [usb()], port_opener=lambda **kw: Stream())
    _finish_direct(c, tmp_path / "direct9.ucf")
    c.select_mode("network")
    c2 = make(tmp_path, list_ports=lambda: [usb()])
    c2.select_mode("uart_direct")
    assert c2.context().mode == "operate" and c2.context().session_name == "direct9.ucf"


@pytest.mark.usefixtures('single_channel_default')
def test_context_reports_active_template_channels_for_single_channel_warning(tmp_path):
    # F3-Warnung der Oberfläche hängt an session_channels; die aktive Vorlage ist einkanalig.
    c = make(tmp_path)
    assert c.context().session_channels == 1


@pytest.mark.usefixtures('single_channel_default')
def test_session_format_follows_mode_port_and_restart(tmp_path, monkeypatch):
    from dispread_bridge_app import session_templates

    c = make(tmp_path, list_ports=lambda: ['COM4', 'COM5', 'COM8', usb()])
    c.select_mode('network')
    c.set_port_pair('COM4', 'COM5')
    c.export_session_file(tmp_path / 'network5.ucf', fmt='4ch')
    assert (c.context().session_format, c.context().session_channels) == ('4ch', 4)
    c.set_port_pair('COM4', 'COM8')
    assert (c.context().session_format, c.context().session_channels) == (None, 1)
    c.export_session_file(tmp_path / 'network8.ucf', fmt='1ch')
    c.select_mode('uart_bridge')
    assert c.context().session_format is None
    c.export_session_file(tmp_path / 'bridge8.ucf', fmt='4ch')
    c.select_mode('uart_direct')
    c.select_adapter('usb-9')
    direct = c.export_session_file(tmp_path / 'direct9.ucf', fmt='4ch')
    assert direct.fmt == c.context().session_format == '4ch'
    # A later default change must never relabel an existing file.
    monkeypatch.setattr(session_templates, 'DEFAULT_SESSION_FORMAT', '4ch')
    c2 = make(tmp_path, list_ports=lambda: ['COM4', 'COM5', 'COM8', usb()])
    assert (c2.context().session_format, c2.context().session_channels) == ('4ch', 4)
    c2.select_mode('network')
    assert (c2.context().session_format, c2.context().session_channels) == ('1ch', 1)
    assert c2.context().default_session_format == '4ch'
    c2.set_port_pair('COM4', 'COM5')
    assert (c2.context().session_format, c2.context().session_channels) == ('4ch', 4)
    c2.select_mode('uart_bridge')
    assert c2.context().session_format is None
    c2.set_port_pair('COM4', 'COM8')
    assert c2.context().session_format == '4ch'


def test_legacy_session_path_is_single_even_after_default_switch(tmp_path, monkeypatch):
    from dispread_bridge_app import session_templates

    c = make(tmp_path)
    c.select_mode('network')
    c.set_port_pair('COM4', 'COM5')
    c.export_session_file(tmp_path / 'legacy.ucf')
    state = json.loads(c._state_path.read_text())
    state.pop('session_formats', None)
    c._state_path.write_text(json.dumps(state))
    monkeypatch.setattr(session_templates, 'DEFAULT_SESSION_FORMAT', '4ch')
    c2 = make(tmp_path)
    assert c2.context().default_session_format == '4ch'
    assert (c2.context().session_format, c2.context().session_channels) == ('1ch', 1)
