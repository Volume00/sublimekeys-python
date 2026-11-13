# Changelog

## 0.3.1 — unreleased

- Fix: an expiry without a timezone in a lease (e.g. a date-only `"2027-11-13"`) made the offline check raise `TypeError` and crash the host app. Such values are now read as UTC, and an unparseable value fails closed with `LeaseError` (so `verify()` simply asks the server). Covered by new tests.
- README: trial length is now configurable per product (7/14/30 days); new "Time-limited licenses" section; clarified that only *revoked* licenses can take up to 7 days to be noticed offline — an expired one is rejected as soon as its date passes.

## 0.3.0

- Fix: network errors were mislabelled `source="online"`; they now report `source="network_error"`
- New offline trial cache: `trial_status()` replays the last server-confirmed snapshot when the network is unreachable

## 0.2.0 — 2026-07-09

- New `sublimekeys` CLI (installed automatically): `activate`, `verify`, `deactivate`, `trial-start`, `trial-status`, `machine-id`, with `--json` output and shell-friendly exit codes
- HTTP requests now retry transient failures (connection errors, 5xx) with exponential backoff, tunable via `max_retries`/`backoff_base` on `SublimeKeysClient`
- New `ServerError` exception (subclass of `NetworkError`) raised when a 5xx response survives all retries

## 0.1.0 — 2026-07-09

Initial release.

- `SublimeKeysClient`: `activate`, `verify`, `deactivate`, `start_trial`, `trial_status`, `get_machine_id`
- Offline-capable `verify()` via Ed25519-signed leases — cached locally, verified with no network call, transparent fallback to the API once the 7-day trust window lapses
- Zero required dependencies beyond `cryptography`
