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
- Before pushing to GitHub, opening a PR, or preparing a Release, check whether
  `README.md`, `RELEASE_NOTES.md`, and `CHANGELOG.md` still match the current
  code, folder structure, build scripts, Release assets, and known limitations.

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

## Documentation Rules

- When adding, changing, or removing functionality, decide whether `README.md`
  also needs to change.
- Update `README.md` whenever installation, execution, build, usage, Release
  file names, executable names, folder structure, or requirements change.
- Check `RELEASE_NOTES.md` and `CHANGELOG.md` before GitHub Release work.
- Distinguish implemented features from planned or excluded features.
- Do not document features that are not present in the code.
- Write README procedures as beginner-friendly step-by-step instructions,
  assuming the reader may not be familiar with GitHub or the development
  environment.
- For Windows executable projects, do not imply that macOS can directly produce
  the final Windows EXE. State that Windows EXE packaging must be verified on a
  Windows PC or GitHub Actions Windows runner.
- Do not include internal IP addresses, real device names, credentials, raw
  command output, internal network details, customer names, or generated private
  reports in documentation.
- Use sample values such as `192.0.2.10`, `10.10.10.0/24`, and
  `sample_controller`.
- If documentation does not need to change, state why in the final report.

## Safety Rules

- Keep tests independent from real controllers and private networks.
- Mask sensitive values in diagnostics and generated support material.
- Use stable diagnostic codes and sanitized summaries when field logs cannot be
  shared back to Codex.
