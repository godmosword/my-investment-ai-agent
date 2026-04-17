"""Optional single-task Crew for Phase 5b 〔時事多觀點〕 — 不掛載 tools，僅結構化 JSON。"""

from __future__ import annotations

import logging
import os
from textwrap import dedent

from crewai import Agent, Crew, LLM, Process, Task

from crew_output_parse import kickoff_to_pydantic
from schemas import (
    AISection,
    CryptoSection,
    CurrentAffairsRoundtable,
    dashboard_semantic_keys_for_roundtable,
)

logger = logging.getLogger(__name__)

_VERBOSE = os.getenv("CREW_VERBOSE", "").lower() in ("1", "true", "yes")


def _dashboard_excerpt(section: CryptoSection | AISection, *, max_lines: int = 80) -> str:
    lines: list[str] = []
    for row in section.dashboard[:max_lines]:
        if row.is_section_header:
            lines.append(f"[{row.label}]")
        else:
            emoji = (row.status_emoji or "").strip()
            em = f"{emoji} " if emoji else ""
            lines.append(f"{em}{row.label}: {row.value}")
    return "\n".join(lines)


def _news_headlines_excerpt(crypto: CryptoSection, ai: AISection, *, max_each: int = 6) -> str:
    parts: list[str] = []
    for label, items in (("加密", crypto.news[:max_each]), ("AI", ai.news[:max_each])):
        for n in items:
            parts.append(f"〔{label}〕{n.title}")
    return "\n".join(parts)


def _roundtable_llm() -> LLM:
    from config import MODEL_GPT_NANO  # noqa: PLC0415

    return LLM(model=MODEL_GPT_NANO, temperature=0.2)


def _merge_dashboard_anchor_whitelist(
    rt: CurrentAffairsRoundtable,
    crypto: CryptoSection,
    ai: AISection,
) -> CurrentAffairsRoundtable:
    """Expand dashboard_anchors with actual MetricLine labels so evidence_anchor can validate."""
    auto: list[str] = []
    for sec in (crypto, ai):
        for row in sec.dashboard:
            lab = (row.label or "").strip()
            if lab:
                auto.append(lab)
    merged: list[str] = []
    seen: set[str] = set()
    for x in auto + [str(a).strip() for a in rt.dashboard_anchors if str(a).strip()]:
        if x and x not in seen:
            seen.add(x)
            merged.append(x)
    return rt.model_copy(update={"dashboard_anchors": merged[:25]})


def run_current_affairs_roundtable_task(
    *,
    crypto: CryptoSection,
    ai: AISection,
) -> CurrentAffairsRoundtable | None:
    """Return validated roundtable or None on skip / failure (non-blocking for pipeline)."""
    if os.getenv("BRIEF_CURRENT_AFFAIRS", "").strip().lower() not in ("1", "true", "yes"):
        return None

    crypto_dashboard_text = _dashboard_excerpt(crypto)
    ai_dashboard_text = _dashboard_excerpt(ai)
    recent_headlines = _news_headlines_excerpt(crypto, ai)

    llm = _roundtable_llm()
    agent = Agent(
        role="日報時事多觀點編輯（單一結構化輸出）",
        goal="在嚴禁捏造儀表數字的前提下，產出 2–4 則多角色短評與共識／未決。",
        backstory="只根據提供的儀表板文字與標題摘要寫作；evidence_anchor 須為白名單 key 或字面值 N/A。",
        llm=llm,
        tools=[],
        verbose=_VERBOSE,
    )
    prompt = dedent(f"""
        你是機構日報的「時事多觀點」文字對談編輯（非音訊）。

        【紅線】
        - 嚴禁捏造、推算或補齊任何儀表數字。若無法從下方儀表文字對應到具體讀值，evidence_anchor 填 **N/A**（字面值）。
        - 每則 voice 的 viewpoint 為敘事與判斷，不得含新的具體價格／百分比，除非該數字已明確出現在「加密儀表板」或「AI 儀表板」摘錄中。
        - 至少一則 voice 的 disagreement 非空。
        - consensus（一句話）或 unresolved（1–3 短句）至少一類非空。

        【加密儀表板摘錄（區塊①）】
        {crypto_dashboard_text[:6000]}

        【AI 儀表板摘錄（區塊①）】
        {ai_dashboard_text[:6000]}

        【今日新聞標題（僅供敘事主題，勿抄數字）】
        {recent_headlines[:4000]}

        【dashboard_anchors 白名單（優先從下列 key 選 3–8 個寫入 JSON）】
        {dashboard_semantic_keys_for_roundtable(crypto, ai)}
        每個 voice 若有非 N/A 的 evidence_anchor，必須是 dashboard_anchors 中的某一項（或填 N/A）。

        【輸出】僅輸出符合 CurrentAffairsRoundtable schema 的 JSON（不要 markdown fence）。
    """).strip()

    task = Task(
        description=prompt,
        expected_output="CurrentAffairsRoundtable JSON 物件",
        agent=agent,
        output_pydantic=CurrentAffairsRoundtable,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)
    try:
        result = crew.kickoff()
        rt = kickoff_to_pydantic(result, CurrentAffairsRoundtable)
        rt = _merge_dashboard_anchor_whitelist(rt, crypto, ai)
        try:
            return CurrentAffairsRoundtable.model_validate(rt.model_dump(mode="python"))
        except Exception as v_err:
            logger.warning("current_affairs_roundtable post-validate failed: %s", v_err)
            return None
    except Exception as exc:
        logger.warning("current_affairs_roundtable crew skipped: %s", exc)
        return None
