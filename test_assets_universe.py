"""Unit tests for tiered equity universe (assets_config + assets_universe)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import assets_universe as au


class TestAssetsUniverse(unittest.TestCase):
    def tearDown(self) -> None:
        au.clear_assets_universe_cache()

    def test_repo_assets_config_includes_goog_avgo_tsm(self) -> None:
        repo_json = Path(__file__).resolve().parent / "assets_config.json"
        self.assertTrue(repo_json.is_file(), "repo assets_config.json missing")
        with patch.dict("os.environ", {"ASSETS_CONFIG_PATH": str(repo_json)}):
            au.clear_assets_universe_cache()
            merged = au.equity_universe_merged()
        self.assertIn("NVDA", merged)
        self.assertIn("MSFT", merged)
        self.assertIn("GOOG", merged)
        self.assertIn("AVGO", merged)
        self.assertIn("TSM", merged)

    def test_core_extended_from_file(self) -> None:
        data = {
            "core_equity": ["AAA", "BBB"],
            "extended_equity": ["CCC", "DDD"],
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            p = f.name
        try:
            with patch.dict("os.environ", {"ASSETS_CONFIG_PATH": p}):
                au.clear_assets_universe_cache()
                self.assertEqual(au.equity_core_tickers(), ("AAA", "BBB"))
                self.assertEqual(au.equity_extended_tickers(), ("CCC", "DDD"))
                self.assertEqual(
                    au.equity_universe_merged(),
                    ("AAA", "BBB", "CCC", "DDD"),
                )
        finally:
            Path(p).unlink(missing_ok=True)
            au.clear_assets_universe_cache()

    def test_legacy_equity_only_file(self) -> None:
        data = {"equity": ["X", "Y", "Z", "W"]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(data, f)
            p = f.name
        try:
            with patch.dict("os.environ", {"ASSETS_CONFIG_PATH": p}):
                au.clear_assets_universe_cache()
                self.assertEqual(au.equity_core_tickers(), ("X", "Y"))
                self.assertEqual(au.equity_extended_tickers(), ("Z", "W"))
        finally:
            Path(p).unlink(missing_ok=True)
            au.clear_assets_universe_cache()


if __name__ == "__main__":
    unittest.main()
