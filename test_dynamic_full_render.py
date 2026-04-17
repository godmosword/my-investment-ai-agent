"""Phase 4d: optional YAML-driven dynamic full render (BRIEF_DYNAMIC_RENDER=1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_render import render_telegram_daily_brief
from test_validate_report import _make_minimal_structured_report_dbr

_ROOT = Path(__file__).resolve().parent
_FULL_REORDER = _ROOT / "config" / "brief_layouts" / "example_full_reorder_header_exec.yaml"


@pytest.mark.smoke
def test_dynamic_full_reorder_exec_before_header(monkeypatch):
    monkeypatch.setenv("BRIEF_LAYOUT_FILE", str(_FULL_REORDER.relative_to(_ROOT)))
    monkeypatch.setenv("BRIEF_DYNAMIC_RENDER", "1")
    monkeypatch.delenv("BRIEF_CURRENT_AFFAIRS", raising=False)
    report = _make_minimal_structured_report_dbr()
    html = render_telegram_daily_brief(report, profile="full")
    i_scan = html.find("掃讀順序")
    i_title = html.find("Q-Silicon Institutional Research")
    assert i_scan >= 0 and i_title >= 0
    assert i_scan < i_title
