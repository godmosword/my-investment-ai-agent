"""Smoke tests for P1 gate coercions (validation_rules + report_render + schemas)."""

import pytest

from report_render import _coerce_sections_for_gate, _low_confidence_disclaimer_plain
from schemas import AISection, CryptoSection, ExecutableTradeLeg, MarketRegimeBlock, MetricLine, NewsItem
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
    assert out.startswith("連日維持（同昨日 BQ QSREC）")
    assert "BTC 敘事延續" in out
    assert "重複選用理由" not in out


@pytest.mark.smoke
def test_normalize_leading_repeat_pick_equity_label_rewrites():
    out = normalize_leading_repeat_pick_phrase("重複選股理由：NVDA 維持。", same_as_yesterday=True)
    assert out.startswith("連日維持（同昨日 BQ QSREC）")
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
