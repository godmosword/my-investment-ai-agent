"""tracker 的 JSONL 後端契約測試（GCP 移除前置）。

BigQuery 是 tracker 唯一沒有 fallback 的儲存後端。這裡先固定 jsonl 後端的
write→read 往返語意，讓後續刪除 BigQuery 分支時有紅綠可依。

命名與斷言刻意對齊既有 test_tracker.py，不修改該檔任何斷言。
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest

import tracker

# 單一取值：對齊 tracker.py 既有的 date.today() 慣例，避免測試散落多次呼叫。
TODAY = date.today()

SAMPLE_REPORT = """\
[QSREC_START]
[
  {"asset": "BTC", "direction": "LONG", "current_price": 95000, "entry": 94500,
   "target": 100000, "stop": 91000, "confidence": 4, "category": "CRYPTO",
   "narrative": "ETF 持續流入"},
  {"asset": "SOL", "direction": "SHORT", "current_price": 145.5, "entry": 146,
   "target": 130, "stop": 152, "confidence": 3, "category": "CRYPTO",
   "narrative": "TVL 下滑"}
]
[QSREC_END]
"""


@pytest.fixture(autouse=True)
def _jsonl_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("QSILICON_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("TRACKER_STORE_BACKEND", "jsonl")
    monkeypatch.delenv("SKIP_BIGQUERY", raising=False)
    yield


def test_backend_defaults_to_jsonl_when_unset(monkeypatch):
    monkeypatch.delenv("TRACKER_STORE_BACKEND", raising=False)
    assert tracker._recs_store_backend() == "jsonl"


def test_save_recommendations_persists_without_bigquery():
    saved = tracker.save_recommendations(SAMPLE_REPORT, report_date="2026-01-05")
    assert saved == 2
    rows = tracker._load_recs()
    assert {r["asset"] for r in rows} == {"BTC", "SOL"}
    assert all(r["status"] == "OPEN" for r in rows)


def test_save_recommendations_never_touches_bigquery_client():
    with patch.object(tracker, "_get_bq_client", side_effect=AssertionError("BQ used")):
        assert tracker.save_recommendations(SAMPLE_REPORT, report_date="2026-01-05") == 2


def test_rerun_same_day_replaces_open_rows_not_duplicates():
    """同日重跑刪除既有 OPEN，對齊 BigQuery 分支的 DELETE ... WHERE status='OPEN'。"""
    tracker.save_recommendations(SAMPLE_REPORT, report_date="2026-01-05")
    tracker.save_recommendations(SAMPLE_REPORT, report_date="2026-01-05")
    rows = tracker._load_recs()
    assert len(rows) == 2


def test_rerun_preserves_closed_rows_from_same_day():
    tracker.save_recommendations(SAMPLE_REPORT, report_date="2026-01-05")
    rows = tracker._load_recs()
    rows[0]["status"] = "HIT_TARGET"
    tracker._replace_recs(rows)

    tracker.save_recommendations(SAMPLE_REPORT, report_date="2026-01-05")
    statuses = sorted(r["status"] for r in tracker._load_recs())
    assert "HIT_TARGET" in statuses
    assert statuses.count("OPEN") == 2


def test_report_date_reads_back_as_date_object():
    """下游 (today - rep_date).days 依賴 date 物件，JSONL 存字串必須還原。"""
    tracker.save_recommendations(SAMPLE_REPORT, report_date="2026-01-05")
    assert tracker._load_recs()[0]["report_date"] == date(2026, 1, 5)


def test_check_and_update_positions_closes_on_target():
    tracker.save_recommendations(SAMPLE_REPORT, report_date=TODAY.isoformat())
    with patch.object(tracker, "_current_prices_for_assets", return_value={"BTC": 101000, "SOL": 148}):
        closed = tracker.check_and_update_positions()
    assert [c["asset"] for c in closed] == ["BTC"]
    assert closed[0]["status"] == "HIT_TARGET"

    stored = {r["asset"]: r for r in tracker._load_recs()}
    assert stored["BTC"]["status"] == "HIT_TARGET"
    assert stored["BTC"]["exit_price"] == 101000
    assert stored["BTC"]["pnl_pct"] == pytest.approx(6.88, abs=0.01)
    assert stored["SOL"]["status"] == "OPEN"


def test_check_and_update_positions_expires_at_exactly_30_days():
    """BigQuery 分支的視窗是 report_date >= today-30，而 EXPIRED 條件是 days_held >= 30，
    因此只有正好 30 天的列會被判 EXPIRED。此處保留該既有邊界，不改行為。"""
    old = (TODAY - timedelta(days=30)).isoformat()
    tracker.save_recommendations(SAMPLE_REPORT, report_date=old)
    with patch.object(tracker, "_current_prices_for_assets", return_value={"BTC": 95000, "SOL": 146}):
        closed = tracker.check_and_update_positions()
    assert {c["status"] for c in closed} == {"EXPIRED"}


def test_check_and_update_positions_ignores_rows_older_than_30_days_window():
    """BigQuery 分支只掃最近 30 天；超過視窗的 OPEN 不應被重新評估。"""
    tracker.save_recommendations(SAMPLE_REPORT, report_date="2020-01-01")
    with patch.object(tracker, "_current_prices_for_assets", return_value={"BTC": 101000}):
        assert tracker.check_and_update_positions() == []


def test_get_recent_lessons_aggregates_hit_stop_rows():
    tracker.save_recommendations(SAMPLE_REPORT, report_date=TODAY.isoformat())
    rows = tracker._load_recs()
    for row in rows:
        if row["asset"] == "SOL":
            row.update(status="HIT_STOP", pnl_pct=-4.1, exit_date=TODAY.isoformat())
    tracker._replace_recs(rows)

    out = tracker.get_recent_lessons(days=3)
    assert out
    assert "SOL" in out


def test_get_recent_lessons_returns_empty_when_no_stops():
    tracker.save_recommendations(SAMPLE_REPORT, report_date=TODAY.isoformat())
    assert tracker.get_recent_lessons(days=3) == ""


def test_load_previous_recs_block_renders_last_prior_day():
    yesterday = (TODAY - timedelta(days=1)).isoformat()
    tracker.save_recommendations(SAMPLE_REPORT, report_date=yesterday)
    with patch.object(tracker, "_current_prices_for_assets", return_value={"BTC": 96000, "SOL": 140}):
        block = tracker.load_previous_recs_block()
    assert "【上期建議追蹤】" in block
    assert yesterday in block
    assert "$BTC" in block


def test_load_previous_recs_block_excludes_today():
    tracker.save_recommendations(SAMPLE_REPORT, report_date=TODAY.isoformat())
    with patch.object(tracker, "_current_prices_for_assets", return_value={"BTC": 96000}):
        assert tracker.load_previous_recs_block() == ""


def test_load_previous_recs_block_empty_store_returns_empty_string():
    assert tracker.load_previous_recs_block() == ""


def test_generate_performance_summary_counts_closed_rows():
    tracker.save_recommendations(SAMPLE_REPORT, report_date=TODAY.isoformat())
    rows = tracker._load_recs()
    rows[0].update(status="HIT_TARGET", pnl_pct=5.8, days_held=3)
    rows[1].update(status="HIT_STOP", pnl_pct=-4.1, days_held=2)
    tracker._replace_recs(rows)

    summary = tracker.generate_performance_summary(days=30)
    assert summary
    assert "50" in summary  # 1 勝 1 敗 = 50% 勝率


def test_generate_performance_summary_ignores_open_rows():
    tracker.save_recommendations(SAMPLE_REPORT, report_date=TODAY.isoformat())
    assert tracker.generate_performance_summary(days=30) == ""
