"""Tests for SPY ETF anchor vs ^GSPC index disambiguation in tools_legacy."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from tools import _CACHE
from tools_legacy import fetch_spy_etf_last_close_anchor


class TestSpyEtfAnchor(unittest.TestCase):
    def setUp(self) -> None:
        _CACHE.clear()

    def test_fetch_spy_returns_last_valid_close(self) -> None:
        df = pd.DataFrame({"Close": [100.0, 612.34]})
        with patch("tools_legacy._yf_download_with_timeout", return_value=df):
            v = fetch_spy_etf_last_close_anchor()
        self.assertEqual(v, 612.34)


if __name__ == "__main__":
    unittest.main()
