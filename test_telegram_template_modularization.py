"""Phase 1: modular `templates/blocks/*.j2` must match monolithic template byte-for-byte."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2 import TemplateNotFound

from report_render import (
    _INSTITUTIONAL_DISCLAIMER_HTML,
    assemble_daily_brief_report,
    build_telegram_jinja_env,
    telegram_render_context,
)
from schemas import (
    AISection,
    ChatterItem,
    CryptoSection,
    DailyBriefReport,
    ExecutableTradeLeg,
    MarketRegimeBlock,
    MetricLine,
    NewsItem,
    TradeRecommendation,
)

_ROOT = Path(__file__).resolve().parent
_MONOLITHIC_REL = Path("tests/fixtures/telegram_report_phase0_monolithic.j2")


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
            pricing_note="未定價／增量資訊",
        ),
        NewsItem(
            index=2,
            timestamp_line="[03/22 11:00 UTC+8]",
            title="T2",
            source_and_nature="來源：Y｜性質：likely",
            summary="S2",
            investment_takeaway="投資解讀：費率 0.01%",
            editor_consensus="💎主編共識：ETH",
            pricing_note="大致已定價",
        ),
        NewsItem(
            index=3,
            timestamp_line="[03/22 12:00 UTC+8]",
            title="T3",
            source_and_nature="來源：Z｜性質：unverified rumor",
            summary="S3",
            investment_takeaway="投資解讀：ETF 1.2%",
            editor_consensus="💎主編共識：SOL",
            pricing_note="已高度反應",
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
            pricing_note="未定價／增量資訊",
        ),
        NewsItem(
            index=5,
            timestamp_line="[03/22 14:00 UTC+8]",
            title="A2",
            source_and_nature="來源：R｜性質：confirmed",
            summary="AS2",
            investment_takeaway="投資解讀：資料中心 5%",
            editor_consensus="💎主編共識：AMD",
            pricing_note="大致已定價",
        ),
        NewsItem(
            index=6,
            timestamp_line="[03/22 15:00 UTC+8]",
            title="A3",
            source_and_nature="來源：R｜性質：confirmed",
            summary="AS3",
            investment_takeaway="投資解讀：雲端 8%",
            editor_consensus="💎主編共識：MSFT",
            pricing_note="已高度反應",
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
        bull_scenario="多頭：突破前高，目標 110",
        base_scenario="基礎：區間震盪，持倉觀望",
        bear_scenario="空頭：跌破 95 停損出場",
        liquidity_execution_note="主要所深度足，建議限價分批。",
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
        rr_ratio=2.5,
        max_drawdown_pct=-4.0,
        expected_win_rate=55.0,
        signal_score=70.0,
        bull_scenario="突破 100 量能延續看多。",
        base_scenario="區間 95–105 機率 50%。",
        bear_scenario="跌破 95 多頭失效。",
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
        rr_ratio=2.5,
        max_drawdown_pct=-4.0,
        expected_win_rate=55.0,
        signal_score=72.0,
        bull_scenario="財報優於預期延續漲勢。",
        base_scenario="橫盤等待指引機率 55%。",
        bear_scenario="指引失望則回調。",
    )


def _report_minimal() -> DailyBriefReport:
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="risk_on", score_suffix="（+4/6）"),
        narrative_of_day="test",
        macro_framework_lines=["macro"],
        dashboard=[MetricLine(label="DXY", value="104")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason=(
            "現貨 ETF 淨流入與交易所淨流出同向，資金費率支持短線偏多，新聞面以 BTC 催化最集中"
        ),
        risk_budget_summary="risk_on 模式下總倉位 15%",
        signal_conflict_summary="無顯著多空衝突，維持原策略執行節奏",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["bridge"],
        dashboard=[MetricLine(label="熱度", value="N/A")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason=(
            "NVDA 與 AMD 於主流新聞同時具備資料中心 CAPEX 與 GPU 拉貨能見度，財報前瞻形成共振"
        ),
        signal_conflict_summary="無顯著多空衝突，維持原策略執行節奏",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    return assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )


def _report_rich_institutional_and_source() -> DailyBriefReport:
    """`model_construct`：繞過 `assemble_daily_brief_report` 的 BQ／yfinance 副作用，仍滿足 partial tier 3–5 則新聞。"""
    crypto_news = _sample_news_crypto()[:2]
    ai_news = _sample_news_ai()[:3]
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="risk_on", score_suffix="（+4/6）"),
        narrative_of_day="主敘事一句測試",
        portfolio_framing_summary="測試組合：加密與美股雙軸在風險預算內；淨曝險偏多；與 SPY 相關性中高。",
        scenario_probability_notes=(
            "· 樂觀：延續（機率 30%）\n"
            "· 基準：震盪（機率 45%）\n"
            "· 悲觀：收縮（機率 25%）"
        ),
        crypto_cycle_valuation_notes="NVT 與儀表板一致；週期位置測試。",
        equity_valuation_framing="AI 權值溢價與利率壓力測試敘述。",
        event_calendar_lines=[
            "03/25 NVDA 財報",
            "03/26 FOMC",
            "04/01 期權到期",
        ],
        macro_framework_lines=["宏觀一行"],
        dashboard=[MetricLine(label="DXY", value="104")],
        news=crypto_news,
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
        dashboard=[
            MetricLine(label="模型熱度", value="N/A"),
            MetricLine(label="FinancialDatasets NVDA 年度損益", value="$61B"),
        ],
        news=ai_news,
        chatter=[ChatterItem(text="產業呢喃（未確認）｜可信度：72/100｜主流媒體二次驗證：否")],
        pick_reason=(
            "本日選擇理由：NVDA 與 AMD 於主流新聞同時具備資料中心 CAPEX 與 GPU 拉貨能見度，"
            "財報前瞻與供應鏈報導形成共振，故兩檔並列為今日美股主倉。"
        ),
        signal_conflict_summary="訊號衝突摘要：無顯著衝突。",
        trade_legs=[_sample_trade_leg("NVDA"), _sample_trade_leg("AMD")],
        qsrec=[_sample_qsrec_equity()],
    )
    return DailyBriefReport.model_construct(
        crypto=crypto,
        ai=ai,
        institutional_disclaimer_html=_INSTITUTIONAL_DISCLAIMER_HTML,
        previous_recs_html="<b>上期</b> <code>TEST</code>\n",
        source_observability_block="【SourceHealth】 ok\n【SourceErrors】 none\n【SourceQuota】 ok\n",
        report_tier_partial_news=True,
        low_confidence_disclaimer="",
    )


def _render_with_fixture(template_basename: str, report: DailyBriefReport) -> str:
    fixture_dir = _ROOT / "tests" / "fixtures"
    env = build_telegram_jinja_env(fixture_dir)
    ctx = telegram_render_context(report)
    try:
        tmpl = env.get_template(template_basename)
    except TemplateNotFound as exc:
        raise AssertionError(
            f"Fixture template missing: {fixture_dir / template_basename}"
        ) from exc
    return tmpl.render(**ctx)


@pytest.mark.smoke
def test_monolithic_fixture_exists():
    path = _ROOT / _MONOLITHIC_REL
    assert path.is_file(), f"Commit monolithic baseline at {path}"


@pytest.mark.smoke
@pytest.mark.parametrize(
    "factory",
    [_report_minimal, _report_rich_institutional_and_source],
    ids=["minimal", "rich_partial_news_source"],
)
def test_modular_template_byte_matches_monolithic_fixture(factory):
    """Merge gate: `templates/telegram_report.j2` (macros) ≡ frozen monolithic Jinja."""
    report = factory()
    modular = build_telegram_jinja_env(_ROOT / "templates").get_template(
        "telegram_report.j2"
    ).render(**telegram_render_context(report))
    mono = _render_with_fixture("telegram_report_phase0_monolithic.j2", report)
    assert modular == mono, (
        "Modular telegram_report.j2 diverged from phase-0 monolithic fixture "
        f"(len modular={len(modular)} mono={len(mono)}). First diff index: "
        f"{next((i for i, (a, b) in enumerate(zip(modular, mono)) if a != b), 'n/a')}"
    )


@pytest.mark.boundary
def test_modular_template_matches_constructed_partial_news_low_confidence():
    """Edge: partial tier + low_confidence without assemble (model_construct)."""
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="X", value="1")],
        news=[],
        chatter=[],
        pick_reason="p",
        risk_budget_summary="r",
        signal_conflict_summary="s",
        trade_legs=[],
        qsrec=[],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="Y", value="2")],
        news=[],
        chatter=[],
        pick_reason="ap",
        signal_conflict_summary="as",
        trade_legs=[],
        qsrec=[],
    )
    report = DailyBriefReport.model_construct(
        crypto=crypto,
        ai=ai,
        institutional_disclaimer_html="",
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=True,
        low_confidence_disclaimer="低信心免責測試",
    )
    modular = build_telegram_jinja_env(_ROOT / "templates").get_template(
        "telegram_report.j2"
    ).render(**telegram_render_context(report))
    mono = _render_with_fixture("telegram_report_phase0_monolithic.j2", report)
    assert modular == mono
