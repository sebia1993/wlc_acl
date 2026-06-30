"""Collect raw command output from WLC devices.

This module is the live-device boundary. Code above this layer should work with
CollectionResult objects instead of calling SSH/Telnet commands directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .aos8_parser import discover_aliases_from_config, discover_roles_from_config
from .config import resolve_credentials
from .models import CollectionResult, CommandOutput, Controller, ControllerCredentials

ProgressCallback = Callable[[str, dict[str, object]], None]


BASE_COMMANDS = (
    ("disable_paging", "no paging"),
    ("clock", "show clock"),
    ("version", "show version"),
    ("configuration_effective", "show configuration effective"),
    ("ip_interface_brief", "show ip interface brief"),
    ("user_table", "show user-table"),
)


def collect_from_controller(
    controller: Controller,
    *,
    timeout: int = 60,
    credentials: ControllerCredentials | None = None,
    progress_callback: ProgressCallback | None = None,
) -> CollectionResult:
    credentials = credentials or resolve_credentials(controller)
    result = CollectionResult(controller=controller)

    try:
        from netmiko import ConnectHandler
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("netmiko is required for live WLC collection") from exc

    # 여기서부터가 실제 장비와 통신하는 유일한 구간입니다.
    # 이후 단계는 CollectionResult에 담긴 텍스트만 보고 동작하게 분리해 둡니다.
    params = _build_connect_params(controller=controller, credentials=credentials, timeout=timeout)

    connection = None
    try:
        _emit(progress_callback, "connect", host=controller.host, protocol=controller.protocol, port=controller.port)
        connection = ConnectHandler(**params)
        _emit(progress_callback, "connect_done", host=controller.host)
        if credentials.enable_password:
            try:
                connection.enable()
                result.commands.append(CommandOutput(command_id="enable", command="enable", output="enable succeeded"))
                _emit(progress_callback, "command_done", command_id="enable", command="enable", output_length=0)
            except Exception as exc:
                result.commands.append(
                    CommandOutput(command_id="enable", command="enable", success=False, error=str(exc))
                )
                _emit(progress_callback, "command_error", command_id="enable", command="enable", error=str(exc))

        # 기본 명령은 보고서 생성에 필요한 최소 입력값입니다.
        # 특히 configuration_effective가 없으면 Role/ACL/Alias 탐색을 계속할 수 없습니다.
        for command_id, command in BASE_COMMANDS:
            _emit(progress_callback, "command_start", command_id=command_id, command=command, timeout=timeout)
            try:
                output = _run_command(connection, command, timeout=timeout)
            except Exception as exc:
                result.commands.append(
                    CommandOutput(command_id=command_id, command=command, success=False, error=str(exc))
                )
                _emit(
                    progress_callback,
                    "command_error",
                    command_id=command_id,
                    command=command,
                    error=str(exc),
                )
                if command_id == "configuration_effective":
                    return result
                continue

            result.commands.append(CommandOutput(command_id=command_id, command=command, output=output))
            _emit(
                progress_callback,
                "command_done",
                command_id=command_id,
                command=command,
                output_length=len(output),
            )

        config_output = result.command_output("configuration_effective")
        if not config_output:
            _emit(
                progress_callback,
                "command_error",
                command_id="configuration_effective",
                command="show configuration effective",
                error="No output was collected.",
            )
            return result

        # 설정 안에서 alias 이름만 먼저 찾고, 각 alias의 실제 host/network/range는 추가 명령으로 보강합니다.
        aliases = discover_aliases_from_config(config_output)
        _emit(progress_callback, "aliases_discovered", total=len(aliases))
        for index, alias in enumerate(aliases, start=1):
            command = f'show netdestination "{alias}"' if " " in alias else f"show netdestination {alias}"
            _emit(
                progress_callback,
                "command_start",
                command_id=f"netdestination::{alias}",
                command=command,
                alias=alias,
                index=index,
                total=len(aliases),
                timeout=timeout,
            )
            try:
                output = _run_command(connection, command, timeout=timeout)
                result.commands.append(
                    CommandOutput(command_id=f"netdestination::{alias}", command=command, output=output)
                )
                _emit(
                    progress_callback,
                    "command_done",
                    command_id=f"netdestination::{alias}",
                    command=command,
                    alias=alias,
                    index=index,
                    total=len(aliases),
                    output_length=len(output),
                )
            except Exception as exc:
                result.commands.append(
                    CommandOutput(
                        command_id=f"netdestination::{alias}",
                        command=command,
                        success=False,
                        error=str(exc),
                    )
                )
                _emit(
                    progress_callback,
                    "command_error",
                    command_id=f"netdestination::{alias}",
                    command=command,
                    alias=alias,
                    index=index,
                    total=len(aliases),
                    error=str(exc),
                )

        # Role 이름도 설정에서 먼저 찾은 뒤 show rights로 실제 적용 ACL을 보강합니다.
        roles = discover_roles_from_config(config_output)
        _emit(progress_callback, "roles_discovered", total=len(roles))
        for index, role in enumerate(roles, start=1):
            command = f'show rights "{role}"' if " " in role else f"show rights {role}"
            _emit(
                progress_callback,
                "command_start",
                command_id=f"rights::{role}",
                command=command,
                role=role,
                index=index,
                total=len(roles),
                timeout=timeout,
            )
            try:
                output = _run_command(connection, command, timeout=timeout)
                result.commands.append(
                    CommandOutput(command_id=f"rights::{role}", command=command, output=output)
                )
                _emit(
                    progress_callback,
                    "command_done",
                    command_id=f"rights::{role}",
                    command=command,
                    role=role,
                    index=index,
                    total=len(roles),
                    output_length=len(output),
                )
            except Exception as exc:
                result.commands.append(
                    CommandOutput(
                        command_id=f"rights::{role}",
                        command=command,
                        success=False,
                        error=str(exc),
                    )
                )
                _emit(
                    progress_callback,
                    "command_error",
                    command_id=f"rights::{role}",
                    command=command,
                    role=role,
                    index=index,
                    total=len(roles),
                    error=str(exc),
                )
        _emit(progress_callback, "complete", command_count=len(result.commands))
    except Exception as exc:
        result.commands.append(
            CommandOutput(
                command_id="connect",
                command="connect",
                success=False,
                error=str(exc),
            )
        )
        _emit(progress_callback, "command_error", command_id="connect", command="connect", error=str(exc))
    finally:
        if connection is not None:
            try:
                connection.disconnect()
            except Exception:
                pass
    return result


def collect_from_offline_raw(controller: Controller, raw_root: Path) -> CollectionResult:
    # 실제 장비 없이 테스트할 때 쓰는 경로입니다.
    # tests/fixtures처럼 저장된 명령 결과 파일을 CollectionResult로 바꿔 파서/리포트를 검증합니다.
    controller_dir = raw_root / controller.name
    result = CollectionResult(controller=controller)

    config_path = controller_dir / "show_configuration_effective.txt"
    if not config_path.exists():
        result.commands.append(
            CommandOutput(
                command_id="configuration_effective",
                command="show configuration effective",
                success=False,
                error=f"missing offline raw file: {config_path}",
            )
        )
        return result

    config_output = config_path.read_text(encoding="utf-8-sig")
    result.commands.extend(
        [
            CommandOutput(
                command_id="configuration_effective",
                command="show configuration effective",
                output=config_output,
            )
        ]
    )

    for command_id, command, filename in (
        ("ip_interface_brief", "show ip interface brief", "show_ip_interface_brief.txt"),
        ("user_table", "show user-table", "show_user_table.txt"),
    ):
        path = controller_dir / filename
        if path.exists():
            result.commands.append(
                CommandOutput(
                    command_id=command_id,
                    command=command,
                    output=path.read_text(encoding="utf-8-sig"),
                )
            )

    for role in discover_roles_from_config(config_output):
        rights_path = controller_dir / f"show_rights__{_safe_role_file_name(role)}.txt"
        if rights_path.exists():
            result.commands.append(
                CommandOutput(
                    command_id=f"rights::{role}",
                    command=f"show rights {role}",
                    output=rights_path.read_text(encoding="utf-8-sig"),
                )
            )
    for alias in discover_aliases_from_config(config_output):
        alias_path = controller_dir / f"show_netdestination__{_safe_role_file_name(alias)}.txt"
        if alias_path.exists():
            result.commands.append(
                CommandOutput(
                    command_id=f"netdestination::{alias}",
                    command=f"show netdestination {alias}",
                    output=alias_path.read_text(encoding="utf-8-sig"),
                )
            )
    return result


def _run_command(connection, command: str, *, timeout: int) -> str:
    return connection.send_command_timing(
        command_string=command,
        strip_prompt=False,
        strip_command=False,
        cmd_verify=False,
        read_timeout=timeout,
    )


def _build_connect_params(
    *,
    controller: Controller,
    credentials: ControllerCredentials,
    timeout: int,
) -> dict:
    return {
        "device_type": controller.device_type,
        "host": controller.host,
        "port": controller.port,
        "username": credentials.username,
        "password": credentials.password,
        "secret": credentials.enable_password or None,
        "timeout": timeout,
        "conn_timeout": timeout,
        "auth_timeout": timeout,
        "banner_timeout": timeout,
        "fast_cli": False,
    }


def _emit(callback: ProgressCallback | None, event: str, **payload: object) -> None:
    if callback is not None:
        callback(event, payload)


def _safe_role_file_name(role: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in role)
