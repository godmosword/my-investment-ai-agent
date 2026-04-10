"""LangChain-compatible tool bridge for LangGraph deep research.

Wraps Q-Silicon legacy ``tools`` callables (CrewAI ``@tool`` / ``.run``) so
``ChatOpenAI.bind_tools`` can execute real API fetches during deep_research_node.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from tools import (
    coinglass_data_tool,
    financial_datasets_tool,
    newsapi_tool,
    prediction_markets_tool,
)

logger = logging.getLogger(__name__)


def _run_legacy_tool(tool_obj: Any, *args: Any, **kwargs: Any) -> str:
    try:
        runner = getattr(tool_obj, "run", None)
        if callable(runner):
            out = runner(*args, **kwargs)
        elif callable(tool_obj):
            out = tool_obj(*args, **kwargs)
        else:
            return "[DATA_MISSING:tool_not_callable]"
        return out if isinstance(out, str) else str(out)
    except Exception as exc:  # pragma: no cover - defensive
        return f"[DATA_MISSING:{exc}]"


@tool
def fetch_crypto_derivatives(metric: str) -> str:
    """取得加密貨幣衍生品與清算數據。

    支援的 metric 包含: 'funding_rate' (資金費率), 'liquidations' (爆倉/清算數據),
    'long_short_ratio' (多空比), 'open_interest' (未平倉), 'options_info'（選擇權）。
    可使用 'metric:SYMBOL'（例如 'funding_rate:ETH'），預設 BTC。
    當主編要求確認市場槓桿或爆倉狀況時使用。
    """
    logger.info("[Tool Call] fetch_crypto_derivatives: %s", metric)
    return _run_legacy_tool(coinglass_data_tool, metric)


@tool
def fetch_us_equity_financials(ticker: str) -> str:
    """取得美股的即時財報摘要與基本面數據。

    傳入美股代號 (如 'NVDA', 'MSFT')，或 'watchlist' 一次查多檔；
    亦可 'NVDA:quarterly' 指定季報。
    """
    logger.info("[Tool Call] fetch_us_equity_financials: %s", ticker)
    q = (ticker or "").strip() or "watchlist"
    return _run_legacy_tool(financial_datasets_tool, q)


@tool
def fetch_latest_news(query: str) -> str:
    """搜尋與特定關鍵字相關的最新金融/加密貨幣新聞。

    傳入關鍵字 (如 'Bitcoin ETF flow', 'AI Data Center')。
    """
    logger.info("[Tool Call] fetch_latest_news: %s", query)
    return _run_legacy_tool(newsapi_tool, query)


@tool
def fetch_prediction_market_hot_events(query: str = "") -> str:
    """取得 Polymarket 等平台之預測市場熱門二元事件（Yes 隱含機率、成交量級）。

    query 可留空。僅能複述回傳列，禁止自行推算機率。
    """
    logger.info("[Tool Call] fetch_prediction_market_hot_events: %s", query or "(default)")
    return _run_legacy_tool(prediction_markets_tool, query or "")


RESEARCH_TOOLS = [
    fetch_crypto_derivatives,
    fetch_us_equity_financials,
    fetch_latest_news,
    fetch_prediction_market_hot_events,
]
