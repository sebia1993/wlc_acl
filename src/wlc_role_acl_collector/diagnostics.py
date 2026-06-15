from __future__ import annotations

from dataclasses import dataclass

from .diagnostic_codes import classify_message_to_code
from .models import CollectionResult


@dataclass(frozen=True)
class FailureInfo:
    category: str
    title: str
    detail: str
    suggestion: str
    code: str = "WLC-UNK-001"

    def as_text(self) -> str:
        return f"{self.title}\n\nError code: {self.code}\n\n{self.detail}\n\n{self.suggestion}"


def classify_error_message(message: str) -> FailureInfo:
    diagnostic_code = classify_message_to_code(message)
    normalized = message.lower()

    if any(token in normalized for token in ("authentication", "auth", "password", "login failed")):
        return FailureInfo(
            category="authentication",
            title="Authentication failed",
            detail=message or "The WLC rejected the login.",
            suggestion=(
                "Check the username/password, account lock status, and whether this account is "
                "allowed to log in to the WLC over the selected protocol."
            ),
            code=diagnostic_code.code,
        )

    if any(
        token in normalized
        for token in (
            "timed out",
            "timeout",
            "tcp connection",
            "connection refused",
            "unreachable",
            "no route",
            "port",
            "firewall",
        )
    ):
        return FailureInfo(
            category="timeout",
            title="Connection timed out or was refused",
            detail=message or "The WLC did not respond on the selected IP/port.",
            suggestion=(
                "Check the WLC IP, protocol, port, routing, firewall, and whether SSH/Telnet "
                "is enabled on the controller."
            ),
            code=diagnostic_code.code,
        )

    if any(token in normalized for token in ("show configuration effective", "invalid input", "permission", "denied")):
        return FailureInfo(
            category="command",
            title="Command failed after login",
            detail=message or "Login succeeded, but the required command output was not collected.",
            suggestion=(
                "Check whether the account has permission to run 'show configuration effective' "
                "and 'show rights <role>' on this WLC."
            ),
            code=diagnostic_code.code,
        )

    return FailureInfo(
        category="unknown",
        title="Collection failed",
        detail=message or "The collection failed before a report could be generated.",
        suggestion="Open the raw/log files in the result folder and check the exact device response.",
        code=diagnostic_code.code,
    )


def summarize_collection_failure(result: CollectionResult) -> FailureInfo:
    failed_commands = [command for command in result.commands if command.error]
    for command_id in ("connect", "configuration_effective"):
        for command in failed_commands:
            if command.command_id == command_id:
                return classify_error_message(command.error)

    if not result.command_output("configuration_effective"):
        return classify_error_message("show configuration effective output was not collected.")

    if failed_commands:
        return classify_error_message("; ".join(command.error for command in failed_commands))

    return classify_error_message("")
