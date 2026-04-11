"""Unit tests for tracker System A — JSON-based recommendation parsing."""

import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from tracker import (
    extract_recommendations_json,
    strip_tracker_blocks,
    canonical_asset_key,
    previous_rec_row_should_skip,
    previous_rec_pnl_implausible_for_display,
    _infer_previous_rec_category,
    _compute_trade_metrics,
    _current_prices_for_assets,
    _validate_rec,
    get_recent_lessons,
    generate_performance_summary,
)

# ── realistic snippet mirroring actual LLM-generated report ──
SAMPLE_REPORT = """\
<b>【資金流向與精準操作 (Crypto)】</b>

· <b>$BTC (LONG)</b>｜現價：$95,000｜信心水準：⭐️⭐️⭐️⭐️
· 進場：<code>$94500</code>｜目標：<code>$100000 (+5.8%)</code>｜停損：<code>$91000 (-3.7%)</code>
· 敘事邏輯：ETF 持續流入，鏈上鯨魚增持

[QSREC_START]
[
  {"asset": "BTC", "direction": "LONG", "current_price": 95000, "entry": 94500, "target": 100000, "stop": 91000, "confidence": 4, "category": "CRYPTO", "narrative": "ETF 持續流入，鏈上鯨魚增持"},
  {"asset": "SOL", "direction": "SHORT", "current_price": 145.5, "entry": 146, "target": 130, "stop": 152, "confidence": 3, "category": "CRYPTO", "narrative": "DeFi TVL 下滑，鏈上活躍度回落"}
]
[QSREC_END]

<b>【AI 產業鏈精準操作 (US Equities)】</b>

[QSREC_START]
[
  {"asset": "NVDA", "direction": "LONG", "current_price": 890, "entry": 885, "target": 950, "stop": 860, "confidence": 4, "category": "EQUITY", "narrative": "B200 需求強勁，雲端巨頭增加 CAPEX"}
]
[QSREC_END]
"""

REPORT_NO_JSON = """\
<b>【資金流向與精準操作 (Crypto)】</b>
· <b>$BTC (LONG)</b>｜現價：$95,000
"""


class TestCanonicalAssetKey(unittest.TestCase):
    def test_normalizes_pair_and_dollar(self):
        self.assertEqual(canonical_asset_key("$BTC-SOL"), "BTC/SOL")
        self.assertEqual(canonical_asset_key(" btc "), "BTC")


class TestPreviousRecRowShouldSkip(unittest.TestCase):
    def test_skips_long_placeholder_100_vs_low_price(self):
        self.assertTrue(previous_rec_row_should_skip("SKM", "LONG", 100.0, 29.92))

    def test_keeps_reasonable_long(self):
        self.assertFalse(previous_rec_row_should_skip("SKM", "LONG", 28.0, 29.92))

    def test_skips_entry_outside_sanity_range(self):
        self.assertTrue(previous_rec_row_should_skip("BTC", "LONG", 5000.0, 66000.0))


class TestPreviousRecPnlPlausibility(unittest.TestCase):
    def test_equity_huge_pnl_within_two_days_omitted(self):
        self.assertTrue(
            previous_rec_pnl_implausible_for_display(
                category="EQUITY",
                report_date=date.today(),
                pnl_pct=94.0,
            )
        )

    def test_equity_moderate_kept(self):
        self.assertFalse(
            previous_rec_pnl_implausible_for_display(
                category="EQUITY",
                report_date=date.today(),
                pnl_pct=20.0,
            )
        )

    def test_equity_huge_but_old_kept(self):
        self.assertFalse(
            previous_rec_pnl_implausible_for_display(
                category="EQUITY",
                report_date=date(2020, 1, 1),
                pnl_pct=94.0,
            )
        )

    def test_crypto_threshold_one_day(self):
        self.assertTrue(
            previous_rec_pnl_implausible_for_display(
                category="CRYPTO",
                report_date=date.today(),
                pnl_pct=60.0,
            )
        )
        self.assertFalse(
            previous_rec_pnl_implausible_for_display(
                category="CRYPTO",
                report_date=date.today(),
                pnl_pct=40.0,
            )
        )

    def test_infer_category_from_asset_when_bq_null(self):
        self.assertEqual(_infer_previous_rec_category("BTC", None), "CRYPTO")
        self.assertEqual(_infer_previous_rec_category("SMH", None), "EQUITY")
        self.assertEqual(_infer_previous_rec_category("NVDA", "EQUITY"), "EQUITY")


