"""TradingView MCP bridge: optional repo-side wrapper with mock and yfinance fallback."""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
from typing import Any

from crewai.tools import tool

from tools.base import load_mock_json, mock_apis_enabled

logger = logging.getLogger(__name__)


def tradingview_mcp_enabled() -> bool:
    return os.getenv("TRADINGVIEW_MCP_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def _fallback_yfinance(symbol: str, reason: str) -> str:
    if os.getenv("TRADINGVIEW_FALLBACK_YFINANCE", "1").strip().lower() not in ("1", "true", "yes"):
        return f"[DATA_MISSING:tradingview_{reason}]"
    try:
        from tools_legacy import multi_timeframe_tool

        runner = getattr(multi_timeframe_tool, "run", None)
        out = runner(symbol) if callable(runner) else multi_timeframe_tool(symbol)
        return f"【TradingView fallback:yfinance】{out}"
    except Exception as exc:
        return f"[DATA_MISSING:tradingview_{reason}] yfinance fallback failed: {exc}"


def _format_snapshot(data: Any, symbol: str) -> str:
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, dict):
        return ""
    if isinstance(data.get("symbols"), dict):
        data = data["symbols"].get(symbol.upper()) or data["symbols"].get(symbol) or {}
    if not isinstance(data, dict):
        return ""
    if data.get("summary"):
        return str(data["summary"]).strip()
    fields = {
        "symbol": data.get("symbol") or symbol.upper(),
        "timeframe": data.get("timeframe") or data.get("interval"),
        "signal": data.get("signal") or data.get("recommendation"),
        "price": data.get("price") or data.get("close"),
        "source": data.get("source") or "TradingView MCP",
    }
    bits = [f"{k}={v}" for k, v in fields.items() if v not in (None, "")]
    return "【TradingView snapshot】" + " | ".join(bits) if bits else ""


def tradingview_summary(symbol: str = "BTC") -> str:
    """Return TradingView snapshot text, using fixture or fallback when MCP is unavailable."""
    clean = (symbol or "BTC").strip().upper().strip("$")
    if not clean:
        return "[DATA_MISSING:tradingview_symbol]"

    if mock_apis_enabled():
        mocked = _format_snapshot(load_mock_json("tradingview.json"), clean)
        return mocked or "[DATA_MISSING:tradingview_mock_fixture]"

    if not tradingview_mcp_enabled():
        return _fallback_yfinance(clean, "disabled")

    command = os.getenv("TRADINGVIEW_MCP_COMMAND", "").strip()
    if not command:
        return _fallback_yfinance(clean, "command_missing")

    timeout = float(os.getenv("TRADINGVIEW_TIMEOUT_SEC", "8") or "8")
    try:
        completed = subprocess.run(
            [*shlex.split(command), clean],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        logger.warning("TradingView MCP command failed: %s", exc)
        return _fallback_yfinance(clean, "command_failed")

    stdout = (completed.stdout or "").strip()
    if completed.returncode != 0 or not stdout:
        logger.warning("TradingView MCP command returned %s: %s", completed.returncode, completed.stderr)
        return _fallback_yfinance(clean, "command_failed")
    try:
        parsed = json.loads(stdout)
        formatted = _format_snapshot(parsed, clean)
        return formatted or stdout[:4000]
    except json.JSONDecodeError:
        return stdout[:4000]


@tool
def tradingview_snapshot_tool(symbol: str = "BTC") -> str:
    """Optional TradingView chart/technical snapshot; never the only price source."""
    return tradingview_summary(symbol)
