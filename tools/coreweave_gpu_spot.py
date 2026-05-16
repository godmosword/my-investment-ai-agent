"""CoreWeave public GPU pricing fetcher for the compute/memory dashboard.

Scrapes the public ``coreweave.com/pricing`` page (HTML, no API) and extracts
on-demand + spot hourly $ for the four SKUs exposed by
``/api/macro/compute-memory``. Used only when ``COMPUTE_MEMORY_GPU_LIVE=1``;
failures fall back to the local mock fixture without raising.

Governance entry: ``docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`` §2 / §6.2.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

PRICING_URL = "https://www.coreweave.com/pricing"
_REQUEST_TIMEOUT_SEC = 10.0
_CACHE_TTL_SEC = 3600.0  # 1h; CoreWeave updates pricing infrequently.

# UI SKU → substring used to locate the row in the rendered HTML.
SKU_NEEDLES: list[tuple[str, str]] = [
    ("H100 SXM", "NVIDIA HGX H100"),
    ("H200 SXM", "NVIDIA HGX H200"),
    ("B200 HGX", "NVIDIA HGX B200"),
    ("A100 SXM", "NVIDIA A100"),
]

_CACHE: tuple[list[dict[str, Any]] | None, float] | None = None
_CACHE_LOCK = threading.Lock()


def _user_agent() -> str:
    email = (os.getenv("SEC_EDGAR_CONTACT_EMAIL") or "").strip()
    return f"q-silicon-research/1.0 ({email})" if email else "q-silicon-research/1.0"


def reset_cache_for_tests() -> None:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


def _cache_get() -> list[dict[str, Any]] | None | str:
    with _CACHE_LOCK:
        hit = _CACHE
    if not hit:
        return "MISS"
    val, exp = hit
    if time.monotonic() > exp:
        reset_cache_for_tests()
        return "MISS"
    return val


def _cache_set(value: list[dict[str, Any]] | None) -> None:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = (value, time.monotonic() + _CACHE_TTL_SEC)


def _fetch_html() -> str | None:
    req = urllib.request.Request(PRICING_URL, headers={"User-Agent": _user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        logger.warning("coreweave pricing HTTP %s", exc.code)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("coreweave pricing network error: %s", exc)
        return None


_ON_DEMAND_RE = re.compile(r"On-Demand Price:[^$]{0,200}\$([0-9]+(?:\.[0-9]+)?)")
_SPOT_RE = re.compile(r"Spot Price:[^$]{0,200}\$([0-9]+(?:\.[0-9]+)?)")


def _parse_row(html: str, needle: str) -> tuple[float | None, float | None]:
    idx = html.find(needle)
    if idx < 0:
        return None, None
    window = html[idx : idx + 4000]
    od = _ON_DEMAND_RE.search(window)
    sp = _SPOT_RE.search(window)
    on_demand = float(od.group(1)) if od else None
    spot = float(sp.group(1)) if sp else None
    return on_demand, spot


def fetch_gpu_pricing() -> list[dict[str, Any]] | None:
    """Return list of ``{sku, provider, hourly_usd, spot_hourly_usd, as_of, source}``.

    Returns ``None`` for any failure mode (HTTP error, parse error, no SKUs
    matched). All four SKUs must successfully parse on-demand price; the
    spot price is optional. Numbers are per 8-GPU HGX node (CoreWeave's
    list-price granularity).
    """
    cached = _cache_get()
    if cached != "MISS":
        return cached

    html = _fetch_html()
    if not html:
        _cache_set(None)
        return None

    today_iso = datetime.now(timezone.utc).date().isoformat()
    items: list[dict[str, Any]] = []
    for sku, needle in SKU_NEEDLES:
        on_demand, spot = _parse_row(html, needle)
        if on_demand is None:
            logger.warning("coreweave: could not parse on-demand price for %s", sku)
            _cache_set(None)
            return None
        items.append(
            {
                "sku": sku,
                "provider": "CoreWeave",
                "hourly_usd": on_demand,
                "spot_hourly_usd": spot,
                "regions": [],
                "as_of": today_iso,
                "source": "coreweave_pricing",
                "note": "Per 8-GPU HGX node list price from coreweave.com/pricing.",
            }
        )

    _cache_set(items)
    return items
