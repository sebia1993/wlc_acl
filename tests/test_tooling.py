from pathlib import Path


def test_validate_script_runs_local_checks():
    script = Path(__file__).parents[1] / "tools" / "validate.ps1"

    text = script.read_text(encoding="utf-8")

    assert "python -m pytest -q" in text
    assert "python -m compileall -q src" in text
    assert "node --check" in text
    assert "Node.js was not found. Skipping JavaScript syntax check." in text


def test_release_zip_includes_user_guide():
    script = Path(__file__).parents[1] / "build_windows_gui_exe.ps1"

    text = script.read_text(encoding="utf-8")

    assert "docs\\USER_GUIDE_KO.md" in text
    assert "USER_GUIDE_KO.md" in text
