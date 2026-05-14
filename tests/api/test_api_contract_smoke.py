"""Minimal HTTP contract smoke for critical /api routes (queue 9 starter)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    return TestClient(app)


def test_health_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body


def test_metrics_latest_shape(client, monkeypatch):
    monkeypatch.setenv("SKIP_BIGQUERY", "1")
    r = client.get("/api/metrics/latest")
    assert r.status_code in (200, 404, 503)


def test_scenario_suggestions_contract_when_enabled(client, tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(tmp_path / "ei.jsonl"))
    monkeypatch.setenv("PORTFOLIO_HOLDINGS_FILE", str(tmp_path / "ph.jsonl"))
    monkeypatch.setenv("SCENARIO_OPTIMIZER_ENABLED", "1")
    (tmp_path / "ei.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "ph.jsonl").write_text("", encoding="utf-8")
    r = client.get("/api/scenario/suggestions")
    assert r.status_code == 200
    body = r.json()
    assert body.get("enabled") is True
    assert "scenarios" in body and isinstance(body["scenarios"], list)
    assert "portfolio" in body and isinstance(body["portfolio"], dict)
