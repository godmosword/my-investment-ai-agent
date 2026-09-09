"""Repo-root Vercel polyglot contract (GCP exit P2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


@pytest.mark.smoke
def test_root_vercel_json_routes_api_before_spa_catchall():
    cfg = json.loads((_REPO / "vercel.json").read_text(encoding="utf-8"))
    services = cfg["services"]
    assert services["pwa"]["root"] == "data-verification-ui"
    assert services["pwa"]["framework"] == "vite"
    assert services["api"]["root"] == "."
    assert services["api"]["framework"] == "fastapi"
    assert services["api"]["entrypoint"] == "api:app"
    assert "requirements-api.txt" in services["api"]["installCommand"]
    assert cfg["git"]["deploymentEnabled"]["main"] is False

    rewrites = cfg["rewrites"]
    dests = [r["destination"]["service"] for r in rewrites]
    sources = [r["source"] for r in rewrites]
    assert dests[-1] == "pwa"
    assert sources[-1] == "/(.*)"
    api_idx = next(i for i, r in enumerate(rewrites) if r["source"].startswith("/api/"))
    health_idx = next(i for i, r in enumerate(rewrites) if r["source"] == "/healthz")
    catch_idx = len(rewrites) - 1
    assert health_idx < catch_idx
    assert api_idx < catch_idx
    assert dests[api_idx] == "api"
    assert dests[health_idx] == "api"


@pytest.mark.smoke
def test_requirements_api_txt_is_not_the_job_image():
    lines = [
        ln.strip().lower()
        for ln in (_REPO / "requirements-api.txt").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]
    text = "\n".join(lines)
    for banned in (
        "crewai",
        "streamlit",
        "sentence-transformers",
        "google-cloud-bigquery",
        "google-cloud-firestore",
        "litellm",
    ):
        assert banned not in text, f"{banned} must not be in requirements-api.txt"


@pytest.mark.smoke
def test_pwa_deploy_allows_empty_vite_api_url():
    text = (_REPO / ".github/workflows/pwa-deploy.yml").read_text(encoding="utf-8")
    assert "VITE_API_URL empty" in text
    assert "VITE_API_URL secret is required" not in text
    assert "npx vercel@59.13.1" in text
    assert "vercel.json" in text
    assert "requirements-api.txt" in text
    assert "api_routers/**" in text
