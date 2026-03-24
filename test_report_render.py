"""Smoke for Jinja Telegram render + structured validation."""

import pytest
from report_render import assemble_daily_brief_report, render_telegram_daily_brief
from report_validator import validate_report, validate_structured_report
from schemas import (
    AISection,
    ChatterItem,
    CryptoSection,
    ExecutableTradeLeg,
    MarketRegimeBlock,
    MetricLine,
    NewsItem,
    TradeRecommendation,
)


def _sample_news_crypto() -> list[NewsItem]:
    return [
        NewsItem(
            index=1,
            timestamp_line="[03/22 10:00 UTC+8]",
            title="T1",
            source_and_nature="來源：X｜性質：confirmed",
            summary="S1",
            investment_takeaway="投資解讀：RSI 55%",
            editor_consensus="💎主編共識：BTC",
        ),
        NewsItem(
            index=2,
            timestamp_line="[03/22 11:00 UTC+8]",
            title="T2",
            source_and_nature="來源：Y｜性質：likely",
            summary="S2",
            investment_takeaway="投資解讀：費率 0.01%",
            editor_consensus="💎主編共識：ETH",
        ),
        NewsItem(
            index=3,
            timestamp_line="[03/22 12:00 UTC+8]",
            title="T3",
            source_and_nature="來源：Z｜性質：unverified rumor",
            summary="S3",
            investment_takeaway="投資解讀：ETF 1.2%",
            editor_consensus="💎主編共識：SOL",
        ),
    ]


def _sample_news_ai() -> list[NewsItem]:
    return [
        NewsItem(
            index=4,
            timestamp_line="[03/22 13:00 UTC+8]",
            title="A1",
            source_and_nature="來源：R｜性質：confirmed",
            summary="AS1",
            investment_takeaway="投資解讀：GPU 10%",
            editor_consensus="💎主編共識：NVDA",
        ),
        NewsItem(
            index=5,
            timestamp_line="[03/22 14:00 UTC+8]",
            title="A2",
            source_and_nature="來源：R｜性質：confirmed",
            summary="AS2",
            investment_takeaway="投資解讀：資料中心 5%",
            editor_consensus="💎主編共識：AMD",
        ),
        NewsItem(
            index=6,
            timestamp_line="[03/22 15:00 UTC+8]",
            title="A3",
            source_and_nature="來源：R｜性質：confirmed",
            summary="AS3",
            investment_takeaway="投資解讀：雲端 8%",
            editor_consensus="💎主編共識：MSFT",
        ),
    ]


def _sample_trade_leg(sym: str) -> ExecutableTradeLeg:
    return ExecutableTradeLeg(
        asset=sym,
        direction="LONG",
        current_price="100",
        star_rating=3,
        entry="99",
        target="110 (+11%)",
        stop="95 (-4%)",
        rr="1:2.5",
        max_drawdown_pct="-4.0%",
        expected_win_rate="55%",
        signal_score="70/100",
        trigger="突破",
        sizing_logic="分批",
        invalidation="跌破 95",
        position_pct="5%",
        narrative="催化",
    )


def _sample_qsrec_crypto() -> TradeRecommendation:
    return TradeRecommendation(
        asset="BTC",
        direction="LONG",
        current_price=100.0,
        entry=99.0,
        target=110.0,
        stop=95.0,
        confidence=3,
        category="CRYPTO",
        narrative="n",
        trigger="t",
        invalidation="i",
        position_pct=5.0,
        timeframe="3d",
        selection_score=80.0,
        catalyst_score=80.0,
        flow_score=76.0,
        technical_score=75.0,
        risk_fit_score=74.0,
        execution_score=79.0,
        alt_candidate_score=65.0,
        score_gap=15.0,
        repeat_days=0,
    )


def _sample_qsrec_equity() -> TradeRecommendation:
    return TradeRecommendation(
        asset="NVDA",
        direction="LONG",
        current_price=900.0,
        entry=890.0,
        target=950.0,
        stop=860.0,
        confidence=3,
        category="EQUITY",
        narrative="n",
        trigger="t",
        invalidation="i",
        position_pct=5.0,
        timeframe="5d",
        selection_score=82.0,
        catalyst_score=84.0,
        flow_score=78.0,
        technical_score=80.0,
        risk_fit_score=77.0,
        execution_score=82.0,
        alt_candidate_score=66.0,
        score_gap=16.0,
        repeat_days=0,
    )