REPORT_BAD_JSON = """\
[QSREC_START]
{ invalid json here
[QSREC_END]
"""


class TestExtractRecommendationsJson(unittest.TestCase):
    """Tests for extract_recommendations_json (System A)."""

    def test_parses_correct_count(self):
        recs = extract_recommendations_json(SAMPLE_REPORT)
        self.assertEqual(len(recs), 3)

    def test_btc_long_fields(self):
        recs = extract_recommendations_json(SAMPLE_REPORT)
        btc = next((r for r in recs if r["asset"] == "BTC"), None)
        self.assertIsNotNone(btc, "BTC recommendation not found")
        self.assertEqual(btc["direction"], "LONG")
        self.assertAlmostEqual(btc["entry"], 94500.0)
        self.assertAlmostEqual(btc["target"], 100000.0)
        self.assertAlmostEqual(btc["stop"], 91000.0)
        self.assertEqual(btc["confidence"], 4)
        self.assertEqual(btc["category"], "CRYPTO")
        self.assertIn("ETF 持續流入", btc["narrative"])

    def test_sol_short_fields(self):
        recs = extract_recommendations_json(SAMPLE_REPORT)
        sol = next((r for r in recs if r["asset"] == "SOL"), None)
        self.assertIsNotNone(sol, "SOL recommendation not found")
        self.assertEqual(sol["direction"], "SHORT")
        self.assertAlmostEqual(sol["entry"], 146.0)
        self.assertAlmostEqual(sol["target"], 130.0)
        self.assertAlmostEqual(sol["stop"], 152.0)

    def test_nvda_equity(self):
        recs = extract_recommendations_json(SAMPLE_REPORT)
        nvda = next((r for r in recs if r["asset"] == "NVDA"), None)
        self.assertIsNotNone(nvda, "NVDA recommendation not found")
        self.assertEqual(nvda["category"], "EQUITY")
        self.assertAlmostEqual(nvda["entry"], 885.0)
        self.assertIn("B200 需求強勁", nvda["narrative"])

    def test_empty_report(self):
        self.assertEqual(extract_recommendations_json(""), [])

    def test_no_qsrec_block(self):
        self.assertEqual(extract_recommendations_json(REPORT_NO_JSON), [])

    def test_malformed_json_does_not_crash(self):
        recs = extract_recommendations_json(REPORT_BAD_JSON)
        self.assertIsInstance(recs, list)
        self.assertEqual(len(recs), 0)

    def test_multiple_blocks_merged(self):
        """Two separate [QSREC_START] blocks should both be parsed."""
        recs = extract_recommendations_json(SAMPLE_REPORT)
        assets = {r["asset"] for r in recs}
        self.assertIn("BTC", assets)
        self.assertIn("NVDA", assets)


class TestStripTrackerBlocks(unittest.TestCase):
    """Tests for strip_tracker_blocks."""

    def test_removes_qsrec_block(self):
        cleaned = strip_tracker_blocks(SAMPLE_REPORT)
        self.assertNotIn("[QSREC_START]", cleaned)
        self.assertNotIn("[QSREC_END]", cleaned)

    def test_preserves_html_content(self):
        cleaned = strip_tracker_blocks(SAMPLE_REPORT)
        self.assertIn("資金流向與精準操作", cleaned)
        self.assertIn("AI 產業鏈精準操作", cleaned)

    def test_no_block_unchanged(self):
        cleaned = strip_tracker_blocks(REPORT_NO_JSON)
        self.assertEqual(cleaned, REPORT_NO_JSON.rstrip())


