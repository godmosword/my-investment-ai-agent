"""Daily options pipeline: snapshots → unusual flow + GEX → BigQuery + summary.

``run_daily_options_pipeline()`` is the single entrypoint, callable from a GitHub
Actions tick, Cloud Run / Cloud Scheduler job, or cron. Per-symbol failures are
isolated so one bad ticker never aborts the run; missing entitlements/data surface
as ``[DATA_MISSING:...]`` markers rather than fabricated numbers.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone

import options_bigquery_writer as bq

from tools.base import load_mock_json, mock_apis_enabled

from .analyzer import UnusualOptionsAnalyzer, calculate_gex
from .client import PolygonOptionsClient
from .models import (
    Capability,
    GEXResult,
    PipelineSummary,
    UnderlyingOptionsResult,
    UnusualFlowSignal,
    data_missing,
)

logger = logging.getLogger(__name__)

_DEFAULT_WATCHLIST = ("MU", "NVDA", "AMD", "TSM", "AVGO", "SMH")
# Only chase trades for the few snapshot contracts that already look unusual.
_TRADES_TOP_N = 5


def _watchlist() -> list[str]:
    raw = (os.getenv("OPTIONS_WATCHLIST") or "").strip()
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    return list(_DEFAULT_WATCHLIST)


def _spot_price(underlying: str) -> float | None:
    """Spot price for GEX scaling. Mockable; yfinance fallback for live runs."""
    if mock_apis_enabled():
        spots = load_mock_json("polygon_spot.json") or {}
        val = spots.get(underlying)
        return float(val) if isinstance(val, (int, float)) else None
    try:
        import yfinance as yf

        fast = yf.Ticker(underlying).fast_info
        price = getattr(fast, "last_price", None) or fast.get("lastPrice")  # type: ignore[union-attr]
        return float(price) if price else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("options pipeline spot price failed for %s: %s", underlying, exc)
        return None


def _process_underlying(
    underlying: str,
    trade_date: date,
    client: PolygonOptionsClient,
    analyzer: UnusualOptionsAnalyzer,
    capabilities: set[Capability],
) -> UnderlyingOptionsResult:
    missing: list[str] = []
    gex: GEXResult | None = None
    unusual: list[UnusualFlowSignal] = []

    snapshots = client.get_snapshots(underlying)
    if not snapshots:
        missing.append(data_missing("polygon_options_snapshot_greeks"))

    # GEX (needs Greeks + spot)
    spot = _spot_price(underlying)
    if spot is None:
        missing.append(data_missing("options_gex_spot_price"))
    elif snapshots:
        result = calculate_gex(underlying, spot, snapshots, as_of=datetime.now(timezone.utc))
        if isinstance(result, str):
            missing.append(result)
        else:
            gex = result
            bq.write_gex(trade_date, gex)
            bq.write_gex_by_strike(trade_date, gex)  # per-strike 分布（by-strike 圖）

    # Snapshot-level unusual flow (volume vs OI)
    if snapshots:
        unusual.extend(analyzer.from_snapshots(snapshots))
        bq.write_snapshots(underlying, trade_date, snapshots)

    # Tick-level sweep/block (needs Advanced trades entitlement)
    if Capability.TRADES in capabilities:
        top = sorted(
            (s for s in snapshots if s.day_volume),
            key=lambda s: s.day_volume or 0,
            reverse=True,
        )[:_TRADES_TOP_N]
        trades = []
        for snap in top:
            trades.extend(client.get_recent_trades(snap.contract))
        unusual.extend(analyzer.from_trades(trades))
    else:
        missing.append(data_missing("polygon_options_trades"))

    if unusual:
        bq.write_unusual(underlying, trade_date, unusual)

    return UnderlyingOptionsResult(
        underlying=underlying,
        trade_date=trade_date,
        gex=gex,
        unusual=tuple(unusual),
        missing=tuple(dict.fromkeys(missing)),  # de-dup, keep order
    )


def _build_text_summary(results: list[UnderlyingOptionsResult]) -> str:
    lines: list[str] = []
    for r in results:
        if r.gex is not None:
            regime = "正 gamma" if r.gex.total_gex >= 0 else "負 gamma"
            lines.append(
                f"{r.underlying}: GEX {r.gex.total_gex:,.0f}（{regime}）；"
                f"異常流 {len(r.unusual)} 筆"
            )
        else:
            why = ", ".join(r.missing) if r.missing else "no data"
            lines.append(f"{r.underlying}: GEX 不可得（{why}）；異常流 {len(r.unusual)} 筆")
    return "\n".join(lines)


def run_daily_options_pipeline(
    watchlist: list[str] | None = None,
    *,
    client: PolygonOptionsClient | None = None,
) -> PipelineSummary:
    """Run the full daily options pipeline and return a structured summary."""
    symbols = watchlist or _watchlist()
    client = client or PolygonOptionsClient()
    analyzer = UnusualOptionsAnalyzer()
    trade_date = datetime.now(timezone.utc).date()

    capabilities = client.probe_capabilities()
    logger.info("options pipeline capabilities: %s", sorted(c.value for c in capabilities))

    results: list[UnderlyingOptionsResult] = []
    for underlying in symbols:
        try:
            results.append(
                _process_underlying(underlying, trade_date, client, analyzer, capabilities)
            )
        except Exception as exc:  # noqa: BLE001 — isolate per-symbol failures
            logger.exception("options pipeline failed for %s: %s", underlying, exc)
            results.append(
                UnderlyingOptionsResult(
                    underlying=underlying,
                    trade_date=trade_date,
                    missing=(data_missing(f"options_pipeline_error_{underlying}"),),
                )
            )

    return PipelineSummary(
        run_at=datetime.now(timezone.utc),
        capabilities=tuple(sorted(capabilities, key=lambda c: c.value)),
        results=tuple(results),
        text_summary=_build_text_summary(results),
    )