def test_render_contains_qsrec_and_passes_structured_gate():
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="risk_on", score_suffix="（+4/6）"),
        narrative_of_day="主敘事一句測試",
        macro_framework_lines=["宏觀一行"],
        dashboard=[MetricLine(label="DXY", value="104")],
        news=_sample_news_crypto(),
        chatter=[ChatterItem(text="呢喃測試（未確認）｜可信度：B｜主流媒體二次驗證：否")],
        pick_reason=(
            "本日選擇理由：現貨 ETF 淨流入與交易所淨流出同向，且資金費率與清算數據支持短線偏多，"
            "新聞面以 BTC 催化最集中，故以 BTC 為單邊主軸並以 ETH 作相對強弱配對觀察。"
        ),
        risk_budget_summary="今日風險預算：regime=risk_on 總曝險 60%",
        signal_conflict_summary="訊號衝突摘要：無顯著衝突。",
        trade_legs=[_sample_trade_leg("BTC"), _sample_trade_leg("ETH")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上：VIX 偏低"],
        dashboard=[MetricLine(label="模型熱度", value="N/A")],
        news=_sample_news_ai(),
        chatter=[ChatterItem(text="產業呢喃（未確認）｜可信度：72/100｜主流媒體二次驗證：否")],
        pick_reason=(
            "本日選擇理由：NVDA 與 AMD 於主流新聞同時具備資料中心 CAPEX 與 GPU 拉貨能見度，"
            "財報前瞻與供應鏈報導形成共振，故兩檔並列為今日美股主倉。"
        ),
        signal_conflict_summary="訊號衝突摘要：無顯著衝突。",
        trade_legs=[_sample_trade_leg("NVDA"), _sample_trade_leg("AMD")],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="【SourceHealth】 ok\n【SourceErrors】 none\n【SourceQuota】 ok\n",
        report_tier_partial_news=False,
    )
    html = render_telegram_daily_brief(report) + "x" * 3500
    assert "[QSREC_START]" in html
    assert "BTC" in html
    sres = validate_structured_report(report)
    assert sres["valid"], sres["issues"]
    vhtml = validate_report(html)
    assert vhtml["valid"], vhtml["issues"]


def _minimal_report():
    from schemas import MarketRegimeBlock, MetricLine
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="risk_on", score_suffix="（+4/6）"),
        narrative_of_day="test",
        macro_framework_lines=["macro"],
        dashboard=[MetricLine(label="DXY", value="104")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="本日選擇理由：test",
        risk_budget_summary="test",
        signal_conflict_summary="test",
        trade_legs=[],
        qsrec=[],
    )
    ai = AISection(
        macro_bridge_lines=["bridge"],
        dashboard=[MetricLine(label="熱度", value="N/A")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="本日選擇理由：test",
        signal_conflict_summary="test",
        trade_legs=[],
        qsrec=[],
    )
    return assemble_daily_brief_report(
        crypto, ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )


def test_render_raises_helpful_error_on_missing_template():
    """render_telegram_daily_brief should raise RuntimeError (not bare jinja2
    TemplateNotFound) when the template file is absent."""
    import jinja2
    from unittest.mock import patch

    report = _minimal_report()
    with patch.object(
        jinja2.Environment, "get_template",
        side_effect=jinja2.TemplateNotFound("telegram_report.j2"),
    ):
        with pytest.raises(RuntimeError, match="telegram_report.j2"):
            render_telegram_daily_brief(report)


def test_render_raises_helpful_error_on_template_syntax_error():
    """TemplateError during render should surface as RuntimeError with path info."""
    import jinja2
    from unittest.mock import patch, MagicMock

    report = _minimal_report()
    broken_tmpl = MagicMock()
    broken_tmpl.render.side_effect = jinja2.TemplateError("unexpected end of template")
    with patch.object(jinja2.Environment, "get_template", return_value=broken_tmpl):
        with pytest.raises(RuntimeError, match="telegram_report.j2"):
            render_telegram_daily_brief(report)
