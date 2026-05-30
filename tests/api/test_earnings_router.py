"""Earnings calendar + filing insight read API (P3)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from api_routers import earnings as earnings_router
from tests.api.helpers import make_api_client


@pytest.fixture()
def client(monkeypatch):
    earnings_router.reset_cache_for_tests()
    return make_api_client(monkeypatch)


def test_upcoming_shape_with_no_results(client, monkeypatch):
    """Default behaviour: yfinance unavailable / empty → empty items + stable envelope."""
    monkeypatch.setattr(earnings_router, "tickers_with_earnings_between", lambda *a, **kw: [])
    r = client.get("/api/earnings/upcoming")
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 14
    assert body["items"] == []
    assert isinstance(body["watchlist_size"], int) and body["watchlist_size"] > 0
    assert "as_of" in body


def test_upcoming_pillar_and_days_until(client, monkeypatch):
    monkeypatch.setattr(earnings_router, "pipeline_anchor_date", lambda: date(2026, 5, 1))
    fake = [
        ("NVDA", date(2026, 5, 5)),
        ("MSFT", date(2026, 5, 7)),
        ("TSM", date(2026, 5, 12)),
        ("XYZNEW", date(2026, 5, 6)),  # unknown -> "other"
    ]
    monkeypatch.setattr(earnings_router, "tickers_with_earnings_between", lambda *a, **kw: fake)
    r = client.get("/api/earnings/upcoming?days=14")
    assert r.status_code == 200
    items = r.json()["items"]
    by_sym = {row["symbol"]: row for row in items}
    assert by_sym["NVDA"]["pillar"] == "ai_silicon"
    assert by_sym["NVDA"]["days_until"] == 4
    assert by_sym["MSFT"]["pillar"] == "cloud_software"
    assert by_sym["TSM"]["pillar"] == "semiconductor"
    assert by_sym["XYZNEW"]["pillar"] == "other"
    assert all(row["status"] == "unknown" for row in items)


def test_upcoming_days_param_clamped(client):
    r = client.get("/api/earnings/upcoming?days=0")
    assert r.status_code == 422
    r = client.get("/api/earnings/upcoming?days=999")
    assert r.status_code == 422


def test_upcoming_watchlist_override(client, monkeypatch):
    captured: dict[str, object] = {}

    def fake(tickers, start, end):
        captured["tickers"] = tickers
        return []

    monkeypatch.setattr(earnings_router, "tickers_with_earnings_between", fake)
    monkeypatch.setenv("EARNINGS_WATCHLIST_OVERRIDE", "NVDA, AMD, FOO")
    r = client.get("/api/earnings/upcoming")
    assert r.status_code == 200
    assert captured["tickers"] == ("NVDA", "AMD", "FOO")
    assert r.json()["watchlist_size"] == 3


def test_upcoming_cache_avoids_repeat_yfinance(client, monkeypatch):
    calls: list[int] = []

    def fake(tickers, start, end):
        calls.append(1)
        return [("NVDA", date(2026, 5, 5))]

    monkeypatch.setattr(earnings_router, "pipeline_anchor_date", lambda: date(2026, 5, 1))
    monkeypatch.setattr(earnings_router, "tickers_with_earnings_between", fake)
    r1 = client.get("/api/earnings/upcoming?days=7")
    r2 = client.get("/api/earnings/upcoming?days=7")
    assert r1.status_code == 200 and r2.status_code == 200
    assert len(calls) == 1  # second hit served from cache


def test_insight_disabled_when_no_scaffold(client, monkeypatch, tmp_path):
    monkeypatch.setenv("DEEP_FILING_ANALYSIS_FILE", str(tmp_path / "missing.jsonl"))
    r = client.get("/api/earnings/NVDA/insight")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["symbol"] == "NVDA"
    assert body["reason"] == "no_filing_scaffold_data"


def test_insight_returns_scaffold_when_present(client, monkeypatch, tmp_path):
    path = tmp_path / "deep.jsonl"
    older = {
        "ticker": "NVDA",
        "filing_type": "10-Q",
        "as_of": "2026-02-01",
        "answers": {"1": "old answer"},
        "citations": {"1": [{"excerpt": "old excerpt"}]},
        "red_flags": [],
    }
    newer = {
        "ticker": "NVDA",
        "filing_type": "10-Q",
        "as_of": "2026-05-01",
        "answers": {"1": "Datacenter revenue grew 80% YoY"},
        "citations": {"1": [{"excerpt": "MD&A — datacenter segment"}]},
        "red_flags": ["Inventory days up 12%"],
    }
    path.write_text(json.dumps(older) + "\n" + json.dumps(newer) + "\n", encoding="utf-8")
    monkeypatch.setenv("DEEP_FILING_ANALYSIS_FILE", str(path))

    r = client.get("/api/earnings/nvda/insight")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["symbol"] == "NVDA"
    assert body["as_of"] == "2026-05-01"
    analysis = body["analysis"]
    assert analysis["ticker"] == "NVDA"
    assert analysis["filing_type"] == "10-Q"
    assert "Datacenter revenue" in analysis["answers"]["1"]
    assert analysis["red_flags"] == ["Inventory days up 12%"]


def test_insight_rejects_invalid_symbol(client):
    r = client.get("/api/earnings/!!!/insight")
    assert r.status_code == 400


def test_insight_invalid_scaffold_returns_enabled_false(client, monkeypatch, tmp_path):
    path = tmp_path / "deep.jsonl"
    # answers without citations violates DeepFilingAnalysis invariant.
    bad = {"ticker": "AMD", "filing_type": "10-Q", "answers": {"1": "x"}, "citations": {}}
    path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    monkeypatch.setenv("DEEP_FILING_ANALYSIS_FILE", str(path))
    r = client.get("/api/earnings/AMD/insight")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["reason"] == "scaffold_invalid"
