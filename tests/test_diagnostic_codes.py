from wlc_role_acl_collector.diagnostic_codes import classify_message_to_code, get_diagnostic_code
from wlc_role_acl_collector.diagnostics import classify_error_message


def test_known_diagnostic_code_contains_safe_operator_guidance():
    code = get_diagnostic_code("WLC-CMD-001")

    assert code.stage == "DGN-CMD"
    assert "show configuration effective" in code.operator_action


def test_message_classification_returns_stable_code():
    code = classify_message_to_code("TCP connection to device failed with timeout", command_id="connect")

    assert code.code == "WLC-NET-001"


def test_legacy_failure_info_exposes_new_code():
    info = classify_error_message("Authentication failed: bad password")

    assert info.category == "authentication"
    assert info.code == "WLC-AUTH-001"
