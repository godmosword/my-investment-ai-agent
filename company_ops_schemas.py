"""Structured payloads for multi-department / Arbiter war-room (Direction 3).

Avoid `schemas/` package — it would shadow root `schemas.py` (DailyBriefReport).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DepartmentMemo(BaseModel):
    """單一職能部門備忘（不得包含可驗證報價捏造；敘事層級）。"""

    department: Literal["product", "growth", "finance", "engineering", "editorial"]
    summary: str = Field(..., max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    open_questions: list[str] = Field(default_factory=list, max_length=12)


class ArbiterInput(BaseModel):
    memos: list[DepartmentMemo] = Field(min_length=1, max_length=16)


class ArbiterResolution(BaseModel):
    """仲裁輸出：優先序與衝突點，不覆寫工具層數字。"""

    headline: str = Field(..., max_length=500)
    priorities: list[str] = Field(default_factory=list, max_length=8)
    conflicts: list[str] = Field(default_factory=list, max_length=8)
    needs_data: list[str] = Field(default_factory=list, max_length=8)
