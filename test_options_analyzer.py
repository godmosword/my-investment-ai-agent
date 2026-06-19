"""Unusual options flow detection tests (snapshot volume/OI + tick sweep/block)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from tools.options.analyzer import FlowThresholds, UnusualOptionsAnalyzer
from tools.options.models import (
    ContractType,
    FlowSignalType,
    OptionContract,
    OptionSnapshot,
    OptionTrade,
    Provenance,
)

_PROV = Provenance(source="test", as_of=datetime(2026, 1, 15, tzinfo=timezone.utc), method="x")
_CALL = OptionContract(
    ticker="O:MU260116C00100000",
    underlying="MU",
    expiration=date(2026, 1, 16),
    strike=100,
    contract_type=ContractType.CALL,
)


def _snap(volume: int, oi: int) -> OptionSnapshot:
    return OptionSnapshot(contract=_CALL, open_interest=oi, day_volume=volume, provenance=_PROV)


def test_volume_oi_signal_fires_above_threshold():
    signals = UnusualOptionsAnalyzer().from_snapshots([_snap(volume=5000, oi=1000)])
    assert len(signals) == 1
    assert signals[0].signal_type is FlowSignalType.VOLUME_OI
    assert signals[0].open_interest == 1000


def test_volume_oi_signal_suppressed_below_threshold():
    assert UnusualOptionsAnalyzer().from_snapshots([_snap(volume=1000, oi=1000)]) == []


def test_tiny_oi_is_ignored_as_noise():
    assert UnusualOptionsAnalyzer().from_snapshots([_snap(volume=1000, oi=10)]) == []


def _trade(size: int, price: float, ts_ns: int, exchange: int) -> OptionTrade:
    return OptionTrade(
        contract=_CALL,
        price=price,
        size=size,
        premium=price * size * 100,
        sip_timestamp=datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc),
        exchange=exchange,
        provenance=_PROV,
    )


def test_block_signal_on_large_premium_trade():
    signals = UnusualOptionsAnalyzer().from_trades([_trade(300, 10.0, 1_700_000_000_000_000_000, 300)])
    blocks = [s for s in signals if s.signal_type is FlowSignalType.BLOCK]
    assert len(blocks) == 1
    assert blocks[0].premium == 300 * 10.0 * 100


def test_sweep_signal_across_exchanges_same_second():
    same_second = 1_700_000_000_000_000_000
    trades = [
        _trade(100, 2.3, same_second, 300),
        _trade(100, 2.3, same_second, 301),
        _trade(100, 2.3, same_second, 302),
    ]
    signals = UnusualOptionsAnalyzer().from_trades(trades)
    sweeps = [s for s in signals if s.signal_type is FlowSignalType.SWEEP]
    assert len(sweeps) == 1
    assert sweeps[0].volume == 300


def test_thresholds_are_configurable():
    analyzer = UnusualOptionsAnalyzer(FlowThresholds(min_volume_oi_ratio=10.0))
    assert analyzer.from_snapshots([_snap(volume=5000, oi=1000)]) == []  # 5x < 10x
