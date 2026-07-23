import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path


def test_validate_script_runs_local_checks():
    script = Path(__file__).parents[1] / "tools" / "validate.ps1"

    text = script.read_text(encoding="utf-8")

    assert "python -m pytest -q" in text
    assert "python -m compileall -q app.py src tests tools" in text
    assert "node --check" in text
    assert "_role_image_export_script" in text
    assert "Path(sys.argv[1]).write_text" in text
    assert "Set-Content -LiteralPath $tempAccessScript" not in text
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
    assert "collect_data_files('wlc_role_acl_collector')" in spec_text
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


def test_streamlit_portable_build_contract():
    repo_root = Path(__file__).parents[1]
    build_script = (repo_root / "build_windows_streamlit_portable.ps1").read_text(encoding="utf-8")
    verifier = (repo_root / "tools" / "verify_streamlit_portable_package.py").read_text(encoding="utf-8")
    launcher = (repo_root / "packaging" / "streamlit_portable" / "start_webapp.cmd").read_text(encoding="utf-8")
    settings = (repo_root / "packaging" / "streamlit_portable" / "webapp_settings.cmd").read_text(encoding="utf-8")
    guide = (repo_root / "packaging" / "streamlit_portable" / "README_WEBAPP_KO.txt").read_text(
        encoding="utf-8"
    )

    assert "python-$EmbeddedPythonVersion-embed-amd64.zip" in build_script
    assert "https://www.python.org/ftp/python/$EmbeddedPythonVersion" in build_script
    assert '"--target", $sitePackages, ".[web]"' in build_script
    assert "WlcRoleAclCollectorWeb_v${version}.zip" in build_script
    assert "start_webapp.cmd --smoke" in build_script
    assert "python.exe" in build_script
    assert "compileall" in build_script
    assert "Portable module precompile failed." in build_script
    assert "app\\app.py" in build_script
    assert "config\\role_networks.example.xlsx" in build_script
    assert "Lib\\site-packages" in build_script
    assert "import site" in build_script

    assert "start_webapp.cmd" in verifier
    assert "webapp_settings.cmd" in verifier
    assert "python/python.exe" in verifier
    assert "python/Lib/site-packages/streamlit/" in verifier
    assert "python/Lib/site-packages/wlc_role_acl_collector/" in verifier
    assert "STREAMLIT_PORTABLE_OK" in verifier
    assert "Get-FileHash" not in verifier

    assert "--server.address" in launcher
    assert "--server.port" in launcher
    assert "--server.headless true" in launcher
    assert "--server.fileWatcherType none" in launcher
    assert "--server.runOnSave false" in launcher
    assert "--global.developmentMode false" in launcher
    assert "--client.toolbarMode minimal" in launcher
    assert "--browser.gatherUsageStats false" in launcher
    assert "--smoke" in launcher
    assert "STREAMLIT_PORTABLE_OK" in launcher
    assert "python\\python.exe" in launcher
    assert "WLC_WEB_ADDRESS=0.0.0.0" in settings
    assert "WLC_WEB_PORT=8763" in settings
    assert "Python을 별도로 설치하지 않고" in guide
    assert "첫 실행" in guide
    assert "start_webapp.cmd" in guide


def test_combined_release_build_contract():
    repo_root = Path(__file__).parents[1]
    build_script = (repo_root / "build_windows_combined_release.ps1").read_text(encoding="utf-8")
    verifier = (repo_root / "tools" / "verify_combined_release_package.py").read_text(encoding="utf-8")
    readme = (repo_root / "packaging" / "combined_release" / "README_START_HERE_KO.txt").read_text(
        encoding="utf-8"
    )

    assert "WlcRoleAclCollectorGUI_*.zip" in build_script
    assert "WlcRoleAclCollectorWeb_*.zip" in build_script
    assert "WlcRoleAclCollectorWindows_v${version}.zip" in build_script
    assert "README_START_HERE_KO.txt" in build_script
    assert '"gui"' in build_script
    assert '"web"' in build_script

    assert "gui/WlcRoleAclCollectorGUI.exe" in verifier
    assert "gui/WlcRoleAclCollectorCLI.exe" in verifier
    assert "web/start_webapp.cmd" in verifier
    assert "web/python/python.exe" in verifier
    assert "web/python/Lib/site-packages/streamlit/" in verifier
    assert "web/python/Lib/site-packages/wlc_role_acl_collector/" in verifier
    assert "--expected-sha256" in verifier
    assert "STREAMLIT_PORTABLE_OK" in verifier
    assert "Source code" in readme
    assert "gui\\WlcRoleAclCollectorGUI.exe" in readme
    assert "web\\start_webapp.cmd" in readme


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


