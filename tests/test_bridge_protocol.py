import json

import pytest

from dispread.bridge.protocol import (
    V2LineReader,
    canonical_uart_hello,
    decode_v2,
    encode_v2,
    parse_profile,
)


def profile(**changes):
    return {
        "schema": 1,
        "pi_id": "pi-test",
        "name": "Labor Pi",
        "certificate_pem": "-----BEGIN CERTIFICATE-----\nYQ==\n-----END CERTIFICATE-----\n",
        "certificate_sha256": "a" * 64,
        "endpoints": ["https://pi-test.local:8443/api/bridge"],
        "protocol_version": 2,
        **changes,
    }


def poll(**changes):
    return dict(
        version=2,
        type="poll",
        request_id="req-1",
        pi_id="pi-test",
        client_id="pc-1",
        run_id="run-1",
        lease_id="lease-1",
        **changes,
    )


def test_profile_rejects_oversize_and_executable_urls():
    with pytest.raises(ValueError):
        parse_profile(b" " * 16385)
    for endpoint in [
        "file:///tmp/x",
        "javascript:alert(1)",
        "https://user:secret@pi.local/",
        "https://pi.local/?command=run",
        "https://pi.local/#x",
        "https://pi.local\\evil/",
    ]:
        with pytest.raises(ValueError):
            parse_profile(json.dumps(profile(endpoints=[endpoint])).encode())
    with pytest.raises(ValueError):
        parse_profile(json.dumps(profile(path="/tmp/execute")).encode())


def test_profile_preserves_ipv6_scope():
    endpoint = "wss://[fe80::1234%25Ethernet_2]:8443/api/bridge"
    parsed = parse_profile(json.dumps(profile(endpoints=[endpoint])).encode())
    assert parsed.endpoints == (endpoint,)
    assert parsed.pairing_offer is None


@pytest.mark.parametrize(
    "changes",
    [
        {"schema": True},
        {"protocol_version": 1},
        {"endpoints": ["https://pi.local/"] * 9},
        {"endpoints": ["https://pi.local/", "https://pi.local/"]},
        {"certificate_sha256": "x" * 64},
        {"pairing_offer": "short"},
    ],
)
def test_profile_rejects_invalid_schema(changes):
    with pytest.raises(ValueError):
        parse_profile(json.dumps(profile(**changes)).encode())


def test_v2_rejects_wrong_version_nonfinite_and_oversize():
    for raw in [b'{"version":1}', b'{"version":2,"x":NaN}', b" " * 65537, b'{"version":2,"version":2}', b"[]", b"\xff"]:
        with pytest.raises(ValueError):
            decode_v2(raw)
    with pytest.raises(ValueError):
        encode_v2({**poll(), "version": True})
    with pytest.raises(ValueError):
        encode_v2({**poll(), "unknown": 1})


def test_v2_roundtrip_and_bounded_fragmented_framing():
    message = poll()
    payload = encode_v2(message)
    assert decode_v2(payload) == message
    reader = V2LineReader()
    assert reader.feed(payload[:7]) == []
    assert reader.feed(payload[7:] + payload) == [message, message]
    with pytest.raises(ValueError):
        V2LineReader().feed(b"x" * 65537)


@pytest.mark.parametrize("field,value", [("run_id", "bad run"), ("lease_id", ""), ("request_id", "bad\nrequest")])
def test_v2_requires_bound_identifiers(field, value):
    with pytest.raises(ValueError):
        decode_v2(json.dumps({**poll(), field: value}).encode())


def test_canonical_uart_hello_binds_version_pi_and_nonce():
    expected = (
        b'dispread.bridge.uart-hello.v2\0{"client_id":"pc-1","nonce":"'
        + b"a" * 43
        + b'","pi_id":"pi-test","protocol_version":2,"transport":"uart"}'
    )
    assert canonical_uart_hello("pi-test", "pc-1", "a" * 43) == expected
    assert canonical_uart_hello("other-pi", "pc-1", "a" * 43) != expected
    with pytest.raises(ValueError):
        canonical_uart_hello("pi-test", "pc-1", "a" * 43, protocol_version=1)


