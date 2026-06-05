from pathlib import Path

from openpyxl import load_workbook

from wlc_role_acl_collector.collector import collect_from_offline_raw
from wlc_role_acl_collector.models import Controller, RoleNetworkDefinition
from wlc_role_acl_collector.report import (
    _acl_rows_html,
    _is_role_related_acl,
    build_parsed_controllers,
    write_raw_result,
    write_reports,
)


def test_write_excel_and_html_report(tmp_path):
    fixture_root = Path(__file__).parent / "fixtures"
    controller = Controller(name="sample_controller", host="192.0.2.10")
    result = collect_from_offline_raw(controller, fixture_root)
    write_raw_result(result, tmp_path / "raw")
    parsed = build_parsed_controllers([result])

    files = write_reports(parsed_controllers=parsed, collection_results=[result], output_dir=tmp_path)

    assert files["xlsx"].exists()
    assert files["html"].exists()
    workbook = load_workbook(files["xlsx"], read_only=True)
    assert {
        "Overview",
        "SSID_Role_Map",
        "Role_Network_Context",
        "Local_Role_Networks",
        "Role_ACL_Detail",
        "Alias_Detail",
        "Unresolved",
        "Raw_Commands",
    }.issubset(set(workbook.sheetnames))
    acl_headers = [cell.value for cell in next(workbook["Role_ACL_Detail"].iter_rows(max_row=1))]
    assert "source_detail" not in acl_headers
    assert "destination_detail" not in acl_headers
    assert "source_interpretation" in acl_headers
    assert "destination_interpretation" in acl_headers
    assert "role_user_network" in acl_headers
    overview_headers = [cell.value for cell in next(workbook["Overview"].iter_rows(max_row=1))]
    ssid_headers = [cell.value for cell in next(workbook["SSID_Role_Map"].iter_rows(max_row=1))]
    raw_headers = [cell.value for cell in next(workbook["Raw_Commands"].iter_rows(max_row=1))]
    for headers in (overview_headers, ssid_headers, raw_headers):
        assert "site" not in headers
        assert "zone" not in headers
    assert "effective_vlan" in ssid_headers
    assert "role_user_network" in ssid_headers
    assert "network_evidence" in ssid_headers
    assert "network_confidence" in ssid_headers
    assert "assignment_source" in ssid_headers
    assert "configured_vlan" in ssid_headers
    assert "configured_subnet" in ssid_headers
    assert "observed_user_count" in ssid_headers
    context_headers = [cell.value for cell in next(workbook["Role_Network_Context"].iter_rows(max_row=1))]
    assert "role_user_network" in context_headers
    assert "network_confidence" in context_headers
    assert "assignment_source" in context_headers
    assert "configured_vlan" in context_headers
    assert "configured_subnet" in context_headers
    assert "observed_networks" in context_headers
    html = files["html"].read_text(encoding="utf-8")
    assert "corp-employee" in html
    assert "<th>Zone</th>" not in html
    assert 'id="filter"' not in html
    assert 'id="ssid-table"' not in html
    assert 'class="toolbar no-print"' not in html
    assert "<details" not in html
    assert "<th>SSID</th>" not in html
    assert "<th>AP Group</th>" not in html
    assert "<th>AAA Profile</th>" not in html
    assert "<th>Role Type</th>" not in html
    assert "<th>VAP VLAN</th>" not in html
    assert "<th>Effective VLAN</th>" not in html
    assert "Role User Network" not in html
    assert "Local Role Network" not in html
    assert "Configured Subnet" not in html
    assert "network-context" not in html
    assert "network-chip" not in html
    assert "network-confidence" not in html
    assert 'class="role-tabs no-print"' in html
    assert 'class="role-tab"' in html
    assert 'role="tab"' in html
    assert 'id="role-panel-1" data-role="guest-logon"' in html
    assert 'aria-selected="true"' in html
    assert "afterprint" in html
    assert html.index('<span class="role-tab-name">guest-logon</span>') < html.index(
        '<span class="role-tab-name">corp-employee</span>'
    )
    assert "User IP (current client assigned to this role)" in html
    assert "Any (0.0.0.0/0)" in html
    assert "Source Detail" not in html
    assert "Destination Detail" not in html
    assert "Alias Detail" not in html
    assert 'class="alias-link"' in html
    assert 'class="alias-detail-row" hidden' in html
    assert "<th>Comment</th>" in html
    assert 'class="comment-input"' in html
    assert 'class="comment-status"' in html
    assert 'class="comment-print"' in html
    assert 'id="acl-comments-data"' in html
    assert "localStorage" in html
    assert "commentStorageKey" in html
    assert "임시저장 복원됨" in html
    assert "저장됨" in html
    assert "주석 포함 HTML 저장" in html
    assert "PDF 저장/인쇄" in html
    assert "window.print()" in html
    assert "beforeprint" in html
    assert "@media print" in html
    assert 'class="report-actions no-print"' in html
    assert 'id="toggle-raw"' in html
    assert 'aria-pressed="false">Raw 보기</button>' in html
    assert "Raw 숨김" in html
    assert '<th class="raw-column">Raw</th>' in html
    assert 'class="raw raw-column"' in html
    assert ".raw-column { display: none; }" in html
    assert "body.raw-visible .raw-column { display: table-cell; }" in html
    assert "document.body.classList.toggle('raw-visible')" in html
    assert "syncRawToggleButton" in html
    assert 'class="acl-filter-button toggle-other-acls"' in html
    assert 'data-other-acl-count="5"' in html
    assert "5 other hidden" in html
    assert "Show other ACLs" in html
    assert "Hide other ACLs" in html
    assert 'class="acl-rule-row other-acl-rule" data-other-acl="true" hidden' in html
    assert "syncOtherAclRows" in html
    assert "panel.querySelectorAll('.other-acl-rule')" in html
    assert "document.querySelectorAll('.other-acl-rule')" in html
    assert 'colspan="8"' in html
    assert "alias-type-host" in html
    assert "alias-type-network" in html
    assert "10.10.20.0 255.255.255.0" in html
    raw_text = result.raw_file.read_text(encoding="utf-8")
    assert "[show user-table output redacted]" in raw_text
    assert "corp-user-2" not in raw_text
    assert "aa:bb:cc" not in raw_text


