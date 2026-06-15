import socket
from pathlib import Path

import pytest

from wlc_role_acl_collector.mock_scenarios import load_mock_scenario
from wlc_role_acl_collector.mock_server import MockWlcServer


def _recv_until(sock: socket.socket, marker: str) -> str:
    chunks: list[bytes] = []
    while marker.encode("utf-8") not in b"".join(chunks):
        chunks.append(sock.recv(1024))
    return b"".join(chunks).decode("utf-8", errors="ignore")


def test_load_mock_scenario_from_packaged_config():
    scenario = load_mock_scenario(Path("config/mock_scenarios/success_minimal.json"))

    assert scenario.name == "success_minimal"
    assert "show configuration effective" in scenario.commands


def test_telnet_mock_server_returns_synthetic_command_output():
    scenario = load_mock_scenario(Path("config/mock_scenarios/success_minimal.json"))
    server = MockWlcServer("telnet", scenario)
    endpoint = server.start()
    try:
        with socket.create_connection((endpoint.host, endpoint.port), timeout=5) as sock:
            assert "Username:" in _recv_until(sock, "Username:")
            sock.sendall(b"admin\n")
            assert "Password:" in _recv_until(sock, "Password:")
            sock.sendall(b"password\n")
            assert "(mock-wlc) #" in _recv_until(sock, "(mock-wlc) #")
            sock.sendall(b"show version\n")
            response = _recv_until(sock, "(mock-wlc) #")
            assert "MOCK-WLC" in response
    finally:
        server.stop()


def test_ssh_mock_server_accepts_shell_commands():
    paramiko = pytest.importorskip("paramiko")
    scenario = load_mock_scenario(Path("config/mock_scenarios/success_minimal.json"))
    server = MockWlcServer("ssh", scenario)
    endpoint = server.start()
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            endpoint.host,
            port=endpoint.port,
            username="admin",
            password="password",
            look_for_keys=False,
            allow_agent=False,
            timeout=5,
        )
        channel = client.invoke_shell()
        channel.settimeout(5)
        _recv_channel_until(channel, "(mock-wlc) #")
        channel.send("show version\n")
        response = _recv_channel_until(channel, "(mock-wlc) #")
        assert "MOCK-WLC" in response
        client.close()
    finally:
        server.stop()


def _recv_channel_until(channel, marker: str) -> str:
    chunks: list[bytes] = []
    marker_bytes = marker.encode("utf-8")
    while marker_bytes not in b"".join(chunks):
        chunks.append(channel.recv(1024))
    return b"".join(chunks).decode("utf-8", errors="ignore")
