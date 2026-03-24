"""
LLM-as-judge 與硬規則裁判（對齊 Dexter eval 思路）。

- 硬規則：快速擋 API 錯誤洩漏、Traceback 等（原 _codex_judge_pass）。
- 軟評分：可選 litellm 呼叫，預設關閉；開啟時寫入 scratchpad judge_result。
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import litellm

logger = logging.getLogger(__name__)


def _litellm_completion(**kwargs: Any) -> Any:
    """Thin wrapper so tests can patch without resolving litellm re-exports."""
    return litellm.completion(**kwargs)

_HARD_FAIL_PATTERNS = re.compile(
    r"HTTPError|\[DATA_MISSING:|Traceback|Exception:|API key 未設定|Will be right back",
    re.IGNORECASE,
)


def hard_pattern_judge_pass(report_text: str) -> bool:
    """若命中已知洩漏／錯誤字樣，回傳 False（應觸發重試）。"""
    return not bool(_HARD_FAIL_PATTERNS.search(report_text or ""))


def hard_pattern_judge_reason(report_text: str) -> str | None:
    """供除錯：回傳第一個命中片段或 None。"""
    m = _HARD_FAIL_PATTERNS.search(report_text or "")
    return m.group(0) if m else None


def llm_quality_judge(report_html: str) -> dict[str, Any]:
    """
    以 rubric 對戰報做 0–100 評分；回傳 dict：
    pass, overall_score, rubric (dict), reasons (list), raw_error (optional).

    環境變數：
    - REPORT_LLM_JUDGE_MODEL：預設 openai/gpt-4o-mini（LiteLLM 格式）
    - OPENAI_API_KEY：與管線相同
    """
    out: dict[str, Any] = {
        "pass": True,
        "overall_score": 100.0,
        "rubric": {},
        "reasons": [],
        "raw_error": None,
    }
    text = (report_html or "").strip()
    if len(text) > 14000:
        text = text[:14000] + "\n…[truncated for judge]"

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        out["raw_error"] = "OPENAI_API_KEY missing; skip LLM judge"
        return out

    model = (os.getenv("REPORT_LLM_JUDGE_MODEL") or "openai/gpt-4o-mini").strip()

    system = (
        "You are a strict editorial QA judge for an institutional daily brief in Telegram HTML. "
        "Score 0-100 per rubric dimension. Output ONLY valid JSON with keys: "
        "overall_score (number), pass (boolean), rubric (object with keys structure, data_hygiene, "
        "actionability, each 0-100), reasons (array of short strings). "
        "pass should be true only if overall_score>=70 and no dimension below 50."
    )
    user = (
        "Evaluate this report HTML fragment.\n\n" + text
    )

    try:
        resp = _litellm_completion(
            model=model,
            api_key=api_key,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        choice = resp.choices[0].message.content
        if isinstance(choice, list):
            raw = "".join(str(x) for x in choice)
        else:
            raw = str(choice or "")
        parsed = json.loads(raw)
        overall = float(parsed.get("overall_score", 0))
        rubric = parsed.get("rubric") if isinstance(parsed.get("rubric"), dict) else {}
        reasons = parsed.get("reasons") if isinstance(parsed.get("reasons"), list) else []
        p = bool(parsed.get("pass", overall >= 70))
        out["overall_score"] = overall
        out["rubric"] = rubric
        out["reasons"] = [str(x) for x in reasons[:12]]
        out["pass"] = p
    except Exception as e:
        logger.warning("llm_quality_judge failed: %s", e)
        out["pass"] = True
        out["overall_score"] = 100.0
        out["raw_error"] = str(e)[:500]
    return out


def llm_judge_should_block(result: dict[str, Any]) -> bool:
    """REPORT_LLM_JUDGE_BLOCKING=1 且評分未達門檻時為 True。"""
    if os.getenv("REPORT_LLM_JUDGE_BLOCKING", "").lower() not in ("1", "true", "yes"):
        return False
    try:
        min_score = float(os.getenv("REPORT_LLM_JUDGE_MIN_SCORE", "70"))
    except ValueError:
        min_score = 70.0
    if result.get("raw_error"):
        return False
    overall = float(result.get("overall_score") or 0)
    if not result.get("pass") or overall < min_score:
        return True
    return False
