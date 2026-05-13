from __future__ import annotations

from fastapi.testclient import TestClient

from api import app


def test_industry_themes_include_rotation_and_additive_fields(monkeypatch, tmp_path):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(tmp_path / "execution_intents.jsonl"))
    client = TestClient(app)

    response = client.get("/api/industries/themes")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "static+execution_intents.jsonl"
    assert body["themes"]
    assert {"id", "label", "symbols", "regime_score", "risk_level", "thesis"}.issubset(body["themes"][0].keys())
    assert body["rotation"]
    scores = [row["regime_score"] for row in body["rotation"]]
    assert scores == sorted(scores, reverse=True)
