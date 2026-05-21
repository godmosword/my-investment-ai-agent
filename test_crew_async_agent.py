"""Crew async_execution must not share one Agent instance (CrewAI executor guard)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crew import _agent_for_async_lane, _crew_agent_roster


class _StubAgent:
    """Minimal stand-in when conftest stubs crewai.Agent."""

    def __init__(self, role: str = "r") -> None:
        self.role = role
        self.agent_executor = object()

    def copy(self) -> "_StubAgent":
        return _StubAgent(self.role)


def test_agent_for_async_lane_returns_distinct_instances() -> None:
    base = _StubAgent("researcher")
    a = _agent_for_async_lane(base, "lane_a")  # type: ignore[arg-type]
    b = _agent_for_async_lane(base, "lane_b")  # type: ignore[arg-type]
    assert a is not base
    assert b is not base
    assert a is not b


def test_crew_agent_roster_dedupes_by_identity() -> None:
    a1 = _StubAgent("a")
    a2 = _StubAgent("b")
    roster = _crew_agent_roster(a1, a2, a1)  # type: ignore[arg-type]
    assert len(roster) == 2


@pytest.mark.smoke
def test_async_lane_clones_via_agent_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    """When real CrewAI Agent is present, copy() must be used (not shared instance)."""
    base = MagicMock()
    base.role = "crypto"
    child_a = MagicMock(agent_executor=None)
    child_b = MagicMock(agent_executor=None)
    base.copy.side_effect = [child_a, child_b]

    out_a = _agent_for_async_lane(base, "a")
    out_b = _agent_for_async_lane(base, "b")
    assert out_a is child_a
    assert out_b is child_b
    assert base.copy.call_count == 2
