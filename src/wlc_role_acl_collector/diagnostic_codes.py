"""Stable diagnostic codes for field troubleshooting.

Codes are intentionally safe to share outside the company network. They do not
contain device output, IP addresses, hostnames, usernames, or policy names.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiagnosticCode:
    code: str
    stage: str
    category: str
    title: str
    safe_message: str
    likely_cause: str
    operator_action: str
    retryable: bool = False


DIAGNOSTIC_CODES: dict[str, DiagnosticCode] = {
    "OK": DiagnosticCode(
        code="OK",
        stage="DGN-COMPLETE",
        category="success",
        title="Diagnostic completed",
        safe_message="Diagnostic checks completed without a blocking issue.",
        likely_cause="No known failure was detected.",
        operator_action="Use the generated report for local records. No raw device output was saved.",
        retryable=False,
    ),
    "WLC-ENV-001": DiagnosticCode(
        code="WLC-ENV-001",
        stage="DGN-BOOT",
        category="environment",
        title="Runtime initialization failed",
        safe_message="The application could not initialize the local runtime.",
        likely_cause="The executable package is incomplete or blocked by local Windows security policy.",
        operator_action="Re-run the packaged EXE from a local folder and check antivirus or AppLocker policy.",
        retryable=True,
    ),
    "WLC-INP-001": DiagnosticCode(
        code="WLC-INP-001",
        stage="DGN-INPUT",
        category="input",
        title="Invalid diagnostic input",
        safe_message="One or more connection inputs are invalid.",
        likely_cause="The protocol, port, timeout, or WLC address field is malformed.",
        operator_action="Check that protocol is ssh/telnet, port is 1-65535, and timeout is at least 5 seconds.",
        retryable=True,
    ),
    "WLC-NET-001": DiagnosticCode(
        code="WLC-NET-001",
        stage="DGN-NET",
        category="network",
        title="Connection timed out",
        safe_message="The WLC did not respond before the timeout expired.",
        likely_cause="Routing, firewall, controller reachability, or SSH/Telnet service availability issue.",
        operator_action="Verify WLC reachability, selected protocol, port, routing, and firewall policy.",
        retryable=True,
    ),
    "WLC-NET-002": DiagnosticCode(
        code="WLC-NET-002",
        stage="DGN-NET",
        category="network",
        title="Connection refused",
        safe_message="The target actively refused the selected TCP connection.",
        likely_cause="The selected port is closed or the selected protocol is disabled on the WLC.",
        operator_action="Check whether SSH or Telnet is enabled on the WLC and that the correct port is selected.",
        retryable=True,
    ),
    "WLC-NET-003": DiagnosticCode(
        code="WLC-NET-003",
        stage="DGN-NET",
        category="network",
        title="Network path unavailable",
        safe_message="The diagnostic could not reach the WLC network path.",
        likely_cause="No route, unreachable network, local firewall, or intermediate access control issue.",
        operator_action="Check local IP routing, VPN, firewall, and network access from the field PC.",
        retryable=True,
    ),
    "WLC-AUTH-001": DiagnosticCode(
        code="WLC-AUTH-001",
        stage="DGN-AUTH",
        category="authentication",
        title="Authentication failed",
        safe_message="The WLC rejected the login credentials.",
        likely_cause="Incorrect ID/password, expired password, account lock, or login method restriction.",
        operator_action="Verify the account, password, lock status, and SSH/Telnet login permission.",
        retryable=True,
    ),
    "WLC-AUTH-002": DiagnosticCode(
        code="WLC-AUTH-002",
        stage="DGN-AUTH",
        category="authentication",
        title="Enable password failed",
        safe_message="Login succeeded, but enable mode could not be entered.",
        likely_cause="Missing or incorrect enable password, or the account does not require/support enable mode.",
        operator_action="Verify enable password requirements for this WLC account.",
        retryable=True,
    ),
    "WLC-PRM-001": DiagnosticCode(
        code="WLC-PRM-001",
        stage="DGN-PROMPT",
        category="prompt",
        title="Prompt detection failed",
        safe_message="The application could not reliably detect the WLC prompt after login.",
        likely_cause="Unexpected banner, paging prompt, unsupported shell, or slow prompt response.",
        operator_action="Check login banner behavior and increase timeout if the controller is slow.",
        retryable=True,
    ),
    "WLC-CMD-001": DiagnosticCode(
        code="WLC-CMD-001",
        stage="DGN-CMD",
        category="command",
        title="Required configuration output missing",
        safe_message="The required configuration command returned no usable output.",
        likely_cause="Command unsupported, insufficient privilege, or empty command response.",
        operator_action="Check permission for 'show configuration effective' on the WLC.",
        retryable=False,
    ),
    "WLC-CMD-002": DiagnosticCode(
        code="WLC-CMD-002",
        stage="DGN-CMD",
        category="command",
        title="Command timed out",
        safe_message="A WLC command did not complete before the timeout expired.",
        likely_cause="Slow controller response, paging behavior, or command execution delay.",
        operator_action="Increase timeout and confirm paging is disabled.",
        retryable=True,
    ),
    "WLC-CMD-003": DiagnosticCode(
        code="WLC-CMD-003",
        stage="DGN-CMD",
        category="command",
        title="Command rejected or not permitted",
        safe_message="The WLC rejected a required command or the account lacks permission.",
        likely_cause="Invalid command on this platform/version or insufficient account privilege.",
        operator_action="Check WLC version and command authorization for required show commands.",
        retryable=False,
    ),
    "WLC-CMD-004": DiagnosticCode(
        code="WLC-CMD-004",
        stage="DGN-CMD",
        category="command",
        title="Optional role or alias command failed",
        safe_message="A role or alias detail command failed, but base collection may still be usable.",
        likely_cause="Specific Role/Alias command permission, unsupported object name, or timeout.",
        operator_action="Review the command ID in the diagnostic report and verify object-specific permission.",
        retryable=True,
    ),
    "WLC-PRS-001": DiagnosticCode(
        code="WLC-PRS-001",
        stage="DGN-PARSE",
        category="parse",
        title="Configuration parsing failed",
        safe_message="The collected configuration could not be parsed into Role/ACL data.",
        likely_cause="Unsupported Aruba output format or incomplete configuration output.",
        operator_action="Confirm the controller is AOS8 WLC and the required command returned full output.",
        retryable=False,
    ),
    "WLC-PRS-002": DiagnosticCode(
        code="WLC-PRS-002",
        stage="DGN-PARSE",
        category="parse",
        title="Alias parsing incomplete",
        safe_message="Some Alias values could not be interpreted as IP ranges.",
        likely_cause="Alias contains names, unsupported entry types, or output was incomplete.",
        operator_action="Use the warning count in the report to decide whether manual Alias review is needed.",
        retryable=False,
    ),
    "WLC-RPT-001": DiagnosticCode(
        code="WLC-RPT-001",
        stage="DGN-REPORT",
        category="report",
        title="Output folder write failed",
        safe_message="The diagnostic could not write to the selected output folder.",
        likely_cause="Folder permission, locked file, unavailable drive, or path policy restriction.",
        operator_action="Choose a local writable folder such as Documents.",
        retryable=True,
    ),
    "WLC-RPT-002": DiagnosticCode(
        code="WLC-RPT-002",
        stage="DGN-REPORT",
        category="report",
        title="Report generation failed",
        safe_message="The diagnostic report could not be generated.",
        likely_cause="Local file system error or report rendering failure.",
        operator_action="Retry in a short local path and check Windows file permissions.",
        retryable=True,
    ),
    "WLC-SEC-001": DiagnosticCode(
        code="WLC-SEC-001",
        stage="DGN-SEC",
        category="security",
        title="Redaction self-test failed",
        safe_message="The diagnostic stopped because sensitive-data masking did not pass self-test.",
        likely_cause="Unexpected redaction module error.",
        operator_action="Do not export diagnostic files. Rebuild or update the tool before use.",
        retryable=False,
    ),
    "WLC-MOCK-001": DiagnosticCode(
        code="WLC-MOCK-001",
        stage="DGN-MOCK",
        category="mock",
        title="Mock server start failed",
        safe_message="The local mock WLC server could not start.",
        likely_cause="Local port is in use or Windows blocked local listener creation.",
        operator_action="Choose a different local port or run from a folder allowed by Windows policy.",
        retryable=True,
    ),
    "WLC-MOCK-002": DiagnosticCode(
        code="WLC-MOCK-002",
        stage="DGN-MOCK",
        category="mock",
        title="Mock scenario invalid",
        safe_message="The mock server scenario file is missing or invalid.",
        likely_cause="Scenario JSON is malformed or required command responses are missing.",
        operator_action="Use the packaged mock scenario files or validate the JSON scenario.",
        retryable=False,
    ),
    "WLC-UNK-001": DiagnosticCode(
        code="WLC-UNK-001",
        stage="DGN-UNKNOWN",
        category="unknown",
        title="Unknown diagnostic failure",
        safe_message="The failure did not match a known diagnostic code.",
        likely_cause="Unexpected application or device behavior.",
        operator_action="Share only this code and the safe diagnostic report with the developer.",
        retryable=True,
    ),
}


def get_diagnostic_code(code: str) -> DiagnosticCode:
    return DIAGNOSTIC_CODES.get(code, DIAGNOSTIC_CODES["WLC-UNK-001"])


def classify_message_to_code(message: str, *, command_id: str = "") -> DiagnosticCode:
    normalized = (message or "").casefold()
    normalized_command = (command_id or "").casefold()

    if any(token in normalized for token in ("authentication", "auth", "password", "login failed")):
        return DIAGNOSTIC_CODES["WLC-AUTH-001"]
    if "enable" in normalized and any(token in normalized for token in ("failed", "denied", "password")):
        return DIAGNOSTIC_CODES["WLC-AUTH-002"]
    if "connection refused" in normalized:
        return DIAGNOSTIC_CODES["WLC-NET-002"]
    if any(token in normalized for token in ("no route", "unreachable", "network is unreachable")):
        return DIAGNOSTIC_CODES["WLC-NET-003"]
    if any(token in normalized for token in ("timed out", "timeout", "tcp connection")):
        if normalized_command and normalized_command != "connect":
            return DIAGNOSTIC_CODES["WLC-CMD-002"]
        return DIAGNOSTIC_CODES["WLC-NET-001"]
    if any(token in normalized for token in ("prompt", "pattern not detected", "search pattern never detected")):
        return DIAGNOSTIC_CODES["WLC-PRM-001"]
    if "show configuration effective" in normalized and any(
        token in normalized for token in ("missing", "not collected", "no output", "empty")
    ):
        return DIAGNOSTIC_CODES["WLC-CMD-001"]
    if any(token in normalized for token in ("invalid input", "permission", "denied", "not authorized")):
        return DIAGNOSTIC_CODES["WLC-CMD-003"]
    if normalized_command.startswith(("rights::", "netdestination::")):
        return DIAGNOSTIC_CODES["WLC-CMD-004"]
    return DIAGNOSTIC_CODES["WLC-UNK-001"]
