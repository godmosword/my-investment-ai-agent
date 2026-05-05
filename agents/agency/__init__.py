"""Agency 模板載入（Phase 1）：預設不啟用研究路徑；見 ``docs/architecture/agency_agents_research.md`` §12。"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_AGENCY_DIR = Path(__file__).resolve().parent


def agency_research_enabled() -> bool:
    return os.getenv("AGENCY_RESEARCH_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def _load_agency_template(relative_path: str) -> str:
    """讀取 ``agents/agency/`` 下 markdown；失敗回空字串（供上層 fallback）。"""
    if not agency_research_enabled():
        return ""
    try:
        p = (_AGENCY_DIR / relative_path).resolve()
        if not str(p).startswith(str(_AGENCY_DIR)):
            return ""
        if not p.is_file():
            logger.warning("agency template missing: %s", relative_path)
            return ""
        return p.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("agency template read failed %s: %s", relative_path, exc)
        return ""
