"""TradeRecommendation Pydantic rules (high-confidence scenarios)."""

import pytest

from pydantic import ValidationError

from schemas import CryptoSection, TradeRecommendation


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


@pytest.mark.smoke
def test_score_gap_derived_when_omitted_but_scores_present() -> None:
    """對齊生產 STRICT_CONSISTENCY：漏填 score_gap 時由 selection − alt 導出。"""
    d = _base_rec()
    del d["score_gap"]
    r = TradeRecommendation(**d)
    assert r.score_gap == pytest.approx(78.0 - 63.0)


@pytest.mark.smoke
def test_direction_inferred_from_prices_when_field_absent() -> None:
    """LLM 漏填 direction 時，以 entry/target/stop 幾何推斷，避免 CryptoSection 解析硬失敗。"""
    d = _base_rec()
    del d["direction"]
    r = TradeRecommendation(**d)
    assert r.direction == "LONG"


@pytest.mark.smoke
def test_direction_taken_from_side_alias_when_absent() -> None:
    d = _base_rec(
        entry=100.0,
        target=90.0,
        stop=102.0,
    )
    del d["direction"]
    d["side"] = "SHORT"
    r = TradeRecommendation(**d)
    assert r.direction == "SHORT"


@pytest.mark.smoke
def test_crypto_section_backfills_qsrec_direction_from_trade_legs() -> None:
    """同段 trade_legs 有方向時，補齊 qsrec 缺漏的 direction（Crew 漂移）。

    qsrec 價位幾何若單獨推斷會偏空，但與腿方向不一致時須以 trade_legs 為準。
    """
    leg = {
        "asset": "BTC",
        "direction": "LONG",
        "current_price": "95000",
        "star_rating": 2,
        "entry": "94500",
        "target": "100000 (+5%)",
        "stop": "91000 (-4%)",
        "rr": "1:2",
        "max_drawdown_pct": "-4%",
        "expected_win_rate": "52%",
        "signal_score": "58/100",
        "trigger": "觸價",
        "sizing_logic": "分批",
        "invalidation": "跌破",
        "narrative": "測試展示句",
        "bull_scenario": "上行情境",
        "base_scenario": "中性情境",
        "bear_scenario": "下行情境",
    }
    crypto = CryptoSection.model_validate(
        {
            "report_title_date": "2026-05-08",
            "market": {"regime": "neutral"},
            "narrative_of_day": "測試敘事",
            "dashboard": [{"label": "BTC", "value": "95000"}],
            "pick_reason": "本日選擇理由足以超過三十四字長度門檻測試用內容填充",
            "risk_budget_summary": "neutral 模式下風險預算適中測試說明文字",
            "signal_conflict_summary": "空方主線測試｜多方主線測試",
            "trade_legs": [leg],
            "qsrec": [
                {
                    "asset": "BTC",
                    "category": "CRYPTO",
                    "confidence": 2,
                    "current_price": 100.0,
                    "entry": 100.0,
                    "target": 90.0,
                    "stop": 102.0,
                    "selection_score": 70.0,
                    "alt_candidate_score": 60.0,
                }
            ],
        }
    )
    assert crypto.qsrec[0].direction == "LONG"
