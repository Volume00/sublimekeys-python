"""A stable per-install machine identifier.

Deliberately a persisted random UUID, not a hardware fingerprint. Real
hardware IDs (MAC addresses, disk serials, ...) are spoofable, change on
VMs/cloud desktops/Apple Silicon Rosetta in ways that generate false
mismatches and support tickets, and buy little real security over a
persisted UUID for this use case. Trivially resettable by deleting one
file — that's a known, accepted tradeoff (a soft deterrent, not DRM),
not an oversight.
"""

import uuid
from pathlib import Path

from .storage import default_cache_dir


def get_or_create_machine_id(product_id: str, base: Path | None = None) -> str:
    path = (base or default_cache_dir(product_id)) / "machine_id"
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    machine_id = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(machine_id, encoding="utf-8")
    return machine_id
