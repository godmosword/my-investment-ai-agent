"""Agent-facing options tools (CrewAI ``@tool`` callables).

Tool 快取紅線: these go through the shared
:func:`tools_cache_http._get_cache` / ``_set_cache`` (no private cache).
All numbers are computed in Python and returned as structured JSON so the LLM
only interprets them (無數據幻覺紅線).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from tools_cache_http import _get_cache, _set_cache

from .analyzer import UnusualOptionsAnalyzer, calculate_gex
from .client import PolygonOptionsClient
from .models import data_missing

logger = logging.getLogger(__name__)

try:  # CrewAI is a runtime dep; keep import soft for non-crew callers/tests.
    from crewai.tools import tool
except Exception:  # noqa: BLE001
    def tool(fn):  # type: ignore[misc]
        return fn


def _gex_payload(underlying: str) -> str:
    underlying = (underlying or "").strip().upper()
    if not underlying:
        return data_missing("options_gex_underlying")
    cache_key = ("options_gex", underlying)
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    client = PolygonOptionsClient()
    snapshots = client.get_snapshots(underlying)
    spot = _spot_price(underlying)
    if spot is None:
        return data_missing("options_gex_spot_price")
    result = calculate_gex(underlying, spot, snapshots, as_of=datetime.now(timezone.utc))
    if isinstance(result, str):
        return result  # [DATA_MISSING:...]
    body = result.model_dump_json()
    _set_cache(cache_key, body)
    return body


def _flow_payload(underlying: str) -> str:
    underlying = (underlying or "").strip().upper()
    if not underlying:
        return data_missing("options_flow_underlying")
    cache_key = ("options_flow", underlying)
    cached = _get_cache(cache_key)
    if cached is not None:
        return cached

    client = PolygonOptionsClient()
    snapshots = client.get_snapshots(underlying)
    if not snapshots:
        return data_missing("polygon_options_snapshot_greeks")
    signals = UnusualOptionsAnalyzer().from_snapshots(snapshots)
    body = json.dumps([s.model_dump(mode="json") for s in signals])
    _set_cache(cache_key, body)
    return body


def _spot_price(underlying: str) -> float | None:
    from .pipeline import _spot_price as _ps

    return _ps(underlying)


@tool
def options_gex_tool(underlying: str = "") -> str:
    """取得指定標的（如 MU、NVDA）的 Gamma Exposure (GEX) 結構化結果（JSON）。

    回傳 Python 已算好的 total_gex / call_gex / put_gex（每 1% 移動 USD；正 gamma
    抑制波動、負 gamma 放大）、spot_price 與 per_strike。資料不足時回 [DATA_MISSING:...]。
    參數 underlying：美股代號字串。
    """
    return _gex_payload(underlying)


@tool
def options_flow_tool(underlying: str = "") -> str:
    """取得指定標的的不尋常期權流訊號（JSON 陣列）。

    snapshot 級（volume vs open interest）異常；tick-level sweep/block 需 Polygon
    Advanced 方案。每筆含 signal_type / score / premium / volume / rationale。
    資料不足時回 [DATA_MISSING:...]。參數 underlying：美股代號字串。
    """
    return _flow_payload(underlying)
