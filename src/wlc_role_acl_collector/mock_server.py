"""Local mock SSH/Telnet WLC server for development without real devices."""

from __future__ import annotations

import socket
import socketserver
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .mock_scenarios import MockScenario, load_mock_scenario


@dataclass(frozen=True)
class MockServerEndpoint:
    protocol: str
    host: str
    port: int
    scenario: str


class MockWlcServer:
    def __init__(self, protocol: str, scenario: MockScenario, *, host: str = "127.0.0.1", port: int = 0) -> None:
        self.protocol = protocol.casefold()
        self.scenario = scenario
        self.host = host
        self.port = port
        self._server = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @classmethod
    def from_file(cls, protocol: str, scenario_path: Path, *, host: str = "127.0.0.1", port: int = 0):
        return cls(protocol, load_mock_scenario(scenario_path), host=host, port=port)

    def start(self) -> MockServerEndpoint:
        if self.protocol == "telnet":
            self._start_telnet()
        elif self.protocol == "ssh":
            self._start_ssh()
        else:
            raise ValueError("Mock protocol must be ssh or telnet.")
        return MockServerEndpoint(
            protocol=self.protocol,
            host=self.host,
            port=self.port,
            scenario=self.scenario.name,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
            try:
                self._server.server_close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _start_telnet(self) -> None:
        scenario = self.scenario

        class Handler(socketserver.BaseRequestHandler):
            def handle(handler_self) -> None:
                _send(handler_self.request, scenario.username_prompt)
                _read_line(handler_self.request)
                _send(handler_self.request, scenario.password_prompt)
                _read_line(handler_self.request)
                if scenario.login.casefold() != "success":
                    _send(handler_self.request, "Authentication failed\n")
                    return
                _send(handler_self.request, f"\n{scenario.prompt}")
                while True:
                    command = _read_line(handler_self.request)
                    if not command:
                        return
                    if command.casefold() in {"exit", "quit", "logout"}:
                        _send(handler_self.request, "logout\n")
                        return
                    response = scenario.response_for(command)
                    _send(handler_self.request, f"\n{response}\n{scenario.prompt}")

        server = _ThreadingTcpServer((self.host, self.port), Handler)
        self._server = server
        self.port = int(server.server_address[1])
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    def _start_ssh(self) -> None:
        try:
            import paramiko
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("paramiko is required for mock SSH server") from exc

        scenario = self.scenario
        host_key = paramiko.RSAKey.generate(2048)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.listen(20)
        listener.settimeout(0.5)
        self.port = int(listener.getsockname()[1])

        def run() -> None:
            while not self._stop_event.is_set():
                try:
                    client, _address = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(
                    target=_serve_ssh_client,
                    args=(client, host_key, scenario),
                    daemon=True,
                ).start()

        self._server = _SocketWrapper(listener)
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()


def run_mock_server(protocol: str, scenario_path: Path, *, host: str = "127.0.0.1", port: int = 0) -> MockWlcServer:
    server = MockWlcServer.from_file(protocol, scenario_path, host=host, port=port)
    endpoint = server.start()
    print(f"Mock {endpoint.protocol.upper()} WLC server listening on {endpoint.host}:{endpoint.port}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        server.stop()
    return server


class _ThreadingTcpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


class _SocketWrapper:
    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock

    def shutdown(self) -> None:
        self.sock.close()

    def server_close(self) -> None:
        self.sock.close()


def _serve_ssh_client(client: socket.socket, host_key, scenario: MockScenario) -> None:
    import paramiko

    class Server(paramiko.ServerInterface):
        def __init__(self) -> None:
            self.event = threading.Event()

        def check_auth_password(self, username: str, password: str):
            if scenario.login.casefold() == "success":
                return paramiko.AUTH_SUCCESSFUL
            return paramiko.AUTH_FAILED

        def get_allowed_auths(self, username: str) -> str:
            return "password"

        def check_channel_request(self, kind: str, chanid: int):
            if kind == "session":
                return paramiko.OPEN_SUCCEEDED
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

        def check_channel_shell_request(self, channel) -> bool:
            self.event.set()
            return True

        def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes) -> bool:
            return True

    transport = paramiko.Transport(client)
    try:
        transport.add_server_key(host_key)
        server = Server()
        transport.start_server(server=server)
        channel = transport.accept(10)
        if channel is None:
            return
        server.event.wait(10)
        channel.send(f"{scenario.prompt}")
        _ssh_command_loop(channel, scenario)
    finally:
        try:
            transport.close()
        except Exception:
            pass


def _ssh_command_loop(channel, scenario: MockScenario) -> None:
    buffer = ""
    while True:
        data = channel.recv(1024)
        if not data:
            return
        buffer += data.decode("utf-8", errors="ignore")
        while "\n" in buffer or "\r" in buffer:
            command, buffer = _split_command_buffer(buffer)
            command = command.strip()
            if not command:
                continue
            if command.casefold() in {"exit", "quit", "logout"}:
                channel.send("logout\n")
                return
            channel.send(f"\n{scenario.response_for(command)}\n{scenario.prompt}")


def _split_command_buffer(buffer: str) -> tuple[str, str]:
    indexes = [index for index in (buffer.find("\n"), buffer.find("\r")) if index >= 0]
    index = min(indexes)
    return buffer[:index], buffer[index + 1 :]


def _send(sock: socket.socket, text: str) -> None:
    sock.sendall(text.encode("utf-8"))


def _read_line(sock: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        data = sock.recv(1)
        if not data:
            return b"".join(chunks).decode("utf-8", errors="ignore").strip()
        if data in {b"\n", b"\r"}:
            return b"".join(chunks).decode("utf-8", errors="ignore").strip()
        chunks.append(data)
