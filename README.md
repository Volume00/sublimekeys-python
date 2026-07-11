# sublimekeys

Official Python SDK for [SublimeKeys](https://keys.sublimearts.io) — license
key generation, activation, verification and trials for indie desktop apps,
with **offline-capable verification**: once a license is activated, your app
can verify it locally in milliseconds with no network call, for up to 7 days
at a time, before quietly re-syncing online.

```bash
pip install sublimekeys
```

## Quickstart

This mirrors the lifecycle described in the [SublimeKeys docs](https://keys.sublimearts.io/docs):
first run activates, every later run verifies (offline-first), uninstall
deactivates.

```python
from sublimekeys import SublimeKeysClient

client = SublimeKeysClient(product_id="my-app")

# First run — ask the user for their key once.
result = client.activate(license_key=user_entered_key)
if result.valid:
    unlock_full_version()

# Every later launch — offline-first, instant, falls back online
# automatically once the cached lease's 7-day trust window lapses.
result = client.verify(license_key=saved_key)
if result.valid:
    unlock_full_version()
print(result.source)  # "offline_cache" most days, "online" roughly weekly

# Uninstall / sign out.
client.deactivate(license_key=saved_key)
```

`client.get_machine_id()` gives you a stable, locally-persisted identifier if
you need to store it yourself — every method above also generates and caches
one automatically the first time it's needed, so passing it explicitly is
optional.

## Trials

```python
result = client.start_trial()       # get-or-create a 7-day trial; idempotent —
                                     # reinstalling never resets the clock
if result.status == "active":
    print(f"{result.days_left} days left")

result = client.trial_status()      # read-only check, never starts one
```

Trial state lives server-side, keyed to `machine_id` — the server's clock
decides `days_left`, never the client's, so rolling back a machine's system
clock doesn't extend a trial. `trial_status()` still works offline: if the
network call fails, it replays the last server-confirmed snapshot
(`source="offline_cache"`) instead of just failing — but that snapshot is
never locally recomputed or decremented, so it can go stale (frozen at its
last known value) rather than silently trusting the local clock. Falls back
to `status="network_error"` only if there's no cached snapshot yet either
(e.g. the very first check happens offline).

## How offline verification works

When `activate()` or `verify()` succeeds, the server returns a lease — a
small Ed25519-signed token proving "this license is valid for this machine,
as of now." The SDK caches it locally and, on every later `verify()` call,
checks the signature against a **pinned public key built into this package**
— no network call, no dependency on the server being reachable.

The lease itself expires after 7 days (server-controlled). Once it does, the
next `verify()` call transparently goes online, gets a fresh lease, and the
cycle repeats. This means a revoked or expired license can take up to 7 days
to be caught while a machine stays fully offline — an intentional tradeoff
for instant, network-independent checks the rest of the time, not a bug.

## API

| Method | What it does |
|---|---|
| `activate(license_key, machine_id=None)` | First run. Always online. |
| `verify(license_key, machine_id=None, allow_offline=True)` | Every later run. Offline-first by default. |
| `deactivate(license_key, machine_id=None)` | Uninstall/sign-out. Frees the seat, clears the local cache. |
| `start_trial(machine_id=None)` | Get-or-create a trial. |
| `trial_status(machine_id=None)` | Read-only trial check. |
| `get_machine_id()` | Stable per-install identifier (auto-generated, persisted locally). |

All methods return a small dataclass (`LicenseResult` or `TrialResult`) —
never raise for a normal "not valid" outcome. Network failures are retried
automatically with exponential backoff (2 retries by default, tunable via
`SublimeKeysClient(..., max_retries=, backoff_base=)`) before giving up;
`verify()` then falls back to the offline cache or a
`valid=False, source="offline_cache_miss"` result rather than raising.
A 5xx response that survives all retries raises `ServerError` (a
`NetworkError` subclass) instead of the usual dataclass return — the one
case worth distinguishing from an ordinary "not valid" result.

**Don't treat every `valid=False` as "bad license".** A network failure on
`activate()` or `deactivate()` (offline on first run, DNS hiccup, etc.)
still returns a normal dataclass rather than raising — check
`source == "network_error"` to show "no connection, try again" instead of
"invalid license". `verify()` and the trial methods don't need this check
on their own: they already try their local cache first, so a network
failure there only surfaces as `source == "offline_cache_miss"` (`verify()`)
or `status == "network_error"` with no `source == "offline_cache"` fallback
available (trials, first-ever offline check only) once there's truly
nothing usable, cached or online.

## Command-line interface

Installing the package also installs a `sublimekeys` command — handy for
testing an integration from a terminal or in a shell script, without
writing a throwaway Python file:

```bash
sublimekeys activate --product my-app YOUR-LICENSE-KEY
sublimekeys verify --product my-app YOUR-LICENSE-KEY
sublimekeys verify --product my-app --json YOUR-LICENSE-KEY   # machine-readable
sublimekeys trial-status --product my-app
sublimekeys machine-id --product my-app
```

Exit code is `0` for a valid/active result, `1` for invalid, `2` for a
usage error. Run `sublimekeys --help` or `sublimekeys <command> --help`
for the full flag list (`--base-url`, `--cache-dir`, `--machine-id`, `--json`).

## Packaging with PyInstaller

`cryptography`'s compiled backend is the kind of dependency that works fine
under `python app.py` and only breaks in a frozen build. Before shipping:

- `pyinstaller-hooks-contrib` ships an official `hook-cryptography` and is
  usually auto-discovered. If you hit `ModuleNotFoundError: _cffi_backend`,
  add `--collect-all cryptography` (or `--hidden-import=_cffi_backend`) to
  your PyInstaller command.
- **Test the frozen executable's `activate()`/`verify()` calls**, not just
  the unfrozen dev script — this is the single highest-value check before
  shipping to real users.
- On macOS, notarizing a PyInstaller bundle that includes OpenSSL/rust-openssl
  dylibs is a known extra step — sign all bundled dylibs and test the signed,
  notarized build specifically.

See `examples/pyinstaller/` for a minimal buildable example.

## License

MIT
