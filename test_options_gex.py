"""GEX calculation golden tests (D3 standard dealer convention).

Hand-computed reference:
  call: gamma 0.05 * OI 1000 * 100 * spot^2(100^2=10000) * 0.01 = +500,000
  put:  gamma 0.04 * OI  500 * 100 * spot^2(10000)        * 0.01 = -200,000  (puts negative)
  total = +300,000
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from tools.options.analyzer import calculate_gex
from tools.options.models import (
    ContractType,
    OptionContract,
    OptionGreeks,
    OptionSnapshot,
    Provenance,
)

_PROV = Provenance(source="test", as_of=datetime(2026, 1, 15, tzinfo=timezone.utc), method="snapshot_greeks")


def _snap(ctype: ContractType, strike: float, gamma: float, oi: int) -> OptionSnapshot:
    return OptionSnapshot(
        contract=OptionContract(
            ticker=f"O:MU{ctype.value[0].upper()}{int(strike)}",
            underlying="MU",
            expiration=date(2026, 1, 16),
            strike=strike,
            contract_type=ctype,
        ),
        open_interest=oi,
        greeks=OptionGreeks(gamma=gamma),
        provenance=_PROV,
    )


def test_gex_golden_total_and_signs():
    snaps = [
        _snap(ContractType.CALL, 100, 0.05, 1000),
        _snap(ContractType.PUT, 95, 0.04, 500),
    ]
    result = calculate_gex("MU", 100.0, snaps)
    assert not isinstance(result, str)
    assert result.call_gex == 500_000.0
    assert result.put_gex == -200_000.0
    assert result.total_gex == 300_000.0
    assert result.contracts_used == 2
    assert len(result.per_strike) == 2


def test_gex_per_strike_breakdown():
    snaps = [
        _snap(ContractType.CALL, 100, 0.05, 1000),
        _snap(ContractType.PUT, 100, 0.04, 500),  # same strike
    ]
    result = calculate_gex("MU", 100.0, snaps)
    assert not isinstance(result, str)
    assert len(result.per_strike) == 1
    sg = result.per_strike[0]
    assert sg.strike == 100
    assert sg.call_gex == 500_000.0
    assert sg.put_gex == -200_000.0
    assert sg.net_gex == 300_000.0


def test_gex_missing_spot_returns_data_missing():
    snaps = [_snap(ContractType.CALL, 100, 0.05, 1000)]
    assert calculate_gex("MU", 0.0, snaps) == "[DATA_MISSING:options_gex_spot_price]"


def test_gex_missing_greeks_returns_data_missing():
    snap = OptionSnapshot(
        contract=OptionContract(
            ticker="O:MU100",
            underlying="MU",
            expiration=date(2026, 1, 16),
            strike=100,
            contract_type=ContractType.CALL,
        ),
        open_interest=1000,
        greeks=OptionGreeks(gamma=None),  # no gamma
        provenance=_PROV,
    )
    assert calculate_gex("MU", 100.0, [snap]) == "[DATA_MISSING:polygon_options_snapshot_greeks]"
