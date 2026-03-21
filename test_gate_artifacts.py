"""Gate 失敗時本機 artifacts 與 Telegram follow-up 訊息格式。"""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from main import (
    GATE_CODE_CRITICAL_SOURCE,
    _format_gate_issues_followup_messages,
    _gate_alert_severity_and_code,
    _persist_gate_validation_failure,
)


class TestGateIssuesFollowup(unittest.TestCase):
    def test_chunks_when_many_issues(self):
        issues = [f"issue number {i} " + ("x" * 200) for i in range(20)]
        chunks = _format_gate_issues_followup_messages(issues)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c) <= 4000 for c in chunks))
        self.assertIn("issue number 1", chunks[0])
        self.assertIn("共 20 項", chunks[0])


class TestPersistGateFailure(unittest.TestCase):
    def test_writes_files_under_env_dir(self):
        root = Path(__file__).resolve().parent / ".pytest_gate_fail_tmp"
        root.mkdir(exist_ok=True)
        try:
            with patch.dict(
                os.environ,
                {"GATE_FAILURE_ARTIFACT_DIR": str(root), "GATE_FAILURE_ARTIFACTS": "1"},
                clear=False,
            ):
                # re-read dir from env each call
                p = _persist_gate_validation_failure(
                    "<b>draft</b> report body",
                    {"valid": False, "issues": ["a", "b"]},
                )
            self.assertIsNotNone(p)
            self.assertTrue((p / "draft_report.txt").is_file())
            self.assertTrue((p / "issues.txt").is_file())
            self.assertTrue((p / "validation_summary.json").is_file())
            data = json.loads((p / "validation_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(data["issue_count"], 2)
            self.assertEqual(data["issues"], ["a", "b"])
        finally:
            for f in root.glob("**/*"):
                if f.is_file():
                    f.unlink()
            for d in sorted(root.glob("**/*"), reverse=True):
                if d.is_dir():
                    try:
                        d.rmdir()
                    except OSError:
                        pass
            try:
                root.rmdir()
            except OSError:
                pass


class TestGateAlertSeverity(unittest.TestCase):
    def test_critical_when_critical_missing_in_full_list(self):
        sev, code = _gate_alert_severity_and_code(
            "",
            None,
            all_issues_list=["x", "關鍵資料來源缺失（hard fail）"],
        )
        self.assertEqual(sev, "CRITICAL")
        self.assertEqual(code, GATE_CODE_CRITICAL_SOURCE)


if __name__ == "__main__":
    unittest.main()
