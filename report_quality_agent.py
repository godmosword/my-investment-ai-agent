"""
日報產出品質代理（可選）：結構驗證通過後，以 LLM rubric + 域規則加權評分；
低於門檻時將改善項寫入 TODOS.md 機器區塊，並可選 git commit／push。

預設關閉；啟用需 REPORT_QUALITY_AGENT=1。
不修改戰報內文；不取代 validate_report。
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from report_judge import domain_quality_check, llm_quality_judge

logger = logging.getLogger(__name__)

_TODOS_MARK_BEGIN = "<!-- REPORT_QUALITY_AGENT_TODOS_BEGIN -->"
_TODOS_MARK_END = "<!-- REPORT_QUALITY_AGENT_TODOS_END -->"


def _env_truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


_FORMAT_NOISE_EMOJI_RE = re.compile(r"[📈📉🔥🚨💥💣🧨]")


def _formatting_quality_hints(report_html: str) -> list[str]:
    """Lightweight formatter checks aligned with DAILY_BRIEF_V2 mobile reading goals."""
    if not (report_html or "").strip():
        return []
    plain = re.sub(r"<[^>]+>", "", report_html)
    lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
    hints: list[str] = []

    mobile_lines = [
        ln for ln in lines
        if ln.startswith(("·", "→", "本日選擇理由", "今日風險預算", "訊號衝突摘要"))
    ]
    overlong = [ln for ln in mobile_lines if len(ln) > 72]
    if overlong:
        hints.append(f"手機可讀性：有 {len(overlong)} 行超過 72 字，建議分句或軟換行。")

    noisy = [ln for ln in lines if len(_FORMAT_NOISE_EMOJI_RE.findall(ln)) >= 2]
    if noisy:
        hints.append(f"視覺噪音：有 {len(noisy)} 行含 2 個以上高噪音 emoji，建議精簡。")

    sep_count = sum(1 for ln in lines if "────────────" in ln)
    if sep_count > 4:
        hints.append(f"分隔線偏多：偵測 {sep_count} 條，建議控制在 4 條以內。")

    return hints


def _composite_score(
    llm: dict[str, Any],
    dqc: dict[str, Any] | None,
    source: str,
) -> tuple[float | None, str]:
    """
    回傳 (分數, 來源標籤)。LLM 若 raw_error 則不採信其分數。
    """
    src = (source or "dual").strip().lower()
    llm_ok = not (llm.get("raw_error"))
    llm_score = float(llm.get("overall_score") or 0) if llm_ok else None
    dom_score = float(dqc["overall"]) if dqc is not None else None

    if src == "llm":
        return (llm_score, "llm") if llm_score is not None else (None, "llm_skip")
    if src == "domain":
        return (dom_score, "domain") if dom_score is not None else (None, "domain_skip")

    # dual
    if llm_score is not None and dom_score is not None:
        return (round((llm_score + dom_score) / 2.0, 1), "dual_avg")
    if llm_score is not None:
        return (llm_score, "llm_only")
    if dom_score is not None:
        return (dom_score, "domain_only")
    return (None, "none")


def _build_improvement_items(
    llm: dict[str, Any],
    dqc: dict[str, Any] | None,
    formatting_hints: list[str] | None = None,
) -> list[str]:
    items: list[str] = []
    rubric = llm.get("rubric") if isinstance(llm.get("rubric"), dict) else {}
    for dim, sc in rubric.items():
        try:
            fv = float(sc)
        except (TypeError, ValueError):
            continue
        if fv < 60:
            items.append(f"強化「{dim}」維度（rubric {dim}={fv:.0f}）：對照 `docs/DAILY_BRIEF_V2.md` 與 crew 任務輸出範本。")

    for r in llm.get("reasons") or []:
        s = str(r).strip()
        if s and s not in items:
            items.append(s)

    if dqc:
        tools = dqc.get("tools") or {}
        labels = {
            "correlation": "BTC/SPX 相關係數段落",
            "cot": "CME COT／機構倉位段落",
            "valuation": "估值錨（MVRV／NVT 等）",
            "historical": "歷史類比段落",
            "grayscale": "GBTC／Grayscale 折溢價",
        }
        for k, ok in tools.items():
            if ok:
                continue
            label = labels.get(k, k)
            items.append(f"補齊儀表板或內文之 {label}（`report_judge.domain_quality_check` 未偵測）。")

        if not dqc.get("has_exec"):
            items.append("補上「執行摘要」區塊或等效小標，提升可執行性。")

        tl = int(dqc.get("trade_legs") or 0)
        sl = int(dqc.get("scenario_legs") or 0)
        if tl > 0 and sl < tl:
            items.append(f"三情境（🐂⚖️🐻）覆蓋率偏低（{sl}/{tl} 交易腿）；檢視 crew 交易卡模板。")

    for hint in formatting_hints or []:
        if hint:
            items.append(hint)

    # 去重保序
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        key = it[:200]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out[:12]


def _read_todos_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _replace_or_insert_agent_block(full: str, inner_lines: list[str], max_lines: int) -> str:
    """在 TODOS.md 插入或取代 REPORT_QUALITY_AGENT 區塊；超過 max_lines 時自頂裁切。"""
    inner = inner_lines[:]
    while len(inner) > max_lines:
        inner.pop(0)
    block_body = "\n".join(inner)
    block = f"{_TODOS_MARK_BEGIN}\n{block_body}\n{_TODOS_MARK_END}"

    if _TODOS_MARK_BEGIN in full and _TODOS_MARK_END in full:
        pattern = re.compile(
            re.escape(_TODOS_MARK_BEGIN) + r"[\s\S]*?" + re.escape(_TODOS_MARK_END),
            re.MULTILINE,
        )
        return pattern.sub(block.strip(), full, count=1)

    # 插在「下一批隊列」之前，若找不到則附於檔尾
    anchor = "\n## 下一批隊列"
    if anchor in full:
        return full.replace(anchor, f"\n## 日報品質代理 backlog（自動，勿手改區塊內標記）\n\n{block}\n{anchor}", 1)
    return (full.rstrip() + "\n\n## 日報品質代理 backlog（自動，勿手改區塊內標記）\n\n" + block + "\n")


def append_quality_followup_todos(
    todos_path: Path,
    *,
    score: float,
    score_label: str,
    items: list[str],
    max_block_lines: int = 40,
) -> bool:
    """寫入 TODOS.md；回傳是否寫入檔案。"""
    if not items:
        return False
    path = todos_path.resolve()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    bullets = [f"- **[{ts}]** 品質分 {score:.1f}（{score_label}）— {it}" for it in items]
    text = _read_todos_text(path)
    new_text = _replace_or_insert_agent_block(text, bullets, max_block_lines)
    if new_text == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    return True


def _git_commit_and_push(todos_path: Path, score: float, score_label: str) -> None:
    if not _env_truthy("REPORT_QUALITY_AGENT_GIT_PUSH"):
        return
    if not _env_truthy("REPORT_QUALITY_AGENT_GIT_ALLOW"):
        logger.warning(
            "REPORT_QUALITY_AGENT_GIT_PUSH=1 但 REPORT_QUALITY_AGENT_GIT_ALLOW 未設為 1；略過 git 操作。"
        )
        return
    rel = todos_path.resolve().relative_to(_repo_root())
    try:
        subprocess.run(
            ["git", "add", str(rel)],
            cwd=str(_repo_root()),
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        msg = f"chore(quality): TODOS follow-ups from report QA (score={score:.1f} {score_label})"
        subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=str(_repo_root()),
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as e:
        logger.warning("Quality agent git commit failed: %s | %s", e, (e.stderr or "")[:500])
        return
    except FileNotFoundError:
        logger.warning("git not found; skip push")
        return

    try:
        br = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(_repo_root()),
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        branch = (br.stdout or "").strip() or "main"
    except Exception:
        branch = "main"

    try:
        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=str(_repo_root()),
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
        logger.info("Quality agent: pushed TODOS updates to origin/%s", branch)
    except subprocess.CalledProcessError as e:
        logger.warning("Quality agent git push failed: %s | %s", e, (e.stderr or "")[:500])


def maybe_run_report_quality_agent_after_success(
    final_report_html: str,
    *,
    gate_passed: bool,
    validation_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    在 validate_report 乾淨通過（或可接受的 warn-pass）後呼叫。
    回傳摘要 dict 供 log／scratchpad；未啟用時回傳 None。
    """
    if not _env_truthy("REPORT_QUALITY_AGENT"):
        return None
    if not gate_passed:
        return None
    if not (final_report_html or "").strip():
        return None

    t0 = time.monotonic()
    run_domain = _env_truthy("REPORT_QUALITY_AGENT_DOMAIN")
    llm = llm_quality_judge(final_report_html)
    dqc = domain_quality_check(final_report_html) if run_domain else None
    fmt_hints = _formatting_quality_hints(final_report_html)

    source = (os.getenv("REPORT_QUALITY_AGENT_SOURCE") or "dual").strip().lower()
    score, score_label = _composite_score(llm, dqc, source)
    if score is None:
        logger.info("Report quality agent: no composite score (skipped).")
        return None

    try:
        min_score = float(os.getenv("REPORT_QUALITY_AGENT_COMPOSITE_MIN", "72"))
    except ValueError:
        min_score = 72.0

    summary: dict[str, Any] = {
        "composite_score": score,
        "composite_label": score_label,
        "min_score": min_score,
        "below_threshold": score < min_score,
        "llm": {k: llm.get(k) for k in ("pass", "overall_score", "rubric", "reasons", "raw_error")},
        "domain": dqc,
        "formatting_hints": fmt_hints,
        "elapsed_sec": round(time.monotonic() - t0, 3),
    }

    if score >= min_score:
        logger.info(
            "Report quality agent: score=%.1f (%s) >= min=%.1f — no TODOS write.",
            score,
            score_label,
            min_score,
        )
        return summary

    items = _build_improvement_items(llm, dqc, fmt_hints)
    if not items:
        items = [f"綜合分 {score:.1f} 低於門檻 {min_score:.1f}；請檢視本輪 HTML 與 gate 日誌。"]

    todos_path = Path(os.getenv("REPORT_QUALITY_AGENT_TODOS_PATH") or _repo_root() / "TODOS.md")
    try:
        max_lines = int(os.getenv("REPORT_QUALITY_AGENT_TODOS_MAX_LINES") or "40")
    except ValueError:
        max_lines = 40

    wrote = append_quality_followup_todos(
        todos_path,
        score=score,
        score_label=score_label,
        items=items,
        max_block_lines=max_lines,
    )
    summary["todos_written"] = wrote
    summary["todos_path"] = str(todos_path)

    if wrote:
        logger.warning(
            "Report quality agent: score=%.1f (%s) < min=%.1f — wrote %d follow-up(s) to %s",
            score,
            score_label,
            min_score,
            len(items),
            todos_path,
        )
        _git_commit_and_push(todos_path, score, score_label)
    else:
        logger.info("Report quality agent: below threshold but TODOS unchanged (no write).")

    return summary


def quality_agent_summary_for_scratchpad(payload: dict[str, Any] | None) -> dict[str, Any]:
    """精簡寫入 scratchpad 的欄位。"""
    if not payload:
        return {}
    return {
        "composite_score": payload.get("composite_score"),
        "composite_label": payload.get("composite_label"),
        "min_score": payload.get("min_score"),
        "below_threshold": payload.get("below_threshold"),
        "todos_written": payload.get("todos_written"),
        "todos_path": payload.get("todos_path"),
        "elapsed_sec": payload.get("elapsed_sec"),
        "llm_overall": (payload.get("llm") or {}).get("overall_score"),
        "domain_overall": (payload.get("domain") or {}).get("overall"),
    }
