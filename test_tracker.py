"""Unit tests for tracker.parse_trade_signals."""

import unittest

from tracker import parse_trade_signals


# ── realistic snippet mirroring actual LLM-generated report ──
SAMPLE_REPORT = """\
<b>【資金流向與精準操作 (Crypto)】</b>

· <b>$BTC (做多)</b>｜現價：$95,000｜信心水準：⭐️⭐️⭐️⭐️
· 進場：<code>$94,500</code>｜目標：<code>$100,000 (+5.8%)</code>｜停損：<code>$91,000 (-3.7%)</code>
· 敘事邏輯：ETF 持續流入，鏈上鯨魚增持

· <b>$SOL (做空)</b>｜現價：$145.50｜信心水準：⭐️⭐️⭐️
· 進場：<code>$146.00</code>｜目標：<code>$130.00 (-11%)</code>｜停損：<code>$152.00 (+4.1%)</code>
· 敘事邏輯：DeFi TVL 下滑，鏈上活躍度回落

<b>【AI 產業鏈精準操作 (US Equities)】</b>

· <b>$NVDA (做多)</b>｜現價：$890.00｜信心水準：⭐️⭐️⭐️⭐️⭐️
· 進場：<code>$885.00</code>｜目標：<code>$950.00 (+7.3%)</code>｜停損：<code>$860.00 (-2.8%)</code>
· 敘事邏輯：B200 需求強勁，雲端巨頭增加 CAPEX
"""


class TestParseTradeSignals(unittest.TestCase):
    """Tests for parse_trade_signals regex extraction."""

    def test_parses_correct_count(self):
        signals = parse_trade_signals(SAMPLE_REPORT)
        self.assertEqual(len(signals), 3)

    def test_btc_long(self):
        signals = parse_trade_signals(SAMPLE_REPORT)
        btc = next((s for s in signals if s["symbol"] == "BTC"), None)
        self.assertIsNotNone(btc, "BTC signal not found")
        self.assertEqual(btc["direction"], "LONG")
        self.assertAlmostEqual(btc["entry_price"], 94500.0)
        self.assertAlmostEqual(btc["target_price"], 100000.0)
        self.assertAlmostEqual(btc["stop_loss"], 91000.0)
        self.assertEqual(btc["confidence_level"], 4)
        self.assertIn("ETF 持續流入", btc["narrative"])

    def test_sol_short(self):
        signals = parse_trade_signals(SAMPLE_REPORT)
        sol = next((s for s in signals if s["symbol"] == "SOL"), None)
        self.assertIsNotNone(sol, "SOL signal not found")
        self.assertEqual(sol["direction"], "SHORT")
        self.assertAlmostEqual(sol["entry_price"], 146.0)
        self.assertAlmostEqual(sol["target_price"], 130.0)
        self.assertAlmostEqual(sol["stop_loss"], 152.0)
        self.assertEqual(sol["confidence_level"], 3)
        self.assertIn("DeFi TVL 下滑", sol["narrative"])

    def test_nvda_five_stars(self):
        signals = parse_trade_signals(SAMPLE_REPORT)
        nvda = next((s for s in signals if s["symbol"] == "NVDA"), None)
        self.assertIsNotNone(nvda, "NVDA signal not found")
        self.assertEqual(nvda["direction"], "LONG")
        self.assertEqual(nvda["confidence_level"], 5)
        self.assertAlmostEqual(nvda["entry_price"], 885.0)
        self.assertIn("B200 需求強勁", nvda["narrative"])

    def test_empty_report(self):
        self.assertEqual(parse_trade_signals(""), [])

    def test_no_trade_section(self):
        self.assertEqual(parse_trade_signals("Just some random text with no trades"), [])

    def test_malformed_report_does_not_crash(self):
        bad = "【資金流向與精準操作 (Crypto)】\n· <b>$XYZ (做多)</b>｜現價：abc｜信心水準：⭐️"
        signals = parse_trade_signals(bad)
        # Should return empty or partial — must NOT raise
        self.assertIsInstance(signals, list)

    def test_signal_fields_present(self):
        signals = parse_trade_signals(SAMPLE_REPORT)
        required = {"symbol", "direction", "entry_price", "target_price", "stop_loss", "confidence_level", "narrative"}
        for s in signals:
            self.assertTrue(required.issubset(s.keys()), f"Missing fields in {s}")

    def test_commas_in_prices(self):
        """Prices with comma separators (e.g. $95,000) should be parsed correctly."""
        report = """\
【資金流向與精準操作 (Crypto)】
· <b>$ETH (做多)</b>｜現價：$3,450.50｜信心水準：⭐️⭐️
· 進場：<code>$3,400.00</code>｜目標：<code>$3,800.00 (+11.8%)</code>｜停損：<code>$3,200.00 (-5.9%)</code>
"""
        signals = parse_trade_signals(report)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["symbol"], "ETH")
        self.assertAlmostEqual(signals[0]["entry_price"], 3400.0)


if __name__ == "__main__":
    unittest.main()
