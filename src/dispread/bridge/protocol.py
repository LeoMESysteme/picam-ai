"""Strict v2 codecs. Validation proves structure, never identity or permission."""

from __future__ import annotations

import ipaddress
import json
import math
import re
from urllib.parse import urlsplit

from dispread.bridge.types import BridgeProfile
from dispread.records import TimeBaseKind, TimestampSemantics, ValueRecord

MAX_MESSAGE_BYTES = 65536
MAX_PROFILE_BYTES = 16384
MAX_ENDPOINTS = 8
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_TOKEN = re.compile(r"(?:[A-Za-z0-9_-]{43}|[0-9a-f]{64})\Z")
_BASE = {"version", "type", "request_id", "pi_id", "client_id"}
_BOUND = {"run_id", "lease_id"}
#: Additiv seit 2026-11-09 (R1): bestaetigte Testfreigabe echter Werte. Fehlt
#: das Feld, gilt fuer echte Werte weiterhin die Sperre. Es gibt bewusst nur
#: diesen einen Wert, keine "Abnahme"-Stufe.
TEST_RELEASE = "test_unaccepted"
ACK_OUTCOMES = ("written", "expired", "failed", "unconfirmed", "omitted")
_FIELDS = {
    "hello": (
        {"protocol_version", "transport", "run_id", "state", "release_block", "capabilities", "permissions"},
        {"lease_id", "nonce", "signature", "release"},
    ),
    "demo_request": ({"transport", "run_id", "count", "rate_hz"}, set()),
    "poll": (_BOUND, set()),
    "heartbeat": (_BOUND, set()),
    "uart_challenge": ({"nonce"}, set()),
    "uart_proof": ({"nonce", "signature"}, set()),
    "uart_auth": ({"nonce", "mode", "credential"}, set()),
    "uart_authenticated": ({"token"}, set()),
    "record": (_BOUND | {"demo", "record", "frame_age_ns", "barrier_id"}, {"release"}),
    "idle": (_BOUND | {"release_block"}, {"release"}),
    "ended": (_BOUND, set()),
    "ack": (_BOUND | {"frame_sequence", "barrier_id", "outcome"}, set()),
    "error": ({"code", "detail", "run_id"}, {"lease_id"}),
}
_RECORD_FIELDS = {
    "schema_version",
    "frame_sequence",
    "capture_timestamp",
    "value",
    "unit",
    "status",
    "confidence",
    "profile_id",
    "trigger_sequence",
    "result_timestamp",
    "raw_text",
    "reject_reasons",
    "frames_confirmed",
    "confirmation_span_ns",
    "trace",
    "component_versions",
}
_TRACE_FIELDS = {
    "t_dequeue_ns",
    "t_locate_done_ns",
    "t_rectify_done_ns",
    "t_read_done_ns",
    "t_gate_done_ns",
    "t_record_built_ns",
    "queue_depth",
    "dropped_frames",
}


def _reject_constant(value):
    raise ValueError(f"non-finite JSON constant: {value}")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _json_tree(value, depth=0):
    if depth > 16:
        raise ValueError("JSON nesting too deep")
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        for item in value.values():
            _json_tree(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _json_tree(item, depth + 1)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
    elif value is not None and type(value) not in (str, bool, int):
        raise ValueError("not a JSON value")


def _load(raw, maximum):
    if not isinstance(raw, bytes) or len(raw) > maximum:
        raise ValueError("invalid or oversized JSON bytes")
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_object)
        _json_tree(value)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("invalid bridge JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("bridge JSON must be an object")
    return value


def _fields(value, required, optional=()):
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - set(optional):
        raise ValueError("missing or unknown fields")


def _text(value, *, maximum=4096, nullable=False, allow_empty=False, allow_controls=False):
    if value is None and nullable:
        return
    if (
        not isinstance(value, str)
        or not int(not allow_empty) <= len(value) <= maximum
        or (not allow_controls and any(ord(c) < 32 or ord(c) == 127 for c in value))
    ):
        raise ValueError("invalid text")


def _identifier(value, *, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("invalid identifier")


def _integer(value, *, minimum=0, maximum=2**63 - 1, nullable=False):
    if value is None and nullable:
        return
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid integer")


def _number(value, *, nullable=False):
    if value is None and nullable:
        return
    if type(value) not in (int, float) or (isinstance(value, float) and not math.isfinite(value)):
        raise ValueError("invalid finite number")


def _transport(value):
    if value not in ("network", "uart"):
        raise ValueError("invalid bridge transport")


def _token(value):
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError("expected 256-bit token representation")


def _endpoint(value):
    _text(value, maximum=2048)
    if any(c.isspace() for c in value) or "\\" in value:
        raise ValueError("invalid endpoint URL")
    try:
        url = urlsplit(value)
        if (
            url.scheme not in ("https", "wss")
            or not url.hostname
            or url.username is not None
            or url.password is not None
        ):
            raise ValueError("endpoint must be HTTPS/WSS without credentials")
        if url.query or url.fragment or "?" in value or "#" in value:
            raise ValueError("endpoint cannot contain query or fragment")
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError("invalid endpoint port")
        host = url.hostname
        if ":" in host:
            address, separator, scope = host.partition("%")
            ipaddress.IPv6Address(address)
            if separator:
                scope = scope[2:] if scope.startswith("25") else scope
                if not re.fullmatch(r"[A-Za-z0-9_.~-]{1,64}", scope):
                    raise ValueError("invalid IPv6 scope")
        elif not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9.])?", host):
            raise ValueError("invalid endpoint hostname")
        if re.search(r"%(?![0-9A-Fa-f]{2})", url.path):
            raise ValueError("invalid URL escape")
    except (ValueError, UnicodeError) as exc:
        raise ValueError("invalid endpoint URL") from exc


