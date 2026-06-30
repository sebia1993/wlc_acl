import sys
from pathlib import Path
from types import SimpleNamespace

from wlc_role_acl_collector.collector import collect_from_controller
from wlc_role_acl_collector.models import Controller, ControllerCredentials


FIXTURE = Path(__file__).parent / "fixtures" / "sample_controller" / "show_configuration_effective.txt"


class FakeConnection:
    def __init__(self, *, responses=None, failures=None, enable_failure=None):
        self.responses = responses or {}
        self.failures = failures or {}
        self.enable_failure = enable_failure
        self.enable_called = False
        self.commands = []
        self.disconnected = False

    def enable(self):
        self.enable_called = True
        if self.enable_failure:
            raise self.enable_failure

    def send_command_timing(self, *, command_string, **_kwargs):
        self.commands.append(command_string)
        if command_string in self.failures:
            raise self.failures[command_string]
        return self.responses.get(command_string, "")

    def disconnect(self):
        self.disconnected = True


def _install_fake_netmiko(monkeypatch, connection):
    monkeypatch.setitem(sys.modules, "netmiko", SimpleNamespace(ConnectHandler=lambda **_params: connection))


def test_collect_continues_when_disable_paging_fails(monkeypatch):
    config = FIXTURE.read_text(encoding="utf-8")
    connection = FakeConnection(
        responses={
            "show clock": "clock output",
            "show version": "version output",
            "show configuration effective": config,
            "show netdestination controller": "Name: controller\n1 host 10.10.10.1 32\n",
            "show rights corp-employee": "corp rights",
            "show rights guest-logon": "guest rights",
            "show rights logon": "logon rights",
        },
        failures={"no paging": RuntimeError("no paging is not supported")},
    )
    _install_fake_netmiko(monkeypatch, connection)
    events = []

    result = collect_from_controller(
        Controller(name="wlc", host="192.0.2.10"),
        credentials=ControllerCredentials(username="admin", password="secret"),
        progress_callback=lambda event, payload: events.append((event, payload)),
    )

    assert result.command_output("configuration_effective") == config
    assert any(command.command_id == "disable_paging" and not command.success for command in result.commands)
    assert not any(command.command_id == "connect" for command in result.commands)
    assert any(event == "roles_discovered" and payload["total"] == 3 for event, payload in events)
    assert any(event == "aliases_discovered" and payload["total"] == 1 for event, payload in events)
    assert "show netdestination controller" in connection.commands
    assert "show rights corp-employee" in connection.commands
    assert connection.disconnected is True


def test_collect_records_configuration_command_failure(monkeypatch):
    connection = FakeConnection(
        responses={"no paging": "", "show clock": "clock output", "show version": "version output"},
        failures={"show configuration effective": RuntimeError("Invalid input: show configuration effective")},
    )
    _install_fake_netmiko(monkeypatch, connection)
    events = []

    result = collect_from_controller(
        Controller(name="wlc", host="192.0.2.10"),
        credentials=ControllerCredentials(username="admin", password="secret"),
        progress_callback=lambda event, payload: events.append((event, payload)),
    )

    failed = [command for command in result.commands if not command.success]
    assert [(command.command_id, command.command) for command in failed] == [
        ("configuration_effective", "show configuration effective")
    ]
    assert not any(command.command_id == "connect" for command in result.commands)
    assert not any(command.startswith("show rights") for command in connection.commands)
    assert any(
        event == "command_error" and payload["command_id"] == "configuration_effective"
        for event, payload in events
    )


def test_collect_records_enable_password_failure_and_continues(monkeypatch):
    config = FIXTURE.read_text(encoding="utf-8")
    connection = FakeConnection(
        responses={
            "no paging": "",
            "show clock": "clock output",
            "show version": "version output",
            "show configuration effective": config,
            "show ip interface brief": "ip interface output",
            "show user-table": "user table output",
            "show netdestination controller": "Name: controller\n1 host 10.10.10.1 32\n",
            "show rights corp-employee": "corp rights",
            "show rights guest-logon": "guest rights",
            "show rights logon": "logon rights",
        },
        enable_failure=RuntimeError("enable denied"),
    )
    _install_fake_netmiko(monkeypatch, connection)
    events = []

    result = collect_from_controller(
        Controller(name="wlc", host="192.0.2.10"),
        credentials=ControllerCredentials(username="admin", password="secret", enable_password="bad"),
        progress_callback=lambda event, payload: events.append((event, payload)),
    )

    enable = next(command for command in result.commands if command.command_id == "enable")
    assert connection.enable_called is True
    assert enable.success is False
    assert "enable denied" in enable.error
    assert result.command_output("configuration_effective") == config
    assert any(
        event == "command_error" and payload["command_id"] == "enable" and "enable denied" in payload["error"]
        for event, payload in events
    )
    assert "show rights corp-employee" in connection.commands
