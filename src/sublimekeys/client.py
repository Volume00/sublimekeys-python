"""SublimeKeysClient — the main SDK entry point.

Cache-first, not online-first-with-fallback: after one successful
activate()/verify(), subsequent verify() calls make zero network requests
for as long as the cached lease's trust window is valid (currently 7 days,
set server-side) — that's the actual point of offline leases. A network
call only happens again once the cache is missing, invalid, or its trust
window has lapsed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import _pubkey, storage
from .exceptions import LeaseError, NetworkError
from .http import DEFAULT_BASE_URL, HttpClient
from .lease import _b64u_decode, verify_lease
from .machine import get_or_create_machine_id


@dataclass
class LicenseResult:
    valid: bool
    message: str
    email: str | None = None
    expires_at: str | None = None
    source: str = "online"  # "online" | "offline_cache" | "offline_cache_miss" | "network_error"


@dataclass
class TrialResult:
    status: str  # "active" | "expired" | "none" | "network_error"
    days_left: int = 0
    expires_at: str | None = None
    message: str = ""
    source: str = "online"  # "online" | "offline_cache" | "network_error"


class SublimeKeysClient:
    def __init__(
        self,
        product_id: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        cache_dir: Path | None = None,
        public_key_b64u: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        backoff_base: float = 0.5,
    ):
        self.product_id = product_id
        self._http = HttpClient(
            base_url=base_url, timeout=timeout,
            max_retries=max_retries, backoff_base=backoff_base,
        )
        self._cache_base = Path(cache_dir) if cache_dir else None
        self._public_key_bytes = _b64u_decode(public_key_b64u or _pubkey.PUBLIC_KEY_B64U)

    def get_machine_id(self) -> str:
        """Returns a stable, persisted-locally machine identifier —
        generated once on first call, reused after that."""
        return get_or_create_machine_id(self.product_id, base=self._cache_base)

    def activate(self, license_key: str, machine_id: str | None = None) -> LicenseResult:
        """First run for this license on this machine. Always goes online —
        activation is inherently server-side state. Safe to call again on
        a machine that's already activated (the server treats it as a
        no-op that doesn't consume another activation slot)."""
        machine_id = machine_id or self.get_machine_id()
        try:
            data = self._http.post_json("/activate", {
                "license_key": license_key,
                "machine_id": machine_id,
                "product_id": self.product_id,
            })
        except NetworkError as e:
            return LicenseResult(valid=False, message=f"Network error: {e}", source="network_error")

        result = LicenseResult(
            valid=data["valid"], message=data["message"],
            email=data.get("email"), expires_at=data.get("expires_at"), source="online",
        )
        if result.valid and data.get("lease"):
            storage.save_lease(self.product_id, license_key, data["lease"], base=self._cache_base)
        return result

    def verify(
        self,
        license_key: str,
        machine_id: str | None = None,
        *,
        allow_offline: bool = True,
        _now: datetime | None = None,
    ) -> LicenseResult:
        """Every launch after the first. Checks the local cached lease first
        (instant, no network) if allow_offline is True; falls back to an
        online /verify call when there's no usable cached lease. Refreshes
        the cache on every successful online check, and clears it on a
        revoked/invalid result so a stale cache never outlives the license
        it was issued for."""
        machine_id = machine_id or self.get_machine_id()

        if allow_offline:
            cached = storage.load_lease(self.product_id, base=self._cache_base)
            if cached and cached.get("license_key") == license_key:
                try:
                    payload = verify_lease(
                        cached["token"], self._public_key_bytes,
                        expected_license_key=license_key,
                        expected_machine_id=machine_id,
                        expected_product_id=self.product_id,
                        now=_now,
                    )
                    return LicenseResult(
                        valid=True, message="Valid (offline)",
                        email=payload.get("email"),
                        expires_at=payload.get("license_expires_at"),
                        source="offline_cache",
                    )
                except LeaseError:
                    pass  # cache unusable — fall through to an online check

        try:
            data = self._http.post_json("/verify", {
                "license_key": license_key,
                "machine_id": machine_id,
                "product_id": self.product_id,
            })
        except NetworkError:
            return LicenseResult(
                valid=False, message="Offline and no valid cached lease",
                source="offline_cache_miss",
            )

        result = LicenseResult(
            valid=data["valid"], message=data["message"],
            email=data.get("email"), expires_at=data.get("expires_at"), source="online",
        )
        if result.valid and data.get("lease"):
            storage.save_lease(self.product_id, license_key, data["lease"], base=self._cache_base)
        elif not result.valid:
            # Don't leave a stale cache behind — a license revoked server-side
            # must not keep offline-verifying as valid for days afterward.
            storage.clear_lease(self.product_id, base=self._cache_base)
        return result

    def deactivate(self, license_key: str, machine_id: str | None = None) -> LicenseResult:
        """User signs out / uninstalls. Clears the local cache immediately —
        otherwise a deliberately-deactivated license would keep
        offline-verifying as valid until its trust window lapsed."""
        machine_id = machine_id or self.get_machine_id()
        try:
            data = self._http.post_json("/deactivate", {
                "license_key": license_key,
                "machine_id": machine_id,
                "product_id": self.product_id,
            })
        except NetworkError as e:
            return LicenseResult(valid=False, message=f"Network error: {e}", source="network_error")

        storage.clear_lease(self.product_id, base=self._cache_base)
        return LicenseResult(valid=data["valid"], message=data["message"], source="online")

    def start_trial(self, machine_id: str | None = None) -> TrialResult:
        """Get-or-create a trial for this machine. Idempotent server-side —
        reinstalling never resets the clock."""
        return self._trial_call("/trial/start", machine_id)

    def trial_status(self, machine_id: str | None = None) -> TrialResult:
        """Read-only trial check — never starts one. Offline-tolerant: if a
        network call fails, falls back to the last server-confirmed trial
        snapshot (source="offline_cache") instead of just failing — the
        snapshot is never locally recomputed, so an offline user can't
        extend a trial by manipulating their system clock."""
        return self._trial_call("/trial/status", machine_id)

    def _trial_call(self, path: str, machine_id: str | None) -> TrialResult:
        machine_id = machine_id or self.get_machine_id()
        try:
            data = self._http.post_json(path, {
                "machine_id": machine_id, "product_id": self.product_id,
            })
        except NetworkError as e:
            cached = storage.load_trial(self.product_id, base=self._cache_base)
            if cached:
                return TrialResult(
                    status=cached["status"], days_left=cached.get("days_left", 0),
                    expires_at=cached.get("expires_at"), message=cached.get("message", ""),
                    source="offline_cache",
                )
            return TrialResult(status="network_error", message=f"Network error: {e}",
                                source="network_error")

        result = TrialResult(
            status=data["status"], days_left=data.get("days_left", 0),
            expires_at=data.get("expires_at"), message=data.get("message", ""),
            source="online",
        )
        storage.save_trial(self.product_id, {
            "status": result.status, "days_left": result.days_left,
            "expires_at": result.expires_at, "message": result.message,
        }, base=self._cache_base)
        return result
