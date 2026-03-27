"""Tests for optional HTML polish (report_editor)."""

import unittest
from unittest.mock import MagicMock, patch

from report_editor import polish_daily_report_html


class TestReportEditor(unittest.TestCase):
    def test_disabled_returns_original(self):
        html = "<b>x</b><code>42</code>"
        with patch.dict("os.environ", {"EDITOR_AGENT_ENABLED": "0"}, clear=False):
            out, meta = polish_daily_report_html(html)
        self.assertEqual(out, html)
        self.assertFalse(meta.get("enabled"))
        self.assertEqual(meta.get("skipped_reason"), "disabled")

    @patch.dict("os.environ", {"EDITOR_AGENT_ENABLED": "1", "OPENAI_API_KEY": "sk-test"}, clear=False)
    @patch("report_editor._litellm_completion")
    def test_accepts_polish_when_code_blocks_unchanged(self, mock_comp):
        html = "<b>Title</b><p>old</p><code>BTC 100</code>"
        polished = "<b>Title</b><p>new prose</p><code>BTC 100</code>"
        mock_comp.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=polished))]
        )
        out, meta = polish_daily_report_html(html)
        self.assertEqual(out, polished)
        self.assertTrue(meta.get("enabled"))
        self.assertTrue(meta.get("changed"))
        self.assertEqual(meta.get("skipped_reason"), None)

    @patch.dict("os.environ", {"EDITOR_AGENT_ENABLED": "1", "OPENAI_API_KEY": "sk-test"}, clear=False)
    @patch("report_editor._litellm_completion")
    def test_rejects_when_code_block_changes(self, mock_comp):
        html = "<code>A</code>"
        bad = "<code>B</code>"
        mock_comp.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=bad))]
        )
        out, meta = polish_daily_report_html(html)
        self.assertEqual(out, html)
        self.assertEqual(meta.get("skipped_reason"), "code_block_mismatch")

    @patch.dict("os.environ", {"EDITOR_AGENT_ENABLED": "1", "OPENAI_API_KEY": ""}, clear=False)
    def test_skips_without_openai_key(self):
        out, meta = polish_daily_report_html("<code>x</code>")
        self.assertIn("OPENAI_API_KEY", str(meta.get("skipped_reason", "")))
        self.assertEqual(out, "<code>x</code>")


if __name__ == "__main__":
    unittest.main()
