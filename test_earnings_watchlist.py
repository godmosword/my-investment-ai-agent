"""Unit tests for shared earnings watchlist helpers (no network)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from earnings_watchlist import (
    next_monday_sunday_after_weekend,
    pipeline_anchor_date,
    week_range_containing,
)


@pytest.mark.smoke
def test_week_range_containing_monday():
    d = date(2026, 4, 13)  # Monday
    a, b = week_range_containing(d)
    assert a.weekday() == 0
    assert b == a + timedelta(days=6)


@pytest.mark.smoke
def test_next_monday_sunday_saturday():
    sat = date(2026, 4, 11)
    span = next_monday_sunday_after_weekend(sat)
    assert span is not None
    mon, sun = span
    assert mon == date(2026, 4, 13)
    assert sun == date(2026, 4, 19)


@pytest.mark.smoke
def test_next_monday_sunday_sunday():
    sun = date(2026, 4, 12)
    span = next_monday_sunday_after_weekend(sun)
    assert span is not None
    mon, _ = span
    assert mon == date(2026, 4, 13)


@pytest.mark.smoke
def test_next_monday_sunday_weekday_none():
    assert next_monday_sunday_after_weekend(date(2026, 4, 8)) is None


@pytest.mark.smoke
def test_pipeline_anchor_date_from_env(monkeypatch):
    monkeypatch.setenv("PIPELINE_REPORT_DATE", "2026-05-01")
    assert pipeline_anchor_date().isoformat() == "2026-05-01"
