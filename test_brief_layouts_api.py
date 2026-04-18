"""Smoke tests for GET /api/brief-layouts."""

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.smoke
def test_brief_layouts_returns_yaml_inventory(client):
    r = client.get("/api/brief-layouts")
    assert r.status_code == 200
    body = r.json()
    assert "layouts" in body
    assert isinstance(body["layouts"], list)
    names = {item["filename"] for item in body["layouts"]}
    assert "example_lite_reorder.yaml" in names
    assert all("path" in item for item in body["layouts"])
    example = next(i for i in body["layouts"] if i["filename"] == "example_lite_reorder.yaml")
    assert example.get("applies_to_profile") == "lite"
    assert isinstance(example.get("blocks"), list)
    assert "header" in example["blocks"]
    assert "exec_summary" in example["blocks"]
