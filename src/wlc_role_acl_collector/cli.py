from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .collector import collect_from_controller, collect_from_offline_raw
from .config import load_controllers
from .diagnostic_mode import run_diagnostic
from .interactive import prompt_controller_targets
from .mock_server import run_mock_server
from .models import ControllerTarget
from .report import build_parsed_controllers, create_run_dir, write_raw_result, write_reports
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

    diagnose_parser = subparsers.add_parser("diagnose", help="Run field diagnostics without saving raw output")
    diagnose_parser.add_argument("--controllers", type=Path, help="controllers CSV path")
    diagnose_parser.add_argument("--output-dir", default=Path("outputs"), type=Path, help="diagnostic output root")
    diagnose_parser.add_argument("--timeout", default=60, type=int, help="per-command timeout seconds")
    diagnose_parser.add_argument(
        "--offline-raw-dir",
        type=Path,
        default=None,
        help="read offline raw fixture data for local diagnostic testing",
    )

    mock_parser = subparsers.add_parser("mock-server", help="Start a local synthetic WLC SSH/Telnet mock server")
    mock_parser.add_argument("--protocol", choices=("ssh", "telnet"), default="telnet")
    mock_parser.add_argument(
        "--scenario",
        type=Path,
        default=Path("config/mock_scenarios/success_minimal.json"),
        help="mock scenario JSON file",
    )
    mock_parser.add_argument("--host", default="127.0.0.1", help="local listen address")
    mock_parser.add_argument("--port", type=int, default=0, help="local listen port; 0 selects a free port")

    args = parser.parse_args(argv)
    if args.command == "collect":
        return _collect(args)
    if args.command == "diagnose":
        return _diagnose(args)
    if args.command == "mock-server":
        run_mock_server(args.protocol, args.scenario, host=args.host, port=args.port)
        return 0
    return 2


def _collect(args: argparse.Namespace) -> int:
    try:
        local_role_networks = load_role_network_definitions(args.role_networks) if args.role_networks else []
    except RoleNetworkDefinitionError as exc:
        print(f"Role network Excel error: {exc}", file=sys.stderr)
        return 2

    targets = _resolve_targets(args)
    run_dir = create_run_dir(args.output_dir)
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


def _diagnose(args: argparse.Namespace) -> int:
    targets = _resolve_targets(args)
    exit_code = 0
    for target in targets:
        diagnostic = run_diagnostic(
            target,
            output_root=args.output_dir,
            timeout=args.timeout,
            offline_raw_dir=args.offline_raw_dir,
        )
        print(f"Diagnostic output directory: {diagnostic.run_dir}")
        print(f"Primary code: {diagnostic.primary_code}")
        print(f"Diagnostic JSON: {diagnostic.report_paths['json']}")
        print(f"Diagnostic HTML: {diagnostic.report_paths['html']}")
        if diagnostic.primary_code != "OK":
            exit_code = 1
    return exit_code
