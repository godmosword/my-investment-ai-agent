"""Minimal HTTP contract smoke for critical /api routes (queue 9 starter)."""

from __future__ import annotations




def test_health_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("service") == "api"


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


def test_data_health_contract(client, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    r = client.get("/api/data-health")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert isinstance(body["items"], list)
    ids = {item["id"] for item in body["items"]}
    assert {"options", "portfolio", "news", "reports"}.issubset(ids)
    for item in body["items"]:
        assert {"id", "label", "status", "source", "hint", "row_count", "latest_as_of"}.issubset(item)
        assert item["status"] in {"ready", "pending", "empty", "stale", "error"}


def test_data_health_options_probe_reads_all_configured_tables(client, monkeypatch):
    from datetime import datetime, timezone

    from google.cloud import bigquery

    from api_routers import health as health_router

    latest = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    counts = {
        "proj.market_data.options_snapshots": 2,
        "proj.market_data.options_unusual_trades": 3,
        "proj.market_data.options_gex_history": 1,
        "proj.market_data.options_gex_by_strike": 4,
    }
    queried: list[str] = []

    class FakeJob:
        def __init__(self, rows):
            self._rows = rows

        def result(self):
            return self._rows

    class FakeClient:
        def __init__(self, project):
            self.project = project

        def query(self, sql):
            table = sql.split("FROM `", 1)[1].split("`", 1)[0]
            queried.append(table)
            return FakeJob([{"row_count": counts[table], "latest_as_of": latest}])

    monkeypatch.setattr(bigquery, "Client", FakeClient)
    monkeypatch.setattr(health_router, "OPTIONS_SNAPSHOTS_TABLE", "proj.market_data.options_snapshots")
    monkeypatch.setattr(health_router, "OPTIONS_UNUSUAL_TRADES_TABLE", "proj.market_data.options_unusual_trades")
    monkeypatch.setattr(health_router, "OPTIONS_GEX_HISTORY_TABLE", "proj.market_data.options_gex_history")
    monkeypatch.setattr(health_router, "OPTIONS_GEX_BY_STRIKE_TABLE", "proj.market_data.options_gex_by_strike")

    r = client.get("/api/data-health")

    assert r.status_code == 200
    options = next(item for item in r.json()["items"] if item["id"] == "options")
    assert options["status"] == "ready"
    assert options["row_count"] == 10
    assert options["latest_as_of"] == latest
    assert set(queried) == set(counts)


def test_data_health_portfolio_bigquery_probe_reads_table(client, monkeypatch):
    from datetime import datetime, timezone

    from google.cloud import bigquery

    from api_routers import health as health_router

    latest = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    seen_sql: list[str] = []

    class FakeJob:
        def result(self):
            return [{"row_count": 2, "latest_as_of": latest}]

    class FakeClient:
        def __init__(self, project):
            self.project = project

        def query(self, sql):
            seen_sql.append(sql)
            return FakeJob()

    monkeypatch.setattr(bigquery, "Client", FakeClient)
    monkeypatch.setenv("PORTFOLIO_STORE_BACKEND", "bigquery")
    monkeypatch.setenv("PORTFOLIO_HOLDINGS_TABLE", "proj.dataset.portfolio_holdings")
    monkeypatch.setattr(health_router, "OPTIONS_SNAPSHOTS_TABLE", "")
    monkeypatch.setattr(health_router, "OPTIONS_UNUSUAL_TRADES_TABLE", "")
    monkeypatch.setattr(health_router, "OPTIONS_GEX_HISTORY_TABLE", "")
    monkeypatch.setattr(health_router, "OPTIONS_GEX_BY_STRIKE_TABLE", "")

    r = client.get("/api/data-health")

    assert r.status_code == 200
    portfolio = next(item for item in r.json()["items"] if item["id"] == "portfolio")
    assert portfolio["status"] == "ready"
    assert portfolio["row_count"] == 2
    assert portfolio["latest_as_of"] == latest
    assert "COALESCE(updated_at, created_at)" in seen_sql[0]


def test_data_health_empty_backends_return_setup_hints(client, monkeypatch):
    from google.cloud import bigquery

    from api_routers import health as health_router

    class FakeJob:
        def result(self):
            return [{"row_count": 0, "latest_as_of": None}]

    class FakeClient:
        def __init__(self, project):
            self.project = project

        def query(self, sql):
            return FakeJob()

    monkeypatch.setattr(bigquery, "Client", FakeClient)
    monkeypatch.setenv("PORTFOLIO_STORE_BACKEND", "bigquery")
    monkeypatch.setenv("PORTFOLIO_HOLDINGS_TABLE", "proj.dataset.portfolio_holdings")
    monkeypatch.setattr(health_router, "OPTIONS_SNAPSHOTS_TABLE", "proj.dataset.options_snapshots")
    monkeypatch.setattr(health_router, "OPTIONS_UNUSUAL_TRADES_TABLE", "proj.dataset.options_unusual_trades")
    monkeypatch.setattr(health_router, "OPTIONS_GEX_HISTORY_TABLE", "proj.dataset.options_gex_history")
    monkeypatch.setattr(health_router, "OPTIONS_GEX_BY_STRIKE_TABLE", "proj.dataset.options_gex_by_strike")

    r = client.get("/api/data-health")

    assert r.status_code == 200
    items = {item["id"]: item for item in r.json()["items"]}
    assert items["options"]["status"] == "empty"
    assert "options_flow_tick.py" in items["options"]["hint"]
    assert items["portfolio"]["status"] == "empty"
    assert "first portfolio holding" in items["portfolio"]["hint"]
