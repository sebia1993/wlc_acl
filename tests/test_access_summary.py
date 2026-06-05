from wlc_role_acl_collector.access_summary import classify_access
from wlc_role_acl_collector.models import AclRule


def test_classify_internal_block_with_internet_nat():
    rules = [
        AclRule("wlc", "acl", 1, "any network 10.0.0.0 255.0.0.0 any deny", action="deny"),
        AclRule("wlc", "acl", 2, "any any any src-nat", action="src-nat"),
    ]

    summary, flags = classify_access(rules)

    assert summary == "내부망 차단, 인터넷 중심"
    assert "internal_network_deny" in flags
    assert "source_nat" in flags


def test_classify_portal_dns_dhcp():
    rules = [
        AclRule("wlc", "acl", 1, "user any svc-dhcp permit", action="permit"),
        AclRule("wlc", "acl", 2, "user any svc-dns permit", action="permit"),
        AclRule("wlc", "acl", 3, "user any svc-http dst-nat 8080", action="dst-nat"),
    ]

    summary, flags = classify_access(rules)

    assert summary == "포털/DNS/DHCP 중심"
    assert {"dhcp", "dns", "web", "destination_nat"}.issubset(set(flags))

