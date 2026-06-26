# WLC Role ACL Collector Codex Instructions

## Scope

This file applies to the `wlc_role_acl_collector` repository.

Keep this `AGENTS.md` tracked in Git. It is part of the source handoff so the
same project rules follow GitHub clones, MacBook work, GitHub Actions, and
future Windows workstations.

## Project Summary

This repository collects and analyzes Aruba WLC role and ACL information. It
contains CLI and GUI launchers, parser and evaluator modules, diagnostic mode,
mock scenarios, redaction helpers, reports, and Windows packaging support.

## Default Workflow

- Inspect `git status --short --branch` before editing or committing.
- Prefer fixtures, mock scenarios, and parser-level tests over live controller
  access.
- Treat controller addresses, host names, credentials, command output, role
  names, ACLs, and generated reports as sensitive operational data.
- Do not run live controller changes or destructive actions unless the user
  explicitly asks for that exact operation.
- Keep generated reports, logs, build folders, dist folders, release artifacts,
  and local inventories out of Git.

## Important Areas

- `src/wlc_role_acl_collector/`: package source for CLI, collector, parser,
  ACL evaluation, diagnostics, GUI support, redaction, and reporting.
- `cli_launcher.py`: CLI launch helper.
- `gui_launcher.py`: GUI launch helper.
- `config/`: sanitized controller examples, role network templates, and mock
  scenarios.
- `tests/`: deterministic tests for parser, collector, ACL evaluation,
  diagnostics, GUI support, mock server, reports, and tooling.
- `tools/`: validation and documentation generation helpers.
- `docs/`: Korean user, developer, security, diagnostic, and error-code docs.

## Validation Commands

```powershell
python -m pytest
powershell -ExecutionPolicy Bypass -File .\tools\validate.ps1
```

For GUI or packaging changes, verify the Windows executable build separately on
a Windows machine.

## Safety Rules

- Keep tests independent from real controllers and private networks.
- Mask sensitive values in diagnostics and generated support material.
- Use stable diagnostic codes and sanitized summaries when field logs cannot be
  shared back to Codex.
