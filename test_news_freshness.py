"""專項測試：新聞新鮮度 Gate（STRICT_NEWS_FRESHNESS_GATE 等）。"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from report_html_gates import _check_news_freshness


def _news_line(date_part: str, body: str = "摘要") -> str:
    return f"〔新聞 1〕{body} [{date_part} UTC+8]"


@pytest.mark.smoke
def test_news_freshness_gate_off_allows_stale():
    text = _news_line("2025-03-01 12:00")
    ref = datetime(2025, 3, 25, 12, 0, tzinfo=timezone.utc)
    with patch.dict(os.environ, {"STRICT_NEWS_FRESHNESS_GATE": "0"}, clear=False):
        ok, err = _check_news_freshness(text, report_dt=ref)
    assert ok is True
    assert err == ""


@pytest.mark.smoke
def test_news_freshness_within_window_passes():
    text = _news_line("2025-03-24 14:00")
    ref = datetime(2025, 3, 25, 12, 0, tzinfo=timezone.utc)
    with patch.dict(
        os.environ,
        {"STRICT_NEWS_FRESHNESS_GATE": "1", "NEWS_FRESHNESS_WINDOW_HOURS": "36"},
        clear=False,
    ):
        ok, err = _check_news_freshness(text, report_dt=ref)
    assert ok is True
    assert err == ""


@pytest.mark.smoke
def test_news_freshness_stale_fails():
    text = _news_line("2025-03-01 12:00")
    ref = datetime(2025, 3, 25, 12, 0, tzinfo=timezone.utc)
    with patch.dict(
        os.environ,
        {"STRICT_NEWS_FRESHNESS_GATE": "1", "NEWS_FRESHNESS_WINDOW_HOURS": "36"},
        clear=False,
    ):
        ok, err = _check_news_freshness(text, report_dt=ref)
    assert ok is False
    assert "新聞新鮮度" in err


@pytest.mark.smoke
def test_news_freshness_whitelist_skips_stale_line():
    text = "〔新聞 1〕FRED 數據 [2025-03-01 12:00 UTC+8]"
    ref = datetime(2025, 3, 25, 12, 0, tzinfo=timezone.utc)
    with patch.dict(
        os.environ,
        {
            "STRICT_NEWS_FRESHNESS_GATE": "1",
            "NEWS_FRESHNESS_WINDOW_HOURS": "36",
            "NEWS_FRESHNESS_SOURCE_WHITELIST": "FRED",
        },
        clear=False,
    ):
        ok, err = _check_news_freshness(text, report_dt=ref)
    assert ok is True
    assert err == ""


@pytest.mark.smoke
def test_news_freshness_no_parseable_timestamps_passes():
    text = "〔新聞 1〕僅敘述無時間括號"
    ref = datetime(2025, 3, 25, 12, 0, tzinfo=timezone.utc)
    with patch.dict(os.environ, {"STRICT_NEWS_FRESHNESS_GATE": "1"}, clear=False):
        ok, err = _check_news_freshness(text, report_dt=ref)
    assert ok is True
    assert err == ""
