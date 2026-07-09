"""Offline verification of SublimeKeys signed leases.

A lease is a compact token: base64url(json_payload) + "." + base64url(signature),
signed with Ed25519 by the SublimeKeys license server. Verifying it locally
requires no network call, which is the entire point of this module.
"""

import base64
import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .exceptions import LeaseError


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_lease(
    token: str,
    public_key_bytes: bytes,
    *,
    expected_license_key: str,
    expected_machine_id: str,
    expected_product_id: str,
    now: datetime | None = None,
) -> dict:
    """Verify a lease token and return its payload dict if valid.

    Raises LeaseError for any failure — malformed token, bad signature,
    wrong license/machine/product, or an expired trust window/license.
    A valid signature only proves "SublimeKeys signed this", not "this is
    for the product/machine/license you expect" — the three equality
    checks below are not optional and cannot be skipped by a caller.
    """
    try:
        payload_b64, sig_b64 = token.split(".")
        payload_bytes = _b64u_decode(payload_b64)
        sig_bytes = _b64u_decode(sig_b64)
    except (ValueError, Exception) as e:
        raise LeaseError(f"malformed lease token: {e}")

    public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    try:
        # Verify the signature BEFORE parsing the payload as JSON — never
        # hand unauthenticated bytes to a parser first, even a safe one.
        public_key.verify(sig_bytes, payload_bytes)
    except InvalidSignature:
        raise LeaseError("invalid lease signature")

    payload = json.loads(payload_bytes)

    if payload.get("license_key") != expected_license_key:
        raise LeaseError("lease license_key does not match")
    if payload.get("machine_id") != expected_machine_id:
        raise LeaseError("lease machine_id does not match")
    if payload.get("product_id") != expected_product_id:
        raise LeaseError("lease product_id does not match")

    now = now or datetime.now(timezone.utc)

    lease_expires_at = payload.get("lease_expires_at")
    if not lease_expires_at or now >= datetime.fromisoformat(lease_expires_at):
        raise LeaseError("lease trust window has lapsed")

    license_expires_at = payload.get("license_expires_at")
    if license_expires_at and now >= datetime.fromisoformat(license_expires_at):
        raise LeaseError("license has expired")

    return payload