class TestYfinanceBatchPrices(unittest.TestCase):
    """OPEN／上期追蹤應合併 symbol 批次下載，避免 N+1 yfinance 請求。"""

    def test_current_prices_single_batched_download(self):
        cols = pd.MultiIndex.from_tuples(
            [("Close", "BTC-USD"), ("Close", "NVDA")],
            names=["Price", "Ticker"],
        )
        df = pd.DataFrame(
            [[90000.0, 100.0], [91000.0, 101.0]],
            index=pd.date_range("2026-01-01", periods=2, freq="D"),
            columns=cols,
        )
        calls: list[tuple] = []

        def fake_download(*args, **kwargs):
            calls.append(args)
            return df

        # conftest 在 CI 將 yfinance stub 成空模組，需 create=True 才能掛上 fake download
        import tracker as tr

        with patch.object(tr.yf, "download", side_effect=fake_download, create=True):
            prices = _current_prices_for_assets(["BTC", "NVDA", "BTC"])

        self.assertAlmostEqual(prices["BTC"], 91000.0)
        self.assertAlmostEqual(prices["NVDA"], 101.0)
        self.assertEqual(len(calls), 1, "expected one batched yf.download for unique legs")


class TestRiskControls(unittest.TestCase):
    """Tests for regime caps and trade-structure filters."""

    def test_compute_metrics_long_positive_rr(self):
        m = _compute_trade_metrics(entry=100, target=110, stop=95, direction="LONG", confidence=3)
        self.assertGreater(m["rr_ratio"], 1.0)
        self.assertLess(m["max_drawdown_pct"], 0.0)
        self.assertGreater(m["expected_win_rate"], 0.0)

    def test_validate_rec_clamps_position_in_risk_off(self):
        raw = {
            "asset": "BTC",
            "direction": "LONG",
            "entry": 70000,
            "target": 73000,
            "stop": 68000,
            "confidence": 3,
            "category": "CRYPTO",
            "narrative": "test",
            "trigger": "4H close above 70k",
            "invalidation": "daily close below 67k",
            "position_pct": 12,
            "timeframe": "3-5d",
        }
        rec = _validate_rec(raw, "2026-03-12", "risk_off")
        self.assertIsNotNone(rec)
        self.assertAlmostEqual(rec["position_pct"], 5.0)

    def test_validate_rec_rejects_invalid_long_structure(self):
        raw = {
            "asset": "BTC",
            "direction": "LONG",
            "entry": 70000,
            "target": 69000,  # invalid for LONG
            "stop": 68000,
            "confidence": 3,
            "category": "CRYPTO",
            "narrative": "test",
        }
        rec = _validate_rec(raw, "2026-03-12", "neutral")
        self.assertIsNone(rec)

    def test_validate_rec_rejects_low_rr(self):
        raw = {
            "asset": "BTC",
            "direction": "LONG",
            "entry": 70000,
            "target": 70500,  # tiny reward
            "stop": 68000,    # large risk
            "confidence": 3,
            "category": "CRYPTO",
            "narrative": "test",
            "trigger": "x",
            "invalidation": "y",
            "timeframe": "3d",
        }
        rec = _validate_rec(raw, "2026-03-12", "neutral")
        self.assertIsNone(rec)


