"""Field diagnostic mode.

Diagnostic mode runs the same read-only collection path but writes only safe
stage/code reports. Raw device output remains in memory and is not persisted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .collector import collect_from_controller, collect_from_offline_raw
from .diagnostic_codes import DiagnosticCode, classify_message_to_code, get_diagnostic_code
from .diagnostic_events import DiagnosticEvent, event_from_code, safe_info_event
from .diagnostic_report import write_diagnostic_report
from .models import ControllerTarget
from .redaction import redaction_self_test
from .report import build_parsed_controllers, timestamp_slug


@dataclass(frozen=True)
class DiagnosticRun:
    run_dir: Path
    primary_code: str
    report_paths: dict[str, Path]
    events: list[DiagnosticEvent]


def run_diagnostic(
    target: ControllerTarget,
    *,
    output_root: Path,
    timeout: int = 60,
    offline_raw_dir: Path | None = None,
) -> DiagnosticRun:
    run_dir = output_root / timestamp_slug()
    events: list[DiagnosticEvent] = []

    def finish(code: str | DiagnosticCode) -> DiagnosticRun:
        diagnostic_code = code if isinstance(code, DiagnosticCode) else get_diagnostic_code(code)
        report_paths = write_diagnostic_report(
            run_dir,
            events=events,
            primary_code=diagnostic_code,
            metadata={
                "protocol": target.controller.protocol,
                "port": target.controller.port,
                "timeout_seconds": timeout,
                "offline_raw_mode": bool(offline_raw_dir),
            },
        )
        return DiagnosticRun(
            run_dir=run_dir,
            primary_code=diagnostic_code.code,
            report_paths=report_paths,
            events=events,
        )

    events.append(safe_info_event("DGN-BOOT", "Diagnostic mode started."))
    if not redaction_self_test():
        events.append(event_from_code("WLC-SEC-001"))
        return finish("WLC-SEC-001")

    input_error = _validate_input(target, timeout)
    if input_error:
        events.append(event_from_code("WLC-INP-001", detail=input_error))
        return finish("WLC-INP-001")
    events.append(safe_info_event("DGN-INPUT", "Diagnostic inputs validated."))

    def progress(event: str, payload: dict[str, object]) -> None:
        command_id = str(payload.get("command_id", ""))
        if event == "connect":
            events.append(safe_info_event("DGN-NET", "Connection attempt started."))
        elif event == "connect_done":
            events.append(safe_info_event("DGN-AUTH", "Login succeeded."))
        elif event == "command_start":
            events.append(safe_info_event("DGN-CMD", "Command started.", command_id=command_id))
        elif event == "command_done":
            events.append(safe_info_event("DGN-CMD", "Command completed.", command_id=command_id))
        elif event == "command_error":
            code = classify_message_to_code(str(payload.get("error", "")), command_id=command_id)
            events.append(event_from_code(code, command_id=command_id, detail=str(payload.get("error", ""))))
        elif event in {"roles_discovered", "aliases_discovered"}:
            events.append(safe_info_event("DGN-PARSE", f"{event.replace('_', ' ').title()}."))

    if offline_raw_dir:
        events.append(safe_info_event("DGN-MOCK", "Offline raw diagnostic input selected."))
        result = collect_from_offline_raw(target.controller, offline_raw_dir)
    else:
        result = collect_from_controller(
            target.controller,
            timeout=timeout,
            credentials=target.credentials,
            progress_callback=progress,
        )

    config_output = result.command_output("configuration_effective")
    if _configuration_output_rejected(config_output):
        events.append(event_from_code("WLC-CMD-003", command_id="configuration_effective"))
        return finish("WLC-CMD-003")
    if not config_output:
        code = _code_for_collection_result(result)
        events.append(event_from_code(code, command_id="configuration_effective"))
        return finish(code)

    try:
        parsed = build_parsed_controllers([result])
    except Exception as exc:
        events.append(event_from_code("WLC-PRS-001", detail=str(exc)))
        return finish("WLC-PRS-001")

    unresolved_count = sum(len(item.unresolved) for item in parsed)
    if unresolved_count:
        events.append(
            event_from_code(
                "WLC-PRS-002",
                status="warning",
                detail=f"Unresolved parser entries: {unresolved_count}",
            )
        )
    else:
        events.append(safe_info_event("DGN-PARSE", "Configuration parsed successfully."))

    events.append(safe_info_event("DGN-REPORT", "Safe diagnostic report generated."))
    return finish("OK")


def _validate_input(target: ControllerTarget, timeout: int) -> str:
    if target.controller.protocol not in {"ssh", "telnet"}:
        return "Protocol must be ssh or telnet."
    if not 1 <= int(target.controller.port) <= 65535:
        return "Port must be between 1 and 65535."
    if timeout < 5:
        return "Timeout must be at least 5 seconds."
    if not str(target.controller.host).strip():
        return "WLC address is required."
    return ""


def _code_for_collection_result(result) -> DiagnosticCode:
    failed_commands = [command for command in result.commands if command.error]
    for command in failed_commands:
        code = classify_message_to_code(command.error, command_id=command.command_id)
        if code.code != "WLC-UNK-001":
            return code
    return get_diagnostic_code("WLC-CMD-001")


def _configuration_output_rejected(output: str) -> bool:
    normalized = (output or "").casefold()
    return any(token in normalized for token in ("permission denied", "invalid input", "not authorized"))
