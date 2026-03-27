"""Smoke：HTTP 重試、Telegram 推播路徑、BigQuery 寫入錯誤日誌。"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import main
import tools
import tools_cache_http


@pytest.mark.smoke
def test_get_with_retry_503_then_ok():
    bad = MagicMock()
    bad.status_code = 503
    good = MagicMock()
    good.status_code = 200
    good.raise_for_status = MagicMock()

    tools._get_http_session()  # ensure singleton is initialized before patching
    with patch.object(tools_cache_http._HTTP_SESSION, "get", side_effect=[bad, good]) as mock_get:
        with patch("tools.time.sleep"):
            resp = tools._get_with_retry("http://example.test", params={}, retries=2)
    assert resp.status_code == 200
    assert mock_get.call_count == 2


@pytest.mark.smoke
def test_send_telegram_report_mock_bot():
    with patch("main.os.path.exists", return_value=False):
        mock_bot = MagicMock()
        with patch("telegram_sender.telebot.TeleBot", return_value=mock_bot):
            main._send_telegram_report("<b>hi</b>", "dummy-token", "12345")
    mock_bot.send_message.assert_called()


@pytest.mark.smoke
def test_extract_and_save_metrics_logs_insert_errors(caplog):
    caplog.set_level(logging.ERROR)
    schema_names = [
        "timestamp",
        "dxy",
        "etf_flow_millions",
        "avg_risk_score",
        "gpu_b200_price",
        "grok_summary",
        "gpt_summary",
        "mvrv_z_score",
        "news_titles",
        "sentiment_score",
        "sopr",
        "exchange_netflow",
        "regime_score",
    ]
    fake_table = MagicMock()
    fake_table.schema = [SimpleNamespace(name=n) for n in schema_names]

    fake_client = MagicMock()
    fake_client.get_table.return_value = fake_table
    fake_client.insert_rows_json.return_value = [{"index": 0, "errors": [{"message": "mock"}]}]

    report = (
        "ICE DXY → 99.5\n"
        "ETF 資金流入 1.5 億\n"
        "IMPACT：中性\n"
        "MVRV Z-Score: 1.2\n"
    )

    def _schema_field(name: str, _ftype: str) -> SimpleNamespace:
        return SimpleNamespace(name=name)

    with (
        patch("bigquery_writer.bigquery.Client", return_value=fake_client),
        patch("bigquery_writer.bigquery.SchemaField", side_effect=_schema_field),
        patch("bigquery_writer.bigquery.Table", return_value=MagicMock()),
    ):
        main.extract_and_save_metrics(report, project_id="test-project")

    assert any("BigQuery insert errors" in r.getMessage() for r in caplog.records)
