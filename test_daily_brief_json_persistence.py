import json

from test_telegram_template_modularization import _report_minimal


def test_persist_pipeline_raw_report_writes_daily_json(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SKIP_BIGQUERY", "1")

    import main

    report = _report_minimal()
    main._persist_pipeline_raw_report(report)

    daily_path = tmp_path / ".qsilicon" / "daily_brief_reports" / f"{report.crypto.report_title_date}.json"
    assert daily_path.is_file()
    payload = json.loads(daily_path.read_text(encoding="utf-8"))
    assert payload["crypto"]["report_title_date"] == report.crypto.report_title_date
    assert list((tmp_path / "logs").glob("run_*/raw_data.json"))