def test_write_report_includes_local_role_network_mapping(tmp_path):
    fixture_root = Path(__file__).parent / "fixtures"
    controller = Controller(name="sample_controller", host="192.0.2.10")
    result = collect_from_offline_raw(controller, fixture_root)
    parsed = build_parsed_controllers([result])
    local_role_networks = [
        RoleNetworkDefinition(
            role="guest-logon",
            network="10.30.0.0/24",
            subnet_mask="255.255.255.0",
            source_file="role_networks.xlsx",
            source_row=2,
        ),
        RoleNetworkDefinition(
            role="guest-logon",
            network="10.31.0.0/24",
            subnet_mask="255.255.255.0",
            source_file="role_networks.xlsx",
            source_row=3,
        ),
    ]

    files = write_reports(
        parsed_controllers=parsed,
        collection_results=[result],
        output_dir=tmp_path,
        local_role_networks=local_role_networks,
    )

    workbook = load_workbook(files["xlsx"], read_only=True)
    acl_headers = [cell.value for cell in next(workbook["Role_ACL_Detail"].iter_rows(max_row=1))]
    assert "local_role_networks" in acl_headers
    assert "local_network_status" in acl_headers
    assert "local_network_notes" in acl_headers
    local_rows = [
        {header: value for header, value in zip(
            [cell.value for cell in next(workbook["Local_Role_Networks"].iter_rows(max_row=1))],
            row,
        )}
        for row in workbook["Local_Role_Networks"].iter_rows(min_row=2, values_only=True)
    ]
    assert any(row["role"] == "guest-logon" and row["status"] == "Mismatch" for row in local_rows)
    assert any(row["role"] == "corp-employee" and row["status"] == "Local mapping missing" for row in local_rows)

    html = files["html"].read_text(encoding="utf-8")
    assert "Local Role Network" in html
    assert "10.30.0.0/24" in html
    assert "10.31.0.0/24" in html
    assert "Mismatch" in html
    assert "Local mapping missing" in html
    assert "Local Role Network: 10.30.0.0/24, 10.31.0.0/24" in html


def test_acl_rows_keep_collection_order_and_hide_other_acls():
    rows = [
        {"acl": "shared-acl", "sequence": 1},
        {"acl": "guest-logon-acl", "sequence": 2},
        {"acl": "tail-acl", "sequence": 4},
    ]

    html = _acl_rows_html("guest-logon", rows, {})

    assert html.index("<td>shared-acl</td>") < html.index("<td>guest-logon-acl</td>")
    assert html.index("<td>guest-logon-acl</td>") < html.index("<td>tail-acl</td>")
    assert html.count('class="acl-rule-row other-acl-rule" data-other-acl="true" hidden') == 2
    assert html.count('class="acl-rule-row"') == 1


def test_role_related_acl_allows_role_name_inside_acl_name():
    assert _is_role_related_acl("guest-logon", "guest-logon-acl")
    assert _is_role_related_acl("guest-logon", "branch-guest-logon-policy")
    assert not _is_role_related_acl("corp-employee", "corp-acl")
