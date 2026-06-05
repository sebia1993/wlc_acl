from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Controller:
    name: str
    host: str
    protocol: str = "ssh"
    port: int = 22
    device_type: str = "aruba_os"
    username_env: str = ""
    password_env: str = ""
    enable_password_env: str = ""


@dataclass
class ControllerCredentials:
    username: str
    password: str
    enable_password: str = ""


@dataclass
class ControllerTarget:
    controller: Controller
    credentials: ControllerCredentials | None = None


@dataclass
class CommandOutput:
    command_id: str
    command: str
    success: bool = True
    output: str = ""
    error: str = ""


@dataclass
class CollectionResult:
    controller: Controller
    commands: list[CommandOutput] = field(default_factory=list)
    raw_file: Path | None = None

    def command_output(self, command_id: str) -> str:
        for item in self.commands:
            if item.command_id == command_id and item.success:
                return item.output
        return ""

    def command_status_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.commands:
            rows.append(
                {
                    "controller": self.controller.name,
                    "command_id": item.command_id,
                    "command": item.command,
                    "success": item.success,
                    "error": item.error,
                    "raw_file": str(self.raw_file or ""),
                }
            )
        return rows


@dataclass
class AclRule:
    controller: str
    acl: str
    sequence: int
    raw: str
    action: str = ""
    source: str = ""
    destination: str = ""
    service: str = ""
    source_detail: str = ""
    destination_detail: str = ""


@dataclass
class NetDestinationEntry:
    controller: str
    alias: str
    sequence: int
    entry_type: str
    value: str
    raw: str = ""


@dataclass
class RolePolicy:
    controller: str
    role: str
    acl_names: list[str] = field(default_factory=list)
    rules: list[AclRule] = field(default_factory=list)
    vlan: str = ""
    access_summary: str = "명확하지 않음"
    access_flags: list[str] = field(default_factory=list)
    rights_output: str = ""
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class VlanNetwork:
    controller: str
    vlan: str
    ip_address: str
    netmask: str
    network: str
    evidence: str


@dataclass
class UserRoleObservation:
    controller: str
    role: str
    observed_user_count: int = 0
    observed_vlans: list[str] = field(default_factory=list)
    observed_networks: list[str] = field(default_factory=list)


@dataclass
class RoleNetworkContext:
    controller: str
    role: str
    effective_vlan: str
    role_user_network: str
    network_evidence: str
    ssids: list[str] = field(default_factory=list)
    ap_groups: list[str] = field(default_factory=list)
    observed_user_count: int = 0
    observed_vlans: list[str] = field(default_factory=list)
    observed_networks: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class SsidRoleMapping:
    controller: str
    ap_group: str
    virtual_ap: str
    ssid_profile: str
    ssid: str
    aaa_profile: str
    role_type: str
    role: str
    vlan: str
    forward_mode: str
    access_summary: str
    effective_vlan: str = ""
    role_user_network: str = "Unknown"
    network_evidence: str = ""
    observed_user_count: int = 0
    dynamic_role_possible: bool = False
    dynamic_role_reason: str = ""


@dataclass
class ParsedController:
    controller: Controller
    ssid_role_mappings: list[SsidRoleMapping] = field(default_factory=list)
    role_policies: dict[str, RolePolicy] = field(default_factory=dict)
    vlan_networks: dict[str, VlanNetwork] = field(default_factory=dict)
    user_role_observations: dict[str, UserRoleObservation] = field(default_factory=dict)
    role_network_contexts: list[RoleNetworkContext] = field(default_factory=list)
    netdestination_aliases: dict[str, list[NetDestinationEntry]] = field(default_factory=dict)
    unresolved: list[dict[str, str]] = field(default_factory=list)
