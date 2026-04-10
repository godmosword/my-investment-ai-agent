"""Tiered US equity universe from ``assets_config.json`` (core vs extended).

Core tickers get full FinancialDatasets + yfinance coverage in batch ``watchlist`` queries;
extended tickers are included in the same batch with a per-name line cap in crew prompts.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).resolve().parent / "assets_config.json"

# Defaults if JSON missing fields (backward compatible with old ``equity``-only files)
_DEFAULT_CORE_EQUITY: Final[tuple[str, ...]] = ("NVDA", "MSFT")
_DEFAULT_EXTENDED_EQUITY: Final[tuple[str, ...]] = (
    "AAPL",
    "TSLA",
    "GOOGL",
    "GOOG",
    "AMZN",
    "META",
    "AVGO",
    "TSM",
)


def _config_path() -> Path:
    raw = (os.getenv("ASSETS_CONFIG_PATH") or "").strip()
    return Path(raw) if raw else _DEFAULT_PATH


@lru_cache(maxsize=1)
def _raw_assets_config() -> dict[str, object]:
    path = _config_path()
    if not path.exists():
        logger.debug("assets config not found at %s, using defaults", path)
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("Failed to read assets config %s: %s", path, e)
        return {}


def clear_assets_universe_cache() -> None:
    """Test hook: clear cached config after mutating files or env."""
    _raw_assets_config.cache_clear()


def _upper_str_list(key: str, data: dict[str, object]) -> list[str]:
    raw = data.get(key)
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x).upper().strip().lstrip("$")[:12]
        if s and s.isalnum():
            out.append(s)
    return out


def equity_core_tickers() -> tuple[str, ...]:
    """Anchors: full FD + yfinance rows expected (≥2 MetricLines each in crew)."""
    data = _raw_assets_config()
    core = _upper_str_list("core_equity", data)
    if core:
        return tuple(dict.fromkeys(core))
    # Legacy: single ``equity`` list → first two as core, rest extended
    legacy = _upper_str_list("equity", data)
    if len(legacy) >= 2:
        return tuple(legacy[:2])
    if legacy:
        return tuple(legacy)
    return _DEFAULT_CORE_EQUITY


def equity_extended_tickers() -> tuple[str, ...]:
    """Satellite: ≤3 FD lines per name in crew; still in batch watchlist."""
    data = _raw_assets_config()
    ext = _upper_str_list("extended_equity", data)
    if ext:
        core_set = set(equity_core_tickers())
        merged: list[str] = []
        for s in ext:
            if s not in core_set and s not in merged:
                merged.append(s)
        return tuple(merged)
    legacy = _upper_str_list("equity", data)
    if len(legacy) > 2:
        return tuple(legacy[2:])
    return _DEFAULT_EXTENDED_EQUITY


def equity_universe_merged() -> tuple[str, ...]:
    """Core first, then extended; dedupe."""
    out: list[str] = []
    for bucket in (equity_core_tickers(), equity_extended_tickers()):
        for s in bucket:
            if s not in out:
                out.append(s)
    return tuple(out)


def financial_datasets_watchlist_tickers() -> list[str]:
    """Ordered tickers for ``financial_datasets_tool`` query watchlist / empty."""
    return list(equity_universe_merged())


def ai_sector_yfinance_symbols() -> tuple[str, ...]:
    """ETF benchmarks + full merged equity universe (one row per symbol in tool output)."""
    base = ("SMH", "SOXX")
    eq = equity_universe_merged()
    tail = ("SPY",)
    out: list[str] = []
    for s in (*base, *eq, *tail):
        if s not in out:
            out.append(s)
    return tuple(out)


def financial_datasets_tickers_for_prompt() -> str:
    """Comma list for crew / docstrings (stable order)."""
    return "、".join(financial_datasets_watchlist_tickers())
