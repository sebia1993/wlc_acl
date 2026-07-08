"""Streamlit-facing collection workflow without Streamlit imports.

The web UI should stay thin: this module owns temporary file handling, report
generation, preview rows, and downloadable bytes so it can be tested without a
browser or a live WLC.
"""

from __future__ import annotations

import csv
import io
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .collector import collect_from_controller, collect_from_offline_raw
from .config import default_device_type_for_protocol
from .diagnostics import summarize_collection_failure
from .models import CollectionResult, Controller, ControllerCredentials, ParsedController
from .report import build_parsed_controllers, create_run_dir, write_raw_result, write_reports
from .role_networks import RoleNetworkLoadSummary, load_role_network_definitions_with_summary

ProgressCallback = Callable[[str, dict[str, object]], None]


@dataclass(frozen=True)
class WebCollectionRequest:
    host: str
    username: str
    password: str
    controller_name: str = ""
    protocol: str = "ssh"
    port: int = 22
    enable_password: str = ""
    timeout: int = 60
    role_networks_filename: str = ""
    role_networks_bytes: bytes | None = None
    export_local_role_networks: bool = True
    offline_raw_dir: Path | None = None


@dataclass(frozen=True)
class WebArtifact:
    filename: str
    data: bytes
    media_type: str


@dataclass(frozen=True)
class WebCollectionResult:
    success: bool
    run_id: str
    summary: dict[str, object]
    preview_rows: list[dict[str, object]]
    acl_preview_rows: list[dict[str, object]]
    artifacts: dict[str, WebArtifact] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    error: str = ""


def run_web_collection(
    request: WebCollectionRequest,
    *,
    progress_callback: ProgressCallback | None = None,
) -> WebCollectionResult:
    """Collect WLC data and return browser-downloadable artifacts.

    All on-disk files are written inside a temporary directory. The caller gets
    bytes for downloads, and the temporary directory is removed before return.
    """

    run_id = _new_run_id()
    messages: list[str] = []
    _validate_request(request)

    with tempfile.TemporaryDirectory(prefix="wlc_streamlit_") as temp_root_text:
        temp_root = Path(temp_root_text)
        controller = _build_controller(request)
        credentials = ControllerCredentials(
            username=request.username,
            password=request.password,
            enable_password=request.enable_password,
        )
        run_dir = create_run_dir(temp_root, label=f"{controller.name}_{run_id}")
        role_network_summary = _load_uploaded_role_networks(request, temp_root)
        local_role_networks = role_network_summary.definitions if role_network_summary else []
        if role_network_summary:
            messages.append(
                "Role network Excel loaded: "
                f"{role_network_summary.network_count} network row(s), "
                f"sheet={role_network_summary.sheet_name or 'unknown'}"
            )
            if role_network_summary.sheet_notice:
                messages.append(role_network_summary.sheet_notice)

        result = _collect(
            controller,
            credentials,
            request=request,
            progress_callback=progress_callback,
        )
        write_raw_result(result, run_dir / "raw")

        if not result.command_output("configuration_effective"):
            failure = summarize_collection_failure(result)
            return WebCollectionResult(
                success=False,
                run_id=run_id,
                summary=_build_failure_summary(result, role_network_summary),
                preview_rows=[],
                acl_preview_rows=[],
                messages=messages,
                error=failure.as_text(),
            )

        parsed = build_parsed_controllers([result])
        files = write_reports(
            parsed_controllers=parsed,
            collection_results=[result],
            output_dir=run_dir,
            local_role_networks=local_role_networks,
            export_local_role_networks=bool(local_role_networks) and request.export_local_role_networks,
            access_history_enabled=False,
        )
        preview_rows = _build_ssid_preview_rows(parsed)
        acl_preview_rows = _build_acl_preview_rows(parsed)
        artifacts = _build_artifacts(run_id, files, preview_rows)
        return WebCollectionResult(
            success=True,
            run_id=run_id,
            summary=_build_success_summary(result, parsed, role_network_summary),
            preview_rows=preview_rows,
            acl_preview_rows=acl_preview_rows,
            artifacts=artifacts,
            messages=messages,
        )


def format_web_progress(event: str, payload: dict[str, object]) -> tuple[str, str]:
    command = str(payload.get("command") or "")
    command_id = str(payload.get("command_id") or "")
    role = str(payload.get("role") or "")
    alias = str(payload.get("alias") or "")
    index = payload.get("index")
    total = payload.get("total")

    if event == "connect":
        return "접속 중", f"CONNECT {payload.get('host', '')} ({payload.get('protocol', '')}:{payload.get('port', '')})"
    if event == "connect_done":
        return "로그인 성공", f"CONNECT OK {payload.get('host', '')}"
    if event == "command_start":
        target = alias or role or command
        progress = f" {index}/{total}" if index and total else ""
        return "명령 실행 중", f"START{progress} {command_id}: {target}"
    if event == "command_done":
        target = alias or role or command
        return "명령 완료", f"DONE {command_id}: {target}"
    if event == "command_error":
        target = alias or role or command or command_id
        return "명령 실패", f"ERROR {command_id}: {target} - {payload.get('error', '')}"
    if event == "aliases_discovered":
        return "Alias 발견", f"ALIASES {payload.get('total', 0)}"
    if event == "roles_discovered":
        return "Role 발견", f"ROLES {payload.get('total', 0)}"
    if event == "complete":
        return "수집 완료", f"COMMANDS COMPLETE {payload.get('command_count', 0)}"
    return "", ""


