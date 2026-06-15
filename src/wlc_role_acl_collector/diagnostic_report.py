"""Write safe diagnostic reports without raw device output."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from . import __version__
from .diagnostic_codes import DiagnosticCode, get_diagnostic_code
from .diagnostic_events import DiagnosticEvent
from .redaction import redact_payload, redact_sensitive_text


def write_diagnostic_report(
    output_dir: Path,
    *,
    events: list[DiagnosticEvent],
    primary_code: str | DiagnosticCode,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    code = primary_code if isinstance(primary_code, DiagnosticCode) else get_diagnostic_code(primary_code)
    payload = _diagnostic_payload(events=events, primary_code=code, metadata=metadata or {})

    json_path = output_dir / "diagnostic_summary.json"
    html_path = output_dir / "diagnostic_summary.html"
    log_path = output_dir / "diagnostic_run.log"

    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(_diagnostic_html(payload), encoding="utf-8")
    log_path.write_text(_diagnostic_log(payload), encoding="utf-8")
    return {"json": json_path, "html": html_path, "log": log_path}


def _diagnostic_payload(
    *,
    events: list[DiagnosticEvent],
    primary_code: DiagnosticCode,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    status = "ok" if primary_code.code == "OK" else "attention"
    safe_metadata = redact_payload(metadata)
    return {
        "schema_version": "1.0",
        "app_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "diagnostic",
        "status": status,
        "raw_output_saved": False,
        "primary": {
            "code": primary_code.code,
            "stage": primary_code.stage,
            "category": primary_code.category,
            "title": primary_code.title,
            "safe_message": primary_code.safe_message,
            "likely_cause": primary_code.likely_cause,
            "operator_action": primary_code.operator_action,
            "retryable": primary_code.retryable,
        },
        "metadata": safe_metadata,
        "events": [event.to_dict() for event in events],
    }


def _diagnostic_html(payload: dict[str, Any]) -> str:
    primary = payload.get("primary", {})
    rows = "\n".join(
        f"""
        <tr>
          <td>{escape(str(event.get('timestamp', '')))}</td>
          <td>{escape(str(event.get('stage', '')))}</td>
          <td>{escape(str(event.get('status', '')))}</td>
          <td>{escape(str(event.get('code', '')))}</td>
          <td>{escape(str(event.get('command_id', '')))}</td>
          <td>{escape(str(event.get('message', '')))}</td>
        </tr>
        """
        for event in payload.get("events", [])
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WLC Diagnostic Summary</title>
  <style>
    body {{ background: #f4f7fb; color: #172033; font-family: Segoe UI, Arial, sans-serif; margin: 0; }}
    main {{ margin: 0 auto; max-width: 1120px; padding: 24px; }}
    .panel {{ background: #fff; border: 1px solid #d8e0ea; border-radius: 8px; box-shadow: 0 8px 24px rgba(15, 23, 42, .06); margin-bottom: 16px; padding: 18px; }}
    h1 {{ font-size: 24px; margin: 0 0 6px; }}
    h2 {{ font-size: 17px; margin: 0 0 12px; }}
    .code {{ background: #eef4ff; border: 1px solid #bdd4ff; border-radius: 6px; display: inline-block; font-weight: 700; padding: 5px 8px; }}
    .notice {{ color: #667085; font-size: 13px; }}
    .grid {{ display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }}
    .field strong {{ color: #667085; display: block; font-size: 11px; text-transform: uppercase; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid #e4e9f1; font-size: 13px; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f8fafc; color: #475467; }}
  </style>
</head>
<body>
<main>
  <section class="panel">
    <h1>WLC Diagnostic Summary</h1>
    <p class="notice">This report intentionally excludes raw device output, IP addresses, hostnames, credentials, and command results.</p>
    <p class="code">{escape(str(primary.get('code', '')))}</p>
  </section>
  <section class="panel">
    <h2>Primary Finding</h2>
    <div class="grid">
      <div class="field"><strong>Stage</strong>{escape(str(primary.get('stage', '')))}</div>
      <div class="field"><strong>Category</strong>{escape(str(primary.get('category', '')))}</div>
      <div class="field"><strong>Title</strong>{escape(str(primary.get('title', '')))}</div>
      <div class="field"><strong>Retryable</strong>{escape(str(primary.get('retryable', '')))}</div>
    </div>
    <p>{escape(str(primary.get('safe_message', '')))}</p>
    <p><strong>Likely cause:</strong> {escape(str(primary.get('likely_cause', '')))}</p>
    <p><strong>Operator action:</strong> {escape(str(primary.get('operator_action', '')))}</p>
  </section>
  <section class="panel">
    <h2>Stage Events</h2>
    <table>
      <thead><tr><th>Time</th><th>Stage</th><th>Status</th><th>Code</th><th>Command ID</th><th>Safe Message</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""


def _diagnostic_log(payload: dict[str, Any]) -> str:
    primary = payload.get("primary", {})
    lines = [
        "WLC diagnostic run log",
        "raw_output_saved: false",
        f"primary_code: {primary.get('code', '')}",
        f"primary_stage: {primary.get('stage', '')}",
        "",
        "events:",
    ]
    for event in payload.get("events", []):
        lines.append(
            " | ".join(
                redact_sensitive_text(str(value))
                for value in (
                    event.get("timestamp", ""),
                    event.get("stage", ""),
                    event.get("status", ""),
                    event.get("code", ""),
                    event.get("command_id", ""),
                    event.get("message", ""),
                )
            )
        )
    return "\n".join(lines)
