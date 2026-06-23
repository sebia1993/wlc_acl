"""Parse Aruba AOS8 command output into structured report data.

The parser translates raw WLC text into dataclasses such as RolePolicy,
SsidRoleMapping, VLAN context, and netdestination alias entries.
"""

from __future__ import annotations

import ipaddress
import re
import shlex
from collections import defaultdict
from dataclasses import dataclass, field

from .access_summary import classify_access
from .models import (
    AclRule,
    Controller,
    NetDestinationEntry,
    ParsedController,
    RoleNetworkContext,
    RolePolicy,
    SsidRoleMapping,
    UserRoleObservation,
    VlanNetwork,
)


ROLE_FIELDS = (
    ("initial", "initial_role"),
    ("mac-default", "mac_default_role"),
    ("dot1x-default", "dot1x_default_role"),
)

KNOWN_SERVICES = {
    "any",
    "svc-dhcp",
    "svc-dns",
    "svc-http",
    "svc-https",
    "svc-http-proxy",
    "svc-http-proxy1",
    "svc-http-proxy2",
    "svc-http-proxy3",
    "svc-icmp",
    "svc-natt",
    "svc-kerberos",
    "svc-ldap",
    "svc-ldaps",
    "svc-smb",
    "svc-smtp",
    "svc-ssh",
    "svc-telnet",
    "svc-snmp",
    "svc-syslog",
    "tcp",
    "udp",
    "icmp",
}


@dataclass
class AaaProfile:
    name: str
    initial_role: str = ""
    mac_default_role: str = ""
    dot1x_default_role: str = ""
    radius_server_group: str = ""
    mac_server_group: str = ""
    dot1x_server_group: str = ""
    user_derivation_rules: str = ""
    download_role_from_cppm: bool = False
    raw_lines: list[str] = field(default_factory=list)

    @property
    def dynamic_role_possible(self) -> bool:
        return bool(
            self.radius_server_group
            or self.mac_server_group
            or self.dot1x_server_group
            or self.user_derivation_rules
            or self.download_role_from_cppm
        )

    @property
    def dynamic_role_reason(self) -> str:
        reasons = []
        if self.dot1x_server_group:
            reasons.append(f"dot1x-server-group={self.dot1x_server_group}")
        if self.mac_server_group:
            reasons.append(f"mac-server-group={self.mac_server_group}")
        if self.radius_server_group:
            reasons.append(f"radius-accounting/server-group={self.radius_server_group}")
        if self.user_derivation_rules:
            reasons.append(f"user-derivation-rules={self.user_derivation_rules}")
        if self.download_role_from_cppm:
            reasons.append("download-role-from-cppm")
        return "; ".join(reasons)


