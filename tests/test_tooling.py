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

    assert "tools\\generate_doc_html.py" in text
    assert "docs\\USER_GUIDE_KO.md" in text
    assert "docs\\USER_GUIDE_KO.html" in text
    assert "docs\\DEVELOPER_GUIDE_KO.md" in text
    assert "docs\\DEVELOPER_GUIDE_KO.html" in text
    assert "USER_GUIDE_KO.md" in text
    assert "USER_GUIDE_KO.html" in text
    assert "DEVELOPER_GUIDE_KO.md" in text
    assert "DEVELOPER_GUIDE_KO.html" in text


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
    assert user_html == (repo_root / "docs" / "USER_GUIDE_KO.html").read_text(encoding="utf-8")
    assert developer_html == (repo_root / "docs" / "DEVELOPER_GUIDE_KO.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in user_html
    assert "<html lang=\"ko\">" in user_html
    assert "WLC Role ACL Collector 사용자 설명서" in user_html
    assert "<table>" in user_html
    assert "WLC Role ACL Collector 개발자 설명서" in developer_html
    assert "Generated from Markdown for browser viewing." in developer_html
