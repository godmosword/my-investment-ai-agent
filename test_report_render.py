"""Smoke for Jinja Telegram render + structured validation."""

import os
from unittest.mock import patch

import pytest
from report_html_gates import _REPEAT_PICK_REASON_RE
from report_render import assemble_daily_brief_report, instrument_sections_for_ib_layout, render_telegram_daily_brief
from report_html_gates import validate_report
from schemas import (
    validate_structured_report,
    AISection,
    ChatterItem,
    CryptoSection,
    ExecutableTradeLeg,
    MarketRegimeBlock,
    MetricLine,
    NewsItem,
    TradeRecommendation,
    QSREC_JSON_EXCLUDE_FIELDS,
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


def test_auto_repeat_pick_prefix_matches_rotation_gate_regex():
    """assemble 自動補註前綴須命中 _REPEAT_PICK_REASON_RE（與 STRICT_PICK_ROTATION 一致）。"""
    from validation_rules import _REPEAT_SAME_YESTERDAY_PREFIX

    assert _REPEAT_PICK_REASON_RE.search(_REPEAT_SAME_YESTERDAY_PREFIX), (
        "prefix must satisfy repeat-pick reason pattern"
    )


def test_auto_repeat_pick_disclaimer_when_yesterday_matches():
    """BQ 昨日標的與今日相同時自動前綴「連日維持…」（略過 LLM 漏寫，避免與模板「本日選擇理由：」雙重抬頭）。"""

    def _yesterday(cat: str):
        return {"BTC"} if cat == "CRYPTO" else {"NVDA"}

    crypto = CryptoSection(
        report_title_date="2025-03-22",
        exec_summary=["→ 測試"],
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason=(
            "僅寫催化與鏈上與估值錨，未含官方重複選用片語；仍點名 BTC 作為主倉配置。"
        ),
        risk_budget_summary="neutral 20%",
        signal_conflict_summary="空｜多",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason=(
            "財報與資料中心敘事延續，未寫跨日倉位延續說明；仍點名 NVDA 作為核心持倉標的。"
        ),
        signal_conflict_summary="無",
        trade_legs=[_sample_trade_leg("NVDA")],
        qsrec=[_sample_qsrec_equity()],
    )
    with patch("report_html_gates._fetch_yesterday_qsrec_canonical_set", side_effect=_yesterday):
        report = assemble_daily_brief_report(
            crypto,
            ai,
            previous_recs_html="",
            source_observability_block="",
            report_tier_partial_news=False,
        )
    assert report.crypto.pick_reason.startswith("連日維持")
    assert report.ai.pick_reason.startswith("連日維持")


def test_auto_repeat_pick_disclaimer_skipped_when_env_off(monkeypatch):
    monkeypatch.setenv("AUTO_REPEAT_PICK_DISCLAIMER", "0")

    def _yesterday(cat: str):
        return {"BTC"} if cat == "CRYPTO" else {"NVDA"}

    crypto = CryptoSection(
        report_title_date="2025-03-22",
        exec_summary=["→ 測試"],
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason=(
            "僅寫催化與鏈上與估值錨，未含官方重複選用片語；仍點名 BTC 作為主倉配置。"
        ),
        risk_budget_summary="neutral 20%",
        signal_conflict_summary="空｜多",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason=(
            "財報與資料中心敘事延續，未寫跨日倉位延續說明；仍點名 NVDA 作為核心持倉標的。"
        ),
        signal_conflict_summary="無",
        trade_legs=[_sample_trade_leg("NVDA")],
        qsrec=[_sample_qsrec_equity()],
    )
    with patch("report_html_gates._fetch_yesterday_qsrec_canonical_set", side_effect=_yesterday):
        report = assemble_daily_brief_report(
            crypto,
            ai,
            previous_recs_html="",
            source_observability_block="",
            report_tier_partial_news=False,
        )
    assert not report.crypto.pick_reason.startswith("連日維持")
    assert not report.ai.pick_reason.startswith("連日維持")


@pytest.mark.smoke
def test_chatter_item_credibility_autofill_uses_reader_safe_suffix():
    c = ChatterItem(text="機構傳聞（未確認）｜來源：側寫")
    assert "自動補填" not in c.text
    assert "｜可信度：C｜主流媒體二次驗證：否" in c.text


@pytest.mark.smoke
def test_chatter_item_downgrades_credibility_a_when_unconfirmed():
    c = ChatterItem(
        text="測試傳聞（未確認）｜來源：側寫｜可信度：A｜主流媒體二次驗證：否"
    )
    assert "可信度：B" in c.text
    assert "可信度：A" not in c.text


@pytest.mark.smoke
def test_assemble_ib_layout_dashboard_groups_and_block4_summary():
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        investment_thesis_one_liner="BTC 與美股雙軸在風險預算內偏多。",
        thesis_supporting_points=["論點甲：ETF 流與儀表板一致", "論點乙：鏈上費率偏多"],
        thesis_contrary_points=["反駁甲：清算壓力", "反駁乙：利率重訂"],
        key_assumptions_lines=["假設一：流動性大致穩定", "假設二：主要標的深度足"],
        narrative_invalidation_summary="若 ETF 資金流逆轉則重估。",
        dashboard=[
            MetricLine(label="VIX", value="<code>20</code>"),
            MetricLine(label="資金費率", value="<code>0.01</code>"),
            MetricLine(label="BTC RSI", value="<code>55</code>"),
        ],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="現貨 ETF 淨流入與監管新聞構成催化，鏈上資金費率與多空比同步支持偏多結構，選 BTC 作為單邊主倉。",
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="空方主線一句｜多方主線一句",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[
            MetricLine(label="NVDA yfinance", value="1"),
            MetricLine(label="NVDA FinancialDatasets", value="2"),
        ],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
        signal_conflict_summary="無",
        trade_legs=[_sample_trade_leg("NVDA")],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="【SourceHealth】 ok",
        report_tier_partial_news=False,
    )
    html = render_telegram_daily_brief(report)
    assert "掃讀順序" in html
    assert "· <b>宏觀與跨資產</b>" in html or "宏觀與跨資產" in html
    assert "<b>加密部位摘要</b>" in html
    assert "<b>美股部位摘要</b>" in html
    assert "【機構速讀｜命題與情境】" in html
    assert "【投資命題】" in html
    assert "【SourceHealth】" in html
    assert "[QSREC_START]" in html
    assert html.find("【SourceHealth】") < html.find("[QSREC_START]")


