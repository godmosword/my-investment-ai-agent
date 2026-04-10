"""Tests for ai_sector_market_tool / HF sort preference."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


class TestAiSectorMarketYfinance(unittest.TestCase):
    def test_body_formats_pct_lines(self) -> None:
        import tools_legacy as tl

        tickers = list(tl._ai_sector_basket_symbols())
        idx = pd.bdate_range("2025-03-03", periods=8, freq="B")
        cols = pd.MultiIndex.from_arrays([["Close"] * len(tickers), tickers])
        row = np.arange(8, dtype=float)
        data = np.column_stack([100.0 + row + j * 0.05 for j in range(len(tickers))])
        mock_df = pd.DataFrame(data, index=idx, columns=cols)

        # conftest stubs yfinance as an empty module; patch the stub's download.
        yf_mod = sys.modules["yfinance"]
        with patch.object(yf_mod, "download", return_value=mock_df, create=True):
            out = tl._ai_sector_market_yfinance_body()

        self.assertIn("【AI／半導體族群市場｜yfinance 日線】", out)
        self.assertIn("SMH", out)
        self.assertIn("SPY", out)
        self.assertNotIn("[DATA_MISSING:ai_sector_market]", out)


class TestHfFetchSortPreference(unittest.TestCase):
    def test_prefer_downloads_uses_downloads_first(self) -> None:
        import tools_legacy as tl

        calls: list[str] = []

        def fake_http_get(url, **kwargs):
            class R:
                status_code = 200

                def json(self):
                    return []

            sort = (kwargs.get("params") or {}).get("sort")
            calls.append(str(sort))
            return R()

        with patch.object(tl, "_http_get", side_effect=fake_http_get):
            tl._hf_fetch_models(prefer_downloads=True)

        self.assertEqual(calls[0], "downloads")

    def test_default_uses_trending_first(self) -> None:
        import tools_legacy as tl

        calls: list[str] = []

        def fake_http_get(url, **kwargs):
            class R:
                status_code = 200

                def json(self):
                    return []

            sort = (kwargs.get("params") or {}).get("sort")
            calls.append(str(sort))
            return R()

        with patch.object(tl, "_http_get", side_effect=fake_http_get):
            tl._hf_fetch_models(prefer_downloads=False)

        self.assertEqual(calls[0], "trendingScore")


if __name__ == "__main__":
    unittest.main()
