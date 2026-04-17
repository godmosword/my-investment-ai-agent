"""Phase 5: optional 〔時事多觀點〕 render + Gate (BRIEF_CURRENT_AFFAIRS)."""

from __future__ import annotations

import pytest

from report_html_gates import validate_report
from report_render import render_telegram_daily_brief, telegram_render_context
from schemas import CurrentAffairsRoundtable, RoundtableVoice
from test_telegram_template_modularization import _report_minimal, _render_with_fixture
from test_validate_report import _make_minimal_structured_report_dbr


@pytest.mark.smoke
def test_full_byte_identical_when_brief_current_affairs_off(monkeypatch):
    monkeypatch.delenv("BRIEF_CURRENT_AFFAIRS", raising=False)
    report = _report_minimal()
    mono = _render_with_fixture("telegram_report_phase0_monolithic.j2", report)
    rendered = render_telegram_daily_brief(report, profile="full")
    assert mono == rendered


@pytest.mark.smoke
def test_full_inserts_roundtable_when_flag_and_data(monkeypatch):
    monkeypatch.setenv("BRIEF_CURRENT_AFFAIRS", "1")
    base = _make_minimal_structured_report_dbr()
    rt = CurrentAffairsRoundtable(
        topic="流動性與事件定價",
        voices=[
            RoundtableVoice(
                role="宏觀",
                viewpoint="短端利率與風險資產相關性仍高，敘述須保持審慎。",
                disagreement="與加密端對波動外溢幅度看法不同。",
                evidence_anchor="VIX",
            ),
            RoundtableVoice(
                role="加密",
                viewpoint="衍生品資金費率與現貨基差仍為主要邊際訊號。",
                disagreement="對風險資產同步回撤幅度較樂觀。",
                evidence_anchor="BTC_RSI14_1d",
            ),
        ],
        consensus="維持資料驅動、避免單邊押注。",
        dashboard_anchors=["VIX", "BTC_RSI14_1d"],
    )
    report = base.model_copy(update={"current_affairs_roundtable": rt})
    html = render_telegram_daily_brief(report, profile="full")
    assert "<b>〔時事多觀點〕" in html
    assert html.count("<blockquote>") >= 2
    assert "[QSREC_START]" in html


@pytest.mark.smoke
def test_strict_gate_requires_block_when_env_pair(monkeypatch):
    monkeypatch.setenv("BRIEF_CURRENT_AFFAIRS", "1")
    monkeypatch.setenv("STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE", "1")
    report = _make_minimal_structured_report_dbr()
    html = render_telegram_daily_brief(report, profile="full")
    r = validate_report(html, profile="full")
    assert not r["valid"]
    assert any("〔時事多觀點〕" in i for i in (r.get("issues") or []))


@pytest.mark.smoke
def test_telegram_render_context_includes_empty_block_html_by_default(monkeypatch):
    monkeypatch.delenv("BRIEF_CURRENT_AFFAIRS", raising=False)
    report = _report_minimal()
    ctx = telegram_render_context(report)
    assert ctx.get("current_affairs_block_html") == ""
