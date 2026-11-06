"""Single-use, expiring, scoped credentials without plaintext persistence."""

import concurrent.futures
import secrets

import pytest

from dispread.bridge.pairing import PairingError, PairingStore


@pytest.fixture
def store(tmp_path):
    return PairingStore(tmp_path / "pairing", clock=lambda: 1000.0)


def test_pairing_offer_expires_at_300_seconds(tmp_path):
    now = [1000.0]
    store = PairingStore(tmp_path / "pairing", clock=lambda: now[0])
    offer = store.create_offer("network")
    assert len(offer) == 43
    now[0] += 300
    with pytest.raises(PairingError):
        store.redeem_offer(offer, "client-a", "network")


def test_offer_can_be_redeemed_once_even_concurrently(tmp_path):
    stores = [PairingStore(tmp_path / "pairing", clock=lambda: 1000.0) for _ in range(8)]
    offer = stores[0].create_offer("network")

    def redeem(store):
        try:
            return store.redeem_offer(offer, "client-a", "network")
        except PairingError:
            return None

    with concurrent.futures.ThreadPoolExecutor() as pool:
        tokens = list(pool.map(redeem, stores))
    assert len([token for token in tokens if token]) == 1


def test_wrong_client_or_transport_is_rejected(store):
    offer = store.create_offer("uart", "client-a")
    with pytest.raises(PairingError):
        store.redeem_offer(offer, "client-b", "uart")
    with pytest.raises(PairingError):
        store.redeem_offer(offer, "client-a", "network")
    token = store.redeem_offer(offer, "client-a", "uart")
    assert store.authorize(token, "uart") == "client-a"
    with pytest.raises(PairingError):
        store.authorize(token, "network")


def test_revoked_token_fails(store):
    tokens = [store.redeem_offer(store.create_offer(t), "client-a", t) for t in ("uart", "network")]
    other = store.redeem_offer(store.create_offer("uart"), "client-b", "uart")
    store.revoke("client-a")
    for token, transport in zip(tokens, ("uart", "network"), strict=True):
        with pytest.raises(PairingError):
            store.authorize(token, transport)
    assert store.authorize(other, "uart") == "client-b"


def test_credentials_never_reach_logs(store, caplog):
    offer = store.create_offer("network")
    token = store.redeem_offer(offer, "client-a", "network")
    assert store.authorize(token, "network") == "client-a"
    with pytest.raises(PairingError) as error:
        store.redeem_offer(offer, "client-a", "network")
    assert offer not in str(error.value) + caplog.text
    assert token not in str(error.value) + caplog.text
    for path in store.directory.iterdir():
        content = path.read_bytes()
        assert offer.encode() not in content
        assert token.encode() not in content
        assert path.stat().st_mode & 0o777 == 0o600


def test_repairing_replaces_prior_transport_token(store):
    old = store.redeem_offer(store.create_offer("uart"), "client-a", "uart")
    new = store.redeem_offer(store.create_offer("uart"), "client-a", "uart")
    with pytest.raises(PairingError):
        store.authorize(old, "uart")
    assert store.authorize(new, "uart") == "client-a"


def test_failed_redemptions_are_rate_limited(store):
    for _ in range(5):
        with pytest.raises(PairingError):
            store.redeem_offer(secrets.token_urlsafe(32), "client-a", "network")
    offer = store.create_offer("network")
    with pytest.raises(PairingError, match="rate"):
        store.redeem_offer(offer, "client-a", "network")


@pytest.mark.parametrize("client", ["", "bad/client", "x" * 129])
def test_invalid_client_rejected(store, client):
    with pytest.raises(ValueError):
        store.create_offer("network", client)


def test_rotating_client_names_cannot_bypass_global_redemption_limit(store):
    for index in range(20):
        with pytest.raises(PairingError):
            store.redeem_offer(secrets.token_urlsafe(32), f"client-{index}", "network")
    offer = store.create_offer("network")
    with pytest.raises(PairingError, match="rate"):
        store.redeem_offer(offer, "fresh-client", "network")


def test_offer_is_boot_bound_but_client_tokens_survive_store_restart(store):
    token = store.redeem_offer(store.create_offer("uart"), "client-a", "uart")
    offer = store.create_offer("network")
    restarted = PairingStore(store.directory, clock=lambda: 1000.0)
    assert restarted.authorize(token, "uart") == "client-a"
    restarted.boot_id = "another-boot"
    with pytest.raises(PairingError):
        restarted.redeem_offer(offer, "client-b", "network")
    assert restarted.authorize(token, "uart") == "client-a"


def test_expiry_cannot_be_extended_by_reopening_store(store):
    offer = store.create_offer("uart")
    later = PairingStore(store.directory, clock=lambda: 1300.0)
    with pytest.raises(PairingError):
        later.redeem_offer(offer, "client-a", "uart")


def test_revoke_invalidates_pending_bound_offer(store):
    offer = store.create_offer("network", "client-a")
    store.revoke("client-a")
    with pytest.raises(PairingError):
        store.redeem_offer(offer, "client-a", "network")


def test_offer_expiring_while_waiting_for_write_lock_is_refused(tmp_path, monkeypatch):
    import sqlite3
    import threading

    now = [1000.0]
    store = PairingStore(tmp_path / "pairing", clock=lambda: now[0])
    offer = store.create_offer("network")
    now[0] = 1299.0
    connect = sqlite3.connect
    blocker = connect(store.path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    attempted_lock = threading.Event()

    def connect_with_lock_signal(*args, **kwargs):
        db = connect(*args, **kwargs)

        def observe(statement):
            if statement == "BEGIN IMMEDIATE":
                attempted_lock.set()

        db.set_trace_callback(observe)
        return db

    monkeypatch.setattr(sqlite3, "connect", connect_with_lock_signal)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        redemption = pool.submit(store.redeem_offer, offer, "client-a", "network")
        try:
            assert attempted_lock.wait(timeout=5), "redemption did not attempt transaction"
            now[0] = 1301.0
        finally:
            blocker.rollback()
            blocker.close()
        with pytest.raises(PairingError, match="expired"):
            redemption.result(timeout=5)
