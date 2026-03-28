"""TradeRecommendation Pydantic rules (high-confidence scenarios)."""

import pytest

from pydantic import ValidationError

from schemas import TradeRecommendation


def _base_rec(**kwargs: object) -> dict[str, object]:
    d: dict[str, object] = {
        "asset": "BTC",
        "direction": "LONG",
        "current_price": 95000.0,
        "entry": 94500.0,
        "target": 100000.0,
        "stop": 91000.0,
        "confidence": 4,
        "category": "CRYPTO",
        "narrative": "ETF 淨流入延續，結構偏多。",
        "trigger": "突破前高",
        "invalidation": "跌破支撐",
        "position_pct": 5.0,
        "timeframe": "3d",
        "regime": "risk_on",
        "selection_score": 78.0,
        "catalyst_score": 80.0,
        "flow_score": 76.0,
        "technical_score": 75.0,
        "risk_fit_score": 74.0,
        "execution_score": 79.0,
        "alt_candidate_score": 63.0,
        "score_gap": 15.0,
        "repeat_days": 1,
        "bull_scenario": "突破 95k 量能延續，目標 100k。",
        "base_scenario": "區間 90–98k 機率 55%。",
        "bear_scenario": "跌破 91k 多頭失效。",
    }
    d.update(kwargs)
    return d


@pytest.mark.smoke
def test_confidence_3_requires_scenarios_and_narrative() -> None:
    TradeRecommendation(**_base_rec())

    with pytest.raises(ValidationError):
        TradeRecommendation(**_base_rec(bull_scenario=None))

    with pytest.raises(ValidationError):
        TradeRecommendation(**_base_rec(narrative="—"))


@pytest.mark.smoke
def test_confidence_2_allows_missing_scenarios() -> None:
    r = TradeRecommendation(
        **_base_rec(
            confidence=2,
            bull_scenario=None,
            base_scenario=None,
            bear_scenario=None,
        )
    )
    assert r.confidence == 2