def parse_controller_config(
    *,
    controller: Controller,
    config_text: str,
    rights_outputs: dict[str, str] | None = None,
    netdestination_outputs: dict[str, str] | None = None,
    ip_interface_brief_output: str = "",
    user_table_output: str = "",
) -> ParsedController:
    rights_outputs = rights_outputs or {}
    netdestination_outputs = netdestination_outputs or {}

    # AOS8 설정은 "wlan ...", "user-role ..." 같은 블록 단위로 의미가 나뉩니다.
    # 먼저 블록을 전부 분리한 뒤, 필요한 관계를 뒤에서 다시 연결합니다.
    blocks = list(_iter_blocks(config_text))

    ap_groups: dict[str, list[str]] = defaultdict(list)
    virtual_aps: dict[str, dict[str, str]] = {}
    ssid_profiles: dict[str, dict[str, str]] = {}
    aaa_profiles: dict[str, AaaProfile] = {}
    role_defs: dict[str, dict[str, object]] = {}
    acl_rules: dict[str, list[AclRule]] = {}
    netdestination_aliases: dict[str, list[NetDestinationEntry]] = {}
    config_vlan_networks: dict[str, VlanNetwork] = {}

    for block_type, name, lines in blocks:
        if block_type == "ap_group":
            ap_groups[name].extend(_parse_ap_group(lines))
        elif block_type == "virtual_ap":
            virtual_aps[name] = _parse_virtual_ap(lines)
        elif block_type == "ssid_profile":
            ssid_profiles[name] = _parse_ssid_profile(lines)
        elif block_type == "aaa_profile":
            aaa_profiles[name] = _parse_aaa_profile(name, lines)
        elif block_type == "user_role":
            role_defs[name] = _parse_user_role(lines)
        elif block_type == "acl":
            acl_rules[name] = _parse_acl_rules(controller.name, name, lines)
        elif block_type == "netdestination":
            netdestination_aliases[name] = _parse_netdestination_config(controller.name, name, lines)
        elif block_type == "interface_vlan":
            network = _parse_interface_vlan_config(controller.name, name, lines)
            if network is not None:
                config_vlan_networks[network.vlan] = network

    parsed = ParsedController(controller=controller)

    # show netdestination 결과가 있으면 설정 파일의 alias 정의보다 우선 사용합니다.
    # 운영 장비에서는 show 명령 결과가 host/network/range를 더 명확히 보여주는 경우가 많습니다.
    for alias, output in netdestination_outputs.items():
        entries = _parse_show_netdestination(controller.name, alias, output)
        if entries:
            netdestination_aliases[alias] = entries
    parsed.netdestination_aliases = netdestination_aliases
    _expand_acl_alias_references(acl_rules, netdestination_aliases)
    # Role은 user-role 블록에 직접 정의될 수도 있고 AAA Profile의 기본 Role로만 등장할 수도 있습니다.
    role_names = set(role_defs)
    for aaa_profile in aaa_profiles.values():
        for _, field_name in ROLE_FIELDS:
            role = getattr(aaa_profile, field_name)
            if role:
                role_names.add(role)

    for role_name in sorted(role_names):
        role_def = role_defs.get(role_name, {})
        acl_names = list(dict.fromkeys(role_def.get("acl_names", [])))
        rules: list[AclRule] = []
        for acl_name in acl_names:
            if acl_name in acl_rules:
                rules.extend(acl_rules[acl_name])
            else:
                parsed.unresolved.append(
                    {
                        "controller": controller.name,
                        "type": "missing_acl",
                        "name": acl_name,
                        "context": f"role={role_name}",
                    }
                )
        summary, flags = classify_access(rules)
        parsed.role_policies[role_name] = RolePolicy(
            controller=controller.name,
            role=role_name,
            acl_names=acl_names,
            rules=rules,
            vlan=str(role_def.get("vlan", "")),
            access_summary=summary,
            access_flags=flags,
            rights_output=rights_outputs.get(role_name, ""),
            raw_lines=list(role_def.get("raw_lines", [])),
        )

    _record_acl_unknowns(parsed, acl_rules, netdestination_aliases)

    # SSID -> Virtual AP -> AAA Profile -> Role 순서로 따라가야 사용자가 어떤 Role을 받는지 알 수 있습니다.
    _build_ssid_role_mappings(
        parsed=parsed,
        ap_groups=ap_groups,
        virtual_aps=virtual_aps,
        ssid_profiles=ssid_profiles,
        aaa_profiles=aaa_profiles,
    )
    parsed.vlan_networks = _merge_vlan_networks(
        config_vlan_networks,
        _parse_show_ip_interface_brief(controller.name, ip_interface_brief_output),
    )
    parsed.user_role_observations = _parse_user_table_summary(
        controller.name,
        user_table_output,
        role_names=set(parsed.role_policies),
    )
    # VLAN/user-table 기반 네트워크 추정은 참고 정보입니다.
    # 정확한 Role 대역은 별도 Role network Excel 기능으로 보강하도록 분리되어 있습니다.
    _apply_role_network_context(parsed)
    return parsed


def discover_roles_from_config(config_text: str) -> list[str]:
    # collector.py에서 show rights 대상 Role을 정하기 위한 가벼운 탐색 함수입니다.
    # 전체 파싱보다 빠르게 Role 이름만 뽑습니다.
    roles: set[str] = set()
    for block_type, name, lines in _iter_blocks(config_text):
        if block_type == "user_role":
            roles.add(name)
        elif block_type == "aaa_profile":
            aaa = _parse_aaa_profile(name, lines)
            for _, field_name in ROLE_FIELDS:
                role = getattr(aaa, field_name)
                if role:
                    roles.add(role)
    return sorted(roles)


def discover_aliases_from_config(config_text: str) -> list[str]:
    # ACL 안의 alias 참조만 먼저 찾아야 collector.py가 show netdestination을 추가 실행할 수 있습니다.
    aliases: set[str] = set()
    for block_type, _name, lines in _iter_blocks(config_text):
        if block_type != "acl":
            continue
        for line in lines:
            aliases.update(_alias_names_from_acl_line(line))
    return sorted(aliases)


