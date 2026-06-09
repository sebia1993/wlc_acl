from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .acl_evaluator import access_rule_id, build_access_check_data
from .aos8_parser import parse_controller_config
from .models import CollectionResult, ParsedController, RoleNetworkDefinition


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
    local_role_networks: list[RoleNetworkDefinition] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = output_dir / "ssid_role_acl_report.xlsx"
    html_path = output_dir / "ssid_role_acl_report.html"

    local_role_networks = local_role_networks or []
    frames = _build_frames(parsed_controllers, collection_results, local_role_networks)
    _write_excel(workbook_path, frames)
    _write_html(html_path, frames, local_role_networks_enabled=bool(local_role_networks))
    return {"xlsx": workbook_path, "html": html_path}


def _build_frames(
    parsed_controllers: list[ParsedController],
    collection_results: list[CollectionResult],
    local_role_networks: list[RoleNetworkDefinition] | None = None,
) -> dict[str, pd.DataFrame]:
    local_role_networks = local_role_networks or []
    local_lookup = _group_local_role_networks(local_role_networks)
    local_mapping_enabled = bool(local_role_networks)
    ssid_rows: list[dict[str, Any]] = []
    role_network_rows: list[dict[str, Any]] = []
    local_network_rows: list[dict[str, Any]] = []
    acl_rows: list[dict[str, Any]] = []
    alias_rows: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, Any]] = []

    for parsed in parsed_controllers:
        local_status_by_role = _local_network_status_by_role(parsed, local_lookup, local_mapping_enabled)
        local_network_rows.extend(
            _local_network_rows(parsed, local_lookup, local_status_by_role, local_mapping_enabled)
        )
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
            local_status = local_status_by_role.get(mapping.role, _empty_local_network_status())
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
                    "local_role_networks": local_status["networks"],
                    "local_network_status": local_status["status"],
                    "local_network_notes": local_status["notes"],
                    "observed_user_count": mapping.observed_user_count,
                    "forward_mode": mapping.forward_mode,
                    "access_summary": mapping.access_summary,
                    "dynamic_role_possible": mapping.dynamic_role_possible,
                    "dynamic_role_reason": mapping.dynamic_role_reason,
                }
            )
        for policy in parsed.role_policies.values():
            local_status = local_status_by_role.get(policy.role, _empty_local_network_status())
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
                        "local_role_networks": local_status["networks"],
                        "local_network_status": local_status["status"],
                        "local_network_notes": local_status["notes"],
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
                        "source_interpretation": _acl_field_interpretation(
                            rule.source,
                            local_networks=local_status["networks"],
                            local_mapping_enabled=local_mapping_enabled,
                        ),
                        "destination_interpretation": _acl_field_interpretation(
                            rule.destination,
                            local_networks=local_status["networks"],
                            local_mapping_enabled=local_mapping_enabled,
                        ),
                        "service": rule.service,
                        "role_user_network": _role_network_summary(parsed, policy.role),
                        "local_role_networks": local_status["networks"],
                        "local_network_status": local_status["status"],
                        "local_network_notes": local_status["notes"],
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
        "Local_Role_Networks": pd.DataFrame(
            local_network_rows,
            columns=[
                "controller",
                "role",
                "local_role_network",
                "subnet_mask",
                "source_file",
                "source_row",
                "status",
                "notes",
                "wlc_configured_subnets",
            ],
        ),
        "Role_ACL_Detail": pd.DataFrame(acl_rows),
        "Alias_Detail": pd.DataFrame(alias_rows),
        "Unresolved": pd.DataFrame(unresolved_rows),
        "Raw_Commands": pd.DataFrame(raw_rows),
    }


def _group_local_role_networks(
    definitions: list[RoleNetworkDefinition],
) -> dict[str, list[RoleNetworkDefinition]]:
    grouped: dict[str, list[RoleNetworkDefinition]] = {}
    for definition in definitions:
        grouped.setdefault(definition.role.casefold(), []).append(definition)
    return grouped


