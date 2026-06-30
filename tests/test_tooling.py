import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path


def test_validate_script_runs_local_checks():
    script = Path(__file__).parents[1] / "tools" / "validate.ps1"

    text = script.read_text(encoding="utf-8")

    assert "python -m pytest -q" in text
    assert "python -m compileall -q src" in text
    assert "node --check" in text
    assert "Node.js was not found. Skipping JavaScript syntax check." in text


def test_release_zip_includes_guides():
    script = Path(__file__).parents[1] / "build_windows_gui_exe.ps1"
    spec = Path(__file__).parents[1] / "WlcRoleAclCollectorGUI.spec"

    text = script.read_text(encoding="utf-8")
    spec_text = spec.read_text(encoding="utf-8")

    assert "WlcRoleAclCollectorGUI" in text
    assert "WlcRoleAclCollectorCLI" in text
    assert "--collect-data customtkinter" in text
    assert "collect_data_files('customtkinter')" in spec_text
    assert ".\\cli_launcher.py" in text
    assert "tools\\generate_doc_html.py" in text
    assert "docs\\USER_GUIDE_KO.md" in text
    assert "docs\\USER_GUIDE_KO.html" in text
    assert "docs\\DEVELOPER_GUIDE_KO.md" in text
    assert "docs\\DEVELOPER_GUIDE_KO.html" in text
    assert "docs\\ERROR_CODES_KO.md" in text
    assert "docs\\ERROR_CODES_KO.html" in text
    assert "docs\\DIAGNOSTIC_MODE_KO.md" in text
    assert "docs\\DIAGNOSTIC_MODE_KO.html" in text
    assert "docs\\SECURITY_MODEL_KO.md" in text
    assert "docs\\SECURITY_MODEL_KO.html" in text
    assert "config\\role_networks.example.xlsx" in text
    assert "config\\mock_scenarios" in text
    assert "USER_GUIDE_KO.md" in text
    assert "USER_GUIDE_KO.html" in text
    assert "DEVELOPER_GUIDE_KO.md" in text
    assert "DEVELOPER_GUIDE_KO.html" in text
    assert "ERROR_CODES_KO.md" in text
    assert "DIAGNOSTIC_MODE_KO.md" in text
    assert "SECURITY_MODEL_KO.md" in text


def test_verify_release_package_checks_zip_contents_and_checksum(tmp_path):
    repo_root = Path(__file__).parents[1]
    script = repo_root / "tools" / "verify_release_package.py"
    zip_path = tmp_path / "WlcRoleAclCollectorGUI_v0.1.0.zip"
    required_entries = [
        "WlcRoleAclCollectorGUI.exe",
        "WlcRoleAclCollectorCLI.exe",
        "USER_GUIDE_KO.md",
        "USER_GUIDE_KO.html",
        "DEVELOPER_GUIDE_KO.md",
        "DEVELOPER_GUIDE_KO.html",
        "ERROR_CODES_KO.md",
        "ERROR_CODES_KO.html",
        "DIAGNOSTIC_MODE_KO.md",
        "DIAGNOSTIC_MODE_KO.html",
        "SECURITY_MODEL_KO.md",
        "SECURITY_MODEL_KO.html",
        "config/role_networks.example.xlsx",
        "config/mock_scenarios/auth_failed.json",
        "config/mock_scenarios/missing_config.json",
        "config/mock_scenarios/permission_denied.json",
        "config/mock_scenarios/success_minimal.json",
    ]
    with zipfile.ZipFile(zip_path, "w") as archive:
        for entry in required_entries:
            archive.writestr(entry, "fixture")

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    checksum_path = tmp_path / f"{zip_path.name}.sha256"
    checksum_path.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii")

    subprocess.run(
        [sys.executable, str(script), "--zip", str(zip_path), "--sha256", str(checksum_path)],
        check=True,
        cwd=repo_root,
    )