def _build_ssid_role_mappings(
    *,
    parsed: ParsedController,
    ap_groups: dict[str, list[str]],
    virtual_aps: dict[str, dict[str, str]],
    ssid_profiles: dict[str, dict[str, str]],
    aaa_profiles: dict[str, AaaProfile],
) -> None:
    controller = parsed.controller
    linked_vaps = set()

    for ap_group, vap_names in sorted(ap_groups.items()):
        for vap_name in vap_names:
            linked_vaps.add(vap_name)
            _append_vap_mappings(
                parsed=parsed,
                controller=controller,
                ap_group=ap_group,
                vap_name=vap_name,
                virtual_aps=virtual_aps,
                ssid_profiles=ssid_profiles,
                aaa_profiles=aaa_profiles,
            )

    for vap_name in sorted(set(virtual_aps) - linked_vaps):
        _append_vap_mappings(
            parsed=parsed,
            controller=controller,
            ap_group="",
            vap_name=vap_name,
            virtual_aps=virtual_aps,
            ssid_profiles=ssid_profiles,
            aaa_profiles=aaa_profiles,
        )


def _append_vap_mappings(
    *,
    parsed: ParsedController,
    controller: Controller,
    ap_group: str,
    vap_name: str,
    virtual_aps: dict[str, dict[str, str]],
    ssid_profiles: dict[str, dict[str, str]],
    aaa_profiles: dict[str, AaaProfile],
) -> None:
    vap = virtual_aps.get(vap_name)
    if vap is None:
        parsed.unresolved.append(
            {
                "controller": controller.name,
                "type": "missing_virtual_ap",
                "name": vap_name,
                "context": f"ap_group={ap_group}",
            }
        )
        return

    ssid_profile_name = vap.get("ssid_profile", "")
    aaa_profile_name = vap.get("aaa_profile", "")
    ssid = ssid_profiles.get(ssid_profile_name, {}).get("essid", ssid_profile_name)
    aaa_profile = aaa_profiles.get(aaa_profile_name)
    if ssid_profile_name and ssid_profile_name not in ssid_profiles:
        parsed.unresolved.append(
            {
                "controller": controller.name,
                "type": "missing_ssid_profile",
                "name": ssid_profile_name,
                "context": f"vap={vap_name}",
            }
        )
    if aaa_profile_name and aaa_profile is None:
        parsed.unresolved.append(
            {
                "controller": controller.name,
                "type": "missing_aaa_profile",
                "name": aaa_profile_name,
                "context": f"vap={vap_name}",
            }
        )
        return
    if aaa_profile is None:
        return

    for role_type, field_name in ROLE_FIELDS:
        role = getattr(aaa_profile, field_name)
        if not role:
            continue
        policy = parsed.role_policies.get(role)
        parsed.ssid_role_mappings.append(
            SsidRoleMapping(
                controller=controller.name,
                ap_group=ap_group,
                virtual_ap=vap_name,
                ssid_profile=ssid_profile_name,
                ssid=ssid,
                aaa_profile=aaa_profile_name,
                role_type=role_type,
                role=role,
                vlan=vap.get("vlan", ""),
                forward_mode=vap.get("forward_mode", ""),
                access_summary=policy.access_summary if policy else "명확하지 않음",
                dynamic_role_possible=aaa_profile.dynamic_role_possible,
                dynamic_role_reason=aaa_profile.dynamic_role_reason,
            )
        )
        if policy is None:
            parsed.unresolved.append(
                {
                    "controller": controller.name,
                    "type": "missing_role",
                    "name": role,
                    "context": f"aaa_profile={aaa_profile_name}; vap={vap_name}",
                }
            )


def _iter_blocks(text: str):
    current_type = ""
    current_name = ""
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = _strip_prompt(line).strip()
        if not stripped:
            continue

        header = _match_header(stripped)
        if header:
            if current_type:
                yield current_type, current_name, current_lines
            current_type, current_name = header
            current_lines = []
            continue

        if stripped == "!":
            if current_type:
                yield current_type, current_name, current_lines
                current_type = ""
                current_name = ""
                current_lines = []
            continue

        if current_type:
            current_lines.append(stripped)

    if current_type:
        yield current_type, current_name, current_lines


def _match_header(line: str) -> tuple[str, str] | None:
    patterns = (
        ("ap_group", r"^ap-group\s+(.+)$"),
        ("virtual_ap", r"^wlan\s+virtual-ap\s+(.+)$"),
        ("ssid_profile", r"^wlan\s+ssid-profile\s+(.+)$"),
        ("aaa_profile", r"^aaa\s+profile\s+(.+)$"),
        ("user_role", r"^user-role\s+(.+)$"),
        ("acl", r"^ip\s+access-list\s+session\s+(.+)$"),
        ("netdestination", r"^netdestination\s+(.+)$"),
        ("interface_vlan", r"^interface\s+vlan\s+(.+)$"),
    )
    for block_type, pattern in patterns:
        match = re.match(pattern, line, flags=re.IGNORECASE)
        if match:
            return block_type, _clean_value(match.group(1))
    return None


