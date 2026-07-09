import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@pytest.fixture
def keypair():
    """An ephemeral test keypair — never the real production key."""
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )
    return priv, pub_bytes


def make_lease(priv, *, license_key="TEST-KEY", machine_id="test-machine",
                product_id="test-product", email="buyer@example.com",
                license_expires_at=None, issued_at=None, lease_expires_at=None,
                kid="v1"):
    now = issued_at or datetime.now(timezone.utc)
    payload = {
        "kid": kid,
        "license_key": license_key,
        "machine_id": machine_id,
        "product_id": product_id,
        "email": email,
        "license_expires_at": license_expires_at,
        "issued_at": now.isoformat(),
        "lease_expires_at": (lease_expires_at or (now + timedelta(days=7))).isoformat()
            if not isinstance(lease_expires_at, str) else lease_expires_at,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    sig = priv.sign(payload_bytes)
    return f"{_b64u(payload_bytes)}.{_b64u(sig)}"


@pytest.fixture
def lease_factory(keypair):
    priv, _ = keypair
    def _make(**kwargs):
        return make_lease(priv, **kwargs)
    return _make
