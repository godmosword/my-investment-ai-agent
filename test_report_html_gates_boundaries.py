"""Boundary tests for report_html_gates thresholds (equity pick length, DATA_MISSING cap).

Complements test_validate_report.py rotation score_gap 11/12 cases.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from report_html_gates import (
    _data_missing_count_gate_max,
    _pick_justification_equity_ok,
    _pick_rotation_override_min_gap,
)
from main import validate_report
from test_validate_report import _make_report


class TestEquityPickReasonLengthBoundaries(unittest.TestCase):
    """_pick_justification_equity_ok: len < 38 short-circuit; 80-char branch with 1 keyword."""

    def setUp(self) -> None:
        self.recs = [{"asset": "NVDA", "category": "EQUITY"}]

    def _report(self, reason_body: str) -> str:
        old = (
            "本日選擇理由：NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。"
        )
        return _make_report().replace(old, "本日選擇理由：" + reason_body)

    def test_len_37_fails_short_message_even_with_two_keywords(self) -> None:
        body = "NVDA財報GPU" + "敘" * (37 - len("NVDA財報GPU"))
        self.assertEqual(len(body), 37)
        ok, err = _pick_justification_equity_ok(self._report(body), self.recs)
        self.assertFalse(ok)
        self.assertIn("過短", err)

    def test_len_38_two_keywords_passes(self) -> None:
        body = "NVDA財報GPU" + "敘" * (37 - len("NVDA財報GPU")) + "X"
        self.assertEqual(len(body), 38)
        ok, err = _pick_justification_equity_ok(self._report(body), self.recs)
        self.assertTrue(ok, err)

    def test_len_79_one_keyword_named_fails_dynamic(self) -> None:
        body = "NVDA財報" + "補" * (79 - len("NVDA財報"))
        self.assertEqual(len(body), 79)
        ok, err = _pick_justification_equity_ok(self._report(body), self.recs)
        self.assertFalse(ok)
        self.assertIn("未達動態選股標準", err)

    def test_len_80_one_keyword_named_passes(self) -> None:
        body = "NVDA財報" + "補" * (80 - len("NVDA財報"))
        self.assertEqual(len(body), 80)
        ok, err = _pick_justification_equity_ok(self._report(body), self.recs)
        self.assertTrue(ok, err)


class TestPickRotationOverrideMinGap(unittest.TestCase):
    def test_default_min_gap_is_twelve(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            # If env unset, implementation reads default "12"
            os.environ.pop("PICK_ROTATION_OVERRIDE_MIN_GAP", None)
            self.assertEqual(_pick_rotation_override_min_gap(), 12.0)

    def test_env_override_parses_float(self) -> None:
        with patch.dict(os.environ, {"PICK_ROTATION_OVERRIDE_MIN_GAP": "15.5"}, clear=False):
            self.assertEqual(_pick_rotation_override_min_gap(), 15.5)


class TestDataMissingCountGate(unittest.TestCase):
    def test_validate_report_blocks_when_tags_exceed_max(self) -> None:
        base = Path("tests/fixtures/reports/valid_full/report.txt").read_text(encoding="utf-8")
        injected = base + "\n[DATA_MISSING:metric_a][DATA_MISSING:metric_b]"
        env_patch = {
            "SKIP_BIGQUERY": "1",
            "STRICT_NEWS_FRESHNESS_GATE": "0",
            "PIPELINE_REPORT_DATE": "",
            "STRICT_EXEC_SUMMARY_HTML_GATE": "0",
            "STRICT_TOOL_EVIDENCE_GATE": "0",
            "PICK_ROLLING_FREQ_GATE": "0",
            "STRICT_MACRO_CONFLICT_GATE": "0",
            "DATA_MISSING_COUNT_GATE_MAX": "1",
        }
        with patch.dict(os.environ, env_patch, clear=False):
            result = validate_report(injected)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("資料缺失標記過多" in i for i in result["blocking_issues"]),
            result["blocking_issues"],
        )


class TestDataMissingGateMaxHelper(unittest.TestCase):
    def test_zero_disables_gate(self) -> None:
        with patch.dict(os.environ, {"DATA_MISSING_COUNT_GATE_MAX": "0"}, clear=False):
            self.assertEqual(_data_missing_count_gate_max(), 0)

    def test_positive_parsed(self) -> None:
        with patch.dict(os.environ, {"DATA_MISSING_COUNT_GATE_MAX": "3"}, clear=False):
            self.assertEqual(_data_missing_count_gate_max(), 3)