def _strip_prompt(line: str) -> str:
    return re.sub(r"^\([^)]*\)\s+(?:\[[^]]+\]\s+)?(?:\(config[^)]*\)\s*#|#)\s*", "", line)


def _parse_ap_group(lines: list[str]) -> list[str]:
    values = []
    for line in lines:
        match = re.match(r"virtual-ap\s+(.+)$", line, flags=re.IGNORECASE)
        if match:
            values.append(_clean_value(match.group(1)))
    return values


def _parse_virtual_ap(lines: list[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in lines:
        for key, pattern in (
            ("aaa_profile", r"^aaa-profile\s+(.+)$"),
            ("ssid_profile", r"^ssid-profile\s+(.+)$"),
            ("vlan", r"^vlan\s+(.+)$"),
            ("forward_mode", r"^forward-mode\s+(.+)$"),
        ):
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                data[key] = _clean_value(match.group(1))
    return data


def _parse_ssid_profile(lines: list[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^essid\s+(.+)$", line, flags=re.IGNORECASE)
        if match:
            data["essid"] = _clean_value(match.group(1))
    return data


def _parse_aaa_profile(name: str, lines: list[str]) -> AaaProfile:
    profile = AaaProfile(name=name, raw_lines=lines)
    field_patterns = (
        ("initial_role", r"^initial-role\s+(.+)$"),
        ("mac_default_role", r"^mac-default-role\s+(.+)$"),
        ("dot1x_default_role", r"^dot1x-default-role\s+(.+)$"),
        ("radius_server_group", r"^radius-accounting-server-group\s+(.+)$"),
        ("mac_server_group", r"^mac-server-group\s+(.+)$"),
        ("dot1x_server_group", r"^dot1x-server-group\s+(.+)$"),
        ("user_derivation_rules", r"^user-derivation-rules\s+(.+)$"),
    )
    for line in lines:
        if re.search(r"download-role-from-cppm", line, flags=re.IGNORECASE):
            profile.download_role_from_cppm = True
        for field_name, pattern in field_patterns:
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                setattr(profile, field_name, _clean_value(match.group(1)))
    return profile


def _parse_user_role(lines: list[str]) -> dict[str, object]:
    acl_names: list[str] = []
    vlan = ""
    for line in lines:
        acl_match = re.match(
            r"^(?:session-acl|access-list\s+session)\s+(.+)$",
            line,
            flags=re.IGNORECASE,
        )
        if acl_match:
            acl_names.append(_clean_value(acl_match.group(1)))
            continue
        vlan_match = re.match(r"^vlan\s+(.+)$", line, flags=re.IGNORECASE)
        if vlan_match:
            vlan = _clean_value(vlan_match.group(1))
    return {"acl_names": acl_names, "vlan": vlan, "raw_lines": lines}


def _parse_interface_vlan_config(
    controller_name: str,
    vlan: str,
    lines: list[str],
) -> VlanNetwork | None:
    vlan_id = _normalize_vlan(vlan)
    if not vlan_id:
        return None
    for line in lines:
        match = re.match(r"^ip\s+address\s+(\S+)(?:\s+(\S+))?", line, flags=re.IGNORECASE)
        if not match:
            continue
        ip_value = match.group(1)
        mask_value = match.group(2) or ""
        return _build_vlan_network(
            controller_name=controller_name,
            vlan=vlan_id,
            ip_value=ip_value,
            mask_value=mask_value,
            evidence="interface vlan configuration",
        )
    return None


def _parse_show_ip_interface_brief(controller_name: str, output: str) -> dict[str, VlanNetwork]:
    networks: dict[str, VlanNetwork] = {}
    for raw_line in output.splitlines():
        line = _strip_prompt(raw_line).strip()
        if not line or re.match(r"^(Interface\b|-+)", line, flags=re.IGNORECASE):
            continue
        tokens = _split_cli(line)
        if len(tokens) < 3:
            continue
        vlan = _vlan_from_interface_name(tokens[0:2])
        if not vlan:
            continue
        ip_value = _first_ipv4_token(tokens)
        if not ip_value or ip_value.lower() == "unassigned":
            continue
        mask_value = _netmask_after_ip(tokens, ip_value)
        network = _build_vlan_network(
            controller_name=controller_name,
            vlan=vlan,
            ip_value=ip_value,
            mask_value=mask_value,
            evidence="show ip interface brief",
        )
        if network is not None:
            networks[vlan] = network
    return networks


def _merge_vlan_networks(
    config_networks: dict[str, VlanNetwork],
    brief_networks: dict[str, VlanNetwork],
) -> dict[str, VlanNetwork]:
    merged = dict(config_networks)
    merged.update(brief_networks)
    return dict(sorted(merged.items(), key=lambda item: int(item[0]) if item[0].isdigit() else item[0]))


def _parse_user_table_summary(
    controller_name: str,
    output: str,
    *,
    role_names: set[str],
) -> dict[str, UserRoleObservation]:
    observations: dict[str, UserRoleObservation] = {
        role: UserRoleObservation(controller=controller_name, role=role) for role in role_names
    }
    if not output.strip() or not role_names:
        return observations

    sorted_roles = sorted(role_names, key=len, reverse=True)
    observed_ips: dict[str, list[str]] = defaultdict(list)
    observed_vlans: dict[str, set[str]] = defaultdict(set)

    for raw_line in output.splitlines():
        line = _strip_prompt(raw_line).strip()
        if not line:
            continue
        ip_value = _first_ipv4_token(_split_cli(line))
        if not ip_value:
            continue
        role = _role_from_user_table_line(line, sorted_roles)
        if not role:
            continue
        observed_ips[role].append(ip_value)
        vlan = _vlan_from_user_table_line(line)
        if vlan:
            observed_vlans[role].add(vlan)

    for role in role_names:
        ips = observed_ips.get(role, [])
        observations[role] = UserRoleObservation(
            controller=controller_name,
            role=role,
            observed_user_count=len(ips),
            observed_vlans=sorted(observed_vlans.get(role, set()), key=lambda value: int(value) if value.isdigit() else value),
            observed_networks=_summarize_observed_networks(ips),
        )
    return observations


def _apply_role_network_context(parsed: ParsedController) -> None:
    contexts: dict[tuple[str, str, str, str], RoleNetworkContext] = {}

    for mapping in parsed.ssid_role_mappings:
        policy = parsed.role_policies.get(mapping.role)
        role_vlan = _normalize_vlan(policy.vlan if policy and policy.vlan else "")
        vap_vlan = _normalize_vlan(mapping.vlan)
        effective_vlan, confidence, assignment_source = _network_assignment_for_mapping(
            role_vlan=role_vlan,
            vap_vlan=vap_vlan,
            mapping=mapping,
        )
        mapping.effective_vlan = effective_vlan
        mapping.network_confidence = confidence
        mapping.assignment_source = assignment_source
        mapping.configured_vlan = effective_vlan

        vlan_network = parsed.vlan_networks.get(effective_vlan)
        if vlan_network is None:
            mapping.role_user_network = "Unknown"
            mapping.configured_subnet = "Unknown"
            mapping.network_evidence = "VLAN subnet not found" if effective_vlan else "No VLAN mapping found"
        else:
            mapping.role_user_network = vlan_network.network
            mapping.configured_subnet = vlan_network.network
            mapping.network_evidence = vlan_network.evidence

        observation = parsed.user_role_observations.get(mapping.role)
        if observation is not None:
            mapping.observed_user_count = observation.observed_user_count

        key = (mapping.role, effective_vlan, confidence, assignment_source)
        context = contexts.get(key)
        if context is None:
            notes = _role_network_notes(
                effective_vlan=effective_vlan,
                vlan_network_found=vlan_network is not None,
                mapping=mapping,
            )
            context = RoleNetworkContext(
                controller=parsed.controller.name,
                role=mapping.role,
                effective_vlan=effective_vlan,
                role_user_network=mapping.role_user_network,
                network_evidence=mapping.network_evidence,
                network_confidence=confidence,
                assignment_source=assignment_source,
                configured_vlan=mapping.configured_vlan,
                configured_subnet=mapping.configured_subnet,
                observed_user_count=observation.observed_user_count if observation else 0,
                observed_vlans=observation.observed_vlans if observation else [],
                observed_networks=observation.observed_networks if observation else [],
                notes=notes,
            )
            contexts[key] = context

        if mapping.ssid and mapping.ssid not in context.ssids:
            context.ssids.append(mapping.ssid)
        if mapping.ap_group and mapping.ap_group not in context.ap_groups:
            context.ap_groups.append(mapping.ap_group)

    all_roles = set(parsed.role_policies) | set(parsed.user_role_observations)
    for role in all_roles:
        if any(context.role == role for context in contexts.values()):
            continue
        observation = parsed.user_role_observations.get(role)
        key = (role, "", "Unknown", "No SSID/VLAN mapping found")
        contexts[key] = RoleNetworkContext(
            controller=parsed.controller.name,
            role=role,
            effective_vlan="",
            role_user_network="Unknown",
            network_evidence="No SSID/VLAN mapping found",
            network_confidence="Unknown",
            assignment_source="No SSID/VLAN mapping found",
            configured_vlan="",
            configured_subnet="Unknown",
            observed_user_count=observation.observed_user_count if observation else 0,
            observed_vlans=observation.observed_vlans if observation else [],
            observed_networks=observation.observed_networks if observation else [],
            notes="Role was observed or defined, but no SSID/VLAN mapping was found.",
        )

    parsed.role_network_contexts = sorted(
        contexts.values(),
        key=lambda item: (
            item.role,
            int(item.effective_vlan) if item.effective_vlan.isdigit() else 0,
            item.effective_vlan,
            item.network_confidence,
            item.assignment_source,
        ),
    )


def _network_assignment_for_mapping(
    *,
    role_vlan: str,
    vap_vlan: str,
    mapping: SsidRoleMapping,
) -> tuple[str, str, str]:
    if role_vlan:
        return role_vlan, "Exact", "user-role vlan"
    if vap_vlan and mapping.dynamic_role_possible:
        reason = mapping.dynamic_role_reason or "AAA profile can assign roles dynamically"
        return vap_vlan, "Dynamic Possible", f"virtual-ap vlan; dynamic role possible ({reason})"
    if vap_vlan:
        return vap_vlan, "Inherited", "virtual-ap vlan"
    if mapping.dynamic_role_possible:
        reason = mapping.dynamic_role_reason or "AAA profile can assign roles dynamically"
        return "", "Dynamic Possible", f"no configured VLAN; dynamic role possible ({reason})"
    return "", "Unknown", "No VLAN mapping found"


def _role_network_notes(
    *,
    effective_vlan: str,
    vlan_network_found: bool,
    mapping: SsidRoleMapping,
) -> str:
    notes = []
    if not effective_vlan:
        notes.append("No VLAN was found for this Role mapping.")
    elif not vlan_network_found:
        notes.append("VLAN was found, but no subnet evidence was collected.")
    if mapping.dynamic_role_possible:
        reason = mapping.dynamic_role_reason or "AAA profile can assign roles dynamically"
        notes.append(f"Dynamic role assignment possible: {reason}.")
    return " ".join(notes)


def _parse_acl_rules(controller_name: str, acl_name: str, lines: list[str]) -> list[AclRule]:
    rules: list[AclRule] = []
    for sequence, line in enumerate(lines, start=1):
        if not line or line.startswith("!"):
            continue
        rules.append(_parse_acl_rule(controller_name, acl_name, sequence, line))
    return rules


def _parse_netdestination_config(
    controller_name: str,
    alias: str,
    lines: list[str],
) -> list[NetDestinationEntry]:
    entries: list[NetDestinationEntry] = []
    for sequence, line in enumerate(lines, start=1):
        tokens = _split_cli(line)
        if not tokens:
            continue
        entry_type = tokens[0].lower()
        value = " ".join(tokens[1:]).strip() if len(tokens) > 1 else "true"
        entries.append(
            NetDestinationEntry(
                controller=controller_name,
                alias=alias,
                sequence=sequence,
                entry_type=entry_type,
                value=value,
                raw=line,
            )
        )
    return entries


def _parse_show_netdestination(
    controller_name: str,
    default_alias: str,
    output: str,
) -> list[NetDestinationEntry]:
    entries: list[NetDestinationEntry] = []
    current_alias = default_alias
    for raw_line in output.splitlines():
        line = _strip_prompt(raw_line).strip()
        if not line:
            continue
        name_match = re.match(r"^Name\s*:?\s*(.+)$", line, flags=re.IGNORECASE)
        if name_match:
            current_alias = _clean_value(name_match.group(1).lstrip(":").strip())
            continue
        description_match = re.match(r"^Description\s*:?\s*(.+)$", line, flags=re.IGNORECASE)
        if description_match:
            entries.append(
                NetDestinationEntry(
                    controller=controller_name,
                    alias=current_alias,
                    sequence=len(entries) + 1,
                    entry_type="description",
                    value=description_match.group(1).lstrip(":").strip(),
                    raw=line,
                )
            )
            continue
        if re.match(r"^(Destination ID|Position\b|-+)", line, flags=re.IGNORECASE):
            continue

        tokens = _split_cli(line)
        if len(tokens) < 3 or not tokens[0].isdigit():
            continue
        entry_type = tokens[1].lower()
        value = _format_show_netdestination_value(entry_type, tokens[2:])
        entries.append(
            NetDestinationEntry(
                controller=controller_name,
                alias=current_alias,
                sequence=int(tokens[0]),
                entry_type=entry_type,
                value=value,
                raw=line,
            )
        )
    return entries


def _format_show_netdestination_value(entry_type: str, values: list[str]) -> str:
    if not values:
        return ""
    if entry_type == "host" and len(values) >= 2:
        return f"{values[0]}/{values[1]}"
    if entry_type == "name" and len(values) >= 2:
        return values[-1]
    if entry_type == "range" and len(values) >= 2:
        return f"{values[0]} - {values[1]}"
    return " ".join(values)


def _parse_acl_rule(controller_name: str, acl_name: str, sequence: int, line: str) -> AclRule:
    tokens = _split_cli(line)
    action_words = {"permit", "deny", "src-nat", "dst-nat", "redirect", "route", "tunnel", "forward"}
    action = ""
    action_index = -1
    for index, token in enumerate(tokens):
        if token.lower() in action_words:
            action = token.lower()
            action_index = index
            break

    pre_action = tokens[:action_index] if action_index >= 0 else tokens
    source, destination, service = _best_effort_acl_fields(pre_action)
    return AclRule(
        controller=controller_name,
        acl=acl_name,
        sequence=sequence,
        raw=line,
        action=action,
        source=source,
        destination=destination,
        service=service,
    )


def _best_effort_acl_fields(tokens: list[str]) -> tuple[str, str, str]:
    if not tokens:
        return "", "", ""

    fields: list[str] = []
    index = 0
    while index < len(tokens) and len(fields) < 3:
        token = tokens[index]
        normalized = token.lower()
        if normalized in {"host", "alias"} and index + 1 < len(tokens):
            fields.append(f"{token} {tokens[index + 1]}")
            index += 2
        elif normalized == "network" and index + 2 < len(tokens) and _looks_like_network_mask(tokens[index + 2]):
            fields.append(f"{token} {tokens[index + 1]} {tokens[index + 2]}")
            index += 3
        elif normalized == "network" and index + 1 < len(tokens):
            fields.append(f"{token} {tokens[index + 1]}")
            index += 2
        elif normalized == "range" and index + 2 < len(tokens):
            fields.append(f"range {tokens[index + 1]} {tokens[index + 2]}")
            index += 3
        else:
            fields.append(token)
            index += 1
    while len(fields) < 3:
        fields.append("")
    return fields[0], fields[1], " ".join([fields[2], *tokens[index:]]).strip()


def _looks_like_network_mask(value: str) -> bool:
    if value.isdigit():
        return 0 <= int(value) <= 32
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        return False
    return True


def _expand_acl_alias_references(
    acl_rules: dict[str, list[AclRule]],
    netdestination_aliases: dict[str, list[NetDestinationEntry]],
) -> None:
    for rules in acl_rules.values():
        for rule in rules:
            rule.source_detail = _alias_detail_text(rule.source, netdestination_aliases)
            rule.destination_detail = _alias_detail_text(rule.destination, netdestination_aliases)


def _alias_detail_text(
    value: str,
    netdestination_aliases: dict[str, list[NetDestinationEntry]],
) -> str:
    alias = _alias_name_from_field(value)
    if not alias:
        return ""
    entries = netdestination_aliases.get(alias, [])
    if not entries:
        return ""
    return "; ".join(f"{entry.entry_type} {entry.value}".strip() for entry in entries)


def _alias_name_from_field(value: str) -> str:
    tokens = _split_cli(value)
    if len(tokens) >= 2 and tokens[0].lower() == "alias":
        return tokens[1]
    return ""


def _record_acl_unknowns(
    parsed: ParsedController,
    acl_rules: dict[str, list[AclRule]],
    netdestination_aliases: dict[str, list[NetDestinationEntry]],
) -> None:
    for acl_name, rules in acl_rules.items():
        for rule in rules:
            tokens = _split_cli(rule.raw)
            for alias_name in _alias_names_from_acl_line(rule.raw):
                if alias_name not in netdestination_aliases:
                    parsed.unresolved.append(
                        {
                            "controller": parsed.controller.name,
                            "type": "alias_not_defined",
                            "name": alias_name,
                            "context": f"acl={acl_name}; rule={rule.sequence}",
                        }
                    )
            for token in tokens:
                if token.startswith("svc-") and token not in KNOWN_SERVICES:
                    parsed.unresolved.append(
                        {
                            "controller": parsed.controller.name,
                            "type": "service_not_classified",
                            "name": token,
                            "context": f"acl={acl_name}; rule={rule.sequence}",
                        }
                    )


def _alias_names_from_acl_line(line: str) -> set[str]:
    tokens = _split_cli(line)
    aliases: set[str] = set()
    for index, token in enumerate(tokens):
        if token.lower() == "alias" and index + 1 < len(tokens):
            aliases.add(tokens[index + 1])
    return aliases


def _build_vlan_network(
    *,
    controller_name: str,
    vlan: str,
    ip_value: str,
    mask_value: str,
    evidence: str,
) -> VlanNetwork | None:
    try:
        if "/" in ip_value:
            interface = ipaddress.ip_interface(ip_value)
        elif mask_value:
            interface = ipaddress.ip_interface(f"{ip_value}/{mask_value}")
        else:
            return None
    except ValueError:
        return None
    return VlanNetwork(
        controller=controller_name,
        vlan=vlan,
        ip_address=str(interface.ip),
        netmask=str(interface.network.netmask),
        network=str(interface.network),
        evidence=evidence,
    )


def _normalize_vlan(value: str) -> str:
    match = re.search(r"\b(\d{1,4})\b", str(value or ""))
    if not match:
        return ""
    vlan = int(match.group(1))
    if 1 <= vlan <= 4094:
        return str(vlan)
    return ""


def _vlan_from_interface_name(tokens: list[str]) -> str:
    if not tokens:
        return ""
    first = tokens[0].lower()
    if first in {"vlan", "vlan-interface", "vlanif"} and len(tokens) > 1:
        return _normalize_vlan(tokens[1])
    match = re.match(r"^(?:vlan|vlan-interface|vlanif)(\d+)$", first)
    if match:
        return _normalize_vlan(match.group(1))
    return ""


def _first_ipv4_token(tokens: list[str]) -> str:
    for token in tokens:
        candidate = token.strip(",;()")
        if "/" in candidate:
            try:
                interface = ipaddress.ip_interface(candidate)
            except ValueError:
                continue
            if interface.version == 4:
                return candidate
            continue
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if "." in candidate:
            return candidate
    return ""


def _netmask_after_ip(tokens: list[str], ip_value: str) -> str:
    for index, token in enumerate(tokens):
        if token.strip(",;()").split("/", 1)[0] != ip_value:
            continue
        for candidate in tokens[index + 1 : index + 4]:
            value = candidate.strip(",;()")
            if value == "/":
                continue
            try:
                ipaddress.ip_address(value)
            except ValueError:
                continue
            if "." in value:
                return value
    return ""


def _role_from_user_table_line(line: str, roles: list[str]) -> str:
    padded = f" {line} "
    for role in roles:
        if re.search(rf"(?<!\S){re.escape(role)}(?!\S)", padded):
            return role
    return ""


def _vlan_from_user_table_line(line: str) -> str:
    explicit = re.search(r"\bvlan\s*[:=]?\s*(\d{1,4})\b", line, flags=re.IGNORECASE)
    if explicit:
        return _normalize_vlan(explicit.group(1))
    return ""


def _summarize_observed_networks(ips: list[str]) -> list[str]:
    networks = set()
    for ip_value in ips:
        try:
            ip = ipaddress.ip_address(ip_value)
        except ValueError:
            continue
        if ip.version == 4:
            networks.add(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
    return sorted(networks, key=lambda value: tuple(int(part) for part in value.split("/", 1)[0].split(".")))


def _split_cli(line: str) -> list[str]:
    try:
        return shlex.split(line, posix=True)
    except ValueError:
        return line.split()


def _clean_value(value: str) -> str:
    value = value.strip()
    tokens = _split_cli(value)
    if "position" in [token.lower() for token in tokens]:
        position_index = [token.lower() for token in tokens].index("position")
        tokens = tokens[:position_index]
    if len(tokens) == 1:
        return tokens[0]
    if tokens:
        return " ".join(tokens)
    return value.strip('"')
