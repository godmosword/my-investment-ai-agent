"""Offline smoke test for the daily options pipeline (MOCK_APIS, no network/BQ)."""

from __future__ import annotations

import pytest


@pytest.fixture()
def _offline(monkeypatch):
    monkeypatch.setenv("MOCK_APIS", "1")
    monkeypatch.setenv("SKIP_BIGQUERY", "1")


@pytest.mark.smoke
def test_pipeline_runs_offline_and_computes_gex(_offline):
    from tools.options.pipeline import run_daily_options_pipeline

    summary = run_daily_options_pipeline(["MU"])
    assert len(summary.results) == 1
    mu = summary.results[0]
    assert mu.underlying == "MU"
    # Golden GEX from fixture: +500,000 (call) - 200,000 (put) = +300,000
    assert mu.gex is not None
    assert mu.gex.total_gex == 300_000.0
    # Snapshot-level unusual flow: the call has 5x volume/OI.
    assert any(s.signal_type.value == "volume_oi" for s in mu.unusual)


@pytest.mark.smoke
def test_pipeline_text_summary_is_plain_text(_offline):
    """Telegram safety: summary carries no HTML tags (whitelist-safe by construction)."""
    from tools.options.pipeline import run_daily_options_pipeline

    summary = run_daily_options_pipeline(["MU"])
    assert "<" not in summary.text_summary and ">" not in summary.text_summary


@pytest.mark.smoke
def test_pipeline_missing_symbol_degrades_without_crash(_offline):
    from tools.options.pipeline import run_daily_options_pipeline

    summary = run_daily_options_pipeline(["ZZZZ"])  # no fixture data
    zz = summary.results[0]
    assert zz.gex is None
    assert any("DATA_MISSING" in m for m in zz.missing)
