from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from wlc_role_acl_collector.web_logic import WebCollectionRequest, run_web_collection


def test_run_web_collection_offline_returns_preview_and_downloads():
    fixture_root = Path(__file__).parent / "fixtures"
    role_networks = _role_network_workbook_bytes()
    events = []

    result = run_web_collection(
        WebCollectionRequest(
            host="192.0.2.10",
            controller_name="sample_controller",
            username="",
            password="",
            role_networks_filename="role_networks.xlsx",
            role_networks_bytes=role_networks,
            offline_raw_dir=fixture_root,
        ),
        progress_callback=lambda event, payload: events.append((event, payload)),
    )

    assert result.success is True
    assert result.summary["ssid_count"] > 0
    assert result.summary["role_network_rows"] == 1
    assert result.preview_rows
    assert result.acl_preview_rows
    assert {"xlsx", "csv", "html"}.issubset(result.artifacts)
    assert result.artifacts["xlsx"].filename.endswith(".xlsx")
    assert result.artifacts["csv"].data.startswith(b"\xef\xbb\xbfcontroller,ssid")
    assert b"guest-logon" in result.artifacts["csv"].data
    assert result.artifacts["html"].data.startswith(b"<!doctype html>")
    assert any(event == "complete" for event, _payload in events)


def _role_network_workbook_bytes() -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Role_Networks"
    worksheet.append(["Role 이름", "네트워크 대역", "서브넷마스크"])
    worksheet.append(["guest-logon", "10.30.0.0/24", ""])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