def parse_profile(raw: bytes) -> BridgeProfile:
    """Parse untrusted configuration; crypto verification belongs to identity adapter."""
    obj = _load(raw, MAX_PROFILE_BYTES)
    _fields(
        obj,
        {"schema", "pi_id", "name", "certificate_pem", "certificate_sha256", "endpoints", "protocol_version"},
        {"pairing_offer"},
    )
    if type(obj["schema"]) is not int or obj["schema"] != 1:
        raise ValueError("unsupported profile schema")
    if type(obj["protocol_version"]) is not int or obj["protocol_version"] != 2:
        raise ValueError("unsupported protocol version")
    _identifier(obj["pi_id"])
    _text(obj["name"], maximum=256)
    pem = obj["certificate_pem"]
    if (
        not isinstance(pem, str)
        or len(pem) > 12288
        or not re.fullmatch(r"-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\r?\n?", pem)
    ):
        raise ValueError("invalid certificate PEM envelope")
    if not isinstance(obj["certificate_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", obj["certificate_sha256"]):
        raise ValueError("invalid certificate fingerprint")
    endpoints = obj["endpoints"]
    if not isinstance(endpoints, list) or len(endpoints) > MAX_ENDPOINTS:
        raise ValueError("invalid endpoint list")
    for endpoint in endpoints:
        _endpoint(endpoint)
    if len(set(endpoints)) != len(endpoints):
        raise ValueError("duplicate endpoints")
    if obj.get("pairing_offer") is not None:
        _token(obj["pairing_offer"])
    return BridgeProfile(**{**obj, "endpoints": tuple(endpoints)})


def canonical_uart_hello(
    pi_id: str, client_id: str, nonce: str, *, transport: str = "uart", protocol_version: int = 2
) -> bytes:
    """Domain-separated payload; sign and verify these exact bytes, never reinterpreted JSON."""
    _identifier(pi_id)
    _identifier(client_id)
    _token(nonce)
    if transport != "uart" or type(protocol_version) is not int or protocol_version != 2:
        raise ValueError("UART hello requires v2/uart")
    payload = dict(
        pi_id=pi_id, client_id=client_id, nonce=nonce, transport=transport, protocol_version=protocol_version
    )
    return b"dispread.bridge.uart-hello.v2\0" + json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _timestamp(value):
    _fields(value, {"value_ns", "base", "semantics", "uncertainty_ns"})
    _integer(value["value_ns"])
    TimeBaseKind(value["base"])
    TimestampSemantics(value["semantics"])
    _integer(value["uncertainty_ns"], nullable=True)


def _record(value, *, demo=True):
    _fields(value, _RECORD_FIELDS)
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported ValueRecord schema")
    _integer(value["frame_sequence"])
    _timestamp(value["capture_timestamp"])
    if demo and value["capture_timestamp"]["base"] != "synthetic":
        raise ValueError("DUT output remains blocked; only synthetic demo records allowed")
    if value["result_timestamp"] is not None:
        _timestamp(value["result_timestamp"])
    _number(value["value"], nullable=True)
    _number(value["confidence"])
    _text(value["unit"], maximum=128, nullable=True, allow_empty=True)
    _text(value["profile_id"], maximum=128)
    _text(value["raw_text"], nullable=True, allow_empty=True, allow_controls=True)
    _integer(value["trigger_sequence"], nullable=True)
    _integer(value["frames_confirmed"], minimum=1)
    _integer(value["confirmation_span_ns"])
    if not isinstance(value["reject_reasons"], list) or len(value["reject_reasons"]) > 128:
        raise ValueError("invalid rejection reasons")
    for reason in value["reject_reasons"]:
        _text(reason)
    versions = value["component_versions"]
    if not isinstance(versions, dict) or len(versions) > 128:
        raise ValueError("invalid component versions")
    for key, version in versions.items():
        _text(key, maximum=128)
        _text(version, maximum=256)
    trace = value["trace"]
    if trace is not None:
        _fields(trace, _TRACE_FIELDS)
        for key, item in trace.items():
            _integer(item, nullable=key not in ("t_dequeue_ns", "queue_depth", "dropped_frames"))
    try:
        ValueRecord.from_dict(value)
    except (TypeError, KeyError, AssertionError) as exc:
        raise ValueError("invalid ValueRecord") from exc


def _validate_v2(message):
    if not isinstance(message, dict) or type(message.get("version")) is not int or message["version"] != 2:
        raise ValueError("expected bridge protocol version 2")
    kind = message.get("type")
    if not isinstance(kind, str) or kind not in _FIELDS:
        raise ValueError("unknown v2 message type")
    required, optional = _FIELDS[kind]
    _fields(message, _BASE | required, optional)
    for key in ("request_id", "pi_id", "client_id"):
        _identifier(message[key])
    if "run_id" in message:
        _identifier(message["run_id"], nullable=kind in ("hello", "demo_request", "error", "poll", "idle", "heartbeat"))
    if "lease_id" in message:
        _identifier(message["lease_id"], nullable=kind in ("hello", "error"))
    if "release_block" in message:
        _text(message["release_block"], nullable=True)
    if "release" in message:
        # Nur der exakte Testfreigabe-Marker, nie zusammen mit einer Sperre.
        if message["release"] != TEST_RELEASE or message.get("release_block") is not None:
            raise ValueError("invalid release marker")
    if kind == "hello":
        if type(message["protocol_version"]) is not int or message["protocol_version"] != 2:
            raise ValueError("incompatible hello protocol")
        _transport(message["transport"])
        _text(message["state"], maximum=128)
        if not isinstance(message["capabilities"], dict):
            raise ValueError("capabilities must be an object")
        permissions = message["permissions"]
        if not isinstance(permissions, list) or len(permissions) > 32:
            raise ValueError("invalid permissions")
        for permission in permissions:
            _text(permission, maximum=128)
        if "nonce" in message:
            _token(message["nonce"])
        if "signature" in message:
            _text(message["signature"])
    elif kind.startswith("uart_"):
        if "nonce" in message:
            _token(message["nonce"])
        if "signature" in message:
            _text(message["signature"], maximum=4096)
        if "token" in message:
            _token(message["token"])
        if kind == "uart_auth":
            if message["mode"] not in ("token", "offer"):
                raise ValueError("invalid UART authentication mode")
            _token(message["credential"])
    elif kind == "demo_request":
        _transport(message["transport"])
        _integer(message["count"], minimum=1, maximum=100000)
        _number(message["rate_hz"])
        if not 0 < message["rate_hz"] <= 100:
            raise ValueError("invalid demo rate")
    elif kind == "record":
        # Echte Werte nur mit Testfreigabe-Marker; nie eine Altersbehauptung.
        demo = message["demo"]
        if (demo is not True and (demo is not False or message.get("release") != TEST_RELEASE)) \
                or (demo is True and "release" in message) or message["frame_age_ns"] is not None:
            raise ValueError("only synthetic demo or confirmed test release without age claim allowed")
        _integer(message["barrier_id"], minimum=1, nullable=True)
        _record(message["record"], demo=demo)
    elif kind == "ack":
        _integer(message["frame_sequence"])
        _integer(message["barrier_id"], minimum=1, nullable=True)
        if message["outcome"] not in ACK_OUTCOMES:
            raise ValueError("invalid ACK outcome")
    elif kind == "error":
        _identifier(message["code"])
        _text(message["detail"])


def encode_v2(message: dict) -> bytes:
    _json_tree(message)
    _validate_v2(message)
    try:
        result = (json.dumps(message, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    except (TypeError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid bridge JSON") from exc
    if len(result) > MAX_MESSAGE_BYTES:
        raise ValueError("bridge message too large")
    return result


def decode_v2(raw: bytes) -> dict:
    result = _load(raw, MAX_MESSAGE_BYTES)
    _validate_v2(result)
    return result


class V2LineReader:
    """Incremental bounded UART framing, independent from v1 line reader."""

    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        result = []
        for chunk in data.splitlines(keepends=True):
            self.buffer.extend(chunk)
            if len(self.buffer) > MAX_MESSAGE_BYTES:
                self.buffer.clear()
                raise ValueError("bridge message too large")
            if self.buffer.endswith(b"\n"):
                raw = bytes(self.buffer)
                self.buffer.clear()
                result.append(decode_v2(raw))
        return result