def test_verify_streamlit_portable_package_checks_zip_contents_and_checksum(tmp_path):
    repo_root = Path(__file__).parents[1]
    script = repo_root / "tools" / "verify_streamlit_portable_package.py"
    zip_path = tmp_path / "WlcRoleAclCollectorWeb_v0.1.0.zip"
    required_entries = [
        "start_webapp.cmd",
        "webapp_settings.cmd",
        "README_WEBAPP_KO.txt",
        "python/python.exe",
        "python/Lib/site-packages/streamlit/__init__.py",
        "python/Lib/site-packages/wlc_role_acl_collector/__init__.py",
        "app/app.py",
        "config/role_networks.example.xlsx",
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


def test_verify_combined_release_package_checks_zip_contents_and_checksum(tmp_path):
    repo_root = Path(__file__).parents[1]
    script = repo_root / "tools" / "verify_combined_release_package.py"
    zip_path = tmp_path / "WlcRoleAclCollectorWindows_v0.1.0.zip"
    required_entries = [
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
        "web/python/Lib/site-packages/streamlit/__init__.py",
        "web/python/Lib/site-packages/wlc_role_acl_collector/__init__.py",
        "web/app/app.py",
        "web/config/role_networks.example.xlsx",
    ]
    with zipfile.ZipFile(zip_path, "w") as archive:
        for entry in required_entries:
            archive.writestr(entry, "fixture")

    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()

    subprocess.run(
        [sys.executable, str(script), "--zip", str(zip_path), "--expected-sha256", digest],
        check=True,
        cwd=repo_root,
    )


def test_release_documentation_describes_current_package_contract():
    repo_root = Path(__file__).parents[1]
    app = (repo_root / "app.py").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    release_notes = (repo_root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    agents = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    requirements = (repo_root / "requirements.txt").read_text(encoding="utf-8")

    for text in (readme, release_notes):
        assert "wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip" in text
        assert "WlcRoleAclCollectorGUI.exe" in text
        assert "WlcRoleAclCollectorCLI.exe" in text
        assert "start_webapp.cmd" in text
        assert "webapp_settings.cmd" in text
        assert "README_START_HERE_KO.txt" in text
        assert "Source code (zip)" in text
        assert "config/mock_scenarios" in text or "config\\mock_scenarios" in text
        assert "wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_windows.zip.sha256" not in text
        assert "wlc-role-acl-collector_vYYYY.MM.DD-HHMMSS_streamlit_windows_portable.zip" not in text

    assert "python .\\tools\\verify_release_package.py --dist .\\dist --smoke-cli" in readme
    assert "python .\\tools\\verify_streamlit_portable_package.py --dist .\\dist --smoke" in readme
    assert "python .\\tools\\verify_combined_release_package.py --dist .\\dist --smoke" in readme
    assert "streamlit run app.py --server.address 0.0.0.0 --server.port 8763" in readme
    assert "http://공용PC_IP:8763" in readme
    assert "Windows 방화벽" in readme
    assert "절전모드" in readme
    assert "Windows PC에 Python을 별도로 설치하지 않습니다" in readme
    assert "WlcRoleAclCollectorWindows_v0.1.0.zip" in readme
    assert "streamlit run app.py --server.address 0.0.0.0 --server.port 8763" in release_notes
    assert "python .\\tools\\verify_streamlit_portable_package.py --dist .\\dist --smoke" in release_notes
    assert "python .\\tools\\verify_combined_release_package.py --dist .\\dist --smoke" in release_notes
    assert "-e .[web]" in requirements
    assert "st.file_uploader" in app
    assert "st.download_button" in app
    assert "macOS" in readme and "Windows EXE" in readme
    assert "통합 ZIP 하나" in changelog
    assert "Streamlit 웹앱 자체 사용자 로그인/권한 관리" in changelog
    assert "코드서명, installer, MSIX, SmartScreen" in changelog
    assert "README.md`, `RELEASE_NOTES.md`, and `CHANGELOG.md`" in agents
    assert "beginner-friendly step-by-step instructions" in agents
    assert "GitHub Actions Windows runner" in agents


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
    web_build_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_windows_streamlit_portable.ps1"
    web_verify_command = "python .\\tools\\verify_streamlit_portable_package.py --dist .\\dist --smoke"
    combined_build_command = "powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_windows_combined_release.ps1"
    combined_verify_command = "python .\\tools\\verify_combined_release_package.py --dist .\\dist --smoke"

    assert "pull_request:" in pr_workflow
    assert "branches: [main]" in pr_workflow
    assert validation_command in pr_workflow
    assert build_command in pr_workflow
    assert "python .\\tools\\verify_release_package.py --dist .\\dist --smoke-cli" in pr_workflow
    assert web_build_command in pr_workflow
    assert web_verify_command in pr_workflow
    assert combined_build_command in pr_workflow
    assert combined_verify_command in pr_workflow
    assert "gh release" not in pr_workflow

    assert "push:" in release_workflow
    assert "pull_request:" not in release_workflow
    assert "contents: write" in release_workflow
    assert "Korea Standard Time" in release_workflow
    assert "yyyy.MM.dd-HHmmss" in release_workflow
    assert validation_command in release_workflow
    assert build_command in release_workflow
    assert web_build_command in release_workflow
    assert combined_build_command in release_workflow
    assert "python .\\tools\\verify_release_package.py --dist .\\dist --smoke-cli" in release_workflow
    assert web_verify_command in release_workflow
    assert combined_verify_command in release_workflow
    assert "WlcRoleAclCollectorWindows_*.zip" in release_workflow
    assert "web_asset_name" not in release_workflow
    assert "streamlit_windows_portable.zip" not in release_workflow
    assert "checksum_path" not in release_workflow
    assert "web_checksum_path" not in release_workflow
    assert "web_asset_path" not in release_workflow
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
    assert "- 실행한 웹앱 빌드 명령: powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_windows_streamlit_portable.ps1" in release_workflow
    assert "- 실행한 통합 ZIP 빌드 명령: powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_windows_combined_release.ps1" in release_workflow
    assert "- 실행한 웹앱 ZIP 검증 명령: python .\\tools\\verify_streamlit_portable_package.py --dist .\\dist --smoke" in release_workflow
    assert "- 실행한 통합 ZIP 검증 명령: python .\\tools\\verify_combined_release_package.py --dist .\\dist --smoke" in release_workflow
    assert "## 첨부파일" in release_workflow
    assert "- 다운로드할 파일: $assetName" in release_workflow
    assert "- SHA256 체크섬: $checksum" in release_workflow
    assert "Source code (zip)" in release_workflow
    assert "start_webapp.cmd" in release_workflow
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
    repo_root = Path(__file__).parents[1]
    pyproject = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    renderer = repo_root / "src" / "wlc_role_acl_collector" / "static" / "html2canvas.min.js"
    license_file = repo_root / "src" / "wlc_role_acl_collector" / "static" / "LICENSE.html2canvas.txt"

    assert '"customtkinter>=5.2"' in pyproject
    assert '"streamlit>=1.36"' in pyproject
    assert "[tool.setuptools.package-data]" in pyproject
    assert '"static/*.js"' in pyproject
    assert '"static/*.txt"' in pyproject
    assert renderer.stat().st_size > 190_000
    assert "Permission is hereby granted, free of charge" in license_file.read_text(encoding="utf-8")
