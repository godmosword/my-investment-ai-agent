"""Tests for Phase 3 dual-run validation compare (observe-only)."""

import unittest
from unittest.mock import patch

from main import _log_validation_dual_run, validate_report
from report_pipeline_compare import compare_validation_results, validation_snapshot


class TestCompareValidationResults(unittest.TestCase):
    def test_identical_snapshots(self):
        a = {"valid": True, "issues": ["x", "y"], "news_count": 8}
        b = {"valid": True, "issues": ["y", "x"], "news_count": 8}
        # 補齊 snapshot 需要的鍵（測試只關心 issues_sorted）
        for d in (a, b):
            d.setdefault("fallback_news_count", 0)
            d.setdefault("has_data_missing", False)
        diff = compare_validation_results(a, b)
        self.assertTrue(diff["identical"])

    def test_issues_mismatch(self):
        legacy = validate_report("short")
        candidate = dict(legacy)
        candidate["issues"] = list(legacy.get("issues") or []) + ["SYNTHETIC_TEST_ONLY"]
        diff = compare_validation_results(legacy, candidate)
        self.assertFalse(diff["identical"])
        self.assertIn("SYNTHETIC_TEST_ONLY", diff["issues_only_in_candidate"])


class TestLogDualRun(unittest.TestCase):
    @patch("main._validate_report_candidate")
    @patch("main.logger")
    def test_logs_warning_on_mismatch(self, mock_logger, mock_candidate):
        text = "x" * 3100
        legacy = validate_report(text)
        mock_candidate.return_value = {**legacy, "valid": not legacy.get("valid")}
        with patch.dict("os.environ", {"REPORT_COMPARE_MODE": "1"}, clear=False):
            _log_validation_dual_run(text, legacy)
        mock_logger.warning.assert_called()
        args = str(mock_logger.warning.call_args)
        self.assertIn("REPORT_COMPARE", args)

    @patch("main.logger")
    def test_skips_when_mode_off(self, mock_logger):
        legacy = validate_report("x")
        with patch.dict("os.environ", {"REPORT_COMPARE_MODE": "0"}, clear=False):
            _log_validation_dual_run("x" * 3100, legacy)
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()


class TestValidationSnapshotStable(unittest.TestCase):
    def test_snapshot_sorts_issues(self):
        base = validate_report("x" * 4000)
        base["issues"] = ["zebra", "apple"]
        snap = validation_snapshot(base)
        self.assertEqual(snap["issues_sorted"], ["apple", "zebra"])


if __name__ == "__main__":
    unittest.main()