def test_readiness_poll_has_nullable_run_and_demo_request_is_explicitly_bounded():
    assert decode_v2(encode_v2({**poll(), "run_id": None}))["run_id"] is None
    demo = {**poll(), "type": "demo_request", "run_id": None, "transport": "network", "count": 20, "rate_hz": 10.0}
    del demo["lease_id"]
    assert decode_v2(encode_v2(demo)) == demo
    for field, value in [
        ("count", True),
        ("count", 0),
        ("count", 100001),
        ("rate_hz", 0),
        ("rate_hz", float("inf")),
        ("rate_hz", 101),
        ("transport", "wss"),
    ]:
        with pytest.raises(ValueError):
            encode_v2({**demo, field: value})


def demo_record():
    from dispread.records import TimeBaseKind, Timestamp, ValueRecord, ValueStatus

    record = ValueRecord(
        1,
        Timestamp(1, TimeBaseKind.SYNTHETIC),
        None,
        None,
        ValueStatus.UNREADABLE,
        0.0,
        "test",
        None,
        None,
        raw_text="",
        reject_reasons=("unreadable",),
    )
    return {**poll(), "type": "record", "demo": True, "frame_age_ns": None, "barrier_id": 1, "record": record.to_dict()}


def test_record_preserves_optional_unit_empty_text_and_unknown_uncertainty():
    message = demo_record()
    decoded = decode_v2(encode_v2(message))
    assert decoded == message
    assert decoded["record"]["capture_timestamp"]["uncertainty_ns"] is None


@pytest.mark.parametrize("changes", [{"demo": False}, {"frame_age_ns": 0}, {"barrier_id": True}])
def test_record_never_authorizes_dut_or_fabricates_age(changes):
    with pytest.raises(ValueError):
        encode_v2({**demo_record(), **changes})


def test_record_rejects_real_capture_and_unmarked_stale_numeric_value():
    message = demo_record()
    message["record"]["capture_timestamp"]["base"] = "v4l2_monotonic"
    with pytest.raises(ValueError):
        encode_v2(message)
    message = demo_record()
    message["record"]["value"] = 1.0
    with pytest.raises(ValueError):
        encode_v2(message)


def test_v2_rejects_excessive_nesting_and_nonfinite_exponent():
    for raw in [b'{"x":' + b"[" * 18 + b"0" + b"]" * 18 + b"}", b'{"version":2,"x":1e999}']:
        with pytest.raises(ValueError):
            decode_v2(raw)


@pytest.mark.parametrize('kind,fields', [
    ('heartbeat', {'run_id': None, 'lease_id': 'lease'}),
    ('uart_challenge', {'nonce': 'a' * 43}),
    ('uart_proof', {'nonce': 'a' * 43, 'signature': 'YWJj'}),
    ('uart_auth', {'nonce': 'a' * 43, 'mode': 'token', 'credential': 'b' * 43}),
    ('uart_authenticated', {'token': 'b' * 43}),
])
def test_heartbeat_and_uart_controls_are_bounded_exact_schemas(kind, fields):
    message = dict(version=2, type=kind, request_id='r', pi_id='pi', client_id='pc', **fields)
    assert decode_v2(encode_v2(message)) == message
    with pytest.raises(ValueError):
        encode_v2({**message, 'capabilities': {'token': 'b' * 43}})
    if 'nonce' in message:
        with pytest.raises(ValueError):
            encode_v2({**message, 'nonce': 'short'})
    if kind == 'uart_auth':
        with pytest.raises(ValueError):
            encode_v2({**message, 'mode': 'network'})


# R1 (2026-11-09): bestaetigte Testfreigabe echter Werte, additiv in v2.
def released_record():
    message = demo_record()
    message["demo"] = False
    message["release"] = "test_unaccepted"
    message["record"]["capture_timestamp"]["base"] = "v4l2_monotonic"
    return message


