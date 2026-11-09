"""Transport-neutral identity and event values (not authorization decisions)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BridgeProfile:
    schema: int
    pi_id: str
    name: str
    certificate_pem: str
    certificate_sha256: str
    endpoints: tuple[str, ...]
    protocol_version: int
    pairing_offer: str | None = None


@dataclass(frozen=True, slots=True)
class PeerHello:
    pi_id: str
    client_id: str
    protocol_version: int
    transport: str
    run_id: str | None
    state: str
    release_block: str | None
    #: R1: "test_unaccepted" nur bei bestaetigter Testfreigabe fuer genau
    #: diesen Ausgabeweg; sonst None (echte Werte gesperrt).
    release: str | None = None


@dataclass(frozen=True, slots=True)
class BridgeEvent:
    """Producer must exclude credentials, pairing offers and signature material."""

    kind: str
    code: str | None
    run_id: str | None
    frame_sequence: int | None
    detail: dict