def _validate_request(request: WebCollectionRequest) -> None:
    protocol = request.protocol.strip().lower()
    if not request.host.strip():
        raise ValueError("WLC IP 또는 Host를 입력하세요.")
    if protocol not in {"ssh", "telnet"}:
        raise ValueError("Protocol은 ssh 또는 telnet이어야 합니다.")
    if not 1 <= int(request.port) <= 65535:
        raise ValueError("Port는 1에서 65535 사이여야 합니다.")
    if int(request.timeout) < 5:
        raise ValueError("Timeout은 5초 이상이어야 합니다.")
    if not request.offline_raw_dir:
        if not request.username.strip():
            raise ValueError("Username을 입력하세요.")
        if not request.password:
            raise ValueError("Password를 입력하세요.")


def _build_controller(request: WebCollectionRequest) -> Controller:
    name = request.controller_name.strip() or f"wlc-{request.host.strip()}"
    protocol = request.protocol.strip().lower() or "ssh"
    return Controller(
        name=name,
        host=request.host.strip(),
        protocol=protocol,
        port=int(request.port),
        device_type=default_device_type_for_protocol(protocol),
    )


def _load_uploaded_role_networks(
    request: WebCollectionRequest,
    temp_root: Path,
) -> RoleNetworkLoadSummary | None:
    if not request.role_networks_bytes:
        return None
    suffix = Path(request.role_networks_filename or "role_networks.xlsx").suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        suffix = ".xlsx"
    upload_path = temp_root / f"role_networks_{uuid.uuid4().hex[:8]}{suffix}"
    upload_path.write_bytes(request.role_networks_bytes)
    return load_role_network_definitions_with_summary(upload_path)


def _collect(
    controller: Controller,
    credentials: ControllerCredentials,
    *,
    request: WebCollectionRequest,
    progress_callback: ProgressCallback | None,
) -> CollectionResult:
    if request.offline_raw_dir:
        if progress_callback:
            progress_callback("command_start", {"command_id": "offline_raw", "command": "offline raw fixture"})
        result = collect_from_offline_raw(controller, request.offline_raw_dir)
        if progress_callback:
            progress_callback("complete", {"command_count": len(result.commands)})
        return result
    return collect_from_controller(
        controller,
        timeout=int(request.timeout),
        credentials=credentials,
        progress_callback=progress_callback,
    )


def _build_success_summary(
    result: CollectionResult,
    parsed: list[ParsedController],
    role_network_summary: RoleNetworkLoadSummary | None,
) -> dict[str, object]:
    ssid_count = sum(len(item.ssid_role_mappings) for item in parsed)
    role_count = sum(len(item.role_policies) for item in parsed)
    acl_rule_count = sum(len(policy.rules) for item in parsed for policy in item.role_policies.values())
    alias_count = sum(len(item.netdestination_aliases) for item in parsed)
    failed_commands = [command.command_id for command in result.commands if not command.success]
    return {
        "controller": result.controller.name,
        "host": result.controller.host,
        "ssid_count": ssid_count,
        "role_count": role_count,
        "acl_rule_count": acl_rule_count,
        "alias_count": alias_count,
        "failed_command_count": len(failed_commands),
        "failed_commands": ", ".join(failed_commands),
        "role_network_rows": role_network_summary.network_count if role_network_summary else 0,
    }


def _build_failure_summary(
    result: CollectionResult,
    role_network_summary: RoleNetworkLoadSummary | None,
) -> dict[str, object]:
    failed_commands = [command.command_id for command in result.commands if not command.success]
    return {
        "controller": result.controller.name,
        "host": result.controller.host,
        "failed_command_count": len(failed_commands),
        "failed_commands": ", ".join(failed_commands),
        "role_network_rows": role_network_summary.network_count if role_network_summary else 0,
    }


def _build_ssid_preview_rows(parsed: list[ParsedController]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in parsed:
        for mapping in item.ssid_role_mappings:
            rows.append(
                {
                    "controller": mapping.controller,
                    "ssid": mapping.ssid,
                    "ap_group": mapping.ap_group,
                    "role": mapping.role,
                    "role_type": mapping.role_type,
                    "effective_vlan": mapping.effective_vlan,
                    "role_user_network": mapping.role_user_network,
                    "network_confidence": mapping.network_confidence,
                    "access_summary": mapping.access_summary,
                }
            )
    return rows


def _build_acl_preview_rows(parsed: list[ParsedController]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in parsed:
        for policy in item.role_policies.values():
            for rule in policy.rules:
                rows.append(
                    {
                        "controller": item.controller.name,
                        "role": policy.role,
                        "acl": rule.acl,
                        "sequence": rule.sequence,
                        "action": rule.action,
                        "source": rule.source,
                        "destination": rule.destination,
                        "service": rule.service,
                    }
                )
    return rows


def _build_artifacts(
    run_id: str,
    files: dict[str, Path],
    preview_rows: list[dict[str, object]],
) -> dict[str, WebArtifact]:
    prefix = f"wlc_role_acl_{run_id}"
    return {
        "xlsx": WebArtifact(
            filename=f"{prefix}.xlsx",
            data=files["xlsx"].read_bytes(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        "csv": WebArtifact(
            filename=f"{prefix}_ssid_role_map.csv",
            data=_rows_to_csv_bytes(preview_rows),
            media_type="text/csv",
        ),
        "html": WebArtifact(
            filename=f"{prefix}.html",
            data=files["html"].read_bytes(),
            media_type="text/html",
        ),
    }


def _rows_to_csv_bytes(rows: list[dict[str, object]]) -> bytes:
    headers = [
        "controller",
        "ssid",
        "ap_group",
        "role",
        "role_type",
        "effective_vlan",
        "role_user_network",
        "network_confidence",
        "access_summary",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


def _new_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{stamp}_{uuid.uuid4().hex[:8]}"
