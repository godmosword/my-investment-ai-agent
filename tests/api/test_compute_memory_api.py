"""Compute / memory dashboard fixture endpoint (queue 45 · P2-mock)."""

from __future__ import annotations

import json

import pytest

from api_routers import macro as macro_router
from tests.api.helpers import make_api_client


@pytest.fixture()
def client(monkeypatch):
    macro_router._compute_memory_reset_cache_for_tests()
    return make_api_client(monkeypatch)


def test_compute_memory_returns_enabled_false_when_fixture_missing(client, monkeypatch, tmp_path):
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(tmp_path / "nope.json"))
    r = client.get("/api/macro/compute-memory")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["reason"] == "fixture_missing"


def test_compute_memory_returns_enabled_false_on_invalid_json(client, monkeypatch, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    r = client.get("/api/macro/compute-memory")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["reason"] == "fixture_invalid"


def test_compute_memory_returns_enabled_false_on_top_level_array(client, monkeypatch, tmp_path):
    path = tmp_path / "arr.json"
    path.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    r = client.get("/api/macro/compute-memory")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["reason"] == "fixture_invalid"


def test_compute_memory_returns_three_blocks_from_fixture(client, monkeypatch, tmp_path):
    path = tmp_path / "good.json"
    path.write_text(
        json.dumps(
            {
                "as_of": "2026-05-16",
                "live": False,
                "disclaimer": "test mock",
                "hbm_dram_spot": {"as_of": "2026-05-16", "source": "mock", "items": [{"product": "HBM3"}]},
                "hyperscaler_capex": {"as_of": "2026-Q1", "source": "mock", "items": [{"ticker": "MSFT"}]},
                "gpu_spot": {"as_of": "2026-05-16", "source": "mock", "items": [{"sku": "H100 SXM"}]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    r = client.get("/api/macro/compute-memory")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["as_of"] == "2026-05-16"
    assert body["live"] is False
    assert body["disclaimer"] == "test mock"
    assert body["hbm_dram_spot"]["items"][0]["product"] == "HBM3"
    assert body["hyperscaler_capex"]["items"][0]["ticker"] == "MSFT"
    assert body["gpu_spot"]["items"][0]["sku"] == "H100 SXM"


def test_compute_memory_live_flag_requires_both_env_and_fixture(client, monkeypatch, tmp_path):
    """``live: true`` only when fixture says so AND ``COMPUTE_MEMORY_LIVE=1``."""
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps({"as_of": "2026-05-16", "live": True, "hbm_dram_spot": {}, "hyperscaler_capex": {}, "gpu_spot": {}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))

    # Fixture says live=true but env not set → still mock.
    monkeypatch.delenv("COMPUTE_MEMORY_LIVE", raising=False)
    macro_router._compute_memory_reset_cache_for_tests()
    body = client.get("/api/macro/compute-memory").json()
    assert body["enabled"] is True and body["live"] is False

    # Env on AND fixture flag on → live.
    monkeypatch.setenv("COMPUTE_MEMORY_LIVE", "1")
    macro_router._compute_memory_reset_cache_for_tests()
    body = client.get("/api/macro/compute-memory").json()
    assert body["live"] is True


def test_capex_live_uses_sec_edgar_when_flag_on(client, monkeypatch, tmp_path):
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps(
            {
                "as_of": "2026-05-16",
                "hbm_dram_spot": {"items": []},
                "hyperscaler_capex": {"items": [{"ticker": "MSFT", "source": "mock"}]},
                "gpu_spot": {"items": []},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    monkeypatch.setenv("COMPUTE_MEMORY_CAPEX_LIVE", "1")

    from tools import sec_edgar_capex

    live_items = [
        {"ticker": t, "quarter": "2026-Q1", "capex_b_usd": 10.0, "as_of": "2025-09-30", "source": "sec_edgar"}
        for t in sec_edgar_capex.HYPERSCALER_CIKS
    ]
    monkeypatch.setattr(sec_edgar_capex, "fetch_all_hyperscaler_capex", lambda: live_items)

    macro_router._compute_memory_reset_cache_for_tests()
    body = client.get("/api/macro/compute-memory").json()
    assert body["live_block_status"]["capex"] == "live"
    assert body["live_block_status"]["hbm"] == "mock"
    assert body["live_block_status"]["gpu"] == "mock"
    assert body["hyperscaler_capex"]["source"] == "sec_edgar"
    assert {row["ticker"] for row in body["hyperscaler_capex"]["items"]} >= {"MSFT", "GOOG"}


def test_capex_live_falls_back_to_fixture_when_fetch_fails(client, monkeypatch, tmp_path):
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps(
            {
                "hbm_dram_spot": {"items": []},
                "hyperscaler_capex": {"source": "mock", "items": [{"ticker": "MSFT"}]},
                "gpu_spot": {"items": []},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    monkeypatch.setenv("COMPUTE_MEMORY_CAPEX_LIVE", "1")

    from tools import sec_edgar_capex

    monkeypatch.setattr(sec_edgar_capex, "fetch_all_hyperscaler_capex", lambda: None)

    macro_router._compute_memory_reset_cache_for_tests()
    body = client.get("/api/macro/compute-memory").json()
    assert body["live_block_status"]["capex"] == "fallback"
    assert body["hyperscaler_capex"]["source"] == "mock"


def test_gpu_live_uses_coreweave_when_flag_on(client, monkeypatch, tmp_path):
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps(
            {
                "hbm_dram_spot": {"items": []},
                "hyperscaler_capex": {"items": []},
                "gpu_spot": {"source": "mock", "items": [{"sku": "H100 SXM"}]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    monkeypatch.setenv("COMPUTE_MEMORY_GPU_LIVE", "1")

    from tools import coreweave_gpu_spot

    live_items = [
        {"sku": "H100 SXM", "provider": "CoreWeave", "hourly_usd": 49.24, "as_of": "2026-05-16", "source": "coreweave_pricing"},
        {"sku": "H200 SXM", "provider": "CoreWeave", "hourly_usd": 50.44, "as_of": "2026-05-16", "source": "coreweave_pricing"},
        {"sku": "B200 HGX", "provider": "CoreWeave", "hourly_usd": 68.80, "as_of": "2026-05-16", "source": "coreweave_pricing"},
        {"sku": "A100 SXM", "provider": "CoreWeave", "hourly_usd": 21.60, "as_of": "2026-05-16", "source": "coreweave_pricing"},
    ]
    monkeypatch.setattr(coreweave_gpu_spot, "fetch_gpu_pricing", lambda: live_items)

    macro_router._compute_memory_reset_cache_for_tests()
    body = client.get("/api/macro/compute-memory").json()
    assert body["live_block_status"]["gpu"] == "live"
    assert body["gpu_spot"]["source"] == "coreweave_pricing"
    assert body["gpu_spot"]["items"][0]["hourly_usd"] == 49.24


def test_gpu_live_falls_back_when_fetch_fails(client, monkeypatch, tmp_path):
    path = tmp_path / "fallback.json"
    path.write_text(
        json.dumps(
            {
                "hbm_dram_spot": {"items": []},
                "hyperscaler_capex": {"items": []},
                "gpu_spot": {"source": "mock", "items": [{"sku": "H100 SXM"}]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    monkeypatch.setenv("COMPUTE_MEMORY_GPU_LIVE", "1")

    from tools import coreweave_gpu_spot

    monkeypatch.setattr(coreweave_gpu_spot, "fetch_gpu_pricing", lambda: None)

    macro_router._compute_memory_reset_cache_for_tests()
    body = client.get("/api/macro/compute-memory").json()
    assert body["live_block_status"]["gpu"] == "fallback"
    assert body["gpu_spot"]["source"] == "mock"


def test_capex_live_off_keeps_mock_status(client, monkeypatch, tmp_path):
    path = tmp_path / "good.json"
    path.write_text(
        json.dumps({"hbm_dram_spot": {}, "hyperscaler_capex": {"source": "mock"}, "gpu_spot": {}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    monkeypatch.delenv("COMPUTE_MEMORY_CAPEX_LIVE", raising=False)
    macro_router._compute_memory_reset_cache_for_tests()
    body = client.get("/api/macro/compute-memory").json()
    assert body["live_block_status"]["capex"] == "mock"


def test_compute_memory_caches_within_ttl(client, monkeypatch, tmp_path):
    path = tmp_path / "good.json"
    path.write_text(json.dumps({"hbm_dram_spot": {}, "hyperscaler_capex": {}, "gpu_spot": {}}), encoding="utf-8")
    monkeypatch.setenv("COMPUTE_MEMORY_FIXTURE_FILE", str(path))
    r1 = client.get("/api/macro/compute-memory").json()
    r2 = client.get("/api/macro/compute-memory").json()
    assert r1.get("cached") is False
    assert r2.get("cached") is True
