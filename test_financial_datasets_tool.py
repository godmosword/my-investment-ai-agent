"""Tests for financial_datasets_tool (Financial Datasets API wrapper)."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Stub missing runtime deps so tests run without the full project environment.
# Use MagicMock so any attribute access on stubs never raises AttributeError.
for _mod in (
    # telegram / network
    "telebot",
    "requests",
    # ML / data
    "pandas",
    "yfinance",
    "sklearn",
    "sklearn.ensemble",
    "sklearn.preprocessing",
    "numpy",
    # Google Cloud
    "google",
    "google.cloud",
    "google.cloud.bigquery",
    "google.api_core",
    "google.api_core.exceptions",
    # Apify / LiteLLM
    "apify_client",
    "litellm",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# crewai.tools.tool must be a passthrough decorator, not a MagicMock,
# so that financial_datasets_tool remains callable with a real .run() method.
if "crewai" not in sys.modules:
    def _passthrough_tool(f):
        """Passthrough @tool decorator: preserves the function and adds .run = f."""
        f.run = f
        return f

    _crewai_mod = MagicMock()
    _crewai_tools_mod = MagicMock()
    _crewai_tools_mod.tool = _passthrough_tool
    sys.modules["crewai"] = _crewai_mod
    sys.modules["crewai.tools"] = _crewai_tools_mod

from report_validator import _ai_fundamentals_citation_ok  # noqa: E402
from tools import _CACHE, financial_datasets_tool  # noqa: E402


def _fake_fd(path: str, params: dict) -> dict | None:
    sym = str(params.get("ticker", "X"))
    if "income-statements" in path:
        return {
            "income_statements": [
                {
                    "ticker": sym,
                    "fiscal_period": "2025-FY",
                    "period": "annual",
                    "revenue": 100_000_000_000.0,
                    "net_income": 20_000_000_000.0,
                    "gross_profit": 50_000_000_000.0,
                    "operating_income": 25_000_000_000.0,
                    "earnings_per_share_diluted": 5.0,
                },
                {
                    "ticker": sym,
                    "revenue": 90_000_000_000.0,
                },
            ]
        }
    if "balance-sheets" in path:
        return {
            "balance_sheets": [
                {
                    "total_assets": 200_000_000_000.0,
                    "cash_and_equivalents": 30_000_000_000.0,
                    "total_debt": 10_000_000_000.0,
                }
            ]
        }
    if "cash-flow" in path:
        return {
            "cash_flow_statements": [
                {
                    "net_cash_flow_from_operations": 40_000_000_000.0,
                    "free_cash_flow": 35_000_000_000.0,
                }
            ]
        }
    return None


class TestFinancialDatasetsTool(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()

    @patch("tools._fd_http_get_json", side_effect=_fake_fd)
    def test_watchlist_contains_tickers_and_financialdatasets_hint(self, _mock):
        out = financial_datasets_tool.run("watchlist")
        self.assertIn("NVDA", out)
        self.assertIn("MSFT", out)
        self.assertIn("AAPL", out)
        self.assertIn("FinancialDatasets", out)
        self.assertIn("營收", out)
        self.assertIn("(source=financial_datasets)", out)

    @patch("tools._fd_http_get_json", side_effect=_fake_fd)
    def test_single_ticker_quarterly(self, _mock):
        out = financial_datasets_tool.run("AMD:quarterly")
        self.assertIn("AMD", out)
        self.assertIn("損益", out)


class TestFinancialDatasetsToolEdgeCases(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()

    @patch("tools._fd_http_get_json", return_value=None)
    def test_api_failure_returns_error_line_per_ticker(self, _mock):
        """Income API 失敗時應回傳含 ticker 的錯誤說明行（不是 DATA_MISSING）。"""
        out = financial_datasets_tool.run("NVDA")
        self.assertIn("NVDA", out)
        self.assertIn("損益表 API 無資料或請求失敗", out)

    @patch("tools._fd_http_get_json", side_effect=_fake_fd)
    def test_cache_hit_skips_second_api_call(self, mock_fd):
        """第二次相同查詢應走 cache，不再呼叫 API。"""
        financial_datasets_tool.run("NVDA")
        calls_after_first = mock_fd.call_count
        financial_datasets_tool.run("NVDA")
        self.assertEqual(mock_fd.call_count, calls_after_first)

    @patch("tools._fd_http_get_json", return_value=None)
    def test_invalid_ticker_returns_data_missing(self, _mock):
        """非字母數字 ticker 應被過濾，回傳 DATA_MISSING。"""
        out = financial_datasets_tool.run("@#$%!")
        self.assertIn("[DATA_MISSING", out)

    @patch("tools._fd_http_get_json", side_effect=_fake_fd)
    def test_quarterly_period_selection(self, _mock):
        """TICKER:quarterly 應使用 quarterly period。"""
        out = financial_datasets_tool.run("TSLA:quarterly")
        self.assertIn("TSLA", out)
        self.assertIn("損益", out)


class TestAiFundamentalsCitationGate(unittest.TestCase):
    """Tests for _ai_fundamentals_citation_ok gate in report_validator."""

    _AI_PREFIX = "🤖 AI 市場\n"
    _REASON_FUNDAMENTAL = "本日選擇理由：NVDA 營收強勁，自由現金流創高。\n"
    _REASON_NO_FUNDAMENTAL = "本日選擇理由：技術形態突破，動能轉強。\n"
    _FD_MARKER = "FinancialDatasets NVDA 年度損益\n"

    def _report(self, reason: str, fd_marker: bool) -> str:
        marker = self._FD_MARKER if fd_marker else ""
        return self._AI_PREFIX + marker + reason + "[QSREC_START]\n"

    def test_passes_with_fd_marker(self):
        """含基本面用語 + FinancialDatasets 標記 → gate 通過。"""
        ok, msg = _ai_fundamentals_citation_ok(self._report(self._REASON_FUNDAMENTAL, fd_marker=True))
        self.assertTrue(ok, msg)

    def test_fails_fundamental_claim_without_fd_marker(self):
        """含基本面用語但無 FinancialDatasets 標記 → gate 失敗。"""
        with patch.dict(os.environ, {"STRICT_AI_FUNDAMENTALS_CITATION": "1"}):
            ok, msg = _ai_fundamentals_citation_ok(
                self._report(self._REASON_FUNDAMENTAL, fd_marker=False)
            )
        self.assertFalse(ok)
        self.assertIn("FinancialDatasets", msg)

    def test_passes_when_no_fundamental_claim(self):
        """pick_reason 無基本面用語 → gate 通過（即使無 FD 標記）。"""
        ok, msg = _ai_fundamentals_citation_ok(
            self._report(self._REASON_NO_FUNDAMENTAL, fd_marker=False)
        )
        self.assertTrue(ok, msg)

    def test_gate_disabled_via_env(self):
        """STRICT_AI_FUNDAMENTALS_CITATION=0 → gate 恆通過。"""
        with patch.dict(os.environ, {"STRICT_AI_FUNDAMENTALS_CITATION": "0"}):
            ok, msg = _ai_fundamentals_citation_ok(
                self._report(self._REASON_FUNDAMENTAL, fd_marker=False)
            )
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
