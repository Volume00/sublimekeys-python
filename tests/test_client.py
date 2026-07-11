import base64
import json
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

import sublimekeys.http as http_module
import sublimekeys.storage as storage
from sublimekeys.client import SublimeKeysClient


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeResponse:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeTransport:
    def __init__(self):
        self.calls = []
        self._queue = []
        self._offline = False

    def queue_response(self, data: dict):
        self._queue.append(data)

    def go_offline(self):
        self._offline = True

    def __call__(self, req, timeout=None):
        self.calls.append(req)
        if self._offline:
            raise urllib.error.URLError("simulated offline")
        if not self._queue:
            raise AssertionError("FakeTransport called with no queued response")
        return FakeResponse(self._queue.pop(0))


@pytest.fixture
def fake_transport(monkeypatch):
    transport = FakeTransport()
    monkeypatch.setattr(http_module.urllib.request, "urlopen", transport)
    return transport


@pytest.fixture
def client(tmp_path, keypair):
    _, pub = keypair
    return SublimeKeysClient("test-product", cache_dir=tmp_path, public_key_b64u=_b64u(pub))


def test_activate_writes_cache_on_success(client, fake_transport, lease_factory, tmp_path):
    lease = lease_factory(license_key="LIC-1", machine_id=client.get_machine_id())
    fake_transport.queue_response({
        "valid": True, "message": "Activated", "email": "buyer@example.com",
        "expires_at": None, "lease": lease,
    })

    result = client.activate("LIC-1")

    assert result.valid is True
    assert result.source == "online"
    assert (tmp_path / "lease.json").exists()


def test_verify_uses_cache_with_zero_network_calls_when_valid(client, fake_transport, lease_factory):
    machine_id = client.get_machine_id()
    lease = lease_factory(license_key="LIC-1", machine_id=machine_id)
    fake_transport.queue_response({
        "valid": True, "message": "Activated", "email": "buyer@example.com",
        "expires_at": None, "lease": lease,
    })
    client.activate("LIC-1")
    calls_before = len(fake_transport.calls)

    result = client.verify("LIC-1")

    assert result.valid is True
    assert result.source == "offline_cache"
    assert len(fake_transport.calls) == calls_before  # no new network calls


def test_verify_falls_back_online_when_trust_window_lapsed(client, fake_transport, lease_factory):
    machine_id = client.get_machine_id()
    past = datetime.now(timezone.utc) - timedelta(days=10)
    lease = lease_factory(license_key="LIC-1", machine_id=machine_id,
                           issued_at=past, lease_expires_at=past + timedelta(days=7))
    fake_transport.queue_response({
        "valid": True, "message": "Activated", "email": "buyer@example.com",
        "expires_at": None, "lease": lease,
    })
    client.activate("LIC-1")

    fresh_lease = lease_factory(license_key="LIC-1", machine_id=machine_id)
    fake_transport.queue_response({
        "valid": True, "message": "Valid", "email": "buyer@example.com",
        "expires_at": None, "lease": fresh_lease,
    })
    calls_before = len(fake_transport.calls)

    result = client.verify("LIC-1")

    assert result.source == "online"
    assert len(fake_transport.calls) == calls_before + 1  # forced an online call


def test_revocation_clears_cache_and_stays_invalid_offline(client, fake_transport, lease_factory):
    """The correctness-critical scenario: an online check that comes back
    invalid must clear the cache, so a subsequent fully-offline check
    doesn't resurrect a stale 'valid' from before the revocation."""
    machine_id = client.get_machine_id()
    lease = lease_factory(license_key="LIC-1", machine_id=machine_id)
    fake_transport.queue_response({
        "valid": True, "message": "Activated", "email": "buyer@example.com",
        "expires_at": None, "lease": lease,
    })
    client.activate("LIC-1")

    # Force an online check that simulates server-side revocation.
    past = datetime.now(timezone.utc) - timedelta(days=10)
    expired_lease = lease_factory(license_key="LIC-1", machine_id=machine_id,
                                   issued_at=past, lease_expires_at=past + timedelta(days=7))
    storage.save_lease("test-product", "LIC-1", expired_lease, base=client._cache_base)
    fake_transport.queue_response({
        "valid": False, "message": "Revoked", "email": None, "expires_at": None, "lease": None,
    })
    result = client.verify("LIC-1")
    assert result.valid is False
    assert not (client._cache_base / "lease.json").exists()

    # Now fully offline — must NOT resurrect a stale valid=True.
    fake_transport.go_offline()
    result2 = client.verify("LIC-1")
    assert result2.valid is False
    assert result2.source == "offline_cache_miss"


def test_deactivate_clears_cache(client, fake_transport, lease_factory):
    machine_id = client.get_machine_id()
    lease = lease_factory(license_key="LIC-1", machine_id=machine_id)
    fake_transport.queue_response({
        "valid": True, "message": "Activated", "email": "buyer@example.com",
        "expires_at": None, "lease": lease,
    })
    client.activate("LIC-1")
    assert (client._cache_base / "lease.json").exists()

    fake_transport.queue_response({"valid": True, "message": "Deactivated",
                                    "email": None, "expires_at": None, "lease": None})
    client.deactivate("LIC-1")

    assert not (client._cache_base / "lease.json").exists()


def test_activate_network_error_is_distinguishable_from_rejection(client, fake_transport):
    """A network failure on activate() must not be labeled source="online" —
    that reads as "the server was reached and said no", which it wasn't."""
    fake_transport.go_offline()

    result = client.activate("LIC-1")

    assert result.valid is False
    assert result.source == "network_error"


def test_deactivate_network_error_is_distinguishable_from_rejection(client, fake_transport):
    fake_transport.go_offline()

    result = client.deactivate("LIC-1")

    assert result.valid is False
    assert result.source == "network_error"


def test_trial_start_network_error_is_distinguishable_from_no_trial(client, fake_transport):
    fake_transport.go_offline()

    result = client.start_trial()

    assert result.status == "network_error"


def test_trial_status_network_error_is_distinguishable_from_no_trial(client, fake_transport):
    fake_transport.go_offline()

    result = client.trial_status()

    assert result.status == "network_error"


def test_trial_status_falls_back_to_cache_when_offline(client, fake_transport):
    fake_transport.queue_response({
        "status": "active", "days_left": 5, "expires_at": None, "message": "Trial active",
    })
    online_result = client.trial_status()
    assert online_result.source == "online"

    fake_transport.go_offline()
    result = client.trial_status()

    assert result.status == "active"
    assert result.days_left == 5
    assert result.source == "offline_cache"


def test_trial_cache_is_never_locally_recomputed(client, fake_transport):
    """The cached snapshot must be replayed verbatim, not decremented client-
    side — otherwise trial state would trust the local clock again, exactly
    the class of manipulation server-authoritative trials are meant to close."""
    fake_transport.queue_response({
        "status": "active", "days_left": 5, "expires_at": None, "message": "Trial active",
    })
    client.trial_status()

    fake_transport.go_offline()
    first = client.trial_status()
    second = client.trial_status()

    assert first.days_left == second.days_left == 5
