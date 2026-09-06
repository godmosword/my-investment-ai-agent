"""Contract coverage for the ``/api/reports*`` routes in ``api_routers.reports``.

Moved from ``tests/api/test_api_py_contract.py`` together with the handlers; the
assertions (paths, status codes, payload keys) are unchanged.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from api_routers import reports as reports_router


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
        reports_router,
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
        reports_router,
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