def _local_network_status_by_role(
    parsed: ParsedController,
    local_lookup: dict[str, list[RoleNetworkDefinition]],
    local_mapping_enabled: bool,
) -> dict[str, dict[str, str]]:
    if not local_mapping_enabled:
        return {}

    collected_roles = (
        set(parsed.role_policies)
        | set(parsed.user_role_observations)
        | {mapping.role for mapping in parsed.ssid_role_mappings if mapping.role}
    )
    collected_role_keys = {role.casefold() for role in collected_roles}
    local_roles = {
        definitions[0].role
        for definitions in local_lookup.values()
        if definitions and definitions[0].role.casefold() not in collected_role_keys
    }
    statuses: dict[str, dict[str, str]] = {}

    for role in sorted(collected_roles | local_roles, key=str.casefold):
        definitions = local_lookup.get(role.casefold(), [])
        local_networks = [definition.network for definition in definitions]
        wlc_networks = _wlc_configured_subnets_for_role(parsed, role)

        if role.casefold() not in collected_role_keys:
            status = "Role not collected"
            notes = "Role exists in the local Excel file, but it was not collected from this WLC."
        elif not definitions:
            status = "Local mapping missing"
            notes = "Role was collected from WLC but was not found in the local Role network Excel."
        elif wlc_networks and set(local_networks) != set(wlc_networks):
            status = "Mismatch"
            notes = f"Local: {', '.join(local_networks)} / WLC collected: {', '.join(wlc_networks)}"
        elif wlc_networks:
            status = "Matched"
            notes = "Local Role network matches WLC configured subnet evidence."
        else:
            status = "Local mapping loaded"
            notes = "No reliable WLC subnet was available for comparison."

        statuses[role] = {
            "networks": ", ".join(local_networks),
            "status": status,
            "notes": notes,
            "wlc_configured_subnets": ", ".join(wlc_networks),
        }
    return statuses


def _local_network_rows(
    parsed: ParsedController,
    local_lookup: dict[str, list[RoleNetworkDefinition]],
    status_by_role: dict[str, dict[str, str]],
    local_mapping_enabled: bool,
) -> list[dict[str, Any]]:
    if not local_mapping_enabled:
        return []

    rows: list[dict[str, Any]] = []
    for role, status in sorted(status_by_role.items(), key=lambda item: item[0].casefold()):
        definitions = local_lookup.get(role.casefold(), [])
        if not definitions:
            rows.append(
                {
                    "controller": parsed.controller.name,
                    "role": role,
                    "local_role_network": "",
                    "subnet_mask": "",
                    "source_file": "",
                    "source_row": "",
                    "status": status["status"],
                    "notes": status["notes"],
                    "wlc_configured_subnets": status["wlc_configured_subnets"],
                }
            )
            continue
        for definition in definitions:
            rows.append(
                {
                    "controller": parsed.controller.name,
                    "role": role,
                    "local_role_network": definition.network,
                    "subnet_mask": definition.subnet_mask,
                    "source_file": definition.source_file,
                    "source_row": definition.source_row,
                    "status": status["status"],
                    "notes": status["notes"],
                    "wlc_configured_subnets": status["wlc_configured_subnets"],
                }
            )
    return rows


def _empty_local_network_status() -> dict[str, str]:
    return {
        "networks": "",
        "status": "",
        "notes": "",
        "wlc_configured_subnets": "",
    }


def _wlc_configured_subnets_for_role(parsed: ParsedController, role: str) -> list[str]:
    networks = [
        context.configured_subnet
        for context in parsed.role_network_contexts
        if context.role.casefold() == role.casefold()
        and context.configured_subnet
        and context.configured_subnet.casefold() != "unknown"
    ]
    return list(dict.fromkeys(networks))


def _role_network_summary(parsed: ParsedController, role: str) -> str:
    networks = [
        context.role_user_network
        for context in parsed.role_network_contexts
        if context.role == role and context.role_user_network
    ]
    return ", ".join(dict.fromkeys(networks)) or "Unknown"


def _acl_field_interpretation(
    value: str,
    *,
    local_networks: str = "",
    local_mapping_enabled: bool = False,
) -> str:
    normalized = value.strip().lower()
    if normalized == "user":
        if local_networks:
            return f"User IP (current client assigned to this role). Local Role Network: {local_networks}"
        if local_mapping_enabled:
            return "User IP (current client assigned to this role). Local Role Network: mapping missing."
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


