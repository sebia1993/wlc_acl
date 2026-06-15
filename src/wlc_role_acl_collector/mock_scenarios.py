"""Mock WLC response scenarios.

Scenario files contain synthetic output only. They must never be populated with
real controller logs or customer IP/host data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MockScenario:
    name: str
    prompt: str = "(mock-wlc) #"
    username_prompt: str = "Username: "
    password_prompt: str = "Password: "
    login: str = "success"
    commands: dict[str, str] = field(default_factory=dict)

    def response_for(self, command: str) -> str:
        normalized = command.strip()
        if normalized in self.commands:
            return self.commands[normalized]
        return "% Invalid input detected at '^' marker."


def load_mock_scenario(path: Path) -> MockScenario:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ValueError(f"Unable to read mock scenario: {path}") from exc
    return mock_scenario_from_dict(data)


def mock_scenario_from_dict(data: dict[str, Any]) -> MockScenario:
    name = str(data.get("name") or "").strip()
    commands = data.get("commands")
    if not name:
        raise ValueError("Mock scenario requires a name.")
    if not isinstance(commands, dict):
        raise ValueError("Mock scenario requires a commands object.")
    return MockScenario(
        name=name,
        prompt=str(data.get("prompt") or "(mock-wlc) #"),
        username_prompt=str(data.get("username_prompt") or "Username: "),
        password_prompt=str(data.get("password_prompt") or "Password: "),
        login=str(data.get("login") or "success"),
        commands={str(key): str(value) for key, value in commands.items()},
    )
