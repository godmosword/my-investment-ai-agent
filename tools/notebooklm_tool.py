"""NotebookLM 工具 Phase 1：預設關閉；介面與 cache 契約預留（見 ``docs/architecture/notebooklm_research.md`` §14）。"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_CACHE: dict[tuple[Any, ...], tuple[str, float]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SEC = 600.0
_CACHE_MAX = 128
_CITATION_RE = re.compile(
    r"\[(?:p\.?|page)\s*(?P<page>\d+)(?::\s*(?P<excerpt>[^\]]+))?\]",
    re.IGNORECASE,
)


def _get_cache(key: tuple[Any, ...]) -> str | None:
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if not hit:
        return None
    val, exp = hit
    if time.monotonic() > exp:
        with _CACHE_LOCK:
            _CACHE.pop(key, None)
        return None
    return val


def _set_cache(key: tuple[Any, ...], value: str) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            oldest = min(_CACHE.items(), key=lambda kv: kv[1][1])[0]
            _CACHE.pop(oldest, None)
        _CACHE[key] = (value, time.monotonic() + _CACHE_TTL_SEC)


def notebooklm_enabled() -> bool:
    return os.getenv("NOTEBOOKLM_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def _resolve_notebook_id(notebook_id: str = "") -> str:
    return (notebook_id or os.getenv("NOTEBOOKLM_NOTEBOOK_ID", "")).strip()


def parse_notebooklm_citations(text: str) -> list[dict[str, Any]]:
    """Extract lightweight [p.12: excerpt] citations from a NotebookLM answer."""
    out: list[dict[str, Any]] = []
    for m in _CITATION_RE.finditer(text or ""):
        page = int(m.group("page"))
        excerpt = (m.group("excerpt") or f"p.{page}").strip()
        out.append({"page": page, "excerpt": excerpt})
    return out


def notebooklm_query(question: str, *, notebook_id: str = "") -> str:
    """同步問答 stub：未接 notebooklm-client 前回傳 DATA_MISSING；預設關閉。"""
    if not notebooklm_enabled():
        return "[DATA_MISSING:notebooklm_disabled]"
    resolved_notebook_id = _resolve_notebook_id(notebook_id)
    if not resolved_notebook_id:
        return "[DATA_MISSING:notebooklm_notebook_id_missing]"
    key = ("notebooklm_q", resolved_notebook_id, (question or "").strip()[:512])
    cached = _get_cache(key)
    if cached is not None:
        return cached
    out = "[DATA_MISSING:notebooklm_not_implemented]"
    _set_cache(key, out)
    logger.info("notebooklm_query stub (Phase 1); NOTEBOOKLM_ENABLED=1 but no client wired")
    return out


def notebooklm_query_many(
    questions: list[str],
    *,
    notebook_id: str = "",
) -> dict[int, dict[str, Any]]:
    """Structured multi-question helper used by graph nodes.

    The live client is intentionally not wired here. Enabled CI paths monkeypatch
    this helper; disabled or missing-id paths return DATA_MISSING records.
    """
    out: dict[int, dict[str, Any]] = {}
    for idx, question in enumerate(questions, start=1):
        answer = notebooklm_query(question, notebook_id=notebook_id)
        out[idx] = {
            "question": question,
            "answer": answer,
            "citations": parse_notebooklm_citations(answer),
        }
    return out
