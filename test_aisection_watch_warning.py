"""AISection：觀望 HTML vs EQUITY QSREC 一致性警告（僅 log，不擋解析）。"""

import logging

import pytest

from schemas import AISection, MetricLine, TradeRecommendation


@pytest.mark.smoke
def test_aisection_warns_when_no_trade_legs_but_equity_qsrec_has_prices(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    rec = TradeRecommendation(
        asset="NVDA",
        direction="LONG",
        current_price=100.0,
        entry=100.0,
        target=110.0,
        stop=95.0,
        confidence=2,
        category="EQUITY",
        selection_score=80.0,
        catalyst_score=80.0,
        flow_score=80.0,
        technical_score=80.0,
        risk_fit_score=80.0,
        execution_score=80.0,
        alt_candidate_score=70.0,
        score_gap=10.0,
    )
    AISection(
        dashboard=[MetricLine(label="L", value="1")],
        pick_reason="足夠長度之本日選擇理由敘述以滿足結構化欄位要求",
        signal_conflict_summary="無",
        trade_legs=[],
        qsrec=[rec],
    )
    assert any("trade_legs 為空" in r.message and "QSREC" in r.message for r in caplog.records)


@pytest.mark.smoke
def test_aisection_no_warning_when_legs_present(caplog: pytest.LogCaptureFixture) -> None:
    from schemas import ExecutableTradeLeg

    caplog.set_level(logging.WARNING)
    leg = ExecutableTradeLeg(
        asset="NVDA",
        direction="LONG",
        current_price="100",
        star_rating=2,
        entry="100",
        target="110",
        stop="95",
        rr="1:2",
        max_drawdown_pct="-3%",
        expected_win_rate="50%",
        signal_score="60/100",
        narrative="n",
        bull_scenario="b",
        base_scenario="base",
        bear_scenario="bear",
    )
    rec = TradeRecommendation(
        asset="NVDA",
        direction="LONG",
        current_price=100.0,
        entry=100.0,
        target=110.0,
        stop=95.0,
        confidence=2,
        category="EQUITY",
        selection_score=80.0,
        catalyst_score=80.0,
        flow_score=80.0,
        technical_score=80.0,
        risk_fit_score=80.0,
        execution_score=80.0,
        alt_candidate_score=70.0,
        score_gap=10.0,
    )
    AISection(
        dashboard=[MetricLine(label="L", value="1")],
        pick_reason="足夠長度之本日選擇理由敘述以滿足結構化欄位要求",
        signal_conflict_summary="無",
        trade_legs=[leg],
        qsrec=[rec],
    )
    assert not any("trade_legs 為空" in r.message for r in caplog.records)
