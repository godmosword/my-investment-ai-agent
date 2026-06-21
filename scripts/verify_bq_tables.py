#!/usr/bin/env python3
"""BigQuery optional 表診斷（補齊用，不自動建表）。

列出各 optional 表的 env 設定狀態、DDL 路徑、是否由 writer 自動建表，並在已設且
有憑證時檢查存在/schema/列數。**env 未設＝optional skip，非 deploy blocker。**

用法::

    python scripts/verify_bq_tables.py            # 診斷（已設且有憑證才查 BQ）
    python scripts/verify_bq_tables.py --json      # 機器可讀

退出碼永遠 0（純診斷）；缺表只提示對應 DDL，不阻擋。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# (顯示名, config 屬性名, DDL 路徑, writer 是否自動建表)
TABLE_REGISTRY: list[tuple[str, str, str, bool]] = [
    ("options_snapshots", "OPTIONS_SNAPSHOTS_TABLE", "docs/SQL/options_snapshots.sql", False),
    ("options_unusual_trades", "OPTIONS_UNUSUAL_TRADES_TABLE", "docs/SQL/options_unusual_trades.sql", False),
    ("options_gex_history", "OPTIONS_GEX_HISTORY_TABLE", "docs/SQL/options_gex_history.sql", False),
    ("options_gex_by_strike", "OPTIONS_GEX_BY_STRIKE_TABLE", "docs/SQL/options_gex_by_strike.sql", False),
    ("recommendation_outcomes", "RECOMMENDATION_OUTCOMES_TABLE", "docs/SQL/recommendation_outcomes.sql", True),
    ("paper_execution_audit", "PAPER_EXECUTION_AUDIT_TABLE", "docs/SQL/paper_execution_audit.sql", True),
    ("price_probe_log", "PRICE_PROBE_LOG_TABLE", "docs/SQL/price_probe_log.sql", False),
    ("web_push_subscriptions", "WEB_PUSH_SUBSCRIPTIONS_TABLE", "docs/SQL/web_push_subscriptions.sql", False),
]


def _resolve_table_id(attr: str) -> str:
    import config

    return str(getattr(config, attr, "") or "").strip()


def _bq_check(table_id: str) -> dict:
    """回傳 {status, rows?, fields?}。無憑證/不存在皆 graceful。"""
    try:
        from google.cloud import bigquery

        project = table_id.split(".", 1)[0]
        client = bigquery.Client(project=project)
        t = client.get_table(table_id)
        return {"status": "exists", "rows": t.num_rows, "fields": len(t.schema)}
    except Exception as exc:  # noqa: BLE001 — 缺憑證/不存在/權限皆視為「無法確認」
        msg = str(exc).lower()
        if "not found" in msg or "404" in msg:
            return {"status": "missing"}
        return {"status": "unknown", "detail": str(exc)[:120]}


def build_report(checker=_bq_check) -> list[dict]:
    rows: list[dict] = []
    for name, attr, ddl, auto in TABLE_REGISTRY:
        table_id = _resolve_table_id(attr)
        if not table_id:
            rows.append(
                {
                    "name": name,
                    "env": attr,
                    "configured": False,
                    "status": "unset (optional skip)",
                    "ddl": ddl,
                    "auto_create": auto,
                }
            )
            continue
        check = checker(table_id)
        rows.append(
            {
                "name": name,
                "env": attr,
                "configured": True,
                "table_id": table_id,
                "status": check.get("status"),
                "rows": check.get("rows"),
                "fields": check.get("fields"),
                "ddl": ddl,
                "auto_create": auto,
            }
        )
    return rows


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="BigQuery optional 表診斷")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print("── BigQuery optional 表診斷（未設＝optional skip，不阻擋部署）──")
    for r in report:
        if not r["configured"]:
            note = "（writer 自動建表）" if r["auto_create"] else f"（手動 DDL：{r['ddl']}）"
            print(f"  [skip] {r['name']:<26} env {r['env']} 未設 {note}")
            continue
        status = r["status"]
        if status == "exists":
            print(f"  [ok]   {r['name']:<26} {r['table_id']}  rows={r['rows']} fields={r['fields']}")
        elif status == "missing":
            hint = "writer 會自動建表" if r["auto_create"] else f"套用 {r['ddl']}"
            print(f"  [MISS] {r['name']:<26} {r['table_id']}  → {hint}")
        else:
            print(f"  [?]    {r['name']:<26} {r['table_id']}  無法確認（憑證/權限？）{r.get('detail','')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
