# Changelog

## 0.2.0 — 2026-07-09

- New `sublimekeys` CLI (installed automatically): `activate`, `verify`, `deactivate`, `trial-start`, `trial-status`, `machine-id`, with `--json` output and shell-friendly exit codes
- HTTP requests now retry transient failures (connection errors, 5xx) with exponential backoff, tunable via `max_retries`/`backoff_base` on `SublimeKeysClient`
- New `ServerError` exception (subclass of `NetworkError`) raised when a 5xx response survives all retries

## 0.1.0 — 2026-07-09

Initial release.

- `SublimeKeysClient`: `activate`, `verify`, `deactivate`, `start_trial`, `trial_status`, `get_machine_id`
- Offline-capable `verify()` via Ed25519-signed leases — cached locally, verified with no network call, transparent fallback to the API once the 7-day trust window lapses
- Zero required dependencies beyond `cryptography`
