"""Boundary tests for main pipeline dual-crew execution (failure before assembly)."""

from __future__ import annotations

import concurrent.futures
import os
import unittest
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.boundary

_real_thread_pool_executor = concurrent.futures.ThreadPoolExecutor


class _CryptoFailExecutor:
    """Stub ThreadPoolExecutor: first future.result() raises (crypto leg), second never runs."""

    def __init__(self, max_workers: int = 2) -> None:
        self._slot = 0

    def __enter__(self) -> _CryptoFailExecutor:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def submit(self, fn):  # noqa: ANN001
        slot = self._slot
        self._slot += 1

        class _Fut:
            def result(self_inner, timeout=None):  # noqa: ANN001
                if slot == 0:
                    raise RuntimeError("crypto_crew_failed")
                return fn()

        return _Fut()


class _ThreadPoolExecutorSelective:
    """Only the dual-crew pool (max_workers=2) uses the failure stub; prewarm keeps the real executor."""

    def __new__(cls, max_workers: int = 5):  # noqa: ANN004
        if max_workers == 2:
            return _CryptoFailExecutor()
        return _real_thread_pool_executor(max_workers=max_workers)


def _patch_dual_crew_pool() -> patch:
    return patch.object(concurrent.futures, "ThreadPoolExecutor", _ThreadPoolExecutorSelective)


@patch.dict(os.environ, {"SKIP_BIGQUERY": "1"}, clear=False)
@patch("main.get_recent_lessons", return_value="{}")
@patch("tools.regime_scorecard_tool")
@patch("main.get_realtime_quotes", return_value="")
@patch("main._prewarm_tool_caches")
@_patch_dual_crew_pool()
class TestRunPipelineOnceDualCrewFailure(unittest.TestCase):
    def test_crypto_future_raises_returns_empty_html_and_error(
        self,
        _mock_prewarm: MagicMock,
        _mock_quotes: MagicMock,
        mock_scorecard: MagicMock,
        _mock_lessons: MagicMock,
    ) -> None:
        mock_scorecard.run.return_value = "【今日市場模式】 risk_on"
        import main as main_mod

        html, err, model = main_mod._run_pipeline_once(None)
        self.assertEqual(html, "")
        self.assertIsInstance(err, RuntimeError)
        self.assertIn("crypto_crew_failed", str(err))
        self.assertIsNone(model)


@patch.dict(os.environ, {"SKIP_BIGQUERY": "1", "SCRATCHPAD_ENABLED": "0"}, clear=False)
@patch("main.write_llm_run_log")
@patch("main.get_recent_lessons", return_value="{}")
@patch("tools.regime_scorecard_tool")
@patch("main.get_realtime_quotes", return_value="")
@patch("main._prewarm_tool_caches")
@_patch_dual_crew_pool()
class TestRunPipelineWithRetriesCryptoFailureFinalize(unittest.TestCase):
    """Scratchpad disabled: still assert finalize_run would record execution_error_report via spy."""

    def test_crypto_failure_finalizes_as_execution_error_report(
        self,
        _mock_prewarm: MagicMock,
        _mock_quotes: MagicMock,
        mock_scorecard: MagicMock,
        _mock_lessons: MagicMock,
        _mock_llm_log: MagicMock,
    ) -> None:
        mock_scorecard.run.return_value = "【今日市場模式】 risk_on"
        import main as main_mod

        finalize_calls: list[tuple[str, dict | None]] = []

        def _capture_finalize(status: str, extra: dict | None = None) -> None:
            finalize_calls.append((status, extra))

        with patch("scratchpad.finalize_run", side_effect=_capture_finalize):
            final_html, report_valid, _last_val = main_mod.run_pipeline_with_retries(None)

        self.assertTrue(final_html.startswith("🚨"))
        self.assertFalse(report_valid)
        statuses = [s for s, _ in finalize_calls]
        self.assertIn("execution_error_report", statuses)
