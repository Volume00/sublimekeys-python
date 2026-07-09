# Changelog

## 0.1.0 — 2026-07-09

Initial release.

- `SublimeKeysClient`: `activate`, `verify`, `deactivate`, `start_trial`, `trial_status`, `get_machine_id`
- Offline-capable `verify()` via Ed25519-signed leases — cached locally, verified with no network call, transparent fallback to the API once the 7-day trust window lapses
- Zero required dependencies beyond `cryptography`
