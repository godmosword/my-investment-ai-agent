"""main.validate_report 與 report_html_gates.validate_report 一致（同一路徑）。"""

import unittest

from report_html_gates import validate_report as validate_html_gates
from main import validate_report as validate_main


class TestCoreReportValidationDelegate(unittest.TestCase):
    def test_candidate_matches_legacy_on_short_text(self):
        text = "x" * 500
        a = validate_main(text)
        b = validate_html_gates(text)
        self.assertEqual(a["valid"], b["valid"])
        self.assertEqual(a["news_count"], b["news_count"])
        self.assertEqual(sorted(a.get("issues") or []), sorted(b.get("issues") or []))

    def test_candidate_matches_legacy_on_rich_stub(self):
        from test_smoke_pipeline import _minimal_valid_report  # type: ignore

        text = _minimal_valid_report()
        a = validate_main(text)
        b = validate_html_gates(text)
        self.assertEqual(a["valid"], b["valid"])
        self.assertEqual(sorted(a.get("issues") or []), sorted(b.get("issues") or []))


if __name__ == "__main__":
    unittest.main()
