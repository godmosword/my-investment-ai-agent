"""Earnings-day focus for the daily pipeline (AI / mega-cap tech watchlist).

When enabled, detects tickers whose yfinance earnings calendar falls on the
pipeline anchor date and injects exclusion context so crews pull quarterly
fundamentals and center news on verified figures (no hallucination).

Weekend runs (anchor Sat/Sun) prepend a **next-week earnings forecast** block.
"""

from __future__ import annotations

import logging
import os
from typing import Final

from earnings_watchlist import (
    MEGA_CAP_TECH_EARNINGS_TICKERS,
    next_monday_sunday_after_weekend,
    pipeline_anchor_date,
    tickers_with_earnings_between,
)

logger = logging.getLogger(__name__)

# Back-compat alias for imports / docs
EARNINGS_FOCUS_WATCHLIST: Final[tuple[str, ...]] = MEGA_CAP_TECH_EARNINGS_TICKERS


def earnings_focus_tickers_today() -> list[str]:
    """Return watchlist tickers with yfinance calendar earnings on anchor date."""
    anchor = pipeline_anchor_date()
    pairs = tickers_with_earnings_between(MEGA_CAP_TECH_EARNINGS_TICKERS, anchor, anchor)
    return [sym for sym, _ in pairs]


def weekend_next_week_earnings_forecast_block() -> str:
    """Sat/Sun anchor: inject next Mon–Sun watchlist earnings schedule."""
    anchor = pipeline_anchor_date()
    span = next_monday_sunday_after_weekend(anchor)
    if span is None:
        return ""
    monday, sunday = span
    pairs = tickers_with_earnings_between(MEGA_CAP_TECH_EARNINGS_TICKERS, monday, sunday)
    if not pairs:
        sched = "（watchlist 內 yfinance 日曆未顯示下週已排程日期；仍以 macro_context 與新聞交叉驗證。）"
    else:
        sched = " · ".join(f"{sym} {ed.strftime('%m/%d')}" for sym, ed in pairs)
    return (
        "【下週財報預告】錨定日為週末；以下為 **下一完整曆週**（"
        f"{monday.strftime('%m/%d')}（一）–{sunday.strftime('%m/%d')}（日））"
        f" watchlist 之 yfinance 財報日：<code>{sched}</code>\n"
        "· AI 段：於【近端事件日曆】或宏觀銜接至少 **1 行**摘錄上表；"
        "若實際發佈落在盤前／盤後，須以新聞時間戳與工具讀值區分「已發／待發」。\n"
        "· 週一開盤前日報可再開 **EARNINGS_FOCUS_MODE** 觸發【財報聚焦日】深化季報工具。\n"
    )


def earnings_focus_exclusion_block(tickers: list[str]) -> str:
    """Human + model instructions appended to exclude_context."""
    if not tickers:
        return ""
    joined = ", ".join(tickers)
    return (
        "【財報聚焦日】以下美股於本輪**錨定日**之 yfinance 財報日曆為「公告日」（"
        "通常對應美東當日；**實際發佈可能在盤前或盤後**——須以新聞來源時間與公司 IR 為準，"
        "不可假設一律盤後）："
        f"<code>{joined}</code>。\n"
        "· **盤前／盤後**：若新聞已載明 Before market open／After market close／美東時段，"
        "標題或 timestamp_line 須可讀出時段；投資解讀須區分「數字已出」vs「僅日曆、待發佈」。\n"
        "· AI 段（強制）：對上列**每一檔**必呼叫 <code>financial_datasets_tool('TICKER:quarterly')</code>；"
        "儀表板須含**季報口徑**之營收／同比%（或工具回傳之最近一季欄位），label 仍須含 FinancialDatasets 與代號。\n"
        "· 區塊② 至少 **1 則**新聞須以該檔**財報／法說／指引**為主線；"
        "<code>investment_takeaway</code> 之數字**僅能**複述本輪工具已列讀值（含季報工具與 yfinance 族群列），"
        "禁止臆測 EPS 或「beat/miss」除非新聞來源已明確報導且可對照工具。\n"
        "· 區塊④／QSREC：須與財報催化**一致**（方向、觀望理由、或明確寫「財報後待指引明朗」）；不得與工具數字矛盾。\n"
        "· 加密段：不得虛構上列美股財報數字；跨資產連結僅在有因果鏈時一句帶過，主線仍為加密工具讀值。\n"
    )


def maybe_prepend_earnings_focus_exclusion(existing: str | None) -> str | None:
    """Prepend weekend forecast and/or earnings-day focus per env."""
    mode = (os.getenv("EARNINGS_FOCUS_MODE") or "").strip().lower()
    base = (existing or "").strip()

    parts: list[str] = []
    wk = weekend_next_week_earnings_forecast_block()
    if wk:
        parts.append(wk.strip())

    if mode in ("1", "true", "yes", "auto"):
        tickers = earnings_focus_tickers_today()
        if tickers:
            parts.append(earnings_focus_exclusion_block(tickers).strip())
        elif mode in ("1", "true", "yes") and not tickers:
            logger.info(
                "EARNINGS_FOCUS_MODE=%s but no watchlist earnings on anchor %s",
                mode,
                pipeline_anchor_date(),
            )

    if not parts:
        return existing
    block = "\n\n".join(parts)
    if base:
        return f"{block}\n\n{base}"
    return block
