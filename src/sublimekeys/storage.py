"""Local cache for signed leases — one JSON file per product, written
atomically (temp file + os.replace) so a crash mid-write never leaves a
half-written file behind."""

import json
import os
import tempfile
from pathlib import Path


def default_cache_dir(product_id: str) -> Path:
    return Path.home() / ".sublimekeys" / product_id


def _lease_path(product_id: str, base: Path | None) -> Path:
    return (base or default_cache_dir(product_id)) / "lease.json"


def load_lease(product_id: str, base: Path | None = None) -> dict | None:
    path = _lease_path(product_id, base)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_lease(product_id: str, license_key: str, token: str, base: Path | None = None) -> None:
    path = _lease_path(product_id, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"license_key": license_key, "token": token})

    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=".lease-", suffix=".tmp")
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


def clear_lease(product_id: str, base: Path | None = None) -> None:
    path = _lease_path(product_id, base)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
