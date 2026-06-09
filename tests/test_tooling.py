from pathlib import Path


def test_validate_script_runs_local_checks():
    script = Path(__file__).parents[1] / "tools" / "validate.ps1"

    text = script.read_text(encoding="utf-8")

    assert "python -m pytest -q" in text
    assert "python -m compileall -q src" in text
    assert "node --check" in text
    assert "Node.js was not found. Skipping JavaScript syntax check." in text