@pytest.mark.smoke
def test_assemble_fills_empty_trade_leg_position_pct():
    leg_crypto = _sample_trade_leg("BTC").model_copy(update={"position_pct": ""})
    leg_ai = _sample_trade_leg("NVDA").model_copy(update={"position_pct": "   "})
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="催化與鏈上支持 BTC 主軸敘述足夠長度以通過 gate 最小要求欄位",
        risk_budget_summary="neutral 模式下總曝險 40%",
        signal_conflict_summary="空｜多",
        trade_legs=[leg_crypto],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
        signal_conflict_summary="無",
        trade_legs=[leg_ai],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert report.crypto.trade_legs[0].position_pct.strip().endswith("%")
    assert float(report.crypto.trade_legs[0].position_pct.replace("%", "").strip()) > 0
    assert report.ai.trade_legs[0].position_pct.strip().endswith("%")


def _sum_leg_position_pct(legs: list) -> float:
    return sum(float(x.position_pct.replace("%", "").strip()) for x in legs)


@pytest.mark.smoke
def test_assemble_scales_two_equity_legs_to_combined_cap_neutral():
    leg_nvda = _sample_trade_leg("NVDA").model_copy(update={"position_pct": "8%"})
    leg_msft = _sample_trade_leg("MSFT").model_copy(update={"position_pct": "8%"})
    msft_qsrec = _sample_qsrec_equity().model_copy(
        update={
            "asset": "MSFT",
            "current_price": 373.0,
            "entry": 373.0,
            "target": 345.0,
            "stop": 390.0,
        }
    )
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="催化與鏈上支持 BTC 主軸敘述足夠長度以通過 gate 最小要求欄位",
        risk_budget_summary="neutral 模式下總曝險 40%",
        signal_conflict_summary="空｜多",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="NVDA 與 MSFT 財報前瞻與資料中心 Capex 敘事強化，兩檔並列為今日美股主倉。",
        signal_conflict_summary="無",
        trade_legs=[leg_nvda, leg_msft],
        qsrec=[_sample_qsrec_equity(), msft_qsrec],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert len(report.ai.trade_legs) == 2
    assert abs(_sum_leg_position_pct(report.ai.trade_legs) - 10.0) < 0.05
    a, b = (
        float(report.ai.trade_legs[0].position_pct.replace("%", "").strip()),
        float(report.ai.trade_legs[1].position_pct.replace("%", "").strip()),
    )
    assert abs(a - b) < 0.01
    assert abs(a - 5.0) < 0.01


