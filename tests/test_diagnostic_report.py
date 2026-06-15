import json

from wlc_role_acl_collector.diagnostic_events import DiagnosticEvent, event_from_code
from wlc_role_acl_collector.diagnostic_report import write_diagnostic_report


def test_diagnostic_report_writes_no_raw_output_and_redacts_sensitive_metadata(tmp_path):
    paths = write_diagnostic_report(
        tmp_path,
        events=[
            DiagnosticEvent(
                stage="DGN-NET",
                status="error",
                code="WLC-NET-001",
                command_id="connect",
                message="Connection timeout",
                detail="10.10.10.10 password Secret123 wlc-prod-01",
            ),
            event_from_code("WLC-NET-001", command_id="connect"),
        ],
        primary_code="WLC-NET-001",
        metadata={"host": "10.10.10.10", "hostname": "wlc-prod-01", "password": "Secret123"},
    )

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    html = paths["html"].read_text(encoding="utf-8")
    log = paths["log"].read_text(encoding="utf-8")

    assert payload["raw_output_saved"] is False
    assert payload["primary"]["code"] == "WLC-NET-001"
    for text in (paths["json"].read_text(encoding="utf-8"), html, log):
        assert "10.10.10.10" not in text
        assert "Secret123" not in text
        assert "wlc-prod-01" not in text
