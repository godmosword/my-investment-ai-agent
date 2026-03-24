"""Tests for report_judge (hard + LLM judge helpers)."""

import unittest
from unittest.mock import MagicMock, patch

from report_judge import (
    hard_pattern_judge_pass,
    llm_judge_should_block,
    llm_quality_judge,
)


class TestHardPatternJudge(unittest.TestCase):
    def test_clean_pass(self):
        self.assertTrue(hard_pattern_judge_pass("<b>OK</b> report"))

    def test_data_missing_fails(self):
        self.assertFalse(hard_pattern_judge_pass("body [DATA_MISSING:x] tail"))

    def test_traceback_fails(self):
        self.assertFalse(hard_pattern_judge_pass("Traceback (most recent call last)"))


class TestLLMQualityJudge(unittest.TestCase):
    @patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False)
    def test_skips_without_key(self):
        r = llm_quality_judge("<html>x</html>")
        self.assertTrue(r["pass"])
        self.assertIn("missing", str(r.get("raw_error", "")).lower())

    @patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=False)
    @patch("report_judge._litellm_completion")
    def test_parses_json_response(self, mock_comp):
        mock_comp.return_value = MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(
                        content='{"overall_score": 85, "pass": true, '
                        '"rubric": {"structure": 80, "data_hygiene": 90, "actionability": 85}, '
                        '"reasons": ["ok"]}'
                    )
                )
            ]
        )
        r = llm_quality_judge("<b>report</b>")
        self.assertEqual(r["overall_score"], 85.0)
        self.assertTrue(r["pass"])
        self.assertEqual(r["rubric"].get("structure"), 80)

    @patch.dict(
        "os.environ",
        {
            "OPENAI_API_KEY": "sk-x",
            "REPORT_LLM_JUDGE_BLOCKING": "1",
            "REPORT_LLM_JUDGE_MIN_SCORE": "70",
        },
        clear=False,
    )
    def test_block_low_score(self):
        r = {"pass": False, "overall_score": 40.0, "raw_error": None}
        self.assertTrue(llm_judge_should_block(r))

    @patch.dict("os.environ", {"REPORT_LLM_JUDGE_BLOCKING": "0"}, clear=False)
    def test_no_block_when_disabled(self):
        r = {"pass": False, "overall_score": 10.0, "raw_error": None}
        self.assertFalse(llm_judge_should_block(r))


if __name__ == "__main__":
    unittest.main()
