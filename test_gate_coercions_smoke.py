"""Smoke tests for P1 gate coercions (validation_rules + report_render + schemas)."""

import pytest

from report_render import (
    _coerce_sections_for_gate,
    _low_confidence_disclaimer_plain,
    assemble_daily_brief_report,
)
from schemas import (
    AISection,
    CryptoSection,
    ExecutableTradeLeg,
    MarketRegimeBlock,
    MetricLine,
    NewsItem,
    TradeRecommendation,
)
from validation_rules import (
    crypto_risk_budget_has_regime_token,
    ensure_crypto_risk_budget_regime_token,
    ensure_news_timestamp_line_utc8,
    normalize_authoritative_regime_tokens_multiline,
    normalize_leading_repeat_pick_phrase,
    sanitize_lines_with_us_treasury_keyword,
    sanitize_us_treasury_yield_tokens_in_line,
)


@pytest.mark.smoke
def test_ensure_news_timestamp_line_utc8_appends():
    assert "[03/22 10:00 UTC+8]" == ensure_news_timestamp_line_utc8("[03/22 10:00]")
    assert "[2026-03-22 09:30 UTC+8]" == ensure_news_timestamp_line_utc8("[2026-03-22 09:30]")


@pytest.mark.smoke
def test_ensure_news_timestamp_line_utc8_idempotent():
    s = "[03/22 10:00 UTC+8]"
    assert ensure_news_timestamp_line_utc8(s) == s


@pytest.mark.smoke
def test_sanitize_us_treasury_yield_outlier():
    line = "· 美債 10Y：99.9% 參考"
    out = sanitize_us_treasury_yield_tokens_in_line(line)
    assert "99.9%" not in out
    assert "N/A" in out


@pytest.mark.smoke
def test_sanitize_lines_with_us_treasury_keyword_skips_other():
    lines = ["· BTC RSI 70", "· 美債 2Y：99%"]
    out = sanitize_lines_with_us_treasury_keyword(lines)
    assert out[0] == lines[0]
    assert "N/A" in out[1]


@pytest.mark.smoke
def test_news_item_model_injects_utc8():
    n = NewsItem(
        index=1,
        timestamp_line="[03/22 10:00]",
        title="t",
        source_and_nature="Src confirmed",
        summary="s",
        investment_takeaway="BTC 2.1% 日內波動",
        editor_consensus="BTC 觀望",
    )
    assert "UTC+8" in n.timestamp_line


@pytest.mark.smoke
def test_coerce_sections_locks_regime_and_macro():
    crypto = CryptoSection(
        report_title_date="2026-03-29",
        market=MarketRegimeBlock(regime="risk_off"),
        narrative_of_day="測試",
        dashboard=[MetricLine(label="BTC", value="1")],
        news=[
            NewsItem(
                index=1,
                timestamp_line="[03/22 10:00 UTC+8]",
                title="h",
                source_and_nature="s ok",
                summary="sum",
                investment_takeaway="BTC 1%",
                editor_consensus="BTC",
            )
        ],
        pick_reason="r",
        risk_budget_summary="b",
        signal_conflict_summary="多空平衡",
    )
    ai = AISection(
        dashboard=[MetricLine(label="NVDA", value="1")],
        news=[
            NewsItem(
                index=4,
                timestamp_line="[03/22 11:00 UTC+8]",
                title="h",
                source_and_nature="s ok",
                summary="sum",
                investment_takeaway="NVDA 1%",
                editor_consensus="NVDA",
            )
        ],
        pick_reason="r",
        signal_conflict_summary="ok",
        macro_bridge_lines=["· 美債 10Y：50% 測試"],
    )
    c2, a2 = _coerce_sections_for_gate(crypto, ai, agreed_regime="risk_on")
    assert c2.market.regime == "risk_on"
    assert "N/A" in a2.macro_bridge_lines[0]
    assert "risk_on" in (c2.risk_budget_summary or "")


@pytest.mark.smoke
def test_normalize_leading_repeat_pick_same_yesterday_rewrites():
    out = normalize_leading_repeat_pick_phrase("重複選用理由：BTC 敘事延續。", same_as_yesterday=True)
    assert out.startswith("連日維持與昨日相同建議標的")
    assert "BTC 敘事延續" in out
    assert "重複選用理由" not in out


