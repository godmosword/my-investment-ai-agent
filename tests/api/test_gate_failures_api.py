"""Contract for FE-4 GET /api/gate-failures (queue 49)."""

from __future__ import annotations

import pytest




@pytest.fixture()
def client(client_skip_bq):
    return client_skip_bq

def test_gate_failures_default_shape(client):
    r = client.get("/api/gate-failures")
    assert r.status_code == 200
    body = r.json()
    assert body["days"] == 7
    assert "entries" in body and isinstance(body["entries"], list)
    assert body["source"] in {"bq", "fixture", "empty"}


def test_gate_failures_fixture_fallback(client):
    r = client.get("/api/gate-failures?days=30")
    body = r.json()
    assert body["source"] == "fixture"
    assert body["count"] > 0
    entry = body["entries"][0]
    for key in (
        "timestamp",
        "attempt",
        "blocking_count",
        "warning_count",
        "issue_count",
        "profile",
        "issues_preview",
    ):
        assert key in entry


def test_gate_failures_days_bounds(client):
    assert client.get("/api/gate-failures?days=0").status_code == 422
    assert client.get("/api/gate-failures?days=31").status_code == 422
