from wlc_role_acl_collector.gui_app import _collection_failure_message, _write_run_log, format_collection_progress
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

    assert status == "Role 2/5 수집 중: corp-employee"
    assert lines == ["START: rights::corp-employee | show rights corp-employee"]


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
