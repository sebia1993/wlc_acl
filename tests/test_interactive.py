from wlc_role_acl_collector.interactive import prompt_controller_targets


def test_prompt_controller_targets_telnet_defaults():
    values = iter(
        [
            "192.0.2.20",
            "outside-wlc",
            "telnet",
            "",
            "admin",
            "n",
        ]
    )

    targets = prompt_controller_targets(
        input_func=lambda _prompt: next(values),
        password_func=lambda _prompt: "secret",
    )

    assert len(targets) == 1
    target = targets[0]
    assert target.controller.protocol == "telnet"
    assert target.controller.port == 23
    assert target.controller.device_type == "generic_telnet"
    assert target.credentials.username == "admin"
    assert target.credentials.password == "secret"
