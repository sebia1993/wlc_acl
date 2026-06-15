import json
from pathlib import Path

from wlc_role_acl_collector.diagnostic_mode import run_diagnostic
from wlc_role_acl_collector.models import Controller, ControllerTarget


def test_run_diagnostic_offline_writes_safe_summary_without_raw_files(tmp_path):
    fixture_root = Path(__file__).parent / "fixtures"
    target = ControllerTarget(controller=Controller(name="sample_controller", host="192.0.2.10"))

    result = run_diagnostic(target, output_root=tmp_path, offline_raw_dir=fixture_root)

    payload = json.loads(result.report_paths["json"].read_text(encoding="utf-8"))
    report_text = result.report_paths["html"].read_text(encoding="utf-8")

    assert result.primary_code == "OK"
    assert payload["raw_output_saved"] is False
    assert not (result.run_dir / "raw").exists()
    assert "aa:bb:cc" not in report_text
    assert "corp-user-2" not in report_text
