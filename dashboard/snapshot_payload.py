"""Shared Streamlit snapshot loader for dashboard ↔ API shape parity tests."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_dashboard_symbol_snapshot_payload(
    *,
    symbol: str,
    days: int,
    recommendation_limit: int,
    http_base: str,
    validate_symbol: Callable[[str], str],
    build_snapshot: Callable[..., dict[str, object]],
    client_factory: Callable[[], Any],
) -> dict[str, object]:
    """Return the same payload shape as ``GET /api/symbols/{symbol}/snapshot``.

    Streamlit can either:
    - call FastAPI over HTTP when ``SYMBOL_SNAPSHOT_HTTP_BASE`` is configured
    - build the payload locally via ``symbol_snapshot_service.build_symbol_snapshot``

    Both branches should return the same JSON envelope so PWA / Streamlit semantics do not drift.
    """

    from urllib import parse

    sym = validate_symbol(symbol.strip())
    base = (http_base or "").strip().rstrip("/")
    if base:
        q = parse.urlencode(
            {"days": int(days), "recommendation_limit": int(recommendation_limit)}
        )
        url = f"{base}/api/symbols/{parse.quote(sym, safe='')}/snapshot?{q}"
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=90) as resp:
                return json.loads(resp.read().decode())
        except (HTTPError, URLError, ValueError, OSError, json.JSONDecodeError) as exc:
            return {"_error": f"HTTP snapshot failed: {exc}"}

    client = client_factory()
    return build_snapshot(
        client,
        sym,
        days=int(days),
        recommendation_limit=int(recommendation_limit),
    )
