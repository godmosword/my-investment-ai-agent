"""Tests for report_quality_agent (TODOS follow-up + composite score)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from report_quality_agent import (
    append_quality_followup_todos,
    maybe_run_report_quality_agent_after_success,
    _composite_score,
    _replace_or_insert_agent_block,
)


class TestCompositeScore(unittest.TestCase):
    def test_dual_avg(self):
        llm = {"overall_score": 80, "raw_error": None}
        dqc = {"overall": 60.0}
        s, lab = _composite_score(llm, dqc, "dual")
        self.assertEqual(lab, "dual_avg")
        self.assertEqual(s, 70.0)

    def test_llm_skip_uses_domain(self):
        llm = {"overall_score": 99, "raw_error": "skip"}
        dqc = {"overall": 55.0}
        s, lab = _composite_score(llm, dqc, "dual")
        self.assertEqual(lab, "domain_only")
        self.assertEqual(s, 55.0)


class TestTodosBlock(unittest.TestCase):
    def test_insert_block_with_markers(self):
        base = "# T\n\n## 下一批隊列\n\n1. x\n"
        inner = ["- item a", "- item b"]
        out = _replace_or_insert_agent_block(base, inner, max_lines=40)
        self.assertIn("REPORT_QUALITY_AGENT_TODOS_BEGIN", out)
        self.assertIn("item a", out)
        self.assertIn("下一批隊列", out)

    def test_replace_existing_block(self):
        base = (
            "head\n"
            "<!-- REPORT_QUALITY_AGENT_TODOS_BEGIN -->\n"
            "- old\n"
            "<!-- REPORT_QUALITY_AGENT_TODOS_END -->\n"
            "tail\n"
        )
        out = _replace_or_insert_agent_block(base, ["- new"], max_lines=40)
        self.assertIn("- new", out)
        self.assertNotIn("- old", out)


class TestMaybeRunAgent(unittest.TestCase):
    def test_disabled(self):
        with patch.dict("os.environ", {}, clear=True):
            r = maybe_run_report_quality_agent_after_success(
                "<b>x</b>", gate_passed=True, validation_result={"valid": True}
            )
        self.assertIsNone(r)

    @patch("report_quality_agent.llm_quality_judge")
    def test_writes_todos_when_low_score(self, mock_llm):
        mock_llm.return_value = {
            "pass": False,
            "overall_score": 40.0,
            "rubric": {"structure": 40},
            "reasons": ["weak headline"],
            "raw_error": None,
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TODOS.md"
            p.write_text("# X\n\n## 下一批隊列\n\n- keep\n", encoding="utf-8")
            with patch.dict(
                "os.environ",
                {
                    "REPORT_QUALITY_AGENT": "1",
                    "REPORT_QUALITY_AGENT_COMPOSITE_MIN": "90",
                    "REPORT_QUALITY_AGENT_DOMAIN": "0",
                    "REPORT_QUALITY_AGENT_SOURCE": "llm",
                    "REPORT_QUALITY_AGENT_TODOS_PATH": str(p),
                },
                clear=False,
            ):
                r = maybe_run_report_quality_agent_after_success(
                    "<b>ok</b>", gate_passed=True, validation_result={"valid": True}
                )
            self.assertIsNotNone(r)
            self.assertTrue(r.get("below_threshold"))
            self.assertTrue(r.get("todos_written"))
            text = p.read_text(encoding="utf-8")
            self.assertIn("weak headline", text)
            self.assertIn("下一批隊列", text)

    @patch("report_quality_agent.llm_quality_judge")
    def test_no_write_when_score_ok(self, mock_llm):
        mock_llm.return_value = {
            "pass": True,
            "overall_score": 95.0,
            "rubric": {},
            "reasons": [],
            "raw_error": None,
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "TODOS.md"
            original = "# X\n\n## 下一批隊列\n\n"
            p.write_text(original, encoding="utf-8")
            with patch.dict(
                "os.environ",
                {
                    "REPORT_QUALITY_AGENT": "1",
                    "REPORT_QUALITY_AGENT_COMPOSITE_MIN": "70",
                    "REPORT_QUALITY_AGENT_SOURCE": "llm",
                    "REPORT_QUALITY_AGENT_TODOS_PATH": str(p),
                },
                clear=False,
            ):
                r = maybe_run_report_quality_agent_after_success(
                    "<b>ok</b>", gate_passed=True, validation_result={"valid": True}
                )
            self.assertIsNotNone(r)
            self.assertFalse(r.get("below_threshold"))
            self.assertEqual(p.read_text(encoding="utf-8"), original)


class TestAppendQualityFollowup(unittest.TestCase):
    def test_append_bullets(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "T.md"
            p.write_text("## 下一批隊列\n\n", encoding="utf-8")
            ok = append_quality_followup_todos(
                p, score=50.0, score_label="llm", items=["do a", "do b"], max_block_lines=20
            )
            self.assertTrue(ok)
            t = p.read_text(encoding="utf-8")
            self.assertIn("do a", t)
            self.assertIn("品質分 50.0", t)


if __name__ == "__main__":
    unittest.main()