class TestGetRecentLessons(unittest.TestCase):
    """Reflection loop: BQ HIT_STOP rows → compact JSON for strategist context."""

    def test_skip_bigquery_returns_empty(self):
        with patch.dict(os.environ, {"SKIP_BIGQUERY": "1"}):
            out = get_recent_lessons(3)
        self.assertEqual(out, "")

    @patch("tracker._get_bq_client")
    def test_hit_stop_single_row_json_monitor(self, mock_get_client):
        mock_row = {
            "asset": "NVDA",
            "category": "EQUITY",
            "direction": "SHORT",
            "pnl_pct": -2.5,
            "exit_date": date(2025, 3, 1),
        }
        mock_job = MagicMock()
        mock_job.result.return_value = [mock_row]
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_get_client.return_value = mock_client

        with patch.dict(os.environ, {"SKIP_BIGQUERY": "", "REFLECTION_MIN_STOPS_REDUCE": "2"}, clear=False):
            out = get_recent_lessons(3)

        self.assertTrue(out.startswith("{"))
        self.assertIn("recent_lessons", out)
        self.assertIn("NVDA", out)
        self.assertIn("monitor", out)
        self.assertIn("ai_semis", out)

    @patch("tracker._get_bq_client")
    def test_hit_stop_two_same_ticker_reduce_exposure(self, mock_get_client):
        rows = [
            {
                "asset": "NVDA",
                "category": "EQUITY",
                "direction": "LONG",
                "pnl_pct": -3.0,
                "exit_date": date(2025, 3, 2),
            },
            {
                "asset": "$NVDA",
                "category": "EQUITY",
                "direction": "LONG",
                "pnl_pct": -2.0,
                "exit_date": date(2025, 3, 1),
            },
        ]
        mock_job = MagicMock()
        mock_job.result.return_value = rows
        mock_client = MagicMock()
        mock_client.query.return_value = mock_job
        mock_get_client.return_value = mock_client

        with patch.dict(os.environ, {"SKIP_BIGQUERY": "", "REFLECTION_MIN_STOPS_REDUCE": "2"}, clear=False):
            out = get_recent_lessons(3)

        self.assertIn("reduce_exposure", out)
        self.assertIn('"stop_loss_count":2', out)

    @patch("tracker._get_bq_client")
    def test_query_failure_returns_empty(self, mock_get_client):
        mock_get_client.side_effect = RuntimeError("bq down")
        with patch.dict(os.environ, {"SKIP_BIGQUERY": ""}, clear=False):
            out = get_recent_lessons(3)
        self.assertEqual(out, "")

    def test_aggregate_hit_stop_lessons_crypto_sector(self):
        from tracker import _aggregate_hit_stop_lessons

        rows = [
            {"asset": "BTC", "category": "CRYPTO", "direction": "LONG", "pnl_pct": -4.0},
            {"asset": "ETH", "category": "CRYPTO", "direction": "LONG", "pnl_pct": -1.0},
        ]
        payload = _aggregate_hit_stop_lessons(rows, window_days=3, min_reduce=2)
        self.assertEqual(payload["recent_lessons"]["by_sector"]["crypto"]["stop_loss_count"], 2)
        self.assertEqual(
            payload["recent_lessons"]["by_sector"]["crypto"]["suggestion"],
            "reduce_exposure",
        )


class TestGeneratePerformanceSummary(unittest.TestCase):
    """Telegram HTML 績效週報：指標定義與 regime 小樣本註記。"""

    @patch("tracker._get_bq_client")
    def test_includes_definitions_and_regime_caveats(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        status_rows = [
            {
                "status": "HIT_STOP",
                "cnt": 9,
                "avg_pnl": -5.0,
                "best": -1.0,
                "worst": -100.0,
                "avg_days": 5.0,
            },
            {
                "status": "HIT_TARGET",
                "cnt": 6,
                "avg_pnl": 12.0,
                "best": 50.0,
                "worst": 2.0,
                "avg_days": 4.0,
            },
        ]
        pnl_rows = [{"report_date": None, "created_at": None, "pnl_pct": float(i), "regime_at_signal": "neutral"} for i in (-2.0, 3.0, -1.0, 4.0)]
        regime_rows = [
            {"regime": "neutral", "cnt": 12, "avg_pnl": 1.5, "win_rate": 40.0},
            {"regime": "risk_on", "cnt": 5, "avg_pnl": 2.0, "win_rate": 40.0},
            {"regime": "unknown", "cnt": 3, "avg_pnl": 900.0, "win_rate": 33.0},
        ]

        def _job(rows):
            j = MagicMock()
            j.result.return_value = rows
            return j

        mock_client.query.side_effect = [
            _job(status_rows),
            _job(pnl_rows),
            _job(regime_rows),
        ]

        out = generate_performance_summary(project_id="test-proj", days=30)
        self.assertIn("指標說明", out)
        self.assertIn("回撤說明", out)
        self.assertIn("Profit Factor", out)
        self.assertIn("不等於", out)
        self.assertIn("unknown", out)
        self.assertIn("缺 regime", out)
        self.assertIn("少於 10 筆", out)
        self.assertIn("解讀建議", out)


if __name__ == "__main__":
    unittest.main()
