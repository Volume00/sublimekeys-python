"""Command-line interface — `sublimekeys activate/verify/deactivate/...`.

Mainly useful for testing a product's integration from a terminal without
writing a throwaway script, and for shell-scriptable license checks (CI
smoke tests, install scripts). Exit code is 0 for a valid/successful result,
1 for an invalid result, 2 for a usage error (argparse's default).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .client import DEFAULT_BASE_URL, SublimeKeysClient
from .exceptions import SublimeKeysError


def _print_result(result, *, as_json: bool) -> int:
    data = asdict(result)
    if as_json:
        print(json.dumps(data))
    else:
        for key, value in data.items():
            print(f"{key}: {value}")
    return 0 if data.get("valid") or data.get("status") == "active" else 1


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--product", required=True, help="Product ID (slug from the dashboard)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Override the API base URL")
    parser.add_argument("--cache-dir", default=None, help="Override the local lease cache directory")
    parser.add_argument("--machine-id", default=None, help="Override the auto-generated machine ID")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")


def _client_from_args(args: argparse.Namespace) -> SublimeKeysClient:
    return SublimeKeysClient(args.product, base_url=args.base_url, cache_dir=args.cache_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sublimekeys", description="SublimeKeys license CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    activate = sub.add_parser("activate", help="Activate a license key on this machine")
    _add_common_args(activate)
    activate.add_argument("license_key")

    verify = sub.add_parser("verify", help="Verify a license key (offline-first)")
    _add_common_args(verify)
    verify.add_argument("license_key")
    verify.add_argument("--online-only", action="store_true", help="Skip the offline cache, force an API call")

    deactivate = sub.add_parser("deactivate", help="Deactivate a license key on this machine")
    _add_common_args(deactivate)
    deactivate.add_argument("license_key")

    trial_start = sub.add_parser("trial-start", help="Start (or resume) a trial on this machine")
    _add_common_args(trial_start)

    trial_status = sub.add_parser("trial-status", help="Check trial status without starting one")
    _add_common_args(trial_status)

    machine_id = sub.add_parser("machine-id", help="Print this machine's persisted identifier")
    _add_common_args(machine_id)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = _client_from_args(args)

    try:
        if args.command == "activate":
            result = client.activate(args.license_key, machine_id=args.machine_id)
            return _print_result(result, as_json=args.json)

        if args.command == "verify":
            result = client.verify(
                args.license_key, machine_id=args.machine_id,
                allow_offline=not args.online_only,
            )
            return _print_result(result, as_json=args.json)

        if args.command == "deactivate":
            result = client.deactivate(args.license_key, machine_id=args.machine_id)
            return _print_result(result, as_json=args.json)

        if args.command == "trial-start":
            result = client.start_trial(machine_id=args.machine_id)
            return _print_result(result, as_json=args.json)

        if args.command == "trial-status":
            result = client.trial_status(machine_id=args.machine_id)
            return _print_result(result, as_json=args.json)

        if args.command == "machine-id":
            print(client.get_machine_id())
            return 0

    except SublimeKeysError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
