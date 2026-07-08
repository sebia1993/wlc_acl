"""Validate the Streamlit portable Windows ZIP.

The package is expected to contain an embeddable Python runtime, installed
Streamlit dependencies, the web app entrypoint, and the Role network template.
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
    "start_webapp.cmd",
    "webapp_settings.cmd",
    "README_WEBAPP_KO.txt",
    "python/python.exe",
    "app/app.py",
    "config/role_networks.example.xlsx",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Streamlit portable Windows release ZIP.")
    parser.add_argument("--zip", dest="zip_path", type=Path, help="release ZIP path")
    parser.add_argument("--dist", type=Path, default=Path("dist"), help="directory containing a web release ZIP")
    parser.add_argument("--sha256", type=Path, help="SHA256 sidecar file to verify")
    parser.add_argument("--smoke", action="store_true", help="run start_webapp.cmd --smoke on Windows")
    parser.add_argument(
        "--require-smoke",
        action="store_true",
        help="fail if --smoke is requested on a non-Windows host",
    )
    args = parser.parse_args(argv)

    zip_path = args.zip_path or _find_latest_web_zip(args.dist)
    if not zip_path.exists():
        raise SystemExit(f"Streamlit portable ZIP does not exist: {zip_path}")
    if zip_path.stat().st_size <= 0:
        raise SystemExit(f"Streamlit portable ZIP is empty: {zip_path}")

    names = _read_zip_names(zip_path)
    _verify_required_files(names)
    _verify_site_packages(names)

    if args.sha256:
        _verify_sha256(zip_path, args.sha256)

    if args.smoke:
        _smoke_webapp(zip_path, require=args.require_smoke)

    print(f"Verified Streamlit portable package: {zip_path}")
    return 0


def _find_latest_web_zip(dist_dir: Path) -> Path:
    candidates = sorted(dist_dir.glob("WlcRoleAclCollectorWeb*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit(f"No Streamlit portable ZIP was found in {dist_dir}")
    return candidates[0]


def _read_zip_names(zip_path: Path) -> set[str]:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            bad_file = archive.testzip()
            if bad_file:
                raise SystemExit(f"Streamlit portable ZIP contains a corrupt entry: {bad_file}")
            return {name.replace("\\", "/").rstrip("/") for name in archive.namelist()}
    except zipfile.BadZipFile as exc:
        raise SystemExit(f"Streamlit portable ZIP is not a valid ZIP file: {zip_path}") from exc


def _verify_required_files(names: set[str]) -> None:
    missing = sorted(REQUIRED_FILES - names)
    if missing:
        raise SystemExit("Streamlit portable ZIP is missing required files:\n" + "\n".join(f"- {item}" for item in missing))


def _verify_site_packages(names: set[str]) -> None:
    required_prefixes = (
        "python/Lib/site-packages/streamlit/",
        "python/Lib/site-packages/wlc_role_acl_collector/",
    )
    missing = [prefix for prefix in required_prefixes if not _contains_prefix(names, prefix)]
    if missing:
        raise SystemExit(
            "Streamlit portable ZIP is missing installed Python packages:\n"
            + "\n".join(f"- {item}" for item in missing)
        )


def _contains_prefix(names: set[str], prefix: str) -> bool:
    return any(name.startswith(prefix) for name in names)


def _verify_sha256(zip_path: Path, checksum_path: Path) -> None:
    if not checksum_path.exists():
        raise SystemExit(f"SHA256 file does not exist: {checksum_path}")

    parts = checksum_path.read_text(encoding="ascii").strip().split()
    if len(parts) < 2:
        raise SystemExit(f"SHA256 file must contain '<hash>  <filename>': {checksum_path}")

    expected_hash = parts[0].lower()
    expected_name = parts[-1]
    if len(expected_hash) != 64 or any(char not in "0123456789abcdef" for char in expected_hash):
        raise SystemExit(f"SHA256 hash is invalid: {expected_hash}")
    if expected_name != zip_path.name:
        raise SystemExit(f"SHA256 filename mismatch: expected {zip_path.name}, got {expected_name}")

    actual_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        raise SystemExit(f"SHA256 mismatch for {zip_path.name}: expected {expected_hash}, got {actual_hash}")


def _smoke_webapp(zip_path: Path, *, require: bool) -> None:
    if platform.system() != "Windows":
        if require:
            raise SystemExit("Streamlit portable smoke test requires Windows.")
        print("Skipping Streamlit portable smoke test on non-Windows host.")
        return

    with tempfile.TemporaryDirectory(prefix="wlc_streamlit_smoke_") as temp_dir:
        extract_dir = Path(temp_dir)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        launcher = extract_dir / "start_webapp.cmd"
        if not launcher.exists():
            raise SystemExit(f"Streamlit launcher was not found after extraction: {launcher}")

        completed = subprocess.run(
            ["cmd.exe", "/c", "start_webapp.cmd", "--smoke"],
            cwd=extract_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=False,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode != 0:
            raise SystemExit(
                f"Streamlit portable smoke command failed with exit code {completed.returncode}:\n{output.strip()}"
            )
        if "STREAMLIT_PORTABLE_OK" not in output:
            raise SystemExit("Streamlit portable smoke output did not include STREAMLIT_PORTABLE_OK.")


if __name__ == "__main__":
    raise SystemExit(main())
