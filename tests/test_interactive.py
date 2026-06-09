from wlc_role_acl_collector.interactive import prompt_controller_targets


def test_prompt_controller_targets_telnet_defaults():
    prompts = []
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
        input_func=lambda prompt: prompts.append(prompt) or next(values),
        password_func=lambda _prompt: "secret",
    )

    assert prompts[:2] == ["WLC IP: ", "Report name [wlc-192.0.2.20]: "]
    assert len(targets) == 1
    target = targets[0]
    assert target.controller.protocol == "telnet"
    assert target.controller.port == 23
    assert target.controller.device_type == "generic_telnet"
    assert target.credentials.username == "admin"
    assert target.credentials.password == "secret"