@pytest.mark.smoke
def test_normalize_leading_repeat_pick_equity_label_rewrites():
    out = normalize_leading_repeat_pick_phrase("重複選股理由：NVDA 維持。", same_as_yesterday=True)
    assert out.startswith("連日維持與昨日相同建議標的")
    assert "NVDA 維持" in out


@pytest.mark.smoke
def test_normalize_leading_repeat_pick_not_same_strips_only():
    out = normalize_leading_repeat_pick_phrase("重複選用理由：輪動後新敘事。", same_as_yesterday=False)
    assert out == "輪動後新敘事。"


@pytest.mark.smoke
def test_ensure_crypto_risk_budget_regime_token_prepends_when_chinese_only():
    s = ensure_crypto_risk_budget_regime_token("中性體制下總曝險 40%，謹慎加倉", "neutral")
    assert s.startswith("neutral")
    assert "中性體制" in s
    assert crypto_risk_budget_has_regime_token("neutral", s)


@pytest.mark.smoke
def test_normalize_regime_skips_conditional_line():
    t = "若轉為 risk_off 則減碼；其餘維持 risk_on"
    out = normalize_authoritative_regime_tokens_multiline(t, "neutral")
    assert out == t


@pytest.mark.smoke
def test_normalize_regime_replaces_tokens_on_plain_line():
    out = normalize_authoritative_regime_tokens_multiline("盤面 risk_off 明顯", "risk_on")
    assert "risk_off" not in out.lower()
    assert "risk_on" in out


@pytest.mark.smoke
def test_metric_line_sanitizes_treasury_yield_value():
    row = MetricLine(label="美債 10Y", value="10Y：88.0%")
    assert "N/A" in row.value
    assert "88" not in row.value


@pytest.mark.smoke
def test_executable_trade_leg_default_invalidation_when_star_high():
    leg = ExecutableTradeLeg(
        asset="BTC",
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
        invalidation="",
        position_pct="5%",
        narrative="催化",
        bull_scenario="多頭",
        base_scenario="基礎",
        bear_scenario="空頭",
    )
    assert "支撐" in leg.invalidation or "跌破" in leg.invalidation


@pytest.mark.smoke
def test_low_confidence_disclaimer_when_many_na_in_model():
    def _ni(idx: int) -> NewsItem:
        return NewsItem(
            index=idx,
            timestamp_line="[03/22 10:00 UTC+8]",
            title="h",
            source_and_nature="s",
            summary="s",
            investment_takeaway="BTC 1%",
            editor_consensus="BTC",
        )
    crypto = CryptoSection(
        report_title_date="2026-03-29",
        market=MarketRegimeBlock(regime="risk_on"),
        narrative_of_day="敘事",
        dashboard=[
            MetricLine(label="a", value="N/A"),
            MetricLine(label="b", value="N/A"),
            MetricLine(label="c", value="N/A"),
            MetricLine(label="d", value="N/A"),
        ],
        news=[_ni(1)],
        pick_reason="本日選擇理由測試字串長度需達三十四字以上才通過結構驗證門檻",
        risk_budget_summary="risk_on 模式下總倉位上限百分之十五測試",
        signal_conflict_summary="平衡",
    )
    ai = AISection(
        dashboard=[MetricLine(label="n", value="1")],
        news=[_ni(4)],
        pick_reason="AI 本日選擇理由測試字串長度需達三十八個字元以上結構門檻",
        signal_conflict_summary="ok",
    )
    disc = _low_confidence_disclaimer_plain(crypto, ai)
    assert "低置信度" in disc
    assert "資料缺失原因" in disc


def _trade_rec_with_scores(
    *,
    asset: str,
    category: str,
    regime: str | None,
    direction: str = "LONG",
) -> TradeRecommendation:
    return TradeRecommendation(
        asset=asset,
        direction=direction,
        current_price=100.0,
        entry=99.0,
        target=110.0,
        stop=95.0,
        confidence=3,
        category=category,
        narrative="n",
        trigger="t",
        invalidation="i",
        position_pct=3.0,
        timeframe="3d",
        regime=regime,
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
        bull_scenario="多頭情境一句話測試。",
        base_scenario="基準情境一句話測試。",
        bear_scenario="悲觀情境一句話測試。",
    )


