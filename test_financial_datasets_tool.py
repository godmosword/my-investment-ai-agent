"""Tests for financial_datasets_tool (Financial Datasets API wrapper)."""

import unittest
from unittest.mock import patch

from tools import _CACHE, financial_datasets_tool


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


if __name__ == "__main__":
    unittest.main()
