"""Structured macro snapshot API for the five-board dashboard."""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/macro", tags=["macro"])

_CACHE_TTL = timedelta(seconds=60)
_macro_cache: tuple[datetime, dict[str, Any]] | None = None

INDICATOR_ORDER = [
    "yields_10y",
    "spread_2s10s",
    "dxy",
    "vix",
    "btc",
    "soxx_spy_ratio",
    "ai_momentum",
    "next_fed_cpi",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _drop_missing(values: list[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        n = _finite_float(value)
        if n is not None:
            out.append(n)
    return out


def _download_close_series(symbol: str, period: str = "14d") -> list[float]:
    """Fetch a daily close series from yfinance.

    Kept as a small helper so API tests can monkeypatch it without importing the
    yfinance package in CI.
    """
    try:
        import yfinance as yf  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - CI stubs may omit yfinance
        logger.warning("yfinance unavailable for macro snapshot: %s", exc)
        return []

    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    except Exception as exc:
        logger.warning("macro snapshot yfinance download failed for %s: %s", symbol, exc)
        return []
    if df is None or getattr(df, "empty", True) or "Close" not in df:
        return []
    close = df["Close"].dropna()
    if hasattr(close, "ndim") and close.ndim > 1:
        close = close.iloc[:, 0]
    try:
        return _drop_missing(close.tolist())
    except Exception:
        return []


def _pct_change(series: list[float], periods: int) -> float | None:
    if len(series) <= periods:
        return None
    last = series[-1]
    prev = series[-1 - periods]
    if prev == 0:
        return None
    return round((last - prev) / abs(prev) * 100.0, 4)


def _point_change(series: list[float], periods: int) -> float | None:
    if len(series) <= periods:
        return None
    return round(series[-1] - series[-1 - periods], 4)


def _empty_indicator(indicator_id: str, label: str, unit: str, source: str, as_of: str, error: str) -> dict[str, Any]:
    return {
        "id": indicator_id,
        "label": label,
        "value": None,
        "display": "N/A",
        "unit": unit,
        "change_1d": None,
        "change_5d": None,
        "change_unit": "%",
        "spark": [],
        "source": source,
        "as_of": as_of,
        "error": error,
    }


def _price_indicator(
    indicator_id: str,
    label: str,
    symbol: str,
    unit: str,
    as_of: str,
) -> dict[str, Any]:
    series = _download_close_series(symbol)
    if not series:
        return _empty_indicator(indicator_id, label, unit, f"yfinance:{symbol}", as_of, "price_unavailable")
    value = round(series[-1], 4)
    return {
        "id": indicator_id,
        "label": label,
        "value": value,
        "display": f"{value:,.2f}" if abs(value) >= 100 else f"{value:.2f}",
        "unit": unit,
        "change_1d": _pct_change(series, 1),
        "change_5d": _pct_change(series, 5),
        "change_unit": "%",
        "spark": [round(x, 4) for x in series[-7:]],
        "source": f"yfinance:{symbol}",
        "as_of": as_of,
        "error": None,
    }


def _spread_indicator(as_of: str) -> dict[str, Any]:
    y10 = _download_close_series("^TNX")
    y2 = _download_close_series("2YY=F")
    n = min(len(y10), len(y2))
    if n == 0:
        return _empty_indicator("spread_2s10s", "2s10s Spread", "bp", "yfinance:^TNX/2YY=F", as_of, "spread_unavailable")
    spread = [round((a - b) * 100.0, 4) for a, b in zip(y10[-n:], y2[-n:])]
    value = round(spread[-1], 2)
    return {
        "id": "spread_2s10s",
        "label": "2s10s Spread",
        "value": value,
        "display": f"{value:+.1f} bp",
        "unit": "bp",
        "change_1d": _point_change(spread, 1),
        "change_5d": _point_change(spread, 5),
        "change_unit": "bp",
        "spark": spread[-7:],
        "source": "yfinance:^TNX/2YY=F",
        "as_of": as_of,
        "error": None,
    }


def _ratio_indicator(as_of: str) -> dict[str, Any]:
    soxx = _download_close_series("SOXX")
    spy = _download_close_series("SPY")
    n = min(len(soxx), len(spy))
    if n == 0:
        return _empty_indicator("soxx_spy_ratio", "SOXX / SPY", "ratio", "yfinance:SOXX/SPY", as_of, "ratio_unavailable")
    ratio = [round(a / b, 6) for a, b in zip(soxx[-n:], spy[-n:]) if b]
    if not ratio:
        return _empty_indicator("soxx_spy_ratio", "SOXX / SPY", "ratio", "yfinance:SOXX/SPY", as_of, "ratio_unavailable")
    value = round(ratio[-1], 4)
    return {
        "id": "soxx_spy_ratio",
        "label": "SOXX / SPY",
        "value": value,
        "display": f"{value:.3f}",
        "unit": "ratio",
        "change_1d": _pct_change(ratio, 1),
        "change_5d": _pct_change(ratio, 5),
        "change_unit": "%",
        "spark": ratio[-7:],
        "source": "yfinance:SOXX/SPY",
        "as_of": as_of,
        "error": None,
    }


def _ai_momentum_indicator(as_of: str) -> dict[str, Any]:
    symbols = ["NVDA", "AMD", "AVGO", "MSFT", "AAPL", "SMH"]
    series_list = [_download_close_series(sym) for sym in symbols]
    series_list = [s for s in series_list if len(s) >= 2 and s[0] != 0]
    if not series_list:
        return _empty_indicator("ai_momentum", "AI Momentum", "index", "yfinance:AI basket", as_of, "basket_unavailable")
    n = min(len(s) for s in series_list)
    trimmed = [s[-n:] for s in series_list]
    normalized = [[value / s[0] * 100.0 for value in s] for s in trimmed]
    basket = [round(sum(row[i] for row in normalized) / len(normalized), 4) for i in range(n)]
    value = round(basket[-1], 2)
    return {
        "id": "ai_momentum",
        "label": "AI Momentum",
        "value": value,
        "display": f"{value:.1f}",
        "unit": "index",
        "change_1d": _pct_change(basket, 1),
        "change_5d": _pct_change(basket, 5),
        "change_unit": "%",
        "spark": basket[-7:],
        "source": "yfinance:NVDA/AMD/AVGO/MSFT/AAPL/SMH",
        "as_of": as_of,
        "error": None,
    }


def _fetch_catalysts(now: datetime) -> list[dict[str, Any]]:
    key = (os.getenv("FMP_API_KEY") or "").strip()
    if not key:
        return []
    start = now.date()
    end = start + timedelta(days=7)
    try:
        resp = requests.get(
            "https://financialmodelingprep.com/api/v3/economic_calendar",
            params={"from": start.isoformat(), "to": end.isoformat(), "apikey": key},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        logger.warning("macro catalysts fetch failed: %s", exc)
        return []
    if not isinstance(raw, list):
        return []
    keywords = ("FOMC", "FED", "CPI", "PCE", "NFP", "PAYROLL", "PPI", "JOBLESS")
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        country = str(item.get("country") or "").upper()
        if country not in {"US", "USA", "UNITED STATES"}:
            continue
        event = str(item.get("event") or item.get("title") or "").strip()
        if not event or not any(k in event.upper() for k in keywords):
            continue
        out.append(
            {
                "date": str(item.get("date") or "")[:10],
                "name": event,
                "importance": str(item.get("impact") or "high").lower(),
                "estimate": item.get("estimate"),
                "previous": item.get("previous"),
                "source": "financialmodelingprep",
            }
        )
    return out[:8]


def _next_catalyst_indicator(catalysts: list[dict[str, Any]], now: datetime, as_of: str) -> dict[str, Any]:
    if not catalysts:
        return {
            "id": "next_fed_cpi",
            "label": "Next Fed / CPI",
            "value": None,
            "display": "N/A",
            "unit": "days",
            "change_1d": None,
            "change_5d": None,
            "change_unit": "days",
            "spark": [],
            "source": "financialmodelingprep_optional",
            "as_of": as_of,
            "error": "calendar_unavailable",
        }
    first = catalysts[0]
    try:
        event_date = datetime.fromisoformat(str(first.get("date"))[:10]).date()
        days = max((event_date - now.date()).days, 0)
    except ValueError:
        days = None
    return {
        "id": "next_fed_cpi",
        "label": "Next Fed / CPI",
        "value": days,
        "display": f"{first.get('date')} · {first.get('name')}",
        "unit": "days",
        "change_1d": None,
        "change_5d": None,
        "change_unit": "days",
        "spark": [],
        "source": str(first.get("source") or "financialmodelingprep"),
        "as_of": as_of,
        "error": None,
    }


def _regime_from_indicators(indicators: dict[str, dict[str, Any]]) -> dict[str, Any]:
    drivers: list[dict[str, Any]] = []

    def add(name: str, score: int, note: str) -> None:
        drivers.append({"name": name, "score": score, "note": note})

    vix = _finite_float(indicators.get("vix", {}).get("value"))
    if vix is not None:
        add("VIX", 1 if vix < 18 else -1 if vix > 25 else 0, f"{vix:.1f}")

    spread = _finite_float(indicators.get("spread_2s10s", {}).get("value"))
    if spread is not None:
        add("2s10s", 1 if spread > 25 else -1 if spread < 0 else 0, f"{spread:+.1f}bp")

    btc_5d = _finite_float(indicators.get("btc", {}).get("change_5d"))
    if btc_5d is not None:
        add("BTC 5D", 1 if btc_5d > 0 else -1 if btc_5d < -3 else 0, f"{btc_5d:+.1f}%")

    ai_5d = _finite_float(indicators.get("ai_momentum", {}).get("change_5d"))
    if ai_5d is not None:
        add("AI 5D", 1 if ai_5d > 0 else -1 if ai_5d < -3 else 0, f"{ai_5d:+.1f}%")

    dxy_5d = _finite_float(indicators.get("dxy", {}).get("change_5d"))
    if dxy_5d is not None:
        add("DXY 5D", 1 if dxy_5d < -0.5 else -1 if dxy_5d > 1 else 0, f"{dxy_5d:+.1f}%")

    score = sum(int(d["score"]) for d in drivers)
    if score >= 2:
        label = "risk_on"
    elif score <= -2:
        label = "risk_off"
    else:
        label = "neutral"
    return {"score": score, "label": label, "drivers": drivers}


def build_macro_snapshot() -> dict[str, Any]:
    now = _now()
    as_of = _iso(now)
    catalysts = _fetch_catalysts(now)
    indicators = {
        "yields_10y": _price_indicator("yields_10y", "10Y Yield", "^TNX", "%", as_of),
        "spread_2s10s": _spread_indicator(as_of),
        "dxy": _price_indicator("dxy", "DXY", "DX-Y.NYB", "index", as_of),
        "vix": _price_indicator("vix", "VIX", "^VIX", "index", as_of),
        "btc": _price_indicator("btc", "BTC", "BTC-USD", "USD", as_of),
        "soxx_spy_ratio": _ratio_indicator(as_of),
        "ai_momentum": _ai_momentum_indicator(as_of),
        "next_fed_cpi": _next_catalyst_indicator(catalysts, now, as_of),
    }
    return {
        "as_of": as_of,
        "cache_ttl_seconds": int(_CACHE_TTL.total_seconds()),
        "indicator_order": INDICATOR_ORDER,
        "indicators": indicators,
        "catalysts": catalysts,
        "regime": _regime_from_indicators(indicators),
    }


@router.get("/snapshot")
def get_macro_snapshot() -> dict[str, Any]:
    global _macro_cache
    now = _now()
    if _macro_cache and now - _macro_cache[0] <= _CACHE_TTL:
        return {**_macro_cache[1], "cached": True}
    payload = build_macro_snapshot()
    _macro_cache = (now, payload)
    return {**payload, "cached": False}


# --- Compute / Memory mock dashboard (queue 45 P2-mock) ----------------------
# Read-only fixture endpoint for HBM/DRAM spot, hyperscaler capex, GPU spot.
# Lives behind the same /api/macro prefix so the dashboard can fan out from
# one router. Live providers (TrendForce / CoreWeave / parsed capex) are out
# of scope for P2-mock — they require governance review before being honored.

_COMPUTE_MEMORY_CACHE_TTL = timedelta(minutes=5)
_compute_memory_cache: tuple[datetime, dict[str, Any]] | None = None


def _compute_memory_fixture_path() -> Path:
    raw = (os.getenv("COMPUTE_MEMORY_FIXTURE_FILE") or "data/compute_memory_mock.json").strip()
    return Path(raw)


def _compute_memory_reset_cache_for_tests() -> None:
    global _compute_memory_cache
    _compute_memory_cache = None


@router.get("/compute-memory")
def get_compute_memory() -> dict[str, Any]:
    """HBM/DRAM spot + hyperscaler capex + GPU spot from a local fixture.

    Live providers are intentionally not wired here; ``COMPUTE_MEMORY_LIVE=1``
    is reserved as a future toggle, currently treated as enabled-with-mock
    so the contract stays stable.
    """
    global _compute_memory_cache
    now = _now()
    if _compute_memory_cache and now - _compute_memory_cache[0] <= _COMPUTE_MEMORY_CACHE_TTL:
        return {**_compute_memory_cache[1], "cached": True}

    path = _compute_memory_fixture_path()
    if not path.exists():
        empty = {
            "enabled": False,
            "live": False,
            "reason": "fixture_missing",
            "fixture_path": str(path),
            "hint": "Copy data/compute_memory_mock.json (or set COMPUTE_MEMORY_FIXTURE_FILE).",
        }
        _compute_memory_cache = (now, empty)
        return {**empty, "cached": False}

    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("compute_memory fixture parse failed for %s: %s", path, exc)
        broken = {
            "enabled": False,
            "live": False,
            "reason": "fixture_invalid",
            "fixture_path": str(path),
            "error": str(exc),
        }
        _compute_memory_cache = (now, broken)
        return {**broken, "cached": False}

    if not isinstance(body, dict):
        broken = {
            "enabled": False,
            "live": False,
            "reason": "fixture_invalid",
            "fixture_path": str(path),
            "error": "top-level JSON is not an object",
        }
        _compute_memory_cache = (now, broken)
        return {**broken, "cached": False}

    live_env = (os.getenv("COMPUTE_MEMORY_LIVE") or "0").strip().lower() in ("1", "true", "yes")
    capex_block = dict(body.get("hyperscaler_capex") or {})
    capex_status = "mock"
    if (os.getenv("COMPUTE_MEMORY_CAPEX_LIVE") or "0").strip().lower() in ("1", "true", "yes"):
        from tools import sec_edgar_capex

        live_items = sec_edgar_capex.fetch_all_hyperscaler_capex()
        if live_items:
            capex_block = {
                "as_of": live_items[0].get("as_of"),
                "source": "sec_edgar",
                "note": "Live: SEC EDGAR XBRL us-gaap:PaymentsToAcquirePropertyPlantAndEquipment.",
                "items": live_items,
            }
            capex_status = "live"
        else:
            capex_status = "fallback"

    gpu_block = dict(body.get("gpu_spot") or {})
    gpu_status = "mock"
    if (os.getenv("COMPUTE_MEMORY_GPU_LIVE") or "0").strip().lower() in ("1", "true", "yes"):
        from tools import coreweave_gpu_spot

        live_gpu_items = coreweave_gpu_spot.fetch_gpu_pricing()
        if live_gpu_items:
            gpu_block = {
                "as_of": live_gpu_items[0].get("as_of"),
                "source": "coreweave_pricing",
                "note": "Live: CoreWeave public pricing (per 8-GPU HGX node).",
                "items": live_gpu_items,
            }
            gpu_status = "live"
        else:
            gpu_status = "fallback"

    payload = {
        "enabled": True,
        "live": bool(body.get("live", False)) and live_env,
        "fixture_path": str(path),
        "as_of": body.get("as_of"),
        "disclaimer": body.get("disclaimer"),
        "hbm_dram_spot": body.get("hbm_dram_spot") or {},
        "hyperscaler_capex": capex_block,
        "gpu_spot": gpu_block,
        "live_block_status": {
            "hbm": "mock",
            "capex": capex_status,
            "gpu": gpu_status,
        },
    }
    _compute_memory_cache = (now, payload)
    return {**payload, "cached": False}


# --- Crypto on-chain mock dashboard (queue 45 P5-mock) -----------------------
# Mirrors compute-memory shape: fixture-driven, mock-first, governance flip.

_ONCHAIN_CACHE_TTL = timedelta(minutes=5)
_onchain_cache: tuple[datetime, dict[str, Any]] | None = None


def _onchain_fixture_path() -> Path:
    raw = (os.getenv("ONCHAIN_FIXTURE_FILE") or "data/onchain_metrics_mock.json").strip()
    return Path(raw)


def _onchain_reset_cache_for_tests() -> None:
    global _onchain_cache
    _onchain_cache = None


@router.get("/onchain")
def get_onchain_metrics() -> dict[str, Any]:
    """Crypto on-chain dashboard (BTC valuation / exchange flow / funding rate).

    Live providers (Glassnode / CryptoQuant / Coinglass) require governance
    review; ``ONCHAIN_LIVE=1`` is reserved for that future flip and only
    honored when the fixture itself also sets ``live: true``.
    """
    global _onchain_cache
    now = _now()
    if _onchain_cache and now - _onchain_cache[0] <= _ONCHAIN_CACHE_TTL:
        return {**_onchain_cache[1], "cached": True}

    path = _onchain_fixture_path()
    if not path.exists():
        empty = {
            "enabled": False,
            "live": False,
            "reason": "fixture_missing",
            "fixture_path": str(path),
            "hint": "Copy data/onchain_metrics_mock.json (or set ONCHAIN_FIXTURE_FILE).",
        }
        _onchain_cache = (now, empty)
        return {**empty, "cached": False}

    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("onchain fixture parse failed for %s: %s", path, exc)
        broken = {
            "enabled": False,
            "live": False,
            "reason": "fixture_invalid",
            "fixture_path": str(path),
            "error": str(exc),
        }
        _onchain_cache = (now, broken)
        return {**broken, "cached": False}

    if not isinstance(body, dict):
        broken = {
            "enabled": False,
            "live": False,
            "reason": "fixture_invalid",
            "fixture_path": str(path),
            "error": "top-level JSON is not an object",
        }
        _onchain_cache = (now, broken)
        return {**broken, "cached": False}

    live_env = (os.getenv("ONCHAIN_LIVE") or "0").strip().lower() in ("1", "true", "yes")

    funding_block = dict(body.get("funding_rate") or {})
    funding_status = "mock"
    if (os.getenv("ONCHAIN_FUNDING_LIVE") or "0").strip().lower() in ("1", "true", "yes"):
        from tools import binance_funding_rate

        live_funding = binance_funding_rate.fetch_funding_rates()
        if live_funding:
            funding_block = {
                "as_of": live_funding[0].get("as_of"),
                "source": "binance_fapi",
                "note": "Live: Binance USD-M futures premiumIndex; annualized lastFundingRate × 3 × 365.",
                "items": live_funding,
            }
            funding_status = "live"
        else:
            funding_status = "fallback"

    payload = {
        "enabled": True,
        "live": bool(body.get("live", False)) and live_env,
        "fixture_path": str(path),
        "as_of": body.get("as_of"),
        "disclaimer": body.get("disclaimer"),
        "btc_valuation": body.get("btc_valuation") or {},
        "exchange_flow": body.get("exchange_flow") or {},
        "funding_rate": funding_block,
        "live_block_status": {
            "valuation": "mock",
            "exchange_flow": "mock",
            "funding": funding_status,
        },
    }
    _onchain_cache = (now, payload)
    return {**payload, "cached": False}
