from wlc_role_acl_collector.gui_app import (
    COLLECTION_ACTION_LABEL,
    DIAGNOSTIC_ACTION_LABEL,
    REPORT_NAME_LABEL,
    STAGE_LABELS,
    STAGE_PROGRESS,
    WLC_IP_LABEL,
    WLC_TARGET_NOTICE,
    _collection_failure_message,
    _constrain_window_rect,
    _log_tag_for_line,
    _write_run_log,
    format_collection_progress,
    format_diagnostic_progress,
)
from wlc_role_acl_collector.diagnostic_events import event_from_code, safe_info_event
from wlc_role_acl_collector.gui_support import (
    GuiConnectionInput,
    build_target_from_gui_input,
    default_gui_output_dir,
)
from wlc_role_acl_collector.models import CollectionResult, CommandOutput
from wlc_role_acl_collector.report import write_raw_result


def test_gui_app_importable():
    import wlc_role_acl_collector.gui_app as gui_app

    assert callable(gui_app.main)


def test_gui_notice_tells_user_to_connect_to_wlc_not_mm():
    assert "Mobility Master(MM)" in WLC_TARGET_NOTICE
    assert "WLC controller IP" in WLC_TARGET_NOTICE
    assert "Hostname" not in WLC_TARGET_NOTICE


def test_gui_connection_labels_do_not_imply_hostname_is_required():
    assert WLC_IP_LABEL == "WLC IP"
    assert REPORT_NAME_LABEL == "Report name (optional)"
    assert "Hostname" not in WLC_IP_LABEL


def test_gui_stage_labels_support_operational_console_flow():
    assert [STAGE_LABELS[key] for key in ("ready", "connecting", "collecting", "reporting", "completed")] == [
        "Ready",
        "Connecting",
        "Collecting",
        "Reporting",
        "Completed",
    ]
    assert STAGE_LABELS["failed"] == "Failed"
    assert STAGE_PROGRESS == {
        "ready": 0,
        "connecting": 20,
        "collecting": 50,
        "reporting": 80,
        "completed": 100,
        "failed": 100,
    }


def test_gui_actions_include_safe_diagnostic_button():
    assert COLLECTION_ACTION_LABEL == "Start Collection"
    assert DIAGNOSTIC_ACTION_LABEL == "Safe Diagnostic"


def test_log_tag_for_line_classifies_operational_log_levels():
    assert _log_tag_for_line("ERROR: Authentication failed") == "error"
    assert _log_tag_for_line("DONE: configuration_effective | show configuration effective | 100 chars") == "success"
    assert _log_tag_for_line("START: rights::corp | show rights corp") == "info"
    assert _log_tag_for_line("DIAG: DGN-CMD | OK") == "info"
    assert _log_tag_for_line("Diagnostic HTML: C:\\temp\\diagnostic_summary.html") == "success"
    assert _log_tag_for_line("WLC IP: 10.10.10.10") == "muted"


def test_default_gui_output_dir_is_documents_folder():
    path = default_gui_output_dir()

    assert path.name == "outputs"
    assert path.parent.name == "WlcRoleAclCollector"


def test_gui_input_builds_ssh_target_defaults():
    target = build_target_from_gui_input(
        GuiConnectionInput(
            host="10.10.10.10",
            username="admin",
            password="secret",
        )
    )

    assert target.controller.name == "wlc-10.10.10.10"
    assert target.controller.protocol == "ssh"
    assert target.controller.port == 22
    assert target.controller.device_type == "aruba_os"
    assert target.credentials.username == "admin"
    assert target.credentials.password == "secret"


def test_gui_input_requires_wlc_ip():
    try:
        build_target_from_gui_input(GuiConnectionInput(host="", username="admin", password="secret"))
    except ValueError as exc:
        assert str(exc) == "WLC IP is required."
    else:
        raise AssertionError("Expected WLC IP validation error")


def test_gui_input_builds_telnet_target_defaults():
    target = build_target_from_gui_input(
        GuiConnectionInput(
            host="10.10.20.10",
            name="outside-wlc",
            protocol="telnet",
            username="admin",
            password="secret",
        )
    )

    assert target.controller.name == "outside-wlc"
    assert target.controller.protocol == "telnet"
    assert target.controller.port == 23
    assert target.controller.device_type == "generic_telnet"


def test_password_not_written_to_raw_result(tmp_path):
    target = build_target_from_gui_input(
        GuiConnectionInput(
            host="10.10.10.10",
            username="admin",
            password="very-secret-password",
            enable_password="enable-secret",
        )
    )
    result = CollectionResult(controller=target.controller)

    raw_path = write_raw_result(result, tmp_path)
    text = raw_path.read_text(encoding="utf-8")

    assert "very-secret-password" not in text
    assert "enable-secret" not in text


def test_write_run_log(tmp_path):
    path = _write_run_log(tmp_path, ["line1", "line2"])

    assert path.name == "run.log"
    assert path.read_text(encoding="utf-8") == "line1\nline2\n"


def test_format_collection_progress_for_role_command():
    status, lines = format_collection_progress(
        "command_start",
        {
            "command_id": "rights::corp-employee",
            "command": "show rights corp-employee",
            "role": "corp-employee",
            "index": 2,
            "total": 5,
            "timeout": 60,
        },
    )

    assert status == "Collecting role 2/5: corp-employee"
    assert lines == ["START: rights::corp-employee | show rights corp-employee"]


def test_constrain_window_rect_keeps_window_inside_monitor_work_area():
    assert _constrain_window_rect(900, 650, 1200, 900, (0, 0, 1000, 700)) == (0, 0, 1000, 700)
    assert _constrain_window_rect(800, 650, 760, 560, (100, 100, 900, 700)) == (140, 140, 760, 560)


def test_collection_failure_message_includes_failed_command_and_run_log(tmp_path):
    result = CollectionResult(controller=build_target_from_gui_input(
        GuiConnectionInput(host="10.10.10.10", username="admin", password="secret")
    ).controller)
    result.commands.append(
        CommandOutput(
            command_id="configuration_effective",
            command="show configuration effective",
            success=False,
            error="Invalid input",
        )
    )
    run_log = tmp_path / "run.log"

    message = _collection_failure_message("Collection failed", result, run_log)

    assert "Failed command: configuration_effective" in message
    assert "Command: show configuration effective" in message
    assert str(run_log) in message


def test_format_diagnostic_progress_summarizes_code_stage_and_reports(tmp_path):
    lines = format_diagnostic_progress(
        "WLC-CMD-001",
        {
            "json": tmp_path / "diagnostic_summary.json",
            "html": tmp_path / "diagnostic_summary.html",
        },
        [
            safe_info_event("DGN-BOOT", "Diagnostic mode started."),
            event_from_code("WLC-CMD-001", command_id="configuration_effective"),
        ],
    )

    assert lines[0] == "Diagnostic primary code: WLC-CMD-001"
    assert "DIAG: DGN-BOOT | OK" in lines
    assert "DIAG: DGN-CMD | ERROR | WLC-CMD-001 | configuration_effective" in lines
    assert any(line.startswith("Diagnostic JSON:") for line in lines)
    assert any(line.startswith("Diagnostic HTML:") for line in lines)
