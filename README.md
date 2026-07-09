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
never raise for a normal "not valid" outcome. Network failures are caught
internally too; `verify()` falls back to the offline cache or a
`valid=False, source="offline_cache_miss"` result rather than raising.

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
