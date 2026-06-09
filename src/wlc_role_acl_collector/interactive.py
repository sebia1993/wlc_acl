from __future__ import annotations

import getpass
from typing import Callable

from .config import default_device_type_for_protocol, default_port_for_protocol
from .models import Controller, ControllerCredentials, ControllerTarget


InputFunc = Callable[[str], str]
PasswordFunc = Callable[[str], str]


def prompt_controller_targets(
    *,
    input_func: InputFunc = input,
    password_func: PasswordFunc = getpass.getpass,
) -> list[ControllerTarget]:
    targets: list[ControllerTarget] = []

    while True:
        host = _prompt_required(input_func, "WLC IP: ")
        default_name = f"wlc-{host}"
        name = _prompt_default(input_func, f"Report name [{default_name}]: ", default_name)
        protocol = _prompt_protocol(input_func)
        default_port = default_port_for_protocol(protocol)
        port = _prompt_int_default(input_func, f"Port [{default_port}]: ", default_port)
        username = _prompt_required(input_func, "Username: ")
        password = password_func("Password: ")
        enable_password = password_func("Enable password (optional): ")

        controller = Controller(
            name=name,
            host=host,
            protocol=protocol,
            port=port,
            device_type=default_device_type_for_protocol(protocol),
        )
        targets.append(
            ControllerTarget(
                controller=controller,
                credentials=ControllerCredentials(
                    username=username,
                    password=password,
                    enable_password=enable_password,
                ),
            )
        )

        add_more = input_func("Add another controller? [y/N]: ").strip().lower()
        if add_more not in {"y", "yes"}:
            break

    return targets


def _prompt_required(input_func: InputFunc, prompt: str) -> str:
    while True:
        value = input_func(prompt).strip()
        if value:
            return value
        print("Value is required.")


def _prompt_default(input_func: InputFunc, prompt: str, default: str) -> str:
    value = input_func(prompt).strip()
    return value if value else default


def _prompt_protocol(input_func: InputFunc) -> str:
    while True:
        value = input_func("Protocol [ssh/telnet] (default: ssh): ").strip().lower() or "ssh"
        if value in {"ssh", "telnet"}:
            return value
        print("Protocol must be ssh or telnet.")


def _prompt_int_default(input_func: InputFunc, prompt: str, default: int) -> int:
    while True:
        value = input_func(prompt).strip()
        if not value:
            return default
        try:
            port = int(value)
        except ValueError:
            print("Port must be a number.")
            continue
        if 1 <= port <= 65535:
            return port
        print("Port must be between 1 and 65535.")
