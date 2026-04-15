"""Tests for prediction_markets_tool / Polymarket Gamma fetch (mocked HTTP)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import _CACHE, prediction_markets_tool
from tools_legacy import fetch_polymarket_hot_highlight_lines


class _FakeResp:
    def __init__(self, status: int, payload: object):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class TestPredictionMarketsTool(unittest.TestCase):
    def setUp(self) -> None:
        _CACHE.clear()

    def test_fetch_returns_three_lines_with_probabilities(self) -> None:
        events = [
            {
                "title": "Parent",
                "volume24hr": 1e9,
                "markets": [
                    {
                        "question": "Will X happen in 2026?",
                        "outcomePrices": '["0.35", "0.65"]',
                        "volume24hr": 2_000_000,
                    }
                ],
            },
            {
                "title": "Parent2",
                "markets": [
                    {
                        "question": "Will Y win?",
                        "outcomePrices": ["0.5", "0.5"],
                        "volume24hr": 1_500_000,
                    }
                ],
            },
            {
                "title": "Parent3",
                "markets": [
                    {
                        "question": "Will Z pass?",
                        "outcomePrices": ["0.12", "0.88"],
                        "volume24hr": 1_200_000,
                    }
                ],
            },
        ]

        def fake_get(url, params=None, timeout=None, headers=None):
            self.assertIn("polymarket", url)
            return _FakeResp(200, events)

        with patch.dict("os.environ", {"MOCK_APIS": ""}, clear=False):
            with patch("tools_legacy._http_get", side_effect=fake_get):
                lines = fetch_polymarket_hot_highlight_lines(limit_events=10, top_n=5)
        self.assertGreaterEqual(len(lines), 3)
        self.assertTrue(all("Polymarket Yes≈" in ln for ln in lines))
        self.assertTrue(any("35.0%" in ln or "50.0%" in ln for ln in lines))

    def test_tool_wraps_with_header_and_data_as_of(self) -> None:
        events = [
            {
                "title": "E",
                "markets": [
                    {
                        "question": "Binary Q?",
                        "outcomePrices": ["0.4", "0.6"],
                        "volume24hr": 900_000,
                    }
                ],
            },
            {
                "title": "E2",
                "markets": [
                    {
                        "question": "Binary Q2?",
                        "outcomePrices": ["0.41", "0.59"],
                        "volume24hr": 800_000,
                    }
                ],
            },
            {
                "title": "E3",
                "markets": [
                    {
                        "question": "Binary Q3?",
                        "outcomePrices": ["0.42", "0.58"],
                        "volume24hr": 700_000,
                    }
                ],
            },
        ]

        with patch.dict("os.environ", {"MOCK_APIS": ""}, clear=False):
            with patch("tools_legacy._http_get", return_value=_FakeResp(200, events)):
                out = prediction_markets_tool.run("")
        self.assertIn("【預測市場熱門", out)
        self.assertIn("Polymarket", out)
        self.assertIn("[data_as_of:", out)

    def test_fetch_prefers_keyword_allowlist_over_high_volume_sports(self) -> None:
        events = [
            {
                "title": "Sports",
                "volume24hr": 9_000_000,
                "markets": [
                    {
                        "question": "NBA: Player X over 10 rebounds tonight?",
                        "outcomePrices": '["0.45", "0.55"]',
                        "volume24hr": 8_000_000,
                    }
                ],
            },
            {
                "title": "Macro",
                "volume24hr": 2_000_000,
                "markets": [
                    {
                        "question": "Will the Fed cut rates before June 2026?",
                        "outcomePrices": '["0.40", "0.60"]',
                        "volume24hr": 1_800_000,
                    }
                ],
            },
            {
                "title": "Crypto",
                "volume24hr": 1_500_000,
                "markets": [
                    {
                        "question": "Will spot Bitcoin ETF see net inflows this week?",
                        "outcomePrices": '["0.42", "0.58"]',
                        "volume24hr": 1_200_000,
                    }
                ],
            },
            {
                "title": "Macro2",
                "markets": [
                    {
                        "question": "Will CPI YoY print above 3% next release?",
                        "outcomePrices": '["0.38", "0.62"]',
                        "volume24hr": 900_000,
                    }
                ],
            },
        ]

        def fake_get(url, params=None, timeout=None, headers=None):
            return _FakeResp(200, events)

        env = {
            "MOCK_APIS": "",
            "PREDICTION_MARKETS_KEYWORDS": "Fed,Bitcoin,CPI",
            "PREDICTION_MARKETS_DENYLIST": "nba,rebounds",
        }
        with patch.dict("os.environ", env, clear=False):
            with patch("tools_legacy._http_get", side_effect=fake_get):
                lines = fetch_polymarket_hot_highlight_lines(limit_events=10, top_n=3)
        self.assertGreaterEqual(len(lines), 3)
        joined = "\n".join(lines)
        self.assertNotIn("rebounds", joined.lower())
        self.assertNotIn("nba", joined.lower())
        self.assertIn("Fed", joined)
        self.assertIn("Bitcoin", joined)
        self.assertIn("CPI", joined)

    def test_fetch_passes_tag_id_and_exclude_when_env_set(self) -> None:
        captured: list[dict] = []
        bulk = [
            {
                "id": "fb1",
                "markets": [
                    {
                        "question": "Will macro X hit?",
                        "outcomePrices": '["0.33", "0.67"]',
                        "volume24hr": 3_000_000,
                    }
                ],
            },
            {
                "id": "fb2",
                "markets": [
                    {
                        "question": "Will macro Y hit?",
                        "outcomePrices": '["0.34", "0.66"]',
                        "volume24hr": 2_500_000,
                    }
                ],
            },
            {
                "id": "fb3",
                "markets": [
                    {
                        "question": "Will macro Z hit?",
                        "outcomePrices": '["0.35", "0.65"]',
                        "volume24hr": 2_000_000,
                    }
                ],
            },
        ]

        def fake_get(url, params=None, timeout=None, headers=None):
            p = dict(params or {})
            captured.append(p)
            if p.get("tag_id"):
                return _FakeResp(200, [])
            return _FakeResp(200, bulk)

        env = {
            "MOCK_APIS": "",
            "PREDICTION_MARKETS_TAG_IDS": "100381,100382",
            "PREDICTION_MARKETS_EXCLUDE_TAG_IDS": "999",
        }
        with patch.dict("os.environ", env, clear=False):
            with patch("tools_legacy._http_get", side_effect=fake_get):
                lines = fetch_polymarket_hot_highlight_lines(limit_events=10, top_n=3)
        self.assertGreaterEqual(len(lines), 3)
        self.assertEqual([c.get("tag_id") for c in captured[:2]], ["100381", "100382"])
        self.assertEqual(captured[0].get("exclude_tag_id"), "999")
        self.assertEqual(captured[0].get("order"), "volume_24hr")
        self.assertNotIn("tag_id", captured[-1])

    def test_fetch_fallback_without_tag_when_tag_pool_insufficient(self) -> None:
        events_global = [
            {
                "id": "g1",
                "title": "Macro",
                "markets": [
                    {
                        "question": "Will CPI surprise next?",
                        "outcomePrices": '["0.44", "0.56"]',
                        "volume24hr": 2_000_000,
                    }
                ],
            },
            {
                "id": "g2",
                "title": "Macro2",
                "markets": [
                    {
                        "question": "Will Fed cut before Q3?",
                        "outcomePrices": '["0.46", "0.54"]',
                        "volume24hr": 1_800_000,
                    }
                ],
            },
            {
                "id": "g3",
                "title": "Macro3",
                "markets": [
                    {
                        "question": "Will core PCE stay above 2%?",
                        "outcomePrices": '["0.41", "0.59"]',
                        "volume24hr": 1_500_000,
                    }
                ],
            },
        ]
        calls: list[dict] = []

        def fake_get(url, params=None, timeout=None, headers=None):
            c = dict(params or {})
            calls.append(c)
            if c.get("tag_id") == "424242":
                return _FakeResp(200, [])
            return _FakeResp(200, events_global)

        env = {"MOCK_APIS": "", "PREDICTION_MARKETS_TAG_IDS": "424242"}
        with patch.dict("os.environ", env, clear=False):
            with patch("tools_legacy._http_get", side_effect=fake_get):
                lines = fetch_polymarket_hot_highlight_lines(limit_events=10, top_n=3)
        self.assertGreaterEqual(len(lines), 3)
        self.assertTrue(any("tag_id" not in c or c.get("tag_id") is None for c in calls))
        self.assertTrue(any(c.get("tag_id") == "424242" for c in calls))


if __name__ == "__main__":
    unittest.main()
