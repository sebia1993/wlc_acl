from __future__ import annotations

import csv
import os
from pathlib import Path

from .models import Controller, ControllerCredentials


def default_port_for_protocol(protocol: str) -> int:
    return 23 if protocol.lower() == "telnet" else 22


def default_device_type_for_protocol(protocol: str) -> str:
    return "generic_telnet" if protocol.lower() == "telnet" else "aruba_os"


def load_controllers(path: Path) -> list[Controller]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        controllers: list[Controller] = []
        for row_number, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            host = (row.get("host") or "").strip()
            if not name or not host:
                raise ValueError(f"controllers CSV row {row_number}: name and host are required")
            protocol = (row.get("protocol") or "ssh").strip().lower()
            port_value = (row.get("port") or "").strip()
            port = int(port_value) if port_value else default_port_for_protocol(protocol)
            device_type = (row.get("device_type") or "").strip()
            controllers.append(
                Controller(
                    name=name,
                    host=host,
                    protocol=protocol,
                    port=port,
                    device_type=device_type or default_device_type_for_protocol(protocol),
                    username_env=(row.get("username_env") or "").strip(),
                    password_env=(row.get("password_env") or "").strip(),
                    enable_password_env=(row.get("enable_password_env") or "").strip(),
                )
            )
    return controllers


def resolve_credentials(controller: Controller) -> ControllerCredentials:
    if not controller.username_env:
        raise ValueError(f"{controller.name}: username_env is required")
    if not controller.password_env:
        raise ValueError(f"{controller.name}: password_env is required")

    username = os.getenv(controller.username_env, "")
    password = os.getenv(controller.password_env, "")
    enable_password = os.getenv(controller.enable_password_env, "") if controller.enable_password_env else ""

    missing = []
    if not username:
        missing.append(controller.username_env)
    if not password:
        missing.append(controller.password_env)
    if missing:
        raise ValueError(f"{controller.name}: missing environment variables: {', '.join(missing)}")

    return ControllerCredentials(username=username, password=password, enable_password=enable_password)
