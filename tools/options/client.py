"""Polygon options client: contracts, snapshots (+Greeks), trades, capability probe.

Design notes
------------
* API key from ``POLYGON_API_KEY`` (never hard-coded; red line: secrets).
* The official ``polygon`` RESTClient is imported lazily so CI / offline runs
  (``MOCK_APIS=1``) never need the dependency installed.
* Raw provider payloads are cached via the shared
  :func:`tools_cache_http._get_cache` / ``_set_cache`` (Tool 快取紅線).
* :meth:`probe_capabilities` degrades gracefully per Polygon tier; missing
  entitlements surface as absent capabilities (callers emit ``[DATA_MISSING:...]``).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, datetime, timezone

from tools.base import load_mock_json, mock_apis_enabled
from tools_cache_http import _get_cache, _set_cache

from .models import (
    CONTRACT_MULTIPLIER,
    Capability,
    ContractType,
    OptionContract,
    OptionGreeks,
    OptionSnapshot,
    OptionTrade,
    Provenance,
)

logger = logging.getLogger(__name__)

_CACHE_TTL_TAG = "polygon_options"
_MAX_RETRIES = 3
_RETRY_BACKOFF_SEC = 1.5


class PolygonAuthError(RuntimeError):
    """Raised when POLYGON_API_KEY is missing for a live call."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_retriable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(code in msg for code in ("429", "500", "502", "503", "504", "timeout"))


# ── provider-dict → model parsers (shared by live + mock paths) ──────────────

