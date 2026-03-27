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


def domain_quality_check(report_html: str) -> dict[str, Any]:
    """
    域專用品質檢查（無需 API key，確定性規則）。

    回傳 dict：
      tools        — 5 個新工具是否出現在報告正文
      scenario_legs — 有三情境分析的交易腿數量
      trade_legs   — 總交易腿數量
      has_exec     — 執行摘要是否存在
      source_health — newsapi/gnews/apify 健康分（從報告標頭解析）
      scores       — tools/scenarios/sources/exec 各維度 0–100
      overall      — 加權總分 0–100
    """
    text = report_html or ""

    # ── 新工具出現檢查 ──────────────────────────────────────────────────
    tools: dict[str, bool] = {
        # 📐 相關係數：crew 強制輸出 "📐 BTC 相關係數：BTC/SPX ..."
        "correlation": bool(re.search(r"BTC\s*相關係數|BTC/SPX|📐", text)),
        # 🏦 COT：crew 強制輸出 "🏦 機構周倉位" 或 "CME COT" 或倉位方向箭頭
        "cot":         bool(re.search(r"CME\s*COT|COT|🏦|機構.*倉位|機構.*週[▲▼↑↓]", text)),
        # 📊 估值錨：MVRV/NVT 常見於 dashboard 區塊
        "valuation":   bool(re.search(r"估值錨|MVRV|NVT|📊.*估值", text)),
        # 🕰️ 歷史類比：注意 🕰 (U+1F570) 可能帶 variation selector FE0F
        "historical":  bool(re.search(r"歷史類比|\U0001F570|最近似.*\d{4}|歷史.*相似", text)),
        # 🔒 Grayscale：折溢價通常附 %
        "grayscale":   bool(re.search(r"GBTC|Grayscale|🔒", text)),
    }

    # ── 情境分析覆蓋率 ──────────────────────────────────────────────────
    # Telegram HTML 格式：· <b>$BTC (LONG)</b> — 需跳過 HTML 標籤
    # 用純文字版本（strip tags）做 split，避免 <b> 干擾
    plain = re.sub(r"<[^>]+>", "", text)
    legs = re.split(r"(?=·\s*\$\w+\s*\((?:LONG|SHORT)\))", plain)
    scenario_legs = sum(
        1 for leg in legs
        if re.search(r"🐂", leg) and re.search(r"⚖️", leg) and re.search(r"🐻", leg)
    )
    trade_legs = max(len(legs) - 1, 0)  # legs[0] is pre-trade content

    # trade_legs=0 代表 leg 解析失敗（格式不符），情境分數設中性避免虛高
    scenario_score = (scenario_legs / trade_legs * 100) if trade_legs > 0 else 50.0

    # ── 執行摘要 ────────────────────────────────────────────────────────
    has_exec = bool(re.search(r"執行摘要", text))

    # ── Source Health（從報告 SourceHealth 標頭解析）─────────────────────
    source_health: dict[str, float | None] = {}
    for src in ("newsapi", "gnews", "apify"):
        m = re.search(rf"{src}:([0-9]+\.[0-9]+)", text)
        source_health[src] = float(m.group(1)) if m else None

    # ── 各維度分數（0–100）──────────────────────────────────────────────
    tool_score = sum(tools.values()) / len(tools) * 100
    valid_srcs = [v for v in source_health.values() if v is not None]
    source_score = (sum(valid_srcs) / len(valid_srcs) * 100) if valid_srcs else 50.0
    exec_score = 100.0 if has_exec else 0.0

    # 加權：工具出現 40%、情境分析 30%、來源健康 20%、執行摘要 10%
    overall = round(
        0.40 * tool_score
        + 0.30 * scenario_score
        + 0.20 * source_score
        + 0.10 * exec_score,
        1,
    )

    return {
        "tools":         tools,
        "scenario_legs": scenario_legs,
        "trade_legs":    trade_legs,
        "has_exec":      has_exec,
        "source_health": source_health,
        "scores": {
            "tools":     round(tool_score, 1),
            "scenarios": round(scenario_score, 1),
            "sources":   round(source_score, 1),
            "exec":      exec_score,
        },
        "overall": overall,
    }


def format_quality_card(dqc: dict[str, Any], elapsed_sec: float | None = None) -> str:
    """
    將 domain_quality_check() 結果格式化為可發送到 Telegram 的品質卡 HTML。
    """
    overall = dqc.get("overall", 0.0)
    grade = "🟢" if overall >= 75 else "🟡" if overall >= 55 else "🔴"

    tools = dqc.get("tools", {})
    tool_icons = {
        "correlation": "📐相關係數",
        "cot":         "🏦COT",
        "valuation":   "📊估值錨",
        "historical":  "🕰歷史類比",
        "grayscale":   "🔒Grayscale",
    }
    tool_line = " | ".join(
        f"{'✅' if v else '❌'}{tool_icons[k]}"
        for k, v in tools.items()
    )

    sl = dqc.get("scenario_legs", 0)
    tl = dqc.get("trade_legs", 0)
    if tl == 0:
        # leg 解析失敗（HTML 格式未匹配），顯示為未知而非錯誤數字
        scenario_line = "❓ 情境分析 ?/? 腿（格式未識別）"
    else:
        scenario_line = f"{'✅' if sl == tl else '⚠️'} 情境分析 {sl}/{tl} 腿"

    src = dqc.get("source_health", {})
    src_parts = []
    for s, v in src.items():
        if v is None:
            src_parts.append(f"{s}:N/A")
        elif v >= 0.6:
            src_parts.append(f"✅{s}:{v:.2f}")
        else:
            src_parts.append(f"⚠️{s}:{v:.2f}")
    src_line = " | ".join(src_parts)

    elapsed_line = ""
    if elapsed_sec is not None:
        m, s = divmod(int(elapsed_sec), 60)
        elapsed_line = f"\n⏱ 產報耗時：{m}m{s:02d}s"

    scores = dqc.get("scores", {})
    score_detail = (
        f"工具:{scores.get('tools',0):.0f} "
        f"情境:{scores.get('scenarios',0):.0f} "
        f"來源:{scores.get('sources',0):.0f} "
        f"摘要:{scores.get('exec',0):.0f}"
    )

    return (
        f"{grade} <b>Q-Score: {overall:.0f}/100</b>  "
        f"<code>({score_detail})</code>\n"
        f"{tool_line}\n"
        f"{scenario_line}\n"
        f"📰 {src_line}"
        f"{elapsed_line}"
    )


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
