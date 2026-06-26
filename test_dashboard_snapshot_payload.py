"""Dashboard snapshot loader parity tests (Streamlit ↔ API shape)."""

from __future__ import annotations

import json

import pytest

from dashboard.snapshot_payload import load_dashboard_symbol_snapshot_payload


class _FakeHttpResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False


@pytest.mark.smoke
def test_dashboard_snapshot_payload_direct_builder_shape() -> None:
    def _build_snapshot(_client, symbol, **_kwargs):
        return {
            "symbol": symbol,
            "latest_metrics": {"avg_risk_score": 2.5},
            "history": [],
            "price_series": [],
            "event_markers": [],
            "recommendations": [],
            "report_links": [],
            "data_provenance": {"daily_metrics": {"source": "bigquery"}},
            "price_alignment": {"aligned": True},
        }

    out = load_dashboard_symbol_snapshot_payload(
        symbol="btc",
        days=30,
        recommendation_limit=12,
        http_base="",
        validate_symbol=lambda s: s.strip().upper(),
        build_snapshot=_build_snapshot,
        client_factory=lambda: object(),
    )
    assert out["symbol"] == "BTC"
    assert "data_provenance" in out
    assert "price_alignment" in out


@pytest.mark.smoke
def test_dashboard_snapshot_payload_http_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = {
        "symbol": "BTC",
        "latest_metrics": {"avg_risk_score": 2.5},
        "history": [],
        "price_series": [],
        "event_markers": [],
        "recommendations": [],
        "report_links": [],
        "data_provenance": {"daily_metrics": {"source": "bigquery"}},
        "price_alignment": {"aligned": False, "quote_error": None},
    }

    def _fake_urlopen(req, timeout=90):  # noqa: ARG001
        assert req.full_url.endswith("/api/symbols/BTC/snapshot?days=30&recommendation_limit=12")
        return _FakeHttpResponse(expected)

    def _unused_build_snapshot(*_args, **_kwargs):
        return {"_should_not": "run"}

    monkeypatch.setattr("dashboard.snapshot_payload.urlopen", _fake_urlopen)

    out = load_dashboard_symbol_snapshot_payload(
        symbol="btc",
        days=30,
        recommendation_limit=12,
        http_base="http://127.0.0.1:8000",
        validate_symbol=lambda s: s.strip().upper(),
        build_snapshot=_unused_build_snapshot,
        client_factory=lambda: object(),
    )
    assert out == expected
