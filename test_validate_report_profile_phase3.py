"""Phase 3: validate_report(..., profile=) — full 等價、lite 放寬、機構 Gate 不誤擋。"""

from __future__ import annotations

import pytest

from report_html_gates import validate_report
from report_render import render_telegram_daily_brief
from test_report_render import _minimal_report
from test_telegram_template_modularization import _report_minimal, _render_with_fixture


@pytest.mark.smoke
def test_validate_report_full_profile_matches_default():
    """Default profile is full — same issues/valid as explicit profile='full'."""
    report = _minimal_report()
    html = render_telegram_daily_brief(report, profile="full")
    a = validate_report(html)
    b = validate_report(html, profile="full")
    assert a["valid"] == b["valid"]
    assert a["issues"] == b["issues"]
    assert a.get("profile") == "full"
    assert b.get("profile") == "full"


@pytest.mark.smoke
def test_validate_report_full_byte_pipeline_matches_monolithic_fixture():
    """Regression: full HTML from fixture vs render(full) — validate_report 結果一致。"""
    report = _minimal_report()
    mono = _render_with_fixture("telegram_report_phase0_monolithic.j2", report)
    rendered = render_telegram_daily_brief(report, profile="full")
    assert mono == rendered
    vm = validate_report(mono, profile="full")
    vr = validate_report(rendered, profile="full")
    assert vm["valid"] == vr["valid"]
    assert vm["issues"] == vr["issues"]


@pytest.mark.smoke
def test_lite_validate_passes_with_strict_institutional_phase_a(monkeypatch):
    """STRICT_INSTITUTIONAL_PHASE_A_GATE=1 must not block lite (no 機構速讀 HTML)."""
    report = _report_minimal()
    monkeypatch.setenv("STRICT_INSTITUTIONAL_PHASE_A_GATE", "1")
    monkeypatch.setenv("STRICT_INSTITUTIONAL_PHASE_B_GATE", "1")
    monkeypatch.setenv("STRICT_INSTITUTIONAL_PHASE_C_GATE", "1")
    html = render_telegram_daily_brief(report, profile="lite")
    r = validate_report(html, profile="lite")
    assert r.get("profile") == "lite"
    assert "【投資命題】" not in html
    blocking = r.get("blocking_issues") or []
    assert not any("【投資命題】" in i or "Phase A" in i for i in blocking), blocking
    assert not any("缺少數據儀表板" in i for i in r.get("issues", [])), r.get("issues")
    assert not any("缺少 AI 市場段落" in i for i in r.get("issues", [])), r.get("issues")
    assert not any("缺少呢喃" in i for i in r.get("issues", [])), r.get("issues")


@pytest.mark.smoke
def test_lite_profile_consistency_rejects_full_html():
    """Passing profile=lite with full-template HTML must fail profile consistency."""
    report = _minimal_report()
    full_html = render_telegram_daily_brief(report, profile="full")
    r = validate_report(full_html, profile="lite")
    assert not r["valid"]
    issues = " ".join(r.get("issues") or [])
    assert "lite 版型" in issues or "加密市場" in issues


@pytest.mark.smoke
def test_crypto_only_renders_omits_ai_and_validate_passes_smoke(monkeypatch):
    """Phase 4a: crypto-only profile template + validate_report(profile=) smoke."""
    report = _minimal_report()
    html = render_telegram_daily_brief(report, profile="crypto-only")
    assert "🤖 AI 市場" not in html
    assert "══════" in html and "📊 加密市場" in html
    assert "[QSREC_START]" in html
    r = validate_report(html, profile="crypto-only")
    assert r.get("profile") == "crypto-only"
    blocking = r.get("blocking_issues") or []
    assert not any("缺少 AI 市場段落" in i for i in r.get("issues", [])), r.get("issues")
    assert not any("缺少 AI 美股操作" in i for i in r.get("issues", [])), r.get("issues")
    assert not any("Phase A" in i or "【投資命題】" in i for i in blocking), blocking


@pytest.mark.smoke
def test_crypto_only_profile_consistency_rejects_full_html():
    """Passing profile=crypto-only with full-template HTML must fail profile consistency."""
    report = _minimal_report()
    full_html = render_telegram_daily_brief(report, profile="full")
    r = validate_report(full_html, profile="crypto-only")
    assert not r["valid"]
    issues = " ".join(r.get("issues") or [])
    assert "crypto-only 版型" in issues
