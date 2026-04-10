"""Market-domain tools (migration target from :mod:`tools_legacy`).

Phase 1 keeps live ``@tool`` callables in legacy, but graph-facing code can use the
lightweight ports/factories here so ``MOCK_APIS`` and future provider swaps do not
leak across every node.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from tools.base import load_mock_json, mock_apis_enabled

MARKET_FIXTURE = "market.json"


def market_fixture_dict() -> dict:
    """When ``MOCK_APIS`` is on, return ``market.json`` as a dict; otherwise ``{}``."""
    if not mock_apis_enabled():
        return {}
    data = load_mock_json(MARKET_FIXTURE)
    return data if isinstance(data, dict) else {}


class MarketSnapshotPort(Protocol):
    def get_snapshot(self, key: str, *args: Any, **kwargs: Any) -> Any: ...


class NewsSourcePort(Protocol):
    def get_news_payload(self, key: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class ToolRegistryPort:
    """Adapter around the current ``tools`` surface with optional fixture overrides."""

    tools_module: Any
    fixture: dict[str, Any]

    def get_snapshot(self, key: str, *args: Any, **kwargs: Any) -> Any:
        fixture_value = self.fixture.get("snapshots", {}).get(key)
        if fixture_value is not None:
            return fixture_value
        tool_obj = getattr(self.tools_module, key)
        runner = getattr(tool_obj, "run", None)
        if callable(runner):
            return runner(*args, **kwargs)
        return tool_obj(*args, **kwargs)

    def get_news_payload(self, key: str, **kwargs: Any) -> Any:
        fixture_value = self.fixture.get("news", {}).get(key)
        if fixture_value is not None:
            return fixture_value
        tool_obj = getattr(self.tools_module, key)
        runner = getattr(tool_obj, "run", None)
        if callable(runner):
            return runner(**kwargs)
        return tool_obj(**kwargs)


def build_tool_registry(tools_module: Any) -> ToolRegistryPort:
    """Return a graph-friendly adapter over ``tools`` with fixture fallback."""
    return ToolRegistryPort(tools_module=tools_module, fixture=market_fixture_dict())
