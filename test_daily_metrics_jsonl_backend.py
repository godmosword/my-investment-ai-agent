"""daily_metrics 的 JSONL 後端契約測試（GCP 移除前置）。

extract_and_save_metrics / fetch_exclusion_context / _get_last_success_report_time_utc
組成日對日去重與「上次成功戰報時間」的記憶迴圈。BigQuery 拔除後這條迴圈必須
仍然成立，否則報告品質會靜默下降。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import bigquery_writer

REPORT_WITH_METRICS = """\
ICE DXY → 104.25
ETF 流出 3.5 億
平均風險分數：6.2/10
MVRV Z-Score：2.15
"""


@pytest.fixture(autouse=True)
def _jsonl_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("QSILICON_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("METRICS_STORE_BACKEND", "jsonl")
    monkeypatch.setattr(bigquery_writer, "SKIP_BIGQUERY", False)
    yield


def test_backend_defaults_to_jsonl_when_unset(monkeypatch):
    monkeypatch.delenv("METRICS_STORE_BACKEND", raising=False)
    assert bigquery_writer._metrics_store_backend() == "jsonl"


def test_extract_and_save_metrics_writes_row_without_bigquery():
    bigquery_writer.extract_and_save_metrics(REPORT_WITH_METRICS)
    rows = bigquery_writer._load_metrics()
    assert len(rows) == 1
    assert rows[0]["dxy"] == pytest.approx(104.25)
    assert rows[0]["timestamp"]


def test_extract_and_save_metrics_never_touches_bigquery_client():
    with patch.object(bigquery_writer.bigquery, "Client", side_effect=AssertionError("BQ used")):
        bigquery_writer.extract_and_save_metrics(REPORT_WITH_METRICS)
    assert len(bigquery_writer._load_metrics()) == 1


def test_empty_report_writes_nothing():
    """全部關鍵指標皆 None 時不寫入，對齊 BigQuery 分支的 non_null_count 守門。"""
    bigquery_writer.extract_and_save_metrics("沒有任何可萃取的數字")
    assert bigquery_writer._load_metrics() == []


def test_skip_flag_still_short_circuits(monkeypatch):
    monkeypatch.setattr(bigquery_writer, "SKIP_BIGQUERY", True)
    bigquery_writer.extract_and_save_metrics(REPORT_WITH_METRICS)
    assert bigquery_writer._load_metrics() == []


def test_metrics_appends_across_runs():
    bigquery_writer.extract_and_save_metrics(REPORT_WITH_METRICS)
    bigquery_writer.extract_and_save_metrics(REPORT_WITH_METRICS)
    assert len(bigquery_writer._load_metrics()) == 2


def test_last_success_time_reads_newest_row():
    older = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    newer = datetime.now(timezone.utc).isoformat()
    bigquery_writer._append_metrics([{"timestamp": older}, {"timestamp": newer}])
    out = bigquery_writer._get_last_success_report_time_utc()
    assert out
    assert out.endswith("UTC")


def test_last_success_time_empty_store_returns_none():
    assert bigquery_writer._get_last_success_report_time_utc() is None


def test_exclusion_context_uses_news_titles_within_36h():
    bigquery_writer._append_metrics([{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_titles": "BTC ETF 核准\nNVDA 財報",
    }])
    with patch.object(bigquery_writer, "_fetch_recent_recommended_assets", return_value=[]), \
         patch.object(bigquery_writer, "_fetch_recent_stopped_out_trades", return_value=None), \
         patch.object(bigquery_writer, "_fetch_last_rotation_gate_warnings", return_value=None):
        out = bigquery_writer.fetch_exclusion_context()
    assert out is not None
    assert "BTC ETF 核准" in out


def test_exclusion_context_ignores_rows_older_than_36h():
    stale = (datetime.now(timezone.utc) - timedelta(hours=40)).isoformat()
    bigquery_writer._append_metrics([{"timestamp": stale, "news_titles": "過期標題"}])
    with patch.object(bigquery_writer, "_fetch_recent_recommended_assets", return_value=[]), \
         patch.object(bigquery_writer, "_fetch_recent_stopped_out_trades", return_value=None), \
         patch.object(bigquery_writer, "_fetch_last_rotation_gate_warnings", return_value=None):
        assert bigquery_writer.fetch_exclusion_context() is None


def test_exclusion_context_falls_back_to_summaries():
    bigquery_writer._append_metrics([{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "grok_summary": "Grok 昨日摘要",
        "gpt_summary": "GPT 昨日摘要",
    }])
    with patch.object(bigquery_writer, "_fetch_recent_recommended_assets", return_value=[]), \
         patch.object(bigquery_writer, "_fetch_recent_stopped_out_trades", return_value=None), \
         patch.object(bigquery_writer, "_fetch_last_rotation_gate_warnings", return_value=None):
        out = bigquery_writer.fetch_exclusion_context()
    assert "Grok 昨日摘要" in out
    assert "GPT 昨日摘要" in out


def test_exclusion_context_appends_recent_assets():
    bigquery_writer._append_metrics([{
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_titles": "標題",
    }])
    with patch.object(bigquery_writer, "_fetch_recent_recommended_assets", return_value=["BTC", "SOL"]), \
         patch.object(bigquery_writer, "_fetch_recent_stopped_out_trades", return_value=None), \
         patch.object(bigquery_writer, "_fetch_last_rotation_gate_warnings", return_value=None):
        out = bigquery_writer.fetch_exclusion_context()
    assert "$BTC" in out
    assert "$SOL" in out


def test_metrics_row_is_json_serialisable_on_disk():
    bigquery_writer.extract_and_save_metrics(REPORT_WITH_METRICS)
    path = bigquery_writer._metrics_store_path()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1


# ── client=None 時改讀 tracker 本地建議存放 ────────────────────────────────

TRACKER_REPORT = """\
[QSREC_START]
[
  {"asset": "BTC", "direction": "LONG", "current_price": 95000, "entry": 94500,
   "target": 100000, "stop": 91000, "confidence": 4, "category": "CRYPTO",
   "narrative": "ETF 流入"},
  {"asset": "SOL", "direction": "SHORT", "current_price": 145.5, "entry": 146,
   "target": 130, "stop": 152, "confidence": 3, "category": "CRYPTO",
   "narrative": "TVL 下滑"}
]
[QSREC_END]
"""


@pytest.fixture
def _tracker_jsonl(monkeypatch):
    import tracker

    monkeypatch.setenv("TRACKER_STORE_BACKEND", "jsonl")
    today = datetime.now(timezone.utc).date()
    tracker.save_recommendations(TRACKER_REPORT, report_date=today.isoformat())
    return tracker


def test_recent_recommended_assets_reads_local_store(_tracker_jsonl):
    assert bigquery_writer._fetch_recent_recommended_assets(None, days=3) == ["BTC", "SOL"]


def test_recent_recommended_assets_excludes_rows_outside_window(_tracker_jsonl):
    _tracker_jsonl.save_recommendations(TRACKER_REPORT, report_date="2020-01-01")
    assert bigquery_writer._fetch_recent_recommended_assets(None, days=3) == ["BTC", "SOL"]


def test_recent_recommended_assets_empty_store_returns_empty_list():
    assert bigquery_writer._fetch_recent_recommended_assets(None, days=3) == []


def test_stopped_out_trades_reads_local_store(_tracker_jsonl):
    rows = _tracker_jsonl._load_recs()
    for row in rows:
        if row["asset"] == "SOL":
            row.update(status="HIT_STOP", pnl_pct=-4.1)
    _tracker_jsonl._replace_recs(rows)

    out = bigquery_writer._fetch_recent_stopped_out_trades(None, days=3)
    assert out is not None
    assert "$SOL" in out
    assert "-4.1%" in out


def test_stopped_out_trades_returns_none_without_stops(_tracker_jsonl):
    assert bigquery_writer._fetch_recent_stopped_out_trades(None, days=3) is None
