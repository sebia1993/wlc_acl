import inspect

import customtkinter as ctk

from wlc_role_acl_collector.gui_app import (
    ADVANCED_OPTIONS_HIDE_LABEL,
    ADVANCED_OPTIONS_SHOW_LABEL,
    APP_TITLE,
    COLLECTION_ACTION_LABEL,
    CUSTOMTKINTER_APPEARANCE_MODE,
    CUSTOMTKINTER_COLOR_THEME,
    DEFAULT_WINDOW_SIZE,
    DIAGNOSTIC_ACTION_LABEL,
    DIAGNOSTIC_LOG_MENU_LABEL,
    LOG_HIDE_LABEL,
    LOG_SHOW_LABEL,
    MENU_LABELS,
    OPEN_FOLDER_LABEL,
    OPEN_HTML_LABEL,
    OPEN_XLSX_LABEL,
    COLLECTION_MENU_LABEL,
    REPORT_NAME_LABEL,
    REPORT_MANAGEMENT_MENU_LABEL,
    ROLE_NETWORK_EMPTY_STATUS,
    ROLE_NETWORK_GUIDE_LABEL,
    ROLE_NETWORK_GUIDE_TEXT,
    ROLE_NETWORK_HELP,
    ROLE_NETWORK_LABEL,
    ROLE_NETWORK_SELECT_LABEL,
    ROLE_NETWORK_TEMPLATE_LABEL,
    SETTINGS_MENU_LABEL,
    SIDEBAR_WIDTH,
    SSH_STATUS_LABEL,
    _find_role_network_template,
    _role_network_template_candidates,
    _role_networks_status_message,
    STAGE_LABELS,
    STAGE_PROGRESS,
    WlcRoleAclCollectorGui,
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
from wlc_role_acl_collector.role_networks import ROLE_NETWORKS_FALLBACK_NOTICE, RoleNetworkLoadSummary


def test_gui_app_importable():
    import wlc_role_acl_collector.gui_app as gui_app

    assert callable(gui_app.main)


def test_gui_uses_customtkinter_dark_blue_app_shell():
    assert issubclass(WlcRoleAclCollectorGui, ctk.CTk)
    assert APP_TITLE == "Aruba WLC Ops Analyzer v2.0"
    assert DEFAULT_WINDOW_SIZE == (1100, 750)
    assert CUSTOMTKINTER_APPEARANCE_MODE == "Dark"
    assert CUSTOMTKINTER_COLOR_THEME == "blue"


def test_gui_dashboard_navigation_uses_sidebar_and_tabview():
    assert MENU_LABELS == (
        SETTINGS_MENU_LABEL,
        COLLECTION_MENU_LABEL,
        DIAGNOSTIC_LOG_MENU_LABEL,
        REPORT_MANAGEMENT_MENU_LABEL,
    )
    assert MENU_LABELS == ("설정", "수집 및 분석", "진단 로그", "보고서 관리")
    assert SSH_STATUS_LABEL == "SSH Status"
    assert SIDEBAR_WIDTH >= 220

    layout_source = inspect.getsource(WlcRoleAclCollectorGui._layout)
    sidebar_source = inspect.getsource(WlcRoleAclCollectorGui._sidebar)

    assert "CTkTabview" in layout_source
    assert "sidebar_menu_buttons" in sidebar_source


def test_gui_notice_tells_user_to_connect_to_wlc_not_mm():
    assert "Mobility Master(MM)" in WLC_TARGET_NOTICE
    assert "WLC 컨트롤러 IP" in WLC_TARGET_NOTICE
    assert "Hostname" not in WLC_TARGET_NOTICE


def test_gui_connection_labels_do_not_imply_hostname_is_required():
    assert WLC_IP_LABEL == "WLC IP"
    assert REPORT_NAME_LABEL == "보고서 이름(선택)"
    assert "Hostname" not in WLC_IP_LABEL


def test_gui_stage_labels_support_operational_console_flow():
    assert [STAGE_LABELS[key] for key in ("ready", "connecting", "collecting", "reporting", "completed")] == [
        "준비",
        "접속 중",
        "수집 중",
        "보고서 생성",
        "완료",
    ]
    assert STAGE_LABELS["failed"] == "실패"
    assert STAGE_PROGRESS == {
        "ready": 0,
        "connecting": 20,
        "collecting": 50,
        "reporting": 80,
        "completed": 100,
        "failed": 100,
    }


def test_gui_actions_prioritize_collection_and_html_result():
    assert COLLECTION_ACTION_LABEL == "수집 시작"
    assert DIAGNOSTIC_ACTION_LABEL == "안전 진단"
    assert ADVANCED_OPTIONS_SHOW_LABEL == "고급 옵션 표시"
    assert ADVANCED_OPTIONS_HIDE_LABEL == "고급 옵션 숨김"
    assert LOG_SHOW_LABEL == "수집 로그 표시"
    assert LOG_HIDE_LABEL == "수집 로그 숨김"
    assert OPEN_HTML_LABEL == "HTML 보고서 열기"
    assert OPEN_XLSX_LABEL == "Excel 열기"
    assert OPEN_FOLDER_LABEL == "결과 폴더 열기"


def test_gui_role_network_copy_explains_internal_report_behavior():
    assert ROLE_NETWORK_LABEL == "사내 Role 대역표"
    assert ROLE_NETWORK_SELECT_LABEL == "파일 선택"
    assert ROLE_NETWORK_GUIDE_LABEL == "작성법"
    assert ROLE_NETWORK_TEMPLATE_LABEL == "샘플 열기"
    assert "내부용 HTML/Excel 보고서" in ROLE_NETWORK_HELP
    assert ".xlsx/.xlsm" in ROLE_NETWORK_EMPTY_STATUS
    assert "필수 컬럼" in ROLE_NETWORK_GUIDE_TEXT
    assert "Sheet 선택 기준" in ROLE_NETWORK_GUIDE_TEXT
    assert "Role_Networks Sheet가 있으면" in ROLE_NETWORK_GUIDE_TEXT
    assert "10.40.1.0/24" in ROLE_NETWORK_GUIDE_TEXT
    assert "같은 Role에 여러 대역" in ROLE_NETWORK_GUIDE_TEXT
    assert "내부망 전용 보고서" in ROLE_NETWORK_GUIDE_TEXT


def test_gui_can_find_packaged_role_network_template():
    candidates = _role_network_template_candidates()
    template = _find_role_network_template()

    assert any(path.name == "role_networks.example.xlsx" for path in candidates)
    assert template is not None
    assert template.name == "role_networks.example.xlsx"


def test_gui_role_network_status_includes_selected_sheet_and_fallback_notice():
    summary = RoleNetworkLoadSummary(
        definitions=[],
        role_count=1,
        network_count=2,
        duplicate_count=1,
        source_file="role_networks.xlsx",
        sheet_name="사내대역",
        sheet_fallback_used=True,
        sheet_notice=ROLE_NETWORKS_FALLBACK_NOTICE,
    )

    message = _role_networks_status_message(summary)

    assert "Role 1개 / 대역 2개 / 중복 1행 제외 / Sheet: 사내대역" in message
    assert ROLE_NETWORKS_FALLBACK_NOTICE in message
    assert "내부용 보고서" in message


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
        assert str(exc) == "WLC IP를 입력하세요."
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

    assert status == "Role 수집 2/5: corp-employee"
    assert lines == ["START: rights::corp-employee | show rights corp-employee"]


def test_constrain_window_rect_keeps_window_inside_monitor_work_area():
    assert _constrain_window_rect(900, 650, 1200, 900, (0, 0, 1000, 700)) == (0, 0, 1000, 700)
    assert _constrain_window_rect(800, 650, 760, 560, (100, 100, 900, 700)) == (100, 140, 800, 560)


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

    assert "실패한 명령 ID: configuration_effective" in message
    assert "명령어: show configuration effective" in message
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