@pytest.mark.smoke
def test_assemble_clamps_single_equity_leg_to_regime_cap():
    leg = _sample_trade_leg("NVDA").model_copy(update={"position_pct": "12%"})
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="催化與鏈上支持 BTC 主軸敘述足夠長度以通過 gate 最小要求欄位",
        risk_budget_summary="neutral 模式下總曝險 40%",
        signal_conflict_summary="空｜多",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
        signal_conflict_summary="無",
        trade_legs=[leg],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert float(report.ai.trade_legs[0].position_pct.replace("%", "").strip()) == 10.0


@pytest.mark.smoke
def test_assemble_rewrites_leading_repeat_reason_when_same_yesterday():
    def _yesterday(cat: str):
        return {"BTC"} if cat == "CRYPTO" else {"NVDA"}

    crypto = CryptoSection(
        report_title_date="2025-03-22",
        exec_summary=["→ 測試"],
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason=(
            "重複選用理由：BTC 跌破 MA50 與 VIX 期限倒掛同時成立，政策面 401(k) 仍屬提議階段；"
            "連日敘事仍支持防禦性空頭，故維持與昨日相同之風險框定與倉位紀律。"
        ),
        risk_budget_summary="neutral 20%",
        signal_conflict_summary="空｜多",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason=(
            "重複選股理由：NVDA 與 MSFT 在財報前瞻與資料中心 Capex 敘事上仍具能見度，"
            "惟 VIX Backwardation 與流動性收縮壓制估值；連日維持防禦空頭符合昨日 BQ 標的組合。"
        ),
        signal_conflict_summary="無",
        trade_legs=[_sample_trade_leg("NVDA")],
        qsrec=[_sample_qsrec_equity()],
    )
    with patch("report_html_gates._fetch_yesterday_qsrec_canonical_set", side_effect=_yesterday):
        report = assemble_daily_brief_report(
            crypto,
            ai,
            previous_recs_html="",
            source_observability_block="",
            report_tier_partial_news=False,
        )
    assert report.crypto.pick_reason.startswith("連日維持與昨日相同建議標的")
    assert "BTC 跌破 MA50" in report.crypto.pick_reason
    assert report.ai.pick_reason.startswith("連日維持與昨日相同建議標的")
    assert "NVDA 與 MSFT" in report.ai.pick_reason


@pytest.mark.smoke
def test_assemble_strips_erroneous_repeat_label_when_yesterday_differs():
    def _yesterday(cat: str):
        return {"ETH"} if cat == "CRYPTO" else {"MSFT"}

    crypto = CryptoSection(
        report_title_date="2025-03-22",
        exec_summary=["→ 測試"],
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason=(
            "重複選用理由：本日加密 QSREC 已輪動至 BTC 主軸，與昨日 ETH 主敘事不同；"
            "VIX 高企下仍採防禦倉位，此處不應再標「重複選用」抬頭，僅保留催化與技術面依據敘述。"
        ),
        risk_budget_summary="neutral 20%",
        signal_conflict_summary="空｜多",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason=(
            "重複選股理由：美股段已自昨日兩檔切換敘事，NVDA 仍為核心但 MSFT 權重調整；"
            "不應沿用「重複選股」標籤，以下僅陳述電力成本與流動性對估值之壓力。"
        ),
        signal_conflict_summary="無",
        trade_legs=[_sample_trade_leg("NVDA")],
        qsrec=[_sample_qsrec_equity()],
    )
    with patch("report_html_gates._fetch_yesterday_qsrec_canonical_set", side_effect=_yesterday):
        report = assemble_daily_brief_report(
            crypto,
            ai,
            previous_recs_html="",
            source_observability_block="",
            report_tier_partial_news=False,
        )
    assert report.crypto.pick_reason.startswith("本日加密 QSREC")
    assert "不應再標" in report.crypto.pick_reason
    assert report.ai.pick_reason.startswith("美股段已自昨日")
    assert "不應沿用" in report.ai.pick_reason


