"""CoreWeave GPU pricing fetcher (queue 45 · P2-live PR-B)."""

from __future__ import annotations

import io
import urllib.error
from typing import Any

import pytest

from tools import coreweave_gpu_spot


@pytest.fixture(autouse=True)
def _reset_cache():
    coreweave_gpu_spot.reset_cache_for_tests()
    yield
    coreweave_gpu_spot.reset_cache_for_tests()


def _make_pricing_html() -> str:
    """Minimal HTML mirroring the public page's parseable structure."""
    return """
    <div class="row">NVIDIA HGX H100
        <span class="instance-price">On-Demand Price: </span>$49.24
        <span class="spot-price">Spot Price: </span>$19.71
    </div>
    <div class="row">NVIDIA HGX H200
        <span class="instance-price">On-Demand Price: </span>$50.44
        <span class="spot-price">Spot Price: </span>$20.93
    </div>
    <div class="row">NVIDIA HGX B200
        <span class="instance-price">On-Demand Price: </span>$68.80
        <span class="spot-price">Spot Price: </span>$34.11
    </div>
    <div class="row">NVIDIA A100
        <span class="instance-price">On-Demand Price: </span>$21.60
        <span class="spot-price">Spot Price: </span>$9.65
    </div>
    """


def _fake_response(text: str) -> Any:
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return text.encode("utf-8")

    return _Resp()


def test_fetch_returns_four_skus_on_success(monkeypatch):
    monkeypatch.setattr(
        coreweave_gpu_spot.urllib.request,
        "urlopen",
        lambda *_a, **_k: _fake_response(_make_pricing_html()),
    )

    items = coreweave_gpu_spot.fetch_gpu_pricing()
    assert items is not None
    by_sku = {row["sku"]: row for row in items}
    assert set(by_sku) == {"H100 SXM", "H200 SXM", "B200 HGX", "A100 SXM"}
    assert by_sku["H100 SXM"]["hourly_usd"] == 49.24
    assert by_sku["H100 SXM"]["spot_hourly_usd"] == 19.71
    assert by_sku["B200 HGX"]["hourly_usd"] == 68.80
    assert by_sku["A100 SXM"]["spot_hourly_usd"] == 9.65
    assert all(row["provider"] == "CoreWeave" for row in items)
    assert all(row["source"] == "coreweave_pricing" for row in items)


def test_fetch_returns_none_when_sku_missing(monkeypatch):
    """If even one SKU can't be parsed, the whole batch is rejected (no half-mock)."""
    partial = _make_pricing_html().replace("NVIDIA A100", "NVIDIA A40")
    monkeypatch.setattr(
        coreweave_gpu_spot.urllib.request,
        "urlopen",
        lambda *_a, **_k: _fake_response(partial),
    )
    assert coreweave_gpu_spot.fetch_gpu_pricing() is None


@pytest.mark.parametrize("code", [403, 429, 503])
def test_fetch_returns_none_on_http_error(monkeypatch, code):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(b""))

    monkeypatch.setattr(coreweave_gpu_spot.urllib.request, "urlopen", boom)
    assert coreweave_gpu_spot.fetch_gpu_pricing() is None


def test_fetch_returns_none_on_url_error(monkeypatch):
    monkeypatch.setattr(
        coreweave_gpu_spot.urllib.request,
        "urlopen",
        lambda *_a, **_k: (_ for _ in ()).throw(urllib.error.URLError("DNS")),
    )
    assert coreweave_gpu_spot.fetch_gpu_pricing() is None


def test_cache_skips_network_within_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _fake_response(_make_pricing_html())

    monkeypatch.setattr(coreweave_gpu_spot.urllib.request, "urlopen", fake_urlopen)
    coreweave_gpu_spot.fetch_gpu_pricing()
    coreweave_gpu_spot.fetch_gpu_pricing()
    assert calls["n"] == 1
