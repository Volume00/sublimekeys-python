import base64
from datetime import datetime, timedelta, timezone

import pytest

from sublimekeys.exceptions import LeaseError
from sublimekeys.lease import verify_lease


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _flip_first_byte(b64_segment: str) -> str:
    """Flips a bit in the first DECODED byte, then re-encodes. Manipulating
    raw bytes (not the base64 characters) sidesteps a real edge case:
    base64's last character in a partial group can have padding bits that
    don't affect the decoded value, making a naive last-character flip an
    unreliable way to guarantee a changed payload/signature."""
    raw = bytearray(_b64u_decode(b64_segment))
    raw[0] ^= 0xFF
    return _b64u(bytes(raw))


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
    tampered = _flip_first_byte(payload_b64) + "." + sig_b64
    with pytest.raises(LeaseError):
        verify_lease(tampered, pub, expected_license_key="TEST-KEY",
                      expected_machine_id="test-machine", expected_product_id="test-product")


def test_rejects_tampered_signature(keypair, lease_factory):
    _, pub = keypair
    token = lease_factory()
    payload_b64, sig_b64 = token.split(".")
    tampered = payload_b64 + "." + _flip_first_byte(sig_b64)
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


def _verify(token, pub):
    return verify_lease(token, pub, expected_license_key="TEST-KEY",
                         expected_machine_id="test-machine", expected_product_id="test-product")


@pytest.mark.parametrize("expiry", ["2099-01-01", "2099-01-01T23:59:59", "2099-01-01T23:59:59Z"])
def test_accepts_future_expiry_without_timezone(keypair, lease_factory, expiry):
    # A date-only / naive expiry used to raise TypeError ("can't compare
    # offset-naive and offset-aware datetimes"). It is read as UTC now.
    _, pub = keypair
    payload = _verify(lease_factory(license_expires_at=expiry), pub)
    assert payload["license_expires_at"] == expiry


@pytest.mark.parametrize("expiry", ["2000-01-01", "2000-01-01T00:00:00"])
def test_rejects_past_expiry_without_timezone(keypair, lease_factory, expiry):
    _, pub = keypair
    with pytest.raises(LeaseError, match="expired"):
        _verify(lease_factory(license_expires_at=expiry), pub)


def test_malformed_expiry_is_a_lease_error_not_a_crash(keypair, lease_factory):
    # A garbage value must fail closed with LeaseError (which verify() turns
    # into "go online"), never an unhandled ValueError/TypeError in the app.
    _, pub = keypair
    with pytest.raises(LeaseError, match="malformed"):
        _verify(lease_factory(license_expires_at="next year"), pub)


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
