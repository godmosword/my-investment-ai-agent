"""Contract for T5b read-only gate × intent index (queue 36)."""

from __future__ import annotations




def test_gate_intent_index_shape(client):
    r = client.get("/api/execution-intents/gate-index")
    assert r.status_code == 200
    body = r.json()
    assert body.get("schema_version") == "qsi_gate_intent_index_v1"
    assert isinstance(body.get("matches"), list)
    assert isinstance(body.get("gate_issue_preview"), list)
    assert body.get("intent_scanned") is not None
    assert body.get("intent_rows_with_hints") is not None
