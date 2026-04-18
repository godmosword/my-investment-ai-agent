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
    monkeypatch.setattr("api._latest_gate_failure_summary", lambda: None)
    monkeypatch.setattr("api._try_load_daily_brief_raw_dict", lambda _d: (None, None))

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
    assert body["gate_summary"]["available"] is False


@pytest.mark.smoke
def test_report_structured_with_daily_brief_json(tmp_path, monkeypatch, client):
    from test_validate_report import _make_minimal_structured_report_dbr

    sample_legacy = {
        "report_date": "2026-04-01",
        "timestamp": "2026-04-01T08:00:00",
        "dxy": 104.2,
        "grok_summary": "x",
        "gpt_summary": "y",
        "recommendations": [],
    }
    model = _make_minimal_structured_report_dbr()
    json_path = tmp_path / "2026-04-01.json"
    json_path.write_text(model.model_dump_json(), encoding="utf-8")

    monkeypatch.setenv("DAILY_BRIEF_JSON_DIR", str(tmp_path))
    monkeypatch.setattr("api._load_report_legacy", lambda _d: sample_legacy)
    monkeypatch.setattr("api._latest_gate_failure_summary", lambda: None)

    r = client.get("/api/reports/2026-04-01/structured?profile=full")
    assert r.status_code == 200
    body = r.json()
    assert body["structured_body_available"] is True
    assert str(body["structured_source"]).endswith("2026-04-01.json")
    assert body["daily_brief_report"] is not None
    assert body["daily_brief_report"]["crypto"]["narrative_of_day"] == "BTC 上漲"
    assert body["gate_summary"]["structured_validation"] is not None
    assert body["gate_summary"]["structured_validation"]["valid"] is True


@pytest.mark.smoke
def test_report_structured_invalid_profile(client):
    r = client.get("/api/reports/2026-04-01/structured?profile=not-a-profile")
    assert r.status_code == 400


@pytest.mark.smoke
def test_report_structured_bad_date(client):
    r = client.get("/api/reports/not-a-date/structured")
    assert r.status_code == 400