@pytest.mark.smoke
def test_crypto_section_qsrec_auto_coerces_equity_category_to_crypto():
    """CryptoSection.qsrec 中 category=EQUITY 的條目應自動被修正為 CRYPTO（不崩潰）。"""
    def _ni(idx: int) -> NewsItem:
        return NewsItem(
            index=idx,
            timestamp_line="[04/23 09:00 UTC+8]",
            title="h",
            source_and_nature="s confirmed",
            summary="s",
            investment_takeaway="BTC 1%",
            editor_consensus="BTC",
        )

    crypto = CryptoSection(
        report_title_date="2026-04-23",
        market=MarketRegimeBlock(regime="neutral"),
        narrative_of_day="測試主敘事",
        dashboard=[MetricLine(label="BTC", value="93000")],
        news=[_ni(1), _ni(2), _ni(3)],
        pick_reason="本日選擇理由測試字串長度需達三十四字以上才通過結構驗證門檻",
        risk_budget_summary="neutral 模式下總風險預算百分之四十測試敘述",
        signal_conflict_summary="多空平衡",
        qsrec=[
            # 第一筆正確 CRYPTO
            _trade_rec_with_scores(asset="BTC", category="CRYPTO", regime="neutral"),
            # 第二筆錯誤 EQUITY — 應被自動修正
            _trade_rec_with_scores(asset="ETH", category="EQUITY", regime="neutral"),
        ],
    )
    # 兩筆均應被修正為 CRYPTO
    assert crypto.qsrec[0].category == "CRYPTO"
    assert crypto.qsrec[1].category == "CRYPTO", (
        "CryptoSection.qsrec 第 2 筆 category 應自動修正為 CRYPTO"
    )


@pytest.mark.smoke
def test_ai_section_qsrec_auto_coerces_crypto_category_to_equity():
    """AISection.qsrec 中 category=CRYPTO 的條目應自動被修正為 EQUITY（不崩潰）。"""
    def _ni(idx: int) -> NewsItem:
        return NewsItem(
            index=idx,
            timestamp_line="[04/23 10:00 UTC+8]",
            title="h",
            source_and_nature="s confirmed",
            summary="s",
            investment_takeaway="NVDA 2%",
            editor_consensus="NVDA",
        )

    ai = AISection(
        dashboard=[MetricLine(label="NVDA", value="800")],
        news=[_ni(4), _ni(5), _ni(6)],
        pick_reason="AI 本日選擇理由測試字串長度需達三十八個字元以上結構門檻驗證用",
        signal_conflict_summary="多空平衡",
        qsrec=[
            # 正確 EQUITY
            _trade_rec_with_scores(asset="NVDA", category="EQUITY", regime="neutral"),
            # 錯誤 CRYPTO — 應被自動修正為 EQUITY
            _trade_rec_with_scores(asset="MSFT", category="CRYPTO", regime="neutral"),
        ],
    )
    assert ai.qsrec[0].category == "EQUITY"
    assert ai.qsrec[1].category == "EQUITY", (
        "AISection.qsrec 第 2 筆 category 應自動修正為 EQUITY"
    )


