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


def test_macro_snapshot_contract(client, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    r = client.get("/api/macro/snapshot")
    assert r.status_code in (200, 503)
    if r.status_code != 200:
        return
    body = r.json()
    assert "indicators" in body and isinstance(body["indicators"], dict)
    assert "indicator_order" in body and isinstance(body["indicator_order"], list)


def test_paper_lifecycle_contract(client, tmp_path, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(tmp_path / "ei.jsonl"))
    (tmp_path / "ei.jsonl").write_text("", encoding="utf-8")
    r = client.get("/api/paper/lifecycle")
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body and isinstance(body["summary"], dict)


def test_track_record_summary_contract(client, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    r = client.get("/api/track-record/summary")
    assert r.status_code == 200
    body = r.json()
    assert "source" in body
    assert "source_row_count" in body


def test_execution_intents_list_contract(client, tmp_path, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(tmp_path / "ei.jsonl"))
    (tmp_path / "ei.jsonl").write_text("", encoding="utf-8")
    r = client.get("/api/execution-intents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_execution_intents_gate_index_contract(client, tmp_path, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(tmp_path / "ei.jsonl"))
    (tmp_path / "ei.jsonl").write_text("", encoding="utf-8")
    r = client.get("/api/execution-intents/gate-index")
    assert r.status_code == 200
    body = r.json()
    assert body.get("schema_version") == "qsi_gate_intent_index_v1"
    assert "matches" in body and isinstance(body["matches"], list)


def test_price_alerts_digest_contract(client, tmp_path, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "pa.jsonl"))
    (tmp_path / "pa.jsonl").write_text("", encoding="utf-8")
    r = client.get("/api/push/price-alerts/digest")
    assert r.status_code == 200
    body = r.json()
    assert body.get("schema_version") == "qsi_price_alert_digest_v1"
    assert body.get("total") == 0
    assert body.get("pending") == 0
    assert body.get("triggered") == 0
    assert body.get("symbols") == []


def test_run_crew_status_contract(client, monkeypatch):
    monkeypatch.delenv("CREW_HTTP_ENABLED", raising=False)
    r = client.get("/api/run-crew/status")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "age_seconds" in body
    assert "is_stale" in body
    assert body.get("stale_after_seconds") == 1800
