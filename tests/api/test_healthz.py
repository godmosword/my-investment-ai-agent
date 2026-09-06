"""Cheap API liveness: GET /healthz (ITER-GO-LIVE-001)."""

from __future__ import annotations

import inspect

import pytest

from api_routers.health import healthz
from tests.api.helpers import make_api_client


@pytest.mark.smoke
def test_healthz_ok_without_credentials(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "service": "api"}


@pytest.mark.smoke
def test_healthz_ok_when_master_key_set_without_header(monkeypatch):
    client = make_api_client(monkeypatch, QSILICON_MASTER_KEY="only-for-api")
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "service": "api"}


@pytest.mark.smoke
def test_healthz_handler_source_avoids_backends():
    src = inspect.getsource(healthz).lower()
    for token in (
        "bigquery",
        "crew",
        "llm",
        "redis",
        "telegram",
        "paper",
        "google.cloud",
    ):
        assert token not in src


@pytest.mark.smoke
def test_healthz_does_not_call_optional_backends(client, monkeypatch):
    from api_routers import health as health_router

    def boom(*_args, **_kwargs):
        raise AssertionError("healthz must not probe optional backends")

    monkeypatch.setattr(health_router, "latest_execution_intents", boom)
    monkeypatch.setattr(health_router, "load_holdings", boom)
    monkeypatch.setattr(health_router, "load_track_record_records", boom)
    monkeypatch.setattr(health_router, "_safe_bq_table_stats", boom)

    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "service": "api"}
