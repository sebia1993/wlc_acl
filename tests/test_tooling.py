import subprocess
import sys
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

    text = script.read_text(encoding="utf-8")

    assert "WlcRoleAclCollectorGUI" in text
    assert "WlcRoleAclCollectorCLI" in text
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
    assert "gh release" not in pr_workflow

    assert "push:" in release_workflow
    assert "pull_request:" not in release_workflow
    assert "contents: write" in release_workflow
    assert "Korea Standard Time" in release_workflow
    assert "yyyy.MM.dd-HHmmss" in release_workflow
    assert validation_command in release_workflow
    assert build_command in release_workflow
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
