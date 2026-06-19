"""Pydantic v2 models for Polygon options flow + GEX.

Red line (Q-Silicon 無數據幻覺): every numeric payload carries provenance
(``source`` / ``as_of`` / ``method``). When upstream data is missing, callers
emit a ``[DATA_MISSING:...]`` marker (see :func:`data_missing`) rather than
fabricating values. LLM-facing code consumes these structured objects only and
must never re-derive the numbers itself.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# Standard equity option contract multiplier (shares per contract).
CONTRACT_MULTIPLIER = 100


def data_missing(reason: str) -> str:
    """Return the canonical ``[DATA_MISSING:...]`` marker string."""
    return f"[DATA_MISSING:{reason}]"


class ContractType(str, Enum):
    CALL = "call"
    PUT = "put"


class Capability(str, Enum):
    """Polygon options entitlements probed at startup."""

    REFERENCE = "reference"  # contracts reference data
    SNAPSHOT_GREEKS = "snapshot_greeks"  # snapshot incl. Greeks + OI + IV
    TRADES = "trades"  # tick-level trades (sweep/block detection)


class Provenance(BaseModel):
    """Where a number came from and when. Frozen to keep payloads immutable."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(description="e.g. 'polygon_options'")
    as_of: datetime
    method: str = Field(description="e.g. 'snapshot', 'tick_trade', 'black_scholes'")


class OptionGreeks(BaseModel):
    model_config = ConfigDict(frozen=True)

    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None


class OptionContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str  # e.g. O:MU260116C00100000
    underlying: str
    expiration: date
    strike: float
    contract_type: ContractType


class OptionSnapshot(BaseModel):
    """Per-contract snapshot: OI, IV, Greeks, volume, last price."""

    model_config = ConfigDict(frozen=True)

    contract: OptionContract
    open_interest: int | None = None
    implied_volatility: float | None = None
    day_volume: int | None = None
    last_price: float | None = None
    greeks: OptionGreeks = Field(default_factory=OptionGreeks)
    provenance: Provenance


class OptionTrade(BaseModel):
    """A single executed options trade (Polygon Advanced tier)."""

    model_config = ConfigDict(frozen=True)

    contract: OptionContract
    price: float
    size: int
    premium: float  # price * size * CONTRACT_MULTIPLIER
    sip_timestamp: datetime
    exchange: int | None = None
    conditions: tuple[int, ...] = ()
    provenance: Provenance


class FlowSignalType(str, Enum):
    PREMIUM = "premium"  # single trade premium over threshold
    VOLUME_OI = "volume_oi"  # day volume abnormal vs open interest
    SWEEP = "sweep"  # multi-exchange sweep (needs trades)
    BLOCK = "block"  # large single block (needs trades)
    CONCENTRATION = "concentration"  # strike/expiry clustering


class UnusualFlowSignal(BaseModel):
    model_config = ConfigDict(frozen=True)

    underlying: str
    contract: OptionContract
    signal_type: FlowSignalType
    score: float = Field(ge=0.0, description="0..1 relative abnormality")
    premium: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    rationale: str
    provenance: Provenance


class StrikeGamma(BaseModel):
    model_config = ConfigDict(frozen=True)

    strike: float
    call_gex: float
    put_gex: float

    @property
    def net_gex(self) -> float:
        return self.call_gex + self.put_gex


class GEXResult(BaseModel):
    """Total Gamma Exposure for one underlying.

    Convention (D3, standard dealer GEX): calls positive, puts negative
    (dealer long calls / short puts), weighted by open interest, contract
    multiplier 100, scaled by spot^2 * 0.01 → dollars per 1% spot move.
    """

    model_config = ConfigDict(frozen=True)

    underlying: str
    spot_price: float
    total_gex: float
    call_gex: float
    put_gex: float
    per_strike: tuple[StrikeGamma, ...] = ()
    contracts_used: int = 0
    provenance: Provenance


class UnderlyingOptionsResult(BaseModel):
    """Per-underlying pipeline output: GEX + unusual flow + missing markers."""

    model_config = ConfigDict(frozen=True)

    underlying: str
    trade_date: date
    gex: GEXResult | None = None
    unusual: tuple[UnusualFlowSignal, ...] = ()
    missing: tuple[str, ...] = ()  # list of [DATA_MISSING:...] markers


class PipelineSummary(BaseModel):
    """Top-level daily run output (text + JSON) for Agent / Telegram / BigQuery."""

    model_config = ConfigDict(frozen=True)

    run_at: datetime
    capabilities: tuple[Capability, ...]
    results: tuple[UnderlyingOptionsResult, ...]
    text_summary: str = ""
