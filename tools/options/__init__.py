"""Polygon options flow + GEX sub-package.

Public surface for Agent / pipeline callers. Implementation lives in:
``client`` (Polygon access + capability probe), ``analyzer`` (GEX + unusual flow),
``pipeline`` (daily entrypoint), ``agent_tools`` (CrewAI tools), ``models``
(Pydantic v2), ``prompts`` (analysis-only LLM prompt).

Red lines: numbers are Python-computed (無數據幻覺); Agent tools go through the
shared tool cache (Tool 快取). See ``docs/AGENT-WORKFLOW.md``.
"""

from __future__ import annotations

from .agent_tools import options_flow_tool, options_gex_tool
from .analyzer import FlowThresholds, UnusualOptionsAnalyzer, calculate_gex
from .client import PolygonAuthError, PolygonOptionsClient
from .models import (
    Capability,
    ContractType,
    GEXResult,
    OptionContract,
    OptionSnapshot,
    OptionTrade,
    PipelineSummary,
    UnderlyingOptionsResult,
    UnusualFlowSignal,
    data_missing,
)
from .pipeline import run_daily_options_pipeline

__all__ = [
    "Capability",
    "ContractType",
    "FlowThresholds",
    "GEXResult",
    "OptionContract",
    "OptionSnapshot",
    "OptionTrade",
    "PipelineSummary",
    "PolygonAuthError",
    "PolygonOptionsClient",
    "UnderlyingOptionsResult",
    "UnusualFlowSignal",
    "UnusualOptionsAnalyzer",
    "calculate_gex",
    "data_missing",
    "options_flow_tool",
    "options_gex_tool",
    "run_daily_options_pipeline",
]
