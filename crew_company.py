"""
試點：Growth 敘事 crew（Direction 3A）— 產出內部 context，不進 Telegram 正文。

環境變數：COMPANY_CREW_ENABLED=1 啟用（預設關閉，避免加倍管線時間）。
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crewai import Agent, Crew, Process, Task

from crew import _VERBOSE, _get_llms_for_crew
from tools import ai_momentum_tool

logger = logging.getLogger(__name__)

_COMPANY_JSON = Path(__file__).resolve().parent / ".qsilicon" / "company_run_latest.json"


def company_crew_enabled() -> bool:
    return os.getenv("COMPANY_CREW_ENABLED", "").lower() in ("1", "true", "yes")


def _persist_company_snapshot(text: str, meta: dict) -> None:
    try:
        _COMPANY_JSON.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "growth_raw": text[:12000],
            **meta,
        }
        with open(_COMPANY_JSON, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("company crew: wrote %s", _COMPANY_JSON)
    except OSError as e:
        logger.warning("company crew: could not persist snapshot: %s", e)


class GrowthNarrativeCrew:
    """單一 Agent + 單一 Task，僅允許 ai_momentum_tool。"""

    def __init__(self, *, use_fallback_llm: bool = False) -> None:
        llms = _get_llms_for_crew(use_fallback_llm)
        self._agent = Agent(
            role="Growth 敘事觀測員",
            goal="根據 ai_momentum 工具輸出整理繁中 bullet，供主研究管線參考。",
            backstory="嚴禁發明工具未提供的模型名與數字；僅複述與摘要。",
            llm=llms["gemini"],
            tools=[ai_momentum_tool],
            verbose=_VERBOSE,
        )

    def run(self) -> str:
        tz8 = timezone(timedelta(hours=8))
        today = datetime.now(tz8).strftime("%Y-%m-%d")
        task = Task(
            description=(
                f"今天是 {today}（台北）。\n"
                "必須依序呼叫：ai_momentum_tool('downloads') 與 ai_momentum_tool('openrouter_rankings')。\n"
                "輸出 **僅** 以下格式（繁中）：\n"
                "1) 以「Top 模型熱度」為標題，5 條 bullet，每條 ≤45 字，逐字來自工具輸出。\n"
                "2) 以「敘事觀察」為標題，3 條 bullet，說明對交易敘事的影響（仍不得發明數字）。\n"
                "禁止輸出 JSON、禁止 HTML。"
            ),
            expected_output="純文字兩段 bullet。",
            agent=self._agent,
        )
        crew = Crew(agents=[self._agent], tasks=[task], process=Process.sequential)
        return str(crew.kickoff())


def run_growth_narrative_for_context(*, use_fallback_llm: bool = False) -> str | None:
    """執行 Growth crew，回傳可 prepend 到 exclusion context 的文字。"""
    if not company_crew_enabled():
        return None
    try:
        raw = GrowthNarrativeCrew(use_fallback_llm=use_fallback_llm).run()
        text = (raw or "").strip()
        if not text:
            return None
        wrapped = "【Company · Growth 敘事素材（內部，非 Telegram 正文）】\n" + text
        _persist_company_snapshot(text, {"crew": "GrowthNarrativeCrew", "chars": len(text)})
        return wrapped
    except Exception as e:
        logger.warning("GrowthNarrativeCrew failed (non-fatal): %s", e)
        return None


def load_company_war_room_snapshot() -> dict | None:
    """供 Streamlit 唯讀顯示。"""
    if not _COMPANY_JSON.is_file():
        return None
    try:
        with open(_COMPANY_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
