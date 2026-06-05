from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .aos8_parser import parse_controller_config
from .models import CollectionResult, ParsedController


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_raw_result(result: CollectionResult, raw_dir: Path) -> Path:
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{_safe_file_name(result.controller.name)}.txt"
    lines = [
        "=== Controller ===",
        f"name: {result.controller.name}",
        f"host: {result.controller.host}",
        "",
    ]
    for command in result.commands:
        lines.extend(
            [
                f"=== Command: {command.command_id} | {command.command} ===",
                f"success: {command.success}",
                f"error: {command.error}",
                "--- output ---",
                _raw_output_for_storage(command),
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    result.raw_file = path
    return path


def _raw_output_for_storage(command) -> str:
    if command.command_id == "user_table":
        line_count = len([line for line in command.output.splitlines() if line.strip()])
        return "\n".join(
            [
                "[show user-table output redacted]",
                "Original output is used in memory only to calculate Role user count and observed network summary.",
                f"Non-empty line count: {line_count}",
            ]
        )
    return command.output or ""


def build_parsed_controllers(results: list[CollectionResult]) -> list[ParsedController]:
    parsed_items: list[ParsedController] = []
    for result in results:
        rights_outputs = {}
        netdestination_outputs = {}
        for command in result.commands:
            if command.success and command.command_id.startswith("rights::"):
                rights_outputs[command.command_id.split("::", 1)[1]] = command.output
            if command.success and command.command_id.startswith("netdestination::"):
                netdestination_outputs[command.command_id.split("::", 1)[1]] = command.output
        parsed_items.append(
            parse_controller_config(
                controller=result.controller,
                config_text=result.command_output("configuration_effective"),
                rights_outputs=rights_outputs,
                netdestination_outputs=netdestination_outputs,
                ip_interface_brief_output=result.command_output("ip_interface_brief"),
                user_table_output=result.command_output("user_table"),
            )
        )
    return parsed_items


def write_reports(
    *,
    parsed_controllers: list[ParsedController],
    collection_results: list[CollectionResult],
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = output_dir / "ssid_role_acl_report.xlsx"
    html_path = output_dir / "ssid_role_acl_report.html"

    frames = _build_frames(parsed_controllers, collection_results)
    _write_excel(workbook_path, frames)
    _write_html(html_path, frames)
    return {"xlsx": workbook_path, "html": html_path}


def _build_frames(
    parsed_controllers: list[ParsedController],
    collection_results: list[CollectionResult],
) -> dict[str, pd.DataFrame]:
    ssid_rows: list[dict[str, Any]] = []
    role_network_rows: list[dict[str, Any]] = []
    acl_rows: list[dict[str, Any]] = []
    alias_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []

    for parsed in parsed_controllers:
        for context in parsed.role_network_contexts:
            role_network_rows.append(
                {
                    "controller": context.controller,
                    "role": context.role,
                    "effective_vlan": context.effective_vlan,
                    "role_user_network": context.role_user_network,
                    "network_evidence": context.network_evidence,
                    "network_confidence": context.network_confidence,
                    "assignment_source": context.assignment_source,
                    "configured_vlan": context.configured_vlan,
                    "configured_subnet": context.configured_subnet,
                    "ssids": ", ".join(context.ssids),
                    "ap_groups": ", ".join(context.ap_groups),
                    "observed_user_count": context.observed_user_count,
                    "observed_vlans": ", ".join(context.observed_vlans),
                    "observed_networks": ", ".join(context.observed_networks),
                    "notes": context.notes,
                }
            )
        for mapping in parsed.ssid_role_mappings:
            ssid_rows.append(
                {
                    "controller": mapping.controller,
                    "ssid": mapping.ssid,
                    "ap_group": mapping.ap_group,
                    "virtual_ap": mapping.virtual_ap,
                    "ssid_profile": mapping.ssid_profile,
                    "aaa_profile": mapping.aaa_profile,
                    "role_type": mapping.role_type,
                    "role": mapping.role,
                    "vlan": mapping.vlan,
                    "effective_vlan": mapping.effective_vlan,
                    "role_user_network": mapping.role_user_network,
                    "network_evidence": mapping.network_evidence,
                    "network_confidence": mapping.network_confidence,
                    "assignment_source": mapping.assignment_source,
                    "configured_vlan": mapping.configured_vlan,
                    "configured_subnet": mapping.configured_subnet,
                    "observed_user_count": mapping.observed_user_count,
                    "forward_mode": mapping.forward_mode,
                    "access_summary": mapping.access_summary,
                    "dynamic_role_possible": mapping.dynamic_role_possible,
                    "dynamic_role_reason": mapping.dynamic_role_reason,
                }
            )
        for policy in parsed.role_policies.values():
            if not policy.rules:
                acl_rows.append(
                    {
                        "controller": policy.controller,
                        "role": policy.role,
                        "acl": ", ".join(policy.acl_names),
                        "sequence": "",
                        "action": "",
                        "source": "",
                        "destination": "",
                        "source_interpretation": "",
                        "destination_interpretation": "",
                        "service": "",
                        "role_user_network": _role_network_summary(parsed, policy.role),
                        "access_summary": policy.access_summary,
                        "access_flags": ", ".join(policy.access_flags),
                        "raw_rule": "",
                    }
                )
            for rule in policy.rules:
                acl_rows.append(
                    {
                        "controller": policy.controller,
                        "role": policy.role,
                        "acl": rule.acl,
                        "sequence": rule.sequence,
                        "action": rule.action,
                        "source": rule.source,
                        "destination": rule.destination,
                        "source_interpretation": _acl_field_interpretation(rule.source),
                        "destination_interpretation": _acl_field_interpretation(rule.destination),
                        "service": rule.service,
                        "role_user_network": _role_network_summary(parsed, policy.role),
                        "access_summary": policy.access_summary,
                        "access_flags": ", ".join(policy.access_flags),
                        "raw_rule": rule.raw,
                    }
                )
        for alias, entries in sorted(parsed.netdestination_aliases.items()):
            if not entries:
                alias_rows.append(
                    {
                        "controller": parsed.controller.name,
                        "alias": alias,
                        "sequence": "",
                        "entry_type": "",
                        "value": "",
                        "raw": "",
                    }
                )
            for entry in entries:
                alias_rows.append(
                    {
                        "controller": entry.controller,
                        "alias": entry.alias,
                        "sequence": entry.sequence,
                        "entry_type": entry.entry_type,
                        "value": entry.value,
                        "raw": entry.raw,
                    }
                )
        unresolved_rows.extend(parsed.unresolved)

    raw_rows: list[dict[str, Any]] = []
    for result in collection_results:
        raw_rows.extend(result.command_status_rows())

    overview_rows = []
    for parsed in parsed_controllers:
        controller = parsed.controller.name
        overview_rows.append(
            {
                "controller": controller,
                "ssid_count": len({row["ssid"] for row in ssid_rows if row["controller"] == controller}),
                "role_count": len(parsed.role_policies),
                "acl_rule_count": sum(
                    len(policy.rules) for policy in parsed.role_policies.values()
                ),
                "alias_count": len(parsed.netdestination_aliases),
                "unresolved_count": len(parsed.unresolved),
            }
        )

    return {
        "Overview": pd.DataFrame(overview_rows),
        "SSID_Role_Map": pd.DataFrame(ssid_rows),
        "Role_Network_Context": pd.DataFrame(role_network_rows),
        "Role_ACL_Detail": pd.DataFrame(acl_rows),
        "Alias_Detail": pd.DataFrame(alias_rows),
        "Unresolved": pd.DataFrame(unresolved_rows),
        "Raw_Commands": pd.DataFrame(raw_rows),
    }


def _role_network_summary(parsed: ParsedController, role: str) -> str:
    networks = [
        context.role_user_network
        for context in parsed.role_network_contexts
        if context.role == role and context.role_user_network
    ]
    return ", ".join(dict.fromkeys(networks)) or "Unknown"


def _acl_field_interpretation(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "user":
        return "User IP (current client assigned to this role)"
    if normalized == "any":
        return "Any (0.0.0.0/0)"
    return ""


def _write_excel(path: Path, frames: dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, frame in frames.items():
            frame.to_excel(writer, index=False, sheet_name=sheet_name)
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = "A2"
            if worksheet.max_row >= 1 and worksheet.max_column >= 1:
                worksheet.auto_filter.ref = worksheet.dimensions
            for cell in worksheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E78")
            for column_cells in worksheet.columns:
                max_length = 8
                for cell in column_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, min(len(value), 80))
                worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = max_length + 2


def _write_html(path: Path, frames: dict[str, pd.DataFrame]) -> None:
    overview = frames["Overview"].to_dict(orient="records")
    role_network_rows = frames["Role_Network_Context"].to_dict(orient="records")
    acl_rows = frames["Role_ACL_Detail"].to_dict(orient="records")
    alias_rows = frames["Alias_Detail"].to_dict(orient="records")
    alias_lookup = _group_by_alias(alias_rows)
    role_user_counts = _role_observed_user_counts(role_network_rows)
    unresolved_count = len(frames["Unresolved"])

    cards = "\n".join(
        f"""
        <section class="metric">
          <span>{escape(str(row.get('controller', '')))}</span>
          <strong>{escape(str(row.get('ssid_count', 0)))}</strong>
          <small>SSID / Role {escape(str(row.get('role_count', 0)))} / Alias {escape(str(row.get('alias_count', 0)))} / Unresolved {escape(str(row.get('unresolved_count', 0)))}</small>
        </section>
        """
        for row in overview
    )

    acl_by_role: dict[str, list[dict[str, Any]]] = {}
    for row in acl_rows:
        acl_by_role.setdefault(str(row.get("role", "")), []).append(row)

    role_items = [
        {
            "role": role,
            "rows": _sort_acl_rows_for_role(role, rows),
            "user_count": role_user_counts.get(role, 0),
            "panel_id": f"role-panel-{index}",
        }
        for index, (role, rows) in enumerate(
            sorted(
                acl_by_role.items(),
                key=lambda item: (-role_user_counts.get(item[0], 0), item[0].lower()),
            ),
            start=1,
        )
    ]
    role_buttons = "\n".join(
        f"""
        <button class="role-tab" type="button" role="tab" data-panel-id="{escape(str(item['panel_id']))}"
          aria-controls="{escape(str(item['panel_id']))}" aria-selected="{'true' if index == 1 else 'false'}">
          <span class="role-tab-name">{escape(str(item['role']))}</span>
          <span class="role-tab-meta">{len(item['rows'])} rules / {item['user_count']} users</span>
        </button>
        """
        for index, item in enumerate(role_items, start=1)
    )
    acl_sections = "\n".join(
        f"""
        <section class="acl-section role-panel" id="{escape(str(item['panel_id']))}" data-role="{escape(str(item['role']))}" {'hidden' if index != 1 else ''}>
          <div class="acl-section-header">
            <h3>{escape(str(item['role']))}</h3>
            <span>{len(item['rows'])} rules / {item['user_count']} observed users</span>
          </div>
          <table>
            <thead><tr><th>ACL</th><th>#</th><th>Action</th><th>Source</th><th>Destination</th><th>Service</th><th class="raw-column">Raw</th><th>Comment</th></tr></thead>
            <tbody>
              {_acl_rows_html(str(item['role']), item['rows'], alias_lookup)}
            </tbody>
          </table>
        </section>
        """
        for index, item in enumerate(role_items, start=1)
    )

    html = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WLC SSID Role ACL Report</title>
  <style>
    :root {{
      --bg: #f5f7fa;
      --panel: #ffffff;
      --text: #172033;
      --muted: #667085;
      --line: #d0d5dd;
      --accent: #0f6cbd;
      --accent-2: #0b7a75;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Malgun Gothic", Arial, sans-serif;
      color: var(--text);
      background: var(--bg);
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 20px 28px;
    }}
    h1 {{ margin: 0; font-size: 24px; letter-spacing: 0; }}
    main {{ padding: 24px 28px 40px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .metric span, .metric small {{ color: var(--muted); display: block; }}
    .metric strong {{ font-size: 28px; display: block; margin: 4px 0; }}
    .report-actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 18px 0 10px;
    }}
    .report-action {{
      background: #0f6cbd;
      border: 0;
      border-radius: 6px;
      color: #ffffff;
      cursor: pointer;
      font-size: 13px;
      padding: 10px 12px;
    }}
    .report-action.secondary {{ background: #e5eef8; color: #15324b; }}
    .role-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 10px 0 12px;
    }}
    .role-tab {{
      align-items: flex-start;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 8px;
      color: var(--text);
      cursor: pointer;
      display: inline-flex;
      flex-direction: column;
      gap: 3px;
      min-width: 150px;
      padding: 9px 12px;
      text-align: left;
    }}
    .role-tab[aria-selected="true"] {{
      background: #eef6ff;
      border-color: #84caff;
      color: #175cd3;
      font-weight: 600;
    }}
    .role-tab-name {{ font-size: 13px; }}
    .role-tab-meta {{ color: var(--muted); font-size: 11px; font-weight: 400; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--panel); }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; font-size: 13px; }}
    th {{ background: #1f4e78; color: #fff; position: sticky; top: 0; }}
    .raw-column {{ display: none; }}
    body.raw-visible .raw-column {{ display: table-cell; }}
    .alias-prefix {{
      color: var(--muted);
      margin-right: 4px;
    }}
    .alias-link {{
      border: 1px solid #a6c8ff;
      background: #eef6ff;
      color: #0f4c81;
      border-radius: 999px;
      cursor: pointer;
      font: inherit;
      padding: 2px 8px;
    }}
    .alias-link:hover {{ background: #dbeafe; }}
    .alias-detail-row[hidden] {{ display: none; }}
    .alias-detail {{
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
    }}
    .alias-detail-title {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
      text-transform: uppercase;
    }}
    .alias-chip {{
      align-items: center;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 999px;
      display: inline-flex;
      gap: 6px;
      margin: 3px 6px 3px 0;
      padding: 4px 8px;
    }}
    .alias-type {{
      border-radius: 999px;
      color: #ffffff;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0;
      padding: 2px 6px;
    }}
    .alias-type-host {{ background: #0f6cbd; }}
    .alias-type-network {{ background: #0b7a75; }}
    .alias-type-range {{ background: #c2410c; }}
    .alias-type-name {{ background: #6d28d9; }}
    .alias-type-raw {{ background: #667085; }}
    .acl-section {{
      margin-top: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .acl-section-header {{
      align-items: center;
      display: flex;
      gap: 10px;
      justify-content: space-between;
      padding: 12px 14px;
    }}
    .acl-section-header h3 {{ font-size: 15px; margin: 0; }}
    .acl-section-header span {{ color: var(--muted); font-size: 12px; }}
    .raw {{ font-family: Consolas, monospace; white-space: pre-wrap; }}
    .comment-cell {{ min-width: 220px; width: 24%; }}
    .comment-input {{
      border: 1px solid var(--line);
      border-radius: 6px;
      font-family: inherit;
      font-size: 13px;
      min-height: 74px;
      padding: 8px 10px;
      resize: vertical;
      width: 100%;
    }}
    .comment-print {{
      display: none;
      white-space: pre-wrap;
    }}
    .comment-status {{
      color: var(--muted);
      font-size: 11px;
      margin-top: 4px;
    }}
    .comment-status[data-state="saved"],
    .comment-status[data-state="restored"] {{
      color: #05603a;
    }}
    .comment-status[data-state="unavailable"] {{
      color: #b42318;
    }}
    .notice {{ color: var(--muted); margin: 8px 0 0; }}
    @media print {{
      body {{ background: #ffffff; }}
      header, main {{ padding: 14px 18px; }}
      .no-print {{ display: none !important; }}
      .acl-section {{ break-inside: auto; }}
      th {{ position: static; }}
      .alias-link {{
        background: transparent;
        border: 0;
        color: inherit;
        padding: 0;
      }}
      .comment-input {{ display: none; }}
      .comment-print {{
        display: block;
        min-height: 20px;
        white-space: pre-wrap;
      }}
      .comment-status {{ display: none; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>WLC SSID Role ACL Report</h1>
    <p class="notice">생성시각: {escape(datetime.now().isoformat(timespec='seconds'))} / Unresolved: {unresolved_count}</p>
  </header>
  <main>
    <div class="metrics">{cards}</div>
    <div class="report-actions no-print">
      <button id="save-commented-html" class="report-action" type="button">주석 포함 HTML 저장</button>
      <button id="print-pdf" class="report-action secondary" type="button">PDF 저장/인쇄</button>
      <button id="toggle-raw" class="report-action secondary" type="button" aria-pressed="false">Raw 보기</button>
    </div>
    <h2>Role ACL Detail</h2>
    <div class="role-tabs no-print" role="tablist" aria-label="Role ACL list">
      {role_buttons}
    </div>
    {acl_sections}
  </main>
  <textarea id="acl-comments-data" hidden>{{}}</textarea>
  <script>
    const roleTabs = Array.from(document.querySelectorAll('.role-tab'));
    const rolePanels = Array.from(document.querySelectorAll('.role-panel'));
    const rawToggleButton = document.querySelector('#toggle-raw');
    let selectedRolePanelId = roleTabs.find((button) => button.getAttribute('aria-selected') === 'true')?.dataset.panelId || roleTabs[0]?.dataset.panelId || '';

    function syncRawToggleButton() {{
      if (!rawToggleButton) {{
        return;
      }}
      const rawVisible = document.body.classList.contains('raw-visible');
      rawToggleButton.textContent = rawVisible ? 'Raw 숨김' : 'Raw 보기';
      rawToggleButton.setAttribute('aria-pressed', String(rawVisible));
    }}

    if (rawToggleButton) {{
      rawToggleButton.addEventListener('click', () => {{
        document.body.classList.toggle('raw-visible');
        syncRawToggleButton();
      }});
      syncRawToggleButton();
    }}

    function selectRolePanel(panelId) {{
      selectedRolePanelId = panelId || selectedRolePanelId;
      for (const panel of rolePanels) {{
        panel.hidden = panel.id !== selectedRolePanelId;
      }}
      for (const button of roleTabs) {{
        button.setAttribute('aria-selected', String(button.dataset.panelId === selectedRolePanelId));
      }}
    }}

    for (const button of roleTabs) {{
      button.addEventListener('click', () => {{
        selectRolePanel(button.dataset.panelId);
      }});
    }}
    if (selectedRolePanelId) {{
      selectRolePanel(selectedRolePanelId);
    }}

    for (const button of document.querySelectorAll('.alias-link')) {{
      button.addEventListener('click', () => {{
        const detailId = button.dataset.detailId;
        const detail = document.getElementById(detailId);
        if (!detail) return;
        const isHidden = detail.hasAttribute('hidden');
        detail.toggleAttribute('hidden', !isHidden);
        button.setAttribute('aria-expanded', String(isHidden));
      }});
    }}
    const commentsDataElement = document.querySelector('#acl-comments-data');
    const commentInputs = Array.from(document.querySelectorAll('.comment-input'));
    const commentStorageKey = `wlc-role-acl-comments:${{location.pathname || document.title}}`;
    const commentStorageAvailable = (() => {{
      try {{
        localStorage.setItem('wlc-role-acl-storage-test', '1');
        localStorage.removeItem('wlc-role-acl-storage-test');
        return true;
      }} catch (_error) {{
        return false;
      }}
    }})();
    let aclComments = {{}};

    function readEmbeddedComments() {{
      try {{
        return JSON.parse(commentsDataElement.value || commentsDataElement.textContent || '{{}}');
      }} catch (_error) {{
        return {{}};
      }}
    }}

    function syncCommentsData() {{
      const text = JSON.stringify(aclComments, null, 2);
      commentsDataElement.value = text;
      commentsDataElement.textContent = text;
    }}

    function readStoredComments() {{
      if (!commentStorageAvailable) {{
        return {{}};
      }}
      try {{
        return JSON.parse(localStorage.getItem(commentStorageKey) || '{{}}');
      }} catch (_error) {{
        return {{}};
      }}
    }}

    function persistComments() {{
      if (!commentStorageAvailable) {{
        return;
      }}
      localStorage.setItem(commentStorageKey, JSON.stringify(aclComments));
    }}

    function setCommentStatus(input, text, state) {{
      const status = document.getElementById(`${{input.dataset.commentId}}-status`);
      if (!status) {{
        return;
      }}
      status.textContent = text;
      status.dataset.state = state || '';
    }}

    function updateCommentPrint(input) {{
      const printValue = document.getElementById(`${{input.dataset.commentId}}-print`);
      if (printValue) {{
        printValue.textContent = input.value || '';
      }}
    }}

    function collectComments() {{
      aclComments = {{}};
      for (const input of commentInputs) {{
        if (input.value) {{
          aclComments[input.dataset.commentId] = input.value;
        }}
        updateCommentPrint(input);
      }}
      syncCommentsData();
      persistComments();
    }}

    function syncTextareaDomValues() {{
      for (const input of commentInputs) {{
        input.textContent = input.value;
      }}
    }}

    function preparePrint() {{
      collectComments();
      for (const panel of rolePanels) {{
        panel.hidden = false;
      }}
      for (const detail of document.querySelectorAll('.alias-detail-row')) {{
        detail.hidden = false;
      }}
      for (const button of document.querySelectorAll('.alias-link')) {{
        button.setAttribute('aria-expanded', 'true');
      }}
    }}

    function restoreScreenView() {{
      if (selectedRolePanelId) {{
        selectRolePanel(selectedRolePanelId);
      }}
    }}

    function saveCommentedHtml() {{
      collectComments();
      syncTextareaDomValues();
      const html = '<!doctype html>\\n' + document.documentElement.outerHTML;
      const blob = new Blob([html], {{ type: 'text/html;charset=utf-8' }});
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `ssid_role_acl_report_commented_${{stamp}}.html`;
      document.body.appendChild(link);
      link.click();
      URL.revokeObjectURL(link.href);
      link.remove();
    }}

    const embeddedComments = readEmbeddedComments();
    const storedComments = readStoredComments();
    const hasStoredComments = Object.keys(storedComments).length > 0;
    aclComments = Object.assign({{}}, embeddedComments, storedComments);
    for (const input of commentInputs) {{
      input.value = aclComments[input.dataset.commentId] || '';
      updateCommentPrint(input);
      if (!commentStorageAvailable) {{
        setCommentStatus(input, '브라우저 자동 저장 불가', 'unavailable');
      }} else if (hasStoredComments && input.value) {{
        setCommentStatus(input, '임시저장 복원됨', 'restored');
      }} else {{
        setCommentStatus(input, '입력 시 자동 저장', '');
      }}
      input.addEventListener('input', () => {{
        collectComments();
        setCommentStatus(input, '저장됨', 'saved');
      }});
    }}
    syncCommentsData();
    persistComments();

    document.querySelector('#save-commented-html').addEventListener('click', saveCommentedHtml);
    document.querySelector('#print-pdf').addEventListener('click', () => {{
      preparePrint();
      window.print();
    }});
    window.addEventListener('beforeprint', preparePrint);
    window.addEventListener('afterprint', restoreScreenView);
  </script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _acl_rows_html(
    role: str,
    rows: list[dict[str, Any]],
    alias_lookup: dict[str, list[dict[str, Any]]],
) -> str:
    rendered = []
    for index, row in enumerate(rows, start=1):
        comment_id = f"acl-comment-{_safe_dom_id(role)}-{index}"
        detail_id = f"alias-detail-{_safe_dom_id(role)}-{index}"
        source_alias = _alias_name_from_field(str(row.get("source", "")))
        destination_alias = _alias_name_from_field(str(row.get("destination", "")))
        detail_html = _inline_alias_detail_html(
            detail_id=detail_id,
            source_alias=source_alias,
            destination_alias=destination_alias,
            alias_lookup=alias_lookup,
        )
        rendered.append(
            f"""
            <tr>
              <td>{escape(str(row.get('acl', '')))}</td>
              <td>{escape(str(row.get('sequence', '')))}</td>
              <td>{escape(str(row.get('action', '')))}</td>
              <td>{_acl_field_html(str(row.get('source', '')), detail_id, str(row.get('source_interpretation', '')))}</td>
              <td>{_acl_field_html(str(row.get('destination', '')), detail_id, str(row.get('destination_interpretation', '')))}</td>
              <td>{escape(str(row.get('service', '')))}</td>
              <td class="raw raw-column">{escape(str(row.get('raw_rule', '')))}</td>
              <td class="comment-cell">
                <textarea class="comment-input" data-comment-id="{escape(comment_id)}" aria-label="ACL comment"></textarea>
                <div id="{escape(comment_id)}-status" class="comment-status">입력 시 자동 저장</div>
                <div id="{escape(comment_id)}-print" class="comment-print"></div>
              </td>
            </tr>
            {detail_html}
            """
        )
    return "".join(rendered)


def _acl_field_html(value: str, detail_id: str, interpretation: str = "") -> str:
    alias = _alias_name_from_field(value)
    if not alias:
        field = escape(value)
    else:
        field = (
        f'<span class="alias-prefix">alias</span>'
        f'<button class="alias-link" type="button" data-detail-id="{escape(detail_id)}" '
        f'aria-expanded="false">{escape(alias)}</button>'
        )
    if not interpretation:
        return field
    return f'{field}<div class="notice">{escape(interpretation)}</div>'


def _inline_alias_detail_html(
    *,
    detail_id: str,
    source_alias: str,
    destination_alias: str,
    alias_lookup: dict[str, list[dict[str, Any]]],
) -> str:
    aliases: list[tuple[str, str]] = []
    if source_alias:
        aliases.append(("Source", source_alias))
    if destination_alias and destination_alias != source_alias:
        aliases.append(("Destination", destination_alias))
    if not aliases:
        return ""

    sections = []
    for position, alias in aliases:
        sections.append(
            f"""
            <div class="alias-detail-title">{escape(position)} alias: {escape(alias)}</div>
            <div>{_alias_chips_html(alias_lookup.get(alias, []))}</div>
            """
        )
    return f"""
    <tr id="{escape(detail_id)}" class="alias-detail-row" hidden>
      <td colspan="8">
        <div class="alias-detail">{''.join(sections)}</div>
      </td>
    </tr>
    """


def _alias_chips_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<span class="notice">Alias detail was not collected.</span>'
    return "".join(
        f"""
        <span class="alias-chip">
          <span class="alias-type alias-type-{_alias_type_class(str(row.get('entry_type', '')))}">{escape(_alias_type_label(str(row.get('entry_type', ''))))}</span>
          <span>{escape(str(row.get('value', '')))}</span>
        </span>
        """
        for row in rows
    )


def _alias_type_label(entry_type: str) -> str:
    normalized = entry_type.strip().lower()
    if normalized in {"host", "network", "range", "name"}:
        return normalized.upper()
    return "RAW"


def _alias_type_class(entry_type: str) -> str:
    normalized = entry_type.strip().lower()
    if normalized in {"host", "network", "range", "name"}:
        return normalized
    return "raw"


def _alias_name_from_field(value: str) -> str:
    stripped = value.strip()
    if stripped.lower().startswith("alias "):
        return stripped.split(" ", 1)[1].strip()
    return ""


def _group_by_alias(alias_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in alias_rows:
        grouped.setdefault(str(row.get("alias", "")), []).append(row)
    return dict(sorted(grouped.items()))


def _role_observed_user_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        role = str(row.get("role", ""))
        if not role:
            continue
        counts[role] = max(counts.get(role, 0), _int_value(row.get("observed_user_count", 0)))
    return counts


def _sort_acl_rows_for_role(role: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    role_name = role.strip()
    return [
        row
        for _, row in sorted(
            enumerate(rows),
            key=lambda item: (
                0 if str(item[1].get("acl", "")).strip() == role_name else 1,
                item[0],
            ),
        )
    ]


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_dom_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-") or "item"


def _safe_file_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)
