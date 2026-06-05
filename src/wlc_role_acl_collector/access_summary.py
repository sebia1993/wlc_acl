from __future__ import annotations

import re

from .models import AclRule


RFC1918_PATTERNS = (
    r"\b10\.",
    r"\b172\.(1[6-9]|2\d|3[0-1])\.",
    r"\b192\.168\.",
    r"RFC1918",
    r"internal",
    r"inside",
)


def classify_access(rules: list[AclRule]) -> tuple[str, list[str]]:
    if not rules:
        return "명확하지 않음", ["no_acl_rules"]

    raw_lines = [rule.raw.lower() for rule in rules]
    combined = "\n".join(raw_lines)
    flags: list[str] = []

    has_any_permit = any(_is_broad_permit(line) for line in raw_lines)
    has_src_nat = "src-nat" in combined
    has_dst_nat = "dst-nat" in combined
    has_dns = "svc-dns" in combined or re.search(r"\b53\b", combined) is not None
    has_dhcp = "svc-dhcp" in combined or re.search(r"\b(67|68)\b", combined) is not None
    has_web = any(token in combined for token in ("svc-http", "svc-https", "svc-http-proxy"))
    has_deny = any(rule.action == "deny" or " deny" in line for rule, line in zip(rules, raw_lines))
    has_internal_deny = any(
        (" deny" in line or line.endswith("deny"))
        and any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in RFC1918_PATTERNS)
        for line in raw_lines
    )
    has_only_deny = all((rule.action == "deny" or " deny" in line) for rule, line in zip(rules, raw_lines))

    if has_internal_deny:
        flags.append("internal_network_deny")
    if has_src_nat:
        flags.append("source_nat")
    if has_dst_nat:
        flags.append("destination_nat")
    if has_dns:
        flags.append("dns")
    if has_dhcp:
        flags.append("dhcp")
    if has_web:
        flags.append("web")
    if has_any_permit:
        flags.append("broad_permit")
    if has_deny:
        flags.append("deny")

    if has_only_deny:
        return "대부분 차단", flags
    if has_internal_deny and (has_src_nat or has_any_permit or has_web):
        return "내부망 차단, 인터넷 중심", flags
    if has_any_permit and not has_internal_deny:
        return "전체 허용", flags
    if has_dst_nat and (has_dns or has_dhcp or has_web):
        return "포털/DNS/DHCP 중심", flags
    if has_dns or has_dhcp or has_web:
        return "제한적 허용", flags
    if has_deny:
        return "제한적 허용", flags
    return "명확하지 않음", flags or ["unclassified"]


def _is_broad_permit(line: str) -> bool:
    compact = re.sub(r"\s+", " ", line.strip())
    return bool(
        re.search(r"^(any|user)\s+any\s+any\s+permit\b", compact)
        or re.search(r"^(any|user)\s+any\s+any\s+src-nat\b", compact)
        or re.search(r"^(any|user)\s+any\s+any\s+route\b", compact)
    )