def _write_html(
    path: Path,
    frames: dict[str, pd.DataFrame],
    *,
    local_role_networks_enabled: bool = False,
) -> None:
    overview = frames["Overview"].to_dict(orient="records")
    role_network_rows = frames["Role_Network_Context"].to_dict(orient="records")
    local_network_rows = frames["Local_Role_Networks"].to_dict(orient="records")
    acl_rows = frames["Role_ACL_Detail"].to_dict(orient="records")
    alias_rows = frames["Alias_Detail"].to_dict(orient="records")
    alias_lookup = _group_by_alias(alias_rows)
    local_network_lookup = _group_local_network_rows(local_network_rows)
    role_user_counts = _role_observed_user_counts(role_network_rows)
    raw_command_rows = frames["Raw_Commands"].to_dict(orient="records")
    user_table_counts_reliable = _user_table_counts_reliable(raw_command_rows)
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
            "rows": rows,
            "other_acl_count": _other_acl_row_count(role, rows),
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
    zero_user_hiding_enabled = (
        user_table_counts_reliable
        and any(_int_value(item["user_count"]) > 0 for item in role_items)
        and any(_int_value(item["user_count"]) == 0 for item in role_items)
    )
    for item in role_items:
        item["zero_user_hidden"] = zero_user_hiding_enabled and _int_value(item["user_count"]) == 0
    zero_user_hidden_count = sum(1 for item in role_items if item["zero_user_hidden"])
    selected_panel_id = next(
        (str(item["panel_id"]) for item in role_items if not item["zero_user_hidden"]),
        str(role_items[0]["panel_id"]) if role_items else "",
    )
    zero_user_role_controls = _zero_user_role_controls_html(
        enabled=zero_user_hiding_enabled,
        hidden_count=zero_user_hidden_count,
        user_table_counts_reliable=user_table_counts_reliable,
        role_items=role_items,
    )
    access_check_data = build_access_check_data(role_items, alias_rows, local_network_rows)
    access_check_json = _json_for_html(access_check_data)
    access_check_controls = _access_check_controls_html(access_check_data)
    access_check_css = _access_check_css()
    access_check_script = _access_check_script()
    role_buttons = "\n".join(
        f"""
        <button class="role-tab{_zero_user_role_class(bool(item['zero_user_hidden']))}" type="button" role="tab" data-panel-id="{escape(str(item['panel_id']))}"
          aria-controls="{escape(str(item['panel_id']))}" aria-selected="{'true' if str(item['panel_id']) == selected_panel_id else 'false'}"{_zero_user_role_attrs(bool(item['zero_user_hidden']))}{_hidden_attr(bool(item['zero_user_hidden']))}>
          <span class="role-tab-name">{escape(str(item['role']))}</span>
          <span class="role-tab-meta">{len(item['rows'])} rules / {item['user_count']} users</span>
        </button>
        """
        for index, item in enumerate(role_items, start=1)
    )
    acl_sections = "\n".join(
        f"""
        <section class="acl-section role-panel{_zero_user_role_class(bool(item['zero_user_hidden']))}" id="{escape(str(item['panel_id']))}" data-role="{escape(str(item['role']))}"{_zero_user_role_attrs(bool(item['zero_user_hidden']))}{_hidden_attr(bool(item['zero_user_hidden']) or str(item['panel_id']) != selected_panel_id)}>
          <div class="acl-section-header">
            <h3>{escape(str(item['role']))}</h3>
            <span>{len(item['rows'])} rules / {item['user_count']} observed users{_other_acl_meta_text(int(item['other_acl_count']))}</span>
          </div>
          {_local_role_network_html(local_network_lookup.get(str(item['role']), []), local_role_networks_enabled)}
          {_other_acl_toggle_html(str(item['panel_id']), int(item['other_acl_count']))}
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
    .zero-user-role[hidden] {{ display: none; }}
    .zero-user-role-controls {{
      align-items: center;
      display: flex;
      gap: 8px;
      margin: 6px 0 10px;
    }}
    .zero-user-role-notice {{
      background: #fff7ed;
      border: 1px solid #fed7aa;
      border-radius: 6px;
      color: #9a3412;
      font-size: 12px;
      margin: 6px 0 10px;
      padding: 8px 10px;
    }}
    .local-network {{
      background: #f8fafc;
      border-top: 1px solid var(--line);
      padding: 10px 14px 12px;
    }}
    .local-network-title {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 7px;
      text-transform: uppercase;
    }}
    .local-subnet-pill {{
      align-items: center;
      background: #ffffff;
      border: 1px solid var(--line);
      border-radius: 999px;
      display: inline-flex;
      gap: 6px;
      margin: 3px 6px 3px 0;
      padding: 4px 8px;
    }}
    .local-network-status {{
      border-radius: 999px;
      color: #ffffff;
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      margin: 3px 6px 3px 0;
      padding: 4px 8px;
    }}
    .local-network-status.status-matched {{ background: #05603a; }}
    .local-network-status.status-missing {{ background: #b42318; }}
    .local-network-status.status-mismatch {{ background: #c2410c; }}
    .local-network-status.status-loaded {{ background: #0f6cbd; }}
    .local-network-status.status-not-collected {{ background: #667085; }}
    .local-network-notes {{ color: var(--muted); font-size: 12px; margin-top: 5px; }}
    .acl-filter-actions {{
      background: #ffffff;
      border-top: 1px solid var(--line);
      padding: 9px 14px;
    }}
    .acl-filter-button {{
      background: #e5eef8;
      border: 0;
      border-radius: 6px;
      color: #15324b;
      cursor: pointer;
      font-size: 12px;
      padding: 8px 10px;
    }}
    .other-acl-rule[hidden] {{ display: none; }}
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
    {access_check_css}
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
    {access_check_controls}
    <h2>Role ACL Detail</h2>
    {zero_user_role_controls}
    <div class="role-tabs no-print" role="tablist" aria-label="Role ACL list">
      {role_buttons}
    </div>
    {acl_sections}
  </main>
  <script id="access-check-data" type="application/json">{access_check_json}</script>
  <textarea id="acl-comments-data" hidden>{{}}</textarea>
  <script>
    const roleTabs = Array.from(document.querySelectorAll('.role-tab'));
    const rolePanels = Array.from(document.querySelectorAll('.role-panel'));
    const rawToggleButton = document.querySelector('#toggle-raw');
    const zeroUserToggleButton = document.querySelector('#toggle-zero-user-roles');
    const otherAclToggles = Array.from(document.querySelectorAll('.toggle-other-acls'));
    let selectedRolePanelId = roleTabs.find((button) => button.getAttribute('aria-selected') === 'true' && !button.hidden)?.dataset.panelId || roleTabs.find((button) => !button.hidden)?.dataset.panelId || roleTabs[0]?.dataset.panelId || '';
    {access_check_script}

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

    function zeroUserRolesVisible() {{
      return !zeroUserToggleButton || zeroUserToggleButton.getAttribute('aria-pressed') === 'true';
    }}

    function firstVisibleRolePanelId() {{
      return roleTabs.find((button) => !button.hidden)?.dataset.panelId || roleTabs[0]?.dataset.panelId || '';
    }}

    function rolePanelIsAvailable(panelId) {{
      const button = roleTabs.find((item) => item.dataset.panelId === panelId);
      return Boolean(button && !button.hidden);
    }}

    function syncZeroUserToggleButton() {{
      if (!zeroUserToggleButton) {{
        return;
      }}
      const count = zeroUserToggleButton.dataset.zeroUserRoleCount || '0';
      const visible = zeroUserRolesVisible();
      zeroUserToggleButton.textContent = visible ? `Hide zero-user roles (${{count}})` : `Show zero-user roles (${{count}})`;
      zeroUserToggleButton.setAttribute('aria-pressed', String(visible));
    }}

    function syncZeroUserRoles() {{
      const visible = zeroUserRolesVisible();
      for (const item of document.querySelectorAll('.zero-user-role')) {{
        item.hidden = !visible;
      }}
      if (!rolePanelIsAvailable(selectedRolePanelId)) {{
        selectedRolePanelId = firstVisibleRolePanelId();
      }}
      if (selectedRolePanelId) {{
        selectRolePanel(selectedRolePanelId);
      }}
      syncZeroUserToggleButton();
    }}

    if (zeroUserToggleButton) {{
      zeroUserToggleButton.addEventListener('click', () => {{
        zeroUserToggleButton.setAttribute('aria-pressed', String(!zeroUserRolesVisible()));
        syncZeroUserRoles();
      }});
    }}

    function syncOtherAclButton(button) {{
      const count = button.dataset.otherAclCount || '0';
      const visible = button.getAttribute('aria-pressed') === 'true';
      button.textContent = visible ? `Hide other ACLs (${{count}})` : `Show other ACLs (${{count}})`;
    }}

    function syncOtherAclRows(button) {{
      const panel = button.closest('.role-panel');
      if (!panel) {{
        return;
      }}
      const visible = button.getAttribute('aria-pressed') === 'true';
      for (const row of panel.querySelectorAll('.other-acl-rule')) {{
        row.hidden = !visible;
      }}
      if (!visible) {{
        for (const link of panel.querySelectorAll('.other-acl-rule .alias-link')) {{
          const detail = document.getElementById(link.dataset.detailId);
          if (detail) {{
            detail.hidden = true;
          }}
          link.setAttribute('aria-expanded', 'false');
        }}
      }}
      syncOtherAclButton(button);
    }}

    for (const button of otherAclToggles) {{
      button.addEventListener('click', () => {{
        const visible = button.getAttribute('aria-pressed') === 'true';
        button.setAttribute('aria-pressed', String(!visible));
        syncOtherAclRows(button);
      }});
      syncOtherAclRows(button);
    }}

    function selectRolePanel(panelId) {{
      selectedRolePanelId = rolePanelIsAvailable(panelId) ? panelId : firstVisibleRolePanelId();
      for (const panel of rolePanels) {{
        const available = !panel.classList.contains('zero-user-role') || zeroUserRolesVisible();
        panel.hidden = !available || panel.id !== selectedRolePanelId;
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
    syncZeroUserRoles();

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
      for (const item of document.querySelectorAll('.zero-user-role')) {{
        item.hidden = false;
      }}
      for (const row of document.querySelectorAll('.other-acl-rule')) {{
        row.hidden = false;
      }}
      for (const detail of document.querySelectorAll('.alias-detail-row')) {{
        detail.hidden = false;
      }}
      for (const button of document.querySelectorAll('.alias-link')) {{
        button.setAttribute('aria-expanded', 'true');
      }}
    }}

    function restoreScreenView() {{
      syncZeroUserRoles();
      for (const button of otherAclToggles) {{
        syncOtherAclRows(button);
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


def _json_for_html(data: dict[str, Any]) -> str:
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _access_check_controls_html(access_check_data: dict[str, Any]) -> str:
    roles = access_check_data.get("roles", [])
    role_options = "".join(
        f"""
        <option value="{escape(str(role.get('role', '')))}">
          {escape(str(role.get('role', '')))} ({escape(str(role.get('userCount', 0)))} users)
        </option>
        """
        for role in roles
    )
    service_options = "".join(
        f'<option value="{escape(str(service))}">{escape(str(service))}</option>'
        for service in access_check_data.get("services", [])
    )
    disabled = " disabled" if not roles else ""
    return f"""
    <section class="access-check no-print" aria-label="Role access check">
      <div class="access-check-title">
        <h2>Access Check</h2>
      </div>
      <div class="access-check-grid">
        <label class="access-field">
          <span>Role</span>
          <select id="access-check-role"{disabled}>{role_options}</select>
        </label>
        <label class="access-field">
          <span>Source IP</span>
          <input id="access-check-source" type="text" inputmode="decimal" placeholder="10.10.10.10"{disabled}>
        </label>
        <label class="access-field">
          <span>Destination IP</span>
          <input id="access-check-destination" type="text" inputmode="decimal" placeholder="10.20.20.20"{disabled}>
        </label>
        <label class="access-field">
          <span>Service</span>
          <select id="access-check-service"{disabled}>
            <option value="">No service selected</option>
            {service_options}
          </select>
        </label>
        <button id="run-access-check" class="report-action access-run" type="button"{disabled}>Check</button>
      </div>
      <div id="access-check-result" class="access-check-result" data-status="empty" aria-live="polite">
        <span>No access check result.</span>
      </div>
    </section>
    """


def _access_check_css() -> str:
    return """
    .access-check {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 18px 0;
      padding: 14px;
    }
    .access-check-title {
      align-items: center;
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;
    }
    .access-check-title h2 {
      font-size: 18px;
      margin: 0;
    }
    .access-check-grid {
      align-items: end;
      display: grid;
      gap: 10px;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    }
    .access-field {
      display: flex;
      flex-direction: column;
      gap: 5px;
      min-width: 0;
    }
    .access-field span {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }
    .access-field input,
    .access-field select {
      border: 1px solid var(--line);
      border-radius: 6px;
      color: var(--text);
      font: inherit;
      min-height: 38px;
      padding: 8px 10px;
      width: 100%;
    }
    .access-run {
      min-height: 38px;
      width: 100%;
    }
    .access-check-result {
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-top: 12px;
      padding: 10px 12px;
    }
    .access-check-result[data-status="empty"] {
      color: var(--muted);
    }
    .access-check-result[data-status="allowed"] {
      background: #ecfdf3;
      border-color: #abefc6;
    }
    .access-check-result[data-status="blocked"] {
      background: #fef3f2;
      border-color: #fecdca;
    }
    .access-check-result[data-status="special"],
    .access-check-result[data-status="unknown"] {
      background: #fffaeb;
      border-color: #fedf89;
    }
    .access-check-result[data-status="error"] {
      background: #fef3f2;
      border-color: #fecdca;
      color: #b42318;
    }
    .access-result-title {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    .access-conditional {
      background: #f79009;
      border-radius: 999px;
      color: #ffffff;
      font-size: 11px;
      padding: 2px 7px;
    }
    .access-result-meta {
      display: grid;
      gap: 5px 12px;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      margin-top: 8px;
    }
    .access-result-meta div {
      min-width: 0;
    }
    .access-result-meta strong {
      color: var(--muted);
      display: block;
      font-size: 11px;
      text-transform: uppercase;
    }
    .access-warning-list {
      margin: 9px 0 0;
      padding-left: 18px;
    }
    .access-rule-match {
      background: #fffbeb;
      outline: 2px solid #f79009;
      outline-offset: -2px;
    }
    """


def _access_check_script() -> str:
    return """
    const accessCheckData = (() => {
      const dataElement = document.getElementById('access-check-data');
      if (!dataElement) {
        return { roles: [], services: [] };
      }
      try {
        return JSON.parse(dataElement.textContent || '{"roles":[],"services":[]}');
      } catch (_error) {
        return { roles: [], services: [] };
      }
    })();
    const accessRoleInput = document.getElementById('access-check-role');
    const accessSourceInput = document.getElementById('access-check-source');
    const accessDestinationInput = document.getElementById('access-check-destination');
    const accessServiceInput = document.getElementById('access-check-service');
    const accessRunButton = document.getElementById('run-access-check');
    const accessResultElement = document.getElementById('access-check-result');

    function accessEscapeHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function accessIpToNumber(value) {
      const parts = String(value || '').trim().split('.');
      if (parts.length !== 4) {
        throw new Error(`Invalid IPv4 address: ${value}`);
      }
      let number = 0;
      for (const part of parts) {
        if (!/^\\d+$/.test(part)) {
          throw new Error(`Invalid IPv4 address: ${value}`);
        }
        const octet = Number(part);
        if (!Number.isInteger(octet) || octet < 0 || octet > 255) {
          throw new Error(`Invalid IPv4 address: ${value}`);
        }
        number = number * 256 + octet;
      }
      return number;
    }

    function accessUnique(values) {
      return Array.from(new Set(values.filter(Boolean)));
    }

    function accessEndpointMatches(ipNumber, matchers, direction, sourceNumber, destinationNumber) {
      let matched = false;
      let uncertain = false;
      const warnings = [];
      for (const matcher of matchers || []) {
        const type = String(matcher.type || '').toLowerCase();
        if (type === 'any') {
          matched = true;
        } else if (type === 'user') {
          matched = matched || direction === 'source' || destinationNumber === sourceNumber;
        } else if (type === 'host' || type === 'network' || type === 'range') {
          const start = Number(matcher.start);
          const end = Number(matcher.end);
          if (Number.isFinite(start) && Number.isFinite(end) && start <= ipNumber && ipNumber <= end) {
            matched = true;
          }
        } else {
          uncertain = true;
          if (matcher.warning) {
            warnings.push(String(matcher.warning));
          }
        }
      }
      return { matched, uncertain, warnings: accessUnique(warnings) };
    }

    function accessServiceMatches(ruleService, selectedService) {
      const normalizedRuleService = String(ruleService || 'any').trim().toLowerCase() || 'any';
      const normalizedSelectedService = String(selectedService || '').trim().toLowerCase();
      if (!normalizedSelectedService) {
        if (normalizedRuleService === 'any') {
          return { matched: true, conditional: false, warnings: [] };
        }
        return {
          matched: true,
          conditional: true,
          warnings: [`Service was not selected; matched rule is limited to ${ruleService}.`],
        };
      }
      return {
        matched: normalizedRuleService === 'any' || normalizedRuleService === normalizedSelectedService,
        conditional: false,
        warnings: [],
      };
    }

    function accessActionVerdict(action) {
      const normalized = String(action || '').trim().toLowerCase();
      if (normalized === 'deny') {
        return { status: 'blocked', label: 'Blocked' };
      }
      if (normalized === 'permit') {
        return { status: 'allowed', label: 'Allowed' };
      }
      if (['src-nat', 'dst-nat', 'redirect', 'route', 'tunnel', 'forward'].includes(normalized)) {
        return { status: 'special', label: 'Allowed with NAT/Special Action' };
      }
      return { status: 'unknown', label: `Unknown action: ${action || 'not parsed'}` };
    }

    function accessLocalWarnings(roleData, sourceNumber, sourceText) {
      const networks = roleData.localNetworks || [];
      if (!networks.length) {
        return [];
      }
      const matched = networks.some((network) => Number(network.start) <= sourceNumber && sourceNumber <= Number(network.end));
      if (matched) {
        return [];
      }
      const labels = networks.map((network) => network.network || network.label).filter(Boolean).join(', ');
      return [`Source IP ${sourceText} is outside the local Role Network mapping: ${labels}`];
    }

    function accessClearHighlights() {
      for (const row of document.querySelectorAll('.access-rule-match')) {
        row.classList.remove('access-rule-match');
      }
    }

    function accessHighlightRule(ruleId) {
      if (!ruleId) {
        return;
      }
      const row = Array.from(document.querySelectorAll('[data-rule-id]')).find((item) => item.dataset.ruleId === ruleId);
      if (!row) {
        return;
      }
      const panel = row.closest('.role-panel');
      if (panel) {
        if (panel.classList.contains('zero-user-role') && zeroUserToggleButton && !zeroUserRolesVisible()) {
          zeroUserToggleButton.setAttribute('aria-pressed', 'true');
          syncZeroUserRoles();
        }
        if (typeof selectRolePanel === 'function') {
          selectRolePanel(panel.id);
        }
        if (row.classList.contains('other-acl-rule')) {
          const toggle = panel.querySelector('.toggle-other-acls');
          if (toggle) {
            toggle.setAttribute('aria-pressed', 'true');
            syncOtherAclRows(toggle);
          }
        }
      }
      row.classList.add('access-rule-match');
      row.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }

    function accessRenderResult(result) {
      if (!accessResultElement) {
        return;
      }
      accessResultElement.dataset.status = result.status || 'unknown';
      const warnings = accessUnique(result.warnings || []);
      const warningHtml = warnings.length
        ? `<ul class="access-warning-list">${warnings.map((warning) => `<li>${accessEscapeHtml(warning)}</li>`).join('')}</ul>`
        : '';
      const rule = result.matchedRule;
      const conditional = result.conditional ? '<span class="access-conditional">Conditional</span>' : '';
      const ruleHtml = rule
        ? `<div class="access-result-meta">
            <div><strong>ACL</strong>${accessEscapeHtml(rule.acl)}</div>
            <div><strong>Sequence</strong>${accessEscapeHtml(rule.sequence)}</div>
            <div><strong>Action</strong>${accessEscapeHtml(rule.action)}</div>
            <div><strong>Service</strong>${accessEscapeHtml(rule.service || 'any')}</div>
            <div><strong>Source</strong>${accessEscapeHtml(rule.source)}</div>
            <div><strong>Destination</strong>${accessEscapeHtml(rule.destination)}</div>
            <div><strong>Raw</strong>${accessEscapeHtml(rule.raw)}</div>
          </div>`
        : '<div class="access-result-meta"><div><strong>ACL</strong>No ACL rule matched.</div></div>';
      accessResultElement.innerHTML = `
        <div class="access-result-title">
          <span>${accessEscapeHtml(result.verdict || '')}</span>
          ${conditional}
        </div>
        ${ruleHtml}
        ${warningHtml}
      `;
    }

    function runAccessCheck() {
      accessClearHighlights();
      const roleName = accessRoleInput?.value || '';
      const sourceText = accessSourceInput?.value || '';
      const destinationText = accessDestinationInput?.value || '';
      let sourceNumber;
      let destinationNumber;
      try {
        sourceNumber = accessIpToNumber(sourceText);
        destinationNumber = accessIpToNumber(destinationText);
      } catch (error) {
        accessRenderResult({ status: 'error', verdict: error.message, warnings: [] });
        return;
      }
      const roleData = (accessCheckData.roles || []).find((role) => String(role.role || '').toLowerCase() === roleName.toLowerCase());
      if (!roleData) {
        accessRenderResult({ status: 'error', verdict: `Role not found: ${roleName}`, warnings: [] });
        return;
      }
      const selectedService = accessServiceInput?.value || '';
      const localWarnings = accessLocalWarnings(roleData, sourceNumber, sourceText);
      let uncertainCount = 0;
      for (const rule of roleData.rules || []) {
        const sourceResult = accessEndpointMatches(sourceNumber, rule.sourceMatchers, 'source', sourceNumber, destinationNumber);
        const destinationResult = accessEndpointMatches(destinationNumber, rule.destinationMatchers, 'destination', sourceNumber, destinationNumber);
        if (!sourceResult.matched || !destinationResult.matched) {
          if (sourceResult.uncertain || destinationResult.uncertain) {
            uncertainCount += 1;
          }
          continue;
        }
        const serviceResult = accessServiceMatches(rule.service, selectedService);
        if (!serviceResult.matched) {
          continue;
        }
        const verdict = accessActionVerdict(rule.action);
        const warnings = accessUnique([
          ...localWarnings,
          ...sourceResult.warnings,
          ...destinationResult.warnings,
          ...serviceResult.warnings,
          ...(rule.warnings || []),
        ]);
        accessRenderResult({
          status: verdict.status,
          verdict: verdict.label,
          conditional: serviceResult.conditional,
          matchedRule: rule,
          warnings,
        });
        accessHighlightRule(rule.id);
        return;
      }
      const warnings = [...localWarnings];
      if (uncertainCount > 0) {
        warnings.push(`${uncertainCount} rule(s) could not be fully evaluated because alias/name data is incomplete.`);
      }
      accessRenderResult({
        status: 'blocked',
        verdict: 'Implicit deny',
        conditional: false,
        matchedRule: null,
        warnings,
      });
    }

    if (accessRunButton) {
      accessRunButton.addEventListener('click', runAccessCheck);
    }
    """


def _acl_rows_html(
    role: str,
    rows: list[dict[str, Any]],
    alias_lookup: dict[str, list[dict[str, Any]]],
) -> str:
    rendered = []
    for index, row in enumerate(rows, start=1):
        is_other_acl = not _is_role_related_acl(role, str(row.get("acl", "")))
        row_class = "acl-rule-row other-acl-rule" if is_other_acl else "acl-rule-row"
        other_acl_attr = ' data-other-acl="true" hidden' if is_other_acl else ""
        rule_id = access_rule_id(role, index)
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
            <tr class="{row_class}"{other_acl_attr} data-rule-id="{escape(rule_id)}">
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


def _other_acl_toggle_html(panel_id: str, other_acl_count: int) -> str:
    if other_acl_count <= 0:
        return ""
    return f"""
    <div class="acl-filter-actions no-print">
      <button class="acl-filter-button toggle-other-acls" type="button"
        data-panel-id="{escape(panel_id)}" data-other-acl-count="{other_acl_count}" aria-pressed="false">
        Show other ACLs ({other_acl_count})
      </button>
    </div>
    """


def _other_acl_meta_text(other_acl_count: int) -> str:
    if other_acl_count <= 0:
        return ""
    return f" / {other_acl_count} other hidden"


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


def _zero_user_role_controls_html(
    *,
    enabled: bool,
    hidden_count: int,
    user_table_counts_reliable: bool,
    role_items: list[dict[str, Any]],
) -> str:
    if enabled and hidden_count > 0:
        return f"""
        <div class="zero-user-role-controls no-print">
          <button id="toggle-zero-user-roles" class="report-action secondary" type="button"
            data-zero-user-role-count="{hidden_count}" aria-pressed="false">
            Show zero-user roles ({hidden_count})
          </button>
        </div>
        """
    if role_items and not user_table_counts_reliable:
        return """
        <p class="zero-user-role-notice">Role user counts were not available from show user-table, so zero-user Role hiding is disabled.</p>
        """
    if role_items and all(_int_value(item.get("user_count")) == 0 for item in role_items):
        return """
        <p class="zero-user-role-notice">All Roles have 0 observed users, so zero-user Role hiding is disabled to avoid an empty report.</p>
        """
    return ""


def _zero_user_role_class(hidden: bool) -> str:
    return " zero-user-role" if hidden else ""


def _zero_user_role_attrs(hidden: bool) -> str:
    return ' data-zero-user-role="true"' if hidden else ""


def _hidden_attr(hidden: bool) -> str:
    return " hidden" if hidden else ""


def _local_role_network_html(rows: list[dict[str, Any]], enabled: bool) -> str:
    if not enabled:
        return ""

    if not rows:
        status = "Local mapping missing"
        notes = "Role was collected from WLC but was not found in the local Role network Excel."
        networks: list[str] = []
    else:
        status = str(rows[0].get("status", "") or "Local mapping loaded")
        notes = str(rows[0].get("notes", ""))
        networks = [
            str(row.get("local_role_network", "")).strip()
            for row in rows
            if str(row.get("local_role_network", "")).strip()
        ]

    network_html = "".join(
        f'<span class="local-subnet-pill"><strong>LOCAL</strong><span>{escape(network)}</span></span>'
        for network in dict.fromkeys(networks)
    )
    if not network_html:
        network_html = '<span class="notice">No local network is defined for this Role.</span>'

    return f"""
    <div class="local-network">
      <div class="local-network-title">Local Role Network</div>
      <span class="local-network-status {_local_network_status_class(status)}">{escape(status)}</span>
      {network_html}
      <div class="local-network-notes">{escape(notes)}</div>
    </div>
    """


def _local_network_status_class(status: str) -> str:
    normalized = status.casefold()
    if "mismatch" in normalized:
        return "status-mismatch"
    if "missing" in normalized:
        return "status-missing"
    if "matched" in normalized:
        return "status-matched"
    if "not collected" in normalized:
        return "status-not-collected"
    return "status-loaded"


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


def _group_local_network_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        role = str(row.get("role", "")).strip()
        if role:
            grouped.setdefault(role, []).append(row)
    return dict(sorted(grouped.items()))


def _role_observed_user_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        role = str(row.get("role", ""))
        if not role:
            continue
        counts[role] = max(counts.get(role, 0), _int_value(row.get("observed_user_count", 0)))
    return counts


def _user_table_counts_reliable(rows: list[dict[str, Any]]) -> bool:
    user_table_rows = [
        row for row in rows if str(row.get("command_id", "")).strip() == "user_table"
    ]
    return bool(user_table_rows) and all(_bool_value(row.get("success")) for row in user_table_rows)


def _bool_value(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def _other_acl_row_count(role: str, rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if not _is_role_related_acl(role, str(row.get("acl", ""))))


def _is_role_related_acl(role: str, acl_name: str) -> bool:
    role_name = role.strip().casefold()
    acl = acl_name.strip().casefold()
    if not role_name or not acl:
        return False
    return acl == role_name or acl.startswith(role_name) or role_name in acl


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_dom_id(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value).strip("-") or "item"


def _safe_file_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in value)
