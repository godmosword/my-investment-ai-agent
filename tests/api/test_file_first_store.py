"""File/JSONL-first reports, metrics, and trades — GCP-exit P1."""

from __future__ import annotations

import json

import pytest

from tests.api.helpers import make_api_client, write_jsonl_rows


def _isolate(tmp_path, monkeypatch):
    state = tmp_path / "state"
    briefs = tmp_path / "briefs"
    state.mkdir()
    briefs.mkdir()
    monkeypatch.setenv("QSILICON_STATE_DIR", str(state))
    monkeypatch.setenv("DAILY_BRIEF_JSON_DIR", str(briefs))
    return state, briefs


@pytest.mark.smoke
def test_reports_list_empty_when_skip_bigquery(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/reports?limit=5")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.smoke
def test_reports_list_from_daily_brief_json(tmp_path, monkeypatch):
    from test_validate_report import _make_minimal_structured_report_dbr

    _isolate(tmp_path, monkeypatch)
    report_date = "2026-05-09"
    payload = _make_minimal_structured_report_dbr().model_dump(mode="json")
    (tmp_path / "briefs" / f"{report_date}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/reports?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["report_date"] == report_date
    assert body[0]["grok_summary"] == "BTC 上漲"


@pytest.mark.smoke
def test_report_detail_from_json_attaches_qsrec(tmp_path, monkeypatch):
    from test_validate_report import _make_minimal_structured_report_dbr

    _isolate(tmp_path, monkeypatch)
    report_date = "2026-05-09"
    payload = _make_minimal_structured_report_dbr().model_dump(mode="json")
    (tmp_path / "briefs" / f"{report_date}.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get(f"/api/reports/{report_date}")
    assert response.status_code == 200
    body = response.json()
    assert body["report_date"] == report_date
    assert body["recommendations"][0]["asset"] == "BTC"
    assert body["recommendations"][0]["entry_price"] == 94500


@pytest.mark.smoke
def test_report_detail_missing_is_404_not_503(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/reports/2099-01-01")
    assert response.status_code == 404


@pytest.mark.smoke
def test_reports_list_from_metrics_jsonl(tmp_path, monkeypatch):
    state, _briefs = _isolate(tmp_path, monkeypatch)
    write_jsonl_rows(
        state / "daily_metrics.jsonl",
        [
            {
                "timestamp": "2026-05-09T02:31:00+00:00",
                "dxy": 104.1,
                "grok_summary": "risk-on",
                "gpt_summary": "balanced",
            }
        ],
    )
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/reports?limit=1")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["report_date"] == "2026-05-09"
    assert body[0]["dxy"] == pytest.approx(104.1)
    assert body[0]["grok_summary"] == "risk-on"


@pytest.mark.smoke
def test_metrics_latest_from_jsonl(tmp_path, monkeypatch):
    state, _briefs = _isolate(tmp_path, monkeypatch)
    write_jsonl_rows(
        state / "daily_metrics.jsonl",
        [
            {
                "timestamp": "2026-05-08T02:00:00+00:00",
                "dxy": 103.0,
            },
            {
                "timestamp": "2026-05-09T02:00:00+00:00",
                "dxy": 104.0,
            },
        ],
    )
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/metrics/latest")
    assert response.status_code == 200
    body = response.json()
    assert body["dxy"] == pytest.approx(104.0)
    assert body["delta_dxy"] == pytest.approx(1.0)


@pytest.mark.smoke
def test_metrics_latest_empty_is_404_when_skip_bq(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/metrics/latest")
    assert response.status_code == 404


@pytest.mark.smoke
def test_trades_list_from_jsonl(tmp_path, monkeypatch):
    state, _briefs = _isolate(tmp_path, monkeypatch)
    write_jsonl_rows(
        state / "trade_recommendations.jsonl",
        [
            {
                "report_date": "2026-09-08",
                "asset": "ETH",
                "direction": "LONG",
                "status": "OPEN",
                "entry_price": 3200,
                "confidence": 3,
            }
        ],
    )
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/trades?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body[0]["asset"] == "ETH"
    assert body[0]["status"] == "OPEN"


@pytest.mark.smoke
def test_trades_empty_when_skip_bigquery(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/trades?limit=10")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.smoke
def test_trades_performance_empty_when_skip_bigquery(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = make_api_client(monkeypatch, SKIP_BIGQUERY="1")
    response = client.get("/api/trades/performance?days=30")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["by_category"] == []
    assert body["equity_curve"] == []
