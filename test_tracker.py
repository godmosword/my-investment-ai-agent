"""Unit tests for tracker System A — JSON-based recommendation parsing."""

import unittest

from tracker import (
    extract_recommendations_json,
    strip_tracker_blocks,
    _compute_trade_metrics,
    _validate_rec,
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


if __name__ == "__main__":
    unittest.main()
