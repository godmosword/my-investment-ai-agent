"""Shared US mega-cap / AI tech earnings watchlist and pipeline anchor date.

Used by ``macro_context_tool``, ``earnings_focus``, and weekend forecast injection.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Final

logger = logging.getLogger(__name__)

# 大型科技／AI 供應鏈 — 財報日曆與 macro_context「本週財報」掃描用（yfinance）。
# 與 crew `financial_datasets` watchlist（NVDA/MSFT/AAPL…）重疊但非完全一致；擴名單請同步 crew 與文件。
MEGA_CAP_TECH_EARNINGS_TICKERS: Final[tuple[str, ...]] = (
    "NVDA",
    "AMD",
    "MSFT",
    "GOOGL",
    "AAPL",
    "META",
    "AMZN",
    "TSM",
    "AVGO",
    "ARM",
)


def pipeline_anchor_date() -> date:
    """Report anchor: ``PIPELINE_REPORT_DATE`` (YYYY-MM-DD) if set, else UTC today."""
    raw = (os.getenv("PIPELINE_REPORT_DATE") or "").strip()
    if len(raw) >= 10:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def next_monday_sunday_after_weekend(anchor: date) -> tuple[date, date] | None:
    """If anchor is Saturday or Sunday, return (next Monday, that week's Sunday)."""
    wd = anchor.weekday()  # Mon=0 .. Sun=6
    if wd not in (5, 6):
        return None
    # Sat → +2, Sun → +1
    days_to_mon = 2 if wd == 5 else 1
    monday = anchor + timedelta(days=days_to_mon)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def week_range_containing(d: date) -> tuple[date, date]:
    """Monday–Sunday calendar week containing ``d`` (UTC anchor semantics)."""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def yf_earnings_calendar_dates(ticker_sym: str) -> list[date]:
    """Earnings dates from yfinance ``Ticker.calendar`` (may omit pre/post session)."""
    out: list[date] = []
    try:
        import yfinance as yf  # noqa: PLC0415
    except Exception as exc:
        logger.warning("yf_earnings_calendar_dates: yfinance import failed: %s", exc)
        return out
    try:
        t = yf.Ticker(ticker_sym)
        cal = t.calendar
        if cal is None:
            return out
        if hasattr(cal, "get"):
            ed = cal.get("Earnings Date")
        elif hasattr(cal, "iloc"):
            ed = cal.iloc[0].get("Earnings Date") if not cal.empty else None
        else:
            ed = None
        if ed is None:
            return out
        dates = ed if isinstance(ed, list) else [ed]
        for d in dates:
            try:
                ed_date = d.date() if hasattr(d, "date") else None
                if ed_date:
                    out.append(ed_date)
            except (TypeError, ValueError, AttributeError):
                continue
    except Exception as e:
        logger.warning("yf_earnings_calendar_dates %s: %s", ticker_sym, e)
    return sorted(set(out))


def tickers_with_earnings_between(
    tickers: tuple[str, ...],
    start: date,
    end: date,
) -> list[tuple[str, date]]:
    """Pairs (ticker, earnings_date) with calendar date in [start, end], sorted by date then ticker."""
    pairs: list[tuple[str, date]] = []
    for sym in tickers:
        for ed in yf_earnings_calendar_dates(sym):
            if start <= ed <= end:
                pairs.append((sym, ed))
                break
    pairs.sort(key=lambda x: (x[1], x[0]))
    return pairs
