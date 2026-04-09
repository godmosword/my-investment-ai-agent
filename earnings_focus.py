"""Earnings-day focus for the daily pipeline (AI / mega-cap tech watchlist).

When enabled, detects tickers whose yfinance earnings calendar falls on the
pipeline anchor date and injects exclusion context so crews pull quarterly
fundamentals and center news on verified figures (no hallucination).
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Final

logger = logging.getLogger(__name__)

# Keep in sync with tools_legacy._EARNINGS_WATCHLIST (macro_context_tool).
EARNINGS_FOCUS_WATCHLIST: Final[tuple[str, ...]] = (
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


def _pipeline_anchor_date() -> date:
    """Match PIPELINE_REPORT_DATE when set; else UTC calendar date."""
    raw = (os.getenv("PIPELINE_REPORT_DATE") or "").strip()
    if len(raw) >= 10:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    return datetime.now(timezone.utc).date()


def earnings_focus_tickers_today() -> list[str]:
    """Return watchlist tickers with yfinance calendar earnings on anchor date."""
    anchor = _pipeline_anchor_date()
    out: list[str] = []
    try:
        import yfinance as yf  # noqa: PLC0415
    except Exception as exc:
        logger.warning("earnings_focus: yfinance import failed: %s", exc)
        return out

    for ticker_sym in EARNINGS_FOCUS_WATCHLIST:
        try:
            t = yf.Ticker(ticker_sym)
            cal = t.calendar
            if cal is None:
                continue
            if hasattr(cal, "get"):
                ed = cal.get("Earnings Date")
            elif hasattr(cal, "iloc"):
                ed = cal.iloc[0].get("Earnings Date") if not cal.empty else None
            else:
                ed = None
            if ed is None:
                continue
            dates = ed if isinstance(ed, list) else [ed]
            for d in dates:
                try:
                    ed_date = d.date() if hasattr(d, "date") else None
                    if ed_date == anchor:
                        out.append(ticker_sym)
                        break
                except (TypeError, ValueError, AttributeError) as ed_e:
                    logger.debug("earnings_focus date parse %s: %s", ticker_sym, ed_e)
        except Exception as e:
            logger.warning("earnings_focus calendar %s: %s", ticker_sym, e)
            continue
    return sorted(set(out))


def earnings_focus_exclusion_block(tickers: list[str]) -> str:
    """Human + model instructions appended to exclude_context."""
    if not tickers:
        return ""
    joined = ", ".join(tickers)
    return (
        "【財報聚焦日】以下美股於本輪錨定日之 yfinance 財報日曆為「公告日」："
        f"<code>{joined}</code>。\n"
        "· AI 段（強制）：對上列**每一檔**必呼叫 <code>financial_datasets_tool('TICKER:quarterly')</code>；"
        "儀表板須含**季報口徑**之營收／同比%（或工具回傳之最近一季欄位），label 仍須含 FinancialDatasets 與代號。\n"
        "· 區塊② 至少 **1 則**新聞須以該檔**財報／法說／指引**為主線；"
        "<code>investment_takeaway</code> 之數字**僅能**複述本輪工具已列讀值（含季報工具與 yfinance 族群列），禁止臆測 EPS 或「beat/miss」除非新聞來源已明確報導且可對照工具。\n"
        "· 區塊④／QSREC：須與財報催化**一致**（方向、觀望理由、或明確寫「財報後待指引明朗」）；不得與工具數字矛盾。\n"
        "· 加密段：不得虛構上列美股財報數字；跨資產連結僅在有因果鏈時一句帶過，主線仍為加密工具讀值。\n"
    )


def maybe_prepend_earnings_focus_exclusion(existing: str | None) -> str | None:
    """If EARNINGS_FOCUS_MODE is on and tickers match today, prepend focus block."""
    mode = (os.getenv("EARNINGS_FOCUS_MODE") or "").strip().lower()
    if mode not in ("1", "true", "yes", "auto"):
        return existing
    tickers = earnings_focus_tickers_today()
    if not tickers:
        return existing
    block = earnings_focus_exclusion_block(tickers)
    base = (existing or "").strip()
    if base:
        return f"{block}\n\n{base}"
    return block
