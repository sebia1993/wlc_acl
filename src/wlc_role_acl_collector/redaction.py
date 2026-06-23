"""Sensitive data redaction for reports and logs."""

from __future__ import annotations

import re
from typing import Any


MASK = "***"
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
    "community",
}

_IPV4_PATTERN = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_MAC_PATTERN = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_AUTH_HEADER_PATTERN = re.compile(r"(?i)\b(authorization\s*:\s*)(bearer|basic)\s+([A-Za-z0-9._~+/=-]+)")
_URL_CREDENTIAL_PATTERN = re.compile(r"(?i)(://[^/\s:@]+):([^@\s]+)@")
_KEY_VALUE_SECRET_PATTERN = re.compile(
    r"(?ix)"
    r"\b("
    r"password|passwd|pwd|secret|token|api[_-]?key|apikey|"
    r"access[_-]?token|refresh[_-]?token|private[_-]?key|community"
    r")\b"
    r"(\s*[:=]\s*|\s+)"
    r"(\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_NETWORK_SECRET_PATTERN = re.compile(
    r"(?i)\b((?:enable\s+)?secret|snmp-server\s+community|username\s+\S+\s+(?:password|secret))"
    r"\s+(?:[0-9]\s+)?([^\s,;]+)"
)
_HOSTNAME_PATTERN = re.compile(
    r"(?ix)"
    r"\b("
    r"(?:[a-z][a-z0-9-]{2,63}\.)+(?:local|lan|corp|internal|com|net|kr)|"
    r"(?:wlc|mm|aruba|ctrl|controller|host)[a-z0-9._-]+"
    r")\b"
)


class Redactor:
    def __init__(self) -> None:
        # 같은 값은 같은 라벨로 치환해 리포트 안에서 흐름은 따라갈 수 있게 합니다.
        # 예: 같은 IP는 항상 <IP:1>로 보이지만 실제 값은 노출하지 않습니다.
        self._ip_labels: dict[str, str] = {}
        self._mac_labels: dict[str, str] = {}
        self._host_labels: dict[str, str] = {}

    def redact(self, value: str) -> str:
        if not value:
            return value

        text = str(value)
        text = _AUTH_HEADER_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)} {MASK}", text)
        text = _URL_CREDENTIAL_PATTERN.sub(lambda match: f"{match.group(1)}:{MASK}@", text)
        text = _NETWORK_SECRET_PATTERN.sub(lambda match: f"{match.group(1)} {MASK}", text)
        text = _KEY_VALUE_SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}{MASK}", text)
        text = _MAC_PATTERN.sub(lambda match: self._label(self._mac_labels, match.group(0), "MAC"), text)
        text = _IPV4_PATTERN.sub(lambda match: self._label(self._ip_labels, match.group(0), "IP"), text)
        text = _HOSTNAME_PATTERN.sub(lambda match: self._label(self._host_labels, match.group(0), "HOST"), text)
        return text

    @staticmethod
    def _label(cache: dict[str, str], value: str, prefix: str) -> str:
        key = value.casefold()
        if key not in cache:
            cache[key] = f"<{prefix}:{len(cache) + 1}>"
        return cache[key]


_DEFAULT_REDACTOR = Redactor()


def redact_sensitive_text(value: str) -> str:
    return _DEFAULT_REDACTOR.redact(value)


def redact_payload(value: Any) -> Any:
    # 진단 리포트는 문자열뿐 아니라 dict/list 형태의 metadata도 저장합니다.
    # 구조는 유지하되 민감한 key나 값만 재귀적으로 마스킹합니다.
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item) for item in value)
    if isinstance(value, dict):
        return {
            key: MASK if str(key).strip().casefold() in _SENSITIVE_KEYS else redact_payload(item)
            for key, item in value.items()
        }
    return value


def redaction_self_test() -> bool:
    sample = "host wlc-prod-01 10.10.10.10 password Secret123 snmp-server community public aa:bb:cc:dd:ee:ff"
    redacted = Redactor().redact(sample)
    return (
        "10.10.10.10" not in redacted
        and "Secret123" not in redacted
        and "public" not in redacted
        and "aa:bb:cc:dd:ee:ff" not in redacted.casefold()
        and "wlc-prod-01" not in redacted
    )
