"""Phase 2: brief_profiles / REPORT_PROFILE / lite vs full (full stays byte-identical)."""

from __future__ import annotations

from pathlib import Path

import pytest

from brief_profiles import (
    BLOCK_IDS,
    BLOCK_REGISTRY,
    PROFILES,
    assert_registry_covers_block_ids,
    get_active_profile,
    profile_block_ids,
    telegram_profile_template_relpath,
)
from report_render import (
    build_telegram_jinja_env,
    render_telegram_daily_brief,
    telegram_render_context,
)
from test_telegram_template_modularization import (
    _render_with_fixture,
    _report_minimal,
)


_ROOT = Path(__file__).resolve().parent


def test_block_ids_match_registry_keys():
    assert_registry_covers_block_ids()
    assert set(BLOCK_IDS) == set(BLOCK_REGISTRY.keys())


def test_profiles_stable_keys():
    assert tuple(PROFILES["full"]) == BLOCK_IDS
    assert PROFILES["lite"] == (
        "header",
        "exec_summary",
        "market_mode",
        "crypto_trades",
        "ai_trades",
        "qsrec",
    )


def test_get_active_profile_env(monkeypatch):
    monkeypatch.delenv("REPORT_PROFILE", raising=False)
    assert get_active_profile() == "full"
    monkeypatch.setenv("REPORT_PROFILE", "lite")
    assert get_active_profile() == "lite"
    assert get_active_profile("full") == "full"


def test_get_active_profile_invalid():
    with pytest.raises(ValueError, match="REPORT_PROFILE"):
        get_active_profile("not-a-profile")


def test_telegram_profile_template_paths():
    assert telegram_profile_template_relpath("full") == "profiles/telegram_full.j2"
    assert telegram_profile_template_relpath("lite") == "profiles/telegram_lite.j2"


@pytest.mark.smoke
def test_full_profile_byte_identical_to_phase0_fixture():
    report = _report_minimal()
    modular = build_telegram_jinja_env(_ROOT / "templates").get_template(
        "profiles/telegram_full.j2"
    ).render(**telegram_render_context(report))
    mono = _render_with_fixture("telegram_report_phase0_monolithic.j2", report)
    assert modular == mono


@pytest.mark.smoke
def test_render_telegram_daily_brief_full_default_matches_fixture(monkeypatch):
    monkeypatch.delenv("REPORT_PROFILE", raising=False)
    report = _report_minimal()
    out = render_telegram_daily_brief(report)
    mono = _render_with_fixture("telegram_report_phase0_monolithic.j2", report)
    assert out == mono


@pytest.mark.smoke
def test_lite_profile_shorter_and_omits_full_only_sections(monkeypatch):
    monkeypatch.delenv("REPORT_PROFILE", raising=False)
    report = _report_minimal()
    full_html = render_telegram_daily_brief(report, profile="full")
    lite_html = render_telegram_daily_brief(report, profile="lite")
    assert len(lite_html) < len(full_html)
    assert "══════" not in lite_html  # no crypto section banner
    assert "🤖 AI 市場" not in lite_html
    assert "<b>上期</b>" not in lite_html
    assert "【機構速讀｜命題與情境】" not in lite_html
    assert "[QSREC_START]" in lite_html
    assert "【今日市場模式】" in lite_html
    assert "<b>區塊④</b>【資金流向與精準操作 (Crypto)】" in lite_html


def test_profile_block_ids_helper():
    assert profile_block_ids("lite") == PROFILES["lite"]
