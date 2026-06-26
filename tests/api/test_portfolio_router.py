from __future__ import annotations

import pytest




@pytest.fixture()
def client(client_portfolio):
    return client_portfolio

def test_portfolio_crud_round_trip(client):
    create = client.post(
        "/api/portfolio",
        json={
            "symbol": "nvda",
            "shares": 10,
            "cost_basis": 500,
            "opened_at": "2024-01-01",
            "notes": "AI core",
        },
    )
    assert create.status_code == 200
    created = create.json()
    assert created["id"]
    assert created["symbol"] == "NVDA"
    assert created["shares"] == 10

    listed = client.get("/api/portfolio")
    assert listed.status_code == 200
    assert listed.json()["holdings"] == [created]

    patched = client.patch(f"/api/portfolio/{created['id']}", json={"shares": 12})
    assert patched.status_code == 200
    assert patched.json()["shares"] == 12

    deleted = client.delete(f"/api/portfolio/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get("/api/portfolio").json()["holdings"] == []


def test_portfolio_csv_import_round_trip(client):
    csv_text = (
        "symbol,shares,cost_basis,opened_at,notes\n"
        "NVDA,10,500,2024-01-01,core ai\n"
        "SPY,2,450,2024-02-01,index\n"
    )
    imported = client.post(
        "/api/portfolio/import",
        files={"file": ("holdings.csv", csv_text, "text/csv")},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["imported"] == 2

    holdings = client.get("/api/portfolio").json()["holdings"]
    assert {row["symbol"] for row in holdings} == {"NVDA", "SPY"}


def test_portfolio_get_exposes_jsonl_source_metadata(client):
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["source"] == "jsonl"
    assert body["as_of"]
    assert body["holdings"] == []


def test_portfolio_bigquery_mode_without_table_returns_pending(client, monkeypatch):
    monkeypatch.setenv("PORTFOLIO_STORE_BACKEND", "bigquery")
    monkeypatch.delenv("PORTFOLIO_HOLDINGS_TABLE", raising=False)

    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["source"] == "bigquery"
    assert body["reason"] == "portfolio_bigquery_table_missing"
    assert body["holdings"] == []

    create = client.post(
        "/api/portfolio",
        json={"symbol": "NVDA", "shares": 1, "cost_basis": 100, "opened_at": "2024-01-01"},
    )
    assert create.status_code == 503
    assert "PORTFOLIO_HOLDINGS_TABLE" in create.json()["detail"]


def test_portfolio_csv_import_rejects_wrong_columns(client):
    imported = client.post(
        "/api/portfolio/import",
        files={"file": ("bad.csv", "ticker,shares\nNVDA,10\n", "text/csv")},
    )
    assert imported.status_code == 422


def test_portfolio_pnl_math(client, monkeypatch):
    created = client.post(
        "/api/portfolio",
        json={
            "symbol": "NVDA",
            "shares": 10,
            "cost_basis": 500,
            "opened_at": "2024-01-01",
            "notes": "",
        },
    ).json()

    monkeypatch.setattr(
        "api_routers.portfolio.fetch_symbol_quote",
        lambda symbol: {
            "symbol": symbol,
            "last": 800,
            "change_pct_1d": 1.5,
            "error": None,
        },
    )

    response = client.get("/api/portfolio/pnl")
    assert response.status_code == 200
    body = response.json()
    assert body["total_value"] == pytest.approx(8000)
    assert body["total_pnl"] == pytest.approx(3000)
    assert body["total_day_pnl"] == pytest.approx(120)

    row = body["holdings"][0]
    assert row["id"] == created["id"]
    assert row["market_value"] == pytest.approx(8000)
    assert row["pnl"] == pytest.approx(3000)
    assert row["pnl_pct"] == pytest.approx(60)
    assert row["weight"] == pytest.approx(100)


def test_portfolio_pnl_keeps_going_when_quote_unavailable(client, monkeypatch):
    client.post(
        "/api/portfolio",
        json={
            "symbol": "ZZZ",
            "shares": 1,
            "cost_basis": 10,
            "opened_at": "2024-01-01",
        },
    )

    monkeypatch.setattr(
        "api_routers.portfolio.fetch_symbol_quote",
        lambda _symbol: {"last": None, "error": "no_price_data"},
    )

    body = client.get("/api/portfolio/pnl").json()
    assert body["total_value"] == 0
    assert body["holdings"][0]["symbol"] == "ZZZ"
    assert body["holdings"][0]["error"] == "quote_unavailable"
