#!/usr/bin/env python3
"""
Gate 失敗週摘要 → Markdown 草稿（人審用）。

對齊 docs/GATE_FAILURE_HINT_WORKFLOW.md：只產出可貼內部文件的 bullet 草稿，
**不**寫入 repo、不自動改 crew。

用法（須 GCP 憑證，與 write_gate_failure_log 相同專案）：
  python3 scripts/gate_failure_hint_digest.py
  GATE_FAILURE_DIGEST_DAYS=21 python3 scripts/gate_failure_hint_digest.py

SKIP_BIGQUERY=1 或無憑證時：印出說明並以 exit 0 結束（便於 CI 略過）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    os.chdir(_root())
    if os.getenv("SKIP_BIGQUERY", "").lower() in ("1", "true", "yes"):
        print("SKIP_BIGQUERY=1：略過 BQ digest（預期行為）。", file=sys.stderr)
        return 0

    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import bigquery
    except ImportError as e:
        print(f"缺少 google-cloud-bigquery：{e}", file=sys.stderr)
        return 1

    try:
        from config import GATE_FAILURE_LOG_TABLE, PROJECT_ID
    except ImportError:
        sys.path.insert(0, str(_root()))
        from config import GATE_FAILURE_LOG_TABLE, PROJECT_ID  # noqa: PLC0415

    days = 14
    try:
        days = max(1, min(90, int(os.getenv("GATE_FAILURE_DIGEST_DAYS", "14"), 10)))
    except ValueError:
        pass

    tid = (GATE_FAILURE_LOG_TABLE or "").strip()
    if not tid or tid.count(".") < 2:
        tid = f"{PROJECT_ID}.market_data.gate_failure_log"

    sql = f"""
    SELECT
      issues_preview,
      COUNT(*) AS cnt
    FROM `{tid}`
    WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
      AND issues_preview IS NOT NULL AND issues_preview != ''
    GROUP BY 1
    ORDER BY cnt DESC
    LIMIT 25
    """

    try:
        client = bigquery.Client(project=tid.split(".", 1)[0])
        rows = list(client.query(sql).result())
    except DefaultCredentialsError as e:
        print(f"無 ADC／服務帳戶憑證：{e}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"BQ 查詢失敗：{e}", file=sys.stderr)
        return 1

    print(f"# Gate 失敗摘要草稿（近 {days} 日，人審用）\n")
    print("> 來源表：`" + tid + "`\n")
    print("## 高頻 issues_preview（去識別後請再人工過濾）\n")
    if not rows:
        print("_（無列／表空／期間內無寫入）_\n")
        print("## 下一步（人工）\n")
        print("- 確認 `GATE_FAILURE_BQ_LOG=1` 且管線曾寫入失敗列。\n")
        return 0

    for i, row in enumerate(rows, 1):
        prev = str(row["issues_preview"] or "").replace("\n", " ")[:240]
        print(f"{i}. （×{row['cnt']}） `{prev}`")
    print("\n## 下一步（人工）\n")
    print("- 將反模式寫成 bullet → **審核後**再改 `crew.py`／`validation_rules.py`／`report_html_gates.py`。\n")
    print("- 詳見 `docs/GATE_FAILURE_HINT_WORKFLOW.md`。\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
