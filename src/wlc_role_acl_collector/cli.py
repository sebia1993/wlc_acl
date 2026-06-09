from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .collector import collect_from_controller, collect_from_offline_raw
from .config import load_controllers
from .interactive import prompt_controller_targets
from .models import ControllerTarget
from .report import build_parsed_controllers, timestamp_slug, write_raw_result, write_reports
from .role_networks import RoleNetworkDefinitionError, load_role_network_definitions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="wlc-role-acl-collector",
        description="Collect Aruba AOS8 WLC SSID, Role, and ACL mappings.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect_parser = subparsers.add_parser("collect", help="Collect data and generate reports")
    collect_parser.add_argument("--controllers", type=Path, help="controllers CSV path")
    collect_parser.add_argument("--output-dir", default=Path("outputs"), type=Path, help="report output root")
    collect_parser.add_argument("--timeout", default=60, type=int, help="per-command timeout seconds")
    collect_parser.add_argument(
        "--role-networks",
        type=Path,
        default=None,
        help="optional local Role network mapping Excel file; not exported unless explicitly enabled",
    )
    collect_parser.add_argument(
        "--export-local-role-networks",
        action="store_true",
        help="include local Role network mapping data in generated reports",
    )
    collect_parser.add_argument(
        "--offline-raw-dir",
        type=Path,
        default=None,
        help="read raw command outputs from a fixture directory instead of connecting to WLCs",
    )

    args = parser.parse_args(argv)
    if args.command == "collect":
        return _collect(args)
    return 2


def _collect(args: argparse.Namespace) -> int:
    try:
        local_role_networks = load_role_network_definitions(args.role_networks) if args.role_networks else []
    except RoleNetworkDefinitionError as exc:
        print(f"Role network Excel error: {exc}", file=sys.stderr)
        return 2

    targets = _resolve_targets(args)
    run_dir = args.output_dir / timestamp_slug()
    raw_dir = run_dir / "raw"

    results = []
    for target in targets:
        controller = target.controller
        if args.offline_raw_dir:
            result = collect_from_offline_raw(controller, args.offline_raw_dir)
        else:
            result = collect_from_controller(
                controller,
                timeout=args.timeout,
                credentials=target.credentials,
            )
        write_raw_result(result, raw_dir)
        results.append(result)

    parsed = build_parsed_controllers(results)
    files = write_reports(
        parsed_controllers=parsed,
        collection_results=results,
        output_dir=run_dir,
        local_role_networks=local_role_networks,
        export_local_role_networks=args.export_local_role_networks,
        access_history_enabled=False,
    )
    print(f"Output directory: {run_dir}")
    if local_role_networks and not args.export_local_role_networks:
        print("Role network Excel was loaded for this run only; local networks were not exported.")
    print(f"Excel: {files['xlsx']}")
    print(f"HTML: {files['html']}")
    return 0


def _resolve_targets(args: argparse.Namespace) -> list[ControllerTarget]:
    if args.controllers:
        return [ControllerTarget(controller=controller) for controller in load_controllers(args.controllers)]
    return prompt_controller_targets()
