"""Contract coverage for inline routes that still live in ``api.py``."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

import api


def _query_result(rows: list[dict[str, Any]]) -> MagicMock:
    result = MagicMock()
    result.__iter__ = lambda self: iter(rows)
    query = MagicMock()
    query.result.return_value = result
    return query


def _bq_client(*row_sets: list[dict[str, Any]]) -> MagicMock:
    bq = MagicMock()
    bq.query.side_effect = [_query_result(rows) for rows in row_sets]
    return bq


@pytest.fixture()
def client(client_skip_bq):
    return client_skip_bq


def test_reports_list_contract_keys(client, monkeypatch):
    monkeypatch.setattr(
        api,
        "_get_bq_client",
        lambda: _bq_client(
            [
                {
                    "report_date": "2026-05-09",
                    "timestamp": "2026-05-09T02:31:00+00:00",
                    "dxy": 104.1,
                    "etf_flow_millions": 120.5,
                    "avg_risk_score": 0.3,
                    "mvrv_z_score": 1.2,
                    "regime_score": 0.8,
                    "sentiment_score": 0.5,
                    "grok_summary": "risk-on",
                    "gpt_summary": "balanced",
                    "news_titles": ["A", "B"],
                }
            ]
        ),
    )

    response = client.get("/api/reports?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert set(body[0]).issuperset({"report_date", "timestamp", "grok_summary", "gpt_summary"})


def test_reports_list_limit_bounds(client):
    assert client.get("/api/reports?limit=0").status_code == 422
    assert client.get("/api/reports?limit=91").status_code == 422


def test_report_legacy_contract_attaches_recommendations(client, monkeypatch):
    monkeypatch.setattr(
        api,
        "_get_bq_client",
        lambda: _bq_client(
            [
                {
                    "report_date": "2026-05-09",
                    "timestamp": "2026-05-09T02:31:00+00:00",
                    "dxy": 104.1,
                    "etf_flow_millions": 120.5,
                    "avg_risk_score": 0.3,
                    "mvrv_z_score": 1.2,
                    "regime_score": 0.8,
                    "sentiment_score": 0.5,
                    "sopr": None,
                    "exchange_netflow": None,
                    "grok_summary": "risk-on",
                    "gpt_summary": "balanced",
                    "news_titles": [],
                }
            ],
            [
                {
                    "asset": "NVDA",
                    "direction": "LONG",
                    "entry_price": 900,
                    "target_price": 960,
                    "stop_price": 870,
                    "confidence": 0.73,
                    "narrative": "sample",
                    "trigger": "breakout",
                    "invalidation": "below support",
                    "position_pct": 2,
                    "timeframe": "swing",
                    "category": "AI",
                    "status": "OPEN",
                    "exit_price": None,
                    "exit_date": None,
                    "pnl_pct": None,
                    "rr_ratio": 2.0,
                }
            ],
        ),
    )

    response = client.get("/api/reports/2026-05-09")

    assert response.status_code == 200
    body = response.json()
    assert body["report_date"] == "2026-05-09"
    assert isinstance(body["recommendations"], list)
    assert body["recommendations"][0]["asset"] == "NVDA"


def test_report_legacy_date_validation(client):
    response = client.get("/api/reports/not-a-date")

    assert response.status_code == 400


def test_report_gate_status_fixture_contract(client):
    response = client.get("/api/reports/2026-05-09/gate-status")

    assert response.status_code == 200
    body = response.json()
    assert body["gate_status"] in {"pass", "fail", "degraded", "未審"}
    assert set(body).issuperset({"gate_status", "run_id", "revision_count", "final_trade_count"})


def test_report_html_missing_file_contract(client):
    response = client.get("/api/reports/2099-01-01/html")

    assert response.status_code == 404


def test_qsrec_stats_contract_and_bounds(client):
    response = client.get("/api/reports/qsrec-stats?days=30")

    assert response.status_code == 200
    body = response.json()
    assert body["days"] == 30
    assert set(body).issuperset(
        {
            "total_days",
            "pass_count",
            "degraded_count",
            "fail_count",
            "pass_rate_pct",
            "avg_trade_count",
        }
    )
    assert client.get("/api/reports/qsrec-stats?days=0").status_code == 422
    assert client.get("/api/reports/qsrec-stats?days=91").status_code == 422


def test_trades_list_contract_keys(client, monkeypatch):
    monkeypatch.setattr(
        api,
        "_get_bq_client",
        lambda: _bq_client(
            [
                {
                    "report_date": "2026-05-09",
                    "asset": "BTC",
                    "direction": "LONG",
                    "category": "CRYPTO",
                    "entry_price": 65000,
                    "target_price": 70000,
                    "stop_price": 62000,
                    "confidence": 0.68,
                    "narrative": "sample",
                    "trigger": "momentum",
                    "invalidation": "breakdown",
                    "position_pct": 1.5,
                    "timeframe": "swing",
                    "rr_ratio": 1.7,
                    "status": "OPEN",
                    "exit_price": None,
                    "exit_date": None,
                    "pnl_pct": None,
                    "days_held": None,
                    "regime_at_signal": "risk_on",
                    "created_at": "2026-05-09T02:31:00+00:00",
                }
            ]
        ),
    )

    response = client.get("/api/trades?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert set(body[0]).issuperset({"asset", "direction", "status", "entry_price"})


def test_trades_reject_invalid_status(client):
    response = client.get("/api/trades?status=UNKNOWN")

    assert response.status_code == 400


def test_open_positions_contract_uses_open_status(client, monkeypatch):
    seen_sql: list[str] = []

    def fake_client() -> MagicMock:
        bq = MagicMock()
        query = _query_result([])

        def capture(sql: str, *args: Any, **kwargs: Any) -> Any:
            seen_sql.append(sql)
            return query

        bq.query.side_effect = capture
        return bq

    monkeypatch.setattr(api, "_get_bq_client", fake_client)

    response = client.get("/api/positions/open?limit=5")

    assert response.status_code == 200
    assert response.json() == []
    assert "status = 'OPEN'" in seen_sql[0]


def test_trades_performance_contract_keys(client, monkeypatch):
    monkeypatch.setattr(
        api,
        "_get_bq_client",
        lambda: _bq_client(
            [
                {
                    "total": 3,
                    "wins": 1,
                    "losses": 1,
                    "expired": 0,
                    "open_count": 1,
                    "avg_pnl_pct": 2.5,
                    "avg_rr": 1.8,
                    "max_loss_pct": -1.2,
                    "max_gain_pct": 6.4,
                    "win_rate_pct": 50.0,
                }
            ],
            [{"category": "AI", "total": 1, "wins": 1, "win_rate_pct": 100.0, "avg_pnl_pct": 6.4}],
            [{"date": "2026-05-09", "cumulative_pnl": 6.4}],
        ),
    )

    response = client.get("/api/trades/performance?days=30")

    assert response.status_code == 200
    body = response.json()
    assert set(body).issuperset({"total", "wins", "losses", "by_category", "equity_curve"})
    assert isinstance(body["by_category"], list)
    assert isinstance(body["equity_curve"], list)


def test_push_subscribe_invalid_body_contract(client, monkeypatch):
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    response = client.post("/api/push/subscribe", json={})

    assert response.status_code == 422
