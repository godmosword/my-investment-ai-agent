"""Market-domain tools (migration target from :mod:`tools_legacy`).

Phase 1 only exposes fixture helpers; live ``@tool`` callables remain in legacy until moved.
"""

from __future__ import annotations

from tools.base import load_mock_json, mock_apis_enabled

MARKET_FIXTURE = "market.json"


def market_fixture_dict() -> dict:
    """When ``MOCK_APIS`` is on, return ``market.json`` as a dict; otherwise ``{}``."""
    if not mock_apis_enabled():
        return {}
    data = load_mock_json(MARKET_FIXTURE)
    return data if isinstance(data, dict) else {}
