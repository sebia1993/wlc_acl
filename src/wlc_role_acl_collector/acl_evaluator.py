"""Evaluate whether a source/destination pair matches a Role ACL.

The same matching rules are used by Python tests and by the generated HTML
Access Check data so the browser report follows the server-side expectations.
"""

from __future__ import annotations

import ipaddress
import shlex
from typing import Any


SPECIAL_ALLOW_ACTIONS = {"src-nat", "dst-nat", "redirect", "route", "tunnel", "forward"}
NO_MATCHING_ROLE_ACL_VERDICT = "일치하는 Role ACL 없음"
EXACT_ROLE_ACL_WARNING = (
    "Access Check는 선택한 Role 이름과 정확히 같은 ACL만 판정합니다."
)


def access_rule_id(role: str, index: int) -> str:
    safe_role = "".join(ch if ch.isalnum() else "-" for ch in role).strip("-") or "role"
    return f"access-rule-{safe_role}-{index}"


def build_access_check_data(
    role_items: list[dict[str, Any]],
    alias_rows: list[dict[str, Any]],
    local_network_rows: list[dict[str, Any]],
    *,
    include_local_networks: bool = True,
) -> dict[str, Any]:
    alias_lookup = _group_alias_rows(alias_rows)
    local_network_lookup = _group_local_network_rows(local_network_rows) if include_local_networks else {}
    services: set[str] = set()
    roles: list[dict[str, Any]] = []

    for item in role_items:
        role = _clean(item.get("role"))
        rules: list[dict[str, Any]] = []
        for index, row in enumerate(item.get("rows", []), start=1):
            # Access Check는 "선택한 Role과 같은 이름의 ACL"만 평가합니다.
            # 다른 ACL까지 섞으면 운영자가 묻는 "이 Role에서 허용되는가?"의 답이 흐려집니다.
            if not _acl_name_exactly_matches_role(role, _clean(row.get("acl"))):
                continue
            service = _clean(row.get("service"))
            if service:
                services.add(service)
            source_matchers, source_warnings = endpoint_matchers(_clean(row.get("source")), alias_lookup)
            destination_matchers, destination_warnings = endpoint_matchers(
                _clean(row.get("destination")),
                alias_lookup,
            )
            rules.append(
                {
                    "id": access_rule_id(role, index),
                    "acl": _clean(row.get("acl")),
                    "sequence": _clean(row.get("sequence")),
                    "action": _clean(row.get("action")).lower(),
                    "source": _clean(row.get("source")),
                    "destination": _clean(row.get("destination")),
                    "service": service,
                    "raw": _clean(row.get("raw_rule")),
                    "sourceMatchers": source_matchers,
                    "destinationMatchers": destination_matchers,
                    "warnings": _unique(source_warnings + destination_warnings),
                }
            )

        role_data = {
            "role": role,
            "userCount": _int_value(item.get("user_count")),
            "zeroUser": bool(item.get("zero_user_hidden")),
            "panelId": _clean(item.get("panel_id")),
            "rules": rules,
        }
        if include_local_networks:
            role_data["localNetworks"] = local_network_lookup.get(role.casefold(), [])
        roles.append(role_data)

    return {
        "roles": roles,
        "services": _sorted_services(services),
    }


