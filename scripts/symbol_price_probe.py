#!/usr/bin/env python3
"""實盤觀測：BigQuery snapshot（含建議列）與 yfinance OHLC／quote 對照；可選寫入 BQ 日誌表。

用法::

    python scripts/symbol_price_probe.py BTC
    PRICE_PROBE_WRITE_BQ=1 PRICE_PROBE_LOG_TABLE=proj.dataset.price_alignment_probe_log \\
        python scripts/symbol_price_probe.py SPY

環境變數見 ``ENV_TEMPLATE.txt``（``PRICE_PROBE_*``）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _truthy(k: str) -> bool:
    return (os.getenv(k) or "").strip().lower() in ("1", "true", "yes")


def main() -> int:
    parser = argparse.ArgumentParser(description="BQ snapshot vs yfinance OHLC/quote probe")
    parser.add_argument("symbol", help="Ticker e.g. BTC, SPY, NVDA")
    parser.add_argument("--days", type=int, default=30, help="OHLC lookback days")
    args = parser.parse_args()

    from google.cloud import bigquery

    from config import PROJECT_ID, RECOMMENDATIONS_TABLE
    from symbol_snapshot_service import (
        build_symbol_snapshot,
        fetch_symbol_ohlc,
        fetch_symbol_quote,
        validate_symbol_for_snapshot,
        _align_snapshot_price,
    )

    sym = validate_symbol_for_snapshot(args.symbol)

    yf_ohlc = fetch_symbol_ohlc(sym, days=args.days)
    bar = yf_ohlc[-1] if yf_ohlc else None
    yf_close = float(bar["close"]) if bar and bar.get("close") is not None else None
    bar_date = str(bar.get("time")) if bar else None

    quote_row = fetch_symbol_quote(sym)
    yf_last = float(quote_row["last"]) if quote_row.get("last") is not None and not quote_row.get("error") else None

    align = _align_snapshot_price(sym, yf_ohlc)

    try:
        client = bigquery.Client(project=PROJECT_ID)
        snap = build_symbol_snapshot(client, sym, days=args.days, recommendation_limit=5)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"symbol": sym, "error": str(exc)}, indent=2))
        return 1

    latest_metrics = snap.get("latest_metrics") or {}
    extra_field = (os.getenv("PRICE_PROBE_BQ_METRIC") or "").strip()
    bq_value = None
    if extra_field and extra_field in latest_metrics:
        v = latest_metrics.get(extra_field)
        try:
            bq_value = float(v) if v is not None else None
        except (TypeError, ValueError):
            bq_value = None

    rec_entry = None
    qsql = f"""
        SELECT report_date, entry_price, asset
        FROM `{RECOMMENDATIONS_TABLE}`
        WHERE UPPER(asset) = @sym
        ORDER BY report_date DESC
        LIMIT 1
    """
    job = client.query(
        qsql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("sym", "STRING", sym)]
        ),
    )
    rows = list(job.result())
    if rows:
        r0 = rows[0]
        rec_entry = {
            "report_date": str(r0.get("report_date") or ""),
            "entry_price": float(r0["entry_price"]) if r0.get("entry_price") is not None else None,
        }

    out = {
        "probe_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "symbol": sym,
        "yf_ohlc_close": yf_close,
        "yf_ohlc_bar_date": bar_date,
        "yf_quote_last": yf_last,
        "price_alignment": align,
        "bq_latest_metrics_timestamp": latest_metrics.get("timestamp"),
        "bq_echo_metric": extra_field or None,
        "bq_echo_value": bq_value,
        "bq_latest_recommendation": rec_entry,
        "note": (
            "price_alignment：yfinance OHLC 尾端 vs yfinance /quote；"
            "bq_latest_recommendation.entry_price 為歷史建議價（語意不同於即時 last）。"
        ),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))

    if _truthy("PRICE_PROBE_WRITE_BQ"):
        table = (os.getenv("PRICE_PROBE_LOG_TABLE") or "").strip()
        if not table:
            print("PRICE_PROBE_WRITE_BQ=1 but PRICE_PROBE_LOG_TABLE empty — skip BQ write", file=sys.stderr)
            return 0
        try:
            entry = (rec_entry or {}).get("entry_price")
            row = {
                "probe_ts": out["probe_ts"],
                "symbol": sym,
                "bq_metric_field": extra_field or "recommendation_entry_price",
                "bq_value": entry if entry is not None else bq_value,
                "bq_as_of": None,
                "yf_ohlc_close": yf_close,
                "yf_ohlc_bar_date": bar_date,
                "yf_quote_last": yf_last,
                "abs_diff": align.get("abs_diff"),
                "rel_diff": align.get("rel_diff"),
                "aligned": align.get("aligned"),
                "note": out["note"][:450],
            }
            errs = client.insert_rows_json(table, [row])
            if errs:
                print(f"BQ insert errors: {errs}", file=sys.stderr)
                return 1
            print(f"Wrote 1 row to {table}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"BQ write failed: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
