"""
Gate 門檻自適應（Direction 2A / P3）：集中讀取可動態調整的閾值。

`ADAPTIVE_GATE_THRESHOLDS=1` 時：
- 預設仍以 `PICK_ROTATION_OVERRIDE_MIN_GAP` 為底。
- 若 `ADAPTIVE_GATE_BQ_READ` 未關閉且 BigQuery 可連線，會查詢 `gate_failure_log`
  近 N 日內「疑似 rotation／選標」相關失敗占比；超過門檻且樣本數足夠時，將 gap **加上** `ADAPTIVE_GATE_GAP_BUMP`
  （緩步放寬同標延續難度，降低同類 Gate 連續失敗；數值仍受 `ADAPTIVE_GATE_GAP_CEILING` 上限）。
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


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)), 10)
    except ValueError:
        return default


def _bq_rotation_gap_bump() -> float:
    """Return non-negative delta to add to base min gap when BQ suggests tightening rotation gate."""
    if os.getenv("ADAPTIVE_GATE_BQ_READ", "1").lower() in ("0", "false", "no"):
        return 0.0
    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import bigquery
    except ImportError:
        return 0.0

    try:
        from bigquery_writer import SKIP_BIGQUERY
        from config import GATE_FAILURE_LOG_TABLE, PROJECT_ID
    except ImportError:
        return 0.0

    if SKIP_BIGQUERY:
        return 0.0

    tid = (GATE_FAILURE_LOG_TABLE or "").strip()
    if not tid or tid.count(".") < 2:
        tid = f"{PROJECT_ID}.market_data.gate_failure_log"

    days = max(1, _env_int("ADAPTIVE_GATE_BQ_LOOKBACK_DAYS", 14))
    min_rows = max(1, _env_int("ADAPTIVE_BQ_MIN_FAILURE_ROWS", 5))
    frac_threshold = _env_float("ADAPTIVE_ROTATION_PREVIEW_FRACTION", 0.35)
    bump = max(0.0, _env_float("ADAPTIVE_GATE_GAP_BUMP", 2.0))

    # issues_preview 片段：與 _bucket_gate_issues「trade」桶及 rotation 文案對齊（寬鬆匹配）
    days = min(max(days, 1), 366)
    sql = f"""
    SELECT
      COUNT(*) AS total_n,
      COUNTIF(
        REGEXP_CONTAINS(COALESCE(issues_preview, ''), r'(?i)(同標|重複選用|選標|rotation|STRICT_PICK|差分|持有理由)')
        OR REGEXP_CONTAINS(COALESCE(bucket_counts_json, ''), r'"regime"')
      ) AS rot_n
    FROM `{tid}`
    WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
    """
    try:
        bq_project = tid.split(".", 1)[0]
        client = bigquery.Client(project=bq_project)
        rows = list(client.query(sql).result())
    except DefaultCredentialsError as e:
        logger.info("ADAPTIVE_GATE_THRESHOLDS: BQ read skipped (no credentials): %s", e)
        return 0.0
    except Exception as e:
        logger.warning("ADAPTIVE_GATE_THRESHOLDS: BQ rotation query failed: %s", e)
        return 0.0

    if not rows:
        return 0.0
    row = rows[0]
    total_n = int(row["total_n"] or 0)
    rot_n = int(row["rot_n"] or 0)
    if total_n < min_rows:
        logger.info(
            "ADAPTIVE_GATE_THRESHOLDS: BQ sample too small (n=%s < min_rows=%s); no bump",
            total_n,
            min_rows,
        )
        return 0.0
    ratio = rot_n / total_n if total_n else 0.0
    if ratio < frac_threshold:
        logger.info(
            "ADAPTIVE_GATE_THRESHOLDS: rotation-like fraction %.3f < threshold %.3f; no bump",
            ratio,
            frac_threshold,
        )
        return 0.0
    logger.info(
        "ADAPTIVE_GATE_THRESHOLDS: applying gap bump +%.4f (rotation-like %s/%s=%.3f over %d days)",
        bump,
        rot_n,
        total_n,
        ratio,
        days,
    )
    return bump


def effective_pick_rotation_override_min_gap() -> float:
    """
    同標延續最低分差（PICK_ROTATION_OVERRIDE_MIN_GAP）。
    `ADAPTIVE_GATE_THRESHOLDS=1` 時可疊加 BQ 建議 bump；結果不超過 `ADAPTIVE_GATE_GAP_CEILING`。
    """
    base = _env_float("PICK_ROTATION_OVERRIDE_MIN_GAP", 12.0)
    if os.getenv("ADAPTIVE_GATE_THRESHOLDS", "0").lower() not in ("1", "true", "yes"):
        return base

    bump = _bq_rotation_gap_bump()
    merged = base + bump
    ceiling = _env_float("ADAPTIVE_GATE_GAP_CEILING", 24.0)
    if ceiling > 0 and merged > ceiling:
        logger.info(
            "ADAPTIVE_GATE_THRESHOLDS: merged gap %.4f capped to ceiling %.4f",
            merged,
            ceiling,
        )
        merged = ceiling
    if bump == 0.0:
        logger.info(
            "ADAPTIVE_GATE_THRESHOLDS=1：pick rotation min gap 使用環境預設 %.4f（BQ 無 bump 或已關閉）",
            base,
        )
    return merged
