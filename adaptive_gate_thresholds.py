"""
Gate 門檻自適應（Direction 2A / P3）：集中讀取可動態調整的閾值。

現況：`ADAPTIVE_GATE_THRESHOLDS=1` 時仍回退至環境變數預設（BQ／pass rate 連動待擴充）。
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def effective_pick_rotation_override_min_gap() -> float:
    """
    同標延續最低分差（PICK_ROTATION_OVERRIDE_MIN_GAP）。
    未來可在此讀取 BigQuery gate_failure_log 聚合後覆寫。
    """
    base = _env_float("PICK_ROTATION_OVERRIDE_MIN_GAP", 12.0)
    if os.getenv("ADAPTIVE_GATE_THRESHOLDS", "0").lower() not in ("1", "true", "yes"):
        return base
    logger.info(
        "ADAPTIVE_GATE_THRESHOLDS=1：pick rotation min gap 仍使用環境預設 %.4f（BQ 自適應尚未接線）",
        base,
    )
    return base
