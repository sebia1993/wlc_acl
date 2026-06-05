from wlc_role_acl_collector.config import (
    default_device_type_for_protocol,
    default_port_for_protocol,
    load_controllers,
)


def test_protocol_defaults():
    assert default_port_for_protocol("ssh") == 22
    assert default_port_for_protocol("telnet") == 23
    assert default_device_type_for_protocol("ssh") == "aruba_os"
    assert default_device_type_for_protocol("telnet") == "generic_telnet"


def test_load_controllers_defaults_telnet_device_type(tmp_path):
    path = tmp_path / "controllers.csv"
    path.write_text(
        "name,host,protocol,port,device_type,username_env,password_env,enable_password_env\n"
        "outside,192.0.2.20,telnet,,,USER_ENV,PASS_ENV,\n",
        encoding="utf-8",
    )

    controller = load_controllers(path)[0]

    assert controller.port == 23
    assert controller.device_type == "generic_telnet"


def test_load_controllers_ignores_legacy_site_zone_columns(tmp_path):
    path = tmp_path / "controllers.csv"
    path.write_text(
        "name,host,protocol,port,device_type,site,zone,username_env,password_env,enable_password_env\n"
        "outside,192.0.2.20,telnet,,,HQ,outside,USER_ENV,PASS_ENV,\n",
        encoding="utf-8",
    )

    controller = load_controllers(path)[0]

    assert controller.port == 23
    assert controller.device_type == "generic_telnet"
    assert controller.username_env == "USER_ENV"
    assert controller.password_env == "PASS_ENV"
