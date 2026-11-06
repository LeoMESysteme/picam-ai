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