@pytest.mark.smoke
def test_assemble_prepends_regime_when_risk_budget_has_no_english_token():
    """LLM 僅輸出中文風險預算時，assemble 補上 canonical regime，通過 DailyBriefReport 結構化驗證。"""
    crypto = CryptoSection(
        report_title_date="2026-03-30",
        exec_summary=["→ 測試"],
        market=MarketRegimeBlock(regime="neutral", score_suffix="（0/6）"),
        narrative_of_day="主敘事",
        macro_framework_lines=["宏觀"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="ETF 淨流入與鏈上數據支持風險資產，本日選擇理由含催化與估值錨敘述。",
        risk_budget_summary="中性體制下總曝險約四成，單筆倉位遵上限。",
        signal_conflict_summary="空｜多",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=["承上"],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="NVDA 財報前瞻與 GPU 拉貨見於主流新聞，資料中心 Capex 敘事強化，故選 NVDA。",
        signal_conflict_summary="無",
        trade_legs=[_sample_trade_leg("NVDA")],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
        agreed_regime="neutral",
    )
    assert report.crypto.risk_budget_summary.startswith("neutral")
    assert "中性體制" in report.crypto.risk_budget_summary
    v = validate_structured_report(report)
    assert v["valid"], v["issues"]


def test_qsrec_json_excludes_internal_reasoning():
    raw = TradeRecommendation(
        asset="BTC",
        direction="LONG",
        current_price=1.0,
        entry=1.0,
        target=2.0,
        stop=0.5,
        confidence=2,
        category="CRYPTO",
        internal_reasoning="SECRET_COT_SHOULD_NOT_LEAK",
        narrative="公開敘事",
    ).model_dump(exclude_none=True, exclude=QSREC_JSON_EXCLUDE_FIELDS)
    assert "internal_reasoning" not in raw
    assert raw.get("narrative") == "公開敘事"


def test_render_contains_qsrec_and_passes_structured_gate():
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
        dashboard=[MetricLine(label="模型熱度", value="N/A"), MetricLine(label="FinancialDatasets NVDA 年度損益", value="$61B")],
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
    # 固定樣本新聞為 03/22；本測試重點在 QSREC／結構化 gate，非新聞新鮮度（見 test_news_freshness.py）。
    with patch.dict(os.environ, {"STRICT_NEWS_FRESHNESS_GATE": "0"}, clear=False):
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


def test_render_strips_dollar_from_trade_leg_fields():
    """entry/target/stop with a leading '$' should be stripped in rendered HTML."""
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
        trade_legs=[
            ExecutableTradeLeg(
                asset="BTC",
                direction="LONG",
                current_price="$95000",
                star_rating=3,
                entry="$94500",
                target="$100000",
                stop="$91000",
                rr="1:2.5",
                max_drawdown_pct="-4.0%",
                expected_win_rate="55%",
                signal_score="70/100",
                trigger="突破前高",
                sizing_logic="分批建倉",
                invalidation="跌破 91000 則失效。",
                position_pct="5%",
                narrative="催化",
                bull_scenario="突破前高延續。",
                base_scenario="區間震盪。",
                bear_scenario="跌破停損。",
            )
        ],
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
    report = assemble_daily_brief_report(
        crypto, ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    html = render_telegram_daily_brief(report)
    # entry/target/stop should appear without a leading '$' inside <code> tags
    assert "<code>94500</code>" in html, "entry '$94500' should be stripped to '94500'"
    assert "<code>100000</code>" in html, "target '$100000' should be stripped to '100000'"
    assert "<code>91000</code>" in html, "stop '$91000' should be stripped to '91000'"
    # The hardcoded '$' prefix on current_price should still appear
    assert "$95000" in html


def test_clean_invalidation_anchored_strip():
    """_clean_invalidation: strips leading 若 only, preserves compound words."""
    from report_render import _clean_invalidation

    # Leading bare 若 with space — stripped
    assert _clean_invalidation("若 BTC跌破50000則失效。") == "BTC跌破50000"
    # Leading bare 若 without space — stripped
    assert _clean_invalidation("若BTC跌破50000則失效。") == "BTC跌破50000"
    # Compound word 如若 — 若 must NOT be stripped (would garble the word)
    result = _clean_invalidation("如若BTC跌破50000則失效。")
    assert result == "如若BTC跌破50000", f"Got: {result!r}"
    # Mid-string 則失效。 — stripped even when not at end-of-string
    result = _clean_invalidation("若跌破支撐則失效。反之突破則看漲")
    assert "則失效" not in result, f"則失效 should be stripped mid-string; got: {result!r}"
    assert "反之突破則看漲" in result, f"Text after 則失效 should be preserved; got: {result!r}"
    # None input → empty string
    assert _clean_invalidation(None) == ""
    # Double period collapsed
    assert _clean_invalidation("跌破50000。。") == "跌破50000。"


@patch("main._get_extended_price_data")
def test_ensure_btc_ma_dashboard_rows_inserts_after_btc_spot(mock_ext, monkeypatch):
    monkeypatch.delenv("MOCK_APIS", raising=False)
    monkeypatch.delenv("SKIP_BTC_MA_DASHBOARD_INJECT", raising=False)
    mock_ext.return_value = {
        "ma20": 68781.12,
        "ma50": 68627.0,
        "close": 69199.0,
        "rsi14": 54.4,
    }
    from report_render import _ensure_btc_ma_dashboard_rows

    crypto = CryptoSection(
        report_title_date="2026-04-06",
        exec_summary=[],
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[
            MetricLine(label="BTC 現價", value="$69,199.42"),
            MetricLine(label="BTC RSI(14)", value="54.40"),
        ],
        news=_sample_news_crypto(),
        x_highlights=[],
        chatter=[
            ChatterItem(
                text="流動性（未確認）｜來源：a｜可信度：B｜主流媒體二次驗證：否"
            )
        ],
        pick_reason="x" * 40,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    out = _ensure_btc_ma_dashboard_rows(crypto)
    assert len(out.dashboard) == len(crypto.dashboard) + 2
    labels_vals = [(r.label, r.value) for r in out.dashboard]
    assert any("MA20" in lab for lab, _ in labels_vals)
    assert any("MA50" in lab for lab, _ in labels_vals)
    mock_ext.assert_called_once()


def test_sync_dashboard_btc_rsi_emoji_matches_scorecard():
    from report_render import _sync_dashboard_btc_rsi_with_scorecard

    crypto = CryptoSection(
        report_title_date="2026-04-10",
        exec_summary=[],
        market=MarketRegimeBlock(
            regime="risk_on",
            score_suffix="（+4/6）",
            scorecard_lines=[
                "✅ VIX <code>18.0(<20)</code>→+1 | ✅ BTC RSI <code>55.0(45–65)</code>→+1",
            ],
        ),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[
            MetricLine(label="BTC RSI(14)", value="55.0", status_emoji="⬜"),
        ],
        news=_sample_news_crypto(),
        x_highlights=[],
        chatter=[
            ChatterItem(
                text="流動性（未確認）｜來源：a｜可信度：B｜主流媒體二次驗證：否"
            )
        ],
        pick_reason="x" * 40,
        risk_budget_summary="risk_on 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    out = _sync_dashboard_btc_rsi_with_scorecard(crypto)
    rsi_rows = [r for r in out.dashboard if "RSI" in (r.label or "").upper() and "BTC" in (r.label or "").upper()]
    assert rsi_rows
    assert rsi_rows[0].status_emoji == "✅"


def test_normalize_btc_ma_citations_aligns_nearby_dollar_to_dashboard():
    from report_render import _normalize_btc_ma_citations_from_dashboard

    crypto = CryptoSection(
        report_title_date="2026-04-10",
        exec_summary=[],
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="BTC MA20 支撐於 $69155.98 附近",
        macro_framework_lines=[],
        dashboard=[
            MetricLine(label="BTC MA20（日線）", value="$69,156.64", status_emoji="⬜"),
            MetricLine(label="BTC MA50（日線）", value="$68,627.00", status_emoji="⬜"),
        ],
        news=_sample_news_crypto(),
        x_highlights=[],
        chatter=[
            ChatterItem(
                text="流動性（未確認）｜來源：a｜可信度：B｜主流媒體二次驗證：否"
            )
        ],
        pick_reason="x" * 40,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    out = _normalize_btc_ma_citations_from_dashboard(crypto)
    assert "$69,156.64" in (out.narrative_of_day or "")
    assert "69155.98" not in (out.narrative_of_day or "")


def test_ensure_crypto_liquidation_fallback_note_appends_when_absent():
    from report_render import _ensure_crypto_liquidation_fallback_note

    crypto = CryptoSection(
        report_title_date="2025-03-22",
        exec_summary=["→ t"],
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC 資金費率", value="0.01%")],
        news=_sample_news_crypto(),
        x_highlights=[],
        chatter=[
            ChatterItem(
                text="假日流動性（未確認）｜來源：a｜可信度：B｜主流媒體二次驗證：否"
            )
        ],
        pick_reason="x" * 40,
        risk_budget_summary="y",
        signal_conflict_summary="空方｜多方",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    out = _ensure_crypto_liquidation_fallback_note(crypto)
    assert len(out.dashboard) == len(crypto.dashboard) + 1
    assert "爆倉" in out.dashboard[-1].value


@patch("report_render._current_prices_for_assets")
def test_assemble_backfills_na_equity_prices_and_synth_target_stop(mock_pf, monkeypatch):
    monkeypatch.delenv("MOCK_APIS", raising=False)
    monkeypatch.delenv("SKIP_EQUITY_YF_BACKFILL", raising=False)
    mock_pf.return_value = {"TST": 50.0}
    ai = AISection(
        dashboard=[MetricLine(label="L", value="1")],
        news=_sample_news_ai(),
        pick_reason="p" * 40,
        signal_conflict_summary="a｜b",
        trade_legs=[
            ExecutableTradeLeg(
                asset="TST",
                direction="LONG",
                current_price="N/A",
                star_rating=2,
                entry="N/A",
                target="N/A",
                stop="N/A",
                rr="1:2.5",
                max_drawdown_pct="-4.0%",
                expected_win_rate="55%",
                signal_score="70/100",
                trigger="t",
                sizing_logic="s",
                invalidation="i",
                position_pct="5%",
                narrative="n",
                bull_scenario="b",
                base_scenario="base",
                bear_scenario="bear",
            )
        ],
        qsrec=[_sample_qsrec_equity()],
    )
    crypto = CryptoSection(
        report_title_date="2025-03-22",
        exec_summary=[],
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_crypto(),
        x_highlights=[],
        chatter=[
            ChatterItem(
                text="流動性（未確認）｜來源：a｜可信度：B｜主流媒體二次驗證：否"
            )
        ],
        pick_reason="x" * 40,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[_sample_trade_leg("BTC")],
        qsrec=[_sample_qsrec_crypto()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    leg = report.ai.trade_legs[0]
    assert leg.current_price == "50.00"
    assert leg.entry == "50.00"
    assert "55" in leg.target and "%" in leg.target
    assert "48" in leg.stop and "%" in leg.stop
    mock_pf.assert_called_once()


def test_chatter_item_appends_msm_when_credibility_inline_only():
    item = ChatterItem(text="流動性傳聞（未確認）｜來源：社群｜可信度：B")
    assert "主流媒體二次驗證" in item.text


def test_assemble_neutralizes_halving_calendar_row():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        event_calendar_lines=[
            "04/10 BTC 月度期權到期",
            "04/12 PPI",
            "04/20 BTC 預期減半日（區塊高度 840,000）",
        ],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    cal = report.crypto.event_calendar_lines
    assert len(cal) == 3
    assert "840" not in cal[2] or "略過" in cal[2]
    assert "減半" not in cal[2] or "略過" in cal[2]


def test_assemble_strips_scenario_probability_leading_bullets():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        scenario_probability_notes=(
            "· 樂觀：x（機率 30%）\n"
            "· 基準：y（機率 45%）\n"
            "· 悲觀：z（機率 25%）"
        ),
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    lines = [ln for ln in report.crypto.scenario_probability_notes.split("\n") if ln.strip()]
    assert len(lines) == 3
    assert not lines[0].lstrip().startswith("·")


def test_assemble_fixes_scenario_btc_76k_typo_when_spot_above_50k():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[
            MetricLine(label="BTC 現價", value="$73,000.62"),
            MetricLine(label="ETH 現價", value="2000"),
        ],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        scenario_probability_notes=(
            "· 樂觀：BTC 若突破 7.6k 阻力結構（機率 30%）\n"
            "· 基準：y（機率 45%）\n"
            "· 悲觀：z（機率 25%）"
        ),
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    scen = report.crypto.scenario_probability_notes
    assert "76k" in scen
    assert "7.6k" not in scen.lower()


def test_assemble_keeps_scenario_7_6k_when_btc_spot_not_above_50k():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[
            MetricLine(label="BTC 現價", value="$42,000"),
        ],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        scenario_probability_notes=(
            "· 樂觀：BTC 若突破 7.6k 阻力（機率 30%）\n"
            "· 基準：y（機率 45%）\n"
            "· 悲觀：z（機率 25%）"
        ),
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert "7.6k" in report.crypto.scenario_probability_notes.lower()


def test_instrument_sections_strip_placeholder_section_rows_and_dedup_headers():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[
            MetricLine(label="價格與技術結構", value="   ", is_section_header=False),
            MetricLine(label="價格與技術結構", value=" ", is_section_header=True),
            MetricLine(label="價格與技術結構", value=" ", is_section_header=True),
            MetricLine(label="BTC 現價", value="$70,000"),
        ],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    cr, _ai2 = instrument_sections_for_ib_layout(crypto, ai)
    assert not any(
        (r.label or "").strip() == "價格與技術結構"
        and not getattr(r, "is_section_header", False)
        and not (r.value or "").strip()
        for r in cr.dashboard
    )
    for i in range(len(cr.dashboard) - 1):
        a, b = cr.dashboard[i], cr.dashboard[i + 1]
        if getattr(a, "is_section_header", False) and getattr(b, "is_section_header", False):
            assert (a.label or "").strip() != (b.label or "").strip()


def test_assemble_syncs_invalidation_when_macro_contango_and_backwardation():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=["VIX 期貨維持 Contango"],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        narrative_invalidation_summary="若 VIX 期限結構轉為 Backwardation 則命題失效。",
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert "Backwardation" not in report.crypto.narrative_invalidation_summary
    assert "VIX 現貨升破 25" in report.crypto.narrative_invalidation_summary


def test_assemble_fills_crypto_fd_from_ai_dashboard():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[
            MetricLine(
                label="MSFT FinancialDatasets Revenue",
                value="N/A (第三方資料源未回傳)",
            )
        ],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[
            MetricLine(
                label="FinancialDatasets MSFT 營收",
                value="<code>$61.86B</code>",
            )
        ],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    msft_row = next(r for r in report.crypto.dashboard if "MSFT" in r.label)
    assert "N/A" not in msft_row.value
    assert "61.86" in msft_row.value


def test_assemble_scrubs_halving_from_crypto_cycle_notes():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        crypto_cycle_valuation_notes="BTC 處於減半前夕，區塊高度 840,000 將至。",
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert "略" in report.crypto.crypto_cycle_valuation_notes or "移除" in report.crypto.crypto_cycle_valuation_notes


def test_assemble_softens_exec_summary_history_slogan():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        exec_summary=["→ 歷史顯示此為反彈前兆"],
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert "歷史顯示" not in report.crypto.exec_summary[0]


def test_assemble_strips_calendar_notionals_from_unrelated_news_takeaway():
    news = list(_sample_news_crypto())
    news[0] = news[0].model_copy(
        update={
            "investment_takeaway": (
                "投資解讀：法律風險降低；總持倉 $28.5B 衍生品結構支撐修復行情。"
            )
        }
    )
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=news,
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        event_calendar_lines=["04/10 BTC 期權到期（名目價值 $28.5B）"],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    n1 = report.crypto.news[0]
    assert "28.5" not in n1.investment_takeaway
    assert "法律" in n1.investment_takeaway or "降低" in n1.investment_takeaway


def test_assemble_neutral_softens_risk_on_phrases_in_portfolio_and_exec():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        exec_summary=["→ 維持跨資產偏多配置"],
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        portfolio_framing_summary="同步做多偏好，總曝險 40%。",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert "同步做多偏好" not in report.crypto.portfolio_framing_summary
    assert "跨資產偏多配置" not in report.crypto.exec_summary[0]


def test_assemble_removes_generic_event_calendar_rows():
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
        event_calendar_lines=[
            "04/12 礦企季報披露與算力調整公告",
            "04/15 Fed 官員就流動性釋放發表談話",
            "04/10 已核實之具體事件",
        ],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    cal = report.crypto.event_calendar_lines
    assert len(cal) == 1
    assert "04/10" in cal[0]


def test_assemble_fixes_chatter_missing_unconfirmed():
    from schemas import ChatterItem

    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[
            ChatterItem(text="傳 AWS 內部測試｜可信度：B"),
        ],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=_sample_news_ai(),
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    assert "（未確認）" in report.crypto.chatter[0].text


def test_assemble_softens_ai_news_beat_without_consensus_headline():
    ai_news = list(_sample_news_ai())
    ai_news[0] = ai_news[0].model_copy(
        update={
            "title": "Wearable launch",
            "summary": "新硬體發表。",
            "investment_takeaway": "營收超預期帶動估值。",
        }
    )
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=ai_news,
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    tw = report.ai.news[0].investment_takeaway
    assert "超預期" not in tw


def test_assemble_softens_equity_trigger_beat_without_consensus():
    leg = _sample_trade_leg("NVDA").model_copy(
        update={"trigger": "訂閱數據超預期且站穩支撐"}
    )
    def _bare(idx: int) -> NewsItem:
        return NewsItem(
            index=idx,
            timestamp_line="[03/22 13:00 UTC+8]",
            title="產業動態",
            summary="事件更新。",
            source_and_nature="來源：R｜性質：confirmed",
            investment_takeaway="投資解讀：敘事延續。",
            editor_consensus="💎主編共識：觀察龍頭",
            pricing_note="未定價／增量資訊",
        )

    bare_ai_news = [_bare(4), _bare(5), _bare(6)]
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=bare_ai_news,
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[leg],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    tr = report.ai.trade_legs[0].trigger
    assert "超預期" not in tr


def test_assemble_rewrites_editor_consensus_ticker_not_in_legs():
    ai_news = list(_sample_news_ai())
    ai_news[0] = ai_news[0].model_copy(
        update={"editor_consensus": "利好 $ONDO 敘事"}
    )
    crypto = CryptoSection(
        report_title_date="2026-04-09",
        market=MarketRegimeBlock(regime="neutral", score_suffix=""),
        narrative_of_day="n",
        macro_framework_lines=[],
        dashboard=[MetricLine(label="BTC", value="1")],
        news=_sample_news_crypto(),
        chatter=[],
        pick_reason="p" * 50,
        risk_budget_summary="neutral 模式下總風險預算 40%",
        signal_conflict_summary="a｜b",
        trade_legs=[],
        qsrec=[_sample_qsrec_crypto()],
    )
    ai = AISection(
        macro_bridge_lines=[],
        dashboard=[MetricLine(label="x", value="1")],
        news=ai_news,
        chatter=[],
        pick_reason="p" * 50,
        signal_conflict_summary="a｜b",
        trade_legs=[_sample_trade_leg("NVDA"), _sample_trade_leg("MSFT")],
        qsrec=[_sample_qsrec_equity()],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
    )
    ec = report.ai.news[0].editor_consensus
    assert "$ONDO" not in ec
    assert "ONDO" in ec
