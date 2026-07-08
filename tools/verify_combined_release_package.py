"""Validate the single combined Windows release ZIP.

The combined package is the only file uploaded to GitHub Releases. It contains
the GUI/CLI package under ``gui/`` and the Streamlit portable package under
``web/``.
"""

from __future__ import annotations

import argparse
import hashlib
import platform
import subprocess
import tempfile
import zipfile
from pathlib import Path


REQUIRED_FILES = {
    "README_START_HERE_KO.txt",
    "gui/WlcRoleAclCollectorGUI.exe",
    "gui/WlcRoleAclCollectorCLI.exe",
    "gui/USER_GUIDE_KO.md",
    "gui/USER_GUIDE_KO.html",
    "gui/DEVELOPER_GUIDE_KO.md",
    "gui/DEVELOPER_GUIDE_KO.html",
    "gui/ERROR_CODES_KO.md",
    "gui/ERROR_CODES_KO.html",
    "gui/DIAGNOSTIC_MODE_KO.md",
    "gui/DIAGNOSTIC_MODE_KO.html",
    "gui/SECURITY_MODEL_KO.md",
    "gui/SECURITY_MODEL_KO.html",
    "gui/config/role_networks.example.xlsx",
    "gui/config/mock_scenarios/auth_failed.json",
    "gui/config/mock_scenarios/missing_config.json",
    "gui/config/mock_scenarios/permission_denied.json",
    "gui/config/mock_scenarios/success_minimal.json",
    "web/start_webapp.cmd",
    "web/webapp_settings.cmd",
    "web/README_WEBAPP_KO.txt",
    "web/python/python.exe",
    "web/app/app.py",
    "web/config/role_networks.example.xlsx",
}

REQUIRED_PREFIXES = (
    "web/python/Lib/site-packages/streamlit/",
    "web/python/Lib/site-packages/wlc_role_acl_collector/",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a combined WLC Role ACL Collector Windows release ZIP.")
    parser.add_argument("--zip", dest="zip_path", type=Path, help="combined release ZIP path")
    parser.add_argument("--dist", type=Path, default=Path("dist"), help="directory containing a combined release ZIP")
    parser.add_argument("--expected-sha256", help="expected SHA256 hash for the combined ZIP")
    parser.add_argument("--smoke", action="store_true", help="run GUI CLI and web portable smoke checks on Windows")
    parser.add_argument(
        "--require-smoke",
        action="store_true",
        help="fail if --smoke is requested on a non-Windows host",
    )
    args = parser.parse_args(argv)

    zip_path = args.zip_path or _find_latest_combined_zip(args.dist)
    if not zip_path.exists():
        raise SystemExit(f"Combined release ZIP does not exist: {zip_path}")
    if zip_path.stat().st_size <= 0:
        raise SystemExit(f"Combined release ZIP is empty: {zip_path}")

    names = _read_zip_names(zip_path)
    _verify_required_files(names)
    _verify_required_prefixes(names)

    if args.expected_sha256:
        _verify_expected_sha256(zip_path, args.expected_sha256)

    if args.smoke:
        _smoke_combined_package(zip_path, require=args.require_smoke)

    print(f"Verified combined release package: {zip_path}")
    return 0


def _find_latest_combined_zip(dist_dir: Path) -> Path:
    candidates = sorted(
        dist_dir.glob("WlcRoleAclCollectorWindows*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SystemExit(f"No combined release ZIP was found in {dist_dir}")
    return candidates[0]


def _read_zip_names(zip_path: Path) -> set[str]:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            bad_file = archive.testzip()
            if bad_file:
                raise SystemExit(f"Combined release ZIP contains a corrupt entry: {bad_file}")
            return {name.replace("\\", "/").rstrip("/") for name in archive.namelist()}
    except zipfile.BadZipFile as exc:
        raise SystemExit(f"Combined release ZIP is not a valid ZIP file: {zip_path}") from exc


def _verify_required_files(names: set[str]) -> None:
    missing = sorted(REQUIRED_FILES - names)
    if missing:
        raise SystemExit("Combined release ZIP is missing required files:\n" + "\n".join(f"- {item}" for item in missing))


def _verify_required_prefixes(names: set[str]) -> None:
    missing = [prefix for prefix in REQUIRED_PREFIXES if not any(name.startswith(prefix) for name in names)]
    if missing:
        raise SystemExit(
            "Combined release ZIP is missing required package directories:\n"
            + "\n".join(f"- {item}" for item in missing)
        )


def _verify_expected_sha256(zip_path: Path, expected_sha256: str) -> None:
    expected_hash = expected_sha256.strip().lower()
    if len(expected_hash) != 64 or any(char not in "0123456789abcdef" for char in expected_hash):
        raise SystemExit(f"Expected SHA256 hash is invalid: {expected_sha256}")

    actual_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise SystemExit(f"SHA256 mismatch for {zip_path.name}: expected {expected_hash}, got {actual_hash}")


def _smoke_combined_package(zip_path: Path, *, require: bool) -> None:
    if platform.system() != "Windows":
        if require:
            raise SystemExit("Combined release smoke test requires Windows.")
        print("Skipping combined release smoke test on non-Windows host.")
        return

    with tempfile.TemporaryDirectory(prefix="wlc_combined_smoke_") as temp_dir:
        extract_dir = Path(temp_dir)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        _smoke_cli(extract_dir)
        _smoke_web(extract_dir)


def _smoke_cli(extract_dir: Path) -> None:
    cli_exe = extract_dir / "gui" / "WlcRoleAclCollectorCLI.exe"
    if not cli_exe.exists():
        raise SystemExit(f"CLI executable was not found after extraction: {cli_exe}")

    completed = subprocess.run(
        [str(cli_exe), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode != 0:
        raise SystemExit(f"CLI smoke command failed with exit code {completed.returncode}:\n{output.strip()}")
    if "collect" not in output or "diagnose" not in output:
        raise SystemExit("CLI help output did not include expected commands: collect, diagnose")


def _smoke_web(extract_dir: Path) -> None:
    web_dir = extract_dir / "web"
    launcher = web_dir / "start_webapp.cmd"
    if not launcher.exists():
        raise SystemExit(f"Streamlit launcher was not found after extraction: {launcher}")

    completed = subprocess.run(
        ["cmd.exe", "/c", "start_webapp.cmd", "--smoke"],
        cwd=web_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode != 0:
        raise SystemExit(f"Streamlit smoke command failed with exit code {completed.returncode}:\n{output.strip()}")
    if "STREAMLIT_PORTABLE_OK" not in output:
        raise SystemExit("Streamlit smoke output did not include STREAMLIT_PORTABLE_OK.")


if __name__ == "__main__":
    raise SystemExit(main())
