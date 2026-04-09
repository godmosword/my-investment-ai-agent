"""Tests for optional earnings-day exclusion injection."""

from __future__ import annotations

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
    assert earnings_focus.maybe_prepend_earnings_focus_exclusion("base") == "base"


@pytest.mark.smoke
def test_maybe_prepend_when_enabled_and_tickers(monkeypatch):
    monkeypatch.setenv("EARNINGS_FOCUS_MODE", "1")
    monkeypatch.setattr(earnings_focus, "earnings_focus_tickers_today", lambda: ["NVDA"])
    out = earnings_focus.maybe_prepend_earnings_focus_exclusion("prev")
    assert "財報聚焦日" in out
    assert "NVDA" in out
    assert "prev" in out
