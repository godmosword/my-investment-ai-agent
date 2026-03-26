"""
版本化 ML／因子權重儲存，供回測產出寫入並可選注入 crew exclusion context。

檔案（預設專案根下 .qsilicon/，可與 .gitignore 對齊）：
  - ml_weights_active.json   當前啟用
  - ml_weights_previous.json 上一版（rollback 用）

環境變數：
  WEIGHTS_CONTEXT_ENABLED=1  在 fetch_exclusion_context 附加權重摘要
  SIGNAL_WEIGHTS_DIR         覆寫目錄（預設 .qsilicon）
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DIR = ".qsilicon"
_ACTIVE_NAME = "ml_weights_active.json"
_PREVIOUS_NAME = "ml_weights_previous.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def weights_dir() -> Path:
    rel = (os.getenv("SIGNAL_WEIGHTS_DIR") or _DEFAULT_DIR).strip()
    return _repo_root() / rel


def active_weights_path() -> Path:
    return weights_dir() / _ACTIVE_NAME


def previous_weights_path() -> Path:
    return weights_dir() / _PREVIOUS_NAME


def load_active_weights() -> dict[str, Any] | None:
    p = active_weights_path()
    if not p.is_file():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("signal_weights: could not load %s: %s", p, e)
        return None


def format_weights_for_crew_context() -> str | None:
    """回傳可 append 到 exclusion context 的一段文字；未啟用或無檔案時 None。"""
    if os.getenv("WEIGHTS_CONTEXT_ENABLED", "").lower() not in ("1", "true", "yes"):
        return None
    data = load_active_weights()
    if not data:
        return None
    w = data.get("weights")
    if not isinstance(w, dict) or not w:
        return None
    lines = [
        "【系統：回測權重快照（僅供敘事參考，不得改寫儀表板數字）】",
        f"版本：{data.get('version', '?')} ｜ 更新：{data.get('updated_at', '?')} ｜ 來源：{data.get('source', 'unknown')}",
    ]
    for k, v in sorted(w.items(), key=lambda x: str(x[0])):
        try:
            fv = float(v)
            lines.append(f"  · {k}: {fv:.4f}")
        except (TypeError, ValueError):
            lines.append(f"  · {k}: {v!r}")
    return "\n".join(lines)


def write_weights(payload: dict[str, Any], *, backup_previous: bool = True) -> Path:
    """
    寫入新權重：可選將現有 active 複製為 previous 再覆寫。
    payload 建議含：version, updated_at, source, weights (dict str->float)
    """
    d = weights_dir()
    d.mkdir(parents=True, exist_ok=True)
    active = active_weights_path()
    prev = previous_weights_path()
    if backup_previous and active.is_file():
        try:
            shutil.copy2(active, prev)
        except OSError as e:
            logger.warning("signal_weights: backup to previous failed: %s", e)
    if "updated_at" not in payload:
        payload = {**payload, "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(active, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("signal_weights: wrote %s (version=%s)", active, payload.get("version"))
    return active


def rollback_weights() -> bool:
    """以 ml_weights_previous.json 覆蓋 active；成功回傳 True。"""
    prev, active = previous_weights_path(), active_weights_path()
    if not prev.is_file():
        logger.warning("signal_weights: rollback skipped — no previous file")
        return False
    try:
        shutil.copy2(prev, active)
        logger.info("signal_weights: rolled back active from previous")
        return True
    except OSError as e:
        logger.error("signal_weights: rollback failed: %s", e)
        return False
