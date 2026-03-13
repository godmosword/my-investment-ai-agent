import unittest

from pydantic import ValidationError

from report_output_validator import (
    ReportOutput,
    assert_report_output,
    assert_sample_output,
    build_judge_prompt,
    parse_report_output,
)


class TestReportOutputValidator(unittest.TestCase):
    def test_parse_report_output_valid(self):
        output_json = {
            "title": "Daily Brief",
            "summary": (
                "這是一份測試摘要，長度刻意拉長超過五十個字元，"
                "用來確認自訂驗證條件可穩定通過，且不會被視為空回應。"
                "此外也會檢查格式是否完整、語意是否正常。"
            ),
            "code": "<code>BTC: 68000</code>",
            "news": "正常新聞內容",
        }
        result = parse_report_output(output_json)
        self.assertIsInstance(result, ReportOutput)
        assert_report_output(result)

    def test_parse_report_output_invalid_structure(self):
        bad_json = {"title": "Daily Brief", "summary": "only two fields"}
        with self.assertRaises(ValidationError):
            parse_report_output(bad_json)

    def test_assert_report_output_blocks_error_summary(self):
        result = ReportOutput(
            title="Daily Brief",
            summary="Error: API key missing, this message should fail custom assertion check now.",
            code="<code>BTC: 68000</code>",
        )
        with self.assertRaises(AssertionError):
            assert_report_output(result)

    def test_assert_sample_output_rules(self):
        sample_output = {
            "title": "Daily Brief",
            "code": "<code>NVDA: 900</code>",
            "news": "clean news",
        }
        assert_sample_output(sample_output)

        bad_output = {
            "title": "Daily Brief",
            "code": "<code>NVDA: 900</code>",
            "news": "HTTPError 429 from NewsAPI",
        }
        with self.assertRaises(AssertionError):
            assert_sample_output(bad_output)

    def test_build_judge_prompt(self):
        output = "這是一份報告內容。"
        prompt = build_judge_prompt(output)
        self.assertIn("回答 yes/no", prompt)
        self.assertIn(output, prompt)


if __name__ == "__main__":
    unittest.main()