def endpoint_matchers(
    value: str,
    alias_lookup: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    # ACL의 source/destination 표현을 공통 matcher로 바꿉니다.
    # 이후 evaluate_access는 matcher 타입을 몰라도 IP 숫자 범위만 비교하면 됩니다.
    alias_lookup = alias_lookup or {}
    value = value.strip()
    if not value:
        return [{"type": "unknown", "label": "", "warning": "Endpoint is empty."}], ["Endpoint is empty."]

    tokens = _split_cli(value)
    if not tokens:
        return [{"type": "unknown", "label": value, "warning": f"Endpoint is not readable: {value}"}], [
            f"Endpoint is not readable: {value}"
        ]

    keyword = tokens[0].casefold()
    if keyword == "any":
        return [{"type": "any", "label": value}], []
    if keyword == "user":
        # Aruba ACL의 user는 "현재 Role 사용자의 IP"라는 의미라 실제 대역을 코드만으로 확정할 수 없습니다.
        # 그래서 매칭 단계에서 source/destination 방향을 함께 보고 판단합니다.
        return [{"type": "user", "label": value}], []
    if keyword == "host" and len(tokens) >= 2:
        return _host_matcher(tokens[1], value)
    if keyword == "network" and len(tokens) >= 2:
        mask = tokens[2] if len(tokens) >= 3 else ""
        return _network_matcher(tokens[1], mask, value)
    if keyword == "range" and len(tokens) >= 3:
        return _range_matcher(tokens[1], tokens[2], value)
    if keyword == "alias" and len(tokens) >= 2:
        return _alias_matchers(tokens[1], alias_lookup)
    if len(tokens) == 1:
        return _host_matcher(tokens[0], value)

    warning = f"Endpoint type is not supported for IP matching: {value}"
    return [{"type": "unknown", "label": value, "warning": warning}], [warning]


def evaluate_access(
    access_data: dict[str, Any],
    *,
    role: str,
    source_ip: str,
    destination_ip: str,
    service: str = "",
) -> dict[str, Any]:
    source_number = _ip_to_int(source_ip)
    destination_number = _ip_to_int(destination_ip)
    selected_service = service.strip().casefold()
    role_data = _find_role(access_data, role)
    if role_data is None:
        return {
            "status": "error",
            "verdict": "Role을 찾을 수 없음",
            "warnings": [f"보고서 데이터에서 Role을 찾을 수 없습니다: {role}"],
        }
    if not role_data.get("rules", []):
        return {
            "status": "unknown",
            "verdict": NO_MATCHING_ROLE_ACL_VERDICT,
            "conditional": False,
            "matchedRule": None,
            "warnings": [EXACT_ROLE_ACL_WARNING],
        }

    local_warnings = _local_source_warnings(role_data, source_number, source_ip)
    uncertain_rules: list[dict[str, Any]] = []
    for rule in role_data.get("rules", []):
        # ACL은 위에서부터 처음 매칭되는 행이 결과를 결정합니다.
        # HTML Access Check도 장비 ACL을 읽는 방식과 맞추기 위해 같은 순서를 유지합니다.
        source_result = _endpoint_matches(
            source_number,
            rule.get("sourceMatchers", []),
            direction="source",
            source_number=source_number,
            destination_number=destination_number,
        )
        destination_result = _endpoint_matches(
            destination_number,
            rule.get("destinationMatchers", []),
            direction="destination",
            source_number=source_number,
            destination_number=destination_number,
        )
        if not source_result["matched"] or not destination_result["matched"]:
            if source_result["uncertain"] or destination_result["uncertain"]:
                uncertain_rules.append(rule)
            continue

        # service를 비워 두면 "서비스 조건은 자동으로 맞는 규칙을 찾는다"는 사용 흐름으로 처리합니다.
        service_result = _service_matches(_clean(rule.get("service")), selected_service)
        if not service_result["matched"]:
            continue

        verdict = _action_verdict(_clean(rule.get("action")))
        warnings = _unique(
            local_warnings
            + source_result["warnings"]
            + destination_result["warnings"]
            + service_result["warnings"]
            + list(rule.get("warnings", []))
        )
        return {
            "status": verdict["status"],
            "verdict": verdict["label"],
            "conditional": service_result["conditional"],
            "matchedRule": rule,
            "warnings": warnings,
        }

    warnings = list(local_warnings)
    if uncertain_rules:
        warnings.append(
            f"{len(uncertain_rules)}개 rule은 alias/name 데이터가 불완전해 완전 판정하지 못했습니다."
        )
    return {
        "status": "blocked",
        "verdict": "기본 차단(Implicit deny)",
        "conditional": False,
        "matchedRule": None,
        "warnings": _unique(warnings),
    }


def _alias_matchers(
    alias: str,
    alias_lookup: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = alias_lookup.get(alias.casefold(), [])
    if not rows:
        warning = f"Alias detail was not collected: {alias}"
        return [{"type": "unknown", "label": f"alias {alias}", "warning": warning}], [warning]

    matchers: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in rows:
        entry_type = _clean(row.get("entry_type")).casefold()
        value = _clean(row.get("value"))
        label = f"alias {alias}: {entry_type} {value}".strip()
        if entry_type == "host":
            entry_matchers, entry_warnings = _host_matcher(value, label)
        elif entry_type == "network":
            entry_matchers, entry_warnings = _network_from_text(value, label)
        elif entry_type == "range":
            entry_matchers, entry_warnings = _range_from_text(value, label)
        elif entry_type in {"name", "description"}:
            warning = f"Alias {alias} has {entry_type} entry that cannot be evaluated as an IP range: {value}"
            entry_matchers, entry_warnings = (
                [{"type": "unknown", "label": label, "warning": warning}],
                [warning],
            )
        else:
            warning = f"Alias {alias} has unsupported entry type for IP matching: {entry_type or 'raw'} {value}"
            entry_matchers, entry_warnings = (
                [{"type": "unknown", "label": label, "warning": warning}],
                [warning],
            )
        matchers.extend(entry_matchers)
        warnings.extend(entry_warnings)
    return matchers, _unique(warnings)


def _host_matcher(value: str, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    value = value.strip()
    if "/" in value:
        return _network_from_text(value, label)
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        warning = f"Host value is not a valid IPv4 address: {value}"
        return [{"type": "unknown", "label": label, "warning": warning}], [warning]
    if address.version != 4:
        warning = f"Only IPv4 host values are supported: {value}"
        return [{"type": "unknown", "label": label, "warning": warning}], [warning]
    number = int(address)
    return [{"type": "host", "label": label, "ip": str(address), "start": number, "end": number}], []


def _network_matcher(value: str, mask: str, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    network_text = f"{value}/{mask}" if mask else value
    return _network_from_text(network_text, label)


def _network_from_text(value: str, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    tokens = _split_cli(value)
    network_text = f"{tokens[0]}/{tokens[1]}" if len(tokens) >= 2 and "/" not in tokens[0] else value
    try:
        network = ipaddress.ip_network(network_text, strict=False)
    except ValueError:
        warning = f"Network value is not a valid IPv4 network: {value}"
        return [{"type": "unknown", "label": label, "warning": warning}], [warning]
    if network.version != 4:
        warning = f"Only IPv4 network values are supported: {value}"
        return [{"type": "unknown", "label": label, "warning": warning}], [warning]
    return [
        {
            "type": "network",
            "label": label,
            "network": f"{network.network_address}/{network.prefixlen}",
            "start": int(network.network_address),
            "end": int(network.broadcast_address),
        }
    ], []


def _range_matcher(start: str, end: str, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    try:
        start_ip = ipaddress.ip_address(start)
        end_ip = ipaddress.ip_address(end)
    except ValueError:
        warning = f"Range value is not valid IPv4: {start} - {end}"
        return [{"type": "unknown", "label": label, "warning": warning}], [warning]
    if start_ip.version != 4 or end_ip.version != 4:
        warning = f"Only IPv4 range values are supported: {start} - {end}"
        return [{"type": "unknown", "label": label, "warning": warning}], [warning]
    start_number = int(start_ip)
    end_number = int(end_ip)
    if start_number > end_number:
        start_number, end_number = end_number, start_number
        start_ip, end_ip = end_ip, start_ip
    return [
        {
            "type": "range",
            "label": label,
            "startIp": str(start_ip),
            "endIp": str(end_ip),
            "start": start_number,
            "end": end_number,
        }
    ], []


def _range_from_text(value: str, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    normalized = value.replace("-", " ")
    tokens = _split_cli(normalized)
    if len(tokens) < 2:
        warning = f"Range value is not readable: {value}"
        return [{"type": "unknown", "label": label, "warning": warning}], [warning]
    return _range_matcher(tokens[0], tokens[1], label)


def _endpoint_matches(
    ip_number: int,
    matchers: list[dict[str, Any]],
    *,
    direction: str,
    source_number: int,
    destination_number: int,
) -> dict[str, Any]:
    matched = False
    uncertain = False
    warnings: list[str] = []
    for matcher in matchers:
        matcher_type = _clean(matcher.get("type")).casefold()
        if matcher_type == "any":
            matched = True
        elif matcher_type == "user":
            matched = matched or (direction == "source" or destination_number == source_number)
        elif matcher_type in {"host", "network", "range"}:
            matched = matched or _int_value(matcher.get("start")) <= ip_number <= _int_value(matcher.get("end"))
        else:
            uncertain = True
            warning = _clean(matcher.get("warning"))
            if warning:
                warnings.append(warning)
    return {"matched": matched, "uncertain": uncertain, "warnings": _unique(warnings)}


def _service_matches(rule_service: str, selected_service: str) -> dict[str, Any]:
    normalized_rule_service = rule_service.strip().casefold() or "any"
    if not selected_service:
        if normalized_rule_service == "any":
            return {"matched": True, "conditional": False, "warnings": []}
        return {
            "matched": True,
            "conditional": True,
            "warnings": [
                f"Service 자동 모드가 {rule_service} 전용 rule에 매칭되었습니다. 정확한 Service를 선택해 재확인하세요."
            ],
        }
    return {
        "matched": normalized_rule_service == "any" or normalized_rule_service == selected_service,
        "conditional": False,
        "warnings": [],
    }


def _action_verdict(action: str) -> dict[str, str]:
    normalized = action.strip().casefold()
    if normalized == "deny":
        return {"status": "blocked", "label": "차단(Blocked)"}
    if normalized == "permit":
        return {"status": "allowed", "label": "허용(Allowed)"}
    if normalized in SPECIAL_ALLOW_ACTIONS:
        return {"status": "special", "label": "NAT/특수 Action 허용"}
    return {"status": "unknown", "label": f"알 수 없는 action: {action or 'not parsed'}"}


def _local_source_warnings(role_data: dict[str, Any], source_number: int, source_ip: str) -> list[str]:
    networks = role_data.get("localNetworks", [])
    if not networks:
        return []
    if any(_int_value(network.get("start")) <= source_number <= _int_value(network.get("end")) for network in networks):
        return []
    labels = ", ".join(_clean(network.get("network") or network.get("label")) for network in networks)
    return [f"Source IP {source_ip}가 사내 Role 대역표 범위 밖입니다: {labels}"]


def _group_alias_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        alias = _clean(row.get("alias"))
        if alias:
            grouped.setdefault(alias.casefold(), []).append(row)
    return grouped


def _acl_name_exactly_matches_role(role: str, acl_name: str) -> bool:
    return bool(role.strip()) and role.strip().casefold() == acl_name.strip().casefold()


def _group_local_network_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        role = _clean(row.get("role"))
        network = _clean(row.get("local_role_network"))
        if not role or not network:
            continue
        matchers, _warnings = _network_from_text(network, network)
        for matcher in matchers:
            if matcher.get("type") == "network":
                grouped.setdefault(role.casefold(), []).append(matcher)
    return grouped


def _find_role(access_data: dict[str, Any], role: str) -> dict[str, Any] | None:
    role_key = role.casefold()
    for item in access_data.get("roles", []):
        if _clean(item.get("role")).casefold() == role_key:
            return item
    return None


def _ip_to_int(value: str) -> int:
    address = ipaddress.ip_address(value.strip())
    if address.version != 4:
        raise ValueError(f"Only IPv4 addresses are supported: {value}")
    return int(address)


def _split_cli(value: str) -> list[str]:
    try:
        return shlex.split(value)
    except ValueError:
        return value.split()


def _sorted_services(services: set[str]) -> list[str]:
    return sorted((service for service in services if service), key=_service_sort_key)


def _service_sort_key(service: str) -> tuple[int, str]:
    normalized = service.casefold()
    if normalized == "any":
        return (0, normalized)
    if normalized.startswith("svc-"):
        return (1, normalized)
    return (2, normalized)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() == "nan" else text
