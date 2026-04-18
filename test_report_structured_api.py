"""Smoke tests for GET /api/reports/{date}/structured (V2 visualization envelope)."""

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.smoke
def test_report_structured_shape(monkeypatch, client):
    sample_legacy = {
        "report_date": "2026-04-01",
        "dxy": 104.2,
        "grok_summary": "x",
        "gpt_summary": "y",
        "recommendations": [],
    }

    monkeypatch.setattr("api._load_report_legacy", lambda _d: sample_legacy)

    r = client.get("/api/reports/2026-04-01/structured?profile=full")
    assert r.status_code == 200
    body = r.json()
    assert body["report_date"] == "2026-04-01"
    assert body["profile"] == "full"
    assert isinstance(body["block_ids"], list)
    assert len(body["block_ids"]) >= 1
    assert "header" in body["block_ids"]
    assert body["structured_body_available"] is False
    assert body["daily_brief_report"] is None
    assert body["legacy"]["grok_summary"] == "x"
    assert "exec_summary" in body["block_registry"]


@pytest.mark.smoke
def test_report_structured_invalid_profile(client):
    r = client.get("/api/reports/2026-04-01/structured?profile=not-a-profile")
    assert r.status_code == 400


@pytest.mark.smoke
def test_report_structured_bad_date(client):
    r = client.get("/api/reports/not-a-date/structured")
    assert r.status_code == 400
