from datetime import datetime, timedelta, timezone

import pytest

from sublimekeys.exceptions import LeaseError
from sublimekeys.lease import verify_lease


def test_accepts_a_fresh_valid_token(keypair, lease_factory):
    priv, pub = keypair
    token = lease_factory()
    payload = verify_lease(
        token, pub,
        expected_license_key="TEST-KEY", expected_machine_id="test-machine",
        expected_product_id="test-product",
    )
    assert payload["license_key"] == "TEST-KEY"


def test_rejects_tampered_payload(keypair, lease_factory):
    _, pub = keypair
    token = lease_factory()
    payload_b64, sig_b64 = token.split(".")
    tampered = payload_b64[:-1] + ("A" if payload_b64[-1] != "A" else "B") + "." + sig_b64
    with pytest.raises(LeaseError):
        verify_lease(tampered, pub, expected_license_key="TEST-KEY",
                      expected_machine_id="test-machine", expected_product_id="test-product")


def test_rejects_tampered_signature(keypair, lease_factory):
    _, pub = keypair
    token = lease_factory()
    payload_b64, sig_b64 = token.split(".")
    tampered = payload_b64 + "." + (sig_b64[:-1] + ("A" if sig_b64[-1] != "A" else "B"))
    with pytest.raises(LeaseError):
        verify_lease(tampered, pub, expected_license_key="TEST-KEY",
                      expected_machine_id="test-machine", expected_product_id="test-product")


def test_rejects_lapsed_trust_window(keypair, lease_factory):
    _, pub = keypair
    past = datetime.now(timezone.utc) - timedelta(days=10)
    token = lease_factory(issued_at=past, lease_expires_at=past + timedelta(days=7))
    with pytest.raises(LeaseError, match="trust window"):
        verify_lease(token, pub, expected_license_key="TEST-KEY",
                      expected_machine_id="test-machine", expected_product_id="test-product")


def test_rejects_expired_license(keypair, lease_factory):
    _, pub = keypair
    past_expiry = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    token = lease_factory(license_expires_at=past_expiry)
    with pytest.raises(LeaseError, match="expired"):
        verify_lease(token, pub, expected_license_key="TEST-KEY",
                      expected_machine_id="test-machine", expected_product_id="test-product")


@pytest.mark.parametrize("field,expected", [
    ("expected_license_key", "WRONG-KEY"),
    ("expected_machine_id", "wrong-machine"),
    ("expected_product_id", "wrong-product"),
])
def test_rejects_mismatched_claims(keypair, lease_factory, field, expected):
    _, pub = keypair
    token = lease_factory()
    kwargs = {
        "expected_license_key": "TEST-KEY",
        "expected_machine_id": "test-machine",
        "expected_product_id": "test-product",
    }
    kwargs[field] = expected
    with pytest.raises(LeaseError):
        verify_lease(token, pub, **kwargs)


@pytest.mark.parametrize("malformed", [
    "not-a-valid-token",
    "only.one.dot.too.many",
    "!!!invalid-base64!!!.also-invalid",
])
def test_rejects_malformed_tokens(keypair, malformed):
    _, pub = keypair
    with pytest.raises(LeaseError):
        verify_lease(malformed, pub, expected_license_key="TEST-KEY",
                      expected_machine_id="test-machine", expected_product_id="test-product")


def test_wrong_public_key_is_rejected(keypair, lease_factory):
    """A lease signed by one key must not verify against a different key —
    this is the core guarantee the whole feature rests on."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    token = lease_factory()
    other_priv = Ed25519PrivateKey.generate()
    other_pub = other_priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    )
    with pytest.raises(LeaseError):
        verify_lease(token, other_pub, expected_license_key="TEST-KEY",
                      expected_machine_id="test-machine", expected_product_id="test-product")
