from pathlib import Path

import pytest
from openpyxl import Workbook

from wlc_role_acl_collector.role_networks import (
    RoleNetworkDefinitionError,
    load_role_network_definitions,
)


def test_load_role_network_definitions_normalizes_korean_template(tmp_path):
    path = tmp_path / "role_networks.xlsx"
    _write_workbook(
        path,
        [
            ["Role 이름", "네트워크 대역", "서브넷마스크"],
            ["guest-logon", "10.30.0.5", "255.255.255.0"],
            ["corp-employee", "10.40.1.0/24", ""],
            ["guest-logon", "10.31.0.0", "255.255.0.0"],
        ],
    )

    definitions = load_role_network_definitions(path)

    assert [(item.role, item.network, item.subnet_mask, item.source_row) for item in definitions] == [
        ("guest-logon", "10.30.0.0/24", "255.255.255.0", 2),
        ("corp-employee", "10.40.1.0/24", "255.255.255.0", 3),
        ("guest-logon", "10.31.0.0/16", "255.255.0.0", 4),
    ]


def test_load_role_network_definitions_rejects_invalid_rows(tmp_path):
    path = tmp_path / "role_networks.xlsx"
    _write_workbook(
        path,
        [
            ["role", "network", "subnet_mask"],
            ["guest-logon", "10.30.0.0", ""],
            ["corp-employee", "10.40.1.0/24", "255.255.0.0"],
        ],
    )

    with pytest.raises(RoleNetworkDefinitionError) as exc_info:
        load_role_network_definitions(path)

    message = str(exc_info.value)
    assert "Subnet mask is required" in message
    assert "CIDR prefix and subnet mask do not match" in message


def _write_workbook(path: Path, rows: list[list[str]]) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
