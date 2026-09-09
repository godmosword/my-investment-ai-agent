"""Contract coverage for trades/positions routes (now in ``api_routers.trades``) and remaining ``api.py`` inline routes."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from api_routers import trades
from tests.api.helpers import make_api_client


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
def client_bq(monkeypatch, tmp_path):
    """Unskipped client so trades/positions still exercise the BQ mock path."""
    state = tmp_path / "state"
    briefs = tmp_path / "briefs"
    state.mkdir()
    briefs.mkdir()
    return make_api_client(
        monkeypatch,
        SKIP_BIGQUERY=None,
        QSILICON_STATE_DIR=str(state),
        DAILY_BRIEF_JSON_DIR=str(briefs),
    )


def test_trades_list_contract_keys(client_bq, monkeypatch):
    monkeypatch.setattr(
        trades,
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

    response = client_bq.get("/api/trades?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert set(body[0]).issuperset({"asset", "direction", "status", "entry_price"})


def test_trades_reject_invalid_status(client_bq):
    response = client_bq.get("/api/trades?status=UNKNOWN")

    assert response.status_code == 400


def test_open_positions_contract_uses_open_status(client_bq, monkeypatch):
    seen_sql: list[str] = []

    def fake_client() -> MagicMock:
        bq = MagicMock()
        query = _query_result([])

        def capture(sql: str, *args: Any, **kwargs: Any) -> Any:
            seen_sql.append(sql)
            return query

        bq.query.side_effect = capture
        return bq

    monkeypatch.setattr(trades, "_get_bq_client", fake_client)

    response = client_bq.get("/api/positions/open?limit=5")

    assert response.status_code == 200
    assert response.json() == []
    assert "status = 'OPEN'" in seen_sql[0]


def test_trades_performance_contract_keys(client_bq, monkeypatch):
    monkeypatch.setattr(
        trades,
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

    response = client_bq.get("/api/trades/performance?days=30")

    assert response.status_code == 200
    body = response.json()
    assert set(body).issuperset({"total", "wins", "losses", "by_category", "equity_curve"})
    assert isinstance(body["by_category"], list)
    assert isinstance(body["equity_curve"], list)


def test_push_subscribe_invalid_body_contract(client_bq, monkeypatch):
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    response = client_bq.post("/api/push/subscribe", json={})

    assert response.status_code == 422
