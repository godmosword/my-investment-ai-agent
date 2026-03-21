"""core.report_validation 與 main.validate_report 等價性（Phase 3 接線）。"""

import unittest

from core.report_validation import validate_report_candidate
from main import validate_report


class TestCoreReportValidationDelegate(unittest.TestCase):
    def test_candidate_matches_legacy_on_short_text(self):
        text = "x" * 500
        a = validate_report(text)
        b = validate_report_candidate(text)
        self.assertEqual(a["valid"], b["valid"])
        self.assertEqual(a["news_count"], b["news_count"])
        self.assertEqual(sorted(a.get("issues") or []), sorted(b.get("issues") or []))

    def test_candidate_matches_legacy_on_rich_stub(self):
        from test_smoke_pipeline import _minimal_valid_report  # type: ignore

        text = _minimal_valid_report()
        a = validate_report(text)
        b = validate_report_candidate(text)
        self.assertEqual(a["valid"], b["valid"])
        self.assertEqual(sorted(a.get("issues") or []), sorted(b.get("issues") or []))


if __name__ == "__main__":
    unittest.main()
