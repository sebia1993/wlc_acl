from pathlib import Path

from wlc_role_acl_collector.aos8_parser import discover_aliases_from_config, discover_roles_from_config, parse_controller_config
from wlc_role_acl_collector.models import Controller


FIXTURE = Path(__file__).parent / "fixtures" / "sample_controller" / "show_configuration_effective.txt"


def test_discover_roles_from_config():
    roles = discover_roles_from_config(FIXTURE.read_text(encoding="utf-8"))

    assert "corp-employee" in roles
    assert "guest-logon" in roles
    assert "logon" in roles


def test_discover_aliases_from_config():
    aliases = discover_aliases_from_config(FIXTURE.read_text(encoding="utf-8"))

    assert aliases == ["controller"]


def test_parse_ssid_role_mapping_and_acl_summary():
    controller = Controller(name="sample_controller", host="192.0.2.10")
    fixture_dir = FIXTURE.parent
    parsed = parse_controller_config(
        controller=controller,
        config_text=FIXTURE.read_text(encoding="utf-8"),
        ip_interface_brief_output=(fixture_dir / "show_ip_interface_brief.txt").read_text(encoding="utf-8"),
        user_table_output=(fixture_dir / "show_user_table.txt").read_text(encoding="utf-8"),
    )

    rows = {
        (mapping.ssid, mapping.role_type, mapping.role): mapping
        for mapping in parsed.ssid_role_mappings
    }

    assert ("CORP", "dot1x-default", "corp-employee") in rows
    assert rows[("CORP", "dot1x-default", "corp-employee")].access_summary == "내부망 차단, 인터넷 중심"
    assert rows[("CORP", "dot1x-default", "corp-employee")].dynamic_role_possible is True
    assert ("GUEST", "initial", "guest-logon") in rows
    assert parsed.role_policies["corp-employee"].acl_names == ["corp-acl"]
    assert parsed.role_policies["corp-employee"].vlan == "40"
    assert "controller" in parsed.netdestination_aliases
    assert [entry.value for entry in parsed.netdestination_aliases["controller"]] == [
        "10.10.10.1",
        "10.10.20.0 255.255.255.0",
    ]
    guest_alias_rule = next(
        rule for rule in parsed.role_policies["guest-logon"].rules if rule.destination == "alias controller"
    )
    assert "host 10.10.10.1" in guest_alias_rule.destination_detail
    assert "network 10.10.20.0 255.255.255.0" in guest_alias_rule.destination_detail
    assert not any(item["type"] == "alias_not_defined" for item in parsed.unresolved)

    assert parsed.vlan_networks["20"].network == "10.20.0.0/24"
    assert parsed.vlan_networks["30"].network == "10.30.0.0/24"
    assert parsed.vlan_networks["40"].network == "10.40.1.0/24"
    assert parsed.vlan_networks["40"].evidence == "show ip interface brief"

    corp = rows[("CORP", "dot1x-default", "corp-employee")]
    assert corp.effective_vlan == "40"
    assert corp.role_user_network == "10.40.1.0/24"
    assert corp.network_evidence == "show ip interface brief"
    assert corp.observed_user_count == 1

    guest = rows[("GUEST", "initial", "guest-logon")]
    assert guest.effective_vlan == "30"
    assert guest.role_user_network == "10.30.0.0/24"
    assert guest.network_evidence == "interface vlan configuration"
    assert guest.observed_user_count == 2

    contexts = {(context.role, context.effective_vlan): context for context in parsed.role_network_contexts}
    assert contexts[("corp-employee", "40")].observed_networks == ["10.40.1.0/24"]
    assert contexts[("guest-logon", "30")].observed_networks == ["10.30.0.0/24"]


def test_parse_show_netdestination_output_overrides_config_alias_detail():
    controller = Controller(name="sample_controller", host="192.0.2.10")
    parsed = parse_controller_config(
        controller=controller,
        config_text=FIXTURE.read_text(encoding="utf-8"),
        netdestination_outputs={
            "controller": """
Name: controller
Destination ID: 34
Position Type IP addr Mask-Len/Range
-------- ---- ------- --------------
1 host 10.20.30.40 32
2 name 0.0.0.8 controller.example.com
""",
        },
    )

    assert [entry.value for entry in parsed.netdestination_aliases["controller"]] == [
        "10.20.30.40/32",
        "controller.example.com",
    ]
