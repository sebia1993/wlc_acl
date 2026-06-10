from wlc_role_acl_collector.acl_evaluator import build_access_check_data, evaluate_access


def test_evaluate_access_blocks_first_matching_deny_rule():
    access_data = build_access_check_data(
        [
            {
                "role": "corp-employee",
                "user_count": 1,
                "zero_user_hidden": False,
                "panel_id": "role-panel-1",
                "rows": [
                    {
                        "acl": "corp-acl",
                        "sequence": 1,
                        "action": "deny",
                        "source": "any",
                        "destination": "network 10.0.0.0 255.0.0.0",
                        "service": "any",
                        "raw_rule": "any network 10.0.0.0 255.0.0.0 any deny",
                    },
                    {
                        "acl": "corp-acl",
                        "sequence": 2,
                        "action": "src-nat",
                        "source": "any",
                        "destination": "any",
                        "service": "any",
                        "raw_rule": "any any any src-nat",
                    },
                ],
            }
        ],
        [],
        [{"role": "corp-employee", "local_role_network": "10.40.1.0/24"}],
    )

    result = evaluate_access(
        access_data,
        role="corp-employee",
        source_ip="10.40.1.10",
        destination_ip="10.1.2.3",
        service="svc-http",
    )

    assert result["status"] == "blocked"
    assert result["verdict"] == "Blocked"
    assert result["matchedRule"]["sequence"] == "1"


def test_evaluate_access_treats_nat_actions_as_special_allow():
    access_data = build_access_check_data(
        [
            {
                "role": "corp-employee",
                "user_count": 1,
                "zero_user_hidden": False,
                "panel_id": "role-panel-1",
                "rows": [
                    {
                        "acl": "corp-acl",
                        "sequence": 1,
                        "action": "deny",
                        "source": "any",
                        "destination": "network 10.0.0.0 255.0.0.0",
                        "service": "any",
                        "raw_rule": "any network 10.0.0.0 255.0.0.0 any deny",
                    },
                    {
                        "acl": "corp-acl",
                        "sequence": 2,
                        "action": "src-nat",
                        "source": "any",
                        "destination": "any",
                        "service": "any",
                        "raw_rule": "any any any src-nat",
                    },
                ],
            }
        ],
        [],
        [{"role": "corp-employee", "local_role_network": "10.40.1.0/24"}],
    )

    result = evaluate_access(
        access_data,
        role="corp-employee",
        source_ip="10.40.1.10",
        destination_ip="8.8.8.8",
        service="svc-http",
    )

    assert result["status"] == "special"
    assert result["verdict"] == "Allowed with NAT/Special Action"
    assert result["matchedRule"]["sequence"] == "2"


def test_evaluate_access_auto_service_matches_alias_and_marks_specific_service_conditional():
    access_data = build_access_check_data(
        [
            {
                "role": "guest-logon",
                "user_count": 2,
                "zero_user_hidden": False,
                "panel_id": "role-panel-1",
                "rows": [
                    {
                        "acl": "guest-logon-acl",
                        "sequence": 1,
                        "action": "dst-nat",
                        "source": "user",
                        "destination": "alias controller",
                        "service": "svc-https",
                        "raw_rule": "user alias controller svc-https dst-nat 8081",
                    }
                ],
            }
        ],
        [
            {"alias": "controller", "entry_type": "host", "value": "10.10.10.1"},
            {"alias": "controller", "entry_type": "network", "value": "10.10.20.0 255.255.255.0"},
        ],
        [],
    )

    exact_result = evaluate_access(
        access_data,
        role="guest-logon",
        source_ip="10.30.0.10",
        destination_ip="10.10.20.50",
        service="svc-https",
    )
    conditional_result = evaluate_access(
        access_data,
        role="guest-logon",
        source_ip="10.30.0.10",
        destination_ip="10.10.20.50",
    )

    assert exact_result["status"] == "special"
    assert exact_result["conditional"] is False
    assert conditional_result["status"] == "special"
    assert conditional_result["conditional"] is True
    assert "Service auto mode matched a rule limited to svc-https" in conditional_result["warnings"][0]


def test_evaluate_access_auto_service_uses_first_source_destination_match_in_order():
    access_data = build_access_check_data(
        [
            {
                "role": "guest-logon",
                "user_count": 2,
                "zero_user_hidden": False,
                "panel_id": "role-panel-1",
                "rows": [
                    {
                        "acl": "guest-logon-acl",
                        "sequence": 10,
                        "action": "deny",
                        "source": "user",
                        "destination": "host 10.10.10.10",
                        "service": "svc-http",
                        "raw_rule": "user host 10.10.10.10 svc-http deny",
                    },
                    {
                        "acl": "guest-logon-acl",
                        "sequence": 20,
                        "action": "permit",
                        "source": "user",
                        "destination": "host 10.10.10.10",
                        "service": "svc-https",
                        "raw_rule": "user host 10.10.10.10 svc-https permit",
                    },
                ],
            }
        ],
        [],
        [],
    )

    result = evaluate_access(
        access_data,
        role="guest-logon",
        source_ip="10.30.0.10",
        destination_ip="10.10.10.10",
    )

    assert result["status"] == "blocked"
    assert result["conditional"] is True
    assert result["matchedRule"]["sequence"] == "10"


def test_evaluate_access_warns_when_source_is_outside_local_role_network():
    access_data = build_access_check_data(
        [
            {
                "role": "corp-employee",
                "user_count": 1,
                "zero_user_hidden": False,
                "panel_id": "role-panel-1",
                "rows": [
                    {
                        "acl": "corp-acl",
                        "sequence": 1,
                        "action": "permit",
                        "source": "any",
                        "destination": "any",
                        "service": "any",
                        "raw_rule": "any any any permit",
                    }
                ],
            }
        ],
        [],
        [{"role": "corp-employee", "local_role_network": "10.40.1.0/24"}],
    )

    result = evaluate_access(
        access_data,
        role="corp-employee",
        source_ip="10.50.1.10",
        destination_ip="8.8.8.8",
    )

    assert result["status"] == "allowed"
    assert result["warnings"] == [
        "Source IP 10.50.1.10 is outside the local Role Network mapping: 10.40.1.0/24"
    ]
