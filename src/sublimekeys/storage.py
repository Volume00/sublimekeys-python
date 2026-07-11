"""Local cache for signed leases — one JSON file per product, written
atomically (temp file + os.replace) so a crash mid-write never leaves a
half-written file behind."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def default_cache_dir(product_id: str) -> Path:
    return Path.home() / ".sublimekeys" / product_id


def _lease_path(product_id: str, base: Path | None) -> Path:
    return (base or default_cache_dir(product_id)) / "lease.json"


def _trial_path(product_id: str, base: Path | None) -> Path:
    return (base or default_cache_dir(product_id)) / "trial.json"


def load_lease(product_id: str, base: Path | None = None) -> dict | None:
    path = _lease_path(product_id, base)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload)

    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".sk-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # best-effort — no-op on native Windows ACLs, real on POSIX/WSL


def save_lease(product_id: str, license_key: str, token: str, base: Path | None = None) -> None:
    _atomic_write_json(_lease_path(product_id, base), {"license_key": license_key, "token": token})


def clear_lease(product_id: str, base: Path | None = None) -> None:
    path = _lease_path(product_id, base)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def load_trial(product_id: str, base: Path | None = None) -> dict | None:
    path = _trial_path(product_id, base)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_trial(product_id: str, data: dict, base: Path | None = None) -> None:
    """Caches the last server-confirmed trial snapshot verbatim — never
    locally recomputed or decremented. The client's clock is never trusted
    for trial state; a stale-but-honest snapshot is safer than a
    locally-ticking countdown an offline user could manipulate."""
    _atomic_write_json(_trial_path(product_id, base), data)
