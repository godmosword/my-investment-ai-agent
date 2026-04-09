"""Slim formatter schemas for LangGraph native final formatter.

These models intentionally exclude tool-grounded fields (news, trade legs,
dashboard, qsrec) so the formatter LLM focuses on narrative synthesis only.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CryptoFormatterNarrative(BaseModel):
    """Narrative-only fields that can be derived from internal debate brief."""

    narrative_of_day: str = Field(
        ...,
        description="一句話總結今日主敘事，需與多空共識一致。",
    )
    signal_conflict_summary: str = Field(
        ...,
        description="兩句內交代空方主線與多方主線，避免重複。",
    )
    pick_reason: str = Field(
        ...,
        description="本日選擇理由，聚焦可執行風險回報與催化。",
    )
    risk_budget_summary: str = Field(
        ...,
        description="今日風險預算說明，需給出倉位風險取向。",
    )
    macro_framework_lines: list[str] = Field(
        default_factory=list,
        description="可選：最多四行宏觀框架摘要。",
    )


class AIFormatterNarrative(BaseModel):
    """Narrative-only fields for AI section formatter."""

    signal_conflict_summary: str = Field(
        ...,
        description="兩句內交代空方主線與多方主線，避免重複。",
    )
    pick_reason: str = Field(
        ...,
        description="本日選擇理由，聚焦 AI/美股交易催化與風險。",
    )
    macro_bridge_lines: list[str] = Field(
        default_factory=list,
        description="可選：1-2 行宏觀對 AI 權值連結。",
    )