def test_test_release_record_carries_real_capture_without_age_claim():
    message = released_record()
    assert decode_v2(encode_v2(message)) == message
    message["record"]["capture_timestamp"]["base"] = "synthetic"  # synthetische Live-Quelle
    assert decode_v2(encode_v2(message)) == message


@pytest.mark.parametrize("changes", [
    {"release": None}, {"release": "accepted"}, {"release": True}, {"frame_age_ns": 5},
])
def test_test_release_record_requires_exact_marker_and_no_age(changes):
    with pytest.raises(ValueError):
        encode_v2({**released_record(), **changes})
    without = released_record()
    del without["release"]
    with pytest.raises(ValueError):
        encode_v2(without)


def test_demo_record_never_carries_release_marker():
    with pytest.raises(ValueError):
        encode_v2({**demo_record(), "release": "test_unaccepted"})


def hello(**changes):
    return {**dict(version=2, type="hello", request_id="r", pi_id="pi-test", client_id="pc-1",
                   protocol_version=2, transport="uart", run_id="run-1", state="ready", release_block=None,
                   capabilities={}, permissions=[], lease_id="lease-1"), **changes}


def test_hello_and_idle_release_marker_is_optional_exact_and_unblocked():
    assert "release" not in decode_v2(encode_v2(hello()))
    assert decode_v2(encode_v2(hello(release="test_unaccepted")))["release"] == "test_unaccepted"
    idle = {**poll(), "type": "idle", "release_block": None, "release": "test_unaccepted"}
    assert decode_v2(encode_v2(idle)) == idle
    for message in (hello(release="accepted"), hello(release=None),
                    hello(release="test_unaccepted", release_block="gesperrt"),
                    {**idle, "release_block": "gesperrt"}, {**idle, "release": ""}):
        with pytest.raises(ValueError):
            encode_v2(message)


def test_ack_may_report_local_omission():
    ack = {**poll(), "type": "ack", "frame_sequence": 3, "barrier_id": 2, "outcome": "omitted"}
    assert decode_v2(encode_v2(ack))["outcome"] == "omitted"


# Brückentest 2026-11-11: unlesbare/Übergangswerte der echten Kamera tragen
# frames_confirmed = 0; die Barriere dafür muss kodierbar bleiben, sonst trennt
# der Pi bei jedem Wechsel gültig -> ungültig die Verbindung.
@pytest.mark.parametrize("status", ["transition", "unreadable", "stale"])
def test_invalid_record_may_have_zero_confirmed_frames(status):
    message = released_record()
    message["record"]["status"] = status
    message["record"]["frames_confirmed"] = 0
    assert decode_v2(encode_v2(message)) == message
    demo = demo_record()
    demo["record"]["status"] = status
    demo["record"]["frames_confirmed"] = 0
    assert decode_v2(encode_v2(demo)) == demo


def test_valid_record_still_requires_a_confirmed_frame():
    message = released_record()
    message["record"].update(status="valid", value=0.5, raw_text="0.5", frames_confirmed=0)
    message["barrier_id"] = None
    with pytest.raises(ValueError):
        encode_v2(message)
    message["record"]["frames_confirmed"] = 1
    assert decode_v2(encode_v2(message)) == message


def test_profile_uart_baud_defaults_and_explicit_rate():
    # Ohne Feld stammt das Profil von einem Pi vor UX2, der noch 115 200 Baud fährt.
    legacy = {k: v for k, v in profile().items() if k != "uart_baud"}
    assert parse_profile(json.dumps(legacy).encode()).uart_baud == 115200
    assert parse_profile(json.dumps(profile(uart_baud=230400)).encode()).uart_baud == 230400


@pytest.mark.parametrize('rate', [True, None, '460800', 0, -1, 99999999])
def test_profile_rejects_invalid_uart_baud(rate):
    with pytest.raises(ValueError):
        parse_profile(json.dumps(profile(uart_baud=rate)).encode())
