"""Unusual options flow detection + Gamma Exposure (GEX) calculation.

Pure functions over structured :mod:`tools.options.models` inputs so they are
trivially unit-testable and never touch the network. Missing inputs (no Greeks,
no OI, no spot) yield ``[DATA_MISSING:...]`` markers instead of guesses
(Q-Silicon 無數據幻覺紅線).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from .models import (
    CONTRACT_MULTIPLIER,
    ContractType,
    FlowSignalType,
    GEXResult,
    OptionSnapshot,
    OptionTrade,
    Provenance,
    StrikeGamma,
    UnusualFlowSignal,
    data_missing,
)

logger = logging.getLogger(__name__)

# 1% spot move scaling: dollar gamma per 1% = gamma * OI * 100 * spot^2 * 0.01.
_PCT_MOVE = 0.01


def _contract_gex(gamma: float, open_interest: int, spot_price: float, contract_type: ContractType) -> float:
    """Standard dealer GEX for one contract (calls +, puts −), per 1% move."""
    sign = 1.0 if contract_type is ContractType.CALL else -1.0
    return sign * gamma * open_interest * CONTRACT_MULTIPLIER * (spot_price**2) * _PCT_MOVE


def calculate_gex(
    underlying: str,
    spot_price: float,
    snapshots: list[OptionSnapshot],
    *,
    as_of: datetime | None = None,
) -> GEXResult | str:
    """Total Gamma Exposure for ``underlying``.

    Returns a :class:`GEXResult` or a ``[DATA_MISSING:...]`` marker string when
    the inputs are insufficient (no valid spot, or no contract carries both
    gamma and open interest).
    """
    if not spot_price or spot_price <= 0:
        return data_missing("options_gex_spot_price")

    usable = [
        s
        for s in snapshots
        if s.contract.underlying == underlying
        and s.greeks.gamma is not None
        and s.open_interest is not None
    ]
    if not usable:
        return data_missing("polygon_options_snapshot_greeks")

    strike_calls: dict[float, float] = defaultdict(float)
    strike_puts: dict[float, float] = defaultdict(float)
    call_total = 0.0
    put_total = 0.0

    for snap in usable:
        contract = snap.contract
        gex = _contract_gex(snap.greeks.gamma, snap.open_interest, spot_price, contract.contract_type)
        if contract.contract_type is ContractType.CALL:
            strike_calls[contract.strike] += gex
            call_total += gex
        else:
            strike_puts[contract.strike] += gex
            put_total += gex

    strikes = sorted(set(strike_calls) | set(strike_puts))
    per_strike = tuple(
        StrikeGamma(strike=k, call_gex=strike_calls.get(k, 0.0), put_gex=strike_puts.get(k, 0.0))
        for k in strikes
    )

    return GEXResult(
        underlying=underlying,
        spot_price=spot_price,
        total_gex=call_total + put_total,
        call_gex=call_total,
        put_gex=put_total,
        per_strike=per_strike,
        contracts_used=len(usable),
        provenance=Provenance(
            source="polygon_options",
            as_of=as_of or datetime.now(timezone.utc),
            method="snapshot_greeks",
        ),
    )


@dataclass(frozen=True)
class FlowThresholds:
    """Tunable thresholds for unusual flow detection."""

    min_premium: float = 250_000.0  # single-trade premium (USD)
    min_volume_oi_ratio: float = 3.0  # day volume / open interest
    min_block_size: int = 250  # contracts in a single trade → block
    min_oi_for_ratio: int = 50  # ignore tiny-OI noise


class UnusualOptionsAnalyzer:
    """Detect unusual options flow from snapshots (volume/OI) and trades (sweep/block).

    Snapshot-only path (Polygon Starter) yields ``VOLUME_OI`` signals. Tick-level
    ``SWEEP`` / ``BLOCK`` / ``PREMIUM`` signals require trades (Polygon Advanced);
    callers that lack trades should record ``[DATA_MISSING:polygon_options_trades]``.
    """

    def __init__(self, thresholds: FlowThresholds | None = None) -> None:
        self.thresholds = thresholds or FlowThresholds()

    def from_snapshots(self, snapshots: list[OptionSnapshot]) -> list[UnusualFlowSignal]:
        out: list[UnusualFlowSignal] = []
        for snap in snapshots:
            oi = snap.open_interest
            vol = snap.day_volume
            if not oi or oi < self.thresholds.min_oi_for_ratio or not vol:
                continue
            ratio = vol / oi
            if ratio < self.thresholds.min_volume_oi_ratio:
                continue
            score = min(1.0, ratio / (self.thresholds.min_volume_oi_ratio * 3))
            out.append(
                UnusualFlowSignal(
                    underlying=snap.contract.underlying,
                    contract=snap.contract,
                    signal_type=FlowSignalType.VOLUME_OI,
                    score=score,
                    volume=vol,
                    open_interest=oi,
                    rationale=f"day_volume {vol} = {ratio:.1f}x open_interest {oi}",
                    provenance=snap.provenance,
                )
            )
        return out

    def from_trades(self, trades: list[OptionTrade]) -> list[UnusualFlowSignal]:
        out: list[UnusualFlowSignal] = []
        # Group by contract+second to approximate a sweep (one order hitting
        # multiple exchanges within the same second).
        sweep_buckets: dict[tuple[str, int], list[OptionTrade]] = defaultdict(list)
        for tr in trades:
            if tr.premium >= self.thresholds.min_premium:
                out.append(self._block_or_premium(tr))
            bucket = (tr.contract.ticker, int(tr.sip_timestamp.timestamp()))
            sweep_buckets[bucket].append(tr)

        for (ticker, _sec), group in sweep_buckets.items():
            exchanges = {t.exchange for t in group if t.exchange is not None}
            if len(group) >= 3 and len(exchanges) >= 2:
                total_prem = sum(t.premium for t in group)
                total_size = sum(t.size for t in group)
                first = group[0]
                out.append(
                    UnusualFlowSignal(
                        underlying=first.contract.underlying,
                        contract=first.contract,
                        signal_type=FlowSignalType.SWEEP,
                        score=min(1.0, total_prem / (self.thresholds.min_premium * 4)),
                        premium=total_prem,
                        volume=total_size,
                        rationale=(
                            f"sweep {ticker}: {len(group)} prints across "
                            f"{len(exchanges)} exchanges, premium ${total_prem:,.0f}"
                        ),
                        provenance=first.provenance,
                    )
                )
        return out

    def _block_or_premium(self, tr: OptionTrade) -> UnusualFlowSignal:
        is_block = tr.size >= self.thresholds.min_block_size
        return UnusualFlowSignal(
            underlying=tr.contract.underlying,
            contract=tr.contract,
            signal_type=FlowSignalType.BLOCK if is_block else FlowSignalType.PREMIUM,
            score=min(1.0, tr.premium / (self.thresholds.min_premium * 4)),
            premium=tr.premium,
            volume=tr.size,
            rationale=(
                f"{'block' if is_block else 'large trade'} {tr.size} @ {tr.price} "
                f"= ${tr.premium:,.0f} premium"
            ),
            provenance=tr.provenance,
        )
