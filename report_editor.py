"""
日報 HTML 潤稿（Direction 橫切）：render + post_process 之後、validate 之前。

環境變數：
  EDITOR_AGENT_ENABLED=1        啟用（預設關）
  EDITOR_AGENT_MODEL            LiteLLM 模型字串，預設 openai/gpt-4o-mini
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import litellm

logger = logging.getLogger(__name__)

_CODE_BLOCK_RE = re.compile(r"<code>[\s\S]*?</code>", re.IGNORECASE)


def editor_agent_enabled() -> bool:
    return os.getenv("EDITOR_AGENT_ENABLED", "").lower() in ("1", "true", "yes")


def _extract_codes(html: str) -> list[str]:
    return _CODE_BLOCK_RE.findall(html or "")


def _litellm_completion(**kwargs: Any) -> Any:
    return litellm.completion(**kwargs)


def polish_daily_report_html(html: str) -> tuple[str, dict[str, Any]]:
    """
    回傳 (html, meta)。若未啟用、缺 key、或潤稿後 <code> 區塊變動，則回傳原文。
    """
    meta: dict[str, Any] = {"enabled": False, "changed": False, "skipped_reason": None}
    if not editor_agent_enabled():
        meta["skipped_reason"] = "disabled"
        return html, meta

    text = html or ""
    if not text.strip():
        meta["skipped_reason"] = "empty"
        return html, meta

    before_codes = _extract_codes(text)
    meta["enabled"] = True
    meta["code_blocks_before"] = len(before_codes)
    meta["chars_in"] = len(text)

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        meta["skipped_reason"] = "OPENAI_API_KEY missing"
        logger.warning("report_editor: skip — OPENAI_API_KEY missing")
        return html, meta

    model = (os.getenv("EDITOR_AGENT_MODEL") or "openai/gpt-4o-mini").strip()
    # 控制長度避免爆 token
    send = text if len(text) < 28000 else text[:28000] + "\n…[truncated]"

    system = (
        "機構日報 Telegram HTML 資深主編：通讀全文、最終審稿。"
        "潤稿：語氣一致、段落銜接、刪贅字與重複；繁中書面、機構簡報（克制可掃讀）；可調句長標點。"
        "可做：<blockquote>精煉贅詞與順序（不改事實與時間戳）；<b>/<i>位置微調；"
        "四大區塊（儀表板／新聞／評述／操作）敘事拉齊。"
        "紅線—任一違反只回傳 PASS_THROUGH："
        "<code>...</code> 逐字不改；〔新聞 N〕與新聞時間結構不動；"
        "不增刪／推斷報價、%、日期、代號（數字僅留在未改之 <code>）；"
        "HTML 僅 b,i,u,s,code,blockquote,a。"
    )
    user = "輸出潤稿後完整 HTML（標籤種類不變）。無法保證紅線則：PASS_THROUGH\n\n" + send

    try:
        resp = _litellm_completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.25,
            max_tokens=min(16000, len(send) + 2000),
            api_key=api_key,
        )
        choice = resp.choices[0].message.content
        out = (choice or "").strip()
    except Exception as e:
        meta["skipped_reason"] = f"llm_error:{e}"
        logger.warning("report_editor: LLM failed: %s", e)
        return html, meta

    if out == "PASS_THROUGH" or not out:
        meta["skipped_reason"] = "pass_through"
        return html, meta

    after_codes = _extract_codes(out)
    if after_codes != before_codes:
        meta["skipped_reason"] = "code_block_mismatch"
        logger.warning(
            "report_editor: discarded polish — <code> blocks changed (%d -> %d)",
            len(before_codes),
            len(after_codes),
        )
        return html, meta

    meta["changed"] = out != text
    meta["chars_out"] = len(out)
    meta["char_delta"] = len(out) - len(text)
    return out, meta