# --- B2 (2026-11-11): kompakte Taktnachricht ``tick`` und ``tick_ack`` -----------------

def tick(**changes):
    return {**poll(), "type": "tick", "seq": 7, "valid": True, "value_text": "0.63956",
            "frame_sequence": 42, "time_unix_ns": 1_794_397_184_232_361_000,
            "origin_unix_ns": 1_794_397_183_532_361_000, "rate_hz": 10,
            "release": "test_unaccepted", **changes}


def tick_ack(**changes):
    return {**poll(), "type": "tick_ack", "seq": 7, "outcome": "written", "filled": 0, **changes}


def test_tick_roundtrip_is_compact():
    raw = encode_v2(tick())
    assert decode_v2(raw) == tick()
    assert len(raw) < 330  # statt ~1,2 kB je ValueRecord
    invalid = tick(valid=False, value_text=None, frame_sequence=None)
    assert decode_v2(encode_v2(invalid)) == invalid


@pytest.mark.parametrize("changes", [
    {"value_text": "1E+300"}, {"value_text": "1e3"}, {"value_text": "NaN"}, {"value_text": "Inf"},
    {"value_text": "-inf"}, {"value_text": "99999999.0"}, {"value_text": "99999999"},
    {"value_text": " 1.0"}, {"value_text": ""}, {"value_text": None},
    {"valid": False},                                   # Wert nur bei gueltig
    {"valid": False, "value_text": None},               # Bildnummer nur bei gueltig
    {"frame_sequence": None},
    {"valid": 1}, {"seq": 0}, {"seq": True}, {"seq": 1.0},
    {"time_unix_ns": -1}, {"time_unix_ns": 1.5}, {"origin_unix_ns": None},
    {"rate_hz": 0}, {"rate_hz": 11}, {"rate_hz": True},
    {"run_id": None}, {"release": None}, {"release": "accepted"},
    {"release_block": None}, {"extra": 1},
])
def test_tick_schema_is_strict(changes):
    with pytest.raises(ValueError):
        encode_v2(tick(**changes))
    with pytest.raises(ValueError):
        decode_v2(json.dumps(tick(**changes)).encode())


def test_tick_without_release_marker_is_rejected():
    message = tick()
    del message["release"]
    with pytest.raises(ValueError):
        encode_v2(message)


def test_tick_ack_is_bounded():
    assert decode_v2(encode_v2(tick_ack(filled=50))) == tick_ack(filled=50)
    for outcome in ("written", "expired", "failed", "unconfirmed"):
        decode_v2(encode_v2(tick_ack(outcome=outcome)))
    for changes in ({"outcome": "omitted"}, {"filled": 51}, {"filled": -1}, {"seq": 0},
                    {"frame_sequence": 1}, {"run_id": None}):
        with pytest.raises(ValueError):
            encode_v2(tick_ack(**changes))


# --- Nachtrag B2 (2026-11-11): output_format in hello/idle ---------------------------

@pytest.mark.parametrize("value", ["4ch", "1ch", None])
def test_hello_and_idle_may_carry_output_format(value):
    idle = {**poll(), "type": "idle", "release_block": None, "output_format": value}
    assert decode_v2(encode_v2(idle)) == idle
    assert decode_v2(encode_v2(hello(output_format=value)))["output_format"] == value
    assert "output_format" not in decode_v2(encode_v2(hello()))      # alte Form bleibt gültig


@pytest.mark.parametrize("value", ["4CH", "2ch", "", 4, True, ["4ch"]])
def test_output_format_is_strict(value):
    with pytest.raises(ValueError):
        encode_v2(hello(output_format=value))
    with pytest.raises(ValueError):
        encode_v2({**poll(), "type": "idle", "release_block": None, "output_format": value})


def test_output_format_only_in_hello_and_idle():
    for message in (poll(output_format="4ch"), {**poll(), "type": "ended", "output_format": "4ch"}):
        with pytest.raises(ValueError):
            encode_v2(message)
