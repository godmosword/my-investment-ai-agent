"""Smoke tests for /api/reports profile integration and /api/reports/profile-stats."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client():
    return TestClient(app)


def _fake_bq_client(rows: list[dict[str, Any]]) -> MagicMock:
    """Return a mock bigquery.Client whose .query(...).result() yields ``rows``."""
    mock_client = MagicMock()
    # rows behave like dict-subscriptable objects (matches _rows_to_dicts usage)
    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(rows)
    mock_query = MagicMock()
    mock_query.result.return_value = mock_result
    mock_client.query.return_value = mock_query
    return mock_client


# ── /api/reports/profile-stats ────────────────────────────────────────────────


@pytest.mark.smoke
def test_profile_stats_shape_with_full_data(monkeypatch, client):
    """All known profiles appear in breakdown, and unknowns are appended."""
    rows = [
        {"profile": "full", "report_count": 10, "latest_date": "2026-04-17"},
        {"profile": "lite", "report_count": 3, "latest_date": "2026-04-15"},
    ]
    monkeypatch.setattr("api._get_bq_client", lambda: _fake_bq_client(rows))

    r = client.get("/api/reports/profile-stats?days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["window_days"] == 30
    assert body["total_reports"] == 13

    profiles = {b["profile"]: b for b in body["breakdown"]}
    # Known profiles are always present, even when absent from the log
    assert {"full", "lite", "crypto-only"}.issubset(profiles.keys())
    assert profiles["full"]["report_count"] == 10
    assert profiles["full"]["latest_date"] == "2026-04-17"
    assert profiles["lite"]["report_count"] == 3
    assert profiles["crypto-only"]["report_count"] == 0
    assert profiles["crypto-only"]["latest_date"] is None


@pytest.mark.smoke
def test_profile_stats_includes_unknown_profile(monkeypatch, client):
    rows = [
        {"profile": "full", "report_count": 1, "latest_date": "2026-04-17"},
        {"profile": "experimental", "report_count": 2, "latest_date": "2026-04-16"},
    ]
    monkeypatch.setattr("api._get_bq_client", lambda: _fake_bq_client(rows))

    r = client.get("/api/reports/profile-stats")
    assert r.status_code == 200
    body = r.json()
    profiles = {b["profile"]: b for b in body["breakdown"]}
    assert "experimental" in profiles
    assert profiles["experimental"]["report_count"] == 2
    assert body["total_reports"] == 3


@pytest.mark.smoke
def test_profile_stats_empty(monkeypatch, client):
    monkeypatch.setattr("api._get_bq_client", lambda: _fake_bq_client([]))

    r = client.get("/api/reports/profile-stats?days=7")
    assert r.status_code == 200
    body = r.json()
    assert body["window_days"] == 7
    assert body["total_reports"] == 0
    # All known profiles still present with count=0
    for entry in body["breakdown"]:
        assert entry["report_count"] == 0
        assert entry["latest_date"] is None


@pytest.mark.smoke
def test_profile_stats_bigquery_failure(monkeypatch, client):
    mock_client = MagicMock()
    mock_client.query.side_effect = RuntimeError("BQ down")
    monkeypatch.setattr("api._get_bq_client", lambda: mock_client)

    r = client.get("/api/reports/profile-stats")
    assert r.status_code == 503


@pytest.mark.smoke
def test_profile_stats_days_bounds(client):
    assert client.get("/api/reports/profile-stats?days=0").status_code == 422
    assert client.get("/api/reports/profile-stats?days=400").status_code == 422


# ── /api/reports?profile=... ─────────────────────────────────────────────────


@pytest.mark.smoke
def test_list_reports_without_profile(monkeypatch, client):
    """Without ?profile, endpoint queries metrics table directly (single query)."""
    sample_rows = [
        {
            "report_date": "2026-04-17",
            "timestamp": "2026-04-17T08:00:00",
            "dxy": 104.1,
            "etf_flow_millions": 120.5,
            "avg_risk_score": 0.3,
            "mvrv_z_score": 1.2,
            "regime_score": 0.8,
            "sentiment_score": 0.5,
            "grok_summary": "g",
            "gpt_summary": "p",
            "news_titles": [],
        }
    ]
    mock_client = _fake_bq_client(sample_rows)
    monkeypatch.setattr("api._get_bq_client", lambda: mock_client)

    r = client.get("/api/reports?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert body[0]["report_date"] == "2026-04-17"
    # Single query call, no profile join
    assert mock_client.query.call_count == 1
    sent_sql = mock_client.query.call_args[0][0]
    assert "llm_run_log" not in sent_sql.lower()


@pytest.mark.smoke
def test_list_reports_with_profile_joins_llm_run_log(monkeypatch, client):
    sample_rows = [
        {
            "report_date": "2026-04-17",
            "timestamp": "2026-04-17T08:00:00",
            "dxy": 104.1,
            "etf_flow_millions": None,
            "avg_risk_score": None,
            "mvrv_z_score": None,
            "regime_score": None,
            "sentiment_score": None,
            "grok_summary": None,
            "gpt_summary": None,
            "news_titles": None,
        }
    ]
    mock_client = _fake_bq_client(sample_rows)
    monkeypatch.setattr("api._get_bq_client", lambda: mock_client)

    r = client.get("/api/reports?limit=10&profile=lite")
    assert r.status_code == 200
    # SQL includes JOIN on llm_run_log with @profile parameter
    sent_sql = mock_client.query.call_args[0][0]
    assert "llm_run_log" in sent_sql.lower()
    assert "@profile" in sent_sql
    # job_config is attached (ScalarQueryParameter is stubbed by conftest,
    # so we can't introspect .name/.value; SQL shape check is sufficient)
    assert mock_client.query.call_args.kwargs.get("job_config") is not None


@pytest.mark.smoke
def test_list_reports_invalid_profile(client):
    r = client.get("/api/reports?profile=not-a-profile")
    assert r.status_code == 400


@pytest.mark.smoke
def test_list_reports_empty_profile_treated_as_absent(monkeypatch, client):
    """profile='' should behave as if no profile filter was supplied."""
    mock_client = _fake_bq_client([])
    monkeypatch.setattr("api._get_bq_client", lambda: mock_client)

    r = client.get("/api/reports?profile=")
    assert r.status_code == 200
    sent_sql = mock_client.query.call_args[0][0]
    assert "llm_run_log" not in sent_sql.lower()