def test_generate_doc_html_outputs_browser_files(tmp_path):
    repo_root = Path(__file__).parents[1]
    script = repo_root / "tools" / "generate_doc_html.py"

    subprocess.run(
        [sys.executable, str(script), "--source-dir", str(repo_root / "docs"), "--output-dir", str(tmp_path)],
        check=True,
        cwd=repo_root,
    )

    user_html = (tmp_path / "USER_GUIDE_KO.html").read_text(encoding="utf-8")
    developer_html = (tmp_path / "DEVELOPER_GUIDE_KO.html").read_text(encoding="utf-8")
    error_codes_html = (tmp_path / "ERROR_CODES_KO.html").read_text(encoding="utf-8")
    diagnostic_html = (tmp_path / "DIAGNOSTIC_MODE_KO.html").read_text(encoding="utf-8")
    security_html = (tmp_path / "SECURITY_MODEL_KO.html").read_text(encoding="utf-8")
    assert user_html == (repo_root / "docs" / "USER_GUIDE_KO.html").read_text(encoding="utf-8")
    assert developer_html == (repo_root / "docs" / "DEVELOPER_GUIDE_KO.html").read_text(encoding="utf-8")
    assert error_codes_html == (repo_root / "docs" / "ERROR_CODES_KO.html").read_text(encoding="utf-8")
    assert diagnostic_html == (repo_root / "docs" / "DIAGNOSTIC_MODE_KO.html").read_text(encoding="utf-8")
    assert security_html == (repo_root / "docs" / "SECURITY_MODEL_KO.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in user_html
    assert "<html lang=\"ko\">" in user_html
    assert "WLC Role ACL Collector 사용자 설명서" in user_html
    assert "<table>" in user_html
    assert "WLC Role ACL Collector 개발자 설명서" in developer_html
    assert "WLC Role ACL Collector 오류 코드" in error_codes_html
    assert "WLC Role ACL Collector 진단 모드" in diagnostic_html
    assert "WLC Role ACL Collector 보안 모델" in security_html
    assert "Generated from Markdown for browser viewing." in developer_html


def test_github_actions_split_pr_validation_and_release():
    repo_root = Path(__file__).parents[1]
    pr_workflow = (repo_root / ".github" / "workflows" / "pr-validation.yml").read_text(encoding="utf-8")
    release_workflow = (repo_root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

    validation_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\validate.ps1"
    build_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_windows_gui_exe.ps1"

    assert "pull_request:" in pr_workflow
    assert "branches: [main]" in pr_workflow
    assert validation_command in pr_workflow
    assert build_command in pr_workflow
    assert "python .\\tools\\verify_release_package.py --dist .\\dist --smoke-cli" in pr_workflow
    assert "gh release" not in pr_workflow

    assert "push:" in release_workflow
    assert "pull_request:" not in release_workflow
    assert "contents: write" in release_workflow
    assert "Korea Standard Time" in release_workflow
    assert "yyyy.MM.dd-HHmmss" in release_workflow
    assert validation_command in release_workflow
    assert build_command in release_workflow
    assert "python .\\tools\\verify_release_package.py --dist .\\dist --smoke-cli" in release_workflow
    assert "--sha256 \"${{ steps.assets.outputs.checksum_path }}\"" in release_workflow
    assert "Get-FileHash -Algorithm SHA256" in release_workflow
    assert "git tag" in release_workflow
    assert 'git push origin "refs/tags/' in release_workflow
    assert "gh release create" in release_workflow
    assert "--verify-tag" in release_workflow
    assert "--draft" in release_workflow
    assert "gh release edit" in release_workflow
    assert "--draft=false" in release_workflow
    assert "--cleanup-tag" in release_workflow
    assert 'git push origin ":refs/tags/$tag"' in release_workflow
    assert "이 릴리즈는 main 브랜치에 반영된 변경 사항을 기준으로" in release_workflow
    assert "## 변경내용" in release_workflow
    assert "$changeSummaryText" in release_workflow
    assert "### 변경 영역" in release_workflow
    assert "$areaText" in release_workflow
    assert "## 검증" in release_workflow
    assert "- 기준 커밋 SHA: $sha" in release_workflow
    assert "- 브랜치명: $branch" in release_workflow
    assert "- 실행한 검증 명령: powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\validate.ps1" in release_workflow
    assert "- 실행한 빌드 명령: powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_windows_gui_exe.ps1" in release_workflow
    assert "## 첨부파일" in release_workflow
    assert "- 산출물 파일명: $assetName" in release_workflow
    assert "- SHA256 파일명: $assetName.sha256" in release_workflow
    assert "- SHA256 체크섬: $checksum" in release_workflow
    assert "<details>" in release_workflow
    assert "<summary>세부 커밋 및 변경 파일</summary>" in release_workflow
    assert "### 원본 커밋 목록" in release_workflow
    assert "### 변경 파일" in release_workflow
    assert "git diff --name-only" in release_workflow
    assert "배포 자동화: GitHub Actions 검증, 빌드, Release 생성 흐름" in release_workflow
    assert "GUI: 화면 구성, 진행 상태, 사용자 알림 또는 수집 동작" in release_workflow
    assert "Release metadata" not in release_workflow
    assert "Changed commits" not in release_workflow
    assert "## 주요 변경 사항" not in release_workflow


def test_runtime_dependencies_include_customtkinter():
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert '"customtkinter>=5.2"' in pyproject
