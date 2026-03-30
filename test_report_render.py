"""Smoke for Jinja Telegram render + structured validation."""

from unittest.mock import patch

import pytest
from report_render import assemble_daily_brief_report, render_telegram_daily_brief
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
        bull_scenario="多頭：突破前高，目標 110",
        base_scenario="基礎：區間震盪，持倉觀望",
        bear_scenario="空頭：跌破 95 停損出場",
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


def test_auto_repeat_pick_disclaimer_when_yesterday_matches():
    """BQ 昨日標的與今日相同時自動前綴「重複選用理由」（略過 LLM 漏寫）。"""

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
    assert report.crypto.pick_reason.startswith("重複選用理由：")
    assert report.ai.pick_reason.startswith("重複選用理由：")


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
    assert not report.crypto.pick_reason.startswith("重複選用理由：")
    assert not report.ai.pick_reason.startswith("重複選用理由：")


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