def _parse_contract(details: dict, underlying: str) -> OptionContract | None:
    try:
        return OptionContract(
            ticker=str(details["ticker"]),
            underlying=underlying,
            expiration=date.fromisoformat(str(details["expiration_date"])),
            strike=float(details["strike_price"]),
            contract_type=ContractType(str(details["contract_type"]).lower()),
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("polygon_options: bad contract details %s: %s", details, exc)
        return None


def _parse_snapshot(row: dict, underlying: str, prov: Provenance) -> OptionSnapshot | None:
    details = row.get("details")
    if not isinstance(details, dict):
        return None
    contract = _parse_contract(details, underlying)
    if contract is None:
        return None
    greeks_raw = row.get("greeks") or {}
    day = row.get("day") or {}
    last_trade = row.get("last_trade") or {}

    def _num(d: dict, key: str) -> float | None:
        v = d.get(key)
        return float(v) if isinstance(v, (int, float)) else None

    def _int(d: dict, key: str) -> int | None:
        v = d.get(key)
        return int(v) if isinstance(v, (int, float)) else None

    return OptionSnapshot(
        contract=contract,
        open_interest=_int(row, "open_interest"),
        implied_volatility=_num(row, "implied_volatility"),
        day_volume=_int(day, "volume"),
        last_price=_num(last_trade, "price") or _num(day, "close"),
        greeks=OptionGreeks(
            delta=_num(greeks_raw, "delta"),
            gamma=_num(greeks_raw, "gamma"),
            theta=_num(greeks_raw, "theta"),
            vega=_num(greeks_raw, "vega"),
        ),
        provenance=prov,
    )


def _parse_trade(row: dict, contract: OptionContract, prov: Provenance) -> OptionTrade | None:
    try:
        price = float(row["price"])
        size = int(row["size"])
    except (KeyError, ValueError, TypeError):
        return None
    sip_ns = row.get("sip_timestamp")
    ts = (
        datetime.fromtimestamp(int(sip_ns) / 1e9, tz=timezone.utc)
        if isinstance(sip_ns, (int, float))
        else prov.as_of
    )
    conditions = tuple(int(c) for c in (row.get("conditions") or []) if isinstance(c, (int, float)))
    exch = row.get("exchange")
    return OptionTrade(
        contract=contract,
        price=price,
        size=size,
        premium=price * size * CONTRACT_MULTIPLIER,
        sip_timestamp=ts,
        exchange=int(exch) if isinstance(exch, (int, float)) else None,
        conditions=conditions,
        provenance=prov,
    )


class PolygonOptionsClient:
    """Thin wrapper over the Polygon options REST endpoints."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key or os.getenv("POLYGON_API_KEY") or "").strip()
        self._rest = None  # lazy

    # ── live REST plumbing ────────────────────────────────────────────────
    def _client(self):
        if self._rest is None:
            if not self._api_key:
                raise PolygonAuthError("POLYGON_API_KEY is not set")
            from polygon import RESTClient  # lazy: not needed under MOCK_APIS

            self._rest = RESTClient(self._api_key)
        return self._rest

    def _cached_provider(self, key: tuple, fetch) -> object:
        """Fetch a raw provider payload (list/dict) with retry + shared cache."""
        cached = _get_cache(key)
        if cached is not None:
            return json.loads(cached)
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                payload = fetch()
                _set_cache(key, json.dumps(payload))
                return payload
            except Exception as exc:  # noqa: BLE001 — provider exceptions vary
                last_exc = exc
                if not _is_retriable(exc) or attempt == _MAX_RETRIES - 1:
                    break
                time.sleep(_RETRY_BACKOFF_SEC * (attempt + 1))
        logger.warning("polygon_options fetch failed for %s: %s", key, last_exc)
        raise last_exc if last_exc else RuntimeError("polygon fetch failed")

    # ── public API ────────────────────────────────────────────────────────
    def probe_capabilities(self) -> set[Capability]:
        """Detect which options entitlements this key has (degrades gracefully)."""
        if mock_apis_enabled():
            caps = load_mock_json("polygon_capabilities.json") or {}
            return {Capability(c) for c in caps.get("capabilities", []) if c in Capability._value2member_map_}
        caps: set[Capability] = set()
        for cap, probe in (
            (Capability.SNAPSHOT_GREEKS, self._probe_snapshot),
            (Capability.TRADES, self._probe_trades),
        ):
            try:
                if probe():
                    caps.add(cap)
            except Exception as exc:  # noqa: BLE001
                logger.info("polygon_options capability %s unavailable: %s", cap.value, exc)
        if caps:
            caps.add(Capability.REFERENCE)
        return caps

    def _probe_snapshot(self) -> bool:
        rows = self._snapshot_rows("SPY")
        return any(isinstance(r, dict) and (r.get("greeks") or {}).get("gamma") is not None for r in rows)

    def _probe_trades(self) -> bool:
        contracts = self.get_option_contracts("SPY", limit=1)
        if not contracts:
            return False
        return bool(self.get_recent_trades(contracts[0], limit=1))

    def get_option_contracts(self, underlying: str, *, limit: int = 250) -> list[OptionContract]:
        rows = self._provider_results(
            ("options_contracts", underlying, limit),
            lambda: self._list_to_dicts(
                self._client().list_options_contracts(underlying_ticker=underlying, limit=limit)
            ),
            mock_file="polygon_contracts.json",
        )
        out = [_parse_contract(r, underlying) for r in rows]
        return [c for c in out if c is not None]

    def get_snapshots(self, underlying: str) -> list[OptionSnapshot]:
        prov = Provenance(source="polygon_options", as_of=_now(), method="snapshot_greeks")
        rows = self._snapshot_rows(underlying)
        out = [_parse_snapshot(r, underlying, prov) for r in rows if isinstance(r, dict)]
        return [s for s in out if s is not None]

    def get_recent_trades(self, contract: OptionContract, *, limit: int = 1000) -> list[OptionTrade]:
        prov = Provenance(source="polygon_options", as_of=_now(), method="tick_trade")
        rows = self._provider_results(
            ("options_trades", contract.ticker, limit),
            lambda: self._list_to_dicts(self._client().list_trades(contract.ticker, limit=limit)),
            mock_file="polygon_trades.json",
            mock_key=contract.ticker,
        )
        out = [_parse_trade(r, contract, prov) for r in rows if isinstance(r, dict)]
        return [t for t in out if t is not None]

    # ── internal helpers ─────────────────────────────────────────────────
    def _snapshot_rows(self, underlying: str) -> list[dict]:
        return self._provider_results(
            ("options_snapshot", underlying),
            lambda: self._list_to_dicts(self._client().list_snapshot_options_chain(underlying)),
            mock_file="polygon_snapshots.json",
            mock_key=underlying,
        )

    def _provider_results(self, key: tuple, fetch, *, mock_file: str, mock_key: str | None = None) -> list[dict]:
        if mock_apis_enabled():
            data = load_mock_json(mock_file) or {}
            if mock_key is not None:
                rows = data.get(mock_key, data.get("results", []))
            else:
                rows = data.get("results", data if isinstance(data, list) else [])
            return [r for r in rows if isinstance(r, dict)]
        payload = self._cached_provider((_CACHE_TTL_TAG, *key), fetch)
        if isinstance(payload, dict):
            payload = payload.get("results", [])
        return [r for r in payload if isinstance(r, dict)] if isinstance(payload, list) else []

    @classmethod
    def _list_to_dicts(cls, iterator) -> list[dict]:
        """Normalise polygon SDK objects/generators into plain (nested) dicts."""
        out: list[dict] = []
        for item in iterator:
            converted = cls._to_plain(item)
            if isinstance(converted, dict):
                out.append(converted)
        return out

    @classmethod
    def _to_plain(cls, obj):
        """Recursively convert SDK dataclass-like objects into JSON-safe dicts."""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: cls._to_plain(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [cls._to_plain(v) for v in obj]
        if hasattr(obj, "__dict__"):
            return {k: cls._to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}
        return str(obj)
