"""Tests for optional earnings-day exclusion injection."""

from __future__ import annotations

from datetime import date

import pytest

import earnings_focus


@pytest.mark.smoke
def test_earnings_focus_exclusion_block_empty():
    assert earnings_focus.earnings_focus_exclusion_block([]) == ""


@pytest.mark.smoke
def test_earnings_focus_exclusion_block_nonempty():
    b = earnings_focus.earnings_focus_exclusion_block(["NVDA", "MSFT"])
    assert "NVDA" in b and "MSFT" in b
    assert "financial_datasets_tool" in b
    assert "季報" in b


@pytest.mark.smoke
def test_maybe_prepend_when_disabled(monkeypatch):
    monkeypatch.delenv("EARNINGS_FOCUS_MODE", raising=False)
    monkeypatch.setattr(earnings_focus, "pipeline_anchor_date", lambda: date(2026, 4, 8))
    assert earnings_focus.maybe_prepend_earnings_focus_exclusion("base") == "base"


@pytest.mark.smoke
def test_maybe_prepend_when_enabled_and_tickers(monkeypatch):
    monkeypatch.setenv("EARNINGS_FOCUS_MODE", "1")
    monkeypatch.setattr(earnings_focus, "pipeline_anchor_date", lambda: date(2026, 4, 8))
    monkeypatch.setattr(earnings_focus, "earnings_focus_tickers_today", lambda: ["NVDA"])
    out = earnings_focus.maybe_prepend_earnings_focus_exclusion("prev")
    assert "財報聚焦日" in out
    assert "NVDA" in out
    assert "prev" in out


@pytest.mark.smoke
def test_weekend_prepends_forecast_without_focus_mode(monkeypatch):
    monkeypatch.delenv("EARNINGS_FOCUS_MODE", raising=False)
    monkeypatch.setattr(earnings_focus, "pipeline_anchor_date", lambda: date(2026, 4, 11))
    monkeypatch.setattr(
        earnings_focus,
        "tickers_with_earnings_between",
        lambda *_a, **_k: [("NVDA", date(2026, 4, 15))],
    )
    out = earnings_focus.maybe_prepend_earnings_focus_exclusion("tail")
    assert "下週財報預告" in out
    assert "週末" in out
    assert "NVDA" in out
    assert "tail" in out


@pytest.mark.smoke
def test_friday_prepends_forecast_without_focus_mode(monkeypatch):
    monkeypatch.delenv("EARNINGS_FOCUS_MODE", raising=False)
    monkeypatch.setattr(earnings_focus, "pipeline_anchor_date", lambda: date(2026, 4, 10))
    monkeypatch.setattr(
        earnings_focus,
        "tickers_with_earnings_between",
        lambda *_a, **_k: [("MSFT", date(2026, 4, 14))],
    )
    out = earnings_focus.maybe_prepend_earnings_focus_exclusion("z")
    assert "下週財報預告" in out
    assert "週五" in out
    assert "MSFT" in out


@pytest.mark.smoke
def test_earnings_focus_block_mentions_premarket_afterhours():
    b = earnings_focus.earnings_focus_exclusion_block(["AAPL"])
    assert "盤前" in b and "盤後" in b
