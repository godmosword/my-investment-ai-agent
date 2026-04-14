"""
Q-Silicon run scratchpad（Phase 1：Dexter 式可追溯軌跡）

每次 `main.run_pipeline_with_retries` 建立一個 JSONL 檔，記錄：
  - init / gate_result / run_end / pipeline_error
工具層可選記錄 tool_call / tool_result（見 _scratchpad_traced）。

環境變數：
  SCRATCHPAD_ENABLED=1（預設開啟；設 0/false/no 關閉）
  SCRATCHPAD_DIR=.qsilicon/scratchpad（相對專案根目錄）
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_CURRENT_FILE: Path | None = None
_RUN_ID: str | None = None
_FINALIZED: bool = False
_TOOL_CALL_COUNT: int = 0
_RAW_TOOL_INVOCATIONS: int = 0  # 每次 traced_tool_execution 遞增（不受 SCRATCHPAD 檔案影響）
_TOOL_INVOCATIONS_CRYPTO: int = 0  # kickoff 階段 CryptoResearchCrew（見 set_tool_invocation_lane）
_TOOL_INVOCATIONS_AI: int = 0  # kickoff 階段 AIResearchCrew
_TOOL_LANE_LOCAL = threading.local()
_TOOL_HISTORY: deque[tuple[str, str]] = deque(maxlen=64)
_PIPELINE_T0: float | None = None


def scratchpad_enabled() -> bool:
    return os.getenv("SCRATCHPAD_ENABLED", "1").lower() not in ("0", "false", "no")


def scratchpad_dir() -> Path:
    raw = (os.getenv("SCRATCHPAD_DIR") or ".qsilicon/scratchpad").strip()
    return Path(__file__).resolve().parent / raw


def current_run_id() -> str | None:
    return _RUN_ID


def current_scratchpad_path() -> Path | None:
    return _CURRENT_FILE


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _redact_obj(obj: Any, max_depth: int = 4) -> Any:
    """遞迴縮小並遮蔽疑似敏感欄位，避免 JSONL 外洩金鑰。"""
    if max_depth <= 0:
        return "…"
    sensitive = {"api_key", "apikey", "authorization", "token", "password", "secret"}
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in list(obj.items())[:40]:
            lk = str(k).lower()
            if any(s in lk for s in sensitive):
                out[str(k)] = "[REDACTED]"
            else:
                out[str(k)] = _redact_obj(v, max_depth - 1)
        if len(obj) > 40:
            out["_truncated_keys"] = len(obj) - 40
        return out
    if isinstance(obj, (list, tuple)):
        seq = [_redact_obj(x, max_depth - 1) for x in obj[:30]]
        if len(obj) > 30:
            seq.append(f"…+{len(obj) - 30} items")
        return seq
    if isinstance(obj, str):
        if len(obj) > 800:
            return obj[:800] + "…[truncated]"
        return obj
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return str(obj)[:400]


def _write_event(event_type: str, payload: dict[str, Any]) -> None:
    global _CURRENT_FILE, _RUN_ID
    if not scratchpad_enabled() or _CURRENT_FILE is None:
        return
    line = {
        "type": event_type,
        "timestamp": _utc_now_iso(),
        "runId": _RUN_ID,
        **payload,
    }
    try:
        with _LOCK:
            with open(_CURRENT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("scratchpad write failed: %s", e)


def set_tool_invocation_lane(lane: str | None) -> None:
    """標記目前執行緒的工具呼叫歸屬（crypto／ai），供 MIN_TOOL_CALLS_PER_CREW 統計。prewarm 等請傳 None。"""
    if lane is not None and lane not in ("crypto", "ai"):
        raise ValueError("lane must be 'crypto', 'ai', or None")
    _TOOL_LANE_LOCAL.name = lane


def raw_tool_invocation_count_crypto() -> int:
    """本 run 內、lane=crypto 時經 traced_tool_execution 的呼叫次數。"""
    with _LOCK:
        return _TOOL_INVOCATIONS_CRYPTO


def raw_tool_invocation_count_ai() -> int:
    """本 run 內、lane=ai 時經 traced_tool_execution 的呼叫次數。"""
    with _LOCK:
        return _TOOL_INVOCATIONS_AI


def begin_run(metadata: dict[str, Any] | None = None) -> str | None:
    """
    開始一次新產報 run，建立 JSONL 檔並寫入 init。
    回傳 run_id；關閉或未啟用時回傳 None。
    """
    global _CURRENT_FILE, _RUN_ID, _FINALIZED, _TOOL_CALL_COUNT, _RAW_TOOL_INVOCATIONS
    global _TOOL_INVOCATIONS_CRYPTO, _TOOL_INVOCATIONS_AI, _TOOL_HISTORY, _PIPELINE_T0
    _FINALIZED = False
    _TOOL_CALL_COUNT = 0
    _RAW_TOOL_INVOCATIONS = 0
    _TOOL_INVOCATIONS_CRYPTO = 0
    _TOOL_INVOCATIONS_AI = 0
    _TOOL_HISTORY.clear()
    if not scratchpad_enabled():
        _PIPELINE_T0 = None
        _CURRENT_FILE = None
        _RUN_ID = None
        return None
    _PIPELINE_T0 = time.perf_counter()
    meta = dict(metadata or {})
    rid = f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    d = scratchpad_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("scratchpad mkdir failed: %s", e)
        _CURRENT_FILE = None
        _RUN_ID = None
        return None
    path = d / f"{rid}.jsonl"
    with _LOCK:
        _RUN_ID = rid
        _CURRENT_FILE = path
    _write_event(
        "init",
        {
            "scratchpadFile": str(path),
            "meta": _redact_obj(meta),
        },
    )
    logger.info("Scratchpad init run_id=%s file=%s", rid, path)
    return rid


def log_equity_price_backfill(legs: list[dict[str, Any]]) -> None:
    """Record assemble-time yfinance / R:R synthesis touches (reader-neutral observability)."""
    if not legs:
        return
    _write_event("equity_price_backfill", {"legs": _redact_obj(legs)})


def append_gate_result(attempt: int, result: dict[str, Any] | None) -> None:
    """每次 validate_report 後寫入 gate_result。"""
    if not result:
        return
    issues = result.get("issues") or []
    top = [str(x) for x in issues[:12]]
    blocking = result.get("blocking_issues") or []
    warnings = result.get("warning_issues") or []
    _write_event(
        "gate_result",
        {
            "attempt": attempt,
            "valid": bool(result.get("valid")),
            "news_count": result.get("news_count"),
            "issues_count": len(issues),
            "blocking_count": len(blocking),
            "warning_count": len(warnings),
            "top_issues": top,
        },
    )


def finalize_run(status: str, extra: dict[str, Any] | None = None) -> None:
    """流程結束（成功/失敗/例外）。"""
    global _FINALIZED, _CURRENT_FILE, _RUN_ID, _PIPELINE_T0
    if not scratchpad_enabled():
        with _LOCK:
            _RUN_ID = None
            _CURRENT_FILE = None
        _FINALIZED = True
        _PIPELINE_T0 = None
        return
    with _LOCK:
        if _FINALIZED:
            return
        _FINALIZED = True
    elapsed = None
    if _PIPELINE_T0 is not None:
        elapsed = round(time.perf_counter() - _PIPELINE_T0, 2)
    payload = {"status": status, **(extra or {})}
    if elapsed is not None:
        payload["elapsed_sec"] = elapsed
    _write_event("run_end", payload)
    _PIPELINE_T0 = None
    with _LOCK:
        _RUN_ID = None
        _CURRENT_FILE = None


def log_pipeline_error(message: str) -> None:
    _write_event("pipeline_error", {"message": (message or "")[:2000]})


def log_tool_call(tool_name: str, args: dict[str, Any]) -> None:
    _write_event(
        "tool_call",
        {"toolName": tool_name, "args": _redact_obj(args)},
    )


def log_tool_result(
    tool_name: str,
    *,
    ok: bool,
    elapsed_ms: float,
    summary: str | None = None,
    error: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "toolName": tool_name,
        "ok": ok,
        "elapsed_ms": round(elapsed_ms, 2),
    }
    if summary is not None:
        payload["llmSummary"] = summary[:2000] if summary else ""
    if error is not None:
        payload["error"] = error[:1500]
    _write_event("tool_result", payload)


def append_judge_result(payload: dict[str, Any]) -> None:
    """LLM-as-judge 或品質評分結果（Dexter eval 對齊）。"""
    _write_event("judge_result", {"payload": _redact_obj(payload)})


def append_quality_agent_result(payload: dict[str, Any]) -> None:
    """日報品質代理（REPORT_QUALITY_AGENT）：複合分與 TODOS 後續摘要。"""
    _write_event("quality_agent_result", {"payload": _redact_obj(payload)})


def append_graph_deep_research_metrics(payload: dict[str, Any]) -> None:
    """LangGraph deep_research_node（GRAPH_DEEP_RESEARCH_TOOL_LLM=1）輕量觀測。"""
    _write_event("graph_deep_research_metrics", {"payload": _redact_obj(payload)})


def append_editor_result(payload: dict[str, Any]) -> None:
    """日報潤稿 Agent 結果（meta only，不寫全文）。"""
    _write_event("editor_result", {"payload": _redact_obj(payload)})


def _args_fingerprint(args: dict[str, Any]) -> str:
    try:
        return json.dumps(args, sort_keys=True, default=str)[:800]
    except (TypeError, ValueError):
        return str(hash(frozenset((str(k), str(v)) for k, v in list(args.items())[:50])))


def _tool_guard_check(tool_name: str, args: dict[str, Any]) -> None:
    """單次 run 內工具呼叫上限與連續相同參數偵測（防跑飛）。"""
    global _TOOL_CALL_COUNT
    if not scratchpad_enabled() or _CURRENT_FILE is None:
        return
    try:
        max_calls = int(os.getenv("MAX_TOOL_CALLS_PER_RUN", "80"))
    except ValueError:
        max_calls = 80
    if max_calls > 0:
        _TOOL_CALL_COUNT += 1
        if _TOOL_CALL_COUNT > max_calls:
            raise RuntimeError(
                f"MAX_TOOL_CALLS_PER_RUN exceeded ({max_calls}); aborting to prevent runaway tool loop."
            )
    try:
        thresh = int(os.getenv("REPEATED_CALL_THRESHOLD", "3"))
    except ValueError:
        thresh = 3
    if thresh <= 0:
        return
    fp = (tool_name, _args_fingerprint(args))
    _TOOL_HISTORY.append(fp)
    streak = 0
    for x in reversed(_TOOL_HISTORY):
        if x == fp:
            streak += 1
        else:
            break
    if streak >= thresh:
        raise RuntimeError(
            f"REPEATED_CALL_THRESHOLD: tool {tool_name!r} with same args {streak} times (>= {thresh})."
        )


def raw_tool_invocation_count() -> int:
    """本 run 內經 traced_tool_execution 包裝的工具呼叫次數（含 SCRATCHPAD 關閉時）。"""
    return _RAW_TOOL_INVOCATIONS


def traced_tool_execution(tool_name: str, args: dict[str, Any], fn: Callable[[], str]) -> str:
    """執行 fn() 並記錄 tool_call / tool_result（供 tools.py 使用）。"""
    global _RAW_TOOL_INVOCATIONS, _TOOL_INVOCATIONS_CRYPTO, _TOOL_INVOCATIONS_AI
    lane = getattr(_TOOL_LANE_LOCAL, "name", None)
    with _LOCK:
        _RAW_TOOL_INVOCATIONS += 1
        if lane == "crypto":
            _TOOL_INVOCATIONS_CRYPTO += 1
        elif lane == "ai":
            _TOOL_INVOCATIONS_AI += 1
    _tool_guard_check(tool_name, args)
    if not scratchpad_enabled() or _CURRENT_FILE is None:
        return fn()
    log_tool_call(tool_name, args)
    t0 = time.perf_counter()
    try:
        out = fn()
        elapsed = (time.perf_counter() - t0) * 1000
        summ = (out or "")[:2000]
        log_tool_result(tool_name, ok=True, elapsed_ms=elapsed, summary=summ)
        return out
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        log_tool_result(tool_name, ok=False, elapsed_ms=elapsed, error=str(e))
        raise
