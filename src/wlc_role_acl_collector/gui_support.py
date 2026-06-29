from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import default_device_type_for_protocol, default_port_for_protocol
from .models import Controller, ControllerCredentials, ControllerTarget


@dataclass(frozen=True)
class GuiConnectionInput:
    host: str
    name: str = ""
    protocol: str = "ssh"
    port: str = ""
    username: str = ""
    password: str = ""
    enable_password: str = ""


def build_target_from_gui_input(values: GuiConnectionInput) -> ControllerTarget:
    host = values.host.strip()
    if not host:
        raise ValueError("WLC IP를 입력하세요.")

    protocol = values.protocol.strip().lower() or "ssh"
    if protocol not in {"ssh", "telnet"}:
        raise ValueError("Protocol은 SSH 또는 Telnet이어야 합니다.")

    port_text = values.port.strip()
    if port_text:
        try:
            port = int(port_text)
        except ValueError as exc:
            raise ValueError("Port는 숫자로 입력하세요.") from exc
        if not 1 <= port <= 65535:
            raise ValueError("Port는 1에서 65535 사이여야 합니다.")
    else:
        port = default_port_for_protocol(protocol)

    username = values.username.strip()
    if not username:
        raise ValueError("Username을 입력하세요.")
    if not values.password:
        raise ValueError("Password를 입력하세요.")

    name = values.name.strip() or f"wlc-{host}"
    controller = Controller(
        name=name,
        host=host,
        protocol=protocol,
        port=port,
        device_type=default_device_type_for_protocol(protocol),
    )
    credentials = ControllerCredentials(
        username=username,
        password=values.password,
        enable_password=values.enable_password,
    )
    return ControllerTarget(controller=controller, credentials=credentials)


def default_gui_output_dir() -> Path:
    return Path.home() / "Documents" / "WlcRoleAclCollector" / "outputs"