@pytest.mark.smoke
def test_assemble_coerces_qsrec_regime_to_market_and_fixes_us_equity_note():
    long_crypto_reason = (
        "本日選擇理由測試字串長度需達三十四字以上才通過結構驗證門檻，"
        "補充敘事以滿足 DailyBriefReport 契約。"
    )
    long_ai_reason = (
        "AI 本日選擇理由測試字串長度需達三十八個字元以上結構門檻驗證用，"
        "補充產業敘事以滿足 DailyBriefReport 契約。"
    )
    crypto = CryptoSection(
        report_title_date="2026-04-08",
        exec_summary=["→ 測試執行摘要要點"],
        market=MarketRegimeBlock(regime="neutral", score_suffix="（-1/6）"),
        narrative_of_day="測試主敘事",
        dashboard=[MetricLine(label="BTC", value="1")],
        news=[
            NewsItem(
                index=1,
                timestamp_line="[04/08 09:00 UTC+8]",
                title="t",
                source_and_nature="s",
                summary="s",
                investment_takeaway="BTC 1%",
                editor_consensus="BTC",
            ),
            NewsItem(
                index=2,
                timestamp_line="[04/08 10:00 UTC+8]",
                title="t2",
                source_and_nature="s",
                summary="s",
                investment_takeaway="費率 0.01%",
                editor_consensus="ETH",
            ),
            NewsItem(
                index=3,
                timestamp_line="[04/08 11:00 UTC+8]",
                title="t3",
                source_and_nature="s",
                summary="s",
                investment_takeaway="OI 1%",
                editor_consensus="SOL",
            ),
        ],
        pick_reason=long_crypto_reason,
        risk_budget_summary="neutral 模式下總風險預算百分之四十測試敘述",
        signal_conflict_summary="空方一句｜多方一句平衡",
        trade_legs=[
            ExecutableTradeLeg(
                asset="BTC",
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
                position_pct="3%",
                narrative="催化",
                bull_scenario="多頭：突破前高",
                base_scenario="基礎：區間震盪",
                bear_scenario="空頭：跌破停損",
            )
        ],
        qsrec=[_trade_rec_with_scores(asset="BTC", category="CRYPTO", regime="risk_off")],
    )
    ai = AISection(
        dashboard=[MetricLine(label="NVDA yfinance", value="100")],
        news=[
            NewsItem(
                index=4,
                timestamp_line="[04/08 12:00 UTC+8]",
                title="a",
                source_and_nature="s",
                summary="s",
                investment_takeaway="GPU 10%",
                editor_consensus="NVDA",
            ),
            NewsItem(
                index=5,
                timestamp_line="[04/08 13:00 UTC+8]",
                title="b",
                source_and_nature="s",
                summary="s",
                investment_takeaway="雲端 5%",
                editor_consensus="MSFT",
            ),
            NewsItem(
                index=6,
                timestamp_line="[04/08 14:00 UTC+8]",
                title="c",
                source_and_nature="s",
                summary="s",
                investment_takeaway="資料中心 3%",
                editor_consensus="AMD",
            ),
        ],
        pick_reason=long_ai_reason,
        signal_conflict_summary="空方一句｜多方一句",
        us_equity_allocation_note="兩檔合計不超過 4%（risk_off）測試",
        trade_legs=[
            ExecutableTradeLeg(
                asset="NVDA",
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
                position_pct="2%",
                narrative="催化",
                bull_scenario="多頭：突破前高",
                base_scenario="基礎：區間震盪",
                bear_scenario="空頭：跌破停損",
            ),
            ExecutableTradeLeg(
                asset="MSFT",
                direction="SHORT",
                current_price="200",
                star_rating=2,
                entry="200",
                target="180 (-10%)",
                stop="210 (+5%)",
                rr="1:2",
                max_drawdown_pct="-5.0%",
                expected_win_rate="50%",
                signal_score="60/100",
                trigger="反彈無力",
                sizing_logic="分批",
                invalidation="突破 210",
                position_pct="2%",
                narrative="對沖",
                bull_scenario="多頭：反轉",
                base_scenario="基礎：橫盤",
                bear_scenario="空頭：續跌",
            ),
        ],
        qsrec=[
            _trade_rec_with_scores(asset="NVDA", category="EQUITY", regime="risk_off"),
            _trade_rec_with_scores(
                asset="MSFT", category="EQUITY", regime="risk_off", direction="SHORT"
            ),
        ],
    )
    report = assemble_daily_brief_report(
        crypto,
        ai,
        previous_recs_html="",
        source_observability_block="",
        report_tier_partial_news=False,
        agreed_regime=None,
    )
    assert report.crypto.qsrec[0].regime == "neutral"
    assert report.ai.qsrec[0].regime == "neutral"
    assert report.ai.qsrec[1].regime == "neutral"
    assert "risk_off" not in (report.ai.us_equity_allocation_note or "").lower()
    assert "對齊主判定：neutral" in (report.ai.us_equity_allocation_note or "")
