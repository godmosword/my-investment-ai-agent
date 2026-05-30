"""Minimal HTTP contract smoke for critical /api routes (queue 9 starter)."""

from __future__ import annotations




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


def test_paper_execution_tick_disabled_by_default(client, monkeypatch):
    """``POST /api/paper/execution-tick`` 404s unless ``PAPER_TICK_HTTP_ENABLED=1`` (M5 slice 1)."""
    monkeypatch.delenv("PAPER_TICK_HTTP_ENABLED", raising=False)
    r = client.post("/api/paper/execution-tick")
    assert r.status_code == 404


def test_price_alerts_check_contract(client, tmp_path, monkeypatch):
    """``POST /api/push/price-alerts/check`` returns digest-shaped envelope (M4 slice 2)."""
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.delenv("PRICE_ALERTS_TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("SSE_PRICE_ALERT_ENABLED", raising=False)
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "pa.jsonl"))
    (tmp_path / "pa.jsonl").write_text("", encoding="utf-8")
    r = client.post("/api/push/price-alerts/check?send_push=false")
    assert r.status_code == 200
    body = r.json()
    assert body.get("checked") == 0
    assert body.get("triggered") == 0
    assert body.get("alerts") == []
    assert body.get("push_results") == []
    assert body.get("telegram_results") == []


def test_war_room_stream_disabled_by_default(client, monkeypatch):
    """``GET /api/stream/war-room`` 404s unless ``TERMINAL_SSE_ENABLED=1`` (M4 slice 3)."""
    monkeypatch.delenv("TERMINAL_SSE_ENABLED", raising=False)
    r = client.get("/api/stream/war-room")
    assert r.status_code == 404


def test_stream_token_disabled_by_default(client, monkeypatch):
    """``POST /api/stream/token`` 404s unless ``API_STREAM_AUTH_KEY`` is set."""
    monkeypatch.delenv("API_STREAM_AUTH_KEY", raising=False)
    r = client.post("/api/stream/token")
    assert r.status_code == 404


def test_earnings_upcoming_shape(client, monkeypatch):
    """``GET /api/earnings/upcoming`` returns a stable envelope even on empty data."""
    from api_routers import earnings as earnings_router

    monkeypatch.setattr(earnings_router, "tickers_with_earnings_between", lambda *a, **kw: [])
    earnings_router.reset_cache_for_tests()
    r = client.get("/api/earnings/upcoming")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("items"), list)
    assert body.get("days") == 14
    assert "as_of" in body


def test_earnings_insight_disabled_by_default(client, monkeypatch, tmp_path):
    """``GET /api/earnings/{symbol}/insight`` returns enabled=false when scaffold missing."""
    monkeypatch.setenv("DEEP_FILING_ANALYSIS_FILE", str(tmp_path / "missing.jsonl"))
    r = client.get("/api/earnings/NVDA/insight")
    assert r.status_code == 200
    assert r.json().get("enabled") is False


def test_compute_memory_envelope_stable(client, monkeypatch, tmp_path):
    """``GET /api/macro/compute-memory`` returns a stable envelope (enabled or disabled)."""
    from api_routers import macro as macro_router

    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(tmp_path / "absent.json"))
    macro_router._compute_memory_reset_cache_for_tests()
    r = client.get("/api/macro/compute-memory")
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert "live" in body


def test_onchain_envelope_stable(client, monkeypatch, tmp_path):
    """``GET /api/macro/onchain`` returns a stable envelope (enabled or disabled)."""
    from api_routers import macro as macro_router

    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(tmp_path / "absent.json"))
    macro_router._onchain_reset_cache_for_tests()
    r = client.get("/api/macro/onchain")
    assert r.status_code == 200
    body = r.json()
    assert "enabled" in body
    assert "live" in body


def test_run_crew_status_contract(client, monkeypatch):
    monkeypatch.delenv("CREW_HTTP_ENABLED", raising=False)
    r = client.get("/api/run-crew/status")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "age_seconds" in body
    assert "is_stale" in body
    assert body.get("stale_after_seconds") == 1800
