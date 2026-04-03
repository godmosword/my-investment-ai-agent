"""Boundary tests for report_render position_pct helpers and tracker regime caps."""

from __future__ import annotations

import pytest

from report_render import (
    _coerce_ai_trade_legs_single_and_combined_cap,
    _parse_position_pct_float,
    _trade_leg_position_pct_needs_fill,
)
from schemas import AISection, ExecutableTradeLeg, MetricLine
from tracker import (
    default_position_pct_for_leg,
    equity_combined_cap_percent,
    regime_single_leg_cap_percent,
)
from validation_rules import normalize_leading_repeat_pick_phrase


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("%", None),
        ("5", 5.0),
        ("5%", 5.0),
        (" 6.25 % ", 6.25),
        ("0.5%", 0.5),
        ("N/A", None),
        ("abc", None),
    ],
)
def test_parse_position_pct_float_boundaries(raw: str | None, expected: float | None) -> None:
    assert _parse_position_pct_float(raw) == expected


@pytest.mark.parametrize(
    ("raw", "needs"),
    [
        (None, True),
        ("", True),
        ("  ", True),
        ("%", True),
        ("5%", False),
        ("5", False),
        ("N/A", True),
        ("x", True),
    ],
)
def test_trade_leg_position_pct_needs_fill_boundaries(raw: str | None, needs: bool) -> None:
    assert _trade_leg_position_pct_needs_fill(raw) is needs


@pytest.mark.parametrize("regime", ["neutral", "NEUTRAL", "risk_on", "Risk On", "risk-off", "bogus"])
@pytest.mark.parametrize("fn", [regime_single_leg_cap_percent, equity_combined_cap_percent])
def test_regime_caps_fallback_for_unknown_spellings(regime: str, fn) -> None:
    v = fn(regime)
    assert v > 0
    if regime == "bogus":
        assert v == fn("neutral")


def test_equity_combined_cap_matches_crew_contract() -> None:
    assert equity_combined_cap_percent("neutral") == 10.0
    assert equity_combined_cap_percent("risk_on") == 15.0
    assert equity_combined_cap_percent("risk_off") == 4.0
    assert regime_single_leg_cap_percent("neutral") == 10.0
    assert regime_single_leg_cap_percent("risk_on") == 15.0
    assert regime_single_leg_cap_percent("risk_off") == 5.0


@pytest.mark.parametrize("stars", [0, 1, 4, 99])
def test_default_position_pct_star_rating_clamped(stars: int) -> None:
    p = default_position_pct_for_leg("neutral", stars)
    assert 0 < p <= 10.0


def _leg(sym: str, pct: str, stars: int = 3) -> ExecutableTradeLeg:
    return ExecutableTradeLeg(
        asset=sym,
        direction="LONG",
        current_price="100",
        star_rating=stars,
        entry="99",
        target="110 (+11%)",
        stop="95 (-4%)",
        rr="1:2.5",
        max_drawdown_pct="-4.0%",
        expected_win_rate="55%",
        signal_score="70/100",
        trigger="t",
        sizing_logic="s",
        invalidation="i",
        position_pct=pct,
        narrative="n",
        bull_scenario="b",
        base_scenario="base",
        bear_scenario="bear",
    )


def _ai(legs: list[ExecutableTradeLeg]) -> AISection:
    return AISection(
        dashboard=[MetricLine(label="L", value="1")],
        pick_reason="足夠長度之本日選擇理由敘述以滿足結構化欄位要求",
        signal_conflict_summary="無",
        trade_legs=legs,
    )


def test_coerce_ai_zero_legs_noop() -> None:
    ai = _ai([])
    assert _coerce_ai_trade_legs_single_and_combined_cap(ai, "neutral") is ai


def test_coerce_ai_two_legs_exactly_at_combined_no_scale() -> None:
    ai = _ai([_leg("NVDA", "5%"), _leg("MSFT", "5%")])
    out = _coerce_ai_trade_legs_single_and_combined_cap(ai, "neutral")
    assert out is ai


def test_coerce_ai_two_legs_risk_off_scales_to_four_pct_total() -> None:
    ai = _ai([_leg("NVDA", "3%"), _leg("MSFT", "3%")])
    out = _coerce_ai_trade_legs_single_and_combined_cap(ai, "risk_off")
    assert out is not ai
    a = _parse_position_pct_float(out.trade_legs[0].position_pct)
    b = _parse_position_pct_float(out.trade_legs[1].position_pct)
    assert a is not None and b is not None
    assert abs(a + b - 4.0) < 0.05
    assert abs(a - b) < 0.01


def test_coerce_ai_two_legs_risk_on_scales_combined_to_fifteen_pct() -> None:
    """Each leg under single-leg cap but sum > combined cap → proportional scale to 15%."""
    ai = _ai([_leg("NVDA", "10%"), _leg("MSFT", "10%")])
    out = _coerce_ai_trade_legs_single_and_combined_cap(ai, "risk_on")
    assert out is not ai
    a = _parse_position_pct_float(out.trade_legs[0].position_pct)
    b = _parse_position_pct_float(out.trade_legs[1].position_pct)
    assert a is not None and b is not None
    assert abs(a + b - 15.0) < 0.06
    assert abs(a - b) < 0.02


def test_coerce_ai_three_legs_proportional_scale_neutral() -> None:
    ai = _ai([_leg("A", "4%"), _leg("B", "4%"), _leg("C", "4%")])
    out = _coerce_ai_trade_legs_single_and_combined_cap(ai, "neutral")
    vals = [_parse_position_pct_float(x.position_pct) for x in out.trade_legs]
    assert all(v is not None for v in vals)
    assert abs(sum(vals) - 10.0) < 0.06
    assert abs(vals[0] - vals[1]) < 0.02 and abs(vals[1] - vals[2]) < 0.02


def test_coerce_ai_single_leg_clamps_to_per_regime_cap() -> None:
    ai = _ai([_leg("NVDA", "20%")])
    out = _coerce_ai_trade_legs_single_and_combined_cap(ai, "neutral")
    assert _parse_position_pct_float(out.trade_legs[0].position_pct) == 10.0


def test_coerce_ai_invalid_pct_uses_default_then_clamps() -> None:
    ai = _ai([_leg("NVDA", "not-a-number")])
    out = _coerce_ai_trade_legs_single_and_combined_cap(ai, "neutral")
    v = _parse_position_pct_float(out.trade_legs[0].position_pct)
    assert v is not None
    assert v <= 10.0
    assert v == default_position_pct_for_leg("neutral", 3)


def test_normalize_repeat_pick_empty_string() -> None:
    assert normalize_leading_repeat_pick_phrase("", same_as_yesterday=True) == ""
    assert normalize_leading_repeat_pick_phrase("   ", same_as_yesterday=False) == "   "


@pytest.mark.smoke
def test_chatter_confirmed_grade_a_not_downgraded_without_unconfirmed_tag() -> None:
    from schemas import ChatterItem

    c = ChatterItem(
        text="官方公告已確認｜來源：SEC｜可信度：A｜主流媒體二次驗證：是"
    )
    assert "可信度：A" in c.text
