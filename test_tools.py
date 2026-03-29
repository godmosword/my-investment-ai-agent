"""Unit tests for tools.py — mock-based tests for external API tools."""

import unittest
from unittest.mock import patch, MagicMock

from tools import (
    _parse_coinglass_funding_rate,
    _parse_coinglass_liquidations,
    _get_cache,
    _set_cache,
    _CACHE,
    fear_greed_tool,
    _binance_funding_rate,
    _binance_long_short_ratio,
    _binance_open_interest,
)


class TestParseCoinglassFundingRate(unittest.TestCase):
    """Test _parse_coinglass_funding_rate parser (no mock needed)."""

    def test_positive_rate(self):
        data = [{"close": 0.0003}]
        result = _parse_coinglass_funding_rate(data, "BTC")
        self.assertIn("0.0300%", result)
        self.assertIn("偏熱", result)

    def test_negative_rate(self):
        data = [{"close": -0.0005}]
        result = _parse_coinglass_funding_rate(data, "ETH")
        self.assertIn("ETH", result)
        self.assertIn("偏冷", result)

    def test_extreme_positive(self):
        data = [{"close": 0.001}]
        result = _parse_coinglass_funding_rate(data, "BTC")
        self.assertIn("極度過熱", result)

    def test_neutral_rate(self):
        data = [{"close": 0.00005}]
        result = _parse_coinglass_funding_rate(data, "BTC")
        self.assertIn("中性", result)
        self.assertIn("近零", result)
        self.assertIn("0.005000%", result)

    def test_tiny_rate_uses_six_decimals(self):
        data = [{"close": 0.000001}]
        result = _parse_coinglass_funding_rate(data, "BTC")
        self.assertIn("0.000100%", result)
        self.assertIn("近零", result)

    def test_empty_data(self):
        result = _parse_coinglass_funding_rate([], "BTC")
        self.assertIn("DATA_MISSING", result)

    def test_none_data(self):
        result = _parse_coinglass_funding_rate(None, "BTC")
        self.assertIn("DATA_MISSING", result)

    def test_missing_close_field(self):
        data = [{"unrelated": 123}]
        result = _parse_coinglass_funding_rate(data, "BTC")
        self.assertIn("DATA_MISSING", result)

    def test_fallback_fields(self):
        """Should try fundingRate if close is missing."""
        data = [{"fundingRate": 0.0002}]
        result = _parse_coinglass_funding_rate(data, "BTC")
        self.assertIn("0.0200%", result)


class TestParseCoinglassLiquidations(unittest.TestCase):
    """Test _parse_coinglass_liquidations parser (no mock needed)."""

    def test_normal_data(self):
        data = [
            {"long_liquidation_usd": 5_000_000, "short_liquidation_usd": 3_000_000},
            {"long_liquidation_usd": 2_000_000, "short_liquidation_usd": 1_000_000},
        ]
        result = _parse_coinglass_liquidations(data, "BTC")
        self.assertIn("BTC", result)
        self.assertIn("$11.00M", result)
        self.assertIn("多頭爆倉 $7.00M", result)
        self.assertIn("空頭爆倉 $4.00M", result)

    def test_empty_data(self):
        result = _parse_coinglass_liquidations([], "BTC")
        self.assertIn("DATA_MISSING", result)

    def test_partial_fields(self):
        data = [{"long_liquidation_usd": 1_000_000}]
        result = _parse_coinglass_liquidations(data, "SOL")
        self.assertIn("SOL", result)
        self.assertIn("$1.00M", result)


class TestCacheOperations(unittest.TestCase):
    """Test in-memory cache get/set."""

    def setUp(self):
        _CACHE.clear()

    def test_set_and_get(self):
        _set_cache(("test", "key"), "value123")
        self.assertEqual(_get_cache(("test", "key")), "value123")

    def test_cache_miss(self):
        self.assertIsNone(_get_cache(("nonexistent", "key")))


class TestFearGreedTool(unittest.TestCase):
    """Test fear_greed_tool with mocked HTTP."""

    def setUp(self):
        _CACHE.clear()

    @patch("tools._http_get")
    def test_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": [
                {"value": "25", "value_classification": "Extreme Fear"},
                {"value": "30", "value_classification": "Fear"},
            ]
        }
        mock_get.return_value = mock_resp

        result = fear_greed_tool.run()
        self.assertIn("25/100", result)
        self.assertIn("Extreme Fear", result)
        self.assertIn("極度恐懼", result)

    @patch("tools._http_get")
    def test_api_failure(self, mock_get):
        mock_get.side_effect = Exception("timeout")

        _CACHE.clear()
        result = fear_greed_tool.run()
        self.assertIn("DATA_MISSING", result)


class TestBinanceFallbacks(unittest.TestCase):
    """Test Binance fallback functions with mocked HTTP."""

    @patch("tools._http_get")
    def test_binance_funding_rate_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"fundingRate": "0.0001"}]
        mock_get.return_value = mock_resp

        result = _binance_funding_rate()
        self.assertIn("BTC", result)
        self.assertIn("Binance", result)
        self.assertNotIn("DATA_MISSING", result)

    @patch("tools._http_get")
    def test_binance_funding_rate_failure(self, mock_get):
        mock_get.side_effect = Exception("network error")

        result = _binance_funding_rate()
        self.assertIn("DATA_MISSING", result)

    @patch("tools._http_get")
    def test_binance_long_short_ratio_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"longShortRatio": "1.25"}]
        mock_get.return_value = mock_resp

        result = _binance_long_short_ratio()
        self.assertIn("1.250", result)
        self.assertIn("多方佔優", result)

    @patch("tools._http_get")
    def test_binance_open_interest_success(self, mock_get):
        responses = [
            MagicMock(status_code=200, ok=True),
            MagicMock(status_code=200, ok=True),
        ]
        responses[0].raise_for_status = MagicMock()
        responses[0].json.return_value = {"openInterest": "200000"}
        responses[1].json.return_value = {"price": "95000"}
        mock_get.side_effect = responses

        result = _binance_open_interest()
        self.assertIn("BTC", result)
        self.assertIn("OI", result)
        self.assertIn("Binance", result)


if __name__ == "__main__":
    unittest.main()
